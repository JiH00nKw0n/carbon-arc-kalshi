"""
Factor 1 — shared library for the channel-agnostic unified pipeline (EXPERIMENT_SPEC.md).
X = card | web (set by env F1_CHANNEL). Z (transcript) and Y (revenue surprise) are FIXED.
Column 'x_yoy' is the active channel's alt-data YoY (web users / card spend). Everything
downstream (baselines, LLM arms, metrics, validation) is identical across channels.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from f1_channels import cfg, active  # noqa: E402

ROOT = Path("/Users/junekwon/Desktop/Projects/carbon_arc")
OUT = ROOT / "factor1" / "outputs"
CUTOFF = pd.Timestamp("2025-12-01")
HIST_ROWS = 6
MAX_TRANSCRIPT_CHARS = 48000
SCREEN = ROOT / "factor1" / "data" / "altdata_ticker_screen.csv"

_LM = json.load(open(ROOT / "lm_sentiment.json"))
POS, NEG = set(_LM["positive"]), set(_LM["negative"])


# ----- sentiment (Loughran-McDonald 2011; net = (pos-neg)/(pos+neg)) -----
def sentiment(path):
    try:
        words = Path(path).read_text().lower().split()
    except Exception:
        return np.nan
    p = sum(w.strip(".,;:!?()'\"").lstrip("-") in POS for w in words)
    n = sum(w.strip(".,;:!?()'\"").lstrip("-") in NEG for w in words)
    return (p - n) / (p + n) if (p + n) else 0.0


# ----- panel build (X = active channel) -----
def _load_factset():
    c = cfg()
    d = pd.DataFrame(json.load(open(c["factset"]))["rows"])
    for col in ("ACTUAL", "CONS_EARLY", "CONS_PRINT"):
        d[col] = pd.to_numeric(d[col], errors="coerce")
    d["FE_FP_END"] = pd.to_datetime(d["FE_FP_END"])
    d["REPORT_DATE"] = pd.to_datetime(d["REPORT_DATE"])
    d["ticker"] = d["FSYM_ID"].map(c["fsym2tkr"])
    d = d.dropna(subset=["ticker", "ACTUAL", "CONS_EARLY"]).copy()
    d["surprise_early"] = (d.ACTUAL - d.CONS_EARLY) / d.CONS_EARLY
    d["surprise_print"] = (d.ACTUAL - d.CONS_PRINT) / d.CONS_PRINT
    return d.sort_values(["ticker", "FE_FP_END"])


def _load_x():
    c = cfg()
    frames = [pd.read_csv(p) for p in c["x_csv"]]
    x = pd.concat(frames, ignore_index=True)
    val = c["x_val"]
    if c["entity_map"] is not None:                       # web: entity_name -> ticker
        x = x[~x["entity_name"].isin(c["entity_drop"])].copy()
        x["ticker"] = x["entity_name"].map(c["entity_map"])
        x = x.dropna(subset=["ticker"])
    else:                                                 # card: entity_name IS ticker
        x["ticker"] = x["entity_name"]
    x["date"] = pd.to_datetime(x["date"])
    x = x.groupby(["ticker", "date"], as_index=False)[val].sum().sort_values(["ticker", "date"])
    x["x_yoy"] = x.groupby("ticker")[val].pct_change(c["yoy_lag"])
    x["x_yoy_3m"] = x.groupby("ticker")["x_yoy"].transform(lambda s: s.rolling(3, min_periods=1).mean())
    return x[["ticker", "date", "x_yoy", "x_yoy_3m"]]


def build_panel():
    c = cfg()
    fs, x = _load_factset(), _load_x()
    tol = pd.Timedelta(days=45 if c["yoy_lag"] == 12 else 60)
    rows = []
    for tkr, e in fs.groupby("ticker"):
        a = x[x.ticker == tkr][["date", "x_yoy", "x_yoy_3m"]].dropna(subset=["x_yoy"])
        if a.empty:
            continue
        m = pd.merge_asof(e.sort_values("FE_FP_END"), a.sort_values("date"),
                          left_on="FE_FP_END", right_on="date", direction="nearest", tolerance=tol)
        rows.append(m)
    p = pd.concat(rows, ignore_index=True).sort_values(["ticker", "FE_FP_END"])
    p["lag_surprise"] = p.groupby("ticker")["surprise_early"].shift(1)
    # strength tier from the O/X screen (for tiered reporting)
    try:
        sc = pd.read_csv(SCREEN)
        sc = sc[(sc.data_type == c["screen_dt"]) & (sc.impact == "O")][["ticker", "strength"]]
        p = p.merge(sc, on="ticker", how="left")
    except Exception:
        p["strength"] = np.nan
    return p


# ----- target assembly (post-cutoff eval events; identical filter across models) -----
def prior_calls(ix, tkr, report_date, k=1):
    c = ix[(ix.ticker == tkr) & (ix.call_date <= report_date - pd.Timedelta(days=31))]
    if len(c) < k:
        return None
    return list(c.iloc[-k:]["path"])[::-1]   # most-recent first


def read_text(path):
    try:
        return Path(path).read_text()[:MAX_TRANSCRIPT_CHARS]
    except Exception:
        return None


def load_txindex():
    ix = pd.read_csv(cfg()["tx_index"])
    ix["call_date"] = pd.to_datetime(ix["call_date"])
    return ix.sort_values(["ticker", "call_date"])


def build_targets(p, ix, require_text=True):
    p = p.copy()
    p["FE_FP_END"] = pd.to_datetime(p["FE_FP_END"]); p["REPORT_DATE"] = pd.to_datetime(p["REPORT_DATE"])
    p = p.sort_values(["ticker", "FE_FP_END"])
    targets = []
    for tkr, g in p.groupby("ticker"):
        g = g.sort_values("FE_FP_END")
        for row in g[g.REPORT_DATE > CUTOFF].itertuples():
            if pd.isna(row.x_yoy) or pd.isna(row.surprise_early):
                continue
            hist = g[g.FE_FP_END < row.FE_FP_END]
            calls = prior_calls(ix, tkr, row.REPORT_DATE, 1)
            if calls is None or len(hist) < 3:
                continue
            txt = read_text(calls[0])
            if require_text and not txt:
                continue
            calls2 = prior_calls(ix, tkr, row.REPORT_DATE, 2)
            txt2 = read_text(calls2[1]) if calls2 and len(calls2) == 2 else None
            targets.append({"tkr": tkr, "fp": row.FE_FP_END, "report": row.REPORT_DATE,
                            "true": float(row.surprise_early), "x_yoy": float(row.x_yoy),
                            "strength": getattr(row, "strength", np.nan),
                            "hist": hist, "row": row, "text": txt, "text2": txt2,
                            "call_path": calls[0]})
    return targets


# ----- prompt tables -----
def fin_table(hist, target):
    rows = hist.tail(HIST_ROWS)
    out = ["fiscal_q_end | actual($M) | consensus($M) | surprise%"]
    for r in rows.itertuples():
        out.append(f"{r.FE_FP_END.date()} | {r.ACTUAL:,.0f} | {r.CONS_EARLY:,.0f} | {r.surprise_early*100:+.2f}%")
    out.append(f"{target.FE_FP_END.date()} | (pending) | {target.CONS_EARLY:,.0f} | <- PREDICT")
    return "\n".join(out)


def x_table(hist, target):
    out = [cfg()["x_table_label"] + ":", "fiscal_q_end | " + cfg()["x_unit"]]
    for r in hist.dropna(subset=["x_yoy"]).tail(HIST_ROWS).itertuples():
        out.append(f"{r.FE_FP_END.date()} | {r.x_yoy*100:+.1f}%")
    out.append(f"{target.FE_FP_END.date()} | {target.x_yoy*100:+.1f}%  <- upcoming")
    return "\n".join(out)


# ----- metrics (MSE-primary; all inputs in percent) -----
def metrics(pred_pct, true_pct):
    pred, true = np.asarray(pred_pct, float), np.asarray(true_pct, float)
    sse = ((true - pred) ** 2).sum(); sst = ((true - true.mean()) ** 2).sum()
    r = np.corrcoef(pred, true)[0, 1] if np.std(pred) > 1e-9 else np.nan
    return {"rmse": float(np.sqrt(((true - pred) ** 2).mean())),
            "r2": float(1 - sse / sst), "corr": float(r), "corr2": float(r * r),
            "mae": float(np.abs(pred - true).mean()),
            "sign": float((np.sign(pred) == np.sign(true)).mean())}
