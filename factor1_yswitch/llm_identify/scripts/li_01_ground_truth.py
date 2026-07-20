"""
Ground-truth 통합 (Task 6) — LLM 식별의 '정답지'.

두 레벨의 정답:
  (A) channel × Y : 각 조합의 실제 r / rank-IC / pass  (metric-fit 정답)
  (B) channel × company : 각 회사에서 X가 Y(surprise_early)를 얼마나 잘 예측하는가
      = per-company Pearson r (그 회사 시계열에서 x_yoy vs surprise_early). (company-fit 정답)

패널은 factor1_yswitch/outputs/panel_{card,foot,click}.csv (no-lookahead 적용본) 재사용.
SSS/nonrev 패널도 있으면 합류.

산출물:
  outputs/gt_channel_metric.csv   (channel, y, r, mean_ic, pass, n)
  outputs/gt_channel_company.csv  (channel, ticker, r_company, n_company, y=surprise_early)

Usage:  python li_01_ground_truth.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "factor1" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1].parent / "scripts"))
from f1_stats import cluster_boot, surrogate  # noqa: E402
from li_config import OUT, YSROOT  # noqa: E402
import ys_lib as L  # noqa: E402

PANELS = YSROOT / "outputs"
Y_LEVELS = ["rev_yoy", "surprise_early", "surprise_print"]


def channel_metric_table() -> pd.DataFrame:
    rows = []
    for ch in ["card", "foot", "click"]:
        p = PANELS / f"panel_{ch}.csv"
        if not p.exists():
            continue
        d = pd.read_csv(p)
        d["FE_FP_END"] = pd.to_datetime(d["FE_FP_END"])
        for y in Y_LEVELS:
            r, pb, n = cluster_boot(d, "x_yoy", y)
            ps = surrogate(d, "x_yoy", y, r) if not np.isnan(r) else np.nan
            ic = L.rank_ic(d, "x_yoy", y)
            rows.append({"channel": ch, "y": y, "r": round(r, 4), "n": n,
                         "p_boot": round(pb, 4), "p_surr": round(ps, 4) if not np.isnan(ps) else None,
                         "mean_ic": round(ic["mean_ic"], 4) if not np.isnan(ic["mean_ic"]) else None,
                         "ic_ir": round(ic["ic_ir"], 4) if not np.isnan(ic["ic_ir"]) else None,
                         "pass": bool((not np.isnan(ps)) and ps < 0.05 and pb < 0.05)})
    # attach SSS (foot) if present
    sss = PANELS / "panel_foot_sss.csv"
    if sss.exists():
        d = pd.read_csv(sss)
        d["FE_FP_END"] = pd.to_datetime(d["FE_FP_END"])
        for y in ["sss_surprise", "SSS_ACTUAL"]:
            r, pb, n = cluster_boot(d, "x_yoy", y)
            ps = surrogate(d, "x_yoy", y, r) if not np.isnan(r) else np.nan
            ic = L.rank_ic(d, "x_yoy", y)
            rows.append({"channel": "foot", "y": y, "r": round(r, 4), "n": n,
                         "p_boot": round(pb, 4), "p_surr": round(ps, 4) if not np.isnan(ps) else None,
                         "mean_ic": round(ic["mean_ic"], 4) if not np.isnan(ic["mean_ic"]) else None,
                         "ic_ir": round(ic["ic_ir"], 4) if not np.isnan(ic["ic_ir"]) else None,
                         "pass": bool((not np.isnan(ps)) and ps < 0.05 and pb < 0.05)})
    return pd.DataFrame(rows)


def channel_company_table(min_obs: int = 5) -> pd.DataFrame:
    """per-company r(x_yoy, surprise_early) — 각 회사에서 신호 강도."""
    rows = []
    for ch in ["card", "foot", "click"]:
        p = PANELS / f"panel_{ch}.csv"
        if not p.exists():
            continue
        d = pd.read_csv(p).dropna(subset=["x_yoy", "surprise_early"])
        for t, g in d.groupby("ticker"):
            if len(g) >= min_obs and g["x_yoy"].nunique() > 1 and g["surprise_early"].nunique() > 1:
                r = np.corrcoef(g["x_yoy"], g["surprise_early"])[0, 1]
                rows.append({"channel": ch, "ticker": t, "y": "surprise_early",
                             "r_company": round(float(r), 4), "n_company": len(g)})
    return pd.DataFrame(rows).sort_values(["channel", "r_company"], ascending=[True, False])


def main():
    cm = channel_metric_table()
    cm.to_csv(OUT / "gt_channel_metric.csv", index=False)
    print("=== channel × Y ground truth ===")
    print(cm.to_string(index=False))

    cc = channel_company_table()
    cc.to_csv(OUT / "gt_channel_company.csv", index=False)
    print(f"\n=== channel × company ground truth: {len(cc)} rows ===")
    for ch in ["card", "foot", "click"]:
        sub = cc[cc.channel == ch]
        print(f"\n[{ch}] {len(sub)} companies (n>=5 qtrs). top5 by r_company:")
        print(sub.head(5)[["ticker", "r_company", "n_company"]].to_string(index=False))
    print(f"\nsaved: {OUT/'gt_channel_metric.csv'}, {OUT/'gt_channel_company.csv'}")


if __name__ == "__main__":
    main()
