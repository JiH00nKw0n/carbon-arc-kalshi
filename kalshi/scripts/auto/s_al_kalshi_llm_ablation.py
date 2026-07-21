#!/usr/bin/env python3
"""Run the four-arm Kalshi raw-ladder LLM experiment.

Arms:
  fin
  fin+kalshi_ladder
  fin+earnings_call
  fin+kalshi_ladder+earnings_call

Each arm is repeated independently. Evaluation uses the mean prediction while
the per-run outputs remain available for model-variance checks.
"""
import argparse
import asyncio
import html as _html
import json
import os
import re
import time
from collections import Counter
from pathlib import Path

import asyncpg
import boto3
import numpy as np
import pandas as pd
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[3]
KALSHI_ROOT = ROOT / "kalshi"
OUTPUTS = KALSHI_ROOT / "outputs" / "auto"
PRE_PANEL = KALSHI_ROOT / "outputs" / "auto" / "kalshi_prereport_ladder_panel.csv"
Y_PANEL = KALSHI_ROOT / "outputs" / "auto" / "kalshi_factset_revenue_surprise_panel.csv"
EARNINGS_CALL_CACHE = KALSHI_ROOT / "outputs" / "auto" / "prior_earnings_call_transcripts"

GPT_MODEL = os.getenv("GPT_PARSER_MODEL", "gpt-5.5-2026-04-23")
GPT_EFFORT = os.getenv("GPT_REASONING_EFFORT", "medium")
MAX_EARNINGS_CALL_CHARS = 48_000
PRIOR_EARNINGS_CALL_COUNT = 2
KNOWLEDGE_CUTOFF = pd.Timestamp("2025-12-01")
HISTORY_ROWS = 6
LONG_CTX_THRESHOLD = 272_000
PRICING = {
    "short": {"in": 5.0, "cached": 0.5, "out": 30.0},
    "long": {"in": 10.0, "cached": 1.0, "out": 45.0},
}
ARMS = [
    "fin",
    "fin+kalshi_ladder",
    "fin+earnings_call",
    "fin+kalshi_ladder+earnings_call",
]
SYS = (
    "You are an equity revenue-surprise nowcaster. You only see information available BEFORE the "
    "upcoming quarter's earnings report; you do NOT know the actual result. The target is the REVENUE "
    "surprise = (actual - analyst consensus)/consensus, i.e. the part NOT already priced into estimates. "
    "Score the deviation from consensus expectations, not absolute fundamentals. Be calibrated and "
    "conservative. Output only the requested structured fields."
)

SYS_YOY = (
    "You are an equity revenue nowcaster. You only see information available BEFORE the upcoming "
    "quarter's earnings report; you do NOT know the actual result. The target is REVENUE YEAR-OVER-YEAR "
    "GROWTH = (actual this quarter - actual in the same quarter last year)/actual last year. "
    "Score the level of growth, not the deviation from consensus. Be calibrated and conservative. "
    "Output only the requested structured fields."
)

# target key -> (truth column, reference column shown as the anchor, system prompt, instruction)
TARGETS = {
    "surprise": (
        "surprise_early",
        "CONS_EARLY",
        SYS,
        "Predict the revenue surprise %.",
    ),
    "yoy": (
        "rev_yoy",
        "cons_early_growth",
        SYS_YOY,
        "Predict the revenue year-over-year growth %.",
    ),
}


def default_output_paths(target):
    return {
        "out_csv": OUTPUTS / f"kalshi_llm_ladder_ablation_{target}_preds.csv",
        "out_jsonl": OUTPUTS / f"kalshi_llm_ladder_ablation_{target}_run_log.jsonl",
        "out_eligible_csv": OUTPUTS / f"kalshi_llm_eligible_targets_{target}.csv",
    }


class SurprisePredict(BaseModel):
    predicted_revenue_surprise_pct: float = Field(
        description="predicted (actual-consensus)/consensus in percent for the upcoming quarter."
    )
    confidence: int = Field(description="0..100.")
    rationale: str


class YoyPredict(BaseModel):
    predicted_revenue_yoy_pct: float = Field(
        description=(
            "predicted (actual-this-quarter minus actual-same-quarter-last-year) "
            "/ actual-same-quarter-last-year in percent."
        )
    )
    confidence: int = Field(description="0..100.")
    rationale: str


PREDICTION_MODELS = {
    "surprise": SurprisePredict,
    "yoy": YoyPredict,
}
PREDICTION_FIELDS = {
    "surprise": "predicted_revenue_surprise_pct",
    "yoy": "predicted_revenue_yoy_pct",
}


