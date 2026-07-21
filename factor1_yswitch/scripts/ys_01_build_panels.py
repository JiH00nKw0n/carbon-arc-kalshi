"""
Y-switching — build one analysis panel per channel (card / foot / click) × FactSet Y.

For each channel: X long-form (ys_lib builder) is merge_asof-aligned to each fiscal-quarter-end
(tolerance 45d), exactly like 지훈's ft_01_build_panel.py. Y columns (rev_yoy, surprise_early,
surprise_print) come from FactSet PIT. Also carries x_yoy(t-1) lag for the lead/lag test.

OUT: outputs/panel_<channel>.csv

Usage:  python ys_01_build_panels.py
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ys_config import (CARD_CSV, FOOT_CSVS, CLICK_CSV, CLICK_NAME2TKR, FACTSET_JSON, OUT)  # noqa: E402
import ys_lib as L  # noqa: E402

Y_COLS = ["rev_yoy", "surprise_early", "surprise_print"]


def align(xdf: pd.DataFrame, y: pd.DataFrame) -> pd.DataFrame:
    """merge_asof X (long) onto each fiscal-quarter-end in Y, per ticker."""
    xdf = xdf.sort_values(["ticker", "date"])
    xdf["x_yoy_lag1"] = xdf.groupby("ticker")["x_yoy"].shift(1)
    rows = []
    for t in sorted(set(xdf.ticker) & set(y.ticker)):
        e = y[y.ticker == t].sort_values("FE_FP_END")
        a = xdf[xdf.ticker == t].dropna(subset=["x_yoy"]).sort_values("date")
        if a.empty:
            continue
        merged = pd.merge_asof(e, a[["date", "x_yoy", "x_yoy_3m", "x_yoy_lag1"]]
                               .rename(columns={"date": "x_date"}),
                               left_on="FE_FP_END", right_on="x_date",
                               direction="nearest", tolerance=pd.Timedelta(days=45))
        rows.append(merged)
    if not rows:
        return pd.DataFrame()
    p = pd.concat(rows, ignore_index=True)
    p = p.dropna(subset=["x_yoy"])
    # NO-LOOKAHEAD GUARD: the aligned X observation must be dated strictly BEFORE the
    # earnings report. merge_asof(nearest) can otherwise grab an X point up to ~40d AFTER
    # REPORT_DATE (measured post-announcement), which would leak the surprise it "predicts".
    # (Empirically ~4% of rows; removing them leaves r unchanged to 3 decimals — signal is real.)
    n_before = len(p)
    p = p[p["x_date"] < p["REPORT_DATE"]]
    dropped = n_before - len(p)
    if dropped:
        print(f"    [no-lookahead] dropped {dropped}/{n_before} rows where X was observed after REPORT_DATE")
    keep = ["ticker", "FE_FP_END", "REPORT_DATE", "x_date", "ACTUAL", "CONS_EARLY", "CONS_PRINT",
            *Y_COLS, "x_yoy", "x_yoy_3m", "x_yoy_lag1"]
    return p[keep].sort_values(["ticker", "FE_FP_END"])


def main():
    y = L.load_factset(FACTSET_JSON)
    print(f"FactSet Y: {y.ticker.nunique()} tickers, {len(y)} qtr-rows")

    channels = {
        "card":  L.build_card(CARD_CSV),
        "foot":  L.build_foot(FOOT_CSVS),
        "click": L.build_click(CLICK_CSV, CLICK_NAME2TKR),
    }
    for name, xdf in channels.items():
        p = align(xdf, y)
        if p.empty:
            print(f"[{name}] EMPTY panel"); continue
        p.to_csv(OUT / f"panel_{name}.csv", index=False)
        print(f"[{name}] panel_{name}.csv: {len(p)} events · {p.ticker.nunique()} tickers · "
              f"{p.FE_FP_END.min().date()}..{p.FE_FP_END.max().date()}")


if __name__ == "__main__":
    main()
