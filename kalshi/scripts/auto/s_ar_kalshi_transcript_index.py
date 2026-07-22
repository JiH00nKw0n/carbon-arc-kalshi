#!/usr/bin/env python3
"""Cache corrected earnings calls and build the Kalshi transcript index.

The FactSet revenue panel is the identity source: its selected Stock DB ``stock_id`` values avoid
ambiguous ticker joins. Every corrected earnings-call document for those stocks is indexed; missing
text is fetched from the internal S3 bucket and converted from HTML to plain text. The prediction
pipeline independently applies the benchmark's report-minus-31-days embargo and two-call cap.
"""
from __future__ import annotations

import argparse
import asyncio
import html
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import asyncpg
import boto3
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
CACHE = ROOT / "kalshi" / "outputs" / "auto" / "prior_earnings_call_transcripts"
REVENUE = ROOT / "kalshi" / "outputs" / "auto" / "kalshi_prereport_ladder_panel_firmscreened.csv"
OUT = ROOT / "kalshi" / "outputs" / "auto" / "transcript_index_kalshi.csv"
ENV_PATHS = [
    ROOT.parent / "mcp-server" / ".env",
    ROOT.parent / "agent-server" / ".env",
    ROOT.parent / "agent-server" / ".claude" / ".env.db-credentials",
    ROOT.parent / "analytics-server" / ".env",
    ROOT.parent / "linq-mcp-server" / ".env.local",
    ROOT / ".env",
]

QUERY = """
    SELECT sd.stock_id, sd.file_key, sd.event_start_at::date AS call_date
    FROM stock_documents sd
    WHERE sd.stock_id = ANY($1::text[])
      AND sd.doc_type = 'earnings_call'
      AND sd.file_key LIKE '%_corrected.html'
      AND sd.event_start_at IS NOT NULL
      AND sd.fiscal_date IS NOT NULL
    ORDER BY sd.stock_id, call_date, sd.file_key
"""


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return values
    for raw in lines:
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.replace("export ", "").strip()] = value.strip().strip('"').strip("'")
    return values


def server_env() -> dict[str, str]:
    values: dict[str, str] = {}
    for path in ENV_PATHS:
        for key, value in read_env(path).items():
            values.setdefault(key, value)
    values.update({key: value for key, value in os.environ.items() if value})
    return values


def aws_credentials() -> dict[str, str]:
    process = {key: os.getenv(key, "") for key in (
        "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"
    )}
    if process["AWS_ACCESS_KEY_ID"] and process["AWS_SECRET_ACCESS_KEY"]:
        return process
    for path in ENV_PATHS:
        values = read_env(path)
        if values.get("AWS_ACCESS_KEY_ID") and values.get("AWS_SECRET_ACCESS_KEY"):
            return {key: values.get(key, "") for key in process}
    return {}


def revenue_identities(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, usecols=["ticker", "stock_id"])
    frame = frame.dropna().drop_duplicates()
    duplicates = frame.groupby("ticker")["stock_id"].nunique()
    if (duplicates > 1).any():
        raise RuntimeError(f"multiple stock IDs for ticker(s): {duplicates[duplicates > 1].index.tolist()}")
    return frame


async def fetch_documents(identities: pd.DataFrame, env: dict[str, str]) -> pd.DataFrame:
    required = ["STOCK_DB_HOST", "STOCK_DB_PORT", "STOCK_DB_NAME", "STOCK_DB_USER", "STOCK_DB_PASSWORD"]
    missing = [key for key in required if not env.get(key)]
    if missing:
        raise RuntimeError(f"missing Stock DB settings: {missing}")
    conn = await asyncpg.connect(
        host=env["STOCK_DB_HOST"], port=int(env["STOCK_DB_PORT"]),
        database=env["STOCK_DB_NAME"], user=env["STOCK_DB_USER"],
        password=env["STOCK_DB_PASSWORD"], timeout=20,
    )
    try:
        rows = await conn.fetch(QUERY, identities["stock_id"].tolist())
    finally:
        conn.terminate()
    docs = pd.DataFrame([dict(row) for row in rows])
    return docs.merge(identities, on="stock_id", how="inner") if len(docs) else docs


