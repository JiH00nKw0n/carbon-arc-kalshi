#!/usr/bin/env python3
"""
Convert Kalshi company market ladders into event-level X features.

The main feature is a market-implied value from greater-than threshold ladders:
P(metric > strike). This is a snapshot feature, not a historical point-in-time
backtest by itself. It becomes testable once joined to FactSet revenue-surprise
rows by ticker and report/event date.
"""
import argparse
import re
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning, message="ChainedAssignmentError*")
warnings.filterwarnings("ignore", category=FutureWarning, message="The default fill_method*")

ROOT = Path(__file__).resolve().parents[3]
KALSHI_ROOT = ROOT / "kalshi"
INVENTORY = KALSHI_ROOT / "outputs" / "auto" / "kalshi_company_markets.csv"
OUT = KALSHI_ROOT / "outputs" / "auto" / "kalshi_company_event_features.csv"
OUT_MD = KALSHI_ROOT / "docs" / "analysis_kalshi_company_features.md"
STRIKE_TEXT_RE = r"\$?[\d,.]+(?:\.\d+)?\s*(?:%|million|billion|thousand)?"


def num(v):
    try:
        if pd.isna(v) or str(v).strip() == "":
            return np.nan
        return float(v)
    except (TypeError, ValueError):
        return np.nan


def prob_from_row(r):
    bid = num(r.get("yes_bid_dollars"))
    ask = num(r.get("yes_ask_dollars"))
    last = num(r.get("last_price_dollars"))
    if np.isfinite(bid) and np.isfinite(ask) and ask >= bid:
        return float(np.clip((bid + ask) / 2.0, 0.0, 1.0)), "yes_mid"
    if np.isfinite(last):
        return float(np.clip(last, 0.0, 1.0)), "last_price"
    return np.nan, ""


def clean(v):
    if v is None or pd.isna(v):
        return ""
    return re.sub(r"\s+", " ", str(v or "").replace("\n", " ")).strip()


def metric_label(group):
    text = " ".join(clean(v) for v in list(group["rules_primary"].dropna().head(3)) + list(group["market_title"].dropna().head(3)))
    m = re.search(
        rf"reports?\s+(?:above|at least|more than)\s+{STRIKE_TEXT_RE}\s+(.+?)\s+in\s+(Q[1-4]|FY|20\d{{2}})",
        text,
        flags=re.I,
    )
    if m:
        return clean(m.group(1)).lower()
    m = re.search(rf"above\s+{STRIKE_TEXT_RE}\s+(.+?)\s+in\s+(Q[1-4]|FY|20\d{{2}})", text, flags=re.I)
    if m:
        return clean(m.group(1)).lower()
    title = clean(group["market_title"].iloc[0] if len(group) else "")
    title = re.sub(r"\bWill\b", "", title, flags=re.I)
    title = re.sub(r"\breport\s+(above|at least|more than).*$", "", title, flags=re.I)
    return clean(title).lower()


def period_label(group):
    text = " ".join(clean(v) for v in list(group["rules_primary"].dropna().head(3)) + list(group["market_title"].dropna().head(3)))
    m = re.search(r"\b(Q[1-4]\s+20\d{2}|FY\s*20\d{2}|20\d{2})\b", text, flags=re.I)
    return clean(m.group(1).upper().replace("  ", " ")) if m else ""


def implied_ladder(group):
    g = group.copy()
    if g.empty:
        return {
            "n_strikes": 0,
            "strike_min": np.nan,
            "strike_max": np.nan,
            "strike_step_median": np.nan,
            "prob_lowest": np.nan,
            "prob_highest": np.nan,
            "implied_value": np.nan,
            "implied_value_no_tail": np.nan,
            "implied_value_incremental": np.nan,
            "price_sources": "",
        }
    g["strike"] = g["floor_strike"].map(num)
    price_cols = list(g.apply(prob_from_row, axis=1))
    g["prob"], g["price_source"] = zip(*price_cols)
    g = g.dropna(subset=["strike", "prob"]).sort_values("strike")
    if len(g) < 2:
        return {
            "n_strikes": len(g),
            "strike_min": g["strike"].min() if len(g) else np.nan,
            "strike_max": g["strike"].max() if len(g) else np.nan,
            "strike_step_median": np.nan,
            "prob_lowest": g["prob"].iloc[0] if len(g) else np.nan,
            "prob_highest": g["prob"].iloc[-1] if len(g) else np.nan,
            "implied_value": np.nan,
            "implied_value_no_tail": np.nan,
            "implied_value_incremental": np.nan,
            "price_sources": "|".join(sorted(set(g["price_source"]))),
        }
    strikes = g["strike"].to_numpy(float)
    probs = np.clip(g["prob"].to_numpy(float), 0.0, 1.0)
    gaps = np.diff(strikes)
    step = float(np.nanmedian(gaps[gaps > 0])) if np.any(gaps > 0) else 0.0

    # E[X] = integral P(X>x) dx. We only observe survival probabilities at
    # threshold strikes, so this approximation assumes probability one below
    # the first strike and a one-step tail above the last strike.
    incremental = float(np.sum(probs[:-1] * gaps) + probs[-1] * step)
    no_tail = float(strikes[0] + np.sum(probs[:-1] * gaps))
    implied = float(strikes[0] + incremental)
    return {
        "n_strikes": len(g),
        "strike_min": float(strikes[0]),
        "strike_max": float(strikes[-1]),
        "strike_step_median": step,
        "prob_lowest": float(probs[0]),
        "prob_highest": float(probs[-1]),
        "implied_value": implied,
        "implied_value_no_tail": no_tail,
        "implied_value_incremental": incremental,
        "price_sources": "|".join(sorted(set(g["price_source"]))),
    }


