import json
from dataclasses import dataclass
from datetime import date
from types import SimpleNamespace

import pandas as pd
import pytest

from prediction.arms.specs import get_arm
from prediction.config.schema import RunCfg
from prediction.domain.records import CallRef
from prediction.predict.llm_predictor import predict_arms
from prediction.registry import Registry
from prediction.run.grid import Cell
from prediction.run.store import ResultStore
from prediction.targets.schemas import BPredictSurprise
from prediction.targets.ytarget import get_y_target
from prediction.tests.conftest import FakeTranscriptStore, _ChannelBoundDescriptions


@dataclass
class LoggedResult:
    parsed: object
    cost_usd: float = 0.125
    tool_calls: tuple[str, ...] = ()
    tool_trace: tuple[dict, ...] = ()
    input_tokens: int = 100
    cached_input_tokens: int = 20
    output_tokens: int = 30
    attempts: int = 1
    error: str | None = None


class AsyncLoggedClient:
    async def predict_structured(self, _request):
        return LoggedResult(parsed=BPredictSurprise(
            predicted_revenue_musd=128.0,
            consensus_revenue_musd=125.0,
            predicted_surprise_pct=2.4,
            confidence=73,
            rationale="Demand evidence supports a modest beat.",
        ))


@pytest.mark.asyncio
async def test_prediction_call_log_preserves_prompt_rationale_and_telemetry(
        prompt_target, card_channel, descriptions):
    run_cfg = RunCfg(cutoff=date(2025, 12, 1))
    transcripts = FakeTranscriptStore(
        [CallRef(prompt_target.ticker, date(2024, 11, 15), prompt_target.call_path)],
        texts={prompt_target.call_path: prompt_target.text},
    )
    batch = await predict_arms(
        [prompt_target],
        Registry.get("prompt", "BASE"),
        False,
        [get_arm("fin+x+text")],
        get_y_target("surprise_early"),
        card_channel,
        transcripts,
        _ChannelBoundDescriptions(descriptions, card_channel.name),
        AsyncLoggedClient(),
        run_cfg,
        cell=Cell(channel="card", y="surprise_early", variant="BASE"),
        seed=2026,
        llm_cfg=SimpleNamespace(model="gpt-test", effort="medium"),
    )

    assert len(batch.rows) == 1
    assert len(batch.calls) == 1
    call = batch.calls[0]
    assert call["parsed_output"]["rationale"] == "Demand evidence supports a modest beat."
    assert call["parsed_output"]["confidence"] == 73
    assert call["parsed_output"]["predicted_revenue_musd"] == 128.0
    assert call["derived_prediction_pct"] == pytest.approx(2.4)
    assert "ZZTEXTMARKERZZ" in call["user_prompt"]
    assert len(call["prompt_sha256"]) == 64
    assert call["input_tokens"] == 100
    assert call["cost_usd"] == pytest.approx(0.125)
    assert "true" not in call


def test_result_store_requires_and_writes_complete_call_log(tmp_path):
    store = ResultStore(str(tmp_path), "gpt-test", "medium", 2026)
    cell = Cell(channel="kalshi", y="surprise_early", variant="BASE")
    preds = pd.DataFrame([{
        "tkr": "AAA", "fp": "2026-03-31", "report": "2026-05-01",
        "true": 0.01, "x_yoy": None, "fin": 1.0, "tool_calls__fin": "",
    }])
    calls = [{"schema_version": 1, "ticker": "AAA",
              "parsed_output": {"rationale": "complete"}}]

    store.write_preds(cell, preds, calls)
    assert not store.done(cell)
    store.report_path(cell).write_text("complete\n")

    assert store.done(cell)
    directory = tmp_path / "kalshi.surprise_early.BASE.gpt-test.medium.seed2026"
    saved = json.loads((directory / "calls.jsonl").read_text())
    assert saved["parsed_output"]["rationale"] == "complete"
