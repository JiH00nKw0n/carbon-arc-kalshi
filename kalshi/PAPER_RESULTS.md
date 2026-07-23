# Kalshi Paper Experiment

## Protocol

- Config: `prediction/configs/kalshi_paper.yaml`
- Seeds: 2026, 2027, 2028
- Repetitions: 3
- Model: `gpt-5.5-2026-04-23` at `medium` reasoning effort
- Evaluation rows: 21 company-quarters /
  16 firms
- Grid: 3 targets x 2 variants x 4 arms
- Complete prediction calls: 1512
- Calls with saved rationale: 1512
- Tool invocations: 1506
- Screening calls: 14 (7 medium-effort screeners + 7 high-effort auditors)
- Repaired calls after exhausting the original retry budget: 2
- Recorded API cost: $141.26

Every call log contains the exact system/user prompt, prompt hash, complete parsed structured
output, predicted revenue, confidence, rationale, tool calls and returned text, token usage, cost,
retry count, and error status. The exporter verifies that BASE and TOOL prompts are byte-identical
for the same target and arm. Raw call logs remain under the git-ignored run directory. The two
original timeout records and their replacements are preserved in cell-level `repairs.jsonl` files.

## Result Coverage

The prediction run is complete for the paper grid. It contains 1512 LLM calls:
3 targets x 2 tool variants x 4 source arms x 21 targets x 3 repetitions.
Evaluation produces 216 run-level result rows: 108 numeric rows
and 108 structural N/A baseline rows. Averaging the three repetitions leaves
36 numeric Y/variant/model rows. The headline paper sections below use only a
subset of those rows; the complete six-cell grid is reported under `Complete Six-Cell Results`.

| Experiment family | Status | Scope |
|---|---|---|
| Four-source ablation | Complete | 3 Y definitions x BASE/TOOL x H/H+X/H+Z/H+X+Z x 3 runs |
| Analyst comparison | Complete | Early and latest consensus, TOOL/H+X+Z |
| Tool ablation | Complete | BASE versus TOOL on matched prompts |
| Prediction rationales and qualitative cases | Complete | Rationale saved for every call; two cases selected by a fixed rule |
| Screening decisions and rationale figure | Complete | Every candidate pair has screener and auditor logs |
| Classical baseline table | Partial by design | N0 and N2 available; six X-dependent models are N/A because no scalar X is defined |
| Quantitative pre/post-screen X-Y correlation | Not run | The paper's diagnostic requires a scalar X; a raw probability ladder has no pre-specified scalar equivalent |
| A/C/B architecture sensitivity | Not run | Auxiliary experiment in Jihoon's research runner; requires additional prompt schemas and calls |
| One-call versus two-call Z-depth sensitivity | Not run | Auxiliary experiment in Jihoon's research runner; requires additional calls |

Therefore, the 1,512-call paper prediction grid is complete, but this is not a complete replication
of every auxiliary experiment in Jihoon's repository. `kalshi_screening.tex` is explicitly a
screening funnel, not a replacement result for the paper's scalar-X correlation table.

## Experimental Contract

| Component | Fixed definition |
|---|---|
| H | Up to six prior quarterly actuals, point-in-time consensus values and surprises, plus the target-quarter anchor |
| X | The raw variable-length Kalshi probability ladder for the company KPI; no scalarization |
| Z | Up to two most recent corrected earnings calls at least 31 days before the report, truncated to 48,000 characters each |
| Output | Predicted total revenue in $M, confidence and rationale; the target metric is derived deterministically from predicted revenue |
| Y: early surprise | `(actual revenue - early consensus) / early consensus` |
| Y: latest surprise | `(actual revenue - latest pre-report consensus) / latest consensus` |
| Y: revenue YoY | `(actual revenue - prior-year revenue) / prior-year revenue` |
| Row matching | Every H/H+X/H+Z/H+X+Z arm and BASE/TOOL variant uses the same target rows |
| Primary metrics | RMSE in percentage points, OOS R-squared, calibrated OOS R-squared and Pearson correlation |

`H quarters shown` counts prior financial rows rendered in the prompt. `Prior X ladder quarters
shown` counts historical Kalshi ladders rendered before the target-quarter ladder. `Prior calls`
counts eligible corrected transcripts included in Z.

## Universe

