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
--write-ticker-screen writes the Kalshi-owned ticker-level screen used by the prediction pipeline
to apply its strength tiers (enabling strong_only) without modifying Carbon Arc data.

Uses the shared prediction LLM-gateway client so model authentication is identical to the
benchmark run.
"""
import argparse
import asyncio
import json
import sys
import unicodedata
from pathlib import Path
from typing import List

import pandas as pd
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from prediction.data.llm_client import gpt5_cost, make_openai_client

KALSHI_ROOT = ROOT / "kalshi"
SCREEN_IN = KALSHI_ROOT / "outputs" / "auto" / "kalshi_kpi_revenue_screen.csv"
EVENTS = KALSHI_ROOT / "outputs" / "auto" / "kalshi_x_revsurprise_events.csv"
LADDER_PANEL = KALSHI_ROOT / "outputs" / "auto" / "kalshi_prereport_ladder_panel_screened.csv"
OUT_SCREEN = KALSHI_ROOT / "outputs" / "auto" / "kalshi_kpi_firm_screen.csv"
OUT_LOG = KALSHI_ROOT / "outputs" / "auto" / "kalshi_kpi_firm_screen_calls.jsonl"
OUT_PANEL = KALSHI_ROOT / "outputs" / "auto" / "kalshi_prereport_ladder_panel_firmscreened.csv"
TICKER_SCREEN = KALSHI_ROOT / "data" / "ticker_screen.csv"
MODEL = "gpt-5.5-2026-04-23"


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


async def run_agent(client, model, system, user, effort, expected, stage, batch_number):
    errors = []
    for attempt in range(6):
        try:
            completion = await client.beta.chat.completions.parse(
                model=model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                response_format=Screen,
                reasoning_effort=effort,
            )
            parsed = completion.choices[0].message.parsed
            actual = {(row.ticker, row.metric_label) for row in parsed.verdicts}
            if actual != expected:
                raise RuntimeError(
                    f"screen row mismatch: missing={sorted(expected - actual)} "
                    f"extra={sorted(actual - expected)}"
                )
            usage = completion.usage
            details = getattr(usage, "prompt_tokens_details", None)
            return parsed, {
                "schema_version": 1,
                "status": "ok",
                "stage": stage,
                "batch": batch_number,
                "model": model,
                "reasoning_effort": effort,
                "system_prompt": system,
                "user_prompt": user,
                "expected_pairs": sorted([list(pair) for pair in expected]),
                "parsed_output": parsed.model_dump(mode="json"),
                "input_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
                "cached_input_tokens": int(
                    (getattr(details, "cached_tokens", 0) or 0) if details is not None else 0
                ),
                "output_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
                "cost_usd": gpt5_cost(usage),
                "attempts": attempt + 1,
                "retry_errors": errors,
            }
        except Exception as exc:
            errors.append(f"{type(exc).__name__}: {exc}")
            if attempt == 5:
                raise
            delay = 2 ** attempt
            print(f"[retry] effort={effort} attempt={attempt + 1}/6: {exc}; sleep={delay}s", flush=True)
            await asyncio.sleep(delay)


async def screen_batch(client, model, batch, number, no_audit):
    expected = {(row["ticker"], row["metric_label"]) for row in batch}
    listing = "\n".join(
        f"{row['ticker']} | {row['stock_name']} | KPI metric: {row['metric_label']}" for row in batch
    )
    user = (
        f"Screen these {len(batch)} candidate (company, Kalshi KPI metric) pairs. For EACH pair "
        f"return exactly one verdict row and preserve ticker and metric_label verbatim.\n\n{listing}"
    )
    print(f"[screener {number}] {len(batch)} pairs -> effort=medium", flush=True)
    draft, draft_log = await run_agent(
        client, model, SCREENER_SYS, user, "medium", expected, "screener", number
    )
    if no_audit:
        return draft.verdicts, [draft_log]
    audit_user = (
        "Draft verdicts to audit. Return exactly one corrected row per pair and preserve ticker and "
        "metric_label verbatim:\n\n"
        + json.dumps([row.model_dump() for row in draft.verdicts], indent=1)
    )
    print(f"[auditor {number}] {len(batch)} pairs -> effort=high", flush=True)
    audited, audit_log = await run_agent(
        client, model, AUDITOR_SYS, audit_user, "high", expected, "auditor", number
    )
    return audited.verdicts, [draft_log, audit_log]


async def main_async(args):
    client = make_openai_client()
    model = MODEL

    cand = candidates()
    print(f"[screen] {len(cand)} candidate pairs -> model={model} batch={args.batch_size}", flush=True)
    verdicts = []
    args.log.parent.mkdir(parents=True, exist_ok=True)
    partial_log = args.log.with_suffix(args.log.suffix + ".partial")
    partial_log.write_text("")
    for offset in range(0, len(cand), args.batch_size):
        batch_verdicts, logs = await screen_batch(
            client, model, cand[offset:offset + args.batch_size],
            offset // args.batch_size + 1, args.no_audit,
        )
        verdicts.extend(batch_verdicts)
        with partial_log.open("a") as handle:
            for record in logs:
                handle.write(json.dumps(record, ensure_ascii=True, separators=(",", ":")) + "\n")

    rows = [verdict.model_dump() for verdict in verdicts]
    df = pd.DataFrame(rows)
    df = df.assign(impact=(df["impact"].str.upper().str.strip()
                           .replace({"INCLUDE": "O", "EXCLUDE": "X"})))
    df = df.sort_values(["impact", "ticker"])
    args.out_screen.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out_screen, index=False)
    partial_log.replace(args.log)

    keep_df = df[df["impact"] == "O"]
    drop_df = df[df["impact"] == "X"]
    print(f"[result] O {len(keep_df)} pairs ({keep_df['ticker'].nunique()} firms) · "
          f"X {len(drop_df)} pairs ({drop_df['ticker'].nunique()} firms)")
    for r in drop_df.itertuples():
        print(f"   X {r.ticker:<6} {r.metric_label[:38]:<40} {r.est_share:<9} {r.reason}")
    print(f"[written] {args.out_screen}")
    print(f"[written] {args.log}")

    if args.write_ticker_screen:
        write_ticker_screen(df, args.ticker_screen)
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


def write_ticker_screen(screen_df, path):
    """Write one Kalshi-owned strength row per ticker for the prediction pipeline."""
    rows = []
    for ticker, g in screen_df.groupby("ticker"):
        o = g[g["impact"] == "O"]
        pick = (o.loc[o["strength"].map(_STRENGTH_RANK).fillna(0).idxmax()] if len(o)
                else g.iloc[0])
        rows.append({"data_type": "kalshi_kpi", "ticker": ticker,
                     "impact": "O" if len(o) else "X", "strength": pick["strength"],
                     "est_share": pick["est_share"], "reason": pick["reason"]})
    add = pd.DataFrame(rows).map(_ascii_cell)
    path.parent.mkdir(parents=True, exist_ok=True)
    add.to_csv(path, index=False)
    n_o = (add["impact"] == "O").sum()
    print(f"[ticker-screen] {len(add)} rows ({n_o} O / {len(add) - n_o} X) -> {path}")


def _ascii_cell(value):
    if pd.isna(value):
        return ""
    text = str(value).replace("\u2018", "'").replace("\u2019", "'")
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-screen", type=Path, default=OUT_SCREEN)
    ap.add_argument("--log", type=Path, default=OUT_LOG,
                    help="Lossless JSONL log of screener and auditor prompts and rationales.")
    ap.add_argument("--no-audit", action="store_true", help="Skip the adversarial auditor pass.")
    ap.add_argument("--batch-size", type=int, default=8,
                    help="Candidate pairs per structured LLM call (default: 8).")
    ap.add_argument("--apply-panel", action="store_true",
                    help="Write a ladder panel keeping only O (ticker, metric) pairs.")
    ap.add_argument("--write-ticker-screen", action="store_true",
                    help="Write the Kalshi-owned ticker-level strength screen.")
    ap.add_argument("--ticker-screen", type=Path, default=TICKER_SCREEN)
    ap.add_argument("--ladder-panel", type=Path, default=LADDER_PANEL)
    ap.add_argument("--out-panel", type=Path, default=OUT_PANEL)
    args = ap.parse_args()
    if args.batch_size < 1:
        raise SystemExit("--batch-size must be at least 1")
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
