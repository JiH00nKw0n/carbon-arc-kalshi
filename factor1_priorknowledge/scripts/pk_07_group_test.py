"""
회사 그룹화 검정 — 개별 회사(분기 8~10, 노이즈 큼) 대신 그룹 pooled 상관 비교.

개별 per-company r은 검정력 부족(90% 회사에서 r이 0과 구별 안 됨). 대신 회사를 2그룹으로
나누고 각 그룹의 pooled X→Y 상관(그룹당 이벤트 200+)을 비교하면 통계적으로 견고.

핵심 질문: 회사를 어떤 기준으로 나누면, "예측 잘 되는 그룹 vs 안 되는 그룹"의 신호차가 실제로
유의하게 나타나는가? 세 그룹화 기준 비교:
  (1) LLM signal_strength   — LLM 예측(strong vs weak)이 실제 그룹차를 만드나
  (2) 사전지식 traffic_relevant — 도메인 지식(방문이 매출동인인가)이 그룹차를 만드나
  (3) FactSet margin_vol      — 정량지표(고변동성 vs 저변동성)가 그룹차를 만드나

검정: 그룹별 clustered-bootstrap r + 두 그룹 r 차이의 bootstrap 유의성 (회사 단위 재추출).

OUT: outputs/group_test.md + group_test.csv

Usage:  python pk_07_group_test.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pk_config import DATA, OUT  # noqa: E402

F1 = Path(__file__).resolve().parents[2] / "factor1" / "scripts"
YS = Path(__file__).resolve().parents[2] / "factor1_yswitch" / "outputs"
LI = Path(__file__).resolve().parents[2] / "factor1_yswitch" / "llm_identify" / "outputs"
sys.path.insert(0, str(F1))
from f1_stats import cluster_boot  # noqa: E402

Y = "surprise_early"
md, rec = [], []


def log(s=""):
    print(s); md.append(s)


def group_diff_boot(d, gcol, x=Y, n=5000, seed=2026):
    """두 그룹 pooled r 차이의 bootstrap. 회사 단위 재추출. returns (r_hi, r_lo, diff, p)."""
    rng = np.random.default_rng(seed)
    hi = d[d[gcol] == "hi"]; lo = d[d[gcol] == "lo"]
    def pooled_r(sub):
        m = sub[["x_yoy", x]].dropna()
        return np.corrcoef(m["x_yoy"], m[x])[0, 1] if len(m) > 3 and m["x_yoy"].nunique() > 1 else np.nan
    r_hi, r_lo = pooled_r(hi), pooled_r(lo)
    obs = r_hi - r_lo
    # bootstrap: resample tickers within each group
    def boot_r(sub):
        ticks = sub.ticker.unique(); by = {t: g for t, g in sub.groupby("ticker")}
        s = pd.concat([by[t] for t in rng.choice(ticks, len(ticks), replace=True)])
        return pooled_r(s)
    diffs = []
    for _ in range(n):
        diffs.append(boot_r(hi) - boot_r(lo))
    diffs = np.array(diffs); diffs = diffs[~np.isnan(diffs)]
    # two-sided p: P(diff crosses 0)
    p = 2 * min((diffs > 0).mean(), (diffs < 0).mean()) if len(diffs) else np.nan
    return r_hi, r_lo, obs, p


def main():
    pk = json.load(open(DATA / "priorknowledge_all.json"))
    fund = json.load(open(DATA / "factset_fundamentals.json"))
    llm = pd.read_csv(LI / "llm_pred_company.csv")

    fund_vols = [v.get("margin_vol") for v in fund.values() if v.get("margin_vol") is not None]
    vol_med = float(np.median(fund_vols))

    log("# 회사 그룹화 검정 — 개별 대신 그룹 pooled 상관\n")
    log(f"Y={Y}. 각 기준으로 회사를 2그룹(hi/lo)으로 나눠 pooled X→Y 상관 비교.")
    log(f"차이의 유의성 = 회사단위 clustered-bootstrap (n=5000). margin_vol 중앙값={vol_med:.2f}\n")

    for ch in ["card", "foot"]:
        d = pd.read_csv(YS / f"panel_{ch}.csv").dropna(subset=["x_yoy", Y])
        log(f"## {ch}  ({len(d)} 이벤트 · {d.ticker.nunique()} 회사)\n")

        # 기준 1: LLM signal_strength (strong=hi, weak/moderate=lo)
        lm = llm[llm.channel == ch].set_index("ticker")["signal_strength"].to_dict()
        d["g_llm"] = d.ticker.map(lambda t: "hi" if lm.get(t) == "strong" else "lo")
        # 기준 2: traffic_relevant (foot에 특히 의미) / card는 card_dominant
        key = "traffic_relevant" if ch == "foot" else "card_dominant"
        d["g_prior"] = d.ticker.map(lambda t: "hi" if pk.get(t, {}).get(key) is True else "lo")
        # 기준 3: FactSet margin_vol (고변동성=hi = 서프라이즈 여지 큼)
        d["g_vol"] = d.ticker.map(lambda t: "hi" if (fund.get(t, {}).get("margin_vol") or 0) > vol_med else "lo")

        for gcol, name in [("g_llm", "LLM signal_strength (strong vs rest)"),
                           ("g_prior", f"사전지식 {key} (True vs False)"),
                           ("g_vol", "FactSet margin_vol (고 vs 저)")]:
            nhi = d[d[gcol] == "hi"].ticker.nunique(); nlo = d[d[gcol] == "lo"].ticker.nunique()
            if nhi < 3 or nlo < 3:
                log(f"### {name}: 그룹 불균형(hi {nhi}/lo {nlo}), skip"); continue
            r_hi, r_lo, diff, p = group_diff_boot(d, gcol)
            v = "✅ 유의" if (not np.isnan(p) and p < 0.05) else "유의하지 않음"
            log(f"### {name}")
            log(f"  hi그룹({nhi}사): r={r_hi:+.3f}   lo그룹({nlo}사): r={r_lo:+.3f}")
            log(f"  차이 Δ={diff:+.3f}  bootstrap p={p:.3f}  → **{v}**\n")
            rec.append({"channel": ch, "grouping": name, "r_hi": round(r_hi, 3),
                        "r_lo": round(r_lo, 3), "diff": round(diff, 3),
                        "p": round(p, 4) if not np.isnan(p) else None,
                        "significant": bool((not np.isnan(p)) and p < 0.05)})

    pd.DataFrame(rec).to_csv(OUT / "group_test.csv", index=False)
    (OUT / "group_test.md").write_text("\n".join(md))
    log("## 요약")
    sig = [r for r in rec if r["significant"]]
    if sig:
        for r in sig:
            log(f"  ✅ {r['channel']} — {r['grouping']}: hi r={r['r_hi']} vs lo r={r['r_lo']} (p={r['p']})")
    else:
        log("  어떤 그룹화도 유의한 신호차를 못 만듦")
    print(f"\nsaved: group_test.csv, group_test.md")


if __name__ == "__main__":
    main()
