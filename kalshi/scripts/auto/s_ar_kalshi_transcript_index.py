#!/usr/bin/env python3
"""Build transcript_index_kalshi.csv for the prediction/ `kalshi` channel.

prediction/data/transcripts.TranscriptStore reads a per-channel index with columns
(ticker, call_date, path) and picks the most-recent call on/before report-31d. Our cached
transcripts are named by document id, so this maps each cached file back to (ticker, call_date)
via the Stock DB (same query s_al uses), keying on file_key.

Reads the Stock DB creds from mcp-server/.env (never prints values). Emits only rows whose cached
transcript file actually exists on disk.
"""
import asyncio
from pathlib import Path

import asyncpg
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
CACHE = ROOT / "kalshi" / "outputs" / "auto" / "prior_earnings_call_transcripts"
REVENUE = ROOT / "kalshi" / "outputs" / "auto" / "kalshi_factset_revenue_surprise_panel.csv"
OUT = ROOT / "kalshi" / "outputs" / "auto" / "transcript_index_kalshi.csv"
MCP_ENV = ROOT.parent / "mcp-server" / ".env"

QUERY = """
    SELECT DISTINCT s.ticker, sd.file_key, sd.event_start_at::date AS call_date
    FROM stock_documents sd
    JOIN stocks s ON s.id = sd.stock_id
    WHERE s.ticker = ANY($1::text[])
      AND s.is_primary IS TRUE
      AND sd.doc_type = 'earnings_call'
      AND sd.file_key LIKE '%_corrected.html'
      AND sd.event_start_at IS NOT NULL
    ORDER BY s.ticker, call_date
"""


def _env(path):
    out = {}
    for raw in Path(path).read_text().splitlines():
        s = raw.strip()
        if s and not s.startswith("#") and "=" in s:
            k, v = s.split("=", 1)
            out[k.replace("export ", "").strip()] = v.strip().strip('"').strip("'")
    return out


async def _fetch(tickers):
    env = _env(MCP_ENV)
    conn = await asyncpg.connect(
        host=env["STOCK_DB_HOST"], port=int(env["STOCK_DB_PORT"]), database=env["STOCK_DB_NAME"],
        user=env["STOCK_DB_USER"], password=env["STOCK_DB_PASSWORD"], timeout=20,
    )
    try:
        return await conn.fetch(QUERY, tickers)
    finally:
        await conn.close()


def main():
    tickers = sorted(pd.read_csv(REVENUE)["ticker"].dropna().unique().tolist())
    rows = asyncio.run(_fetch(tickers))
    index = []
    for r in rows:
        cache_file = CACHE / (Path(r["file_key"]).name + ".txt")
        if cache_file.exists():
            index.append({"ticker": r["ticker"], "call_date": r["call_date"], "path": str(cache_file)})
    frame = pd.DataFrame(index).drop_duplicates(["ticker", "call_date"]).sort_values(["ticker", "call_date"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUT, index=False)
    cached = len(list(CACHE.glob("*.txt")))
    print(f"[db] {len(rows)} earnings-call docs for {len(tickers)} tickers")
    print(f"[index] {len(frame)} rows / {frame['ticker'].nunique()} tickers matched to cached files "
          f"(cache has {cached} files)")
    print(f"[written] {OUT}")


if __name__ == "__main__":
    main()
