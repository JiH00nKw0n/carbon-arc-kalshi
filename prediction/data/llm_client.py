"""LLM boundary — an AsyncOpenAI structured-output client. No vendor object crosses out.

Pricing, the long-context threshold, the cost formula, and the system prompt are copied verbatim
from f1_llm.py so cost/behavior match the proven runs. `predict_structured` mirrors f1_llm.acall: a
gpt-5.5 structured-parse call under a shared concurrency semaphore, with an exponential-backoff retry
loop that yields an empty result (parsed=None, cost=0) after the final attempt fails. When the
request carries tools, the parse step first runs a tool_call/tool_result loop (see `_parse_once`).

The OpenAI API key is read from the environment (``OPENAI_API_KEY``); ``load_dotenv()`` pulls it from
a ``.env`` file at the project root if one is present.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from dataclasses import dataclass, replace
from typing import Any, Callable, Optional, Protocol

import httpx
from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import BaseModel

from prediction.registry import register_llm

__all__ = [
    "LLMConfig", "LLMRequest", "LLMResult", "LLMClient",
    "OpenAIStructuredClient", "make_openai_client", "SYS", "PRICING", "LONG_CTX_THRESHOLD",
    "gpt5_cost", "gpt5_cost_responses",
]

# gpt-5.5 pricing $/1M (OpenAI): SHORT (<=272K input tok) vs LONG (>272K). Verbatim from f1_llm.py.
PRICING = {"short": {"in": 5.0, "cached": 0.5, "out": 30.0},
           "long":  {"in": 10.0, "cached": 1.0, "out": 45.0}}
LONG_CTX_THRESHOLD = 272_000

# Per-request timeout (s). Transcript-bearing paper prompts can take several minutes at the gateway;
# keep a finite ceiling for genuinely stalled requests without aborting valid long-context reasoning.
_REQUEST_TIMEOUT = 600.0


def _http_client() -> httpx.AsyncClient:
    """Fresh-connection HTTP client (keep-alive disabled). A laptop sleep silently kills the pooled
    TCP/TLS connections; with keep-alive on, httpx re-hands those dead sockets to every retry and the
    run hangs forever after resume. max_keepalive_connections=0 dials a fresh connection per request,
    so the run self-recovers from sleep — at the cost of one handshake per call."""
    return httpx.AsyncClient(
        timeout=httpx.Timeout(_REQUEST_TIMEOUT, connect=15.0),
        limits=httpx.Limits(max_keepalive_connections=0, max_connections=64))

SYS = (
    "You are an equity revenue-surprise nowcaster. You only see information available BEFORE the "
    "upcoming quarter's earnings report; you do NOT know the actual result. The target is the REVENUE "
    "surprise = (actual - analyst consensus)/consensus, i.e. the part NOT already priced into estimates. "
    "Score the deviation from consensus expectations, not absolute fundamentals. Be calibrated and "
    "conservative. Output only the requested structured fields."
)


def gpt5_cost(usage) -> float:
    """$ for one gpt-5.5 call from its usage object (tiered by input length, cache-aware). Verbatim."""
    pin = getattr(usage, "prompt_tokens", 0) or 0
    pout = getattr(usage, "completion_tokens", 0) or 0
    details = getattr(usage, "prompt_tokens_details", None)
    cached = (getattr(details, "cached_tokens", 0) or 0) if details is not None else 0
    tier = PRICING["long" if pin > LONG_CTX_THRESHOLD else "short"]
    return (max(pin - cached, 0) * tier["in"] + cached * tier["cached"] + pout * tier["out"]) / 1e6


def gpt5_cost_responses(usage) -> float:
    """gpt5_cost for a Responses-API usage object (input_tokens / output_tokens / cached_tokens)."""
    pin = getattr(usage, "input_tokens", 0) or 0
    pout = getattr(usage, "output_tokens", 0) or 0
    details = getattr(usage, "input_tokens_details", None)
    cached = (getattr(details, "cached_tokens", 0) or 0) if details is not None else 0
    tier = PRICING["long" if pin > LONG_CTX_THRESHOLD else "short"]
    return (max(pin - cached, 0) * tier["in"] + cached * tier["cached"] + pout * tier["out"]) / 1e6


@dataclass(frozen=True)
class LLMConfig:
    """Everything the client needs: model, reasoning effort, retry budget, concurrency gate size."""
    model: str
    effort: str = "medium"
    max_retries: int = 6
    concurrency: int = 192
    max_tool_rounds: int = 4       # cap on tool_call -> tool_result rounds before the structured answer


@dataclass(frozen=True)
class LLMRequest:
    """One structured-output ask: system + user text and the Pydantic schema to parse into.

    ``tools`` (OpenAI tool schema list) and ``dispatch`` (``name, args -> str``) are set only for the
    TOOL variant; when present the client runs a tool_call/tool_result loop before the final parse.
    """
    system: str
    user: str
    schema: type[BaseModel]
    tools: Optional[list] = None
    dispatch: Optional[Callable[[str, dict], str]] = None


@dataclass(frozen=True)
class LLMResult:
    """Parsed output plus the complete request telemetry needed for experiment audit logs."""
    parsed: Optional[BaseModel]
    cost_usd: float
    tool_calls: tuple[str, ...] = ()
    tool_trace: tuple[dict[str, Any], ...] = ()
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    attempts: int = 1
    error: Optional[str] = None


class LLMClient(Protocol):
    """The boundary contract the predictor depends on (one concrete + a test fake implement it)."""

    async def predict_structured(self, request: LLMRequest) -> LLMResult: ...


def _read_env_file(path) -> dict:
    values: dict = {}
    try:
        for raw in Path(path).read_text().splitlines():
            s = raw.strip()
            if s and not s.startswith("#") and "=" in s:
                k, v = s.split("=", 1)
                values[k.replace("export ", "").strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return values


def make_openai_client() -> AsyncOpenAI:
    """OpenAI-direct when OPENAI_API_KEY is set; otherwise the Linq LLM gateway.

    The gateway base_url/key resolve from the environment or the sibling mcp-server/.env, so the
    pipeline runs on machines where only the gateway (not a raw OpenAI key) is provisioned. Falls
    back to a keyless AsyncOpenAI so the openai SDK raises its own clear auth error if neither exists.
    """
    if os.getenv("OPENAI_API_KEY"):
        return AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"), http_client=_http_client(),
                           max_retries=0)
    root = Path(__file__).resolve().parents[2]
    env: dict = {}
    for p in (root / ".env", root.parent / "mcp-server" / ".env", root.parent / "agent-server" / ".env"):
        env.update(_read_env_file(p))
    url = (os.getenv("LLM_GATEWAY_URL") or env.get("LLM_GATEWAY_URL") or "").rstrip("/")
    key = os.getenv("LLM_GATEWAY_API_KEY") or env.get("LLM_GATEWAY_API_KEY")
    if url and key:
        return AsyncOpenAI(api_key=key, base_url=f"{url}/v1", http_client=_http_client(),
                           max_retries=0,
                           default_headers={"x-gw-server": "carbon-arc-kalshi", "x-gw-feature": "prediction"})
    return AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=_REQUEST_TIMEOUT, max_retries=0)


@register_llm("openai")
class OpenAIStructuredClient:
    """AsyncOpenAI structured-parse client: shared semaphore + backoff retry, cost per call."""

    def __init__(self, config: LLMConfig):
        self._config = config
        load_dotenv()                                     # load .env from the project root if present
        self._client = make_openai_client()
        self._semaphore: Optional[asyncio.Semaphore] = None

    async def predict_structured(self, request: LLMRequest) -> LLMResult:
        async with self._gate():
            return await self._parse_with_retry(request)

    async def _parse_with_retry(self, request: LLMRequest) -> LLMResult:
        total_cost = 0.0
        total_input = 0
        total_cached = 0
        total_output = 0
        all_calls: list[str] = []
        all_trace: list[dict[str, Any]] = []
        last_error: Optional[str] = None
        for attempt in range(self._config.max_retries):
            try:
                result = await self._parse_once(request)
                total_cost += result.cost_usd
                total_input += result.input_tokens
                total_cached += result.cached_input_tokens
                total_output += result.output_tokens
                all_calls.extend(result.tool_calls)
                all_trace.extend({"attempt": attempt + 1, **item} for item in result.tool_trace)
                if result.parsed is not None:
                    return replace(
                        result,
                        cost_usd=total_cost,
                        tool_calls=tuple(all_calls),
                        tool_trace=tuple(all_trace),
                        input_tokens=total_input,
                        cached_input_tokens=total_cached,
                        output_tokens=total_output,
                        attempts=attempt + 1,
                    )
                last_error = result.error or "structured output was not returned"
            except Exception as exc:  # transient API/parse failure
                last_error = f"{type(exc).__name__}: {exc}"
            if attempt < self._config.max_retries - 1:
                await asyncio.sleep(2 ** attempt)
        return LLMResult(
            parsed=None,
            cost_usd=total_cost,
            tool_calls=tuple(all_calls),
            tool_trace=tuple(all_trace),
            input_tokens=total_input,
            cached_input_tokens=total_cached,
            output_tokens=total_output,
            attempts=self._config.max_retries,
            error=last_error,
        )

    async def _parse_once(self, request: LLMRequest) -> LLMResult:
        """One structured parse. BASE (no tools) uses chat.completions; the TOOL variant routes to the
        Responses API, because gpt-5.5 rejects function tools + reasoning_effort on chat.completions."""
        if request.tools:
            return await self._parse_once_responses(request)
        messages = [{"role": "system", "content": request.system},
                    {"role": "user", "content": request.user}]
        completion = await self._parse_call(request, messages)
        cost = gpt5_cost(completion.usage)
        parsed = completion.choices[0].message.parsed
        pin, cached, pout = _usage_counts(completion.usage, responses=False)
        return LLMResult(
            parsed=parsed,
            cost_usd=cost,
            input_tokens=pin,
            cached_input_tokens=cached,
            output_tokens=pout,
            error=None if parsed is not None else "chat completion did not contain parsed output",
        )

    async def _parse_once_responses(self, request: LLMRequest) -> LLMResult:
        """TOOL variant on /v1/responses: loop function_call -> function_call_output before the parse.

        The org runs Zero-Data-Retention, so ``previous_response_id`` is unavailable. Each response's
        output items, including encrypted reasoning state and function calls, are therefore carried
        forward explicitly with the function outputs. The prompt remains byte-identical to BASE."""
        input_items: list[Any] = [{"role": "user", "content": request.user}]
        cost = 0.0
        input_tokens = 0
        cached_input_tokens = 0
        output_tokens = 0
        called: list[str] = []
        trace: list[dict[str, Any]] = []
        for _ in range(self._config.max_tool_rounds):
            resp = await self._client.responses.parse(
                model=self._config.model, instructions=request.system, input=input_items,
                text_format=request.schema, reasoning={"effort": self._config.effort},
                tools=request.tools, store=False, include=["reasoning.encrypted_content"])
            cost += gpt5_cost_responses(resp.usage)
            pin, cached, pout = _usage_counts(resp.usage, responses=True)
            input_tokens += pin
            cached_input_tokens += cached
            output_tokens += pout
            if resp.output_parsed is not None:
                return LLMResult(
                    parsed=resp.output_parsed,
                    cost_usd=cost,
                    tool_calls=tuple(called),
                    tool_trace=tuple(trace),
                    input_tokens=input_tokens,
                    cached_input_tokens=cached_input_tokens,
                    output_tokens=output_tokens,
                )
            calls = [it for it in resp.output if getattr(it, "type", None) == "function_call"]
            if not calls or request.dispatch is None:
                break
            input_items.extend(resp.output)
            for c in calls:
                args = json.loads(c.arguments or "{}")
                output = str(request.dispatch(c.name, args))
                called.append(c.name)
                trace.append({"name": c.name, "arguments": args, "output": output})
                input_items.append({"type": "function_call_output", "call_id": c.call_id,
                                    "output": output})
        return LLMResult(
            parsed=None,
            cost_usd=cost,
            tool_calls=tuple(called),
            tool_trace=tuple(trace),
            input_tokens=input_tokens,
            cached_input_tokens=cached_input_tokens,
            output_tokens=output_tokens,
            error="responses tool loop ended without parsed output",
        )

    async def _parse_call(self, request: LLMRequest, messages: list[dict]):
        params: dict[str, Any] = dict(
            model=self._config.model, messages=messages,
            response_format=request.schema, reasoning_effort=self._config.effort)
        if request.tools:
            params["tools"] = request.tools
        return await self._client.beta.chat.completions.parse(**params)

    def _gate(self) -> asyncio.Semaphore:
        if self._semaphore is None:                       # lazy: bind the gate to the active event loop
            self._semaphore = asyncio.Semaphore(self._config.concurrency)
        return self._semaphore


def _append_tool_exchange(messages: list[dict], message, dispatch: Callable[[str, dict], str]) -> None:
    """Append the assistant's tool_calls turn, then one tool-result message per call it made."""
    messages.append({"role": "assistant", "content": message.content,
                     "tool_calls": [tc.model_dump() for tc in message.tool_calls]})
    for call in message.tool_calls:
        args = json.loads(call.function.arguments or "{}")
        result = dispatch(call.function.name, args)
        messages.append({"role": "tool", "tool_call_id": call.id, "content": str(result)})


def _usage_counts(usage, responses: bool) -> tuple[int, int, int]:
    """Normalize Chat Completions and Responses token counters."""
    input_name = "input_tokens" if responses else "prompt_tokens"
    output_name = "output_tokens" if responses else "completion_tokens"
    details_name = "input_tokens_details" if responses else "prompt_tokens_details"
    pin = int(getattr(usage, input_name, 0) or 0)
    pout = int(getattr(usage, output_name, 0) or 0)
    details = getattr(usage, details_name, None)
    cached = int((getattr(details, "cached_tokens", 0) or 0) if details is not None else 0)
    return pin, cached, pout
