#!/usr/bin/env python3
"""Build the Kalshi revenue-surprise panel directly from FactSet FE_V4.

Financial values come from the FactSet Snowflake tables used by the Carbon Arc
benchmark. Stock DB is used only for ticker-to-FactSet-ID mapping and company
fiscal labels.

CONS_EARLY is the latest quarterly SALES consensus snapshot with
CONS_END_DATE <= fiscal quarter end + 7 days. CONS_PRINT is the latest snapshot
with CONS_END_DATE < REPORT_DATE.
"""

import argparse
import asyncio
import hashlib
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from urllib import request

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
KALSHI_ROOT = ROOT / "kalshi"
FEATURES = KALSHI_ROOT / "outputs" / "auto" / "kalshi_company_event_features.csv"
OUT_CSV = KALSHI_ROOT / "outputs" / "auto" / "kalshi_factset_revenue_surprise_panel.csv"
AUDIT_JSON = KALSHI_ROOT / "outputs" / "auto" / "kalshi_factset_query_audit.json"

FACTSET_MCP_URL = os.getenv("FACTSET_MCP_URL", "http://mcp.linqalpha.stag/mcp")
EARLY_DAYS = 7
FACTSET_ROW_LIMIT = 500

DEFAULT_ENV_PATHS = [
    ROOT.parent / "mcp-server" / ".env",
    ROOT.parent / "agent-server" / ".env",
    ROOT.parent / "agent-server" / ".claude" / ".env.db-credentials",
    ROOT.parent / "analytics-server" / ".env",
    ROOT.parent / "linq-mcp-server" / ".env.local",
]

REQUIRED_ENV = [
    "STOCK_DB_HOST",
    "STOCK_DB_PORT",
    "STOCK_DB_NAME",
    "STOCK_DB_USER",
    "STOCK_DB_PASSWORD",
]


def load_env(paths):
    env = {}
    for path in paths:
        if not path.exists():
            continue
        for raw in path.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[len("export ") :].strip()
            key, val = line.split("=", 1)
            env.setdefault(key.strip(), val.strip().strip('"').strip("'"))
    for key in REQUIRED_ENV:
        if os.getenv(key):
            env[key] = os.environ[key]
    missing = [key for key in REQUIRED_ENV if not env.get(key)]
    if missing:
        raise SystemExit(f"missing stock DB env keys: {missing}")
    return env


def load_tickers(path):
    if not path.exists():
        raise SystemExit(f"features CSV missing: {path}")
    features = pd.read_csv(path)
    if "feature_family" in features.columns:
        features = features[features["feature_family"].eq("kpi_ladder")].copy()
    tickers = sorted(
        str(ticker).strip().upper()
        for ticker in features.get("matched_ticker", pd.Series(dtype=str))
        .dropna()
        .unique()
        if str(ticker).strip()
    )
    if not tickers:
        raise SystemExit(f"no matched tickers in {path}")
    return tickers


def with_columns(frame, **columns):
    data = {column: frame[column] for column in frame.columns}
    data.update(columns)
    return pd.DataFrame(data, index=frame.index)


def parse_mcp_response(body):
    envelopes = []
    stripped = body.strip()
    if stripped.startswith("{"):
        envelopes.append(json.loads(stripped))
    else:
        for line in body.splitlines():
            if line.startswith("data: "):
                envelopes.append(json.loads(line[len("data: ") :]))
    if not envelopes:
        raise RuntimeError("FactSet MCP returned no JSON-RPC payload")
    envelope = envelopes[-1]
    if envelope.get("error"):
        raise RuntimeError(f"FactSet MCP error: {envelope['error']}")
    content = envelope.get("result", {}).get("content", [])
    text_blocks = [
        block.get("text", "") for block in content if block.get("type") == "text"
    ]
    if not text_blocks:
        raise RuntimeError("FactSet MCP returned no text content")
    payload = json.loads(text_blocks[0])
    if not payload.get("success"):
        raise RuntimeError(f"FactSet query failed: {payload.get('error', payload)}")
    return payload


def call_mcp_tool(url, name, arguments, timeout_seconds):
    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
            "id": 1,
        }
    ).encode("utf-8")
    req = request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    opener = request.build_opener(request.ProxyHandler({}))
    with opener.open(req, timeout=timeout_seconds) as response:
        return parse_mcp_response(response.read().decode("utf-8"))


