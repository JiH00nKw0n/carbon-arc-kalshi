#!/usr/bin/env python3
"""
s_kb_build_X.py — X builder: Kalshi implied KPI distribution at T-k (leak-safe).

Per (series, quarter):
  1. load the full strike ladder for the event  (/historical/markets?event_ticker=..)
  2. anchor T = Kalshi close_time (KPI release / settlement day)
  3. for each strike, pull its candlestick series (/historical/markets/{ticker}/candlesticks)
     and read the YES price as of T-k (k in {1,7} days). price.close, else (yes_bid+yes_ask)/2.
     ALL candles with end_period_ts >= T are dropped -> no look-ahead.
  4. strike->P(KPI >= strike) = survival S(x). Enforce monotone non-increasing.
     implied CDF F(x)=1-S(x); PDF mass on each strike interval.
  5. features: implied_mean, implied_sd, implied_skew, and P(KPI>=strike) grid.

Quality tags per quarter so downstream can run Tesla-only vs all-3:
  n_strikes, bracketed (has both a ~1 and a ~0 strike at T-k), snapshot coverage.

Units are native per series (Tesla=deliveries count, Meta=billions DAP, Netflix=millions adds);
implied moments are in those native units. Downstream converts to a surprise vs consensus.

Output: outputs/kalshi_X.csv   (one row per series-quarter-snapshot)
        outputs/kalshi_X_grid.csv  (long: per strike, the T-k implied prob — audit/plots)
"""
import csv
import sys
import time
import math
import collections
from datetime import datetime, timedelta
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "kalshi_X.csv"
OUT_GRID = ROOT / "outputs" / "kalshi_X_grid.csv"
BASE = "https://api.elections.kalshi.com/trade-api/v2"
H = {"accept": "application/json", "user-agent": "carbonarc-research/1.0"}

# panel = every resolved KPI series-prefix we found (legacy + KX). data tags the quality.
# discovered via s_kd_multico_scan.py (Financials category). Company-KPI ladders with
# FactSet revenue coverage — excludes macro ladders (TSA passengers, retail, home sales).
SERIES = {
    "Tesla":   {"kpi": "deliveries", "unit": "count",    "prefixes": ["KXTESLA", "TESLA"]},
    "MetaDAP": {"kpi": "DAP",         "unit": "billions", "prefixes": ["KXMETADAP", "METADAP"]},
    "Netflix": {"kpi": "sub_adds",    "unit": "millions", "prefixes": ["KXNETFLIXSUBS", "NETFLIXSUBS"]},
    "NYT":     {"kpi": "sub_adds",    "unit": "thousands", "prefixes": ["KXNYTSUBS", "NYTSUBS"]},
    "Robinhood": {"kpi": "gold_members", "unit": "millions", "prefixes": ["KXRHGOLD", "RHGOLD"]},
    "Spotify": {"kpi": "subscribers", "unit": "millions", "prefixes": ["KXSPOTIFYSUBS", "SPOTIFYSUBS"]},
    "SoFi":    {"kpi": "new_members", "unit": "thousands", "prefixes": ["KXSOFIMEMBERS", "SOFIMEMBERS"]},
    # thin (n=2 resolved) — included for completeness; tagged, no statistics
    "Uber":    {"kpi": "trips",       "unit": "billions", "prefixes": ["KXUBERTRIPS", "UBERTRIPS"]},
    "DoorDash": {"kpi": "orders",     "unit": "millions", "prefixes": ["KXDASHORDERS", "DASHORDERS"]},
    "Boeing":  {"kpi": "deliveries",  "unit": "count",    "prefixes": ["KXBOEING", "BOEING"]},
    "Southwest": {"kpi": "seat_miles", "unit": "misc",    "prefixes": ["KXLUV", "LUV"]},
    "SpotifyMAU": {"kpi": "MAU",      "unit": "millions", "prefixes": ["KXSPOTIFYMAU", "SPOTIFYMAU"]},
}
SNAPSHOTS_DAYS = [1, 7, 30, 60]  # T-1, T-7 (late); T-30, T-60 (early) -> enables revision-X

sess = requests.Session()
sess.headers.update(H)


def get(path, params, tries=4):
    for i in range(tries):
        try:
            r = sess.get(f"{BASE}{path}", params=params, timeout=30)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (429, 500, 502, 503):
                time.sleep(0.4 * (i + 1)); continue
            return None
        except Exception:
            time.sleep(0.4 * (i + 1))
    return None


def iso2ts(s):
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())


