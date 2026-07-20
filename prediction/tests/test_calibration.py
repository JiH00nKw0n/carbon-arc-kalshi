"""Test 4 — leak-free calibration folded by company.

cross_fit_calibrate fits `true% ~ a + b*raw` on the other folds and predicts the held-out fold,
partitioning by COMPANY. We prove leak-freeness behaviorally instead of peeking at fold internals:

Five "clean" companies lie exactly on the line y% = 1 + 2*raw. One outlier company O (raw=10) has a
wildly off-line true value. Because folds are by company, whenever O's fold is held out its training
set is clean-only, so any OLS fit on a subset of the collinear clean points recovers (1, 2) exactly
and must predict 1 + 2*10 = 21 for O -- regardless of which fold O lands in. If O's own row leaked
into training, that prediction would be dragged toward O. So `out[O] == 21` <=> O was held out of its
own calibration fit.
"""
import numpy as np
import pandas as pd
import pytest

from prediction.evaluate.calibration import cross_fit_calibrate

INTERCEPT, SLOPE = 1.0, 2.0  # percent


@pytest.fixture
def collinear_with_outlier() -> pd.DataFrame:
    clean_raw = [1.0, 2.0, 3.0, 4.0, 5.0]
    rows = [dict(tkr=f"C{i}", raw=r, true=(INTERCEPT + SLOPE * r) / 100.0)
            for i, r in enumerate(clean_raw)]
    rows.append(dict(tkr="O", raw=10.0, true=5.00))            # 500% -- far off the clean line
    return pd.DataFrame(rows)


def test_outlier_prediction_is_leave_company_out(collinear_with_outlier):
    df = collinear_with_outlier
    out = cross_fit_calibrate(df, "raw", np.random.default_rng(2026))

    o = df.index[df.tkr == "O"][0]
    leakfree = INTERCEPT + SLOPE * 10.0                        # 21.0, the clean-line value
    assert out[o] == pytest.approx(leakfree, abs=1e-6)

    # Contrast: a fit that INCLUDED O predicts something far from 21 at raw=10.
    y = df["true"].values * 100
    x = df["raw"].values
    b = np.linalg.lstsq(np.column_stack([np.ones(len(x)), x]), y, rcond=None)[0]
    leaky = b[0] + b[1] * 10.0
    assert not np.isclose(out[o], leaky, atol=1.0)


def test_every_company_receives_a_finite_out_of_fold_prediction(collinear_with_outlier):
    out = cross_fit_calibrate(collinear_with_outlier, "raw", np.random.default_rng(2026))
    assert np.isfinite(out).all()
    assert len(out) == len(collinear_with_outlier)


def test_calibration_is_deterministic_under_a_fixed_seed(collinear_with_outlier):
    a = cross_fit_calibrate(collinear_with_outlier, "raw", np.random.default_rng(2026))
    b = cross_fit_calibrate(collinear_with_outlier, "raw", np.random.default_rng(2026))
    assert np.array_equal(a, b)
