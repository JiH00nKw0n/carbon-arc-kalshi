#!/usr/bin/env python3
"""Validate the three-repetition Kalshi run and generate paper-ready artifacts.

All figures and tables are derived from prediction ``preds.csv`` and lossless ``calls.jsonl``
artifacts. The script refuses to write paper outputs when a target/arm call, parsed rationale,
confidence, predicted revenue, or screening-audit rationale is missing.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import prediction  # noqa: F401
from prediction.channels.specs import get_channel
from prediction.config.loader import load
from prediction.data.transcripts import TranscriptStore
from prediction.run.experiment import PanelCache, _Transcripts, _evaluate_cell, _select_strong
from prediction.run.grid import Cell
from prediction.targets.ytarget import get_y_target

CONFIG = ROOT / "prediction" / "configs" / "kalshi_paper.yaml"
AUTO = ROOT / "kalshi" / "outputs" / "auto"
PAPER = ROOT / "kalshi" / "paper"
FIGURES = PAPER / "figures"
TABLES = PAPER / "tables"
DATA = PAPER / "data"
REPORT = ROOT / "kalshi" / "PAPER_RESULTS.md"
ARMS = ("fin", "fin+x", "fin+text", "fin+x+text")
HEADLINE = "fin+x+text"
TARGET_LABELS = {
    "surprise_early": "Early-consensus revenue surprise",
    "surprise_print": "Latest-consensus revenue surprise",
    "rev_yoy": "Revenue YoY",
}
MODEL_LABELS = (
    ("fin", "H"),
    ("fin+x", "H+X"),
    ("fin+text", "H+Z"),
    ("fin+x+text", "H+X+Z"),
    ("N0", "N0"),
    ("N1", "N1"),
    ("N2", "N2"),
    ("N3", "N3"),
    ("N4", "N4"),
    ("N3b", "N3b"),
    ("N4b", "N4b"),
    ("N5", "N5"),
)
SYNERGY_QUANTITIES = ("r_fwt", "syn_corr", "skill_fwt", "syn_skill")

CARBON_ARC_ACCURACY = {
    "surprise_early": {
        "rmse": [("Card", 3.40, 3.08), ("Web", 2.86, 1.76), ("Foot", 2.83, 2.69)],
        "win": [("Card", 54.0), ("Web", 81.0), ("Foot", 59.0)],
    },
    "surprise_print": {
        "rmse": [("Card", 3.32, 2.90), ("Web", 2.54, 1.65), ("Foot", 2.06, 1.68)],
        "win": [("Card", 53.0), ("Web", 78.0), ("Foot", 64.0)],
    },
}


def cell_dir(cfg, seed: int, y: str, variant: str) -> Path:
    slug = f"kalshi.{y}.{variant}.{cfg.llm.model}.{cfg.llm.effort}.seed{seed}"
    return ROOT / cfg.output_dir / slug


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        raise RuntimeError(f"missing required log: {path}")
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def metric_map(result) -> dict[str, dict]:
    calibration = {row["model"]: row["calib_r2"] for row in result.calib}
    out = {}
    for row in result.metrics_table:
        item = dict(row)
        item["calib_r2"] = calibration.get(row["model"])
        out[row["model"]] = item
    return out


def validate_calls(calls: list[dict], preds: pd.DataFrame, seed: int, y: str, variant: str) -> None:
    y_target = get_y_target(y)
    expected = {(row.tkr, str(row.fp), arm) for row in preds.itertuples() for arm in ARMS}
    actual = {
        (call["ticker"], str(call["fiscal_period_end"]), call["arm"])
        for call in calls if call.get("status") == "ok"
    }
    if actual != expected or len(calls) != len(expected):
        raise RuntimeError(
            f"incomplete call log seed={seed} {y}/{variant}: "
            f"calls={len(calls)} expected={len(expected)} "
            f"missing={sorted(expected - actual)} extra={sorted(actual - expected)}"
        )
    for call in calls:
        if call.get("seed") != seed or call.get("target") != y or call.get("variant") != variant:
            raise RuntimeError(f"call log identity mismatch: {call}")
        if call.get("prompt_protocol") != "paper":
            raise RuntimeError(f"non-paper prompt protocol in {seed} {y}/{variant}")
        if call.get("system_prompt") != y_target.paper_system_prompt:
            raise RuntimeError(f"system prompt differs from paper protocol in {seed} {y}/{variant}")
        parsed = call.get("parsed_output") or {}
        missing = [
            field for field in ("predicted_revenue_musd", "confidence", "rationale")
            if parsed.get(field) in (None, "")
        ]
        if missing:
            raise RuntimeError(
                f"call log lacks {missing}: seed={seed} {y}/{variant} "
                f"{call.get('ticker')} {call.get('fiscal_period_end')} {call.get('arm')}"
            )
        if not call.get("user_prompt") or not call.get("prompt_sha256"):
            raise RuntimeError("call log lacks exact prompt text or hash")
        prompt = call["user_prompt"]
        if hashlib.sha256(prompt.encode("utf-8")).hexdigest() != call["prompt_sha256"]:
            raise RuntimeError("call log prompt hash does not match prompt text")
        surprise_header = (
            "| quarter | revenue ($M) | revenue YoY | consensus ($M) | surprise % |"
        )
        yoy_header = "| quarter | revenue ($M) | revenue YoY |"
        if y == "rev_yoy":
            if yoy_header not in prompt or surprise_header in prompt:
                raise RuntimeError("paper revenue-YoY timeline columns are not preserved")
        elif surprise_header not in prompt:
            raise RuntimeError("paper revenue-surprise timeline columns are not preserved")


def validate_variant_prompt_identity(records: list[dict]) -> None:
    prompts: dict[tuple, dict[str, str]] = {}
    for record in records:
        for call in record["calls"]:
            key = (
                record["seed"], record["y"], call["ticker"],
                str(call["fiscal_period_end"]), call["arm"],
            )
            prompts.setdefault(key, {})[record["variant"]] = call["user_prompt"]
    for key, variants in prompts.items():
        if set(variants) != {"BASE", "TOOL"}:
            raise RuntimeError(f"missing BASE/TOOL prompt pair: {key}")
        if variants["BASE"] != variants["TOOL"]:
            raise RuntimeError(f"BASE/TOOL user prompts differ: {key}")


def validate_screen_logs(screen: pd.DataFrame) -> list[dict]:
    logs = read_jsonl(AUTO / "kalshi_kpi_firm_screen_calls.jsonl")
    audit = [record for record in logs if record.get("stage") == "auditor"]
    if not audit:
        raise RuntimeError("screening log has no high-effort auditor records")
    logged = {}
    for record in audit:
        for row in record["parsed_output"]["verdicts"]:
            logged[(row["ticker"], row["metric_label"])] = row
    expected = set(zip(screen["ticker"], screen["metric_label"]))
    if set(logged) != expected:
        raise RuntimeError(
            f"screening audit/final CSV mismatch: missing={sorted(expected - set(logged))} "
            f"extra={sorted(set(logged) - expected)}"
        )
    for row in screen.itertuples():
        record = logged[(row.ticker, row.metric_label)]
        if not str(record.get("reason", "")).strip():
            raise RuntimeError(f"screening rationale missing for {row.ticker}/{row.metric_label}")
    return logs


def load_run():
    cfg = load(str(CONFIG))
    seeds = [cfg.seed + offset for offset in range(cfg.run.reps)]
    manifest = pd.read_csv(ROOT / cfg.output_dir / "evaluation_manifest.csv")
    target_sets = [
        set(zip(group["ticker"], group["FE_FP_END"].astype(str)))
        for _, group in manifest.groupby("y")
    ]
    if len(target_sets) != len(cfg.grid.targets) or any(s != target_sets[0] for s in target_sets[1:]):
        raise RuntimeError("the three Y definitions do not share one evaluation row set")

    channel = get_channel("kalshi")
    panel = _select_strong(
        PanelCache(cfg.data.panel_out, cfg.data.screen_csv).get_or_build(channel),
        cfg.run,
    )
    transcripts = _Transcripts(
        TranscriptStore(channel, cfg.run.max_transcript_chars),
        cfg.run.max_transcript_chars,
    )
    records = []
    metric_rows = []
    all_calls = []
    for seed in seeds:
        for y in cfg.grid.targets:
            for variant in cfg.grid.variants:
                directory = cell_dir(cfg, seed, y, variant)
                preds_path = directory / "preds.csv"
                if not preds_path.exists():
                    raise RuntimeError(f"missing predictions: {preds_path}")
                preds = pd.read_csv(preds_path)
                calls = read_jsonl(directory / "calls.jsonl")
                validate_calls(calls, preds, seed, y, variant)
                expected = set(zip(
                    manifest.loc[manifest["y"].eq(y), "ticker"],
                    manifest.loc[manifest["y"].eq(y), "FE_FP_END"].astype(str),
                ))
                actual = set(zip(preds["tkr"], preds["fp"].astype(str)))
                if actual != expected:
                    raise RuntimeError(f"prediction/manifest mismatch seed={seed} {y}/{variant}")
                cell = Cell(channel="kalshi", y=y, variant=variant)
                context = SimpleNamespace(
                    transcripts=transcripts,
                    y_target=get_y_target(y),
                    channel=channel,
                )
                result = _evaluate_cell(cfg, cell, panel, preds, context, seed)
                metrics = metric_map(result)
                record = {
                    "seed": seed,
                    "y": y,
                    "variant": variant,
                    "preds": preds,
                    "calls": calls,
                    "context": context,
                    "result": result,
                    "metrics": metrics,
                }
                records.append(record)
                all_calls.extend(calls)
                for model, values in metrics.items():
                    metric_rows.append({
                        "seed": seed,
                        "y": y,
                        "variant": variant,
                        "model": model,
                        "available": values.get("available", True),
                        "rmse": values.get("rmse"),
                        "r2": values.get("r2"),
                        "calib_r2": values.get("calib_r2"),
                        "corr": values.get("corr"),
                        "mae": values.get("mae"),
                        "sign": values.get("sign"),
                    })
    validate_variant_prompt_identity(records)
    return cfg, seeds, manifest, panel, records, pd.DataFrame(metric_rows), all_calls


def exact_two_call_manifest(manifest: pd.DataFrame) -> pd.DataFrame:
    """Return one matched target set whose Z input contains exactly two calls."""
    if "earnings_call_count" not in manifest:
        raise RuntimeError("evaluation manifest lacks earnings_call_count")
    selected = manifest[manifest["earnings_call_count"].eq(2)].copy()
    target_sets = [
        set(zip(group["ticker"], group["FE_FP_END"].astype(str)))
        for _, group in selected.groupby("y")
    ]
    if len(target_sets) != len(TARGET_LABELS) or any(
        targets != target_sets[0] for targets in target_sets[1:]
    ):
        raise RuntimeError("exact-two-call sensitivity does not have matched Y target sets")
    if not target_sets or not target_sets[0]:
        raise RuntimeError("exact-two-call sensitivity has no eligible targets")
    return selected.sort_values(["y", "ticker", "FE_FP_END"]).reset_index(drop=True)


def reevaluate_exact_two_call(cfg, manifest: pd.DataFrame, panel: pd.DataFrame,
                              records: list[dict]) -> tuple[pd.DataFrame, list[dict],
                                                            pd.DataFrame]:
    """Re-evaluate existing predictions after applying the same two-call row filter to every arm."""
    selected = exact_two_call_manifest(manifest)
    keys_by_y = {
        y: set(zip(group["ticker"], group["FE_FP_END"].astype(str)))
        for y, group in selected.groupby("y")
    }
    sensitivity_records = []
    metric_rows = []
    for record in records:
        expected = keys_by_y[record["y"]]
        preds = record["preds"].copy()
        keys = list(zip(preds["tkr"], preds["fp"].astype(str)))
        preds = preds[[key in expected for key in keys]].reset_index(drop=True)
        actual = set(zip(preds["tkr"], preds["fp"].astype(str)))
        if actual != expected or len(preds) != len(expected):
            raise RuntimeError(
                "exact-two-call prediction/manifest mismatch "
                f"seed={record['seed']} {record['y']}/{record['variant']}"
            )
        filtered_calls = [
            call for call in record["calls"]
            if (call["ticker"], str(call["fiscal_period_end"])) in expected
        ]
        result = _evaluate_cell(
            cfg,
            Cell(channel="kalshi", y=record["y"], variant=record["variant"]),
            panel,
            preds,
            record["context"],
            record["seed"],
        )
        metrics = metric_map(result)
        sensitivity_record = {
            "seed": record["seed"],
            "y": record["y"],
            "variant": record["variant"],
            "preds": preds,
            "calls": filtered_calls,
            "context": record["context"],
            "result": result,
            "metrics": metrics,
        }
        sensitivity_records.append(sensitivity_record)
        for model, values in metrics.items():
            metric_rows.append({
                "seed": record["seed"],
                "y": record["y"],
                "variant": record["variant"],
                "model": model,
                "available": values.get("available", True),
                "rmse": values.get("rmse"),
                "r2": values.get("r2"),
                "calib_r2": values.get("calib_r2"),
                "corr": values.get("corr"),
                "mae": values.get("mae"),
                "sign": values.get("sign"),
            })
    return selected, sensitivity_records, pd.DataFrame(metric_rows)


def aggregate_metrics(metric_rows: pd.DataFrame) -> pd.DataFrame:
    available = metric_rows[metric_rows["available"].ne(False)].copy()
    numeric = ["rmse", "r2", "calib_r2", "corr", "mae", "sign"]
    return (
        available.groupby(["y", "variant", "model"], as_index=False)[numeric]
        .mean()
        .sort_values(["y", "variant", "model"])
    )


def accuracy(records: list[dict]) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    for record in records:
        if record["variant"] != "TOOL" or record["y"] not in {"surprise_early", "surprise_print"}:
            continue
        preds = record["preds"]
        truth = preds["true"].to_numpy(float) * 100.0
        model = preds[HEADLINE].to_numpy(float)
        rows.append({
            "seed": record["seed"],
            "target": record["y"],
            "n": len(preds),
            "analyst_rmse": float(np.sqrt(np.mean(truth ** 2))),
            "method_rmse": float(np.sqrt(np.mean((model - truth) ** 2))),
            "analyst_mae": float(np.mean(np.abs(truth))),
            "method_mae": float(np.mean(np.abs(model - truth))),
            "method_wins": int((np.abs(model - truth) < np.abs(truth)).sum()),
            "win_rate_pct": float(np.mean(np.abs(model - truth) < np.abs(truth)) * 100.0),
        })
    per_rep = pd.DataFrame(rows).sort_values(["target", "seed"])
    mean = (
        per_rep.groupby("target", as_index=False)
        .agg(
            n=("n", "first"),
            analyst_rmse=("analyst_rmse", "mean"),
            method_rmse=("method_rmse", "mean"),
            analyst_mae=("analyst_mae", "mean"),
            method_mae=("method_mae", "mean"),
            win_rate_pct=("win_rate_pct", "mean"),
        )
    )
    return per_rep, mean


def call_index(records: list[dict]) -> dict[tuple, dict]:
    index = {}
    for record in records:
        for call in record["calls"]:
            key = (
                record["seed"], record["y"], record["variant"],
                call["ticker"], str(call["fiscal_period_end"]), call["arm"],
            )
            index[key] = call
    return index


def qualitative_cases(records: list[dict], panel: pd.DataFrame) -> list[dict]:
    tool = [
        record for record in records
        if record["variant"] == "TOOL" and record["y"] in {"surprise_early", "surprise_print"}
    ]
    rows = []
    for record in tool:
        frame = record["preds"].copy(deep=True)
        frame = frame.assign(
            seed=record["seed"],
            y=record["y"],
            true_pp=frame["true"] * 100.0,
        )
        frame = frame.assign(
            gain=(
                (frame["fin+text"] - frame["true_pp"]).abs()
                - (frame["fin+x+text"] - frame["true_pp"]).abs()
            )
        )
        rows.append(frame[["seed", "y", "tkr", "fp", "true_pp", "fin+text",
                           "fin+x+text", "gain"]])
    frame = pd.concat(rows, ignore_index=True)
    grouped = (
        frame.groupby(["y", "tkr", "fp"], as_index=False)
        .agg(
            true_pp=("true_pp", "first"),
            without_x=("fin+text", "mean"),
            with_x=("fin+x+text", "mean"),
            gain=("gain", "mean"),
        )
    )
    early = grouped[grouped["y"].eq("surprise_early")].sort_values("gain", ascending=False).iloc[0]
    print_candidates = grouped[
        grouped["y"].eq("surprise_print") & grouped["tkr"].ne(early.tkr)
    ].sort_values("gain", ascending=False)
    latest = (
        print_candidates.iloc[0]
        if len(print_candidates)
        else grouped[grouped["y"].eq("surprise_print")].sort_values("gain", ascending=False).iloc[0]
    )

    index = call_index(records)
    selected = []
    for summary in (early, latest):
        reps = frame[
            frame["y"].eq(summary.y)
            & frame["tkr"].eq(summary.tkr)
            & frame["fp"].astype(str).eq(str(summary.fp))
        ].copy()
        reps = reps.assign(
            center_distance=(
                (reps["fin+text"] - summary.without_x).abs()
                + (reps["fin+x+text"] - summary.with_x).abs()
            )
        )
        representative = reps.sort_values(["center_distance", "seed"]).iloc[0]
        key_base = (
            int(representative.seed), summary.y, "TOOL",
            summary.tkr, str(summary.fp),
        )
        with_x_call = index[key_base + ("fin+x+text",)]
        without_x_call = index[key_base + ("fin+text",)]
        panel_row = panel[
            panel["ticker"].eq(summary.tkr)
            & panel["FE_FP_END"].astype(str).eq(str(summary.fp))
        ].iloc[0]
        anchor_col = "CONS_EARLY" if summary.y == "surprise_early" else "CONS_PRINT"
        ladders = json.loads(panel_row["x_payload"])
        selected.append({
            "target": summary.y,
            "ticker": summary.tkr,
            "fiscal_period_end": str(summary.fp),
            "representative_seed": int(representative.seed),
            "selection_rule": (
                "largest mean three-repetition reduction in absolute H+Z error after adding X; "
                "latest-consensus case excludes the early-case ticker when possible"
            ),
            "mean_error_reduction_pp": float(summary.gain),
            "actual_revenue_musd": float(panel_row["ACTUAL"]),
            "anchor_revenue_musd": float(panel_row[anchor_col]),
            "prior_year_revenue_musd": float(panel_row["prior_year_actual"]),
            "actual_surprise_pct": float(panel_row[summary.y] * 100.0),
            "model_revenue_musd": float(
                with_x_call["parsed_output"]["predicted_revenue_musd"]
            ),
            "model_surprise_pct": float(with_x_call["derived_prediction_pct"]),
            "without_x_revenue_musd": float(
                without_x_call["parsed_output"]["predicted_revenue_musd"]
            ),
            "without_x_surprise_pct": float(without_x_call["derived_prediction_pct"]),
            "rationale": with_x_call["parsed_output"]["rationale"],
            "without_x_rationale": without_x_call["parsed_output"]["rationale"],
            "prompt_sha256": with_x_call["prompt_sha256"],
            "metric_label": ladders[0].get("metric_label", "company KPI"),
            "ladder_summary": ladder_summary(ladders[0]),
        })
    return selected


def ladder_summary(ladder: dict) -> str:
    rungs = ladder.get("rungs") or []
    if not rungs:
        return "No priced rungs"
    closest = sorted(rungs, key=lambda row: abs(float(row.get("probability", 0.0)) - 0.5))[:2]
    closest = sorted(closest, key=lambda row: float(row.get("strike", 0.0)))
    parts = []
    for rung in closest:
        condition = str(rung.get("yes_contract") or f"above {rung.get('strike')}")
        parts.append(f"{condition}: {100 * float(rung.get('probability', 0.0)):.0f}%")
    return "; ".join(parts)


def screen_examples(screen: pd.DataFrame, events: pd.DataFrame) -> list[dict]:
    preferred = [
        ("TSLA", "how many tesla deliveries will there be this quarter"),
        ("TSLA", "tesla production"),
        ("NFLX", "netflix subscribers"),
        ("NFLX", "netflix subscribers gain"),
    ]
    keyed = screen.set_index(["ticker", "metric_label"], drop=False)
    if not all(pair in keyed.index for pair in preferred):
        mixed = [
            ticker for ticker, group in screen.groupby("ticker")
            if set(group["impact"]) == {"O", "X"}
        ]
        if len(mixed) < 2:
            raise RuntimeError("screen figure needs two firms with both O and X KPI decisions")
        preferred = []
        for ticker in mixed[:2]:
            group = screen[screen["ticker"].eq(ticker)]
            preferred.extend([
                (ticker, group[group["impact"].eq("O")].iloc[0]["metric_label"]),
                (ticker, group[group["impact"].eq("X")].iloc[0]["metric_label"]),
            ])
    names = (
        events[["ticker", "stock_name"]].dropna().drop_duplicates("ticker")
        .set_index("ticker")["stock_name"].to_dict()
    )
    return [
        {
            **keyed.loc[pair].to_dict(),
            "company_name": names.get(pair[0], pair[0]),
        }
        for pair in preferred
    ]


def summarize(values) -> dict:
    sample = np.asarray(values, float)
    lo, hi = np.percentile(sample, [2.5, 97.5])
    return {
        "mean": float(sample.mean()),
        "ci_low": float(lo),
        "ci_high": float(hi),
        "p_le_zero": float((sample <= 0).mean()),
    }


def evaluation_statistics(records: list[dict]) -> tuple[dict, pd.DataFrame, pd.DataFrame,
                                                        pd.DataFrame]:
    """Summarize every Y/variant cell without discarding the three run-level results."""
    grouped: dict[tuple[str, str], list[dict]] = {}
    per_rep_rows = []
    surrogate_rows = []
    for record in records:
        key = (record["y"], record["variant"])
        grouped.setdefault(key, []).append(record)
        surrogate_rows.append({
            "seed": record["seed"],
            "y": record["y"],
            "variant": record["variant"],
            "surrogate_p": record["result"].surrogate,
        })
        for quantity in SYNERGY_QUANTITIES:
            per_rep_rows.append({
                "seed": record["seed"],
                "y": record["y"],
                "variant": record["variant"],
                "quantity": quantity,
                **summarize(record["result"].synergy[quantity]),
            })

    by_cell = {}
    pooled_rows = []
    for key, cell_records in grouped.items():
        by_cell[key] = {}
        for quantity in SYNERGY_QUANTITIES:
            summary = summarize(np.concatenate([
                record["result"].synergy[quantity] for record in cell_records
            ]))
            by_cell[key][quantity] = summary
            pooled_rows.append({
                "y": key[0],
                "variant": key[1],
                "quantity": quantity,
                **summary,
            })

    return (
        by_cell,
        pd.DataFrame(per_rep_rows).sort_values(["y", "variant", "seed", "quantity"]),
        pd.DataFrame(pooled_rows).sort_values(["y", "variant", "quantity"]),
        pd.DataFrame(surrogate_rows).sort_values(["y", "variant", "seed"]),
    )


def nested_synergy(by_cell: dict) -> dict:
    return {
        y: {
            variant: by_cell[(y, variant)]
            for variant in ("BASE", "TOOL")
        }
        for y in TARGET_LABELS
    }


def write_data(cfg, seeds, manifest, metrics, accuracy_rep, accuracy_mean,
               cases, screens, calls, screen_logs, synergy_by_cell,
               synergy_by_rep, synergy_pooled, surrogate_by_rep):
    DATA.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(DATA / "metrics_by_rep.csv", index=False)
    aggregate_metrics(metrics).to_csv(DATA / "metrics_mean.csv", index=False)
    accuracy_rep.to_csv(DATA / "accuracy_by_rep.csv", index=False)
    accuracy_mean.to_csv(DATA / "accuracy_mean.csv", index=False)
    synergy_by_rep.to_csv(DATA / "synergy_by_rep.csv", index=False)
    synergy_pooled.to_csv(DATA / "synergy_pooled.csv", index=False)
    surrogate_by_rep.to_csv(DATA / "surrogate_by_rep.csv", index=False)
    manifest.to_csv(DATA / "evaluation_manifest.csv", index=False)
    (DATA / "qualitative_cases.json").write_text(
        json.dumps(cases, indent=2, ensure_ascii=True) + "\n"
    )
    (DATA / "screen_examples.json").write_text(
        json.dumps(screens, indent=2, ensure_ascii=True) + "\n"
    )
    audit = {
        "config": str(CONFIG.relative_to(ROOT)),
        "output_dir": cfg.output_dir,
        "seeds": seeds,
        "prediction_call_count": len(calls),
        "prediction_rationale_count": sum(
            bool((call.get("parsed_output") or {}).get("rationale")) for call in calls
        ),
        "screen_call_count": len(screen_logs),
        "total_cost_usd": float(sum(float(call.get("cost_usd", 0.0)) for call in calls)),
        "synergy": nested_synergy(synergy_by_cell),
    }
    (DATA / "run_audit.json").write_text(json.dumps(audit, indent=2) + "\n")


def write_exact_two_call_data(full_manifest: pd.DataFrame, manifest: pd.DataFrame,
                              records: list[dict], metrics: pd.DataFrame,
                              accuracy_rep: pd.DataFrame, accuracy_mean: pd.DataFrame,
                              synergy_by_cell: dict, synergy_by_rep: pd.DataFrame,
                              synergy_pooled: pd.DataFrame,
                              surrogate_by_rep: pd.DataFrame) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    prefix = "exact_two_call"
    metrics.to_csv(DATA / f"{prefix}_metrics_by_rep.csv", index=False)
    aggregate_metrics(metrics).to_csv(DATA / f"{prefix}_metrics_mean.csv", index=False)
    accuracy_rep.to_csv(DATA / f"{prefix}_accuracy_by_rep.csv", index=False)
    accuracy_mean.to_csv(DATA / f"{prefix}_accuracy_mean.csv", index=False)
    synergy_by_rep.to_csv(DATA / f"{prefix}_synergy_by_rep.csv", index=False)
    synergy_pooled.to_csv(DATA / f"{prefix}_synergy_pooled.csv", index=False)
    surrogate_by_rep.to_csv(DATA / f"{prefix}_surrogate_by_rep.csv", index=False)
    manifest.to_csv(DATA / f"{prefix}_evaluation_manifest.csv", index=False)

    reference_y = next(iter(TARGET_LABELS))
    full = full_manifest[full_manifest["y"].eq(reference_y)]
    kept = manifest[manifest["y"].eq(reference_y)]
    kept_keys = set(zip(kept["ticker"], kept["FE_FP_END"].astype(str)))
    excluded = [
        {
            "ticker": row.ticker,
            "FE_FP_END": str(row.FE_FP_END),
            "earnings_call_count": int(row.earnings_call_count),
        }
        for row in full.itertuples()
        if (row.ticker, str(row.FE_FP_END)) not in kept_keys
    ]
    audit = {
        "analysis": "exact-two-call coverage sensitivity",
        "selection_rule": "earnings_call_count == 2 after the 31-day embargo",
        "interpretation": (
            "Matched-sample coverage sensitivity; not a causal comparison of one-call "
            "versus two-call Z depth."
        ),
        "new_llm_calls": 0,
        "existing_arm_predictions_reused": int(sum(
            len(record["preds"]) * len(ARMS) for record in records
        )),
        "target_rows_per_y": int(len(kept)),
        "firms": int(kept["ticker"].nunique()),
        "excluded_targets": excluded,
        "row_matching": "The same target rows are used by every arm, variant, Y, and repetition.",
        "synergy": nested_synergy(synergy_by_cell),
    }
    (DATA / f"{prefix}_audit.json").write_text(json.dumps(audit, indent=2) + "\n")


def render_accuracy(accuracy_mean: pd.DataFrame) -> None:
    data = {}
    for target, key in (("surprise_early", "early"), ("surprise_print", "print")):
        row = accuracy_mean[accuracy_mean["target"].eq(target)].iloc[0]
        rmse = [
            {"ch": ch, "analyst": analyst, "llm": method}
            for ch, analyst, method in CARBON_ARC_ACCURACY[target]["rmse"]
        ]
        rmse.append({
            "ch": "Kalshi",
            "analyst": round(float(row.analyst_rmse), 3),
            "llm": round(float(row.method_rmse), 3),
        })
        win = [{"ch": ch, "v": value} for ch, value in CARBON_ARC_ACCURACY[target]["win"]]
        win.append({"ch": "Kalshi", "v": round(float(row.win_rate_pct), 1)})
        data[key] = {"rmse": rmse, "win": win}
    payload = json.dumps(data, separators=(",", ":"))
    document = """<!doctype html><html><head><meta charset="utf-8"><title>Revenue-surprise accuracy</title>
