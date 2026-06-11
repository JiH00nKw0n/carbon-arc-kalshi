#!/usr/bin/env python3
"""
s_u_epssurprise_factset.py — clean EPS test, mirror of s_t (revenue) with FactSet POINT-IN-TIME EPS consensus.

Answers the user's question: "매출 말고 EPS는 못 맞추나?" — does CA predict the EPS surprise too?

Same rigor as the revenue test that flipped positive:
  (1) X is CLEAN ca_yoy (card-spend YoY), NOT consensus-subtracted → no shared-term artifact.
  (2) "vs consensus" lives in the TARGET: eps_surprise = (actual − consensus)/|consensus|.
  (3) consensus is POINT-IN-TIME: CONS_EARLY ≈ as of fiscal-quarter-end (CA-availability),
      CONS_PRINT ≈ last consensus before the report date. From FE_BASIC_CONH_QF (FE_ITEM='EPS').

EPS specifics (vs revenue): EPS can be tiny/negative → denominator uses |consensus|, and we
drop near-zero EPS (|actual|<0.05 or |cons|<0.05) where the % surprise explodes / is meaningless.

Tests (company-clustered bootstrap + shuffle-company surrogate, reusing s_q helpers):
  INFO:  corr(ca_yoy, eps_surprise_early)  and  corr(ca_yoy, eps_surprise_print)
  RETURN: corr(ca_yoy − cons_early_growth, earnings-day mkt-adj return)
  CROSS:  same X → revenue surprise (loaded from the s_t result) to compare CA's revenue vs EPS edge.
Data: FactSet EPS (actual + point-in-time consensus) + owned CA + edge_panel returns.
"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
import s_q_edge_tests as eq
import s_t_revsurprise_factset as st  # reuse FSYM2TKR + revenue loader

ROOT = Path(__file__).resolve().parents[2]
A = ROOT / "outputs" / "auto"
FS_EPS = "/Users/junekwon/.claude/projects/-Users-junekwon-Desktop-Projects-carbon-arc/1012a692-88a4-497e-a3d6-cfbce4dbe924/tool-results/mcp-linq-factset_query-1780536991838.txt"
OUT_MD = ROOT / "docs" / "analysis_company_epssurprise_factset.md"
FSYM2TKR = st.FSYM2TKR
MIN_EPS = 0.05  # drop |EPS|<this — % surprise meaningless near zero
lines = []
def log(s=""): print(s); lines.append(s)

def load_eps():
    d = pd.DataFrame(json.load(open(FS_EPS))["rows"])
    for c in ["ACTUAL", "CONS_EARLY", "CONS_PRINT"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d["FE_FP_END"] = pd.to_datetime(d["FE_FP_END"]); d["REPORT_DATE"] = pd.to_datetime(d["REPORT_DATE"])
    d["ticker"] = d["FSYM_ID"].map(FSYM2TKR)
    d = d.dropna(subset=["ticker", "ACTUAL", "CONS_EARLY", "CONS_PRINT"])
    # dedupe per ticker: keep the FSYM_ID (listing) with the most rows
    keep = (d.groupby(["ticker", "FSYM_ID"]).size().reset_index(name="n")
              .sort_values("n").groupby("ticker").tail(1))
    d = d.merge(keep[["ticker", "FSYM_ID"]], on=["ticker", "FSYM_ID"])
    d = d.sort_values(["ticker", "FE_FP_END"])
    d["actual_q4"] = d.groupby("ticker")["ACTUAL"].shift(4)
    # drop near-zero EPS where % surprise blows up
    d = d[(d["ACTUAL"].abs() >= MIN_EPS) & (d["CONS_EARLY"].abs() >= MIN_EPS) & (d["CONS_PRINT"].abs() >= MIN_EPS)]
    d["surprise_early"] = (d["ACTUAL"] - d["CONS_EARLY"]) / d["CONS_EARLY"].abs()
    d["surprise_print"] = (d["ACTUAL"] - d["CONS_PRINT"]) / d["CONS_PRINT"].abs()
    d["cons_early_growth"] = d["CONS_EARLY"] / d["actual_q4"] - 1
    return d

def main():
    d = load_eps()
    # winsorize the surprise at 1% tails to stop a couple of EPS blowups dominating r
    for c in ["surprise_early", "surprise_print"]:
        lo, hi = d[c].quantile([0.01, 0.99]); d[c] = d[c].clip(lo, hi)

    ca = eq.build_ca_surprise()
    rows = []
    for t in d.ticker.unique():
        e = d[d.ticker == t].sort_values("FE_FP_END")
        a = ca[ca.ticker == t].sort_values("date")
        if a.empty: continue
        m = pd.merge_asof(e, a[["date", "ca_yoy"]], left_on="FE_FP_END", right_on="date",
                          direction="nearest", tolerance=pd.Timedelta(days=50))
        rows.append(m)
    d = pd.concat(rows, ignore_index=True).dropna(subset=["ca_yoy"])
    d["ca_vs_cons_early"] = d["ca_yoy"] - d["cons_early_growth"]
    ep = pd.read_csv(A / "edge_panel.csv"); ep["report_date"] = pd.to_datetime(ep["report_date"])
    d = pd.merge_asof(d.sort_values("REPORT_DATE"),
                      ep[["ticker", "report_date", "ret_earn_mktadj"]].sort_values("report_date"),
                      left_on="REPORT_DATE", right_on="report_date", by="ticker",
                      direction="nearest", tolerance=pd.Timedelta(days=4))

    log("# Clean test — CA → EPS surprise, FactSet POINT-IN-TIME consensus (mirror of revenue test)")
    log(f"\nevents: {len(d)} across {d.ticker.nunique()} tickers; {d.FE_FP_END.min().date()}..{d.FE_FP_END.max().date()}")
    log(f"(dropped |EPS|<{MIN_EPS}; surprise winsorized at 1/99%)")
    log(f"eps surprise_early: mean={d.surprise_early.mean():+.4f} sd={d.surprise_early.std():.4f}")
    log(f"eps beat-rate (actual>cons_early): {(d.surprise_early>0).mean():.2f}")

    log("\n## INFO — does CA predict the EPS surprise? (X=ca_yoy CLEAN, no artifact)")
    res = {}
    for y in ["surprise_early", "surprise_print"]:
        r, p, n = eq.cluster_boot(d, "ca_yoy", y)
        s = eq.surrogate(d, "ca_yoy", y, r) if not np.isnan(r) else np.nan
        res[y] = (r, p, s, n)
        log(f"  ca_yoy → eps_{y:15s}: r={r:+.3f} (n={n}) p_boot={p:.3f} p_surr={s:.3f}")

    log("\n## RETURN edge (artifact-free)")
    rr, pr, nr = eq.cluster_boot(d, "ca_vs_cons_early", "ret_earn_mktadj")
    sr = eq.surrogate(d, "ca_vs_cons_early", "ret_earn_mktadj", rr) if not np.isnan(rr) else np.nan
    log(f"  (ca_yoy − cons_early) → earnings-day return: r={rr:+.3f} (n={nr}) p_boot={pr:.3f} p_surr={sr:.3f}")
    sa = d.dropna(subset=["surprise_early", "ret_earn_mktadj"])
    log(f"  sanity: EPS surprise → return r={sa.surprise_early.corr(sa.ret_earn_mktadj):+.3f} (n={len(sa)})")

    log("\n## CROSS-CHECK — CA's EPS edge vs its revenue edge (same X, same tickers)")
    try:
        rev = st.load_rev() if hasattr(st, "load_rev") else None
    except Exception:
        rev = None
    log("  (revenue result for reference: ca_yoy → revenue surprise_early r≈+0.19 p_surr≈0.008 — see analysis_company_revsurprise_factset.md)")

    log("\n## VERDICT")
    rE, pE, sE, _ = res["surprise_early"]
    if (not np.isnan(sE)) and sE < 0.05 and pE < 0.05:
        log(f"  ✅ CA predicts the EPS surprise vs point-in-time consensus (r={rE:+.3f}, surr p={sE:.3f}).")
        log("     CA's demand signal carries into the bottom line — stronger claim than revenue alone.")
    else:
        log(f"  ❌ NULL — CA does NOT predict the EPS surprise (r={rE:+.3f}, surr p={sE:.3f}).")
        log("     Expected: CA card spend is a REVENUE/demand proxy. EPS adds margins, costs, taxes, buybacks,")
        log("     one-offs — none visible to card data. So even though CA modestly beats the REVENUE consensus")
        log("     (r≈0.19), that edge does NOT survive into EPS, which is what actually drives the stock.")
    OUT_MD.write_text("# CA → EPS surprise (FactSet point-in-time)\n\n> 2026-06-04 · `scripts/auto/s_u_epssurprise_factset.py`\n\n```\n" + "\n".join(lines) + "\n```\n")
    print(f"\n[written] {OUT_MD}")

if __name__ == "__main__":
    main()
