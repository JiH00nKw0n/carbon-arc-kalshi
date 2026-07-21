#!/usr/bin/env python3
"""
Step 2 of making the Kalshi channel paper-compliant: the firm-level screening agent
(the paper's contribution #1, Figure 2 stage 1, EXPERIMENT_SPEC section 2.1).

Step 1 (s_ap) already dropped metrics that are not a revenue base at all (headcount).
This step goes further, exactly as the carbon-arc Screener does: for each candidate firm
it judges whether that firm's Kalshi KPI is a DOMINANT driver of its TOTAL revenue, and
excludes firms where the KPI captures only a minority segment.

    include   the KPI mechanically drives the majority of TOTAL revenue (volume x price)
    exclude   the KPI is a minority segment, a capacity metric that is not sold volume,
              or otherwise <~40% of total revenue

The classic catch this makes that step 1 cannot: DIS "Disney+/Hulu subscribers" is a real
subscriber metric (step 1 keeps it) but DTC streaming is a minority of Disney's TOTAL
revenue, which is dominated by Parks and Studios -> EXCLUDE.

Two agents mirror EXPERIMENT_SPEC section 2.1:
  Screener (effort=medium)  first-pass verdicts over all candidate (ticker, metric) pairs
  Auditor  (effort=high)    adversarial pass: flip mis-calls, catch segment/capacity traps

Output: kalshi_kpi_firm_screen.csv with {ticker, metric_label, impact INCLUDE/EXCLUDE,
strength, est_share, reason}. The experiment then keeps INCLUDE pairs; --apply-panel writes
a screened ladder panel just like s_ap does.

Reuses the LLM-gateway client and env resolution from s_al so the model and auth are
identical to the ablation run.
"""
import argparse
import asyncio
import importlib.util
import json
from pathlib import Path
from typing import List

import pandas as pd
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[3]
KALSHI_ROOT = ROOT / "kalshi"
SCREEN_IN = KALSHI_ROOT / "outputs" / "auto" / "kalshi_kpi_revenue_screen.csv"
EVENTS = KALSHI_ROOT / "outputs" / "auto" / "kalshi_x_revsurprise_events.csv"
LADDER_PANEL = KALSHI_ROOT / "outputs" / "auto" / "kalshi_prereport_ladder_panel_screened.csv"
OUT_SCREEN = KALSHI_ROOT / "outputs" / "auto" / "kalshi_kpi_firm_screen.csv"
OUT_PANEL = KALSHI_ROOT / "outputs" / "auto" / "kalshi_prereport_ladder_panel_firmscreened.csv"