<style>
html,body{margin:0;padding:0;background:#fff}.fig{--ink:#1c1b19;--muted:#736c60;--blue:#29b9f2;
--gray:#737373;--line:#e4ded4;--grid:#efeae1;max-width:760px;margin:0 auto;padding:18px 16px 20px;
font-family:"DejaVu Serif",Georgia,"Times New Roman",serif;color:var(--ink)}*{box-sizing:border-box}
.legend{display:flex;gap:22px;justify-content:center;font-size:14px;margin-bottom:16px}.key{display:flex;
align-items:center;gap:7px}.swatch{width:13px;height:13px;border-radius:2px}.unit{margin-bottom:9px}
.rowlab{font-size:15px;font-weight:700;margin:3px 3px 2px}.panels{display:flex;gap:16px}
.panels svg{width:100%;height:auto}.fig svg text{font-family:inherit}.ptitle{fill:var(--ink);font-size:14px}
.tick{fill:var(--muted);font-size:11px}.vlab{fill:var(--ink);font-size:10.5px;font-weight:700}
.xlab{fill:var(--ink);font-size:12px}.reflab{fill:var(--muted);font-size:10px}.grid{stroke:var(--grid)}
.axis{stroke:var(--line);stroke-width:1.2}.ref{stroke:var(--muted);stroke-dasharray:4 3}
.analyst{fill:var(--gray)}.method{fill:var(--blue)}
</style></head><body><figure class="fig">
<div class="legend"><span class="key"><span class="swatch" style="background:var(--gray)"></span>Analyst consensus</span>
<span class="key"><span class="swatch" style="background:var(--blue)"></span>Our method</span></div>
<div class="unit"><div class="rowlab">Revenue surprise - Our method vs. early consensus</div><div class="panels" id="early"></div></div>
<div class="unit"><div class="rowlab">Revenue surprise - Our method vs. latest consensus</div><div class="panels" id="print"></div></div>
</figure><script>
const DATA=__DATA__;const W=350,H=250,mL=36,mR=10,mT=28,mB=34,pw=W-mL-mR,ph=H-mT-mB,y0=H-mB;
function rmsePanel(rows){const yMax=5,yS=v=>mT+ph-(v/yMax)*ph;let s=`<svg viewBox="0 0 ${W} ${H}">`;
s+=`<text class="ptitle" x="${mL}" y="16">RMSE (% of revenue)</text>`;for(let t=0;t<=yMax;t++){const y=yS(t);
s+=`<line class="grid" x1="${mL}" y1="${y}" x2="${W-mR}" y2="${y}"/><text class="tick" x="${mL-5}" y="${y+3.5}" text-anchor="end">${t}</text>`}
const gw=pw/rows.length,bw=22,gap=5;rows.forEach((d,i)=>{const gx=mL+i*gw+gw/2,ax=gx-bw-gap/2,lx=gx+gap/2,ay=yS(d.analyst),ly=yS(d.llm);
s+=`<rect class="analyst" x="${ax}" y="${ay}" width="${bw}" height="${y0-ay}"/><text class="vlab" x="${ax+bw/2}" y="${ay-4}" text-anchor="middle">${d.analyst.toFixed(2)}</text>`;
s+=`<rect class="method" x="${lx}" y="${ly}" width="${bw}" height="${y0-ly}"/><text class="vlab" x="${lx+bw/2}" y="${ly-4}" text-anchor="middle">${d.llm.toFixed(2)}</text><text class="xlab" x="${gx}" y="${y0+17}" text-anchor="middle">${d.ch}</text>`});
return s+`<line class="axis" x1="${mL}" y1="${y0}" x2="${W-mR}" y2="${y0}"/></svg>`}
function winPanel(rows){const yS=v=>mT+ph-(v/100)*ph;let s=`<svg viewBox="0 0 ${W} ${H}"><text class="ptitle" x="${mL}" y="16">Win rate (%)</text>`;
[0,25,50,75,100].forEach(t=>{const y=yS(t);s+=`<line class="grid" x1="${mL}" y1="${y}" x2="${W-mR}" y2="${y}"/><text class="tick" x="${mL-5}" y="${y+3.5}" text-anchor="end">${t}</text>`});
const gw=pw/rows.length,bw=34;rows.forEach((d,i)=>{const gx=mL+i*gw+gw/2,y=yS(d.v);s+=`<rect class="method" x="${gx-bw/2}" y="${y}" width="${bw}" height="${y0-y}"/><text class="vlab" x="${gx}" y="${y-4}" text-anchor="middle">${d.v.toFixed(d.v%1?1:0)}%</text><text class="xlab" x="${gx}" y="${y0+17}" text-anchor="middle">${d.ch}</text>`});
const y50=yS(50);return s+`<line class="ref" x1="${mL}" y1="${y50}" x2="${W-mR}" y2="${y50}"/><text class="reflab" x="${W-mR}" y="${y50-4}" text-anchor="end">50%</text><line class="axis" x1="${mL}" y1="${y0}" x2="${W-mR}" y2="${y0}"/></svg>`}
for(const key of ["early","print"]){document.getElementById(key).innerHTML=rmsePanel(DATA[key].rmse)+winPanel(DATA[key].win)}
</script></body></html>""".replace("__DATA__", payload)
    FIGURES.mkdir(parents=True, exist_ok=True)
    (FIGURES / "kalshi_accuracy_chart.html").write_text(document)


def highlight_rationale(text: str, metric_label: str) -> str:
    terms = {"kalshi", "probability", "market", "ladder"}
    terms.update(token for token in re.findall(r"[a-z]+", metric_label.lower()) if len(token) >= 5)
    sentences = re.split(r"(?<=[.!?])\s+", str(text).strip())
    rendered = []
    for sentence in sentences:
        escaped = html.escape(sentence)
        rendered.append(
            f"<mark>{escaped}</mark>"
            if any(term in sentence.lower() for term in terms)
            else escaped
        )
    return " ".join(rendered)


def money(value: float) -> str:
    return f"${value:,.0f}M"


def signed(value: float) -> str:
    return f"{value:+.1f}%".replace("-", "&minus;")


def render_qualitative(cases: list[dict]) -> None:
    rows = []
    for case in cases:
        consensus = "early" if case["target"] == "surprise_early" else "latest"
        rows.append(f"""<div class="case"><div class="tbl">
