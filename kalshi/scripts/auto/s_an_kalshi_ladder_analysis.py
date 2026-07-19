#!/usr/bin/env python3
"""Generate the canonical Kalshi experiment results report."""
import argparse
import json
import os
import re
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
KALSHI_ROOT = ROOT / "kalshi"
OUTPUTS = KALSHI_ROOT / "outputs" / "auto"
SEED = 2026
KNOWLEDGE_CUTOFF = pd.Timestamp("2025-12-01")
ARMS = [
    "fin",
    "fin+kalshi_ladder",
    "fin+earnings_call",
    "fin+kalshi_ladder+earnings_call",
]
PAIRS = [
    ("fin", "fin+kalshi_ladder", "Ladder over financial history"),
    (
        "fin+earnings_call",
        "fin+kalshi_ladder+earnings_call",
        "Ladder after controlling for the prior earnings call",
    ),
]


def rel(path):
    path = Path(path).resolve()
    return path.relative_to(ROOT) if path.is_relative_to(ROOT) else path


def markdown_table(headers, rows):
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    lines.extend("| " + " | ".join(str(value) for value in row) + " |" for row in rows)
    return lines


def target_count(frame):
    if frame.empty:
        return 0
    return len(frame[["ticker", "FE_FP_END"]].drop_duplicates())


def with_columns(frame, **columns):
    data = {column: frame[column] for column in frame.columns}
    data.update(columns)
    return pd.DataFrame(data, index=frame.index)


def rmse(errors):
    return float(np.sqrt(np.square(errors).mean()))


def metrics(prediction, truth):
    data = pd.DataFrame({"prediction": prediction, "truth": truth}).dropna()
    error = data["prediction"] - data["truth"]
    sse = float(np.square(error).sum())
    centered = data["truth"] - data["truth"].mean()
    sst = float(np.square(centered).sum())
    corr = (
        data["prediction"].corr(data["truth"])
        if len(data) > 1 and data["prediction"].std() > 1e-12
        else np.nan
    )
    return {
        "n": len(data),
        "rmse": rmse(error),
        "mae": float(error.abs().mean()),
        "corr": float(corr) if pd.notna(corr) else np.nan,
        "corr2": float(corr * corr) if pd.notna(corr) else np.nan,
        "r2": float(1 - sse / sst) if sst > 1e-12 else np.nan,
        "sign": float((np.sign(data["prediction"]) == np.sign(data["truth"])).mean()),
    }


def rmse_delta(data, base_arm, added_arm):
    common = data.dropna(subset=[base_arm, added_arm, "true_pct"])
    return rmse(common[added_arm] - common["true_pct"]) - rmse(
        common[base_arm] - common["true_pct"]
    )


def clustered_bootstrap(data, base_arm, added_arm, samples, seed):
    rng = np.random.default_rng(seed)
    companies = [group for _, group in data.groupby("ticker")]
    deltas = np.empty(samples)
    for index in range(samples):
        selected = rng.integers(0, len(companies), len(companies))
        sample = pd.concat([companies[item] for item in selected], ignore_index=True)
        deltas[index] = rmse_delta(sample, base_arm, added_arm)
    lower, upper = np.percentile(deltas, [2.5, 97.5])
    return float(lower), float(upper)


def company_sign_permutation(data, base_arm, added_arm, samples, seed):
    paired = data.assign(
        squared_error_difference=(
            np.square(data[added_arm] - data["true_pct"])
            - np.square(data[base_arm] - data["true_pct"])
        )
    )
    company_effects = (
        paired.groupby("ticker")["squared_error_difference"].sum().to_numpy(float)
    )
    observed = float(company_effects.sum() / len(paired))
    rng = np.random.default_rng(seed)
    extreme = 0
    completed = 0
    while completed < samples:
        size = min(10_000, samples - completed)
        signs = rng.choice([-1.0, 1.0], size=(size, len(company_effects)))
        null = (signs * company_effects).sum(axis=1) / len(paired)
        extreme += int((np.abs(null) >= abs(observed)).sum())
        completed += size
    return float((extreme + 1) / (samples + 1))


def leave_one_company_out(data, base_arm, added_arm):
    observed = rmse_delta(data, base_arm, added_arm)
    values = {
        ticker: rmse_delta(data[data["ticker"].ne(ticker)], base_arm, added_arm)
        for ticker in sorted(data["ticker"].unique())
    }
    influential = max(values, key=lambda ticker: abs(values[ticker] - observed))
    return (
        float(min(values.values())),
        float(max(values.values())),
        influential,
        float(values[influential]),
    )