def prediction_value(prediction, target):
    return float(getattr(prediction, PREDICTION_FIELDS[target]))


def with_columns(frame, **columns):
    data = {column: frame[column] for column in frame.columns}
    data.update(columns)
    return pd.DataFrame(data, index=frame.index)


def parse_ladders(raw):
    try:
        value = json.loads(raw) if isinstance(raw, str) and raw.strip() else []
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid kalshi_ladders_json: {exc}") from exc
    if not isinstance(value, list):
        raise ValueError("kalshi_ladders_json must be a list")
    return value


def validate_publication_cutoff(panel, label="Kalshi pre-report ladder panel"):
    required = {
        "published_at",
        "pre_as_of_ts",
        "pre_cutoff_source",
        "pre_candle_search_rule",
        "pre_event_count",
        "pre_total_priced_rungs",
        "kalshi_ladders_json",
    }
    missing = sorted(required - set(panel.columns))
    if missing:
        raise SystemExit(
            f"{label} lacks cutoff/provenance fields: {', '.join(missing)}. "
            "Regenerate it with s_ak_kalshi_prereport_features.py."
        )

    problems = []
    for index, row in panel.iterrows():
        raw_event_count = pd.to_numeric(row["pre_event_count"], errors="coerce")
        raw_rung_count = pd.to_numeric(row["pre_total_priced_rungs"], errors="coerce")
        event_count = int(raw_event_count) if pd.notna(raw_event_count) else 0
        rung_count = int(raw_rung_count) if pd.notna(raw_rung_count) else 0
        if event_count == 0 and rung_count == 0:
            continue
        published_at = pd.to_datetime(row["published_at"], errors="coerce", utc=True)
        as_of_ts = pd.to_numeric(row["pre_as_of_ts"], errors="coerce")
        if (
            pd.isna(published_at)
            or pd.isna(as_of_ts)
            or row["pre_cutoff_source"] != "published_at_minus_buffer"
            or row["pre_candle_search_rule"] != "market_open_to_publication_cutoff"
            or float(as_of_ts) >= published_at.timestamp()
        ):
            problems.append(f"row {index}: invalid publication cutoff")
            continue
        try:
            ladders = parse_ladders(row["kalshi_ladders_json"])
        except ValueError as exc:
            problems.append(f"row {index}: {exc}")
            continue
        if len(ladders) != event_count:
            problems.append(f"row {index}: event count mismatch")
        actual_rungs = 0
        for ladder in ladders:
            rungs = ladder.get("rungs") if isinstance(ladder, dict) else None
            if not isinstance(rungs, list) or len(rungs) < 2:
                problems.append(f"row {index}: event with fewer than two rungs")
                continue
            actual_rungs += len(rungs)
            for rung in rungs:
                candle_ts = pd.to_numeric(rung.get("candle_ts"), errors="coerce")
                market_open_at = pd.to_datetime(
                    rung.get("market_open_at"), errors="coerce", utc=True
                )
                probability = pd.to_numeric(rung.get("probability"), errors="coerce")
                if (
                    pd.isna(candle_ts)
                    or float(candle_ts) > float(as_of_ts)
                    or float(candle_ts) >= published_at.timestamp()
                    or pd.isna(market_open_at)
                    or float(candle_ts) < market_open_at.timestamp()
                ):
                    problems.append(f"row {index}: rung at/after cutoff")
                if pd.isna(probability) or not 0 <= float(probability) <= 1:
                    problems.append(f"row {index}: invalid rung probability")
                if not rung.get("price_source"):
                    problems.append(f"row {index}: missing rung price source")
        if actual_rungs != rung_count:
            problems.append(f"row {index}: rung count mismatch")
    if problems:
        sample = "; ".join(problems[:8])
        raise SystemExit(f"{label} failed provenance validation ({len(problems)} issue(s)): {sample}")


def read_env(path):
    values = {}
    if not path.exists():
        return values
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.replace("export ", "").strip()] = value.strip().strip('"').strip("'")
    return values


def server_env_paths():
    return [
        ROOT.parent / "mcp-server" / ".env",
        ROOT.parent / "agent-server" / ".env",
        ROOT.parent / "analytics-server" / ".env",
        ROOT.parent / "linq-mcp-server" / ".env.local",
        ROOT / ".env",
    ]


def server_env():
    values = {}
    for path in server_env_paths():
        for key, value in read_env(path).items():
            values.setdefault(key, value)
    for key, value in os.environ.items():
        if value:
            values[key] = value
    return values


