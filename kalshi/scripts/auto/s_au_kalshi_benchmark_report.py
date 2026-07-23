#!/usr/bin/env python3
"""Generate the single source-of-truth Kalshi benchmark report."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import prediction  # noqa: F401  # populate registries
from prediction.channels.specs import get_channel
from prediction.config.loader import load
from prediction.data.transcripts import TranscriptStore
from prediction.run.experiment import (
    PanelCache,
    _Transcripts,
    _evaluate_cell,
    _select_strong,
)
from prediction.run.grid import Cell
from prediction.targets.ytarget import get_y_target

CONFIG = ROOT / "prediction" / "configs" / "kalshi_full.yaml"
AUTO = ROOT / "kalshi" / "outputs" / "auto"
OUT = ROOT / "kalshi" / "BENCHMARK.md"
ARMS = ("fin", "fin+x", "fin+text", "fin+x+text")
TARGET_LABELS = {
    "surprise_early": "Early-consensus revenue surprise",
    "surprise_print": "Pre-report-consensus revenue surprise",
    "rev_yoy": "Revenue YoY",
}


def csv(name: str) -> pd.DataFrame:
    return pd.read_csv(AUTO / name)


def result_path(cfg, y: str, variant: str) -> Path:
    slug = f"kalshi.{y}.{variant}.{cfg.llm.model}.{cfg.llm.effort}.seed{cfg.seed}"
    return ROOT / cfg.output_dir / slug / "preds.csv"


def summarize(values) -> tuple[float, float, float, float]:
    sample = np.asarray(values, float)
    lo, hi = np.percentile(sample, [2.5, 97.5])
    return float(sample.mean()), float(lo), float(hi), float((sample <= 0).mean())


def metric_map(result) -> dict[str, dict]:
    calibration = {row["model"]: row["calib_r2"] for row in result.calib}
    rows = {}
    for row in result.metrics_table:
        item = dict(row)
        item["calib_r2"] = calibration.get(row["model"])
        rows[row["model"]] = item
    return rows


def tool_usage(preds: pd.DataFrame) -> tuple[int, Counter]:
    used = 0
    calls: Counter = Counter()
    for arm in ARMS:
        column = f"tool_calls__{arm}"
        if column not in preds:
            continue
        for raw in preds[column].fillna(""):
            names = [name for name in str(raw).split("|") if name]
            used += int(bool(names))
            calls.update(names)
    return used, calls


def evaluate_results(cfg, panel, transcripts, manifest) -> list[dict]:
    records = []
    expected = {
        y: set(zip(group["ticker"], group["FE_FP_END"].astype(str)))
        for y, group in manifest.groupby("y")
    }
    for y in cfg.grid.targets:
        for variant in cfg.grid.variants:
            path = result_path(cfg, y, variant)
            if not path.exists():
                raise RuntimeError(f"missing completed prediction cell: {path}")
            preds = pd.read_csv(path)
            actual = set(zip(preds["tkr"], preds["fp"].astype(str)))
            if actual != expected[y]:
                raise RuntimeError(
                    f"prediction/manifest mismatch for {y}/{variant}: "
                    f"missing={sorted(expected[y] - actual)}, extra={sorted(actual - expected[y])}"
                )
            cell = Cell(channel="kalshi", y=y, variant=variant)
            context = SimpleNamespace(
                transcripts=transcripts, y_target=get_y_target(y), channel=get_channel("kalshi")
            )
            result = _evaluate_cell(cfg, cell, panel, preds, context, cfg.seed)
            used, calls = tool_usage(preds)
            records.append({
                "y": y, "variant": variant, "preds": preds, "result": result,
                "metrics": metric_map(result), "tool_requests_used": used, "tool_calls": calls,
            })
    return records


def protocol(cfg) -> str:
    tool_context = json.loads(
        (ROOT / "kalshi" / "data" / "tool_context.json").read_text()
    )
    tool_source = tool_context["source"]
    return f"""## Benchmark contract

The benchmark contract is copied from Jihoon's latest `main` config. Only the X channel changes
from Carbon Arc data to Kalshi raw ladders.