def pull_series_markets(prefix):
    rows, cur, pages = [], "", 0
    while pages < 30:
        p = {"series_ticker": prefix, "limit": 1000}
        if cur:
            p["cursor"] = cur
        d = get("/historical/markets", p)
        if not d:
            break
        rows += d.get("markets", []) or []
        cur = (d.get("cursor") or "").strip()
        pages += 1
        if not cur:
            break
    return rows


def yes_price_at(candles, t_cut):
    """last candle strictly before t_cut. price.close, else mid(yes_bid,yes_ask). None if nothing."""
    best = None
    for c in candles:
        ep = c.get("end_period_ts")
        if ep is None or ep >= t_cut:      # drop candles at/after the cut -> leak-safe
            continue
        if best is None or ep > best.get("end_period_ts", -1):
            best = c
    if best is None:
        return None
    pr = best.get("price") or {}
    if pr.get("close") is not None:
        return float(pr["close"])
    yb = (best.get("yes_bid") or {}).get("close")
    ya = (best.get("yes_ask") or {}).get("close")
    yb = float(yb) if yb is not None else None
    ya = float(ya) if ya is not None else None
    if yb is not None and ya is not None:
        return (yb + ya) / 2.0
    return yb if yb is not None else ya


def implied_moments(strikes, probs):
    """
    strikes ascending, probs = P(KPI >= strike) (survival, monotone non-increasing after cleanup).
    PDF mass between consecutive strikes = S(x_i) - S(x_{i+1}). Mass below first / above last
    handled as tail point mass at the boundary strike. Returns (mean, sd, skew) or None if degenerate.
    """
    # enforce monotone non-increasing survival
    s = list(probs)
    for i in range(1, len(s)):
        s[i] = min(s[i], s[i - 1])
    s = [max(0.0, min(1.0, v)) for v in s]
    xs = strikes
    # bin representative values = midpoints; tails anchored at boundary strikes
    pts, mass = [], []
    # mass above the top strike:
    pts.append(xs[-1]); mass.append(s[-1])
    # interior bins:
    for i in range(len(xs) - 1):
        m = s[i] - s[i + 1]
        if m > 1e-9:
            pts.append((xs[i] + xs[i + 1]) / 2.0); mass.append(m)
    # mass below the bottom strike:
    below = 1.0 - s[0]
    if below > 1e-9:
        pts.append(xs[0]); mass.append(below)
    tot = sum(mass)
    if tot <= 1e-6:
        return None
    mass = [m / tot for m in mass]
    mean = sum(p * m for p, m in zip(pts, mass))
    var = sum((p - mean) ** 2 * m for p, m in zip(pts, mass))
    sd = math.sqrt(var) if var > 0 else 0.0
    skew = (sum((p - mean) ** 3 * m for p, m in zip(pts, mass)) / (sd ** 3)) if sd > 1e-9 else 0.0
    return mean, sd, skew


