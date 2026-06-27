"""
Factor 1 — fetch earnings-call transcripts from S3 (the factor3 SQL path).

Discovery (run once, via linq MCP stock_server_query) → factor1/data/transcript_docs_web.json
(GITIGNORED: holds internal S3 file_keys). Regenerate with the factor3-documented SQL:
  SELECT s.ticker, sd.file_key, sd.fiscal_date, sd.name FROM stock_documents sd
  JOIN stocks s ON s.id = sd.stock_id
  WHERE doc_type='earnings_call' AND file_key LIKE '%_corrected.html'
    AND fiscal_date IS NOT NULL AND name ILIKE '%Earnings Call%'
    AND s.ticker IN (<post-cutoff web tickers>)
  → dump rows as [{"ticker","file_key","name"}, ...] to that JSON.
`fiscal_date IS NOT NULL` isolates real earnings calls from investor-conference talks;
the call DATE is parsed from `name` ("..., Q# YYYY Earnings Call, DD-Month-YYYY").

Download: boto3 (AWS_PROFILE + AWS_S3_BUCKET_NAME from .env — no hardcoded creds/bucket/keys),
key = file_key, html_to_text (s_ae_smoke logic), cache → factor1/data/transcripts/<id>.txt.
Collision guard: PETS/REAL/ZIP S&P tickers also list a same-ticker FOREIGN company; keep only
the intended US issuer by name. OUT: factor1/data/transcript_index_web.csv (ticker,call_date,file_key,path).

Run:  python3 factor1/scripts/f1_03_fetch_transcripts.py
"""
import html as _html
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import boto3
import pandas as pd
from dotenv import load_dotenv

ROOT = Path("/Users/junekwon/Desktop/Projects/carbon_arc")
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from f1_config import DATA  # noqa: E402

TXDIR = DATA / "transcripts"
INDEX = DATA / "transcript_index_web.csv"
DOCS_JSON = DATA / "transcript_docs_web.json"   # gitignored — internal S3 file_keys
BUCKET = os.getenv("AWS_S3_BUCKET_NAME")
PROFILE = os.getenv("AWS_PROFILE")

# Same-ticker foreign-issuer collisions → keep only the intended US company (substring match on name).
US_ONLY = {"PETS": "PetMed", "REAL": "RealReal", "ZIP": "ZipRecruiter"}

_MON = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August",
     "September", "October", "November", "December"], 1)}


def parse_call_date(name: str):
    m = re.search(r"Earnings Call,\s*(\d{1,2})-([A-Za-z]+)-(\d{4})", name)
    if not m:
        return None
    return datetime(int(m.group(3)), _MON[m.group(2)], int(m.group(1))).date()


def html_to_text(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    text = _html.unescape(raw)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def main():
    assert BUCKET, "AWS_S3_BUCKET_NAME not set in .env"
    assert DOCS_JSON.exists(), f"missing {DOCS_JSON} — regenerate via the discovery SQL (see docstring)"
    TXDIR.mkdir(parents=True, exist_ok=True)
    docs = json.load(open(DOCS_JSON))
    s3 = boto3.Session(profile_name=PROFILE).client("s3")

    seen, rows = set(), []
    for d in docs:
        tkr, key, name = d["ticker"], d["file_key"], d["name"]
        if key in seen:
            continue
        if tkr in US_ONLY and US_ONLY[tkr].lower() not in name.lower():
            continue
        cd = parse_call_date(name)
        if cd is None:
            print(f"  [warn] no date parsed: {name}"); continue
        seen.add(key)
        rows.append({"ticker": tkr, "call_date": cd, "file_key": key,
                     "path": str(TXDIR / (key.split("/")[-1] + ".txt"))})
    print(f"docs: {len(rows)} unique transcripts across {len({r['ticker'] for r in rows})} tickers")

    def fetch(r):
        out = Path(r["path"])
        if out.exists() and out.stat().st_size > 500:
            return (r["file_key"], True, "cached")
        try:
            raw = s3.get_object(Bucket=BUCKET, Key=r["file_key"])["Body"].read().decode("utf-8", "replace")
            out.write_text(html_to_text(raw))
            return (r["file_key"], True, f"{out.stat().st_size}b")
        except Exception as e:
            return (r["file_key"], False, f"{type(e).__name__}: {str(e)[:80]}")

    ok = 0
    with ThreadPoolExecutor(max_workers=12) as ex:
        for key, good, msg in ex.map(fetch, rows):
            if good:
                ok += 1
            else:
                print(f"  [FAIL] {key} -> {msg}")
    print(f"downloaded/cached: {ok}/{len(rows)}")

    df = pd.DataFrame([r for r in rows if Path(r["path"]).exists()]).sort_values(["ticker", "call_date"])
    df.to_csv(INDEX, index=False)
    print(f"[written] {INDEX}: {len(df)} rows · {df.call_date.min()}..{df.call_date.max()}")


if __name__ == "__main__":
    main()
