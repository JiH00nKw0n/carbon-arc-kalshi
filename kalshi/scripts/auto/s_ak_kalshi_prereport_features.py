#!/usr/bin/env python3
"""Build company-quarter inputs from raw pre-publication Kalshi KPI ladders.

Every eligible KPI event mapped to a target quarter is retained. Each rung
stores its source quote, selected probability, and actual candle timestamp.
No integrated scalar or post-settlement market result is produced.
"""
import argparse
import json
import re
import time
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[3]
KALSHI_ROOT = ROOT / "kalshi"
JOINED = KALSHI_ROOT / "outputs" / "auto" / "kalshi_x_revsurprise_events.csv"
INVENTORY = KALSHI_ROOT / "outputs" / "auto" / "kalshi_company_markets.csv"
OUT_CSV = KALSHI_ROOT / "outputs" / "auto" / "kalshi_prereport_ladder_panel.csv"
BASE = "https://external-api.kalshi.com/trade-api/v2"
HEADERS = {
    "accept": "application/json",
    "user-agent": "kalshi-raw-ladder-experiment/2.0",
}
NUMBER_RE = re.compile(r"(-?[\d,.]+(?:\.\d+)?)\s*(thousand|million|billion|%)?", re.I)
TARGET_COLUMNS = [
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
    "surprise_early",
    "surprise_print",
    "actual_q4",
    "rev_yoy",
    "cons_early_growth",
]


def clean(value):
    if value is None or pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value).replace("\n", " ")).strip()


def number(value):
    try:
        if value is None or pd.isna(value) or str(value).strip() == "":
            return np.nan
        return float(value)
    except (TypeError, ValueError):
        return np.nan


def quote_value(candle, quote, field):
    block = candle.get(quote)
    if not isinstance(block, dict):
        return np.nan
    dollars = number(block.get(f"{field}_dollars"))
    if np.isfinite(dollars):
        return dollars
    raw = number(block.get(field))
    if np.isfinite(raw) and 1 < raw <= 100:
        return raw / 100.0
    return raw


def select_probability(candle, max_mid_spread):
    bid = quote_value(candle, "yes_bid", "close")
    ask = quote_value(candle, "yes_ask", "close")
    last = quote_value(candle, "price", "close")
    previous = quote_value(candle, "price", "previous")
    valid_book = (
        np.isfinite(bid)
        and np.isfinite(ask)
        and 0 <= bid <= ask <= 1
        and ask > 0
    )
    spread = float(ask - bid) if valid_book else np.nan
    if valid_book and spread <= max_mid_spread:
        probability = (bid + ask) / 2.0
        source = "yes_quote_midpoint"
    elif np.isfinite(last) and 0 <= last <= 1:
        probability = last
        source = "last_trade_close"
    elif np.isfinite(previous) and 0 <= previous <= 1:
        probability = previous
        source = "previous_trade"
    else:
        probability = np.nan
        source = ""
    return {
        "probability": float(probability) if np.isfinite(probability) else np.nan,
        "price_source": source,
        "yes_bid": float(bid) if np.isfinite(bid) else None,
        "yes_ask": float(ask) if np.isfinite(ask) else None,
        "last": float(last) if np.isfinite(last) else None,
        "previous": float(previous) if np.isfinite(previous) else None,
        "spread": float(spread) if np.isfinite(spread) else None,
        "wide_spread_fallback": bool(
            valid_book and spread > max_mid_spread and source in {"last_trade_close", "previous_trade"}
        ),
    }


def parsed_strike(row):
    strike = number(row.get("floor_strike"))
    if np.isfinite(strike):
        return strike
    match = NUMBER_RE.search(clean(row.get("yes_sub_title")))
    if not match:
        return np.nan
    value = float(match.group(1).replace(",", ""))
    scale = {
        "thousand": 1_000.0,
        "million": 1_000_000.0,
        "billion": 1_000_000_000.0,
        "%": 1.0,
    }.get((match.group(2) or "").lower(), 1.0)
    return value * scale