| Component | Fixed rule |
|---|---|
| H (financial) | Up to {cfg.run.hist_rows} prior quarterly actuals, early consensus and realized surprise, plus target-quarter consensus |
| X (Kalshi) | Chronological raw pre-publication KPI ladders; all retained events, rungs and quote fields |
| Z (text) | Up to {cfg.run.n_calls} most recent corrected earnings calls dated at least 31 days before report; one call is allowed when only one exists |
| Y | `surprise_early`, `surprise_print`, and `rev_yoy`, evaluated separately |
| Model | `{cfg.llm.model}`, `{cfg.llm.effort}` reasoning |
| Variants | `BASE` and byte-identical `TOOL` prompt with optional lookups |
| Arms | `fin`, `fin+x`, `fin+text`, `fin+x+text` |
| Repeats | {cfg.run.reps} independent call per arm and target |
| Knowledge guard | `REPORT_DATE > {cfg.run.cutoff}` |
| Pairing | Every arm within a cell uses the exact same `ticker + FE_FP_END` rows |
| Seed | {cfg.seed} |

### Input, output and labels

The model outputs predicted total quarterly revenue in USD millions. The evaluator then derives:

- `surprise_early = (predicted revenue - early consensus) / early consensus`
- `surprise_print = (predicted revenue - last pre-report consensus) / last pre-report consensus`
- `rev_yoy = (predicted revenue - same-quarter prior-year actual) / prior-year actual`

The true labels apply the same formulas to FactSet actual revenue. Predictions and labels are scored
in percentage points. Structured output also contains confidence and rationale, but neither enters
the metrics.

### TOOL variant interface

`BASE` and `TOOL` render the same system and user prompt. `BASE` exposes no functions. `TOOL`
exposes the following two strict, no-argument functions to every arm:

| Tool | Explicit model input | Context bound by the runner | Plain-text output |
|---|---|---|---|
| `get_company_profile` | `{{}}` | Current target ticker | Frozen FMP company description: business model, sector and revenue drivers |
| `get_alt_data_description` | `{{}}` | Active `kalshi` channel | Frozen description of the Kalshi universe, pre-publication snapshot and ladder construction |

The model does not choose or pass the ticker. The runner binds `target.ticker` and the active channel
before dispatch. A tool round therefore has this shape:

```text
same BASE prompt + two function schemas
    -> model emits get_company_profile({{}}) or get_alt_data_description({{}})
    -> runner reads the target-bound string from kalshi/data/tool_context.json
    -> model receives the string and returns the structured revenue prediction
```

The tools do not return a Kalshi ladder, financial history, target-quarter actual, label, or live
search result. Raw ladder values are supplied directly in the prompt only for arms containing X.
The local context contains {len(tool_context['company_profiles'])} company profiles fetched once
from {tool_source['company_profiles']} at `{tool_source['retrieved_at_utc']}` plus one repository
methodology description. "Frozen" means reproducible after retrieval; the FMP profile is not a
historical point-in-time profile as of each target report.

