"""
Factor 1 — classical (non-LLM) statistical baselines vs the LLM ablation.

F3's N0–N3 grid, realized for web. Fit on PRE-cutoff events, predict the SAME post-cutoff
test set the LLM saw (report>2025-12-01, prior-call available, >=3 history) → fair zero-data-leak
comparison (LLM is zero-shot on post-cutoff; OLS is trained only on pre-cutoff).

Models:
  N0 naive    — per-company mean past surprise (track record); global mean fallback.
  N1 web-OLS  — surprise ~ web_yoy.
  N2 sent-OLS — surprise ~ net LM-lexicon sentiment of the prior-quarter call.
  N3 web+sent — surprise ~ web_yoy + sentiment.
  N3b +lag    — surprise ~ web_yoy + sentiment + lagged surprise.
Reported next to the LLM arms (from run_ablation_preds.csv). OUT: factor1/outputs/f1_baselines.md
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from f1_config import CUTOFF, OUT  # noqa: E402

PANEL = OUT / "panel_web.csv"
TXINDEX = Path(__file__).resolve().parents[1] / "data" / "transcript_index_web.csv"
ABL = OUT / "run_ablation_preds.csv"

# Sentiment lexicon = Loughran-McDonald Master Dictionary (sraf.nd.edu; L&M 2011 JF 66(1):35-65).
# Members = category column > 0 (year added; negative = removed). Preprocessed to lm_sentiment.json
# (repo root) — Positive 347 / Negative 2345. See EXPERIMENT_SPEC.md §5.
import json as _json  # noqa: E402
_LM = _json.load(open(Path(__file__).resolve().parents[2] / "lm_sentiment.json"))
POS, NEG = set(_LM["positive"]), set(_LM["negative"])


def sentiment(path):
    try:
        words = Path(path).read_text().lower().split()
    except Exception:
        return np.nan
    p = sum(w.strip(".,;:!?()'\"").lstrip("-") in POS for w in words)
    n = sum(w.strip(".,;:!?()'\"").lstrip("-") in NEG for w in words)
    return (p - n) / (p + n) if (p + n) else 0.0


def prior_call(ix, tkr, report_date):
    c = ix[(ix.ticker == tkr) & (ix.call_date <= report_date - pd.Timedelta(days=31))]
    return None if c.empty else c.iloc[-1]["path"]


def ols_fit_predict(tr, te, cols):
    """Fit on pre-cutoff (surprise in %), predict test → percent."""
    y = tr["surprise_early"].values * 100
    X = np.column_stack([np.ones(len(tr))] + [tr[c].values for c in cols])
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    Xt = np.column_stack([np.ones(len(te))] + [te[c].values for c in cols])
    return Xt @ b


def metrics(pred_pct, true_pct):
    """All inputs in percent."""
    pred, true = np.asarray(pred_pct, float), np.asarray(true_pct, float)
    r = np.corrcoef(pred, true)[0, 1] if np.std(pred) > 1e-9 else np.nan
    sse = ((true - pred) ** 2).sum(); sst = ((true - true.mean()) ** 2).sum()
    return r, 1 - sse / sst, np.abs(pred - true).mean(), (np.sign(pred) == np.sign(true)).mean()


def main():
    p = pd.read_csv(PANEL); p["FE_FP_END"] = pd.to_datetime(p["FE_FP_END"]); p["REPORT_DATE"] = pd.to_datetime(p["REPORT_DATE"])
    p = p.sort_values(["ticker", "FE_FP_END"])
    p["lag_surprise"] = p.groupby("ticker")["surprise_early"].shift(1)
    ix = pd.read_csv(TXINDEX); ix["call_date"] = pd.to_datetime(ix["call_date"])

    # attach prior-call sentiment; build train(pre-cutoff) / test(post-cutoff, prior-call, >=3 hist)
    rows = []
    for tkr, g in p.groupby("ticker"):
        g = g.sort_values("FE_FP_END")
        for row in g.itertuples():
            if pd.isna(row.web_yoy) or pd.isna(row.surprise_early):
                continue
            path = prior_call(ix, tkr, row.REPORT_DATE)
            hist = g[g.FE_FP_END < row.FE_FP_END]
            d = {"ticker": tkr, "FE_FP_END": row.FE_FP_END, "REPORT_DATE": row.REPORT_DATE,
                 "web_yoy": row.web_yoy, "surprise_early": row.surprise_early,
                 "lag_surprise": row.lag_surprise, "n_hist": len(hist),
                 "sent": sentiment(path) if path else np.nan,
                 "test": (row.REPORT_DATE > CUTOFF) and (path is not None) and (len(hist) >= 3)}
            rows.append(d)
    d = pd.DataFrame(rows)
    d["lag_surprise"] = d["lag_surprise"].fillna(d["surprise_early"].mean())
    d["sent"] = d["sent"].fillna(0.0)
    train = d[(d.REPORT_DATE <= CUTOFF)].dropna(subset=["web_yoy", "surprise_early"])
    test = d[d.test].dropna(subset=["web_yoy", "surprise_early"]).copy()
    print(f"train (pre-cutoff)={len(train)} · test (post-cutoff, matched)={len(test)} · {test.ticker.nunique()} tickers")

    cmean = train.groupby("ticker")["surprise_early"].mean()
    gmean = train["surprise_early"].mean()
    preds = {
        "N0 naive (track record)": test.ticker.map(cmean).fillna(gmean).values * 100,
        "N1 web-OLS": ols_fit_predict(train, test, ["web_yoy"]),
        "N2 sentiment-OLS": ols_fit_predict(train, test, ["sent"]),
        "N3 web+sentiment": ols_fit_predict(train, test, ["web_yoy", "sent"]),
        "N3b web+sent+lag": ols_fit_predict(train, test, ["web_yoy", "sent", "lag_surprise"]),
    }
    true = test["surprise_early"].values * 100

    lines = ["# Factor 1 — classical statistical baselines (non-LLM)\n",
             f"train(pre-cutoff)={len(train)} · test(post-cutoff)={len(test)} · {test.ticker.nunique()} tickers\n",
             f"{'model':26s}  corr    R²      MAE   sign"]
    for nm, pr in preds.items():
        r, r2, mae, hit = metrics(pr, true)
        lines.append(f"{nm:26s}  {r:+.3f}  {r2:+.3f}  {mae:.2f}  {hit:.2f}")
    # LLM arms for comparison (same post-cutoff set)
    if ABL.exists():
        a = pd.read_csv(ABL)
        lines.append(f"\n  --- LLM (gpt-5.5, zero-shot) on the post-cutoff set, n={len(a)} ---")
        for arm in ["fin", "fin+web", "fin+text", "fin+web+text"]:
            m = a[[arm, "true"]].dropna()
            r, r2, mae, hit = metrics(m[arm].values, m["true"].values * 100)
            lines.append(f"{'LLM '+arm:26s}  {r:+.3f}  {r2:+.3f}  {mae:.2f}  {hit:.2f}")
    out = "\n".join(lines)
    print(out)
    (OUT / "f1_baselines.md").write_text("<!-- f1_04_baselines.py -->\n```\n" + out + "\n```\n")
    print(f"\n[written] {OUT/'f1_baselines.md'}")


if __name__ == "__main__":
    main()
