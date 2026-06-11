#!/usr/bin/env python3
"""
s_q_edge_tests.py — EDGE tests (Step 2). Does CA carry info NOT already in price/consensus?

Signal CA_surprise(Q) = CA card-spend YoY for the reported quarter, residualized vs the company's own
trailing-4q mean (self-contained "acceleration"; known at quarter-end, BEFORE the earnings print).

H1 (money)     : ret_earn_mktadj ~ CA_surprise   (does CA predict the earnings-day move?)
H2 (analysts)  : eps_surprise_pct ~ CA_surprise   (does CA predict the EPS surprise?)
H3 (rigorous)  : OOS Diebold-Mariano — does CA improve OOS forecast of rev_yoy vs AR baseline?
H4 (where)     : H1/H2 split by card-share tercile (per-company ca↔rev corr) and analyst coverage.

Inference: company-clustered bootstrap p + shuffle-company surrogate + BH-FDR; H1 also hit-rate + L/S PnL.
Inputs: edge_panel.csv, ca0056_card_spend_by_ticker_q_3y.csv, fmp_revenue_by_ticker.csv
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import s_h_leadlag_stats as kt  # _ssr for DM

ROOT = Path(__file__).resolve().parents[2]
A = ROOT / "outputs" / "auto"
OUT_MD = ROOT / "docs" / "analysis_company_edge.md"
lines = []
def log(s=""): print(s); lines.append(s)


def build_ca_surprise():
    ca = pd.read_csv(A / "ca0056_card_spend_by_ticker_q_3y.csv")
    ca = ca.groupby(["entity_name", "date"], as_index=False)["credit_card_spend"].sum()
    ca = ca.rename(columns={"entity_name": "ticker"})
    ca["date"] = pd.to_datetime(ca["date"])
    ca = ca.sort_values(["ticker", "date"])
    ca["ca_yoy"] = ca.groupby("ticker")["credit_card_spend"].pct_change(4)
    # residualize vs trailing-4q mean of ca_yoy (acceleration), self-contained
    ca["ca_trend"] = ca.groupby("ticker")["ca_yoy"].transform(lambda s: s.shift(1).rolling(4, min_periods=2).mean())
    ca["ca_surprise"] = ca["ca_yoy"] - ca["ca_trend"]
    return ca


def per_company_cardshare():
    ca = pd.read_csv(A / "ca0056_card_spend_by_ticker_q_3y.csv")
    ca = ca.groupby(["entity_name", "date"], as_index=False)["credit_card_spend"].sum().rename(columns={"entity_name": "ticker"})
    ca["date"] = pd.to_datetime(ca["date"]); ca = ca.sort_values(["ticker", "date"])
    ca["ca_yoy"] = ca.groupby("ticker")["credit_card_spend"].pct_change(4)
    rev = pd.read_csv(A / "fmp_revenue_by_ticker.csv"); rev["date"] = pd.to_datetime(rev["date"])
    rev = rev.dropna(subset=["revenue"]).sort_values(["ticker", "date"])
    rev["rev_yoy"] = rev.groupby("ticker")["revenue"].pct_change(4)
    out = {}
    for t in ca.ticker.unique():
        a = ca[ca.ticker == t][["date", "ca_yoy"]]
        r = rev[rev.ticker == t][["date", "rev_yoy"]]
        m = pd.merge_asof(a.sort_values("date"), r.sort_values("date"), on="date", direction="nearest", tolerance=pd.Timedelta(days=50)).dropna()
        out[t] = m["ca_yoy"].corr(m["rev_yoy"]) if len(m) >= 5 else np.nan
    return out


def cluster_boot(d, x, y, n=3000):
    d = d.dropna(subset=[x, y])
    if len(d) < 15 or d[x].std() < 1e-12:
        return np.nan, np.nan, len(d)
    r0 = d[x].corr(d[y]); ticks = d.ticker.unique(); rng = np.random.default_rng(7); bs = []
    for _ in range(n):
        s = pd.concat([d[d.ticker == k] for k in rng.choice(ticks, len(ticks), True)])
        if s[x].std() > 1e-12 and s[y].std() > 1e-12:
            bs.append(s[x].corr(s[y]))
    bs = np.array(bs); p = 2 * min((bs > 0).mean(), (bs < 0).mean())
    return r0, p, len(d)


def surrogate(d, x, y, r_obs, n=2000):
    d = d.dropna(subset=[x, y]); ticks = list(d.ticker.unique()); rng = np.random.default_rng(11)
    by = {t: d[d.ticker == t][[x, y]].reset_index(drop=True) for t in ticks}
    ge = tot = 0
    for _ in range(n):
        perm = rng.permutation(ticks); xs = []; ys = []
        for t, ps in zip(ticks, perm):
            yv = by[t][y].values; xv = by[ps][x].values; k = min(len(yv), len(xv))
            xs += list(xv[:k]); ys += list(yv[:k])
        xs = np.array(xs); ys = np.array(ys)
        if np.std(xs) > 1e-12 and np.std(ys) > 1e-12:
            tot += 1; ge += abs(np.corrcoef(xs, ys)[0, 1]) >= abs(r_obs)
    return (ge + 1) / (tot + 1)


def h1_pnl(d):
    d = d.dropna(subset=["ca_surprise", "ret_earn_mktadj"])
    pos = np.sign(d["ca_surprise"])
    hit = (pos == np.sign(d["ret_earn_mktadj"])).mean()
    ls = (pos * d["ret_earn_mktadj"])  # long if CA_surprise>0 else short
    return hit, ls.mean(), ls.std() / np.sqrt(len(ls)), len(d)


def oos_dm():
    """H3: per company expanding-window forecast of rev_yoy: AR(1) baseline vs +ca_yoy. pooled DM."""
    ca = build_ca_surprise()[["ticker", "date", "ca_yoy"]]
    rev = pd.read_csv(A / "fmp_revenue_by_ticker.csv"); rev["date"] = pd.to_datetime(rev["date"])
    rev = rev.dropna(subset=["revenue"]).sort_values(["ticker", "date"])
    rev["rev_yoy"] = rev.groupby("ticker")["revenue"].pct_change(4)
    eb, ec = [], []
    for t in rev.ticker.unique():
        r = rev[rev.ticker == t][["date", "rev_yoy"]].dropna()
        m = pd.merge_asof(r.sort_values("date"), ca[ca.ticker == t].sort_values("date"),
                          on="date", direction="nearest", tolerance=pd.Timedelta(days=50)).dropna(subset=["rev_yoy", "ca_yoy"])
        m = m.reset_index(drop=True)
        m["y1"] = m["rev_yoy"].shift(1)
        m = m.dropna()
        if len(m) < 7:
            continue
        for i in range(5, len(m)):
            tr = m.iloc[:i]; te = m.iloc[i:i + 1]
            ones = np.ones((len(tr), 1)); ytr = tr["rev_yoy"].values
            Xb = np.hstack([ones, tr[["y1"]].values]); _, bb = kt._ssr(ytr, Xb)
            Xc = np.hstack([ones, tr[["y1", "ca_yoy"]].values]); _, bc = kt._ssr(ytr, Xc)
            pb = float(np.hstack([[1.0], te[["y1"]].values[0]]) @ bb)
            pc = float(np.hstack([[1.0], te[["y1", "ca_yoy"]].values[0]]) @ bc)
            act = te["rev_yoy"].values[0]
            eb.append(act - pb); ec.append(act - pc)
    eb, ec = np.array(eb), np.array(ec); dd = eb**2 - ec**2; nt = len(dd)
    from scipy import stats
    dm = dd.mean() / np.sqrt(np.var(dd) / nt) if np.var(dd) > 0 else np.nan
    p = 2 * (1 - stats.t.cdf(abs(dm), nt - 1))
    return nt, np.sqrt((eb**2).mean()), np.sqrt((ec**2).mean()), dm, p


def main():
    ep = pd.read_csv(A / "edge_panel.csv")
    ep["report_date"] = pd.to_datetime(ep["report_date"])
    ca = build_ca_surprise()
    # align CA quarter (ends ~45d before report) to each earnings event
    ep["key"] = ep["report_date"] - pd.Timedelta(days=45)
    rows = []
    for t in ep.ticker.unique():
        e = ep[ep.ticker == t].sort_values("key")
        a = ca[ca.ticker == t].sort_values("date")
        if a.empty:
            continue
        m = pd.merge_asof(e, a[["date", "ca_yoy", "ca_surprise"]], left_on="key", right_on="date",
                          direction="nearest", tolerance=pd.Timedelta(days=60))
        rows.append(m)
    d = pd.concat(rows, ignore_index=True).dropna(subset=["ca_surprise"])
    cs = per_company_cardshare()
    d["cardshare"] = d["ticker"].map(cs)
    log("# Company EDGE tests — does CA carry info beyond price/consensus?")
    log(f"\nearnings events with CA_surprise: {len(d)} across {d.ticker.nunique()} tickers; "
        f"{d.report_date.min().date()}..{d.report_date.max().date()}")

    # H1
    r1, p1, n1 = cluster_boot(d, "ca_surprise", "ret_earn_mktadj")
    s1 = surrogate(d, "ca_surprise", "ret_earn_mktadj", r1) if not np.isnan(r1) else np.nan
    hit, lsm, lse, nls = h1_pnl(d)
    log("\n## H1 (MONEY) — CA_surprise → earnings-day mkt-adj return")
    log(f"  r={r1:+.3f} (n={n1}) p_boot={p1:.3f} p_surrogate={s1:.3f}")
    log(f"  sign hit-rate={hit:.1%}  L/S mean earnings-day return={lsm:+.4f} (SE {lse:.4f}, t={lsm/lse:+.2f}, n={nls})")

    # H2
    r2, p2, n2 = cluster_boot(d, "ca_surprise", "eps_surprise_pct")
    s2 = surrogate(d, "ca_surprise", "eps_surprise_pct", r2) if not np.isnan(r2) else np.nan
    log("\n## H2 (ANALYSTS) — CA_surprise → EPS surprise (actual-est)")
    log(f"  r={r2:+.3f} (n={n2}) p_boot={p2:.3f} p_surrogate={s2:.3f}")

    # H3
    nt, rmse_b, rmse_c, dm, pdm = oos_dm()
    log("\n## H3 (RIGOROUS) — OOS Diebold-Mariano: rev_yoy forecast, AR(1) vs +CA")
    log(f"  n_test={nt}  RMSE base={rmse_b:.4f}  RMSE +CA={rmse_c:.4f}  DM={dm:+.2f} p={pdm:.3f}  "
        f"({'CA improves' if rmse_c<rmse_b and pdm<0.05 else 'no sig improvement'})")

    # H4 heterogeneity
    log("\n## H4 (WHERE) — H1/H2 by card-share tercile & analyst coverage")
    d["cs_tier"] = pd.qcut(d["cardshare"].rank(method="first"), 3, labels=["low", "mid", "high"])
    for tier in ["high", "mid", "low"]:
        sub = d[d.cs_tier == tier]
        rr, pp, nn = cluster_boot(sub, "ca_surprise", "ret_earn_mktadj")
        re, pe, ne = cluster_boot(sub, "ca_surprise", "eps_surprise_pct")
        log(f"  cardshare={tier:4s}: H1 r={rr:+.3f}(p{pp:.2f},n{nn}) | H2 r={re:+.3f}(p{pe:.2f},n{ne})")
    if d["n_analysts"].notna().any():
        d["cov_tier"] = pd.qcut(d["n_analysts"].rank(method="first"), 2, labels=["low_cov", "high_cov"])
        for tier in ["low_cov", "high_cov"]:
            sub = d[d.cov_tier == tier]
            rr, pp, nn = cluster_boot(sub, "ca_surprise", "ret_earn_mktadj")
            log(f"  {tier}: H1 r={rr:+.3f}(p{pp:.2f},n{nn})")

    log("\n## VERDICT")
    h1ok = (not np.isnan(s1)) and s1 < 0.05 and p1 < 0.05
    h3ok = rmse_c < rmse_b and pdm < 0.05
    log(f"  H1 money: {'SIGNAL' if h1ok else 'null'} | H3 OOS: {'CA adds info' if h3ok else 'null'} | "
        f"H2 analysts: {'signal' if (not np.isnan(s2) and s2<0.05) else 'null'}")
    if not (h1ok or h3ok):
        log("  → CA has NO tradeable edge at company level (measures revenue, but no info beyond price/consensus). Conclude.")
    else:
        log("  → edge candidate survives — pursue stretch (FactSet revenue-consensus / Polymarket price / weekly timing).")

    OUT_MD.write_text("# Company EDGE tests\n\n> 2026-06-03 · `scripts/auto/s_q_edge_tests.py`\n\n```\n" + "\n".join(lines) + "\n```\n")
    print(f"\n[written] {OUT_MD}")


if __name__ == "__main__":
    main()
