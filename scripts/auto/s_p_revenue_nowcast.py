#!/usr/bin/env python3
"""
s_p_revenue_nowcast.py — Track A: does CarbonArc card spend nowcast COMPANY revenue?

Company-level pivot (macro thesis was a comprehensive null). X = CA card spend per ticker per
quarter (bought: 35 consumer tickers). Y = reported quarterly revenue (FMP). Unit = company-quarter
→ big N across companies AND quarters (escapes the macro single-cycle/small-N problem), and card
spend is a LARGE fraction of a consumer company's revenue (high signal ratio).

Hypotheses (results interpreted in experiments/test_2026-06-03.md):
  H1  LEVELS: within company, does CA card-spend level track revenue level? (panel representativeness)
  H2  GROWTH: does CA YoY growth track revenue YoY growth? (the useful nowcast — predicts the change)
  H3  SECTOR: is the link stronger for high-card-share sectors (restaurants/specialty) vs e-comm/membership?
  H4  LEAD vs CONTEMP: CA quarter Q (known ~weeks before the Q earnings print) vs revenue Q.

Alignment: CA = calendar quarter-end; FMP revenue = fiscal quarter-end. Match per ticker by NEAREST
date (≤50d) → handles fiscal offset; YoY (÷4 quarters) further neutralizes fixed offset.
Inference: pooled corr with COMPANY-clustered bootstrap + shuffle-company surrogate.
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CA = ROOT / "outputs" / "auto" / "ca0056_card_spend_by_ticker_q_3y.csv"
REV = ROOT / "outputs" / "auto" / "fmp_revenue_by_ticker.csv"
OUT_MD = ROOT / "docs" / "analysis_company_revenue.md"

SECTOR = {
    **{t: "restaurant" for t in ["MCD","SBUX","CMG","YUM","DPZ","WEN","DRI","TXRH","CAVA"]},
    **{t: "bigbox_retail" for t in ["WMT","TGT","COST","HD","LOW"]},
    **{t: "discount" for t in ["DG","DLTR","KR","TJX","ROST","BBY"]},
    **{t: "apparel_specialty" for t in ["NKE","LULU","GAP","AEO","ANF","URBN"]},
    **{t: "ecom_digital" for t in ["AMZN","AAPL","ETSY","CHWY","NFLX"]},
    **{t: "travel_gig" for t in ["ABNB","UBER","DAL","DASH"]},
}

lines = []
def log(s=""):
    print(s); lines.append(s)


def load_aligned():
    ca = pd.read_csv(CA)
    ca = ca.groupby(["entity_name", "date"], as_index=False)["credit_card_spend"].sum()
    ca["date"] = pd.to_datetime(ca["date"])
    ca = ca.rename(columns={"entity_name": "ticker", "credit_card_spend": "ca"})
    rev = pd.read_csv(REV)
    rev["date"] = pd.to_datetime(rev["date"])
    rev = rev.dropna(subset=["revenue"])[["ticker", "date", "revenue"]]
    out = []
    for t in ca["ticker"].unique():
        a = ca[ca.ticker == t].sort_values("date")
        r = rev[rev.ticker == t].sort_values("date")
        if len(a) < 5 or len(r) < 5:
            continue
        merged = pd.merge_asof(r, a[["date", "ca"]], on="date", direction="nearest",
                               tolerance=pd.Timedelta(days=50)).dropna(subset=["ca"])
        merged = merged.sort_values("date")
        merged["ca_yoy"] = merged["ca"].pct_change(4)
        merged["rev_yoy"] = merged["revenue"].pct_change(4)
        merged["ticker"] = t
        out.append(merged)
    return pd.concat(out, ignore_index=True)


def clustered_boot(df, xcol, ycol, n=3000):
    d = df.dropna(subset=[xcol, ycol])
    if len(d) < 10:
        return np.nan, np.nan, np.nan, 0
    r0 = d[xcol].corr(d[ycol])
    ticks = d["ticker"].unique()
    rng = np.random.default_rng(7)
    boots = []
    for _ in range(n):
        samp = rng.choice(ticks, len(ticks), replace=True)
        sub = pd.concat([d[d.ticker == k] for k in samp])
        if sub[xcol].std() < 1e-12 or sub[ycol].std() < 1e-12:
            continue
        boots.append(sub[xcol].corr(sub[ycol]))
    boots = np.array(boots)
    lo, hi = np.percentile(boots, [2.5, 97.5])
    p = 2 * min((boots > 0).mean(), (boots < 0).mean())
    return r0, lo, hi, p


def surrogate(df, xcol, ycol, r_obs, n=2000):
    """shuffle CA series across companies (break ticker pairing), preserve each series shape."""
    d = df.dropna(subset=[xcol, ycol]).copy()
    ticks = list(d["ticker"].unique())
    rng = np.random.default_rng(11)
    ge = tot = 0
    # build per-ticker x-vectors keyed by within-ticker order
    by = {t: d[d.ticker == t][[xcol, ycol]].reset_index(drop=True) for t in ticks}
    for _ in range(n):
        perm = rng.permutation(ticks)
        xs, ys = [], []
        for t, ps in zip(ticks, perm):
            yv = by[t][ycol].values
            xv = by[ps][xcol].values
            k = min(len(yv), len(xv))
            xs += list(xv[:k]); ys += list(yv[:k])
        xs, ys = np.array(xs), np.array(ys)
        if np.std(xs) < 1e-12 or np.std(ys) < 1e-12:
            continue
        tot += 1
        if abs(np.corrcoef(xs, ys)[0, 1]) >= abs(r_obs):
            ge += 1
    return (ge + 1) / (tot + 1)


def main():
    df = load_aligned()
    df["sector"] = df["ticker"].map(SECTOR)
    log("# Track A — CarbonArc card spend → company revenue (nowcast)")
    log(f"\naligned company-quarters: {len(df)} across {df.ticker.nunique()} tickers; "
        f"date {df.date.min().date()}..{df.date.max().date()}")

    # H1 LEVELS (within-company), H2 GROWTH (within-company) — per-company corr distribution
    per = []
    for t, g in df.groupby("ticker"):
        g2 = g.dropna(subset=["ca", "revenue"])
        gl = g.dropna(subset=["ca_yoy", "rev_yoy"])
        lev = g2["ca"].corr(g2["revenue"]) if len(g2) >= 5 else np.nan
        yoy = gl["ca_yoy"].corr(gl["rev_yoy"]) if len(gl) >= 5 else np.nan
        per.append((t, SECTOR.get(t), len(g2), lev, yoy))
    perdf = pd.DataFrame(per, columns=["ticker", "sector", "nq", "level_corr", "yoy_corr"])

    log("\n## H1 (levels) & H2 (YoY growth): per-company correlation")
    log(f"  LEVELS  median r = {perdf.level_corr.median():+.3f} | frac r>0.5: {(perdf.level_corr>0.5).mean():.0%} | frac r>0: {(perdf.level_corr>0).mean():.0%}")
    log(f"  GROWTH  median r = {perdf.yoy_corr.median():+.3f} | frac r>0.3: {(perdf.yoy_corr>0.3).mean():.0%} | frac r>0: {(perdf.yoy_corr>0).mean():.0%}")

    rL, loL, hiL, pL = clustered_boot(df, "ca", "revenue")
    rG, loG, hiG, pG = clustered_boot(df, "ca_yoy", "rev_yoy")
    psG = surrogate(df, "ca_yoy", "rev_yoy", rG)
    log("\n## Pooled (company-clustered bootstrap + shuffle-company surrogate)")
    log(f"  H1 LEVELS pooled r={rL:+.3f} CI[{loL:+.2f},{hiL:+.2f}] p_boot={pL:.3f}")
    log(f"  H2 GROWTH pooled r={rG:+.3f} CI[{loG:+.2f},{hiG:+.2f}] p_boot={pG:.3f}  p_surrogate={psG:.3f}")

    # H4 LEAD vs CONTEMP: CA quarter Q vs revenue Q (contemp), and CA Q-1 vs revenue Q
    df2 = df.sort_values(["ticker", "date"]).copy()
    df2["ca_yoy_lag1"] = df2.groupby("ticker")["ca_yoy"].shift(1)   # prior quarter CA
    rC, *_ , pC = clustered_boot(df2, "ca_yoy", "rev_yoy")
    rLag, *_ , pLag = clustered_boot(df2, "ca_yoy_lag1", "rev_yoy")
    log("\n## H4 timing: contemporaneous vs lagged CA")
    log(f"  contemp  CA_yoy(Q)   vs rev_yoy(Q): r={rC:+.3f} p={pC:.3f}  (CA known ~weeks before the Q print → nowcast)")
    log(f"  lagged   CA_yoy(Q-1) vs rev_yoy(Q): r={rLag:+.3f} p={pLag:.3f}")

    # H3 SECTOR
    log("\n## H3 sector breakdown (pooled YoY growth corr)")
    for s, g in df.groupby("sector"):
        gg = g.dropna(subset=["ca_yoy", "rev_yoy"])
        if len(gg) >= 10:
            log(f"  {s:18s} n={len(gg):3d} tickers={gg.ticker.nunique():2d}  r(ca_yoy,rev_yoy)={gg['ca_yoy'].corr(gg['rev_yoy']):+.3f}")

    log("\n## per-company table")
    log(perdf.sort_values("yoy_corr", ascending=False).to_string(index=False))

    OUT_MD.write_text("# Track A — CarbonArc card → company revenue\n\n> 2026-06-03 · `scripts/auto/s_p_revenue_nowcast.py`\n\n```\n" + "\n".join(lines) + "\n```\n")
    print(f"\n[written] {OUT_MD}")


if __name__ == "__main__":
    main()
