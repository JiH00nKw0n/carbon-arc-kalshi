# Y-switching experiment — Carbon Arc X (card/foot/click) × FactSet Y

Verdict gate (지훈): p_boot<0.05 AND p_surr<0.05. Baseline: card×surprise_early r≈+0.192.
Metrics: r (Pearson, clustered-boot), rho (Spearman), hit (sign agreement),
         IC/IR (per-quarter cross-sectional rank-IC mean & info-ratio).

## CARD  (562 events · 64 tickers · 2024-02-29..2026-04-30)
### Y-switch (X = x_yoy)
  card | x_yoy → rev_yoy             r=+0.415 n=560 p_boot=+0.000 p_surr=+0.000 | rho=+0.533 hit=0.61 IC=+0.514 IR=+2.776 nQ=18  [PASS]
  card | x_yoy → surprise_early      r=+0.201 n=562 p_boot=+0.000 p_surr=+0.000 | rho=+0.217 hit=0.56 IC=+0.242 IR=+1.403 nQ=18  [PASS]
  card | x_yoy → surprise_print      r=+0.195 n=562 p_boot=+0.001 p_surr=+0.000 | rho=+0.209 hit=0.56 IC=+0.241 IR=+1.336 nQ=18  [PASS]
  within-company corr(x_yoy, surprise_early) = +0.137  (firm-mean removed → right quarter, not just right firm)
### X-transform robustness → surprise_early
  card | x_yoy → surprise_early      r=+0.201 n=562 p_boot=+0.000 p_surr=+0.000 | rho=+0.217 hit=0.56 IC=+0.242 IR=+1.403 nQ=18  [PASS]
  card | x_yoy_3m → surprise_early   r=+0.201 n=562 p_boot=+0.000 p_surr=+0.000 | rho=+0.217 hit=0.56 IC=+0.242 IR=+1.403 nQ=18  [PASS]
### lead/lag → surprise_early
  card | x_yoy(t-1) → surprise_early r=+0.058 n=499 p_boot=+0.365 p_surr=+0.269 | rho=+0.119 hit=0.50 IC=+0.133 IR=+0.832 nQ=16  [fail]

## FOOT  (434 events · 54 tickers · 2024-04-30..2026-05-31)
### Y-switch (X = x_yoy)
  foot | x_yoy → rev_yoy             r=+0.385 n=434 p_boot=+0.000 p_surr=+0.000 | rho=+0.403 hit=0.69 IC=+0.372 IR=+1.103 nQ=20  [PASS]
  foot | x_yoy → surprise_early      r=+0.015 n=434 p_boot=+0.843 p_surr=+0.785 | rho=-0.026 hit=0.56 IC=-0.071 IR=-0.269 nQ=20  [fail]
  foot | x_yoy → surprise_print      r=+0.006 n=434 p_boot=+0.943 p_surr=+0.905 | rho=-0.038 hit=0.55 IC=-0.086 IR=-0.323 nQ=20  [fail]
  within-company corr(x_yoy, surprise_early) = +0.033  (firm-mean removed → right quarter, not just right firm)
### X-transform robustness → surprise_early
  foot | x_yoy → surprise_early      r=+0.015 n=434 p_boot=+0.843 p_surr=+0.785 | rho=-0.026 hit=0.56 IC=-0.071 IR=-0.269 nQ=20  [fail]
  foot | x_yoy_3m → surprise_early   r=+0.069 n=424 p_boot=+0.207 p_surr=+0.260 | rho=+0.031 hit=0.54 IC=-0.036 IR=-0.150 nQ=19  [fail]
### lead/lag → surprise_early
  foot | x_yoy(t-1) → surprise_early r=+0.088 n=424 p_boot=+0.086 p_surr=+0.152 | rho=+0.055 hit=0.60 IC=-0.052 IR=-0.180 nQ=19  [fail]

## CLICK  (319 events · 33 tickers · 2023-12-31..2026-03-31)
### Y-switch (X = x_yoy)
  click | x_yoy → rev_yoy            r=+0.058 n=315 p_boot=+0.058 p_surr=+0.192 | rho=+0.150 hit=0.62 IC=+0.367 IR=+2.794 nQ=10  [fail]
  click | x_yoy → surprise_early     r=+0.122 n=319 p_boot=+0.000 p_surr=+0.001 | rho=+0.202 hit=0.60 IC=+0.235 IR=+1.268 nQ=10  [PASS]
  click | x_yoy → surprise_print     r=+0.082 n=319 p_boot=+0.002 p_surr=+0.032 | rho=+0.180 hit=0.60 IC=+0.214 IR=+1.469 nQ=10  [PASS]
  within-company corr(x_yoy, surprise_early) = +0.118  (firm-mean removed → right quarter, not just right firm)
### X-transform robustness → surprise_early
  click | x_yoy → surprise_early     r=+0.122 n=319 p_boot=+0.000 p_surr=+0.001 | rho=+0.202 hit=0.60 IC=+0.235 IR=+1.268 nQ=10  [PASS]
  click | x_yoy_3m → surprise_early  r=+0.171 n=291 p_boot=+0.001 p_surr=+0.018 | rho=+0.182 hit=0.63 IC=+0.238 IR=+1.358 nQ= 9  [PASS]
### lead/lag → surprise_early
  click | x_yoy(t-1) → surprise_early r=+0.157 n=291 p_boot=+0.002 p_surr=+0.012 | rho=+0.160 hit=0.62 IC=+0.201 IR=+1.229 nQ= 9  [PASS]
