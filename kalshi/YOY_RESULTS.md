# Kalshi KPI ladder (revenue YoY) in the paper's Table 1 format

> n = 32 company-quarters, 28 firms. Source: `kalshi_llm_ladder_ablation_yoy_preds.csv`. Calibrated R2 uses company-held-out rescaling.

## Run record

- target: revenue YoY (`rev_yoy`)
- calls: 384; successful: 384; errors: 0
- repeats per arm and target: 3
- estimated gateway cost: USD 30.06

| Sources | R2 | R2 (Calib.) | rho |
|---|---|---|---|
| H | 0.920 | 0.910 | 0.963 |
| H + X | 0.925 | 0.915 | 0.964 |
| H + Z | 0.910 | 0.892 | 0.955 |
| H + X + Z | **0.919** | **0.902** | **0.959** |
| Synergy | ✗ | - | ✗ |

## Definition 3.1 applied verbatim

| term | value | verdict |
|---|---:|---|
| G_X = L(H) - L(HX) | +1.822 | |
| G_Z = L(H) - L(HZ) | -2.952 | Z alone HURTS |
| G_XZ = L(H) - L(HXZ) | -0.242 | |
| **cond 1** d_mse = G_XZ - G_X - G_Z | **+0.888** | ✓ |
| **cond 2** L(HXZ) < min(L(H),L(HX),L(HZ)) | 25.539 vs 23.475 (margin +2.064) | ✗ |
| **cross-source synergy (MSE)** | | **✗** |
| d_corr | +0.003 | ✓ |
| rho(HXZ) > max others | 0.959 vs 0.964 | ✗ |
| **cross-source synergy (corr)** | | **✗** |

**Why condition 2 fails.** The positive interaction is produced by Z being harmful, not by X and Z genuinely complementing each other: the best single condition is H+X, and adding Z moves it back up. The paper anticipates exactly this case in Section 3.3 -- "two individually harmful sources can combine merely to recover the baseline, producing a positive interaction without useful prediction" -- which is why dominance is required alongside super-additivity.

