# Kalshi Raw-Ladder Benchmark

This is the authoritative design and result report for the Kalshi-only X substitution in the shared revenue-nowcasting paper framework.

## Benchmark contract

The benchmark contract is copied from Jihoon's latest `main` config. Only the X channel changes
from Carbon Arc data to Kalshi raw ladders.

| Component | Fixed rule |
|---|---|
| H (financial) | Up to 6 prior quarterly actuals, early consensus and realized surprise, plus target-quarter consensus |
| X (Kalshi) | Chronological raw pre-publication KPI ladders; all retained events, rungs and quote fields |
| Z (text) | Up to 2 most recent corrected earnings calls dated at least 31 days before report; one call is allowed when only one exists |
| Y | `surprise_early`, `surprise_print`, and `rev_yoy`, evaluated separately |
| Model | `gpt-5.5-2026-04-23`, `medium` reasoning |
| Variants | `BASE` and byte-identical `TOOL` prompt with optional lookups |
| Arms | `fin`, `fin+x`, `fin+text`, `fin+x+text` |
| Repeats | 1 independent call per arm and target |
| Knowledge guard | `REPORT_DATE > 2025-12-01` |
| Pairing | Every arm within a cell uses the exact same `ticker + FE_FP_END` rows |
| Seed | 2026 |

### Input, output and labels

The model outputs predicted total quarterly revenue in USD millions. The evaluator then derives:

- `surprise_early = (predicted revenue - early consensus) / early consensus`
- `surprise_print = (predicted revenue - last pre-report consensus) / last pre-report consensus`
- `rev_yoy = (predicted revenue - same-quarter prior-year actual) / prior-year actual`

The true labels apply the same formulas to FactSet actual revenue. Predictions and labels are scored
in percentage points. Structured output also contains confidence and rationale, but neither enters
the metrics.


## Data universe

The crawl uses Kalshi's public Trade API v2 `/series?tags=KPIs` cursor pagination, then fetches both
current and historical markets for every returned series. The inventory is complete for the API
response captured by this run; explicit issuer aliases map public companies. The seven deliberately
unmapped series are non-public or non-company questions (Waymo, OpenAI/LLM rankings, subway
ridership and aggregate EV share).

| Stage | Rows / units | Distinct tickers | Rule |
|---|---:|---:|---|
| KPI series crawl | 193 series (186 mapped) | 89 | Public current + historical API pages |
| Market inventory | 2254 contracts | 84 | Preserve raw contract metadata |
| `kalshi_company_event_features.csv` | 271 events / 2217 numeric contracts | 84 | One metadata row per event with at least two numeric YES-threshold rungs; this file is not model input |
| Direct FactSet panel | 2211 company-quarters | 84 | 84 FactSet IDs; actuals and point-in-time consensus from FE_V4 |
| Exact fiscal join | 113 events / 100 quarters | 42 | Same ticker, fiscal year and fiscal quarter |
| Valid pre-publication ladder | 98 quarters | 42 | At least two priced rungs before publication |
| Metric screen | 51 O pairs | 42 | Remove non-revenue KPI types |
| Firm revenue-driver screen | 22 O pairs | 20 | Screener + high-effort auditor against total revenue |
| Firm-screened ladder panel | 46 quarters | 20 | Keep O `(ticker, metric)` ladders |
| Strong-O benchmark candidates | - | 18 | Jihoon `main` primary tier |
| Final matched evaluation | 22 company-quarters | 16 | Post-cutoff + ladder + >=3 financial rows + >=1 eligible transcript |

The metric screen is a deterministic wording rule that removes non-revenue KPI types. The 51
surviving `(ticker, metric)` pairs then pass through `gpt-5.5-2026-04-23` at medium effort and an adversarial
high-effort audit, in batches of eight with exact pair-key validation. `O` means the KPI is a
dominant, clean driver of total revenue; `strength` is confidence in that verdict, not estimated
revenue share. This follows the committed Carbon Arc screening CSV practice, which can retain a
dominant clean driver below 50% share; it does not impose a hard revenue-share threshold.

