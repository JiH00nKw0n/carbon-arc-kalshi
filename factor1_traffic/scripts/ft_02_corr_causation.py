"""
Foot Traffic — correlation / causation battery (H1).

Mirrors f1_02_corr_causation.py exactly, with foot_yoy / foot_yoy_3m instead of web_yoy.
Verdict gate = company-clustered bootstrap (p_boot<0.05) AND shuffle-company surrogate (p_surr<0.05).

OUT: traffic/outputs/ft_corr_causation.md  +  traffic/outputs/corr_results.csv

Usage:
    python ft_02_corr_causation.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# reuse f1_stats directly
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "factor1" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from f1_stats import cluster_boot, surrogate, within_company_corr  # noqa: E402
from ft_config import OUT  # noqa: E402

P = OUT / "panel_foot.csv"
rows_md, rec = [], []


def log(s=""):
    print(s); rows_md.append(s)


def test(d, x, y, tag):
    r, pb, n = cluster_boot(d, x, y)
    ps = surrogate(d, x, y, r) if not np.isnan(r) else np.nan
    verdict = "✅" if (not np.isnan(ps) and ps < 0.05 and pb < 0.05) else (
        "·" if np.isnan(ps) else "❌")
    log(f"  {tag:38s} r={r:+.3f}  n={n:>3}  p_boot={pb:.3f}  p_surr={ps:.3f}  {verdict}")
    rec.append({"test": tag, "x": x, "y": y,
                "r": round(r, 4) if not np.isnan(r) else None,
                "n": n,
                "p_boot": round(pb, 4) if not np.isnan(pb) else None,
                "p_surr": round(ps, 4) if not np.isnan(ps) else None,
                "pass": verdict == "✅"})
    return r, pb, ps


def main():
    d = pd.read_csv(P)
    d["FE_FP_END"] = pd.to_datetime(d["FE_FP_END"])
    d = d.sort_values(["ticker", "FE_FP_END"])
    d["foot_yoy_lag1"] = d.groupby("ticker")["foot_yoy"].shift(1)

    log("# Foot Traffic (CA0060) — correlation / causation\n")
    log(f"panel: {len(d)} events · {d.ticker.nunique()} tickers · "
        f"{d.FE_FP_END.min().date()}..{d.FE_FP_END.max().date()}")
    log(f"surprise_early: mean={d.surprise_early.mean()*100:+.2f}%  "
        f"sd={d.surprise_early.std()*100:.2f}%  "
        f"pos-rate={(d.surprise_early>0).mean():.2f}\n")

    log("## LEVEL — does foot traffic track revenue growth? (sanity)")
    test(d, "foot_yoy", "rev_yoy", "foot_yoy → rev_yoy")

    log("\n## SURPRISE — does foot traffic carry info BEYOND consensus? (THE test)")
    rE, pbE, psE = test(d, "foot_yoy", "surprise_early", "foot_yoy → surprise_early")
    test(d, "foot_yoy", "surprise_print", "foot_yoy → surprise_print")
    wc = within_company_corr(d, "foot_yoy", "surprise_early")
    log(f"  within-company corr(foot_yoy, surprise_early) = {wc:+.3f}  "
        f"(firm-mean removed → is it the right quarter, not just the right firm?)")

    log("\n## TRANSFORM robustness → surprise_early")
    for x in ["foot_yoy", "foot_yoy_3m"]:
        test(d, x, "surprise_early", f"{x} → surprise_early")

    log("\n## SPLIT by foot-traffic-revenue-dominance tier → surprise_early")
    for s in ["strong", "moderate"]:
        sub = d[d.strength == s]
        if len(sub) >= 5:
            test(sub, "foot_yoy", "surprise_early", f"[{s}] foot_yoy → surprise_early")
        else:
            log(f"  [{s}] skipped (n={len(sub)} < 5)")

    log("\n## OUTLIER ROBUSTNESS — DLTR FY2025Q1 structural break")
    log("  Pre-declared rule: exclude quarters with structural breaks (M&A / spin-off) where")
    log("  consensus was set on a pre-restructuring basis, making surprise non-comparable.")
    log("  DLTR 2025-01-31: Family Dollar spin-off — ACTUAL=$4,997M (DollarTree standalone)")
    log("  vs CONS_EARLY=$8,238M (pre-spinoff combined) → surprise=-39.3% is an artifact.")
    log("  Correct treatment: remove ONLY that 1 quarter; DLTR's other 9 quarters remain.")
    # [pre-declared] only the contaminated quarter is dropped, not the whole company
    d_drop1 = d[~((d.ticker == "DLTR") & (d.FE_FP_END == "2025-01-31"))]
    r1, pb1, ps1 = test(d_drop1, "foot_yoy", "surprise_early",
                        "[drop DLTR 2025-01-31] foot_yoy → surprise_early")
    # for reference: full-company exclusion (shows why this is wrong)
    d_no_dltr = d[d.ticker != "DLTR"]
    rND, pbND, psND = test(d_no_dltr, "foot_yoy", "surprise_early",
                           "[no DLTR all] foot_yoy → surprise_early")

    log("\n## LEAD/LAG — does prior-quarter foot traffic lead the surprise?")
    test(d, "foot_yoy_lag1", "surprise_early", "foot_yoy(t-1) → surprise_early")

    log("\n## VERDICT")
    log("  Headline uses [drop DLTR 2025-01-31] per pre-declared structural-break rule.")
    if not np.isnan(psE) and psE < 0.05 and pbE < 0.05:
        log(f"  ✅ Full panel passes (r={rE:+.3f}, p_boot={pbE:.3f}, p_surr={psE:.3f}).")
    if not np.isnan(ps1) and ps1 < 0.05 and pb1 < 0.05:
        log(f"  ✅ [drop DLTR 2025-01-31] passes: r={r1:+.3f}, p_boot={pb1:.3f}, p_surr={ps1:.3f}.")
    else:
        log(f"  ❌ NULL (drop-1-qtr): r={r1:+.3f}, p_boot={pb1:.3f}, p_surr={ps1:.3f}.")
        log(f"  Full panel (contaminated): r={rE:+.3f}, p_boot={pbE:.3f}, p_surr={psE:.3f}.")
    log(f"  [no DLTR all] reference (wrong — drops 9 clean quarters): r={rND:+.3f}, p_boot={pbND:.3f}.")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "ft_corr_causation.md").write_text(
        "<!-- generated by ft_02_corr_causation.py -->\n```\n" + "\n".join(rows_md) + "\n```\n")
    pd.DataFrame(rec).to_csv(OUT / "corr_results.csv", index=False)
    log(f"\n[written] {OUT / 'ft_corr_causation.md'} · {OUT / 'corr_results.csv'}")


if __name__ == "__main__":
    main()
