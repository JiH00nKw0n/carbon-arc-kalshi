#!/usr/bin/env python3
"""
Rebuild Kalshi X features from pre-report candlesticks.

The earlier public market snapshot is useful for inventory, but finalized market
prices after the earnings release leak the target. This script uses the latest
daily candlestick available at REPORT_DATE - 1 day for each matched Kalshi event.
"""
import argparse
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

warnings.filterwarnings("ignore", category=FutureWarning, message="ChainedAssignmentError*")

ROOT = Path(__file__).resolve().parents[3]
KALSHI_ROOT = ROOT / "kalshi"
JOINED = KALSHI_ROOT / "outputs" / "auto" / "kalshi_x_revsurprise_panel_all_features.csv"
INVENTORY = KALSHI_ROOT / "outputs" / "auto" / "kalshi_company_markets.csv"
OUT_CSV = KALSHI_ROOT / "outputs" / "auto" / "kalshi_prereport_x_revsurprise_panel.csv"
OUT_MD = KALSHI_ROOT / "docs" / "analysis_kalshi_prereport_x_revsurprise.md"
BASE = "https://external-api.kalshi.com/trade-api/v2"


def rel(path):
    path = Path(path)
    try:
        return path.resolve().relative_to(ROOT)
    except ValueError:
        return path


def num(v):
    try:
        if pd.isna(v) or str(v).strip() == "":
            return np.nan
        return float(v)
    except (TypeError, ValueError):
        return np.nan


def nested(d, *keys):
    cur = d
    for key in keys:
        if not isinstance(cur, dict):
            return np.nan
        cur = cur.get(key)
    return num(cur)


def candle_prob(c):
    bid = nested(c, "yes_bid", "close_dollars")
    ask = nested(c, "yes_ask", "close_dollars")
    price = nested(c, "price", "close_dollars")
    prev = nested(c, "price", "previous_dollars")
    if np.isfinite(bid) and np.isfinite(ask) and ask >= bid:
        return float(np.clip((bid + ask) / 2, 0, 1)), "yes_mid_close"
    if np.isfinite(price):
        return float(np.clip(price, 0, 1)), "price_close"
    if np.isfinite(prev):
        return float(np.clip(prev, 0, 1)), "previous_price"
    return np.nan, ""


def empty_ladder():
    return {
        "pre_n_strikes": 0,
        "pre_strike_min": np.nan,
        "pre_strike_max": np.nan,
        "pre_strike_step_median": np.nan,
        "pre_prob_lowest": np.nan,
        "pre_prob_highest": np.nan,
        "pre_implied_value": np.nan,
        "pre_implied_value_no_tail": np.nan,
        "pre_implied_value_incremental": np.nan,
    }


def latest_candle(series_ticker, market_ticker, as_of_ts, window_days, timeout):
    start_ts = int(as_of_ts - window_days * 86400)
    params = {
        "start_ts": start_ts,
        "end_ts": int(as_of_ts),
        "period_interval": 1440,
        "include_latest_before_start": "true",
    }
    urls = [
        f"{BASE}/series/{series_ticker}/markets/{market_ticker}/candlesticks",
        f"{BASE}/historical/markets/{market_ticker}/candlesticks",
    ]
    last_error = ""
    for url in urls:
        try:
            r = requests.get(url, params=params, timeout=timeout)
        except requests.RequestException as exc:
            last_error = type(exc).__name__
            continue
        if r.status_code == 404:
            last_error = "404"
            continue
        if not r.ok:
            last_error = f"http_{r.status_code}"
            continue
        candles = r.json().get("candlesticks", [])
        candles = [c for c in candles if c.get("end_period_ts") and c["end_period_ts"] <= as_of_ts]
        if not candles:
            last_error = "empty"
            continue
        return sorted(candles, key=lambda c: c["end_period_ts"])[-1], ""
    return None, last_error or "missing"


def implied_ladder(g):
    if g.empty or not {"floor_strike", "pre_prob"}.issubset(g.columns):
        return empty_ladder()
    g = g.dropna(subset=["floor_strike", "pre_prob"]).copy()
    g["strike"] = pd.to_numeric(g["floor_strike"], errors="coerce")
    g = g.dropna(subset=["strike"]).sort_values("strike")
    if len(g) < 2:
        out = empty_ladder()
        out.update({
            "pre_n_strikes": int(len(g)),
            "pre_strike_min": g["strike"].min() if len(g) else np.nan,
            "pre_strike_max": g["strike"].max() if len(g) else np.nan,
            "pre_strike_step_median": np.nan,
            "pre_prob_lowest": g["pre_prob"].iloc[0] if len(g) else np.nan,
            "pre_prob_highest": g["pre_prob"].iloc[-1] if len(g) else np.nan,
        })
        return out
    strikes = g["strike"].to_numpy(float)
    probs = np.clip(g["pre_prob"].to_numpy(float), 0, 1)
    gaps = np.diff(strikes)
    step = float(np.nanmedian(gaps[gaps > 0])) if np.any(gaps > 0) else 0.0
    incremental = float(np.sum(probs[:-1] * gaps) + probs[-1] * step)
    no_tail = float(strikes[0] + np.sum(probs[:-1] * gaps))
    implied = float(strikes[0] + incremental)
    return {
        "pre_n_strikes": int(len(g)),
        "pre_strike_min": float(strikes[0]),
        "pre_strike_max": float(strikes[-1]),
        "pre_strike_step_median": step,
        "pre_prob_lowest": float(probs[0]),
        "pre_prob_highest": float(probs[-1]),
        "pre_implied_value": implied,
        "pre_implied_value_no_tail": no_tail,
        "pre_implied_value_incremental": incremental,
    }


