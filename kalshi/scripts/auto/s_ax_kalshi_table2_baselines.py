#!/usr/bin/env python3
"""Build the Kalshi block for the paper's Revenue-YoY baseline table.

The LLM continues to receive the full raw Kalshi ladder. This module defines a separate,
pre-specified scalar representation only for classical OLS/GBT baselines:

    normalized survival-curve AUC = integral P(KPI > strike) d(normalized strike)

The transformation is unitless, uses no realized KPI or revenue label, and preserves raw rung
probabilities without monotonic smoothing. The evaluator reports the full 21-row sample and the
exact-two-call 19-row sensitivity without making any new LLM calls.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from prediction.baselines.estimators import get_estimator
from prediction.baselines.specs import GBT_PARAMS
from prediction.panel.features import lag_y, sentiment

ROOT = Path(__file__).resolve().parents[3]
LEXICON = ROOT / "lm_sentiment.json"
FEATURES = ("kalshi_x_auc", "sent", "lag_y")
LLM_ARMS = ("fin", "fin+x", "fin+text", "fin+x+text")
METHODS = (
    ("historical_average", "Historical Avg."),
    ("ols", "OLS"),
    ("gbt", "GBT"),
    ("ensembled_llm", "Ensembled LLM"),
    ("our_method", "Our Method"),
)
BOOTSTRAP_REPS = 5_000
BOOTSTRAP_SEED = 2026


def _target_key(ticker, fp) -> tuple[str, str]:
    return str(ticker), str(pd.Timestamp(fp).date())


def _payload_event(payload) -> dict | None:
    if not isinstance(payload, str) or not payload.strip():
        return None
    events = json.loads(payload)
    if len(events) != 1:
        raise ValueError(
            f"Table 2 scalarization requires exactly one Kalshi event per quarter, got {len(events)}"
        )
    return events[0]


def normalized_survival_auc(payload) -> float:
    """Integrate the raw probability ladder over its normalized strike range."""
    event = _payload_event(payload)
    if event is None:
        return float("nan")
    rungs = event.get("rungs") or []
    if len(rungs) < 2:
        raise ValueError("Table 2 scalarization requires at least two priced rungs")
    operators = {str(rung.get("threshold_operator")) for rung in rungs}
    if not operators.issubset({">", ">="}):
        raise ValueError(f"unsupported Kalshi threshold direction: {sorted(operators)}")

    ordered = sorted(rungs, key=lambda rung: float(rung["strike"]))
    strikes = np.asarray([float(rung["strike"]) for rung in ordered], dtype=float)
    probabilities = np.asarray([float(rung["probability"]) for rung in ordered], dtype=float)
    if not np.isfinite(strikes).all() or not np.isfinite(probabilities).all():
        raise ValueError("non-finite strike or probability in Kalshi ladder")
    if (probabilities < 0).any() or (probabilities > 1).any():
        raise ValueError("Kalshi rung probability is outside [0, 1]")
    if len(np.unique(strikes)) != len(strikes):
        raise ValueError("duplicate strikes are not allowed in Table 2 scalarization")
    width = strikes[-1] - strikes[0]
    if width <= 0:
        raise ValueError("Kalshi ladder strike range must be positive")

    normalized_strikes = (strikes - strikes[0]) / width
    return float(np.trapezoid(probabilities, normalized_strikes))


def _event_metadata(payload) -> dict:
    event = _payload_event(payload)
    if event is None:
        return {
            "kalshi_x_auc": float("nan"),
            "event_ticker": None,
            "metric_label": None,
            "rung_count": 0,
            "monotonicity_violations": 0,
        }
    rungs = event.get("rungs") or []
    return {
        "kalshi_x_auc": normalized_survival_auc(payload),
        "event_ticker": event.get("event_ticker"),
        "metric_label": event.get("metric_label"),
        "rung_count": len(rungs),
        "monotonicity_violations": int(event.get("monotonicity_violations") or 0),
    }


def build_feature_frame(panel: pd.DataFrame, transcripts) -> pd.DataFrame:
    """Create leakage-safe scalar baseline features from the frozen panel and transcript index."""
    frame = panel.copy().astype({
        "FE_FP_END": "datetime64[ns]",
        "REPORT_DATE": "datetime64[ns]",
    })
    frame = frame.sort_values(["ticker", "FE_FP_END"]).reset_index(drop=True)
    frame = frame.assign(
        true=frame["rev_yoy"],
        lag_y=lag_y(frame, "rev_yoy"),
    )

    metadata = pd.DataFrame([
        _event_metadata(payload) for payload in frame["x_payload"]
    ])
    frame = pd.concat([frame.reset_index(drop=True), metadata], axis=1)

    sentiments = []
    has_calls = []
    call_dates = []
    for row in frame.itertuples():
        calls = transcripts.prior_calls(
            row.ticker,
            pd.Timestamp(row.REPORT_DATE).date(),
            1,
        )
        if calls:
            sentiments.append(sentiment(calls[0].path))
            has_calls.append(True)
            call_dates.append(str(calls[0].call_date))
        else:
            sentiments.append(float("nan"))
            has_calls.append(False)
            call_dates.append(None)
    frame = frame.assign(
        sent=sentiments,
        has_call=has_calls,
        call_date=call_dates,
    )
    return frame[[
        "ticker", "FE_FP_END", "REPORT_DATE", "true", "kalshi_x_auc", "sent", "lag_y",
        "has_call", "call_date", "event_ticker", "metric_label", "rung_count",
        "monotonicity_violations",
    ]].rename(columns={
        "FE_FP_END": "fp",
        "REPORT_DATE": "report",
    })


def _target_frame(features: pd.DataFrame, manifest: pd.DataFrame) -> pd.DataFrame:
    targets = (
        manifest[manifest["y"].eq("rev_yoy")][["ticker", "FE_FP_END", "true"]]
        .rename(columns={"FE_FP_END": "fp", "true": "manifest_true"})
        .astype({"fp": "datetime64[ns]"})
    )
    if targets.duplicated(["ticker", "fp"]).any():
        raise RuntimeError("duplicate Revenue-YoY target in Table 2 manifest")
    test = targets.merge(features, on=["ticker", "fp"], how="left", validate="one_to_one")
    if test["kalshi_x_auc"].isna().any():
        missing = test.loc[test["kalshi_x_auc"].isna(), ["ticker", "fp"]].to_dict("records")
        raise RuntimeError(f"Table 2 targets lack scalarized Kalshi X: {missing}")
    if not np.allclose(test["manifest_true"], test["true"], equal_nan=False):
        raise RuntimeError("Table 2 feature truth differs from the evaluation manifest")
    return test.drop(columns="manifest_true").sort_values(["ticker", "fp"]).reset_index(drop=True)


def _ols_fit_predict(train: pd.DataFrame,
                     test: pd.DataFrame) -> tuple[np.ndarray, dict, float]:
    design = np.column_stack([
        np.ones(len(train)),
        *[train[column].to_numpy(float) for column in FEATURES],
    ])
    coefficients, *_ = np.linalg.lstsq(
        design,
        train["true"].to_numpy(float) * 100.0,
        rcond=None,
    )
    test_design = np.column_stack([
        np.ones(len(test)),
        *[test[column].to_numpy(float) for column in FEATURES],
    ])
    names = ("intercept", *FEATURES)
    return (
        test_design @ coefficients,
        {name: float(value) for name, value in zip(names, coefficients)},
        float(np.linalg.cond(design)),
    )


def fit_classical_predictions(features: pd.DataFrame, manifest: pd.DataFrame,
                              cutoff) -> tuple[pd.DataFrame, dict]:
    """Fit N0/N3b/N5 analogues and predict the full matched Revenue-YoY target set."""
    cutoff_ts = pd.Timestamp(cutoff)
    train_all = features[
        features["report"].le(cutoff_ts) & features["true"].notna()
    ].copy()
    train = train_all.dropna(subset=["kalshi_x_auc"]).copy()
    test = _target_frame(features, manifest)
    if len(train) < 10 or train["ticker"].nunique() < 2:
        raise RuntimeError("insufficient pre-cutoff scalarized Kalshi training sample")

    lag_fill = float(train_all["true"].mean())
    train = train.assign(
        sent=train["sent"].fillna(0.0),
        lag_y=train["lag_y"].fillna(lag_fill),
    )
    test = test.assign(
        sent=test["sent"].fillna(0.0),
        lag_y=test["lag_y"].fillna(lag_fill),
    )

    company_mean = train_all.groupby("ticker")["true"].mean() * 100.0
    global_mean = float(train_all["true"].mean() * 100.0)
    historical = test["ticker"].map(company_mean).fillna(global_mean).to_numpy(float)
    ols_predictions, coefficients, condition_number = _ols_fit_predict(train, test)
    gbt_predictions = get_estimator("gbt")(
        train,
        test,
        list(FEATURES),
        GBT_PARAMS,
    )
    test = test.assign(
        historical_average=historical,
        ols=ols_predictions,
        gbt=gbt_predictions,
    )
    audit = {
        "training_rows": int(len(train)),
        "training_firms": int(train["ticker"].nunique()),
        "training_tickers": sorted(train["ticker"].unique()),
        "training_rows_with_eligible_call": int(train["has_call"].sum()),
        "all_pre_cutoff_financial_rows": int(len(train_all)),
        "test_rows": int(len(test)),
        "test_firms": int(test["ticker"].nunique()),
        "test_rows_with_eligible_call": int(test["has_call"].sum()),
        "lag_fill_fraction": lag_fill,
        "ols_coefficients": coefficients,
        "ols_design_condition_number": condition_number,
        "feature_support": {
            column: {
                "train_min": float(train[column].min()),
                "train_max": float(train[column].max()),
                "test_min": float(test[column].min()),
                "test_max": float(test[column].max()),
            }
            for column in FEATURES
        },
        "prediction_ranges_pct": {
            method: {
                "min": float(test[method].min()),
                "max": float(test[method].max()),
            }
            for method in ("historical_average", "ols", "gbt")
        },
        "gbt_parameters": {**GBT_PARAMS, "random_state": 2026},
    }
    return test, audit


def attach_llm_predictions(classical: pd.DataFrame, records: list[dict]) -> pd.DataFrame:
    """Attach TOOL Revenue-YoY predictions and form the three-arm LLM ensemble per repetition."""
    rows = []
    selected = sorted(
        (
            record for record in records
            if record["y"] == "rev_yoy" and record["variant"] == "TOOL"
        ),
        key=lambda record: record["seed"],
    )
    if not selected:
        raise RuntimeError("no TOOL Revenue-YoY records for Table 2")
    expected = {
        _target_key(ticker, fp)
        for ticker, fp in zip(classical["ticker"], classical["fp"])
    }
    for record in selected:
        predictions = record["preds"].copy().astype({"fp": "datetime64[ns]"})
        actual = {
            _target_key(ticker, fp)
            for ticker, fp in zip(predictions["tkr"], predictions["fp"])
        }
        if actual != expected:
            raise RuntimeError(f"Table 2 row mismatch for seed {record['seed']}")
        merged = classical.merge(
            predictions[[
                "tkr", "fp", "true", *LLM_ARMS,
            ]].rename(columns={"tkr": "ticker", "true": "prediction_true"}),
            on=["ticker", "fp"],
            how="inner",
            validate="one_to_one",
        ).copy()
        if not np.allclose(merged["true"], merged["prediction_true"], equal_nan=False):
            raise RuntimeError(f"Table 2 prediction truth mismatch for seed {record['seed']}")
        if merged[list(LLM_ARMS)].isna().any().any():
            raise RuntimeError(f"Table 2 LLM arm prediction is missing for seed {record['seed']}")
        merged = merged.assign(
            seed=record["seed"],
            true_pct=merged["true"] * 100.0,
            ensembled_llm=merged[["fin", "fin+x", "fin+text"]].mean(axis=1),
            our_method=merged["fin+x+text"],
        )
        rows.append(merged.drop(columns="prediction_true"))
    return pd.concat(rows, ignore_index=True).sort_values(
        ["seed", "ticker", "fp"]
    ).reset_index(drop=True)


def fvu_mae(true_pct, prediction_pct) -> dict:
    truth = np.asarray(true_pct, dtype=float)
    prediction = np.asarray(prediction_pct, dtype=float)
    sst = float(np.square(truth - truth.mean()).sum())
    if sst <= 1e-12:
        raise ValueError("FVU is undefined for a constant truth sample")
    return {
        "fvu": float(np.square(truth - prediction).sum() / sst),
        "mae": float(np.abs(truth - prediction).mean()),
    }


def _sample_predictions(predictions: pd.DataFrame, exact_keys: set[tuple[str, str]],
                        sample: str) -> pd.DataFrame:
    if sample == "full_21":
        return predictions.copy()
    if sample != "exact_two_call_19":
        raise ValueError(f"unknown Table 2 sample: {sample}")
    keep = [
        _target_key(ticker, fp) in exact_keys
        for ticker, fp in zip(predictions["ticker"], predictions["fp"])
    ]
    return predictions[keep].copy()


def metrics_by_repetition(predictions: pd.DataFrame,
                          exact_keys: set[tuple[str, str]]) -> pd.DataFrame:
    rows = []
    for sample in ("full_21", "exact_two_call_19"):
        selected = _sample_predictions(predictions, exact_keys, sample)
        for seed, group in selected.groupby("seed", sort=True):
            for method, label in METHODS:
                rows.append({
                    "sample": sample,
                    "seed": int(seed),
                    "method": method,
                    "label": label,
                    "n": int(len(group)),
                    "firms": int(group["ticker"].nunique()),
                    **fvu_mae(group["true_pct"], group[method]),
                })
    return pd.DataFrame(rows)


def ensemble_first_predictions(predictions: pd.DataFrame,
                               exact_keys: set[tuple[str, str]]) -> pd.DataFrame:
    """Average LLM repetitions by target before statistical resampling."""
    baseline_columns = ["historical_average", "ols", "gbt"]
    llm_columns = ["ensembled_llm", "our_method"]
    rows = []
    for sample in ("full_21", "exact_two_call_19"):
        selected = _sample_predictions(predictions, exact_keys, sample)
        baseline_spread = selected.groupby(["ticker", "fp"])[baseline_columns].std().fillna(0.0)
        if (baseline_spread.to_numpy() > 1e-12).any():
            raise RuntimeError("deterministic Table 2 baseline differs across LLM repetitions")
        fixed = (
            selected.groupby(["ticker", "fp"], as_index=False)
            .agg({
                "true_pct": "first",
                **{column: "first" for column in baseline_columns},
                **{column: "mean" for column in llm_columns},
            })
        )
        fixed["sample"] = sample
        rows.append(fixed)
    return pd.concat(rows, ignore_index=True)


def company_cluster_bootstrap(point_predictions: pd.DataFrame,
                              reps: int = BOOTSTRAP_REPS,
                              seed: int = BOOTSTRAP_SEED) -> pd.DataFrame:
    rows = []
    for sample_index, (sample, frame) in enumerate(
        point_predictions.groupby("sample", sort=False)
    ):
        firms = np.asarray(sorted(frame["ticker"].unique()))
        groups = {
            ticker: np.flatnonzero(frame["ticker"].to_numpy() == ticker)
            for ticker in firms
        }
        rng = np.random.default_rng(seed + sample_index)
        bootstrap_id = 0
        attempts = 0
        while bootstrap_id < reps:
            attempts += 1
            if attempts > reps * 100:
                raise RuntimeError(f"could not draw {reps} non-constant bootstrap samples")
            sampled = rng.choice(firms, size=len(firms), replace=True)
            indices = np.concatenate([groups[ticker] for ticker in sampled])
            draw = frame.iloc[indices]
            truth = draw["true_pct"].to_numpy(float)
            if np.square(truth - truth.mean()).sum() <= 1e-12:
                continue
            for method, label in METHODS:
                rows.append({
                    "sample": sample,
                    "bootstrap_id": bootstrap_id,
                    "method": method,
                    "label": label,
                    **fvu_mae(draw["true_pct"], draw[method]),
                })
            bootstrap_id += 1
    return pd.DataFrame(rows)


def summarize_table2(point_predictions: pd.DataFrame,
                     bootstrap: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for sample, frame in point_predictions.groupby("sample", sort=False):
        boot_sample = bootstrap[bootstrap["sample"].eq(sample)]
        for method, label in METHODS:
            point = fvu_mae(frame["true_pct"], frame[method])
            draws = boot_sample[boot_sample["method"].eq(method)]
            row = {
                "sample": sample,
                "method": method,
                "label": label,
                "n": int(len(frame)),
                "firms": int(frame["ticker"].nunique()),
                **point,
            }
            for metric in ("fvu", "mae"):
                values = draws[metric].to_numpy(float)
                row[f"{metric}_bootstrap_mean"] = float(values.mean())
                row[f"{metric}_bootstrap_sd"] = float(values.std(ddof=1))
                row[f"{metric}_ci_low"], row[f"{metric}_ci_high"] = (
                    float(value) for value in np.percentile(values, [2.5, 97.5])
                )
            rows.append(row)
    order = {method: index for index, (method, _) in enumerate(METHODS)}
    result = pd.DataFrame(rows)
    indices = np.lexsort((
        result["method"].map(order).to_numpy(),
        result["sample"].to_numpy(),
    ))
    return result.iloc[indices].reset_index(drop=True)


def evaluate_table2(cfg, panel: pd.DataFrame, records: list[dict],
                    manifest: pd.DataFrame, exact_manifest: pd.DataFrame) -> dict:
    transcript_context = next(
        record["context"].transcripts for record in records
        if record["y"] == "rev_yoy" and record["variant"] == "TOOL"
    )
    features = build_feature_frame(panel, transcript_context)
    classical, model_audit = fit_classical_predictions(
        features,
        manifest,
        cfg.run.cutoff,
    )
    predictions = attach_llm_predictions(classical, records)
    exact_rows = exact_manifest[exact_manifest["y"].eq("rev_yoy")]
    exact_keys = {
        _target_key(ticker, fp)
        for ticker, fp in zip(exact_rows["ticker"], exact_rows["FE_FP_END"])
    }
    full_keys = {
        _target_key(ticker, fp)
        for ticker, fp in zip(classical["ticker"], classical["fp"])
    }
    if len(full_keys) != 21 or len(exact_keys) != 19 or not exact_keys.issubset(full_keys):
        raise RuntimeError(
            "Table 2 requires the frozen 21-row primary and 19-row exact-two-call samples"
        )
    if predictions["seed"].nunique() != cfg.run.reps:
        raise RuntimeError(
            f"Table 2 requires {cfg.run.reps} LLM repetitions, "
            f"got {predictions['seed'].nunique()}"
        )
    predictions = predictions.assign(exact_two_call_eligible=[
        _target_key(ticker, fp) in exact_keys
        for ticker, fp in zip(predictions["ticker"], predictions["fp"])
    ])
    per_rep = metrics_by_repetition(predictions, exact_keys)
    point_predictions = ensemble_first_predictions(predictions, exact_keys)
    bootstrap = company_cluster_bootstrap(point_predictions)
    summary = summarize_table2(point_predictions, bootstrap)

    lexicon = json.loads(LEXICON.read_text())
    audit = {
        "analysis": "Kalshi Revenue-YoY Table 2 baselines",
        "new_llm_calls": 0,
        "llm_input": "Unchanged raw variable-length Kalshi ladder",
        "classical_x": {
            "name": "normalized survival-curve AUC",
            "formula": "integral P(KPI > strike) d(normalized strike)",
            "rationale": (
                "a frozen unit-invariant scalar that makes heterogeneous KPI ladders usable by "
                "OLS and GBT without changing the raw-ladder LLM input"
            ),
            "range": [0.0, 1.0],
            "monotonic_smoothing": False,
            "uses_realized_kpi_or_target_label": False,
            "events_per_company_quarter": 1,
        },
        "classical_z": {
            "name": "Loughran-McDonald net tone",
            "formula": "(positive_hits - negative_hits) / (positive_hits + negative_hits)",
            "source_call": "most recent corrected call satisfying the 31-day embargo",
            "transcript_truncation": "none for the sentiment baseline",
        },
        "classical_h": "one-quarter lag of Revenue YoY",
        "missing_value_policy": {
            "sent_without_eligible_call": 0.0,
            "lag_y": "pre-cutoff mean Revenue YoY; no selected train or test row required it",
        },
        "ensemble_llm": "arithmetic mean of H, H+X, and H+Z predictions for each target and run",
        "our_method": "H+X+Z",
        "samples": {
            "full_21": {
                "rows": int(manifest[manifest["y"].eq("rev_yoy")].shape[0]),
                "firms": int(manifest.loc[manifest["y"].eq("rev_yoy"), "ticker"].nunique()),
            },
            "exact_two_call_19": {
                "rows": int(len(exact_rows)),
                "firms": int(exact_rows["ticker"].nunique()),
            },
        },
        "metrics": {
            "fvu": "SSE / SST = 1 - OOS R-squared",
            "mae": "mean absolute error in Revenue-YoY percentage points",
            "reported_uncertainty": (
                "full-sample point estimate plus or minus company-clustered bootstrap SD"
            ),
        },
        "bootstrap": {
            "repetitions": BOOTSTRAP_REPS,
            "seed_full": BOOTSTRAP_SEED,
            "seed_exact_two_call": BOOTSTRAP_SEED + 1,
            "llm_repetitions": (
                "three predictions are averaged by target before company-clustered resampling"
            ),
        },
        "runtime_lexicon": {
            "path": str(LEXICON.relative_to(ROOT)),
            "sha256": hashlib.sha256(LEXICON.read_bytes()).hexdigest(),
            "positive_words": len(lexicon["positive"]),
            "negative_words": len(lexicon["negative"]),
        },
        "provided_csv_validation": {
            "source_name": "lm_master_dictionary.csv",
            "sha256": "e2d1328682bab7d2187684fb9f5420bb730401c9eefc00daf835edd203f4859d",
            "rows": 86_553,
            "positive_words": 347,
            "negative_words": 2_345,
            "positive_and_negative_sets_match_runtime_lexicon": True,
        },
        "model_fit": model_audit,
    }
    return {
        "features": features,
        "predictions": predictions,
        "point_predictions": point_predictions,
        "metrics_by_rep": per_rep,
        "bootstrap": bootstrap,
        "summary": summary,
        "audit": audit,
    }


def write_table2_data(result: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    result["features"].to_csv(output_dir / "table2_feature_audit.csv", index=False)
    result["predictions"].to_csv(output_dir / "table2_predictions_by_rep.csv", index=False)
    result["point_predictions"].to_csv(
        output_dir / "table2_predictions_ensemble_first.csv",
        index=False,
    )
    result["metrics_by_rep"].to_csv(output_dir / "table2_metrics_by_rep.csv", index=False)
    result["bootstrap"].to_csv(output_dir / "table2_company_bootstrap.csv", index=False)
    result["summary"].to_csv(output_dir / "table2_metrics_summary.csv", index=False)
    (output_dir / "table2_audit.json").write_text(
        json.dumps(result["audit"], indent=2, ensure_ascii=True) + "\n"
    )


def markdown_table(summary: pd.DataFrame, sample: str) -> str:
    rows = summary[summary["sample"].eq(sample)]
    lines = [
        "| Method | FVU (lower is better) | MAE (pp, lower is better) |",
        "|---|---:|---:|",
    ]
    for row in rows.itertuples():
        lines.append(
            f"| {row.label} | {row.fvu:.3f} (+/- {row.fvu_bootstrap_sd:.3f}) | "
            f"{row.mae:.2f} (+/- {row.mae_bootstrap_sd:.2f}) |"
        )
    return "\n".join(lines)


def _latex_table(summary: pd.DataFrame, sample: str, caption: str, label: str) -> str:
    rows = summary[summary["sample"].eq(sample)].copy()
    best_fvu = float(rows["fvu"].min())
    best_mae = float(rows["mae"].min())
    body = []
    for row in rows.itertuples():
        fvu = f"{row.fvu:.3f} ($\\pm${row.fvu_bootstrap_sd:.3f})"
        mae = f"{row.mae:.2f} ($\\pm${row.mae_bootstrap_sd:.2f})"
        if np.isclose(row.fvu, best_fvu):
            fvu = rf"\textbf{{{fvu}}}"
        if np.isclose(row.mae, best_mae):
            mae = rf"\textbf{{{mae}}}"
        body.append(f"{row.label} & {fvu} & {mae} \\\\")
    n = int(rows.iloc[0]["n"])
    firms = int(rows.iloc[0]["firms"])
    return (
        r"""\begin{table}[t]
\centering
\caption{\textbf{""" + caption + r"""}
FVU and MAE are full-sample point estimates; parentheses report company-clustered
bootstrap standard deviations (5,000 draws). LLM predictions are averaged across three
independent runs before resampling. The matched sample contains """ + str(n)
        + " company-quarters / " + str(firms) + r""" firms.}
\label{""" + label + r"""}
\begin{tabular}{lcc}
\toprule
Method & FVU ($\downarrow$) & MAE ($\downarrow$) \\
\midrule
""" + "\n".join(body) + r"""
\bottomrule
\end{tabular}
\end{table}
"""
    )


def render_table2_latex(summary: pd.DataFrame, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "kalshi_baselines.tex").write_text(_latex_table(
        summary,
        "full_21",
        "Kalshi Revenue-YoY prediction versus classical supervised baselines.",
        "tab:kalshi_baselines",
    ))
    (output_dir / "kalshi_baselines_exact_two_call.tex").write_text(_latex_table(
        summary,
        "exact_two_call_19",
        "Kalshi exact-two-call Revenue-YoY baseline sensitivity.",
        "tab:kalshi_baselines_exact_two_call",
    ))
