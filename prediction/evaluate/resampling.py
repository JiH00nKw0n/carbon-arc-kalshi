"""Company-clustered resampling: super-additivity bootstrap + shuffle-company surrogate.

Both procedures are copied verbatim from factor1 f1_22_eval (same math, same defaults). They
operate on the matched evaluation frame `df` whose columns are `tkr`, `true` (a fraction), and
one raw prediction column per arm.
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd

__all__ = ["boot_synergy", "shuffle_company_surrogate"]

# The four arms whose corr/skill combine into the super-additivity contrast.
_ARMS = ("fin", "fin+x", "fin+text", "fin+x+text")


def boot_synergy(df: pd.DataFrame, rng, n: int = 5000) -> dict:
    """Company-clustered bootstrap of corr- and MSE-skill super-additivity.

    Each of `n` resamples draws firms with replacement, then measures both corr and MSE-skill
    (1 − MSE/Var) for every arm. Returns the bootstrap distributions of the headline arm's
    corr/skill and of the synergy contrast M(fin+x+text) − [M(fin+x)+M(fin+text)−M(fin)] for
    corr and skill. Keys: `r_fwt`, `skill_fwt`, `syn_corr`, `syn_skill` (each a list of length n).
    """
    companies = df.tkr.unique()
    out = {"syn_corr": [], "syn_skill": [], "r_fwt": [], "skill_fwt": []}
    for _ in range(n):
        drawn = rng.choice(companies, len(companies), replace=True)
        resample = pd.concat([df[df.tkr == company] for company in drawn])
        y = resample["true"].values * 100
        var = ((y - y.mean()) ** 2).mean()
        corr, skill = {}, {}
        for arm in _ARMS:
            pred = resample[arm].values
            corr[arm] = np.corrcoef(pred, y)[0, 1] if np.std(pred) > 1e-9 else 0.0
            skill[arm] = 1 - ((y - pred) ** 2).mean() / var
        out["r_fwt"].append(corr["fin+x+text"])
        out["skill_fwt"].append(skill["fin+x+text"])
        out["syn_corr"].append(corr["fin+x+text"] - (corr["fin+x"] + corr["fin+text"] - corr["fin"]))
        out["syn_skill"].append(skill["fin+x+text"] - (skill["fin+x"] + skill["fin+text"] - skill["fin"]))
    return out


def shuffle_company_surrogate(df: pd.DataFrame, arm_col: str, rng, n: int = 5000) -> float:
    """Firm-specific-signal test: p-value from reassigning each firm's truth block to a peer.

    Groups rows by firm, then within each size class permutes which firm's truth-block lands
    where (same-size swaps preserve the marginal). The surrogate |corr| is compared to the
    observed |corr(pred, true)| over `n` draws; p = (#ge + 1)/(n + 1). Small p ⇒ the arm tracks
    firm-specific truth, not a common size/scale artifact.
    """
    true = df["true"].values
    pred = df[arm_col].values
    tickers = df["tkr"].values
    rows_of = defaultdict(list)
    for i, ticker in enumerate(tickers):
        rows_of[ticker].append(i)
    firms_by_size = defaultdict(list)
    for ticker, rows in rows_of.items():
        firms_by_size[len(rows)].append(ticker)
    r_obs = abs(np.corrcoef(pred, true)[0, 1])
    count = 0
    for _ in range(n):
        surrogate = true.copy()
        for firms in firms_by_size.values():
            if len(firms) < 2:
                continue
            for src, dst in zip(firms, rng.permutation(firms)):
                surrogate[rows_of[src]] = true[rows_of[dst]]
        if abs(np.corrcoef(pred, surrogate)[0, 1]) >= r_obs:
            count += 1
    return (count + 1) / (n + 1)
