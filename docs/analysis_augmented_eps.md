# Augmented EPS — CA + analyst estimate dynamics

> 2026-06-04 · `scripts/auto/s_ab_augmented_eps.py`

```
# Augmented EPS model — CA + analyst estimate dynamics (free, pre-earnings)

panel: 310 company-quarters, 35 tickers, 2024-02-29..2026-05-31

## Univariate — which pre-earnings signal predicts the EPS surprise?
  ca_yoy       r=+0.066 p_boot=0.308 p_surr=0.228 (n=310)  — CA card (revenue read)
  eps_rev      r=+0.158 p_boot=0.187 p_surr=0.024 (n=310)  — estimate revision momentum
  eps_breadth  r=+0.149 p_boot=0.002 p_surr=0.005 (n=310)  — revision breadth (up−down)
  eps_disp     r=+0.137 p_boot=0.106 p_surr=0.031 (n=310)  — dispersion

## Multivariate — nested models (R² = how much EPS-surprise variance explained)
  card only                         : R²=0.004 (n=310)
  estimate dynamics only            : R²=0.052 (n=310)
  card + estimate dynamics (ALL)    : R²=0.054 (n=310)
  full-model coefficients (company-clustered p):
     ca_yoy       coef=-0.179 p=0.909
     eps_rev      coef=+0.479 p=0.237
     eps_breadth  coef=+0.032 p=0.659
     eps_disp     coef=+0.973 p=0.065

  CA incremental: corr(ca_yoy, EPS-surprise residual after estimate dynamics) = -0.032 p_surr=0.544

## VERDICT
  Estimate revision momentum predicts the EPS surprise at r=+0.158 (surr p=0.024) — it SEES the margin
  part CA can't: full model R²=0.054 vs card-only R²=0.004. BUT this is the analysts' OWN signal
  (public, documented under-reaction). CA's INCREMENT beyond it: r=-0.032 (surr p=0.544) →
  CA adds ~nothing beyond analyst dynamics.
```