def threshold_operator(row):
    return ">=" if clean(row.get("strike_type")).lower() == "greater_or_equal" else ">"


def survival_rungs(group):
    g = group.copy()
    strike_type = g["strike_type"].fillna("").str.lower()
    subtitle = g["yes_sub_title"].fillna("").str.strip().str.lower()
    above = subtitle.str.startswith("above")
    at_least = subtitle.str.startswith("at least") | subtitle.str.contains(r"\bor more\b", regex=True)
    valid_direction = (
        (strike_type.isin(["greater", "structured"]) & above)
        | (strike_type.eq("greater_or_equal") & at_least)
        | (strike_type.eq("") & above)
    )
    g = g[valid_direction].copy()
    g["ladder_strike"] = g.apply(parsed_strike, axis=1)
    return g.dropna(subset=["ladder_strike", "market_ticker"]).drop_duplicates("market_ticker")


def first_numeric(*values):
    for value in values:
        parsed = number(value)
        if np.isfinite(parsed):
            return float(parsed)
    return None


def market_open_timestamp(value):
    opened_at = pd.to_datetime(value, errors="coerce", utc=True)
    return int(opened_at.timestamp()) if pd.notna(opened_at) else None


def latest_candle(session, base_url, series_ticker, market_ticker, start_ts, as_of_ts, timeout):
    params = {
        "start_ts": start_ts,
        "end_ts": int(as_of_ts),
        "period_interval": 1440,
    }
    endpoints = [
        (
            "series_candlesticks",
            f"{base_url}/series/{series_ticker}/markets/{market_ticker}/candlesticks",
        ),
        (
            "historical_candlesticks",
            f"{base_url}/historical/markets/{market_ticker}/candlesticks",
        ),
    ]
    last_error = "missing"
    for endpoint_name, url in endpoints:
        for attempt in range(3):
            try:
                response = session.get(url, params=params, timeout=timeout)
            except requests.RequestException as exc:
                last_error = type(exc).__name__
                time.sleep(0.25 * (attempt + 1))
                continue
            if response.status_code == 404:
                last_error = "404"
                break
            if response.status_code in {429, 500, 502, 503, 504}:
                last_error = f"http_{response.status_code}"
                time.sleep(0.5 * (attempt + 1))
                continue
            if not response.ok:
                last_error = f"http_{response.status_code}"
                break
            candles = response.json().get("candlesticks", []) or []
            eligible = [
                candle
                for candle in candles
                if start_ts <= number(candle.get("end_period_ts")) <= as_of_ts
            ]
            if not eligible:
                last_error = "empty_in_window"
                break
            candle = max(eligible, key=lambda value: number(value.get("end_period_ts")))
            return candle, endpoint_name, ""
    return None, "", last_error


def monotonicity_violations(rungs):
    ordered = sorted(rungs, key=lambda row: (row["strike"], row["market_ticker"]))
    return sum(
        right["probability"] > left["probability"] + 1e-12
        for left, right in zip(ordered, ordered[1:])
        if right["strike"] > left["strike"]
    )


