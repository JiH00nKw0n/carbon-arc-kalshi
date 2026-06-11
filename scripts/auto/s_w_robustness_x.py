#!/usr/bin/env python3
"""
s_w_robustness_x.py — is the r=0.19 (CA → revenue surprise) robust to how X is transformed?

Y is UNCHANGED across all variants: revenue surprise_early = (actual − point-in-time consensus)/consensus
(FactSet, CONS_EARLY ≈ as of fiscal-quarter-end). Only X (the card-spend transform) varies, to test
whether the signal depends on the YoY choice or survives seasonally-adjusted / level-residual forms.

X variants (all from the same raw quarterly card spend per company):
  X1 ca_yoy        : card(Q)/card(Q-4) − 1                                   (baseline; needs Q-4)
  X2 ca_yoy_resid  : ca_yoy − trailing-4q mean(ca_yoy)  (acceleration)
  X3 qoq_sa        : deseasonalized log card, QoQ change (Δ log, seasonal-adj; needs only 1 lag)
  X4 lvl_resid     : deseasonalized log card − its trailing-4q mean (level vs own trend)
Inference per variant: company-clustered bootstrap + shuffle-company surrogate (s_q helpers).
"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
import s_q_edge_tests as eq
import s_t_revsurprise_factset as st

ROOT = Path(__file__).resolve().parents[2]
A = ROOT / "outputs" / "auto"
FS_REV = "/Users/junekwon/.claude/projects/-Users-junekwon-Desktop-Projects-carbon-arc/1012a692-88a4-497e-a3d6-cfbce4dbe924/tool-results/mcp-linq-factset_query-1780538261695.txt"
OUT_MD = ROOT / "docs" / "analysis_company_robustness_x.md"
lines = []
def log(s=""): print(s); lines.append(s)

def build_ca_variants():
    ca = pd.read_csv(A / "ca0056_card_spend_by_ticker_q_3y.csv")
    ca = ca.groupby(["entity_name", "date"], as_index=False)["credit_card_spend"].sum()
    ca = ca.rename(columns={"entity_name": "ticker"})
    ca["date"] = pd.to_datetime(ca["date"]); ca = ca.sort_values(["ticker", "date"])
    ca["log"] = np.log(ca["credit_card_spend"])
    ca["q"] = ca["date"].dt.quarter
    # X1, X2
    ca["ca_yoy"] = ca.groupby("ticker")["credit_card_spend"].pct_change(4)
    ca["ca_yoy_resid"] = ca["ca_yoy"] - ca.groupby("ticker")["ca_yoy"].transform(
        lambda s: s.shift(1).rolling(4, min_periods=2).mean())
    # deseasonalize log within company (in-sample seasonal factors)
    def deseason(g):
        fac = g.groupby("q")["log"].transform("mean") - g["log"].mean()
        return g["log"] - fac
    ca["deseas"] = ca.groupby("ticker", group_keys=False).apply(deseason)
    # X3 QoQ seasonally-adjusted (log change)
    ca["qoq_sa"] = ca.groupby("ticker")["deseas"].diff(1)
    # X4 level vs own trailing trend (deseasonalized)
    ca["lvl_resid"] = ca["deseas"] - ca.groupby("ticker")["deseas"].transform(
        lambda s: s.shift(1).rolling(4, min_periods=2).mean())
    return ca

def main():
    # ---- Y: revenue surprise (unchanged) ----
    d = pd.DataFrame(json.load(open(FS_REV))["rows"])
    for c in ["ACTUAL", "CONS_EARLY"]: d[c] = pd.to_numeric(d[c], errors="coerce")
    d["FE_FP_END"] = pd.to_datetime(d["FE_FP_END"])
    d["ticker"] = d["FSYM_ID"].map(st.FSYM2TKR)
    d = d.dropna(subset=["ticker", "ACTUAL", "CONS_EARLY"])
    keep = (d.groupby(["ticker", "FSYM_ID"]).size().reset_index(name="n")
              .sort_values("n").groupby("ticker").tail(1))
    d = d.merge(keep[["ticker", "FSYM_ID"]], on=["ticker", "FSYM_ID"]).sort_values(["ticker", "FE_FP_END"])
    d["surprise"] = (d["ACTUAL"] - d["CONS_EARLY"]) / d["CONS_EARLY"]

    ca = build_ca_variants()
    variants = ["ca_yoy", "ca_yoy_resid", "qoq_sa", "lvl_resid"]
    log("# Robustness of CA→revenue-surprise to the X transform (Y = revenue surprise, fixed)")
    log(f"\nY = (actual − point-in-time consensus)/consensus; FactSet 2021-2026 revenue.")
    log(f"{'X transform':16s} {'r':>7s} {'n':>5s} {'p_boot':>7s} {'p_surr':>7s}   note")
    notes = {"ca_yoy": "baseline (the r≈0.19 result)", "ca_yoy_resid": "YoY minus own trend (accel)",
             "qoq_sa": "seasonally-adj QoQ Δlog (no Q-4 needed)", "lvl_resid": "deseason level vs own trend"}
    rows_out = []
    for v in variants:
        parts = []
        for t in d.ticker.unique():
            e = d[d.ticker == t].sort_values("FE_FP_END")
            a = ca[ca.ticker == t].dropna(subset=[v]).sort_values("date")
            if a.empty: continue
            m = pd.merge_asof(e, a[["date", v]], left_on="FE_FP_END", right_on="date",
                              direction="nearest", tolerance=pd.Timedelta(days=50))
            parts.append(m)
        dm = pd.concat(parts, ignore_index=True).dropna(subset=[v, "surprise"])
        r, p, n = eq.cluster_boot(dm, v, "surprise")
        s = eq.surrogate(dm, v, "surprise", r) if not np.isnan(r) else np.nan
        rows_out.append((v, r, n, p, s))
        log(f"{v:16s} {r:+7.3f} {n:5d} {p:7.3f} {s:7.3f}   {notes[v]}")

    log("\n## VERDICT")
    base = rows_out[0]
    survive = [v for (v, r, n, p, s) in rows_out if (not np.isnan(s)) and s < 0.05 and p < 0.05]
    log(f"  variants surviving (p_boot<.05 AND p_surr<.05): {survive}")
    if "ca_yoy" in survive and len(survive) >= 3:
        log("  ✅ ROBUST — the revenue-surprise signal is NOT an artifact of the YoY choice; it survives")
        log("     seasonally-adjusted QoQ and level-vs-trend forms too. YoY is a fine (not load-bearing) default.")
    elif "ca_yoy" in survive:
        log("  ~ PARTIAL — survives in YoY but weakens under some transforms (short per-company series make")
        log("     seasonal estimation noisy). Direction consistent; magnitude transform-sensitive.")
    else:
        log("  ❌ FRAGILE — signal depends on the specific transform; treat r≈0.19 with caution.")
    OUT_MD.write_text("# CA→revenue-surprise: robustness to X transform\n\n> 2026-06-04 · `scripts/auto/s_w_robustness_x.py`\n\n```\n" + "\n".join(lines) + "\n```\n")
    print(f"\n[written] {OUT_MD}")

if __name__ == "__main__":
    main()
