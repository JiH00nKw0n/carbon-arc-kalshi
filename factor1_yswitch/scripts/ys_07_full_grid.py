"""
전체 그리드 검정 (8 Y × 3 channel = 24 조합) — LLM 예측과 온전히 대조할 완전한 ground truth.

Y 소스 3개를 통합:
  factset_yswitch_pit.json  → rev_yoy, surprise_early, surprise_print
  factset_sss_pit.json      → sss_surprise (=SSS_ACTUAL−SSS_CONS), sss_level (=SSS_ACTUAL)
  factset_nonrev_pit.json   → SALES_RSF, OCCUPY_RATE_TOT, GMV (각 y_surprise)

각 Y 이벤트에 채널 X(card/foot/click) x_yoy 를 no-lookahead(x_date<REPORT_DATE) 정렬 후 검정.
검정 = 지훈 clustered-bootstrap(p_boot) + shuffle-surrogate(p_surr) + rank-IC.

OUT: llm_identify/outputs/gt_channel_metric_full.csv  (24행: channel,y,r,p_surr,mean_ic,pass,n)

Usage:  python ys_07_full_grid.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "factor1" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from f1_stats import cluster_boot, surrogate  # noqa: E402
from ys_config import (CARD_CSV, FOOT_CSVS, CLICK_CSV, CLICK_NAME2TKR, DATA)  # noqa: E402
import ys_lib as L  # noqa: E402

GT_OUT = Path(__file__).resolve().parents[1] / "llm_identify" / "outputs" / "gt_channel_metric_full.csv"
CHANNELS = {"card": None, "foot": None, "click": None}


def build_x():
    return {"card":  L.build_card(CARD_CSV),
            "foot":  L.build_foot(FOOT_CSVS),
            "click": L.build_click(CLICK_CSV, CLICK_NAME2TKR)}


def y_events() -> dict:
    """returns {y_name: DataFrame[ticker, FE_FP_END, REPORT_DATE, yval]} for all 8 Y."""
    out = {}
    # 1) revenue-based (yswitch pit)
    yw = L.load_factset(DATA / "factset_yswitch_pit.json")
    for y in ["rev_yoy", "surprise_early", "surprise_print"]:
        out[y] = yw[["ticker", "FE_FP_END", "REPORT_DATE", y]].rename(columns={y: "yval"}).dropna(subset=["yval"])
    # 2) SSS pit
    sss = pd.DataFrame(json.load(open(DATA / "factset_sss_pit.json"))["rows"])
    for c in ("SSS_ACTUAL", "SSS_CONS"):
        sss[c] = pd.to_numeric(sss[c], errors="coerce")
    sss["FE_FP_END"] = pd.to_datetime(sss["FE_FP_END"]); sss["REPORT_DATE"] = pd.to_datetime(sss["REPORT_DATE"])
    sss = sss.dropna(subset=["SSS_ACTUAL", "SSS_CONS"])
    sss["sss_surprise"] = sss["SSS_ACTUAL"] - sss["SSS_CONS"]
    out["sss_surprise"] = sss[["ticker", "FE_FP_END", "REPORT_DATE", "sss_surprise"]].rename(columns={"sss_surprise": "yval"})
    out["sss_level"] = sss[["ticker", "FE_FP_END", "REPORT_DATE", "SSS_ACTUAL"]].rename(columns={"SSS_ACTUAL": "yval"})
    # 3) nonrev pit (surprise form)
    nr = json.load(open(DATA / "factset_nonrev_pit.json"))
    for metric in ["SALES_RSF", "OCCUPY_RATE_TOT", "GMV"]:
        df = pd.DataFrame(nr[metric])
        df["FE_FP_END"] = pd.to_datetime(df["FE_FP_END"]); df["REPORT_DATE"] = pd.to_datetime(df["REPORT_DATE"])
        df["y_surprise"] = pd.to_numeric(df["y_surprise"], errors="coerce")
        out[metric] = df[["ticker", "FE_FP_END", "REPORT_DATE", "y_surprise"]].rename(columns={"y_surprise": "yval"}).dropna(subset=["yval"])
    return out


def align(x: pd.DataFrame, y: pd.DataFrame) -> pd.DataFrame:
    x = x.sort_values(["ticker", "date"])
    rows = []
    for t in sorted(set(x.ticker) & set(y.ticker)):
        e = y[y.ticker == t].sort_values("FE_FP_END")
        a = x[x.ticker == t].dropna(subset=["x_yoy"]).sort_values("date")
        if a.empty:
            continue
        m = pd.merge_asof(e, a[["date", "x_yoy"]].rename(columns={"date": "x_date"}),
                          left_on="FE_FP_END", right_on="x_date",
                          direction="nearest", tolerance=pd.Timedelta(days=45))
        rows.append(m)
    if not rows:
        return pd.DataFrame()
    p = pd.concat(rows, ignore_index=True).dropna(subset=["x_yoy"])
    return p[p["x_date"] < p["REPORT_DATE"]]   # no-lookahead


def main():
    X = build_x()
    Y = y_events()
    rows = []
    for ch, xdf in X.items():
        for yname, ydf in Y.items():
            p = align(xdf, ydf)
            if len(p) < 15:
                rows.append({"channel": ch, "y": yname, "r": None, "n": len(p),
                             "p_boot": None, "p_surr": None, "mean_ic": None, "ic_ir": None,
                             "pass": False, "note": "n<15"})
                continue
            p = p.rename(columns={"yval": "y"})
            r, pb, n = cluster_boot(p, "x_yoy", "y")
            ps = surrogate(p, "x_yoy", "y", r) if not np.isnan(r) else np.nan
            ic = L.rank_ic(p, "x_yoy", "y", min_names=4)
            rows.append({"channel": ch, "y": yname,
                         "r": round(r, 4) if not np.isnan(r) else None, "n": n,
                         "p_boot": round(pb, 4) if not np.isnan(pb) else None,
                         "p_surr": round(ps, 4) if not np.isnan(ps) else None,
                         "mean_ic": round(ic["mean_ic"], 4) if not np.isnan(ic["mean_ic"]) else None,
                         "ic_ir": round(ic["ic_ir"], 4) if not np.isnan(ic["ic_ir"]) else None,
                         "pass": bool((not np.isnan(ps)) and ps < 0.05 and (not np.isnan(pb)) and pb < 0.05),
                         "note": ""})
    gt = pd.DataFrame(rows)
    GT_OUT.parent.mkdir(parents=True, exist_ok=True)
    gt.to_csv(GT_OUT, index=False)

    print(f"=== FULL GRID: {len(gt)} rows (8 Y × 3 channel) ===\n")
    for ch in ["card", "foot", "click"]:
        sub = gt[gt.channel == ch]
        print(f"[{ch}]")
        for _, r in sub.iterrows():
            rr = f"{r['r']:+.3f}" if pd.notna(r["r"]) else "  —  "
            ps = f"{r['p_surr']:.3f}" if pd.notna(r["p_surr"]) else "  —  "
            v = "✅" if r["pass"] else ("·" if r["note"] else "❌")
            print(f"    {r['y']:16} r={rr} n={int(r['n']):>3} p_surr={ps} {v} {r['note']}")
        print()
    print(f"saved: {GT_OUT}")


if __name__ == "__main__":
    main()
