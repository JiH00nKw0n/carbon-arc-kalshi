"""Assemble leakage-safe prediction targets from a built panel.

Mirrors `f1_lib.build_targets`: keep post-cutoff events that have a usable alt-data YoY, a
non-missing label for the active Y, at least three strictly-prior quarters, and at least one
readable prior earnings call. Unlike the reference, the true value and denominator anchor are
parameterized on the `YTarget` (not hardcoded to `surprise_early`). Two defensive invariants are
asserted on every emitted target: its report is strictly post-cutoff, and every call it leans on
predates the report by at least 31 days.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional, Protocol

import pandas as pd

from prediction.config.schema import RunCfg
from prediction.domain.records import CallRef, PanelRow, Target
from prediction.errors import LeakageError
from prediction.targets.ytarget import YTarget

__all__ = ["build_targets"]

_MIN_HISTORY = 3
_LEAK_GAP_DAYS = 31


class Transcripts(Protocol):
    """The transcript boundary this builder leans on (implemented in data/transcripts.py)."""

    def prior_calls(self, ticker: str, report: date, k: int) -> Optional[list[CallRef]]: ...

    def read_text(self, call: CallRef) -> Optional[str]: ...


def build_targets(panel: pd.DataFrame, transcripts: Transcripts,
                  y_target: YTarget, run_cfg: RunCfg) -> list[Target]:
    """Return every post-cutoff event that clears the leakage and coverage filters."""
    frame = _prepared(panel)
    cutoff = pd.Timestamp(run_cfg.cutoff)
    targets: list[Target] = []
    for ticker, group in frame.groupby("ticker"):
        group = group.sort_values("FE_FP_END")
        for event in group[group["REPORT_DATE"] > cutoff].itertuples():
            target = _target_for(event, group, ticker, transcripts, y_target, run_cfg)
            if target is not None:
                targets.append(target)
    return targets


def _target_for(event, group: pd.DataFrame, ticker: str, transcripts: Transcripts,
                y_target: YTarget, run_cfg: RunCfg) -> Optional[Target]:
    """Build one target, or None if it fails a coverage filter."""
    if pd.isna(event.x_yoy) or pd.isna(getattr(event, y_target.true_col)):
        return None
    history = group[group["FE_FP_END"] < event.FE_FP_END]
    if len(history) < _MIN_HISTORY:
        return None
    report = event.REPORT_DATE.date()
    calls = transcripts.prior_calls(ticker, report, 1)
    if not calls:
        return None
    text = transcripts.read_text(calls[0])
    if not text:
        return None
    text2, second = _second_call(transcripts, ticker, report, run_cfg.n_calls)
    row = _panel_row(event)
    _guard_leakage(report, [calls[0], *([second] if second else [])], run_cfg.cutoff)
    return Target(
        ticker=ticker, fp=row.fp_end, report=row.report_date,
        true=y_target.label(row), x_yoy=float(event.x_yoy), strength=row.strength,
        row=row, hist=tuple(_panel_row(h) for h in history.itertuples()),
        text=text, text2=text2, call_path=calls[0].path)


def _second_call(transcripts: Transcripts, ticker: str, report: date,
                 n_calls: int) -> tuple[Optional[str], Optional[CallRef]]:
    """The second-most-recent prior call's text (and ref), when a two-deep history is wanted."""
    if n_calls < 2:
        return None, None
    calls = transcripts.prior_calls(ticker, report, 2)
    if not calls or len(calls) < 2:
        return None, None
    return transcripts.read_text(calls[1]), calls[1]


def _guard_leakage(report: date, calls: list[CallRef], cutoff: date) -> None:
    """Raise LeakageError unless the report is post-cutoff and every call precedes report-31d."""
    if not report > cutoff:
        raise LeakageError(f"target report {report} is not strictly after cutoff {cutoff}")
    limit = report - timedelta(days=_LEAK_GAP_DAYS)
    for call in calls:
        if call.call_date > limit:
            raise LeakageError(
                f"call {call.call_date} for {call.ticker} leaks against report {report} "
                f"(must be <= {limit})")


def _prepared(panel: pd.DataFrame) -> pd.DataFrame:
    """Datetime-normalized, ticker/quarter-sorted copy of the panel."""
    frame = panel.copy()
    frame["FE_FP_END"] = pd.to_datetime(frame["FE_FP_END"])
    frame["REPORT_DATE"] = pd.to_datetime(frame["REPORT_DATE"])
    return frame.sort_values(["ticker", "FE_FP_END"])


def _panel_row(row) -> PanelRow:
    """Convert an itertuples panel row into a typed, dependency-free PanelRow."""
    return PanelRow(
        ticker=row.ticker,
        fp_end=row.FE_FP_END.date(),
        report_date=row.REPORT_DATE.date(),
        actual=float(row.ACTUAL),
        cons_early=float(row.CONS_EARLY),
        cons_print=_maybe_float(row.CONS_PRINT),
        prior_year_actual=_maybe_float(row.prior_year_actual),
        x_abs=float(row.x_abs),
        x_yoy=float(row.x_yoy),
        x_yoy_3m=float(row.x_yoy_3m),
        surprise_early=float(row.surprise_early),
        surprise_print=_maybe_float(row.surprise_print),
        rev_yoy=_maybe_float(row.rev_yoy),
        lag_surprise=_maybe_float(row.lag_surprise),
        strength=_maybe_str(row.strength),
    )


def _maybe_float(value) -> Optional[float]:
    return None if pd.isna(value) else float(value)


def _maybe_str(value) -> Optional[str]:
    return None if value is None or pd.isna(value) else str(value)
