# Render throughput benchmark

Generated: 2026-05-07T17:40:22
Reference chart: Anastasia, Волжский 1999-09-12 23:55 (UTC+3)
Host: 4 cores · RENDER_POOL_SIZE=4 (pool workers actually used: 4)

## N = 50
```
  sequential           N=50  | mean=  390.3ms | p95=  501.4ms | total= 19513.3ms | rps=  2.6
  pool (CairoSVG)      N=50  | mean= 8517.9ms | p95=12855.1ms | total= 13253.4ms | rps=  3.8
```

## N = 200
```
  sequential           N=200 | mean=  393.5ms | p95=  500.6ms | total= 78706.2ms | rps=  2.5
  pool (CairoSVG)      N=200 | mean=19825.0ms | p95=37607.5ms | total= 39066.3ms | rps=  5.1
```