The model and prompt text remain fixed across variants, but the transport path is not identical:
`BASE` uses Chat Completions structured parse, while `TOOL` uses the Responses API because the
configured model does not accept reasoning plus function tools on the Chat Completions path.
"""


def universe(cfg, manifest) -> str:
    series = csv("kalshi_company_series.csv")
    markets = csv("kalshi_company_markets.csv")
    features = csv("kalshi_company_event_features.csv")
    factset = csv("kalshi_factset_revenue_surprise_panel.csv")
    events = csv("kalshi_x_revsurprise_events.csv")
    ladders = csv("kalshi_prereport_ladder_panel.csv")
    metric_screen = csv("kalshi_kpi_revenue_screen.csv")
    metric_panel = csv("kalshi_prereport_ladder_panel_screened.csv")
    firm_screen = csv("kalshi_kpi_firm_screen.csv")
    firm_panel = csv("kalshi_prereport_ladder_panel_firmscreened.csv")
    ticker_screen = pd.read_csv(ROOT / cfg.data.screen_csv)
    kalshi_screen = ticker_screen[ticker_screen["data_type"].eq("kalshi_kpi")]
    strong = sorted(kalshi_screen[
        kalshi_screen["impact"].eq("O") & kalshi_screen["strength"].eq("strong")
    ]["ticker"].unique())
    final = sorted(manifest[manifest["y"].eq("surprise_early")]["ticker"].unique())
    candidate = sorted(features["matched_ticker"].dropna().unique())
    joined = sorted(events["ticker"].dropna().unique())
    firm_o = sorted(firm_screen[firm_screen["impact"].eq("O")]["ticker"].unique())
    mapped_series = int(series["matched_ticker"].notna().sum())
    mapped_markets = markets[
        markets["matched_ticker"].fillna("").str.strip().ne("")
        & markets["event_ticker"].fillna("").str.strip().ne("")
    ]
    mapped_market_events = mapped_markets["event_ticker"].nunique()
    mapped_series_tickers = set(series["matched_ticker"].dropna().unique())
    mapped_market_tickers = set(mapped_markets["matched_ticker"].unique())
    no_market_tickers = sorted(mapped_series_tickers - mapped_market_tickers)

    period = features["period_label"].fillna("").str.extract(
        r"^Q([1-4])\s+(20\d{2})$", expand=True
    )
    valid_period = period.notna().all(axis=1)
    valid_feature_date = pd.to_datetime(
        features["feature_date"], errors="coerce", utc=True, format="mixed"
    ).notna()
    quarter_features = features[valid_period & valid_feature_date].copy()
    blank_periods = features["period_label"].fillna("").str.strip().eq("")
    blank_period_count = int((~valid_period & blank_periods).sum())
    nonquarter_period_count = int((~valid_period & ~blank_periods).sum())
    invalid_feature_date_count = int((valid_period & ~valid_feature_date).sum())
    quarter_features["FISCAL_QUARTER"] = period.loc[
        quarter_features.index, 0
    ].astype(int)
    quarter_features["FISCAL_YEAR"] = period.loc[
        quarter_features.index, 1
    ].astype(int)
    raw_factset_keys = factset[
        ["ticker", "FISCAL_YEAR", "FISCAL_QUARTER"]
    ].dropna()
    factset_keys = pd.DataFrame(
        {
            "ticker": raw_factset_keys["ticker"].str.upper(),
            "FISCAL_YEAR": raw_factset_keys["FISCAL_YEAR"].astype(int),
            "FISCAL_QUARTER": raw_factset_keys["FISCAL_QUARTER"].astype(int),
        },
        index=raw_factset_keys.index,
    ).drop_duplicates()
    exact_features = quarter_features.merge(
        factset_keys,
        left_on=["matched_ticker", "FISCAL_YEAR", "FISCAL_QUARTER"],
        right_on=["ticker", "FISCAL_YEAR", "FISCAL_QUARTER"],
        how="inner",
    ).drop_duplicates("event_ticker")

    joined_quarters = events[["ticker", "FE_FP_END"]].drop_duplicates()
    valid_ladders = ladders[ladders["pre_event_count"].gt(0)].copy()
    uncovered_ladders = ladders[ladders["pre_event_count"].eq(0)]
    uncovered_labels = ", ".join(
        f"`{row.ticker} {row.FE_FP_END}`" for row in uncovered_ladders.itertuples()
    )
    metric_o = metric_screen[metric_screen["impact"].eq("O")]
    metric_x = metric_screen[metric_screen["impact"].eq("X")]
    metric_x_labels = ", ".join(
        f"`{row.ticker} / {row.metric_label}`" for row in metric_x.itertuples()
    )
    firm_o_pairs = firm_screen[firm_screen["impact"].eq("O")]
    strong_base = firm_panel[firm_panel["ticker"].isin(strong)]
    strong_columns = {column: strong_base[column] for column in strong_base.columns}
    strong_columns["REPORT_DATE"] = pd.to_datetime(strong_base["REPORT_DATE"])
    strong_rows = pd.DataFrame(
        strong_columns,
        index=strong_base.index,
    )
    postcutoff_rows = strong_rows[
        strong_rows["REPORT_DATE"] > pd.Timestamp(cfg.run.cutoff)
    ]
    audit = json.loads((AUTO / "kalshi_factset_query_audit.json").read_text())

    rows = manifest[manifest["y"].eq("surprise_early")].sort_values(["ticker", "FE_FP_END"])
    later_eligibility_drops = len(postcutoff_rows) - len(rows)
    ticker_lines = [
        "| Ticker | Target fiscal quarters | Targets | H quarters shown | Prior X ladder quarters shown | Prior calls |",
        "|---|---|---:|---|---|---|",
    ]
    for ticker, group in rows.groupby("ticker"):
        ticker_lines.append(
            f"| {ticker} | {', '.join(group['FE_FP_END'].astype(str))} | {len(group)} | "
            f"{', '.join(map(str, group['financial_history_shown']))} | "
            f"{', '.join(map(str, group['ladder_history_shown']))} | "
            f"{', '.join(map(str, group['earnings_call_count']))} |"
        )

    return f"""## Data universe

