"""Test 5 — metric math: r2 == 1 - sse/sst, corr, corr2, rmse, mae, sign on hand arrays.

Reproduces f1_lib.metrics verbatim; all inputs are in percent. Values below are hand-computed,
not read back from the implementation.
"""
import math

import numpy as np
import pytest

from prediction.evaluate.metrics import metrics


def test_r2_equals_one_minus_sse_over_sst():
    pred = [1.0, 2.0, 3.0, 4.0]
    true = [2.0, 2.0, 4.0, 4.0]
    m = metrics(pred, true)

    sse = sum((t - p) ** 2 for p, t in zip(pred, true))          # 2.0
    mean_true = sum(true) / len(true)                             # 3.0
    sst = sum((t - mean_true) ** 2 for t in true)                # 4.0
    assert m["r2"] == pytest.approx(1 - sse / sst)               # 0.5
    assert m["r2"] == pytest.approx(0.5)


def test_rmse_and_mae_on_hand_arrays():
    pred = [1.0, 2.0, 3.0, 4.0]
    true = [2.0, 2.0, 4.0, 4.0]
    m = metrics(pred, true)
    assert m["rmse"] == pytest.approx(math.sqrt(0.5))            # sqrt(mean([1,0,1,0]))
    assert m["mae"] == pytest.approx(0.5)                        # mean([1,0,1,0])


def test_corr_and_corr2_match_numpy():
    pred = [1.0, 2.0, 3.0, 4.0]
    true = [2.0, 2.0, 4.0, 4.0]
    m = metrics(pred, true)
    expected = float(np.corrcoef(pred, true)[0, 1])             # ~0.894427191
    assert m["corr"] == pytest.approx(expected)
    assert m["corr2"] == pytest.approx(expected ** 2)           # 0.8


def test_sign_hit_rate_counts_matching_signs():
    pred = [-2.0, 1.0, -1.0]
    true = [3.0, -1.0, -1.0]                                     # matches: F, F, T
    assert metrics(pred, true)["sign"] == pytest.approx(1 / 3)


def test_all_signs_matching_gives_one():
    assert metrics([1.0, 2.0, 3.0], [5.0, 6.0, 7.0])["sign"] == pytest.approx(1.0)


def test_constant_prediction_yields_nan_corr_but_finite_r2():
    m = metrics([3.0, 3.0, 3.0], [1.0, 2.0, 3.0])              # std(pred)==0 -> corr undefined
    assert math.isnan(m["corr"])
    assert math.isnan(m["corr2"])
    # sse = 5, sst = 2 -> r2 = 1 - 5/2 = -1.5 (still finite)
    assert m["r2"] == pytest.approx(-1.5)
