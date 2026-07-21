"""
입력 카탈로그 구축 (Task 5) — 재현가능한 결정적 입력.

산출물:
  data/channel_entities.json   채널별 (card/foot/click) 확보 entity/ticker list + 기간
  data/factset_metric_catalog.json  FactSet Estimates metric 전체 카탈로그 + 우리 유니버스 커버리지

FactSet metrics 엔드포인트는 1회 호출 후 캐시(cache/factset_metrics_raw.json). 커버리지(각 metric에
컨센서스 있는 우리 티커 수)는 비용이 커서 li_config.Y_METRICS 후보에 한해서만 프로브.

Usage:  python li_00_build_inputs.py
"""
import json
import sys
import time
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
from li_config import DATA, CACHE, LINQ_ENV, YSROOT  # noqa: E402

load_dotenv(LINQ_ENV)
# reuse the FactSet OAuth from the yswitch fetcher
sys.path.insert(0, str(YSROOT / "scripts"))
import ys_00_fetch_factset as F  # noqa: E402
from ys_config import CARD_CSV, FOOT_CSVS, CLICK_CSV, CLICK_NAME2TKR  # noqa: E402


def channel_entities() -> dict:
    def span(df):
        d = pd.to_datetime(df["date"])
        return f"{d.min().date()}..{d.max().date()}"

    card = pd.read_csv(CARD_CSV)
    foot = pd.concat([pd.read_csv(p) for p in FOOT_CSVS], ignore_index=True)
    click = pd.read_csv(CLICK_CSV)
    click_tk = sorted({CLICK_NAME2TKR.get(n) for n in click["entity_name"].unique()} - {None})
    return {
        "card":  {"tickers": sorted(card["entity_name"].unique().tolist()),
                  "n": card["entity_name"].nunique(), "span": span(card), "freq": "quarterly"},
        "foot":  {"tickers": sorted(foot["entity_name"].unique().tolist()),
                  "n": foot["entity_name"].nunique(), "span": span(foot), "freq": "monthly"},
        "click": {"tickers": click_tk, "n": len(click_tk), "span": span(click), "freq": "monthly"},
    }


def factset_catalog(token: str, universe_ids: list[str]) -> dict:
    hdrs = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    raw_cache = CACHE / "factset_metrics_raw.json"
    if raw_cache.exists():
        metrics = json.load(open(raw_cache))
    else:
        metrics = []
        for cat in ["INDUSTRY", "FINANCIAL_STATEMENT", "OTHER"]:
            r = requests.get("https://api.factset.com/content/factset-estimates/v2/metrics",
                             headers=hdrs, params={"category": cat}, timeout=30)
            if r.ok:
                metrics += r.json().get("data", [])
        # dedup by metric code
        seen, uniq = set(), []
        for m in metrics:
            k = m.get("metric")
            if k and k not in seen:
                seen.add(k); uniq.append({"metric": k, "name": m.get("name", ""),
                                          "category": m.get("category", "")})
        metrics = uniq
        json.dump(metrics, open(raw_cache, "w"), indent=2)
    return {"n_metrics": len(metrics), "metrics": metrics}


def main():
    print("building channel entities...")
    ents = channel_entities()
    json.dump(ents, open(DATA / "channel_entities.json", "w"), indent=2)
    for ch, v in ents.items():
        print(f"  {ch}: {v['n']} tickers ({v['freq']}, {v['span']})")

    print("\nbuilding FactSet metric catalog...")
    token = F.get_token()
    cat = factset_catalog(token, [])
    json.dump(cat, open(DATA / "factset_metric_catalog.json", "w"), indent=2)
    print(f"  {cat['n_metrics']} FactSet Estimates metrics catalogued")

    print(f"\nsaved: {DATA/'channel_entities.json'}, {DATA/'factset_metric_catalog.json'}")


if __name__ == "__main__":
    main()
