#!/usr/bin/env python3
"""
Join Kalshi company X features to a FactSet revenue-surprise panel.

This script is deliberately input-driven because the repo does not commit the
licensed FactSet/Carbon Arc/transcript files. Provide any panel CSV with at
least ticker, REPORT_DATE, and surprise_early columns.
"""
import argparse
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning, message="ChainedAssignmentError*")

ROOT = Path(__file__).resolve().parents[3]
KALSHI_ROOT = ROOT / "kalshi"
FEATURES = KALSHI_ROOT / "outputs" / "auto" / "kalshi_company_event_features.csv"
OUT_CSV = KALSHI_ROOT / "outputs" / "auto" / "kalshi_x_revsurprise_panel.csv"
OUT_MD = KALSHI_ROOT / "docs" / "analysis_kalshi_x_revsurprise.md"


def cluster_boot(d, x, y, n=2000, seed=2026):
    d = d.dropna(subset=[x, y])
    if len(d) < 15 or d[x].std() < 1e-12 or d[y].std() < 1e-12:
        return np.nan, np.nan, len(d)
    r0 = d[x].corr(d[y])
    ticks = d["ticker"].dropna().unique()
    rng = np.random.default_rng(seed)
    bs = []
    for _ in range(n):
        sample_ticks = rng.choice(ticks, len(ticks), True)
        s = pd.concat([d[d["ticker"] == t] for t in sample_ticks], ignore_index=True)
        if s[x].std() > 1e-12 and s[y].std() > 1e-12:
            bs.append(s[x].corr(s[y]))
    bs = np.asarray(bs)
    p = 2 * min((bs > 0).mean(), (bs < 0).mean()) if len(bs) else np.nan
    return float(r0), float(p), int(len(d))


def surrogate(d, x, y, r_obs, n=1000, seed=2027):
    d = d.dropna(subset=[x, y])
    ticks = list(d["ticker"].dropna().unique())
    if len(ticks) < 3 or not np.isfinite(r_obs):
        return np.nan
    rng = np.random.default_rng(seed)
    by = {t: d[d["ticker"] == t][[x, y]].reset_index(drop=True) for t in ticks}
    ge = tot = 0
    for _ in range(n):
        perm = rng.permutation(ticks)
        xs, ys = [], []
        for t, p in zip(ticks, perm):
            yv = by[t][y].to_numpy()
            xv = by[p][x].to_numpy()
            k = min(len(yv), len(xv))
            xs.extend(xv[:k])
            ys.extend(yv[:k])
        xs, ys = np.asarray(xs), np.asarray(ys)
        if xs.std() > 1e-12 and ys.std() > 1e-12:
            tot += 1
            ge += abs(np.corrcoef(xs, ys)[0, 1]) >= abs(r_obs)
    return float((ge + 1) / (tot + 1)) if tot else np.nan


def rel(path):
    path = Path(path)
    try:
        return path.resolve().relative_to(ROOT)
    except ValueError:
        return path


def nearest_join(panel, features, tolerance_days):
    panel = panel.copy()
    features = features.copy()
    panel["REPORT_DATE"] = pd.to_datetime(panel["REPORT_DATE"], errors="coerce", utc=True).dt.tz_convert(None)
    if "FE_FP_END" in panel.columns:
        panel["FE_FP_END"] = pd.to_datetime(panel["FE_FP_END"], errors="coerce", utc=True).dt.tz_convert(None)
    features["feature_date"] = pd.to_datetime(features["feature_date"], errors="coerce", utc=True).dt.tz_convert(None)
    features = features.dropna(subset=["matched_ticker", "feature_date"]).copy()
    features = features.rename(columns={"matched_ticker": "ticker"})

    rows = []
    tol = pd.Timedelta(days=tolerance_days)
    for ticker, p in panel.dropna(subset=["ticker", "REPORT_DATE"]).groupby("ticker"):
        f = features[features["ticker"] == ticker].sort_values("feature_date")
        if f.empty:
            continue
        m = pd.merge_asof(
            p.sort_values("REPORT_DATE"),
            f.sort_values("feature_date"),
            left_on="REPORT_DATE",
            right_on="feature_date",
            by="ticker",
            direction="nearest",
            tolerance=tol,
        )
        rows.append(m)
    if not rows:
        return pd.DataFrame()
    d = pd.concat(rows, ignore_index=True)
    d = d.dropna(subset=["event_ticker"])
    if d.empty:
        return d
    # If several Kalshi metrics map to the same earnings report, keep the most
    # liquid event as the primary X row for the headline test.
    d = d.sort_values(["ticker", "REPORT_DATE", "volume_sum"], ascending=[True, True, False])
    d = d.groupby(["ticker", "REPORT_DATE"], as_index=False).head(1)
    return d


