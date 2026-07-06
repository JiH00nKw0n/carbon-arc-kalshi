"""
사전지식 주입 효과 실험 — baseline vs enriched company-fit.

각 채널(card/foot/web)에 대해 LLM에게 "이 alt-data가 revenue surprise를 잘 예측할 회사"를
랭킹시키되 두 조건으로:
  (A) baseline : 티커 + 채널설명만 (기존 li_02와 동일)
  (B) enriched : + 회사별 사전지식(사업모델·디지털비중·card_dominant·traffic_relevant)

두 랭킹을 실제 per-company r(gt_channel_company.csv)과 대조 → AUC/top-k/Spearman이
enriched에서 개선되는가?

기존 li_llm.call_json(OpenAI+캐싱) 재사용.

OUT: outputs/pk_pred_<cond>_<channel>.csv, pk_compare.csv, pk_compare.md

Usage:  python pk_01_llm_compare.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pk_config import DATA, OUT, GT_COMPANY, LI_SCRIPTS  # noqa: E402

sys.path.insert(0, str(LI_SCRIPTS))
from li_llm import call_json  # noqa: E402  (OpenAI + cache)
from li_config import CHANNELS  # noqa: E402

CH_KEY = {"card": "card", "foot": "foot", "web": "click"}

SYSTEM = (
    "You are a quantitative equity researcher specializing in alternative data. For a given "
    "alt-data signal, you rank companies by how well that signal predicts their quarterly revenue "
    "surprise vs consensus. Reason from the economic mechanism linking the data to revenue. "
    "Rank every ticker; be decisive."
)

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["ranking"],
    "properties": {
        "ranking": {
            "type": "array",
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["ticker", "rank", "signal_strength"],
                "properties": {
                    "ticker": {"type": "string"},
                    "rank": {"type": "integer"},
                    "signal_strength": {"type": "string", "enum": ["strong", "moderate", "weak"]},
                },
            },
        },
    },
}


def load_prior():
    pk = {}
    for f in sorted(DATA.glob("priorknowledge_batch_*.json")):
        pk.update(json.load(open(f)))
    return pk


def prior_line(t, pk):
    d = pk.get(t)
    if not d:
        return f"  {t}: (no data)"
    return (f"  {t}: {d.get('business_model','?')}; "
            f"digital≈{d.get('digital_pct')}% instore≈{d.get('instore_pct')}%; "
            f"card_dominant={d.get('card_dominant')}; traffic_relevant={d.get('traffic_relevant')}. "
            f"{d.get('notes','')}")


def predict(ch, tickers, pk, enriched):
    meta = CHANNELS[CH_KEY[ch]]
    body = (f"ALT-DATA: {ch} ({meta['dataset']})\nSignal: {meta['signal']}\n"
            f"Description: {meta['description']}\n\n")
    if enriched:
        body += ("COMPANY PRIOR KNOWLEDGE (business model, digital vs in-store mix, whether card "
                 "spend / foot traffic is a meaningful revenue driver):\n"
                 + "\n".join(prior_line(t, pk) for t in tickers) + "\n\n")
    else:
        body += f"COMPANY SET: {', '.join(tickers)}\n\n"
    body += ("Rank these companies from strongest (rank 1) to weakest by how well THIS alt-data "
             "predicts their revenue surprise. Assign signal_strength. Rank EVERY ticker.")
    tag = f"{'enriched' if enriched else 'baseline'}_{ch}"
    out = call_json(SYSTEM, body, SCHEMA, tag=tag)
    df = pd.DataFrame(out["ranking"]); df["channel"] = ch
    df["cond"] = "enriched" if enriched else "baseline"
    return df


def evaluate(pred, gt, ch):
    g = gt[gt.channel == ch][["ticker", "r_company"]]
    m = pred.merge(g, on="ticker", how="inner")
    if len(m) < 5:
        return None
    m["actual_rank"] = m["r_company"].rank(ascending=False)
    rho, _ = stats.spearmanr(m["rank"], m["actual_rank"])
    k = max(3, len(m) // 4)
    topk = len(set(m.nsmallest(k, "rank").ticker) & set(m.nlargest(k, "r_company").ticker)) / k
    med = m["r_company"].median()
    try:
        from sklearn.metrics import roc_auc_score
        auc = roc_auc_score(m["r_company"] > med, -m["rank"])
    except Exception:
        auc = np.nan
    return {"n": len(m), "rank_spearman": round(rho, 3), "topk_precision": round(topk, 3),
            "auc": round(auc, 3) if not np.isnan(auc) else None}


def main():
    pk = load_prior()
    print(f"prior knowledge: {len(pk)} 회사 로드")
    gt = pd.read_csv(GT_COMPANY)
    uni = json.load(open(DATA / "universe.json"))

    rows = []
    for ch in ["card", "foot", "web"]:
        tickers = sorted([t for t, chans in uni.items() if ch in chans])
        for enriched in [False, True]:
            pred = predict(ch, tickers, pk, enriched)
            pred.to_csv(OUT / f"pk_pred_{'enriched' if enriched else 'baseline'}_{ch}.csv", index=False)
            ev = evaluate(pred, gt, ch)
            if ev:
                rows.append({"channel": ch, "cond": "enriched" if enriched else "baseline", **ev})
                print(f"  {ch} {'enriched' if enriched else 'baseline'}: "
                      f"Spearman={ev['rank_spearman']} topk={ev['topk_precision']} AUC={ev['auc']}")

    cmp = pd.DataFrame(rows)
    cmp.to_csv(OUT / "pk_compare.csv", index=False)

    # delta table
    md = ["# 사전지식 주입 효과 — company-fit baseline vs enriched\n",
          "각 채널에서 LLM이 '신호 강한 회사'를 랭킹. baseline=티커+채널설명만, "
          "enriched=+회사별 사전지식(사업모델·디지털비중·card/traffic 적합성). 실제 per-company r과 대조.\n",
          "| channel | metric | baseline | enriched | Δ |", "|---|---|---|---|---|"]
    for ch in ["card", "foot", "web"]:
        b = cmp[(cmp.channel == ch) & (cmp.cond == "baseline")]
        e = cmp[(cmp.channel == ch) & (cmp.cond == "enriched")]
        if b.empty or e.empty:
            continue
        for met in ["rank_spearman", "topk_precision", "auc"]:
            bv, ev = b[met].iloc[0], e[met].iloc[0]
            if bv is None or ev is None:
                continue
            d = ev - bv
            arrow = "↑" if d > 0.02 else ("↓" if d < -0.02 else "→")
            md.append(f"| {ch} | {met} | {bv:+.3f} | {ev:+.3f} | {d:+.3f} {arrow} |")
    (OUT / "pk_compare.md").write_text("\n".join(md))
    print("\n" + "\n".join(md))
    print(f"\nsaved: pk_compare.csv, pk_compare.md")


if __name__ == "__main__":
    main()