def factset_sql(fsym_ids, start_date):
    for fsym_id in fsym_ids:
        if not fsym_id.endswith("-R") or not fsym_id[:-2].isalnum():
            raise ValueError(f"invalid FactSet regional ID: {fsym_id}")
    ids = ", ".join(f"'{fsym_id}'" for fsym_id in fsym_ids)
    return f"""
WITH actuals_ranked AS (
    SELECT FSYM_ID,
           FE_FP_END,
           ACTUAL_VALUE,
           REPORT_DATE,
           PUBLICATION_DATE,
           CURRENCY,
           ACTUAL_FLAG_CODE,
           ROW_NUMBER() OVER (
               PARTITION BY FSYM_ID, FE_FP_END
               ORDER BY PUBLICATION_DATE DESC NULLS LAST,
                        ADJDATE DESC NULLS LAST,
                        ACTUAL_VALUE DESC NULLS LAST
           ) AS actual_rn
    FROM FACTSET_LISTING.FE_V4.FE_BASIC_ACT_QF
    WHERE FSYM_ID IN ({ids})
      AND FE_ITEM = 'SALES'
      AND FE_FP_END >= '{start_date.isoformat()}'
      AND ACTUAL_VALUE IS NOT NULL
      AND REPORT_DATE IS NOT NULL
),
actuals AS (
    SELECT *
    FROM actuals_ranked
    WHERE actual_rn = 1
),
early_ranked AS (
    SELECT a.FSYM_ID,
           a.FE_FP_END,
           c.FE_MEAN,
           c.CONS_START_DATE,
           c.CONS_END_DATE,
           c.FE_NUM_EST,
           c.CURRENCY,
           ROW_NUMBER() OVER (
               PARTITION BY a.FSYM_ID, a.FE_FP_END
               ORDER BY c.CONS_END_DATE DESC,
                        c.CONS_START_DATE DESC,
                        c.FE_NUM_EST DESC NULLS LAST
           ) AS consensus_rn
    FROM actuals a
    JOIN FACTSET_LISTING.FE_V4.FE_BASIC_CONH_QF c
      ON c.FSYM_ID = a.FSYM_ID
     AND c.FE_ITEM = 'SALES'
     AND c.FE_FP_END = a.FE_FP_END
     AND c.CONS_END_DATE <= DATEADD(day, {EARLY_DAYS}, a.FE_FP_END)
),
print_ranked AS (
    SELECT a.FSYM_ID,
           a.FE_FP_END,
           c.FE_MEAN,
           c.CONS_START_DATE,
           c.CONS_END_DATE,
           c.FE_NUM_EST,
           c.CURRENCY,
           ROW_NUMBER() OVER (
               PARTITION BY a.FSYM_ID, a.FE_FP_END
               ORDER BY c.CONS_END_DATE DESC,
                        c.CONS_START_DATE DESC,
                        c.FE_NUM_EST DESC NULLS LAST
           ) AS consensus_rn
    FROM actuals a
    JOIN FACTSET_LISTING.FE_V4.FE_BASIC_CONH_QF c
      ON c.FSYM_ID = a.FSYM_ID
     AND c.FE_ITEM = 'SALES'
     AND c.FE_FP_END = a.FE_FP_END
     AND c.CONS_END_DATE < a.REPORT_DATE
)
SELECT a.FSYM_ID,
       a.FE_FP_END,
       a.REPORT_DATE,
       a.PUBLICATION_DATE,
       a.ACTUAL_VALUE AS ACTUAL,
       a.CURRENCY AS ACTUAL_CURRENCY,
       a.ACTUAL_FLAG_CODE,
       early.FE_MEAN AS CONS_EARLY,
       early.CONS_START_DATE AS CONS_EARLY_START_DATE,
       early.CONS_END_DATE AS CONS_EARLY_DATE,
       early.FE_NUM_EST AS CONS_EARLY_N,
       early.CURRENCY AS CONS_EARLY_CURRENCY,
       printed.FE_MEAN AS CONS_PRINT,
       printed.CONS_START_DATE AS CONS_PRINT_START_DATE,
       printed.CONS_END_DATE AS CONS_PRINT_DATE,
       printed.FE_NUM_EST AS CONS_PRINT_N,
       printed.CURRENCY AS CONS_PRINT_CURRENCY
FROM actuals a
LEFT JOIN early_ranked early
  ON early.FSYM_ID = a.FSYM_ID
 AND early.FE_FP_END = a.FE_FP_END
 AND early.consensus_rn = 1
LEFT JOIN print_ranked printed
  ON printed.FSYM_ID = a.FSYM_ID
 AND printed.FE_FP_END = a.FE_FP_END
 AND printed.consensus_rn = 1
ORDER BY a.FSYM_ID, a.FE_FP_END
LIMIT {FACTSET_ROW_LIMIT}
""".strip()


