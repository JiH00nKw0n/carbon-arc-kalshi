#!/usr/bin/env python3
"""
Step 2 of making the Kalshi channel paper-compliant: the firm-level screening agent
(the paper's contribution #1, Figure 2 stage 1, EXPERIMENT_SPEC section 2.1).

Step 1 (s_ap) already dropped metrics that are not a revenue base at all (headcount).
This step applies the SAME rubric as the carbon-arc alt-data screen (altdata_ticker_screen.csv):

    O   the KPI is the firm's dominant, CLEAN revenue driver (a sold-volume / monetized
        money-metric that maps to $ via volume x price) -- kept even at 20-45% share when it
        is the largest clean driver, exactly as carbon-arc keeps export-of-record volumes
        at ~20-30% as O.
    X   the KPI is a minority segment dwarfed by other revenue (DIS Disney+ when Parks +
        Studios dominate), OR a WRONG measure (capacity vs sold volume, production vs
        deliveries, engagement/MAU vs monetized, headcount, or a metric made redundant by a
        cleaner money-metric on the same firm).

strength is CONFIDENCE in the O/X verdict (strong/moderate/weak), NOT the revenue share --
this mirrors carbon-arc, where ~100%-of-rev firms can still be X-strong (app/subscription led,
so the channel cannot measure them) and 25-30%-of-rev exporters are O-moderate.

Two agents mirror EXPERIMENT_SPEC section 2.1:
  Screener (effort=medium)  first-pass verdicts over all candidate (ticker, metric) pairs
  Auditor  (effort=high)    adversarial pass: restore under-50% dominant drivers, flip traps

Output: kalshi_kpi_firm_screen.csv with {ticker, metric_label, impact O/X, strength,
est_share, reason}. --apply-panel writes a ladder panel keeping only O (ticker, metric) pairs;
--append-screen appends ticker-level kalshi_kpi rows to altdata_ticker_screen.csv so the
pipeline's _attach_strength gives Kalshi its strength tiers (enabling strong_only).

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
    "prediction-market metric is a DOMINANT, CLEAN driver of the company's TOTAL revenue, using the SAME "
    "rubric as the carbon-arc alt-data screen. The downstream prediction target is the firm's TOTAL revenue "
    "surprise versus analyst consensus.\n"
    "Mark impact 'O' if the KPI is the company's single largest CLEAN revenue driver -- a sold-volume (or the "
    "monetized money-metric) that maps to dollars via volume x price. Keep 'O' EVEN WHEN the share is well "
    "under half (e.g. ~20-45%) as long as it is the dominant single clean driver (mirroring carbon-arc, which "
    "keeps commodity export-of-record volumes at ~20-30% of revenue as O). Examples of O: vehicle deliveries "
    "for an automaker, trading volume for an exchange (Coinbase), commercial-jet deliveries for Boeing, paid "
    "subscribers for a subscription-led business.\n"
    "Mark impact 'X' ONLY when the KPI is not such a driver: (a) a minority segment dwarfed by other revenue "
    "(Disney+ subscribers when Parks + Studios dominate); or (b) a WRONG measure -- capacity rather than sold "
    "volume (available seats/rooms/berths), production rather than deliveries, an engagement/vanity metric "
    "(MAU, hours) not directly monetized, headcount, or a metric made redundant by a cleaner money-metric on "
    "the same firm (MAU when paid subscribers are also available).\n"
    "strength is your CONFIDENCE in the O/X verdict, NOT the revenue share: 'strong' = unambiguous, "
    "'moderate' = reasonably clear, 'weak' = borderline. Set est_share = rough share of TOTAL revenue the "
    "metric drives (free text like '~35-45%'). Give a one-line reason grounded in the revenue mix. Return "
    "ONLY the structured object."
)

AUDITOR_SYS = (
    "You are a senior analyst auditing a first-pass screen of Kalshi KPI metrics under the carbon-arc rubric: "
    "impact 'O' if the KPI is the firm's dominant, CLEAN revenue driver (kept even at ~20-45% share when it is "
    "the largest clean driver); impact 'X' only if it is a minority dwarfed by other revenue OR a wrong/"
    "redundant measure. You receive the draft verdicts as JSON. Return the FINAL corrected list: (1) RESTORE "
    "to 'O' dominant clean drivers wrongly excluded merely for being under 50% (e.g. Boeing commercial "
    "deliveries, Coinbase trading volume); (2) flip to 'X' segment traps (a sub-scale segment dwarfed by other "
    "revenue) and measurement traps (capacity vs sold volume, production vs deliveries, engagement/MAU vs "
    "monetized, redundant-vs-cleaner-metric); (3) make strength reflect CONFIDENCE in the verdict, not the "
    "share; (4) tighten est_share and reason. Judge against TOTAL revenue. Return ONLY the structured object "
    "with one row per input (ticker, metric_label)."
)


class Verdict(BaseModel):
    ticker: str
    metric_label: str
    impact: str = Field(description='"O" (dominant clean revenue driver) or "X" (minority/wrong measure)')
    strength: str = Field(description='"strong"/"moderate"/"weak" -- CONFIDENCE in the O/X verdict, not the share')
    est_share: str = Field(description="rough share of TOTAL revenue the metric drives, e.g. '~35-45%'")
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
    df["impact"] = (df["impact"].str.upper().str.strip()
                    .replace({"INCLUDE": "O", "EXCLUDE": "X"}))
    df = df.sort_values(["impact", "ticker"])
    args.out_screen.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out_screen, index=False)

    keep_df = df[df["impact"] == "O"]
    drop_df = df[df["impact"] == "X"]
    print(f"[result] O {len(keep_df)} pairs ({keep_df['ticker'].nunique()} firms) · "
          f"X {len(drop_df)} pairs ({drop_df['ticker'].nunique()} firms)")
    for r in drop_df.itertuples():
        print(f"   X {r.ticker:<6} {r.metric_label[:38]:<40} {r.est_share:<9} {r.reason}")
    print(f"[written] {args.out_screen}")

    if args.append_screen:
        append_to_master_screen(df, args.master_screen)
    if args.apply_panel:
        keep = {(r.ticker, r.metric_label) for r in keep_df.itertuples()}
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


_STRENGTH_RANK = {"strong": 3, "moderate": 2, "weak": 1}


def append_to_master_screen(screen_df, master_path):
    """Append ticker-level kalshi_kpi rows to the shared altdata_ticker_screen.csv.

    The pipeline's `_attach_strength` reads that file, filters (data_type==kalshi_kpi, impact==O),
    and left-joins `strength` by ticker -- so this is what gives the Kalshi channel its strength
    tiers and makes `strong_only` work. Each firm collapses to one row: impact O when any of its
    metrics is O (strength = its highest-confidence O metric), else X. Idempotent: existing
    kalshi_kpi rows are dropped before the append, so re-running never duplicates."""
    rows = []
    for ticker, g in screen_df.groupby("ticker"):
        o = g[g["impact"] == "O"]
        pick = (o.loc[o["strength"].map(_STRENGTH_RANK).fillna(0).idxmax()] if len(o)
                else g.iloc[0])
        rows.append({"data_type": "kalshi_kpi", "ticker": ticker, "company": "",
                     "impact": "O" if len(o) else "X", "strength": pick["strength"],
                     "est_share": pick["est_share"], "available_company_level": "",
                     "carbonarc_dataset": "kalshi_kpi", "reason": pick["reason"]})
    add = pd.DataFrame(rows)
    master = pd.read_csv(master_path)
    master = master[master["data_type"] != "kalshi_kpi"]      # idempotent re-run
    add = add.reindex(columns=master.columns)                 # align to the master schema
    pd.concat([master, add], ignore_index=True).to_csv(master_path, index=False)
    n_o = (add["impact"] == "O").sum()
    print(f"[master-screen] +{len(add)} kalshi_kpi rows ({n_o} O / {len(add) - n_o} X) -> {master_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-screen", type=Path, default=OUT_SCREEN)
    ap.add_argument("--no-audit", action="store_true", help="Skip the adversarial auditor pass.")
    ap.add_argument("--apply-panel", action="store_true",
                    help="Write a ladder panel keeping only O (ticker, metric) pairs.")
    ap.add_argument("--append-screen", action="store_true",
                    help="Append ticker-level kalshi_kpi rows to altdata_ticker_screen.csv.")
    ap.add_argument("--master-screen", type=Path,
                    default=ROOT / "factor1" / "data" / "altdata_ticker_screen.csv")
    ap.add_argument("--ladder-panel", type=Path, default=LADDER_PANEL)
    ap.add_argument("--out-panel", type=Path, default=OUT_PANEL)
    asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    main()
