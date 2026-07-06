"""
결합 패널 빌드 — 각 조합에 대해 single X들과 combined X를 같은 회사·같은 분기에 정렬.

결합 방식: 채널마다 스케일이 다르므로(카드=달러, 방문=명수, 웹=유저) 각 x_yoy를 z-score 표준화
후 평균 → combined_x. (동일 스케일로 맞춰 단순 평균 = equal-weight 신호 블렌드.)
공정 비교를 위해 single도 같은 공통-티커 패널에서 z-score해 비교(회사셋 동일).

기존 코드 재사용: ys_lib.build_card/foot/click, ys_lib.load_factset. no-lookahead 가드 동일.

OUT: outputs/panel_<combo>.csv  (ticker, FE_FP_END, y, x_single_*, combined_x)

Usage:  python cb_01_build.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cb_config import COMBOS, OUT, YS_SCRIPTS, YSROOT, MIN_COMMON  # noqa: E402

sys.path.insert(0, str(YS_SCRIPTS))
import ys_lib as L  # noqa: E402
from ys_config import CARD_CSV, FOOT_CSVS, CLICK_CSV, CLICK_NAME2TKR  # noqa: E402

FACTSET = YSROOT / "data" / "factset_yswitch_pit.json"
Y_COL = "surprise_early"


def channel_x() -> dict:
    return {"card": L.build_card(CARD_CSV),
            "foot": L.build_foot(FOOT_CSVS),
            "web":  L.build_click(CLICK_CSV, CLICK_NAME2TKR)}


def align_channel(xdf: pd.DataFrame, y: pd.DataFrame) -> pd.DataFrame:
    """merge_asof one channel's x_yoy onto each surprise event (no-lookahead)."""
    xdf = xdf.sort_values(["ticker", "date"])
    rows = []
    for t in sorted(set(xdf.ticker) & set(y.ticker)):
        e = y[y.ticker == t].sort_values("FE_FP_END")
        a = xdf[xdf.ticker == t].dropna(subset=["x_yoy"]).sort_values("date")
        if a.empty:
            continue
        m = pd.merge_asof(e, a[["date", "x_yoy"]].rename(columns={"date": "x_date"}),
                          left_on="FE_FP_END", right_on="x_date",
                          direction="nearest", tolerance=pd.Timedelta(days=45))
        rows.append(m)
    if not rows:
        return pd.DataFrame()
    p = pd.concat(rows, ignore_index=True).dropna(subset=["x_yoy"])
    return p[p["x_date"] < p["REPORT_DATE"]][["ticker", "FE_FP_END", Y_COL, "x_yoy"]]


def main():
    y = L.load_factset(FACTSET)[["ticker", "FE_FP_END", "REPORT_DATE", Y_COL]].dropna(subset=[Y_COL])
    X = channel_x()

    # per-channel aligned panels (event-level x_yoy per channel)
    aligned = {ch: align_channel(X[ch], y).rename(columns={"x_yoy": f"x_{ch}"})
               for ch in ["card", "foot", "web"]}

    summary = []
    for name, chans in COMBOS.items():
        # inner-join channels on (ticker, FE_FP_END, y) so every event has ALL channels present
        base = aligned[chans[0]]
        for ch in chans[1:]:
            base = base.merge(aligned[ch], on=["ticker", "FE_FP_END", Y_COL], how="inner")
        n_tk = base.ticker.nunique()
        if n_tk < MIN_COMMON:
            summary.append({"combo": name, "n_tickers": n_tk, "n_events": len(base),
                            "status": "SKIP (n<%d)" % MIN_COMMON})
            continue

        # z-score each channel's x within THIS common panel, then combined = mean of z's
        for ch in chans:
            col = f"x_{ch}"
            mu, sd = base[col].mean(), base[col].std()
            base[f"z_{ch}"] = (base[col] - mu) / sd if sd > 0 else 0.0
        zcols = [f"z_{ch}" for ch in chans]
        base["combined_x"] = base[zcols].mean(axis=1)

        base.to_csv(OUT / f"panel_{name.replace('+','_')}.csv", index=False)
        summary.append({"combo": name, "n_tickers": n_tk, "n_events": len(base),
                        "channels": "+".join(chans), "status": "OK"})

    sm = pd.DataFrame(summary)
    sm.to_csv(OUT / "combo_coverage.csv", index=False)
    print("=== 조합별 커버리지 ===")
    print(sm.to_string(index=False))
    print(f"\nsaved panels to {OUT}")


if __name__ == "__main__":
    main()
