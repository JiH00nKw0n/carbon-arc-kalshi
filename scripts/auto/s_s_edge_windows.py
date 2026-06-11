#!/usr/bin/env python3
"""
s_s_edge_windows.py — corrected EDGE test: trade from CA-availability, decompose return windows.

Fixes two flaws raised:
  (1) X should be CONSENSUS-REFERENCED, not CA-vs-own-trend:
        CA_vs_cons = ca_yoy(Q) − consensus_growth(Q),  consensus_growth = rev_est(Q)/rev_actual(Q-4) − 1
        (does CA see higher/lower revenue growth than the analyst consensus?)
  (2) You don't wait for the print — CA for quarter Q is known ~quarter-end. Measure the move from
      CA-availability, and DECOMPOSE:
        t_ca   = quarter_end + 7d (CA full-quarter read available)
        ret_pre   = [t_ca → day before print]      (pre-announcement drift; info diffusing in)
        ret_print = [day before → day after print]  (the print-day surprise jump; old H1)
        ret_total = [t_ca → day after print]        (realistic strategy return)
      all market-adjusted vs SPY.
Tests: corr(CA_vs_cons, rev_surprise) [info] and corr(CA_vs_cons, ret_{pre,print,total}) [edge by window]
       + L/S PnL on ret_total; company-clustered bootstrap + shuffle-company surrogate.
"""
import re, time, sys
from pathlib import Path
import requests
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import s_q_edge_tests as eq

ROOT = Path(__file__).resolve().parents[2]
A = ROOT / "outputs" / "auto"
OUT_MD = ROOT / "docs" / "analysis_company_edge_windows.md"
TICKERS = "WMT TGT COST HD LOW DG DLTR KR TJX ROST BBY MCD SBUX CMG YUM DPZ WEN DRI TXRH NKE LULU GAP AEO ANF URBN AMZN AAPL ETSY CHWY ABNB UBER DAL NFLX DASH CAVA".split()
lines = []
def log(s=""): print(s); lines.append(s)
KEY = next(re.match(r'^FMP_API_KEY\s*=\s*"?([A-Za-z0-9]+)"?', l.strip()).group(1)
           for l in open("/Users/junekwon/Desktop/Projects/agent-server/.env") if l.startswith("FMP_API_KEY"))

def fmp(path, **p):
    p["apikey"] = KEY
    for base in ["https://financialmodelingprep.com/stable", "https://financialmodelingprep.com/api/v3"]:
        try:
            r = requests.get(f"{base}/{path}", params=p, timeout=25)
            if r.status_code == 200 and r.json(): return r.json()
        except Exception: pass
    return None

def closes(t):
    d = fmp("historical-price-eod/full", symbol=t, **{"from": "2022-06-01", "to": "2026-06-03"})
    if not isinstance(d, list) or not d: return None
    s = pd.DataFrame(d)[["date", "close"]]; s["date"] = pd.to_datetime(s["date"])
    return s.set_index("date")["close"].sort_index()

def ret(cl, d0, d1):
    if cl is None: return None
    a = cl[cl.index <= d0]; b = cl[cl.index >= d1]
    if a.empty or b.empty: return None
    return b.iloc[0] / a.iloc[-1] - 1.0

