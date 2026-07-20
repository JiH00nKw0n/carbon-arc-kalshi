#!/usr/bin/env python3
"""
s_kf_leadlag.py — EXP-1: does the Kalshi prediction market LEAD analyst consensus?

For each (company, quarter), over the pre-report window:
  A) Kalshi implied KPI daily series  — implied mean of the strike ladder each day
     (candlestick close per strike -> survival -> implied mean). leak-safe: drop >= report.
  B) analyst SALES consensus daily series — FE_V4 FE_BASIC_CONH_QF snapshots by
     CONS_END_DATE, forward-filled to a daily grid.

Both -> daily changes (revisions), z-scored per quarter. Then lagged cross-correlation
  corr( dKalshi[t], dConsensus[t + lag] )   for lag in -10..+10 (days).
lag > 0 with high corr  =>  Kalshi moves first, consensus follows  =>  prediction-market lead.

Pools across quarters within a company (stack the daily revision pairs), and across
companies. Prints the lead-lag curve + the peak lag.

Reads outputs/kalshi_X_grid.csv is NOT enough (only 4 snapshots); we refetch daily
candlesticks here. Consensus via linq-local MCP factset_query.
"""
import csv
import json
import sys
import time
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "kalshi_leadlag.csv"
BASE = "https://api.elections.kalshi.com/trade-api/v2"
H = {"accept": "application/json", "user-agent": "carbonarc-research/1.0"}
MCP = "http://localhost:3035/mcp"

FSYM = {"Tesla": "Q2YN1N-R", "MetaDAP": "QLGSL2-R", "Netflix": "C4C0BL-R",
        "NYT": "BW92P1-R", "Robinhood": "CSC7N1-R", "Spotify": "X5HN6G-R", "SoFi": "HGZX4Y-R"}
PREFIXES = {
    "Tesla": ["KXTESLA", "TESLA"], "MetaDAP": ["KXMETADAP", "METADAP"],
    "Netflix": ["KXNETFLIXSUBS", "NETFLIXSUBS"], "NYT": ["KXNYTSUBS", "NYTSUBS"],
    "Robinhood": ["KXRHGOLD", "RHGOLD"], "Spotify": ["KXSPOTIFYSUBS", "SPOTIFYSUBS"],
    "SoFi": ["KXSOFIMEMBERS", "SOFIMEMBERS"],
}
WINDOW_DAYS = 75     # pre-report window
LAGS = list(range(-10, 11))

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


def mcp(tool, args):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": tool, "arguments": args}}).encode()
    req = urllib.request.Request(MCP, data=body, headers={
        "content-type": "application/json", "accept": "application/json, text/event-stream"})
    raw = urllib.request.urlopen(req, timeout=60).read().decode()
    if "data:" in raw and not raw.strip().startswith("{"):
        for line in raw.splitlines():
            if line.startswith("data:"):
                raw = line[5:].strip(); break
    d = json.loads(raw)
    txt = "\n".join(c.get("text", "") for c in d.get("result", {}).get("content", []))
    return json.loads(txt) if txt else {}


def iso(s):
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())


def day(ts):
    return datetime.utcfromtimestamp(ts).date()


def implied_mean_from(strikes_probs):
    """strikes ascending, probs=P(KPI>=strike). survival->mean (same as X builder)."""
    xs = [s for s, _ in strikes_probs]
    s = [p for _, p in strikes_probs]
    for i in range(1, len(s)):
        s[i] = min(s[i], s[i - 1])
    s = [max(0.0, min(1.0, v)) for v in s]
    pts, mass = [xs[-1]], [s[-1]]
    for i in range(len(xs) - 1):
        m = s[i] - s[i + 1]
        if m > 1e-9:
            pts.append((xs[i] + xs[i + 1]) / 2); mass.append(m)
    below = 1.0 - s[0]
    if below > 1e-9:
        pts.append(xs[0]); mass.append(below)
    tot = sum(mass)
    if tot <= 1e-6:
        return None
    return sum(p * m for p, m in zip(pts, mass)) / tot


