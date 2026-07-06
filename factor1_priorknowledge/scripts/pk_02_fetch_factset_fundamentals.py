"""
FactSet OAuth로 회사 재무 사전지식 수집 — WebSearch 정성지식 보강용 정량 지표.

MCP(linq-local) 미연결이라 FactSet REST를 OAuth로 직접 호출 (ys_00_fetch_factset.get_token 재사용).

수집 (분기 QTR, 2022~2025):
  FF_SALES        매출 (규모)
  FF_OPER_MGN     영업마진 (%)
  FF_NET_MGN      순마진 (%)
  FF_ASSET_TURN   자산회전율

파생 사전지식:
  sales_usd_m     최근 매출 규모
  oper_margin     최근 영업마진
  margin_vol      영업마진 표준편차 (실적 예측난이도 프록시 — 마진 변동 크면 서프라이즈 여지 큼)
  sales_growth_vol 분기 매출 YoY 성장률 표준편차 (수요 변동성 — alt-data가 잡을 여지)

OUT: data/factset_fundamentals.json  {ticker: {sales_usd_m, oper_margin, margin_vol, sales_growth_vol}}

Usage:  python pk_02_fetch_factset_fundamentals.py
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pk_config import DATA  # noqa: E402

# reuse OAuth token from yswitch fetcher
YS = Path(__file__).resolve().parents[2] / "factor1_yswitch" / "scripts"
sys.path.insert(0, str(YS))
import ys_00_fetch_factset as F  # noqa: E402

METRICS = "FF_SALES,FF_OPER_MGN,FF_NET_MGN,FF_ASSET_TURN"


def fetch_batch(token, ids):
    h = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    params = {"ids": ",".join(ids), "metrics": METRICS, "periodicity": "QTR",
              "fiscalPeriodStart": "2022-01-01", "fiscalPeriodEnd": "2025-12-31"}
    r = requests.get("https://api.factset.com/content/factset-fundamentals/v2/fundamentals",
                     params=params, headers=h, timeout=60)
    if not r.ok:
        print(f"  batch error {r.status_code}: {r.text[:150]}")
        return []
    return r.json().get("data", [])


def main():
    uni = json.load(open(DATA / "universe.json"))
    tickers = sorted(uni.keys())
    ids = [f"{t}-US" for t in tickers]
    token = F.get_token()
    print(f"FactSet fundamentals — {len(tickers)} 회사")

    raw = []
    for i in range(0, len(ids), 20):
        raw += fetch_batch(token, ids[i:i + 20])
        time.sleep(0.3)
    print(f"raw rows: {len(raw)}")

    df = pd.DataFrame(raw)
    if df.empty:
        print("no data"); return
    df["ticker"] = df["requestId"].str.replace("-US", "", regex=False)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    # fiscalEndDate may be under different key
    date_col = "fiscalEndDate" if "fiscalEndDate" in df.columns else (
        "date" if "date" in df.columns else None)

    out = {}
    for t, g in df.groupby("ticker"):
        piv = g.pivot_table(index=g.get(date_col) if date_col else g.index,
                            columns="metric", values="value", aggfunc="last")
        rec = {}
        if "FF_SALES" in piv:
            s = piv["FF_SALES"].dropna()
            rec["sales_usd_m"] = round(float(s.iloc[-1]), 0) if len(s) else None
            # YoY growth vol (need >=5 quarters)
            if len(s) >= 6:
                yoy = s.pct_change(4).dropna()
                rec["sales_growth_vol"] = round(float(yoy.std()), 3) if len(yoy) else None
            else:
                rec["sales_growth_vol"] = None
        if "FF_OPER_MGN" in piv:
            m = piv["FF_OPER_MGN"].dropna()
            rec["oper_margin"] = round(float(m.iloc[-1]), 1) if len(m) else None
            rec["margin_vol"] = round(float(m.std()), 2) if len(m) >= 4 else None
        out[t] = rec

    json.dump(out, open(DATA / "factset_fundamentals.json", "w"), indent=2)
    got = sum(1 for v in out.values() if v.get("sales_usd_m"))
    print(f"saved: factset_fundamentals.json — {got}/{len(tickers)} 회사 매출 확보")
    # sample
    for t in ["ULTA", "AMZN", "SG", "BJ", "WING"]:
        if t in out:
            print(f"  {t}: {out[t]}")


if __name__ == "__main__":
    main()
