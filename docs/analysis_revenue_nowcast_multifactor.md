# Multifactor revenue-surprise nowcast

> 2026-06-04 · `scripts/auto/s_ac_revenue_nowcast.py`

```
# Multifactor REVENUE-surprise nowcast (CA + analyst revenue dynamics)

panel: 322 company-quarters, 35 tickers, 2024-02-29..2026-05-31

## Univariate — each factor → revenue surprise
  ca_yoy       r=+0.252 p_boot=0.013 p_surr=0.001 (n=322)
  rev_rev      r=+0.306 p_boot=0.000 p_surr=0.000 (n=322)
  rev_breadth  r=+0.358 p_boot=0.000 p_surr=0.000 (n=322)
  rev_disp     r=+0.019 p_boot=0.883 p_surr=0.796 (n=322)

## Multivariate — nested R²
  card only             : R²=0.063 (n=322)
  analyst dynamics only : R²=0.129 (n=322)
  FULL (card+analyst)   : R²=0.144 (n=322)
  full-model standardized contributions (coef × sd(x)):
     ca_yoy       coef=+0.034  (×sd=+0.0025)
     rev_rev      coef=-0.006  (×sd=-0.0001)
     rev_breadth  coef=+0.012  (×sd=+0.0057)
     rev_disp     coef=+0.011  (×sd=+0.0001)

## ⭐ CA INCREMENTAL beyond analyst revenue dynamics
  corr(ca_yoy, rev-surprise residual after analyst dynamics) = +0.118  p_surr=0.094 (n=322)
  ❌ CA redundant once analyst dynamics are in

## OUT-OF-SAMPLE (expanding window, strict point-in-time): 262 forecasts
  corr(pred, actual surprise): card-only=+0.255  analyst-only=+0.306  FULL=+0.319
  sign hit-rate (FULL): 64.89%
  long/short on predicted surprise: mean=+0.0067 t=+6.01 (longs beat-preds, shorts miss-preds)

## VERDICT
  Multifactor explains R²=0.144 of the revenue surprise in-sample (card alone 0.063).
  CA's value vs analysts: incremental r=+0.118 (surr p=0.094) — no edge beyond public analyst dynamics.
  OOS: full-model forecast corr +0.319, hit-rate 65% — usable nowcast.
```
