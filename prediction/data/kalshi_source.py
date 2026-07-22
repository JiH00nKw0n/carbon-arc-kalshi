"""Kalshi ladder sources — the Y (revenue history) and X (pre-publication KPI ladder) for the
`kalshi` channel.

Unlike the scalar carbon-arc channels, Kalshi's X is a *distribution*: a per-firm-quarter market
ladder already frozen at a leak-safe pre-publication candle. So this source reads two existing,
already-leak-safe artifacts rather than a summed CSV:

  revenue  kalshi_factset_revenue_surprise_panel.csv  full FactSet quarterly history (Y)
  ladder   kalshi_prereport_ladder_panel_firmscreened.csv  one pre-report ladder bundle per firm-quarter

The X carries only the full ladder JSON (`x_payload`, rendered in the LLM prompt). Scalar X fields
remain missing because KPI units and ladder histories are not comparable across firm-quarters.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from prediction.channels.specs import ChannelSpec
from prediction.domain.records import AltPoint, RevenueRecord
from prediction.errors import DataUnavailableError

__all__ = ["KalshiRevenueSource", "KalshiLadderSource"]


def _present(value) -> float | None:
    return None if pd.isna(value) else float(value)


class KalshiRevenueSource:
    """Reads the full FactSet revenue-history CSV into leakage-free RevenueRecords (all quarters)."""

    def __init__(self, channel: ChannelSpec):
        self._path = channel.revenue_panel

    def records(self) -> list[RevenueRecord]:
        try:
            frame = pd.read_csv(self._path)
        except (OSError, ValueError) as exc:
            raise DataUnavailableError(f"cannot read Kalshi revenue panel: {self._path}") from exc
        frame = frame.assign(
            FE_FP_END=pd.to_datetime(frame["FE_FP_END"]),
            REPORT_DATE=pd.to_datetime(frame["REPORT_DATE"]),
        )
        frame = frame.dropna(subset=["ticker", "ACTUAL", "CONS_EARLY"])
        return [
            RevenueRecord(
                ticker=r.ticker, fp_end=r.FE_FP_END.date(), report_date=r.REPORT_DATE.date(),
                actual=float(r.ACTUAL), cons_early=float(r.CONS_EARLY), cons_print=_present(r.CONS_PRINT),
            )
            for r in frame.sort_values(["ticker", "FE_FP_END"]).itertuples()
        ]


class KalshiLadderSource:
    """Read each pre-report raw ladder JSON payload into an exact-quarter AltPoint."""

    def __init__(self, channel: ChannelSpec):
        self._path = channel.ladder_panel

    def points(self) -> list[AltPoint]:
        try:
            frame = pd.read_csv(self._path)
        except (OSError, ValueError) as exc:
            raise DataUnavailableError(f"cannot read Kalshi ladder panel: {self._path}") from exc
        frame = frame.assign(FE_FP_END=pd.to_datetime(frame["FE_FP_END"]))
        points: list[AltPoint] = []
        for r in frame.itertuples():
            ladders = _parse(getattr(r, "kalshi_ladders_json", ""))
            if not ladders:
                continue
            points.append(AltPoint(
                ticker=r.ticker, date=r.FE_FP_END.date(),
                value=float("nan"), x_payload=json.dumps(ladders),
            ))
        return points


def _parse(raw) -> list:
    if not isinstance(raw, str) or not raw.strip():
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return value if isinstance(value, list) else []
