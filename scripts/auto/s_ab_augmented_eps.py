#!/usr/bin/env python3
"""
s_ab_augmented_eps.py — augment CA with FREE pre-earnings signals to predict the EPS surprise.

Card sees only revenue (~5% of the EPS surprise). The other ~95% (margin) needs signals that see the
bottom line BEFORE the print. The strongest free one = ANALYST ESTIMATE DYNAMICS (revision momentum,
dispersion, breadth) from FactSet — the classic earnings-prediction factor, all point-in-time pre-print.

Features (all known before the report):
  ca_yoy      : CA card-spend YoY (CA's semi-independent REVENUE read)
  eps_rev     : EPS consensus revision momentum = (mean_now − mean_90d)/|mean_90d|   ← the star
  eps_disp    : dispersion = FE_STD_DEV / |mean_now|
  eps_breadth : (FE_UP − FE_DOWN)/FE_NUM_EST  (net analysts revising up into the print)
Target: eps_surprise = (actual − point-in-time consensus)/|consensus|.

Questions: (1) do estimate dynamics predict the EPS surprise (the margin part CA can't see)?
           (2) does CA ADD anything beyond analyst dynamics, or is it redundant?
Inference: company-clustered bootstrap + shuffle-company surrogate.
Caveat: estimate dynamics are the analysts' OWN updating → predicting the surprise exploits documented
under-reaction (revision drift), and it is PUBLIC. CA's value is being a less-public, independent read.
"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
import s_q_edge_tests as eq
import s_t_revsurprise_factset as st
import s_u_epssurprise_factset as su
import s_z_pilot_test as sz

ROOT = Path("/Users/junekwon/Desktop/Projects/carbon_arc")
REVF = "/Users/junekwon/.claude/projects/-Users-junekwon-Desktop-Projects-carbon-arc/1012a692-88a4-497e-a3d6-cfbce4dbe924/tool-results/mcp-linq-factset_query-1780542650717.txt"
OUT_MD = ROOT / "docs" / "analysis_augmented_eps.md"
lines = []
def log(s=""): print(s); lines.append(s)

def main():
    rv = pd.DataFrame(json.load(open(REVF))["rows"])
    for c in ["MEAN_NOW", "MEAN_90", "FE_STD_DEV", "FE_NUM_EST", "FE_UP", "FE_DOWN"]:
        rv[c] = pd.to_numeric(rv[c], errors="coerce")
    rv["FE_FP_END"] = pd.to_datetime(rv["FE_FP_END"]); rv["ticker"] = rv["FSYM_ID"].map(st.FSYM2TKR)
    rv = rv.dropna(subset=["ticker", "MEAN_NOW", "MEAN_90"])
    rv = rv[(rv.MEAN_NOW.abs() >= 0.05) & (rv.MEAN_90.abs() >= 0.05)]
    rv["eps_rev"] = (rv.MEAN_NOW - rv.MEAN_90) / rv.MEAN_90.abs()
    rv["eps_disp"] = rv.FE_STD_DEV / rv.MEAN_NOW.abs()
    rv["eps_breadth"] = (rv.FE_UP - rv.FE_DOWN) / rv.FE_NUM_EST
    rv = rv[["ticker", "FE_FP_END", "eps_rev", "eps_disp", "eps_breadth"]]

    # target: EPS surprise
    e = su.load_eps()
    e["eps_surprise"] = (e["ACTUAL"] - e["CONS_EARLY"]) / e["CONS_EARLY"].abs()
    e = e[(e["ACTUAL"].abs() >= 0.05) & (e["CONS_EARLY"].abs() >= 0.05)]
    e = e[["ticker", "FE_FP_END", "eps_surprise"]]

    d = e.merge(rv, on=["ticker", "FE_FP_END"], how="inner")
    ca = eq.build_ca_surprise()[["ticker", "date", "ca_yoy"]]
    parts = []
    for t in d.ticker.unique():
        a = ca[ca.ticker == t].sort_values("date")
        if a.empty: continue
        m = pd.merge_asof(d[d.ticker == t].sort_values("FE_FP_END"), a[["date", "ca_yoy"]],
                          left_on="FE_FP_END", right_on="date", direction="nearest", tolerance=pd.Timedelta(days=50))
        parts.append(m)
    d = pd.concat(parts, ignore_index=True).dropna(subset=["ca_yoy"])
    for c in ["eps_surprise", "eps_rev", "eps_disp", "eps_breadth"]:
        lo, hi = d[c].quantile([.01, .99]); d[c] = d[c].clip(lo, hi)

    log("# Augmented EPS model — CA + analyst estimate dynamics (free, pre-earnings)\n")
    log(f"panel: {len(d)} company-quarters, {d.ticker.nunique()} tickers, {d.FE_FP_END.min().date()}..{d.FE_FP_END.max().date()}\n")

    log("## Univariate — which pre-earnings signal predicts the EPS surprise?")
    for x, desc in [("ca_yoy","CA card (revenue read)"),("eps_rev","estimate revision momentum"),
                    ("eps_breadth","revision breadth (up−down)"),("eps_disp","dispersion")]:
        r,p,n = eq.cluster_boot(d,x,"eps_surprise"); s=eq.surrogate(d,x,"eps_surprise",r)
        log(f"  {x:12s} r={r:+.3f} p_boot={p:.3f} p_surr={s:.3f} (n={n})  — {desc}")

    log("\n## Multivariate — nested models (R² = how much EPS-surprise variance explained)")
    def r2(xs):
        dd = d.dropna(subset=["eps_surprise"]+xs)
        X = np.column_stack([np.ones(len(dd))]+[dd[c].values for c in xs])
        b,*_=np.linalg.lstsq(X,dd["eps_surprise"].values,rcond=None); yh=X@b
        return 1-((dd["eps_surprise"].values-yh)**2).sum()/((dd["eps_surprise"].values-dd["eps_surprise"].mean())**2).sum(), len(dd)
    for label, xs in [("card only",["ca_yoy"]),
                      ("estimate dynamics only",["eps_rev","eps_breadth","eps_disp"]),
                      ("card + estimate dynamics (ALL)",["ca_yoy","eps_rev","eps_breadth","eps_disp"])]:
        rr,nn = r2(xs); log(f"  {label:34s}: R²={rr:.3f} (n={nn})")
    full = sz.mreg_boot(d,"eps_surprise",["ca_yoy","eps_rev","eps_breadth","eps_disp"])
    if full:
        nm=["ca_yoy","eps_rev","eps_breadth","eps_disp"]
        log("  full-model coefficients (company-clustered p):")
        for j,c in enumerate(nm):
            log(f"     {c:12s} coef={full['coef'][j]:+.3f} p={full['p'][j]:.3f}")

    # does CA add beyond estimate dynamics? partial: residualize eps_surprise on estimate dynamics, corr with ca_yoy
    dd = d.dropna(subset=["eps_surprise","eps_rev","eps_breadth","eps_disp","ca_yoy"])
    Xe=np.column_stack([np.ones(len(dd)),dd.eps_rev,dd.eps_breadth,dd.eps_disp])
    be,*_=np.linalg.lstsq(Xe,dd.eps_surprise.values,rcond=None); dd=dd.assign(resid=dd.eps_surprise.values-Xe@be)
    rca,pca,_=eq.cluster_boot(dd,"ca_yoy","resid"); sca=eq.surrogate(dd,"ca_yoy","resid",rca)
    log(f"\n  CA incremental: corr(ca_yoy, EPS-surprise residual after estimate dynamics) = {rca:+.3f} p_surr={sca:.3f}")

    log("\n## VERDICT")
    rrev,_,_=eq.cluster_boot(d,"eps_rev","eps_surprise"); srev=eq.surrogate(d,"eps_rev","eps_surprise",rrev)
    full_r2,_=r2(["ca_yoy","eps_rev","eps_breadth","eps_disp"]); card_r2,_=r2(["ca_yoy"])
    log(f"  Estimate revision momentum predicts the EPS surprise at r={rrev:+.3f} (surr p={srev:.3f}) — it SEES the margin")
    log(f"  part CA can't: full model R²={full_r2:.3f} vs card-only R²={card_r2:.3f}. BUT this is the analysts' OWN signal")
    log(f"  (public, documented under-reaction). CA's INCREMENT beyond it: r={rca:+.3f} (surr p={sca:.3f}) →")
    log(f"  {'CA still adds an independent slice' if (not np.isnan(sca)) and sca<0.10 else 'CA adds ~nothing beyond analyst dynamics'}.")
    OUT_MD.write_text("# Augmented EPS — CA + analyst estimate dynamics\n\n> 2026-06-04 · `scripts/auto/s_ab_augmented_eps.py`\n\n```\n"+"\n".join(lines)+"\n```\n")
    print(f"\n[written] {OUT_MD}")

if __name__ == "__main__":
    main()
