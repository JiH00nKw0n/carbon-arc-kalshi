#!/usr/bin/env python3
"""Build Kalshi Table 1 source-ablation metrics with sampling uncertainty.

The three independent LLM predictions are averaged target by target before evaluation. Point
estimates use the resulting matched panel, and error bars are standard deviations from 5,000
company-clustered bootstrap draws. The primary 21-row sample and exact-two-call 19-row sensitivity
are both retained.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from kalshi.scripts.auto.s_ax_kalshi_table2_baselines import (
    BOOTSTRAP_REPS,
    BOOTSTRAP_SEED,
    fvu_mae,
)

ARMS = (
    ("fin", "H", r"$H$"),
    ("fin+x", "H+X", r"$H+X$"),
    ("fin+text", "H+Z", r"$H+Z$"),
    ("fin+x+text", "H+X+Z", r"$H+X+Z$"),
)
TOOL_SETTINGS = (
    ("BASE", "Without tool use", "Without tool use"),
    ("TOOL", "With tool use", "With tool use"),
)
SAMPLES = ("full_21", "exact_two_call_19")


def average_repetitions(predictions: pd.DataFrame, expected_reps: int) -> pd.DataFrame:
    """Average each source arm across runs while preserving the two frozen samples."""
    arm_columns = [arm for arm, _, _ in ARMS]
    required = {
        "ticker", "fp", "seed", "true_pct", "exact_two_call_eligible", *arm_columns,
    }
    missing = required - set(predictions.columns)
    if missing:
        raise RuntimeError(f"Table 1 predictions lack columns: {sorted(missing)}")
    if predictions[arm_columns].isna().any().any():
        raise RuntimeError("Table 1 source-arm prediction is missing")

    rows = []
    for sample in SAMPLES:
        selected = (
            predictions
            if sample == "full_21"
            else predictions[predictions["exact_two_call_eligible"]].copy()
        )
        counts = selected.groupby(["ticker", "fp"])["seed"].nunique()
        if not counts.eq(expected_reps).all():
            raise RuntimeError(
                f"Table 1 {sample} requires {expected_reps} repetitions for every target"
            )
        truth_spread = selected.groupby(["ticker", "fp"])["true_pct"].std().fillna(0.0)
        if (truth_spread > 1e-12).any():
            raise RuntimeError(f"Table 1 truth differs across repetitions in {sample}")

        averaged = (
            selected.groupby(["ticker", "fp"], as_index=False)
            .agg({
                "true_pct": "first",
                **{arm: "mean" for arm in arm_columns},
            })
        )
        averaged["sample"] = sample
        rows.append(averaged)

    result = pd.concat(rows, ignore_index=True)
    sample_sizes = result.groupby("sample").size().to_dict()
    if sample_sizes != {"exact_two_call_19": 19, "full_21": 21}:
        raise RuntimeError(f"unexpected Table 1 sample sizes: {sample_sizes}")
    return result


def company_cluster_bootstrap(
    point_predictions: pd.DataFrame,
    reps: int = BOOTSTRAP_REPS,
    seed: int = BOOTSTRAP_SEED,
    methods=ARMS,
) -> pd.DataFrame:
    """Resample firms with replacement, preserving all quarters within each sampled firm."""
    rows = []
    for sample_index, sample in enumerate(SAMPLES):
        frame = point_predictions[point_predictions["sample"].eq(sample)].reset_index(drop=True)
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
                raise RuntimeError(f"could not draw {reps} non-constant samples for {sample}")
            sampled = rng.choice(firms, size=len(firms), replace=True)
            indices = np.concatenate([groups[ticker] for ticker in sampled])
            draw = frame.iloc[indices]
            truth = draw["true_pct"].to_numpy(float)
            if np.square(truth - truth.mean()).sum() <= 1e-12:
                continue
            for arm, label, _ in methods:
                rows.append({
                    "sample": sample,
                    "bootstrap_id": bootstrap_id,
                    "model": arm,
                    "label": label,
                    **fvu_mae(draw["true_pct"], draw[arm]),
                })
            bootstrap_id += 1
    return pd.DataFrame(rows)


def summarize(
    point_predictions: pd.DataFrame,
    bootstrap: pd.DataFrame,
    methods=ARMS,
) -> pd.DataFrame:
    """Return full-sample point metrics and paired-bootstrap uncertainty by source arm."""
    rows = []
    for sample in SAMPLES:
        frame = point_predictions[point_predictions["sample"].eq(sample)]
        boot_sample = bootstrap[bootstrap["sample"].eq(sample)]
        for arm, label, _ in methods:
            point = fvu_mae(frame["true_pct"], frame[arm])
            draws = boot_sample[boot_sample["model"].eq(arm)]
            row = {
                "sample": sample,
                "model": arm,
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
    return pd.DataFrame(rows)


def evaluate_table1(predictions: pd.DataFrame, expected_reps: int) -> dict:
    point_predictions = average_repetitions(predictions, expected_reps)
    bootstrap = company_cluster_bootstrap(point_predictions)
    summary = summarize(point_predictions, bootstrap)
    audit = {
        "analysis": "Kalshi Revenue-YoY Table 1 source ablation",
        "new_llm_calls": 0,
        "models": {
            "H": "financial history",
            "H+X": "financial history plus the raw Kalshi ladder",
            "H+Z": "financial history plus eligible corrected earnings calls",
            "H+X+Z": "joint Kalshi method",
        },
        "samples": {
            sample: {
                "rows": int(
                    point_predictions[point_predictions["sample"].eq(sample)].shape[0]
                ),
                "firms": int(
                    point_predictions.loc[
                        point_predictions["sample"].eq(sample), "ticker"
                    ].nunique()
                ),
            }
            for sample in SAMPLES
        },
        "metrics": {
            "fvu": "SSE / SST = 1 - OOS R-squared",
            "mae": "mean absolute error in Revenue-YoY percentage points",
            "reported_uncertainty": (
                "full-sample point estimate plus or minus company-clustered bootstrap SD"
            ),
        },
        "llm_repetitions": {
            "count": expected_reps,
            "aggregation": "arithmetic mean by target and source arm before evaluation",
        },
        "bootstrap": {
            "repetitions": BOOTSTRAP_REPS,
            "seed_full": BOOTSTRAP_SEED,
            "seed_exact_two_call": BOOTSTRAP_SEED + 1,
            "cluster": "ticker",
        },
    }
    return {
        "point_predictions": point_predictions,
        "bootstrap": bootstrap,
        "summary": summary,
        "audit": audit,
    }


def _target_key(ticker, fp) -> tuple[str, str]:
    return str(ticker), str(pd.Timestamp(fp).date())


def average_tool_settings(
    records: list[dict],
    exact_reference: pd.DataFrame,
    expected_reps: int,
) -> pd.DataFrame:
    """Average the headline H+X+Z prediction separately for BASE and TOOL."""
    exact_keys = {
        _target_key(ticker, fp)
        for ticker, fp, eligible in zip(
            exact_reference["ticker"],
            exact_reference["fp"],
            exact_reference["exact_two_call_eligible"],
        )
        if eligible
    }
    rows = []
    for record in records:
        if record["y"] != "rev_yoy" or record["variant"] not in {"BASE", "TOOL"}:
            continue
        predictions = record["preds"].copy().astype({"fp": "datetime64[ns]"})
        if predictions["fin+x+text"].isna().any():
            raise RuntimeError(
                f"Table 1 tool-use prediction is missing for seed {record['seed']} "
                f"{record['variant']}"
            )
        rows.append(pd.DataFrame({
            "ticker": predictions["tkr"],
            "fp": predictions["fp"],
            "seed": record["seed"],
            "variant": record["variant"],
            "true_pct": predictions["true"] * 100.0,
            "prediction": predictions["fin+x+text"],
        }))
    long = pd.concat(rows, ignore_index=True)

    outputs = []
    for sample in SAMPLES:
        selected = long.copy()
        if sample == "exact_two_call_19":
            selected = selected[[
                _target_key(ticker, fp) in exact_keys
                for ticker, fp in zip(selected["ticker"], selected["fp"])
            ]]
        counts = selected.groupby(["ticker", "fp", "variant"])["seed"].nunique()
        if not counts.eq(expected_reps).all():
            raise RuntimeError(
                f"Table 1 tool-use {sample} requires {expected_reps} repetitions per setting"
            )
        target_settings = selected.groupby(["ticker", "fp"])["variant"].nunique()
        if not target_settings.eq(len(TOOL_SETTINGS)).all():
            raise RuntimeError(f"Table 1 tool-use settings do not share rows in {sample}")
        truth_spread = selected.groupby(["ticker", "fp"])["true_pct"].std().fillna(0.0)
        if (truth_spread > 1e-12).any():
            raise RuntimeError(f"Table 1 tool-use truth differs across runs in {sample}")

        truth = (
            selected.groupby(["ticker", "fp"], as_index=False)["true_pct"]
            .first()
        )
        means = (
            selected.groupby(["ticker", "fp", "variant"])["prediction"]
            .mean()
            .unstack("variant")
            .reset_index()
        )
        averaged = truth.merge(means, on=["ticker", "fp"], validate="one_to_one")
        averaged["sample"] = sample
        outputs.append(averaged)

    result = pd.concat(outputs, ignore_index=True)
    sample_sizes = result.groupby("sample").size().to_dict()
    if sample_sizes != {"exact_two_call_19": 19, "full_21": 21}:
        raise RuntimeError(f"unexpected Table 1 tool-use sample sizes: {sample_sizes}")
    return result


def evaluate_tool_use(
    records: list[dict],
    exact_reference: pd.DataFrame,
    expected_reps: int,
) -> dict:
    point_predictions = average_tool_settings(records, exact_reference, expected_reps)
    bootstrap = company_cluster_bootstrap(point_predictions, methods=TOOL_SETTINGS)
    summary = summarize(point_predictions, bootstrap, methods=TOOL_SETTINGS)
    audit = {
        "analysis": "Kalshi Revenue-YoY tool-use error bars",
        "new_llm_calls": 0,
        "headline_arm": "H+X+Z",
        "settings": {
            "BASE": "no tools",
            "TOOL": "company and alternative-data description tools enabled",
        },
        "samples": {
            sample: {
                "rows": int(
                    point_predictions[point_predictions["sample"].eq(sample)].shape[0]
                ),
                "firms": int(
                    point_predictions.loc[
                        point_predictions["sample"].eq(sample), "ticker"
                    ].nunique()
                ),
            }
            for sample in SAMPLES
        },
        "metrics": {
            "fvu": "SSE / SST = 1 - OOS R-squared",
            "mae": "mean absolute error in Revenue-YoY percentage points",
            "reported_uncertainty": (
                "full-sample point estimate plus or minus company-clustered bootstrap SD"
            ),
        },
        "llm_repetitions": {
            "count": expected_reps,
            "aggregation": "arithmetic mean by target and setting before evaluation",
        },
        "bootstrap": {
            "repetitions": BOOTSTRAP_REPS,
            "seed_full": BOOTSTRAP_SEED,
            "seed_exact_two_call": BOOTSTRAP_SEED + 1,
            "cluster": "ticker",
        },
    }
    return {
        "point_predictions": point_predictions,
        "bootstrap": bootstrap,
        "summary": summary,
        "audit": audit,
    }


def write_table1_data(result: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    result["point_predictions"].to_csv(
        output_dir / "table1_predictions_ensemble_first.csv",
        index=False,
    )
    result["bootstrap"].to_csv(output_dir / "table1_company_bootstrap.csv", index=False)
    result["summary"].to_csv(output_dir / "table1_metrics_summary.csv", index=False)
    (output_dir / "table1_audit.json").write_text(
        json.dumps(result["audit"], indent=2, ensure_ascii=True) + "\n"
    )


def write_tool_use_data(result: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    result["point_predictions"].to_csv(
        output_dir / "table1_tool_predictions_ensemble_first.csv",
        index=False,
    )
    result["bootstrap"].to_csv(
        output_dir / "table1_tool_company_bootstrap.csv",
        index=False,
    )
    result["summary"].to_csv(output_dir / "table1_tool_metrics_summary.csv", index=False)
    (output_dir / "table1_tool_audit.json").write_text(
        json.dumps(result["audit"], indent=2, ensure_ascii=True) + "\n"
    )


def markdown_table(
    summary: pd.DataFrame,
    sample: str,
    first_column: str = "Sources",
) -> str:
    rows = summary[summary["sample"].eq(sample)]
    lines = [
        f"| {first_column} | FVU (lower is better) | MAE (pp, lower is better) |",
        "|---|---:|---:|",
    ]
    for row in rows.itertuples():
        lines.append(
            f"| {row.label} | {row.fvu:.3f} (+/- {row.fvu_bootstrap_sd:.3f}) | "
            f"{row.mae:.2f} (+/- {row.mae_bootstrap_sd:.2f}) |"
        )
    return "\n".join(lines)


def _latex_value(point: float, sd: float, digits: int, bold: bool) -> str:
    value = (
        f"{point:.{digits}f} "
        + r"{\footnotesize($\pm$"
        + f"{sd:.{digits}f}"
        + ")}"
    )
    return rf"\textbf{{{value}}}" if bold else value


def _latex_rows(
    summary: pd.DataFrame,
    sample: str,
    include_heading: bool = True,
    methods=ARMS,
) -> str:
    rows = summary[summary["sample"].eq(sample)].copy()
    best_fvu = float(rows["fvu"].min())
    best_mae = float(rows["mae"].min())
    body = []
    if include_heading:
        body.append(r"\multicolumn{3}{l}{\textit{Kalshi prediction markets}} \\")
    latex_labels = {arm: latex for arm, _, latex in methods}
    for row in rows.itertuples():
        fvu = _latex_value(
            row.fvu,
            row.fvu_bootstrap_sd,
            3,
            np.isclose(row.fvu, best_fvu),
        )
        mae = _latex_value(
            row.mae,
            row.mae_bootstrap_sd,
            2,
            np.isclose(row.mae, best_mae),
        )
        body.append(f"\\quad {latex_labels[row.model]} & {fvu} & {mae} \\\\")
    return "\n".join(body)


def _latex_table(
    summary: pd.DataFrame,
    sample: str,
    caption: str,
    label: str,
    methods=ARMS,
    first_column: str = "Sources",
) -> str:
    rows = summary[summary["sample"].eq(sample)]
    n = int(rows.iloc[0]["n"])
    firms = int(rows.iloc[0]["firms"])
    return (
        r"""\begin{table}[t]
