"""
Y-switching — shared library: X builders (per channel) + Y metrics.

X builders return a long DataFrame [ticker, date(month-start or FQ-end), x_yoy, x_yoy_3m].
The panel builder (ys_01) aligns X to each fiscal-quarter-end via merge_asof, exactly like
지훈's ft_01_build_panel.py.

Metrics beyond 지훈's cluster_boot/surrogate (those are imported from f1_stats):
  spearman_panel   — rank correlation (robust to fat tails / outliers in surprise & YoY)
  hit_rate         — P(sign(x)==sign(y)); direction agreement vs the 0.50 coin-flip
  rank_ic          — per-quarter cross-sectional Spearman IC, then time-series mean + IC-IR (mean/std)
                     the real factor-research metric: "in a given quarter, do high-X names beat on Y?"
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


# ----------------------------- X channel builders -----------------------------

def build_card(csv_path) -> pd.DataFrame:
    """CA0056 credit_card_spend — QUARTERLY. Sum Online+Physical per ticker-quarter, YoY=pct_change(4)."""
    f = pd.read_csv(csv_path)
    f["date"] = pd.to_datetime(f["date"])
    f = f.rename(columns={"entity_name": "ticker"})
    q = (f.groupby(["ticker", "date"], as_index=False)["credit_card_spend"].sum()
           .sort_values(["ticker", "date"]))
    q["x_yoy"]    = q.groupby("ticker")["credit_card_spend"].pct_change(4, fill_method=None)
    q["x_yoy_3m"] = q["x_yoy"]  # already quarterly; no separate smoothing
    return q[["ticker", "date", "x_yoy", "x_yoy_3m"]]


def build_foot(csv_paths) -> pd.DataFrame:
    """CA0060 foot_traffic — MONTHLY. Concat files, monthly sum, YoY=pct_change(12, fill_method=None) + 3m-mean YoY."""
    frames = []
    for p in csv_paths:
        d = pd.read_csv(p)
        d["date"] = pd.to_datetime(d["date"])
        frames.append(d.rename(columns={"entity_name": "ticker"})[["ticker", "date", "foot_traffic"]])
    f = pd.concat(frames, ignore_index=True).drop_duplicates(["ticker", "date"])
    f["month"] = f["date"].dt.to_period("M").dt.to_timestamp()
    # drop partial current month
    cur = f["date"].max().to_period("M").to_timestamp()
    f = f[f["month"] < cur]
    m = (f.groupby(["ticker", "month"], as_index=False)["foot_traffic"].sum()
           .rename(columns={"month": "date"}).sort_values(["ticker", "date"]))
    m["x_yoy"] = m.groupby("ticker")["foot_traffic"].pct_change(12, fill_method=None)
    m["x_3m"]  = m.groupby("ticker")["foot_traffic"].transform(lambda s: s.rolling(3, min_periods=2).mean())
    m["x_yoy_3m"] = m.groupby("ticker")["x_3m"].pct_change(12, fill_method=None)
    return m[["ticker", "date", "x_yoy", "x_yoy_3m"]]


def build_click(csv_path, name2tkr) -> pd.DataFrame:
    """CA0030 website_users — MONTHLY. Map company→ticker, sum Mobile+Desktop, YoY=pct_change(12, fill_method=None)."""
    f = pd.read_csv(csv_path)
    f["date"] = pd.to_datetime(f["date"])
    f["ticker"] = f["entity_name"].map(name2tkr)
    f = f.dropna(subset=["ticker"])
    f["month"] = f["date"].dt.to_period("M").dt.to_timestamp()
    cur = f["date"].max().to_period("M").to_timestamp()
    f = f[f["month"] < cur]
    m = (f.groupby(["ticker", "month"], as_index=False)["website_users"].sum()
           .rename(columns={"month": "date"}).sort_values(["ticker", "date"]))
    m["x_yoy"] = m.groupby("ticker")["website_users"].pct_change(12, fill_method=None)
    m["x_3m"]  = m.groupby("ticker")["website_users"].transform(lambda s: s.rolling(3, min_periods=2).mean())
    m["x_yoy_3m"] = m.groupby("ticker")["x_3m"].pct_change(12, fill_method=None)
    return m[["ticker", "date", "x_yoy", "x_yoy_3m"]]


# ----------------------------- Y load -----------------------------

def load_factset(json_path) -> pd.DataFrame:
    import json
    d = pd.DataFrame(json.load(open(json_path))["rows"])
    for c in ("ACTUAL", "CONS_EARLY", "CONS_PRINT"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d["FE_FP_END"]   = pd.to_datetime(d["FE_FP_END"])
    d["REPORT_DATE"] = pd.to_datetime(d["REPORT_DATE"])
    d = d.dropna(subset=["ticker", "ACTUAL", "CONS_EARLY"]).sort_values(["ticker", "FE_FP_END"])
    d["rev_yoy"]        = d.groupby("ticker")["ACTUAL"].pct_change(4)
    d["surprise_early"] = (d["ACTUAL"] - d["CONS_EARLY"]) / d["CONS_EARLY"]
    d["surprise_print"] = (d["ACTUAL"] - d["CONS_PRINT"]) / d["CONS_PRINT"]
    return d


# ----------------------------- extra metrics -----------------------------

def spearman_panel(d: pd.DataFrame, x: str, y: str):
    """Pooled Spearman rho + p. Robust to the fat tails that inflate/deflate Pearson."""
    m = d[[x, y]].dropna()
    if len(m) < 5:
        return np.nan, np.nan, len(m)
    rho, p = stats.spearmanr(m[x], m[y])
    return rho, p, len(m)


def hit_rate(d: pd.DataFrame, x: str, y: str):
    """P(sign(x)==sign(y)). >0.50 = directional edge. Returns (rate, n)."""
    m = d[[x, y]].dropna()
    m = m[(m[x] != 0) & (m[y] != 0)]
    if len(m) < 5:
        return np.nan, len(m)
    return float((np.sign(m[x]) == np.sign(m[y])).mean()), len(m)


def rank_ic(d: pd.DataFrame, x: str, y: str, date_col: str = "FE_FP_END", min_names: int = 5):
    """Per-quarter cross-sectional Spearman IC → time-series mean, std, IC-IR, t-stat.

    The factor metric: within each earnings quarter, rank names by X and by Y, correlate the
    ranks. A real cross-sectional signal has positive mean IC AND stable IC (high IC-IR).
    Needs >= min_names tickers reporting in the same quarter — so this only bites on wide panels.
    """
    ics = []
    for _, g in d[[date_col, x, y]].dropna().groupby(date_col):
        if g[x].nunique() >= min_names and g[y].nunique() >= min_names and len(g) >= min_names:
            rho, _ = stats.spearmanr(g[x], g[y])
            if not np.isnan(rho):
                ics.append(rho)
    ics = np.array(ics)
    if len(ics) < 3:
        return {"mean_ic": np.nan, "ic_std": np.nan, "ic_ir": np.nan,
                "t_stat": np.nan, "n_quarters": len(ics)}
    mean, sd = ics.mean(), ics.std(ddof=1)
    ir = mean / sd if sd > 0 else np.nan
    t = mean / (sd / np.sqrt(len(ics))) if sd > 0 else np.nan
    return {"mean_ic": mean, "ic_std": sd, "ic_ir": ir, "t_stat": t, "n_quarters": len(ics)}