<p class="co">{html.escape(case['ticker'])}</p>
<p class="meta">Kalshi KPI - {consensus} consensus - representative seed {case['representative_seed']}</p>
<table>
<tr><td class="k">Actual revenue</td><td class="v">{money(case['actual_revenue_musd'])}<span class="pct">{signed(case['actual_surprise_pct'])}</span></td></tr>
<tr><td class="k">Consensus ({consensus})</td><td class="v">{money(case['anchor_revenue_musd'])}</td></tr>
<tr><td class="k">Prior-year revenue</td><td class="v">{money(case['prior_year_revenue_musd'])}</td></tr>
<tr class="est"><td class="k">Model estimate</td><td class="v">{money(case['model_revenue_musd'])}<span class="pct">{signed(case['model_surprise_pct'])}</span></td></tr>
<tr class="noalt"><td class="k">without Kalshi X</td><td class="v">{money(case['without_x_revenue_musd'])}<span class="pct">{signed(case['without_x_surprise_pct'])}</span></td></tr>
<tr class="sig"><td class="k">Kalshi ladder</td><td class="v small">{html.escape(case['ladder_summary'])}</td></tr>
</table></div><div class="rat"><p class="ratlab">Model rationale</p>
<p>{highlight_rationale(case['rationale'], case['metric_label'])}</p></div></div>""")
    document = """<!doctype html><html><head><meta charset="utf-8"><title>Kalshi qualitative examples</title>
