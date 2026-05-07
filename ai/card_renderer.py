"""Public renderer entry point.

Thin wrapper over ``ai.svg_renderer.render_chart_png_async`` — kept as a
distinct module so ``bot.routers.*`` import paths stay stable. The
Playwright HTML→PNG fallback was retired in 1.7.10 (see ADR-007 in
vision.mdc); CairoSVG + ProcessPoolExecutor is now the only path.
"""

from ai.svg_renderer import RenderRequest, render_chart_png_async

__all__ = ["RenderRequest", "close_browser", "render_chart_png"]


async def render_chart_png(req: RenderRequest) -> bytes:
    return await render_chart_png_async(req)


async def close_browser() -> None:
    """Lifecycle hook from before ADR-007. Kept as a no-op so the bot's
    shutdown sequence in ``bot/main.py`` doesn't have to special-case the
    renderer choice. Tears down the SVG render pool."""
    from ai._render_pool import shutdown_render_pool

    shutdown_render_pool()
