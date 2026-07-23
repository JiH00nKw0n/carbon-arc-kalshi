#!/usr/bin/env python3
"""Repair failed paper-run calls without re-running successful target arms.

The prediction runner deliberately drops a target row when any arm fails. This script finds failed
call records, replays their exact stored system/user prompts, archives the failed and replacement
records in ``repairs.jsonl``, reconstructs the matched target row, and rewrites the cell report.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import prediction  # noqa: F401
from prediction.config.loader import load
from prediction.data.llm_client import LLMRequest
from prediction.prompts.tools import TOOL_DEFS, make_tool_dispatch
from prediction.run.experiment import (
    _cell_context,
    _evaluate_cell,
    _select_strong,
    build_experiment,
)
from prediction.run.grid import Cell
from prediction.targets.ytarget import get_y_target

DEFAULT_CONFIG = ROOT / "prediction" / "configs" / "kalshi_paper.yaml"
ARMS = ("fin", "fin+x", "fin+text", "fin+x+text")
ANCHOR_COLUMNS = {
    "cons_early": "CONS_EARLY",
    "cons_print": "CONS_PRINT",
    "prior_year_actual": "prior_year_actual",
}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def cell_dir(cfg, seed: int, cell: Cell) -> Path:
    slug = (
        f"{cell.channel}.{cell.y}.{cell.variant}."
        f"{cfg.llm.model}.{cfg.llm.effort}.seed{seed}"
    )
    return ROOT / cfg.output_dir / slug


def finite_or_none(value):
    return float(value) if value is not None and not pd.isna(value) and math.isfinite(value) else None


def reconstructed_row(calls: list[dict], panel_row, y_target) -> dict:
    by_arm = {call["arm"]: call for call in calls}
    if set(by_arm) != set(ARMS) or any(call["status"] != "ok" for call in calls):
        raise RuntimeError("cannot reconstruct target row until all four arms are successful")
    first = calls[0]
    row = {
        "tkr": first["ticker"],
        "fp": first["fiscal_period_end"],
        "report": first["report_date"],
        "true": y_target.label(panel_row),
        "x_yoy": finite_or_none(getattr(panel_row, "x_yoy", None)),
    }
    for arm in ARMS:
        call = by_arm[arm]
        row[arm] = call["derived_prediction_pct"]
        row[f"tool_calls__{arm}"] = "|".join(call.get("tool_calls") or [])
    return row


def extract_prediction(y_target, predicted_revenue_musd: float, panel_row) -> float:
    anchor = getattr(panel_row, ANCHOR_COLUMNS[y_target.anchor_col])
    return y_target.extract(
        predicted_revenue_musd,
        SimpleNamespace(**{y_target.anchor_col: anchor}),
    )


async def repair(config_path: Path) -> int:
    cfg = load(str(config_path))
    experiment = build_experiment(cfg)
    repaired = 0
    try:
        for seed in range(cfg.seed, cfg.seed + cfg.run.reps):
            experiment.store._seed = seed
            for y in cfg.grid.targets:
                for variant in cfg.grid.variants:
                    cell = Cell(channel="kalshi", y=y, variant=variant)
                    directory = cell_dir(cfg, seed, cell)
                    calls_path = directory / "calls.jsonl"
                    preds_path = directory / "preds.csv"
                    if not calls_path.exists() or not preds_path.exists():
                        continue
                    calls = read_jsonl(calls_path)
                    failed_indices = [
                        index for index, call in enumerate(calls)
                        if call.get("status") != "ok"
                    ]
                    if not failed_indices:
                        continue

                    context = _cell_context(experiment, cell)
                    panel = _select_strong(
                        experiment.panels.get_or_build(context.channel),
                        cfg.run,
                    )
                    y_target = get_y_target(y)
                    archive = []
                    repaired_targets = set()

                    for index in failed_indices:
                        original = calls[index]
                        tools_enabled = bool(original.get("tools_enabled"))
                        request = LLMRequest(
                            system=original["system_prompt"],
                            user=original["user_prompt"],
                            schema=y_target.schema,
                            tools=TOOL_DEFS if tools_enabled else None,
                            dispatch=(
                                make_tool_dispatch(context.descriptions, original["ticker"])
                                if tools_enabled else None
                            ),
                        )
                        result = await experiment.llm_client.predict_structured(request)
                        if result.parsed is None:
                            raise RuntimeError(
                                f"repair failed after {result.attempts} attempts: "
                                f"{original['ticker']} {original['fiscal_period_end']} "
                                f"{original['arm']}: {result.error}"
                            )
                        match = panel[
                            panel["ticker"].eq(original["ticker"])
                            & panel["FE_FP_END"].astype(str).eq(
                                str(original["fiscal_period_end"])
                            )
                        ]
                        if len(match) != 1:
                            raise RuntimeError(
                                f"panel row mismatch for {original['ticker']} "
                                f"{original['fiscal_period_end']}: {len(match)} rows"
                            )
                        panel_row = next(match.itertuples(index=False))
                        parsed = result.parsed.model_dump(mode="json")
                        replacement = {
                            **original,
                            "status": "ok",
                            "parsed_output": parsed,
                            "derived_prediction_pct": extract_prediction(
                                y_target, result.parsed.predicted_revenue_musd, panel_row
                            ),
                            "tool_calls": list(result.tool_calls),
                            "tool_trace": list(result.tool_trace),
                            "cost_usd": result.cost_usd,
                            "input_tokens": result.input_tokens,
                            "cached_input_tokens": result.cached_input_tokens,
                            "output_tokens": result.output_tokens,
                            "attempts": result.attempts,
                            "error": result.error,
                            "repair": {
                                "repaired_at": datetime.now(timezone.utc).isoformat(),
                                "prior_status": original.get("status"),
                                "prior_attempts": original.get("attempts"),
                                "prior_error": original.get("error"),
                            },
                        }
                        calls[index] = replacement
                        archive.append({
                            "schema_version": 1,
                            "reason": "exhausted configured retry budget",
                            "original_call": original,
                            "replacement_call": replacement,
                        })
                        repaired_targets.add(
                            (original["ticker"], str(original["fiscal_period_end"]))
                        )
                        repaired += 1
                        print(
                            f"[repaired] seed={seed} {y}/{variant} "
                            f"{original['ticker']} {original['fiscal_period_end']} "
                            f"{original['arm']} attempts={result.attempts}",
                            flush=True,
                        )

                    preds = pd.read_csv(preds_path)
                    for ticker, fp in sorted(repaired_targets):
                        target_calls = [
                            call for call in calls
                            if call["ticker"] == ticker
                            and str(call["fiscal_period_end"]) == fp
                        ]
                        match = panel[
                            panel["ticker"].eq(ticker)
                            & panel["FE_FP_END"].astype(str).eq(fp)
                        ]
                        panel_row = next(match.itertuples(index=False))
                        row = reconstructed_row(target_calls, panel_row, y_target)
                        preds = preds[
                            ~(preds["tkr"].eq(ticker) & preds["fp"].astype(str).eq(fp))
                        ]
                        preds = pd.concat([preds, pd.DataFrame([row])], ignore_index=True)

                    preds = preds.sort_values(["tkr", "fp"]).reset_index(drop=True)
                    experiment.store.write_preds(cell, preds, calls)
                    result = _evaluate_cell(cfg, cell, panel, preds, context, seed)
                    experiment.store.write_report(cell, result)
                    with (directory / "repairs.jsonl").open("a") as handle:
                        for record in archive:
                            handle.write(
                                json.dumps(record, ensure_ascii=True, separators=(",", ":"))
                                + "\n"
                            )
        return repaired
    finally:
        client = getattr(experiment.llm_client, "_client", None)
        if client is not None:
            await client.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    repaired = asyncio.run(repair(args.config))
    print(f"[done] repaired calls={repaired}")


if __name__ == "__main__":
    main()