def aws_credentials():
    process = {
        key: os.getenv(key, "")
        for key in [
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_SESSION_TOKEN",
        ]
    }
    if process["AWS_ACCESS_KEY_ID"] and process["AWS_SECRET_ACCESS_KEY"]:
        return process
    for path in server_env_paths():
        values = read_env(path)
        if values.get("AWS_ACCESS_KEY_ID") and values.get("AWS_SECRET_ACCESS_KEY"):
            return {
                "AWS_ACCESS_KEY_ID": values["AWS_ACCESS_KEY_ID"],
                "AWS_SECRET_ACCESS_KEY": values["AWS_SECRET_ACCESS_KEY"],
                "AWS_SESSION_TOKEN": values.get("AWS_SESSION_TOKEN", ""),
            }
    return {}


def make_openai_client():
    env = server_env()
    gateway_url = (os.getenv("LLM_GATEWAY_URL") or env.get("LLM_GATEWAY_URL") or "").rstrip("/")
    gateway_key = os.getenv("LLM_GATEWAY_API_KEY") or env.get("LLM_GATEWAY_API_KEY")
    if gateway_url and gateway_key:
        return AsyncOpenAI(
            api_key=gateway_key,
            base_url=f"{gateway_url}/v1",
            default_headers={
                "x-gw-server": "kalshi-experiment",
                "x-gw-feature": "raw-ladder-ablation",
            },
        )
    api_key = os.getenv("OPENAI_API_KEY") or env.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("missing LLM_GATEWAY_URL/API_KEY or OPENAI_API_KEY")
    return AsyncOpenAI(api_key=api_key)


def gpt_cost(usage):
    prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
    output_tokens = getattr(usage, "completion_tokens", 0) or 0
    details = getattr(usage, "prompt_tokens_details", None)
    cached_tokens = (getattr(details, "cached_tokens", 0) or 0) if details else 0
    price = PRICING["long" if prompt_tokens > LONG_CTX_THRESHOLD else "short"]
    uncached_tokens = max(prompt_tokens - cached_tokens, 0)
    return (
        uncached_tokens * price["in"]
        + cached_tokens * price["cached"]
        + output_tokens * price["out"]
    ) / 1e6


def stock_env():
    env = server_env()
    required = [
        "STOCK_DB_HOST",
        "STOCK_DB_PORT",
        "STOCK_DB_NAME",
        "STOCK_DB_USER",
        "STOCK_DB_PASSWORD",
    ]
    missing = [key for key in required if not env.get(key)]
    if missing:
        raise SystemExit(f"missing stock DB env keys: {missing}")
    return env


def configure_s3_env():
    env = server_env()
    credentials = aws_credentials()
    for key in ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"]:
        if credentials.get(key):
            os.environ[key] = credentials[key]
    if credentials.get("AWS_SESSION_TOKEN"):
        os.environ["AWS_SESSION_TOKEN"] = credentials["AWS_SESSION_TOKEN"]
    else:
        os.environ.pop("AWS_SESSION_TOKEN", None)
    for key in ["AWS_REGION", "AWS_DEFAULT_REGION", "AWS_S3_BUCKET_NAME"]:
        if env.get(key):
            os.environ[key] = env[key]
    if not os.getenv("AWS_S3_BUCKET_NAME"):
        raise SystemExit("missing AWS_S3_BUCKET_NAME")


async def fetch_earnings_call_docs(tickers):
    env = stock_env()
    conn = await asyncpg.connect(
        host=env["STOCK_DB_HOST"],
        port=int(env["STOCK_DB_PORT"]),
        database=env["STOCK_DB_NAME"],
        user=env["STOCK_DB_USER"],
        password=env["STOCK_DB_PASSWORD"],
        timeout=20,
    )
    try:
        rows = await conn.fetch(
            """
            SELECT DISTINCT
                   s.ticker,
                   sd.file_key,
                   sd.name,
                   sd.fiscal_date,
                   COALESCE(sd.calendar_date, sd.fiscal_date) AS period_end_date,
                   sd.event_start_at AS call_at
            FROM stock_documents sd
            JOIN stocks s ON s.id = sd.stock_id
            WHERE s.ticker = ANY($1::text[])
              AND s.is_primary IS TRUE
              AND sd.doc_type = 'earnings_call'
              AND sd.file_key LIKE '%_corrected.html'
              AND sd.fiscal_date IS NOT NULL
              AND sd.event_start_at IS NOT NULL
            ORDER BY s.ticker, period_end_date, call_at, sd.file_key
            """,
            list(tickers),
        )
    finally:
        await conn.close()
    docs = pd.DataFrame([dict(row) for row in rows])
    if docs.empty:
        return docs
    docs = with_columns(
        docs,
        fiscal_date=pd.to_datetime(docs["fiscal_date"], errors="coerce"),
        period_end_date=pd.to_datetime(docs["period_end_date"], errors="coerce"),
        call_at=pd.to_datetime(docs["call_at"], errors="coerce", utc=True),
    )
    return docs.drop_duplicates(["ticker", "file_key"]).sort_values(
        ["ticker", "period_end_date", "call_at"]
    )