def _load_s_al():
    spec = importlib.util.spec_from_file_location(
        "s_al", Path(__file__).with_name("s_al_kalshi_llm_ablation.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SCREENER_SYS = (
    "You are an equity analyst screening US-listed companies for whether a specific Kalshi KPI "
    "prediction-market metric is a DOMINANT driver of the company's TOTAL revenue. The downstream "
    "prediction target is the firm's TOTAL revenue (surprise versus analyst consensus), so a KPI is "
    "useful only if it mechanically drives the MAJORITY of total revenue through a clear volume x price "
    "relationship.\n"
    "INCLUDE if the metric captures the majority (>~50%) of total revenue via a volume x price mechanism "
    "(e.g. vehicle deliveries for an automaker, transaction volume for an exchange, paid subscribers for a "
    "pure-play subscription business).\n"
    "EXCLUDE if the metric is a minority segment of total revenue (e.g. a streaming subscriber count for a "
    "company whose revenue is mostly parks or hardware), a capacity metric that is not the same as sold "
    "volume, an engagement/vanity metric that is not directly monetized, or otherwise <~40% of total revenue.\n"
    "Judge against TOTAL company revenue, not the segment the KPI belongs to. Give a specific one-line reason "
    "grounded in the company's revenue mix, and est_share = your rough estimate of the share of TOTAL revenue "
    "the metric drives. Return ONLY the structured object."
)

AUDITOR_SYS = (
    "You are a senior analyst auditing a first-pass screen of Kalshi KPI metrics for whether each is a "
    "DOMINANT driver of the company's TOTAL revenue. You receive the draft verdicts as JSON. Return the FINAL "
    "corrected list: (1) flip mis-calls where a metric was marked INCLUDE but is actually a minority of TOTAL "
    "revenue (segment traps such as Disney+ subscribers for Disney, or a single sub-brand); (2) catch capacity "
    "vs sold-volume traps (available seats/rooms/berths vs actually sold), production vs deliveries, and "
    "engagement metrics that are not directly monetized; (3) keep clear majority-revenue drivers as INCLUDE; "
    "(4) tighten est_share and reason. Judge against TOTAL revenue. Return ONLY the structured object with one "
    "row per input (ticker, metric_label)."
)


class Verdict(BaseModel):
    ticker: str
    metric_label: str
    impact: str = Field(description='"INCLUDE" or "EXCLUDE"')
    strength: str = Field(description='"strong", "moderate", or "weak"')
    est_share: str = Field(description="rough share of TOTAL revenue the metric drives, e.g. '~85%'")
    reason: str


class Screen(BaseModel):
    verdicts: List[Verdict]


def candidates():
    scr = pd.read_csv(SCREEN_IN)
    names = pd.read_csv(EVENTS)[["ticker", "stock_name"]].drop_duplicates()
    o = scr[scr["impact"] == "O"].merge(names, on="ticker", how="left")
    return o[["ticker", "stock_name", "metric_label"]].to_dict("records")


async def run_agent(client, model, system, user, effort):
    completion = await client.beta.chat.completions.parse(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        response_format=Screen,
        reasoning_effort=effort,
    )
    return completion.choices[0].message.parsed


async def main_async(args):
    s_al = _load_s_al()
    client = s_al.make_openai_client()
    model = s_al.GPT_MODEL

    cand = candidates()
    listing = "\n".join(
        f"{c['ticker']} | {c['stock_name']} | KPI metric: {c['metric_label']}" for c in cand
    )
    user = (
        f"Screen these {len(cand)} candidate (company, Kalshi KPI metric) pairs. For EACH pair return a "
        f"verdict row.\n\n{listing}"
    )

    print(f"[screener] {len(cand)} candidate pairs -> model={model} effort=medium", flush=True)
    draft = await run_agent(client, model, SCREENER_SYS, user, "medium")

    final = draft
    if not args.no_audit:
        print("[auditor] adversarial pass -> effort=high", flush=True)
        audit_user = (
            "Draft verdicts to audit (return the corrected final list, one row per pair):\n\n"
            + json.dumps([v.model_dump() for v in draft.verdicts], indent=1)
        )
        final = await run_agent(client, model, AUDITOR_SYS, audit_user, "high")

    rows = [v.model_dump() for v in final.verdicts]
    df = pd.DataFrame(rows)
    df["impact"] = df["impact"].str.upper().str.strip()
    df = df.sort_values(["impact", "ticker"])
    args.out_screen.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out_screen, index=False)

    inc = df[df["impact"] == "INCLUDE"]
    exc = df[df["impact"] == "EXCLUDE"]
    print(f"[result] INCLUDE {len(inc)} pairs ({inc['ticker'].nunique()} firms) · "
          f"EXCLUDE {len(exc)} pairs ({exc['ticker'].nunique()} firms)")
    for r in exc.itertuples():
        print(f"   EXCLUDE {r.ticker:<6} {r.metric_label[:38]:<40} {r.est_share:<7} {r.reason}")
    print(f"[written] {args.out_screen}")

    if args.apply_panel:
        keep = {(r.ticker, r.metric_label) for r in inc.itertuples()}
        apply_to_panel(args.ladder_panel, args.out_panel, keep)


def apply_to_panel(panel_path, out_path, keep_pairs):
    panel = pd.read_csv(panel_path)
    kept, dropped, cleaned = [], 0, 0
    for _, row in panel.iterrows():
        raw = row.get("kalshi_ladders_json")
        ladders = json.loads(raw) if isinstance(raw, str) and raw.strip() else []
        keep = [l for l in ladders if (row["ticker"], l.get("metric_label")) in keep_pairs]
        if not keep:
            dropped += 1
            continue
        if len(keep) != len(ladders):
            cleaned += 1
        rec = row.to_dict()
        rec["kalshi_ladders_json"] = json.dumps(keep)
        rec["pre_event_count"] = len(keep)
        rec["pre_total_ladder_markets"] = sum(l.get("n_ladder_markets", 0) for l in keep)
        rec["pre_total_priced_rungs"] = sum(l.get("n_priced_rungs", 0) for l in keep)
        rec["pre_wide_spread_fallback_rungs"] = sum(
            sum(1 for r in l.get("rungs", []) if r.get("wide_spread_fallback")) for l in keep
        )
        rec["kalshi_event_tickers"] = "|".join(l.get("event_ticker", "") for l in keep)
        kept.append(rec)
    out = pd.DataFrame(kept, columns=panel.columns)
    out.to_csv(out_path, index=False)
    print(f"[panel] {len(panel)} -> {len(out)} rows ({dropped} dropped as non-INCLUDE, {cleaned} cleaned)")
    print(f"[written] {out_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-screen", type=Path, default=OUT_SCREEN)
    ap.add_argument("--no-audit", action="store_true", help="Skip the adversarial auditor pass.")
    ap.add_argument("--apply-panel", action="store_true",
                    help="Write a ladder panel keeping only INCLUDE (ticker, metric) pairs.")
    ap.add_argument("--ladder-panel", type=Path, default=LADDER_PANEL)
    ap.add_argument("--out-panel", type=Path, default=OUT_PANEL)
    asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    main()
