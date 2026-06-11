#!/usr/bin/env python3
"""
s_q_edge_fetch.py — build the earnings-event panel for the EDGE tests (Step 1).

Per the 35 owned consumer tickers, pull (FREE, FMP REST; key from agent-server/.env):
  - earnings report dates + EPS actual/estimate  (/api/v3/earnings-surprises/{t})
  - daily closes → earnings-window return (close day-before → day-after), market-adjusted vs SPY
  - analyst coverage proxy (numAnalystsRevenue, current)
Output: outputs/auto/edge_panel.csv
  ticker, report_date, eps_actual, eps_est, eps_surprise_pct, ret_earn, ret_earn_mktadj, n_analysts
"""
import csv, re, time
from pathlib import Path
import requests
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "auto" / "edge_panel.csv"
TICKERS = "WMT TGT COST HD LOW DG DLTR KR TJX ROST BBY MCD SBUX CMG YUM DPZ WEN DRI TXRH NKE LULU GAP AEO ANF URBN AMZN AAPL ETSY CHWY ABNB UBER DAL NFLX DASH CAVA".split()

def fmp_key():
    for line in open("/Users/junekwon/Desktop/Projects/agent-server/.env"):
        mo = re.match(r'^FMP_API_KEY\s*=\s*"?([A-Za-z0-9]+)"?', line.strip())
        if mo:
            return mo.group(1)
    raise SystemExit("no FMP key")

KEY = fmp_key()
B = "https://financialmodelingprep.com"

def get(url, **p):
    p["apikey"] = KEY
    for _ in range(3):
        try:
            r = requests.get(url, params=p, timeout=25)
            if r.status_code == 200:
                return r.json()
            time.sleep(0.4)
        except Exception:
            time.sleep(0.4)
    return None

def daily_closes(t):
    d = get(f"{B}/stable/historical-price-eod/full", symbol=t, **{"from": "2022-06-01", "to": "2026-06-03"})
    if not isinstance(d, list) or not d:
        return None
    s = pd.DataFrame(d)[["date", "close"]].copy()
    s["date"] = pd.to_datetime(s["date"])
    return s.set_index("date")["close"].sort_index()

def earn_window_ret(closes, report_date):
    """close[last trading day < report] -> close[first trading day > report] (straddles BMO/AMC)."""
    if closes is None:
        return None
    before = closes[closes.index < report_date]
    after = closes[closes.index > report_date]
    if before.empty or after.empty:
        return None
    return after.iloc[0] / before.iloc[-1] - 1.0

def main():
    spy = daily_closes("SPY")
    rows = []
    for t in TICKERS:
        es = get(f"{B}/api/v3/earnings-surprises/{t}", limit=40)
        cl = daily_closes(t)
        # coverage proxy
        est = get(f"{B}/stable/analyst-estimates", symbol=t, period="quarter", limit=1)
        ncov = (est[0].get("numAnalystsRevenue") if isinstance(est, list) and est else None)
        if not isinstance(es, list):
            continue
        for e in es:
            try:
                rd = pd.to_datetime(e.get("date"))
            except Exception:
                continue
            if rd.year < 2022 or rd > pd.Timestamp("2026-06-03"):
                continue
            ea, ee = e.get("actualEarningResult"), e.get("estimatedEarning")
            ret = earn_window_ret(cl, rd)
            sret = earn_window_ret(spy, rd)
            if ret is None:
                continue
            eps_sur = ((ea - ee) / abs(ee)) if (ea is not None and ee not in (None, 0)) else None
            rows.append([t, rd.date(), ea, ee, eps_sur, round(ret, 5),
                         round(ret - sret, 5) if sret is not None else None, ncov])
        time.sleep(0.03)
    with open(OUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ticker", "report_date", "eps_actual", "eps_est", "eps_surprise_pct", "ret_earn", "ret_earn_mktadj", "n_analysts"])
        w.writerows(rows)
    df = pd.DataFrame(rows, columns=["ticker", "report_date", "eps_actual", "eps_est", "eps_surprise_pct", "ret_earn", "ret_earn_mktadj", "n_analysts"])
    print(f"rows={len(df)} tickers={df.ticker.nunique()} date {df.report_date.min()}..{df.report_date.max()}")
    print(f"non-null ret={df.ret_earn.notna().sum()} eps_surprise={df.eps_surprise_pct.notna().sum()}")
    print(f"median |ret_earn|={df.ret_earn.abs().median():.3f}  median n_analysts={df.n_analysts.dropna().median() if df.n_analysts.notna().any() else 'na'}")
    print(f"-> {OUT}")

if __name__ == "__main__":
    main()
