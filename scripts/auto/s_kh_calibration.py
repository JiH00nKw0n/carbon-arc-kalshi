#!/usr/bin/env python3
"""
s_kh_calibration.py — EXP-3: is the Kalshi market well-CALIBRATED, or systematically off?

Pure market-efficiency test, independent of revenue/returns. For a large set of
resolved binary markets, take the implied YES probability at T-k days before close
(candlestick close) and compare to the actual settlement (yes=1/no=0).

Outputs:
  - calibration curve: bucket implied-P into deciles, actual settle-rate per bucket
  - favorite-longshot bias: does the market over/under-price longshots vs favorites?
  - Brier score, and mean (implied - outcome).

Universe = our 7 company-KPI series (all strikes across all quarters) + macro series
(CPI/NFP/etc via s_k0's series prefixes). Each STRIKE is one binary market observation.
T-k default = 3 trading days before close (avoid the settlement snap).
"""
import csv
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "kalshi_calibration.csv"
BASE = "https://api.elections.kalshi.com/trade-api/v2"
H = {"accept": "application/json", "user-agent": "carbonarc-research/1.0"}

COMPANY = ["KXTESLA", "TESLA", "KXMETADAP", "METADAP", "KXNETFLIXSUBS", "NETFLIXSUBS",
           "KXNYTSUBS", "KXRHGOLD", "KXSPOTIFYSUBS", "KXSOFIMEMBERS"]
MACRO = ["CPI", "KXCPI", "PAYROLLS", "KXPAYROLLS", "PCECORE", "KXPCECORE",
         "U3", "KXU3", "KXUE", "RETAIL", "KXRETAIL", "KXUSRETAIL"]
SNAP_DAYS = 3   # implied at T-3 days before close

sess = requests.Session(); sess.headers.update(H)


def kget(path, params, tries=5):
    for i in range(tries):
        try:
            r = sess.get(f"{BASE}{path}", params=params, timeout=30)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (429, 500, 502, 503):
                time.sleep(0.4 * (i + 1)); continue
            return None
        except requests.exceptions.RequestException:
            time.sleep(0.5 * (i + 1))
    return None


def iso(s):
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())


def series_markets(pfx):
    rows, cur, pg = [], "", 0
    while pg < 20:
        p = {"series_ticker": pfx, "limit": 1000}
        if cur:
            p["cursor"] = cur
        d = kget("/historical/markets", p)
        if not d:
            break
        rows += d.get("markets", []) or []
        cur = (d.get("cursor") or "").strip(); pg += 1
        if not cur:
            break
    return rows


def implied_at(ticker, close_ts, open_ts, k_days):
    """YES implied prob at ~k_days before close, from daily candles."""
    d = kget(f"/historical/markets/{ticker}/candlesticks",
             {"start_ts": open_ts, "end_ts": close_ts, "period_interval": 1440})
    cands = (d or {}).get("candlesticks", [])
    cut = close_ts - k_days * 86400
    best = None
    for c in cands:
        ep = c.get("end_period_ts")
        if ep is None or ep >= cut:
            continue
        if best is None or ep > best.get("end_period_ts", -1):
            best = c
    if best is None:
        return None
    pr = best.get("price") or {}
    if pr.get("close") is not None:
        return float(pr["close"])
    yb = (best.get("yes_bid") or {}).get("close"); ya = (best.get("yes_ask") or {}).get("close")
    yb = float(yb) if yb is not None else None; ya = float(ya) if ya is not None else None
    if yb is not None and ya is not None:
        return (yb + ya) / 2
    return yb if yb is not None else ya


def collect(prefixes, label):
    obs = []   # (implied_p, outcome, label)
    for pfx in prefixes:
        for m in series_markets(pfx):
            res = m.get("result")
            if res not in ("yes", "no"):
                continue
            ci = m.get("close_time"); oi = m.get("open_time")
            if not ci:
                continue
            p = implied_at(m["ticker"], iso(ci), iso(oi or ci), SNAP_DAYS)
            if p is None:
                continue
            obs.append((p, 1.0 if res == "yes" else 0.0, label))
            time.sleep(0.008)
        print(f"  {pfx}: cumulative {len(obs)} obs", file=sys.stderr)
    return obs


def calibration(obs, label):
    n = len(obs)
    if n < 10:
        print(f"  {label}: only {n} obs"); return []
    brier = sum((p - y) ** 2 for p, y, _ in obs) / n
    mean_bias = sum(p - y for p, y, _ in obs) / n
    print(f"\n=== {label}  (n={n}, snap=T-{SNAP_DAYS}d) ===")
    print(f"  Brier={brier:.4f}   mean(implied - outcome)={mean_bias:+.4f}")
    print(f"  {'bucket':12s} {'n':>4s} {'mean_impl':>9s} {'settle_rate':>11s} {'gap':>7s}")
    rows = []
    for lo in range(0, 100, 10):
        hi = lo + 10
        b = [(p, y) for p, y, _ in obs if lo / 100 <= p < hi / 100 or (hi == 100 and p == 1.0)]
        if not b:
            continue
        mp = sum(p for p, _ in b) / len(b)
        sr = sum(y for _, y in b) / len(b)
        gap = sr - mp
        rows.append({"label": label, "bucket": f"{lo}-{hi}%", "n": len(b),
                     "mean_implied": round(mp, 4), "settle_rate": round(sr, 4), "gap": round(gap, 4)})
        bar = ("+" if gap >= 0 else "-") * int(min(abs(gap) * 50, 30))
        print(f"  {lo:3d}-{hi:3d}%    {len(b):4d} {mp:9.3f} {sr:11.3f} {gap:+7.3f}  {bar}")
    return rows


def main():
    print("collecting company-KPI markets...", file=sys.stderr)
    comp = collect(COMPANY, "company")
    print("collecting macro markets...", file=sys.stderr)
    macro = collect(MACRO, "macro")

    allrows = []
    allrows += calibration(comp, "COMPANY-KPI")
    allrows += calibration(macro, "MACRO")
    allrows += calibration(comp + macro, "ALL")

    # favorite-longshot summary: compare low-P vs high-P buckets
    def flb(obs, lbl):
        low = [(p, y) for p, y, _ in obs if p < 0.2]
        high = [(p, y) for p, y, _ in obs if p > 0.8]
        if low and high:
            lg = sum(y for _, y in low) / len(low) - sum(p for p, _ in low) / len(low)
            hg = sum(y for _, y in high) / len(high) - sum(p for p, _ in high) / len(high)
            print(f"\n  [{lbl}] longshot(P<.2) gap={lg:+.3f} (n={len(low)})   "
                  f"favorite(P>.8) gap={hg:+.3f} (n={len(high)})")
            print("   -> longshot gap<0 & favorite gap>0 = classic favorite-longshot bias"
                  " (longshots overpriced, favorites underpriced)")
    flb(comp + macro, "ALL")

    OUT.parent.mkdir(exist_ok=True)
    if allrows:
        with open(OUT, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(allrows[0].keys())); w.writeheader(); w.writerows(allrows)
        print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
