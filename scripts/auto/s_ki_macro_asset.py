#!/usr/bin/env python3
"""
s_ki_macro_asset.py — EXP-4: do Kalshi MACRO markets predict ASSET moves on release day?

For each macro release (CPI, NFP, ...) with a Kalshi strike ladder:
  implied_value[T-k]  = implied expectation from the ladder (survival -> mean threshold)
  X (market surprise) = implied_late(T-1) - implied_early(T-7)   [market's revision]
                        and  realized - implied_late             [vs-market surprise]
  Y (asset reaction)  = release-day market-adj return of a macro-sensitive asset:
                          CPI/PCE -> TLT (bonds, inverse to inflation), SPY
                          NFP     -> TLT, SPY
Hypothesis: if the prediction market carries macro info, its implied/surprise correlates
with the release-day asset move. If the market is efficient, the move is in the *residual*
(realized - implied), not the implied level.

Prices via FMP historical (key in mcp-server-combined/.env). Kalshi via public API.
"""
import csv
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "kalshi_macro_asset.csv"
BASE = "https://api.elections.kalshi.com/trade-api/v2"
H = {"accept": "application/json", "user-agent": "carbonarc-research/1.0"}
# FMP key: env var FMP_API_KEY, else a .env pointed to by MCP_SERVER_ENV
ENV = Path(os.environ.get("MCP_SERVER_ENV", ""))

MACROS = {
    "CPI":  {"prefixes": ["KXCPI", "CPI"],           "assets": ["TLT", "SPY"]},
    "NFP":  {"prefixes": ["KXPAYROLLS", "PAYROLLS"], "assets": ["TLT", "SPY"]},
    "PCE":  {"prefixes": ["KXPCECORE", "PCECORE"],   "assets": ["TLT", "SPY"]},
}
SNAP_LATE, SNAP_EARLY = 1, 7

sess = requests.Session(); sess.headers.update(H)


def fmp_key():
    if os.environ.get("FMP_API_KEY"):
        return os.environ["FMP_API_KEY"]
    if ENV and ENV.exists():
        for line in ENV.read_text().splitlines():
            if line.startswith("FMP_API_KEY="):
                return line.split("=", 1)[1].strip()
    sys.exit("no FMP key")


KEY = fmp_key()
_pc = {}


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


def fmp_hist(sym, d0, d1):
    ck = (sym, d0, d1)
    if ck in _pc:
        return _pc[ck]
    url = (f"https://financialmodelingprep.com/api/v3/historical-price-full/{sym}"
           f"?from={d0}&to={d1}&apikey={KEY}")
    for _ in range(3):
        try:
            d = json.loads(urllib.request.urlopen(url, timeout=25).read())
            out = {r["date"]: r["close"] for r in (d.get("historical", []) if isinstance(d, dict) else [])}
            _pc[ck] = out; time.sleep(0.15); return out
        except Exception:
            time.sleep(0.6)
    _pc[ck] = {}; return {}


def ret_release(sym, rd):
    d = datetime.fromisoformat(rd).date()
    px = fmp_hist(sym, (d - timedelta(days=8)).isoformat(), (d + timedelta(days=8)).isoformat())
    if not px:
        return None
    dates = sorted(px)
    ge = [x for x in dates if x >= rd]
    if not ge:
        return None
    a = ge[0]; ai = dates.index(a)
    if ai == 0:
        return None
    p0 = px[dates[ai - 1]]
    return px[a] / p0 - 1.0 if p0 else None


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


