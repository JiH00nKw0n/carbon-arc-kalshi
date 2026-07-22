"""
Stage-1 LLM Identification (Task 7) — Notion 연구설계 1단계.

LLM(gpt-5.5)에게 각 채널에 대해 두 가지를 예측하게 한다 (실제 실험결과는 절대 안 줌 = blind):
  (A) metric-fit : 후보 Y metric 들을 그 alt-data가 잘 예측할 순서로 랭킹 + 각 metric이 유의(pass)할지 예측
  (B) company-fit: 회사 set 중 그 alt-data가 revenue surprise 를 잘 예측할 회사 랭킹 + 강신호 여부(strong/weak)

입력: alt-data 설명(li_config.CHANNELS) + Y metric 설명(Y_METRICS) + 회사 리스트(channel_entities.json).
출력: outputs/llm_pred_metric.csv, outputs/llm_pred_company.csv  (전부 캐시되어 재현가능)

Usage:  python li_02_llm_identify.py
"""
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from li_config import CHANNELS, Y_METRICS, DATA, OUT  # noqa: E402
from li_llm import call_json  # noqa: E402

SYSTEM = (
    "You are a quantitative equity researcher specializing in alternative data. You reason from "
    "first principles about WHICH alt-data signal predicts WHICH performance metric for WHICH "
    "company, based on the economic mechanism linking the data to revenue. You are given only "
    "descriptions — never the empirical results — and must predict what the data will show. "
    "Be decisive and rank; do not hedge into ties."
)

METRIC_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["ranking", "reasoning"],
    "properties": {
        "ranking": {
            "type": "array",
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["metric", "rank", "will_be_significant", "rationale"],
                "properties": {
                    "metric": {"type": "string"},
                    "rank": {"type": "integer"},
                    "will_be_significant": {"type": "boolean"},
                    "rationale": {"type": "string"},
                },
            },
        },
        "reasoning": {"type": "string"},
    },
}

COMPANY_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["ranking", "reasoning"],
    "properties": {
        "ranking": {
            "type": "array",
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["ticker", "rank", "signal_strength", "rationale"],
                "properties": {
                    "ticker": {"type": "string"},
                    "rank": {"type": "integer"},
                    "signal_strength": {"type": "string", "enum": ["strong", "moderate", "weak"]},
                    "rationale": {"type": "string"},
                },
            },
        },
        "reasoning": {"type": "string"},
    },
}


def predict_metrics(ch: str, meta: dict) -> pd.DataFrame:
    ylist = "\n".join(f"  - {k}: {v}" for k, v in Y_METRICS.items())
    user = (
        f"ALT-DATA CHANNEL: {ch} ({meta['dataset']})\n"
        f"Signal: {meta['signal']}\n"
        f"Description: {meta['description']}\n"
        f"X transform: {meta['x_transform']}\n\n"
        f"CANDIDATE Y METRICS (predict which this alt-data predicts best):\n{ylist}\n\n"
        "Task: rank ALL candidate Y metrics from most-predictable (rank 1) to least, for THIS "
        "alt-data channel. For each, predict will_be_significant (true if you expect a statistically "
        "significant positive predictive relationship). Reason from the economic mechanism: does this "
        "signal carry information the consensus does NOT already have, for this metric?"
    )
    out = call_json(SYSTEM, user, METRIC_SCHEMA, tag=f"metric_{ch}")
    df = pd.DataFrame(out["ranking"])
    df.insert(0, "channel", ch)
    return df, out["reasoning"]


def predict_companies(ch: str, meta: dict, tickers: list[str]) -> pd.DataFrame:
    user = (
        f"ALT-DATA CHANNEL: {ch} ({meta['dataset']})\n"
        f"Signal: {meta['signal']}\n"
        f"Description: {meta['description']}\n\n"
        f"COMPANY SET ({len(tickers)} US tickers):\n{', '.join(tickers)}\n\n"
        "Task: rank these companies from strongest (rank 1) to weakest by how well THIS alt-data "
        "will predict their REVENUE SURPRISE (actual vs analyst consensus). Assign signal_strength "
        "(strong/moderate/weak). Reason from business model: for which companies is this data a "
        "dominant, consensus-missed revenue driver, vs. a weak/redundant one? Rank EVERY ticker."
    )
    out = call_json(SYSTEM, user, COMPANY_SCHEMA, tag=f"company_{ch}")
    df = pd.DataFrame(out["ranking"])
    df.insert(0, "channel", ch)
    return df, out["reasoning"]


def main():
    ents = json.load(open(DATA / "channel_entities.json"))
    metric_frames, company_frames, notes = [], [], []
    for ch, meta in CHANNELS.items():
        print(f"[{ch}] predicting metric ranking...")
        mdf, mreason = predict_metrics(ch, meta)
        metric_frames.append(mdf)
        print(f"[{ch}] predicting company ranking ({ents[ch]['n']} tickers)...")
        cdf, creason = predict_companies(ch, meta, ents[ch]["tickers"])
        company_frames.append(cdf)
        notes.append({"channel": ch, "metric_reasoning": mreason, "company_reasoning": creason})

    pd.concat(metric_frames, ignore_index=True).to_csv(OUT / "llm_pred_metric.csv", index=False)
    pd.concat(company_frames, ignore_index=True).to_csv(OUT / "llm_pred_company.csv", index=False)
    json.dump(notes, open(OUT / "llm_reasoning.json", "w"), indent=2, ensure_ascii=False)

    print("\n=== LLM metric predictions ===")
    print(pd.concat(metric_frames)[["channel", "metric", "rank", "will_be_significant"]].to_string(index=False))
    print(f"\nsaved: {OUT/'llm_pred_metric.csv'}, {OUT/'llm_pred_company.csv'}, {OUT/'llm_reasoning.json'}")


if __name__ == "__main__":
    main()
