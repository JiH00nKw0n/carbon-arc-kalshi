#!/usr/bin/env python3
"""
Step 4: 3-repeat aggregation of the Kalshi channel result (the paper's final read).

The prediction/ pipeline writes one report per (rep, Y) into a seed-tagged directory
(seed2026/2027/2028). This script AVERAGES each arm's prediction across the 3 reps
(to cancel gpt-5.5 sampling noise), then recomputes metrics + Definition-3.1 super-additivity
synergy + the firm-specific shuffle-company surrogate, on BOTH the full-O universe and the
strong-only subset. It reuses the pipeline's own resampling/metrics so the numbers match the
per-cell reports. $0 -- no LLM calls.

Reads:  {ROOT}/prediction/outputs/kalshi_full/kalshi.surprise_early.BASE.*.seed*/preds.csv
Writes: {ROOT}/kalshi/outputs/auto/kalshi_final_results.md  (with --write)
"""
import argparse
import glob
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from prediction.evaluate.metrics import metrics                     # noqa: E402
from prediction.evaluate.resampling import boot_synergy, shuffle_company_surrogate  # noqa: E402

ARMS = ["fin", "fin+x", "fin+text", "fin+x+text"]
SEED = 2026
RUN_DIR = ROOT / "prediction" / "outputs" / "kalshi_full"
OUT_MD = ROOT / "kalshi" / "outputs" / "auto" / "kalshi_final_results.md"


def strong_tickers() -> set:
    scr = pd.read_csv(ROOT / "factor1" / "data" / "altdata_ticker_screen.csv")
    k = scr[scr.data_type == "kalshi_kpi"]
    return set(k[(k.impact == "O") & (k.strength == "strong")].ticker)


def load_reps(y="surprise_early") -> list:
    frames = []
    for d in sorted(glob.glob(str(RUN_DIR / f"kalshi.{y}.BASE.*.seed*"))):
        p = Path(d) / "preds.csv"
        if p.exists():
            df = pd.read_csv(p)
            df["seed"] = d.split("seed")[-1]
            frames.append(df)
    return frames


def average_reps(frames) -> pd.DataFrame:
    """Average each arm across reps per (tkr, true) target; keep targets present in >=1 rep."""
    allrows = pd.concat(frames, ignore_index=True)
    allrows["key"] = allrows["tkr"] + "|" + allrows["true"].round(8).astype(str)
    return allrows.groupby("key").agg(
        tkr=("tkr", "first"), true=("true", "first"), n_reps=("seed", "nunique"),
        **{a: (a, "mean") for a in ARMS}).reset_index(drop=True)


def evaluate(df, label, out):
    out.append(f"\n### {label} — n={len(df)} targets / {df.tkr.nunique()} firms\n")
    true_pct = df["true"].values * 100
    out.append("| arm | RMSE | R² | corr |\n|---|--:|--:|--:|")
    for a in ARMS:
        m = metrics(df[a].values, true_pct)
        star = " **" if a == "fin+x+text" else " "
        out.append(f"|{star}{a}{star.strip()} | {m['rmse']:.2f} | {m['r2']:+.3f} | {m['corr']:+.3f} |")

    bs = boot_synergy(df, np.random.default_rng(SEED), 5000)

    def summ(key):
        v = np.array(bs[key], float); v = v[np.isfinite(v)]
        lo, hi = np.percentile(v, [2.5, 97.5])
        return v.mean(), lo, hi, (v <= 0).mean()

    out.append("\n| quantity | mean | 95% CI | p(≤0) |\n|---|--:|:-:|--:|")
    for key, name in [("r_fwt", "corr(fin+x+text)"), ("skill_fwt", "skill(fin+x+text)"),
                      ("syn_corr", "synergy(corr)"), ("syn_skill", "synergy(MSE-skill)")]:
        mn, lo, hi, p = summ(key)
        out.append(f"| {name} | {mn:+.3f} | [{lo:+.3f}, {hi:+.3f}] | {p:.3f} |")
    p_surr = shuffle_company_surrogate(df, "fin+x+text", np.random.default_rng(SEED), 5000)
    verdict = "✅ firm-specific" if p_surr < 0.05 else "not firm-specific"
    out.append(f"\nshuffle-company surrogate (fin+x+text): **p = {p_surr:.4f}**  {verdict}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help=f"write the summary to {OUT_MD}")
    args = ap.parse_args()

    frames = load_reps("surprise_early")
    if not frames:
        sys.exit(f"no rep preds under {RUN_DIR}")
    agg = average_reps(frames)
    strong = agg[agg.tkr.isin(strong_tickers())].copy()

    out = ["# Kalshi channel — final 3-repeat result",
           f"\nmodel gpt-5.5-2026-04-23 · effort medium · reps={len(frames)} "
           f"(seeds {[f['seed'].iloc[0] for f in frames]}) · target surprise_early · BASE variant"
           "\n\nPredictions are averaged across the 3 repeats before scoring. Def 3.1 super-additivity"
           " synergy = M(fin+x+text) − [M(fin+x)+M(fin+text)−M(fin)]."]
    evaluate(agg, "FULL-O universe", out)
    evaluate(strong, "STRONG-only universe", out)
    out.append(
        "\n### Caveats (post code-review)\n"
        "- The surrogate p-value tests the COMBINED fin+x+text prediction against firm-specific Y; it does NOT isolate\n"
        "  a firm-specific Kalshi-X signal (H and Z are already firm-specific). A ladder-shuffle / X-increment test is TODO.\n"
        "- X and Z are weak alone: fin+x beats fin only marginally (R2 +0.004), fin+text alone WORSENS it. Only the\n"
        "  combination helps -- a weak super-additive direction, not significant at n=22.\n"
        "- rev_yoy is NOT n=1 (it has 22 valid targets -- the paper's Table-1 target); it was dropped on a stale read\n"
        "  and needs a re-run.\n"
        "- Classical x-baselines are degenerate for the ladder (no reliable dense scalar; COIN's implied value is even\n"
        "  unit-inconsistent) -- x_yoy is zeroed so they run but equal their x-free forms.\n"
        "- TOOL variant is blocked pipeline-wide (gpt-5.5 rejects tools+reasoning on chat-completions); BASE only.")
    text = "\n".join(out) + "\n"
    print(text)
    if args.write:
        OUT_MD.write_text(text)
        print(f"[written] {OUT_MD}")


if __name__ == "__main__":
    main()
