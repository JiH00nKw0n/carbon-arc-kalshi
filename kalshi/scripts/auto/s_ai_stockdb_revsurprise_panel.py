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
OUT_MD = KALSHI_ROOT / "docs" / "analysis_kalshi_stockdb_revenue_surprise_panel.md"

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


def load_tickers(path, include_all_features):
    if not path.exists():
        raise SystemExit(f"features CSV missing: {path}")
    d = pd.read_csv(path)
    if not include_all_features and "feature_family" in d.columns:
        d = d[d["feature_family"] == "numeric_kpi_ladder"].copy()
    tickers = sorted(
        str(t).strip().upper()
        for t in d.get("matched_ticker", pd.Series(dtype=str)).dropna().unique()
        if str(t).strip()
    )
    if not tickers:
        raise SystemExit(f"no matched tickers in {path}")
    return tickers


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
        actual_rows = []
        consensus_rows = []
        skipped = []
        for idx, row in enumerate(stocks.itertuples(), 1):
            stock_id = row.stock_id
            print(f"[db] fetching {idx}/{len(stock_ids)} {row.ticker}", flush=True)
            try:
                actual_part = await asyncio.wait_for(conn.fetch(
                    """
                    SELECT DISTINCT ON (stock_id, calendar_date)
                           stock_id,
                           calendar_date AS "FE_FP_END",
                           item_value AS "ACTUAL",
                           market_effect_date AS "REPORT_DATE",
                           published_at
                    FROM stock_earnings
                    WHERE stock_id = $1
                      AND item_type = 'SALES'
                      AND period_type = 1
                      AND calendar_date >= $2::date
                      AND market_effect_date IS NOT NULL
                    ORDER BY stock_id, calendar_date,
                             published_at DESC NULLS LAST,
                             market_effect_date DESC NULLS LAST
                    """,
                    stock_id,
                    args.start_date,
                ), timeout=args.query_timeout_seconds)
                consensus_part = await asyncio.wait_for(conn.fetch(
                    """
                    SELECT stock_id,
                           calendar_date AS "FE_FP_END",
                           effective_from,
                           estimates_average,
                           number_of_estimates
                    FROM stock_consensuses
                    WHERE stock_id = $1
                      AND item_type = 'SALES'
                      AND period_type = 1
                      AND calendar_date >= $2::date
                    ORDER BY stock_id, calendar_date, effective_from
                    """,
                    stock_id,
                    args.start_date,
                ), timeout=args.query_timeout_seconds)
            except Exception as exc:
                skipped.append({"ticker": row.ticker, "stock_id": stock_id, "reason": type(exc).__name__})
                print(f"[db-warning] skipped {row.ticker}: {type(exc).__name__}", flush=True)
                continue
            actual_rows.extend(actual_part)
            consensus_rows.extend(consensus_part)
            if idx % 10 == 0 or idx == len(stock_ids):
                print(f"[db] fetched {idx}/{len(stock_ids)} stock ids", flush=True)
        args.skipped_stock_fetches = skipped
    finally:
        await conn.close()
    actuals = pd.DataFrame([dict(r) for r in actual_rows])
    consensus = pd.DataFrame([dict(r) for r in consensus_rows])
    return build_panel_from_raw(stocks, actuals, consensus, args)


def pick_consensus(actuals, consensus, as_of_col, prefix):
    if actuals.empty or consensus.empty:
        return pd.DataFrame({"row_id": actuals.get("row_id", pd.Series(dtype=int))})
    base = actuals[["row_id", "stock_id", "FE_FP_END", as_of_col]].copy()
    m = base.merge(consensus, on=["stock_id", "FE_FP_END"], how="left")
    m = m[m["effective_from"].notna() & (m["effective_from"] <= m[as_of_col])].copy()
    if m.empty:
        return pd.DataFrame({"row_id": base["row_id"]})
    m = m.sort_values(
        ["row_id", "effective_from", "number_of_estimates"],
        ascending=[True, True, True],
    )
    picked = m.groupby("row_id", as_index=False).tail(1)
    picked = picked[["row_id", "effective_from", "estimates_average", "number_of_estimates"]].rename(
        columns={
            "effective_from": f"{prefix}_DATE",
            "estimates_average": prefix,
            "number_of_estimates": f"{prefix}_N",
        }
    )
    return picked


