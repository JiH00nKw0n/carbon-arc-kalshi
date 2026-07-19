#!/usr/bin/env python3
"""
Build a revenue-surprise Y panel from Stock DB for Kalshi company tickers.

Output schema mirrors the existing Factor 1/3 panel inputs:
  ticker, FE_FP_END, REPORT_DATE, ACTUAL, CONS_EARLY, CONS_PRINT,
  surprise_early, surprise_print

CONS_EARLY uses the latest quarterly SALES consensus snapshot available at
fiscal quarter end + 7 days. CONS_PRINT uses the latest snapshot available
before the market-effect report date to avoid post-print actual leakage.
"""
import argparse
import asyncio
import os
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
KALSHI_ROOT = ROOT / "kalshi"
FEATURES = KALSHI_ROOT / "outputs" / "auto" / "kalshi_company_event_features.csv"
OUT_CSV = KALSHI_ROOT / "outputs" / "auto" / "kalshi_stockdb_revenue_surprise_panel.csv"

DEFAULT_ENV_PATHS = [
    ROOT.parent / "mcp-server" / ".env",
    ROOT.parent / "agent-server" / ".env",
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
                line = line[len("export "):].strip()
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            env.setdefault(key, val)
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
    d = pd.read_csv(path)
    if "feature_family" in d.columns:
        d = d[d["feature_family"] == "kpi_ladder"].copy()
    tickers = sorted(
        str(t).strip().upper()
        for t in d.get("matched_ticker", pd.Series(dtype=str)).dropna().unique()
        if str(t).strip()
    )
    if not tickers:
        raise SystemExit(f"no matched tickers in {path}")
    return tickers


def with_columns(frame, **columns):
    data = {column: frame[column] for column in frame.columns}
    data.update(columns)
    return pd.DataFrame(data, index=frame.index)


async def fetch_panel(args, tickers, env):
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
                   market_cap
            FROM stocks
            WHERE ticker = ANY($1::text[])
              AND is_primary IS TRUE
            ORDER BY ticker, market_cap DESC NULLS LAST, id
            """,
            tickers,
        )
        stocks = pd.DataFrame([dict(r) for r in stock_rows])
        if stocks.empty:
            return stocks
        stock_ids = stocks["stock_id"].tolist()
        print(
            f"[db] fetching point-in-time panel for {len(stock_ids)} stock ids",
            flush=True,
        )
        panel_rows = await conn.fetch(
            """
            WITH actuals AS (
                SELECT DISTINCT ON (stock_id, calendar_date)
                       stock_id,
                       calendar_date AS "FE_FP_END",
                       item_value AS "ACTUAL",
                       market_effect_date AS "REPORT_DATE",
                       published_at
                FROM stock_earnings
                WHERE stock_id = ANY($1::text[])
                  AND item_type = 'SALES'
                  AND period_type = 1
                  AND calendar_date >= $2::date
                  AND market_effect_date IS NOT NULL
                ORDER BY stock_id, calendar_date,
                         published_at DESC NULLS LAST,
                         market_effect_date DESC NULLS LAST
            )
            SELECT actuals.*,
                   early.estimates_average AS "CONS_EARLY",
                   early.effective_from AS "CONS_EARLY_DATE",
                   early.number_of_estimates AS "CONS_EARLY_N",
                   printed.estimates_average AS "CONS_PRINT",
                   printed.effective_from AS "CONS_PRINT_DATE",
                   printed.number_of_estimates AS "CONS_PRINT_N"
            FROM actuals
            LEFT JOIN LATERAL (
                SELECT estimates_average, effective_from, number_of_estimates
                FROM stock_consensuses
                WHERE stock_id = actuals.stock_id
                  AND calendar_date = actuals."FE_FP_END"
                  AND item_type = 'SALES'
                  AND period_type = 1
                  AND effective_from <= actuals."FE_FP_END" + $3::int
                ORDER BY effective_from DESC,
                         number_of_estimates DESC NULLS LAST,
                         external_id
                LIMIT 1
            ) early ON TRUE
            LEFT JOIN LATERAL (
                SELECT estimates_average, effective_from, number_of_estimates
                FROM stock_consensuses
                WHERE stock_id = actuals.stock_id
                  AND calendar_date = actuals."FE_FP_END"
                  AND item_type = 'SALES'
                  AND period_type = 1
                  AND effective_from <= actuals."REPORT_DATE" - $4::int
                ORDER BY effective_from DESC,
                         number_of_estimates DESC NULLS LAST,
                         external_id
                LIMIT 1
            ) printed ON TRUE
            ORDER BY stock_id, "FE_FP_END"
            """,
            stock_ids,
            args.start_date,
            args.early_days,
            args.print_lag_days,
            timeout=args.query_timeout_seconds,
        )
        print("[db] fetching fiscal labels", flush=True)
        fiscal_document_rows = await conn.fetch(
            """
            SELECT sd.stock_id,
                   sd.calendar_date AS "FE_FP_END",
                   sd.name
            FROM stocks s
            JOIN stock_documents sd ON sd.stock_id = s.id
            WHERE s.ticker = ANY($1::text[])
              AND s.is_primary IS TRUE
              AND sd.doc_type = 'earnings_call'
              AND sd.calendar_date >= $2::date
              AND sd.name IS NOT NULL
            """,
            tickers,
            args.start_date,
            timeout=args.query_timeout_seconds,
        )
    finally:
        await conn.close()
    panel = pd.DataFrame([dict(r) for r in panel_rows])
    if panel.empty:
        return panel
    panel = with_columns(
        panel,
        FE_FP_END=pd.to_datetime(panel["FE_FP_END"], errors="coerce"),
    )
    fiscal_periods = fiscal_period_map(
        pd.DataFrame([dict(r) for r in fiscal_document_rows])
    )
    if not fiscal_periods.empty:
        fiscal_periods = with_columns(
            fiscal_periods,
            FE_FP_END=pd.to_datetime(
                fiscal_periods["FE_FP_END"], errors="coerce"
            ),
        )
        panel = panel.merge(
            fiscal_periods,
            on=["stock_id", "FE_FP_END"],
            how="left",
            validate="many_to_one",
        )
    panel = panel.merge(stocks, on="stock_id", how="left", validate="many_to_one")
    columns = [
        "ticker",
        "stock_id",
        "stock_name",
        "exchange",
        "country",
        "FE_FP_END",
        "FISCAL_YEAR",
        "FISCAL_QUARTER",
        "REPORT_DATE",
        "published_at",
        "ACTUAL",
        "CONS_EARLY",
        "CONS_EARLY_DATE",
        "CONS_EARLY_N",
        "CONS_PRINT",
        "CONS_PRINT_DATE",
        "CONS_PRINT_N",
    ]
    return panel[[column for column in columns if column in panel]].sort_values(
        ["ticker", "FE_FP_END"]
    )


def fiscal_period_map(documents):
    if documents.empty:
        return pd.DataFrame(
            columns=["stock_id", "FE_FP_END", "FISCAL_YEAR", "FISCAL_QUARTER"]
        )
    parsed = documents.copy()
    labels = parsed["name"].fillna("").str.extract(
        r"(?i)\bQ([1-4])\s*[,/-]?\s*(20\d{2})\b"
    )
    parsed = with_columns(
        parsed,
        FISCAL_QUARTER=pd.to_numeric(labels[0], errors="coerce"),
        FISCAL_YEAR=pd.to_numeric(labels[1], errors="coerce"),
    )
    parsed = parsed.dropna(subset=["FISCAL_YEAR", "FISCAL_QUARTER"])
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
    return counts.groupby(["stock_id", "FE_FP_END"], as_index=False).head(1).drop(
        columns="size"
    )


def add_surprises(panel):
    d = panel.copy()
    date_columns = {
        column: pd.to_datetime(d[column], errors="coerce")
        for column in [
            "FE_FP_END",
            "REPORT_DATE",
            "CONS_EARLY_DATE",
            "CONS_PRINT_DATE",
        ]
        if column in d.columns
    }
    numeric_columns = {
        column: pd.to_numeric(d[column], errors="coerce")
        for column in ["ACTUAL", "CONS_EARLY", "CONS_PRINT"]
    }
    d = with_columns(d, **date_columns, **numeric_columns)
    valid_early = d["CONS_EARLY"].notna() & (d["CONS_EARLY"] != 0)
    valid_print = d["CONS_PRINT"].notna() & (d["CONS_PRINT"] != 0)
    surprise_early = (
        (d["ACTUAL"] - d["CONS_EARLY"]) / d["CONS_EARLY"]
    ).where(valid_early)
    surprise_print = (
        (d["ACTUAL"] - d["CONS_PRINT"]) / d["CONS_PRINT"]
    ).where(valid_print)
    actual_q4 = d.groupby("ticker")["ACTUAL"].shift(4)
    return with_columns(
        d,
        surprise_early=pd.to_numeric(surprise_early, errors="coerce"),
        surprise_print=pd.to_numeric(surprise_print, errors="coerce"),
        actual_q4=actual_q4,
        rev_yoy=d["ACTUAL"] / actual_q4 - 1,
        cons_early_growth=d["CONS_EARLY"] / actual_q4 - 1,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", type=Path, default=FEATURES)
    ap.add_argument("--out-csv", type=Path, default=OUT_CSV)
    ap.add_argument("--start-date", default="2019-01-01")
    ap.add_argument("--early-days", type=int, default=7)
    ap.add_argument("--print-lag-days", type=int, default=1)
    ap.add_argument("--query-timeout-seconds", type=float, default=90)
    ap.add_argument("--env-path", action="append", type=Path, default=[])
    args = ap.parse_args()
    args.start_date = date.fromisoformat(args.start_date)

    tickers = load_tickers(args.features)
    env_paths = args.env_path or DEFAULT_ENV_PATHS
    env = load_env(env_paths)
    panel = asyncio.run(fetch_panel(args, tickers, env))
    panel = add_surprises(panel)
    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(args.out_csv, index=False)
    print(f"[written] {args.out_csv}")
    print(
        f"rows={len(panel)} tickers={panel['ticker'].nunique() if len(panel) else 0} "
        f"surprise_rows={panel['surprise_early'].notna().sum() if len(panel) else 0}"
    )


if __name__ == "__main__":
    main()
