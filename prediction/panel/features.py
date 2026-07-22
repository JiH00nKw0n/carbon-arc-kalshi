"""Scalar features for the classical baselines.

`sentiment` reproduces `f1_lib.sentiment` (Loughran-McDonald net tone, full untruncated text) but
accepts either a transcript path or the raw text. `lag_y` generalizes the reference's `lag_surprise`
to the active target column. `x_sent` is the explicit alt-data x sentiment scalar interaction.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Optional

import pandas as pd

from prediction.errors import DataUnavailableError

__all__ = ["sentiment", "lag_y", "x_sent"]

ROOT = Path(__file__).resolve().parents[2]
LEXICON = ROOT / "lm_sentiment.json"
_STRIP = ".,;:!?()'\""


def sentiment(text_or_path) -> float:
    """Net Loughran-McDonald tone (pos-neg)/(pos+neg); NaN if nothing readable, 0.0 if no hits."""
    words = _words(text_or_path)
    if words is None:
        return float("nan")
    positive, negative = _lexicon()
    pos = sum(_normalize(w) in positive for w in words)
    neg = sum(_normalize(w) in negative for w in words)
    total = pos + neg
    return (pos - neg) / total if total else 0.0


def lag_y(panel: pd.DataFrame, true_col: str) -> pd.Series:
    """One-quarter lag of the active target within each ticker (autoregressive feature)."""
    return panel.groupby("ticker")[true_col].shift(1)


def x_sent(x_yoy, sent):
    """Alt-data YoY x sentiment scalar interaction (elementwise; Series or scalar)."""
    return x_yoy * sent


@lru_cache(maxsize=1)
def _lexicon() -> tuple[frozenset[str], frozenset[str]]:
    try:
        data = json.loads(LEXICON.read_text())
    except OSError as exc:
        raise DataUnavailableError(f"sentiment lexicon not found: {LEXICON}") from exc
    return frozenset(data["positive"]), frozenset(data["negative"])


def _words(text_or_path) -> Optional[list[str]]:
    text = _read_if_path(text_or_path)
    return None if text is None else text.lower().split()


def _read_if_path(value) -> Optional[str]:
    """Read the file when `value` names an existing one; otherwise treat it as raw text."""
    if not isinstance(value, (str, Path)):
        return None
    text = str(value)
    try:
        path = Path(text)
        if path.exists():
            return path.read_text()
    except (OSError, ValueError):
        pass
    return text


def _normalize(word: str) -> str:
    return word.strip(_STRIP).lstrip("-")