<style>html,body{margin:0;background:#fff}.qfig{--ink:#1c1b19;--muted:#736c60;--blue:#29b9f2;
--tint:#dcf1fb;--gray:#737373;max-width:1058px;margin:8px auto;padding:6px 21px;font-family:"DejaVu Serif",
Georgia,"Times New Roman",serif;color:var(--ink);line-height:1.45}.qfig *{box-sizing:border-box}.case{display:flex;
gap:19px;align-items:stretch;padding:8px 0;border-top:1px solid var(--gray)}.case:last-child{border-bottom:1px solid var(--gray)}
.tbl{flex:0 0 330px;min-width:0}.co{margin:0;font-size:15px;font-weight:700}.meta{font-size:11px;
letter-spacing:.05em;text-transform:uppercase;margin:0 0 7px}.qfig table{width:100%;border-collapse:collapse;
font-variant-numeric:tabular-nums}.qfig td{padding:3px 2px;vertical-align:baseline}.k{color:var(--muted);
font-size:13px;padding-right:8px}.v{text-align:right;white-space:nowrap;font-size:14px}.pct{color:var(--muted);
font-size:11px;margin-left:5px}.est td{border-top:1px solid var(--gray);padding-top:6px}.est .k{color:var(--ink)}
.est .v,.est .pct{color:var(--blue);font-weight:700}.noalt td{color:var(--muted);font-size:11px}.noalt .k{padding-left:12px}
.sig td{padding-top:6px}.sig .v{font-weight:700}.v.small{white-space:normal;font-size:11px;line-height:1.25}
.rat{flex:1;border:1px solid var(--gray);padding:8px 14px}.ratlab{font-size:11px;letter-spacing:.11em;
text-transform:uppercase;margin:0 0 5px}.rat p:last-child{margin:0;font-size:13px;line-height:1.5}mark{background:var(--tint);
color:var(--ink);padding:1px 2px}@media(max-width:720px){.case{flex-direction:column}.tbl{flex-basis:auto}}</style>
</head><body><figure class="qfig">__ROWS__</figure></body></html>""".replace("__ROWS__", "\n".join(rows))
    (FIGURES / "kalshi_qualitative_figure.html").write_text(document)


def render_screen(examples: list[dict]) -> None:
    rows = []
    for example in examples:
        included = example["impact"] == "O"
        verdict = "Included (O)" if included else "Excluded (X)"
        marked = html.escape(str(example["reason"]))
        rows.append(f"""<div class="row"><div class="tbl">
