"""
Factor 1 — channel-agnostic LLM runner (ablation + architecture + Z-depth) in ONE pass. [ASYNC]
Run:  F1_CHANNEL=card python3 f1_21_run.py     (web: F1_CHANNEL=web)

Per post-cutoff target (REPORT_DATE > 2025-12-01; leakage-guarded), gpt-5.5 end-to-end (B):
  ablation   : fin / fin+x / fin+text / fin+x+text
  architecture: A(fin+text->score) / C(fin+x+text->feat) / B(fin+x+text end-to-end float)
  Z-depth    : z1=B(1 call) vs z2=B(2 calls)            (subset with a 2-quarters-ago call)
The fin+x+text end-to-end prediction is shared across ablation/arch-B/zdepth-z1 (one call).
Writes preds_{ch}_{ablation,arch,zdepth}.csv + run_log_{ch}.jsonl.
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from openai import AsyncOpenAI  # noqa: E402
from f1_channels import active  # noqa: E402
from f1_lib import OUT, CUTOFF, build_targets, load_txindex, fin_table, x_table  # noqa: E402
from f1_llm import AScores, BPredict, CFeatures, GPT_EFFORT, GPT_MODEL, acall  # noqa: E402

CONC = 48


async def main():
    ch = active()
    t0 = time.perf_counter()
    p = pd.read_csv(OUT / f"panel_{ch}.csv")
    ix = load_txindex()
    targets = build_targets(p, ix)
    limit = int(os.getenv("F1_LIMIT", "0"))
    if limit:
        targets = targets[:limit]
        print(f"[{ch}] SMOKE: limited to {len(targets)} targets", flush=True)
    assert all(t["report"] > CUTOFF for t in targets), "LEAKAGE GUARD"
    n2 = sum(1 for t in targets if t["text2"])
    print(f"[{ch}] targets={len(targets)} (with 2nd call={n2}) · {len({t['tkr'] for t in targets})} tickers · "
          f"model={GPT_MODEL} effort={GPT_EFFORT}", flush=True)

    client, sem = AsyncOpenAI(), asyncio.Semaphore(CONC)
    jobs = []
    for i, t in enumerate(targets):
        base = (f"Company {t['tkr']}. Predict the UPCOMING quarter ({t['fp'].date()}) REVENUE SURPRISE "
                "= (actual - consensus)/consensus, in %.\n\n")
        fin = "FINANCIAL HISTORY (FactSet, public):\n" + fin_table(t["hist"], t["row"]) + "\n\n"
        xt = x_table(t["hist"], t["row"]) + "\n\n"
        tr = "\nPRIOR-QUARTER EARNINGS CALL:\n" + t["text"]
        instr = "Predict the revenue surprise %."
        jobs.append(acall(client, sem, (i, "fin"), BPredict, base + fin + instr))
        jobs.append(acall(client, sem, (i, "fin+x"), BPredict, base + fin + xt + instr))
        jobs.append(acall(client, sem, (i, "fin+text"), BPredict, base + fin + instr + tr))
        jobs.append(acall(client, sem, (i, "fin+x+text"), BPredict, base + fin + xt + instr + tr))   # = arch B = zdepth z1
        jobs.append(acall(client, sem, (i, "A"), AScores, base + fin + "Score NEXT-quarter revenue vs the consensus path." + tr))
        jobs.append(acall(client, sem, (i, "C"), CFeatures, base + fin + xt + "Reconcile the alt-data trend with the narrative, vs consensus." + tr))
        if t["text2"]:
            tr2 = "\nTWO-QUARTERS-AGO EARNINGS CALL:\n" + t["text2"]
            jobs.append(acall(client, sem, (i, "z2"), BPredict, base + fin + xt + instr + tr + tr2))

    results, total = [], len(jobs)
    for j, fut in enumerate(asyncio.as_completed(jobs), 1):
        results.append(await fut)
        if j % 60 == 0 or j == total:
            print(f"  ... {j}/{total} calls ({time.perf_counter()-t0:.0f}s)", flush=True)
    res = {k: v for k, v, _ in results}
    cost = sum(c for _, _, c in results)

    OUT.mkdir(parents=True, exist_ok=True)
    abl, arch, zd = [], [], []
    with open(OUT / f"run_log_{ch}.jsonl", "w") as lf:
        for i, t in enumerate(targets):
            g = lambda k: res.get((i, k))                          # noqa: E731
            b = {a: g(a) for a in ("fin", "fin+x", "fin+text", "fin+x+text")}
            for a, v in b.items():
                lf.write(json.dumps({"exp": "ablation", "arm": a, "tkr": t["tkr"], "fp": str(t["fp"].date()),
                                     "true": t["true"], "pred": (v.predicted_revenue_surprise_pct if v else None)}) + "\n")
            if all(v is not None for v in b.values()):
                abl.append({"tkr": t["tkr"], "true": t["true"], "x_yoy": t["x_yoy"],
                            **{a: b[a].predicted_revenue_surprise_pct for a in b}})
            a_, c_, bb = g("A"), g("C"), g("fin+x+text")
            if a_ is not None and c_ is not None and bb is not None:
                arch.append({"tkr": t["tkr"], "true": t["true"], "x_yoy": t["x_yoy"],
                             "A_rev": a_.rev_vs_consensus, "C_rev": c_.rev_vs_consensus,
                             "B_pred": bb.predicted_revenue_surprise_pct})
            z2 = g("z2")
            if t["text2"] and bb is not None and z2 is not None:
                zd.append({"tkr": t["tkr"], "true": t["true"],
                           "z1": bb.predicted_revenue_surprise_pct, "z2": z2.predicted_revenue_surprise_pct})
    pd.DataFrame(abl).to_csv(OUT / f"preds_{ch}_ablation.csv", index=False)
    pd.DataFrame(arch).to_csv(OUT / f"preds_{ch}_arch.csv", index=False)
    pd.DataFrame(zd).to_csv(OUT / f"preds_{ch}_zdepth.csv", index=False)
    print(f"[{ch}] DONE  ablation n={len(abl)} · arch n={len(arch)} · zdepth n={len(zd)} · "
          f"COST ${cost:.2f} / {total} calls · wall {time.perf_counter()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
