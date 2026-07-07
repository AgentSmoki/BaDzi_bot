"""Render throughput benchmark.

Measures end-to-end PNG generation time on the canonical reference chart
(Anastasia, 12.09.1999 23:55 Volgograd) for two configurations:

* sequential: ``render_chart_png`` called in-process, no concurrency
* pool: ``render_chart_png_async`` via ProcessPoolExecutor (1.7.9)

Prints a table with mean / p95 / total wall-clock for N=50 and N=200
parallel requests. Results land in ``doc/benchmarks/render.md``.

Usage::

    python -m scripts.bench_render          # default N=50 and N=200
    RENDER_POOL_SIZE=8 python -m scripts.bench_render
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time
from datetime import datetime
from pathlib import Path

from ai._render_pool import get_pool_size, get_render_pool, shutdown_render_pool
from ai.svg_renderer import RenderRequest, render_chart_png, render_chart_png_async
from calculator import calculate_chart
from calculator.models import ChartInput

REFERENCE_INPUT = ChartInput(
    birth_datetime=datetime(1999, 9, 12, 23, 55),
    latitude=48.7894,
    longitude=44.7783,
    tz_offset=3.0,
    gender="female",
)


def _build_request() -> RenderRequest:
    chart = calculate_chart(REFERENCE_INPUT)
    return RenderRequest(
        chart=chart,
        title="Бенчмарк рендера",
        subtitle="эталон Волжский 1999",
        has_birth_time=True,
    )


def _summary(name: str, n: int, durations_ms: list[float], total_ms: float) -> str:
    mean = statistics.mean(durations_ms)
    p95 = (
        statistics.quantiles(durations_ms, n=20)[18]
        if len(durations_ms) >= 20
        else max(durations_ms)
    )
    rps = (n / total_ms) * 1000 if total_ms else 0
    return (
        f"  {name:<20} N={n:<3} | mean={mean:>7.1f}ms | p95={p95:>7.1f}ms | "
        f"total={total_ms:>8.1f}ms | rps={rps:>5.1f}"
    )


def _bench_sequential(n: int) -> tuple[list[float], float]:
    req = _build_request()
    durations: list[float] = []
    started = time.perf_counter()
    for _ in range(n):
        t0 = time.perf_counter()
        render_chart_png(req)
        durations.append((time.perf_counter() - t0) * 1000)
    total_ms = (time.perf_counter() - started) * 1000
    return durations, total_ms


async def _bench_pool(n: int) -> tuple[list[float], float]:
    req = _build_request()
    get_render_pool()  # warm

    async def one() -> float:
        t0 = time.perf_counter()
        await render_chart_png_async(req)
        return (time.perf_counter() - t0) * 1000

    started = time.perf_counter()
    durations = await asyncio.gather(*[one() for _ in range(n)])
    total_ms = (time.perf_counter() - started) * 1000
    return list(durations), total_ms


async def _amain(sizes: list[int]) -> str:
    import os

    lines: list[str] = []
    lines.append("# Render throughput benchmark")
    lines.append("")
    lines.append(f"Generated: {datetime.now().isoformat(timespec='seconds')}")
    lines.append("Reference chart: Anastasia, Волжский 1999-09-12 23:55 (UTC+3)")
    get_render_pool()
    lines.append(
        f"Host: {os.cpu_count()} cores · "
        f"RENDER_POOL_SIZE={os.environ.get('RENDER_POOL_SIZE', 'auto')} "
        f"(pool workers actually used: {get_pool_size()})"
    )
    lines.append("")

    for n in sizes:
        lines.append(f"## N = {n}")
        lines.append("```")

        seq_d, seq_t = _bench_sequential(n)
        lines.append(_summary("sequential", n, seq_d, seq_t))

        pool_d, pool_t = await _bench_pool(n)
        lines.append(_summary("pool (CairoSVG)", n, pool_d, pool_t))

        lines.append("```")
        lines.append("")

    shutdown_render_pool()
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", type=int, nargs="+", default=[50, 200])
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "doc" / "benchmarks" / "render.md",
    )
    args = parser.parse_args()

    md = asyncio.run(_amain(args.sizes))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(md, encoding="utf-8")
    print(md)
    print(f"\nWritten to {args.out}")


if __name__ == "__main__":
    main()
