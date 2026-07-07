"""SVG → PNG rendering for Bazi charts.

Pipeline: Jinja2 fills the SVG template, CairoSVG rasterises to PNG. No
headless browser, no Chromium, no fonts loaded over the network — the
template references system CJK fonts (PingFang SC on macOS, Noto Sans SC
on Linux Docker) and falls back to serif if neither is available.

Primary entry points:
- ``render_chart_png`` / ``render_chart_svg`` — synchronous, suitable
  for tests, scripts, and pool workers.
- ``render_chart_png_async`` — schedules the sync render in the shared
  ProcessPoolExecutor (ai/_render_pool.py); use this from handlers.

Per ADR-007 this is the only render path — the Playwright fallback was
retired in 1.7.10.
"""

import math
import os
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


_CANVAS_W: Final = 1200
_CANVAS_H: Final = 1400


def render_chart_png(req: RenderRequest, *, scale: float = 1.0) -> bytes:
    """Render a chart to PNG bytes via SVG.

    `scale` controls output DPI. 1.0 = 1200x1380 native, 2.0 = 2400x2760
    (good for retina). Telegram caps photo at 10 MB and downscales preview
    on its own, so 1.0 is fine.
    """
    svg = _jinja_env.get_template("chart.svg.j2").render(_build_context(req))
    # BAZI_DEBUG_DUMP_SVG=1 dumps the exact SVG the bot just rendered so it can
    # be diffed against direct-call output when investigating regressions.
    if os.environ.get("BAZI_DEBUG_DUMP_SVG") == "1":
        # /tmp is intentional: developer-only diagnostic, gated behind an env
        # flag, never enabled in production.
        Path("/tmp/last_chart.svg").write_text(svg, encoding="utf-8")  # noqa: S108
    png: bytes = cairosvg.svg2png(
        bytestring=svg.encode("utf-8"),
        output_width=int(_CANVAS_W * scale),
        output_height=int(_CANVAS_H * scale),
    )
    return png


def render_chart_svg(req: RenderRequest) -> str:
    """Same template, but returns raw SVG markup. Used for unit tests
    (snapshot diff is more useful than PNG byte hashing)."""
    svg: str = _jinja_env.get_template("chart.svg.j2").render(_build_context(req))
    return svg


async def render_chart_png_async(req: RenderRequest, *, scale: float = 1.0) -> bytes:
    """Async wrapper that runs ``render_chart_png`` in the shared
    ProcessPoolExecutor. Use this from the bot/web handlers — the sync
    function is only meant for tests, scripts, and pool workers."""
    from ai._render_pool import run_in_pool

    result: bytes = await run_in_pool(render_chart_png, req, scale=scale)
    return result


def _build_context(req: RenderRequest) -> dict[str, object]:
    chart = req.chart
    # Always render four columns. Hour pillar becomes a muted placeholder when
    # no birth time was provided — visually present but greyed out, so the
    # canvas layout is identical for every chart.
    pillars_data = _build_pillars(chart, req.has_birth_time)

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


def _build_pillars(chart: ChartOutput, has_birth_time: bool) -> list[dict[str, object]]:
    # Mingli convention: hour first, then day, month, year (right-to-left in
    # Chinese ledgers; we run LTR for Russian readers but keep the canonical
    # order). Calculator emits year→month→day→hour, so reverse for display.
    display_order = list(reversed(chart.pillars))
    pillars_data: list[dict[str, object]] = []
    for pillar in display_order:
        if pillar.name == "hour" and not has_birth_time:
            pillars_data.append({"empty": True, "label": _PILLAR_LABEL_RU["hour"], "is_day": False})
            continue
        hidden = chart.hidden_stems.get(pillar.name, [])
        ten_gods_for_pillar = chart.ten_gods.get(pillar.name, [])
        ten_god_stem = ten_gods_for_pillar[0] if ten_gods_for_pillar else ""
        # Position 1-3 hidden stems horizontally inside the pillar (270 wide).
        # Empty list keeps the slot but renders an em-dash.
        pillar_w = 270
        if not hidden:
            hidden_list: list[dict[str, object]] = []
        else:
            slot_w = pillar_w / len(hidden)
            hidden_list = [
                {
                    "char": stem,
                    "el": _STEM_ELEMENT[stem],
                    "yin_yang": _STEM_YIN_YANG_RU[stem],
                    "x": round(slot_w * (idx + 0.5), 1),
                }
                for idx, stem in enumerate(hidden)
            ]
        pillars_data.append(
            {
                "empty": False,
                "label": _PILLAR_LABEL_RU.get(pillar.name, pillar.name.upper()),
                "stem": pillar.stem,
                "branch": pillar.branch,
                "stem_el": _STEM_ELEMENT[pillar.stem],
                "branch_el": _BRANCH_ELEMENT[pillar.branch],
                "stem_yin_yang": _STEM_YIN_YANG_RU[pillar.stem],
                "branch_yin_yang": _BRANCH_YIN_YANG_RU[pillar.branch],
                "branch_animal": _BRANCH_ANIMAL_RU[pillar.branch],
                "ten_god_stem": ten_god_stem,
                "hidden_list": hidden_list,
                "is_day": pillar.name == "day",
            }
        )
    return pillars_data