def build_event_ladder(
    session,
    base_url,
    target,
    event_markets,
    as_of,
    max_mid_spread,
    timeout,
    errors,
):
    candidates = survival_rungs(event_markets)
    rungs = []
    for market in candidates.to_dict("records"):
        open_ts = market_open_timestamp(market.get("open_time"))
        if open_ts is None:
            errors.append(
                {
                    "event_ticker": clean(target.get("event_ticker")),
                    "market_ticker": clean(market.get("market_ticker")),
                    "error": "missing_open_time",
                }
            )
            continue
        if open_ts > int(as_of.timestamp()):
            errors.append(
                {
                    "event_ticker": clean(target.get("event_ticker")),
                    "market_ticker": clean(market.get("market_ticker")),
                    "error": "market_not_open_as_of_cutoff",
                }
            )
            continue
        candle, endpoint, error = latest_candle(
            session,
            base_url,
            clean(market.get("series_ticker")),
            clean(market.get("market_ticker")),
            open_ts,
            int(as_of.timestamp()),
            timeout,
        )
        if candle is None:
            errors.append(
                {
                    "event_ticker": clean(target.get("event_ticker")),
                    "market_ticker": clean(market.get("market_ticker")),
                    "error": error,
                }
            )
            continue
        selected = select_probability(candle, max_mid_spread)
        if not np.isfinite(selected["probability"]):
            errors.append(
                {
                    "event_ticker": clean(target.get("event_ticker")),
                    "market_ticker": clean(market.get("market_ticker")),
                    "error": "no_usable_price",
                }
            )
            continue
        candle_ts = int(number(candle.get("end_period_ts")))
        candle_at = pd.to_datetime(candle_ts, unit="s", utc=True)
        rungs.append(
            {
                "market_ticker": clean(market.get("market_ticker")),
                "market_title": clean(market.get("market_title")),
                "yes_contract": clean(market.get("yes_sub_title")),
                "strike": float(market["ladder_strike"]),
                "threshold_operator": threshold_operator(market),
                **selected,
                "candle_ts": candle_ts,
                "candle_at": candle_at.isoformat(),
                "market_open_at": pd.to_datetime(open_ts, unit="s", utc=True).isoformat(),
                "candle_age_hours": round((as_of - candle_at).total_seconds() / 3600.0, 3),
                "daily_volume": first_numeric(
                    candle.get("volume_fp"), candle.get("volume")
                ),
                "open_interest": first_numeric(
                    candle.get("open_interest_fp"), candle.get("open_interest")
                ),
                "candle_endpoint": endpoint,
            }
        )
    rungs.sort(key=lambda row: (row["strike"], row["market_ticker"]))
    if len(rungs) < 2:
        return None
    return {
        "series_ticker": clean(target.get("series_ticker")),
        "series_title": clean(target.get("series_title")),
        "event_ticker": clean(target.get("event_ticker")),
        "metric_label": clean(target.get("metric_label")),
        "period_label": clean(target.get("period_label")),
        "n_ladder_markets": int(len(candidates)),
        "n_priced_rungs": int(len(rungs)),
        "monotonicity_violations": int(monotonicity_violations(rungs)),
        "rungs": rungs,
    }


