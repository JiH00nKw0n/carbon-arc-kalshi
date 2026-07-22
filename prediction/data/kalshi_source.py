"""Kalshi ladder sources — the Y (revenue history) and X (pre-publication KPI ladder) for the
`kalshi` channel.

Unlike the scalar carbon-arc channels, Kalshi's X is a *distribution*: a per-firm-quarter market
ladder already frozen at a leak-safe pre-publication candle. So this source reads two existing,
already-leak-safe artifacts rather than a summed CSV:

  revenue  kalshi_factset_revenue_surprise_panel.csv  full FactSet quarterly history (Y)
  ladder   kalshi_prereport_ladder_panel_screened.csv  one pre-report ladder bundle per firm-quarter

The X carries BOTH a scalar (`value` = the primary ladder's integrated implied value, so x_yoy and
the classical baselines still work) AND the full ladder JSON (`x_payload`, rendered in the LLM prompt).
This mirrors how Z rides as a sentiment scalar for baselines but full text for the LLM.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from prediction.channels.specs import ChannelSpec
from prediction.domain.records import AltPoint, RevenueRecord
from prediction.errors import DataUnavailableError

__all__ = ["KalshiRevenueSource", "KalshiLadderSource", "implied_value"]


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
        frame["FE_FP_END"] = pd.to_datetime(frame["FE_FP_END"])
        frame["REPORT_DATE"] = pd.to_datetime(frame["REPORT_DATE"])
        frame = frame.dropna(subset=["ticker", "ACTUAL", "CONS_EARLY"])
        return [
            RevenueRecord(
                ticker=r.ticker, fp_end=r.FE_FP_END.date(), report_date=r.REPORT_DATE.date(),
                actual=float(r.ACTUAL), cons_early=float(r.CONS_EARLY), cons_print=_present(r.CONS_PRINT),
            )
            for r in frame.sort_values(["ticker", "FE_FP_END"]).itertuples()
        ]


class KalshiLadderSource:
    """Reads the pre-report ladder panel into AltPoints: scalar implied value + the ladder JSON payload."""

    def __init__(self, channel: ChannelSpec):
        self._path = channel.ladder_panel

    def points(self) -> list[AltPoint]:
        try:
            frame = pd.read_csv(self._path)
        except (OSError, ValueError) as exc:
            raise DataUnavailableError(f"cannot read Kalshi ladder panel: {self._path}") from exc
        frame["FE_FP_END"] = pd.to_datetime(frame["FE_FP_END"])
        points: list[AltPoint] = []
        for r in frame.itertuples():
            ladders = _parse(getattr(r, "kalshi_ladders_json", ""))
            if not ladders:
                continue
            points.append(AltPoint(
                ticker=r.ticker, date=r.FE_FP_END.date(),
                value=implied_value(ladders), x_payload=json.dumps(ladders),
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


def implied_value(ladders: list) -> float:
    """Integrate the primary (most-priced) ladder's survival curve into E[metric].

    E[X] = strike_0 + sum_i P(>strike_i)*(strike_{i+1}-strike_i) + P(>strike_last)*step. The scalar
    a baseline/x_yoy consumes; the full ladder still goes to the LLM via x_payload.
    """
    primary = max(ladders, key=lambda l: l.get("n_priced_rungs", 0), default=None)
    rungs = primary.get("rungs") if isinstance(primary, dict) else None
    if not rungs or len(rungs) < 2:
        return float("nan")
    pairs = sorted(
        ((float(r["strike"]), float(np.clip(r["probability"], 0, 1))) for r in rungs
         if r.get("strike") is not None and r.get("probability") is not None),
        key=lambda t: t[0],
    )
    if len(pairs) < 2:
        return float("nan")
    strikes = np.array([s for s, _ in pairs])
    probs = np.array([p for _, p in pairs])
    gaps = np.diff(strikes)
    step = float(np.nanmedian(gaps[gaps > 0])) if np.any(gaps > 0) else 0.0
    return float(strikes[0] + np.sum(probs[:-1] * gaps) + probs[-1] * step)