def normalize_factset_rows(rows):
    return [
        {key: None if value == "NULL" else value for key, value in row.items()}
        for row in rows
    ]


def fetch_factset_panel(args, fsym_ids):
    rows = []
    audit_batches = []
    for offset in range(0, len(fsym_ids), args.batch_size):
        batch = fsym_ids[offset : offset + args.batch_size]
        sql = factset_sql(batch, args.start_date)
        result = call_mcp_tool(
            args.mcp_url,
            "factset_query",
            {"sql": sql, "max_rows": FACTSET_ROW_LIMIT},
            args.mcp_timeout_seconds,
        )
        batch_rows = normalize_factset_rows(result.get("rows", []))
        if len(batch_rows) >= FACTSET_ROW_LIMIT:
            raise RuntimeError(
                f"FactSet batch hit the {FACTSET_ROW_LIMIT}-row cap: {batch}"
            )
        rows.extend(batch_rows)
        audit_batches.append(
            {
                "fsym_ids": batch,
                "row_count": len(batch_rows),
                "sql_sha256": hashlib.sha256(sql.encode("utf-8")).hexdigest(),
            }
        )
        print(
            f"[factset] batch={offset // args.batch_size + 1} "
            f"ids={len(batch)} rows={len(batch_rows)}",
            flush=True,
        )
    audit = {
        "source": "FACTSET_LISTING.FE_V4 direct via factset_query",
        "mcp_url": args.mcp_url,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "start_date": args.start_date.isoformat(),
        "early_rule": "latest CONS_END_DATE <= FE_FP_END + 7 days",
        "print_rule": "latest CONS_END_DATE < REPORT_DATE",
        "fsym_id_count": len(fsym_ids),
        "row_count": len(rows),
        "batches": audit_batches,
    }
    return pd.DataFrame(rows), audit


async def fetch_stock_metadata(args, tickers, env):
    import asyncpg

    conn = await asyncpg.connect(
        host=env["STOCK_DB_HOST"],
        port=int(env["STOCK_DB_PORT"]),
        database=env["STOCK_DB_NAME"],
        user=env["STOCK_DB_USER"],
        password=env["STOCK_DB_PASSWORD"],
        timeout=20,
        command_timeout=args.query_timeout_seconds,
    )
    try:
        stock_rows = await conn.fetch(
            """
            SELECT DISTINCT ON (ticker)
                   ticker,
                   id AS stock_id,
                   name AS stock_name,
                   exchange,
                   country,
                   market_cap,
                   fsym_regional_id
            FROM stocks
            WHERE ticker = ANY($1::text[])
            ORDER BY ticker,
                     CASE WHEN is_primary IS TRUE THEN 0
                          WHEN is_primary IS NULL THEN 1 ELSE 2 END,
                     market_cap DESC NULLS LAST,
                     id
            """,
            tickers,
        )
        stocks = pd.DataFrame([dict(row) for row in stock_rows])
        if stocks.empty:
            return stocks, pd.DataFrame()
        document_rows = []
        stock_ids = stocks["stock_id"].tolist()
        for offset in range(0, len(stock_ids), 10):
            batch = stock_ids[offset:offset + 10]
            rows = await conn.fetch(
                """
                SELECT sd.stock_id,
                       COALESCE(sd.calendar_date, sd.fiscal_date) AS "FE_FP_END",
                       sd.name
                FROM stock_documents sd
                WHERE sd.stock_id = ANY($1::text[])
                  AND sd.doc_type = 'earnings_call'
                  AND COALESCE(sd.calendar_date, sd.fiscal_date) >= $2::date
                  AND sd.name IS NOT NULL
                  AND sd.name ~* 'Q[1-4][ ,/-]*20[0-9]{2}'
                """,
                batch,
                args.start_date,
                timeout=args.query_timeout_seconds,
            )
            document_rows.extend(rows)
            print(f"[stock-db] documents batch={offset // 10 + 1} "
                  f"stocks={len(batch)} rows={len(rows)}", flush=True)
    finally:
        conn.terminate()
    return stocks, pd.DataFrame([dict(row) for row in document_rows])