def build_panel_from_raw(stocks, actuals, consensus, args):
    if actuals.empty:
        return actuals
    actuals = actuals.copy().reset_index(drop=True)
    actuals["row_id"] = actuals.index
    actuals["FE_FP_END"] = pd.to_datetime(actuals["FE_FP_END"], errors="coerce")
    actuals["REPORT_DATE"] = pd.to_datetime(actuals["REPORT_DATE"], errors="coerce")
    actuals["as_of_early"] = actuals["FE_FP_END"] + pd.Timedelta(days=args.early_days)
    actuals["as_of_print"] = actuals["REPORT_DATE"] - pd.Timedelta(days=args.print_lag_days)
    consensus = consensus.copy()
    if not consensus.empty:
        consensus["FE_FP_END"] = pd.to_datetime(consensus["FE_FP_END"], errors="coerce")
        consensus["effective_from"] = pd.to_datetime(consensus["effective_from"], errors="coerce")
        consensus["estimates_average"] = pd.to_numeric(consensus["estimates_average"], errors="coerce")
        consensus["number_of_estimates"] = pd.to_numeric(consensus["number_of_estimates"], errors="coerce")

    early = pick_consensus(actuals, consensus, "as_of_early", "CONS_EARLY")
    printed = pick_consensus(actuals, consensus, "as_of_print", "CONS_PRINT")
    panel = (
        actuals.merge(stocks, on="stock_id", how="left")
        .merge(early, on="row_id", how="left")
        .merge(printed, on="row_id", how="left")
    )
    cols = [
        "ticker", "stock_id", "stock_name", "exchange", "country",
        "FE_FP_END", "REPORT_DATE", "published_at", "ACTUAL",
        "CONS_EARLY", "CONS_EARLY_DATE", "CONS_EARLY_N",
        "CONS_PRINT", "CONS_PRINT_DATE", "CONS_PRINT_N",
    ]
    return panel[[c for c in cols if c in panel.columns]].sort_values(["ticker", "FE_FP_END"])


def add_surprises(panel):
    d = panel.copy()
    for col in ["FE_FP_END", "REPORT_DATE", "CONS_EARLY_DATE", "CONS_PRINT_DATE"]:
        if col in d.columns:
            d[col] = pd.to_datetime(d[col], errors="coerce")
    for col in ["ACTUAL", "CONS_EARLY", "CONS_PRINT"]:
        d[col] = pd.to_numeric(d[col], errors="coerce")
    valid_early = d["CONS_EARLY"].notna() & (d["CONS_EARLY"] != 0)
    valid_print = d["CONS_PRINT"].notna() & (d["CONS_PRINT"] != 0)
    d["surprise_early"] = pd.NA
    d.loc[valid_early, "surprise_early"] = (
        (d.loc[valid_early, "ACTUAL"] - d.loc[valid_early, "CONS_EARLY"])
        / d.loc[valid_early, "CONS_EARLY"]
    )
    d["surprise_print"] = pd.NA
    d.loc[valid_print, "surprise_print"] = (
        (d.loc[valid_print, "ACTUAL"] - d.loc[valid_print, "CONS_PRINT"])
        / d.loc[valid_print, "CONS_PRINT"]
    )
    d["surprise_early"] = pd.to_numeric(d["surprise_early"], errors="coerce")
    d["surprise_print"] = pd.to_numeric(d["surprise_print"], errors="coerce")
    d["actual_q4"] = d.groupby("ticker")["ACTUAL"].shift(4)
    d["rev_yoy"] = d["ACTUAL"] / d["actual_q4"] - 1
    d["cons_early_growth"] = d["CONS_EARLY"] / d["actual_q4"] - 1
    return d


