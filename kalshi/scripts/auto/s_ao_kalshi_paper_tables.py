#!/usr/bin/env python3
"""
Render the Kalshi channel in the exact table format of the ICAIF submission
("More Than the Sum: LLMs Find Synergy Across Textual and Alternative Data").

The paper reports each alternative-data channel as R2, calibrated R2 and prediction
correlation for H / H+X / H+Z / H+X+Z, plus a Synergy verdict row. This script emits
Kalshi in that shape so it can sit next to card spend, web traffic and foot traffic
in the paper's Table 1, and applies the paper's Definition 3.1 verbatim:

    cross-source synergy  <=>  d_mse > 0  AND  L(HXZ) < min{L(H), L(HX), L(HZ)}
    correlation check     <=>  d_corr > 0 AND  rho(HXZ) > max{rho(H), rho(HX), rho(HZ)}

Condition 2 is the one that matters here: the paper introduces it precisely because
"two individually harmful sources can combine merely to recover the baseline,
producing a positive interaction without useful prediction."

Calibrated R2 uses company-held-out linear rescaling, matching the paper's
leak-free calibration.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
KALSHI_ROOT = ROOT / "kalshi"

# paper notation -> our arm column
SOURCES = {
    "H": "fin",
    "H + X": "fin+kalshi_ladder",
    "H + Z": "fin+earnings_call",
    "H + X + Z": "fin+kalshi_ladder+earnings_call",
}


def calibrated(predictions, truth, groups):
    """Company-held-out linear rescaling, as in the paper's calibrated R2."""
    out = np.full(len(predictions), np.nan)
    for held in pd.unique(groups):
        train = groups != held
        test = groups == held
        if train.sum() < 3:
            continue
        design = np.column_stack([np.ones(train.sum()), predictions[train]])
        coef, *_ = np.linalg.lstsq(design, truth[train], rcond=None)
        out[test] = coef[0] + coef[1] * predictions[test]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--preds",
        type=Path,
        default=KALSHI_ROOT
        / "outputs"
        / "auto"
        / "kalshi_llm_ladder_ablation_yoy_preds.csv",
    )
    ap.add_argument(
        "--run-log",
        type=Path,
        default=KALSHI_ROOT
        / "outputs"
        / "auto"
        / "kalshi_llm_ladder_ablation_yoy_run_log.jsonl",
    )
    ap.add_argument("--label", default="Kalshi KPI ladder")
    ap.add_argument(
        "--out-md", type=Path, default=KALSHI_ROOT / "YOY_RESULTS.md"
    )
    args = ap.parse_args()

    df = pd.read_csv(args.preds)
    if set(df["target"].dropna()) != {"yoy"}:
        raise SystemExit(f"expected target=yoy in {args.preds}")
    if set(df["truth_column"].dropna()) != {"rev_yoy"}:
        raise SystemExit(f"expected truth_column=rev_yoy in {args.preds}")
    with args.run_log.open() as source:
        calls = [json.loads(line) for line in source if line.strip()]
    if any(call.get("target") != "yoy" for call in calls):
        raise SystemExit(f"non-YoY call found in {args.run_log}")
    successful = [
        call for call in calls if call.get("prediction") is not None and not call.get("error")
    ]
    repeats = sorted({int(call["repeat"]) for call in calls})
    call_keys = {
        (call["ticker"], call["FE_FP_END"], call["arm"], int(call["repeat"]))
        for call in calls
    }
    expected_calls = len(df) * len(SOURCES) * len(repeats)
    if len(call_keys) != len(calls):
        raise SystemExit(f"duplicate call keys found in {args.run_log}")
    if len(calls) != expected_calls or len(successful) != expected_calls:
        raise SystemExit(
            f"incomplete YoY run: expected {expected_calls}, found "
            f"{len(calls)} calls and {len(successful)} successes"
        )
    estimated_cost = sum(float(call.get("estimated_cost_usd", 0.0)) for call in calls)
    cols = list(SOURCES.values())
    df = df.dropna(subset=cols + ["true_pct"])
    y = df["true_pct"].to_numpy(float)
    firms = df["ticker"].to_numpy()
    var = float(np.square(y - y.mean()).mean())

    L, R2, R2c, RHO = {}, {}, {}, {}
    for name, col in SOURCES.items():
        p = df[col].to_numpy(float)
        L[name] = float(np.square(y - p).mean())
        R2[name] = 1 - L[name] / var
        c = calibrated(p, y, firms)
        ok = ~np.isnan(c)
        R2c[name] = 1 - float(np.square(y[ok] - c[ok]).mean()) / var
        RHO[name] = float(np.corrcoef(p, y)[0, 1])

    # Definition 3.1
    g_x = L["H"] - L["H + X"]
    g_z = L["H"] - L["H + Z"]
    g_xz = L["H"] - L["H + X + Z"]
    d_mse = g_xz - g_x - g_z
    dominates = L["H + X + Z"] < min(L["H"], L["H + X"], L["H + Z"])
    synergy_mse = (d_mse > 0) and dominates

    gr_x = RHO["H + X"] - RHO["H"]
    gr_z = RHO["H + Z"] - RHO["H"]
    gr_xz = RHO["H + X + Z"] - RHO["H"]
    d_corr = gr_xz - gr_x - gr_z
    rho_dom = RHO["H + X + Z"] > max(RHO["H"], RHO["H + X"], RHO["H + Z"])
    synergy_corr = (d_corr > 0) and rho_dom

    def tick(value):
        return "✓" if value else "✗"

    lines = [
        f"# {args.label} in the paper's Table 1 format",
        "",
        f"> n = {len(df)} company-quarters, {df['ticker'].nunique()} firms. "
        f"Source: `{args.preds.name}`. Calibrated R2 uses company-held-out rescaling.",
        "",
        "## Run record",
        "",
        "- target: revenue YoY (`rev_yoy`)",
        f"- calls: {len(calls)}; successful: {len(successful)}; errors: {len(calls) - len(successful)}",
        f"- repeats per arm and target: {len(repeats)}",
        f"- estimated gateway cost: USD {estimated_cost:.2f}",
        "",
        "| Sources | R2 | R2 (Calib.) | rho |",
        "|---|---|---|---|",
    ]
    for name in SOURCES:
        bold = "**" if name == "H + X + Z" else ""
        lines.append(
            f"| {name} | {bold}{R2[name]:.3f}{bold} | {bold}{R2c[name]:.3f}{bold} | {bold}{RHO[name]:.3f}{bold} |"
        )
    lines += [
        f"| Synergy | {tick(synergy_mse)} | - | {tick(synergy_corr)} |",
        "",
        "## Definition 3.1 applied verbatim",
        "",
        "| term | value | verdict |",
        "|---|---:|---|",
        f"| G_X = L(H) - L(HX) | {g_x:+.3f} | |",
        f"| G_Z = L(H) - L(HZ) | {g_z:+.3f} | {'Z alone HURTS' if g_z < 0 else ''} |",
        f"| G_XZ = L(H) - L(HXZ) | {g_xz:+.3f} | |",
        f"| **cond 1** d_mse = G_XZ - G_X - G_Z | **{d_mse:+.3f}** | {tick(d_mse > 0)} |",
        f"| **cond 2** L(HXZ) < min(L(H),L(HX),L(HZ)) | {L['H + X + Z']:.3f} vs {min(L['H'], L['H + X'], L['H + Z']):.3f} "
        f"(margin {L['H + X + Z'] - min(L['H'], L['H + X'], L['H + Z']):+.3f}) | {tick(dominates)} |",
        f"| **cross-source synergy (MSE)** | | **{tick(synergy_mse)}** |",
        f"| d_corr | {d_corr:+.3f} | {tick(d_corr > 0)} |",
        f"| rho(HXZ) > max others | {RHO['H + X + Z']:.3f} vs {max(RHO['H'], RHO['H + X'], RHO['H + Z']):.3f} | {tick(rho_dom)} |",
        f"| **cross-source synergy (corr)** | | **{tick(synergy_corr)}** |",
        "",
    ]
    if d_mse > 0 and not dominates:
        lines += [
            "**Why condition 2 fails.** The positive interaction is produced by Z being harmful, not by X and Z "
            "genuinely complementing each other: the best single condition is H+X, and adding Z moves it back up. "
            "The paper anticipates exactly this case in Section 3.3 -- \"two individually harmful sources can combine "
            "merely to recover the baseline, producing a positive interaction without useful prediction\" -- which is "
            "why dominance is required alongside super-additivity.",
            "",
        ]
    text = "\n".join(lines)
    print(text)
    if args.out_md:
        args.out_md.parent.mkdir(parents=True, exist_ok=True)
        args.out_md.write_text(text + "\n")
        print(f"[written] {args.out_md}")


if __name__ == "__main__":
    main()
