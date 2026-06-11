#!/usr/bin/env python3
"""
s_ad_icl_regression.py — in-context-learning (ICL) regression: does Claude Opus 4.8 learn
card_yoy -> rev_yoy from k in-context examples, and does MSE fall as k grows (toward OLS)?

Clean eval via the model's Jan-2026 training cutoff: examples drawn from PRE (quarter-end < 2026-01,
263 pairs), tested on POST (>= 2026-01, 49 pairs = 2026Q1/Q2) which cannot be in training.

Arms:
  anon       : numeric pairs only            'x=8.30 -> y=6.10'  (pure ICL regression)
  labeled    : ticker+quarter labels         'WMT 2025Q2: card_spend_yoy=8.30, revenue_yoy=6.10'
  synthetic  : positive control, known law y=0.6x+eps (validates the harness shows MSE↓→OLS)

k grid: 0,1,2,4,8,16,32,64,128, full-pool. R=5 random draws per k (1 for k=0 and k=full).
Concurrency: asyncio + AsyncAnthropic + semaphore. Baselines (code, no API): OLS(x→y) on the k
examples (the "right" answer ICL should approach) and predict-mean. temp=0.

Usage: python3 s_ad_icl_regression.py --smoke   (one call, prints prompt/response/parse)
       python3 s_ad_icl_regression.py --full     (full sweep → CSV + plot)
"""
import os, re, sys, json, asyncio, argparse, random
from pathlib import Path
import numpy as np, pandas as pd
from dotenv import load_dotenv
sys.path.insert(0, str(Path(__file__).resolve().parent))
import s_q_edge_tests as eq, s_t_revsurprise_factset as st

load_dotenv("/Users/junekwon/Desktop/Projects/carbon_arc/.env")
from anthropic import AsyncAnthropic

ROOT = Path("/Users/junekwon/Desktop/Projects/carbon_arc")
A = ROOT / "outputs" / "auto"
NEW_REV = "/Users/junekwon/.claude/projects/-Users-junekwon-Desktop-Projects-carbon-arc/1012a692-88a4-497e-a3d6-cfbce4dbe924/tool-results/mcp-linq-factset_query-1780538261695.txt"
RESULTS = A / "icl_regression_results.csv"
PLOT = A / "icl_mse_vs_shots.png"
MODEL = "claude-opus-4-8"
CUT = pd.Timestamp("2026-01-01")
K_GRID = [0, 1, 4, 16, 64]   # user-chosen k-shot grid
REPEATS = 5
MAXCONC = 8
client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
sem = asyncio.Semaphore(MAXCONC)

# ---------------- data ----------------
def build_real():
    ca = eq.build_ca_surprise()[["ticker", "date", "ca_yoy"]].dropna(); ca["date"] = pd.to_datetime(ca["date"])
    rev = pd.DataFrame(json.load(open(NEW_REV))["rows"]); rev["ACTUAL"] = pd.to_numeric(rev["ACTUAL"], errors="coerce")
    rev["FE_FP_END"] = pd.to_datetime(rev["FE_FP_END"]); rev["ticker"] = rev["FSYM_ID"].map(st.FSYM2TKR)
    rev = rev.dropna(subset=["ticker", "ACTUAL"])
    keep = rev.groupby(["ticker", "FSYM_ID"]).size().reset_index(name="n").sort_values("n").groupby("ticker").tail(1)
    rev = rev.merge(keep[["ticker", "FSYM_ID"]], on=["ticker", "FSYM_ID"]).sort_values(["ticker", "FE_FP_END"])
    rev["rev_yoy"] = rev.groupby("ticker")["ACTUAL"].pct_change(4)
    rev = rev.dropna(subset=["rev_yoy"])[["ticker", "FE_FP_END", "rev_yoy"]]
    parts = []
    for t in rev.ticker.unique():
        a = ca[ca.ticker == t].sort_values("date"); b = rev[rev.ticker == t].sort_values("FE_FP_END")
        if a.empty: continue
        m = pd.merge_asof(b, a[["date", "ca_yoy"]], left_on="FE_FP_END", right_on="date",
                          direction="nearest", tolerance=pd.Timedelta(days=50))
        parts.append(m)
    d = pd.concat(parts, ignore_index=True).dropna(subset=["ca_yoy", "rev_yoy"])
    d["x"] = (d["ca_yoy"] * 100); d["y"] = (d["rev_yoy"] * 100)
    for c in ["x", "y"]:
        lo, hi = d[c].quantile([.01, .99]); d[c] = d[c].clip(lo, hi)
    d["q"] = d["FE_FP_END"].dt.to_period("Q").astype(str)
    return d[["ticker", "q", "FE_FP_END", "x", "y"]]