**84 numeric-ladder candidates:** AAPL, ABNB, ACDVF, AMZN, ATZ, BA, BULL, CAVA, CCL, CDNTF, CMG, COIN, COST, CVNA, DASH, DIS, DLMAF, DPZ, EBAY, F, FDX, FIG, FSLR, FUTU, GOOGL, GRAB, HD, HIMS, HOOD, INTC, KLAR, L, LOW, LULU, LUV, LYFT, MAR, MCD, MELI, META, MO, MTCH, MTN, NCLH, NFLX, NU, NVDA, NYT, ORCL, PETR4, PLNT, PLTR, PM, PSKY, RACE, RBLX, RDDT, RIVN, ROKU, SBUX, SCHW, SE, SG, SHOP, SNAP, SNOW, SOFI, SPOT, STZ, TGT, TLN, TOL, TOST, TSLA, UAL, UBER, ULTA, URBN, WEN, WH, WING, WMT, YOU, ZETA.

**42 exact-joined candidates:** ABNB, BA, BULL, CAVA, CCL, COIN, CVNA, DASH, DIS, DPZ, FUTU, HIMS, HOOD, KLAR, LUV, LYFT, MAR, META, MO, MTCH, MTN, NFLX, NYT, PLNT, PLTR, PM, PSKY, RACE, RBLX, RDDT, ROKU, SCHW, SNOW, SOFI, SPOT, STZ, TOL, TSLA, UAL, UBER, URBN, WH.

**20 firm-screen O tickers:** ABNB, BA, COIN, CVNA, DASH, DPZ, HIMS, LYFT, MO, MTCH, MTN, NFLX, PLNT, RACE, SPOT, STZ, TOL, TSLA, UAL, UBER.

**18 strong-O candidates:** ABNB, BA, COIN, CVNA, DASH, HIMS, LYFT, MO, MTCH, NFLX, PLNT, RACE, SPOT, STZ, TOL, TSLA, UAL, UBER.

**16 final benchmark tickers:** ABNB, BA, COIN, CVNA, DASH, HIMS, LYFT, MO, MTCH, PLNT, RACE, STZ, TOL, TSLA, UAL, UBER.

### Attrition accounting

- **84 -> 42:** 42 numeric-ladder tickers had no exact `(ticker, fiscal year, fiscal quarter)`
  match to the direct FactSet panel.
- **42 -> 20:** the firm-level total-revenue screen rejected every surviving metric for 22 tickers.
- **20 -> 18:** `DPZ` and `MTN` are O-moderate and are excluded by `strong_only: true`.
- **18 -> 16:** `NFLX` and `SPOT` have valid ladders only for reports on or before the
  `2025-12-01` knowledge cutoff, so they have no evaluation target.

### Final ticker-quarters

All three Y definitions use the same 22 target rows.

| Ticker | Target fiscal quarters | Targets | H quarters shown | Prior X ladder quarters shown | Prior calls |
|---|---|---:|---|---|---|
| ABNB | 2026-03-31 | 1 | 6 | 0 | 2 |
| BA | 2025-12-31, 2026-03-31 | 2 | 6, 6 | 0, 1 | 1, 2 |
| COIN | 2026-03-31 | 1 | 6 | 5 | 2 |
| CVNA | 2026-03-31 | 1 | 6 | 0 | 2 |
| DASH | 2025-12-31, 2026-03-31 | 2 | 6, 6 | 0, 1 | 2, 2 |
| HIMS | 2026-03-31 | 1 | 6 | 0 | 2 |
| LYFT | 2026-03-31 | 1 | 6 | 0 | 2 |
| MO | 2026-03-31 | 1 | 6 | 0 | 2 |
| MTCH | 2025-12-31, 2026-03-31 | 2 | 6, 6 | 0, 1 | 2, 2 |
| PLNT | 2026-03-31 | 1 | 6 | 0 | 2 |
| RACE | 2026-03-31 | 1 | 6 | 0 | 2 |
| STZ | 2026-05-31 | 1 | 6 | 0 | 2 |
| TOL | 2026-04-30 | 1 | 6 | 0 | 2 |
| TSLA | 2025-12-31, 2026-03-31 | 2 | 6, 6 | 6, 6 | 1, 2 |
| UAL | 2026-03-31, 2026-06-30 | 2 | 6, 6 | 0, 1 | 2, 2 |
| UBER | 2025-12-31, 2026-03-31 | 2 | 6, 6 | 0, 1 | 2, 2 |


