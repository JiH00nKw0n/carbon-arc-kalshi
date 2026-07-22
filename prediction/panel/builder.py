"""Build the per-channel panel DataFrame from domain records.

Reproduces `f1_lib.build_panel` verbatim (merge_asof nearest, YoY over the channel lag,
45/60-day tolerance) but emits `x_abs`, `rev_yoy`, and `prior_year_actual` for every channel —
not only card. Input is domain records (the boundary sources already mapped ids->tickers and
applied entity filters); output is a plain pandas DataFrame kept internal to `panel/`+`evaluate/`.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from prediction.channels.specs import ChannelSpec
from prediction.domain.records import AltPoint, RevenueRecord
from prediction.errors import DataUnavailableError

__all__ = ["build_panel"]

ROOT = Path(__file__).resolve().parents[2]
SCREEN = ROOT / "factor1" / "data" / "altdata_ticker_screen.csv"

_COLUMNS = [
    "ticker", "FE_FP_END", "REPORT_DATE", "ACTUAL", "CONS_EARLY", "CONS_PRINT",
    "surprise_early", "surprise_print", "x_abs", "x_yoy", "x_yoy_3m",
    "rev_yoy", "prior_year_actual", "lag_surprise", "strength",
]


def build_panel(spec: ChannelSpec, revenue_records: list[RevenueRecord],
                alt_points: list[AltPoint], screen_csv: str | Path = SCREEN) -> pd.DataFrame:
    """Assemble one channel's panel: revenue events joined to their nearest alt-data YoY."""
    revenue = _revenue_frame(revenue_records)
    alt = _alt_frame(alt_points, spec.yoy_lag)
    panel = _join_nearest(revenue, alt, spec.yoy_lag)
    panel = _add_history_columns(panel)
    panel = _attach_strength(panel, spec, screen_csv)
    return panel[_COLUMNS]


def _revenue_frame(records: list[RevenueRecord]) -> pd.DataFrame:
    """FactSet events -> sorted frame with early/print surprise fractions."""
    if not records:
        raise DataUnavailableError("no revenue records to build a panel from")
    frame = pd.DataFrame([{
        "ticker": r.ticker, "FE_FP_END": r.fp_end, "REPORT_DATE": r.report_date,
        "ACTUAL": r.actual, "CONS_EARLY": r.cons_early, "CONS_PRINT": r.cons_print,
    } for r in records]).astype({"FE_FP_END": "datetime64[ns]", "REPORT_DATE": "datetime64[ns]"})
    frame.loc[:, "surprise_early"] = (frame.ACTUAL - frame.CONS_EARLY) / frame.CONS_EARLY
    frame.loc[:, "surprise_print"] = (frame.ACTUAL - frame.CONS_PRINT) / frame.CONS_PRINT
    return frame.sort_values(["ticker", "FE_FP_END"])


def _alt_frame(points: list[AltPoint], yoy_lag: int) -> pd.DataFrame:
    """Alt-data points -> per-ticker level, YoY over the channel lag, and 3-period mean YoY."""
    if not points:
        raise DataUnavailableError("no alt-data points to build a panel from")
    frame = pd.DataFrame(
        [{"ticker": p.ticker, "date": p.date, "value": p.value} for p in points]
    ).astype({"date": "datetime64[ns]"})
    frame = frame.groupby(["ticker", "date"], as_index=False)["value"].sum()
    frame = frame.sort_values(["ticker", "date"])
    frame.loc[:, "x_abs"] = frame["value"]
    frame.loc[:, "x_yoy"] = frame.groupby("ticker")["value"].pct_change(yoy_lag)
    frame.loc[:, "x_yoy_3m"] = frame.groupby("ticker")["x_yoy"].transform(
        lambda s: s.rolling(3, min_periods=1).mean())
    return frame[["ticker", "date", "x_abs", "x_yoy", "x_yoy_3m"]]


def _join_nearest(revenue: pd.DataFrame, alt: pd.DataFrame, yoy_lag: int) -> pd.DataFrame:
    """Per ticker, merge each revenue event to the nearest alt YoY within the channel tolerance."""
    tolerance = pd.Timedelta(days=45 if yoy_lag == 12 else 60)
    joined = []
    for ticker, events in revenue.groupby("ticker"):
        series = alt[alt.ticker == ticker][["date", "x_abs", "x_yoy", "x_yoy_3m"]]
        series = series.dropna(subset=["x_yoy"])
        if series.empty:
            continue
        joined.append(pd.merge_asof(
            events.sort_values("FE_FP_END"), series.sort_values("date"),
            left_on="FE_FP_END", right_on="date", direction="nearest", tolerance=tolerance))
    if not joined:
        raise DataUnavailableError("no ticker overlap between revenue and alt-data")
    return pd.concat(joined, ignore_index=True).sort_values(["ticker", "FE_FP_END"])


def _add_history_columns(panel: pd.DataFrame) -> pd.DataFrame:
    """Add the autoregressive/prior-year columns computed within each ticker."""
    return panel.assign(
        lag_surprise=panel.groupby("ticker")["surprise_early"].shift(1),
        rev_yoy=panel.groupby("ticker")["ACTUAL"].pct_change(4),
        prior_year_actual=panel.groupby("ticker")["ACTUAL"].shift(4),
    )


def _attach_strength(panel: pd.DataFrame, spec: ChannelSpec,
                     screen_csv: str | Path = SCREEN) -> pd.DataFrame:
    """Left-join the O-screen strength tier for this channel's data type (NaN when absent)."""
    path = Path(screen_csv)
    if not path.exists():
        panel = panel.copy()
        panel.loc[:, "strength"] = np.nan
        return panel
    screen = pd.read_csv(path)
    tier = screen[(screen.data_type == spec.screen_dt) & (screen.impact == "O")]
    return panel.merge(tier[["ticker", "strength"]], on="ticker", how="left")