| Stage | Unit | Count | Tickers |
|---|---|---:|---:|
| Numeric KPI candidates | `(ticker, KPI)` pairs | 52 | 42 |
| Revenue-metric screen O | `(ticker, KPI)` pairs | 51 | 42 |
| Firm revenue-driver screen O | `(ticker, KPI)` pairs | 23 | 21 |
| Strong-O ticker screen | tickers | 18 | 18 |
| Final post-cutoff matched sample | company-quarters | 21 | 16 |

The metric screen removes KPI types that are not revenue bases. The firm screen applies one
medium-effort screener and one high-effort auditor to every candidate pair and judges the KPI
against total company revenue. `strength` is confidence in the O/X decision, not estimated revenue
share. This is a Kalshi-specific adaptation of the paper's channel-level screening prompt:
the decision unit is `(ticker, KPI metric)` and the high-effort audit pass is additional. The
prediction prompts themselves use the paper protocol. The resulting screen is frozen before
prediction. This rerun honestly produced DPZ as strong and UAL as moderate, so the final sample is
21 rather than the legacy one-run sample's 22; the screen was not repeated until a preferred
universe appeared.

Final tickers: `ABNB, BA, COIN, CVNA, DASH, DPZ, HIMS, LYFT, MO, MTCH, PLNT, RACE, STZ, TOL, TSLA, UBER`.

| Ticker | Target fiscal quarters | Targets | H quarters shown | Prior X ladder quarters shown | Prior calls |
|---|---|---:|---|---|---|
| ABNB | 2026-03-31 | 1 | 6 | 0 | 2 |
| BA | 2025-12-31, 2026-03-31 | 2 | 6, 6 | 0, 1 | 1, 2 |
| COIN | 2026-03-31 | 1 | 6 | 5 | 2 |
| CVNA | 2026-03-31 | 1 | 6 | 0 | 2 |
| DASH | 2025-12-31, 2026-03-31 | 2 | 6, 6 | 0, 1 | 2, 2 |
| DPZ | 2026-06-30 | 1 | 6 | 0 | 2 |
| HIMS | 2026-03-31 | 1 | 6 | 0 | 2 |
| LYFT | 2026-03-31 | 1 | 6 | 0 | 2 |
| MO | 2026-03-31 | 1 | 6 | 0 | 2 |
| MTCH | 2025-12-31, 2026-03-31 | 2 | 6, 6 | 0, 1 | 2, 2 |
| PLNT | 2026-03-31 | 1 | 6 | 0 | 2 |
| RACE | 2026-03-31 | 1 | 6 | 0 | 2 |
| STZ | 2026-05-31 | 1 | 6 | 0 | 2 |
| TOL | 2026-04-30 | 1 | 6 | 0 | 2 |
| TSLA | 2025-12-31, 2026-03-31 | 2 | 6, 6 | 6, 6 | 1, 2 |
| UBER | 2025-12-31, 2026-03-31 | 2 | 6, 6 | 0, 1 | 2, 2 |

## Tool Variant

BASE receives no tools. TOOL receives two no-argument functions:
`get_company_profile` returns the frozen public business/revenue-driver profile, and
`get_alt_data_description` returns the frozen Kalshi ladder methodology description. Their
returned text and full call order are stored in each call's `tool_trace`.

Classical baselines N1, N3, N4, N3b, N4b and N5 are N/A because they require a dense scalar X.
Kalshi X is intentionally kept as a raw ladder. N0 (historical average) and N2 (call sentiment)
remain available because they do not require scalarizing X.

## Analyst Accuracy

| Consensus snapshot | Analyst RMSE | Kalshi method RMSE | Win rate |
|---|---:|---:|---:|
| Early | 4.644 | 3.517 | 55.6% |
| Latest pre-report | 3.911 | 3.585 | 54.0% |

Values are arithmetic means of the three per-repetition metrics. The Kalshi method is the
paper-consistent `TOOL / H+X+Z` arm; analyst consensus predicts zero surprise.

## Revenue-YoY Results

| Sources | RMSE | OOS R-squared | Calibrated R-squared | Correlation |
|---|---:|---:|---:|---:|
| H | 8.923 | 0.791 | 0.760 | 0.893 |
| H+X | 5.165 | 0.930 | 0.923 | 0.970 |
| H+Z | 6.056 | 0.904 | 0.890 | 0.959 |
| H+X+Z | 5.744 | 0.913 | 0.912 | 0.967 |

