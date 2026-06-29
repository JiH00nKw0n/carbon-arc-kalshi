"""
Foot Traffic — full pipeline: classical baselines (N0–N5) + LLM ablation + architecture + Z-depth.

Classical models:
  N0  per-company mean surprise (track record)
  N1  OLS on foot_yoy
  N2  OLS on Loughran-McDonald sentiment (prior-quarter call)
  N3  OLS on foot_yoy + sentiment
  N3b OLS on foot_yoy + sentiment + lagged_surprise
  N4  N3 + foot_yoy × sentiment interaction
  N5  GradientBoostingRegressor(foot_yoy, sentiment, lag_surprise)

LLM (gpt-4.1 → gpt-4o fallback):
  Ablation (4 arms):  fin / fin+x / fin+text / fin+x+text
  Architecture:
    A  text → scores (distilled) → OLS                  (fin+text→score)
    B  end-to-end float prediction                      (fin+x+text, shared with ablation)
    C  text+x → feature scores → OLS                   (fin+x+text→features)
  Z-depth:
    z1  1 prior call (same as ablation fin+x+text = B)
    z2  2 prior calls stacked

Leakage guard: LLM eval set = REPORT_DATE > 2025-12-01, prior call available, >=3 hist rows.
Skip LLM if fewer than 5 qualifying events.

Metrics: RMSE, R²_OOS, corr, corr² (calibration ceiling), MAE, sign-hit.
LLM calibration: leak-free 5-fold-by-company (a + b*raw).
Synergy (company-clustered bootstrap, B=5000, seed=2026):
  synergy = M(fin+x+text) − [M(fin+x) + M(fin+text) − M(fin)]   (positive = super-additive)

Output: factor1_traffic/outputs/results_foot.md

Run:  python3 ft_04_run.py
      GPT_MODEL=gpt-4o python3 ft_04_run.py   # force model
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import Ridge

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "factor1" / "scripts"))

# ── paths ─────────────────────────────────────────────────────────────────────
ROOT   = Path(__file__).resolve().parents[1]
DATA   = ROOT / "data"
OUT    = ROOT / "outputs"
OUT.mkdir(parents=True, exist_ok=True)

PANEL   = OUT / "panel_foot.csv"
TXINDEX = DATA / "transcript_index_foot.csv"
LM_JSON = Path(__file__).resolve().parents[2] / "lm_sentiment.json"

CUTOFF = pd.Timestamp("2025-12-01")
HIST_ROWS = 6
MAX_TX_CHARS = 48_000

# ── credentials ───────────────────────────────────────────────────────────────
load_dotenv(Path("/Users/suminkim/LinqAlpha/1_linq-platform/agent-server/.env"), override=False)
load_dotenv(Path("/Users/suminkim/LinqAlpha/.env"), override=False)

# ── LLM config ────────────────────────────────────────────────────────────────
_GPT_CANDIDATES = ["gpt-4.1", "gpt-4o"]
GPT_MODEL = os.getenv("GPT_MODEL", _GPT_CANDIDATES[0])

SYS = (
    "You are an equity revenue-surprise nowcaster. You only see information available BEFORE "
    "the upcoming quarter's earnings report; you do NOT know the actual result. The target is "
    "the REVENUE surprise = (actual - analyst consensus)/consensus, i.e. the part NOT already "
    "priced into estimates. Score the deviation from consensus expectations, not absolute "
    "fundamentals. Be calibrated and conservative. Output only the requested structured fields."
)


class BPredict(BaseModel):
    """End-to-end predicted revenue surprise %."""
    predicted_revenue_surprise_pct: float = Field(
        description="predicted (actual-consensus)/consensus in percent for the upcoming quarter.")
    confidence: int = Field(description="0..100.")
    rationale: str


class AScores(BaseModel):
    """Architecture A — LLM reads transcript only → consensus-relative scores (then OLS)."""
    rev_vs_consensus: int = Field(description="-100..+100: does the call imply NEXT-quarter revenue ABOVE(+)/BELOW(-) sell-side consensus?")
    news_not_in_consensus: int = Field(description="0..100: how much NEW info (not yet in estimates) the call carries.")
    signal_reliability: int = Field(description="0..100: guidance specificity + management credibility + low hedging.")


class CFeatures(BaseModel):
    """Architecture C — LLM reads transcript + foot_yoy → feature scores (then OLS)."""
    rev_vs_consensus: int = Field(description="-100..+100: does BOTH the call and foot traffic trend imply revenue ABOVE(+)/BELOW(-) consensus?")
    altdata_confirms_narrative: int = Field(description="-100..+100: does foot traffic trend CONFIRM(+) or CONTRADICT(-) the management narrative?")
    signal_reliability: int = Field(description="0..100: overall reliability of the combined signal.")


# ── LM sentiment ──────────────────────────────────────────────────────────────
_LM  = json.load(open(LM_JSON))
POS  = set(_LM["positive"])
NEG  = set(_LM["negative"])


def sentiment(path_str):
    try:
        words = Path(path_str).read_text().lower().split()
    except Exception:
        return np.nan
    p = sum(w.strip(".,;:!?()'\"").lstrip("-") in POS for w in words)
    n = sum(w.strip(".,;:!?()'\"").lstrip("-") in NEG for w in words)
    return (p - n) / (p + n) if (p + n) else 0.0


# ── prior call lookup ─────────────────────────────────────────────────────────
def prior_call(ix: pd.DataFrame, tkr: str, report_date: pd.Timestamp):
    c = ix[(ix.ticker == tkr) & (ix.call_date <= report_date - pd.Timedelta(days=31))]
    return None if c.empty else c.iloc[-1]


def prior_calls_k(ix: pd.DataFrame, tkr: str, report_date: pd.Timestamp, k: int = 2):
    """Return up to k most-recent prior calls (most-recent first)."""
    c = ix[(ix.ticker == tkr) & (ix.call_date <= report_date - pd.Timedelta(days=31))]
    if c.empty:
        return []
    return list(c.iloc[-k:][::-1].itertuples())  # most-recent first


def read_text(path_str):
    try:
        return Path(path_str).read_text()[:MAX_TX_CHARS]
    except Exception:
        return None


# ── metrics ───────────────────────────────────────────────────────────────────
def metrics(pred_pct, true_pct, label=""):
    pred, true = np.asarray(pred_pct, float), np.asarray(true_pct, float)
    rmse = float(np.sqrt(((true - pred) ** 2).mean()))
    sse  = ((true - pred) ** 2).sum(); sst = ((true - true.mean()) ** 2).sum()
    r2   = float(1 - sse / sst)
    r    = float(np.corrcoef(pred, true)[0, 1]) if np.std(pred) > 1e-9 else float("nan")
    mae  = float(np.abs(pred - true).mean())
    sign = float((np.sign(pred) == np.sign(true)).mean())
    return {"model": label, "n": len(pred), "rmse": rmse, "r2_oos": r2,
            "corr": r, "corr2": r * r if not np.isnan(r) else float("nan"),
            "mae": mae, "sign_hit": sign}


# ── OLS fit + predict ─────────────────────────────────────────────────────────
def ols(train_X, train_y, test_X):
    X = np.column_stack([np.ones(len(train_X)), train_X])
    b, *_ = np.linalg.lstsq(X, train_y, rcond=None)
    Xt = np.column_stack([np.ones(len(test_X)), test_X])
    return Xt @ b


# ── 5-fold by-company Platt calibration (leak-free) ──────────────────────────
def calibrate_cv(raw_preds, true_vals, company_ids):
    """
    Leak-free calibration: in each fold the calibration params are estimated
    on the OTHER companies, then applied to this company's predictions.
    Returns calibrated predictions (same length as input).
    """
    raw   = np.asarray(raw_preds, float)
    true  = np.asarray(true_vals, float)
    comps = np.asarray(company_ids)
    uniq  = np.unique(comps)
    if len(uniq) < 2:
        return raw  # can't calibrate with 1 company
    cal   = raw.copy()
    for tkr in uniq:
        test_mask  = comps == tkr
        train_mask = ~test_mask
        if train_mask.sum() < 2:
            continue
        X = raw[train_mask].reshape(-1, 1)
        y = true[train_mask]
        reg = Ridge(alpha=1.0).fit(X, y)
        cal[test_mask] = reg.predict(raw[test_mask].reshape(-1, 1))
    return cal


# ── company-clustered bootstrap ───────────────────────────────────────────────
def cluster_bootstrap(stat_fn, data, company_ids, B=5000, seed=2026):
    """Bootstrap by resampling companies (with replacement) → distribution of stat."""
    rng    = np.random.default_rng(seed)
    comps  = np.asarray(company_ids)
    uniq   = np.unique(comps)
    boot   = []
    for _ in range(B):
        samp   = rng.choice(uniq, size=len(uniq), replace=True)
        idx    = np.concatenate([np.where(comps == c)[0] for c in samp])
        boot.append(stat_fn(idx))
    return np.array(boot)


# ── fin_table prompt builder ───────────────────────────────────────────────────
def fin_table_str(hist: pd.DataFrame, target_row) -> str:
    rows = hist.tail(HIST_ROWS)
    out  = ["fiscal_q_end | actual($M) | consensus($M) | surprise%"]
    for r in rows.itertuples():
        out.append(f"{r.FE_FP_END} | {r.ACTUAL:,.0f} | {r.CONS_EARLY:,.0f} | {r.surprise_early*100:+.2f}%")
    out.append(f"{target_row.FE_FP_END} | (pending) | {target_row.CONS_EARLY:,.0f} | <- PREDICT")
    return "\n".join(out)


def x_table_str(hist: pd.DataFrame, target_row) -> str:
    out = ["FOOT TRAFFIC YoY (Carbon Arc CA0060):", "fiscal_q_end | foot_yoy%"]
    for r in hist.dropna(subset=["foot_yoy"]).tail(HIST_ROWS).itertuples():
        out.append(f"{r.FE_FP_END} | {r.foot_yoy*100:+.1f}%")
    out.append(f"{target_row.FE_FP_END} | {target_row.foot_yoy*100:+.1f}%  <- upcoming")
    return "\n".join(out)


# ── async LLM call ────────────────────────────────────────────────────────────
async def acall(client, sem, key, user_msg, model, schema=None):
    if schema is None:
        schema = BPredict
    async with sem:
        for attempt in range(5):
            try:
                comp = await client.beta.chat.completions.parse(
                    model=model,
                    messages=[{"role": "system", "content": SYS},
                               {"role": "user", "content": user_msg}],
                    response_format=schema,
                )
                return key, comp.choices[0].message.parsed
            except Exception as e:
                err_str = str(e)
                if "model_not_found" in err_str or "does not exist" in err_str:
                    return key, None
                if attempt == 4:
                    print(f"  [LLM ERR] {key}: {err_str[:120]}")
                    return key, None
                await asyncio.sleep(2 ** attempt)
        return key, None


# ── main ──────────────────────────────────────────────────────────────────────
async def run_llm(targets, model):
    """
    Run ablation (fin/fin+x/fin+text/fin+x+text) + architecture (A/B/C) + Z-depth (z1/z2).
    fin+x+text = arch B = zdepth z1 (shared call, no duplication).
    Returns dict {(i, key): parsed_obj | None}.
    """
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    sem    = asyncio.Semaphore(16)
    jobs   = []
    for i, t in enumerate(targets):
        base  = (f"Company {t['tkr']}. Predict the UPCOMING quarter ({t['fp']}) REVENUE SURPRISE "
                 "= (actual - consensus)/consensus, in %.\n\n")
        fin   = "FINANCIAL HISTORY (FactSet, public):\n" + t["fin_str"] + "\n\n"
        xt    = t["x_str"] + "\n\n"
        tr    = ("\nPRIOR-QUARTER EARNINGS CALL:\n" + t["text"]) if t["text"] else ""
        instr = "Predict the revenue surprise %."

        # ── ablation (4 arms) ──────────────────────────────────────────────────
        jobs.append(acall(client, sem, (i, "fin"),        base + fin + instr,           model))
        jobs.append(acall(client, sem, (i, "fin+x"),      base + fin + xt + instr,      model))
        jobs.append(acall(client, sem, (i, "fin+text"),   base + fin + instr + tr,      model))
        # fin+x+text = arch B = zdepth z1 (one call, shared across 3 roles)
        jobs.append(acall(client, sem, (i, "fin+x+text"), base + fin + xt + instr + tr, model))

        # ── architecture A: transcript → scores → (OLS downstream) ───────────
        if tr:
            a_prompt = (base + fin +
                        "Score the NEXT-quarter revenue outlook vs sell-side consensus "
                        "based on the earnings call below." + tr)
            jobs.append(acall(client, sem, (i, "arch_A"), a_prompt, model, schema=AScores))

        # ── architecture C: transcript + foot_yoy → feature scores → (OLS) ───
        if tr:
            c_prompt = (base + fin + xt +
                        "Reconcile the foot traffic trend with the management narrative. "
                        "Score the combined signal vs consensus." + tr)
            jobs.append(acall(client, sem, (i, "arch_C"), c_prompt, model, schema=CFeatures))

        # ── Z-depth z2: 2 prior calls ──────────────────────────────────────────
        if t.get("text2"):
            tr2 = "\nTWO-QUARTERS-AGO EARNINGS CALL:\n" + t["text2"]
            jobs.append(acall(client, sem, (i, "z2"),
                              base + fin + xt + instr + tr + tr2, model))

    t0    = time.perf_counter()
    total = len(jobs)
    res   = {}
    for j, fut in enumerate(asyncio.as_completed(jobs), 1):
        k, v   = await fut
        res[k] = v
        if j % 20 == 0 or j == total:
            print(f"  LLM calls: {j}/{total} ({time.perf_counter()-t0:.0f}s)", flush=True)

    any_success = any(v is not None for v in res.values())
    return res, any_success


def main():
    # ── 1. load panel ─────────────────────────────────────────────────────────
    p = pd.read_csv(PANEL)
    p["FE_FP_END"]   = pd.to_datetime(p["FE_FP_END"])
    p["REPORT_DATE"] = pd.to_datetime(p["REPORT_DATE"])
    p = p.sort_values(["ticker", "FE_FP_END"])
    p["lag_surprise"] = p.groupby("ticker")["surprise_early"].shift(1)

    # ── 2. load transcript index ───────────────────────────────────────────────
    ix = pd.read_csv(TXINDEX)
    ix["call_date"] = pd.to_datetime(ix["call_date"])
    ix = ix.dropna(subset=["call_date"]).sort_values(["ticker", "call_date"])

    # ── 3. join sentiment ──────────────────────────────────────────────────────
    print("Computing LM sentiment for transcripts …")
    rows = []
    for tkr, g in p.groupby("ticker"):
        g = g.sort_values("FE_FP_END")
        for row in g.itertuples():
            if pd.isna(row.foot_yoy) or pd.isna(row.surprise_early):
                continue
            pc = prior_call(ix, tkr, row.REPORT_DATE)
            hist_g = g[g.FE_FP_END < row.FE_FP_END]
            sent = sentiment(pc["path"]) if pc is not None else np.nan
            rows.append({
                "ticker":         tkr,
                "FE_FP_END":      row.FE_FP_END,
                "REPORT_DATE":    row.REPORT_DATE,
                "ACTUAL":         row.ACTUAL,
                "CONS_EARLY":     row.CONS_EARLY,
                "surprise_early": row.surprise_early,
                "foot_yoy":       row.foot_yoy,
                "lag_surprise":   row.lag_surprise,
                "n_hist":         len(hist_g),
                "sent":           sent,
                "prior_path":     pc["path"] if pc is not None else None,
                "prior_text":     read_text(pc["path"]) if pc is not None else None,
                "is_post":        (row.REPORT_DATE > CUTOFF) and (pc is not None) and (len(hist_g) >= 3),
            })
    d = pd.DataFrame(rows)
    d = d.assign(
        lag_surprise=d["lag_surprise"].fillna(d["surprise_early"].mean()),
        sent=d["sent"].fillna(0.0),
    )

    train = d[(d.REPORT_DATE <= CUTOFF)].dropna(subset=["foot_yoy", "surprise_early"]).copy()
    test  = d[d.is_post].dropna(subset=["foot_yoy", "surprise_early"]).copy()
    print(f"train (pre-cutoff)   : {len(train)} events, {train.ticker.nunique()} tickers")
    print(f"test  (post-cutoff)  : {len(test)}  events, {test.ticker.nunique()} tickers")

    # ── 4. classical baselines ─────────────────────────────────────────────────
    true_pct = test["surprise_early"].values * 100

    # N0: per-company mean track record
    cmean = train.groupby("ticker")["surprise_early"].mean()
    gmean = train["surprise_early"].mean()
    n0_pred = test.ticker.map(cmean).fillna(gmean).values * 100

    # N1: OLS foot_yoy
    Xtr1 = train["foot_yoy"].values.reshape(-1, 1)
    Xte1 = test["foot_yoy"].values.reshape(-1, 1)
    n1_pred = ols(Xtr1, train["surprise_early"].values * 100, Xte1)

    # N2: OLS sentiment
    Xtr2 = train["sent"].values.reshape(-1, 1)
    Xte2 = test["sent"].values.reshape(-1, 1)
    n2_pred = ols(Xtr2, train["surprise_early"].values * 100, Xte2)

    # N3: OLS foot_yoy + sentiment
    Xtr3 = np.column_stack([train["foot_yoy"].values, train["sent"].values])
    Xte3 = np.column_stack([test["foot_yoy"].values, test["sent"].values])
    n3_pred = ols(Xtr3, train["surprise_early"].values * 100, Xte3)

    # N3b: + lagged surprise
    Xtr3b = np.column_stack([train["foot_yoy"].values, train["sent"].values, train["lag_surprise"].values])
    Xte3b = np.column_stack([test["foot_yoy"].values, test["sent"].values, test["lag_surprise"].values])
    n3b_pred = ols(Xtr3b, train["surprise_early"].values * 100, Xte3b)

    # N4: N3 + interaction
    train["interact"] = train["foot_yoy"] * train["sent"]
    test["interact"]  = test["foot_yoy"]  * test["sent"]
    Xtr4 = np.column_stack([train["foot_yoy"].values, train["sent"].values, train["interact"].values])
    Xte4 = np.column_stack([test["foot_yoy"].values, test["sent"].values, test["interact"].values])
    n4_pred = ols(Xtr4, train["surprise_early"].values * 100, Xte4)

    # N5: GBM
    Xtr5 = np.column_stack([train["foot_yoy"].values, train["sent"].values, train["lag_surprise"].values])
    Xte5 = np.column_stack([test["foot_yoy"].values, test["sent"].values, test["lag_surprise"].values])
    gbm  = GradientBoostingRegressor(n_estimators=200, max_depth=2, learning_rate=0.05,
                                     subsample=0.8, random_state=2026)
    gbm.fit(Xtr5, train["surprise_early"].values * 100)
    n5_pred = gbm.predict(Xte5)

    classical = [
        ("N0 track-record",       n0_pred),
        ("N1 foot-OLS",           n1_pred),
        ("N2 sentiment-OLS",      n2_pred),
        ("N3 foot+sent",          n3_pred),
        ("N3b foot+sent+lag",     n3b_pred),
        ("N4 foot+sent+interact", n4_pred),
        ("N5 GBM",                n5_pred),
    ]
    classical_metrics = [metrics(pred, true_pct, nm) for nm, pred in classical]

    # ── 5. LLM targets ────────────────────────────────────────────────────────
    n_post = len(test)
    do_llm = n_post >= 5
    print(f"\nLLM pipeline: {'YES' if do_llm else 'SKIPPED (< 5 post-cutoff events)'} (n={n_post})")

    llm_metrics   = []
    llm_model_used = None
    synergy_results = {}

    if do_llm:
        # Build target dicts (include text2 for Z-depth z2)
        targets = []
        for row in test.itertuples():
            tkr   = row.ticker
            hist  = d[(d.ticker == tkr) & (d.FE_FP_END < row.FE_FP_END)].copy()
            calls = prior_calls_k(ix, tkr, row.REPORT_DATE, k=2)
            text1 = read_text(calls[0].path) if len(calls) >= 1 else ""
            text2 = read_text(calls[1].path) if len(calls) >= 2 else None
            targets.append({
                "tkr":     tkr,
                "fp":      row.FE_FP_END.date(),
                "report":  row.REPORT_DATE,
                "true":    float(row.surprise_early),
                "fin_str": fin_table_str(hist, row),
                "x_str":   x_table_str(hist, row),
                "text":    text1 or "",
                "text2":   text2,
            })

        # Try GPT models in order
        used_model = None
        llm_raw = {}
        for candidate in [GPT_MODEL] + [m for m in _GPT_CANDIDATES if m != GPT_MODEL]:
            print(f"\nTrying LLM model: {candidate} …")
            llm_raw, ok = asyncio.run(run_llm(targets, candidate))
            if ok:
                used_model = candidate
                print(f"  → using {candidate}")
                break
            else:
                print(f"  → {candidate} failed, trying next …")

        if used_model is None:
            print("  [WARN] all LLM models failed; skipping LLM section")
            do_llm = False
        else:
            llm_model_used = used_model
            ARMS = ["fin", "fin+x", "fin+text", "fin+x+text"]

            # Collect raw predictions per arm
            arm_preds_raw = {arm: [] for arm in ARMS}
            arm_true      = []
            arm_tkr       = []
            valid_idx     = []

            for i, t in enumerate(targets):
                preds = {arm: llm_raw.get((i, arm)) for arm in ARMS}
                if any(v is None for v in preds.values()):
                    continue
                for arm in ARMS:
                    arm_preds_raw[arm].append(preds[arm].predicted_revenue_surprise_pct)
                arm_true.append(t["true"] * 100)
                arm_tkr.append(t["tkr"])
                valid_idx.append(i)

            n_llm = len(arm_true)
            print(f"  LLM valid predictions: {n_llm}/{len(targets)}")

            if n_llm >= 5:
                arm_true_arr = np.array(arm_true)

                # Calibrate each ablation arm (5-fold by company)
                arm_preds_cal = {}
                for arm in ARMS:
                    raw_arr = np.array(arm_preds_raw[arm])
                    arm_preds_cal[arm] = calibrate_cv(raw_arr, arm_true_arr, arm_tkr)

                for arm in ARMS:
                    llm_metrics.append(
                        metrics(arm_preds_cal[arm], arm_true_arr, f"LLM({arm})")
                    )

                # ── Architecture A: AScores → OLS → predict ───────────────────
                arch_metrics = []
                a_rows = [(i, llm_raw.get((valid_idx[j], "arch_A")))
                          for j, i in enumerate(range(n_llm))
                          if llm_raw.get((valid_idx[j], "arch_A")) is not None]
                if len(a_rows) >= 5:
                    a_idx  = [r[0] for r in a_rows]
                    a_objs = [r[1] for r in a_rows]
                    a_X    = np.array([[o.rev_vs_consensus, o.news_not_in_consensus,
                                        o.signal_reliability] for o in a_objs], float)
                    a_true = arm_true_arr[a_idx]
                    a_tkrs = [arm_tkr[k] for k in a_idx]
                    # OLS (train = leave-one-company-out)
                    a_pred = np.full(len(a_true), np.nan)
                    uniq_c = list(set(a_tkrs))
                    for tkr_out in uniq_c:
                        te = [k for k, t in enumerate(a_tkrs) if t == tkr_out]
                        tr = [k for k, t in enumerate(a_tkrs) if t != tkr_out]
                        if len(tr) < 3:
                            continue
                        b, *_ = np.linalg.lstsq(
                            np.column_stack([np.ones(len(tr)), a_X[tr]]),
                            a_true[tr], rcond=None)
                        a_pred[te] = np.column_stack(
                            [np.ones(len(te)), a_X[te]]) @ b
                    valid_a = ~np.isnan(a_pred)
                    if valid_a.sum() >= 5:
                        arch_metrics.append(
                            metrics(a_pred[valid_a], a_true[valid_a], "Arch-A(scores→OLS)"))

                # ── Architecture C: CFeatures → OLS → predict ─────────────────
                c_rows = [(i, llm_raw.get((valid_idx[j], "arch_C")))
                          for j, i in enumerate(range(n_llm))
                          if llm_raw.get((valid_idx[j], "arch_C")) is not None]
                if len(c_rows) >= 5:
                    c_idx  = [r[0] for r in c_rows]
                    c_objs = [r[1] for r in c_rows]
                    c_X    = np.array([[o.rev_vs_consensus, o.altdata_confirms_narrative,
                                        o.signal_reliability] for o in c_objs], float)
                    c_true = arm_true_arr[c_idx]
                    c_tkrs = [arm_tkr[k] for k in c_idx]
                    c_pred = np.full(len(c_true), np.nan)
                    for tkr_out in list(set(c_tkrs)):
                        te = [k for k, t in enumerate(c_tkrs) if t == tkr_out]
                        tr = [k for k, t in enumerate(c_tkrs) if t != tkr_out]
                        if len(tr) < 3:
                            continue
                        b, *_ = np.linalg.lstsq(
                            np.column_stack([np.ones(len(tr)), c_X[tr]]),
                            c_true[tr], rcond=None)
                        c_pred[te] = np.column_stack(
                            [np.ones(len(te)), c_X[te]]) @ b
                    valid_c = ~np.isnan(c_pred)
                    if valid_c.sum() >= 5:
                        arch_metrics.append(
                            metrics(c_pred[valid_c], c_true[valid_c], "Arch-C(feat→OLS)"))

                # Arch-B = fin+x+text (already in llm_metrics)
                arch_metrics.append(
                    metrics(arm_preds_cal["fin+x+text"], arm_true_arr, "Arch-B(end-to-end)"))

                # ── Z-depth z2 ─────────────────────────────────────────────────
                zdepth_metrics = []
                z2_rows = [(j, llm_raw.get((valid_idx[j], "z2")))
                           for j in range(n_llm)
                           if llm_raw.get((valid_idx[j], "z2")) is not None]
                if len(z2_rows) >= 5:
                    z2_idx  = [r[0] for r in z2_rows]
                    z2_pred = np.array([r[1].predicted_revenue_surprise_pct for r in z2_rows])
                    z2_true = arm_true_arr[z2_idx]
                    z2_tkrs = [arm_tkr[k] for k in z2_idx]
                    z2_cal  = calibrate_cv(z2_pred, z2_true, z2_tkrs)
                    # z1 on same subset for fair comparison
                    z1_pred = arm_preds_cal["fin+x+text"][z2_idx]
                    zdepth_metrics.append(metrics(z1_pred, z2_true, "Z-depth z1 (1 call)"))
                    zdepth_metrics.append(metrics(z2_cal,  z2_true, "Z-depth z2 (2 calls)"))

                # ── synergy test (company-clustered bootstrap) ──────────────────
                tkr_arr = np.array(arm_tkr)
                true_arr = arm_true_arr

                def _corr(preds, true, idx):
                    p_, t_ = preds[idx], true[idx]
                    if np.std(p_) < 1e-9:
                        return np.nan
                    return float(np.corrcoef(p_, t_)[0, 1])

                def _mse(preds, true, idx):
                    return float(np.mean((preds[idx] - true[idx]) ** 2))

                def synergy_corr_stat(idx):
                    c_full = _corr(arm_preds_cal["fin+x+text"], true_arr, idx)
                    c_x    = _corr(arm_preds_cal["fin+x"],      true_arr, idx)
                    c_t    = _corr(arm_preds_cal["fin+text"],   true_arr, idx)
                    c_fin  = _corr(arm_preds_cal["fin"],        true_arr, idx)
                    return c_full - (c_x + c_t - c_fin)

                def synergy_mse_stat(idx):
                    m_full = _mse(arm_preds_cal["fin+x+text"], true_arr, idx)
                    m_x    = _mse(arm_preds_cal["fin+x"],      true_arr, idx)
                    m_t    = _mse(arm_preds_cal["fin+text"],   true_arr, idx)
                    m_fin  = _mse(arm_preds_cal["fin"],        true_arr, idx)
                    # synergy = additional MSE reduction beyond additive
                    return (m_fin - m_full) - ((m_fin - m_x) + (m_fin - m_t))

                print("  Running synergy bootstrap (B=5000) …")
                boot_corr = cluster_bootstrap(synergy_corr_stat, None, tkr_arr, B=5000, seed=2026)
                boot_mse  = cluster_bootstrap(synergy_mse_stat,  None, tkr_arr, B=5000, seed=2026)

                obs_corr = synergy_corr_stat(np.arange(n_llm))
                obs_mse  = synergy_mse_stat(np.arange(n_llm))
                p_corr   = float(np.mean(boot_corr >= obs_corr)) if not np.isnan(obs_corr) else float("nan")
                p_mse    = float(np.mean(boot_mse  >= obs_mse))  if not np.isnan(obs_mse)  else float("nan")

                synergy_results = {
                    "synergy_corr": obs_corr, "p_corr": p_corr,
                    "synergy_mse":  obs_mse,  "p_mse":  p_mse,
                    "n": n_llm,
                }
                print(f"  Synergy corr={obs_corr:+.4f} p={p_corr:.3f} | "
                      f"mse={obs_mse:+.4f} p={p_mse:.3f}")
            else:
                print(f"  [WARN] only {n_llm} complete LLM responses; skipping metrics")
                do_llm = False

    # ── 6. build report ────────────────────────────────────────────────────────
    hdr = (f"{'Model':<30}  {'n':>4}  {'RMSE':>7}  {'R²_OOS':>7}  "
           f"{'corr':>6}  {'corr²':>6}  {'MAE':>7}  {'sign':>5}")
    sep = "-" * 84

    def fmt_row(m):
        return (f"{m['model']:<30}  {m['n']:>4}  "
                f"{m['rmse']:>7.4f}  {m['r2_oos']:>+7.4f}  "
                f"{m['corr']:>+6.3f}  {m['corr2']:>6.4f}  "
                f"{m['mae']:>7.4f}  {m['sign_hit']:>5.3f}")

    lines = []
    lines += [
        "# Foot Traffic × Earnings Call → Revenue Surprise",
        "## Experiment: CA0060 Foot Traffic — Full Pipeline Results",
        "",
        f"- **Panel**: `panel_foot.csv` ({len(p)} rows, {p['ticker'].nunique()} tickers)",
        f"- **Train** (pre-cutoff ≤ 2025-12-01): {len(train)} events",
        f"- **Test**  (post-cutoff > 2025-12-01): {len(test)} events across {test['ticker'].nunique()} tickers",
        f"- **Transcript index**: {len(ix)} calls, {ix['ticker'].nunique()} tickers",
        "",
        "---",
        "",
        "## Classical Baselines (N0–N5)",
        "",
        hdr, sep,
    ]
    for m in classical_metrics:
        lines.append(fmt_row(m))

    if do_llm and llm_metrics:
        lines += [
            "",
            "---",
            "",
            f"## LLM Ablation ({llm_model_used}, zero-shot, calibrated)",
            "",
            hdr, sep,
        ]
        for m in llm_metrics:
            lines.append(fmt_row(m))

    if synergy_results:
        sr = synergy_results
        lines += [
            "",
            "---",
            "",
            "## Synergy Test (company-clustered bootstrap, B=5000, seed=2026)",
            "",
            "**Definition**: `synergy = M(fin+x+text) − [M(fin+x) + M(fin+text) − M(fin)]`",
            "Positive = super-additive (X and text interact beyond separate contributions).",
            "",
            "| metric | observed | p-value (one-sided) | verdict |",
            "|--------|----------|---------------------|---------|",
            f"| corr synergy | {sr['synergy_corr']:+.4f} | {sr['p_corr']:.3f} | "
            f"{'✅ significant' if sr['p_corr'] < 0.05 else '— not significant'} |",
            f"| MSE  synergy | {sr['synergy_mse']:+.4f} | {sr['p_mse']:.3f} | "
            f"{'✅ significant' if sr['p_mse'] < 0.05 else '— not significant'} |",
            "",
            f"n (LLM eval set) = {sr['n']}",
        ]
    elif do_llm:
        lines += ["", "*(synergy test skipped — too few complete LLM responses)*"]

    # ── Architecture A / B / C ─────────────────────────────────────────────────
    if do_llm and 'arch_metrics' in dir() and arch_metrics:
        lines += [
            "",
            "---",
            "",
            "## Architecture Comparison (A=distilled scores→OLS / B=end-to-end / C=feat→OLS)",
            "",
            "A: LLM reads transcript → 3 scores → leave-one-company-out OLS",
            "B: LLM reads fin+x+text → direct float (= ablation fin+x+text)",
            "C: LLM reads transcript+x → 3 scores → leave-one-company-out OLS",
            "",
            hdr, sep,
        ]
        for m in arch_metrics:
            lines.append(fmt_row(m))
        lines += [
            "",
            "*(A/C use leave-one-company-out OLS on LLM scores; "
            "B is calibrated end-to-end — same as ablation fin+x+text)*",
        ]

    # ── Z-depth ────────────────────────────────────────────────────────────────
    if do_llm and 'zdepth_metrics' in dir() and zdepth_metrics:
        lines += [
            "",
            "---",
            "",
            "## Z-depth: 1 prior call (z1) vs 2 prior calls (z2)",
            "",
            "Subset: events with a 2-quarters-ago call available.",
            "",
            hdr, sep,
        ]
        for m in zdepth_metrics:
            lines.append(fmt_row(m))
    elif do_llm:
        lines += [
            "",
            "---",
            "",
            "## Z-depth",
            "",
            "*(skipped — fewer than 5 events had a 2-quarters-ago transcript)*",
        ]

    if not do_llm:
        lines += [
            "",
            "---",
            "",
            "## LLM Ablation / Architecture / Z-depth",
            "",
            "*(skipped — post-cutoff eval set too small or all LLM calls failed)*",
        ]

    lines += ["", "---", "",
              f"*Generated by ft_04_run.py — {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}*"]
    report = "\n".join(lines)
    (OUT / "results_foot.md").write_text(report)
    print(f"\n[written] {OUT / 'results_foot.md'}")
    print()
    print(report)


if __name__ == "__main__":
    main()