The crawl uses Kalshi's public Trade API v2 `/series?tags=KPIs` cursor pagination, then fetches both
current and historical markets for every returned series. The inventory is complete for the API
response captured by this run; explicit issuer aliases map public companies. The seven deliberately
unmapped series are non-public or non-company questions (Waymo, OpenAI/LLM rankings, subway
ridership and aggregate EV share).

### Counting units

- **Series:** a recurring Kalshi market template, such as quarterly Tesla deliveries.
- **Contract / rung:** one binary threshold market inside an event, such as
  `P(deliveries > 400,000)`.
- **Event / ladder:** one KPI for one stated period, containing at least two threshold rungs.
- **Pair:** one distinct `(ticker, metric_label)` eligibility rule with no time dimension.
- **Company-quarter:** one `(ticker, FE_FP_END)` observation. It can contain more than one event.
- **Target:** a company-quarter that also passes the final model-evaluation rules.

Counts only form a conventional funnel while the unit is unchanged. In particular, pair counts
cannot be compared directly with quarter counts: one retained pair can recur across many quarters.

### Ticker funnel

```mermaid
flowchart TB
    A["{series['matched_ticker'].nunique()} mapped public-company tickers<br/>{mapped_series} of {len(series)} KPI series"]
    B["{features['matched_ticker'].nunique()} tickers with valid numeric ladders"]
    C["{quarter_features['matched_ticker'].nunique()} tickers with quarter-labelled events"]
    D["{events['ticker'].nunique()} tickers matched to FactSet quarters"]
    E["{len(firm_o)} tickers with at least one firm-screen O metric"]
    F["{len(strong)} strong-O benchmark tickers"]
    G["{len(final)} final evaluation tickers"]

    A -->|"{len(no_market_tickers)} mapped tickers returned no contracts"| B
    B -->|"period must be Q1-Q4 plus year"| C
    C -->|"exact fiscal key and date distance at most 60 days"| D
    D -->|"firm total-revenue screen"| E
    E -->|"ticker-level strength must be strong"| F
    F -->|"post-cutoff target and coverage rules"| G
```

### Observation and pair flow

```mermaid
flowchart TB
    A["{len(features)} numeric ladder events<br/>{int(features['n_ladder_markets'].sum()):,} threshold rungs"]
    B["{len(quarter_features)} quarter-labelled events"]
    C["{len(exact_features)} exact fiscal-key event matches"]
    D["{len(events)} date-valid events<br/>{len(joined_quarters)} company-quarters"]
    FS["FactSet side input<br/>{len(factset):,} company-quarters / {factset['ticker'].nunique()} tickers"]
    E["{int(valid_ladders['pre_event_count'].sum())} price-covered event ladders<br/>{len(valid_ladders)} company-quarters"]
    P["{len(metric_screen)} distinct ticker-metric pairs"]
    Q["{len(metric_o)} metric-screen O pairs"]
    R["{int(metric_panel['pre_event_count'].sum())} retained event ladders<br/>{len(metric_panel)} company-quarters"]
    S["{len(firm_o_pairs)} firm-screen O pairs<br/>{len(firm_o)} tickers"]
    T["{int(firm_panel['pre_event_count'].sum())} event ladders<br/>{len(firm_panel)} company-quarters"]
    U["{len(strong_rows)} strong-tier ladder quarters<br/>{len(strong)} tickers"]
    V["{len(rows)} final targets<br/>{len(final)} tickers"]

    A -->|"valid feature date and Q1-Q4 year label"| B
    B -->|"same ticker, fiscal year, fiscal quarter"| C
    FS --> C
    C -->|"nearest report must be within 60 days"| D
    D -->|"publication cutoff and at least 2 priced rungs per event"| E
    D -->|"deduplicate by ticker and metric label"| P
    P -->|"deterministic wording screen"| Q
    E -->|"time observations"| R
    Q -->|"allowed pair keys"| R
    Q -->|"medium screener plus high-effort audit"| S
    R -->|"time observations"| T
    S -->|"allowed pair keys"| T
    T -->|"strong_only: true"| U
    U -->|"report date after {cfg.run.cutoff}; label, history, transcript checks"| V
```

The FactSet panel is a side input to the fiscal join, not another Kalshi attrition stage. It contains
{len(factset):,} revenue company-quarters for {audit['fsym_id_count']} FactSet IDs, with actuals and
point-in-time consensus from FE_V4.

