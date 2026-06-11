# Company EDGE tests

> 2026-06-03 · `scripts/auto/s_q_edge_tests.py`

```
# Company EDGE tests — does CA carry info beyond price/consensus?

earnings events with CA_surprise: 240 across 35 tickers; 2024-10-01..2026-05-28

## H1 (MONEY) — CA_surprise → earnings-day mkt-adj return
  r=-0.075 (n=240) p_boot=0.288 p_surrogate=0.277
  sign hit-rate=55.8%  L/S mean earnings-day return=-0.0016 (SE 0.0059, t=-0.27, n=240)

## H2 (ANALYSTS) — CA_surprise → EPS surprise (actual-est)
  r=+0.015 (n=240) p_boot=0.491 p_surrogate=0.737

## H3 (RIGOROUS) — OOS Diebold-Mariano: rev_yoy forecast, AR(1) vs +CA
  n_test=103  RMSE base=0.0750  RMSE +CA=0.0882  DM=-0.88 p=0.378  (no sig improvement)

## H4 (WHERE) — H1/H2 by card-share tercile & analyst coverage
  cardshare=high: H1 r=-0.017(p0.98,n80) | H2 r=-0.056(p0.52,n80)
  cardshare=mid : H1 r=-0.202(p0.18,n80) | H2 r=-0.027(p0.78,n80)
  cardshare=low : H1 r=-0.092(p0.32,n80) | H2 r=+0.016(p0.68,n80)
  low_cov: H1 r=-0.136(p0.04,n120)
  high_cov: H1 r=+0.083(p0.42,n120)

## VERDICT
  H1 money: null | H3 OOS: null | H2 analysts: null
  → CA has NO tradeable edge at company level (measures revenue, but no info beyond price/consensus). Conclude.
```
