"""Ladder-channel panel builder — Kalshi's analogue of panel/builder.build_panel.

The scalar builder joins revenue to alt-data by *nearest date* (merge_asof) and drops rows whose
`x_yoy` is NaN. A Kalshi ladder is keyed to an exact fiscal quarter and its scalar x_yoy is usually
undefined (sparse, per-firm-varying metric), so this path instead:

  - exact-joins each revenue event to its same-(ticker, FE_FP_END) ladder,
  - carries the ladder JSON through as `x_payload` (X-presence is ladder-presence, not x_yoy),
  - still computes x_abs / x_yoy from the integrated implied value so the classical baselines run,
  - reuses the shared history + strength columns so everything downstream is identical.

Emits the same `_COLUMNS` schema as the scalar builder, plus `x_payload`.
"""
from __future__ import annotations

import pandas as pd

from prediction.channels.specs import ChannelSpec
from prediction.domain.records import AltPoint, RevenueRecord
from prediction.errors import DataUnavailableError
from prediction.panel.builder import _add_history_columns, _attach_strength, _COLUMNS

__all__ = ["build_ladder_panel"]


def build_ladder_panel(spec: ChannelSpec, revenue_records: list[RevenueRecord],
                       alt_points: list[AltPoint]) -> pd.DataFrame:
    """Assemble the Kalshi panel: full revenue history, exact-joined to its per-quarter ladder."""
    revenue = _revenue_frame(revenue_records)
    alt = _ladder_frame(alt_points)
    panel = revenue.merge(alt, on=["ticker", "FE_FP_END"], how="left")
    panel = _add_history_columns(panel)
    panel = _attach_strength(panel, spec)
    return panel[[*_COLUMNS, "x_payload"]]


def _revenue_frame(records: list[RevenueRecord]) -> pd.DataFrame:
    if not records:
        raise DataUnavailableError("no revenue records to build a Kalshi panel from")
    frame = pd.DataFrame([{
        "ticker": r.ticker, "FE_FP_END": r.fp_end, "REPORT_DATE": r.report_date,
        "ACTUAL": r.actual, "CONS_EARLY": r.cons_early, "CONS_PRINT": r.cons_print,
    } for r in records])
    frame["FE_FP_END"] = pd.to_datetime(frame["FE_FP_END"])
    frame["REPORT_DATE"] = pd.to_datetime(frame["REPORT_DATE"])
    frame["surprise_early"] = (frame.ACTUAL - frame.CONS_EARLY) / frame.CONS_EARLY
    frame["surprise_print"] = (frame.ACTUAL - frame.CONS_PRINT) / frame.CONS_PRINT
    return frame.sort_values(["ticker", "FE_FP_END"])


def _ladder_frame(points: list[AltPoint]) -> pd.DataFrame:
    """Ladder AltPoints -> per (ticker, quarter) implied value + YoY (where computable) + payload."""
    if not points:
        raise DataUnavailableError("no ladder points to build a Kalshi panel from")
    frame = pd.DataFrame([{
        "ticker": p.ticker, "FE_FP_END": p.date, "x_abs": p.value, "x_payload": p.x_payload,
    } for p in points])
    frame["FE_FP_END"] = pd.to_datetime(frame["FE_FP_END"])
    frame = frame.sort_values(["ticker", "FE_FP_END"])
    # scalar YoY of the implied value where 4 prior quarters exist; NaN otherwise (ladder still carries X).
    frame["x_yoy"] = frame.groupby("ticker")["x_abs"].pct_change(4)
    frame["x_yoy_3m"] = frame.groupby("ticker")["x_yoy"].transform(
        lambda s: s.rolling(3, min_periods=1).mean())
    return frame[["ticker", "FE_FP_END", "x_abs", "x_yoy", "x_yoy_3m", "x_payload"]]
