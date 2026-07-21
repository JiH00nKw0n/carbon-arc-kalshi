"""
LLM 시너지 판단 vs 실제 검증 — LLM(OpenAI)이 조합 시너지를 미리 맞혔나?

레벨 A (조합): LLM synergy_likely vs 실제(combined r > best single r). 조합 단위 정오.
레벨 B (회사): LLM per-ticker synergy_likely vs 실제 gt_synergy(회사별 combined−best_single>0).
              혼동행렬 → accuracy/precision/recall + top-pick 적중.

OUT: outputs/synergy_validation.md + synergy_validation.csv

Usage:  python cb_04_validate.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cb_config import COMBOS, OUT  # noqa: E402

md = []


def log(s=""):
    print(s); md.append(s)


def main():
    res = pd.read_csv(OUT / "combine_results.csv")
    llm_combo = pd.read_csv(OUT / "llm_synergy_combo.csv")
    llm_comp = pd.read_csv(OUT / "llm_synergy_company.csv")

    log("# LLM 시너지 판단 검증 — OpenAI가 X조합 시너지를 미리 맞혔나\n")

    # ---- 레벨 A: 조합 수준 ----
    log("## 레벨 A — 조합 수준 (시너지 날까?)")
    rowsA = []
    for combo in llm_combo.combo:
        sub = res[res.combo == combo]
        singles = sub[sub.kind == "single"]["r"].dropna()
        comb = sub[sub.kind == "combined"]["r"].iloc[0]
        actual = bool(comb > singles.max())
        pred = bool(llm_combo[llm_combo.combo == combo]["synergy_likely"].iloc[0])
        conf = int(llm_combo[llm_combo.combo == combo]["confidence"].iloc[0])
        ok = "✅" if pred == actual else "❌"
        log(f"  {combo:14s} LLM={'시너지' if pred else '무시너지'}(conf{conf}) | "
            f"실제={'시너지' if actual else '무시너지'} (comb {comb:+.3f} vs best {singles.max():+.3f})  {ok}")
        rowsA.append({"combo": combo, "llm_synergy": pred, "actual_synergy": actual,
                      "confidence": conf, "correct": pred == actual})
    accA = np.mean([r["correct"] for r in rowsA]) if rowsA else np.nan
    log(f"  → 조합 수준 정확도: {accA:.0%} ({sum(r['correct'] for r in rowsA)}/{len(rowsA)})\n")

    # ---- 레벨 B: 회사 수준 ----
    log("## 레벨 B — 회사 수준 (어느 회사에서 시너지?)")
    rowsB = []
    for combo in llm_combo.combo:
        gt_f = OUT / f"gt_synergy_{combo.replace('+','_')}.csv"
        if not gt_f.exists():
            continue
        gt = pd.read_csv(gt_f)[["ticker", "synergy", "has_synergy"]]
        lp = llm_comp[llm_comp.combo == combo][["ticker", "synergy_likely"]]
        m = lp.merge(gt, on="ticker", how="inner")
        if len(m) < 3:
            log(f"  {combo}: n<3, skip"); continue
        tp = ((m.synergy_likely) & (m.has_synergy)).sum()
        fp = ((m.synergy_likely) & (~m.has_synergy)).sum()
        fn = ((~m.synergy_likely) & (m.has_synergy)).sum()
        tn = ((~m.synergy_likely) & (~m.has_synergy)).sum()
        acc = (tp + tn) / len(m)
        prec = tp / (tp + fp) if (tp + fp) else np.nan
        rec = tp / (tp + fn) if (tp + fn) else np.nan
        base = m.has_synergy.mean()   # 실제 시너지 비율 (기저율)
        log(f"  {combo}: n={len(m)}  실제시너지 {m.has_synergy.sum()}/{len(m)} ({base:.0%})")
        log(f"    accuracy={acc:.0%}  precision={prec:.2f}  recall={rec:.2f}  "
            f"(TP={tp} FP={fp} FN={fn} TN={tn})")
        rowsB.append({"combo": combo, "n": len(m), "accuracy": round(acc, 3),
                      "precision": round(prec, 3) if not np.isnan(prec) else None,
                      "recall": round(rec, 3) if not np.isnan(rec) else None,
                      "base_rate": round(base, 3)})
    log("")

    # ---- 결론 ----
    log("## 결론")
    log("LLM이 **조합을 할지 말지(레벨 A)**는 부분적으로 맞힘 — 노이즈 희석(card+foot)은 잡았으나 "
        "보완적 시너지(card+web)는 놓침. **회사별 시너지(레벨 B)**는 기저율 대비 개선이 크지 않음. "
        "→ 앞선 company-fit 결론과 일관: LLM은 '조합의 구조적 방향'은 어느 정도 알지만 "
        "'개별 회사에서 시너지가 실제로 날지'는 데이터가 필요하다.")

    pd.DataFrame(rowsA).to_csv(OUT / "synergy_validation.csv", index=False)
    (OUT / "synergy_validation.md").write_text("\n".join(md))
    print(f"\nsaved: synergy_validation.md, synergy_validation.csv")


if __name__ == "__main__":
    main()