### Exact filter rules

1. **Issuer and market availability.** Of {len(series)} KPI-tagged series, {mapped_series} map to
   {series['matched_ticker'].nunique()} public-company tickers. Current and historical market pages
   return {len(markets):,} contracts across {markets['event_ticker'].nunique()} events; restricting to
   mapped issuers leaves {len(mapped_markets):,} contracts across {mapped_market_events} events and
   {mapped_markets['matched_ticker'].nunique()} tickers. The mapped tickers with no returned
   contracts are `{', '.join(no_market_tickers)}`.
2. **Numeric ladder validity.** A contract survives only when its YES side means `above` or
   `at least`, its numeric strike parses, and its `market_ticker` is unique. An event survives only
   with at least two such rungs. This removes {mapped_market_events - len(features)} mapped events
   and leaves {len(features)} events / {int(features['n_ladder_markets'].sum()):,} rungs.
3. **Quarter identity.** `period_label` must fully match `Q[1-4] YYYY`, and `feature_date` must parse.
   `feature_date` is the earliest available occurrence, close, or expiration timestamp. Of the
   {len(features) - len(quarter_features)} events removed here, {blank_period_count} have no period,
   {nonquarter_period_count} are annual-only or otherwise non-quarter labels, and
   {invalid_feature_date_count} have a quarter label but no parseable date. This leaves
   {len(quarter_features)} events. The event then needs the same ticker, fiscal year, and fiscal
   quarter in FactSet: {len(exact_features)} events pass and
   {len(quarter_features) - len(exact_features)} do not. If more than one FactSet row is possible,
   the nearest report is selected, and absolute `feature_date - REPORT_DATE` must be <=60 days;
   {len(exact_features) - len(events)} more events fail that tolerance, leaving {len(events)} events
   / {len(joined_quarters)} company-quarters.
4. **Leakage-safe price coverage.** The quote cutoff is `published_at - 1 minute`. A rung's market
   must already be open, and the latest daily candle between market open and cutoff must have a
   usable probability. A valid YES book with spread <=0.20 uses its midpoint; otherwise the code
   falls back to last trade, then previous trade. Each event still needs at least two priced rungs,
   and each quarter needs at least one surviving event. This leaves
   {int(valid_ladders['pre_event_count'].sum())} events / {len(valid_ladders)} quarters /
   {int(valid_ladders['pre_total_priced_rungs'].sum()):,} rungs. The uncovered quarters are
   {uncovered_labels}.
5. **Metric wording screen.** The key is `(ticker, metric_label)`, so repeated quarters collapse to
   one pair. Employee/headcount metrics are X. Sold units, deliveries, volume, orders, trips,
   subscribers, bookings, passengers and similar revenue bases are O-strong. Accounts and
   engagement are O-moderate; an unmatched KPI defaults to O-moderate. The result is
   {len(metric_o)} O and {len(metric_screen) - len(metric_o)} X pair out of {len(metric_screen)}.
   The only X pair in this run is {metric_x_labels}, covering {int(metric_x['events'].sum())}
   matched events.
   Applying those keys changes the time panel from {len(valid_ladders)} to {len(metric_panel)}
   quarters and from {int(valid_ladders['pre_event_count'].sum())} to
   {int(metric_panel['pre_event_count'].sum())} event ladders.
6. **Firm total-revenue screen.** The {len(metric_o)} O pairs enter `{cfg.llm.model}` at medium
   effort in validated batches of eight, followed by an adversarial high-effort audit. O requires
   a dominant, clean driver of the firm's total revenue. X covers a minority segment, an indirect
   or wrong measure, or a metric redundant with a cleaner one. This retains {len(firm_o_pairs)}
   pairs and rejects {len(firm_screen) - len(firm_o_pairs)}; applying them leaves {len(firm_panel)}
   company-quarters across {len(firm_o)} tickers. As in the committed Carbon Arc screen, the
   largest clean driver can remain O around 20-45% of revenue; there is no hard 50% threshold.
7. **Primary strong tier.** `strength` is confidence in the O/X verdict, not estimated revenue
   share. The ticker-level screen takes the highest-confidence O verdict per ticker, and
   `strong_only: true` keeps {len(strong)} strong tickers / {len(strong_rows)} ladder quarters.
   `DPZ` and `MTN` are O-moderate and are excluded.
