"""Public renderer entry point. Tries the SVG path first, falls back to
Playwright HTML→PNG if the new pipeline misbehaves on edge data.

Per ADR-007 the migration is two-stage: SVG becomes primary now, the
Playwright path stays around as a safety net for one or two iterations
and gets removed once the SVG output has run in production without
issues. Public API (RenderRequest, render_chart_png, close_browser) is
unchanged so handlers don't need to know which backend rendered them.
"""

import asyncio
from pathlib import Path
from typing import Final

import jinja2
import structlog
from playwright.async_api import Browser, Playwright, async_playwright

from ai.svg_renderer import RenderRequest
from ai.svg_renderer import render_chart_png as _render_via_svg

logger = structlog.get_logger(__name__)

_LEGACY_TEMPLATE_DIR: Final = Path(__file__).resolve().parent.parent / "web" / "templates"
_legacy_jinja_env: Final = jinja2.Environment(
    loader=jinja2.FileSystemLoader(_LEGACY_TEMPLATE_DIR),
    autoescape=True,
)

_browser: Browser | None = None
_playwright: Playwright | None = None
_browser_lock = asyncio.Lock()

__all__ = ["RenderRequest", "close_browser", "render_chart_png"]


async def render_chart_png(req: RenderRequest) -> bytes:
    try:
        return await asyncio.to_thread(_render_via_svg, req)
    except Exception:
        logger.exception("card_renderer.svg_failed_falling_back_to_playwright")
        return await _render_via_playwright(req)


async def close_browser() -> None:
    """Idempotent shutdown — safe to call even if Playwright was never
    spawned (the SVG path doesn't need it)."""
    global _browser, _playwright
    async with _browser_lock:
        if _browser is not None:
            await _browser.close()
            _browser = None
        if _playwright is not None:
            await _playwright.stop()
            _playwright = None


# ── Playwright legacy fallback ───────────────────────────────────────────────
#
# Kept until ADR-007 migration completes (1.7.10). Uses the v1 chart.html
# template, which is itself deprecated; once removed, this entire block goes
# away and card_renderer.py collapses to a one-liner over svg_renderer.

_LEGACY_STEM_EL: Final[dict[str, str]] = {
    "甲": "wood",
    "乙": "wood",
    "丙": "fire",
    "丁": "fire",
    "戊": "earth",
    "己": "earth",
    "庚": "metal",
    "辛": "metal",
    "壬": "water",
    "癸": "water",
}
_LEGACY_BRANCH_EL: Final[dict[str, str]] = {
    "寅": "wood",
    "卯": "wood",
    "巳": "fire",
    "午": "fire",
    "辰": "earth",
    "戌": "earth",
    "丑": "earth",
    "未": "earth",
    "申": "metal",
    "酉": "metal",
    "亥": "water",
    "子": "water",
}
_LEGACY_DM_RU: Final[dict[str, str]] = {
    "甲": "Дерево Ян",
    "乙": "Дерево Инь",
    "丙": "Огонь Ян",
    "丁": "Огонь Инь",
    "戊": "Земля Ян",
    "己": "Земля Инь",
    "庚": "Металл Ян",
    "辛": "Металл Инь",
    "壬": "Вода Ян",
    "癸": "Вода Инь",
}
_LEGACY_EL_RU: Final[dict[str, str]] = {
    "木": "Дерево",
    "火": "Огонь",
    "土": "Земля",
    "金": "Металл",
    "水": "Вода",
}
_LEGACY_EL_CLASS: Final[dict[str, str]] = {
    "木": "wood",
    "火": "fire",
    "土": "earth",
    "金": "metal",
    "水": "water",
}
_LEGACY_PILLAR_LABELS: Final[dict[str, str]] = {
    "year": "Год",
    "month": "Месяц",
    "day": "День",
    "hour": "Час",
}


async def _render_via_playwright(req: RenderRequest) -> bytes:
    html = _legacy_jinja_env.get_template("chart.html").render(_legacy_build_context(req))
    browser = await _get_legacy_browser()
    page = await browser.new_page(viewport={"width": 800, "height": 1200})
    try:
        await page.set_content(html, wait_until="networkidle")
        await page.evaluate("document.fonts.ready")
        element = await page.query_selector("#chart-card")
        if element is None:
            raise RuntimeError("chart-card element not found in rendered HTML")
        png: bytes = await element.screenshot(type="png", omit_background=True)
        return png
    finally:
        await page.close()


def _legacy_build_context(req: RenderRequest) -> dict[str, object]:
    chart = req.chart
    pillars_to_show = chart.pillars if req.has_birth_time else chart.pillars[:3]
    pillars_data: list[dict[str, object]] = []
    for pillar in pillars_to_show:
        hidden = chart.hidden_stems.get(pillar.name, [])
        ten_gods = chart.ten_gods.get(pillar.name, [])
        ten_god_stem = ten_gods[0] if ten_gods else ""
        pillars_data.append(
            {
                "label": _LEGACY_PILLAR_LABELS.get(pillar.name, pillar.name),
                "stem": pillar.stem,
                "branch": pillar.branch,
                "stem_el": _LEGACY_STEM_EL[pillar.stem],
                "branch_el": _LEGACY_BRANCH_EL[pillar.branch],
                "ten_god_stem": ten_god_stem,
                "hidden_str": "·".join(hidden) if hidden else "",
                "ten_god_hidden": "·".join(ten_gods[1:]) if len(ten_gods) > 1 else "",
                "is_day": pillar.name == "day",
            }
        )

    balance_rows: list[dict[str, object]] = []
    for glyph in ("木", "火", "土", "金", "水"):
        pct = chart.element_balance.get(glyph, 0.0)
        balance_rows.append(
            {
                "glyph": glyph,
                "name_ru": _LEGACY_EL_RU[glyph],
                "el_class": _LEGACY_EL_CLASS[glyph],
                "pct": round(pct * 100, 1),
                "pct_str": f"{round(pct * 100):d}%",
            }
        )

    return {
        "title": req.title,
        "subtitle": req.subtitle,
        "num_pillars": len(pillars_to_show),
        "pillars": pillars_data,
        "day_master": chart.day_master,
        "day_master_ru": _LEGACY_DM_RU.get(chart.day_master, ""),
        "dm_element_class": _LEGACY_STEM_EL[chart.day_master],
        "balance": balance_rows,
    }


async def _get_legacy_browser() -> Browser:
    global _browser, _playwright
    async with _browser_lock:
        if _browser is None:
            _playwright = await async_playwright().start()
            _browser = await _playwright.chromium.launch(headless=True)
            logger.info("card_renderer.legacy_browser_launched")
        return _browser
