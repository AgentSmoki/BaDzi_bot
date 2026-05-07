"""Render a Bazi chart to a PNG via headless Chromium.

A single Browser instance is reused for the lifetime of the process —
chromium boot is ~300 ms, screenshotting an element afterwards is
~50-150 ms. The browser is lazy-initialised on first call so import
stays cheap; bot.main shutdown closes it via close_browser().
"""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import jinja2
import structlog
from playwright.async_api import Browser, Playwright, async_playwright

from calculator.models import ChartOutput

logger = structlog.get_logger(__name__)

_TEMPLATE_DIR: Final = Path(__file__).resolve().parent.parent / "web" / "templates"
_jinja_env: Final = jinja2.Environment(
    loader=jinja2.FileSystemLoader(_TEMPLATE_DIR),
    autoescape=True,
)

_STEM_ELEMENT: Final[dict[str, str]] = {
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
_BRANCH_ELEMENT: Final[dict[str, str]] = {
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
_DAY_MASTER_RU: Final[dict[str, str]] = {
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
_ELEMENT_RU: Final[dict[str, str]] = {
    "木": "Дерево",
    "火": "Огонь",
    "土": "Земля",
    "金": "Металл",
    "水": "Вода",
}
_ELEMENT_CLASS: Final[dict[str, str]] = {
    "木": "wood",
    "火": "fire",
    "土": "earth",
    "金": "metal",
    "水": "water",
}
_PILLAR_LABELS: Final[dict[str, str]] = {
    "year": "Год",
    "month": "Месяц",
    "day": "День",
    "hour": "Час",
}

_browser: Browser | None = None
_playwright: Playwright | None = None
_browser_lock = asyncio.Lock()


@dataclass(frozen=True)
class RenderRequest:
    chart: ChartOutput
    title: str
    subtitle: str
    has_birth_time: bool


async def render_chart_png(req: RenderRequest) -> bytes:
    html = _jinja_env.get_template("chart.html").render(_build_context(req))
    browser = await _get_browser()
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


def _build_context(req: RenderRequest) -> dict[str, object]:
    pillars_data = []
    chart = req.chart
    pillars_to_show = chart.pillars if req.has_birth_time else chart.pillars[:3]
    for pillar in pillars_to_show:
        hidden = chart.hidden_stems.get(pillar.name, [])
        ten_gods_for_pillar = chart.ten_gods.get(pillar.name, [])
        ten_god_stem = ten_gods_for_pillar[0] if ten_gods_for_pillar else ""
        ten_god_hidden = "·".join(ten_gods_for_pillar[1:]) if len(ten_gods_for_pillar) > 1 else ""
        pillars_data.append(
            {
                "label": _PILLAR_LABELS.get(pillar.name, pillar.name),
                "stem": pillar.stem,
                "branch": pillar.branch,
                "stem_el": _STEM_ELEMENT[pillar.stem],
                "branch_el": _BRANCH_ELEMENT[pillar.branch],
                "ten_god_stem": ten_god_stem,
                "hidden_str": "·".join(hidden) if hidden else "",
                "ten_god_hidden": ten_god_hidden,
                "is_day": pillar.name == "day",
            }
        )

    balance_rows = []
    for glyph in ("木", "火", "土", "金", "水"):
        pct = chart.element_balance.get(glyph, 0.0)
        balance_rows.append(
            {
                "glyph": glyph,
                "name_ru": _ELEMENT_RU[glyph],
                "el_class": _ELEMENT_CLASS[glyph],
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
        "day_master_ru": _DAY_MASTER_RU.get(chart.day_master, ""),
        "dm_element_class": _STEM_ELEMENT[chart.day_master],
        "balance": balance_rows,
    }


async def _get_browser() -> Browser:
    global _browser, _playwright
    async with _browser_lock:
        if _browser is None:
            _playwright = await async_playwright().start()
            _browser = await _playwright.chromium.launch(headless=True)
            logger.info("card_renderer.browser_launched")
        return _browser


async def close_browser() -> None:
    global _browser, _playwright
    async with _browser_lock:
        if _browser is not None:
            await _browser.close()
            _browser = None
        if _playwright is not None:
            await _playwright.stop()
            _playwright = None
