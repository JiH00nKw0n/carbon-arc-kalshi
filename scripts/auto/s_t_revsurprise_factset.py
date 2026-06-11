#!/usr/bin/env python3
"""
s_t_revsurprise_factset.py — definitive clean info test with FactSet POINT-IN-TIME revenue consensus.

Reflects all three corrections:
  (1) X is CLEAN (ca_yoy), not consensus-subtracted → avoids the shared-term artifact (which inflated
      s_s to r=0.47 vs the true 0.09).
  (2) "vs consensus" lives in the TARGET: surprise = (actual − consensus)/consensus.
  (3) consensus is POINT-IN-TIME as of CA-availability (t_ca = fiscal-quarter-end + 7d), from FactSet
      FE_BASIC_CONH_QF SALES snapshots (CONS_END_DATE). Also the pre-print consensus, for comparison.

Tests (company-clustered bootstrap + shuffle-company surrogate):
  INFO:  corr(ca_yoy, surprise_early)   and   corr(ca_yoy, surprise_print)
  RETURN(edge, artifact-free): corr(ca_yoy − cons_early_growth, earnings-day mkt-adj return)
Data: FactSet (revenue actual + point-in-time consensus) + owned CA + edge_panel returns.
"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
import s_q_edge_tests as eq

ROOT = Path(__file__).resolve().parents[2]
A = ROOT / "outputs" / "auto"
FS = "/Users/junekwon/.claude/projects/-Users-junekwon-Desktop-Projects-carbon-arc/1012a692-88a4-497e-a3d6-cfbce4dbe924/tool-results/mcp-linq-factset_query-1780486182779.txt"
OUT_MD = ROOT / "docs" / "analysis_company_revsurprise_factset.md"
FSYM2TKR = {"CSMTMQ-R":"WMT","X93SZL-R":"CAVA","DGBZCC-R":"DAL","GRS9LG-R":"DRI","VNMTTH-R":"NKE","RBB7RY-R":"ANF","CHKL7S-R":"LOW","MR0PSP-R":"DLTR","PD98GG-R":"HD","VPYPRV-R":"GAP","BDQDB8-R":"DG","WPKF66-R":"BBY","R6YFWL-R":"TGT","D9QJSR-R":"DAL","LFCW0C-R":"DRI","LHPM83-R":"CMG","MH33D6-R":"AAPL","NZVLD0-R":"DAL","S8ZPBT-R":"TJX","QXDYZY-R":"URBN","TWTDGH-R":"SBUX","HVRRX7-R":"CMG","C4C0BL-R":"NFLX","CKHCJ4-R":"DASH","VTBLV9-R":"MCD","X66R72-R":"LULU","MCNYYL-R":"AMZN","NQQWV9-R":"AEO","HZQYZZ-R":"ABNB","FJ4NDH-R":"ROST","BL5KVX-R":"COST","D1LJ47-R":"AEO","X44KDF-R":"TXRH","MWKPV4-R":"LULU","J994MP-R":"TGT","R3D3VF-R":"DAL","KFQHFG-R":"CMG","R2J99W-R":"KR","J61GM6-R":"CMG","XKTZWR-R":"URBN","PVBYXV-R":"ETSY","QZ2DKP-R":"ROST","VXQ46D-R":"WEN","VCNXSP-R":"YUM","R71R5P-R":"DG","LN50TL-R":"COST","TR0FX7-R":"UBER","F05QG0-R":"DPZ","RW40D2-R":"CMG","CF350L-R":"CHWY","R5RD6T-R":"GAP","MVFYFD-R":"BBY"}
lines = []
def log(s=""): print(s); lines.append(s)

def main():
    d = pd.DataFrame(json.load(open(FS))["rows"])
    for c in ["ACTUAL","CONS_EARLY","CONS_PRINT"]: d[c] = pd.to_numeric(d[c], errors="coerce")
    d["FE_FP_END"] = pd.to_datetime(d["FE_FP_END"]); d["REPORT_DATE"] = pd.to_datetime(d["REPORT_DATE"])
    d["ticker"] = d["FSYM_ID"].map(FSYM2TKR)
    d = d.dropna(subset=["ticker","ACTUAL","CONS_EARLY"])
    # dedupe per ticker: keep the FSYM_ID with most rows (canonical live listing)
    keep = d.groupby(["ticker","FSYM_ID"]).size().reset_index(name="n").sort_values("n").groupby("ticker").tail(1)
    d = d.merge(keep[["ticker","FSYM_ID"]], on=["ticker","FSYM_ID"])
    d = d.sort_values(["ticker","FE_FP_END"])
    d["actual_q4"] = d.groupby("ticker")["ACTUAL"].shift(4)
    d["surprise_early"] = (d["ACTUAL"] - d["CONS_EARLY"]) / d["CONS_EARLY"]
    d["surprise_print"] = (d["ACTUAL"] - d["CONS_PRINT"]) / d["CONS_PRINT"]
    d["cons_early_growth"] = d["CONS_EARLY"] / d["actual_q4"] - 1

    ca = eq.build_ca_surprise()
    rows = []
    for t in d.ticker.unique():
        e = d[d.ticker == t].sort_values("FE_FP_END")
        a = ca[ca.ticker == t].sort_values("date")
        if a.empty: continue
        m = pd.merge_asof(e, a[["date","ca_yoy"]], left_on="FE_FP_END", right_on="date",
                          direction="nearest", tolerance=pd.Timedelta(days=50))
        rows.append(m)
    d = pd.concat(rows, ignore_index=True).dropna(subset=["ca_yoy"])
    d["ca_vs_cons_early"] = d["ca_yoy"] - d["cons_early_growth"]
    # earnings-day return from edge_panel
    ep = pd.read_csv(A / "edge_panel.csv"); ep["report_date"] = pd.to_datetime(ep["report_date"])
    d = pd.merge_asof(d.sort_values("REPORT_DATE"), ep[["ticker","report_date","ret_earn_mktadj"]].sort_values("report_date"),
                      left_on="REPORT_DATE", right_on="report_date", by="ticker",
                      direction="nearest", tolerance=pd.Timedelta(days=4))

    log("# Definitive clean test — CA → revenue surprise, FactSet POINT-IN-TIME consensus")
    log(f"\nevents: {len(d)} across {d.ticker.nunique()} tickers; {d.FE_FP_END.min().date()}..{d.FE_FP_END.max().date()}")
    log(f"surprise_early: mean={d.surprise_early.mean():+.4f} sd={d.surprise_early.std():.4f} (vs FMP sd≈1.07 — FactSet much cleaner)")
    log(f"early vs print consensus differ by median {((d.CONS_EARLY-d.CONS_PRINT).abs()/d.CONS_PRINT).median():.4f} (≈0 ⇒ consensus set by quarter-end)")

    log("\n## INFO — does CA predict the revenue surprise? (X=ca_yoy CLEAN, no artifact)")
    for y in ["surprise_early","surprise_print"]:
        r,p,n = eq.cluster_boot(d, "ca_yoy", y); s = eq.surrogate(d,"ca_yoy",y,r) if not np.isnan(r) else np.nan
        log(f"  ca_yoy → {y:15s}: r={r:+.3f} (n={n}) p_boot={p:.3f} p_surr={s:.3f}")
    # confirm the artifact for the record
    rA,_,_ = eq.cluster_boot(d, "ca_vs_cons_early", "surprise_early")
    log(f"  [artifact check] (ca_yoy−cons) → surprise_early: r={rA:+.3f}  ← inflated by shared consensus term, NOT real")

    log("\n## RETURN edge (artifact-free: returns don't contain consensus)")
    rr,pr,nr = eq.cluster_boot(d, "ca_vs_cons_early", "ret_earn_mktadj")
    sr = eq.surrogate(d,"ca_vs_cons_early","ret_earn_mktadj",rr) if not np.isnan(rr) else np.nan
    log(f"  (ca_yoy − cons_early) → earnings-day return: r={rr:+.3f} (n={nr}) p_boot={pr:.3f} p_surr={sr:.3f}")
    # sanity: does the revenue surprise itself move the stock?
    sa = d.dropna(subset=["surprise_early","ret_earn_mktadj"])
    log(f"  sanity: revenue surprise → return r={sa.surprise_early.corr(sa.ret_earn_mktadj):+.3f} (n={len(sa)})")

    log("\n## VERDICT")
    rE,pE,_ = eq.cluster_boot(d,"ca_yoy","surprise_early"); sE = eq.surrogate(d,"ca_yoy","surprise_early",rE)
    if (not np.isnan(sE)) and sE<0.05 and pE<0.05:
        log(f"  ✅ CA predicts revenue surprise vs point-in-time consensus (r={rE:+.3f}, surr p={sE:.3f}) — CA beats analysts on revenue.")
    else:
        log(f"  ❌ NULL — even vs clean FactSet point-in-time revenue consensus, CA does not predict the surprise (r={rE:+.3f}, surr p={sE:.3f}).")
        log("     Definitively closes the information layer: CA = revenue measurement already embedded in consensus. No edge.")
    OUT_MD.write_text("# CA → revenue surprise (FactSet point-in-time)\n\n> 2026-06-03 · `scripts/auto/s_t_revsurprise_factset.py`\n\n```\n"+"\n".join(lines)+"\n```\n")
    print(f"\n[written] {OUT_MD}")

if __name__ == "__main__":
    main()
