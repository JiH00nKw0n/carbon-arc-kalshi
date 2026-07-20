"""
비매출(non-revenue) Y 탐색 — 매출/SSS는 전부 컨센서스 선반영 벽에 막혔다. 방문·거래·점유 같은
'운영 물량' 지표는 애널리스트가 매출만큼 정밀 추정하지 않아 alt-data가 surprise를 만들 여지가 크다.

검정 가능한 비매출 metric (우리 유니버스 커버리지 확인 완료):
  SALES_RSF        Net Sales per Retail Sq.Ft.  — foot 25종목. 방문 밀도=평당 트래픽=평당 매출 (foot의 물리적 정답)
  OCCUPY_RATE_TOT  Occupancy (%)                — card 9종목(호텔/카지노). 방문=투숙
  GMV              Gross Merchandise Volume     — click 5종목(AMZN/EBAY/REAL/BKNG/CART). 웹방문=거래

각 Y에 대해 해당 채널 X(foot/card/click)를 no-lookahead 정렬 후 검정.
Y_surprise = ACTUAL − CONS  (%/레벨 metric은 단순차이, 매출형은 정규화).

OUT: data/factset_nonrev_pit.json  +  outputs/nonrev_ytargets.md

Usage:  python ys_06_nonrev_ytargets.py
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "factor1" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ys_00_fetch_factset as F  # noqa: E402
from f1_stats import cluster_boot, surrogate  # noqa: E402
from ys_config import (CARD_CSV, FOOT_CSVS, CLICK_CSV, CLICK_NAME2TKR, DATA, OUT)  # noqa: E402
import ys_lib as L  # noqa: E402

# metric → (channel, X builder key). normalize=True → divide by |CONS| (revenue-like); False → simple diff (%-metric)
SPECS = {
    "SALES_RSF":       ("foot",  True),
    "OCCUPY_RATE_TOT": ("card",  False),
    "GMV":             ("click", True),
}
md = []


def log(s=""):
    print(s); md.append(s)


def channel_x():
    return {"foot":  L.build_foot(FOOT_CSVS),
            "card":  L.build_card(CARD_CSV),
            "click": L.build_click(CLICK_CSV, CLICK_NAME2TKR)}


def fetch_metric(token, ids, metric):
    h = {"Authorization": f"Bearer {token}", "Accept": "application/json",
         "Content-Type": "application/json"}
    rows = []
    for i in range(0, len(ids), 25):
        r = requests.post("https://api.factset.com/content/factset-estimates/v2/surprise",
                          json={"ids": ids[i:i + 25], "metrics": [metric], "periodicity": "QTR",
                                "startDate": "2022-01-01", "endDate": "2026-07-01", "statistic": "MEAN"},
                          headers=h, timeout=45)
        if r.ok:
            for it in (r.json().get("data") or []):
                a, c = it.get("surpriseAfter"), it.get("surpriseBefore")
                if a is not None and c is not None:
                    rows.append({"ticker": it["requestId"].replace("-US", ""),
                                 "FE_FP_END": it.get("fiscalEndDate"),
                                 "REPORT_DATE": it.get("surpriseDate"),
                                 "ACTUAL": a, "CONS": c})
        time.sleep(0.15)
    return rows


def test(d, x, y, tag):
    r, pb, n = cluster_boot(d, x, y)
    ps = surrogate(d, x, y, r) if not np.isnan(r) else np.nan
    rho, _, _ = L.spearman_panel(d, x, y)
    hr, _ = L.hit_rate(d, x, y)
    ic = L.rank_ic(d, x, y, min_names=4)
    v = "PASS" if (not np.isnan(ps) and ps < 0.05 and pb < 0.05) else ("n/a" if np.isnan(ps) else "fail")
    log(f"  {tag:44s} r={r:+.3f} n={n:>3} p_surr={ps:.3f} | rho={rho:+.3f} hit={hr:.2f} "
        f"IC={ic['mean_ic']:+.3f} nQ={ic['n_quarters']:>2} [{v}]")


def main():
    xb = channel_x()
    all_ids = sorted({f"{t}-US" for df in xb.values() for t in df.ticker.unique()})
    token = F.get_token()
    log("# 비매출 Y 탐색 (SALES_RSF / OCCUPY / GMV)\n")

    store = {}
    for metric, (ch, normalize) in SPECS.items():
        raw = fetch_metric(token, all_ids, metric)
        y = pd.DataFrame(raw)
        if y.empty:
            log(f"## {metric} ({ch}) — no data\n"); continue
        for c in ("ACTUAL", "CONS"):
            y[c] = pd.to_numeric(y[c], errors="coerce")
        y["FE_FP_END"] = pd.to_datetime(y["FE_FP_END"])
        y["REPORT_DATE"] = pd.to_datetime(y["REPORT_DATE"])
        y = y.dropna(subset=["ACTUAL", "CONS"]).drop_duplicates(["ticker", "FE_FP_END"], keep="last")
        y["y_surprise"] = ((y["ACTUAL"] - y["CONS"]) / y["CONS"].abs()) if normalize else (y["ACTUAL"] - y["CONS"])
        y["y_level"] = y["ACTUAL"]
        store[metric] = y

        # align channel X, no-lookahead
        x = xb[ch].sort_values(["ticker", "date"])
        rows = []
        for t in sorted(set(x.ticker) & set(y.ticker)):
            e = y[y.ticker == t].sort_values("FE_FP_END")
            a = x[x.ticker == t].dropna(subset=["x_yoy"]).sort_values("date")
            if a.empty:
                continue
            m = pd.merge_asof(e, a[["date", "x_yoy"]].rename(columns={"date": "x_date"}),
                              left_on="FE_FP_END", right_on="x_date",
                              direction="nearest", tolerance=pd.Timedelta(days=45))
            rows.append(m)
        p = pd.concat(rows, ignore_index=True).dropna(subset=["x_yoy"]) if rows else pd.DataFrame()
        p = p[p["x_date"] < p["REPORT_DATE"]] if len(p) else p

        log(f"## {metric} — {ch} channel  ({len(p)} events · "
            f"{p.ticker.nunique() if len(p) else 0} tickers)")
        if len(p) < 15:
            log(f"  n<15, skipped detailed test\n"); continue
        test(p, "x_yoy", "y_surprise", f"{ch} x_yoy → {metric}_surprise")
        test(p, "x_yoy", "y_level",    f"{ch} x_yoy → {metric}_level (참고)")
        log("")

    with open(DATA / "factset_nonrev_pit.json", "w") as f:
        json.dump({m: y.assign(FE_FP_END=y.FE_FP_END.astype(str),
                               REPORT_DATE=y.REPORT_DATE.astype(str)).to_dict("records")
                   for m, y in store.items()}, f, indent=2, default=str)
    (OUT / "nonrev_ytargets.md").write_text("\n".join(md))
    print(f"\nsaved: {OUT/'nonrev_ytargets.md'}")


if __name__ == "__main__":
    main()