<p class="co">{html.escape(str(example['company_name']))} <span>({html.escape(example['ticker'])})</span></p>
<p class="meta">Kalshi KPI - {html.escape(example['metric_label'])}</p>
<table><tr class="verdict {'o' if included else 'x'}"><td>Screen verdict</td><td>{verdict}</td></tr></table>
</div><div class="rat"><p class="ratlab">Screening rationale</p><p><mark class="{'o' if included else 'x'}">{marked}</mark></p></div></div>""")
    document = """<!doctype html><html><head><meta charset="utf-8"><title>Kalshi screening examples</title>
<style>html,body{margin:0;background:#fff}.sfig{--ink:#1c1b19;--muted:#736c60;--blue:#29b9f2;
--blue-tint:#dcf1fb;--gray:#737373;--gray-tint:#e7e3db;max-width:1058px;margin:8px auto;padding:6px 21px;
font-family:"DejaVu Serif",Georgia,"Times New Roman",serif;color:var(--ink);line-height:1.45}.sfig *{box-sizing:border-box}
.row{display:flex;gap:19px;align-items:stretch;padding:8px 0;border-top:1px solid var(--gray)}.row:last-child{border-bottom:1px solid var(--gray)}
.tbl{flex:0 0 330px;min-width:0}.co{margin:0;font-size:14px;font-weight:700}.co span{color:var(--muted);font-weight:400}
.meta{font-size:11px;letter-spacing:.05em;text-transform:uppercase;margin:0 0 7px;overflow-wrap:anywhere}.sfig table{width:100%;
border-collapse:collapse}.sfig td{border-top:1px solid var(--gray);padding:6px 2px 3px;font-size:13px}.sfig td:last-child{text-align:right;
font-size:15px;font-weight:700}.verdict.o td:last-child{color:var(--blue)}.verdict.x td:last-child{color:var(--muted)}
.rat{flex:1;border:1px solid var(--gray);padding:8px 14px}.ratlab{font-size:11px;letter-spacing:.11em;text-transform:uppercase;
margin:0 0 5px}.rat p:last-child{margin:0;font-size:13px;line-height:1.5}mark{color:var(--ink);padding:1px 2px}
mark.o{background:var(--blue-tint)}mark.x{background:var(--gray-tint)}@media(max-width:720px){.row{flex-direction:column}.tbl{flex-basis:auto}}</style>
</head><body><figure class="sfig">__ROWS__</figure></body></html>""".replace("__ROWS__", "\n".join(rows))
    (FIGURES / "kalshi_screen_figure.html").write_text(document)


def latex_escape(value: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
    }
    return "".join(replacements.get(char, char) for char in str(value))


def metric_lookup(mean_metrics: pd.DataFrame, y: str, variant: str, model: str) -> pd.Series:
    rows = mean_metrics[
        mean_metrics["y"].eq(y)
        & mean_metrics["variant"].eq(variant)
        & mean_metrics["model"].eq(model)
    ]
    if len(rows) != 1:
        raise RuntimeError(f"missing aggregate metric {y}/{variant}/{model}")
    return rows.iloc[0]


def metric_row(mean_metrics: pd.DataFrame, y: str, variant: str,
               model: str) -> pd.Series | None:
    rows = mean_metrics[
        mean_metrics["y"].eq(y)
        & mean_metrics["variant"].eq(variant)
        & mean_metrics["model"].eq(model)
    ]
    return None if rows.empty else rows.iloc[0]


def markdown_full_results(mean_metrics: pd.DataFrame, synergy_by_cell: dict,
                          surrogate_by_rep: pd.DataFrame) -> str:
    sections = []
    for y, title in TARGET_LABELS.items():
        for variant in ("BASE", "TOOL"):
            lines = [
                f"### {title} / {variant}",
                "",
                "| Model | RMSE | OOS R-squared | Calibrated R-squared | Correlation | MAE | Sign |",
                "|---|---:|---:|---:|---:|---:|---:|",
            ]
            for model, label in MODEL_LABELS:
                row = metric_row(mean_metrics, y, variant, model)
                if row is None:
                    values = "N/A | N/A | N/A | N/A | N/A | N/A"
                else:
                    calibrated = (
                        f"{row['calib_r2']:+.3f}"
                        if not pd.isna(row["calib_r2"]) else "-"
                    )
                    values = (
                        f"{row['rmse']:.3f} | {row['r2']:+.3f} | {calibrated} | "
                        f"{row['corr']:+.3f} | {row['mae']:.3f} | {row['sign']:.3f}"
                    )
                lines.append(f"| {label} | {values} |")

            h = metric_lookup(mean_metrics, y, variant, "fin")
            hx = metric_lookup(mean_metrics, y, variant, "fin+x")
            hz = metric_lookup(mean_metrics, y, variant, "fin+text")
            hxz = metric_lookup(mean_metrics, y, variant, "fin+x+text")
            stats = synergy_by_cell[(y, variant)]
            corr = stats["syn_corr"]
            skill = stats["syn_skill"]
            surrogate = surrogate_by_rep[
                surrogate_by_rep["y"].eq(y)
                & surrogate_by_rep["variant"].eq(variant)
            ].sort_values("seed")
            surrogate_text = ", ".join(
                f"{int(row.seed)}={row.surrogate_p:.4f}"
                for row in surrogate.itertuples()
            )
            lines.extend([
                "",
                f"- RMSE change from H after adding X: {hx['rmse'] - h['rmse']:+.3f} pp.",
                f"- RMSE change from H+Z after adding X: {hxz['rmse'] - hz['rmse']:+.3f} pp.",
                f"- Correlation synergy: {corr['mean']:+.3f}, "
                f"95% pooled-bootstrap CI [{corr['ci_low']:+.3f}, {corr['ci_high']:+.3f}], "
                f"`p(value <= 0)={corr['p_le_zero']:.3f}`.",
                f"- MSE-skill synergy: {skill['mean']:+.3f}, "
                f"95% pooled-bootstrap CI [{skill['ci_low']:+.3f}, {skill['ci_high']:+.3f}], "
                f"`p(value <= 0)={skill['p_le_zero']:.3f}`.",
                f"- Shuffle-company surrogate p-values by seed: {surrogate_text}.",
            ])
            sections.append("\n".join(lines))
    return "\n\n".join(sections)


def render_full_grid_latex(mean_metrics: pd.DataFrame,
                           filename: str = "kalshi_full_grid.tex",
                           caption_prefix: str = "Kalshi full-grid results",
                           label_prefix: str = "kalshi_full") -> None:
    arm_labels = {
        "fin": r"$H$",
        "fin+x": r"$H+X$",
        "fin+text": r"$H+Z$",
        "fin+x+text": r"$H+X+Z$",
    }
    tables = []
    for y, title in TARGET_LABELS.items():
        for variant in ("BASE", "TOOL"):
            rows = []
            for model, label in MODEL_LABELS:
                row = metric_row(mean_metrics, y, variant, model)
                latex_label = arm_labels.get(model, label)
                if row is None:
                    values = "N/A & N/A & N/A & N/A & N/A & N/A"
                else:
                    calibrated = (
                        f"{row['calib_r2']:.3f}"
                        if not pd.isna(row["calib_r2"]) else "-"
                    )
                    values = (
                        f"{row['rmse']:.3f} & {row['r2']:.3f} & {calibrated} & "
                        f"{row['corr']:.3f} & {row['mae']:.3f} & {row['sign']:.3f}"
                    )
                rows.append(f"{latex_label} & {values} \\\\")
            slug = f"{y}_{variant.lower()}"
            tables.append(r"""\begin{table*}[p]
\centering
\caption{\textbf{""" + caption_prefix + ": " + title + " / " + variant + r""".}
Point estimates average three independent runs.}
\label{tab:""" + label_prefix + "_" + slug + r"""}
\resizebox{\textwidth}{!}{%
\begin{tabular}{lrrrrrr}
\toprule
Model & RMSE & $R^2$ & $R^2$ (Calib.) & $\rho$ & MAE & Sign \\
\midrule
""" + "\n".join(rows) + r"""
\bottomrule
\end{tabular}}
\end{table*}
""")
    (TABLES / filename).write_text("\n".join(tables))


def render_exact_two_call_tables(mean_metrics: pd.DataFrame, synergy_by_cell: dict,
                                 target_rows: int) -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    rows = []
    for model, label in (
        ("fin", r"$H$"),
        ("fin+x", r"$H+X$"),
        ("fin+text", r"$H+Z$"),
        ("fin+x+text", r"$H+X+Z$"),
    ):
        row = metric_lookup(mean_metrics, "rev_yoy", "TOOL", model)
        rows.append(
            f"{label} & {row['rmse']:.3f} & {row['r2']:.3f} & "
            f"{row['calib_r2']:.3f} & {row['corr']:.3f} & {row['mae']:.3f} \\\\"
        )
    synergy = synergy_by_cell[("rev_yoy", "TOOL")]
    corr = synergy["syn_corr"]
    skill = synergy["syn_skill"]
    table = r"""\begin{table*}[t]