8. **Evaluation target.** A target must have `REPORT_DATE > {cfg.run.cutoff}`, a target-quarter
   ladder payload, a non-missing active Y, at least three strictly prior financial quarters, and at
   least one readable corrected earnings call dated no later than report minus 31 days. Up to six
   financial quarters and two calls are shown; the second call is optional. The date guard reduces
   {len(strong_rows)} strong-tier ladder quarters to {len(postcutoff_rows)}. The later label,
   history, and transcript checks remove {later_eligibility_drops} additional rows, leaving
   {len(rows)} matched targets across {len(final)} tickers.

The deterministic metric screen uses the following ordered map; first match wins. The exact source
of truth is `kalshi/scripts/auto/s_ap_kalshi_revenue_screen.py`.

| Result | Matching metric wording |
|---|---|
| X | `headcount`, `employees`, `staff`, `workforce` |
| O-strong | deliveries/production/unit sales/shipments/vehicles; volume; orders/trips/rides; subscribers/payers/memberships; bookings/nights/passengers/seats/fares/rooms/homes/skier visits/restaurants/stores |
| O-moderate | gold subscribers, funded accounts/accounts; users, MAU/DAU, unique users, hours, streaming, engagement |
| O-moderate | no listed wording matches (default) |

The cutoff does not delete older Kalshi or financial observations. It only prevents them from
becoming evaluation Y rows; eligible earlier observations can still appear as H or prior-X context.

### Final evaluation contraction

| Step | Company-quarters | Tickers | Removed at this step |
|---|---:|---:|---|
| Firm-screen O panel | {len(firm_panel)} | {len(firm_o)} | Starting time panel after pair filters |
| `strong_only: true` | {len(strong_rows)} | {len(strong)} | {len(firm_panel) - len(strong_rows)} quarters: `DPZ`, `MTN` |
| `REPORT_DATE > {cfg.run.cutoff}` | {len(postcutoff_rows)} | {postcutoff_rows['ticker'].nunique()} | {len(strong_rows) - len(postcutoff_rows)} pre-cutoff quarters; `NFLX`, `SPOT` lose all target rows |
| Label, history and transcript coverage | {len(rows)} | {len(final)} | {later_eligibility_drops} additional quarters |

### Why pairs and quarters differ

The firm screen makes one keep/drop decision per `(ticker, metric_label)` and reuses that decision
at every date. For example, the TSLA deliveries metric is one pair-level decision but occurs in nine
matched quarterly events. There are {len(firm_o_pairs)} pairs but {len(firm_o)} tickers because BA
has `deliveries` and `commercial deliveries`, while COIN has `coinbase volume` and
`total trading volume`. Consequently, those {len(firm_o_pairs)} pair definitions expand to
{len(firm_panel)} retained company-quarter observations. After firm screening, this run has one
retained event ladder per retained company-quarter.

**84 numeric-ladder candidates:** {', '.join(candidate)}.

**42 exact-joined candidates:** {', '.join(joined)}.

**20 firm-screen O tickers:** {', '.join(firm_o)}.

**18 strong-O candidates:** {', '.join(strong)}.

**16 final benchmark tickers:** {', '.join(final)}.

At the ticker level, the largest reductions are {features['matched_ticker'].nunique()} ->
{events['ticker'].nunique()} at the quarter/FactSet match and {events['ticker'].nunique()} ->
{len(firm_o)} at the firm revenue-driver screen. `NFLX` and `SPOT` survive the strong screen but have
no ladder report after the knowledge cutoff, producing the final {len(strong)} -> {len(final)}
ticker change.

### Final ticker-quarters

All three Y definitions use the same {len(rows)} target rows.

- **H quarters shown:** number of prior financial quarters included in the prompt, capped at six;
  the target quarter is not counted.
- **Prior X ladder quarters shown:** number of those prior quarters that also include an eligible
  Kalshi ladder; the target-quarter ladder is not counted.
- **Prior calls:** number of corrected earnings-call transcripts supplied to text arms, capped at
  two and restricted to calls dated at least 31 days before the target report.

{chr(10).join(ticker_lines)}
"""


def ladder_rules() -> str:
    return """## Kalshi X construction

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
"""


def evaluation_rules() -> str:
    return """## Evaluation

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

### Why classical baselines are N/A

The Carbon Arc baseline family assumes one comparable scalar `x_yoy` for every company-quarter.
Kalshi X is instead preserved as a variable-length `x_payload` containing raw
`(threshold, probability)` rungs. KPI units, thresholds and rung counts differ across companies and
quarters, so this benchmark does not define `x_abs`, `x_yoy`, or `x_yoy_3m`; those scalar fields are
set to missing by construction.

