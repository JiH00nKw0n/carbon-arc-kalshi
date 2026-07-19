#!/usr/bin/env python3
"""Reduce the Kalshi market inventory to event-level KPI ladder metadata.

This stage intentionally does not calculate a scalar implied value. It only
identifies genuine threshold ladders and preserves the event metadata needed
to fetch point-in-time candlesticks later.
"""
import argparse
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
KALSHI_ROOT = ROOT / "kalshi"
INVENTORY = KALSHI_ROOT / "outputs" / "auto" / "kalshi_company_markets.csv"
OUT = KALSHI_ROOT / "outputs" / "auto" / "kalshi_company_event_features.csv"

NUMBER_RE = re.compile(r"(-?[\d,.]+(?:\.\d+)?)\s*(thousand|million|billion|%)?", re.I)
STRIKE_TEXT_RE = r"\$?-?[\d,.]+(?:\.\d+)?\s*(?:%|million|billion|thousand)?"


def clean(value):
    if value is None or pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value).replace("\n", " ")).strip()


def number(value):
    try:
        if pd.isna(value) or str(value).strip() == "":
            return np.nan
        return float(value)
    except (TypeError, ValueError):
        return np.nan


def parsed_strike(row):
    strike = number(row.get("floor_strike"))
    if np.isfinite(strike):
        return strike
    match = NUMBER_RE.search(clean(row.get("yes_sub_title")))
    if not match:
        return np.nan
    value = float(match.group(1).replace(",", ""))
    scale = {
        "thousand": 1_000.0,
        "million": 1_000_000.0,
        "billion": 1_000_000_000.0,
        "%": 1.0,
    }.get((match.group(2) or "").lower(), 1.0)
    return value * scale


def survival_rungs(group):
    """Return markets whose YES side means the KPI clears a numeric threshold."""
    g = group.copy()
    strike_type = g["strike_type"].fillna("").str.lower()
    subtitle = g["yes_sub_title"].fillna("").str.strip().str.lower()
    above = subtitle.str.startswith("above")
    at_least = subtitle.str.startswith("at least") | subtitle.str.contains(r"\bor more\b", regex=True)
    valid_direction = (
        (strike_type.isin(["greater", "structured"]) & above)
        | (strike_type.eq("greater_or_equal") & at_least)
        | (strike_type.eq("") & above)
    )
    g = g[valid_direction].copy()
    g["ladder_strike"] = g.apply(parsed_strike, axis=1)
    return g.dropna(subset=["ladder_strike", "market_ticker"]).drop_duplicates("market_ticker")


def combined_text(group):
    values = (
        list(group["market_title"].dropna().head(4))
        + list(group["rules_primary"].dropna().head(2))
        + list(group["series_title"].dropna().head(1))
    )
    return " ".join(clean(value) for value in values)


def metric_label(group):
    text = combined_text(group)
    patterns = [
        rf"reports?\s+(?:above|at least|more than)\s+{STRIKE_TEXT_RE}\s+(.+?)\s+in\s+(?:fiscal\s+)?(?:Q[1-4]|FY|20\d{{2}})",
        rf"above\s+{STRIKE_TEXT_RE}\s+(.+?)\s+in\s+(?:fiscal\s+)?(?:Q[1-4]|FY|20\d{{2}})",
        r"how many\s+(.+?)\s+will\s+.+?\s+report",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            return clean(match.group(1)).lower().rstrip("?.")

    title = clean(group["market_title"].dropna().iloc[0] if group["market_title"].notna().any() else "")
    title = re.sub(r"^will\s+.+?\s+report\s+", "", title, flags=re.I)
    title = re.sub(rf"(?:above|at least|more than)\s+{STRIKE_TEXT_RE}\s*", "", title, flags=re.I)
    title = re.sub(r"\s+in\s+(?:fiscal\s+)?(?:Q[1-4]\s+20\d{2}|20\d{2}\s+Q[1-4]|20\d{2}).*$", "", title, flags=re.I)
    return clean(title).lower().rstrip("?.")


def period_label(group):
    text = combined_text(group)
    patterns = [
        r"\b(Q[1-4]\s+20\d{2})\b",
        r"\b(20\d{2}\s+Q[1-4])\b",
        r"\b(?:FY|fiscal)\s*(20\d{2})\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if not match:
            continue
        value = clean(match.group(1)).upper()
        reverse = re.fullmatch(r"(20\d{2})\s+(Q[1-4])", value)
        return f"{reverse.group(2)} {reverse.group(1)}" if reverse else value
    return ""


def feature_date(group):
    values = []
    for column in ["occurrence_datetime", "close_time", "expiration_time"]:
        parsed = pd.to_datetime(group[column], errors="coerce", utc=True)
        values.extend(parsed.dropna().tolist())
    return min(values).isoformat() if values else ""


def build_features(inventory):
    required = {
        "matched_ticker",
        "series_ticker",
        "series_tags",
        "event_ticker",
        "market_ticker",
        "strike_type",
        "floor_strike",
        "yes_sub_title",
    }
    missing = sorted(required - set(inventory.columns))
    if missing:
        raise SystemExit(f"inventory missing columns: {missing}")

    tagged = inventory[
        inventory["series_tags"].fillna("").str.split("|").map(lambda tags: "KPIs" in tags)
    ].copy()
    tagged = tagged[
        tagged["matched_ticker"].fillna("").str.strip().ne("")
        & tagged["event_ticker"].fillna("").str.strip().ne("")
    ]

    rows = []
    for event_ticker, group in tagged.groupby("event_ticker", sort=True):
        rungs = survival_rungs(group)
        if len(rungs) < 2:
            continue
        strikes = np.sort(rungs["ladder_strike"].astype(float).unique())
        operators = []
        for value in rungs["strike_type"].fillna("").str.lower().unique():
            operators.append(">=" if value == "greater_or_equal" else ">")
        first = group.iloc[0]
        rows.append(
            {
                "matched_ticker": clean(first["matched_ticker"]).upper(),
                "company_name_guess": clean(first.get("company_name_guess")),
                "series_ticker": clean(first["series_ticker"]),
                "series_title": clean(first.get("series_title")),
                "series_tags": clean(first["series_tags"]),
                "event_ticker": clean(event_ticker),
                "feature_date": feature_date(group),
                "period_label": period_label(group),
                "metric_label": metric_label(group),
                "n_markets": int(group["market_ticker"].nunique()),
                "n_ladder_markets": int(rungs["market_ticker"].nunique()),
                "strike_min": float(strikes[0]),
                "strike_max": float(strikes[-1]),
                "threshold_operators": "|".join(sorted(set(operators))),
                "feature_family": "kpi_ladder",
            }
        )
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path, default=INVENTORY)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    inventory = pd.read_csv(args.inventory)
    features = build_features(inventory)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    features.to_csv(args.out, index=False)
    print(f"[written] {args.out}")
    print(
        f"events={len(features)} tickers="
        f"{features['matched_ticker'].nunique() if not features.empty else 0} "
        f"rungs={features['n_ladder_markets'].sum() if not features.empty else 0}"
    )


if __name__ == "__main__":
    main()