\centering
\caption{\textbf{Kalshi exact-two-call coverage sensitivity on revenue-YoY prediction.}
The matched sample contains """ + str(target_rows) + r""" company-quarters. Existing predictions
are re-evaluated after requiring exactly two eligible calls; no new LLM calls are made.}
\label{tab:kalshi_exact_two_call}
\begin{tabular}{lccccc}
\toprule
Sources & RMSE & $R^2$ & $R^2$ (Calib.) & $\rho$ & MAE \\
\midrule
""" + "\n".join(rows) + r"""
\midrule
Corr. synergy & \multicolumn{5}{c}{""" + (
        f"{corr['mean']:+.3f} [{corr['ci_low']:+.3f}, {corr['ci_high']:+.3f}]"
    ) + r"""} \\
MSE-skill synergy & \multicolumn{5}{c}{""" + (
        f"{skill['mean']:+.3f} [{skill['ci_low']:+.3f}, {skill['ci_high']:+.3f}]"
    ) + r"""} \\
\bottomrule
\end{tabular}
\end{table*}
"""
    (TABLES / "kalshi_exact_two_call.tex").write_text(table)
    render_full_grid_latex(
        mean_metrics,
        filename="kalshi_exact_two_call_full_grid.tex",
        caption_prefix="Kalshi exact-two-call sensitivity",
        label_prefix="kalshi_exact_two_call",
    )


def render_tables(mean_metrics: pd.DataFrame, synergy_by_cell: dict, screen: pd.DataFrame,
                  manifest: pd.DataFrame) -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    synergy = synergy_by_cell[("rev_yoy", "TOOL")]
    arms = [
        ("fin", r"$H$"), ("fin+x", r"$H+X$"),
        ("fin+text", r"$H+Z$"), ("fin+x+text", r"$H+X+Z$"),
    ]
    synergy_rows = []
    for model, label in arms:
        row = metric_lookup(mean_metrics, "rev_yoy", "TOOL", model)
        synergy_rows.append(
            f"{label} & {row['r2']:.3f} & {row['calib_r2']:.3f} & "
            f"{row['corr']:.3f} & {row['mae']:.3f} \\\\"
        )
    corr = synergy["syn_corr"]
    skill = synergy["syn_skill"]
    corr_text = (
        f"{corr['mean']:+.3f} [{corr['ci_low']:+.3f}, {corr['ci_high']:+.3f}]"
    )
    skill_text = (
        f"{skill['mean']:+.3f} [{skill['ci_low']:+.3f}, {skill['ci_high']:+.3f}]"
    )
    synergy_tex = r"""\begin{table}[t]
\centering
\caption{\textbf{Kalshi cross-source results on revenue-YoY prediction.}
Point estimates average three independent runs. Confidence intervals pool the
company-clustered bootstrap draws from all three runs.}
\label{tab:kalshi_synergy}
\begin{tabular}{lcccc}
\toprule
Sources & $R^2$ & $R^2$ (Calib.) & $\rho$ & MAE \\
\midrule
""" + "\n".join(synergy_rows) + r"""
\midrule
Corr. synergy & \multicolumn{4}{c}{""" + corr_text + r"""} \\
MSE-skill synergy & \multicolumn{4}{c}{""" + skill_text + r"""} \\
\bottomrule
\end{tabular}
\end{table}
"""
    (TABLES / "kalshi_synergy.tex").write_text(synergy_tex)

    baseline_labels = [
        ("N0", "Historical Avg."), ("N1", "OLS: X only"), ("N2", "OLS: call sentiment"),
        ("N3", "OLS: X + sentiment"), ("N4", "OLS: X + sentiment + interaction"),
        ("N3b", "OLS: X + sentiment + lag"), ("N4b", "OLS: full interaction"),
        ("N5", "Gradient-boosted trees"), (HEADLINE, "Our Method"),
    ]
    baseline_rows = []
    for model, label in baseline_labels:
        available = mean_metrics[
            mean_metrics["y"].eq("rev_yoy")
            & mean_metrics["variant"].eq("TOOL")
            & mean_metrics["model"].eq(model)
        ]
        if len(available):
            row = available.iloc[0]
            baseline_rows.append(
                f"{label} & {row['r2']:.3f} & {row['corr']:.3f} & {row['mae']:.3f} \\\\"
            )
        else:
            baseline_rows.append(f"{label} & N/A & N/A & N/A \\\\")
    baselines_tex = r"""\begin{table}[t]
\centering
\caption{\textbf{Kalshi revenue-YoY baselines.}
N/A denotes a baseline that requires a dense scalar $X$; Kalshi is supplied as a raw
variable-length probability ladder and is not scalarized. Point estimates average three runs.}
\label{tab:kalshi_baselines}
\begin{tabular}{lccc}
\toprule
Method & $R^2$ & $\rho$ & MAE \\
\midrule
""" + "\n".join(baseline_rows) + r"""
\bottomrule
\end{tabular}
\end{table}
"""
    (TABLES / "kalshi_baselines.tex").write_text(baselines_tex)

    base = metric_lookup(mean_metrics, "rev_yoy", "BASE", HEADLINE)
    tool = metric_lookup(mean_metrics, "rev_yoy", "TOOL", HEADLINE)
    tool_rows = (
        f"Without tool use & {base['r2']:.3f} & {base['calib_r2']:.3f} & "
        f"{base['corr']:.3f} & {base['mae']:.3f} \\\\\n"
        f"With tool use & {tool['r2']:.3f} & {tool['calib_r2']:.3f} & "
        f"{tool['corr']:.3f} & {tool['mae']:.3f} \\\\"
    )
    tool_tex = r"""\begin{table}[t]
\centering
\caption{\textbf{Effect of tool use for the Kalshi channel on revenue-YoY prediction.}
Point estimates average three independent runs.}
\label{tab:kalshi_tool_use}
\begin{tabular}{lcccc}
\toprule
Setting & $R^2$ & $R^2$ (Calib.) & $\rho$ & MAE \\
\midrule
""" + tool_rows + r"""
\bottomrule
\end{tabular}
\end{table}
"""
    (TABLES / "kalshi_tool.tex").write_text(tool_tex)

    metric_screen = pd.read_csv(AUTO / "kalshi_kpi_revenue_screen.csv")
    firm_o = screen[screen["impact"].eq("O")]
    screen_rows = (
        f"Metric candidates & (ticker, KPI) pairs & {len(metric_screen)} & "
        f"{metric_screen['ticker'].nunique()} \\\\\n"
        f"Metric-screen included & (ticker, KPI) pairs & "
        f"{(metric_screen['impact'] == 'O').sum()} & "
        f"{metric_screen.loc[metric_screen['impact'].eq('O'), 'ticker'].nunique()} \\\\\n"
        f"Firm-screen included & (ticker, KPI) pairs & {len(firm_o)} & "
        f"{firm_o['ticker'].nunique()} \\\\\n"
        f"Final evaluation targets & company-quarters & "
        f"{len(manifest[manifest['y'].eq('surprise_early')])} & "
        f"{manifest.loc[manifest['y'].eq('surprise_early'), 'ticker'].nunique()} \\\\"
    )
    screen_tex = r"""\begin{table}[t]
\centering
\caption{\textbf{Kalshi KPI screening funnel.}
Pair counts refer to distinct (ticker, KPI metric) decisions; target counts refer to
post-cutoff company-quarters. This is a universe-flow table, not the paper's before/after
scalar-$X$ correlation diagnostic; the raw Kalshi ladder has no pre-specified scalar signal.}
\label{tab:kalshi_screening}
\begin{tabular}{llrr}
\toprule
Stage & Unit & Count & Tickers \\
\midrule
""" + screen_rows + r"""
\bottomrule
\end{tabular}
\end{table}
"""
    (TABLES / "kalshi_screening.tex").write_text(screen_tex)

    tickers = sorted(manifest.loc[manifest["y"].eq("surprise_early"), "ticker"].unique())
    tickers_tex = r"""\begin{table}[t]