def target_key(row):
    return (
        clean(row.get("ticker")).upper(),
        clean(row.get("FE_FP_END")),
        clean(row.get("REPORT_DATE")),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--joined", type=Path, default=JOINED)
    parser.add_argument("--inventory", type=Path, default=INVENTORY)
    parser.add_argument("--out-csv", type=Path, default=OUT_CSV)
    parser.add_argument("--base-url", default=BASE)
    parser.add_argument("--max-mid-spread", type=float, default=0.20)
    parser.add_argument("--timeout", type=float, default=20)
    parser.add_argument("--publication-buffer-minutes", type=float, default=1.0)
    args = parser.parse_args()

    joined = pd.read_csv(args.joined)
    inventory = pd.read_csv(args.inventory)
    required = {"ticker", "FE_FP_END", "REPORT_DATE", "published_at", "event_ticker"}
    missing = sorted(required - set(joined.columns))
    if missing:
        raise SystemExit(f"joined panel missing columns: {missing}")

    joined_columns = {column: joined[column] for column in joined.columns}
    joined_columns["published_at"] = pd.to_datetime(
        joined["published_at"], errors="coerce", utc=True
    )
    joined = pd.DataFrame(joined_columns, index=joined.index)
    groups = {}
    for row in joined.to_dict("records"):
        key = target_key(row)
        group = groups.setdefault(
            key,
            {
                "target": {column: row.get(column) for column in TARGET_COLUMNS if column in row},
                "event_rows": {},
            },
        )
        group["event_rows"][clean(row.get("event_ticker"))] = row

    session = requests.Session()
    session.headers.update(HEADERS)
    errors = []
    output_rows = []
    for index, group in enumerate(groups.values(), 1):
        target = group["target"]
        published_at = pd.to_datetime(target.get("published_at"), errors="coerce", utc=True)
        ladders = []
        if pd.notna(published_at):
            as_of = published_at - pd.Timedelta(minutes=args.publication_buffer_minutes)
            for event_ticker, event_row in sorted(group["event_rows"].items()):
                event_markets = inventory[inventory["event_ticker"].eq(event_ticker)].copy()
                ladder = build_event_ladder(
                    session,
                    args.base_url,
                    event_row,
                    event_markets,
                    as_of,
                    args.max_mid_spread,
                    args.timeout,
                    errors,
                )
                if ladder:
                    ladders.append(ladder)
        else:
            as_of = pd.NaT

        all_rungs = [rung for ladder in ladders for rung in ladder["rungs"]]
        candle_timestamps = [rung["candle_ts"] for rung in all_rungs]
        event_market_total = sum(ladder["n_ladder_markets"] for ladder in ladders)
        row = dict(target)
        row.update(
            {
                "pre_as_of_at": as_of.isoformat() if pd.notna(as_of) else "",
                "pre_as_of_ts": int(as_of.timestamp()) if pd.notna(as_of) else np.nan,
                "pre_cutoff_source": (
                    "published_at_minus_buffer" if pd.notna(as_of) else "missing_published_at"
                ),
                "pre_candle_search_rule": (
                    "market_open_to_publication_cutoff"
                    if pd.notna(as_of)
                    else "missing_published_at"
                ),
                "pre_event_count": int(len(ladders)),
                "pre_total_ladder_markets": int(event_market_total),
                "pre_total_priced_rungs": int(len(all_rungs)),
                "pre_daily_volume_sum": float(
                    sum(rung["daily_volume"] or 0.0 for rung in all_rungs)
                ),
                "pre_open_interest_sum": float(
                    sum(rung["open_interest"] or 0.0 for rung in all_rungs)
                ),
                "pre_oldest_candle_ts": min(candle_timestamps) if candle_timestamps else np.nan,
                "pre_latest_candle_ts": max(candle_timestamps) if candle_timestamps else np.nan,
                "pre_max_candle_age_hours": (
                    max(rung["candle_age_hours"] for rung in all_rungs)
                    if all_rungs
                    else np.nan
                ),
                "pre_wide_spread_fallback_rungs": int(
                    sum(rung["wide_spread_fallback"] for rung in all_rungs)
                ),
                "pre_monotonicity_violations": int(
                    sum(ladder["monotonicity_violations"] for ladder in ladders)
                ),
                "kalshi_event_tickers": "|".join(
                    ladder["event_ticker"] for ladder in ladders
                ),
                "kalshi_ladders_json": json.dumps(
                    ladders, separators=(",", ":"), ensure_ascii=True
                ),
            }
        )
        output_rows.append(row)
        print(
            f"[{index}/{len(groups)}] {target.get('ticker')} {clean(target.get('FE_FP_END'))}: "
            f"events={len(ladders)} rungs={len(all_rungs)}",
            flush=True,
        )

    out = pd.DataFrame(output_rows)
    if not out.empty:
        out = out.sort_values(["REPORT_DATE", "ticker"]).reset_index(drop=True)
    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.out_csv, index=False)

    covered = out[out["pre_event_count"].gt(0)] if not out.empty else out
    error_counts = Counter(row["error"] for row in errors)
    print(f"[written] {args.out_csv}")
    print(
        f"targets={len(out)} covered={len(covered)} "
        f"events={int(covered['pre_event_count'].sum()) if not covered.empty else 0} "
        f"rungs={int(covered['pre_total_priced_rungs'].sum()) if not covered.empty else 0} "
        f"misses={dict(error_counts)}"
    )


if __name__ == "__main__":
    main()