def repeat_ids(columns, arm):
    pattern = re.compile(rf"^{re.escape(arm)}__r(\d+)$")
    return {
        int(match.group(1))
        for column in columns
        if (match := pattern.match(column))
    }


def cross_fit_calibrate(data, arm, seed, folds=5):
    rng = np.random.default_rng(seed)
    companies = list(data["ticker"].unique())
    rng.shuffle(companies)
    company_fold = {company: index % folds for index, company in enumerate(companies)}
    fold = data["ticker"].map(company_fold).to_numpy()
    raw = data[arm].to_numpy(float)
    truth = data["true_pct"].to_numpy(float)
    calibrated = np.full(len(data), np.nan)
    for index in range(folds):
        train = fold != index
        test = fold == index
        if train.sum() < 3 or not test.any():
            continue
        design = np.column_stack([np.ones(train.sum()), raw[train]])
        coefficients, *_ = np.linalg.lstsq(design, truth[train], rcond=None)
        calibrated[test] = coefficients[0] + coefficients[1] * raw[test]
    return calibrated


def synergy(data):
    truth = data["true_pct"].to_numpy(float)
    variance = np.square(truth - truth.mean()).mean()
    correlations = {}
    skills = {}
    for arm in ARMS:
        prediction = data[arm].to_numpy(float)
        correlations[arm] = np.corrcoef(prediction, truth)[0, 1]
        skills[arm] = 1 - np.square(truth - prediction).mean() / variance
    correlation_value = correlations[ARMS[3]] - (
        correlations[ARMS[1]] + correlations[ARMS[2]] - correlations[ARMS[0]]
    )
    skill_value = skills[ARMS[3]] - (
        skills[ARMS[1]] + skills[ARMS[2]] - skills[ARMS[0]]
    )
    return float(correlation_value), float(skill_value)


def clustered_synergy(data, samples, seed):
    rng = np.random.default_rng(seed)
    companies = [group for _, group in data.groupby("ticker")]
    values = np.empty((samples, 2))
    for index in range(samples):
        selected = rng.integers(0, len(companies), len(companies))
        sample = pd.concat([companies[item] for item in selected], ignore_index=True)
        values[index] = synergy(sample)
    return values


def company_shuffle_surrogate(data, arm, samples, seed):
    data = data.reset_index(drop=True)
    rng = np.random.default_rng(seed)
    groups = {
        ticker: list(index) for ticker, index in data.groupby("ticker").groups.items()
    }
    by_size = {}
    for ticker, indices in groups.items():
        by_size.setdefault(len(indices), []).append(ticker)
    truth = data["true_pct"].to_numpy(float)
    prediction = data[arm].to_numpy(float)
    observed = abs(np.corrcoef(prediction, truth)[0, 1])
    extreme = 0
    for _ in range(samples):
        shuffled = truth.copy()
        for tickers in by_size.values():
            if len(tickers) < 2:
                continue
            for source, destination in zip(tickers, rng.permutation(tickers)):
                shuffled[groups[source]] = truth[groups[destination]]
        if abs(np.corrcoef(prediction, shuffled)[0, 1]) >= observed:
            extreme += 1
    return float((extreme + 1) / (samples + 1))