def fiscal_period_map(documents):
    if documents.empty:
        return pd.DataFrame(
            columns=["stock_id", "FE_FP_END", "FISCAL_YEAR", "FISCAL_QUARTER"]
        )
    parsed = documents.copy()
    labels = (
        parsed["name"].fillna("").str.extract(r"(?i)\bQ([1-4])\s*[,/-]?\s*(20\d{2})\b")
    )
    parsed = with_columns(
        parsed,
        FISCAL_QUARTER=pd.to_numeric(labels[0], errors="coerce"),
        FISCAL_YEAR=pd.to_numeric(labels[1], errors="coerce"),
    ).dropna(subset=["FISCAL_YEAR", "FISCAL_QUARTER"])
    counts = (
        parsed.groupby(
            ["stock_id", "FE_FP_END", "FISCAL_YEAR", "FISCAL_QUARTER"],
            as_index=False,
        )
        .size()
        .sort_values(
            ["stock_id", "FE_FP_END", "size", "FISCAL_YEAR", "FISCAL_QUARTER"],
            ascending=[True, True, False, False, False],
        )
    )
    return (
        counts.groupby(["stock_id", "FE_FP_END"], as_index=False)
        .head(1)
        .drop(columns="size")
    )


def assemble_panel(factset, stocks, fiscal_documents):
    if factset.empty:
        return factset
    panel = factset.rename(
        columns={
            "FSYM_ID": "fsym_regional_id",
            "PUBLICATION_DATE": "published_at",
        }
    )
    panel = with_columns(
        panel,
        FE_FP_END=pd.to_datetime(panel["FE_FP_END"], errors="coerce"),
        REPORT_DATE=pd.to_datetime(panel["REPORT_DATE"], errors="coerce"),
        published_at=pd.to_datetime(panel["published_at"], errors="coerce", utc=True),
    )
    stock_map = stocks.dropna(subset=["fsym_regional_id"]).copy()
    if stock_map["fsym_regional_id"].duplicated().any():
        duplicates = sorted(
            stock_map.loc[
                stock_map["fsym_regional_id"].duplicated(keep=False), "fsym_regional_id"
            ].unique()
        )
        raise RuntimeError(
            f"duplicate FactSet regional IDs in stock mapping: {duplicates}"
        )
    panel = panel.merge(
        stock_map,
        on="fsym_regional_id",
        how="left",
        validate="many_to_one",
    )
    if panel["ticker"].isna().any():
        missing = sorted(panel.loc[panel["ticker"].isna(), "fsym_regional_id"].unique())
        raise RuntimeError(f"FactSet rows missing ticker mapping: {missing}")
    fiscal_periods = fiscal_period_map(fiscal_documents)
    if not fiscal_periods.empty:
        fiscal_periods = with_columns(
            fiscal_periods,
            FE_FP_END=pd.to_datetime(fiscal_periods["FE_FP_END"], errors="coerce"),
        )
        panel = panel.merge(
            fiscal_periods,
            on=["stock_id", "FE_FP_END"],
            how="left",
            validate="many_to_one",
        )
    currency_mismatch = panel[
        panel["CONS_EARLY"].notna()
        & panel["ACTUAL_CURRENCY"].notna()
        & panel["CONS_EARLY_CURRENCY"].notna()
        & panel["ACTUAL_CURRENCY"].ne(panel["CONS_EARLY_CURRENCY"])
    ]
    if not currency_mismatch.empty:
        raise RuntimeError(
            "FactSet actual/early-consensus currency mismatch for "
            f"{currency_mismatch[['ticker', 'FE_FP_END']].to_dict('records')}"
        )
    columns = [
        "ticker",
        "stock_id",
        "stock_name",
        "exchange",
        "country",
        "fsym_regional_id",
        "FE_FP_END",
        "FISCAL_YEAR",
        "FISCAL_QUARTER",
        "REPORT_DATE",
        "published_at",
        "ACTUAL",
        "ACTUAL_CURRENCY",
        "ACTUAL_FLAG_CODE",
        "CONS_EARLY",
        "CONS_EARLY_START_DATE",
        "CONS_EARLY_DATE",
        "CONS_EARLY_N",
        "CONS_EARLY_CURRENCY",
        "CONS_PRINT",
        "CONS_PRINT_START_DATE",
        "CONS_PRINT_DATE",
        "CONS_PRINT_N",
        "CONS_PRINT_CURRENCY",
    ]
    return panel[[column for column in columns if column in panel]].sort_values(
        ["ticker", "FE_FP_END"]
    )