# Generation cycle order — Wood feeds Fire feeds Earth feeds Metal feeds Water
# feeds Wood. The wheel rotates this list so the day master sits at the top,
# and the rest of the pentagon falls into the standard 5-role layout.
_GENERATION_ORDER: Final[tuple[str, ...]] = ("wood", "fire", "earth", "metal", "water")
_ROLES_RU: Final[tuple[str, ...]] = (
    "Личность, друзья",  # 0: day master itself
    "Самовыражение",  # 1: DM generates this
    "Богатство, жена",  # 2: DM controls this (wealth)
    "Власть, муж",  # 3: this controls DM (power)
    "Ресурсы",  # 4: this generates DM (resources)
)
_ELEMENT_EMOJI: Final[dict[str, str]] = {
    "wood": "🌳",
    "fire": "🔥",
    "earth": "⛰",
    "metal": "⚙",
    "water": "💧",
}
# Element colours mirror the .el-{el} CSS rules so the arrow gradients
# transition smoothly from one element's signature colour into the next.
_ELEMENT_COLOR: Final[dict[str, str]] = {
    "wood": "#5fa86a",
    "fire": "#d04a3a",
    "earth": "#a06030",
    "metal": "#7a8190",
    "water": "#3a78c4",
}


def _tip_path(
    end_x: float,
    end_y: float,
    tux: float,
    tuy: float,
    pux: float,
    puy: float,
    *,
    length: float,
    half_w: float,
    concavity: float = 0.32,
) -> str:
    """Return an SVG ``d`` attribute for a calligraphic-brush arrowhead.

    Long, narrow triangle (tip at ``(end_x, end_y)``, base offset
    *length* px backward along the tangent and spread ``half_w`` px to
    either side) with quadratic-Bezier *concave* sides. The
    ``concavity`` factor pulls each side's mid-point toward the
    arrowhead's centre axis by ``concavity * half_w`` — that's what
    gives the silhouette the swept-in look of a Chinese ink-brush
    stroke instead of a generic triangle.
    """
    base_cx = end_x - length * tux
    base_cy = end_y - length * tuy
    bl_x = base_cx + half_w * pux
    bl_y = base_cy + half_w * puy
    br_x = base_cx - half_w * pux
    br_y = base_cy - half_w * puy
    inset = concavity * half_w
    mid_left_x = (end_x + bl_x) / 2 - inset * pux
    mid_left_y = (end_y + bl_y) / 2 - inset * puy
    mid_right_x = (end_x + br_x) / 2 + inset * pux
    mid_right_y = (end_y + br_y) / 2 + inset * puy
    return (
        f"M {end_x:.1f},{end_y:.1f} "
        f"Q {mid_left_x:.1f},{mid_left_y:.1f} {bl_x:.1f},{bl_y:.1f} "
        f"L {br_x:.1f},{br_y:.1f} "
        f"Q {mid_right_x:.1f},{mid_right_y:.1f} {end_x:.1f},{end_y:.1f} Z"
    )