The best point-estimate RMSE is H+X, not the full H+X+Z arm. The full arm remains the predefined
headline method so that reporting stays symmetric with the paper design.

## Synergy

- Correlation synergy: -0.078,
  95% pooled-bootstrap CI [-0.226,
  -0.001]
- MSE-skill synergy: -0.147,
  95% pooled-bootstrap CI [-0.394,
  -0.003]

Synergy compares the observed full model with the additive expectation
`(H+X improvement) + (H+Z improvement)`. Both intervals are below zero in this run, so the
Kalshi-plus-transcript combination is sub-additive; this is evidence against a positive synergy
claim, not evidence that Kalshi X alone has no value.

## Complete Six-Cell Results

All point estimates below are arithmetic means of three independent runs. The pooled-bootstrap
summary concatenates the three run-specific company-clustered bootstrap distributions; it is a
run-level sensitivity summary, not 15,000 independent observations. Negative RMSE changes favor
the model with Kalshi X. Run-specific metrics and inference outputs are preserved in
`metrics_by_rep.csv`, `synergy_by_rep.csv`, and `surrogate_by_rep.csv`.

### Early-consensus revenue surprise / BASE

| Model | RMSE | OOS R-squared | Calibrated R-squared | Correlation | MAE | Sign |
|---|---:|---:|---:|---:|---:|---:|
| H | 3.856 | +0.235 | +0.140 | +0.487 | 2.449 | 0.698 |
| H+X | 3.538 | +0.363 | +0.197 | +0.625 | 2.538 | 0.603 |
| H+Z | 3.666 | +0.316 | +0.151 | +0.596 | 2.508 | 0.667 |
| H+X+Z | 3.488 | +0.381 | +0.301 | +0.652 | 2.351 | 0.651 |
| N0 | 6.144 | -0.920 | - | -0.297 | 4.159 | 0.524 |
| N1 | N/A | N/A | N/A | N/A | N/A | N/A |
| N2 | 4.465 | -0.014 | - | -0.174 | 3.069 | 0.714 |
| N3 | N/A | N/A | N/A | N/A | N/A | N/A |
| N4 | N/A | N/A | N/A | N/A | N/A | N/A |
| N3b | N/A | N/A | N/A | N/A | N/A | N/A |
| N4b | N/A | N/A | N/A | N/A | N/A | N/A |
| N5 | N/A | N/A | N/A | N/A | N/A | N/A |

- RMSE change from H after adding X: -0.317 pp.
- RMSE change from H+Z after adding X: -0.178 pp.
- Correlation synergy: -0.078, 95% pooled-bootstrap CI [-0.571, +0.333], `p(value <= 0)=0.601`.
- MSE-skill synergy: -0.051, 95% pooled-bootstrap CI [-0.448, +0.226], `p(value <= 0)=0.528`.
- Shuffle-company surrogate p-values by seed: 2026=0.0150, 2027=0.0226, 2028=0.0110.

### Early-consensus revenue surprise / TOOL

| Model | RMSE | OOS R-squared | Calibrated R-squared | Correlation | MAE | Sign |
|---|---:|---:|---:|---:|---:|---:|
| H | 3.899 | +0.220 | +0.113 | +0.479 | 2.511 | 0.667 |
| H+X | 3.458 | +0.391 | +0.213 | +0.654 | 2.533 | 0.587 |
| H+Z | 3.609 | +0.337 | +0.193 | +0.607 | 2.424 | 0.714 |
| H+X+Z | 3.517 | +0.370 | +0.279 | +0.637 | 2.422 | 0.651 |
| N0 | 6.144 | -0.920 | - | -0.297 | 4.159 | 0.524 |
| N1 | N/A | N/A | N/A | N/A | N/A | N/A |
| N2 | 4.465 | -0.014 | - | -0.174 | 3.069 | 0.714 |
| N3 | N/A | N/A | N/A | N/A | N/A | N/A |
| N4 | N/A | N/A | N/A | N/A | N/A | N/A |
| N3b | N/A | N/A | N/A | N/A | N/A | N/A |
| N4b | N/A | N/A | N/A | N/A | N/A | N/A |
| N5 | N/A | N/A | N/A | N/A | N/A | N/A |

