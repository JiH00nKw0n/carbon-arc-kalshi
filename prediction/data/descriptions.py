"""Description provider — official FMP company profiles + Carbon Arc dataset blurbs.

Boundary wrapper over fmp_desc_{channel}.json and carbonarc_desc.json. Mirrors the
prompt_versions FMP_DESC / CARBONARC_DESC loaders verbatim (official text, no paraphrase): the
company map is ticker->profile; the dataset map is channel->official "block" text. Missing files
degrade to empty maps so the TOOL variant's lookup tools return a clean "not available" string
instead of failing when a company or dataset blurb is absent.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from prediction.channels.specs import DATA

__all__ = ["DescriptionProvider"]


class DescriptionProvider:
    """Serves an FMP company profile per ticker and the official Carbon Arc dataset description."""

    def __init__(self, channel_name: str, data_dir: Path = DATA):
        base = Path(data_dir)
        self._profiles = _load_json(base / f"fmp_desc_{channel_name}.json")
        self._datasets = _load_blocks(base / "carbonarc_desc.json")

    def company_profile(self, ticker: str) -> Optional[str]:
        """Official FMP profile text for the ticker, or None when unavailable."""
        return self._profiles.get(ticker) or None

    def dataset_description(self, channel_name: str) -> Optional[str]:
        """Official Carbon Arc dataset 'block' text for the channel, or None when unavailable."""
        return self._datasets.get(channel_name)


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def _load_blocks(path: Path) -> dict:
    raw = _load_json(path)
    return {name: entry["block"] for name, entry in raw.items()
            if isinstance(entry, dict) and "block" in entry}