## Kalshi X construction

For each company-quarter, every eligible KPI event is retained. Each event is an ordered ladder of
binary threshold contracts (rungs), such as `P(deliveries >= 300,000)`. The prompt places any prior
quarter ladder immediately after that quarter's financial row, then places the target-quarter ladder
after the target row.

For each rung, the information cutoff is one minute before the FactSet publication timestamp. The
collector searches from the contract's actual `open_time` through that cutoff and selects the latest
available daily candle. There is no 45-day quote-age cap; 45 days belonged to Carbon Arc's monthly
observation-to-quarter matching rule and is not a Kalshi market rule.

A valid YES bid/ask with spread <= 0.20 uses the midpoint. Invalid or wider books, including
`bid=0, ask=1`, fall back to last trade and then previous trade. The LLM receives condition,
probability, price source, bid, ask, last, previous, spread, candle timestamp, daily volume and open
interest for every rung. It receives no settled result, smoothing, interpolation or implied scalar.


## Evaluation

- **RMSE:** square root of mean squared percentage-point error; lower is better.
- **OOS R2:** `1 - SSE/SST` against the post-cutoff truth mean; higher is better.
- **Calibrated R2 (OOF):** company-held-out five-fold linear rescaling, fit only on other firms.
- **Correlation:** Pearson correlation between prediction and truth.
- **Synergy:** company-clustered bootstrap of `M(fin+x+text) - [M(fin+x) + M(fin+text) - M(fin)]`
  for correlation and MSE skill. Positive values indicate super-additivity; a 95% interval crossing
  zero is not statistically robust.
- **Shuffle-company surrogate:** the benchmark's company-block reassignment of Y. It tests whether
  the combined prediction tracks firm-specific outcomes rather than a common scale effect; it does
  not prove that Kalshi X itself is firm-specific and is not an X-shuffle test.

N0 (company historical mean) and N2 (call sentiment) remain available. N1/N3/N4/N3b/N4b/N5 require
a dense, comparable scalar X and are reported N/A because Kalshi X is a sparse, firm-specific raw
ladder distribution. Fabricating a scalar zero would make those baselines misleading.


## Results

### Early-consensus revenue surprise / BASE

Matched sample: 22 company-quarters / 16 firms.

| Model | RMSE | OOS R2 | Calib. R2 (OOF) | Corr | MAE | Sign |
|---|---:|---:|---:|---:|---:|---:|
| fin | 3.588 | +0.316 | +0.187 | +0.577 | 2.490 | 0.591 |
| fin+x | 3.507 | +0.346 | +0.279 | +0.608 | 2.494 | 0.591 |
| fin+text | 3.490 | +0.353 | +0.166 | +0.628 | 2.374 | 0.727 |
| fin+x+text | 3.406 | +0.383 | +0.194 | +0.650 | 2.195 | 0.682 |
| N0 | 5.997 | -0.911 | - | -0.298 | 3.952 | 0.591 |
| N1 | N/A | N/A | N/A | N/A | N/A | N/A |
| N2 | 4.377 | -0.018 | - | -0.178 | 2.974 | 0.727 |
| N3 | N/A | N/A | N/A | N/A | N/A | N/A |
| N4 | N/A | N/A | N/A | N/A | N/A | N/A |
| N3b | N/A | N/A | N/A | N/A | N/A | N/A |
| N4b | N/A | N/A | N/A | N/A | N/A | N/A |
| N5 | N/A | N/A | N/A | N/A | N/A | N/A |

Descriptive RMSE delta X over H: -0.080 pp; X over H+Z: -0.084 pp (negative favors Kalshi).

| Bootstrap quantity | Mean | 95% CI | p(value <= 0) |
|---|---:|---:|---:|
| Corr synergy | -0.016 | [-0.195, +0.150] | 0.568 |
| MSE-skill synergy | -0.021 | [-0.320, +0.174] | 0.517 |

