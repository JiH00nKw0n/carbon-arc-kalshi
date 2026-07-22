"""
SSS (Same-Store-Sales) surprise 수집 — foot traffic 채널의 "정답 Y" 후보.

풋트래픽은 방문(수량) 신호라 총매출(신규출점 섞임)보다 동일점포매출(comps)과 개념적으로 1:1.
FactSet Estimates metric SAMESTORESALES 로 /surprise 호출 → SSS actual + consensus.

주의: SSS는 이미 % (YoY comps growth) 이므로 surprise 정의가 매출과 다르다:
  sss_surprise = ACTUAL_sss(%) − CONS_sss(%)   (단순 차이, 분모 정규화 불필요; 둘 다 % 단위)

OUT: data/factset_sss_pit.json {"rows":[{ticker,FE_FP_END,REPORT_DATE,SSS_ACTUAL,SSS_CONS}]}

Usage:  python ys_04_fetch_sss.py
"""
import json
import sys
import time
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ys_00_fetch_factset as F  # reuse get_token / config
from ys_config import DATA, FOOT_CSVS  # noqa: E402

METRIC = "SAMESTORESALES"
START_DATE = "2022-01-01"
END_DATE   = "2026-07-01"


def foot_tickers() -> list[str]:
    tk = set()
    for f in FOOT_CSVS:
        tk |= set(pd.read_csv(f)["entity_name"].unique())
    return sorted(tk)


def main():
    tickers = foot_tickers()
    fs_ids = [f"{t}-US" for t in tickers]
    print(f"SSS fetch — {len(tickers)} foot tickers, metric={METRIC}")
    token = F.get_token()
    print("OAuth OK")

    hdrs = {"Authorization": f"Bearer {token}", "Accept": "application/json",
            "Content-Type": "application/json"}
    raw = []
    for i in range(0, len(fs_ids), 25):
        chunk = fs_ids[i:i + 25]
        r = requests.post(
            "https://api.factset.com/content/factset-estimates/v2/surprise",
            json={"ids": chunk, "metrics": [METRIC], "periodicity": "QTR",
                  "startDate": START_DATE, "endDate": END_DATE, "statistic": "MEAN"},
            headers=hdrs, timeout=45)
        if not r.ok:
            print(f"  chunk {i//25} error {r.status_code}: {r.text[:160]}")
            continue
        raw += r.json().get("data", [])
        time.sleep(0.3)
    print(f"raw SSS surprise rows: {len(raw)}")

    rows = []
    for it in raw:
        ticker = it["requestId"].replace("-US", "")
        actual = it.get("surpriseAfter")     # actual SSS (%)
        cons   = it.get("surpriseBefore")    # consensus SSS (%)
        date   = it.get("fiscalEndDate")
        report = it.get("surpriseDate")
        if actual is None or cons is None or date is None:
            continue
        rows.append({"ticker": ticker, "FE_FP_END": date, "REPORT_DATE": report,
                     "SSS_ACTUAL": actual, "SSS_CONS": cons})

    df = pd.DataFrame(rows).drop_duplicates(["ticker", "FE_FP_END"], keep="last")
    df = df.sort_values(["ticker", "FE_FP_END"])
    with open(DATA / "factset_sss_pit.json", "w") as f:
        json.dump({"rows": df.to_dict(orient="records")}, f, indent=2)

    print(f"saved: {DATA/'factset_sss_pit.json'}")
    print(f"coverage: {df.ticker.nunique()} tickers with SSS, {len(df)} qtr-rows")
    have = sorted(df.ticker.unique())
    print(f"tickers WITH SSS: {have}")
    print(f"tickers WITHOUT SSS: {sorted(set(tickers)-set(have))}")


if __name__ == "__main__":
    main()
