#!/usr/bin/env python3
"""
Step 1 of making the Kalshi channel paper-compliant: the revenue-related KPI filter
decided in the 2026-07-20 meeting (retain only KPI markets strongly related to revenue).

A Kalshi KPI market is already a metric analysts watch, so most are revenue-relevant.
This screen classifies each distinct KPI metric by HOW it maps to revenue and drops the
ones that are cost or vanity metrics rather than a revenue base:

    revenue = (a volume) x (a price)

    strong    the metric IS the volume term -- units, transactions, subscribers, orders,
              bookings, deliveries. revenue ~ metric x price.
    moderate  revenue-relevant but one step removed -- capacity (rooms, seats, production),
              engagement (hours, DAU/MAU), or an account base that feeds revenue later.
    none      not a revenue base at all -- headcount is an employee-cost input.

Output mirrors factor1/data/altdata_ticker_screen.csv (the committed carbon-arc screen):
one row per (ticker, metric) with impact O/X, strength, reason. The experiment then keeps
impact == 'O' events (strong + moderate); 'X' events are excluded before the firm-level
screening agent runs.

This is a transparent, reproducible rule keyed on the metric wording. It is intentionally
metric-level; the firm-level screening agent (does the channel drive THIS firm's total
revenue) is a separate, later stage that mirrors carbon-arc exactly.
"""
import argparse
import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
KALSHI_ROOT = ROOT / "kalshi"
EVENTS = KALSHI_ROOT / "outputs" / "auto" / "kalshi_x_revsurprise_events.csv"
OUT_SCREEN = KALSHI_ROOT / "outputs" / "auto" / "kalshi_kpi_revenue_screen.csv"
LADDER_PANEL = KALSHI_ROOT / "outputs" / "auto" / "kalshi_prereport_ladder_panel.csv"
OUT_PANEL = KALSHI_ROOT / "outputs" / "auto" / "kalshi_prereport_ladder_panel_screened.csv"

# keyword -> (strength, revenue mechanism). First match wins, so order matters:
# check the non-revenue exclusions before the broad volume keywords.
RULES = [
    # --- not a revenue base: exclude ---
    (r"headcount|employees|staff|workforce", "none",
     "employee-cost input; revenue is not headcount x price"),
    # --- strong: the metric is the volume term of revenue ---
    (r"deliver|production|unit sales|shipment|vehicle", "strong",
     "units sold/produced x average selling price = revenue"),
    (r"volume", "strong",
     "transaction volume x take-rate = revenue"),
    (r"order|trip|ride", "strong",
     "orders/trips x average value x take-rate = revenue"),
    (r"subscriber|payer|membership|member", "strong",
     "paying base x ARPU = subscription revenue"),
    (r"booked|night|berth|passenger|seat|fare|room|home|skier|restaurant|store", "strong",
     "sold/served volume (or unit count) x price = revenue"),
    (r"\bgold subs\b|funded account|account", "moderate",
     "account/premium base feeds revenue but is not itself the $ base"),
    # --- moderate: revenue-relevant but a step removed ---
    (r"\busers?\b|monthly active|daily active|unique|hours|streamed|engagement", "moderate",
     "engagement/audience -> impressions or funnel -> revenue, indirect"),
]

STRENGTH_TO_IMPACT = {"strong": "O", "moderate": "O", "none": "X"}


def classify(metric_label):
    text = str(metric_label).lower()
    for pattern, strength, reason in RULES:
        if re.search(pattern, text):
            return strength, STRENGTH_TO_IMPACT[strength], reason
    return "moderate", "O", "KPI analysts track; presumed revenue-relevant (no rule matched)"


def apply_to_panel(panel_path, out_path):
    """Filter the pre-report ladder panel to O-impact (revenue-relevant) markets.

    Drops any ladder whose (ticker, metric) is impact X, recomputes the per-row rung/event
    counts so validate_publication_cutoff() still holds, and drops rows left with no ladder.
    Operates on the existing panel -- no candle re-fetch, no LLM cost.
    """
    panel = pd.read_csv(panel_path)
    kept_rows, dropped_rows, cleaned_rows = [], 0, 0
    for _, row in panel.iterrows():
        raw = row.get("kalshi_ladders_json")
        ladders = json.loads(raw) if isinstance(raw, str) and raw.strip() else []
        keep = [lad for lad in ladders if classify(lad.get("metric_label"))[1] == "O"]
        if not keep:
            dropped_rows += 1
            continue
        if len(keep) != len(ladders):
            cleaned_rows += 1
        record = row.to_dict()
        record["kalshi_ladders_json"] = json.dumps(keep)
        record["pre_event_count"] = len(keep)
        record["pre_total_ladder_markets"] = sum(l.get("n_ladder_markets", 0) for l in keep)
        record["pre_total_priced_rungs"] = sum(l.get("n_priced_rungs", 0) for l in keep)
        record["pre_wide_spread_fallback_rungs"] = sum(
            sum(1 for r in l.get("rungs", []) if r.get("wide_spread_fallback")) for l in keep
        )
        record["kalshi_event_tickers"] = "|".join(l.get("event_ticker", "") for l in keep)
        kept_rows.append(record)

    out = pd.DataFrame(kept_rows, columns=panel.columns)
    out.to_csv(out_path, index=False)
    print(f"[panel] {len(panel)} rows -> {len(out)} rows "
          f"({dropped_rows} dropped as revenue-KPI-empty, {cleaned_rows} had an X ladder removed)")
    print(f"[written] {out_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", type=Path, default=EVENTS)
    ap.add_argument("--out-screen", type=Path, default=OUT_SCREEN)
    ap.add_argument("--ladder-panel", type=Path, default=LADDER_PANEL)
    ap.add_argument("--out-panel", type=Path, default=OUT_PANEL)
    ap.add_argument("--apply-panel", action="store_true",
                    help="Also write a screened copy of the pre-report ladder panel (O-impact only).")
    args = ap.parse_args()

    events = pd.read_csv(args.events)
    pairs = (
        events.groupby(["ticker", "metric_label"], dropna=False)
        .size()
        .reset_index(name="events")
    )

    rows = []
    for r in pairs.itertuples():
        strength, impact, reason = classify(r.metric_label)
        rows.append(
            {
                "data_type": "kalshi_kpi",
                "ticker": r.ticker,
                "metric_label": r.metric_label,
                "events": int(r.events),
                "impact": impact,
                "strength": strength,
                "reason": reason,
            }
        )
    screen = pd.DataFrame(rows).sort_values(["impact", "ticker"], ascending=[True, True])
    args.out_screen.parent.mkdir(parents=True, exist_ok=True)
    screen.to_csv(args.out_screen, index=False)

    kept = screen[screen["impact"] == "O"]
    dropped = screen[screen["impact"] == "X"]
    kept_events = int(kept["events"].sum())
    dropped_events = int(dropped["events"].sum())
    print(f"[screen] {len(screen)} distinct (ticker, metric) pairs, {int(screen['events'].sum())} events")
    print(f"[keep O] {len(kept)} pairs / {kept_events} events   "
          f"(strong={int((kept['strength']=='strong').sum())}, moderate={int((kept['strength']=='moderate').sum())})")
    print(f"[drop X] {len(dropped)} pairs / {dropped_events} events")
    if len(dropped):
        for r in dropped.itertuples():
            print(f"         DROP  {r.ticker:<6} {r.metric_label}  ({r.reason})")
    print(f"[written] {args.out_screen}")

    if args.apply_panel:
        apply_to_panel(args.ladder_panel, args.out_panel)


if __name__ == "__main__":
    main()
