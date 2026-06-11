#!/usr/bin/env python3
"""
s_aa_eps_decomp.py — structural EPS build-up: EPS ≈ (revenue − cost) / shares.

User's point: card alone fails on EPS because card only carries the REVENUE term. Build EPS from its
parts and test the chain. This script measures WHERE the build-up breaks, using existing data.

EPS_surprise = (actual EPS − point-in-time consensus EPS)/|cons|. Decompose it:
  Stage A  eps_surprise ~ rev_surprise         → how much of the EPS surprise is just REVENUE flowing
           through (operating leverage)? R² here = the CEILING for any revenue-based EPS predictor.
           margin_resid = eps_surprise − fitted  = the MARGIN/cost/share/other-driven part.
  Stage B  can CA predict each component?
             ca_yoy   → rev_surprise   (CA revenue link; ~0.19)
             cost_yoy → margin_resid   (does the commodity COST proxy explain the MARGIN surprise?)  + surrogate
             ca_yoy   → eps_surprise   (direct; should ≈ 0.19 × [rev→eps link] → explains the ~0.065 null)
  Stage C  composite:  eps_surprise ~ ca_yoy + cost_yoy   (CA-only EPS predictor)
Shares: the third identity term. For the *surprise* it is ~negligible — buybacks are gradual & disclosed,
so consensus EPS already bakes in expected share count; the share-driven surprise ≈ 0. Flagged, not fetched.
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
A = ROOT / "outputs" / "auto"
OUT_MD = ROOT / "docs" / "analysis_eps_decomposition.md"
lines = []
def log(s=""): print(s); lines.append(s)

def ols_r2(d, y, xs):
    d = d.dropna(subset=[y] + xs)
    X = np.column_stack([np.ones(len(d))] + [d[c].values for c in xs])
    b, *_ = np.linalg.lstsq(X, d[y].values, rcond=None)
    yh = X @ b; r2 = 1 - ((d[y].values - yh) ** 2).sum() / ((d[y].values - d[y].mean()) ** 2).sum()
    return b, r2, len(d)

def main():
    # ---- revenue surprise (FactSet, new file) ----
    rev = pd.DataFrame(json.load(open(st.FS))["rows"])
    for c in ["ACTUAL", "CONS_EARLY"]: rev[c] = pd.to_numeric(rev[c], errors="coerce")
    rev["FE_FP_END"] = pd.to_datetime(rev["FE_FP_END"]); rev["ticker"] = rev["FSYM_ID"].map(st.FSYM2TKR)
    rev = rev.dropna(subset=["ticker", "ACTUAL", "CONS_EARLY"])
    keep = rev.groupby(["ticker","FSYM_ID"]).size().reset_index(name="n").sort_values("n").groupby("ticker").tail(1)
    rev = rev.merge(keep[["ticker","FSYM_ID"]], on=["ticker","FSYM_ID"])
    rev["rev_surprise"] = (rev["ACTUAL"] - rev["CONS_EARLY"]) / rev["CONS_EARLY"]
    rev = rev[["ticker","FE_FP_END","rev_surprise"]]

    # ---- eps surprise (FactSet) ----
    e = su.load_eps()
    e["eps_surprise"] = (e["ACTUAL"] - e["CONS_EARLY"]) / e["CONS_EARLY"].abs()
    e = e[(e["ACTUAL"].abs() >= 0.05) & (e["CONS_EARLY"].abs() >= 0.05)]
    lo, hi = e.eps_surprise.quantile([.01, .99]); e["eps_surprise"] = e.eps_surprise.clip(lo, hi)
    e = e[["ticker","FE_FP_END","eps_surprise"]]

    d = e.merge(rev, on=["ticker","FE_FP_END"], how="inner")
    # winsorize rev_surprise too
    lo, hi = d.rev_surprise.quantile([.01,.99]); d["rev_surprise"] = d.rev_surprise.clip(lo,hi)

    log("# Structural EPS build-up: where does (revenue − cost)/shares break for CA?\n")
    log(f"matched EPS×revenue surprises: {len(d)} company-quarters, {d.ticker.nunique()} tickers, "
        f"{d.FE_FP_END.min().date()}..{d.FE_FP_END.max().date()}\n")

    # ---- Stage A: how much of EPS surprise is revenue-driven? ----
    log("## Stage A — EPS surprise = revenue-driven part + margin part")
    rA, pA, nA = eq.cluster_boot(d, "rev_surprise", "eps_surprise")
    b, r2, _ = ols_r2(d, "eps_surprise", ["rev_surprise"])
    log(f"  corr(rev_surprise, eps_surprise) = {rA:+.3f}  (p_boot={pA:.3f}, n={nA})")
    log(f"  eps_surprise ~ rev_surprise: slope={b[1]:+.2f} (operating leverage), R²={r2:.3f}")
    log(f"  ⇒ only ~{r2*100:.0f}% of the EPS-surprise variance is REVENUE-driven; ~{(1-r2)*100:.0f}% is MARGIN/cost/other.")
    d["eps_from_rev"] = b[0] + b[1]*d["rev_surprise"]
    d["margin_resid"] = d["eps_surprise"] - d["eps_from_rev"]

    # ---- Stage B: can CA predict each component? ----
    ca = eq.build_ca_surprise()[["ticker","date","ca_yoy"]]
    parts = []
    for t in d.ticker.unique():
        a = ca[ca.ticker==t].sort_values("date")
        if a.empty: continue
        m = pd.merge_asof(d[d.ticker==t].sort_values("FE_FP_END"), a[["date","ca_yoy"]],
                          left_on="FE_FP_END", right_on="date", direction="nearest", tolerance=pd.Timedelta(days=50))
        parts.append(m)
    d = pd.concat(parts, ignore_index=True).dropna(subset=["ca_yoy"])
    # cost proxy (reuse pilot commodity basket)
    cyoy = sz.commodity_yoy()
    food = cyoy[cyoy.entity_name.isin(sz.FOOD)].groupby("q")["yoy"].mean()
    cotton = cyoy[cyoy.entity_name == sz.COTTON].set_index("q")["yoy"]
    d["fq"] = pd.to_datetime(d["FE_FP_END"]).dt.to_period("Q")
    d["cost_yoy"] = [cotton.get(q, np.nan) if t in sz.APPAREL else food.get(q, np.nan) for t,q in zip(d.ticker, d.fq)]

    log("\n## Stage B — can CA predict each part?")
    r1,p1,n1 = eq.cluster_boot(d,"ca_yoy","rev_surprise"); s1=eq.surrogate(d,"ca_yoy","rev_surprise",r1)
    log(f"  ca_yoy   → rev_surprise : r={r1:+.3f} p_surr={s1:.3f} (n={n1})  ← CA's real revenue link")
    dc = d.dropna(subset=["cost_yoy","margin_resid"])
    rc,pc,nc = eq.cluster_boot(dc,"cost_yoy","margin_resid"); sc=eq.surrogate(dc,"cost_yoy","margin_resid",rc)
    log(f"  cost_yoy → margin_resid : r={rc:+.3f} p_surr={sc:.3f} (n={nc})  ← does commodity COST explain the MARGIN surprise?")
    r0,p0,n0 = eq.cluster_boot(d,"ca_yoy","eps_surprise");
    log(f"  ca_yoy   → eps_surprise : r={r0:+.3f} (n={n0})  ← the direct null; ≈ {r1:+.3f}×{rA:+.3f}(rev→eps) = {r1*rA:+.3f} expected")

    # ---- Stage C: composite CA EPS predictor ----
    log("\n## Stage C — composite CA-only EPS predictor")
    _, r2c, nC = ols_r2(d, "eps_surprise", ["ca_yoy","cost_yoy"])
    _, r2rev, _ = ols_r2(d, "eps_surprise", ["rev_surprise"])
    log(f"  eps_surprise ~ ca_yoy + cost_yoy : R²={r2c:.3f} (n={nC})   [CA-only build-up]")
    log(f"  (benchmark: eps_surprise ~ TRUE rev_surprise : R²={r2rev:.3f} — even perfect revenue info caps here)")

    log("\n## VERDICT")
    log(f"  The build-up is right in spirit, but the math is unkind: EPS surprise is only ~{r2*100:.0f}% revenue-driven,")
    log(f"  and CA captures revenue only at r≈{r1:.2f}. So the revenue channel can carry at most ≈ r1×corr(rev,eps) ≈ {abs(r1*rA):.2f}")
    log(f"  into EPS — which IS the ~{abs(r0):.2f} null we see. The remaining ~{(1-r2)*100:.0f}% (margin) needs the cost proxy,")
    log(f"  and commodity cost → margin_resid is {'significant' if (not np.isnan(sc)) and sc<0.05 else 'NOT significant'} (p_surr={sc:.3f}).")
    log(f"  ⇒ Even assembled structurally, CA can't reach EPS: the revenue link is too weak to amplify, and the")
    log(f"     margin term (which dominates EPS surprises) is largely invisible to CA / already public.")
    OUT_MD.write_text("# EPS decomposition — structural build-up\n\n> 2026-06-04 · `scripts/auto/s_aa_eps_decomp.py`\n\n```\n"+"\n".join(lines)+"\n```\n")
    print(f"\n[written] {OUT_MD}")

if __name__ == "__main__":
    main()
