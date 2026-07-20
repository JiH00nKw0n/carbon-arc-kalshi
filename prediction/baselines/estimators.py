"""Classical baseline estimators — the only three fitting behaviors behind N0..N5.

Each learns labels in PERCENT (the fractional `true` column x100) and predicts in percent,
reproducing the factor1 f1_22_eval numerics verbatim (same lstsq, same GBT config, seed 2026).
The evaluation frame carries one company column and one label column (constants below); feature
columns are named by each BaselineSpec.
"""
from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd

from prediction.errors import ModelConfigError

TICKER_COL = "ticker"       # company identifier in the evaluation frame
LABEL_COL = "true"          # realized active-Y value, stored as a fraction
GBT_SEED = 2026             # frozen so tree fits are reproducible

Predictor = Callable[[pd.DataFrame], np.ndarray]


def _labels_pct(frame: pd.DataFrame) -> np.ndarray:
    """The training labels in percent (fraction x100), as factor1 fits them."""
    return frame[LABEL_COL].values * 100


def _design_matrix(frame: pd.DataFrame, feature_cols: list[str]) -> np.ndarray:
    """Intercept column prepended to the named features — the OLS design matrix."""
    intercept = np.ones(len(frame))
    return np.column_stack([intercept] + [frame[c].values for c in feature_cols])


def naive_company_mean(train_df: pd.DataFrame) -> Predictor:
    """Fit each company's mean percent label; return a predictor with global-mean fallback."""
    per_company = train_df.groupby(TICKER_COL)[LABEL_COL].mean() * 100
    global_mean = train_df[LABEL_COL].mean() * 100

    def predict(test_df: pd.DataFrame) -> np.ndarray:
        return test_df[TICKER_COL].map(per_company).fillna(global_mean).values

    return predict


def ols(train_df: pd.DataFrame, test_df: pd.DataFrame, feature_cols: list[str]) -> np.ndarray:
    """Least-squares fit on the training design matrix; predict the matched test rows (percent)."""
    coef, *_ = np.linalg.lstsq(_design_matrix(train_df, feature_cols), _labels_pct(train_df), rcond=None)
    return _design_matrix(test_df, feature_cols) @ coef


def gbt(train_df: pd.DataFrame, test_df: pd.DataFrame, feature_cols: list[str], params: dict) -> np.ndarray:
    """Gradient-boosted trees on the same scalar features; predict the matched test rows (percent)."""
    try:
        from sklearn.ensemble import GradientBoostingRegressor
    except ImportError as exc:  # scikit-learn absent but a GBT baseline was requested
        raise ModelConfigError("scikit-learn is required for the 'gbt' baseline") from exc
    model = GradientBoostingRegressor(**params, random_state=GBT_SEED)
    model.fit(train_df[feature_cols].values, _labels_pct(train_df))
    return model.predict(test_df[feature_cols].values)


_ESTIMATORS: dict[str, Callable] = {"naive": naive_company_mean, "ols": ols, "gbt": gbt}


def get_estimator(name: str) -> Callable:
    """Return the estimator function for `name` ({naive, ols, gbt}); unknown -> ModelConfigError."""
    if name not in _ESTIMATORS:
        valid = ", ".join(sorted(_ESTIMATORS))
        raise ModelConfigError(f"unknown estimator '{name}'; valid: {valid}")
    return _ESTIMATORS[name]