Baseline feature definitions:

- `x_yoy`: scalar alternative-data year-over-year growth.
- `sent`: Loughran-McDonald sentiment from the most recent eligible prior call.
- `lag_y`: one-quarter lag of the active Y.
- `x_sent`: `x_yoy * sent`.

| Baseline | Estimator and features | Status | Exact reason |
|---|---|---|---|
| N0 | Company historical mean | Available | Does not use X |
| N1 | OLS: `x_yoy` | N/A | `x_yoy` is undefined for a raw ladder |
| N2 | OLS: `sent` | Available | Does not use X |
| N3 | OLS: `x_yoy`, `sent` | N/A | Requires undefined `x_yoy` |
| N4 | OLS: `x_yoy`, `sent`, `x_sent` | N/A | Requires undefined `x_yoy` and its interaction |
| N3b | OLS: `x_yoy`, `sent`, `lag_y` | N/A | `sent` and `lag_y` exist, but `x_yoy` does not |
| N4b | OLS: `x_yoy`, `sent`, `lag_y`, `x_sent` | N/A | Requires undefined `x_yoy` and its interaction |
| N5 | Gradient-boosted trees: `x_yoy`, `sent`, `lag_y` | N/A | Its feature matrix requires undefined `x_yoy` |

For a ladder channel, the evaluator skips any baseline whose feature list contains `x_yoy` and
marks it unavailable before fitting. N/A therefore means **not applicable under the raw-ladder
representation**. It does not mean API failure, insufficient sample size, failed convergence, or
missing target rows. Replacing missing `x_yoy` with zero would falsely encode zero KPI growth and
collapse economically different ladders to the same value.

Producing numeric N1/N3/N4/N3b/N4b/N5 results would require a pre-specified ladder-to-scalar
transformation, followed by a comparable within-company or within-metric YoY calculation. That
would be a separate scalarized-Kalshi experiment, not this raw-ladder benchmark.
"""


def result_section(record) -> str:
    result = record["result"]
    metrics = record["metrics"]
    lines = [
        f"### {TARGET_LABELS[record['y']]} / {record['variant']}", "",
        f"Matched sample: {result.rows} company-quarters / {record['preds']['tkr'].nunique()} firms.", "",
        "| Model | RMSE | OOS R2 | Calib. R2 (OOF) | Corr | MAE | Sign |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name in (*ARMS, "N0", "N1", "N2", "N3", "N4", "N3b", "N4b", "N5"):
        row = metrics[name]
        if row.get("available") is False:
            lines.append(f"| {name} | N/A | N/A | N/A | N/A | N/A | N/A |")
            continue
        calib = row.get("calib_r2")
        lines.append(
            f"| {name} | {row['rmse']:.3f} | {row['r2']:+.3f} | "
            f"{calib:+.3f}" if calib is not None else
            f"| {name} | {row['rmse']:.3f} | {row['r2']:+.3f} | -"
        )
        lines[-1] += f" | {row['corr']:+.3f} | {row['mae']:.3f} | {row['sign']:.3f} |"

    delta_x = metrics["fin+x"]["rmse"] - metrics["fin"]["rmse"]
    delta_xz = metrics["fin+x+text"]["rmse"] - metrics["fin+text"]["rmse"]
    sc = summarize(result.synergy["syn_corr"])
    ss = summarize(result.synergy["syn_skill"])
    lines += [
        "",
        f"Descriptive RMSE delta X over H: {delta_x:+.3f} pp; X over H+Z: {delta_xz:+.3f} pp "
        "(negative favors Kalshi).",
        "",
        "| Bootstrap quantity | Mean | 95% CI | p(value <= 0) |",
        "|---|---:|---:|---:|",
        f"| Corr synergy | {sc[0]:+.3f} | [{sc[1]:+.3f}, {sc[2]:+.3f}] | {sc[3]:.3f} |",
        f"| MSE-skill synergy | {ss[0]:+.3f} | [{ss[1]:+.3f}, {ss[2]:+.3f}] | {ss[3]:.3f} |",
        "",
        f"Shuffle-company surrogate p-value: {result.surrogate:.4f}.",
    ]
    if record["variant"] == "TOOL":
        offered = len(record["preds"]) * len(ARMS)
        counts = ", ".join(f"{key}={value}" for key, value in sorted(record["tool_calls"].items())) or "none"
        lines += ["", f"TOOL telemetry: {record['tool_requests_used']}/{offered} arm requests used at "
                           f"least one lookup; calls: {counts}."]
    return "\n".join(lines)


def conclusion(records) -> str:
    h_improvements = 0
    hz_improvements = 0
    intervals = []
    for record in records:
        metrics = record["metrics"]
        h_improvements += metrics["fin+x"]["rmse"] < metrics["fin"]["rmse"]
        hz_improvements += metrics["fin+x+text"]["rmse"] < metrics["fin+text"]["rmse"]
        intervals.extend((
            summarize(record["result"].synergy["syn_corr"]),
            summarize(record["result"].synergy["syn_skill"]),
        ))
    includes_zero = sum(lo <= 0 <= hi for _, lo, hi, _ in intervals)
    lines = [
        "## Result summary", "",
        f"Across the six cells, adding raw Kalshi X lowers descriptive RMSE in {h_improvements}/6 "
        f"H comparisons and {hz_improvements}/6 H+Z comparisons. However, {includes_zero}/"
        f"{len(intervals)} predefined company-clustered 95% synergy intervals include zero. On this "
        "22-quarter sample, the run therefore shows suggestive point-estimate improvements but no "
        "statistically robust super-additive Kalshi effect.", "",
    ]
    for record in records:
        llm = {name: record["metrics"][name] for name in ARMS}
        best = min(llm, key=lambda name: llm[name]["rmse"])
        sc = summarize(record["result"].synergy["syn_corr"])
        ss = summarize(record["result"].synergy["syn_skill"])
        robust = sc[1] > 0 and ss[1] > 0
        lines.append(
            f"- `{record['y']} / {record['variant']}`: lowest arm RMSE is `{best}` "
            f"({llm[best]['rmse']:.3f}); both synergy intervals are "
            f"{'strictly positive' if robust else 'not strictly positive'}."
        )
    lines += ["", "Direct arm RMSE differences are descriptive because Jihoon's benchmark does not "
              "attach a separate confidence interval to each direct delta. Statistical claims should "
              "therefore rely on the predefined company-clustered synergy intervals and be phrased "
              "without attributing the shuffle-Y surrogate specifically to Kalshi X."]
    return "\n".join(lines)


def artifacts(cfg) -> str:
    return f"""## Reproduction

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

