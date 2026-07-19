#!/usr/bin/env python3
"""Map every Kalshi KPI ladder event to its nearest company earnings target.

The event is the left-hand observation: each event can map to at most one
company-quarter, while a company-quarter may retain several distinct KPI
events. No scalar feature selection or correlation screening happens here.
"""
import argparse
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
KALSHI_ROOT = ROOT / "kalshi"
FEATURES = KALSHI_ROOT / "outputs" / "auto" / "kalshi_company_event_features.csv"
PANEL = KALSHI_ROOT / "outputs" / "auto" / "kalshi_factset_revenue_surprise_panel.csv"
OUT_CSV = KALSHI_ROOT / "outputs" / "auto" / "kalshi_x_revsurprise_events.csv"


def parse_quarter_period(value):
    match = re.fullmatch(r"Q([1-4])\s+(20\d{2})", str(value or "").strip(), re.I)
    return (int(match.group(2)), int(match.group(1))) if match else None


def map_events_to_targets(panel, features, tolerance_days):
    required_panel = {
        "ticker",
        "FE_FP_END",
        "FISCAL_YEAR",
        "FISCAL_QUARTER",
        "REPORT_DATE",
        "published_at",
        "surprise_early",
    }
    missing_panel = sorted(required_panel - set(panel.columns))
    if missing_panel:
        raise SystemExit(f"panel missing columns: {missing_panel}")
    required_features = {
        "matched_ticker",
        "event_ticker",
        "feature_date",
        "metric_label",
        "period_label",
        "feature_family",
    }
    missing_features = sorted(required_features - set(features.columns))
    if missing_features:
        raise SystemExit(f"features missing columns: {missing_features}")

    panel = panel.copy()
    panel_columns = {column: panel[column] for column in panel.columns}
    panel_columns.update(
        {
            "ticker": panel["ticker"].fillna("").str.strip().str.upper(),
            "REPORT_DATE": pd.to_datetime(
                panel["REPORT_DATE"], errors="coerce", utc=True
            ),
            "FE_FP_END": pd.to_datetime(
                panel["FE_FP_END"], errors="coerce", utc=True
            ),
            "FISCAL_YEAR": pd.to_numeric(panel["FISCAL_YEAR"], errors="coerce"),
            "FISCAL_QUARTER": pd.to_numeric(
                panel["FISCAL_QUARTER"], errors="coerce"
            ),
        }
    )
    panel = pd.DataFrame(panel_columns, index=panel.index)
    features = features.copy()
    feature_columns = {column: features[column] for column in features.columns}
    feature_columns.update(
        {
            "matched_ticker": features["matched_ticker"]
            .fillna("")
            .str.strip()
            .str.upper(),
            "feature_date": pd.to_datetime(
                features["feature_date"], errors="coerce", utc=True, format="mixed"
            ),
            "parsed_period": features["period_label"].map(parse_quarter_period),
        }
    )
    features = pd.DataFrame(feature_columns, index=features.index)
    features = features[
        features["feature_family"].eq("kpi_ladder")
        & features["matched_ticker"].ne("")
        & features["feature_date"].notna()
        & features["parsed_period"].notna()
    ].drop_duplicates("event_ticker")

    tolerance = pd.Timedelta(days=tolerance_days)
    rows = []
    for feature in features.itertuples(index=False):
        ticker = feature.matched_ticker
        fiscal_year, fiscal_quarter = feature.parsed_period
        candidates = panel[
            panel["ticker"].eq(ticker)
            & panel["REPORT_DATE"].notna()
            & panel["FISCAL_YEAR"].eq(fiscal_year)
            & panel["FISCAL_QUARTER"].eq(fiscal_quarter)
        ].copy()
        if candidates.empty:
            continue
        distance = (candidates["REPORT_DATE"] - feature.feature_date).abs().rename(
            "_distance"
        )
        candidates = pd.concat([candidates, distance], axis=1)
        candidates = candidates[candidates["_distance"] <= tolerance]
        if candidates.empty:
            continue
        target = candidates.sort_values(
            ["_distance", "REPORT_DATE", "FE_FP_END"]
        ).iloc[0]
        row = target.drop(labels=["_distance"]).to_dict()
        feature_values = feature._asdict()
        feature_values.pop("matched_ticker", None)
        feature_values.pop("parsed_period", None)
        row.update(feature_values)
        row["mapping_method"] = "exact_fiscal_period_then_nearest_date"
        row["event_report_distance_days"] = (
            abs(target["REPORT_DATE"] - feature.feature_date).total_seconds() / 86400.0
        )
        rows.append(row)

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out_columns = {column: out[column] for column in out.columns}
    out_columns.update(
        {
            "REPORT_DATE": pd.to_datetime(out["REPORT_DATE"], utc=True).dt.tz_localize(
                None
            ),
            "FE_FP_END": pd.to_datetime(out["FE_FP_END"], utc=True).dt.tz_localize(
                None
            ),
            "feature_date": pd.to_datetime(
                out["feature_date"], utc=True
            ).dt.tz_localize(None),
        }
    )
    out = pd.DataFrame(out_columns, index=out.index)
    return out.sort_values(
        ["REPORT_DATE", "ticker", "metric_label", "event_ticker"]
    ).reset_index(drop=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", type=Path, default=FEATURES)
    parser.add_argument("--panel", type=Path, default=PANEL)
    parser.add_argument("--out-csv", type=Path, default=OUT_CSV)
    parser.add_argument("--tolerance-days", type=int, default=60)
    args = parser.parse_args()

    if not args.panel.exists():
        raise SystemExit(f"panel CSV missing: {args.panel}")
    if not args.features.exists():
        raise SystemExit(f"features CSV missing: {args.features}")

    out = map_events_to_targets(
        pd.read_csv(args.panel),
        pd.read_csv(args.features),
        args.tolerance_days,
    )
    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.out_csv, index=False)

    if out.empty:
        target_count = ticker_count = 0
        event_counts = pd.Series(dtype=int)
    else:
        key = ["ticker", "FE_FP_END", "REPORT_DATE"]
        target_count = len(out[key].drop_duplicates())
        ticker_count = out["ticker"].nunique()
        event_counts = out.groupby(key)["event_ticker"].nunique()

    print(f"[written] {args.out_csv}")
    print(
        f"events={len(out)} targets={target_count} tickers={ticker_count} "
        f"multi_event_targets={int((event_counts > 1).sum()) if len(event_counts) else 0}"
    )


if __name__ == "__main__":
    main()