- RMSE change from H after adding X: -0.441 pp.
- RMSE change from H+Z after adding X: -0.092 pp.
- Correlation synergy: -0.137, 95% pooled-bootstrap CI [-0.700, +0.206], `p(value <= 0)=0.683`.
- MSE-skill synergy: -0.133, 95% pooled-bootstrap CI [-0.774, +0.181], `p(value <= 0)=0.638`.
- Shuffle-company surrogate p-values by seed: 2026=0.0118, 2027=0.0154, 2028=0.0210.

### Latest-consensus revenue surprise / BASE

| Model | RMSE | OOS R-squared | Calibrated R-squared | Correlation | MAE | Sign |
|---|---:|---:|---:|---:|---:|---:|
| H | 3.674 | -0.081 | -0.128 | +0.219 | 2.462 | 0.619 |
| H+X | 3.575 | -0.024 | -0.154 | +0.227 | 2.593 | 0.524 |
| H+Z | 3.625 | -0.052 | -0.154 | +0.084 | 2.385 | 0.698 |
| H+X+Z | 3.662 | -0.074 | -0.227 | +0.138 | 2.495 | 0.556 |
| N0 | 4.662 | -0.740 | - | -0.213 | 3.294 | 0.571 |
| N1 | N/A | N/A | N/A | N/A | N/A | N/A |
| N2 | 3.568 | -0.019 | - | -0.155 | 2.427 | 0.762 |
| N3 | N/A | N/A | N/A | N/A | N/A | N/A |
| N4 | N/A | N/A | N/A | N/A | N/A | N/A |
| N3b | N/A | N/A | N/A | N/A | N/A | N/A |
| N4b | N/A | N/A | N/A | N/A | N/A | N/A |
| N5 | N/A | N/A | N/A | N/A | N/A | N/A |

- RMSE change from H after adding X: -0.099 pp.
- RMSE change from H+Z after adding X: +0.038 pp.
- Correlation synergy: +0.027, 95% pooled-bootstrap CI [-0.327, +0.414], `p(value <= 0)=0.460`.
- MSE-skill synergy: -0.105, 95% pooled-bootstrap CI [-0.595, +0.175], `p(value <= 0)=0.678`.
- Shuffle-company surrogate p-values by seed: 2026=0.5181, 2027=0.7646, 2028=0.3923.

### Latest-consensus revenue surprise / TOOL

| Model | RMSE | OOS R-squared | Calibrated R-squared | Correlation | MAE | Sign |
|---|---:|---:|---:|---:|---:|---:|
| H | 3.699 | -0.096 | -0.125 | +0.234 | 2.444 | 0.635 |
| H+X | 3.525 | -0.001 | -0.173 | +0.264 | 2.669 | 0.540 |
| H+Z | 3.606 | -0.041 | -0.170 | +0.123 | 2.462 | 0.730 |
| H+X+Z | 3.585 | -0.031 | -0.081 | +0.211 | 2.452 | 0.587 |
| N0 | 4.662 | -0.740 | - | -0.213 | 3.294 | 0.571 |
| N1 | N/A | N/A | N/A | N/A | N/A | N/A |
| N2 | 3.568 | -0.019 | - | -0.155 | 2.427 | 0.762 |
| N3 | N/A | N/A | N/A | N/A | N/A | N/A |
| N4 | N/A | N/A | N/A | N/A | N/A | N/A |
| N3b | N/A | N/A | N/A | N/A | N/A | N/A |
| N4b | N/A | N/A | N/A | N/A | N/A | N/A |
| N5 | N/A | N/A | N/A | N/A | N/A | N/A |

- RMSE change from H after adding X: -0.173 pp.
- RMSE change from H+Z after adding X: -0.020 pp.
- Correlation synergy: +0.046, 95% pooled-bootstrap CI [-0.520, +0.827], `p(value <= 0)=0.500`.
- MSE-skill synergy: -0.084, 95% pooled-bootstrap CI [-1.043, +0.927], `p(value <= 0)=0.588`.
- Shuffle-company surrogate p-values by seed: 2026=0.1390, 2027=0.3719, 2028=0.6293.

### Revenue YoY / BASE