def _wuxing_wheel(dm_class: str) -> dict[str, object]:
    """Pentagon arrangement of the five elements with day master at the top.

    Returns a dict containing:
    - elements: 5-list of dicts with cx/cy, label position+anchor, role, is_dm
    - arrows: list of generation-cycle line segments connecting consecutive
      vertices clockwise (Wood→Fire→Earth→Metal→Water→Wood relative to
      whichever element the day master is)
    - icon_radius: radius of the element circle, exposed for the template
    """
    radius = 130
    icon_radius = 36
    label_dist = 180

    dm_idx = _GENERATION_ORDER.index(dm_class)
    cycle = list(_GENERATION_ORDER[dm_idx:]) + list(_GENERATION_ORDER[:dm_idx])

    # Accumulate raw coordinates first so arrow geometry can be computed
    # without round-tripping through the typed dict.
    coords: list[tuple[float, float]] = []
    elements: list[dict[str, object]] = []
    for i, el in enumerate(cycle):
        angle = math.radians(-90 + i * 72)
        cx = radius * math.cos(angle)
        cy = radius * math.sin(angle)
        coords.append((cx, cy))
        label_cx = label_dist * math.cos(angle)
        label_cy = label_dist * math.sin(angle)

        if i == 0:
            anchor = "middle"
            # The top label sits above a 78px DM emoji on a 64px disc, so it
            # needs a generous gap to avoid clipping into the glyph itself.
            label_cy -= 22
        elif i in (1, 2):
            anchor = "start"
        else:
            anchor = "end"

        elements.append(
            {
                "el": el,
                "role": _ROLES_RU[i],
                "emoji": _ELEMENT_EMOJI[el],
                "cx": round(cx, 1),
                "cy": round(cy, 1),
                "label_cx": round(label_cx, 1),
                "label_cy": round(label_cy + 5, 1),
                "label_anchor": anchor,
                "is_dm": i == 0,
            }
        )

    # The day master sits inside a 54-px dashed halo (template draws it on
    # top of the 36-px element disc); every other element only has its
    # 32-px disc. Arrows have to clear the *visible* edge — including that
    # halo — otherwise the arrowhead lands under the emoji and the eye
    # can't tell which way energy is flowing.
    dm_outer_radius = 54
    other_outer_radius = 32

    def _arc(
        i: int, j: int, *, bulge: float, outward: bool, base_pad: int = 12
    ) -> dict[str, object]:
        """A quadratic-Bezier arc from element *i* to element *j*.

        Endpoints are pulled back from each element's *outer* edge (54-px
        halo around the day master, 32-px disc for the others) by
        ``base_pad`` so the arrowhead lands clearly in empty canvas. The
        control point is offset perpendicular to the chord so the curve
        bows either *outward* (away from the pentagon centre — used by
        the generation cycle along the perimeter) or *inward* (used by
        the control cycle that crosses through the middle).

        Returns the path's `d` attribute plus endpoint coordinates (so the
        template can render an inline `<linearGradient>` aligned with the
        arrow) and the source/destination element ids for stroke colours.
        """
        sx, sy = coords[i]
        dx, dy = coords[j]
        vx, vy = dx - sx, dy - sy
        dist = math.sqrt(vx * vx + vy * vy) or 1.0
        ux, uy = vx / dist, vy / dist
        src_outer = dm_outer_radius if cycle[i] == dm_class else other_outer_radius
        dst_outer = dm_outer_radius if cycle[j] == dm_class else other_outer_radius
        start_x = sx + ux * (src_outer + base_pad)
        start_y = sy + uy * (src_outer + base_pad)
        end_x = dx - ux * (dst_outer + base_pad)
        end_y = dy - uy * (dst_outer + base_pad)
        # Midpoint of the (shortened) chord
        mx = (start_x + end_x) / 2
        my = (start_y + end_y) / 2
        # Offset midpoint along the radial direction (toward or away from
        # pentagon centre at the origin) to bow the curve.
        md = math.sqrt(mx * mx + my * my) or 1.0
        nx, ny = mx / md, my / md
        if not outward:
            nx, ny = -nx, -ny
        ctrl_x = mx + nx * bulge
        ctrl_y = my + ny * bulge
        # Tangent at end of a quadratic Bezier is parallel to (end - control).
        tdx = end_x - ctrl_x
        tdy = end_y - ctrl_y
        tlen = math.hypot(tdx, tdy) or 1.0
        # Unit tangent, plus its perpendicular (rotate 90° CCW in SVG
        # coords, where +y is down).
        tux, tuy = tdx / tlen, tdy / tlen
        pux, puy = -tuy, tux
        # Truncate the line stroke a few pixels into the arrowhead so the
        # head fully overlaps the bow's tip — without this, a stroke wider
        # than the head's silhouette pokes out the sides at the join.
        line_trim = 6.0 if outward else 5.0
        line_end_x = end_x - line_trim * tux
        line_end_y = end_y - line_trim * tuy
        path_d = (
            f"M {start_x:.1f},{start_y:.1f} "
            f"Q {ctrl_x:.1f},{ctrl_y:.1f} {line_end_x:.1f},{line_end_y:.1f}"
        )
        # Build the arrowhead as a calligraphic-brush <path> whose vertex
        # coordinates are computed in Python — no SVG transforms, no
        # markers (CairoSVG ignores orient="auto" and applies
        # transform="rotate(...)" inconsistently on polygons/paths).
        gen_d = _tip_path(end_x, end_y, tux, tuy, pux, puy, length=22, half_w=7.0)
        ctrl_d = _tip_path(end_x, end_y, tux, tuy, pux, puy, length=18, half_w=5.5)
        return {
            "d": path_d,
            "x1": round(start_x, 1),
            "y1": round(start_y, 1),
            "x2": round(end_x, 1),
            "y2": round(end_y, 1),
            "tip_gen_d": gen_d,
            "tip_ctrl_d": ctrl_d,
            "src": cycle[i],
            "dst": cycle[j],
            "src_color": _ELEMENT_COLOR[cycle[i]],
            "dst_color": _ELEMENT_COLOR[cycle[j]],
        }

    # Generation cycle: pentagon perimeter, clockwise (Wood→Fire→Earth→Metal→Water).
    # Bowed outward so the arcs trace the outer ring of energy flow.
    arrows_gen = [_arc(i, (i + 1) % 5, bulge=22, outward=True) for i in range(5)]
    # Control cycle: skips one vertex, drawing the inner 5-pointed star.
    # Almost-straight chords (bulge=8 inward) so the star reads cleanly
    # instead of a tangle of curves crossing the centre.
    arrows_ctrl = [_arc(i, (i + 2) % 5, bulge=8, outward=False) for i in range(5)]

    return {
        "elements": elements,
        "arrows_gen": arrows_gen,
        "arrows_ctrl": arrows_ctrl,
        "icon_radius": icon_radius,
    }