def build_synth(n_pre=263, n_post=49, seed=0):
    rng = np.random.default_rng(seed)
    def gen(n):
        x = rng.normal(0, 7, n); y = 0.6 * x + rng.normal(0, 2.5, n)
        return x, y
    xpre, ypre = gen(n_pre); xpost, ypost = gen(n_post)
    pre = pd.DataFrame({"ticker": "SYN", "q": "PRE", "x": xpre, "y": ypre, "FE_FP_END": CUT - pd.Timedelta(days=100)})
    post = pd.DataFrame({"ticker": "SYN", "q": "POST", "x": xpost, "y": ypost, "FE_FP_END": CUT + pd.Timedelta(days=10)})
    return pd.concat([pre, post], ignore_index=True)

# ---------------- prompts ----------------
SYS_ANON = ("You are a precise numerical regression engine. You receive example (x, y) pairs sampled "
            "from a fixed unknown function y=f(x), then query x values. Infer f from the examples and "
            "predict y for each query. Reply with ONLY one line per query, exactly 'Q<i>: <number>' "
            "(y rounded to 2 decimals). No prose, no units.")
SYS_LABELED = ("You are an equity revenue nowcaster. Each example is a company-quarter with its "
               "credit-card-spend YoY (%) and the actually-reported revenue YoY (%). Infer how card "
               "growth maps to revenue growth and predict revenue_yoy (%) for each query. Reply with "
               "ONLY one line per query, exactly 'Q<i>: <number>' (revenue_yoy %, 2 decimals). No prose.")

def make_prompt(arm, ex, queries):
    if arm == "labeled":
        exl = "\n".join(f"{r.ticker} {r.q}: card_spend_yoy={r.x:.2f}, revenue_yoy={r.y:.2f}" for r in ex.itertuples())
        ql = "\n".join(f"Q{i+1}: {r.ticker} {r.q}: card_spend_yoy={r.x:.2f}, revenue_yoy=?" for i, r in enumerate(queries.itertuples()))
        body = f"EXAMPLES:\n{exl if len(ex) else '(none provided)'}\n\nQUERIES (predict revenue_yoy):\n{ql}\n\nReturn one line per query as 'Q<i>: <revenue_yoy>'."
        return SYS_LABELED, body
    else:  # anon + synthetic
        exl = "\n".join(f"x={r.x:.2f}, y={r.y:.2f}" for r in ex.itertuples())
        ql = "\n".join(f"Q{i+1}: x={r.x:.2f}" for i, r in enumerate(queries.itertuples()))
        body = f"EXAMPLES:\n{exl if len(ex) else '(none provided)'}\n\nQUERIES (predict y):\n{ql}\n\nReturn one line per query as 'Q<i>: <y>'."
        return SYS_ANON, body

def parse(text, k):
    out = {}
    for m in re.finditer(r"Q\s*(\d+)\s*[:=\-]\s*(-?\d+(?:\.\d+)?)", text):
        out[int(m.group(1))] = float(m.group(2))
    return out

# ---------------- model call ----------------
async def call(system, user):
    async with sem:
        for attempt in range(4):
            try:
                resp = await client.messages.create(model=MODEL, max_tokens=2500,
                                                    system=system, messages=[{"role": "user", "content": user}])
                return "".join(b.text for b in resp.content if hasattr(b, "text"))
            except Exception as e:
                if attempt == 3: return f"__ERROR__ {type(e).__name__}: {str(e)[:160]}"
                await asyncio.sleep(2 ** attempt)

def metrics(pred, qdf):
    yhat, ytrue = [], []
    for i, r in enumerate(qdf.itertuples()):
        if (i + 1) in pred:
            yhat.append(pred[i + 1]); ytrue.append(r.y)
    if not yhat: return dict(n=0, mse=np.nan, mae=np.nan, corr=np.nan)
    yhat = np.array(yhat); ytrue = np.array(ytrue)
    corr = np.corrcoef(yhat, ytrue)[0, 1] if len(yhat) > 2 and yhat.std() > 1e-9 else np.nan
    return dict(n=len(yhat), mse=float(((yhat - ytrue) ** 2).mean()), mae=float(np.abs(yhat - ytrue).mean()), corr=float(corr) if corr == corr else np.nan)