def cluster_boot(d, x, y, n=2000, seed=2026):
    d = d.dropna(subset=[x, y])
    if len(d) < 10 or d[x].std() < 1e-12 or d[y].std() < 1e-12:
        return np.nan, np.nan, len(d)
    r0 = d[x].corr(d[y])
    ticks = d["ticker"].dropna().unique()
    rng = np.random.default_rng(seed)
    bs = []
    for _ in range(n):
        sample_ticks = rng.choice(ticks, len(ticks), True)
        s = pd.concat([d[d["ticker"] == t] for t in sample_ticks], ignore_index=True)
        if s[x].std() > 1e-12 and s[y].std() > 1e-12:
            bs.append(s[x].corr(s[y]))
    bs = np.asarray(bs)
    p = 2 * min((bs > 0).mean(), (bs < 0).mean()) if len(bs) else np.nan
    return float(r0), float(p), int(len(d))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--joined", type=Path, default=JOINED)
    ap.add_argument("--inventory", type=Path, default=INVENTORY)
    ap.add_argument("--out-csv", type=Path, default=OUT_CSV)
    ap.add_argument("--out-md", type=Path, default=OUT_MD)
    ap.add_argument("--window-days", type=int, default=45)
    ap.add_argument("--timeout", type=float, default=20)
    args = ap.parse_args()

    joined = pd.read_csv(args.joined)
    inv = pd.read_csv(args.inventory)
    joined["REPORT_DATE"] = pd.to_datetime(joined["REPORT_DATE"], errors="coerce")
    joined["FE_FP_END"] = pd.to_datetime(joined["FE_FP_END"], errors="coerce")

    rows = []
    errors = []
    for idx, target in enumerate(joined.itertuples(), 1):
        if pd.isna(target.REPORT_DATE):
            continue
        as_of = target.REPORT_DATE - pd.Timedelta(days=1)
        as_of_ts = int(datetime(as_of.year, as_of.month, as_of.day, 23, 59, tzinfo=timezone.utc).timestamp())
        event_markets = inv[inv["event_ticker"].eq(target.event_ticker)].copy()
        priced = []
        for m in event_markets.itertuples():
            candle, err = latest_candle(m.series_ticker, m.market_ticker, as_of_ts, args.window_days, args.timeout)
            if candle is None:
                errors.append({"event_ticker": target.event_ticker, "market_ticker": m.market_ticker, "error": err})
                continue
            prob, source = candle_prob(candle)
            row = m._asdict()
            row.update({
                "pre_prob": prob,
                "pre_price_source": source,
                "pre_candle_ts": candle.get("end_period_ts"),
                "pre_volume_fp": num(candle.get("volume_fp")),
                "pre_open_interest_fp": num(candle.get("open_interest_fp")),
            })
            priced.append(row)
        pg = pd.DataFrame(priced)
        greater = pg[pg["strike_type"].fillna("").str.lower().eq("greater")] if not pg.empty else pg
        ladder = implied_ladder(greater) if not pg.empty else implied_ladder(pg)
        out = target._asdict()
        out.update({
            "pre_as_of_date": as_of.date().isoformat(),
            "pre_as_of_ts": as_of_ts,
            "pre_n_markets": int(len(event_markets)),
            "pre_n_priced": int(len(pg)),
            "pre_volume_sum": float(pg["pre_volume_fp"].sum()) if not pg.empty else np.nan,
            "pre_open_interest_sum": float(pg["pre_open_interest_fp"].sum()) if not pg.empty else np.nan,
            "pre_price_sources": "|".join(sorted(set(str(x) for x in pg["pre_price_source"].dropna()))) if not pg.empty else "",
            **ladder,
        })
        rows.append(out)
        print(f"[{idx}/{len(joined)}] {target.ticker} {target.event_ticker}: priced {len(pg)}/{len(event_markets)}", flush=True)

    out = pd.DataFrame(rows)
    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.out_csv, index=False)

    lines = [
        "# Kalshi pre-report X -> revenue surprise",
        "",
        f"> Generated by `kalshi/scripts/auto/s_ak_kalshi_prereport_features.py`.",
        "",
        f"- input joined panel: `{rel(args.joined)}`",
        f"- input inventory: `{rel(args.inventory)}`",
        f"- as-of rule: latest daily candlestick at `REPORT_DATE - 1 day`, lookback {args.window_days} days",
        f"- rows: {len(out):,}",
        f"- tickers: {out['ticker'].nunique() if not out.empty else 0:,}",
        f"- rows with pre-report prices: {int((out['pre_n_priced'] > 0).sum()) if not out.empty else 0:,}",
        f"- market candle fetch misses: {len(errors):,}",
    ]
    test = out[pd.to_datetime(out["REPORT_DATE"], errors="coerce") > pd.Timestamp("2025-12-01")].copy()
    lines += [
        "",
        "## Post-cutoff correlation tests",
        "",
        "| X | r | p_boot | n |",
        "|---|---:|---:|---:|",
    ]
    for x in [
        "pre_implied_value",
        "pre_implied_value_no_tail",
        "pre_implied_value_incremental",
        "pre_prob_lowest",
        "pre_prob_highest",
        "pre_volume_sum",
        "pre_open_interest_sum",
    ]:
        if x not in test.columns:
            continue
        r, p, n = cluster_boot(test, x, "surprise_early")
        lines.append(f"| {x} | {r:+.3f} | {p:.3f} | {n} |")
    lines += [
        "",
        "Leakage note: unlike the public latest/finalized snapshot, these X values are taken before the report date.",
        f"Output CSV: `{rel(args.out_csv)}`",
    ]
    args.out_md.write_text("\n".join(lines) + "\n")
    print(f"[written] {args.out_csv}")
    print(f"[written] {args.out_md}")


if __name__ == "__main__":
    main()
