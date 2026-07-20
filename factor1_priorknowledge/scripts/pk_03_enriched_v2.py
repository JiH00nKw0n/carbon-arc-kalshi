"""
사전지식 v2 — WebSearch(정성) + FactSet(정량) 결합. 특히 마진변동성·매출성장변동성 추가.

가설: v1(WebSearch만)은 card에서 오히려 나빴다. FactSet의 '실적 예측난이도' 지표(margin_vol,
sales_growth_vol)를 추가하면 "어느 회사에서 서프라이즈가 클지"(=alt-data 신호 여지)를 더 잘 판별할 것.

baseline vs enriched_v2 비교 (v1 baseline은 pk_01에서 이미 캐시됨 — 재사용).

OUT: outputs/pk_v2_compare.csv + pk_v2_compare.md

Usage:  python pk_03_enriched_v2.py
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
from li_llm import call_json  # noqa: E402
from li_config import CHANNELS  # noqa: E402
import pk_01_llm_compare as V1  # reuse SYSTEM, SCHEMA, CH_KEY, load_prior, evaluate  # noqa: E402


def load_fundamentals():
    f = DATA / "factset_fundamentals.json"
    return json.load(open(f)) if f.exists() else {}


def prior_line_v2(t, pk, fund):
    d = pk.get(t, {})
    fd = fund.get(t, {})
    parts = [f"  {t}: {d.get('business_model','?')}"]
    if d.get("digital_pct") is not None:
        parts.append(f"digital≈{d.get('digital_pct')}%")
    parts.append(f"card_dominant={d.get('card_dominant')}")
    parts.append(f"traffic_relevant={d.get('traffic_relevant')}")
    # FactSet 정량 (핵심: 실적 예측난이도)
    if fd.get("sales_usd_m") is not None:
        parts.append(f"qtr_sales≈${fd['sales_usd_m']:.0f}M")
    if fd.get("oper_margin") is not None:
        parts.append(f"op_margin={fd['oper_margin']}%")
    if fd.get("margin_vol") is not None:
        parts.append(f"margin_volatility={fd['margin_vol']}")
    if fd.get("sales_growth_vol") is not None:
        parts.append(f"sales_growth_volatility={fd['sales_growth_vol']}")
    line = "; ".join(parts)
    if d.get("notes"):
        line += f". {d['notes']}"
    return line


def predict_v2(ch, tickers, pk, fund):
    meta = CHANNELS[V1.CH_KEY[ch]]
    body = (f"ALT-DATA: {ch} ({meta['dataset']})\nSignal: {meta['signal']}\n"
            f"Description: {meta['description']}\n\n"
            "COMPANY PRIOR KNOWLEDGE. Fields: business model; digital revenue %; whether card-spend / "
            "foot-traffic is a meaningful revenue driver; quarterly sales size; operating margin; "
            "margin_volatility (std of operating margin) and sales_growth_volatility (std of YoY sales "
            "growth) — HIGHER volatility means earnings are HARDER to forecast, so consensus misses more "
            "and there is MORE room for alt-data to predict revenue surprise. LOW-volatility, stable "
            "companies leave little surprise for any signal to capture.\n"
            + "\n".join(prior_line_v2(t, pk, fund) for t in tickers) + "\n\n"
            "Rank these companies from strongest (rank 1) to weakest by how well THIS alt-data predicts "
            "their revenue surprise. Consider BOTH channel-fit (is the signal relevant to this business) "
            "AND surprise-room (does this company have volatile, hard-to-forecast results). "
            "Assign signal_strength. Rank EVERY ticker.")
    out = call_json(V1.SYSTEM, body, V1.SCHEMA, tag=f"enrichedv2_{ch}")
    df = pd.DataFrame(out["ranking"]); df["channel"] = ch
    return df


def main():
    pk = V1.load_prior()
    fund = load_fundamentals()
    print(f"prior: {len(pk)} 회사, fundamentals: {len(fund)} 회사")
    gt = pd.read_csv(GT_COMPANY)
    uni = json.load(open(DATA / "universe.json"))

    rows = []
    for ch in ["card", "foot", "web"]:
        tickers = sorted([t for t, chans in uni.items() if ch in chans])
        # baseline (reuse pk_01 cache) + enriched_v2
        base = V1.predict(ch, tickers, pk, enriched=False)   # cached from pk_01
        ev_b = V1.evaluate(base, gt, ch)
        pred = predict_v2(ch, tickers, pk, fund)
        pred.to_csv(OUT / f"pk_v2_pred_{ch}.csv", index=False)
        ev_e = V1.evaluate(pred, gt, ch)
        if ev_b and ev_e:
            rows.append({"channel": ch, "cond": "baseline", **ev_b})
            rows.append({"channel": ch, "cond": "enriched_v2", **ev_e})
            print(f"  {ch} baseline:    Spearman={ev_b['rank_spearman']} topk={ev_b['topk_precision']} AUC={ev_b['auc']}")
            print(f"  {ch} enriched_v2: Spearman={ev_e['rank_spearman']} topk={ev_e['topk_precision']} AUC={ev_e['auc']}")

    cmp = pd.DataFrame(rows)
    cmp.to_csv(OUT / "pk_v2_compare.csv", index=False)
    md = ["# 사전지식 v2 (WebSearch + FactSet 변동성) — company-fit\n",
          "baseline=티커+채널설명. enriched_v2=+사업모델+디지털비중+FactSet(매출·마진·마진변동성·매출성장변동성).\n",
          "| channel | metric | baseline | enriched_v2 | Δ |", "|---|---|---|---|---|"]
    for ch in ["card", "foot", "web"]:
        b = cmp[(cmp.channel == ch) & (cmp.cond == "baseline")]
        e = cmp[(cmp.channel == ch) & (cmp.cond == "enriched_v2")]
        if b.empty or e.empty:
            continue
        for met in ["rank_spearman", "topk_precision", "auc"]:
            bv, ev = b[met].iloc[0], e[met].iloc[0]
            if bv is None or ev is None:
                continue
            d = ev - bv
            arrow = "↑" if d > 0.02 else ("↓" if d < -0.02 else "→")
            md.append(f"| {ch} | {met} | {bv:+.3f} | {ev:+.3f} | {d:+.3f} {arrow} |")
    (OUT / "pk_v2_compare.md").write_text("\n".join(md))
    print("\n" + "\n".join(md))


if __name__ == "__main__":
    main()
