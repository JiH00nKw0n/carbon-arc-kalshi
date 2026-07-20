"""
LLM Identification 실험 config — Notion 연구설계의 2단계 방법론 중 '1단계(Identification)'를
재현가능한 코드로 구현하기 위한 상수/경로/채널설명.

연구 설계 (Notion, wecoverai 2026-06-29):
  X = alt-data (card/foot/click),  Z = earnings transcript,  Y = firm performance vs consensus.
  1단계 Identification: alt-data 설명 + 회사 set 을 LLM에게 주고, 그 alt-data가 Y를 잘 예측할
    회사(+유용한 Y metric)를 고르게 한다. → 실제 실험결과와 비교해 LLM 식별 정확도 측정.
"""
from pathlib import Path

ROOT   = Path(__file__).resolve().parents[1]          # llm_identify/
YSROOT = ROOT.parent                                   # factor1_yswitch/
DATA   = ROOT / "data"
OUT    = ROOT / "outputs"
CACHE  = ROOT / "cache"
for d in (DATA, OUT, CACHE):
    d.mkdir(parents=True, exist_ok=True)

REPO_ROOT   = YSROOT.parent                            # carbon-arc-kalshi/
LINQ_ENV    = REPO_ROOT.parent.parent / ".env"        # LinqAlpha/.env  (OpenAI + FactSet creds)

OPENAI_MODEL = "gpt-5.5"   # Notion 연구가 쓴 모델 계열

# --- 채널 정의 (사람이 쓴 설명 = LLM에게 주는 alt-data description) ---
CHANNELS = {
    "card": {
        "dataset": "Carbon Arc CA0056",
        "signal": "consumer credit/debit card spend (Online + Physical), aggregated per company, quarterly",
        "description": (
            "Card spend measures the DOLLAR AMOUNT consumers charge at a company. It captures "
            "ticket size, price, promotion and mix — not just how many people showed up. It is a "
            "direct revenue proxy for businesses where consumer cards are the dominant payment "
            "method (retail, restaurants, travel). It is weak/irrelevant for B2B, subscription/SaaS, "
            "wholesale, insurance-billed, or cash-heavy businesses."
        ),
        "x_transform": "YoY of quarterly card spend (pct_change 4Q)",
    },
    "foot": {
        "dataset": "Carbon Arc CA0060",
        "signal": "mobile-geolocation store foot traffic (visits), monthly, per company",
        "description": (
            "Foot traffic measures the NUMBER OF VISITS to physical locations. It is a VOLUME "
            "signal only — it carries no ticket size, price, or mix. Visits track revenue for "
            "in-store-dominant retail/F&B, but analysts can also observe crowds, so consensus often "
            "already prices it in. It is weak for e-commerce, and for companies where average ticket, "
            "new-store openings, promotions or product mix drive revenue independently of visit counts."
        ),
        "x_transform": "monthly foot traffic YoY (pct_change 12M), aligned to fiscal-quarter-end",
    },
    "click": {
        "dataset": "Carbon Arc CA0030",
        "signal": "website visitors / clickstream (Mobile + Desktop), monthly, per company",
        "description": (
            "Web traffic measures ONLINE VISITORS to a company's site. For e-commerce and online "
            "marketplaces, a visit is close to purchase intent, so it can carry information that "
            "consensus misses (leading signal). It is weak for offline-dominant retail, and noisy "
            "for high-growth names where visitor counts swing far more than revenue."
        ),
        "x_transform": "monthly web visitors YoY (pct_change 12M), aligned to fiscal-quarter-end",
    },
}

# --- Y metric universe: 후보 metric 설명 (LLM이 '어떤 Y가 유용한가' 예측할 대상) ---
Y_METRICS = {
    "rev_yoy":         "Revenue growth YoY (level, no consensus). Tests if X tracks the size of revenue.",
    "surprise_early":  "Revenue surprise vs point-in-time consensus = (actual - consensus)/consensus. THE alpha target.",
    "surprise_print":  "Revenue surprise vs print-time consensus.",
    "sss_surprise":    "Same-store-sales surprise = actual comps % - consensus comps %. Removes new-store noise.",
    "sss_level":       "Same-store-sales actual (%). Level of comps growth.",
    "SALES_RSF":       "Net sales per retail square foot (surprise vs consensus). Sales density.",
    "OCCUPY_RATE_TOT": "Hotel/casino occupancy rate surprise. Visit-to-stay proxy.",
    "GMV":             "Gross merchandise volume surprise. Total transaction value for marketplaces.",
}
