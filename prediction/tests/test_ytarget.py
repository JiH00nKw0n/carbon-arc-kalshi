"""Test 3 — Y denominator wiring: label reads the right true column; extract rescales by the right
anchor and returns a signed percent; each Y binds the right output schema.

YTarget is a foundation module already on disk, so these values are exact, not approximate contracts.
"""
import pytest

from prediction.targets.schemas import BPredictSurprise, BPredictYoY
from prediction.targets.ytarget import get_y_target


def test_label_reads_the_matching_true_column(hand_row):
    assert get_y_target("surprise_early").label(hand_row) == pytest.approx(0.10)
    assert get_y_target("surprise_print").label(hand_row) == pytest.approx((110 - 105) / 105)
    assert get_y_target("rev_yoy").label(hand_row) == pytest.approx((110 - 88) / 88)  # 0.25


def test_surprise_early_extract_divides_by_cons_early_not_cons_print(hand_row):
    y = get_y_target("surprise_early")
    # anchor is cons_early=100 -> (105-100)/100*100 = +5.0; if it wrongly used cons_print=105 -> 0.0
    assert y.extract(105.0, hand_row) == pytest.approx(5.0)
    assert y.extract(110.0, hand_row) == pytest.approx(10.0)


def test_surprise_print_extract_divides_by_cons_print(hand_row):
    y = get_y_target("surprise_print")
    assert y.extract(110.0, hand_row) == pytest.approx((110 - 105) / 105 * 100)  # +4.7619%


def test_rev_yoy_extract_divides_by_prior_year_actual(hand_row):
    y = get_y_target("rev_yoy")
    assert y.extract(110.0, hand_row) == pytest.approx((110 - 88) / 88 * 100)    # +25.0%


def test_extract_returns_negative_percent_when_below_anchor(hand_row):
    assert get_y_target("surprise_early").extract(95.0, hand_row) == pytest.approx(-5.0)


def test_each_y_binds_the_right_output_schema():
    assert get_y_target("surprise_early").schema is BPredictSurprise
    assert get_y_target("surprise_print").schema is BPredictSurprise
    assert get_y_target("rev_yoy").schema is BPredictYoY


def test_ask_text_names_the_right_anchor_and_metric(hand_row):
    early = get_y_target("surprise_early").ask_text(hand_row)
    assert "consensus" in early and "SURPRISE" in early
    yoy = get_y_target("rev_yoy").ask_text(hand_row)
    assert "prior-year revenue" in yoy and "YoY GROWTH" in yoy


def test_extract_reads_predicted_revenue_field_of_canned_object(hand_row, fake_llm):
    # The FakeLLMClient hands back the same canned parsed objects the real predictor would.
    surprise_obj = fake_llm.predict_structured().parsed        # BPredictSurprise(level=110)
    yoy_obj = fake_llm.predict_structured().parsed             # BPredictYoY(level=110)
    assert isinstance(surprise_obj, BPredictSurprise)
    assert isinstance(yoy_obj, BPredictYoY)
    assert get_y_target("surprise_early").extract(
        surprise_obj.predicted_revenue_musd, hand_row) == pytest.approx(10.0)
    assert get_y_target("rev_yoy").extract(
        yoy_obj.predicted_revenue_musd, hand_row) == pytest.approx(25.0)
