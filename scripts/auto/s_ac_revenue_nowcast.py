#!/usr/bin/env python3
"""
s_ac_revenue_nowcast.py — multifactor REVENUE-surprise nowcast (CA's one real edge, productized).

Target: rev_surprise = (actual revenue − point-in-time consensus)/consensus  (FactSet).
Factors (all pre-print, point-in-time, all 35 tickers):
  ca_yoy      : CA card-spend YoY  ← the semi-independent revenue read (r≈0.19 alone)
  rev_rev     : revenue consensus revision momentum = (mean_now − mean_90d)/mean_90d
  rev_breadth : (analysts revising revenue UP − DOWN)/num_est
  rev_disp    : dispersion = FE_STD_DEV/mean_now
The crucial test vs the EPS case: does CA ADD beyond analyst revenue dynamics? (For EPS it added nothing;
for revenue — what CA actually measures — it may, since card is a less-public, independent demand read.)

Outputs: in-sample univariate + multivariate; CA incremental (residualized + surrogate); and a real
OUT-OF-SAMPLE evaluation (expanding window, strict point-in-time): pooled corr(pred, actual), sign
hit-rate, and a long/short PnL on the predicted surprise.
"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
import s_q_edge_tests as eq
import s_t_revsurprise_factset as st

ROOT = Path("/Users/junekwon/Desktop/Projects/carbon_arc")
REVF = st.FS  # revenue actuals + point-in-time consensus (2021-2026)
SALESREV = "/Users/junekwon/.claude/projects/-Users-junekwon-Desktop-Projects-carbon-arc/1012a692-88a4-497e-a3d6-cfbce4dbe924/tool-results/mcp-linq-factset_query-1780548237543.txt"
OUT_MD = ROOT / "docs" / "analysis_revenue_nowcast_multifactor.md"
FACT = ["ca_yoy", "rev_rev", "rev_breadth", "rev_disp"]
ANALYST = ["rev_rev", "rev_breadth", "rev_disp"]
lines = []
def log(s=""): print(s); lines.append(s)

def ols(d, y, xs):
    dd = d.dropna(subset=[y] + xs)
    X = np.column_stack([np.ones(len(dd))] + [dd[c].values for c in xs])
    b, *_ = np.linalg.lstsq(X, dd[y].values, rcond=None); yh = X @ b
    r2 = 1 - ((dd[y].values - yh) ** 2).sum() / ((dd[y].values - dd[y].mean()) ** 2).sum()
    return b, r2, len(dd)

def main():
    # target + report date
    rev = pd.DataFrame(json.load(open(REVF))["rows"])
    for c in ["ACTUAL", "CONS_EARLY"]: rev[c] = pd.to_numeric(rev[c], errors="coerce")
    rev["FE_FP_END"] = pd.to_datetime(rev["FE_FP_END"]); rev["REPORT_DATE"] = pd.to_datetime(rev["REPORT_DATE"])
    rev["ticker"] = rev["FSYM_ID"].map(st.FSYM2TKR)
    rev = rev.dropna(subset=["ticker", "ACTUAL", "CONS_EARLY"])
    keep = rev.groupby(["ticker","FSYM_ID"]).size().reset_index(name="n").sort_values("n").groupby("ticker").tail(1)
    rev = rev.merge(keep[["ticker","FSYM_ID"]], on=["ticker","FSYM_ID"])
    rev["rev_surprise"] = (rev["ACTUAL"] - rev["CONS_EARLY"]) / rev["CONS_EARLY"]
    rev = rev[["ticker","FE_FP_END","REPORT_DATE","rev_surprise"]]

    # analyst revenue dynamics
    rv = pd.DataFrame(json.load(open(SALESREV))["rows"])
    for c in ["MEAN_NOW","MEAN_90","FE_STD_DEV","FE_NUM_EST","FE_UP","FE_DOWN"]: rv[c]=pd.to_numeric(rv[c],errors="coerce")
    rv["FE_FP_END"]=pd.to_datetime(rv["FE_FP_END"]); rv["ticker"]=rv["FSYM_ID"].map(st.FSYM2TKR)
    rv=rv.dropna(subset=["ticker","MEAN_NOW","MEAN_90"]); rv=rv[rv.MEAN_90.abs()>0]
    rv["rev_rev"]=(rv.MEAN_NOW-rv.MEAN_90)/rv.MEAN_90.abs()
    rv["rev_breadth"]=(rv.FE_UP-rv.FE_DOWN)/rv.FE_NUM_EST
    rv["rev_disp"]=rv.FE_STD_DEV/rv.MEAN_NOW.abs()
    rv=rv[["ticker","FE_FP_END","rev_rev","rev_breadth","rev_disp"]]

    d = rev.merge(rv, on=["ticker","FE_FP_END"], how="inner")
    ca = eq.build_ca_surprise()[["ticker","date","ca_yoy"]]
    parts=[]
    for t in d.ticker.unique():
        a=ca[ca.ticker==t].sort_values("date")
        if a.empty: continue
        m=pd.merge_asof(d[d.ticker==t].sort_values("FE_FP_END"), a[["date","ca_yoy"]], left_on="FE_FP_END",
                        right_on="date", direction="nearest", tolerance=pd.Timedelta(days=50))
        parts.append(m)
    d=pd.concat(parts,ignore_index=True).dropna(subset=["ca_yoy"])
    for c in FACT+["rev_surprise"]:
        lo,hi=d[c].quantile([.01,.99]); d[c]=d[c].clip(lo,hi)

    log("# Multifactor REVENUE-surprise nowcast (CA + analyst revenue dynamics)\n")
    log(f"panel: {len(d)} company-quarters, {d.ticker.nunique()} tickers, {d.FE_FP_END.min().date()}..{d.FE_FP_END.max().date()}\n")

    log("## Univariate — each factor → revenue surprise")
    for x in FACT:
        r,p,n=eq.cluster_boot(d,x,"rev_surprise"); s=eq.surrogate(d,x,"rev_surprise",r)
        log(f"  {x:12s} r={r:+.3f} p_boot={p:.3f} p_surr={s:.3f} (n={n})")

    log("\n## Multivariate — nested R²")
    for label,xs in [("card only",["ca_yoy"]),("analyst dynamics only",ANALYST),("FULL (card+analyst)",FACT)]:
        b,r2,n=ols(d,"rev_surprise",xs); log(f"  {label:22s}: R²={r2:.3f} (n={n})")
    full=eq.cluster_boot  # placeholder
    b,r2,n=ols(d,"rev_surprise",FACT)
    log("  full-model standardized contributions (coef × sd(x)):")
    for j,c in enumerate(FACT):
        log(f"     {c:12s} coef={b[j+1]:+.3f}  (×sd={b[j+1]*d[c].std():+.4f})")

    # KEY: CA incremental beyond analyst dynamics
    dd=d.dropna(subset=["rev_surprise"]+FACT)
    Xa=np.column_stack([np.ones(len(dd))]+[dd[c].values for c in ANALYST])
    ba,*_=np.linalg.lstsq(Xa,dd.rev_surprise.values,rcond=None)
    dd=dd.assign(resid=dd.rev_surprise.values-Xa@ba)
    rca,pca,_=eq.cluster_boot(dd,"ca_yoy","resid"); sca=eq.surrogate(dd,"ca_yoy","resid",rca)
    log(f"\n## ⭐ CA INCREMENTAL beyond analyst revenue dynamics")
    log(f"  corr(ca_yoy, rev-surprise residual after analyst dynamics) = {rca:+.3f}  p_surr={sca:.3f} (n={len(dd)})")
    log(f"  {'✅ CA adds an INDEPENDENT slice analysts have NOT priced' if (not np.isnan(sca)) and sca<0.05 else '❌ CA redundant once analyst dynamics are in'}")

    # OUT-OF-SAMPLE: expanding window, predict each quarter from strictly-earlier reported quarters
    d=d.sort_values("REPORT_DATE").reset_index(drop=True)
    preds=[]
    for i in d.index:
        tr=d[d.REPORT_DATE < d.at[i,"REPORT_DATE"]].dropna(subset=["rev_surprise"]+FACT)
        if len(tr)<60: continue
        row=d.loc[i,FACT]
        if row.isna().any(): continue
        X=np.column_stack([np.ones(len(tr))]+[tr[c].values for c in FACT])
        b,*_=np.linalg.lstsq(X,tr.rev_surprise.values,rcond=None)
        pred=b[0]+sum(b[j+1]*d.at[i,c] for j,c in enumerate(FACT))
        # card-only and analyst-only OOS preds for comparison
        Xc=np.column_stack([np.ones(len(tr)),tr.ca_yoy.values]); bc,*_=np.linalg.lstsq(Xc,tr.rev_surprise.values,rcond=None)
        predc=bc[0]+bc[1]*d.at[i,"ca_yoy"]
        Xan=np.column_stack([np.ones(len(tr))]+[tr[c].values for c in ANALYST]); ban,*_=np.linalg.lstsq(Xan,tr.rev_surprise.values,rcond=None)
        preda=ban[0]+sum(ban[j+1]*d.at[i,c] for j,c in enumerate(ANALYST))
        preds.append({"ticker":d.at[i,"ticker"],"actual":d.at[i,"rev_surprise"],"pred":pred,"pred_card":predc,"pred_analyst":preda})
    pr=pd.DataFrame(preds)
    log(f"\n## OUT-OF-SAMPLE (expanding window, strict point-in-time): {len(pr)} forecasts")
    cf=pr.pred.corr(pr.actual); cc=pr.pred_card.corr(pr.actual); can=pr.pred_analyst.corr(pr.actual)
    hit=((np.sign(pr.pred)==np.sign(pr.actual)).mean())
    log(f"  corr(pred, actual surprise): card-only={cc:+.3f}  analyst-only={can:+.3f}  FULL={cf:+.3f}")
    log(f"  sign hit-rate (FULL): {hit:.2%}")
    ls=np.sign(pr.pred)*pr.actual
    t_ls=ls.mean()/(ls.std()/np.sqrt(len(ls))) if ls.std()>0 else np.nan
    log(f"  long/short on predicted surprise: mean={ls.mean():+.4f} t={t_ls:+.2f} (longs beat-preds, shorts miss-preds)")

    log("\n## VERDICT")
    b,r2f,_=ols(d,"rev_surprise",FACT); _,r2c,_=ols(d,"rev_surprise",["ca_yoy"])
    log(f"  Multifactor explains R²={r2f:.3f} of the revenue surprise in-sample (card alone {r2c:.3f}).")
    log(f"  CA's value vs analysts: incremental r={rca:+.3f} (surr p={sca:.3f}) — "
        f"{'a genuine independent revenue edge' if (not np.isnan(sca)) and sca<0.05 else 'no edge beyond public analyst dynamics'}.")
    log(f"  OOS: full-model forecast corr {cf:+.3f}, hit-rate {hit:.0%} — {'usable nowcast' if cf>0.15 else 'weak'}.")
    OUT_MD.write_text("# Multifactor revenue-surprise nowcast\n\n> 2026-06-04 · `scripts/auto/s_ac_revenue_nowcast.py`\n\n```\n"+"\n".join(lines)+"\n```\n")
    print(f"\n[written] {OUT_MD}")

if __name__ == "__main__":
    main()