def write_blocker(path, features_path, panel_path):
    lines = [
        "# Kalshi X -> revenue surprise",
        "",
        "No runnable revenue-surprise test was executed.",
        "",
        "Required input is a panel CSV with columns: `ticker`, `REPORT_DATE`, `surprise_early`.",
        f"- features path checked: `{features_path}`",
        f"- panel path checked: `{panel_path or ''}`",
        "",
        "The repo intentionally gitignores licensed FactSet/Carbon Arc/transcript data, so this script is ready but needs the local research data directory or an exported panel.",
    ]
    path.write_text("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", type=Path, default=FEATURES)
    ap.add_argument("--panel", type=Path, default=None)
    ap.add_argument("--out-csv", type=Path, default=OUT_CSV)
    ap.add_argument("--out-md", type=Path, default=OUT_MD)
    ap.add_argument("--tolerance-days", type=int, default=60)
    ap.add_argument("--all-features", action="store_true")
    args = ap.parse_args()

    if args.panel is None or not args.panel.exists():
        args.out_md.parent.mkdir(parents=True, exist_ok=True)
        write_blocker(args.out_md, args.features, args.panel)
        print(f"[blocked] panel CSV missing: {args.panel}")
        print(f"[written] {args.out_md}")
        return
    if not args.features.exists():
        raise SystemExit(f"features CSV missing: {args.features}")

    panel = pd.read_csv(args.panel)
    needed = {"ticker", "REPORT_DATE", "surprise_early"}
    missing = sorted(needed - set(panel.columns))
    if missing:
        raise SystemExit(f"panel missing columns: {missing}")
    features = pd.read_csv(args.features)
    if not args.all_features and "feature_family" in features.columns:
        features = features[features["feature_family"] == "numeric_kpi_ladder"].copy()
    d = nearest_join(panel, features, args.tolerance_days)
    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    d.to_csv(args.out_csv, index=False)

    lines = [
        "# Kalshi X -> revenue surprise",
        "",
        f"> Generated by `kalshi/scripts/auto/s_ah_kalshi_x_revsurprise.py`.",
        "",
        f"- input panel: `{rel(args.panel)}`",
        f"- input features: `{rel(args.features)}`",
        f"- feature filter: {'all' if args.all_features else 'numeric_kpi_ladder'}",
        f"- joined rows: {len(d):,}",
        f"- joined tickers: {d['ticker'].nunique() if not d.empty else 0:,}",
        f"- tolerance days: {args.tolerance_days}",
    ]
    if len(d) < 15:
        lines += [
            "",
            "## Result",
            "Not enough joined observations for a meaningful clustered test (need at least 15 rows).",
        ]
    else:
        lines += ["", "## Correlation tests", "", "| X | r | p_boot | p_surrogate | n |", "|---|---:|---:|---:|---:|"]
        candidates = [
            "implied_value", "implied_value_no_tail", "implied_value_incremental",
            "prob_lowest", "prob_highest", "volume_sum", "open_interest_sum",
        ]
        for x in candidates:
            if x not in d.columns:
                continue
            r, p, n = cluster_boot(d, x, "surprise_early")
            ps = surrogate(d, x, "surprise_early", r)
            lines.append(f"| {x} | {r:+.3f} | {p:.3f} | {ps:.3f} | {n} |")
        lines += [
            "",
            "Interpretation note: raw Kalshi KPI levels differ by metric and company. Treat this as a first-pass screen; stronger tests should use metric-specific surprises versus company history or analyst KPI consensus where available.",
        ]
    lines += ["", f"Output panel: `{rel(args.out_csv)}`"]
    args.out_md.write_text("\n".join(lines) + "\n")
    print(f"[written] {args.out_csv}")
    print(f"[written] {args.out_md}")


if __name__ == "__main__":
    main()
