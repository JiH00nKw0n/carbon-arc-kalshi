"""
Factor 1 — self-contained LLM client (gpt-5.5 end-to-end nowcaster).

Reads keys from carbon_arc/.env (OPENAI_API_KEY). No credit-agent / AWS dependency.
Schema + pricing + system prompt are ported verbatim from factor3/scripts/s_ae_smoke.py
so Factor-1 results are directly comparable to Factor-3 (only X changes: card → web).
"""
import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv(Path("/Users/junekwon/Desktop/Projects/carbon_arc/.env"))

GPT_MODEL = os.getenv("GPT_PARSER_MODEL", "gpt-5.5-2026-04-23")
GPT_EFFORT = os.getenv("GPT_REASONING_EFFORT", "medium")
MAX_TRANSCRIPT_CHARS = 48_000

# gpt-5.5 pricing $/1M (OpenAI): SHORT (<=272K input tok) vs LONG (>272K).
PRICING = {"short": {"in": 5.0, "cached": 0.5, "out": 30.0},
           "long":  {"in": 10.0, "cached": 1.0, "out": 45.0}}
LONG_CTX_THRESHOLD = 272_000

SYS = (
    "You are an equity revenue-surprise nowcaster. You only see information available BEFORE the "
    "upcoming quarter's earnings report; you do NOT know the actual result. The target is the REVENUE "
    "surprise = (actual - analyst consensus)/consensus, i.e. the part NOT already priced into estimates. "
    "Score the deviation from consensus expectations, not absolute fundamentals. Be calibrated and "
    "conservative. Output only the requested structured fields."
)


class BPredict(BaseModel):
    """Option B — LLM end-to-end -> predicted revenue surprise %."""
    predicted_revenue_surprise_pct: float = Field(
        description="predicted (actual-consensus)/consensus in percent for the upcoming quarter.")
    confidence: int = Field(description="0..100.")
    rationale: str


class AScores(BaseModel):
    """Option A — LLM reads TEXT (Z) only -> consensus-relative scores (distilled, then OLS)."""
    rev_vs_consensus: int = Field(description="-100..+100: does the call imply NEXT-quarter revenue ABOVE(+)/BELOW(-) sell-side consensus? Headline.")
    news_not_in_consensus: int = Field(description="0..100: how much NEW info (likely not yet in estimates) the call carries.")
    signal_reliability: int = Field(description="0..100: guidance specificity/quantification + management credibility + low hedging.")
    rev_vs_consensus_quote: str = Field(description="one verbatim sentence justifying rev_vs_consensus.")


class CFeatures(BaseModel):
    """Option C — LLM reads web signal (X) + TEXT (Z) -> joint features (distilled, then OLS)."""
    rev_vs_consensus: int = Field(description="-100..+100 vs consensus, reconciling the web-traffic trend and narrative.")
    news_not_in_consensus: int = Field(description="0..100 new info.")
    signal_reliability: int = Field(description="0..100 reliability.")
    web_narrative_consistency: int = Field(description="-100..+100: web-traffic trend vs management story: -100 strong contradiction, +100 strong agreement.")
    rationale: str


def gpt5_cost(usage) -> float:
    pin = getattr(usage, "prompt_tokens", 0) or 0
    pout = getattr(usage, "completion_tokens", 0) or 0
    det = getattr(usage, "prompt_tokens_details", None)
    cached = (getattr(det, "cached_tokens", 0) or 0) if det is not None else 0
    p = PRICING["long" if pin > LONG_CTX_THRESHOLD else "short"]
    return (max(pin - cached, 0) * p["in"] + cached * p["cached"] + pout * p["out"]) / 1e6


async def acall(client, sem, key, schema, user):
    """One gpt-5.5 structured call with retry. Returns (key, parsed_or_None, cost)."""
    async with sem:
        for attempt in range(6):
            try:
                comp = await client.beta.chat.completions.parse(
                    model=GPT_MODEL,
                    messages=[{"role": "system", "content": SYS}, {"role": "user", "content": user}],
                    response_format=schema, reasoning_effort=GPT_EFFORT)
                return key, comp.choices[0].message.parsed, gpt5_cost(comp.usage)
            except Exception:
                if attempt == 5:
                    return key, None, 0.0
                await asyncio.sleep(2 ** attempt)
