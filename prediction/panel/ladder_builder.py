"""Ladder-channel panel builder — Kalshi's analogue of panel/builder.build_panel.

The scalar builder joins revenue to alt-data by *nearest date* (merge_asof) and drops rows whose
`x_yoy` is NaN. A Kalshi ladder is keyed to an exact fiscal quarter and its scalar x_yoy is usually
undefined (sparse, per-firm-varying metric), so this path instead:

  - exact-joins each revenue event to its same-(ticker, FE_FP_END) ladder,
  - carries the ladder JSON through as `x_payload` (X-presence is ladder-presence, not x_yoy),
  - leaves scalar x_abs / x_yoy fields missing rather than fabricating an implied ladder value,
  - reuses the shared history + strength columns so everything downstream is identical.

Emits the same `_COLUMNS` schema as the scalar builder, plus `x_payload`.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from prediction.channels.specs import ChannelSpec
from prediction.domain.records import AltPoint, RevenueRecord
from prediction.errors import DataUnavailableError
from prediction.panel.builder import SCREEN, _add_history_columns, _attach_strength, _COLUMNS

__all__ = ["build_ladder_panel"]


def build_ladder_panel(spec: ChannelSpec, revenue_records: list[RevenueRecord],
                       alt_points: list[AltPoint], screen_csv: str | Path = SCREEN) -> pd.DataFrame:
    """Assemble the Kalshi panel: full revenue history, exact-joined to its per-quarter ladder."""
    revenue = _revenue_frame(revenue_records)
    alt = _ladder_frame(alt_points)
    panel = revenue.merge(alt, on=["ticker", "FE_FP_END"], how="left")
    panel = _add_history_columns(panel)
    panel = _attach_strength(panel, spec, screen_csv)
    return panel[[*_COLUMNS, "x_payload"]]


def _revenue_frame(records: list[RevenueRecord]) -> pd.DataFrame:
    if not records:
        raise DataUnavailableError("no revenue records to build a Kalshi panel from")
    frame = pd.DataFrame([{
        "ticker": r.ticker, "FE_FP_END": r.fp_end, "REPORT_DATE": r.report_date,
        "ACTUAL": r.actual, "CONS_EARLY": r.cons_early, "CONS_PRINT": r.cons_print,
    } for r in records])
    frame = frame.assign(
        FE_FP_END=pd.to_datetime(frame["FE_FP_END"]),
        REPORT_DATE=pd.to_datetime(frame["REPORT_DATE"]),
        surprise_early=(frame.ACTUAL - frame.CONS_EARLY) / frame.CONS_EARLY,
        surprise_print=(frame.ACTUAL - frame.CONS_PRINT) / frame.CONS_PRINT,
    )
    return frame.sort_values(["ticker", "FE_FP_END"])


def _ladder_frame(points: list[AltPoint]) -> pd.DataFrame:
    """Ladder AltPoints -> exact (ticker, quarter) payload with unavailable scalar X fields."""
    if not points:
        raise DataUnavailableError("no ladder points to build a Kalshi panel from")
    frame = pd.DataFrame([{
        "ticker": p.ticker,
        "FE_FP_END": p.date,
        "x_abs": float("nan"),
        "x_yoy": float("nan"),
        "x_yoy_3m": float("nan"),
        "x_payload": p.x_payload,
    } for p in points]).astype({"FE_FP_END": "datetime64[ns]"})
    frame = frame.sort_values(["ticker", "FE_FP_END"])
    return frame[["ticker", "FE_FP_END", "x_abs", "x_yoy", "x_yoy_3m", "x_payload"]]