\centering
\caption{\textbf{""" + caption + r"""}
FVU and MAE are full-sample point estimates; error bars are company-clustered bootstrap
standard deviations from 5,000 draws. Predictions are averaged across three independent runs
by target before resampling. The matched sample contains """ + str(n)
        + " company-quarters / " + str(firms) + r""" firms.}
\label{""" + label + r"""}
\setlength{\tabcolsep}{15pt}
\begin{tabular}{lcc}
\toprule
""" + first_column + r""" & FVU ($\downarrow$) & MAE ($\downarrow$) \\
\midrule
""" + _latex_rows(
            summary,
            sample,
            include_heading=False,
            methods=methods,
        ) + r"""
\bottomrule
\end{tabular}
\end{table}
"""
    )


def render_table1_latex(summary: pd.DataFrame, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "kalshi_ablation.tex").write_text(_latex_table(
        summary,
        "full_21",
        "Kalshi source ablation on Revenue-YoY prediction.",
        "tab:kalshi_ablation",
    ))
    (output_dir / "kalshi_ablation_exact_two_call.tex").write_text(_latex_table(
        summary,
        "exact_two_call_19",
        "Kalshi exact-two-call source-ablation sensitivity.",
        "tab:kalshi_ablation_exact_two_call",
    ))
    (output_dir / "kalshi_ablation_overleaf_rows.tex").write_text(
        "% Insert these rows into the paper's Table 1 tabular environment.\n"
        + _latex_rows(summary, "full_21")
        + "\n"
    )


def render_tool_use_latex(summary: pd.DataFrame, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "kalshi_tool_fvu_mae.tex").write_text(_latex_table(
        summary,
        "full_21",
        "Effect of tool use for the Kalshi channel on Revenue-YoY prediction.",
        "tab:kalshi_tool_fvu_mae",
        methods=TOOL_SETTINGS,
        first_column="Setting",
    ))
    (output_dir / "kalshi_tool_fvu_mae_exact_two_call.tex").write_text(_latex_table(
        summary,
        "exact_two_call_19",
        "Kalshi exact-two-call tool-use sensitivity.",
        "tab:kalshi_tool_fvu_mae_exact_two_call",
        methods=TOOL_SETTINGS,
        first_column="Setting",
    ))
    (output_dir / "kalshi_tool_fvu_mae_overleaf_rows.tex").write_text(
        "% Insert these rows into the paper's FVU/MAE tool-use table.\n"
        + _latex_rows(
            summary,
            "full_21",
            methods=TOOL_SETTINGS,
        )
        + "\n"
    )
