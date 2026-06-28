"""
Factor 1 — channel-agnostic evaluation (MSE-PRIMARY), per EXPERIMENT_SPEC.md §5-7.  $0, no LLM.
Run:  F1_CHANNEL=card python3 f1_22_eval.py

On ONE matched post-cutoff test set (LLM ablation preds define the rows; classical baselines
evaluated on the SAME rows), reports for every model: RMSE, R²_OOS, corr, corr²(calib ceiling),
MAE, sign-hit. Then: corr- AND MSE-skill super-additivity synergy (company-clustered bootstrap),
shuffle-company surrogate, architecture A/C/B, Z-depth. Writes results_{ch}.md.

Classical (fit pre-cutoff -> predict matched post-cutoff):
  N0 naive (company mean) / N1 X-OLS / N2 sent-OLS / N3 X+sent / N3b X+sent+lag.
"""
import os
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from f1_channels import active  # noqa: E402
from f1_lib import OUT, CUTOFF, sentiment, prior_calls, load_txindex, metrics  # noqa: E402

ARMS = ["fin", "fin+x", "fin+text", "fin+x+text"]


def event_table(p, ix):
    p = p.copy()
    p["FE_FP_END"] = pd.to_datetime(p["FE_FP_END"]); p["REPORT_DATE"] = pd.to_datetime(p["REPORT_DATE"])
    p = p.sort_values(["ticker", "FE_FP_END"])
    rows = []
    for tkr, g in p.groupby("ticker"):
        g = g.sort_values("FE_FP_END")
        for row in g.itertuples():
            if pd.isna(row.x_yoy) or pd.isna(row.surprise_early):
                continue
            calls = prior_calls(ix, tkr, row.REPORT_DATE, 1)
            path = calls[0] if calls else None
            hist = g[g.FE_FP_END < row.FE_FP_END]
            rows.append({"tkr": tkr, "fp": row.FE_FP_END, "report": row.REPORT_DATE,
                         "x_yoy": row.x_yoy, "true": row.surprise_early,
                         "lag_surprise": row.lag_surprise, "n_hist": len(hist),
                         "sent": sentiment(path) if path else np.nan, "has_call": path is not None})
    E = pd.DataFrame(rows)
    E["sent"] = E["sent"].fillna(0.0)
    return E


def ols(tr, te, cols):
    y = tr["true"].values * 100
    X = np.column_stack([np.ones(len(tr))] + [tr[c].values for c in cols])
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    Xt = np.column_stack([np.ones(len(te))] + [te[c].values for c in cols])
    return Xt @ b


def cross_fit_calibrate(df, arm, rng, K=5):
    """Leak-free realized calibration: K-fold over COMPANIES; fit true ~ a+b*raw on the other
    folds, predict the held-out fold. Returns out-of-fold calibrated preds (%) for all rows."""
    comps = list(df.tkr.unique()); rng.shuffle(comps)
    fold = {c: i % K for i, c in enumerate(comps)}
    f = df.tkr.map(fold).values
    y = df["true"].values * 100; x = df[arm].values
    out = np.full(len(df), np.nan)
    for k in range(K):
        tr, tem = f != k, f == k
        if tr.sum() < 3 or tem.sum() == 0:
            continue
        b, *_ = np.linalg.lstsq(np.column_stack([np.ones(tr.sum()), x[tr]]), y[tr], rcond=None)
        out[tem] = b[0] + b[1] * x[tem]
    return out


def boot_synergy(df, rng):
    """company-clustered bootstrap of corr- and MSE-skill super-additivity."""
    comps = df.tkr.unique()
    out = {"syn_corr": [], "syn_skill": [], "r_fwt": [], "skill_fwt": []}
    for _ in range(5000):
        d = pd.concat([df[df.tkr == c] for c in rng.choice(comps, len(comps), replace=True)])
        y = d["true"].values * 100
        var = ((y - y.mean()) ** 2).mean()
        cr, sk = {}, {}
        for a in ARMS:
            pa = d[a].values
            cr[a] = np.corrcoef(pa, y)[0, 1] if np.std(pa) > 1e-9 else 0.0
            sk[a] = 1 - ((y - pa) ** 2).mean() / var
        out["r_fwt"].append(cr["fin+x+text"]); out["skill_fwt"].append(sk["fin+x+text"])
        out["syn_corr"].append(cr["fin+x+text"] - (cr["fin+x"] + cr["fin+text"] - cr["fin"]))
        out["syn_skill"].append(sk["fin+x+text"] - (sk["fin+x"] + sk["fin+text"] - sk["fin"]))
    return out


