"""
LLM 시너지 판단 레이어 — OpenAI(gpt-5.5)가 '이 X 조합이 시너지 날까'를 blind로 판단.

두 레벨 (실제 결과는 절대 안 줌):
  (A) 조합 수준: "card+foot 결합이 각각 단독보다 revenue surprise를 더 잘 예측할까?"
      → synergy_likely (예/아니오) + confidence + 이유
  (B) 회사 수준: 조합의 공통 커버 회사 중 "결합 시너지가 날 회사"를 고르게
      → per-ticker synergy_likely + 이유

그다음 cb_04에서 실제(gt_synergy_*.csv)와 대조: LLM이 시너지를 맞혔나?

기존 li_llm.py(OpenAI 캐싱+JSON schema) 재사용 — 새 코드 최소.

OUT: outputs/llm_synergy_combo.csv, llm_synergy_company.csv

Usage:  python cb_03_llm_synergy.py
"""
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cb_config import COMBOS, OUT, ROOT  # noqa: E402

# reuse OpenAI wrapper + channel descriptions from llm_identify
LI = ROOT.parent / "factor1_yswitch" / "llm_identify" / "scripts"
sys.path.insert(0, str(LI))
from li_llm import call_json  # noqa: E402
from li_config import CHANNELS  # noqa: E402

SYSTEM = (
    "You are a quantitative alt-data researcher. You reason from first principles about whether "
    "COMBINING two alternative-data signals improves prediction of a company's revenue surprise "
    "beyond either signal alone. Synergy happens when the two signals carry DIFFERENT, complementary "
    "information (e.g. one captures dollar spend, the other online intent). Redundant or noisy "
    "combinations do NOT help — averaging a strong signal with a weak/irrelevant one dilutes it. "
    "You are given only descriptions and a company list — never the empirical results. Be decisive."
)

COMBO_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["synergy_likely", "confidence", "rationale"],
    "properties": {
        "synergy_likely": {"type": "boolean"},
        "confidence": {"type": "integer"},
        "rationale": {"type": "string"},
    },
}

COMPANY_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["picks", "reasoning"],
    "properties": {
        "picks": {
            "type": "array",
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["ticker", "synergy_likely", "rationale"],
                "properties": {
                    "ticker": {"type": "string"},
                    "synergy_likely": {"type": "boolean"},
                    "rationale": {"type": "string"},
                },
            },
        },
        "reasoning": {"type": "string"},
    },
}


# combo uses "web"; li_config.CHANNELS keys it as "click"
CH_KEY = {"card": "card", "foot": "foot", "web": "click"}


def combo_desc(chans):
    return "\n".join(f"- {ch} ({CHANNELS[CH_KEY[ch]]['dataset']}): {CHANNELS[CH_KEY[ch]]['description']}"
                     for ch in chans)


def predict_combo(name, chans):
    user = (
        f"CANDIDATE COMBINATION: {name}  (combine these alt-data signals)\n{combo_desc(chans)}\n\n"
        f"Target Y = revenue surprise (actual vs analyst consensus).\n"
        f"Each signal is standardized (z-score) and averaged into one combined signal.\n\n"
        f"Question: will the COMBINED signal predict revenue surprise BETTER than the single best "
        f"individual signal? Consider whether these channels carry complementary vs redundant/noisy "
        f"information for revenue-surprise prediction. Give synergy_likely (true/false), confidence "
        f"1-10, and rationale."
    )
    return call_json(SYSTEM, user, COMBO_SCHEMA, tag=f"combo_{name.replace('+','_')}")


def predict_company(name, chans, tickers):
    user = (
        f"COMBINATION: {name}\n{combo_desc(chans)}\n\n"
        f"COMPANY SET ({len(tickers)}): {', '.join(tickers)}\n\n"
        f"For EACH company, predict whether combining these signals will show SYNERGY — i.e. the "
        f"combined signal predicts that company's revenue surprise better than either signal alone. "
        f"Synergy needs both channels to carry real, complementary information FOR THAT COMPANY "
        f"(e.g. both card AND foot traffic are meaningful revenue drivers). If one channel is "
        f"irrelevant for a company, combining only dilutes → no synergy. Mark synergy_likely per ticker."
    )
    return call_json(SYSTEM, user, COMPANY_SCHEMA, tag=f"synco_{name.replace('+','_')}")


def main():
    combo_rows, comp_rows = [], []
    pairs = {k: v for k, v in COMBOS.items() if len(v) >= 2}
    cov = pd.read_csv(OUT / "combo_coverage.csv")
    ok = set(cov[cov.status == "OK"].combo)

    for name, chans in pairs.items():
        if name not in ok:
            print(f"[{name}] skip (n부족)"); continue
        panel = pd.read_csv(OUT / f"panel_{name.replace('+','_')}.csv")
        tickers = sorted(panel.ticker.unique())

        print(f"[{name}] LLM 조합 시너지 판단...")
        c = predict_combo(name, chans)
        combo_rows.append({"combo": name, "synergy_likely": c["synergy_likely"],
                           "confidence": c["confidence"], "rationale": c["rationale"]})

        print(f"[{name}] LLM 회사별 시너지 판단 ({len(tickers)}개)...")
        co = predict_company(name, chans, tickers)
        for p in co["picks"]:
            comp_rows.append({"combo": name, "ticker": p["ticker"],
                              "synergy_likely": p["synergy_likely"], "rationale": p["rationale"]})

    pd.DataFrame(combo_rows).to_csv(OUT / "llm_synergy_combo.csv", index=False)
    pd.DataFrame(comp_rows).to_csv(OUT / "llm_synergy_company.csv", index=False)
    print("\n=== LLM 조합 시너지 예측 ===")
    print(pd.DataFrame(combo_rows)[["combo", "synergy_likely", "confidence"]].to_string(index=False))
    print(f"\nsaved: llm_synergy_combo.csv, llm_synergy_company.csv")


if __name__ == "__main__":
    main()