def html_to_text(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    text = html.unescape(raw)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def cache_path(file_key: str) -> Path:
    return CACHE / f"{Path(file_key).name}.txt"


def cache_document(s3, bucket: str, file_key: str) -> tuple[str, str]:
    output = cache_path(file_key)
    if output.exists() and output.stat().st_size > 500:
        return file_key, "cached"
    response = s3.get_object(Bucket=bucket, Key=file_key)
    raw = response["Body"].read().decode("utf-8", "replace")
    text = html_to_text(raw)
    if len(text) <= 500:
        raise RuntimeError(f"transcript too short after HTML conversion: {file_key}")
    output.write_text(text)
    return file_key, "fetched"


def cache_documents(docs: pd.DataFrame, env: dict[str, str], workers: int) -> dict[str, str]:
    CACHE.mkdir(parents=True, exist_ok=True)
    credentials = aws_credentials()
    bucket = env.get("AWS_S3_BUCKET_NAME", "")
    if not bucket or not credentials.get("AWS_ACCESS_KEY_ID"):
        raise RuntimeError("missing AWS S3 bucket or one complete AWS credential bundle")
    session = boto3.Session(
        aws_access_key_id=credentials["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=credentials["AWS_SECRET_ACCESS_KEY"],
        aws_session_token=credentials.get("AWS_SESSION_TOKEN") or None,
        region_name=env.get("AWS_REGION") or env.get("AWS_DEFAULT_REGION") or "us-east-1",
    )
    s3 = session.client("s3")
    outcomes: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(cache_document, s3, bucket, key): key
                   for key in docs["file_key"].drop_duplicates()}
        for future in as_completed(futures):
            key = futures[future]
            try:
                _, outcomes[key] = future.result()
            except Exception as exc:
                outcomes[key] = f"error: {exc}"
    return outcomes


def write_index(docs: pd.DataFrame, outcomes: dict[str, str], path: Path) -> pd.DataFrame:
    usable = docs[docs["file_key"].map(lambda key: not outcomes.get(key, "error").startswith("error"))].copy()
    usable = usable.assign(
        path=usable["file_key"].map(lambda key: str(cache_path(key))),
        call_date=pd.to_datetime(usable["call_date"]),
    )
    index = (usable.sort_values(["ticker", "call_date", "file_key"])
             .drop_duplicates(["ticker", "call_date"], keep="last")
             [["ticker", "call_date", "path"]])
    path.parent.mkdir(parents=True, exist_ok=True)
    index.to_csv(path, index=False)
    return index


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--revenue", type=Path, default=REVENUE)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--no-fetch", action="store_true", help="Index only files already in the cache.")
    args = parser.parse_args()

    identities = revenue_identities(args.revenue)
    env = server_env()
    docs = asyncio.run(fetch_documents(identities, env))
    if args.no_fetch:
        outcomes = {key: ("cached" if cache_path(key).exists() else "error: not cached")
                    for key in docs["file_key"].drop_duplicates()}
    else:
        outcomes = cache_documents(docs, env, args.workers)
    index = write_index(docs, outcomes, args.out)

    errors = [value for value in outcomes.values() if value.startswith("error")]
    print(f"[documents] {len(docs)} rows / {docs['ticker'].nunique()} tickers")
    print(f"[cache] fetched={sum(v == 'fetched' for v in outcomes.values())} "
          f"reused={sum(v == 'cached' for v in outcomes.values())} errors={len(errors)}")
    print(f"[index] {len(index)} calls / {index['ticker'].nunique()} tickers -> {args.out}")
    if errors:
        raise SystemExit(f"failed to cache {len(errors)} transcript(s); first error: {errors[0]}")


if __name__ == "__main__":
    main()
