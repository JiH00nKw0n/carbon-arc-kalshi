# H3 OOS-DM re-run (FactSet revenue, pooled)

> 2026-06-04 · `scripts/auto/s_v_h3_oos_factset.py`

```
# H3 (rigorous) re-run — does CA improve the OUT-OF-SAMPLE revenue nowcast? (FactSet)

panel: 311 company-quarters, 35 tickers; 2024-02-29..2026-05-31
baseline AR(1) vs +CA, POOLED expanding-window OLS, within-company demeaning, strict point-in-time.

OOS forecasts produced: 206 (after min-train warmup), 35 tickers
  RMSE baseline AR(1)       = 0.0623
  RMSE +CA                  = 0.0613   (better by +1.7%)
  corr(pred_base, y)=+0.783   corr(pred_ca, y)=+0.791

## INCREMENTAL TEST (d = e_base² − e_ca², >0 ⇒ CA adds forecast info)
  mean(d) = +0.00013
  Diebold-Mariano (HLN-corrected) t = +0.85   (|t|>1.96 ⇒ sig at 5%)
  company-clustered bootstrap (G=35): two-sided p = 0.248

## VERDICT
  ~ CA improves point RMSE (0.062→0.061) but the gain is NOT statistically significant (DM t=+0.85, clustered p=0.248). Consistent with the modest revenue-nowcast edge (r≈0.19) being real but small — it nudges the forecast without dominating revenue's own AR structure.
```