Shuffle-company surrogate p-value: 0.0250.

### Early-consensus revenue surprise / TOOL

Matched sample: 22 company-quarters / 16 firms.

| Model | RMSE | OOS R2 | Calib. R2 (OOF) | Corr | MAE | Sign |
|---|---:|---:|---:|---:|---:|---:|
| fin | 4.146 | +0.087 | -0.080 | +0.342 | 2.475 | 0.636 |
| fin+x | 3.656 | +0.290 | +0.233 | +0.586 | 2.663 | 0.591 |
| fin+text | 3.563 | +0.325 | +0.084 | +0.588 | 2.392 | 0.727 |
| fin+x+text | 3.487 | +0.354 | +0.146 | +0.615 | 2.415 | 0.682 |
| N0 | 5.997 | -0.911 | - | -0.298 | 3.952 | 0.591 |
| N1 | N/A | N/A | N/A | N/A | N/A | N/A |
| N2 | 4.377 | -0.018 | - | -0.178 | 2.974 | 0.727 |
| N3 | N/A | N/A | N/A | N/A | N/A | N/A |
| N4 | N/A | N/A | N/A | N/A | N/A | N/A |
| N3b | N/A | N/A | N/A | N/A | N/A | N/A |
| N4b | N/A | N/A | N/A | N/A | N/A | N/A |
| N5 | N/A | N/A | N/A | N/A | N/A | N/A |

Descriptive RMSE delta X over H: -0.490 pp; X over H+Z: -0.076 pp (negative favors Kalshi).

| Bootstrap quantity | Mean | 95% CI | p(value <= 0) |
|---|---:|---:|---:|
| Corr synergy | -0.204 | [-0.820, +0.320] | 0.701 |
| MSE-skill synergy | -0.146 | [-0.580, +0.256] | 0.684 |

Shuffle-company surrogate p-value: 0.0258.

TOOL telemetry: 88/88 arm requests used at least one lookup; calls: get_alt_data_description=88, get_company_profile=88.

### Pre-report-consensus revenue surprise / BASE

Matched sample: 22 company-quarters / 16 firms.

| Model | RMSE | OOS R2 | Calib. R2 (OOF) | Corr | MAE | Sign |
|---|---:|---:|---:|---:|---:|---:|
| fin | 3.857 | -0.239 | -0.277 | +0.168 | 2.585 | 0.545 |
| fin+x | 3.638 | -0.103 | -0.224 | +0.161 | 2.612 | 0.591 |
| fin+text | 3.737 | -0.164 | -0.350 | -0.028 | 2.485 | 0.682 |
| fin+x+text | 3.327 | +0.078 | -0.076 | +0.377 | 2.139 | 0.682 |
| N0 | 4.539 | -0.716 | - | -0.208 | 3.109 | 0.636 |
| N1 | N/A | N/A | N/A | N/A | N/A | N/A |
| N2 | 3.505 | -0.024 | - | -0.166 | 2.379 | 0.773 |
| N3 | N/A | N/A | N/A | N/A | N/A | N/A |
| N4 | N/A | N/A | N/A | N/A | N/A | N/A |
| N3b | N/A | N/A | N/A | N/A | N/A | N/A |
| N4b | N/A | N/A | N/A | N/A | N/A | N/A |
| N5 | N/A | N/A | N/A | N/A | N/A | N/A |

Descriptive RMSE delta X over H: -0.219 pp; X over H+Z: -0.411 pp (negative favors Kalshi).

| Bootstrap quantity | Mean | 95% CI | p(value <= 0) |
|---|---:|---:|---:|
| Corr synergy | +0.414 | [-0.076, +1.048] | 0.058 |
| MSE-skill synergy | +0.095 | [-0.506, +0.576] | 0.272 |

Shuffle-company surrogate p-value: 0.1672.

### Pre-report-consensus revenue surprise / TOOL

Matched sample: 22 company-quarters / 16 firms.

