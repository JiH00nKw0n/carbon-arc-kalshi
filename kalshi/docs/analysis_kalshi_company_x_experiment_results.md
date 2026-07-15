# Kalshi company X experiment results

> Updated 2026-07-14 KST. Based on live Kalshi public API pulls, Slack context, the existing Factor1/Factor3 repo flow, Linq LLM Gateway env discovery, and Stock DB revenue actual/consensus tables.

## TL;DR

- Kalshi has a usable company-tagged/KPI-tagged universe: 442 candidate series, 2,289 market rows, 275 event-level feature rows.
- Clean numeric KPI ladder X features were extracted for 158 events; 112 matched numeric KPI rows map to 51 tickers.
- Server env discovery is done: the repo now loads Linq LLM Gateway when `LLM_GATEWAY_URL` + `LLM_GATEWAY_API_KEY` are present, and Stock DB credentials were found in server `.env` files. Secret values are intentionally not written here.
- Stock DB Y panel is no longer blocked. I built a point-in-time quarterly SALES revenue-surprise panel from `stock_earnings` + `stock_consensuses`: 1,351 rows, 50 tickers, 1,345 rows with `surprise_early`.
- First-pass latest/finalized Kalshi snapshot join was run, but leakage audit showed every post-cutoff Kalshi event feature occurred after `REPORT_DATE`.
- Leakage-safe pre-report Kalshi X was then rebuilt from Kalshi candlesticks at `REPORT_DATE - 1 day`: 15 rows, 14 tickers, 13 rows with pre-report prices.
- Pre-report statistical test: numeric implied-value correlation was negative and underpowered (`pre_implied_value -> surprise_early`: r=-0.323, p_boot=0.058, n=10); liquidity correlations were positive but not significant.
- LLM mini-ablation was run on 13 post-cutoff targets via Linq LLM Gateway: `fin`, `fin+kalshi`, `fin+text`, `fin+kalshi+text`. On common rows, adding Kalshi worsened RMSE in both comparisons.
- This completes a direct small-sample Slack-style experiment. A production-grade Factor1 channel benchmark is still separate work because Kalshi X is event-based and needs historical snapshots/channel wiring for broader coverage.

## Slack Experiment Interpreted

Slack requested:

```text
X = existing alt data plus Kalshi market/company KPI features
Y = revenue-related point-in-time target, fixed
Z = earnings call, fixed
Only X changes; test whether adding one Kalshi market improves prediction.
```

Existing repo benchmark flow:

| step | script | role | needs LLM gateway? |
|---|---|---|---:|
| panel build | `factor1/scripts/f1_20_panel.py` | joins X, Y, prior earnings-call index | no |
| LLM run | `factor1/scripts/f1_21_run.py` | runs `fin`, `fin+x`, `fin+text`, `fin+x+text` | yes |
| eval | `factor1/scripts/f1_22_eval.py` | evaluates baselines, LLM arms, synergy | no |

I updated the Factor1 LLM client so `f1_21_run.py` uses an OpenAI-compatible Linq LLM Gateway client when gateway env vars exist.

## What Was Run

```bash
python3 kalshi/scripts/auto/s_af_kalshi_company_inventory.py
python3 kalshi/scripts/auto/s_ag_kalshi_company_features.py
/Users/linqalpha/Desktop/linq/linq-mcp-server/.venv/bin/python kalshi/scripts/auto/s_ai_stockdb_revsurprise_panel.py --query-timeout-seconds 12
python3 kalshi/scripts/auto/s_ah_kalshi_x_revsurprise.py --panel kalshi/outputs/auto/kalshi_stockdb_revenue_surprise_panel.csv
python3 kalshi/scripts/auto/s_ah_kalshi_x_revsurprise.py --panel kalshi/outputs/auto/kalshi_stockdb_revenue_surprise_panel.csv --all-features --out-csv kalshi/outputs/auto/kalshi_x_revsurprise_panel_all_features.csv --out-md kalshi/docs/analysis_kalshi_x_revsurprise_all_features.md
python3 kalshi/scripts/auto/s_ak_kalshi_prereport_features.py
python3 kalshi/scripts/auto/s_al_kalshi_llm_ablation.py --concurrency 4 --request-timeout-seconds 120 --max-attempts 1
python3 -m py_compile kalshi/scripts/auto/s_af_kalshi_company_inventory.py kalshi/scripts/auto/s_ag_kalshi_company_features.py kalshi/scripts/auto/s_ah_kalshi_x_revsurprise.py kalshi/scripts/auto/s_ai_stockdb_revsurprise_panel.py kalshi/scripts/auto/s_ak_kalshi_prereport_features.py kalshi/scripts/auto/s_al_kalshi_llm_ablation.py factor1/scripts/f1_llm.py factor1/scripts/f1_21_run.py
```