\centering
\caption{\textbf{Kalshi evaluation tickers.} Final post-cutoff matched sample.}
\label{tab:kalshi_tickers}
\begin{tabularx}{\linewidth}{@{}l X@{}}
\toprule
Channel & Tickers \\
\midrule
Kalshi KPI markets & \texttt{""" + latex_escape(", ".join(tickers)) + r"""} \\
\bottomrule
\end{tabularx}
\end{table}
"""
    (TABLES / "kalshi_tickers.tex").write_text(tickers_tex)
    render_full_grid_latex(mean_metrics)


def render_report(cfg, seeds, manifest, calls, accuracy_mean, synergy_by_cell, cases,
                  metric_rows, mean_metrics, surrogate_by_rep, screen, screen_logs,
                  exact_two_call: dict) -> None:
    synergy = synergy_by_cell[("rev_yoy", "TOOL")]
    early = accuracy_mean[accuracy_mean["target"].eq("surprise_early")].iloc[0]
    latest = accuracy_mean[accuracy_mean["target"].eq("surprise_print")].iloc[0]
    cost = sum(float(call.get("cost_usd", 0.0)) for call in calls)
    rationale_count = sum(
        bool((call.get("parsed_output") or {}).get("rationale")) for call in calls
    )
    tool_invocations = sum(len(call.get("tool_calls") or []) for call in calls)
    repair_count = sum("repair" in call for call in calls)
    sample = (
        manifest[manifest["y"].eq("surprise_early")]
        .sort_values(["ticker", "FE_FP_END"])
        .copy()
    )
    metric_screen = pd.read_csv(AUTO / "kalshi_kpi_revenue_screen.csv")
    ticker_screen = pd.read_csv(ROOT / "kalshi" / "data" / "ticker_screen.csv")
    firm_o = screen[screen["impact"].eq("O")]
    strong_o = ticker_screen[
        ticker_screen["impact"].eq("O") & ticker_screen["strength"].eq("strong")
    ]
    final_tickers = ", ".join(sorted(sample["ticker"].unique()))
    target_lines = []
    for ticker, group in sample.groupby("ticker", sort=True):
        quarters = ", ".join(group["FE_FP_END"].astype(str))
        h_shown = ", ".join(group["financial_history_shown"].astype(int).astype(str))
        x_shown = ", ".join(group["ladder_history_shown"].astype(int).astype(str))
        calls_shown = ", ".join(group["earnings_call_count"].astype(int).astype(str))
        target_lines.append(
            f"| {ticker} | {quarters} | {len(group)} | {h_shown} | {x_shown} | {calls_shown} |"
        )
    target_table = "\n".join(target_lines)
    rev_tool = mean_metrics[
        mean_metrics["y"].eq("rev_yoy")
        & mean_metrics["variant"].eq("TOOL")
        & mean_metrics["model"].isin(ARMS)
    ].set_index("model")
    arm_labels = {
        "fin": "H",
        "fin+x": "H+X",
        "fin+text": "H+Z",
        "fin+x+text": "H+X+Z",
    }
    metric_lines = [
        f"| {arm_labels[arm]} | {rev_tool.loc[arm, 'rmse']:.3f} | "
        f"{rev_tool.loc[arm, 'r2']:.3f} | {rev_tool.loc[arm, 'calib_r2']:.3f} | "
        f"{rev_tool.loc[arm, 'corr']:.3f} | {rev_tool.loc[arm, 'mae']:.3f} |"
        for arm in ARMS
    ]
    metric_table = "\n".join(metric_lines)
    full_results = markdown_full_results(
        mean_metrics, synergy_by_cell, surrogate_by_rep
    )
    two_manifest = exact_two_call["manifest"]
    two_sample = two_manifest[two_manifest["y"].eq("surprise_early")]
    two_mean_metrics = exact_two_call["mean_metrics"]
    two_accuracy = exact_two_call["accuracy_mean"]
    two_early = two_accuracy[two_accuracy["target"].eq("surprise_early")].iloc[0]
    two_latest = two_accuracy[two_accuracy["target"].eq("surprise_print")].iloc[0]
    two_synergy = exact_two_call["synergy_by_cell"][("rev_yoy", "TOOL")]
    two_rev_tool = two_mean_metrics[
        two_mean_metrics["y"].eq("rev_yoy")
        & two_mean_metrics["variant"].eq("TOOL")
        & two_mean_metrics["model"].isin(ARMS)
    ].set_index("model")
    two_metric_table = "\n".join([
        f"| {arm_labels[arm]} | {two_rev_tool.loc[arm, 'rmse']:.3f} | "
        f"{two_rev_tool.loc[arm, 'r2']:.3f} | "
        f"{two_rev_tool.loc[arm, 'calib_r2']:.3f} | "
        f"{two_rev_tool.loc[arm, 'corr']:.3f} | "
        f"{two_rev_tool.loc[arm, 'mae']:.3f} |"
        for arm in ARMS
    ])
    two_keys = set(zip(two_sample["ticker"], two_sample["FE_FP_END"].astype(str)))
    excluded_rows = [
        row for row in sample.itertuples()
        if (row.ticker, str(row.FE_FP_END)) not in two_keys
    ]
    excluded_text = ", ".join(
        f"{row.ticker} {row.FE_FP_END} ({int(row.earnings_call_count)} eligible call)"
        for row in excluded_rows
    )
    numeric_result_rows = int(metric_rows["available"].ne(False).sum())
    unavailable_result_rows = int(metric_rows["available"].eq(False).sum())
    report = f"""# Kalshi Paper Experiment

## Protocol

- Config: `{CONFIG.relative_to(ROOT)}`
- Seeds: {", ".join(map(str, seeds))}
- Repetitions: {cfg.run.reps}
- Model: `{cfg.llm.model}` at `{cfg.llm.effort}` reasoning effort
- Evaluation rows: {len(manifest[manifest['y'].eq('surprise_early')])} company-quarters /
  {manifest.loc[manifest['y'].eq('surprise_early'), 'ticker'].nunique()} firms
- Grid: 3 targets x 2 variants x 4 arms
- Complete prediction calls: {len(calls)}
- Calls with saved rationale: {rationale_count}
- Tool invocations: {tool_invocations}
- Screening calls: {len(screen_logs)} (7 medium-effort screeners + 7 high-effort auditors)
- Repaired calls after exhausting the original retry budget: {repair_count}
- Recorded API cost: ${cost:,.2f}

Every call log contains the exact system/user prompt, prompt hash, complete parsed structured
output, predicted revenue, confidence, rationale, tool calls and returned text, token usage, cost,
retry count, and error status. The exporter verifies that BASE and TOOL prompts are byte-identical
for the same target and arm. Raw call logs remain under the git-ignored run directory. The two
original timeout records and their replacements are preserved in cell-level `repairs.jsonl` files.

## Result Coverage

The prediction run is complete for the paper grid. It contains {len(calls)} LLM calls:
3 targets x 2 tool variants x 4 source arms x {len(sample)} targets x {cfg.run.reps} repetitions.
Evaluation produces {len(metric_rows)} run-level result rows: {numeric_result_rows} numeric rows
and {unavailable_result_rows} structural N/A baseline rows. Averaging the three repetitions leaves
{len(mean_metrics)} numeric Y/variant/model rows. The headline paper sections below use only a
subset of those rows; the complete six-cell grid is reported under `Complete Six-Cell Results`.

| Experiment family | Status | Scope |
|---|---|---|
| Four-source ablation | Complete | 3 Y definitions x BASE/TOOL x H/H+X/H+Z/H+X+Z x 3 runs |
| Analyst comparison | Complete | Early and latest consensus, TOOL/H+X+Z |
| Tool ablation | Complete | BASE versus TOOL on matched prompts |
| Prediction rationales and qualitative cases | Complete | Rationale saved for every call; two cases selected by a fixed rule |
| Screening decisions and rationale figure | Complete | Every candidate pair has screener and auditor logs |
| Classical baseline table | Partial by design | N0 and N2 available; six X-dependent models are N/A because no scalar X is defined |
| Exact-two-call coverage sensitivity | Complete | {len(two_sample)} matched rows; existing predictions re-evaluated with no new LLM calls |
| Quantitative pre/post-screen X-Y correlation | Not run | The paper's diagnostic requires a scalar X; a raw probability ladder has no pre-specified scalar equivalent |
| A/C/B architecture sensitivity | Not run | Auxiliary experiment in Jihoon's research runner; requires additional prompt schemas and calls |
| Controlled one-call versus two-call Z-depth sensitivity | Not run | Requires new calls with Z depth varied on the same target rows |

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
| Primary metrics | RMSE and MAE in percentage points, OOS R-squared, calibrated OOS R-squared and Pearson correlation |

`H quarters shown` counts prior financial rows rendered in the prompt. `Prior X ladder quarters
shown` counts historical Kalshi ladders rendered before the target-quarter ladder. `Prior calls`
counts eligible corrected transcripts included in Z.

## Universe

| Stage | Unit | Count | Tickers |
|---|---|---:|---:|
| Numeric KPI candidates | `(ticker, KPI)` pairs | {len(metric_screen)} | {metric_screen['ticker'].nunique()} |
| Revenue-metric screen O | `(ticker, KPI)` pairs | {len(metric_screen[metric_screen['impact'].eq('O')])} | {metric_screen.loc[metric_screen['impact'].eq('O'), 'ticker'].nunique()} |
| Firm revenue-driver screen O | `(ticker, KPI)` pairs | {len(firm_o)} | {firm_o['ticker'].nunique()} |
| Strong-O ticker screen | tickers | {len(strong_o)} | {len(strong_o)} |
| Final post-cutoff matched sample | company-quarters | {len(sample)} | {sample['ticker'].nunique()} |

The metric screen removes KPI types that are not revenue bases. The firm screen applies one
medium-effort screener and one high-effort auditor to every candidate pair and judges the KPI
against total company revenue. `strength` is confidence in the O/X decision, not estimated revenue
share. This is a Kalshi-specific adaptation of the paper's channel-level screening prompt:
the decision unit is `(ticker, KPI metric)` and the high-effort audit pass is additional. The
prediction prompts themselves use the paper protocol. The resulting screen is frozen before
prediction. This rerun honestly produced DPZ as strong and UAL as moderate, so the final sample is
21 rather than the legacy one-run sample's 22; the screen was not repeated until a preferred
universe appeared.

Final tickers: `{final_tickers}`.

| Ticker | Target fiscal quarters | Targets | H quarters shown | Prior X ladder quarters shown | Prior calls |
|---|---|---:|---|---|---|
{target_table}

