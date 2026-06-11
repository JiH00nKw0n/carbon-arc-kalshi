#!/usr/bin/env python3
"""
s_r_revenue_surprise.py — the clean causal/information test (the last gap).

Does CA know more about REVENUE than analysts? = does CA_surprise predict the REVENUE surprise
(actual − point-in-time consensus)? Cleaner than the EPS proxy (H2): revenue is what card spend
directly measures, and revenueEstimated from FMP is the pre-report consensus.

H_REV : CA_surprise(Q) → revenue_surprise = (rev_actual − rev_est)/rev_est
sanity: (a) does revenue_surprise move the stock? corr(rev_surprise, earnings-day return)
        (b) does CA at least track actual revenue growth? (near-tautological check)
H4    : H_REV by card-share tercile.
Inference: company-clustered bootstrap + shuffle-company surrogate (reuse s_q helpers).
Consensus source: FMP /stable/earnings (revenueEstimated/Actual), key from agent-server/.env.
"""
import re, time, sys
from pathlib import Path
import requests
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import s_q_edge_tests as eq  # build_ca_surprise, cluster_boot, surrogate, per_company_cardshare

ROOT = Path(__file__).resolve().parents[2]
A = ROOT / "outputs" / "auto"
OUT_MD = ROOT / "docs" / "analysis_company_revsurprise.md"
TICKERS = "WMT TGT COST HD LOW DG DLTR KR TJX ROST BBY MCD SBUX CMG YUM DPZ WEN DRI TXRH NKE LULU GAP AEO ANF URBN AMZN AAPL ETSY CHWY ABNB UBER DAL NFLX DASH CAVA".split()
lines = []
def log(s=""): print(s); lines.append(s)

def key():
    for line in open("/Users/junekwon/Desktop/Projects/agent-server/.env"):
        mo = re.match(r'^FMP_API_KEY\s*=\s*"?([A-Za-z0-9]+)"?', line.strip())
        if mo: return mo.group(1)
KEY = key()

def fetch_rev_estimates():
    rows = []
    for t in TICKERS:
        try:
            r = requests.get("https://financialmodelingprep.com/stable/earnings",
                             params={"symbol": t, "apikey": KEY, "limit": 40}, timeout=20)
            d = r.json() if r.status_code == 200 else []
        except Exception:
            d = []
        for e in d if isinstance(d, list) else []:
            ra, re_ = e.get("revenueActual"), e.get("revenueEstimated")
            if ra and re_:
                rows.append([t, e.get("date"), ra, re_])
        time.sleep(0.03)
    df = pd.DataFrame(rows, columns=["ticker", "report_date", "rev_actual", "rev_est"])
    df["report_date"] = pd.to_datetime(df["report_date"])
    df["rev_surprise"] = (df["rev_actual"] - df["rev_est"]) / df["rev_est"]
    return df

def main():
    rev = fetch_rev_estimates()
    log("# Clean causal/information test — CA → REVENUE surprise (actual − consensus)")
    log(f"\nreports with revenue estimate+actual: {len(rev)} across {rev.ticker.nunique()} tickers; "
        f"{rev.report_date.min().date()}..{rev.report_date.max().date()}")
    log(f"revenue-surprise: mean={rev.rev_surprise.mean():+.4f} sd={rev.rev_surprise.std():.4f} (≈0 ⇒ consensus ~unbiased)")

    ca = eq.build_ca_surprise()
    rev["key"] = rev["report_date"] - pd.Timedelta(days=45)
    parts = []
    for t in rev.ticker.unique():
        e = rev[rev.ticker == t].sort_values("key")
        a = ca[ca.ticker == t].sort_values("date")
        if a.empty: continue
        m = pd.merge_asof(e, a[["date", "ca_yoy", "ca_surprise"]], left_on="key", right_on="date",
                          direction="nearest", tolerance=pd.Timedelta(days=60))
        parts.append(m)
    d = pd.concat(parts, ignore_index=True).dropna(subset=["ca_surprise", "rev_surprise"])
    # merge earnings-day return for sanity (a)
    ep = pd.read_csv(A / "edge_panel.csv"); ep["report_date"] = pd.to_datetime(ep["report_date"])
    d = d.merge(ep[["ticker", "report_date", "ret_earn_mktadj"]], on=["ticker", "report_date"], how="left")
    cs = eq.per_company_cardshare(); d["cardshare"] = d["ticker"].map(cs)
    log(f"aligned CA_surprise × revenue_surprise: {len(d)} events, {d.ticker.nunique()} tickers")

    # H_REV
    r, p, n = eq.cluster_boot(d, "ca_surprise", "rev_surprise")
    s = eq.surrogate(d, "ca_surprise", "rev_surprise", r) if not np.isnan(r) else np.nan
    log("\n## H_REV — CA_surprise → revenue surprise (does CA beat the revenue consensus?)")
    log(f"  r={r:+.3f} (n={n}) p_boot={p:.3f} p_surrogate={s:.3f}")
    # also raw ca_yoy vs rev_surprise (in case residualization hurts)
    r2, p2, n2 = eq.cluster_boot(d, "ca_yoy", "rev_surprise")
    log(f"  [raw ca_yoy → rev_surprise]: r={r2:+.3f} p_boot={p2:.3f}")

    # sanity (a): revenue surprise → stock move
    sa = d.dropna(subset=["rev_surprise", "ret_earn_mktadj"])
    ra = sa["rev_surprise"].corr(sa["ret_earn_mktadj"]) if len(sa) > 10 else np.nan
    log(f"\n## sanity(a) revenue_surprise → earnings-day return: r={ra:+.3f} (n={len(sa)})  "
        f"({'market reacts to rev surprise ✓' if ra>0.1 else 'weak'})")
    # sanity (b): CA tracks actual revenue growth (near-tautological)
    d2 = d.copy();
    rb, pb, nb = eq.cluster_boot(d2.assign(rev_a=d2['rev_actual']), "ca_yoy", "rev_a")
    log(f"## sanity(b) CA_yoy ↔ revenue level corr (should be high): r={rb:+.3f}")

    # H4 by card-share tercile
    log("\n## H4 — H_REV by card-share tercile")
    d["cs_tier"] = pd.qcut(d["cardshare"].rank(method="first"), 3, labels=["low", "mid", "high"])
    for tier in ["high", "mid", "low"]:
        sub = d[d.cs_tier == tier]
        rr, pp, nn = eq.cluster_boot(sub, "ca_surprise", "rev_surprise")
        log(f"  cardshare={tier:4s}: r={rr:+.3f} (p{pp:.2f}, n{nn})")

    ok = (not np.isnan(s)) and s < 0.05 and p < 0.05
    log("\n## VERDICT")
    if ok:
        log(f"  ✅ CA predicts the REVENUE surprise (r={r:+.3f}, surrogate p={s:.3f}) → CA knows more than the revenue consensus.")
        log("     (Then re-check why H1 return was null: info present but priced, or EPS≠revenue.)")
    else:
        log(f"  ❌ NULL — CA does NOT predict the revenue surprise (r={r:+.3f}, surrogate p={s:.3f}).")
        log("     Closes the information layer: CA carries NO revenue information beyond analyst consensus.")
        log("     ⇒ CA at company level = a MEASUREMENT of revenue, already embedded in consensus/price. No edge.")
    OUT_MD.write_text("# CA → revenue surprise (clean info test)\n\n> 2026-06-03 · `scripts/auto/s_r_revenue_surprise.py`\n\n```\n" + "\n".join(lines) + "\n```\n")
    print(f"\n[written] {OUT_MD}")

if __name__ == "__main__":
    main()