Primary outputs:

- `kalshi/outputs/auto/kalshi_company_series.csv`
- `kalshi/outputs/auto/kalshi_company_markets.csv`
- `kalshi/outputs/auto/kalshi_company_event_features.csv`
- `kalshi/outputs/auto/kalshi_stockdb_revenue_surprise_panel.csv`
- `kalshi/outputs/auto/kalshi_x_revsurprise_panel.csv`
- `kalshi/outputs/auto/kalshi_x_revsurprise_panel_all_features.csv`
- `kalshi/docs/analysis_kalshi_company_inventory.md`
- `kalshi/docs/analysis_kalshi_company_features.md`
- `kalshi/docs/analysis_kalshi_stockdb_revenue_surprise_panel.md`
- `kalshi/docs/analysis_kalshi_x_revsurprise.md`
- `kalshi/docs/analysis_kalshi_x_revsurprise_all_features.md`
- `kalshi/outputs/auto/kalshi_prereport_x_revsurprise_panel.csv`
- `kalshi/outputs/auto/kalshi_llm_ablation_preds.csv`
- `kalshi/docs/analysis_kalshi_prereport_x_revsurprise.md`
- `kalshi/docs/analysis_kalshi_llm_ablation.md`

## Kalshi Company Universe

| metric | value |
|---|---:|
| fetched categories | Financials, Companies |
| candidate series | 442 |
| market rows | 2,289 |
| matched series | 196 |
| matched series tickers | 63 |
| conflict-filtered series | 1 |

Top tags:

| tag | series |
|---|---:|
| Companies | 222 |
| KPIs | 184 |
| Product launches | 66 |
| IPOs | 39 |
| CEOs | 33 |
| M&A | 20 |

QA note: Kalshi API returned one conflict where an Amazon-looking series exposed Tesla market rules. That series was marked `conflict_series_market` and excluded from matched downstream features.

## X Feature Universe

| metric | value |
|---|---:|
| event-level rows | 275 |
| matched event rows | 139 |
| matched event tickers | 57 |
| numeric KPI ladder rows | 158 |
| matched numeric KPI ladder rows | 112 |
| matched numeric KPI tickers | 51 |

Matched numeric KPI tickers:

`AAPL, ABNB, AMZN, BA, CAVA, CCL, CMG, COIN, CVNA, DASH, DPZ, EBAY, F, FDX, FUTU, GOOG, HD, HIMS, HOOD, INTC, LOW, LULU, LUV, LYFT, MAR, MCD, MELI, META, MTCH, MTN, NCLH, NFLX, RACE, RDDT, RIVN, ROKU, SBUX, SG, SHOP, SPOT, TGT, TOL, TOST, TSLA, UAL, UBER, ULTA, URBN, WEN, WH, WMT`

Top numeric KPI X features by Kalshi volume:

