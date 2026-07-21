"""
검증 (Task 8) — LLM 식별 예측 vs 실제 실험결과.

두 축:
  (A) metric-fit: LLM의 Y-metric 랭킹 vs 실제 랭킹 (실제 = |r| 또는 pass).
      - Spearman rank correlation (LLM rank vs actual |r| rank), per channel
      - significance 예측 정확도: LLM will_be_significant vs actual pass → accuracy/precision/recall
  (B) company-fit: LLM의 회사 랭킹 vs 실제 per-company r.
      - Spearman(LLM rank vs actual r_company), per channel
      - top-k precision: LLM top-k 회사가 실제 상위와 얼마나 겹치나
      - strong/weak 예측 vs 실제 (r_company 중앙값 초과 여부) → AUC-lite

산출물: outputs/validation_metric.csv, validation_company.csv, validation_summary.json

Usage:  python li_03_validate.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
from li_config import OUT  # noqa: E402


def validate_metrics():
    llm = pd.read_csv(OUT / "llm_pred_metric.csv")
    # prefer the full 8Y×3ch grid; fall back to the 3-Y table
    full = OUT / "gt_channel_metric_full.csv"
    gt = pd.read_csv(full if full.exists() else OUT / "gt_channel_metric.csv")
    # drop under-covered combos (n<15): LLM predicted them, but we have no reliable ground truth,
    # so scoring the LLM against a null result would be unfair. Reported separately as 'uncovered'.
    if "note" in gt.columns:
        gt = gt[gt["r"].notna()].copy()
    # actual rank per channel by |r| (higher |r| = better)
    gt["abs_r"] = gt["r"].abs()
    rows, summary = [], []
    for ch in llm.channel.unique():
        l = llm[llm.channel == ch].copy()
        g = gt[gt.channel == ch].copy()
        m = l.merge(g[["y", "abs_r", "r", "pass"]], left_on="metric", right_on="y", how="inner")
        if len(m) < 3:
            continue
        m["actual_rank"] = m["abs_r"].rank(ascending=False)
        rho, p = stats.spearmanr(m["rank"], m["actual_rank"])
        # significance prediction accuracy
        tp = ((m.will_be_significant) & (m["pass"])).sum()
        fp = ((m.will_be_significant) & (~m["pass"])).sum()
        fn = ((~m.will_be_significant) & (m["pass"])).sum()
        tn = ((~m.will_be_significant) & (~m["pass"])).sum()
        acc = (tp + tn) / len(m)
        prec = tp / (tp + fp) if (tp + fp) else np.nan
        rec = tp / (tp + fn) if (tp + fn) else np.nan
        summary.append({"channel": ch, "rank_spearman": round(rho, 3), "rank_p": round(p, 3),
                        "sig_accuracy": round(acc, 3), "sig_precision": round(prec, 3) if not np.isnan(prec) else None,
                        "sig_recall": round(rec, 3) if not np.isnan(rec) else None,
                        "n_metrics": len(m), "tp": int(tp), "fp": int(fp), "fn": int(fn), "tn": int(tn)})
        m["channel"] = ch
        rows.append(m[["channel", "metric", "rank", "actual_rank", "will_be_significant", "pass", "r", "abs_r"]])
    detail = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    detail.to_csv(OUT / "validation_metric.csv", index=False)
    return pd.DataFrame(summary)


def validate_companies():
    llm = pd.read_csv(OUT / "llm_pred_company.csv")
    gt = pd.read_csv(OUT / "gt_channel_company.csv")
    rows, summary = [], []
    for ch in llm.channel.unique():
        l = llm[llm.channel == ch].copy()
        g = gt[gt.channel == ch].copy()
        m = l.merge(g[["ticker", "r_company", "n_company"]], on="ticker", how="inner")
        if len(m) < 5:
            continue
        m["actual_rank"] = m["r_company"].rank(ascending=False)
        rho, p = stats.spearmanr(m["rank"], m["actual_rank"])
        # top-k precision: LLM top-k vs actual top-k overlap
        k = max(3, len(m) // 4)
        llm_topk = set(m.nsmallest(k, "rank")["ticker"])
        act_topk = set(m.nlargest(k, "r_company")["ticker"])
        topk_prec = len(llm_topk & act_topk) / k
        # strong/weak classification vs actual (above-median r_company = truly strong)
        med = m["r_company"].median()
        m["pred_strong"] = m["signal_strength"].isin(["strong", "moderate"])
        m["actual_strong"] = m["r_company"] > med
        # AUC of LLM rank (as score) predicting actual_strong
        try:
            from sklearn.metrics import roc_auc_score
            auc = roc_auc_score(m["actual_strong"], -m["rank"])
        except Exception:
            auc = np.nan
        summary.append({"channel": ch, "rank_spearman": round(rho, 3), "rank_p": round(p, 3),
                        "topk": k, "topk_precision": round(topk_prec, 3),
                        "auc_strong": round(auc, 3) if not np.isnan(auc) else None, "n_companies": len(m)})
        m["channel"] = ch
        rows.append(m[["channel", "ticker", "rank", "actual_rank", "signal_strength",
                       "r_company", "n_company"]])
    detail = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    detail.to_csv(OUT / "validation_company.csv", index=False)
    return pd.DataFrame(summary)


def main():
    ms = validate_metrics()
    cs = validate_companies()
    print("=== METRIC-FIT: LLM predicted metric ranking vs actual ===")
    print(ms.to_string(index=False))
    print("\n=== COMPANY-FIT: LLM predicted company ranking vs actual per-company r ===")
    print(cs.to_string(index=False))
    json.dump({"metric_fit": ms.to_dict("records"), "company_fit": cs.to_dict("records")},
              open(OUT / "validation_summary.json", "w"), indent=2)
    print(f"\nsaved: validation_metric.csv, validation_company.csv, validation_summary.json")


if __name__ == "__main__":
    main()
