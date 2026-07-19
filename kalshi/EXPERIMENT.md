# Kalshi Raw-Ladder Revenue-Surprise Experiment Design

## Research question

Does a raw, pre-publication Kalshi KPI probability ladder improve an LLM's
prediction of quarterly revenue surprise?

This is a paired input ablation. It does not test trading returns, Kalshi market
calibration, or a scalar derived from prediction-market prices.

## Carbon Arc benchmark parity

The implementation follows the Carbon Arc Factor 1 four-arm LLM experiment.
The following components are fixed:

| component | fixed rule |
|---|---|
| Y | `(actual revenue - early consensus) / early consensus` |
| financial input | up to six prior quarterly actuals, early consensus values, and surprises, plus target-quarter early consensus |
| Z | most recent corrected earnings call at least 31 days before the target report |
| model | `gpt-5.5-2026-04-23`, medium reasoning effort |
| prompt | same revenue-surprise nowcasting system prompt and arm ordering as Factor 1 |
| evaluation guard | `REPORT_DATE > 2025-12-01` |
| row matching | every arm is evaluated on the same target rows |
| LLM repeats | one independent call per arm and target |
| primary metric | RMSE in revenue-surprise percentage points |

The sole experimental substitution is:

```text
Carbon Arc X history -> raw Kalshi KPI ladder history
```

## Definitions

### Company-quarter

One prediction target identified by `ticker + FE_FP_END`. A company-quarter can
contain multiple Kalshi KPI events.

### Event

A Kalshi question about one KPI and period, such as Tesla Q1 deliveries. One
event can contain many threshold contracts.

### Rung

One threshold contract inside an event. For example, the contracts for
deliveries above 290,000, above 310,000, and above 330,000 are three separate
rungs. Each rung contributes its threshold, YES probability, quote source,
candle timestamp, volume, and open interest.

### Ladder

The ordered collection of at least two numeric YES-threshold rungs for one
event. The ladder is a discrete view of the market's probability distribution.
The experiment preserves every retained rung rather than choosing a single
contract or integrating the ladder into an implied KPI value.

## Outcome and consensus timing

The prediction target is:

```text
surprise_early = (ACTUAL - CONS_EARLY) / CONS_EARLY
```

`CONS_EARLY` is the latest quarterly SALES consensus whose effective date is no
later than fiscal quarter end plus seven days. This is the fixed Factor 1 target
definition. `CONS_PRINT`, the latest snapshot before the report date, remains a
diagnostic column and is not supplied to the model.

## Universe construction

1. Fetch every series returned by the official Kalshi `tags=KPIs` filter.
2. Fetch current and historical markets for each series.
3. Map explicit company names to approved stock tickers.
4. Keep events with at least two numeric YES-above or YES-at-least contracts.
5. Parse quarter labels as `Q1` through `Q4` plus fiscal year.
6. Join to Stock DB by exact ticker, fiscal year, and fiscal quarter. Date
   distance only resolves duplicate candidates; it never substitutes for the
   fiscal-period match.
7. Require a leakage-safe pre-publication ladder, at least three prior financial
   rows, and a readable eligible prior earnings call.
8. Apply the model-knowledge guard and evaluate all four arms on one paired row
   set.

The exact counts produced by the current artifacts are recorded in
[`RESULTS.md`](RESULTS.md).

## Pre-publication candle rule

For every threshold contract:

1. Set the information cutoff to the Stock DB earnings `published_at` timestamp
   minus one minute.
2. Search daily candles from that contract's actual Kalshi `open_time` through
   the cutoff. There is no maximum candle-age exclusion.
3. Select the latest candle whose end timestamp is no later than the cutoff.
4. Reject a target if no event retains at least two priced rungs.
5. Store and validate `market_open_at <= candle_at <= cutoff < published_at` for
   every rung.

The pipeline originally imposed a 45-day maximum candle age. That number came
from the Carbon Arc panel builder's `merge_asof(..., tolerance=45d)` rule, which
matches a monthly alternative-data observation to a fiscal quarter end. It is
not a Kalshi quote-freshness rule and is not part of the Carbon Arc LLM ablation.
The cap was therefore removed. The correction restored Disney Q1 FY2026, whose
last market candle was 46.3 days before the earnings publication.

FedEx Q4 FY2026 remains excluded because its Stock DB target has no precise
`published_at`. A date-only fallback could include post-result prices, so the
pipeline does not manufacture an intraday cutoff.

## Rung price selection

The selected probability uses the following deterministic order:

1. YES bid/ask midpoint when `0 <= bid <= ask <= 1`, ask is positive, and the
   spread is at most 0.20.
2. Candle last-trade close when the quote is invalid or wider than 0.20.
3. Candle previous trade when no usable last trade exists.

A `bid=0, ask=1` book is not interpreted as a 0.50 probability. Its spread is
1.00, so the code falls back to the last or previous trade. Raw monotonicity
violations are retained. No smoothing, interpolation, settled outcome, current
market status, or scalar ladder summary is supplied to the model.

## Model inputs

### Financial table

Up to six prior quarters of actual revenue, early consensus, and realized
surprise, followed by the target quarter's early consensus.

### Kalshi X table

Up to six prior ladder-bearing quarters plus the target quarter. Each quarter
contains all eligible events and all retained rungs. A row includes:

```text
market | YES condition | probability | source |
bid / ask / last / previous | spread | candle_utc |
daily_volume | open_interest
```

The prompt also includes each quarter's publication cutoff, so the age of every
candle is observable.

### Earnings-call Z text

The most recent corrected earnings-call document dated at least 31 days before
the target report, truncated to 48,000 characters. The same document is used in
both Z arms.

## Four paired arms

| arm | inputs |
|---|---|
| `fin` | financial table |
| `fin+kalshi_ladder` | financial table and raw Kalshi X |
| `fin+earnings_call` | financial table and prior-call Z |
| `fin+kalshi_ladder+earnings_call` | financial table, raw Kalshi X, and prior-call Z |

Each arm is called independently once. No prediction from one arm is supplied
to another arm.

## Evaluation

The primary paired comparisons are:

1. `fin+kalshi_ladder` versus `fin`
2. `fin+kalshi_ladder+earnings_call` versus `fin+earnings_call`

For each comparison:

```text
delta = RMSE(+ ladder) - RMSE(base)
```

A negative delta favors Kalshi. The report also includes MAE, Pearson
correlation, correlation squared, paired-sample R2, and sign accuracy.

The Carbon Arc benchmark robustness outputs are retained: company-clustered
synergy bootstrap, company-shuffle surrogate, and leak-free company-fold linear
calibration. The Kalshi report additionally presents a company-clustered 95%
confidence interval for each direct RMSE delta, company sign permutation, and
leave-one-company-out sensitivity.

A direct incremental result is called statistically robust only when all three
predefined gates pass:

1. RMSE delta is negative.
2. The company-clustered 95% confidence interval is fully below zero.
3. The company-level sign-permutation p-value is below 0.05.

## Reproducibility

The complete command sequence is in [`README.md`](README.md). The final analyzer
recomputes universe counts, ladder diagnostics, LLM metrics, paired inference,
synergy, calibration, and ticker attrition from the generated CSV and JSONL
artifacts. It writes the sole generated narrative report, [`RESULTS.md`](RESULTS.md).
