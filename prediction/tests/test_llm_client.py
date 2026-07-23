"""Responses-API tool-loop regression tests."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from prediction.data.llm_client import LLMConfig, LLMRequest, OpenAIStructuredClient
from prediction.targets.schemas import BPredictSurprise


class FakeResponses:
    def __init__(self, responses):
        self._responses = iter(responses)
        self.calls = []

    async def parse(self, **kwargs):
        self.calls.append(kwargs)
        return next(self._responses)


def _usage(input_tokens=100, output_tokens=20):
    return SimpleNamespace(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        input_tokens_details=SimpleNamespace(cached_tokens=0),
    )


@pytest.mark.asyncio
async def test_responses_tool_loop_carries_reasoning_and_records_usage():
    reasoning = SimpleNamespace(type="reasoning", encrypted_content="encrypted-state")
    function_call = SimpleNamespace(
        type="function_call", call_id="call-1", name="get_company_profile", arguments="{}"
    )
    parsed = BPredictSurprise(
        predicted_revenue_musd=110,
        consensus_revenue_musd=100,
        predicted_surprise_pct=10,
        confidence=60,
        rationale="test",
    )
    api = FakeResponses([
        SimpleNamespace(output_parsed=None, output=[reasoning, function_call], usage=_usage()),
        SimpleNamespace(output_parsed=parsed, output=[], usage=_usage()),
    ])
    client = OpenAIStructuredClient.__new__(OpenAIStructuredClient)
    client._config = LLMConfig(model="gpt-test", effort="medium")
    client._client = SimpleNamespace(responses=api)

    request = LLMRequest(
        system="system",
        user="user",
        schema=BPredictSurprise,
        tools=[{"type": "function", "name": "get_company_profile"}],
        dispatch=lambda name, args: "profile text",
    )
    result = await client._parse_once_responses(request)

    assert result.parsed == parsed
    assert result.tool_calls == ("get_company_profile",)
    assert result.tool_trace == ({
        "name": "get_company_profile",
        "arguments": {},
        "output": "profile text",
    },)
    assert result.input_tokens == 200
    assert result.output_tokens == 40
    assert len(api.calls) == 2
    assert api.calls[0]["store"] is False
    assert api.calls[0]["include"] == ["reasoning.encrypted_content"]
    followup = api.calls[1]["input"]
    assert reasoning in followup
    assert function_call in followup
    assert followup[-1] == {
        "type": "function_call_output",
        "call_id": "call-1",
        "output": "profile text",
    }
