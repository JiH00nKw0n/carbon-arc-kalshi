# Lead-Lag 4-Scenario Experiment Design

> Paper extension of the prior Kalshi-only Lead-Lag work. Goal: show that
> CarbonArc structured panel + LLM-derived unstructured features
> *separately and jointly* lift forecast accuracy on Kalshi macro &
> company-event markets.

**상태 (2026-05-18)**: blueprint 단계. Phase 5 에서 CA0030/0056/0034 framework 3개 구매했지만 본 4-scenario 백테스트는 *아직 미실행*. Phase 5 의 lag corr 결과 (`docs/analysis_per_dataset.md`) 가 시그널 방향 / 데이터셋 적합성 명확히 한 후 본 디자인으로 evaluation 진행 예정. 그 사이는 `LOAD_CA_FEATURES` step 만 활성화하면 됨.

---

## 1. Scope & target markets

### Track A — Macro (primary lead-lag thesis + Phase 0 join)

| Kalshi ticker | Macro release (truth) | CA features (when bought) | Phase 0 lead window |
|---|---|---|---|
| KXUSNFP / KXPAYROLLS / KXJOBSRELEASE | NFP, ADP, Unemployment | CA0053 jobm, CA0043A Job Openings, WC job postings | 1-day lag, 5+ days lead |
| KXJOBLESSCLAIMS | DOL initial claims | CA0053 (real-time hire/sep events) | — |
| KXUSRETAIL / KXRETAIL | Census Retail Sales | CA0028/0056 card, CA0030 clickstream, CA0060 foot | 9-15 days lead |
| KXPCECORE | BEA Core PCE | CA0028/0056 card, CA0049 medical, CA009 ad, CA0040 trade | 23-27 days lead |
| KXRELEASECPI / KXCPICORE220 | BLS CPI | CA0077 commodities, CA0058 health card | 7-11 days lead |
| KXAIRFARECPI / KXSHELTERCPI | BLS CPI components | CA0058 health card | 7 days lead |
| KXUMICHOVR / KXUSMICHCSP | UMich preliminary | CA0030, CA009, CA0060, CA0054 | 11-15 days lead |
| KXISMSERVICES | ISM Services PMI | CA0025 freight | 6 days lead |
| KXPPISEMI | BLS PPI semis | CA0080 maritime, CA0040 trade | 12 days lead |
| KXCHTRADEBAL | China trade balance | CA0040 trade claims | 6 days lead |
| KXTBCOUNT / KXH5N1COUNT / KXGONORRHEACOUNT / KXMPOXCOUNT | CDC disease counts | CA0049 medical/pharmacy claims | direct |

### Track B — Company-event (secondary; mostly Lead-Lag paper continuity)

| Kalshi ticker | Question | CA features |
|---|---|---|
| KXARTISTSTREAMSY (Beatles, Iceman, etc.) | streaming volume by artist | CA007/CA0046 music, CA0030 clickstream |
| KXAISPIKE | AI model score thresholds | CA0084 jobs (130 WC tickers — Anthropic/OpenAI), CA0054 |
| KXOSCARPIC / KXALBUMSALES | media outcomes | CA0011/CA0016 box office |

---

## 2. Four scenarios

| # | Name | Input set | Lift hypothesis |
|---|---|---|---|
| S1 | **Kalshi-only baseline** | Market mid-price, last-N candle features, time-to-expiry | Auto-regressive baseline; no alt-data |
| S2 | **Kalshi + CA structured** | S1 + monthly CA tabular features (card spend, claims, clicks, etc.) at the markets' resolution | "Pure quant" + alt-data lift |
| S3 | **Kalshi + LLM (text-only)** | S1 + LLM features from market description, related Kalshi news, headlines (CA *not* used) | Disentangle "LLM-on-public-text" effect |
| S4 | **Kalshi + CA + LLM** | S1 + S2 features + LLM summaries of CA tabular rows fanned-out to markets | The meeting's differentiator |

The meeting's framing was a 2×2: {LLM, no-LLM} × {CA, no-CA}. Lifts:
- **S2 − S1**: pure CA structured lift.
- **S3 − S1**: pure LLM-on-text lift.
- **S4 − S2**: LLM-derived value of *making CA tables readable*.
- **S4 − S3**: structured CA's value when LLM is already present.

---

## 3. Targets, splits, metrics

### Targets
- **Macro markets**: probability the YES side wins (price → outcome). Outcome resolved by macro print.
- **Company markets**: same.
- For range markets (KXHIGHINFLATION, KXGDPYEAR with multiple strike levels): treat each strike as separate market.

### Time splits
- **Train**: market-closes from Jan 2020 to Dec 2024.
- **Validation**: Jan 2025 to Sep 2025.
- **Test**: Oct 2025 onward (forward-walking; refit monthly).
- **No look-ahead**: features at time *t* must be available before market close.

