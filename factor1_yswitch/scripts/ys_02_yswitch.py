"""
Y-switching — the core experiment. For each channel panel, hold X fixed and switch Y across
targets, reporting 지훈's verdict gate (clustered-bootstrap p_boot + shuffle-surrogate p_surr)
PLUS Spearman, hit-rate, and cross-sectional rank-IC / IC-IR.

Verdict (지훈 gate): pass = p_boot<0.05 AND p_surr<0.05.
Baseline reference: 지훈 factor3 card × surprise_early r=+0.192.

OUT: outputs/yswitch_results.csv  +  outputs/yswitch_report.md

Usage:  python ys_02_yswitch.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "factor1" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from f1_stats import cluster_boot, surrogate, within_company_corr  # noqa: E402  (지훈 shared)
from ys_config import OUT  # noqa: E402
import ys_lib as L  # noqa: E402

CHANNELS = ["card", "foot", "click"]
X_VARS   = ["x_yoy", "x_yoy_3m"]
Y_VARS   = ["rev_yoy", "surprise_early", "surprise_print"]
rec, md = [], []


def log(s=""):
    print(s); md.append(s)


def one(d, x, y, tag):
    r, pb, n = cluster_boot(d, x, y)
    ps = surrogate(d, x, y, r) if not np.isnan(r) else np.nan
    rho, sp_p, _ = L.spearman_panel(d, x, y)
    hr, _ = L.hit_rate(d, x, y)
    ic = L.rank_ic(d, x, y)
    passed = (not np.isnan(ps)) and ps < 0.05 and (not np.isnan(pb)) and pb < 0.05
    verdict = "PASS" if passed else ("n/a" if np.isnan(ps) else "fail")
    log(f"  {tag:34s} r={_f(r)} n={n:>3} p_boot={_f(pb)} p_surr={_f(ps)} "
        f"| rho={_f(rho)} hit={_p(hr)} IC={_f(ic['mean_ic'])} IR={_f(ic['ic_ir'])} "
        f"nQ={ic['n_quarters']:>2}  [{verdict}]")
    rec.append({"channel": tag.split("|")[0].strip(), "x": x, "y": y,
                "r": _round(r), "n": n, "p_boot": _round(pb), "p_surr": _round(ps),
                "spearman_rho": _round(rho), "spearman_p": _round(sp_p),
                "hit_rate": _round(hr), "mean_ic": _round(ic["mean_ic"]),
                "ic_ir": _round(ic["ic_ir"]), "ic_t": _round(ic["t_stat"]),
                "ic_nq": ic["n_quarters"], "pass": passed})


def _f(v):  return "  nan" if (v is None or (isinstance(v, float) and np.isnan(v))) else f"{v:+.3f}"
def _p(v):  return " nan" if (v is None or (isinstance(v, float) and np.isnan(v))) else f"{v:.2f}"
def _round(v): return None if (v is None or (isinstance(v, float) and np.isnan(v))) else round(float(v), 4)


def main():
    log("# Y-switching experiment — Carbon Arc X (card/foot/click) × FactSet Y\n")
    log("Verdict gate (지훈): p_boot<0.05 AND p_surr<0.05. Baseline: card×surprise_early r≈+0.192.")
    log("Metrics: r (Pearson, clustered-boot), rho (Spearman), hit (sign agreement),")
    log("         IC/IR (per-quarter cross-sectional rank-IC mean & info-ratio).\n")

    for ch in CHANNELS:
        p = OUT / f"panel_{ch}.csv"
        if not p.exists():
            log(f"## {ch.upper()} — panel missing, skipped\n"); continue
        d = pd.read_csv(p)
        d["FE_FP_END"] = pd.to_datetime(d["FE_FP_END"])
        d = d.sort_values(["ticker", "FE_FP_END"])
        log(f"## {ch.upper()}  ({len(d)} events · {d.ticker.nunique()} tickers · "
            f"{d.FE_FP_END.min().date()}..{d.FE_FP_END.max().date()})")

        # --- Y switch on the primary X = x_yoy ---
        log(f"### Y-switch (X = x_yoy)")
        for y in Y_VARS:
            one(d, "x_yoy", y, f"{ch} | x_yoy → {y}")
        wc = within_company_corr(d, "x_yoy", "surprise_early")
        log(f"  within-company corr(x_yoy, surprise_early) = {_f(wc)}  "
            f"(firm-mean removed → right quarter, not just right firm)")

        # --- X transform robustness on the winning Y (surprise_early) ---
        log(f"### X-transform robustness → surprise_early")
        for x in X_VARS:
            one(d, x, "surprise_early", f"{ch} | {x} → surprise_early")

        # --- lead/lag: does prior-quarter X lead? ---
        log(f"### lead/lag → surprise_early")
        one(d, "x_yoy_lag1", "surprise_early", f"{ch} | x_yoy(t-1) → surprise_early")
        log("")

    df = pd.DataFrame(rec)
    df.to_csv(OUT / "yswitch_results.csv", index=False)
    (OUT / "yswitch_report.md").write_text("\n".join(md))
    log("## SUMMARY — passes (p_boot<0.05 & p_surr<0.05)")
    pas = df[df["pass"]]
    if pas.empty:
        log("  (none passed the strict dual gate — see r / IC / hit for directional signal)")
    else:
        for _, r in pas.iterrows():
            log(f"  ✅ {r.channel:6} {r.x:12} → {r.y:15} r={r.r:+.3f} IC={r.mean_ic} IR={r.ic_ir}")
    print(f"\nsaved: {OUT/'yswitch_results.csv'}  +  {OUT/'yswitch_report.md'}")


if __name__ == "__main__":
    main()
