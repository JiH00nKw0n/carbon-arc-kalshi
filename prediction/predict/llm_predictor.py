"""Async LLM predictor over targets × arms — pure query, returns rows, writes nothing.

For each target, every arm renders its own prompt (the single BASE builder, driven by the arm's
block set) but shares ONE structured schema (the Y's) and ONE extractor (the Y's): the arm chooses
only which blocks appear, so the four arms score the identical matched row-set. A target row is
emitted only when EVERY arm returned a parsed prediction (mirrors factor1 f1_21_run's
``all(v is not None)`` gate), which keeps the arms on the same rows for the synergy contrast.

``tools_enabled`` comes from the variant spec (BASE=False, TOOL=True). When set, each request carries
the lookup tools + a target-scoped dispatch (``prompts/tools``) and the LLM client runs the
tool_call/tool_result loop before parsing; the prompt itself is identical either way.

Concurrency is bounded by the LLM client's own semaphore: all (target, arm) calls become tasks and
the client gates how many are in flight. The row schema is exactly factor1's ablation frame:
``tkr, true`` (a fraction), ``x_yoy``, and one percent-prediction column per arm name.
"""
from __future__ import annotations

import asyncio
from typing import Optional

from prediction.data.llm_client import SYS, LLMRequest
from prediction.prompts.tools import TOOL_DEFS, make_tool_dispatch

__all__ = ["predict_arms"]


async def predict_arms(targets, prompt_builder, tools_enabled, arm_specs, y_target, channel_spec,
                       transcript_store, description_provider, llm_client, run_cfg) -> list[dict]:
    """One row per fully-scored target: ``tkr, true, x_yoy`` + a percent column per arm."""
    rows = await asyncio.gather(*(
        _predict_target(target, prompt_builder, tools_enabled, arm_specs, y_target, channel_spec,
                        transcript_store, description_provider, llm_client, run_cfg)
        for target in targets))
    return [row for row in rows if row is not None]


async def _predict_target(target, prompt_builder, tools_enabled, arm_specs, y_target, channel_spec,
                          transcript_store, description_provider, llm_client, run_cfg
                          ) -> Optional[dict]:
    """Score all arms for one target; None unless every arm produced a prediction."""
    preds = await asyncio.gather(*(
        _predict_arm(target, arm, prompt_builder, tools_enabled, y_target, channel_spec,
                     transcript_store, description_provider, llm_client, run_cfg)
        for arm in arm_specs))
    if any(pred is None for pred in preds):
        return None
    row = {"tkr": target.ticker, "true": target.true, "x_yoy": target.x_yoy}
    for arm, pred in zip(arm_specs, preds):
        row[arm.name] = pred
    return row


async def _predict_arm(target, arm, prompt_builder, tools_enabled, y_target, channel_spec,
                       transcript_store, description_provider, llm_client, run_cfg
                       ) -> Optional[float]:
    """Render this arm's prompt, ask the LLM, and derive the Y's percent metric (None on failure)."""
    prompt = prompt_builder(target, transcript_store, description_provider, channel_spec,
                            y_target, arm.blocks, run_cfg.n_calls, run_cfg.hist_rows)
    tools = TOOL_DEFS if tools_enabled else None
    dispatch = make_tool_dispatch(description_provider, target.ticker) if tools_enabled else None
    request = LLMRequest(system=SYS, user=prompt, schema=y_target.schema, tools=tools, dispatch=dispatch)
    result = await llm_client.predict_structured(request)
    if result.parsed is None:
        return None
    return y_target.extract(result.parsed.predicted_revenue_musd, target.row)