def write_report(path, args, tickers, panel):
    good = panel.dropna(subset=["surprise_early"])
    lines = [
        "# Kalshi matched tickers: Stock DB revenue-surprise Y panel",
        "",
        f"> Generated by `kalshi/scripts/auto/s_ai_stockdb_revsurprise_panel.py`.",
        "",
        "## Inputs",
        "",
        f"- features: `{args.features.relative_to(ROOT) if args.features.is_relative_to(ROOT) else args.features}`",
        f"- ticker source filter: {'all Kalshi company features' if args.include_all_features else 'numeric KPI ladder features only'}",
        f"- requested tickers: {len(tickers):,}",
        f"- start date: {args.start_date}",
        f"- CONS_EARLY rule: latest quarterly SALES consensus at fiscal quarter end + {args.early_days}d",
        f"- CONS_PRINT rule: latest quarterly SALES consensus at least {args.print_lag_days}d before report market-effect date",
        "",
        "## Output coverage",
        "",
        f"- rows: {len(panel):,}",
        f"- rows with `surprise_early`: {len(good):,}",
        f"- tickers with `surprise_early`: {good['ticker'].nunique() if not good.empty else 0:,}",
        f"- date range: {panel['FE_FP_END'].min().date() if len(panel) else ''}..{panel['FE_FP_END'].max().date() if len(panel) else ''}",
        f"- missing CONS_EARLY rows: {panel['CONS_EARLY'].isna().sum() if len(panel) else 0:,}",
        f"- missing CONS_PRINT rows: {panel['CONS_PRINT'].isna().sum() if len(panel) else 0:,}",
    ]
    if not good.empty:
        lines += [
            f"- surprise_early mean: {good['surprise_early'].mean():+.4f}",
            f"- surprise_early sd: {good['surprise_early'].std():.4f}",
            "",
            "## Sample",
            "",
            "| ticker | FE_FP_END | REPORT_DATE | ACTUAL | CONS_EARLY | surprise_early |",
            "|---|---:|---:|---:|---:|---:|",
        ]
        sample = good.sort_values(["REPORT_DATE", "ticker"], ascending=[False, True]).head(12)
        for r in sample.itertuples():
            lines.append(
                f"| {r.ticker} | {r.FE_FP_END.date()} | {r.REPORT_DATE.date()} | "
                f"{r.ACTUAL:.3f} | {r.CONS_EARLY:.3f} | {r.surprise_early:+.4f} |"
            )
    skipped = getattr(args, "skipped_stock_fetches", [])
    if skipped:
        lines += [
            "",
            "## Skipped Stock DB Fetches",
            "",
            "| ticker | reason |",
            "|---|---|",
        ]
        for row in skipped:
            lines.append(f"| {row['ticker']} | {row['reason']} |")
    lines += [
        "",
        f"Output CSV: `{args.out_csv.relative_to(ROOT) if args.out_csv.is_relative_to(ROOT) else args.out_csv}`",
    ]
    path.write_text("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", type=Path, default=FEATURES)
    ap.add_argument("--out-csv", type=Path, default=OUT_CSV)
    ap.add_argument("--out-md", type=Path, default=OUT_MD)
    ap.add_argument("--start-date", default="2019-01-01")
    ap.add_argument("--early-days", type=int, default=7)
    ap.add_argument("--print-lag-days", type=int, default=1)
    ap.add_argument("--query-timeout-seconds", type=float, default=20)
    ap.add_argument("--include-all-features", action="store_true")
    ap.add_argument("--env-path", action="append", type=Path, default=[])
    args = ap.parse_args()
    args.start_date = date.fromisoformat(args.start_date)

    tickers = load_tickers(args.features, args.include_all_features)
    env_paths = args.env_path or DEFAULT_ENV_PATHS
    env = load_env(env_paths)
    panel = asyncio.run(fetch_panel(args, tickers, env))
    panel = add_surprises(panel)
    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(args.out_csv, index=False)
    write_report(args.out_md, args, tickers, panel)
    print(f"[written] {args.out_csv}")
    print(f"[written] {args.out_md}")
    print(
        f"rows={len(panel)} tickers={panel['ticker'].nunique() if len(panel) else 0} "
        f"surprise_rows={panel['surprise_early'].notna().sum() if len(panel) else 0}"
    )


if __name__ == "__main__":
    main()