def process_event(name, meta, event_ticker, markets):
    """markets = all strikes for one quarter. build X per snapshot."""
    # numeric strike = floor_strike; drop non-numeric
    strikes = []
    for m in markets:
        fs = m.get("floor_strike")
        if fs is None:
            continue
        try:
            strikes.append((float(fs), m))
        except (TypeError, ValueError):
            continue
    strikes.sort(key=lambda x: x[0])
    if len(strikes) < 2:
        return [], []
    close_iso = strikes[0][1].get("close_time") or ""
    if not close_iso:
        return [], []
    T = iso2ts(close_iso)
    # realized KPI (Tesla/Netflix give it; Meta gives 'Yes' -> None)
    exp_raw = strikes[0][1].get("expiration_value")
    realized = None
    if exp_raw:
        s = str(exp_raw).lower().replace(",", "").strip()
        try:
            realized = float(s.split()[0])
        except (ValueError, IndexError):
            realized = None

    # fetch candlesticks once per strike (daily; window = open..close)
    strike_candles = {}
    for x, m in strikes:
        ot = iso2ts(m.get("open_time") or close_iso)
        params = {"start_ts": ot, "end_ts": T, "period_interval": 1440}
        d = get(f"/historical/markets/{m['ticker']}/candlesticks", params)
        strike_candles[x] = (d or {}).get("candlesticks", []) if d else []
        time.sleep(0.015)

    rows, grid = [], []
    xs = [x for x, _ in strikes]
    for k in SNAPSHOTS_DAYS:
        t_cut = T - k * 86400
        probs, have = [], 0
        for x in xs:
            p = yes_price_at(strike_candles[x], t_cut)
            probs.append(p)
            if p is not None:
                have += 1
            grid.append({"name": name, "event": event_ticker, "close": close_iso[:10],
                         "k": k, "strike": x, "yes_prob": "" if p is None else round(p, 4)})
        # need coverage to build a distribution
        if have < 2:
            rows.append({"name": name, "kpi": meta["kpi"], "unit": meta["unit"],
                         "event": event_ticker, "close_date": close_iso[:10], "k": k,
                         "n_strikes": len(xs), "n_priced": have, "bracketed": "",
                         "implied_mean": "", "implied_sd": "", "implied_skew": "",
                         "realized_kpi": "" if realized is None else realized,
                         "note": "insufficient_priced_strikes"})
            continue
        # fill missing probs by nearest-neighbor on the monotone survival (interpolate)
        filled = list(probs)
        for i, v in enumerate(filled):
            if v is None:
                # borrow nearest non-None
                lo = next((filled[j] for j in range(i - 1, -1, -1) if filled[j] is not None), None)
                hi = next((filled[j] for j in range(i + 1, len(filled)) if filled[j] is not None), None)
                filled[i] = (lo if lo is not None else hi) if (lo is None or hi is None) else (lo + hi) / 2
        # bracketed = survival spans from >0.85 down to <0.15 at this snapshot
        hi_p = max(filled); lo_p = min(filled)
        bracketed = (hi_p >= 0.85 and lo_p <= 0.15)
        mom = implied_moments(xs, filled)
        if mom is None:
            rows.append({"name": name, "kpi": meta["kpi"], "unit": meta["unit"],
                         "event": event_ticker, "close_date": close_iso[:10], "k": k,
                         "n_strikes": len(xs), "n_priced": have, "bracketed": int(bracketed),
                         "implied_mean": "", "implied_sd": "", "implied_skew": "",
                         "realized_kpi": "" if realized is None else realized,
                         "note": "degenerate_distribution"})
            continue
        mean, sd, skew = mom
        rows.append({"name": name, "kpi": meta["kpi"], "unit": meta["unit"],
                     "event": event_ticker, "close_date": close_iso[:10], "k": k,
                     "n_strikes": len(xs), "n_priced": have, "bracketed": int(bracketed),
                     "implied_mean": round(mean, 4), "implied_sd": round(sd, 4),
                     "implied_skew": round(skew, 4),
                     "realized_kpi": "" if realized is None else realized,
                     "note": "ok" if bracketed else "unbracketed_coarse"})
    return rows, grid


def main():
    all_rows, all_grid = [], []
    for name, meta in SERIES.items():
        # gather markets across all prefixes, dedup by ticker, group by event
        seen, markets = set(), []
        for pfx in meta["prefixes"]:
            for m in pull_series_markets(pfx):
                t = m.get("ticker")
                if t and t not in seen:
                    seen.add(t); markets.append(m)
        by_event = collections.defaultdict(list)
        for m in markets:
            by_event[m.get("event_ticker")].append(m)
        print(f"{name}: {len(by_event)} quarters, {len(markets)} strikes", file=sys.stderr)
        for et in sorted(by_event):
            rows, grid = process_event(name, meta, et, by_event[et])
            all_rows += rows; all_grid += grid
            done = next((r for r in rows if r.get("note") == "ok"), None)
            tag = "ok" if done else (rows[0]["note"] if rows else "empty")
            print(f"  {et:22s} -> {tag}", file=sys.stderr)

    OUT.parent.mkdir(exist_ok=True)
    cols = ["name", "kpi", "unit", "event", "close_date", "k", "n_strikes", "n_priced",
            "bracketed", "implied_mean", "implied_sd", "implied_skew", "realized_kpi", "note"]
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(all_rows)
    with open(OUT_GRID, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["name", "event", "close", "k", "strike", "yes_prob"])
        w.writeheader(); w.writerows(all_grid)

    # summary
    ok = [r for r in all_rows if r["note"] == "ok"]
    print(f"\nwrote {OUT}  rows={len(all_rows)}  usable(ok)={len(ok)}")
    for name in SERIES:
        n_ok = len({r["event"] for r in ok if r["name"] == name})
        n_tot = len({r["event"] for r in all_rows if r["name"] == name})
        print(f"  {name:9s} usable_quarters(bracketed@some k)={n_ok}/{n_tot}")
    print(f"  -> {OUT_GRID} (per-strike implied prob for audit/plots)")


if __name__ == "__main__":
    main()