def event_date(group):
    for col in ["occurrence_datetime", "close_time", "expiration_time"]:
        vals = [clean(v) for v in group[col].dropna().tolist() if clean(v)]
        if vals:
            return min(vals)
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inventory", type=Path, default=INVENTORY)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--out-md", type=Path, default=OUT_MD)
    args = ap.parse_args()

    d = pd.read_csv(args.inventory).copy()
    if d.empty:
        raise SystemExit(f"empty inventory: {args.inventory}")
    d["volume_num"] = d["volume_fp"].map(num)
    d["open_interest_num"] = d["open_interest_fp"].map(num)

    rows = []
    for event_ticker, g in d.groupby("event_ticker", dropna=True):
        if not clean(event_ticker):
            continue
        ladder = implied_ladder(g[g["strike_type"].fillna("").str.lower() == "greater"])
        first = g.iloc[0]
        rows.append({
            "matched_ticker": clean(first.get("matched_ticker")),
            "company_name_guess": clean(first.get("company_name_guess")),
            "series_ticker": clean(first.get("series_ticker")),
            "series_title": clean(first.get("series_title")),
            "series_tags": clean(first.get("series_tags")),
            "tag_basis": clean(first.get("tag_basis")),
            "event_ticker": clean(event_ticker),
            "feature_date": event_date(g),
            "period_label": period_label(g),
            "metric_label": metric_label(g),
            "n_markets": int(len(g)),
            "n_greater_markets": int((g["strike_type"].fillna("").str.lower() == "greater").sum()),
            "market_statuses": "|".join(sorted(set(clean(v) for v in g["status"].dropna()))),
            "volume_sum": float(np.nansum(g["volume_num"])),
            "open_interest_sum": float(np.nansum(g["open_interest_num"])),
            **ladder,
        })

    out = pd.DataFrame(rows).sort_values(["matched_ticker", "series_ticker", "feature_date", "event_ticker"])
    out["feature_date"] = pd.to_datetime(out["feature_date"], errors="coerce")
    out["is_numeric_kpi_ladder"] = (
        out["series_tags"].fillna("").str.contains("KPIs")
        & out["implied_value"].notna()
        & (out["n_strikes"] >= 2)
    )
    out["feature_family"] = np.where(out["is_numeric_kpi_ladder"], "numeric_kpi_ladder", "other_company_event")
    out["kalshi_implied_value_qoq"] = out.groupby(["matched_ticker", "metric_label"])["implied_value"].pct_change(1, fill_method=None)
    out["kalshi_implied_value_yoy"] = out.groupby(["matched_ticker", "metric_label"])["implied_value"].pct_change(4, fill_method=None)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.out, index=False)

    matched = out[out["matched_ticker"].fillna("").astype(str).str.len() > 0]
    lines = [
        "# Kalshi company event features",
        "",
        f"> Generated by `kalshi/scripts/auto/s_ag_kalshi_company_features.py` from `{args.inventory.relative_to(ROOT)}`.",
        "",
        f"- event rows: {len(out):,}",
        f"- matched ticker rows: {len(matched):,}",
        f"- unique matched tickers: {matched['matched_ticker'].nunique():,}",
        f"- events with implied ladder value: {out['implied_value'].notna().sum():,}",
        f"- numeric KPI ladder rows: {int(out['is_numeric_kpi_ladder'].sum()):,}",
        "",
        "## Top numeric KPI ladder features by Kalshi volume",
        "",
        "| ticker | company | event | metric | period | implied_value | volume_fp |",
        "|---|---|---|---|---|---:|---:|",
    ]
    top_kpi = out[out["is_numeric_kpi_ladder"]].sort_values("volume_sum", ascending=False).head(20)
    for r in top_kpi.itertuples():
        implied = "" if pd.isna(r.implied_value) else f"{r.implied_value:.4g}"
        lines.append(
            f"| {clean(r.matched_ticker)} | {clean(r.company_name_guess)} | `{r.event_ticker}` | "
            f"{r.metric_label} | {r.period_label} | {implied} | {r.volume_sum:.2f} |"
        )
    lines += [
        "",
        "Method note: `implied_value` integrates the observed greater-than price ladder and assumes probability one below the first strike plus a one-step tail above the last strike. Use `implied_value_no_tail` for the no-tail variant.",
        "",
        f"Output: `{args.out.relative_to(ROOT)}`",
    ]
    args.out_md.write_text("\n".join(lines) + "\n")
    print(f"[written] {args.out}")
    print(f"[written] {args.out_md}")


if __name__ == "__main__":
    main()