| Model | RMSE | OOS R2 | Calib. R2 (OOF) | Corr | MAE | Sign |
|---|---:|---:|---:|---:|---:|---:|
| fin | 3.945 | -0.297 | -0.413 | +0.088 | 2.448 | 0.591 |
| fin+x | 3.385 | +0.045 | -0.102 | +0.299 | 2.451 | 0.591 |
| fin+text | 3.597 | -0.078 | -0.366 | +0.081 | 2.376 | 0.727 |
| fin+x+text | 3.718 | -0.152 | -0.315 | -0.018 | 2.506 | 0.636 |
| N0 | 4.539 | -0.716 | - | -0.208 | 3.109 | 0.636 |
| N1 | N/A | N/A | N/A | N/A | N/A | N/A |
| N2 | 3.505 | -0.024 | - | -0.166 | 2.379 | 0.773 |
| N3 | N/A | N/A | N/A | N/A | N/A | N/A |
| N4 | N/A | N/A | N/A | N/A | N/A | N/A |
| N3b | N/A | N/A | N/A | N/A | N/A | N/A |
| N4b | N/A | N/A | N/A | N/A | N/A | N/A |
| N5 | N/A | N/A | N/A | N/A | N/A | N/A |

Descriptive RMSE delta X over H: -0.560 pp; X over H+Z: +0.121 pp (negative favors Kalshi).

| Bootstrap quantity | Mean | 95% CI | p(value <= 0) |
|---|---:|---:|---:|
| Corr synergy | -0.300 | [-0.871, +0.176] | 0.812 |
| MSE-skill synergy | -0.525 | [-1.961, +0.168] | 0.808 |

Shuffle-company surrogate p-value: 0.9406.

TOOL telemetry: 88/88 arm requests used at least one lookup; calls: get_alt_data_description=88, get_company_profile=88.

### Revenue YoY / BASE

Matched sample: 22 company-quarters / 16 firms.

| Model | RMSE | OOS R2 | Calib. R2 (OOF) | Corr | MAE | Sign |
|---|---:|---:|---:|---:|---:|---:|
| fin | 3.730 | +0.961 | +0.955 | +0.981 | 2.512 | 1.000 |
| fin+x | 3.846 | +0.959 | +0.953 | +0.980 | 2.831 | 1.000 |
| fin+text | 3.692 | +0.962 | +0.951 | +0.981 | 2.453 | 1.000 |
| fin+x+text | 4.061 | +0.954 | +0.943 | +0.977 | 2.701 | 1.000 |
| N0 | 25.630 | -0.820 | - | +0.118 | 17.870 | 0.818 |
| N1 | N/A | N/A | N/A | N/A | N/A | N/A |
| N2 | 20.811 | -0.200 | - | +0.269 | 16.974 | 0.818 |
| N3 | N/A | N/A | N/A | N/A | N/A | N/A |
| N4 | N/A | N/A | N/A | N/A | N/A | N/A |
| N3b | N/A | N/A | N/A | N/A | N/A | N/A |
| N4b | N/A | N/A | N/A | N/A | N/A | N/A |
| N5 | N/A | N/A | N/A | N/A | N/A | N/A |

Descriptive RMSE delta X over H: +0.116 pp; X over H+Z: +0.369 pp (negative favors Kalshi).

| Bootstrap quantity | Mean | 95% CI | p(value <= 0) |
|---|---:|---:|---:|
| Corr synergy | -0.003 | [-0.009, +0.003] | 0.825 |
| MSE-skill synergy | -0.006 | [-0.019, +0.008] | 0.840 |

Shuffle-company surrogate p-value: 0.0002.

### Revenue YoY / TOOL

Matched sample: 22 company-quarters / 16 firms.