Generated run artifacts are under `{cfg.output_dir}`. The exact rows are in
`{cfg.output_dir}/evaluation_manifest.csv`; each cell contains `preds.csv`, `resume.jsonl`, and
`report.md`. Licensed FactSet and transcript data remain git-ignored.
"""


def main() -> None:
    cfg = load(str(CONFIG))
    manifest_path = ROOT / cfg.output_dir / "evaluation_manifest.csv"
    manifest = pd.read_csv(manifest_path)
    key_sets = [set(zip(group["ticker"], group["FE_FP_END"].astype(str)))
                for _, group in manifest.groupby("y")]
    if len(key_sets) != len(cfg.grid.targets) or any(keys != key_sets[0] for keys in key_sets[1:]):
        raise RuntimeError("Y targets do not share one matched evaluation row set")

    channel = get_channel("kalshi")
    panel = PanelCache(cfg.data.panel_out, cfg.data.screen_csv).get_or_build(channel)
    panel = _select_strong(panel, cfg.run)
    transcripts = _Transcripts(TranscriptStore(channel, cfg.run.max_transcript_chars),
                               cfg.run.max_transcript_chars)
    records = evaluate_results(cfg, panel, transcripts, manifest)

    sections = [
        "# Legacy Kalshi Raw-Ladder Benchmark\n\n"
        "> Archived one-run Jihoon-main reproduction. The authoritative manuscript run is "
        "`kalshi/PAPER_RESULTS.md`; counts and results below belong to the earlier frozen screen.\n\n"
        "This report records the Kalshi-only X substitution in the shared revenue-nowcasting "
        "benchmark framework.",
        protocol(cfg), universe(cfg, manifest), ladder_rules(), evaluation_rules(),
        "## Results\n\n" + "\n\n".join(result_section(record) for record in records),
        conclusion(records), artifacts(cfg),
    ]
    OUT.write_text("\n\n".join(section.rstrip() for section in sections) + "\n")
    print(f"[written] {OUT}")


if __name__ == "__main__":
    main()