def surrogate(df, arm, rng, N=5000):
    true = df["true"].values; pred = df[arm].values; tk = df["tkr"].values
    g = defaultdict(list)
    for i, t in enumerate(tk):
        g[t].append(i)
    bysize = defaultdict(list)
    for c, idx in g.items():
        bysize[len(idx)].append(c)
    r_obs = abs(np.corrcoef(pred, true)[0, 1]); cnt = 0
    for _ in range(N):
        pt = true.copy()
        for size, clist in bysize.items():
            if len(clist) < 2:
                continue
            for src, dst in zip(clist, rng.permutation(clist)):
                pt[g[src]] = true[g[dst]]
        if abs(np.corrcoef(pred, pt)[0, 1]) >= r_obs:
            cnt += 1
    return (cnt + 1) / (N + 1)


def main():
    ch = active()
    p = pd.read_csv(OUT / f"panel_{ch}.csv")
    ix = load_txindex()
    E = event_table(p, ix)
    train = E[E.report <= CUTOFF].dropna(subset=["x_yoy", "true"]).copy()
    train["lag_surprise"] = train["lag_surprise"].fillna(train["true"].mean())

    DROP = float(os.getenv("F1_DROP_OUTLIER_PCT", "0"))         # structural-break / outlier sensitivity
    A = pd.read_csv(OUT / f"preds_{ch}_ablation.csv")           # LLM rows define the eval set
    if DROP:
        n0 = len(A); A = A[A["true"].abs() * 100 <= DROP].copy()
        print(f"[{ch}] OUTLIER DROP |true|>{DROP:.0f}%: ablation eval {n0} -> {len(A)} rows")
    A["k"] = A.tkr + "|" + A.true.round(8).astype(str)
    E["k"] = E.tkr + "|" + E.true.round(8).astype(str)
    feat = E[["k", "sent", "lag_surprise"]].drop_duplicates("k")
    te = A.merge(feat, on="k", how="left")
    te["lag_surprise"] = te["lag_surprise"].fillna(train["true"].mean())
    te["sent"] = te["sent"].fillna(0.0)
    true = te["true"].values * 100
    cmean = train.groupby("tkr")["true"].mean(); gmean = train["true"].mean()
    for d in (train, te):
        d["x_sent"] = d["x_yoy"] * d["sent"]            # explicit classical X×Z (scalar) interaction

    # N5: gradient-boosted trees on the SAME scalar features — learns interactions/nonlinearity freely
    gb_pred = None
    try:
        from sklearn.ensemble import GradientBoostingRegressor
        feats = ["x_yoy", "sent", "lag_surprise"]
        gb = GradientBoostingRegressor(random_state=2026, n_estimators=150, max_depth=2, learning_rate=0.05)
        gb.fit(train[feats].values, train["true"].values * 100)
        gb_pred = gb.predict(te[feats].values)
    except Exception as e:
        print("  (sklearn GBT skipped:", e, ")")

    preds = {
        "N0 naive (company mean)": te.tkr.map(cmean).fillna(gmean).values * 100,
        "N1 X-OLS": ols(train, te, ["x_yoy"]),
        "N2 sentiment-OLS": ols(train, te, ["sent"]),
        "N3 X+sent (additive)": ols(train, te, ["x_yoy", "sent"]),
        "N4 X×sent interaction": ols(train, te, ["x_yoy", "sent", "x_sent"]),
        "N3b X+sent+lag": ols(train, te, ["x_yoy", "sent", "lag_surprise"]),
        "N4b +lag+interaction": ols(train, te, ["x_yoy", "sent", "lag_surprise", "x_sent"]),
        **({"N5 GBT (x,sent,lag)": gb_pred} if gb_pred is not None else {}),
        "LLM fin": te["fin"].values, "LLM fin+x": te["fin+x"].values,
        "LLM fin+text": te["fin+text"].values, "LLM fin+x+text": te["fin+x+text"].values,
    }

    L = [f"# Factor 1 — UNIFIED EVALUATION  ·  channel = {ch.upper()}  (MSE-primary)\n",
         f"matched test set n={len(te)} · {te.tkr.nunique()} companies (post-cutoff, prior-call, ≥3 hist).",
         f"truth: mean={te.true.mean()*100:+.2f}%  sd={te.true.std()*100:.2f}%  pos-rate={te.true.gt(0).mean():.2f}\n",
         f"  {'model':24s}  RMSE   R²_OOS   corr   corr²   MAE   sign",
         "  " + "-" * 66]
    for nm, pr in preds.items():
        m = metrics(pr, true)
        L.append(f"  {nm:24s}  {m['rmse']:5.2f}  {m['r2']:+.3f}  {m['corr']:+.3f}  {m['corr2']:.3f}  {m['mae']:5.2f}  {m['sign']:.2f}")

    # leak-free realized calibration of the LLM arms (raw number -> OOF rescale -> ceiling)
    n3b_r2 = metrics(preds["N3b X+sent+lag"], true)["r2"]
    L.append("\n## calibration — does the LLM's info survive a LEAK-FREE rescale? (R²_OOS)")
    L.append(f"  {'model':18s}  raw R²   calib R²(OOF)   corr²(ceiling)")
    for a in ARMS:
        cal = cross_fit_calibrate(te, a, np.random.default_rng(2026))
        mr, mc = metrics(te[a].values, true), metrics(cal, true)
        L.append(f"  LLM {a:14s}  {mr['r2']:+.3f}     {mc['r2']:+.3f}         {mr['corr2']:.3f}")
    L.append(f"  {'N3b (OLS, ref)':18s}  {n3b_r2:+.3f}     {n3b_r2:+.3f}         (self-calibrated)")
    L.append("  calib = leak-free 5-fold-by-company linear rescale (fit on other folds); ceiling = corr².")

    # synergy (corr & MSE-skill), company-clustered bootstrap
    rng = np.random.default_rng(2026)
    bs = boot_synergy(te, rng)
    L.append("\n## synergy — super-additivity (company-clustered bootstrap, 5000; seed 2026)")
    L.append(f"  {'quantity':16s} mean     95% CI            p(≤0)")
    for k, lab in [("r_fwt", "corr(fin+x+text)"), ("syn_corr", "synergy(corr)"),
                   ("skill_fwt", "skill(fin+x+text)"), ("syn_skill", "synergy(MSE-skill)")]:
        v = np.array(bs[k]); lo, hi = np.percentile(v, [2.5, 97.5]); pp = (v <= 0).mean()
        L.append(f"  {lab:16s} {v.mean():+.3f}  [{lo:+.3f},{hi:+.3f}]  {pp:.3f}{'  ✅' if pp < 0.05 else ''}")
    L.append("  synergy = M(fin+x+text) − [M(fin+x)+M(fin+text)−M(fin)];  >0 ⇒ X and Z super-additive.")

    # surrogate (firm-specific vs common artifact) on headline arm
    sp = surrogate(te, "fin+x+text", np.random.default_rng(2026))
    L.append(f"\n## shuffle-company surrogate (fin+x+text): p_surr={sp:.3f}{'  ✅ firm-specific' if sp < 0.05 else ''}")

    # architecture A/C/B
    ap = OUT / f"preds_{ch}_arch.csv"
    if ap.exists():
        a = pd.read_csv(ap)
        if DROP:
            a = a[a["true"].abs() * 100 <= DROP].copy()
        def cr(x): m = a[[x, "true"]].dropna(); return np.corrcoef(m[x], m["true"])[0, 1]  # noqa: E704
        L.append(f"\n## architecture (distilled scores vs end-to-end), n={len(a)}")
        L.append(f"  A (text→score)   corr={cr('A_rev'):+.3f}")
        L.append(f"  C (x+text→feat)  corr={cr('C_rev'):+.3f}")
        L.append(f"  B (end-to-end)   corr={cr('B_pred'):+.3f}")

    # Z-depth
    zp = OUT / f"preds_{ch}_zdepth.csv"
    if zp.exists():
        z = pd.read_csv(zp)
        if DROP:
            z = z[z["true"].abs() * 100 <= DROP].copy()
        if len(z):
            tz = z["true"].values * 100
            m1, m2 = metrics(z["z1"].values, tz), metrics(z["z2"].values, tz)
            L.append(f"\n## Z-depth (1 vs 2 prior calls), n={len(z)}")
            L.append(f"  z1 (1 call)   RMSE={m1['rmse']:.2f}  corr={m1['corr']:+.3f}")
            L.append(f"  z2 (2 calls)  RMSE={m2['rmse']:.2f}  corr={m2['corr']:+.3f}")

    out = "\n".join(L)
    print(out)
    (OUT / f"results_{ch}.md").write_text(f"<!-- f1_22_eval.py · channel={ch} -->\n```\n" + out + "\n```\n")
    print(f"\n[written] {OUT/f'results_{ch}.md'}")


if __name__ == "__main__":
    main()