| ticker | event | metric | period | implied value | volume |
|---|---|---|---|---:|---:|
| CAVA | `KXCAVA-26MAYREST` | cava restaurants | Q1 2026 | 459 | 1,354,951.93 |
| TSLA | `KXTSLA-26JULDELIV` | total deliveries | Q2 2026 | 415,000 | 841,163.92 |
| TSLA | `KXTSLA-26JULPROD` | total production | Q2 2026 | 405,000 | 383,270.75 |
| HOOD | `KXHOOD-26JULFUNDED` | funded customers | Q2 2026 | 28,030,000 | 236,938.30 |
| COIN | `KXCOINBASE-26JULVOL` | total trading volume | Q2 2026 | 192,500,000,000 | 152,111.52 |
| RIVN | `KXRIVN-26AUGDELIV` | total vehicles delivered | Q2 2026 | 13,500 | 120,337.69 |
| BA | `KXBA-26JULDELIV` | commercial deliveries | Q2 2026 | 169.9 | 119,950.96 |
| F | `KXF-26JULUSSALES` | total vehicles US sales volume | Q2 2026 | 547,500 | 91,257.40 |
| SBUX | `KXSBUXA-28JANSTORES` | total global stores | 2026 | 41,650 | 82,791.40 |
| UBER | `KXUBERTRIPS-Q2` | trips |  | 3.942 | 77,076.61 |
| MTN | `KXMTN-26JUNSKIER` | skier visits | Q3 2026 | 7,698,000 | 74,775.27 |
| ULTA | `KXULTA-26JUNTXGRW` | transactions growth | Q1 2026 | 1.75 | 72,793.37 |
| FDX | `KXFDX-26JUNADV` | avg daily package volume | Q4 2026 | 17,100,000 | 71,367.89 |
| SG | `KXSG-26AUGMARGIN` | restaurant-level profit margin | Q2 2026 | 15.65 | 66,994.56 |
| HIMS | `KXHIMS-26AUGSUBS` | subscribers | Q2 2026 | 2,796,000 | 65,206.07 |

Feature method: `implied_value` integrates observed `greater-than` strike ladders as survival probabilities. No-tail and incremental variants are also written.

## Y Panel From Stock DB

Y source:

| component | Stock DB table | filter |
|---|---|---|
| revenue actual | `stock_earnings` | `item_type='SALES'`, `period_type=1` |
| point-in-time consensus | `stock_consensuses` | same stock/date/item/period |
| ticker identity | `stocks` | `is_primary IS TRUE` |

Y definitions:

```text
CONS_EARLY = latest quarterly SALES consensus at fiscal quarter end + 7d
CONS_PRINT = latest quarterly SALES consensus at least 1d before report market-effect date
surprise_early = (ACTUAL - CONS_EARLY) / CONS_EARLY
surprise_print = (ACTUAL - CONS_PRINT) / CONS_PRINT
```

Coverage:

| metric | value |
|---|---:|
| requested numeric KPI tickers | 51 |
| rows | 1,351 |
| rows with `surprise_early` | 1,345 |
| tickers with `surprise_early` | 50 |
| requested ticker missing from Y panel | GOOG |
| date range | 2019-01-31..2026-05-31 |
| missing `CONS_EARLY` rows | 6 |
| missing `CONS_PRINT` rows | 1 |
| `surprise_early` mean | +0.0190 |
| `surprise_early` sd | 0.0992 |

## First-Pass Latest Snapshot Kalshi X Test

Join rule: nearest Kalshi event feature date to `REPORT_DATE`, tolerance 60 days. For duplicated earnings-report matches, the most liquid Kalshi event is kept.

### Numeric KPI Ladder Only

| metric | value |
|---|---:|
| joined rows | 12 |
| joined tickers | 11 |
| test status | below 15-row threshold |

This is too small for the clustered bootstrap/surrogate test. The joined examples are mostly current or recent KPI markets such as CAVA restaurants, CCL available lower berth days, COIN volume, FDX package volume, and retailer/home-improvement metrics.

### All Company Features

| metric | value |
|---|---:|
| joined rows | 15 |
| joined tickers | 14 |
| numeric KPI rows | 12 |
| other company event rows | 3 |

Correlation tests:

| X | r | p_boot | p_surrogate | n |
|---|---:|---:|---:|---:|
| volume_sum | +0.017 | 0.903 | 0.873 | 15 |
| open_interest_sum | +0.004 | 0.968 | 0.975 | 15 |
| implied_value | n/a | n/a | n/a | 12 |
| implied_value_no_tail | n/a | n/a | n/a | 12 |
| implied_value_incremental | n/a | n/a | n/a | 12 |

Result: in this first-pass sample, raw Kalshi liquidity variables do not predict revenue surprise, and numeric implied KPI values have too few joined rows for a reliable clustered test.

Leakage audit: all 13 post-cutoff joined latest-snapshot rows had `feature_date > REPORT_DATE` and finalized market status. Those latest/finalized values are useful for inventory and coverage, but not valid as prediction inputs.

