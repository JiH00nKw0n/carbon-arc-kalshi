"""
Factor 1 — significance tests (ported from scripts/auto/s_q_edge_tests.py).

Two firm-aware tests, used as the verdict gate (BOTH must pass, p<0.05):

  cluster_boot — company-clustered bootstrap. Resamples whole tickers with replacement
                 (panel structure), recomputes corr each time; two-tailed p from the sign
                 split of the bootstrap distribution. Guards against pseudo-replication
                 (treating 13 quarters of one firm as 13 independent points).

  surrogate    — shuffle-company surrogate. Pairs each firm's X with ANOTHER firm's Y
                 (permuted ticker labels), rebuilds the pooled series, and asks how often
                 |r| matches/exceeds the observed |r|. Empirical p. Kills "common-trend"
                 artifacts: if the whole sector just moved together, shuffled pairings
                 reproduce the correlation and p stays high.
"""
import numpy as np
import pandas as pd


def corr(d: pd.DataFrame, x: str, y: str) -> float:
    m = d[[x, y]].dropna()
    return np.corrcoef(m[x], m[y])[0, 1] if len(m) > 2 else np.nan


def cluster_boot(d: pd.DataFrame, x: str, y: str, n: int = 5000, seed: int = 2026):
    """Return (r, p_boot, n_obs). Resample tickers (clusters) with replacement."""
    m = d[["ticker", x, y]].dropna()
    if m[x].nunique() < 3 or len(m) < 5:
        return np.nan, np.nan, len(m)
    r0 = np.corrcoef(m[x], m[y])[0, 1]
    ticks = m.ticker.unique()
    by = {t: g for t, g in m.groupby("ticker")}
    rng = np.random.default_rng(seed)
    bs = []
    for _ in range(n):
        s = pd.concat([by[t] for t in rng.choice(ticks, len(ticks), replace=True)])
        if s[x].nunique() > 1 and s[y].nunique() > 1:
            bs.append(np.corrcoef(s[x], s[y])[0, 1])
    bs = np.array(bs)
    p = 2 * min((bs > 0).mean(), (bs < 0).mean())
    return r0, p, len(m)


def surrogate(d: pd.DataFrame, x: str, y: str, r_obs: float, n: int = 5000, seed: int = 2026):
    """Return p_surr = P(|r(shuffled)| >= |r_obs|). Permute ticker labels of X vs Y."""
    m = d[["ticker", x, y]].dropna()
    ticks = m.ticker.unique()
    if len(ticks) < 3 or np.isnan(r_obs):
        return np.nan
    by = {t: g for t, g in m.groupby("ticker")}
    rng = np.random.default_rng(seed)
    ge = 0
    for _ in range(n):
        perm = rng.permutation(ticks)
        xs, ys = [], []
        for t, ps in zip(ticks, perm):
            yv = by[t][y].values
            xv = by[ps][x].values
            k = min(len(yv), len(xv))
            if k:
                xs += list(xv[:k]); ys += list(yv[:k])
        if len(xs) > 2 and np.std(xs) > 0 and np.std(ys) > 0:
            ge += abs(np.corrcoef(xs, ys)[0, 1]) >= abs(r_obs)
    return (ge + 1) / (n + 1)


def within_company_corr(d: pd.DataFrame, x: str, y: str) -> float:
    """Corr after removing each firm's mean (does X track WHICH quarter, not just which firm)."""
    m = d[["ticker", x, y]].dropna().copy()
    for c in (x, y):
        m[c + "_w"] = m[c] - m.groupby("ticker")[c].transform("mean")
    return corr(m, x + "_w", y + "_w")
