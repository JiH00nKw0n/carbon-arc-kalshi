"""Description provider for the optional lookup-tool variant.

Kalshi keeps its frozen, reproducible tool context under ``kalshi/data/tool_context.json``. The
legacy scalar channels retain their original ``factor1/data/fmp_desc_{channel}.json`` and
``carbonarc_desc.json`` lookup convention. Missing files degrade to empty maps so a lookup never
breaks an experiment cell.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from prediction.channels.specs import DATA

ROOT = Path(__file__).resolve().parents[2]

__all__ = ["DescriptionProvider"]


class DescriptionProvider:
    """Serve a frozen company profile and channel-methodology description."""

    def __init__(self, channel_name: str, data_dir: Path = DATA):
        self._channel = channel_name
        context = _load_json(ROOT / channel_name / "data" / "tool_context.json")
        if context:
            self._profiles = context.get("company_profiles", {})
            self._dataset = context.get("dataset_description")
            return
        base = Path(data_dir)
        self._profiles = _load_json(base / f"fmp_desc_{channel_name}.json")
        self._datasets = _load_blocks(base / "carbonarc_desc.json")
        self._dataset = self._datasets.get(channel_name)

    def company_profile(self, ticker: str) -> Optional[str]:
        """Official FMP profile text for the ticker, or None when unavailable."""
        return self._profiles.get(ticker) or None

    def dataset_description(self, channel_name: str) -> Optional[str]:
        """Frozen methodology text for the active alternative-data channel, when available."""
        return self._dataset if channel_name == self._channel else None


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def _load_blocks(path: Path) -> dict:
    raw = _load_json(path)
    return {name: entry["block"] for name, entry in raw.items()
            if isinstance(entry, dict) and "block" in entry}
