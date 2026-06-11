# EPS decomposition — structural build-up

> 2026-06-04 · `scripts/auto/s_aa_eps_decomp.py`

```
# Structural EPS build-up: where does (revenue − cost)/shares break for CA?

matched EPS×revenue surprises: 319 company-quarters, 35 tickers, 2024-01-31..2026-05-31

## Stage A — EPS surprise = revenue-driven part + margin part
  corr(rev_surprise, eps_surprise) = +0.231  (p_boot=0.001, n=319)
  eps_surprise ~ rev_surprise: slope=+4.69 (operating leverage), R²=0.053
  ⇒ only ~5% of the EPS-surprise variance is REVENUE-driven; ~95% is MARGIN/cost/other.

## Stage B — can CA predict each part?
  ca_yoy   → rev_surprise : r=+0.234 p_surr=0.002 (n=304)  ← CA's real revenue link
  cost_yoy → margin_resid : r=+0.019 p_surr=0.771 (n=304)  ← does commodity COST explain the MARGIN surprise?
  ca_yoy   → eps_surprise : r=+0.065 (n=304)  ← the direct null; ≈ +0.234×+0.231(rev→eps) = +0.054 expected

## Stage C — composite CA-only EPS predictor
  eps_surprise ~ ca_yoy + cost_yoy : R²=0.006 (n=304)   [CA-only build-up]
  (benchmark: eps_surprise ~ TRUE rev_surprise : R²=0.052 — even perfect revenue info caps here)

## VERDICT
  The build-up is right in spirit, but the math is unkind: EPS surprise is only ~5% revenue-driven,
  and CA captures revenue only at r≈0.23. So the revenue channel can carry at most ≈ r1×corr(rev,eps) ≈ 0.05
  into EPS — which IS the ~0.06 null we see. The remaining ~95% (margin) needs the cost proxy,
  and commodity cost → margin_resid is NOT significant (p_surr=0.771).
  ⇒ Even assembled structurally, CA can't reach EPS: the revenue link is too weak to amplify, and the
     margin term (which dominates EPS surprises) is largely invisible to CA / already public.
```
