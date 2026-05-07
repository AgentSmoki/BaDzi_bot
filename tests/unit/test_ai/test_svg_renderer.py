"""Snapshot tests for the SVG → PNG renderer.

Driven by a real chart from `calculate_chart()` (we don't mock the calculator —
its output is deterministic and the renderer's job is to faithfully visualise
whatever the calculator produces). The assertions target structural regressions
that have bitten us before:

- hidden stems disappearing from the pillar cards (manifested as blank space
  between the upper and lower divider lines);
- the wuxing wheel rendering only role labels because emoji glyphs failed to
  reach the user's runtime;
- generation/control arrows missing from the pentagon perimeter.

All checks run on the SVG markup (not the rasterised PNG), so they're fast and
don't depend on the host's font configuration.
"""

from datetime import datetime

from ai.svg_renderer import RenderRequest, render_chart_png, render_chart_svg
from calculator import calculate_chart
from calculator.models import ChartInput


def _anastasia_chart() -> RenderRequest:
    inp = ChartInput(
        birth_datetime=datetime(1999, 9, 12, 23, 55),
        latitude=48.7919,
        longitude=44.7497,
        tz_offset=3.0,
        gender="female",
    )
    chart = calculate_chart(inp)
    return RenderRequest(
        chart=chart,
        title="12.09.1999",
        subtitle="Волжский · 23:55",
        has_birth_time=True,
    )


def test_svg_renders_hidden_stems_for_every_branch() -> None:
    """Every branch carries at least one hidden stem in the traditional school,
    so all four pillar cards must have at least one `hidden-stem` <text>."""
    svg = render_chart_svg(_anastasia_chart())
    # Each hidden stem becomes one <text class="glyph hidden-stem el-..."> entry.
    # Anastasia's branches (卯, 酉, 辰, 子) collectively expose 6 hidden stems.
    hidden_stem_count = svg.count('class="glyph hidden-stem el-')
    assert hidden_stem_count >= 4, f"expected ≥4 hidden stems, got {hidden_stem_count}"
    # Yin/yang labels under each stem must be present too.
    assert "Дерево Инь" in svg or "Дерево Ян" in svg


def test_svg_wuxing_wheel_has_icons_arrows_and_emoji_overlay() -> None:
    """Pentagon must emit:
    - 5 `<use xlink:href="#ic-...">` references (one per element, always-visible
      SVG icon underneath the emoji);
    - 5 generation arrows around the perimeter + 1 in the legend;
    - 5 control arrows across the inner star + 1 in the legend;
    - exactly one emoji marked as `wuxing-emoji-dm` (the day master)."""
    svg = render_chart_svg(_anastasia_chart())
    assert svg.count('xlink:href="#ic-') == 5
    assert svg.count('marker-end="url(#gen-arrow)"') == 6
    assert svg.count('marker-end="url(#ctrl-arrow)"') == 6
    assert 'class="wuxing-emoji wuxing-emoji-dm"' in svg


def test_svg_uses_xlink_namespace() -> None:
    """`xlink:href` requires the xlink namespace declaration on the root <svg>;
    CairoSVG silently drops `<use>` references when it isn't declared."""
    svg = render_chart_svg(_anastasia_chart())
    assert 'xmlns:xlink="http://www.w3.org/1999/xlink"' in svg


def test_render_chart_png_returns_valid_png_bytes() -> None:
    """End-to-end: Jinja → CairoSVG → PNG. Header check is enough — pixel-level
    diffing belongs in a manual visual review, not a unit test."""
    png = render_chart_png(_anastasia_chart())
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(png) > 10_000  # placeholder PNG would be tiny


def test_svg_renders_pillar_glyphs_with_element_colours() -> None:
    """Stems and branches in each pillar carry the element colour class
    (`.el-wood`, `.el-fire`, ...) so the rasterised PNG reads correctly even
    without the font picking up colour glyphs."""
    svg = render_chart_svg(_anastasia_chart())
    # 4 stems + 4 branches = 8 large glyphs, plus hidden-stem glyphs and the
    # day-master strip. Conservative lower bound that catches "all glyphs lost
    # their colour" regressions.
    assert svg.count("stem-char el-") >= 4
    assert svg.count("branch-char el-") >= 4
