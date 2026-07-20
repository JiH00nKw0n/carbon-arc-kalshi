"""
Foot Traffic — build the analysis panel (CA0060 × FactSet revenue surprise).

OUT: traffic/outputs/panel_foot.csv  — one row per (ticker, fiscal quarter):
  ticker, FE_FP_END, REPORT_DATE, ACTUAL, CONS_EARLY, CONS_PRINT,
  surprise_early, surprise_print, rev_yoy,
  foot_yoy, foot_yoy_3m, strength

X (foot traffic): CA0060 daily visits → monthly sum → YoY.
  foot_yoy   = pct_change(12) of monthly total, sampled at fiscal-quarter-end month.
  foot_yoy_3m= YoY of the trailing-3-month mean (smoother).
Y (FactSet PIT): surprise_early = (ACTUAL − CONS_EARLY)/CONS_EARLY.

Usage:
    python ft_01_build_panel.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ft_config import CUTOFF, FACTSET, FOOT_CSV, FSYM2TKR, OUT, SCREEN, FOOT_ENTITY2TKR


def load_factset() -> pd.DataFrame:
    d = pd.DataFrame(json.load(open(FACTSET))["rows"])
    for c in ("ACTUAL", "CONS_EARLY", "CONS_PRINT"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d["FE_FP_END"]   = pd.to_datetime(d["FE_FP_END"])
    d["REPORT_DATE"] = pd.to_datetime(d["REPORT_DATE"])
    d["ticker"] = d["FSYM_ID"].map(FSYM2TKR)
    d = d.dropna(subset=["ticker", "ACTUAL", "CONS_EARLY"]).sort_values(["ticker", "FE_FP_END"])
    d["rev_yoy"]       = d.groupby("ticker")["ACTUAL"].pct_change(4)
    d["surprise_early"] = (d["ACTUAL"] - d["CONS_EARLY"]) / d["CONS_EARLY"]
    d["surprise_print"] = (d["ACTUAL"] - d["CONS_PRINT"]) / d["CONS_PRINT"]
    return d


def load_foot() -> pd.DataFrame:
    """Daily CA0060 → monthly sum → YoY."""
    f = pd.read_csv(FOOT_CSV)
    f["date"]   = pd.to_datetime(f["date"])
    f["ticker"] = f["entity_name"].map(FOOT_ENTITY2TKR)
    f = f.dropna(subset=["ticker"])

    # daily → monthly sum (period = month start)
    f["month"] = f["date"].dt.to_period("M").dt.to_timestamp()

    # partial current month 제거: 현재 달 = 데이터 최신 날짜의 month
    latest_date = f["date"].max()
    current_month_start = latest_date.to_period("M").to_timestamp()
    f = f[f["month"] < current_month_start]

    m = (f.groupby(["ticker", "month"], as_index=False)["foot_traffic"].sum()
         .rename(columns={"month": "date"})
         .sort_values(["ticker", "date"]))

    # YoY transforms
    m["foot_yoy"] = m.groupby("ticker")["foot_traffic"].pct_change(12)
    m["foot_3m"]  = m.groupby("ticker")["foot_traffic"].transform(
        lambda s: s.rolling(3, min_periods=2).mean())
    m["foot_yoy_3m"] = m.groupby("ticker")["foot_3m"].pct_change(12)
    m["foot_accel"] = m["foot_yoy"] - m.groupby("ticker")["foot_yoy"].transform(
        lambda s: s.shift(1).rolling(12, min_periods=4).mean())
    return m


def main():
    d = load_factset()
    f = load_foot()
    print(f"factset: {d.ticker.nunique()} tickers, {len(d)} qtr-rows | "
          f"foot:    {f.ticker.nunique()} tickers, {len(f)} months")

    strength = (pd.read_csv(SCREEN).query("data_type=='foot_traffic'")
                .set_index("ticker")["strength"].to_dict())

    rows = []
    for t in sorted(set(d.ticker) & set(f.ticker)):
        e = d[d.ticker == t].sort_values("FE_FP_END")
        a = f[f.ticker == t][["date", "foot_yoy", "foot_yoy_3m", "foot_accel"]].dropna(
            subset=["foot_yoy"]).sort_values("date")
        if a.empty:
            continue
        merged = pd.merge_asof(e, a, left_on="FE_FP_END", right_on="date",
                               direction="nearest", tolerance=pd.Timedelta(days=45))
        merged["strength"] = strength.get(t, "?")
        rows.append(merged)

    p = pd.concat(rows, ignore_index=True)
    p = p.dropna(subset=["foot_yoy", "surprise_early"])
    keep = ["ticker", "FE_FP_END", "REPORT_DATE", "ACTUAL", "CONS_EARLY", "CONS_PRINT",
            "surprise_early", "surprise_print", "rev_yoy",
            "foot_yoy", "foot_yoy_3m", "foot_accel", "strength"]
    p = p[keep].sort_values(["ticker", "FE_FP_END"])
    p.to_csv(OUT / "panel_foot.csv", index=False)

    print(f"\npanel_foot.csv: {len(p)} events · {p.ticker.nunique()} tickers · "
          f"{p.FE_FP_END.min().date()}..{p.FE_FP_END.max().date()}")
    print(f"  post-cutoff (report>2025-12-01): {(p.REPORT_DATE > '2025-12-01').sum()} events, "
          f"{p[p.REPORT_DATE>'2025-12-01'].ticker.nunique()} tickers")
    print(f"  strength: {p.groupby('strength').ticker.nunique().to_dict()}")
    print(f"  surprise_early: mean={p.surprise_early.mean()*100:+.2f}% sd={p.surprise_early.std()*100:.2f}%")
    print(f"  tickers: {sorted(p.ticker.unique())}")


if __name__ == "__main__":
    main()