def baselines(ex, post):
    out = {"ols_mse": np.nan, "mean_mse": np.nan}
    if len(ex) >= 1:
        out["mean_mse"] = float(((post.y.values - ex.y.mean()) ** 2).mean())
    if len(ex) >= 2 and ex.x.std() > 1e-9:
        b1, b0 = np.polyfit(ex.x.values, ex.y.values, 1)
        out["ols_mse"] = float(((post.y.values - (b0 + b1 * post.x.values)) ** 2).mean())
    return out

async def run_task(arm, pre, post, k, rep):
    if k == 0: ex = pre.iloc[0:0]
    else:
        seed = abs(hash((arm, k, rep))) % (2**32)
        ex = pre.sample(n=min(k, len(pre)), random_state=seed)
    system, user = make_prompt(arm, ex, post)
    text = await call(system, user)
    if text.startswith("__ERROR__"):
        return {"arm": arm, "N": k, "repeat": rep, "err": text[:120], **metrics({}, post), **baselines(ex, post)}
    pred = parse(text, k)
    return {"arm": arm, "N": k, "repeat": rep, "err": "", **metrics(pred, post), **baselines(ex, post)}

# ---------------- orchestration ----------------
async def smoke():
    real = build_real(); pre = real[real.FE_FP_END < CUT]; post = real[real.FE_FP_END >= CUT]
    syn = build_synth(); sp = syn[syn.q == "PRE"]; spo = syn[syn.q == "POST"]
    ex = sp.sample(8, random_state=1)
    system, user = make_prompt("synthetic", ex, spo.head(8))
    print("=== SYSTEM ===\n", system, "\n=== USER ===\n", user[:1200], "\n...")
    text = await call(system, user)
    print("\n=== RAW RESPONSE ===\n", text[:1500])
    pred = parse(text, 8); print("\nparsed:", pred)
    print("metrics:", metrics(pred, spo.head(8)), "| baselines:", baselines(ex, spo.head(8)))

async def full():
    real = build_real(); pre = real[real.FE_FP_END < CUT].reset_index(drop=True); post = real[real.FE_FP_END >= CUT].reset_index(drop=True)
    syn = build_synth(); sp = syn[syn.q == "PRE"].reset_index(drop=True); spo = syn[syn.q == "POST"].reset_index(drop=True)
    pool = len(pre)
    grid = [k for k in K_GRID if k <= pool]
    print(f"PRE pool={pool}, POST test={len(post)}; k grid={grid}")
    arms = {"anon": (pre, post), "labeled": (pre, post), "synthetic": (sp, spo)}
    tasks = []
    for arm, (P, Q) in arms.items():
        for k in grid:
            reps = 1 if (k == 0 or k >= len(P)) else REPEATS
            for r in range(reps):
                tasks.append(run_task(arm, P, Q, k, r))
    print(f"{len(tasks)} model calls (conc={MAXCONC}, model={MODEL})...")
    rows = await asyncio.gather(*tasks)
    df = pd.DataFrame(rows)
    df.to_csv(RESULTS, index=False)
    print(f"[saved] {RESULTS}  ({len(df)} rows)")
    # aggregate + plot
    agg = df.groupby(["arm", "N"]).agg(mse=("mse", "mean"), ols=("ols_mse", "mean"),
                                       mean_base=("mean_mse", "mean"), corr=("corr", "mean"),
                                       nparse=("n", "mean")).reset_index()
    print("\n=== MSE by arm × k ===")
    print(agg.to_string(index=False))
    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        fig, axes = plt.subplots(1, 2, figsize=(13, 5))
        for ax, arms_show, title in [(axes[0], ["anon", "labeled"], "Real: card_yoy → rev_yoy"),
                                     (axes[1], ["synthetic"], "Synthetic control: y=0.6x+ε")]:
            for arm in arms_show:
                s = agg[agg.arm == arm].sort_values("N")
                ax.plot(s.N.clip(lower=0.5), s.mse, "o-", label=f"ICL ({arm})")
                ax.plot(s.N.clip(lower=0.5), s.ols, "s--", alpha=.6, label=f"OLS ({arm})")
                ax.plot(s.N.clip(lower=0.5), s.mean_base, ":", alpha=.5, label=f"predict-mean ({arm})")
            ax.set_xscale("log"); ax.set_xlabel("k (in-context examples)"); ax.set_ylabel("MSE on POST"); ax.set_title(title); ax.legend(fontsize=8)
        plt.tight_layout(); plt.savefig(PLOT, dpi=110); print(f"[saved] {PLOT}")
    except Exception as e:
        print("plot skipped:", e)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--smoke", action="store_true"); ap.add_argument("--full", action="store_true")
    args = ap.parse_args()
    asyncio.run(smoke() if args.smoke or not args.full else full())
