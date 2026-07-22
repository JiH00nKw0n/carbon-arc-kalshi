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
"""


def universe(cfg, manifest) -> str:
    series = csv("kalshi_company_series.csv")
    markets = csv("kalshi_company_markets.csv")
    features = csv("kalshi_company_event_features.csv")
    factset = csv("kalshi_factset_revenue_surprise_panel.csv")
    events = csv("kalshi_x_revsurprise_events.csv")
    ladders = csv("kalshi_prereport_ladder_panel.csv")
    metric_screen = csv("kalshi_kpi_revenue_screen.csv")
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
    valid_ladders = int((ladders["pre_total_priced_rungs"] >= 2).sum())
    audit = json.loads((AUTO / "kalshi_factset_query_audit.json").read_text())

    rows = manifest[manifest["y"].eq("surprise_early")].sort_values(["ticker", "FE_FP_END"])
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

| Stage | Rows / units | Distinct tickers | Rule |
|---|---:|---:|---|
| KPI series crawl | {len(series)} series ({mapped_series} mapped) | {series['matched_ticker'].nunique()} | Public current + historical API pages |
| Market inventory | {len(markets)} contracts | {markets['matched_ticker'].nunique()} | Preserve raw contract metadata |
| `kalshi_company_event_features.csv` | {len(features)} events / {int(features['n_ladder_markets'].sum())} numeric contracts | {features['matched_ticker'].nunique()} | One metadata row per event with at least two numeric YES-threshold rungs; this file is not model input |
| Direct FactSet panel | {len(factset)} company-quarters | {factset['ticker'].nunique()} | {audit['fsym_id_count']} FactSet IDs; actuals and point-in-time consensus from FE_V4 |
| Exact fiscal join | {len(events)} events / {events[['ticker', 'FE_FP_END']].drop_duplicates().shape[0]} quarters | {events['ticker'].nunique()} | Same ticker, fiscal year and fiscal quarter |
| Valid pre-publication ladder | {valid_ladders} quarters | {ladders.loc[ladders['pre_total_priced_rungs'] >= 2, 'ticker'].nunique()} | At least two priced rungs before publication |
| Metric screen | {(metric_screen['impact'] == 'O').sum()} O pairs | {metric_screen.loc[metric_screen['impact'] == 'O', 'ticker'].nunique()} | Remove non-revenue KPI types |
| Firm revenue-driver screen | {(firm_screen['impact'] == 'O').sum()} O pairs | {len(firm_o)} | Screener + high-effort auditor against total revenue |
| Firm-screened ladder panel | {len(firm_panel)} quarters | {firm_panel['ticker'].nunique()} | Keep O `(ticker, metric)` ladders |
| Strong-O benchmark candidates | - | {len(strong)} | Jihoon `main` primary tier |
| Final matched evaluation | {len(rows)} company-quarters | {len(final)} | Post-cutoff + ladder + >=3 financial rows + >=1 eligible transcript |

The metric screen is a deterministic wording rule that removes non-revenue KPI types. The 51
surviving `(ticker, metric)` pairs then pass through `{cfg.llm.model}` at medium effort and an adversarial
high-effort audit, in batches of eight with exact pair-key validation. `O` means the KPI is a
dominant, clean driver of total revenue; `strength` is confidence in that verdict, not estimated
revenue share. This follows the committed Carbon Arc screening CSV practice, which can retain a
dominant clean driver below 50% share; it does not impose a hard revenue-share threshold.

**84 numeric-ladder candidates:** {', '.join(candidate)}.

**42 exact-joined candidates:** {', '.join(joined)}.

**20 firm-screen O tickers:** {', '.join(firm_o)}.

**18 strong-O candidates:** {', '.join(strong)}.

**16 final benchmark tickers:** {', '.join(final)}.

### Attrition accounting

- **84 -> 42:** 42 numeric-ladder tickers had no exact `(ticker, fiscal year, fiscal quarter)`
  match to the direct FactSet panel.
- **42 -> 20:** the firm-level total-revenue screen rejected every surviving metric for 22 tickers.
- **20 -> 18:** `DPZ` and `MTN` are O-moderate and are excluded by `strong_only: true`.
- **18 -> 16:** `NFLX` and `SPOT` have valid ladders only for reports on or before the
  `2025-12-01` knowledge cutoff, so they have no evaluation target.

### Final ticker-quarters

All three Y definitions use the same {len(rows)} target rows.

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

N0 (company historical mean) and N2 (call sentiment) remain available. N1/N3/N4/N3b/N4b/N5 require
a dense, comparable scalar X and are reported N/A because Kalshi X is a sparse, firm-specific raw
ladder distribution. Fabricating a scalar zero would make those baselines misleading.
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
        "# Kalshi Raw-Ladder Benchmark\n\nThis is the authoritative design and result report for the "
        "Kalshi-only X substitution in the shared revenue-nowcasting paper framework.",
        protocol(cfg), universe(cfg, manifest), ladder_rules(), evaluation_rules(),
        "## Results\n\n" + "\n\n".join(result_section(record) for record in records),
        conclusion(records), artifacts(cfg),
    ]
    OUT.write_text("\n\n".join(section.rstrip() for section in sections) + "\n")
    print(f"[written] {OUT}")


if __name__ == "__main__":
    main()