def kalshi_daily(name, event_ticker, markets):
    """daily implied-KPI-mean series over the quarter."""
    strikes = []
    for m in markets:
        fs = m.get("floor_strike")
        if fs is None:
            continue
        try:
            strikes.append((float(fs), m))
        except (TypeError, ValueError):
            pass
    strikes.sort(key=lambda x: x[0])
    if len(strikes) < 2:
        return {}
    close_iso = strikes[0][1].get("close_time") or ""
    T = iso(close_iso)
    # per strike: daily candles -> {date: yes_prob}
    strike_day = {}
    for x, m in strikes:
        ot = iso(m.get("open_time") or close_iso)
        d = kget(f"/historical/markets/{m['ticker']}/candlesticks",
                 {"start_ts": ot, "end_ts": T, "period_interval": 1440})
        series = {}
        for c in (d or {}).get("candlesticks", []):
            ep = c.get("end_period_ts")
            if ep is None or ep >= T:
                continue
            pr = c.get("price") or {}
            v = pr.get("close")
            if v is None:
                yb = (c.get("yes_bid") or {}).get("close"); ya = (c.get("yes_ask") or {}).get("close")
                yb = float(yb) if yb is not None else None; ya = float(ya) if ya is not None else None
                v = (yb + ya) / 2 if (yb is not None and ya is not None) else (yb if yb is not None else ya)
            if v is not None:
                series[day(ep)] = float(v)
        strike_day[x] = series
        time.sleep(0.01)
    # build daily implied mean over union of dates, forward-filling each strike
    all_dates = sorted({d for s in strike_day.values() for d in s})
    if not all_dates:
        return {}
    xs = sorted(strike_day)
    last = {x: None for x in xs}
    out = {}
    for dt in all_dates:
        sp = []
        for x in xs:
            if dt in strike_day[x]:
                last[x] = strike_day[x][dt]
            if last[x] is not None:
                sp.append((x, last[x]))
        if len(sp) >= 2:
            im = implied_mean_from(sp)
            if im is not None:
                out[dt] = im
    return out


def consensus_daily(rid, fp_end, report_date):
    """analyst SALES consensus daily (forward-filled) up to report_date."""
    r = mcp("factset_query", {"sql":
        f"SELECT CONS_END_DATE, FE_MEAN FROM FACTSET_LISTING.FE_V4.FE_BASIC_CONH_QF "
        f"WHERE FSYM_ID='{rid}' AND FE_ITEM='SALES' AND FE_FP_END='{fp_end}' "
        f"AND CONS_END_DATE < '{report_date}' ORDER BY CONS_END_DATE", "max_rows": 200})
    snaps = [(datetime.fromisoformat(x["CONS_END_DATE"][:10]).date(), float(x["FE_MEAN"]))
             for x in r.get("rows", []) if x.get("CONS_END_DATE") and x.get("FE_MEAN")]
    return snaps  # list of (date, mean), ascending


def to_daily_grid(snaps, start, end):
    """forward-fill snapshot list to a daily dict over [start,end]."""
    if not snaps:
        return {}
    out = {}
    idx = 0
    cur = None
    dt = start
    while dt <= end:
        while idx < len(snaps) and snaps[idx][0] <= dt:
            cur = snaps[idx][1]; idx += 1
        if cur is not None:
            out[dt] = cur
        dt += timedelta(days=1)
    return out


def zscore_diffs(series_dict, dates):
    """daily first-differences on a common date grid, z-scored."""
    vals = [series_dict.get(d) for d in dates]
    diffs = []
    prev = None
    for v in vals:
        if v is None or prev is None:
            diffs.append(None)
        else:
            diffs.append(v - prev)
        if v is not None:
            prev = v
    present = [d for d in diffs if d is not None]
    if len(present) < 3:
        return diffs
    m = sum(present) / len(present)
    sd = (sum((x - m) ** 2 for x in present) / len(present)) ** 0.5
    return [((d - m) / sd if (d is not None and sd > 0) else None) for d in diffs]