## Leakage-Safe Pre-Report Kalshi X Test

I rebuilt X from Kalshi daily candlesticks using the latest available market price at `REPORT_DATE - 1 day`.

| metric | value |
|---|---:|
| rows | 15 |
| tickers | 14 |
| rows with pre-report prices | 13 |
| market candle fetch misses | 7 |

Post-cutoff correlation tests:

| X | r | p_boot | n |
|---|---:|---:|---:|
| pre_implied_value | -0.323 | 0.058 | 10 |
| pre_implied_value_no_tail | -0.323 | 0.058 | 10 |
| pre_implied_value_incremental | -0.354 | 0.082 | 10 |
| pre_prob_lowest | -0.503 | 0.296 | 10 |
| pre_prob_highest | +0.226 | 0.147 | 10 |
| pre_volume_sum | +0.494 | 0.379 | 13 |
| pre_open_interest_sum | +0.496 | 0.369 | 13 |

Interpretation: the pre-report numeric KPI signal is not a robust positive predictor in this sample. The strongest numeric relation is actually negative and still underpowered.

## LLM Mini-Ablation

To directly test "does adding one Kalshi market improve prediction," I ran a 4-arm LLM ablation on the leakage-safe pre-report panel:

| arm | input |
|---|---|
| `fin` | revenue history and point-in-time consensus only |
| `fin+kalshi` | `fin` plus pre-report Kalshi market feature |
| `fin+text` | `fin` plus prior earnings-call transcript |
| `fin+kalshi+text` | all three |

Run details:

| metric | value |
|---|---:|
| targets | 13 |
| calls | 52 |
| model | `gpt-5.5-2026-04-23` |
| reasoning effort | `medium` |
| estimated cost | $2.25 |
| timed-out gateway calls | 5 |

Arm metrics:

| arm | n | RMSE pct | MAE pct | corr | R2 | sign |
|---|---:|---:|---:|---:|---:|---:|
| fin | 11 | 4.171 | 2.625 | -0.099 | -1.973 | 0.727 |
| fin+kalshi | 12 | 4.031 | 2.666 | -0.014 | -1.946 | 0.583 |
| fin+text | 12 | 3.176 | 2.305 | -0.214 | -1.187 | 0.583 |
| fin+kalshi+text | 12 | 3.518 | 2.676 | -0.252 | -1.428 | 0.333 |

Common-row deltas:

| comparison | common n | RMSE delta |
|---|---:|---:|
| `fin+kalshi` minus `fin` | 10 | +0.242 pct points |
| `fin+kalshi+text` minus `fin+text` | 11 | +0.302 pct points |

Negative delta would mean Kalshi improved the comparison. Here both deltas are positive, so Kalshi did not improve the LLM prediction in this small leakage-safe sample.

## Interpretation

The useful finding is not "Kalshi has no value." The useful finding is narrower:

1. Kalshi has a real company/KPI data universe.
2. Row-level revenue-surprise Y can be built from Stock DB without direct FactSet raw table access.
3. Latest/finalized Kalshi snapshots are leakage-prone for post-cutoff earnings prediction.
4. Pre-report Kalshi candlesticks fix the leakage issue, but coverage is small and the observed signal did not improve either statistical or LLM prediction in this sample.
5. The text leg helped more than Kalshi in the LLM run; adding Kalshi to text worsened common-row RMSE.

## Remaining Work For Exact Factor1 Benchmark

To finish the full `X + Kalshi market -> Y with fixed Z` benchmark:

1. Wire `kalshi` as a Factor1 channel with a stable `x_yoy` or `kalshi_feature` transform.
2. Build or reuse a transcript index for the same Stock DB tickers so Z is fixed like existing `web/card/foot` runs.
3. Decide whether Kalshi X should use latest public snapshots, historical market snapshots, or only pre-report market prices. The leakage-safe answer is historical pre-report prices.
4. Run:

```bash
F1_CHANNEL=kalshi python3 factor1/scripts/f1_20_panel.py
F1_CHANNEL=kalshi python3 factor1/scripts/f1_21_run.py
F1_CHANNEL=kalshi python3 factor1/scripts/f1_22_eval.py
```

The LLM stage is gateway-ready now; the channel/Z wiring is the remaining implementation work.
