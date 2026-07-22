"""Transcript store — leakage-safe earnings-call selection + truncated text reads.

Boundary wrapper over transcript_index_{channel}.csv and the raw transcript files. Mirrors
f1_lib.load_txindex / prior_calls / read_text: a call qualifies only if it happened on or before
`report_date - 31d`, calls are returned most-recent-first, and text is truncated to
`max_transcript_chars`. A missing/short call file yields None (a valid "no usable text" state),
not an exception.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd

from prediction.channels.specs import ChannelSpec
from prediction.domain.records import CallRef
from prediction.errors import DataUnavailableError

__all__ = ["TranscriptStore"]

_EMBARGO_DAYS = 31
_MAX_TRANSCRIPT_CHARS = 48_000


class TranscriptStore:
    """Resolves leakage-safe prior calls for a report and reads their (truncated) transcript text."""

    def __init__(self, channel: ChannelSpec, max_transcript_chars: int = _MAX_TRANSCRIPT_CHARS):
        self._index = self._load_index(channel.tx_index)
        self._max_chars = max_transcript_chars

    def prior_calls(self, ticker: str, report_date: date, k: int) -> list[CallRef]:
        """Up to k calls with call_date <= report_date - 31d, most-recent first (fewer if scarce)."""
        embargo = pd.Timestamp(report_date) - pd.Timedelta(days=_EMBARGO_DAYS)
        eligible = self._index[(self._index.ticker == ticker) & (self._index.call_date <= embargo)]
        recent = eligible.iloc[-k:][["call_date", "path"]]
        refs = [
            CallRef(ticker=ticker, call_date=call_date.date(), path=path)
            for call_date, path in recent.itertuples(index=False, name=None)
        ]
        return refs[::-1]

    def read_text(self, ref: CallRef) -> Optional[str]:
        """Transcript text truncated to max_transcript_chars, or None if the file is unreadable."""
        try:
            return Path(ref.path).read_text()[: self._max_chars]
        except OSError:
            return None

    @staticmethod
    def _load_index(path: str) -> pd.DataFrame:
        try:
            index = pd.read_csv(path)
        except (OSError, ValueError) as exc:
            raise DataUnavailableError(f"cannot read transcript index: {path}") from exc
        index = index.assign(call_date=pd.to_datetime(index["call_date"]))
        return index.sort_values(["ticker", "call_date"])
