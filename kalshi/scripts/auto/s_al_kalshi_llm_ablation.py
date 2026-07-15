#!/usr/bin/env python3
"""
Mini LLM ablation for Kalshi X on the leakage-safe pre-report panel.

Runs four end-to-end BPredict arms:
  fin, fin+kalshi, fin+text, fin+kalshi+text

This is intentionally smaller than the full Factor1 runner because the Kalshi
channel is event-based, not a regular monthly/quarterly X time series yet.
"""
import argparse
import asyncio
import html as _html
import json
import os
import re
import time
import warnings
from pathlib import Path

import asyncpg
import boto3
import numpy as np
import pandas as pd
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

warnings.filterwarnings("ignore", category=FutureWarning, message="ChainedAssignmentError*")

ROOT = Path(__file__).resolve().parents[3]
KALSHI_ROOT = ROOT / "kalshi"
PRE_PANEL = KALSHI_ROOT / "outputs" / "auto" / "kalshi_prereport_x_revsurprise_panel.csv"
Y_PANEL = KALSHI_ROOT / "outputs" / "auto" / "kalshi_stockdb_revenue_surprise_panel.csv"
OUT_CSV = KALSHI_ROOT / "outputs" / "auto" / "kalshi_llm_ablation_preds.csv"
OUT_JSONL = KALSHI_ROOT / "outputs" / "auto" / "kalshi_llm_ablation_run_log.jsonl"
OUT_MD = KALSHI_ROOT / "docs" / "analysis_kalshi_llm_ablation.md"
TX_CACHE = KALSHI_ROOT / "outputs" / "auto" / "kalshi_transcripts"

GPT_MODEL = os.getenv("GPT_PARSER_MODEL", "gpt-5.5-2026-04-23")
GPT_EFFORT = os.getenv("GPT_REASONING_EFFORT", "medium")
MAX_TRANSCRIPT_CHARS = 48_000
LONG_CTX_THRESHOLD = 272_000
PRICING = {
    "short": {"in": 5.0, "cached": 0.5, "out": 30.0},
    "long": {"in": 10.0, "cached": 1.0, "out": 45.0},
}
SYS = (
    "You are an equity revenue-surprise nowcaster. You only see information available BEFORE the "
    "upcoming quarter's earnings report; you do NOT know the actual result. The target is the REVENUE "
    "surprise = (actual - analyst consensus)/consensus, i.e. the part NOT already priced into estimates. "
    "Score the deviation from consensus expectations, not absolute fundamentals. Be calibrated and "
    "conservative. Output only the requested structured fields."
)


class BPredict(BaseModel):
    predicted_revenue_surprise_pct: float = Field(
        description="predicted (actual-consensus)/consensus in percent for the upcoming quarter."
    )
    confidence: int = Field(description="0..100.")
    rationale: str


def rel(path):
    path = Path(path)
    try:
        return path.resolve().relative_to(ROOT)
    except ValueError:
        return path


def read_env(path):
    out = {}
    if not path.exists():
        return out
    for raw in path.read_text().splitlines():
        s = raw.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        out[k.replace("export ", "").strip()] = v.strip().strip('"').strip("'")
    return out


def load_env_values(paths):
    values = {}
    for path in paths:
        values.update(read_env(path))
    return values


def make_openai_client():
    env = load_env_values([
        ROOT / ".env",
        ROOT.parent / "mcp-server" / ".env",
        ROOT.parent / "agent-server" / ".env",
        ROOT.parent / "linq-mcp-server" / ".env.local",
    ])
    gateway_url = (os.getenv("LLM_GATEWAY_URL") or env.get("LLM_GATEWAY_URL") or "").rstrip("/")
    gateway_key = os.getenv("LLM_GATEWAY_API_KEY") or env.get("LLM_GATEWAY_API_KEY")
    if gateway_url and gateway_key:
        return AsyncOpenAI(
            api_key=gateway_key,
            base_url=f"{gateway_url}/v1",
            default_headers={
                "x-gw-server": "carbon-arc-kalshi",
                "x-gw-feature": "kalshi-llm-ablation",
            },
        )
    api_key = os.getenv("OPENAI_API_KEY") or env.get("OPENAI_API_KEY")
    return AsyncOpenAI(api_key=api_key) if api_key else AsyncOpenAI()


def gpt5_cost(usage):
    pin = getattr(usage, "prompt_tokens", 0) or 0
    pout = getattr(usage, "completion_tokens", 0) or 0
    det = getattr(usage, "prompt_tokens_details", None)
    cached = (getattr(det, "cached_tokens", 0) or 0) if det is not None else 0
    price = PRICING["long" if pin > LONG_CTX_THRESHOLD else "short"]
    uncached = max(pin - cached, 0)
    return (uncached * price["in"] + cached * price["cached"] + pout * price["out"]) / 1e6


