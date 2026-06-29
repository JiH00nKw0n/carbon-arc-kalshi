"""
Foot Traffic — LLM runner (wrapper over f1_21_run via ft_lib).
Run:  python ft_21_run.py
Writes: factor1_traffic/outputs/preds_foot_{ablation,arch,zdepth}.csv + run_log_foot.jsonl

Uses gpt-5.5-2026-04-23 (same as web/card) via f1_llm.py.
OPENAI_API_KEY loaded from LinqAlpha/.env (resolved relative to this file's location)
"""
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# load our .env first (overrides f1_llm's hardcoded junekwon path)
load_dotenv(Path(__file__).resolve().parents[3] / ".env", override=True)   # LinqAlpha/.env
load_dotenv(Path.home() / ".env", override=False)                          # fallback

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ft_lib  # noqa: E402  — patches paths + cfg

# now import and run f1_21_run's main with foot context
_F1_SCRIPTS = Path(__file__).resolve().parents[2] / "factor1" / "scripts"
sys.path.insert(0, str(_F1_SCRIPTS))

import asyncio
import json
import time

import pandas as pd
from openai import AsyncOpenAI

from ft_lib import OUT, CUTOFF, build_targets, load_txindex, fin_table, x_table, active  # noqa: E402
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
        fin  = "FINANCIAL HISTORY (FactSet, public):\n" + fin_table(t["hist"], t["row"]) + "\n\n"
        xt   = x_table(t["hist"], t["row"]) + "\n\n"
        tr   = "\nPRIOR-QUARTER EARNINGS CALL:\n" + t["text"]
        instr = "Predict the revenue surprise %."
        jobs.append(acall(client, sem, (i, "fin"),        BPredict, base + fin + instr))
        jobs.append(acall(client, sem, (i, "fin+x"),      BPredict, base + fin + xt + instr))
        jobs.append(acall(client, sem, (i, "fin+text"),   BPredict, base + fin + instr + tr))
        jobs.append(acall(client, sem, (i, "fin+x+text"), BPredict, base + fin + xt + instr + tr))
        jobs.append(acall(client, sem, (i, "A"), AScores,
                          base + fin + "Score NEXT-quarter revenue vs the consensus path." + tr))
        jobs.append(acall(client, sem, (i, "C"), CFeatures,
                          base + fin + xt + "Reconcile the alt-data trend with the narrative, vs consensus." + tr))
        if t["text2"]:
            tr2 = "\nTWO-QUARTERS-AGO EARNINGS CALL:\n" + t["text2"]
            jobs.append(acall(client, sem, (i, "z2"), BPredict, base + fin + xt + instr + tr + tr2))

    results, total = [], len(jobs)
    for j, fut in enumerate(asyncio.as_completed(jobs), 1):
        results.append(await fut)
        if j % 60 == 0 or j == total:
            print(f"  ... {j}/{total} calls ({time.perf_counter()-t0:.0f}s)", flush=True)
    res   = {k: v for k, v, _ in results}
    cost  = sum(c for _, _, c in results)

    OUT.mkdir(parents=True, exist_ok=True)
    abl, arch, zd = [], [], []
    with open(OUT / f"run_log_{ch}.jsonl", "w") as lf:
        for i, t in enumerate(targets):
            g = lambda k: res.get((i, k))  # noqa: E731
            b = {a: g(a) for a in ("fin", "fin+x", "fin+text", "fin+x+text")}
            for a, v in b.items():
                lf.write(json.dumps({"exp": "ablation", "arm": a, "tkr": t["tkr"],
                                     "fp": str(t["fp"].date()), "true": t["true"],
                                     "pred": (v.predicted_revenue_surprise_pct if v else None)}) + "\n")
                if v is not None:
                    abl.append({"tkr": t["tkr"], "fp": str(t["fp"].date()), "true": t["true"],
                                "x_yoy": t["x_yoy"],
                                "fin": (g("fin").predicted_revenue_surprise_pct if g("fin") else None),
                                "fin+x": (g("fin+x").predicted_revenue_surprise_pct if g("fin+x") else None),
                                "fin+text": (g("fin+text").predicted_revenue_surprise_pct if g("fin+text") else None),
                                "fin+x+text": (g("fin+x+text").predicted_revenue_surprise_pct if g("fin+x+text") else None)})
                    break
            av, cv, bv = g("A"), g("C"), g("fin+x+text")
            if any(x is not None for x in (av, cv, bv)):
                arch.append({"tkr": t["tkr"], "fp": str(t["fp"].date()), "true": t["true"],
                             "A_rev": (av.rev_vs_consensus if av else None),
                             "C_rev": (cv.rev_vs_consensus if cv else None),
                             "B_pred": (bv.predicted_revenue_surprise_pct if bv else None)})
            z2v = g("z2")
            if bv is not None and z2v is not None:
                zd.append({"tkr": t["tkr"], "fp": str(t["fp"].date()), "true": t["true"],
                           "z1": bv.predicted_revenue_surprise_pct,
                           "z2": z2v.predicted_revenue_surprise_pct})

    # deduplicate ablation rows (one row per target)
    abl_df = pd.DataFrame(abl).drop_duplicates(subset=["tkr", "fp"])
    abl_df.to_csv(OUT / f"preds_{ch}_ablation.csv", index=False)
    pd.DataFrame(arch).to_csv(OUT / f"preds_{ch}_arch.csv", index=False)
    pd.DataFrame(zd).to_csv(OUT / f"preds_{ch}_zdepth.csv", index=False)

    print(f"\n[{ch}] ablation={len(abl_df)} · arch={len(arch)} · zdepth={len(zd)} · "
          f"cost=${cost:.2f} · {time.perf_counter()-t0:.0f}s")
    for f in [OUT / f"preds_{ch}_ablation.csv", OUT / f"preds_{ch}_arch.csv",
              OUT / f"preds_{ch}_zdepth.csv"]:
        print(f"  [written] {f}")


if __name__ == "__main__":
    asyncio.run(main())
