# CA → revenue surprise (FactSet point-in-time)

> 2026-06-03 · `scripts/auto/s_t_revsurprise_factset.py`

```
# Definitive clean test — CA → revenue surprise, FactSet POINT-IN-TIME consensus

events: 313 across 35 tickers; 2024-02-29..2026-05-31
surprise_early: mean=+0.0061 sd=0.0296 (vs FMP sd≈1.07 — FactSet much cleaner)
early vs print consensus differ by median 0.0016 (≈0 ⇒ consensus set by quarter-end)

## INFO — does CA predict the revenue surprise? (X=ca_yoy CLEAN, no artifact)
  ca_yoy → surprise_early : r=+0.192 (n=313) p_boot=0.015 p_surr=0.008
  ca_yoy → surprise_print : r=+0.152 (n=313) p_boot=0.023 p_surr=0.029
  [artifact check] (ca_yoy−cons) → surprise_early: r=+0.054  ← inflated by shared consensus term, NOT real

## RETURN edge (artifact-free: returns don't contain consensus)
  (ca_yoy − cons_early) → earnings-day return: r=+0.044 (n=188) p_boot=0.418 p_surr=0.522
  sanity: revenue surprise → return r=+0.074 (n=312)

## VERDICT
  ✅ CA predicts revenue surprise vs point-in-time consensus (r=+0.192, surr p=0.008) — CA beats analysts on revenue.
```