def implied_expectation(markets, k_days):
    """implied expected threshold value at T-k. markets = one release ladder.
    survival S(x)=P(value>=x); mean = sum of interval mass * midpoint."""
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
        return None, None
    close_iso = strikes[0][1].get("close_time") or ""
    if not close_iso:
        return None, None
    T = iso(close_iso)
    cut = T - k_days * 86400
    xs, probs = [], []
    for x, m in strikes:
        ot = iso(m.get("open_time") or close_iso)
        d = kget(f"/historical/markets/{m['ticker']}/candlesticks",
                 {"start_ts": ot, "end_ts": T, "period_interval": 1440})
        best = None
        for c in (d or {}).get("candlesticks", []):
            ep = c.get("end_period_ts")
            if ep is None or ep >= cut:
                continue
            if best is None or ep > best.get("end_period_ts", -1):
                best = c
        p = None
        if best:
            pr = best.get("price") or {}
            if pr.get("close") is not None:
                p = float(pr["close"])
            else:
                yb = (best.get("yes_bid") or {}).get("close"); ya = (best.get("yes_ask") or {}).get("close")
                yb = float(yb) if yb is not None else None; ya = float(ya) if ya is not None else None
                p = (yb + ya) / 2 if (yb is not None and ya is not None) else (yb if yb is not None else ya)
        xs.append(x); probs.append(p)
        time.sleep(0.008)
    # need coverage
    if sum(1 for p in probs if p is not None) < 2:
        return None, close_iso[:10]
    # fill + monotone survival -> mean threshold
    filled = list(probs)
    for i, v in enumerate(filled):
        if v is None:
            lo = next((filled[j] for j in range(i - 1, -1, -1) if filled[j] is not None), None)
            hi = next((filled[j] for j in range(i + 1, len(filled)) if filled[j] is not None), None)
            filled[i] = (lo if lo is not None else hi) if (lo is None or hi is None) else (lo + hi) / 2
    s = list(filled)
    for i in range(1, len(s)):
        s[i] = min(s[i], s[i - 1])
    s = [max(0.0, min(1.0, v)) for v in s]
    pts, mass = [xs[-1]], [s[-1]]
    for i in range(len(xs) - 1):
        mm = s[i] - s[i + 1]
        if mm > 1e-9:
            pts.append((xs[i] + xs[i + 1]) / 2); mass.append(mm)
    below = 1.0 - s[0]
    if below > 1e-9:
        pts.append(xs[0]); mass.append(below)
    tot = sum(mass)
    if tot <= 1e-6:
        return None, close_iso[:10]
    return sum(p * m for p, m in zip(pts, mass)) / tot, close_iso[:10]


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None, n
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    sx = sum((a - mx) ** 2 for a in xs) ** 0.5; sy = sum((b - my) ** 2 for b in ys) ** 0.5
    return (cov / (sx * sy) if sx and sy else None), n


def main():
    rows = []
    for macro, cfg in MACROS.items():
        seen, markets = set(), []
        for pfx in cfg["prefixes"]:
            for m in series_markets(pfx):
                t = m.get("ticker")
                if t and t not in seen:
                    seen.add(t); markets.append(m)
        by_event = {}
        for m in markets:
            if m.get("result") in ("yes", "no"):
                by_event.setdefault(m.get("event_ticker"), []).append(m)
        print(f"{macro}: {len(by_event)} resolved releases", file=sys.stderr)
        for et, ms in sorted(by_event.items()):
            late, rd = implied_expectation(ms, SNAP_LATE)
            early, _ = implied_expectation(ms, SNAP_EARLY)
            if late is None or rd is None:
                continue
            # market revision = late - early implied expectation
            revision = (late - early) if early is not None else None
            row = {"macro": macro, "event": et, "release_date": rd,
                   "implied_late": round(late, 4),
                   "implied_early": "" if early is None else round(early, 4),
                   "revision": "" if revision is None else round(revision, 4)}
            for a in cfg["assets"]:
                r = ret_release(a, rd)
                spy = ret_release("SPY", rd)
                row[f"ret_{a}"] = "" if r is None else round(r, 4)
                row[f"ret_{a}_madj"] = ("" if (r is None or spy is None or a == "SPY")
                                        else round(r - spy, 4))
            rows.append(row)

    OUT.parent.mkdir(exist_ok=True)
    cols = sorted({k for r in rows for k in r})
    # stable-ish ordering
    front = ["macro", "event", "release_date", "implied_late", "implied_early", "revision"]
    cols = front + [c for c in cols if c not in front]
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)
    print(f"\nwrote {OUT}  ({len(rows)} releases)")

    # correlations: market revision -> asset move (per macro, per asset)
    print("\n=== market revision (implied_late - implied_early) -> release-day asset move ===")
    for macro, cfg in MACROS.items():
        sub = [r for r in rows if r["macro"] == macro and r["revision"] != ""]
        if len(sub) < 3:
            print(f"  {macro}: n={len(sub)} (too few)"); continue
        for a in cfg["assets"]:
            ycol = f"ret_{a}_madj" if a != "SPY" else f"ret_{a}"
            pairs = [(r["revision"], r[ycol]) for r in sub if r.get(ycol) not in (None, "")]
            if len(pairs) < 3:
                continue
            r, n = pearson([p for p, _ in pairs], [q for _, q in pairs])
            print(f"  {macro:5s} revision -> {a:4s}: corr={0 if r is None else round(r,3):+.3f} (n={n})")


if __name__ == "__main__":
    main()
