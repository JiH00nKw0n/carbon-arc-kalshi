"""Async LLM predictor over targets x arms, returning scores and complete call audit records.

For each target, every arm renders its own prompt (the single BASE builder, driven by the arm's
block set) but shares ONE structured schema (the Y's) and ONE extractor (the Y's): the arm chooses
only which blocks appear, so the four arms score the identical matched row-set. A target row is
emitted only when EVERY arm returned a parsed prediction (mirrors factor1 f1_21_run's
``all(v is not None)`` gate), which keeps the arms on the same rows for the synergy contrast.

``tools_enabled`` comes from the variant spec (BASE=False, TOOL=True). When set, each request carries
the lookup tools + a target-scoped dispatch (``prompts/tools``) and the LLM client runs the
tool_call/tool_result loop before parsing; the prompt itself is identical either way.

Concurrency is bounded by the LLM client's own semaphore. Every attempted call emits a JSON-safe
record containing the exact prompt, complete parsed output (including rationale and confidence),
tool trace, token usage, retry status, and derived metric. Evaluation rows retain the compact
factor1 ablation frame.
"""
from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from typing import Any, Optional

from prediction.data.llm_client import SYS, LLMRequest
from prediction.prompts.tools import TOOL_DEFS, make_tool_dispatch

__all__ = ["PredictionBatch", "predict_arms"]


@dataclass(frozen=True)
class PredictionBatch:
    """Fully matched evaluation rows plus one audit record per attempted LLM call."""
    rows: list[dict]
    calls: list[dict[str, Any]]


@dataclass(frozen=True)
class _ArmPrediction:
    value: Optional[float]
    tool_calls: tuple[str, ...]
    log: dict[str, Any]


async def predict_arms(targets, prompt_builder, tools_enabled, arm_specs, y_target, channel_spec,
                       transcript_store, description_provider, llm_client, run_cfg, *,
                       cell, seed: int, llm_cfg) -> PredictionBatch:
    """Score targets and preserve every call, including failures excluded from matched rows."""
    results = await asyncio.gather(*(
        _predict_target(target, prompt_builder, tools_enabled, arm_specs, y_target, channel_spec,
                        transcript_store, description_provider, llm_client, run_cfg,
                        cell, seed, llm_cfg)
        for target in targets))
    rows = [row for row, _ in results if row is not None]
    calls = [call for _, target_calls in results for call in target_calls]
    return PredictionBatch(rows=rows, calls=calls)


async def _predict_target(target, prompt_builder, tools_enabled, arm_specs, y_target, channel_spec,
                          transcript_store, description_provider, llm_client, run_cfg,
                          cell, seed, llm_cfg) -> tuple[Optional[dict], list[dict[str, Any]]]:
    """Score all arms; retain logs even when one failed arm removes the matched target row."""
    preds = await asyncio.gather(*(
        _predict_arm(target, arm, prompt_builder, tools_enabled, y_target, channel_spec,
                     transcript_store, description_provider, llm_client, run_cfg,
                     cell, seed, llm_cfg)
        for arm in arm_specs))
    logs = [pred.log for pred in preds]
    if any(pred.value is None for pred in preds):
        return None, logs
    row = {
        "tkr": target.ticker,
        "fp": target.fp.isoformat(),
        "report": target.report.isoformat(),
        "true": target.true,
        "x_yoy": target.x_yoy,
    }
    for arm, pred in zip(arm_specs, preds):
        row[arm.name] = pred.value
        row[f"tool_calls__{arm.name}"] = "|".join(pred.tool_calls)
    return row, logs


async def _predict_arm(target, arm, prompt_builder, tools_enabled, y_target, channel_spec,
                       transcript_store, description_provider, llm_client, run_cfg,
                       cell, seed, llm_cfg) -> _ArmPrediction:
    """Render, call, derive the score, and produce a lossless JSON-safe audit record."""
    prompt = prompt_builder(target, transcript_store, description_provider, channel_spec,
                            y_target, arm.blocks, run_cfg.n_calls, run_cfg.hist_rows,
                            run_cfg.prompt_protocol)
    system = (
        y_target.paper_system_prompt
        if run_cfg.prompt_protocol == "paper"
        else SYS
    )
    tools = TOOL_DEFS if tools_enabled else None
    dispatch = make_tool_dispatch(description_provider, target.ticker) if tools_enabled else None
    request = LLMRequest(system=system, user=prompt, schema=y_target.schema,
                         tools=tools, dispatch=dispatch)
    result = await llm_client.predict_structured(request)
    parsed = result.parsed.model_dump(mode="json") if result.parsed is not None else None
    value = (y_target.extract(result.parsed.predicted_revenue_musd, target.row)
             if result.parsed is not None else None)
    tool_calls = tuple(getattr(result, "tool_calls", ()))
    log = {
        "schema_version": 1,
        "status": "ok" if result.parsed is not None else "failed",
        "channel": cell.channel,
        "target": cell.y,
        "variant": cell.variant,
        "arm": arm.name,
        "blocks": sorted(arm.blocks),
        "seed": seed,
        "model": llm_cfg.model,
        "reasoning_effort": llm_cfg.effort,
        "prompt_protocol": run_cfg.prompt_protocol,
        "ticker": target.ticker,
        "fiscal_period_end": target.fp.isoformat(),
        "report_date": target.report.isoformat(),
        "tools_enabled": tools_enabled,
        "response_schema": y_target.schema.__name__,
        "system_prompt": system,
        "user_prompt": prompt,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "prompt_chars": len(prompt),
        "parsed_output": parsed,
        "derived_prediction_pct": value,
        "tool_calls": list(tool_calls),
        "tool_trace": list(getattr(result, "tool_trace", ())),
        "cost_usd": result.cost_usd,
        "input_tokens": getattr(result, "input_tokens", 0),
        "cached_input_tokens": getattr(result, "cached_input_tokens", 0),
        "output_tokens": getattr(result, "output_tokens", 0),
        "attempts": getattr(result, "attempts", 1),
        "error": getattr(result, "error", None),
    }
    return _ArmPrediction(value=value, tool_calls=tool_calls, log=log)