def main():
    spy = closes("SPY")
    ca = eq.build_ca_surprise()  # ticker,date,ca_yoy,ca_surprise
    rev = pd.read_csv(A / "fmp_revenue_by_ticker.csv"); rev["date"] = pd.to_datetime(rev["date"])
    rev = rev.dropna(subset=["revenue"]).sort_values(["ticker", "date"])
    rev["rev_q4"] = rev.groupby("ticker")["revenue"].shift(4)  # prior-year same quarter

    rows = []
    for t in TICKERS:
        earn = fmp("earnings", symbol=t, limit=40)
        cl = closes(t)
        if not isinstance(earn, list) or cl is None: continue
        rv = rev[rev.ticker == t]
        cat = ca[ca.ticker == t].sort_values("date")
        for e in earn:
            ra, re_ = e.get("revenueActual"), e.get("revenueEstimated")
            if not (ra and re_): continue
            try: tp = pd.to_datetime(e.get("date"))
            except Exception: continue
            if tp.year < 2024 or tp > pd.Timestamp("2026-06-03"): continue
            # quarter being reported ≈ ends ~45d before print; align CA + prior-year actual
            qkey = tp - pd.Timedelta(days=45)
            cq = cat[cat.date <= qkey + pd.Timedelta(days=20)]
            if cq.empty or pd.isna(cq.iloc[-1]["ca_yoy"]): continue
            ca_yoy = cq.iloc[-1]["ca_yoy"]; q_end = cq.iloc[-1]["date"]
            rq = rv[(rv.date >= q_end - pd.Timedelta(days=40)) & (rv.date <= q_end + pd.Timedelta(days=40))]
            rev_q4 = rq.iloc[-1]["rev_q4"] if len(rq) and pd.notna(rq.iloc[-1]["rev_q4"]) else None
            if not rev_q4: continue
            cons_growth = re_ / rev_q4 - 1.0
            ca_vs_cons = ca_yoy - cons_growth
            rev_surprise = (ra - re_) / re_
            t_ca = q_end + pd.Timedelta(days=7)
            tb = tp - pd.Timedelta(days=1)
            def madj(d0, d1):
                r = ret(cl, d0, d1); s = ret(spy, d0, d1)
                return (r - s) if (r is not None and s is not None) else None
            rows.append({"ticker": t, "report_date": tp, "ca_vs_cons": ca_vs_cons, "rev_surprise": rev_surprise,
                         "ret_pre": madj(t_ca, tb), "ret_print": madj(tb, tp + pd.Timedelta(days=1)),
                         "ret_total": madj(t_ca, tp + pd.Timedelta(days=1))})
        time.sleep(0.03)
    d = pd.DataFrame(rows).dropna(subset=["ca_vs_cons"])
    log("# Corrected EDGE — consensus-referenced CA signal, return windows from CA-availability")
    log(f"\nevents: {len(d)} across {d.ticker.nunique()} tickers; {d.report_date.min().date()}..{d.report_date.max().date()}")
    log(f"CA_vs_cons mean={d.ca_vs_cons.mean():+.3f} sd={d.ca_vs_cons.std():.3f}")

    def test(y, label):
        r, p, n = eq.cluster_boot(d, "ca_vs_cons", y)
        s = eq.surrogate(d, "ca_vs_cons", y, r) if not np.isnan(r) else np.nan
        # L/S PnL: long if ca_vs_cons>0 else short
        sub = d.dropna(subset=["ca_vs_cons", y]); pos = np.sign(sub["ca_vs_cons"]); ls = pos * sub[y]
        t_ls = ls.mean() / (ls.std() / np.sqrt(len(ls))) if ls.std() > 0 else np.nan
        log(f"  {label:32s} r={r:+.3f} (n={n}) p_boot={p:.3f} p_surr={s:.3f} | L/S mean={ls.mean():+.4f} t={t_ls:+.2f}")
        return (not np.isnan(s)) and s < 0.05 and p < 0.05

    log("\n## INFO layer")
    i_ok = test("rev_surprise", "CA_vs_cons → rev_surprise")
    log("\n## EDGE by window (the key decomposition)")
    e_pre = test("ret_pre", "CA_vs_cons → ret_PRE (CA-avail→pre-print)")
    e_prn = test("ret_print", "CA_vs_cons → ret_PRINT (print-day, old H1)")
    e_tot = test("ret_total", "CA_vs_cons → ret_TOTAL (CA-avail→post-print)")

    log("\n## VERDICT")
    if e_pre or e_tot:
        log("  ✅ EARLY EDGE: CA predicts the pre-announcement drift / total window even if print-day didn't.")
        log("     ⇒ acting on CA when available is tradeable; print-day-only test understated it.")
    elif i_ok:
        log("  ~ CA predicts the revenue surprise but NOT any return window → info real but fully priced (no $).")
    else:
        log("  ❌ NULL across info + all return windows (pre/print/total). Even trading from CA-availability,")
        log("     CA carries no edge over consensus/price. Conclusion stands (not a windowing artifact).")
    OUT_MD.write_text("# Corrected EDGE (windows + consensus-referenced)\n\n> 2026-06-03 · `scripts/auto/s_s_edge_windows.py`\n\n```\n" + "\n".join(lines) + "\n```\n")
    print(f"\n[written] {OUT_MD}")

if __name__ == "__main__":
    main()
