"""SVG → PNG rendering for Bazi charts.

Pipeline: Jinja2 fills the SVG template, CairoSVG rasterises to PNG. No
headless browser, no Chromium, no fonts loaded over the network — the
template references system CJK fonts (PingFang SC on macOS, Noto Sans SC
on Linux Docker) and falls back to serif if neither is available.

This module is the primary path; ai/card_renderer.py keeps a Playwright
fallback for the duration of the migration (ADR-007).
"""

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import cairosvg
import jinja2
import structlog

from calculator.models import ChartOutput

logger = structlog.get_logger(__name__)

_TEMPLATE_DIR: Final = Path(__file__).resolve().parent.parent / "web" / "templates"
_jinja_env: Final = jinja2.Environment(
    loader=jinja2.FileSystemLoader(_TEMPLATE_DIR),
    autoescape=jinja2.select_autoescape(["html", "xml", "svg", "j2"]),
)

# Element / yin-yang lookup tables ─────────────────────────────────────────────

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
_STEM_YIN_YANG_RU: Final[dict[str, str]] = {
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
_BRANCH_YIN_YANG_RU: Final[dict[str, str]] = {
    "子": "Вода Ян",
    "丑": "Земля Инь",
    "寅": "Дерево Ян",
    "卯": "Дерево Инь",
    "辰": "Земля Ян",
    "巳": "Огонь Инь",
    "午": "Огонь Ян",
    "未": "Земля Инь",
    "申": "Металл Ян",
    "酉": "Металл Инь",
    "戌": "Земля Ян",
    "亥": "Вода Инь",
}
_BRANCH_ANIMAL_RU: Final[dict[str, str]] = {
    "子": "Крыса",
    "丑": "Бык",
    "寅": "Тигр",
    "卯": "Кролик",
    "辰": "Дракон",
    "巳": "Змея",
    "午": "Лошадь",
    "未": "Коза",
    "申": "Обезьяна",
    "酉": "Петух",
    "戌": "Собака",
    "亥": "Свинья",
}
_PILLAR_LABEL_RU: Final[dict[str, str]] = {
    "year": "ГОД",
    "month": "МЕСЯЦ",
    "day": "ДЕНЬ",
    "hour": "ЧАС",
}
_ELEMENT_GLYPH_TO_CLASS: Final[dict[str, str]] = {
    "木": "wood",
    "火": "fire",
    "土": "earth",
    "金": "metal",
    "水": "water",
}
_ELEMENT_GLYPH_TO_RU: Final[dict[str, str]] = {
    "木": "Дерево",
    "火": "Огонь",
    "土": "Земля",
    "金": "Металл",
    "水": "Вода",
}
_WUXING_ORDER: Final[tuple[str, ...]] = ("木", "火", "土", "金", "水")


@dataclass(frozen=True)
class RenderRequest:
    chart: ChartOutput
    title: str
    subtitle: str
    has_birth_time: bool


def render_chart_png(req: RenderRequest, *, scale: float = 1.0) -> bytes:
    """Render a chart to PNG bytes via SVG.

    `scale` controls output DPI. 1.0 = 1200x1100 native, 2.0 = 2400x2200
    (good for retina). Telegram caps photo at 10 MB and downscales preview
    on its own, so 1.0 is fine.
    """
    svg = _jinja_env.get_template("chart.svg.j2").render(_build_context(req))
    png: bytes = cairosvg.svg2png(
        bytestring=svg.encode("utf-8"),
        output_width=int(1200 * scale),
        output_height=int(1100 * scale),
    )
    return png


def render_chart_svg(req: RenderRequest) -> str:
    """Same template, but returns raw SVG markup. Used for unit tests
    (snapshot diff is more useful than PNG byte hashing)."""
    svg: str = _jinja_env.get_template("chart.svg.j2").render(_build_context(req))
    return svg


def _build_context(req: RenderRequest) -> dict[str, object]:
    chart = req.chart
    chart_pillars = list(chart.pillars) if req.has_birth_time else list(chart.pillars[:3])
    # Mingli convention: hour first, then day, month, year (right-to-left in
    # Chinese ledgers, but we run LTR for Russian readers). Calculator emits
    # year→month→day→hour, so reverse what we have.
    display_order = list(reversed(chart_pillars))

    pillars_data: list[dict[str, object]] = []
    for pillar in display_order:
        hidden = chart.hidden_stems.get(pillar.name, [])
        ten_gods_for_pillar = chart.ten_gods.get(pillar.name, [])
        ten_god_stem = ten_gods_for_pillar[0] if ten_gods_for_pillar else ""
        pillars_data.append(
            {
                "label": _PILLAR_LABEL_RU.get(pillar.name, pillar.name.upper()),
                "stem": pillar.stem,
                "branch": pillar.branch,
                "stem_el": _STEM_ELEMENT[pillar.stem],
                "branch_el": _BRANCH_ELEMENT[pillar.branch],
                "stem_yin_yang": _STEM_YIN_YANG_RU[pillar.stem],
                "branch_yin_yang": _BRANCH_YIN_YANG_RU[pillar.branch],
                "branch_animal": _BRANCH_ANIMAL_RU[pillar.branch],
                "ten_god_stem": ten_god_stem,
                "hidden_str": "·".join(hidden) if hidden else "—",
                "is_day": pillar.name == "day",
            }
        )

    balance_rows: list[dict[str, object]] = []
    for glyph in _WUXING_ORDER:
        pct = chart.element_balance.get(glyph, 0.0)
        balance_rows.append(
            {
                "glyph": glyph,
                "name_ru": _ELEMENT_GLYPH_TO_RU[glyph],
                "el_class": _ELEMENT_GLYPH_TO_CLASS[glyph],
                "pct": pct * 100,
                "pct_int": round(pct * 100),
            }
        )

    dm_element_class = _STEM_ELEMENT[chart.day_master]
    chart_kind = "карта на 4 столпа" if req.has_birth_time else "3 столпа (без часа)"

    return {
        "title": req.title,
        "subtitle": req.subtitle,
        "pillars": pillars_data,
        "day_master": chart.day_master,
        "day_master_ru": _STEM_YIN_YANG_RU.get(chart.day_master, ""),
        "dm_element_class": dm_element_class,
        "chart_kind": chart_kind,
        "balance": balance_rows,
        "wuxing": _wuxing_wheel(dm_element_class),
    }


def _wuxing_wheel(dm_class: str) -> list[dict[str, object]]:
    """Five-element pentagon: vertices at 90° + 72°·i, radius 95.

    The day-master element gets `is_dm=True` so the template can highlight
    it (full opacity + glow ring). Others stay dim.
    """
    radius = 95
    elements: list[dict[str, object]] = []
    for i, glyph in enumerate(_WUXING_ORDER):
        angle = math.radians(-90 + i * 72)
        elements.append(
            {
                "glyph": glyph,
                "cls": _ELEMENT_GLYPH_TO_CLASS[glyph],
                "cx": round(radius * math.cos(angle)),
                "cy": round(radius * math.sin(angle)),
                "is_dm": _ELEMENT_GLYPH_TO_CLASS[glyph] == dm_class,
            }
        )
    return elements