def load_run_log(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def ladder_rungs(frame):
    rungs = []
    for raw in frame["kalshi_ladders_json"].dropna():
        for ladder in json.loads(raw):
            rungs.extend(ladder.get("rungs", []))
    return rungs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--series", type=Path, default=OUTPUTS / "kalshi_company_series.csv")
    parser.add_argument("--features", type=Path, default=OUTPUTS / "kalshi_company_event_features.csv")
    parser.add_argument("--y-panel", type=Path, default=OUTPUTS / "kalshi_stockdb_revenue_surprise_panel.csv")
    parser.add_argument("--events", type=Path, default=OUTPUTS / "kalshi_x_revsurprise_events.csv")
    parser.add_argument("--ladders", type=Path, default=OUTPUTS / "kalshi_prereport_ladder_panel.csv")
    parser.add_argument("--preds", type=Path, default=OUTPUTS / "kalshi_llm_ladder_ablation_preds.csv")
    parser.add_argument("--run-log", type=Path, default=OUTPUTS / "kalshi_llm_ladder_ablation_run_log.jsonl")
    parser.add_argument("--out-md", type=Path, default=KALSHI_ROOT / "RESULTS.md")
    parser.add_argument("--bootstrap-samples", type=int, default=5_000)
    parser.add_argument("--permutation-samples", type=int, default=50_000)
    parser.add_argument("--model", default=os.getenv("GPT_PARSER_MODEL", "gpt-5.5-2026-04-23"))
    parser.add_argument("--reasoning-effort", default=os.getenv("GPT_REASONING_EFFORT", "medium"))
    args = parser.parse_args()

    series = pd.read_csv(args.series)
    features = pd.read_csv(args.features)
    y_panel = pd.read_csv(args.y_panel)
    events = pd.read_csv(args.events)
    ladders = pd.read_csv(args.ladders)
    predictions = pd.read_csv(args.preds)
    run_log = load_run_log(args.run_log)

    features = features[features["feature_family"].eq("kpi_ladder")].copy()
    valid_y = y_panel[y_panel["surprise_early"].notna()].copy()
    events = with_columns(
        events,
        REPORT_DATE=pd.to_datetime(
            events["REPORT_DATE"], errors="coerce", format="mixed"
        ),
    )
    ladders = with_columns(
        ladders,
        REPORT_DATE=pd.to_datetime(
            ladders["REPORT_DATE"], errors="coerce", format="mixed"
        ),
    )
    predictions = with_columns(
        predictions,
        FE_FP_END=pd.to_datetime(predictions["FE_FP_END"], errors="raise"),
    )
    exact_post = events[events["REPORT_DATE"] > KNOWLEDGE_CUTOFF].copy()
    covered = ladders[
        pd.to_numeric(ladders["pre_event_count"], errors="coerce").fillna(0).gt(0)
    ].copy()
    covered_post = covered[covered["REPORT_DATE"] > KNOWLEDGE_CUTOFF].copy()
    quarterly = features["period_label"].fillna("").str.match(r"^Q[1-4] 20\d{2}$")

    if predictions.duplicated(["ticker", "FE_FP_END"]).any():
        raise SystemExit("prediction rows are not unique by ticker + FE_FP_END")
    missing_arms = sorted(set(ARMS) - set(predictions.columns))
    if missing_arms:
        raise SystemExit(f"predictions missing arms: {missing_arms}")
    if predictions[ARMS].isna().any().any():
        raise SystemExit("at least one final prediction arm is missing")

    final_keys = set(zip(predictions["ticker"], predictions["FE_FP_END"].dt.date))
    final_ladders = covered_post[
        [
            (row.ticker, pd.Timestamp(row.FE_FP_END).date()) in final_keys
            for row in covered_post.itertuples()
        ]
    ].copy()
    rungs = ladder_rungs(final_ladders)
    price_sources = Counter(rung.get("price_source", "missing") for rung in rungs)
    max_age = max(float(rung["candle_age_hours"]) for rung in rungs)

    calls = len(run_log)
    successful_calls = sum(record.get("prediction") is not None for record in run_log)
    call_errors = sum(bool(record.get("error")) for record in run_log)
    cost = sum(float(record.get("estimated_cost_usd", 0.0)) for record in run_log)
    repeats = sorted(repeat_ids(predictions.columns, "fin"))

    stage_rows = [
        ["Official KPI series", len(series), "n/a", 0, "official `tags=KPIs` response"],
        [
            "Series mapped to a stock",
            int(series["matched_ticker"].notna().sum()),
            series["matched_ticker"].nunique(),
            0,
            "approved company alias mapping",
        ],
        [
            "Usable raw-ladder events",
            len(features),
            features["matched_ticker"].nunique(),
            0,
            "at least two numeric YES-threshold contracts",
        ],
        [
            "Quarter-labelled ladder events",
            int(quarterly.sum()),
            features.loc[quarterly, "matched_ticker"].nunique(),
            0,
            "period parses as `Qx YYYY`",
        ],
        [
            "Valid Stock DB targets",
            len(valid_y),
            valid_y["ticker"].nunique(),
            len(valid_y),
            "actual and early point-in-time consensus",
        ],
        [
            "Exact fiscal-period matches",
            len(events),
            events["ticker"].nunique(),
            target_count(events),
            "ticker + fiscal year + fiscal quarter",
        ],
        [
            "Post-cutoff exact candidates",
            len(exact_post),
            exact_post["ticker"].nunique(),
            target_count(exact_post),
            "report date after 2025-12-01",
        ],
        [
            "Pre-publication ladder coverage",
            int(covered["pre_event_count"].sum()),
            covered["ticker"].nunique(),
            target_count(covered),
            "market-open-to-publication candle search",
        ],
        [
            "Post-cutoff ladder coverage",
            int(covered_post["pre_event_count"].sum()),
            covered_post["ticker"].nunique(),
            target_count(covered_post),
            "same cutoff applied after candle coverage",
        ],
        [
            "Final paired LLM sample",
            len(predictions),
            predictions["ticker"].nunique(),
            target_count(predictions),
            "four successful arms on one matched row set",
        ],
    ]

    final_rows = []
    for ticker, group in predictions.sort_values("FE_FP_END").groupby("ticker", sort=True):
        periods = ", ".join(
            f"Q{int(row.FISCAL_QUARTER)} FY{int(row.FISCAL_YEAR)} ({row.FE_FP_END.date()})"
            for row in group.itertuples()
        )
        final_rows.append(
            [
                ticker,
                len(group),
                periods,
                ", ".join(str(int(value)) for value in group["kalshi_history_quarters"]),
                int(group["kalshi_event_count"].sum()),
                int(group["kalshi_priced_rungs"].sum()),
            ]
        )

    arm_results = {
        arm: metrics(predictions[arm], predictions["true_pct"]) for arm in ARMS
    }
    comparison_rows = []
    comparison_details = []
    comparison_stats = []
    for pair_index, (base_arm, added_arm, label) in enumerate(PAIRS):
        data = predictions.dropna(subset=[base_arm, added_arm, "true_pct"]).copy()
        delta = rmse_delta(data, base_arm, added_arm)
        lower, upper = clustered_bootstrap(
            data, base_arm, added_arm, args.bootstrap_samples, SEED + pair_index
        )
        permutation_p = company_sign_permutation(
            data,
            base_arm,
            added_arm,
            args.permutation_samples,
            SEED + 100 + pair_index,
        )
        loo_lower, loo_upper, influential, influential_delta = leave_one_company_out(
            data, base_arm, added_arm
        )
        comparison_rows.append(
            [
                label,
                len(data),
                data["ticker"].nunique(),
                f"{rmse(data[base_arm] - data['true_pct']):.3f}",
                f"{rmse(data[added_arm] - data['true_pct']):.3f}",
                f"**{delta:+.3f}**",
                f"[{lower:+.3f}, {upper:+.3f}]",
                f"{permutation_p:.4f}",
            ]
        )
        comparison_details += [
            f"- **{label}:** leave-one-company-out delta range "
            f"`[{loo_lower:+.3f}, {loo_upper:+.3f}]`; most influential exclusion "
            f"is `{influential}` (`{influential_delta:+.3f}`)."
        ]
        comparison_stats.append((delta, lower, upper, permutation_p))

    matched = predictions.dropna(subset=ARMS + ["true_pct"]).reset_index(drop=True)
    observed_synergy = synergy(matched)
    synergy_bootstrap = clustered_synergy(matched, args.bootstrap_samples, SEED + 200)
    surrogate_p = company_shuffle_surrogate(
        matched, ARMS[-1], args.bootstrap_samples, SEED + 300
    )

    ticker_attrition = []
    for ticker in sorted(features["matched_ticker"].dropna().unique()):
        ticker_series = series[series["matched_ticker"].eq(ticker)]
        ticker_features = features[features["matched_ticker"].eq(ticker)]
        ticker_quarterly = ticker_features[
            ticker_features["period_label"].fillna("").str.match(r"^Q[1-4] 20\d{2}$")
        ]
        ticker_y = valid_y[valid_y["ticker"].eq(ticker)]
        ticker_events = events[events["ticker"].eq(ticker)]
        ticker_exact_post = exact_post[exact_post["ticker"].eq(ticker)]
        ticker_covered = covered[covered["ticker"].eq(ticker)]
        ticker_covered_post = covered_post[covered_post["ticker"].eq(ticker)]
        ticker_predictions = predictions[predictions["ticker"].eq(ticker)]
        if not ticker_predictions.empty:
            terminal_stage = "final sample"
        elif not ticker_exact_post.empty:
            exact_rows = ladders[
                ladders["ticker"].eq(ticker)
                & (ladders["REPORT_DATE"] > KNOWLEDGE_CUTOFF)
            ]
            if exact_rows["published_at"].isna().any():
                terminal_stage = "missing precise publication timestamp"
            elif ticker_covered_post.empty:
                terminal_stage = "no valid pre-publication ladder"
            else:
                terminal_stage = "history or prior-call eligibility"
        elif not ticker_covered.empty:
            terminal_stage = "model knowledge cutoff"
        elif not ticker_events.empty:
            terminal_stage = "no valid pre-publication ladder"
        elif not ticker_y.empty:
            terminal_stage = "no exact fiscal-period match"
        else:
            terminal_stage = "no Stock DB target"
        ticker_attrition.append(
            [
                ticker,
                ticker_series["series_ticker"].nunique(),
                ticker_features["event_ticker"].nunique(),
                ticker_quarterly["event_ticker"].nunique(),
                len(ticker_y),
                target_count(ticker_events),
                target_count(ticker_covered),
                target_count(ticker_predictions),
                terminal_stage,
            ]
        )

    robust = all(
        delta < 0 and upper < 0 and permutation_p < 0.05
        for delta, _, upper, permutation_p in comparison_stats
    )
    conclusion = (
        "Both predefined ladder comparisons pass the robustness gates."
        if robust
        else "The point estimates favor Kalshi, but the predefined robustness gates do not pass."
    )

    lines = [
        "# Kalshi Raw-Ladder Revenue-Surprise Experiment: Results",
        "",
        "> Generated by `kalshi/scripts/auto/s_an_kalshi_ladder_analysis.py`. "
        "Company-cluster seed: 2026.",
        "",
        "## Conclusion",
        "",
        f"{conclusion} Adding the raw ladder reduced RMSE by "
        f"{-comparison_stats[0][0]:.3f} percentage points over financial history and by "
        f"{-comparison_stats[1][0]:.3f} percentage points after controlling for the prior "
        "earnings call. Both company-bootstrap confidence intervals include zero, so the "
        "sample does not establish statistically robust incremental value.",
        "",
        "## Run record",
        "",
        f"- model: `{args.model}`",
        f"- reasoning effort: `{args.reasoning_effort}`",
        f"- targets: {len(predictions)} company-quarters across {predictions['ticker'].nunique()} tickers",
        f"- calls: {calls}; successful: {successful_calls}; errors: {call_errors}",
        f"- repeats per arm and target: {len(repeats)}",
        f"- estimated gateway cost: USD {cost:.2f}",
        f"- fiscal period range: {predictions['FE_FP_END'].min().date()} to {predictions['FE_FP_END'].max().date()}",
        f"- truth: mean {predictions['true_pct'].mean():+.3f}%, sample SD {predictions['true_pct'].std():.3f}%, positive rate {(predictions['true_pct'] > 0).mean():.3f}",
        "",
        "## Universe construction",
        "",
        "A company-quarter is one unique `ticker + FE_FP_END` target. It is not a Kalshi "
        "event, contract, rung, or LLM call.",
        "",
    ]
    lines.extend(
        markdown_table(
            ["stage", "rows / events", "tickers", "company-quarters", "rule"],
            stage_rows,
        )
    )
    lines += [
        "",
        "The earlier 45-day candle-age cap was not part of the Carbon Arc benchmark. "
        "Removing it and searching from each contract's actual `open_time` restored DIS "
        "Q1 FY2026, period end 2025-12-31 (six rungs; oldest age 1,110.7 hours). FDX "
        "remains excluded because "
        "Stock DB has no precise `published_at`, so a leakage-safe intraday cutoff cannot "
        "be constructed.",
        "",
        "## Final sample",
        "",
    ]
    lines.extend(
        markdown_table(
            [
                "ticker",
                "quarters",
                "fiscal periods",
                "prior X quarters",
                "target events",
                "priced rungs",
            ],
            final_rows,
        )
    )
    lines += [
        "",
        "## Raw-ladder diagnostics",
        "",
        f"- target-quarter events: {int(final_ladders['pre_event_count'].sum())}",
        f"- priced rungs: {len(rungs)}",
        f"- quote midpoint rungs: {price_sources['yes_quote_midpoint']}",
        f"- last-trade fallback rungs: {price_sources['last_trade_close']}",
        f"- previous-trade fallback rungs: {price_sources['previous_trade']}",
        f"- maximum candle age: {max_age:.1f} hours",
        f"- raw monotonicity violations: {int(final_ladders['pre_monotonicity_violations'].sum())}",
        "- settled outcomes, monotonic smoothing, interpolation, and scalar integration: none",
        "",
        "## Arm metrics",
        "",
    ]
    lines.extend(
        markdown_table(
            ["arm", "n", "RMSE", "MAE", "corr", "corr2", "R2", "sign accuracy"],
            [
                [
                    arm,
                    result["n"],
                    f"{result['rmse']:.3f}",
                    f"{result['mae']:.3f}",
                    f"{result['corr']:+.3f}",
                    f"{result['corr2']:.3f}",
                    f"{result['r2']:+.3f}",
                    f"{result['sign']:.3f}",
                ]
                for arm, result in arm_results.items()
            ],
        )
    )
    lines += [
        "",
        "RMSE and MAE are in revenue-surprise percentage points. R2 is evaluated on the "
        "paired sample; correlation squared is the benchmark's scale-free calibration ceiling.",
        "",
        "## Predefined incremental comparisons",
        "",
        "Delta is `RMSE(+ ladder) - RMSE(base)`; negative favors Kalshi.",
        "",
    ]
    lines.extend(
        markdown_table(
            [
                "comparison",
                "n",
                "firms",
                "RMSE base",
                "RMSE + ladder",
                "delta",
                "company-bootstrap 95% CI",
                "sign-permutation p",
            ],
            comparison_rows,
        )
    )
    lines += ["", *comparison_details, "", "## Benchmark robustness metrics", ""]
    lines += [
        "The Carbon Arc Factor 1 report also evaluates super-additive X-by-Z synergy, a "
        "company-shuffle surrogate, and leak-free company-fold calibration.",
        "",
        "| metric | observed | bootstrap mean | company-bootstrap 95% CI | p(<=0) |",
        "|---|---:|---:|---:|---:|",
    ]
    for index, label in enumerate(["correlation synergy", "MSE-skill synergy"]):
        lower, upper = np.percentile(synergy_bootstrap[:, index], [2.5, 97.5])
        lines.append(
            f"| {label} | {observed_synergy[index]:+.3f} | "
            f"{synergy_bootstrap[:, index].mean():+.3f} | "
            f"[{lower:+.3f}, {upper:+.3f}] | "
            f"{(synergy_bootstrap[:, index] <= 0).mean():.3f} |"
        )
    lines += [
        "",
        f"Company-shuffle surrogate for `{ARMS[-1]}`: p={surrogate_p:.3f}.",
        "",
        "| arm | raw R2 | calibrated R2 | corr2 ceiling |",
        "|---|---:|---:|---:|",
    ]
    truth = matched["true_pct"].to_numpy(float)
    for arm in ARMS:
        raw_result = metrics(matched[arm], truth)
        calibrated = cross_fit_calibrate(matched, arm, SEED + 400)
        calibrated_result = metrics(calibrated, truth)
        lines.append(
            f"| {arm} | {raw_result['r2']:+.3f} | "
            f"{calibrated_result['r2']:+.3f} | {raw_result['corr2']:.3f} |"
        )
    lines += [
        "",
        "## Decision rule and limitations",
        "",
        "A statistically robust incremental result requires a negative RMSE delta, a "
        "company-clustered 95% confidence interval fully below zero, and a company-level "
        "sign-permutation p-value below 0.05. Neither comparison passes all three gates.",
        "",
        "The evaluation has 36 observations across 28 firms, with only eight firms observed "
        "twice. Each arm was called once, so model-run variance is not estimated. The sample "
        "is concentrated in Q4 FY2025 and Q1 FY2026, and the DIS ladder is 46 days stale "
        "because that market stopped trading well before the earnings publication. These "
        "constraints limit power and generalization.",
        "",
        "## Usable-ladder ticker attrition",
        "",
    ]
    lines.extend(
        markdown_table(
            [
                "ticker",
                "series",
                "ladder events",
                "quarter events",
                "Y quarters",
                "exact quarters",
                "covered quarters",
                "final quarters",
                "terminal stage",
            ],
            ticker_attrition,
        )
    )
    lines += [
        "",
        "## Reproducibility artifacts",
        "",
        f"- predictions: `{rel(args.preds)}`",
        f"- per-call log: `{rel(args.run_log)}`",
        f"- pre-publication ladders: `{rel(args.ladders)}`",
        f"- exact event mappings: `{rel(args.events)}`",
        f"- Stock DB target panel: `{rel(args.y_panel)}`",
    ]

    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.write_text("\n".join(lines) + "\n")
    print(f"[written] {args.out_md}")
    print(
        f"targets={len(predictions)} tickers={predictions['ticker'].nunique()} "
        f"calls={calls} successful={successful_calls}"
    )


if __name__ == "__main__":
    main()
