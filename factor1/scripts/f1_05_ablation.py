"""
Factor 1 — complementarity ablation (web × earnings-call → revenue surprise).  [ASYNC]

Port of factor3/scripts/s_aj_ablation.py with X = CARD → WEB. 4 arms, all B end-to-end
(gpt-5.5 structured float), identical financial baseline table across arms:
  1. fin            — financial track-record table only
  2. fin+web        — + web-traffic YoY table (X)
  3. fin+text       — + prior-quarter earnings call (Z)
  4. fin+web+text   — + both
Synergy = corr(fin+web+text) − [corr(fin+web)+corr(fin+text)−corr(fin)].

Eval set = post-cutoff events (REPORT_DATE > 2025-12-01) so gpt-5.5 (cutoff 2025-12-01)
cannot have memorized the actual. Full logging → outputs/run_log_ablation.jsonl.
Run:  python3 factor1/scripts/f1_05_ablation.py
"""
import asyncio
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from openai import AsyncOpenAI

sys.path.insert(0, str(Path(__file__).resolve().parent))
from f1_config import CUTOFF, OUT  # noqa: E402
from f1_llm import BPredict, GPT_EFFORT, GPT_MODEL, MAX_TRANSCRIPT_CHARS, acall  # noqa: E402

PANEL = OUT / "panel_web.csv"
TXINDEX = Path(__file__).resolve().parents[1] / "data" / "transcript_index_web.csv"
HIST_ROWS = 6
CONC = 48
ARMS = ["fin", "fin+web", "fin+text", "fin+web+text"]


def load_panel():
    p = pd.read_csv(PANEL)
    p["FE_FP_END"] = pd.to_datetime(p["FE_FP_END"])
    p["REPORT_DATE"] = pd.to_datetime(p["REPORT_DATE"])
    return p.sort_values(["ticker", "FE_FP_END"])


def load_txindex():
    ix = pd.read_csv(TXINDEX)
    ix["call_date"] = pd.to_datetime(ix["call_date"])
    return ix.sort_values(["ticker", "call_date"])


def prior_call(ix, tkr, report_date):
    """Z = most recent call held >= 31d before the print (the prior-quarter call)."""
    c = ix[(ix.ticker == tkr) & (ix.call_date <= report_date - pd.Timedelta(days=31))]
    return None if c.empty else c.iloc[-1]["path"]


def fin_table(hist, target):
    rows = hist.tail(HIST_ROWS)
    out = ["fiscal_q_end | actual($M) | consensus($M) | surprise%"]
    for r in rows.itertuples():
        out.append(f"{r.FE_FP_END.date()} | {r.ACTUAL:,.0f} | {r.CONS_EARLY:,.0f} | {r.surprise_early*100:+.2f}%")
    out.append(f"{target.FE_FP_END.date()} | (pending) | {target.CONS_EARLY:,.0f} | <- PREDICT")
    return "\n".join(out)


def web_table(hist, target):
    rows = hist.dropna(subset=["web_yoy"]).tail(HIST_ROWS)
    out = ["fiscal_q_end | web_users_yoy"]
    for r in rows.itertuples():
        out.append(f"{r.FE_FP_END.date()} | {r.web_yoy*100:+.1f}%")
    out.append(f"{target.FE_FP_END.date()} | {target.web_yoy*100:+.1f}%  <- upcoming")
    return "\n".join(out)


def read_text(path):
    try:
        return Path(path).read_text()[:MAX_TRANSCRIPT_CHARS]
    except Exception:
        return None


def build_targets(p, ix):
    targets = []
    for tkr, g in p.groupby("ticker"):
        g = g.sort_values("FE_FP_END")
        for row in g[g.REPORT_DATE > CUTOFF].itertuples():
            if pd.isna(row.web_yoy):
                continue
            hist = g[g.FE_FP_END < row.FE_FP_END]
            path = prior_call(ix, tkr, row.REPORT_DATE)
            if path is None or len(hist) < 3:
                continue
            txt = read_text(path)
            if not txt:
                continue
            targets.append({"tkr": tkr, "fp": row.FE_FP_END, "report": row.REPORT_DATE,
                            "true": float(row.surprise_early), "web_yoy": float(row.web_yoy),
                            "hist": hist, "row": row, "text": txt, "call_path": path})
    return targets