def html_to_text(raw):
    raw = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    text = _html.unescape(raw)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def cache_earnings_call_text(s3, file_key):
    EARNINGS_CALL_CACHE.mkdir(parents=True, exist_ok=True)
    output = EARNINGS_CALL_CACHE / f"{Path(file_key).name}.txt"
    if output.exists() and output.stat().st_size > 500:
        return output.read_text(errors="replace")
    response = s3.get_object(Bucket=os.environ["AWS_S3_BUCKET_NAME"], Key=file_key)
    raw = response["Body"].read().decode("utf-8", "replace")
    text = html_to_text(raw)
    output.write_text(text)
    return text


def prior_earnings_call_candidates(
    docs,
    ticker,
    prediction_cutoff,
    target_period_end=None,
    call_limit=PRIOR_EARNINGS_CALL_COUNT,
):
    if docs.empty:
        return docs
    cutoff = pd.Timestamp(prediction_cutoff)
    if pd.isna(cutoff):
        return docs.iloc[0:0].copy()
    if cutoff.tzinfo is None:
        cutoff = cutoff.tz_localize("UTC")
    else:
        cutoff = cutoff.tz_convert("UTC")
    eligible = docs["ticker"].eq(ticker) & (docs["call_at"] < cutoff)
    if target_period_end is not None:
        target_period = pd.Timestamp(target_period_end).normalize()
        eligible &= docs["period_end_date"] < target_period
    candidates = docs[eligible].copy()
    if candidates.empty:
        return candidates
    candidates = with_columns(
        candidates,
        _call_period=candidates["period_end_date"].dt.normalize(),
    )
    candidates = candidates.dropna(subset=["_call_period"]).sort_values(
        ["call_at", "period_end_date", "file_key"],
        ascending=[False, False, False],
    )
    recent_periods = candidates["_call_period"].drop_duplicates().head(call_limit)
    return candidates[candidates["_call_period"].isin(recent_periods)].copy()


def load_prior_earnings_calls(s3, candidates, max_chars):
    calls = []
    last_error = None
    for _, group in candidates.groupby("_call_period", sort=False):
        selected = None
        for candidate in group.to_dict("records"):
            try:
                text = cache_earnings_call_text(s3, candidate["file_key"])
                selected = {
                    "doc": candidate,
                    "text": text[:max_chars],
                }
                break
            except Exception as exc:
                last_error = exc
        if selected is None:
            return [], last_error
        calls.append(selected)
    calls.sort(key=lambda call: call["doc"]["call_at"])
    return calls, last_error


def earnings_call_block(calls):
    sections = []
    for call in calls:
        doc = call["doc"]
        period_end = pd.Timestamp(doc["period_end_date"]).date().isoformat()
        call_at = pd.Timestamp(doc["call_at"]).isoformat()
        sections.append(
            f"[EARNINGS CALL period_end={period_end} held_at={call_at}]\n{call['text']}"
        )
    return "\n\n".join(sections)


def earnings_call_metadata(calls):
    period_ends = [
        pd.Timestamp(call["doc"]["period_end_date"]).date().isoformat()
        for call in calls
    ]
    held_ats = [pd.Timestamp(call["doc"]["call_at"]).isoformat() for call in calls]
    return {
        "earnings_call_count": len(calls),
        "earnings_call_period_ends": "|".join(period_ends),
        "earnings_call_held_ats": "|".join(held_ats),
        "earnings_call_period_end": period_ends[-1] if period_ends else "",
    }


def format_number(value, digits=4):
    try:
        if value is None or pd.isna(value):
            return "n/a"
        return f"{float(value):.{digits}g}"
    except (TypeError, ValueError):
        return "n/a"