### Metrics (all reported, primary in bold)
1. **Brier score** (lower = better). Primary because it scores calibration not just sign.
2. AUC of probability vs actual outcome (sanity check).
3. **Realized PnL** on a $1/contract bet-when-`|edge|>θ` strategy, fees=0.5% one-way. Sweep θ ∈ {0.02, 0.05, 0.10}.
4. Hit rate (binary correctness).
5. **Lead-time PnL decomposition**: PnL contribution by time-to-close bucket {1d, 3d, 1w, 2w, 1m} — shows whether the alt-data edge is *early* or just *closing-day reweighting*.

### Confidence intervals
Block bootstrap (3-week blocks) for each metric. Report 95% CIs.

---

## 4. Feature engineering (per scenario)

### S1 features (always present)
- Last-close mid price (no-trade fallback to YES bid mid).
- 1d / 3d / 7d / 14d price returns.
- Last-3-day rolling vol.
- Days to market close.
- Order book imbalance (if `kalshi_orderbook` is queriable for that market).
- Market category one-hot (Economics / Health / Companies).

### S2 features (CA structured)
- For each CA dataset bought, monthly aggregate at the relevant geographic resolution.
- Standardize columns: `(date_month, ca_dataset, entity_ticker, metric_value, yoy_pct, mom_pct)`.
- Join to Kalshi market by `(ticker_id|category, date_month)`.
- Optional rolling lag features (1m, 3m, 6m).

### S3 features (LLM-on-text)
- For each market, take its `title` + `sub_title` + `series_ticker description` + last 7 days of `news_rss_search` headlines mentioning the market subject.
- LLM (Claude Sonnet 4.6) → 3-dim summary:
  1. **Sentiment** (−1 .. +1) toward YES.
  2. **Recency-weighted news intensity** (0..10).
  3. **Confidence** (0..1).
- Cache embedding of LLM rationale text for downstream learning-to-rank.

### S4 features (CA × LLM fan-out)
- For each CA row (or daily-aggregated CA window), apply `prompts/ca_row_to_text.md` → 1-2 sentence natural-language summary.
- Run `kalshi_search(summary)` → top-k market candidates. Compute LLM-judged relevance score (0..1) per market.
- For each market, aggregate relevance-weighted CA features (mean of relevant rows in last 30 days).
- Optionally feed the summary text into Claude as a "context block" for final YES probability.

---

## 5. Modeling

Same model class across all four scenarios to keep comparisons clean:

```
Gradient Boosted Trees (LightGBM)
  · objective: binary logistic (for binary markets) / regression (for level markets)
  · early stopping on validation Brier
  · monotone constraints where economic intuition is strong (e.g.,
    pharmacy_claims_yoy should monotonically increase prob(CPI-medical YES))
  · interpretable via SHAP — required for the paper's "interpretable ML" claim
```

Why GBT, not deep nets:
- Sample size (Kalshi market-closes) is small relative to feature dim.
- Methodology requirement: "interpretable ML to capture
  non-linear patterns while still understanding drivers". GBT + SHAP fits exactly.

Holdout for ablations: drop one feature group at a time, report Brier delta.

---

## 6. Outputs / deliverables

For the paper:
- `figs/scenario_brier_bar.pdf` — Brier per scenario per market category.
- `figs/leadtime_pnl.pdf` — PnL by time-to-close bucket.
- `figs/shap_top_features_per_market.pdf` — interpretability.
- `tables/scenario_metrics.tex` — full numeric grid (CIs).
- `appendix/feature_dictionary.tex` — every CA column + every LLM scalar.

For internal review:
- `notebooks/04_scenario_skeleton.ipynb` — wires the harness end-to-end on sample data; swap-in real data when bought.
- `notebooks/05_llm_fanout_poc.ipynb` — Phase 3 deliverable.

---

## 7. Open issues to resolve in the next CarbonArc meeting

1. **Budget**: $50 promo is feasibility-only. To run S2/S4 we need
   real per-market panels — ballpark $50-$150 for the 4 datasets listed
   in PHASE1 recommendations.
2. **Kalshi historical depth**: confirm `kalshi_candlesticks` returns
   per-minute or per-hour back to 2020 for the macro tickers (some new
   tickers like KXUSNFP may have <12 months of price history).
3. **Authorization for daily refits**: paper draft will use forward-walk
   evaluation with monthly refits — confirm OK with team.
4. **CA dataset publication timestamps**: lag_str strings are vendor docs.
   Need to confirm "T+5 Days" = data-end + 5 vs ingestion + 5. This
   determines actual lead window vs Kalshi market close.
5. **추가 의제 항목 (collab partner 측 요청)** — 공유되면 본 framework 와 매핑.

---

## 8. Code skeleton

```
scripts/
  phase2_load_kalshi_candles.py   # cache market history
  phase2_build_S1_features.py     # candle-only baseline features
  phase2_build_S2_features.py     # + CA structured (no-op until data bought)
  phase2_build_S3_features.py     # + LLM-on-text
  phase2_build_S4_features.py     # + CA × LLM fan-out
  phase2_train.py                 # fit GBT, save model per scenario
  phase2_evaluate.py              # Brier + PnL + SHAP + plots
```

Each `build_S*` script writes to `features/<scenario>_<market_group>.parquet`.
`phase2_train.py` takes `--scenario S1|S2|S3|S4` flag.
