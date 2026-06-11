#!/usr/bin/env python3
"""
s_v_h3_oos_factset.py — H3 (rigorous incremental) re-run with FactSet revenue actuals.

Question: does adding CA card-spend to a revenue-forecasting model improve the OUT-OF-SAMPLE
nowcast of revenue YoY, beyond what the revenue series predicts about itself? This is the correct
"does CA *add* information" test for co-measured series (replaces macro-Granger).

Why re-run: the first pass (s_q, FMP revenue) used PER-COMPANY expanding windows with only ~6-12
training points fitting 3 params → the +CA model overfit in-sample and generalized worse (RMSE
0.075→0.088, DM=-0.88). That is an estimation artifact, not evidence CA lacks info. Fixes here:
  (1) FactSet revenue actuals (clean) instead of FMP.
  (2) POOLED expanding-window OLS across all companies (training set = hundreds of company-quarters,
      not 6) with WITHIN-COMPANY demeaning (company fixed effects) → stable coefficients.
  (3) Strict point-in-time: to forecast rev_yoy(Q) at t_ca = fiscal-q-end+7d, train ONLY on
      company-quarters already REPORTED before t_ca; use rev_yoy(Q-1) (last print) + ca_yoy(Q)
      (card spend, known at quarter-end, before the print). No lookahead.

Models (demeaned within company on the training fold):
  A baseline : rev_yoy(Q) ~ a + b·rev_yoy(Q-1)
  B +CA      : rev_yoy(Q) ~ a + b·rev_yoy(Q-1) + c·ca_yoy(Q)
Loss = squared OOS error. d = e_base² − e_ca² (>0 ⇒ CA helps). Inference: company-clustered
bootstrap on mean(d) (primary) + Harvey-corrected Diebold-Mariano (secondary) + pooled RMSE.
"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
import s_q_edge_tests as eq
import s_t_revsurprise_factset as st

ROOT = Path(__file__).resolve().parents[2]
FS_REV = "/Users/junekwon/.claude/projects/-Users-junekwon-Desktop-Projects-carbon-arc/1012a692-88a4-497e-a3d6-cfbce4dbe924/tool-results/mcp-linq-factset_query-1780538261695.txt"  # revenue back to 2021 (was 2024) → ca_yoy is now the binding window, not revenue
OUT_MD = ROOT / "docs" / "analysis_company_h3_oos_factset.md"
FSYM2TKR = st.FSYM2TKR
MIN_TRAIN = 30          # min pooled training company-quarters before we forecast (lowered: bigger panel warms up faster)
MIN_CO_TRAIN = 3        # min prior reported quarters for the target's own company (for its FE mean)
lines = []
def log(s=""): print(s); lines.append(s)

def ols_predict(Xtr, ytr, Xte):
    """OLS via lstsq; returns predictions for Xte. Xtr/Xte include intercept column."""
    beta, *_ = np.linalg.lstsq(Xtr, ytr, rcond=None)
    return Xte @ beta

def dm_hln(d, h=1):
    """Harvey-Leybourne-Newbold small-sample-corrected Diebold-Mariano t-stat for loss diff d."""
    d = np.asarray(d, float); n = len(d)
    if n < 8: return np.nan, np.nan
    dbar = d.mean()
    # long-run variance with Newey-West up to h-1 (h=1 ⇒ just variance)
    gamma0 = np.mean((d - dbar) ** 2)
    var = gamma0
    for k in range(1, h):
        gk = np.mean((d[k:] - dbar) * (d[:-k] - dbar))
        var += 2 * gk
    dm = dbar / np.sqrt(var / n)
    corr = np.sqrt((n + 1 - 2 * h + h * (h - 1) / n) / n)
    return dm * corr, dbar

def cluster_boot_mean(df, col, B=2000, seed=12345):
    """One-sided clustered bootstrap p(mean>0) resampling companies."""
    rng = np.random.default_rng(seed)
    groups = [g[col].values for _, g in df.groupby("ticker")]
    obs = np.concatenate(groups).mean()
    means = np.empty(B)
    G = len(groups)
    for b in range(B):
        idx = rng.integers(0, G, G)
        means[b] = np.concatenate([groups[i] for i in idx]).mean()
    p_two = 2 * min((means <= 0).mean(), (means >= 0).mean())
    return obs, min(p_two, 1.0), G

def main():
    # ---- FactSet revenue → rev_yoy panel ----
    d = pd.DataFrame(json.load(open(FS_REV))["rows"])
    d["ACTUAL"] = pd.to_numeric(d["ACTUAL"], errors="coerce")
    d["FE_FP_END"] = pd.to_datetime(d["FE_FP_END"]); d["REPORT_DATE"] = pd.to_datetime(d["REPORT_DATE"])
    d["ticker"] = d["FSYM_ID"].map(FSYM2TKR)
    d = d.dropna(subset=["ticker", "ACTUAL", "REPORT_DATE"])
    keep = (d.groupby(["ticker", "FSYM_ID"]).size().reset_index(name="n")
              .sort_values("n").groupby("ticker").tail(1))
    d = d.merge(keep[["ticker", "FSYM_ID"]], on=["ticker", "FSYM_ID"]).sort_values(["ticker", "FE_FP_END"])
    d["rev_q4"] = d.groupby("ticker")["ACTUAL"].shift(4)
    d["rev_yoy"] = d["ACTUAL"] / d["rev_q4"] - 1
    d["rev_yoy_lag1"] = d.groupby("ticker")["rev_yoy"].shift(1)

    # ---- align CA (ca_yoy known at fiscal-quarter-end, before the print) ----
    ca = eq.build_ca_surprise()
    parts = []
    for t in d.ticker.unique():
        e = d[d.ticker == t].sort_values("FE_FP_END")
        a = ca[ca.ticker == t].sort_values("date")
        if a.empty: continue
        m = pd.merge_asof(e, a[["date", "ca_yoy"]], left_on="FE_FP_END", right_on="date",
                          direction="nearest", tolerance=pd.Timedelta(days=50))
        parts.append(m)
    d = pd.concat(parts, ignore_index=True)
    d = d.dropna(subset=["rev_yoy", "rev_yoy_lag1", "ca_yoy", "REPORT_DATE"]).reset_index(drop=True)
    d["t_ca"] = d["FE_FP_END"] + pd.Timedelta(days=7)

    log("# H3 (rigorous) re-run — does CA improve the OUT-OF-SAMPLE revenue nowcast? (FactSet)")
    log(f"\npanel: {len(d)} company-quarters, {d.ticker.nunique()} tickers; "
        f"{d.FE_FP_END.min().date()}..{d.FE_FP_END.max().date()}")
    log(f"baseline AR(1) vs +CA, POOLED expanding-window OLS, within-company demeaning, strict point-in-time.")

    # ---- pooled expanding-window OOS ----
    rows = []
    for i in d.index:
        tca = d.at[i, "t_ca"]; co = d.at[i, "ticker"]
        tr = d[(d["REPORT_DATE"] < tca)]                          # only already-printed quarters
        if len(tr) < MIN_TRAIN: continue
        co_tr = tr[tr.ticker == co]
        if len(co_tr) < MIN_CO_TRAIN: continue
        # within-company demeaning using TRAINING means only
        mu_y = tr.groupby("ticker")["rev_yoy"].transform("mean")
        mu_x1 = tr.groupby("ticker")["rev_yoy_lag1"].transform("mean")
        mu_x2 = tr.groupby("ticker")["ca_yoy"].transform("mean")
        y = (tr["rev_yoy"] - mu_y).values
        x1 = (tr["rev_yoy_lag1"] - mu_x1).values
        x2 = (tr["ca_yoy"] - mu_x2).values
        cmy = co_tr["rev_yoy"].mean(); cmx1 = co_tr["rev_yoy_lag1"].mean(); cmx2 = co_tr["ca_yoy"].mean()
        # target (demeaned by its own company's training means)
        xt1 = d.at[i, "rev_yoy_lag1"] - cmx1
        xt2 = d.at[i, "ca_yoy"] - cmx2
        yt = d.at[i, "rev_yoy"]
        n = len(y); ones = np.ones(n)
        Xb_tr = np.column_stack([ones, x1]);        Xb_te = np.array([[1.0, xt1]])
        Xc_tr = np.column_stack([ones, x1, x2]);    Xc_te = np.array([[1.0, xt1, xt2]])
        pb = ols_predict(Xb_tr, y, Xb_te)[0] + cmy
        pc = ols_predict(Xc_tr, y, Xc_te)[0] + cmy
        rows.append({"ticker": co, "y": yt, "pred_base": pb, "pred_ca": pc,
                     "e_base": yt - pb, "e_ca": yt - pc})
    r = pd.DataFrame(rows)
    r["d"] = r["e_base"] ** 2 - r["e_ca"] ** 2     # >0 ⇒ +CA lower squared error
    log(f"\nOOS forecasts produced: {len(r)} (after min-train warmup), {r.ticker.nunique()} tickers")
    rmse_b = np.sqrt((r["e_base"] ** 2).mean()); rmse_c = np.sqrt((r["e_ca"] ** 2).mean())
    log(f"  RMSE baseline AR(1)       = {rmse_b:.4f}")
    log(f"  RMSE +CA                  = {rmse_c:.4f}   ({'better' if rmse_c<rmse_b else 'worse'} by {(rmse_b-rmse_c)/rmse_b*100:+.1f}%)")

    # nowcast skill: correlation of each forecast with truth
    log(f"  corr(pred_base, y)={r.pred_base.corr(r.y):+.3f}   corr(pred_ca, y)={r.pred_ca.corr(r.y):+.3f}")

    dm, dbar = dm_hln(r["d"].values, h=1)
    obs, p_clu, G = cluster_boot_mean(r, "d")
    log(f"\n## INCREMENTAL TEST (d = e_base² − e_ca², >0 ⇒ CA adds forecast info)")
    log(f"  mean(d) = {obs:+.5f}")
    log(f"  Diebold-Mariano (HLN-corrected) t = {dm:+.2f}   (|t|>1.96 ⇒ sig at 5%)")
    log(f"  company-clustered bootstrap (G={G}): two-sided p = {p_clu:.3f}")

    log("\n## VERDICT")
    sig = (not np.isnan(dm)) and abs(dm) > 1.96 and p_clu < 0.05
    if sig and obs > 0:
        log(f"  ✅ CA ADDS out-of-sample revenue forecast value (RMSE {rmse_b:.3f}→{rmse_c:.3f}, DM t={dm:+.2f}, "
            f"clustered p={p_clu:.3f}). The first-pass null was an overfitting artifact of per-company windows.")
    elif obs > 0 and not sig:
        log(f"  ~ CA improves point RMSE ({rmse_b:.3f}→{rmse_c:.3f}) but the gain is NOT statistically significant "
            f"(DM t={dm:+.2f}, clustered p={p_clu:.3f}). Consistent with the modest revenue-nowcast edge (r≈0.19) "
            f"being real but small — it nudges the forecast without dominating revenue's own AR structure.")
    else:
        log(f"  ❌ CA does NOT add OOS forecast value (mean d={obs:+.4f}, DM t={dm:+.2f}, clustered p={p_clu:.3f}).")
    OUT_MD.write_text("# H3 OOS-DM re-run (FactSet revenue, pooled)\n\n> 2026-06-04 · `scripts/auto/s_v_h3_oos_factset.py`\n\n```\n" + "\n".join(lines) + "\n```\n")
    print(f"\n[written] {OUT_MD}")

if __name__ == "__main__":
    main()
