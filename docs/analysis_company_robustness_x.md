# CA→revenue-surprise: robustness to X transform

> 2026-06-04 · `scripts/auto/s_w_robustness_x.py`

```
# Robustness of CA→revenue-surprise to the X transform (Y = revenue surprise, fixed)

Y = (actual − point-in-time consensus)/consensus; FactSet 2021-2026 revenue.
X transform            r     n  p_boot  p_surr   note
ca_yoy            +0.192   313   0.011   0.009   baseline (the r≈0.19 result)
ca_yoy_resid      +0.056   243   0.242   0.546   YoY minus own trend (accel)
qoq_sa            +0.074   418   0.049   0.001   seasonally-adj QoQ Δlog (no Q-4 needed)
lvl_resid         +0.150   383   0.003   0.003   deseason level vs own trend

## VERDICT
  variants surviving (p_boot<.05 AND p_surr<.05): ['ca_yoy', 'qoq_sa', 'lvl_resid']
  ✅ ROBUST — the revenue-surprise signal is NOT an artifact of the YoY choice; it survives
     seasonally-adjusted QoQ and level-vs-trend forms too. YoY is a fine (not load-bearing) default.
```
