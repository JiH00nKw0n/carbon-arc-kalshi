"""
Foot Traffic — fetch earnings-call transcripts from S3 (for foot-traffic 10-ticker universe).

Hard-coded transcript manifest (from S3 ls run):
  CMG, COST, DG, DLTR, DRI, EAT, MCD, ROST, SBUX, ULTA

Reads AWS creds from /Users/suminkim/LinqAlpha/1_linq-platform/agent-server/.env
Reads OPENAI_API_KEY from /Users/suminkim/LinqAlpha/.env (not used here; just noted)

Steps:
  1. Download HTML from S3: stock_files/{TICKER}/earnings_call/{id}_corrected.html
  2. HTML → plain text (strip script/style tags, unescape HTML entities)
  3. Parse call_date from document title / first ~200 chars:
     "Q? YYYY Earnings Call, DD-Month-YYYY"  or  "Month DD, YYYY"
  4. Save to data/transcripts/{ticker}_{id}.txt
  5. Write data/transcript_index_foot.csv: [ticker, call_date, file_key, path]

If call_date cannot be parsed, sort by file ID within ticker (larger ID = more recent)
and leave call_date as NaT (downstream code will skip or handle).

Run:  python3 ft_03_fetch_transcripts.py
"""
import html as _html
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import boto3
import pandas as pd
from dotenv import load_dotenv

# ── paths ─────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]       # factor1_traffic/
DATA = ROOT / "data"
TXDIR = DATA / "transcripts"
INDEX = DATA / "transcript_index_foot.csv"

# ── credentials ───────────────────────────────────────────────────────────────
ENV_AWS = Path("/Users/suminkim/LinqAlpha/1_linq-platform/agent-server/.env")
load_dotenv(ENV_AWS, override=False)
if not os.getenv("AWS_DEFAULT_REGION"):
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

assert os.getenv("AWS_ACCESS_KEY_ID"), f"AWS_ACCESS_KEY_ID not found in {ENV_AWS}"
assert os.getenv("AWS_SECRET_ACCESS_KEY"), f"AWS_SECRET_ACCESS_KEY not found in {ENV_AWS}"

BUCKET = os.getenv("AWS_S3_BUCKET_NAME")
assert BUCKET, f"AWS_S3_BUCKET_NAME not found in {ENV_AWS} (set it in the .env file)"

# ── transcript manifest (from S3 ls) ─────────────────────────────────────────
MANIFEST: dict[str, list[str]] = {
    "CMG":  ["1203887836", "1204007467", "1204171749"],
    "COST": ["1204007421", "1204039129", "1204039132", "1204083190", "1204091225",
             "1204156646", "1204305075", "1204329479"],
    "DG":   ["1203479059", "1203834039", "1203933447", "1203933448", "1203972808",
             "1204100898", "1204194323", "1204271172"],
    "DLTR": ["1203857469", "1203899680", "1203993236", "1204119117", "1204280961"],
    "DRI":  ["1203867628", "1203995047", "1204114292", "1204321885"],
    "EAT":  ["1203333571", "1203577209", "1203577210", "1203671257", "1204054533",
             "1204069562", "1204116352", "1204276832"],
    "MCD":  ["1203802035", "1203919728", "1204052983", "1204216349"],
    "ROST": ["1203848511", "1203972933", "1204109709", "1204281589"],
    "SBUX": ["1203937437", "1204054490", "1204062159", "1204232694", "1204311531",
             "1204327694"],
    "ULTA": ["1203758877", "1203873261", "1203873380", "1203896480", "1204095427",
             "1204208168", "1204232137", "1204327589"],
}

# ── month name → int ──────────────────────────────────────────────────────────
_MON = {m.lower(): i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June",
     "July", "August", "September", "October", "November", "December"], 1)}
_MON3 = {m[:3].lower(): v for m, v in _MON.items()}


def parse_call_date(text: str):
    """Try multiple date patterns in the first 500 chars of the text."""
    head = text[:500]

    # Pattern 1: "DD-Month-YYYY"  (e.g.  25-April-2024)
    m = re.search(r"(\d{1,2})-([A-Za-z]+)-(\d{4})", head)
    if m:
        mon = _MON.get(m.group(2).lower()) or _MON3.get(m.group(2).lower()[:3])
        if mon:
            return datetime(int(m.group(3)), mon, int(m.group(1))).date()

    # Pattern 2: "Month DD, YYYY"  (e.g.  April 25, 2024)
    m = re.search(r"([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})", head)
    if m:
        mon = _MON.get(m.group(1).lower()) or _MON3.get(m.group(1).lower()[:3])
        if mon:
            return datetime(int(m.group(3)), mon, int(m.group(2))).date()

    # Pattern 3: ISO YYYY-MM-DD
    m = re.search(r"(20\d{2})-(\d{2})-(\d{2})", head)
    if m:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).date()

    return None


def html_to_text(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    text = _html.unescape(raw)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def main():
    TXDIR.mkdir(parents=True, exist_ok=True)

    s3 = boto3.client(
        "s3",
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
    )

    # Build flat list of (ticker, file_id, s3_key, local_path)
    jobs = []
    for tkr, ids in MANIFEST.items():
        for fid in ids:
            key = f"stock_files/{tkr}/earnings_call/{fid}_corrected.html"
            out = TXDIR / f"{tkr}_{fid}.txt"
            jobs.append({"ticker": tkr, "file_id": fid, "file_key": key, "path": str(out)})

    print(f"Total transcripts to fetch: {len(jobs)}")

    def fetch(j):
        out = Path(j["path"])
        if out.exists() and out.stat().st_size > 500:
            txt = out.read_text()
            return j, True, "cached", txt
        try:
            body = s3.get_object(Bucket=BUCKET, Key=j["file_key"])["Body"].read().decode("utf-8", "replace")
            txt = html_to_text(body)
            out.write_text(txt)
            return j, True, f"{out.stat().st_size}b", txt
        except Exception as e:
            return j, False, f"{type(e).__name__}: {str(e)[:100]}", ""

    ok = 0
    rows = []
    with ThreadPoolExecutor(max_workers=16) as ex:
        for j, good, msg, txt in ex.map(fetch, jobs):
            if good:
                ok += 1
                cd = parse_call_date(txt) if txt else None
                rows.append({
                    "ticker": j["ticker"],
                    "file_id": j["file_id"],
                    "call_date": cd,
                    "file_key": j["file_key"],
                    "path": j["path"],
                })
            else:
                print(f"  [FAIL] {j['file_key']} -> {msg}")

    print(f"Downloaded / cached: {ok}/{len(jobs)}")

    # Sort by ticker, then file_id (ascending = oldest first within ticker)
    # For rows where call_date is None, keep position by file_id order
    df = pd.DataFrame(rows)
    df["file_id_int"] = df["file_id"].astype(int)
    df = df.sort_values(["ticker", "file_id_int"]).drop(columns=["file_id_int"])

    no_date = df["call_date"].isna().sum()
    if no_date:
        print(f"  [warn] call_date could not be parsed for {no_date} transcripts (will be NaT)")

    df.to_csv(INDEX, index=False)
    print(f"[written] {INDEX}: {len(df)} rows")
    if df["call_date"].notna().any():
        print(f"  date range: {df['call_date'].min()} .. {df['call_date'].max()}")
    print(df[["ticker", "call_date", "file_key"]].to_string(index=False))


if __name__ == "__main__":
    main()
