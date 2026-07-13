#!/usr/bin/env python3
"""
s_kg_kpi_return.py — EXP-2: does the Kalshi KPI surprise move the STOCK on earnings day?

factor3's dead end was "revenue surprise barely moves the stock (~0.07)". Here we test
the KPI channel directly, and on returns (tradeable), not revenue.

X = KPI surprise = (realized_KPI - Kalshi_implied_KPI[T-1]) / implied   (market's own miss)
    Kalshi implied is a strong KPI predictor (GATE1 r~0.95), so this surprise is the part
    that surprised the market too.
Y = earnings-day market-adjusted return = ret(stock, report_date window) - ret(SPY, same)
    prices from FMP historical (key in mcp-server-combined/.env). window = report_date close
    vs prior close (t/t-1), robustness t+1.

Reads outputs/kalshi_X.csv (implied T-1 + realized_kpi) and outputs/kalshi_panel.csv
(report_date). Correlates KPI surprise -> return, plus long-beat/short-miss mean.
"""
import csv
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
XCSV = ROOT / "outputs" / "kalshi_X.csv"
PANEL = ROOT / "outputs" / "kalshi_panel.csv"
OUT = ROOT / "outputs" / "kalshi_kpi_return.csv"
# FMP key: env var FMP_API_KEY, else a .env pointed to by MCP_SERVER_ENV
ENV = Path(os.environ.get("MCP_SERVER_ENV", ""))

TICKER = {"Tesla": "TSLA", "MetaDAP": "META", "Netflix": "NFLX", "NYT": "NYT",
          "Robinhood": "HOOD", "Spotify": "SPOT", "SoFi": "SOFI"}


def fmp_key():
    if os.environ.get("FMP_API_KEY"):
        return os.environ["FMP_API_KEY"]
    if ENV and ENV.exists():
        for line in ENV.read_text().splitlines():
            if line.startswith("FMP_API_KEY="):
                return line.split("=", 1)[1].strip()
    sys.exit("set FMP_API_KEY (or MCP_SERVER_ENV pointing to a .env with it)")


KEY = fmp_key()
_price_cache = {}


def fmp_hist(sym, d0, d1):
    ck = (sym, d0, d1)
    if ck in _price_cache:
        return _price_cache[ck]
    url = (f"https://financialmodelingprep.com/api/v3/historical-price-full/{sym}"
           f"?from={d0}&to={d1}&apikey={KEY}")
    for _ in range(3):
        try:
            d = json.loads(urllib.request.urlopen(url, timeout=25).read())
            hist = d.get("historical", []) if isinstance(d, dict) else []
            out = {r["date"]: r["close"] for r in hist}
            _price_cache[ck] = out
            time.sleep(0.15)
            return out
        except Exception:
            time.sleep(0.6)
    _price_cache[ck] = {}
    return {}


def ret_around(sym, report_date, offset_after=0):
    """close(report_date+offset_after) / close(prior trading day) - 1."""
    rd = datetime.fromisoformat(report_date).date()
    px = fmp_hist(sym, (rd - timedelta(days=8)).isoformat(), (rd + timedelta(days=8)).isoformat())
    if not px:
        return None
    dates = sorted(px)
    # anchor day = first trading day >= report_date, shifted by offset_after
    ge = [d for d in dates if d >= report_date]
    if not ge:
        return None
    anchor = ge[min(offset_after, len(ge) - 1)]
    ai = dates.index(anchor)
    if ai == 0:
        return None
    prior = dates[ai - 1]
    if px[prior] in (0, None):
        return None
    return px[anchor] / px[prior] - 1.0


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None, n
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    sx = sum((a - mx) ** 2 for a in xs) ** 0.5
    sy = sum((b - my) ** 2 for b in ys) ** 0.5
    return (cov / (sx * sy) if sx and sy else None), n


def main():
    # implied T-1 + realized per (name,event)
    implied, realized = {}, {}
    for r in csv.DictReader(open(XCSV)):
        if r["k"] == "1" and r["implied_mean"]:
            implied[(r["name"], r["event"])] = float(r["implied_mean"])
        if r["realized_kpi"]:
            realized[(r["name"], r["event"])] = float(r["realized_kpi"])
    report_date = {}
    for r in csv.DictReader(open(PANEL)):
        report_date[(r["name"], r["event"])] = r["report_date"]

    rows = []
    for key in sorted(implied):
        name, event = key
        if key not in realized or key not in report_date:
            continue
        imp = implied[key]; rz = realized[key]; rd = report_date[key]
        if imp == 0:
            continue
        kpi_surprise = (rz - imp) / abs(imp)
        sym = TICKER[name]
        spy = ret_around("SPY", rd, 0)
        r0 = ret_around(sym, rd, 0)
        r1 = ret_around(sym, rd, 1)
        if r0 is None or spy is None:
            continue
        madj0 = r0 - spy
        spy1 = ret_around("SPY", rd, 1)
        madj1 = (r1 - spy1) if (r1 is not None and spy1 is not None) else None
        rows.append({"name": name, "event": event, "report_date": rd,
                     "implied_kpi": round(imp, 2), "realized_kpi": rz,
                     "kpi_surprise": round(kpi_surprise, 4),
                     "ret_madj_t0": round(madj0, 4),
                     "ret_madj_t1": "" if madj1 is None else round(madj1, 4)})

    OUT.parent.mkdir(exist_ok=True)
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

    print(f"panel: {len(rows)} events with KPI-surprise + earnings-day return")
    print("(note: realized_kpi only present where Kalshi expiration_value is numeric —"
          " Tesla & some; Meta/subs settle 'Yes' → excluded)\n")

    # overall + per company
    def block(sub, label):
        xs = [r["kpi_surprise"] for r in sub]
        for ycol in ("ret_madj_t0", "ret_madj_t1"):
            pairs = [(r["kpi_surprise"], r[ycol]) for r in sub if r[ycol] != ""]
            if len(pairs) < 3:
                print(f"  {label:18s} {ycol}: n={len(pairs)} (too few)"); continue
            xs2 = [a for a, _ in pairs]; ys2 = [b for _, b in pairs]
            r, n = pearson(xs2, ys2)
            # long-beat / short-miss: sign(surprise)*return
            dirpnl = sum((1 if a > 0 else -1) * b for a, b in pairs) / len(pairs)
            print(f"  {label:18s} {ycol}: corr={0 if r is None else round(r,3):+.3f} (n={n})  "
                  f"dir-PnL={dirpnl:+.4f}")

    print("=== KPI surprise -> earnings-day market-adj return ===")
    block(rows, "ALL")
    for name in TICKER:
        sub = [r for r in rows if r["name"] == name]
        if len(sub) >= 3:
            block(sub, name)
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