## Tool Variant

BASE receives no tools. TOOL receives two no-argument functions:
`get_company_profile` returns the frozen public business/revenue-driver profile, and
`get_alt_data_description` returns the frozen Kalshi ladder methodology description. Their
returned text and full call order are stored in each call's `tool_trace`.

Classical baselines N1, N3, N4, N3b, N4b and N5 are N/A because they require a dense scalar X.
Kalshi X is intentionally kept as a raw ladder. N0 (historical average) and N2 (call sentiment)
remain available because they do not require scalarizing X.

## Analyst Accuracy

| Consensus snapshot | Analyst RMSE | Method RMSE | Analyst MAE | Method MAE | Win rate |
|---|---:|---:|---:|---:|---:|
| Early | {early.analyst_rmse:.3f} | {early.method_rmse:.3f} | {early.analyst_mae:.3f} | {early.method_mae:.3f} | {early.win_rate_pct:.1f}% |
| Latest pre-report | {latest.analyst_rmse:.3f} | {latest.method_rmse:.3f} | {latest.analyst_mae:.3f} | {latest.method_mae:.3f} | {latest.win_rate_pct:.1f}% |

Values are arithmetic means of the three per-repetition metrics. RMSE and MAE are in revenue-target
percentage points and lower is better. The Kalshi method is the paper-consistent `TOOL / H+X+Z`
arm; analyst consensus predicts zero surprise.

## Revenue-YoY Results

| Sources | RMSE | OOS R-squared | Calibrated R-squared | Correlation | MAE |
|---|---:|---:|---:|---:|---:|
{metric_table}

The best point-estimate RMSE is H+X, not the full H+X+Z arm. The full arm remains the predefined
headline method so that reporting stays symmetric with the paper design.

## Synergy

- Correlation synergy: {synergy['syn_corr']['mean']:+.3f},
  95% pooled-bootstrap CI [{synergy['syn_corr']['ci_low']:+.3f},
  {synergy['syn_corr']['ci_high']:+.3f}]
- MSE-skill synergy: {synergy['syn_skill']['mean']:+.3f},
  95% pooled-bootstrap CI [{synergy['syn_skill']['ci_low']:+.3f},
  {synergy['syn_skill']['ci_high']:+.3f}]

Synergy compares the observed full model with the additive expectation
`(H+X improvement) + (H+Z improvement)`. Both intervals are below zero in this run, so the
Kalshi-plus-transcript combination is sub-additive; this is evidence against a positive synergy
claim, not evidence that Kalshi X alone has no value.

## Exact-Two-Call Coverage Sensitivity

This sensitivity requires `earnings_call_count == 2` after the 31-day embargo. It excludes
{excluded_text} from every arm, variant, Y definition and repetition, leaving {len(two_sample)}
company-quarters / {two_sample['ticker'].nunique()} firms. It reuses the existing predictions and
makes zero new LLM calls.

This is a matched-sample coverage check: it asks whether the conclusions persist after removing
targets with only one eligible call. It is not a causal one-call-versus-two-call Z-depth test,
because the remaining predictions were originally generated with two calls and the excluded
predictions were generated with one.

| Consensus snapshot | Analyst RMSE | Method RMSE | Analyst MAE | Method MAE | Win rate |
|---|---:|---:|---:|---:|---:|
| Early | {two_early.analyst_rmse:.3f} | {two_early.method_rmse:.3f} | {two_early.analyst_mae:.3f} | {two_early.method_mae:.3f} | {two_early.win_rate_pct:.1f}% |
| Latest pre-report | {two_latest.analyst_rmse:.3f} | {two_latest.method_rmse:.3f} | {two_latest.analyst_mae:.3f} | {two_latest.method_mae:.3f} | {two_latest.win_rate_pct:.1f}% |

Revenue-YoY / TOOL:

| Sources | RMSE | OOS R-squared | Calibrated R-squared | Correlation | MAE |
|---|---:|---:|---:|---:|---:|
{two_metric_table}

- Correlation synergy: {two_synergy['syn_corr']['mean']:+.3f},
  95% pooled-bootstrap CI [{two_synergy['syn_corr']['ci_low']:+.3f},
  {two_synergy['syn_corr']['ci_high']:+.3f}]
- MSE-skill synergy: {two_synergy['syn_skill']['mean']:+.3f},
  95% pooled-bootstrap CI [{two_synergy['syn_skill']['ci_low']:+.3f},
  {two_synergy['syn_skill']['ci_high']:+.3f}]

H+X remains the best Revenue-YoY arm by both RMSE and MAE; removing the two one-call rows does not
rescue a positive synergy result. The complete six-cell sensitivity, including MAE for every
available model, is stored in `exact_two_call_metrics_mean.csv` and
`kalshi_exact_two_call_full_grid.tex`.

## Complete Six-Cell Results

All point estimates below are arithmetic means of three independent runs. The pooled-bootstrap
summary concatenates the three run-specific company-clustered bootstrap distributions; it is a
run-level sensitivity summary, not 15,000 independent observations. Negative RMSE changes favor
the model with Kalshi X. Run-specific metrics and inference outputs are preserved in
`metrics_by_rep.csv`, `synergy_by_rep.csv`, and `surrogate_by_rep.csv`.

{full_results}

## Qualitative Selection

The early- and latest-consensus cases are selected by the pre-specified rule saved in
`kalshi/paper/data/qualitative_cases.json`: largest mean three-repetition reduction in absolute
`H+Z` error after adding X, with distinct tickers when possible. The displayed rationale and
estimate come from the replicate closest to the three-run mean, and its seed and prompt hash are
saved with the case.

Selected cases: {", ".join(f"{case['ticker']} ({case['target']}, seed {case['representative_seed']})" for case in cases)}.

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
- `kalshi/paper/tables/kalshi_exact_two_call.tex`
- `kalshi/paper/tables/kalshi_exact_two_call_full_grid.tex`
- `kalshi/paper/data/exact_two_call_evaluation_manifest.csv`
- `kalshi/paper/data/exact_two_call_metrics_by_rep.csv`
- `kalshi/paper/data/exact_two_call_metrics_mean.csv`
- `kalshi/paper/data/exact_two_call_accuracy_by_rep.csv`
- `kalshi/paper/data/exact_two_call_accuracy_mean.csv`
- `kalshi/paper/data/exact_two_call_synergy_by_rep.csv`
- `kalshi/paper/data/exact_two_call_synergy_pooled.csv`
- `kalshi/paper/data/exact_two_call_surrogate_by_rep.csv`
- `kalshi/paper/data/exact_two_call_audit.json`
- Supporting CSV/JSON files under `kalshi/paper/data/`
"""
    REPORT.write_text(report)


def main() -> None:
    cfg, seeds, manifest, panel, records, metric_rows, calls = load_run()
    screen = pd.read_csv(AUTO / "kalshi_kpi_firm_screen.csv")
    screen_logs = validate_screen_logs(screen)
    events = pd.read_csv(AUTO / "kalshi_x_revsurprise_events.csv")
    mean_metrics = aggregate_metrics(metric_rows)
    accuracy_rep, accuracy_mean = accuracy(records)
    cases = qualitative_cases(records, panel)
    screens = screen_examples(screen, events)
    synergy_by_cell, synergy_by_rep, synergy_pooled, surrogate_by_rep = (
        evaluation_statistics(records)
    )
    two_manifest, two_records, two_metric_rows = reevaluate_exact_two_call(
        cfg, manifest, panel, records
    )
    two_mean_metrics = aggregate_metrics(two_metric_rows)
    two_accuracy_rep, two_accuracy_mean = accuracy(two_records)
    (
        two_synergy_by_cell,
        two_synergy_by_rep,
        two_synergy_pooled,
        two_surrogate_by_rep,
    ) = evaluation_statistics(two_records)
    exact_two_call = {
        "manifest": two_manifest,
        "records": two_records,
        "metric_rows": two_metric_rows,
        "mean_metrics": two_mean_metrics,
        "accuracy_rep": two_accuracy_rep,
        "accuracy_mean": two_accuracy_mean,
        "synergy_by_cell": two_synergy_by_cell,
        "synergy_by_rep": two_synergy_by_rep,
        "synergy_pooled": two_synergy_pooled,
        "surrogate_by_rep": two_surrogate_by_rep,
    }

    FIGURES.mkdir(parents=True, exist_ok=True)
    write_data(
        cfg, seeds, manifest, metric_rows, accuracy_rep, accuracy_mean,
        cases, screens, calls, screen_logs, synergy_by_cell,
        synergy_by_rep, synergy_pooled, surrogate_by_rep,
    )
    write_exact_two_call_data(
        manifest, two_manifest, two_records, two_metric_rows,
        two_accuracy_rep, two_accuracy_mean, two_synergy_by_cell,
        two_synergy_by_rep, two_synergy_pooled, two_surrogate_by_rep,
    )
    render_accuracy(accuracy_mean)
    render_qualitative(cases)
    render_screen(screens)
    render_tables(mean_metrics, synergy_by_cell, screen, manifest)
    render_exact_two_call_tables(
        two_mean_metrics,
        two_synergy_by_cell,
        len(two_manifest[two_manifest["y"].eq("surprise_early")]),
    )
    render_report(
        cfg, seeds, manifest, calls, accuracy_mean, synergy_by_cell, cases,
        metric_rows, mean_metrics, surrogate_by_rep, screen, screen_logs,
        exact_two_call,
    )
    print(f"[written] {PAPER}")
    print(f"[written] {REPORT}")


if __name__ == "__main__":
    main()