| Model | RMSE | OOS R2 | Calib. R2 (OOF) | Corr | MAE | Sign |
|---|---:|---:|---:|---:|---:|---:|
| fin | 3.833 | +0.959 | +0.953 | +0.980 | 2.614 | 1.000 |
| fin+x | 3.642 | +0.963 | +0.958 | +0.982 | 2.548 | 1.000 |
| fin+text | 3.999 | +0.956 | +0.942 | +0.978 | 2.726 | 1.000 |
| fin+x+text | 3.865 | +0.959 | +0.948 | +0.980 | 2.595 | 1.000 |
| N0 | 25.630 | -0.820 | - | +0.118 | 17.870 | 0.818 |
| N1 | N/A | N/A | N/A | N/A | N/A | N/A |
| N2 | 20.811 | -0.200 | - | +0.269 | 16.974 | 0.818 |
| N3 | N/A | N/A | N/A | N/A | N/A | N/A |
| N4 | N/A | N/A | N/A | N/A | N/A | N/A |
| N3b | N/A | N/A | N/A | N/A | N/A | N/A |
| N4b | N/A | N/A | N/A | N/A | N/A | N/A |
| N5 | N/A | N/A | N/A | N/A | N/A | N/A |

Descriptive RMSE delta X over H: -0.191 pp; X over H+Z: -0.134 pp (negative favors Kalshi).

| Bootstrap quantity | Mean | 95% CI | p(value <= 0) |
|---|---:|---:|---:|
| Corr synergy | -0.001 | [-0.006, +0.003] | 0.643 |
| MSE-skill synergy | -0.002 | [-0.013, +0.006] | 0.622 |

Shuffle-company surrogate p-value: 0.0002.

TOOL telemetry: 87/88 arm requests used at least one lookup; calls: get_alt_data_description=87, get_company_profile=87.

## Result summary

Across the six cells, adding raw Kalshi X lowers descriptive RMSE in 5/6 H comparisons and 4/6 H+Z comparisons. However, 12/12 predefined company-clustered 95% synergy intervals include zero. On this 22-quarter sample, the run therefore shows suggestive point-estimate improvements but no statistically robust super-additive Kalshi effect.

- `surprise_early / BASE`: lowest arm RMSE is `fin+x+text` (3.406); both synergy intervals are not strictly positive.
- `surprise_early / TOOL`: lowest arm RMSE is `fin+x+text` (3.487); both synergy intervals are not strictly positive.
- `surprise_print / BASE`: lowest arm RMSE is `fin+x+text` (3.327); both synergy intervals are not strictly positive.
- `surprise_print / TOOL`: lowest arm RMSE is `fin+x` (3.385); both synergy intervals are not strictly positive.
- `rev_yoy / BASE`: lowest arm RMSE is `fin+text` (3.692); both synergy intervals are not strictly positive.
- `rev_yoy / TOOL`: lowest arm RMSE is `fin+x` (3.642); both synergy intervals are not strictly positive.

Direct arm RMSE differences are descriptive because Jihoon's benchmark does not attach a separate confidence interval to each direct delta. Statistical claims should therefore rely on the predefined company-clustered synergy intervals and be phrased without attributing the shuffle-Y surrogate specifically to Kalshi X.

## Reproduction

```bash
python3 kalshi/scripts/auto/s_af_kalshi_company_inventory.py
python3 kalshi/scripts/auto/s_ag_kalshi_company_features.py
python3 kalshi/scripts/auto/s_ai_factset_revsurprise_panel.py
python3 kalshi/scripts/auto/s_ah_kalshi_x_revsurprise.py
python3 kalshi/scripts/auto/s_ak_kalshi_prereport_features.py
python3 kalshi/scripts/auto/s_ap_kalshi_revenue_screen.py --apply-panel
python3 kalshi/scripts/auto/s_aq_kalshi_screening_agent.py --apply-panel --write-ticker-screen
python3 kalshi/scripts/auto/s_ar_kalshi_transcript_index.py
python3 kalshi/scripts/auto/s_at_kalshi_tool_context.py
python3 -m prediction --config prediction/configs/kalshi_full.yaml --render
python3 -m prediction --config prediction/configs/kalshi_full.yaml
python3 kalshi/scripts/auto/s_au_kalshi_benchmark_report.py
```

Generated run artifacts are under `prediction/outputs/kalshi_benchmark`. The exact rows are in
`prediction/outputs/kalshi_benchmark/evaluation_manifest.csv`; each cell contains `preds.csv`, `resume.jsonl`, and
`report.md`. Licensed FactSet and transcript data remain git-ignored.
