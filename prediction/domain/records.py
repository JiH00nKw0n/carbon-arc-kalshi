"""Dependency-free frozen dataclasses — the domain vocabulary crossing every boundary.

No pandas, no pydantic, no vendor types: plain Python so any layer can hold these.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Optional


@dataclass(frozen=True)
class RevenueRecord:
    """One FactSet point-in-time revenue event (actual + consensus snapshots)."""
    ticker: str
    fp_end: date
    report_date: date
    actual: float
    cons_early: float
    cons_print: Optional[float]


@dataclass(frozen=True)
class AltPoint:
    """One alt-data observation for a ticker.

    `value` is the scalar the panel/baselines consume (x_abs -> x_yoy). `x_payload` optionally
    carries a richer object serialized as a string — for the Kalshi channel it is the raw
    pre-publication market ladder (a distribution), which the LLM prompt renders in full while
    the scalar still feeds x_yoy. None for the scalar channels (card/web/foot).
    """
    ticker: str
    date: date
    value: float
    x_payload: Optional[str] = None


@dataclass(frozen=True)
class CallRef:
    """A leakage-safe reference to one earnings-call transcript file."""
    ticker: str
    call_date: date
    path: str


@dataclass(frozen=True)
class PanelRow:
    """Typed view of one built panel row (all channel/Y columns resolved)."""
    ticker: str
    fp_end: date
    report_date: date
    actual: float
    cons_early: float
    cons_print: Optional[float]
    prior_year_actual: Optional[float]
    x_abs: float
    x_yoy: float
    x_yoy_3m: float
    surprise_early: float
    surprise_print: Optional[float]
    rev_yoy: Optional[float]
    lag_surprise: Optional[float]
    strength: Optional[str]
    x_payload: Optional[str] = None


@dataclass(frozen=True)
class Target:
    """One post-cutoff prediction event: the row to predict plus its leakage-safe context."""
    ticker: str
    fp: date
    report: date
    true: float
    x_yoy: float
    strength: Optional[str]
    row: PanelRow
    hist: tuple[PanelRow, ...]
    text: Optional[str]
    text2: Optional[str]
    call_path: str
    x_payload: Optional[str] = None


@dataclass(frozen=True)
class Prediction:
    """One model prediction (percent) for one target under one arm."""
    ticker: str
    true: float
    pred: float
    arm: str


@dataclass(frozen=True)
class EvalResult:
    """The full evaluation of one (channel, Y, variant) cell against baselines."""
    channel: str
    y: str
    variant: str
    rows: int
    metrics_table: list[dict[str, Any]]
    calib: list[dict[str, Any]]
    synergy: dict[str, Any]
    surrogate: float
