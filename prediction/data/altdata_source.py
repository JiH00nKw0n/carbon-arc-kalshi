"""Carbon Arc alt-data source — reads a channel's X CSV(s) into raw (ticker, date, value) points.

Boundary wrapper: mirrors f1_lib._load_x up to the per-(ticker, date) sum of the channel's value
column. YoY / rolling / absolute-level derivations belong to the panel builder, so this source
emits only the summed observations as dependency-free `AltPoint`s. Web maps entity_name->ticker
(with the drop set); card/foot treat entity_name as the ticker.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from prediction.channels.specs import ChannelSpec
from prediction.domain.records import AltPoint
from prediction.errors import DataUnavailableError

__all__ = ["CarbonArcCsvSource"]


class CarbonArcCsvSource:
    """Reads a channel's alt-data CSV(s) into one summed observation per ticker and date."""

    def __init__(self, channel: ChannelSpec):
        self._paths = channel.x_csv
        self._value_col = channel.x_val
        self._entity_map = channel.entity_map
        self._entity_drop = channel.entity_drop

    def points(self) -> list[AltPoint]:
        """One AltPoint per (ticker, date); value = summed channel measure for that day."""
        frame = self._frame()
        return [
            AltPoint(ticker=row.ticker, date=row.date.date(), value=float(getattr(row, self._value_col)))
            for row in frame.itertuples()
        ]

    def _frame(self) -> pd.DataFrame:
        frame = self._concat()
        frame = self._resolve_tickers(frame)
        frame["date"] = pd.to_datetime(frame["date"])
        summed = frame.groupby(["ticker", "date"], as_index=False)[self._value_col].sum()
        return summed.sort_values(["ticker", "date"])

    def _resolve_tickers(self, frame: pd.DataFrame) -> pd.DataFrame:
        if self._entity_map is None:                      # card/foot: entity_name is the ticker
            frame = frame.copy()
            frame["ticker"] = frame["entity_name"]
            return frame
        kept = frame[~frame["entity_name"].isin(self._entity_drop)].copy()
        kept["ticker"] = kept["entity_name"].map(self._entity_map)
        return kept.dropna(subset=["ticker"])

    def _concat(self) -> pd.DataFrame:
        try:
            frames = [pd.read_csv(path) for path in self._paths]
        except (OSError, ValueError) as exc:
            raise DataUnavailableError(f"cannot read alt-data CSV(s): {self._paths}") from exc
        return pd.concat(frames, ignore_index=True)
