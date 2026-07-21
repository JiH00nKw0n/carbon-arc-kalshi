"""
foot traffic 전용 Y 탐색 — 왜 foot는 rev_yoy엔 붙고 surprise엔 안 붙나? foot(수량 신호)에
맞는 Y를 찾는다.

실험 1 (즉시): 인스토어 비중 subset. 지훈 altdata_ticker_screen.csv 의 strength(strong=인스토어
  ~85%+) 로 필터해 surprise_early 재검정. 방문=매출인 종목만 보면 surprise에도 붙는지.
실험 2: revenue_yoy 의 "잔차 서프라이즈" = rev_yoy 에서 컨센서스가 예측한 성장분을 뺀 잔차.
  (컨센서스 성장 기대 = (CONS_EARLY − 작년ACTUAL)/작년ACTUAL). foot가 rev_yoy엔 붙으니
  컨센서스가 놓친 잔차 성장에 신호가 남는지.

SSS/comps surprise 는 별도 fetch(ys_04) 후 합류.

OUT: outputs/foot_ytargets.md

Usage:  python ys_03_foot_ytargets.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "factor1" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from f1_stats import cluster_boot, surrogate  # noqa: E402
from ys_config import OUT  # noqa: E402
import ys_lib as L  # noqa: E402

SCREEN = Path(__file__).resolve().parents[2] / "factor1" / "data" / "altdata_ticker_screen.csv"
md = []


def log(s=""):
    print(s); md.append(s)


def test(d, x, y, tag):
    r, pb, n = cluster_boot(d, x, y)
    ps = surrogate(d, x, y, r) if not np.isnan(r) else np.nan
    rho, _, _ = L.spearman_panel(d, x, y)
    hr, _ = L.hit_rate(d, x, y)
    ic = L.rank_ic(d, x, y)
    v = "PASS" if (not np.isnan(ps) and ps < 0.05 and pb < 0.05) else ("n/a" if np.isnan(ps) else "fail")
    log(f"  {tag:44s} r={r:+.3f} n={n:>3} p_surr={ps:.3f} | rho={rho:+.3f} hit={hr:.2f} "
        f"IC={ic['mean_ic']:+.3f} IR={ic['ic_ir']:+.3f} nQ={ic['n_quarters']:>2} [{v}]")


def main():
    d = pd.read_csv(OUT / "panel_foot.csv")
    d["FE_FP_END"] = pd.to_datetime(d["FE_FP_END"])
    d = d.sort_values(["ticker", "FE_FP_END"])

    # attach strength (in-store dominance) from 지훈 screen
    strength = (pd.read_csv(SCREEN).query("data_type=='foot_traffic'")
                .set_index("ticker")["strength"].to_dict())
    d["strength"] = d["ticker"].map(strength).fillna("?")

    log("# foot traffic — Y target 탐색\n")
    log(f"panel: {len(d)} events · {d.ticker.nunique()} tickers")
    log(f"strength coverage: {d.groupby('strength').ticker.nunique().to_dict()}\n")

    log("## 기준선 (전체 foot)")
    test(d, "x_yoy", "rev_yoy", "ALL foot → rev_yoy")
    test(d, "x_yoy", "surprise_early", "ALL foot → surprise_early")

    log("\n## 실험 1 — 인스토어 비중 subset → surprise_early")
    log("  가설: 방문=매출인 종목만 보면 방문 정보가 surprise에도 남는다.")
    for s in ["strong", "moderate"]:
        sub = d[d.strength == s]
        if sub.ticker.nunique() >= 4 and len(sub) >= 10:
            test(sub, "x_yoy", "surprise_early", f"[{s}] foot → surprise_early "
                                                  f"({sub.ticker.nunique()}tkr)")
        else:
            log(f"  [{s}] skipped (tickers={sub.ticker.nunique()}, n={len(sub)})")
    # strong 종목의 rev_yoy 도 참고
    strong = d[d.strength == "strong"]
    test(strong, "x_yoy", "rev_yoy", "[strong] foot → rev_yoy (참고)")

    log("\n## 실험 2 — '잔차 서프라이즈' (컨센서스가 놓친 성장분)")
    log("  cons_growth = (CONS_EARLY − ACTUAL_{t-4}) / ACTUAL_{t-4}  (컨센서스가 기대한 YoY 성장)")
    log("  resid = rev_yoy − cons_growth  (실제 성장 − 기대 성장 = 컨센서스가 놓친 성장)")
    dd = d.copy()
    dd["actual_lag4"] = dd.groupby("ticker")["ACTUAL"].shift(4)
    dd["cons_growth"] = (dd["CONS_EARLY"] - dd["actual_lag4"]) / dd["actual_lag4"]
    dd["resid_surprise"] = dd["rev_yoy"] - dd["cons_growth"]
    test(dd, "x_yoy", "resid_surprise", "ALL foot → resid_surprise")
    test(dd[dd.strength == "strong"], "x_yoy", "resid_surprise",
         "[strong] foot → resid_surprise")

    (OUT / "foot_ytargets.md").write_text("\n".join(md))
    print(f"\nsaved: {OUT/'foot_ytargets.md'}")


if __name__ == "__main__":
    main()
