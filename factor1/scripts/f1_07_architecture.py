"""
Factor 1 — architecture comparison A / C vs B (does end-to-end beat distilled scores?).  [ASYNC]

F3's signature finding: distilling the LLM to interpretable scores (A: text→score, C: web+text→
features) and regressing them KILLS the signal; only end-to-end B (LLM predicts the % directly)
works. This replays it for web. All on the SAME post-cutoff targets as f1_05.

  A : fin + TEXT only      → AScores.rev_vs_consensus   (-100..+100, then correlated to truth)
  C : fin + WEB + TEXT     → CFeatures.rev_vs_consensus
  B : fin + WEB + TEXT     → BPredict.predicted_revenue_surprise_pct (end-to-end)
Eval: corr(score, true) + label-shuffle p, and nested in-sample R² (web_yoy + each distilled score).

OUT: factor1/outputs/f1_architecture.md
"""
import asyncio
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from openai import AsyncOpenAI

sys.path.insert(0, str(Path(__file__).resolve().parent))
from f1_config import OUT  # noqa: E402
from f1_llm import AScores, BPredict, CFeatures, GPT_MODEL, acall  # noqa: E402
from f1_05_ablation import build_targets, fin_table, load_panel, load_txindex, web_table  # noqa: E402

CONC = 48


async def main():
    t0 = time.perf_counter()
    p, ix = load_panel(), load_txindex()
    targets = build_targets(p, ix)
    print(f"targets={len(targets)} · {len({t['tkr'] for t in targets})} tickers · model={GPT_MODEL}")

    client, sem = AsyncOpenAI(), asyncio.Semaphore(CONC)
    jobs = []
    for i, t in enumerate(targets):
        base = (f"Company {t['tkr']}. The UPCOMING quarter is {t['fp'].date()}. "
                "Target = revenue surprise = (actual - consensus)/consensus, in %.\n\n")
        fin = "FINANCIAL HISTORY (FactSet, public):\n" + fin_table(t["hist"], t["row"]) + "\n\n"
        web = "WEB-TRAFFIC HISTORY (Carbon Arc, website users YoY):\n" + web_table(t["hist"], t["row"]) + "\n\n"
        tr = "\nPRIOR-QUARTER EARNINGS CALL:\n" + t["text"]
        jobs.append(acall(client, sem, (i, "A"), AScores, base + fin + "Score NEXT-quarter revenue vs the consensus path." + tr))
        jobs.append(acall(client, sem, (i, "C"), CFeatures, base + fin + web + "Reconcile the web-traffic trend with the narrative, vs consensus." + tr))
        jobs.append(acall(client, sem, (i, "B"), BPredict, base + fin + web + "Use the full history + call to predict the revenue surprise %." + tr))

    results, total = [], len(jobs)
    for j, fut in enumerate(asyncio.as_completed(jobs), 1):
        results.append(await fut)
        if j % 45 == 0 or j == total:
            print(f"  ... {j}/{total} ({time.perf_counter()-t0:.0f}s)", flush=True)
    res = {k: v for k, v, _ in results}
    cost = sum(c for _, _, c in results)

    rec = []
    for i, t in enumerate(targets):
        a, c, b = res[(i, "A")], res[(i, "C")], res[(i, "B")]
        if a is None or c is None or b is None:
            continue
        rec.append({"tkr": t["tkr"], "true": t["true"], "web_yoy": t["web_yoy"],
                    "A_rev": a.rev_vs_consensus, "C_rev": c.rev_vs_consensus,
                    "B_pred": b.predicted_revenue_surprise_pct})
    df = pd.DataFrame(rec)

    def corr(x):
        m = df[[x, "true"]].dropna(); return np.corrcoef(m[x], m["true"])[0, 1]

    def perm_p(x, n=5000):
        m = df[[x, "true"]].dropna(); r0 = abs(np.corrcoef(m[x], m["true"])[0, 1])
        rng = np.random.default_rng(2026); y = m["true"].values
        return (sum(abs(np.corrcoef(m[x].values, rng.permutation(y))[0, 1]) >= r0 for _ in range(n)) + 1) / (n + 1)

    def ols_r2(cols):
        m = df[["true"] + cols].dropna()
        X = np.column_stack([np.ones(len(m))] + [m[c].values for c in cols])
        bb, *_ = np.linalg.lstsq(X, m["true"].values, rcond=None); yh = X @ bb
        return 1 - ((m["true"].values - yh) ** 2).sum() / ((m["true"].values - m["true"].mean()) ** 2).sum()

    L = ["# Factor 1 — architecture A / C vs B (distilled scores vs end-to-end)\n",
         f"n={len(df)} · {df.tkr.nunique()} tickers\n",
         f"  {'arch':20s} corr    p_perm",
         f"  {'A  (text→score)':20s} {corr('A_rev'):+.3f}  {perm_p('A_rev'):.3f}",
         f"  {'C  (web+text→feat)':20s} {corr('C_rev'):+.3f}  {perm_p('C_rev'):.3f}",
         f"  {'B  (end-to-end)':20s} {corr('B_pred'):+.3f}  {perm_p('B_pred'):.3f}",
         "\n  nested in-sample R² (does the distilled score add to web_yoy?):",
         f"    web_yoy only       : {ols_r2(['web_yoy']):.3f}",
         f"    web_yoy + A_rev    : {ols_r2(['web_yoy','A_rev']):.3f}",
         f"    web_yoy + C_rev    : {ols_r2(['web_yoy','C_rev']):.3f}",
         f"    web_yoy + B_pred   : {ols_r2(['web_yoy','B_pred']):.3f}",
         f"\nCOST ${cost:.2f} / {len(jobs)} calls · wall {time.perf_counter()-t0:.0f}s"]
    out = "\n".join(L); print("\n" + out)
    (OUT / "f1_architecture.md").write_text("<!-- f1_07_architecture.py -->\n```\n" + out + "\n```\n")
    df.to_csv(OUT / "run_architecture_preds.csv", index=False)


if __name__ == "__main__":
    asyncio.run(main())