async def main():
    t0 = time.perf_counter()
    p, ix = load_panel(), load_txindex()
    targets = build_targets(p, ix)
    assert all(t["report"] > CUTOFF for t in targets), "LEAKAGE GUARD"
    print(f"targets={len(targets)} post-cutoff events · {len({t['tkr'] for t in targets})} tickers · "
          f"arms={ARMS} · model={GPT_MODEL} effort={GPT_EFFORT}")

    client, sem = AsyncOpenAI(), asyncio.Semaphore(CONC)
    jobs, meta = [], {}
    for i, t in enumerate(targets):
        base = (f"Company {t['tkr']}. Predict the UPCOMING quarter ({t['fp'].date()}) REVENUE SURPRISE "
                "= (actual - consensus)/consensus, in %.\n\n")
        fin = "FINANCIAL HISTORY (FactSet, public):\n" + fin_table(t["hist"], t["row"]) + "\n\n"
        web = "WEB-TRAFFIC HISTORY (Carbon Arc alt-data, website users YoY):\n" + web_table(t["hist"], t["row"]) + "\n\n"
        tr = "\nPRIOR-QUARTER EARNINGS CALL:\n" + t["text"]
        instr = "Predict the revenue surprise %."
        prompts = {
            "fin": base + fin + instr,
            "fin+web": base + fin + web + instr,
            "fin+text": base + fin + instr + tr,
            "fin+web+text": base + fin + web + instr + tr,
        }
        for arm in ARMS:
            jobs.append(acall(client, sem, (i, arm), BPredict, prompts[arm]))
        meta[i] = {"tkr": t["tkr"], "fp": str(t["fp"].date()), "true": t["true"],
                   "web_yoy": t["web_yoy"], "call_path": Path(t["call_path"]).name}

    results, total = [], len(jobs)
    for j, fut in enumerate(asyncio.as_completed(jobs), 1):
        results.append(await fut)
        if j % 40 == 0 or j == total:
            print(f"  ... {j}/{total} calls done ({time.perf_counter()-t0:.0f}s)", flush=True)
    res = {k: (pp, c) for k, pp, c in results}
    cost = sum(c for _, _, c in results)

    OUT.mkdir(parents=True, exist_ok=True)
    rec = []
    with open(OUT / "run_log_ablation.jsonl", "w") as lf:
        for i in range(len(targets)):
            m = meta[i]; row = {"tkr": m["tkr"], "true": m["true"], "web_yoy": m["web_yoy"]}
            ok = True
            for arm in ARMS:
                b, _ = res[(i, arm)]
                lf.write(json.dumps({"arm": arm, "ticker": m["tkr"], "fp": m["fp"], "true": m["true"],
                                     "web_yoy": m["web_yoy"], "call": m["call_path"],
                                     "pred": (b.predicted_revenue_surprise_pct if b else None),
                                     "confidence": (b.confidence if b else None),
                                     "rationale": (b.rationale if b else None)}) + "\n")
                if b is None:
                    ok = False
                else:
                    row[arm] = b.predicted_revenue_surprise_pct
            if ok:
                rec.append(row)
    df = pd.DataFrame(rec)
    df.to_csv(OUT / "run_ablation_preds.csv", index=False)

    def perm_p(col, n=5000):
        m = df[[col, "true"]].dropna(); r0 = abs(np.corrcoef(m[col], m["true"])[0, 1])
        rng = np.random.default_rng(2026); yv = m["true"].values
        return (sum(abs(np.corrcoef(m[col].values, rng.permutation(yv))[0, 1]) >= r0 for _ in range(n)) + 1) / (n + 1)

    print(f"\n{'='*72}\nFACTOR 1 ABLATION (n={len(df)}; truth mean={df.true.mean()*100:+.2f}% pos={df.true.gt(0).mean():.2f})")
    print(f"  web_yoy → true (X-only corr) = {np.corrcoef(df.web_yoy, df.true)[0,1]:+.3f}")
    print(f"  {'arm':16s}  corr    R²     MAE   sign  p_perm")
    cr = {}
    for arm in ARMS:
        m = df[[arm, "true"]].dropna()
        r = np.corrcoef(m[arm], m["true"])[0, 1]; cr[arm] = r
        mae = (m[arm] - m["true"] * 100).abs().mean()
        hit = (np.sign(m[arm]) == np.sign(m["true"])).mean()
        print(f"  {arm:16s}  {r:+.3f}  {r*r:.3f}  {mae:.2f}  {hit:.2f}  {perm_p(arm):.3f}")
    syn = cr["fin+web+text"] - (cr["fin+web"] + cr["fin+text"] - cr["fin"])
    print("\n  complementarity (corr):")
    print(f"    web adds  (fin→fin+web)        Δ{cr['fin+web']-cr['fin']:+.3f}")
    print(f"    text adds (fin→fin+text)       Δ{cr['fin+text']-cr['fin']:+.3f}")
    print(f"    text on web (fin+web→+text)    Δ{cr['fin+web+text']-cr['fin+web']:+.3f}")
    print(f"    web on text (fin+text→+web)    Δ{cr['fin+web+text']-cr['fin+text']:+.3f}")
    print(f"    >>> SYNERGY (super-additivity) = {syn:+.3f}")
    print(f"\nCOST ${cost:.2f} / {len(jobs)} calls · wall {time.perf_counter()-t0:.0f}s · preds -> {OUT/'run_ablation_preds.csv'}")


if __name__ == "__main__":
    asyncio.run(main())
