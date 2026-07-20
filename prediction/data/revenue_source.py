"""FactSet point-in-time revenue source — reads one channel's factset_*_pit.json.

Boundary wrapper: pandas parsing stays inside; the only thing that crosses out is a list of
dependency-free `RevenueRecord`s. Mirrors f1_lib._load_factset (same numeric coercion, same
fsym->ticker map, same drop rule, same sort). Surprise/YoY are derived downstream in the panel.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import pandas as pd

from prediction.channels.specs import ChannelSpec
from prediction.domain.records import RevenueRecord
from prediction.errors import DataUnavailableError

__all__ = ["FactSetJsonSource"]


class FactSetJsonSource:
    """Reads a channel's FactSet PIT json into leakage-free revenue events."""

    def __init__(self, channel: ChannelSpec):
        self._path = channel.factset
        self._fsym2tkr = channel.fsym2tkr

    def records(self) -> list[RevenueRecord]:
        """One RevenueRecord per (ticker, fiscal-period) with a resolvable ticker + actual + early consensus."""
        frame = self._frame()
        return [
            RevenueRecord(
                ticker=row.ticker,
                fp_end=row.FE_FP_END.date(),
                report_date=row.REPORT_DATE.date(),
                actual=float(row.ACTUAL),
                cons_early=float(row.CONS_EARLY),
                cons_print=_present(row.CONS_PRINT),
            )
            for row in frame.itertuples()
        ]

    def _frame(self) -> pd.DataFrame:
        rows = self._read_rows()
        frame = pd.DataFrame(rows)
        for col in ("ACTUAL", "CONS_EARLY", "CONS_PRINT"):
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
        frame["FE_FP_END"] = pd.to_datetime(frame["FE_FP_END"])
        frame["REPORT_DATE"] = pd.to_datetime(frame["REPORT_DATE"])
        frame["ticker"] = frame["FSYM_ID"].map(self._fsym2tkr)
        frame = frame.dropna(subset=["ticker", "ACTUAL", "CONS_EARLY"])
        return frame.sort_values(["ticker", "FE_FP_END"])

    def _read_rows(self) -> list[dict]:
        try:
            payload = json.loads(Path(self._path).read_text())
        except (OSError, ValueError) as exc:
            raise DataUnavailableError(f"cannot read FactSet json: {self._path}") from exc
        if "rows" not in payload:
            raise DataUnavailableError(f"FactSet json has no 'rows': {self._path}")
        return payload["rows"]


def _present(value: float) -> Optional[float]:
    """Coerced consensus-print level, or None when FactSet left it blank (NaN)."""
    return None if pd.isna(value) else float(value)