def main():
    # collect pooled (dKalshi, dConsensus) daily pairs per lag, per company
    per_company_pairs = {name: [] for name in FSYM}  # list of (dK_series, dC_series) aligned by date
    for name, rid in FSYM.items():
        seen, markets = set(), []
        for pfx in PREFIXES[name]:
            d = kget("/historical/markets", {"series_ticker": pfx, "limit": 1000})
            for m in (d or {}).get("markets", []):
                t = m.get("ticker")
                if t and t not in seen:
                    seen.add(t); markets.append(m)
        by_event = {}
        for m in markets:
            by_event.setdefault(m.get("event_ticker"), []).append(m)
        for et, ms in by_event.items():
            kday = kalshi_daily(name, et, ms)
            if len(kday) < 8:
                continue
            close_iso = ms[0].get("close_time") or ""
            report_date = close_iso[:10]
            # map Kalshi event to fiscal quarter end: use the last date of kday's quarter.
            # FE_FP_END nearest to report_date: query actuals report_date -> fp_end
            r = mcp("factset_query", {"sql":
                f"SELECT FE_FP_END, REPORT_DATE FROM FACTSET_LISTING.FE_V4.FE_BASIC_ACT_QF "
                f"WHERE FSYM_ID='{rid}' AND FE_ITEM='SALES' AND FE_FP_END>='2023-06-01' "
                f"ORDER BY FE_FP_END", "max_rows": 40})
            # pick fp_end whose REPORT_DATE nearest to Kalshi close
            cd = datetime.fromisoformat(report_date).date()
            best = None; bg = 999
            for row in r.get("rows", []):
                if not row.get("REPORT_DATE"):
                    continue
                g = abs((datetime.fromisoformat(row["REPORT_DATE"][:10]).date() - cd).days)
                if g < bg:
                    bg = g; best = row
            if not best or bg > 45:
                continue
            fp_end = best["FE_FP_END"][:10]; rpt = best["REPORT_DATE"][:10]
            snaps = consensus_daily(rid, fp_end, rpt)
            # common daily grid = last WINDOW_DAYS before report
            end = datetime.fromisoformat(rpt).date() - timedelta(days=1)
            start = end - timedelta(days=WINDOW_DAYS)
            cgrid = to_daily_grid(snaps, start, end)
            dates = [start + timedelta(days=i) for i in range((end - start).days + 1)]
            dK = zscore_diffs(kday, dates)
            dC = zscore_diffs(cgrid, dates)
            per_company_pairs[name].append((dK, dC))
        print(f"{name}: {len(per_company_pairs[name])} quarters with paired series", file=sys.stderr)

    # lagged cross-correlation, pooled across all quarters & companies
    def corr_at_lag(pairs, lag):
        xs, ys = [], []
        for dK, dC in pairs:
            n = len(dK)
            for t in range(n):
                tt = t + lag
                if 0 <= tt < n and dK[t] is not None and dC[tt] is not None:
                    xs.append(dK[t]); ys.append(dC[tt])
        m = len(xs)
        if m < 5:
            return None, m
        mx = sum(xs) / m; my = sum(ys) / m
        cov = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
        sx = sum((a - mx) ** 2 for a in xs) ** 0.5; sy = sum((b - my) ** 2 for b in ys) ** 0.5
        return (cov / (sx * sy) if sx and sy else None), m

    all_pairs = [p for name in FSYM for p in per_company_pairs[name]]
    rows = []
    print("\n=== LEAD-LAG: corr(dKalshi[t], dConsensus[t+lag]) — pooled all companies ===")
    print("  lag>0 => Kalshi leads consensus by |lag| days")
    best = (None, -9)
    for lag in LAGS:
        r, m = corr_at_lag(all_pairs, lag)
        rows.append({"scope": "ALL", "lag": lag, "corr": "" if r is None else round(r, 4), "n": m})
        bar = ""
        if r is not None:
            bar = ("+" if r >= 0 else "-") * int(abs(r) * 40)
            if r > best[1]:
                best = (lag, r)
        print(f"  lag={lag:+3d}  r={0 if r is None else r:+.3f} (n={m:4d})  {bar}")
    print(f"\n  PEAK: lag={best[0]:+d}  r={best[1]:+.3f}  "
          f"({'Kalshi LEADS' if best[0] and best[0]>0 else ('consensus leads' if best[0]<0 else 'contemporaneous')})")

    # per-company peak
    print("\n=== per-company peak lag ===")
    for name in FSYM:
        pairs = per_company_pairs[name]
        pk = (None, -9)
        for lag in LAGS:
            r, m = corr_at_lag(pairs, lag)
            if r is not None and r > pk[1]:
                pk = (lag, r, m)
            rows.append({"scope": name, "lag": lag, "corr": "" if r is None else round(r, 4), "n": m})
        if pk[0] is not None:
            print(f"  {name:10s} peak lag={pk[0]:+d} r={pk[1]:+.3f} (n={pk[2]})")

    OUT.parent.mkdir(exist_ok=True)
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["scope", "lag", "corr", "n"]); w.writeheader(); w.writerows(rows)
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
