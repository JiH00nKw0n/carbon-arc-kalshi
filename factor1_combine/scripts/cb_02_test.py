"""
결합 효과 검정 — single X vs combined X 중 무엇이 Y(surprise_early)를 더 잘 예측하나.

각 pair 조합(card+foot, card+web)에 대해 동일 공통-티커 패널에서:
  - single 각 채널 z-score → Y 상관
  - combined (z 평균) → Y 상관
  - 결합이 개선하는가? (combined r > max(single r) 이면 시너지)
지훈 검정(cluster_boot + surrogate) 재사용.

OUT: outputs/combine_results.csv  +  outputs/combine_report.md

Usage:  python cb_02_test.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cb_config import COMBOS, OUT, F1_STATS, YS_SCRIPTS, MIN_OBS  # noqa: E402

sys.path.insert(0, str(F1_STATS)); sys.path.insert(0, str(YS_SCRIPTS))
from f1_stats import cluster_boot, surrogate  # noqa: E402
import ys_lib as L  # noqa: E402

Y = "surprise_early"
md, rec = [], []


def log(s=""):
    print(s); md.append(s)


def test(d, x, y, tag):
    r, pb, n = cluster_boot(d, x, y)
    ps = surrogate(d, x, y, r) if not np.isnan(r) else np.nan
    rho, _, _ = L.spearman_panel(d, x, y)
    v = "PASS" if (not np.isnan(ps) and ps < 0.05 and pb < 0.05) else ("n/a" if np.isnan(ps) else "fail")
    log(f"  {tag:26s} r={r:+.3f}  n={n:>3}  p_surr={ps:.3f}  rho={rho:+.3f}  [{v}]")
    return {"label": tag, "r": round(r, 4) if not np.isnan(r) else None, "n": n,
            "p_surr": round(ps, 4) if not np.isnan(ps) else None,
            "pass": bool((not np.isnan(ps)) and ps < 0.05 and pb < 0.05)}


def main():
    log("# X 조합 실험 — single vs combined → revenue surprise\n")
    log("Y = surprise_early 고정. 결합 = 채널별 x_yoy z-score 평균. 동일 공통-티커 패널에서 비교.")
    log("시너지 = combined r > max(single r).\n")

    pairs = {k: v for k, v in COMBOS.items() if len(v) >= 2}
    for name, chans in pairs.items():
        f = OUT / f"panel_{name.replace('+','_')}.csv"
        if not f.exists():
            log(f"## {name} — 패널 없음 (n부족), skip\n"); continue
        d = pd.read_csv(f)
        d["FE_FP_END"] = pd.to_datetime(d["FE_FP_END"])
        log(f"## {name}  ({d.ticker.nunique()} 공통티커 · {len(d)} 이벤트)")
        if len(d) < MIN_OBS:
            log(f"  n<{MIN_OBS}, skip\n"); continue

        singles = []
        for ch in chans:
            res = test(d, f"z_{ch}", Y, f"{ch} 단독")
            res["combo"] = name; res["kind"] = "single"; rec.append(res)
            if res["r"] is not None:
                singles.append(res["r"])
        cres = test(d, "combined_x", Y, f"{name} 결합")
        cres["combo"] = name; cres["kind"] = "combined"; rec.append(cres)

        # synergy verdict
        best_single = max(singles) if singles else np.nan
        if cres["r"] is not None and not np.isnan(best_single):
            delta = cres["r"] - best_single
            verdict = "✅ 시너지 (결합>단독)" if delta > 0.01 else (
                      "→ 동등" if abs(delta) <= 0.01 else "❌ 결합이 더 나쁨")
            log(f"  → best single r={best_single:+.3f}, combined r={cres['r']:+.3f}, "
                f"Δ={delta:+.3f}  {verdict}")
        log("")

    pd.DataFrame(rec).to_csv(OUT / "combine_results.csv", index=False)
    (OUT / "combine_report.md").write_text("\n".join(md))
    print(f"saved: {OUT/'combine_results.csv'}, {OUT/'combine_report.md'}")


if __name__ == "__main__":
    main()
