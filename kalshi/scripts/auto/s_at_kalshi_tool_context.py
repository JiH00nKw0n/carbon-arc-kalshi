#!/usr/bin/env python3
"""Freeze the company and dataset context exposed by the Kalshi TOOL variant."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[3]
SCREEN = ROOT / "kalshi" / "data" / "ticker_screen.csv"
OUT = ROOT / "kalshi" / "data" / "tool_context.json"
FMP_PROFILE_URL = "https://financialmodelingprep.com/stable/profile"

DATASET_DESCRIPTION = (
    "Kalshi X is a frozen pre-publication probability ladder for a company KPI that passed the "
    "revenue-driver screen. The source universe is Kalshi's public Companies/KPIs series. Each event "
    "contains binary threshold contracts such as P(KPI > strike); the prompt receives every retained "
    "rung's condition, probability, quote source, YES bid and ask, last and previous trade, spread, "
    "candle timestamp, daily volume, and open interest. For each contract, the snapshot is the latest "
    "valid daily candle from market open through one minute before the FactSet publication timestamp. "
    "A narrow valid YES book uses bid/ask midpoint; an invalid or wider-than-0.20 book falls back to "
    "last trade and then previous trade. At least two priced threshold rungs are required. Settled "
    "outcomes, post-publication prices, monotonic smoothing, interpolation, and scalar integration are "
    "not supplied to the LLM."
)


def _env_value(name: str) -> str:
    if os.getenv(name):
        return os.environ[name]
    for path in (ROOT.parent / "mcp-server" / ".env", ROOT.parent / "linq-mcp-server" / ".env.local"):
        try:
            for raw in path.read_text().splitlines():
                if raw.startswith(f"{name}="):
                    return raw.split("=", 1)[1].strip().strip('"').strip("'")
        except OSError:
            continue
    raise RuntimeError(f"{name} is not configured")


def _tickers() -> list[str]:
    screen = pd.read_csv(SCREEN)
    rows = screen[(screen["data_type"] == "kalshi_kpi") & (screen["impact"] == "O")]
    return sorted(rows["ticker"].dropna().unique().tolist())


def _profile(session: requests.Session, ticker: str, key: str) -> str:
    response = session.get(FMP_PROFILE_URL, params={"symbol": ticker, "apikey": key}, timeout=30)
    response.raise_for_status()
    payload = response.json()
    description = payload[0].get("description", "") if isinstance(payload, list) and payload else ""
    if not description.strip():
        raise RuntimeError(f"FMP returned no company description for {ticker}")
    return description.strip()


def main() -> None:
    key = _env_value("FMP_API_KEY")
    session = requests.Session()
    profiles = {ticker: _profile(session, ticker, key) for ticker in _tickers()}
    payload = {
        "source": {
            "company_profiles": "Financial Modeling Prep stable/profile",
            "dataset_methodology": "Kalshi public API plus repository pre-publication snapshot rules",
            "retrieved_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
        "dataset_description": DATASET_DESCRIPTION,
        "company_profiles": profiles,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(f"[written] {OUT}: {len(profiles)} company profiles")


if __name__ == "__main__":
    main()