def fin_table(history, target, target_key="surprise"):
    """Financial history H. The anchor column and the outcome column both follow the target:
    for `surprise` the anchor is the consensus level, for `yoy` it is consensus-implied growth."""
    if target_key == "yoy":
        lines = ["fiscal_q_end | actual($M) | yr-ago actual($M) | revenue YoY%"]
        for row in history.tail(HISTORY_ROWS).itertuples():
            prior = getattr(row, "actual_q4", None)
            prior_text = f"{prior:,.0f}" if prior is not None and pd.notna(prior) else "n/a"
            lines.append(
                f"{row.FE_FP_END.date()} | {row.ACTUAL:,.0f} | {prior_text} | "
                f"{row.rev_yoy * 100:+.2f}%"
            )
        anchor = getattr(target, "cons_early_growth", None)
        anchor_text = (
            f"consensus-implied YoY {anchor * 100:+.2f}%"
            if anchor is not None and pd.notna(anchor)
            else "consensus-implied YoY n/a"
        )
        lines.append(f"{target.FE_FP_END.date()} | (pending) | {anchor_text} | <- PREDICT")
        return "\n".join(lines)

    lines = ["fiscal_q_end | actual($M) | consensus($M) | surprise%"]
    for row in history.tail(HISTORY_ROWS).itertuples():
        lines.append(
            f"{row.FE_FP_END.date()} | {row.ACTUAL:,.0f} | {row.CONS_EARLY:,.0f} | "
            f"{row.surprise_early * 100:+.2f}%"
        )
    lines.append(
        f"{target.FE_FP_END.date()} | (pending) | {target.CONS_EARLY:,.0f} | <- PREDICT"
    )
    return "\n".join(lines)


def kalshi_ladder_table(history, target):
    lines = [
        "KALSHI RAW PRE-PUBLICATION KPI MARKET LADDERS:",
        (
            "Probability selection: YES bid/ask midpoint only for a spread <= 0.20; "
            "otherwise the candle's last trade, then previous trade."
        ),
        (
            "These are raw, uncalibrated binary-market observations. They were not "
            "monotonic-smoothed or integrated into a scalar. No settled outcome is shown."
        ),
    ]
    periods = [(row, "historical") for row in history.tail(HISTORY_ROWS).itertuples(index=False)]
    periods.append((target, "upcoming"))
    for row, role in periods:
        lines += [
            "",
            f"fiscal_q_end: {row.FE_FP_END.date()} ({role})",
            f"cutoff_utc: {row.pre_as_of_at}",
        ]
        for ladder in parse_ladders(row.kalshi_ladders_json):
            lines += [
                f"event: {ladder['event_ticker']}",
                f"KPI: {ladder.get('metric_label') or 'unknown'}",
                f"period: {ladder.get('period_label') or 'unknown'}",
                (
                    f"coverage: {ladder['n_priced_rungs']}/{ladder['n_ladder_markets']} rungs; "
                    f"raw monotonicity violations: {ladder['monotonicity_violations']}"
                ),
                (
                    "market | YES condition | probability | source | bid / ask / last / previous "
                    "| spread | candle_utc | daily_volume | open_interest"
                ),
            ]
            for rung in ladder["rungs"]:
                quote = " / ".join(
                    format_number(rung.get(key), 3)
                    for key in ["yes_bid", "yes_ask", "last", "previous"]
                )
                lines.append(
                    f"{rung['market_ticker']} | KPI {rung['threshold_operator']} "
                    f"{rung['strike']:,.6g} | {rung['probability']:.3f} | "
                    f"{rung['price_source']} | {quote} | "
                    f"{format_number(rung.get('spread'), 3)} | {rung['candle_at']} | "
                    f"{format_number(rung.get('daily_volume'))} | "
                    f"{format_number(rung.get('open_interest'))}"
                )
    return "\n".join(lines)


async def bounded_call(
    client,
    semaphore,
    key,
    prompt,
    timeout,
    attempts,
    system_prompt,
    response_format,
):
    async with semaphore:
        for attempt in range(attempts):
            try:
                completion = await asyncio.wait_for(
                    client.beta.chat.completions.parse(
                        model=GPT_MODEL,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt},
                        ],
                        response_format=response_format,
                        reasoning_effort=GPT_EFFORT,
                    ),
                    timeout=timeout,
                )
                return (
                    key,
                    completion.choices[0].message.parsed,
                    gpt_cost(completion.usage),
                    "",
                )
            except Exception as exc:
                if attempt == attempts - 1:
                    return key, None, 0.0, f"{type(exc).__name__}: {str(exc)[:200]}"
                await asyncio.sleep(2**attempt)


