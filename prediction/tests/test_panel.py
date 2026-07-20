"""Test 6 — panel completeness.

The rebuilt panel must carry x_abs, x_yoy, rev_yoy, and prior_year_actual for every channel (the
on-disk web/foot panels were missing x_abs/rev_yoy). Here we drive build_panel through the extracted
domain records on card geometry (yoy_lag=4) and assert the columns exist and are populated on the
tail quarters, where pct_change(4)/shift(4) become defined.

build_panel's contract (matching the real PanelCache._build caller) is
build_panel(spec, revenue_records, alt_points) over already-extracted lists — not source objects.
"""
from prediction.panel.builder import build_panel

REQUIRED = ["x_abs", "x_yoy", "rev_yoy", "prior_year_actual"]


def test_panel_has_required_columns(card_channel, revenue_records, alt_points):
    panel = build_panel(card_channel, revenue_records, alt_points)
    for col in REQUIRED:
        assert col in panel.columns, f"missing panel column: {col}"


def test_required_columns_are_populated_on_tail_quarters(card_channel, revenue_records,
                                                         alt_points):
    panel = build_panel(card_channel, revenue_records, alt_points)
    panel = panel.sort_values("FE_FP_END")
    # pct_change(4) / shift(4) leave the first four quarters undefined; the last three must be full.
    tail = panel.tail(3)
    for col in REQUIRED:
        assert tail[col].notna().all(), f"{col} has nulls in the tail quarters"


def test_x_abs_carries_the_raw_alt_data_level(card_channel, revenue_records, alt_points):
    panel = build_panel(card_channel, revenue_records, alt_points)
    assert (panel["x_abs"] > 0).any()
    # x_abs is the merged raw level, not a YoY ratio, so it is far larger than any pct change.
    merged = panel.dropna(subset=["x_abs"])
    assert merged["x_abs"].max() >= 500.0


def test_rev_yoy_matches_four_quarter_growth(card_channel, revenue_records, alt_points):
    panel = build_panel(card_channel, revenue_records, alt_points).sort_values("FE_FP_END")
    last = panel.iloc[-1]
    expected = (last["ACTUAL"] - last["prior_year_actual"]) / last["prior_year_actual"]
    assert abs(last["rev_yoy"] - expected) < 1e-9