| Model | RMSE | OOS R-squared | Calibrated R-squared | Correlation | MAE | Sign |
|---|---:|---:|---:|---:|---:|---:|
| H | 8.596 | +0.806 | +0.767 | +0.899 | 6.588 | 0.905 |
| H+X | 5.671 | +0.915 | +0.904 | +0.964 | 4.356 | 1.000 |
| H+Z | 6.457 | +0.891 | +0.871 | +0.952 | 4.348 | 0.952 |
| H+X+Z | 5.801 | +0.912 | +0.906 | +0.964 | 3.913 | 0.984 |
| N0 | 25.325 | -0.682 | - | +0.140 | 16.679 | 0.810 |
| N1 | N/A | N/A | N/A | N/A | N/A | N/A |
| N2 | 21.378 | -0.199 | - | +0.290 | 17.848 | 0.810 |
| N3 | N/A | N/A | N/A | N/A | N/A | N/A |
| N4 | N/A | N/A | N/A | N/A | N/A | N/A |
| N3b | N/A | N/A | N/A | N/A | N/A | N/A |
| N4b | N/A | N/A | N/A | N/A | N/A | N/A |
| N5 | N/A | N/A | N/A | N/A | N/A | N/A |

- RMSE change from H after adding X: -2.925 pp.
- RMSE change from H+Z after adding X: -0.656 pp.
- Correlation synergy: -0.063, 95% pooled-bootstrap CI [-0.203, +0.004], `p(value <= 0)=0.962`.
- MSE-skill synergy: -0.105, 95% pooled-bootstrap CI [-0.357, +0.048], `p(value <= 0)=0.888`.
- Shuffle-company surrogate p-values by seed: 2026=0.0002, 2027=0.0002, 2028=0.0002.

### Revenue YoY / TOOL

| Model | RMSE | OOS R-squared | Calibrated R-squared | Correlation | MAE | Sign |
|---|---:|---:|---:|---:|---:|---:|
| H | 8.923 | +0.791 | +0.760 | +0.893 | 6.738 | 0.905 |
| H+X | 5.165 | +0.930 | +0.923 | +0.970 | 3.927 | 1.000 |
| H+Z | 6.056 | +0.904 | +0.890 | +0.959 | 4.184 | 0.952 |
| H+X+Z | 5.744 | +0.913 | +0.912 | +0.967 | 3.910 | 1.000 |
| N0 | 25.325 | -0.682 | - | +0.140 | 16.679 | 0.810 |
| N1 | N/A | N/A | N/A | N/A | N/A | N/A |
| N2 | 21.378 | -0.199 | - | +0.290 | 17.848 | 0.810 |
| N3 | N/A | N/A | N/A | N/A | N/A | N/A |
| N4 | N/A | N/A | N/A | N/A | N/A | N/A |
| N3b | N/A | N/A | N/A | N/A | N/A | N/A |
| N4b | N/A | N/A | N/A | N/A | N/A | N/A |
| N5 | N/A | N/A | N/A | N/A | N/A | N/A |

- RMSE change from H after adding X: -3.758 pp.
- RMSE change from H+Z after adding X: -0.313 pp.
- Correlation synergy: -0.078, 95% pooled-bootstrap CI [-0.226, -0.001], `p(value <= 0)=0.976`.
- MSE-skill synergy: -0.147, 95% pooled-bootstrap CI [-0.394, -0.003], `p(value <= 0)=0.979`.
- Shuffle-company surrogate p-values by seed: 2026=0.0002, 2027=0.0002, 2028=0.0002.

## Qualitative Selection

The early- and latest-consensus cases are selected by the pre-specified rule saved in
`kalshi/paper/data/qualitative_cases.json`: largest mean three-repetition reduction in absolute
`H+Z` error after adding X, with distinct tickers when possible. The displayed rationale and
estimate come from the replicate closest to the three-run mean, and its seed and prompt hash are
saved with the case.

Selected cases: TSLA (surprise_early, seed 2028), COIN (surprise_print, seed 2027).

## Generated Artifacts

- `kalshi/paper/figures/kalshi_screen_figure.html`
- `kalshi/paper/figures/kalshi_qualitative_figure.html`
- `kalshi/paper/figures/kalshi_accuracy_chart.html`
- `kalshi/paper/tables/kalshi_synergy.tex`
- `kalshi/paper/tables/kalshi_baselines.tex`
- `kalshi/paper/tables/kalshi_screening.tex`
- `kalshi/paper/tables/kalshi_tool.tex`
- `kalshi/paper/tables/kalshi_tickers.tex`
- `kalshi/paper/tables/kalshi_full_grid.tex`
- Supporting CSV/JSON files under `kalshi/paper/data/`