def build_prompts(target, target_key="surprise"):
    row = target["row"]
    if target_key == "yoy":
        intro = (
            f"Company {row.ticker}. Predict the UPCOMING quarter ({row.FE_FP_END.date()}) REVENUE "
            "YEAR-OVER-YEAR GROWTH = (actual - actual same quarter last year)/actual last year, in %.\n\n"
        )
    else:
        intro = (
            f"Company {row.ticker}. Predict the UPCOMING quarter ({row.FE_FP_END.date()}) REVENUE SURPRISE "
            "= (actual - consensus)/consensus, in %.\n\n"
        )
    financials = (
        "FINANCIAL HISTORY (FactSet, public):\n"
        + fin_table(target["history"], row, target_key)
        + "\n\n"
    )
    ladder = kalshi_ladder_table(target["ladder_history"], row) + "\n\n"
    earnings_call = (
        "\nPRIOR EARNINGS CALLS (oldest to newest):\n"
        + earnings_call_block(target["earnings_calls"])
    )
    instruction = TARGETS[target_key][3]
    return {
        "fin": intro + financials + instruction,
        "fin+kalshi_ladder": intro + financials + ladder + instruction,
        "fin+earnings_call": intro + financials + instruction + earnings_call,
        "fin+kalshi_ladder+earnings_call": (
            intro + financials + ladder + instruction + earnings_call
        ),
    }


def load_successful_calls(path, target):
    path = Path(path)
    if not path.exists():
        return {}
    calls = {}
    with path.open() as source:
        for line in source:
            record = json.loads(line)
            if record.get("target") != target or record.get("prediction") is None:
                continue
            key = (
                record["ticker"],
                record["FE_FP_END"],
                record["arm"],
                int(record["repeat"]),
            )
            prediction_model = PREDICTION_MODELS[target]
            calls[key] = (
                prediction_model(
                    **{
                        PREDICTION_FIELDS[target]: float(record["prediction"]),
                        "confidence": int(record["confidence"]),
                        "rationale": record.get("rationale", ""),
                    }
                ),
                float(record.get("estimated_cost_usd", 0.0)),
                "",
            )
    return calls