def add_surprises(panel):
    data = panel.copy()
    date_columns = {
        column: pd.to_datetime(data[column], errors="coerce")
        for column in [
            "FE_FP_END",
            "REPORT_DATE",
            "CONS_EARLY_START_DATE",
            "CONS_EARLY_DATE",
            "CONS_PRINT_START_DATE",
            "CONS_PRINT_DATE",
        ]
        if column in data.columns
    }
    numeric_columns = {
        column: pd.to_numeric(data[column], errors="coerce")
        for column in ["ACTUAL", "CONS_EARLY", "CONS_PRINT"]
    }
    data = with_columns(data, **date_columns, **numeric_columns)
    valid_early = data["CONS_EARLY"].notna() & data["CONS_EARLY"].ne(0)
    valid_print = data["CONS_PRINT"].notna() & data["CONS_PRINT"].ne(0)
    surprise_early = ((data["ACTUAL"] - data["CONS_EARLY"]) / data["CONS_EARLY"]).where(
        valid_early
    )
    surprise_print = ((data["ACTUAL"] - data["CONS_PRINT"]) / data["CONS_PRINT"]).where(
        valid_print
    )
    actual_q4 = data.groupby("ticker")["ACTUAL"].shift(4)
    return with_columns(
        data,
        surprise_early=pd.to_numeric(surprise_early, errors="coerce"),
        surprise_print=pd.to_numeric(surprise_print, errors="coerce"),
        actual_q4=actual_q4,
        rev_yoy=data["ACTUAL"] / actual_q4 - 1,
        cons_early_growth=data["CONS_EARLY"] / actual_q4 - 1,
        financial_data_source="FACTSET_LISTING.FE_V4 direct",
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", type=Path, default=FEATURES)
    parser.add_argument("--out-csv", type=Path, default=OUT_CSV)
    parser.add_argument("--audit-json", type=Path, default=AUDIT_JSON)
    parser.add_argument("--start-date", default="2019-01-01")
    parser.add_argument("--mcp-url", default=FACTSET_MCP_URL)
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("--mcp-timeout-seconds", type=float, default=120)
    parser.add_argument("--query-timeout-seconds", type=float, default=90)
    parser.add_argument("--env-path", action="append", type=Path, default=[])
    args = parser.parse_args()
    args.start_date = date.fromisoformat(args.start_date)
    if args.batch_size < 1:
        raise SystemExit("--batch-size must be at least 1")

    tickers = load_tickers(args.features)
    env = load_env(args.env_path or DEFAULT_ENV_PATHS)
    stocks, fiscal_documents = asyncio.run(fetch_stock_metadata(args, tickers, env))
    if stocks.empty:
        raise SystemExit("no Stock DB mappings found")
    missing_tickers = sorted(set(tickers) - set(stocks["ticker"]))
    missing_fsym = sorted(
        stocks.loc[stocks["fsym_regional_id"].isna(), "ticker"].tolist()
    )
    if missing_tickers:
        print(f"[mapping-warning] missing Stock DB tickers: {missing_tickers}")
    if missing_fsym:
        print(f"[mapping-warning] missing FactSet IDs: {missing_fsym}")
    fsym_ids = sorted(stocks["fsym_regional_id"].dropna().unique())
    factset, audit = fetch_factset_panel(args, fsym_ids)
    panel = add_surprises(assemble_panel(factset, stocks, fiscal_documents))

    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(args.out_csv, index=False)
    args.audit_json.write_text(json.dumps(audit, indent=2, ensure_ascii=True) + "\n")
    print(f"[written] {args.out_csv}")
    print(f"[written] {args.audit_json}")
    print(
        f"rows={len(panel)} tickers={panel['ticker'].nunique() if len(panel) else 0} "
        f"surprise_rows={panel['surprise_early'].notna().sum() if len(panel) else 0}"
    )


if __name__ == "__main__":
    main()
