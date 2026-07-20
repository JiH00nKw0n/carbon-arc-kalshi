"""Leak-free realized calibration: K-fold-by-company linear rescale (verbatim from f1_22)."""
from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = ["cross_fit_calibrate"]


def cross_fit_calibrate(df: pd.DataFrame, arm_col: str, rng, k: int = 5) -> np.ndarray:
    """Out-of-fold calibrated predictions (%) for `arm_col`, folded BY COMPANY (leak-free).

    Companies are shuffled and assigned to folds by `company_index % k`, so every row of a firm
    shares one fold. For each fold, fit `true ~ a + b·raw` on the OTHER folds and predict the
    held-out fold — no firm's rows ever calibrate themselves. `df` carries `tkr`, `true`
    (a fraction), and the raw arm column (already percent). Returns one OOF prediction per row
    (NaN where a fold is too small to fit).
    """
    companies = list(df.tkr.unique())
    rng.shuffle(companies)
    fold_of = {company: i % k for i, company in enumerate(companies)}
    company_fold = df.tkr.map(fold_of).values
    y = df["true"].values * 100
    x = df[arm_col].values
    out = np.full(len(df), np.nan)
    for fold in range(k):
        train, held_out = company_fold != fold, company_fold == fold
        if train.sum() < 3 or held_out.sum() == 0:
            continue
        design = np.column_stack([np.ones(train.sum()), x[train]])
        coef, *_ = np.linalg.lstsq(design, y[train], rcond=None)
        out[held_out] = coef[0] + coef[1] * x[held_out]
    return out