async def main_async(args):
    target_key = args.target
    truth_column, _reference_column, system_prompt, _instruction = TARGETS[target_key]
    prediction_model = PREDICTION_MODELS[target_key]
    configure_s3_env()
    pre_all = pd.read_csv(args.pre_panel)
    y_panel = pd.read_csv(args.y_panel)
    validate_publication_cutoff(pre_all)
    pre_all = with_columns(
        pre_all,
        FE_FP_END=pd.to_datetime(pre_all["FE_FP_END"], errors="coerce"),
        REPORT_DATE=pd.to_datetime(pre_all["REPORT_DATE"], errors="coerce"),
        published_at=pd.to_datetime(pre_all["published_at"], errors="coerce", utc=True),
    )
    y_panel = with_columns(
        y_panel,
        FE_FP_END=pd.to_datetime(y_panel["FE_FP_END"], errors="coerce"),
        REPORT_DATE=pd.to_datetime(y_panel["REPORT_DATE"], errors="coerce"),
    )
    covered = pre_all[
        pd.to_numeric(pre_all["pre_event_count"], errors="coerce").fillna(0).gt(0)
    ].copy()
    pre = covered[covered["REPORT_DATE"] > KNOWLEDGE_CUTOFF].copy()
    if args.evaluation_start:
        pre = pre[pre["REPORT_DATE"] >= pd.Timestamp(args.evaluation_start)]
    pre = pre.sort_values(["REPORT_DATE", "ticker"]).copy()
    assert (pre["REPORT_DATE"] > KNOWLEDGE_CUTOFF).all(), "LLM KNOWLEDGE-CUTOFF GUARD"

    docs = await fetch_earnings_call_docs(pre["ticker"].dropna().unique())
    s3 = boto3.client(
        "s3", region_name=os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
    )
    targets = []
    skip_reasons = Counter()
    for row in pre.itertuples(index=False):
        history = y_panel[
            y_panel["ticker"].eq(row.ticker)
            & (y_panel["FE_FP_END"] < row.FE_FP_END)
        ].sort_values("FE_FP_END")
        history = history.dropna(subset=["ACTUAL", truth_column])
        if len(history) < 3:
            skip_reasons["fewer_than_3_history_rows"] += 1
            continue
        ladder_history = covered[
            covered["ticker"].eq(row.ticker)
            & (covered["FE_FP_END"] < row.FE_FP_END)
            & (covered["published_at"] < row.published_at)
        ].sort_values("FE_FP_END")
        call_candidates = prior_earnings_call_candidates(
            docs,
            row.ticker,
            row.pre_as_of_at,
            target_period_end=row.FE_FP_END,
        )
        if (
            call_candidates.empty
            or call_candidates["_call_period"].nunique()
            < PRIOR_EARNINGS_CALL_COUNT
        ):
            skip_reasons["fewer_than_2_prior_earnings_calls"] += 1
            continue
        earnings_calls, last_error = load_prior_earnings_calls(
            s3, call_candidates, args.max_earnings_call_chars
        )
        if len(earnings_calls) != PRIOR_EARNINGS_CALL_COUNT:
            error_code = (
                getattr(last_error, "response", {})
                .get("Error", {})
                .get("Code", "")
                if last_error
                else ""
            )
            print(
                f"[document-warning] {row.ticker}: "
                f"{type(last_error).__name__ if last_error else 'unknown'}"
                f"{':' + error_code if error_code else ''}",
                flush=True,
            )
            skip_reasons["earnings_call_fetch_failed"] += 1
            continue
        targets.append(
            {
                "row": row,
                "history": history,
                "ladder_history": ladder_history,
                "earnings_calls": earnings_calls,
            }
        )
        print(
            f"[target] {row.ticker} {row.FE_FP_END.date()} "
            f"events={row.pre_event_count} rungs={row.pre_total_priced_rungs}",
            flush=True,
        )
        if args.limit and len(targets) >= args.limit:
            break

    if args.eligibility_only:
        eligible_rows = []
        for target in targets:
            row = target["row"]
            eligible_rows.append(
                {
                    "target": target_key,
                    "truth_column": truth_column,
                    "ticker": row.ticker,
                    "FE_FP_END": row.FE_FP_END.date().isoformat(),
                    "FISCAL_YEAR": int(row.FISCAL_YEAR),
                    "FISCAL_QUARTER": int(row.FISCAL_QUARTER),
                    "REPORT_DATE": row.REPORT_DATE.date().isoformat(),
                    "kalshi_event_count": int(row.pre_event_count),
                    "kalshi_priced_rungs": int(row.pre_total_priced_rungs),
                    "financial_history_quarters": len(target["history"]),
                    "kalshi_history_quarters": min(
                        len(target["ladder_history"]), HISTORY_ROWS
                    ),
                    **earnings_call_metadata(target["earnings_calls"]),
                }
            )
        eligible = pd.DataFrame(eligible_rows)
        args.out_eligible_csv.parent.mkdir(parents=True, exist_ok=True)
        eligible.to_csv(args.out_eligible_csv, index=False)
        print(
            f"[eligible] targets={len(eligible)} "
            f"tickers={eligible['ticker'].nunique() if not eligible.empty else 0} "
            f"excluded={dict(skip_reasons)}",
            flush=True,
        )
        print(f"[written] {args.out_eligible_csv}", flush=True)
        return

    prompts = [build_prompts(target, target_key) for target in targets]
    client = make_openai_client()
    semaphore = asyncio.Semaphore(args.concurrency)
    prior_calls = (
        load_successful_calls(args.out_jsonl, target_key) if args.resume else {}
    )
    result_map = {}
    jobs = []
    for target_index, prompt_set in enumerate(prompts):
        row = targets[target_index]["row"]
        for arm in ARMS:
            for repeat in range(1, args.repeats + 1):
                prior_key = (
                    row.ticker,
                    row.FE_FP_END.date().isoformat(),
                    arm,
                    repeat,
                )
                if prior_key in prior_calls:
                    result_map[(target_index, arm, repeat)] = prior_calls[prior_key]
                    continue
                jobs.append(
                    bounded_call(
                        client,
                        semaphore,
                        (target_index, arm, repeat),
                        prompt_set[arm],
                        args.request_timeout_seconds,
                        args.max_attempts,
                        system_prompt,
                        prediction_model,
                    )
                )

    total_calls = len(targets) * len(ARMS) * args.repeats
    print(
        f"[run] targets={len(targets)} arms={len(ARMS)} repeats={args.repeats} "
        f"calls={total_calls} pending={len(jobs)} model={GPT_MODEL} effort={GPT_EFFORT}",
        flush=True,
    )
    started = time.perf_counter()
    results = []
    for completed, future in enumerate(asyncio.as_completed(jobs), 1):
        results.append(await future)
        if completed % 8 == 0 or completed == len(jobs):
            print(
                f"... {completed}/{len(jobs)} calls "
                f"({time.perf_counter() - started:.0f}s)",
                flush=True,
            )

    result_map.update(
        {key: (prediction, cost, error) for key, prediction, cost, error in results}
    )
    total_cost = sum(cost for _, cost, _ in result_map.values())
    output_rows = []
    args.out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out_jsonl, "w") as log:
        for target_index, target in enumerate(targets):
            row = target["row"]
            item = {
                "target": target_key,
                "truth_column": truth_column,
                "ticker": row.ticker,
                "FE_FP_END": row.FE_FP_END.date().isoformat(),
                "FISCAL_YEAR": int(row.FISCAL_YEAR),
                "FISCAL_QUARTER": int(row.FISCAL_QUARTER),
                "REPORT_DATE": row.REPORT_DATE.date().isoformat(),
                "published_at": row.published_at.isoformat(),
                "kalshi_event_count": int(row.pre_event_count),
                "kalshi_priced_rungs": int(row.pre_total_priced_rungs),
                "kalshi_history_quarters": min(len(target["ladder_history"]), HISTORY_ROWS),
                "kalshi_event_tickers": row.kalshi_event_tickers,
                "true_pct": float(getattr(row, truth_column)) * 100.0,
                **earnings_call_metadata(target["earnings_calls"]),
            }
            for arm in ARMS:
                values = []
                confidences = []
                for repeat in range(1, args.repeats + 1):
                    prediction, cost, error = result_map.get(
                        (target_index, arm, repeat), (None, 0.0, "missing result")
                    )
                    value = prediction_value(prediction, target_key) if prediction else np.nan
                    item[f"{arm}__r{repeat}"] = value
                    if prediction:
                        values.append(value)
                        confidences.append(float(prediction.confidence))
                    log.write(
                        json.dumps(
                            {
                                "target": target_key,
                                "ticker": row.ticker,
                                "FE_FP_END": row.FE_FP_END.date().isoformat(),
                                "arm": arm,
                                "repeat": repeat,
                                "model": GPT_MODEL,
                                "reasoning_effort": GPT_EFFORT,
                                "prediction": value if np.isfinite(value) else None,
                                "confidence": prediction.confidence if prediction else None,
                                "rationale": prediction.rationale if prediction else "",
                                "estimated_cost_usd": cost,
                                "error": error,
                            },
                            ensure_ascii=True,
                        )
                        + "\n"
                    )
                item[arm] = float(np.mean(values)) if values else np.nan
                item[f"{arm}_run_sd"] = (
                    float(np.std(values, ddof=1))
                    if len(values) > 1
                    else 0.0
                    if values
                    else np.nan
                )
                item[f"{arm}_successful_repeats"] = len(values)
                item[f"{arm}_confidence"] = (
                    float(np.mean(confidences)) if confidences else np.nan
                )
            output_rows.append(item)

    output = pd.DataFrame(output_rows)
    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(args.out_csv, index=False)
    print(f"[written] {args.out_csv}")
    print(f"[written] {args.out_jsonl}")
    print(
        f"targets={len(output)} calls={total_calls} "
        f"successful={sum(output[f'{arm}_successful_repeats'].sum() for arm in ARMS)} "
        f"estimated_cost_usd={total_cost:.2f} excluded={dict(skip_reasons)}"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pre-panel", type=Path, default=PRE_PANEL)
    parser.add_argument("--y-panel", type=Path, default=Y_PANEL)
    parser.add_argument("--out-csv", type=Path)
    parser.add_argument("--out-jsonl", type=Path)
    parser.add_argument("--out-eligible-csv", type=Path)
    parser.add_argument("--eligibility-only", action="store_true")
    parser.add_argument("--evaluation-start", default="")
    parser.add_argument(
        "--target",
        choices=sorted(TARGETS),
        default="surprise",
        help=(
            "Prediction target. `surprise` = (actual - consensus)/consensus, which matches the "
            "paper's Figure 4 analyst-consensus comparison. `yoy` = revenue year-over-year growth, "
            "which is what the paper's Table 1 synergy results are computed on. The two are not "
            "comparable: YoY is autocorrelated and scores a far higher R2 than the surprise residual."
        ),
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=3,
        help="Independent calls per arm and target; the paper reports their mean.",
    )
    parser.add_argument(
        "--max-earnings-call-chars",
        type=int,
        default=MAX_EARNINGS_CALL_CHARS,
        help=(
            "Truncation length for the Z transcript. The 48,000 default is an SSOT constant "
            "from EXPERIMENT_SPEC.md so every X channel gets identical Z treatment; it is not a "
            "context or cost limit (longest transcript is ~27.5k tokens against a 272k threshold). "
            "Raise it to test whether truncating away the Q&A section is what makes the call arm hurt."
        ),
    )
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--concurrency", type=int, default=16)
    parser.add_argument("--request-timeout-seconds", type=float, default=180)
    parser.add_argument("--max-attempts", type=int, default=2)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse successful calls in the existing JSONL and retry only missing calls.",
    )
    args = parser.parse_args()
    for name, path in default_output_paths(args.target).items():
        if getattr(args, name) is None:
            setattr(args, name, path)
    if args.repeats < 1:
        raise SystemExit("--repeats must be at least 1")
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
