import json

import pandas as pd
import pytest

from kalshi.scripts.auto import s_ax_kalshi_table2_baselines as table2


def _payload(strikes, probabilities):
    return json.dumps([{
        "event_ticker": "TEST",
        "metric_label": "deliveries",
        "rungs": [
            {
                "strike": strike,
                "probability": probability,
                "threshold_operator": ">=",
            }
            for strike, probability in zip(strikes, probabilities)
        ],
    }])


def test_normalized_survival_auc_is_unit_invariant():
    base = table2.normalized_survival_auc(_payload([100, 200, 300], [0.9, 0.5, 0.1]))
    rescaled = table2.normalized_survival_auc(
        _payload([10_000, 20_000, 30_000], [0.9, 0.5, 0.1])
    )

    assert base == pytest.approx(0.5)
    assert rescaled == pytest.approx(base)


def test_normalized_survival_auc_rejects_multiple_events():
    event = json.loads(_payload([100, 200], [0.8, 0.2]))[0]

    with pytest.raises(ValueError, match="exactly one"):
        table2.normalized_survival_auc(json.dumps([event, event]))


def test_target_key_normalizes_timestamp_to_calendar_date():
    assert table2._target_key("AAA", pd.Timestamp("2026-03-31 00:00:00")) == (
        "AAA",
        "2026-03-31",
    )


def test_fvu_is_one_minus_oos_r_squared():
    result = table2.fvu_mae([0.0, 10.0, 20.0], [5.0, 10.0, 15.0])

    assert result["fvu"] == pytest.approx(0.25)
    assert result["mae"] == pytest.approx(10.0 / 3.0)


def test_attach_llm_predictions_uses_three_arm_average():
    classical = pd.DataFrame({
        "ticker": ["AAA", "BBB"],
        "fp": pd.to_datetime(["2026-03-31", "2026-03-31"]),
        "true": [0.10, 0.20],
        "historical_average": [5.0, 15.0],
        "ols": [7.0, 17.0],
        "gbt": [8.0, 18.0],
    })
    records = [{
        "seed": 2026,
        "y": "rev_yoy",
        "variant": "TOOL",
        "preds": pd.DataFrame({
            "tkr": ["AAA", "BBB"],
            "fp": ["2026-03-31", "2026-03-31"],
            "true": [0.10, 0.20],
            "fin": [8.0, 16.0],
            "fin+x": [10.0, 19.0],
            "fin+text": [12.0, 22.0],
            "fin+x+text": [11.0, 21.0],
        }),
    }]

    result = table2.attach_llm_predictions(classical, records)

    assert result["ensembled_llm"].tolist() == pytest.approx([10.0, 19.0])
    assert result["our_method"].tolist() == pytest.approx([11.0, 21.0])


def test_attach_llm_predictions_rejects_missing_arm_value():
    classical = pd.DataFrame({
        "ticker": ["AAA"],
        "fp": pd.to_datetime(["2026-03-31"]),
        "true": [0.10],
        "historical_average": [5.0],
        "ols": [7.0],
        "gbt": [8.0],
    })
    records = [{
        "seed": 2026,
        "y": "rev_yoy",
        "variant": "TOOL",
        "preds": pd.DataFrame({
            "tkr": ["AAA"],
            "fp": ["2026-03-31"],
            "true": [0.10],
            "fin": [8.0],
            "fin+x": [float("nan")],
            "fin+text": [12.0],
            "fin+x+text": [11.0],
        }),
    }]

    with pytest.raises(RuntimeError, match="arm prediction is missing"):
        table2.attach_llm_predictions(classical, records)


def test_company_cluster_bootstrap_is_reproducible():
    frame = pd.DataFrame({
        "sample": ["full_21"] * 4,
        "ticker": ["AAA", "AAA", "BBB", "CCC"],
        "fp": pd.to_datetime(["2025-12-31", "2026-03-31"] * 2),
        "true_pct": [0.0, 10.0, 20.0, 30.0],
        **{
            method: [1.0, 9.0, 21.0, 29.0]
            for method, _ in table2.METHODS
        },
    })

    first = table2.company_cluster_bootstrap(frame, reps=10, seed=7)
    second = table2.company_cluster_bootstrap(frame, reps=10, seed=7)

    pd.testing.assert_frame_equal(first, second)
    assert len(first) == 10 * len(table2.METHODS)
