"""MSE-primary metric bundle for percent-scaled predictions (verbatim from factor1 f1_lib)."""
from __future__ import annotations

import numpy as np

__all__ = ["metrics"]


def metrics(pred_pct, true_pct) -> dict:
    """RMSE / R²_OOS / corr / corr² / MAE / sign-hit for a percent-scaled prediction vs truth.

    Both inputs are already in percent. R² is out-of-sample skill against the truth mean
    (1 − SSE/SST), not a fitted-line R². `corr`/`corr2` are NaN when the prediction has
    essentially no variance (guarded at 1e-9).
    """
    pred = np.asarray(pred_pct, float)
    true = np.asarray(true_pct, float)
    sse = ((true - pred) ** 2).sum()
    sst = ((true - true.mean()) ** 2).sum()
    corr = np.corrcoef(pred, true)[0, 1] if np.std(pred) > 1e-9 else np.nan
    return {
        "rmse": float(np.sqrt(((true - pred) ** 2).mean())),
        "r2": float(1 - sse / sst),
        "corr": float(corr),
        "corr2": float(corr * corr),
        "mae": float(np.abs(pred - true).mean()),
        "sign": float((np.sign(pred) == np.sign(true)).mean()),
    }
