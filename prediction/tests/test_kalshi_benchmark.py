import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

from prediction.config.loader import load
from prediction.domain.records import AltPoint, PanelRow, Target
from prediction.panel.ladder_builder import _ladder_frame
from prediction.prompts.blocks import timeline_body
from prediction.run.experiment import _baseline_predictions
from prediction.run.store import _manifest_row


ROOT = Path(__file__).resolve().parents[2]


def _panel_row(fp_end, payload=None, actual=90.0):
    return PanelRow(
        ticker="TEST", fp_end=fp_end, report_date=fp_end, actual=actual,
        cons_early=100.0, cons_print=100.0, prior_year_actual=80.0,
        x_abs=float("nan"), x_yoy=float("nan"), x_yoy_3m=float("nan"),
        surprise_early=(actual - 100.0) / 100.0, surprise_print=(actual - 100.0) / 100.0,
        rev_yoy=0.125, lag_surprise=0.0, strength="strong", x_payload=payload,
    )


def _ladder_payload(event, strike):
    return json.dumps([{
        "event_ticker": event, "metric_label": "bookings", "n_priced_rungs": 2,
        "n_ladder_markets": 2, "monotonicity_violations": 0,
        "rungs": [
            {
                "market_ticker": f"{event}-{strike}", "threshold_operator": ">=",
                "strike": strike, "probability": 0.6, "price_source": "yes_quote_midpoint",
                "yes_bid": 0.55, "yes_ask": 0.65, "last": 0.61, "previous": 0.59,
                "spread": 0.10, "candle_at": "2026-01-01T00:00:00+00:00",
                "daily_volume": 12, "open_interest": 34,
            },
            {
                "market_ticker": f"{event}-{strike + 10}", "threshold_operator": ">=",
                "strike": strike + 10, "probability": 0.3, "price_source": "last_trade_close",
                "yes_bid": 0.0, "yes_ask": 1.0, "last": 0.3, "previous": 0.29,
                "spread": 1.0, "candle_at": "2026-01-01T00:00:00+00:00",
                "daily_volume": 5, "open_interest": 8,
            },
        ],
    }])


class NoTranscripts:
    def prior_calls(self, *_args):
        return []


def test_kalshi_config_matches_jihoon_main_protocol():
    benchmark = load(str(ROOT / "prediction/configs/revenue_surprise_full.yaml"))
    kalshi = load(str(ROOT / "prediction/configs/kalshi_full.yaml"))

    assert kalshi.seed == benchmark.seed
    assert kalshi.run == benchmark.run
    assert kalshi.llm == benchmark.llm
    assert kalshi.grid.targets == benchmark.grid.targets
    assert kalshi.grid.variants == benchmark.grid.variants
    assert kalshi.grid.arms == benchmark.grid.arms
    assert kalshi.grid.baselines == benchmark.grid.baselines
    assert kalshi.evaluate == benchmark.evaluate
    assert kalshi.grid.channels == ["kalshi"]
    assert kalshi.data.screen_csv == "kalshi/data/ticker_screen.csv"


def test_ladders_render_in_quarter_order_with_all_frozen_fields():
    old_payload = _ladder_payload("OLD", 100)
    target_payload = _ladder_payload("TARGET", 200)
    history = (_panel_row(date(2025, 9, 30), old_payload),
               _panel_row(date(2025, 12, 31), None, actual=95.0))
    row = _panel_row(date(2026, 3, 31), target_payload, actual=0.0)
    target = Target(
        ticker="TEST", fp=row.fp_end, report=row.report_date, true=0.0,
        x_yoy=float("nan"), strength="strong", row=row, hist=history,
        text=None, text2=None, call_path="", x_payload=target_payload,
    )
    channel = SimpleNamespace(kind="ladder")

    prompt = timeline_body(target, NoTranscripts(), channel, None, {"fin", "x"}, 2, 6)
    assert prompt.index("| 2025-09-30 |") < prompt.index("event: OLD")
    assert prompt.index("event: OLD") < prompt.index("| 2025-12-31 |")
    assert prompt.index("| 2026-03-31 |") < prompt.index("event: TARGET")
    assert "market | YES condition | probability | source | bid | ask | last | previous | spread" in prompt
    assert "candle_utc | daily_volume | open_interest" in prompt
    assert "TARGET-200 | KPI >= 200.00 | 0.600 | yes_quote_midpoint | 0.550 | 0.650" in prompt

    no_x = timeline_body(target, NoTranscripts(), channel, None, {"fin"}, 2, 6)
    assert "KALSHI PRE-PUBLICATION" not in no_x

    manifest = _manifest_row("kalshi", "surprise_early", target, hist_rows=1)
    assert manifest["financial_history_available"] == 2
    assert manifest["financial_history_shown"] == 1
    assert manifest["ladder_history_available"] == 1
    assert manifest["ladder_history_shown"] == 0


def test_scalar_x_baselines_are_unavailable_for_ladders():
    train = pd.DataFrame({
        "ticker": ["A", "B", "C"], "tkr": ["A", "B", "C"],
        "true": [0.0, 0.1, -0.1], "x_yoy": [np.nan] * 3,
        "sent": [0.0, 0.1, -0.1], "lag_y": [0.0, 0.0, 0.0], "x_sent": [np.nan] * 3,
    })
    test = train.iloc[:2].copy()
    result = _baseline_predictions(train, test, ["N0", "N1", "N2", "N3", "N5"], "ladder")
    assert result["N0"] is not None
    assert result["N2"] is not None
    assert result["N1"] is None
    assert result["N3"] is None
    assert result["N5"] is None


def test_ladder_panel_does_not_fabricate_a_scalar_x():
    payload = _ladder_payload("TEST", 100)
    frame = _ladder_frame([
        AltPoint(ticker="TEST", date=date(2026, 3, 31), value=123.0, x_payload=payload)
    ])

    assert frame[["x_abs", "x_yoy", "x_yoy_3m"]].isna().all().all()
    assert frame.loc[0, "x_payload"] == payload