def stock_env():
    env = read_env(ROOT.parent / "mcp-server" / ".env")
    required = ["STOCK_DB_HOST", "STOCK_DB_PORT", "STOCK_DB_NAME", "STOCK_DB_USER", "STOCK_DB_PASSWORD"]
    missing = [k for k in required if not env.get(k)]
    if missing:
        raise SystemExit(f"missing stock DB env keys: {missing}")
    return env


def configure_s3_env():
    agent = read_env(ROOT.parent / "agent-server" / ".env")
    mcp = read_env(ROOT.parent / "mcp-server" / ".env")
    for k in ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"]:
        if mcp.get(k):
            os.environ[k] = mcp[k]
    if agent.get("AWS_S3_BUCKET_NAME"):
        os.environ["AWS_S3_BUCKET_NAME"] = agent["AWS_S3_BUCKET_NAME"]
    for k in ["AWS_REGION", "AWS_DEFAULT_REGION"]:
        if agent.get(k):
            os.environ[k] = agent[k]
    os.environ.pop("AWS_SESSION_TOKEN", None)
    if not os.getenv("AWS_S3_BUCKET_NAME"):
        raise SystemExit("missing AWS_S3_BUCKET_NAME")


async def fetch_docs(tickers):
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
                   sd.event_start_at::date AS call_date
            FROM stock_documents sd
            JOIN stocks s ON s.id = sd.stock_id
            WHERE s.ticker = ANY($1::text[])
              AND s.is_primary IS TRUE
              AND sd.doc_type = 'earnings_call'
              AND sd.file_key LIKE '%_corrected.html'
              AND sd.fiscal_date IS NOT NULL
              AND sd.event_start_at IS NOT NULL
            ORDER BY s.ticker, call_date, sd.file_key
            """,
            list(tickers),
        )
    finally:
        await conn.close()
    docs = pd.DataFrame([dict(r) for r in rows])
    if docs.empty:
        return docs
    docs["call_date"] = pd.to_datetime(docs["call_date"], errors="coerce")
    docs = docs.drop_duplicates(["ticker", "file_key"]).sort_values(["ticker", "call_date"])
    return docs


def html_to_text(raw):
    raw = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    text = _html.unescape(raw)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def download_text(s3, file_key):
    TX_CACHE.mkdir(parents=True, exist_ok=True)
    out = TX_CACHE / (Path(file_key).name + ".txt")
    if out.exists() and out.stat().st_size > 500:
        return out.read_text(errors="replace")
    obj = s3.get_object(Bucket=os.environ["AWS_S3_BUCKET_NAME"], Key=file_key)
    raw = obj["Body"].read().decode("utf-8", "replace")
    text = html_to_text(raw)
    out.write_text(text)
    return text


def prior_doc(docs, ticker, report_date):
    cutoff = pd.Timestamp(report_date) - pd.Timedelta(days=31)
    cand = docs[(docs["ticker"].eq(ticker)) & (docs["call_date"] <= cutoff)].sort_values("call_date")
    if cand.empty:
        return None
    return cand.iloc[-1].to_dict()


def fin_table(hist, target):
    out = ["fiscal_q_end | actual($M) | consensus($M) | surprise%"]
    for r in hist.tail(6).itertuples():
        out.append(f"{r.FE_FP_END.date()} | {r.ACTUAL:,.0f} | {r.CONS_EARLY:,.0f} | {r.surprise_early*100:+.2f}%")
    out.append(f"{target.FE_FP_END.date()} | (pending) | {target.CONS_EARLY:,.0f} | <- PREDICT")
    return "\n".join(out)


def maybe(v, fmt="{:.4g}"):
    try:
        if pd.isna(v):
            return "n/a"
        return fmt.format(float(v))
    except Exception:
        return "n/a"


def kalshi_table(row):
    lines = [
        "KALSHI PRE-REPORT MARKET SIGNAL:",
        f"as_of_date: {row.pre_as_of_date}",
        f"event_ticker: {row.event_ticker}",
        f"metric: {row.metric_label}",
        f"feature_family: {row.feature_family}",
        f"priced_markets: {int(row.pre_n_priced)}/{int(row.pre_n_markets)}",
        f"pre_implied_value: {maybe(row.pre_implied_value)}",
        f"pre_prob_lowest: {maybe(row.pre_prob_lowest)}",
        f"pre_prob_highest: {maybe(row.pre_prob_highest)}",
        f"pre_volume_sum: {maybe(row.pre_volume_sum)}",
        f"pre_open_interest_sum: {maybe(row.pre_open_interest_sum)}",
    ]
    return "\n".join(lines)


def metrics(pred, true):
    d = pd.DataFrame({"pred": pred, "true": true}).dropna()
    if d.empty:
        return {"n": 0, "rmse": np.nan, "mae": np.nan, "corr": np.nan, "r2": np.nan, "sign": np.nan}
    err = d["pred"] - d["true"]
    sse = float((err ** 2).sum())
    sst = float(((d["true"] - d["true"].mean()) ** 2).sum())
    corr = d["pred"].corr(d["true"]) if len(d) > 1 and d["pred"].std() > 1e-12 else np.nan
    return {
        "n": int(len(d)),
        "rmse": float(np.sqrt((err ** 2).mean())),
        "mae": float(err.abs().mean()),
        "corr": float(corr) if pd.notna(corr) else np.nan,
        "r2": float(1 - sse / sst) if sst > 1e-12 else np.nan,
        "sign": float((np.sign(d["pred"]) == np.sign(d["true"])).mean()),
    }


def common_rmse_delta(out, base_arm, add_arm):
    s = out.dropna(subset=[base_arm, add_arm, "true_pct"])
    if s.empty:
        return 0, np.nan, np.nan, np.nan
    base_rmse = float(np.sqrt(((s[base_arm] - s["true_pct"]) ** 2).mean()))
    add_rmse = float(np.sqrt(((s[add_arm] - s["true_pct"]) ** 2).mean()))
    return int(len(s)), base_rmse, add_rmse, add_rmse - base_rmse


async def bounded_acall(client, sem, key, schema, user, timeout, attempts):
    async with sem:
        for attempt in range(attempts):
            try:
                comp = await asyncio.wait_for(
                    client.beta.chat.completions.parse(
                        model=GPT_MODEL,
                        messages=[{"role": "system", "content": SYS}, {"role": "user", "content": user}],
                        response_format=schema,
                        reasoning_effort=GPT_EFFORT,
                    ),
                    timeout=timeout,
                )
                return key, comp.choices[0].message.parsed, gpt5_cost(comp.usage)
            except Exception as exc:
                if attempt == attempts - 1:
                    print(f"[llm-warning] {key} failed: {type(exc).__name__}", flush=True)
                    return key, None, 0.0
                await asyncio.sleep(2 ** attempt)


async def main_async(args):
    configure_s3_env()
    pre = pd.read_csv(args.pre_panel)
    y = pd.read_csv(args.y_panel)
    for d in (pre, y):
        d["FE_FP_END"] = pd.to_datetime(d["FE_FP_END"], errors="coerce")
        d["REPORT_DATE"] = pd.to_datetime(d["REPORT_DATE"], errors="coerce")
    pre = pre[(pre["REPORT_DATE"] > pd.Timestamp("2025-12-01")) & (pre["pre_n_priced"] > 0)].copy()
    if args.numeric_only:
        pre = pre[pre["feature_family"].eq("numeric_kpi_ladder")].copy()
    if args.limit:
        pre = pre.head(args.limit).copy()

    docs = await fetch_docs(pre["ticker"].dropna().unique())
    s3 = boto3.client("s3", region_name=os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION"))
    targets = []
    for row in pre.sort_values(["REPORT_DATE", "ticker"]).itertuples():
        hist = y[(y["ticker"].eq(row.ticker)) & (y["FE_FP_END"] < row.FE_FP_END)].sort_values("FE_FP_END")
        if len(hist.dropna(subset=["surprise_early"])) < 3:
            continue
        doc = prior_doc(docs, row.ticker, row.REPORT_DATE)
        if doc is None:
            continue
        text = download_text(s3, doc["file_key"])[:MAX_TRANSCRIPT_CHARS]
        targets.append({"row": row, "hist": hist, "doc": doc, "text": text})
        print(f"[target] {row.ticker} {row.FE_FP_END.date()} via {row.event_ticker}", flush=True)

    client = make_openai_client()
    sem = asyncio.Semaphore(args.concurrency)
    jobs = []
    for i, t in enumerate(targets):
        row = t["row"]
        base = (
            f"Company {row.ticker}. Predict the UPCOMING quarter ({row.FE_FP_END.date()}) "
            "REVENUE SURPRISE = (actual - consensus)/consensus, in %. "
            "Use only information available before the earnings report.\n\n"
        )
        fin = "FINANCIAL HISTORY (Stock DB point-in-time consensus):\n" + fin_table(t["hist"], row) + "\n\n"
        kx = kalshi_table(row) + "\n\n"
        tr = "\nPRIOR-QUARTER EARNINGS CALL:\n" + t["text"]
        instr = "Predict the revenue surprise %."
        jobs += [
            bounded_acall(client, sem, (i, "fin"), BPredict, base + fin + instr, args.request_timeout_seconds, args.max_attempts),
            bounded_acall(client, sem, (i, "fin+kalshi"), BPredict, base + fin + kx + instr, args.request_timeout_seconds, args.max_attempts),
            bounded_acall(client, sem, (i, "fin+text"), BPredict, base + fin + instr + tr, args.request_timeout_seconds, args.max_attempts),
            bounded_acall(client, sem, (i, "fin+kalshi+text"), BPredict, base + fin + kx + instr + tr, args.request_timeout_seconds, args.max_attempts),
        ]

    print(f"[run] targets={len(targets)} calls={len(jobs)} model={GPT_MODEL} effort={GPT_EFFORT}", flush=True)
    t0 = time.perf_counter()
    results = []
    for j, fut in enumerate(asyncio.as_completed(jobs), 1):
        results.append(await fut)
        if j % 4 == 0 or j == len(jobs):
            print(f"... {j}/{len(jobs)} calls ({time.perf_counter() - t0:.0f}s)", flush=True)
    res = {k: v for k, v, _ in results}
    cost = sum(c for _, _, c in results)

    rows = []
    args.out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out_jsonl, "w") as log:
        for i, t in enumerate(targets):
            row = t["row"]
            true_pct = float(row.surprise_early) * 100
            item = {
                "ticker": row.ticker,
                "FE_FP_END": row.FE_FP_END.date().isoformat(),
                "REPORT_DATE": row.REPORT_DATE.date().isoformat(),
                "event_ticker": row.event_ticker,
                "metric_label": row.metric_label,
                "feature_family": row.feature_family,
                "true_pct": true_pct,
                "call_date": str(t["doc"]["call_date"].date()),
                "file_key": t["doc"]["file_key"],
            }
            for arm in ["fin", "fin+kalshi", "fin+text", "fin+kalshi+text"]:
                pred = res.get((i, arm))
                item[arm] = pred.predicted_revenue_surprise_pct if pred else np.nan
                item[f"{arm}_confidence"] = pred.confidence if pred else np.nan
                item[f"{arm}_rationale"] = pred.rationale if pred else ""
            rows.append(item)
            log.write(json.dumps(item) + "\n")

    out = pd.DataFrame(rows)
    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.out_csv, index=False)

    arms = ["fin", "fin+kalshi", "fin+text", "fin+kalshi+text"]
    mets = {arm: metrics(out[arm], out["true_pct"]) for arm in arms}
    lines = [
        "# Kalshi pre-report X LLM ablation",
        "",
        f"> Generated by `kalshi/scripts/auto/s_al_kalshi_llm_ablation.py`.",
        "",
        f"- model: `{GPT_MODEL}`",
        f"- reasoning effort: `{GPT_EFFORT}`",
        f"- targets: {len(out):,}",
        f"- calls: {len(jobs):,}",
        f"- estimated cost: ${cost:.2f}",
        f"- feature filter: {'numeric only' if args.numeric_only else 'all pre-report joined features'}",
        "",
        "## Metrics",
        "",
        "| arm | n | RMSE pct | MAE pct | corr | R2 | sign |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for arm in arms:
        m = mets[arm]
        lines.append(
            f"| {arm} | {m['n']} | {m['rmse']:.3f} | {m['mae']:.3f} | "
            f"{m['corr']:+.3f} | {m['r2']:+.3f} | {m['sign']:.3f} |"
        )
    if len(out):
        n_fk, rmse_fin, rmse_fk, delta_fk = common_rmse_delta(out, "fin", "fin+kalshi")
        n_full, rmse_ft, rmse_fkt, delta_full = common_rmse_delta(out, "fin+text", "fin+kalshi+text")
        lines += [
            "",
            "## Common-row Deltas",
            "",
            f"- `fin+kalshi` vs `fin` on common rows (n={n_fk}): {rmse_fk:.3f} - {rmse_fin:.3f} = {delta_fk:+.3f} pct points",
            f"- `fin+kalshi+text` vs `fin+text` on common rows (n={n_full}): {rmse_fkt:.3f} - {rmse_ft:.3f} = {delta_full:+.3f} pct points",
            "",
            "Negative delta means Kalshi improved that comparison.",
        ]
    lines += [
        "",
        f"Predictions CSV: `{rel(args.out_csv)}`",
        f"Run log JSONL: `{rel(args.out_jsonl)}`",
    ]
    args.out_md.write_text("\n".join(lines) + "\n")
    print(f"[written] {args.out_csv}")
    print(f"[written] {args.out_jsonl}")
    print(f"[written] {args.out_md}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pre-panel", type=Path, default=PRE_PANEL)
    ap.add_argument("--y-panel", type=Path, default=Y_PANEL)
    ap.add_argument("--out-csv", type=Path, default=OUT_CSV)
    ap.add_argument("--out-jsonl", type=Path, default=OUT_JSONL)
    ap.add_argument("--out-md", type=Path, default=OUT_MD)
    ap.add_argument("--numeric-only", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--concurrency", type=int, default=16)
    ap.add_argument("--request-timeout-seconds", type=float, default=120)
    ap.add_argument("--max-attempts", type=int, default=1)
    args = ap.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
