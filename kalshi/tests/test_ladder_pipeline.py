import importlib.util
import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "kalshi" / "scripts" / "auto"


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


features_script = load_script("s_ag_kalshi_company_features")
join_script = load_script("s_ah_kalshi_x_revsurprise")
factset_script = load_script("s_ai_factset_revsurprise_panel")
ladder_script = load_script("s_ak_kalshi_prereport_features")
runner_script = load_script("s_al_kalshi_llm_ablation")
analysis_script = load_script("s_an_kalshi_ladder_analysis")


class QuoteSelectionTest(unittest.TestCase):
    def test_wide_book_uses_last_trade_instead_of_midpoint(self):
        candle = {
            "yes_bid": {"close_dollars": "0.00"},
            "yes_ask": {"close_dollars": "1.00"},
            "price": {"close_dollars": "0.01", "previous_dollars": "0.02"},
        }
        selected = ladder_script.select_probability(candle, max_mid_spread=0.20)
        self.assertEqual(selected["probability"], 0.01)
        self.assertEqual(selected["price_source"], "last_trade_close")
        self.assertTrue(selected["wide_spread_fallback"])

    def test_narrow_book_uses_midpoint(self):
        candle = {
            "yes_bid": {"close_dollars": "0.40"},
            "yes_ask": {"close_dollars": "0.50"},
            "price": {"close_dollars": "0.10"},
        }
        selected = ladder_script.select_probability(candle, max_mid_spread=0.20)
        self.assertAlmostEqual(selected["probability"], 0.45)
        self.assertEqual(selected["price_source"], "yes_quote_midpoint")


class CandleRangeTest(unittest.TestCase):
    def test_market_open_time_defines_the_candle_search_start(self):
        timestamp = ladder_script.market_open_timestamp("2025-12-12T15:00:00Z")
        self.assertEqual(timestamp, 1765551600)

    def test_missing_market_open_time_is_not_replaced_by_an_arbitrary_window(self):
        self.assertIsNone(ladder_script.market_open_timestamp(None))


class EventMappingTest(unittest.TestCase):
    def test_exact_fiscal_period_wins_and_all_events_are_retained(self):
        panel = pd.DataFrame(
            [
                {
                    "ticker": "TEST",
                    "FE_FP_END": "2024-03-31",
                    "FISCAL_YEAR": 2024,
                    "FISCAL_QUARTER": 1,
                    "REPORT_DATE": "2024-05-01",
                    "published_at": "2024-04-30T20:00:00Z",
                    "surprise_early": 0.01,
                },
                {
                    "ticker": "TEST",
                    "FE_FP_END": "2024-06-30",
                    "FISCAL_YEAR": 2024,
                    "FISCAL_QUARTER": 2,
                    "REPORT_DATE": "2024-08-01",
                    "published_at": "2024-07-31T20:00:00Z",
                    "surprise_early": 0.02,
                },
            ]
        )
        features = pd.DataFrame(
            [
                {
                    "matched_ticker": "TEST",
                    "event_ticker": event,
                    "feature_date": feature_date,
                    "metric_label": metric,
                    "period_label": "Q1 2024",
                    "feature_family": "kpi_ladder",
                }
                for event, metric, feature_date in [
                    ("EVENT-A", "users", "2024-06-29T20:00:00Z"),
                    (
                        "EVENT-B",
                        "orders",
                        "2024-06-29T20:00:00.315950+00:00",
                    ),
                ]
            ]
        )
        joined = join_script.map_events_to_targets(panel, features, tolerance_days=90)
        self.assertEqual(len(joined), 2)
        self.assertEqual(set(joined["event_ticker"]), {"EVENT-A", "EVENT-B"})
        self.assertEqual(set(joined["FISCAL_QUARTER"]), {1})


class AwsCredentialSelectionTest(unittest.TestCase):
    def test_credentials_are_selected_from_one_env_file(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.env"
            second = Path(directory) / "second.env"
            first.write_text(
                "AWS_ACCESS_KEY_ID=first-key\n"
                "AWS_SECRET_ACCESS_KEY=first-secret\n"
            )
            second.write_text(
                "AWS_ACCESS_KEY_ID=second-key\n"
                "AWS_SECRET_ACCESS_KEY=second-secret\n"
                "AWS_SESSION_TOKEN=second-token\n"
            )
            with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(
                runner_script, "server_env_paths", return_value=[first, second]
            ):
                credentials = runner_script.aws_credentials()

        self.assertEqual(credentials["AWS_ACCESS_KEY_ID"], "first-key")
        self.assertEqual(credentials["AWS_SECRET_ACCESS_KEY"], "first-secret")
        self.assertEqual(credentials["AWS_SESSION_TOKEN"], "")


class LadderIdentificationTest(unittest.TestCase):
    def test_greater_or_equal_and_legacy_above_are_ladder_rungs(self):
        rows = pd.DataFrame(
            [
                {
                    "market_ticker": "A",
                    "strike_type": "greater_or_equal",
                    "floor_strike": 100,
                    "yes_sub_title": "100 or more",
                },
                {
                    "market_ticker": "B",
                    "strike_type": "structured",
                    "floor_strike": 110,
                    "yes_sub_title": "Above 110",
                },
                {
                    "market_ticker": "C",
                    "strike_type": None,
                    "floor_strike": None,
                    "yes_sub_title": "Above 120 million",
                },
            ]
        )
        rungs = features_script.survival_rungs(rows)
        self.assertEqual(set(rungs["market_ticker"]), {"A", "B", "C"})
        self.assertEqual(rungs.loc[rungs["market_ticker"].eq("C"), "ladder_strike"].iloc[0], 120_000_000)


class FactSetPanelTest(unittest.TestCase):
    def test_sql_uses_carbon_arc_consensus_timing(self):
        sql = factset_script.factset_sql(["X5HN6G-R"], date(2024, 1, 1))

        self.assertIn(
            "c.CONS_END_DATE <= DATEADD(day, 7, a.FE_FP_END)", sql
        )
        self.assertIn("c.CONS_END_DATE < a.REPORT_DATE", sql)
        self.assertNotIn("c.CONS_START_DATE <=", sql)

    def test_sse_response_is_parsed(self):
        tool_payload = {
            "success": True,
            "rows": [{"FSYM_ID": "X5HN6G-R", "ACTUAL": 1.0}],
        }
        envelope = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "content": [
                    {"type": "text", "text": json.dumps(tool_payload)}
                ]
            },
        }
        body = "event: message\ndata: " + json.dumps(envelope) + "\n\n"

        self.assertEqual(factset_script.parse_mcp_response(body), tool_payload)

    def test_fiscal_labels_and_surprises_are_computed_without_mutating_inputs(self):
        documents = pd.DataFrame(
            [
                {
                    "stock_id": "ID",
                    "FE_FP_END": "2026-04-30",
                    "name": "Q3 2026 earnings call",
                }
            ]
        )
        periods = factset_script.fiscal_period_map(documents)
        self.assertEqual(periods.iloc[0]["FISCAL_YEAR"], 2026)
        self.assertEqual(periods.iloc[0]["FISCAL_QUARTER"], 3)

        panel = pd.DataFrame(
            {
                "ticker": ["TEST"] * 5,
                "FE_FP_END": pd.date_range("2025-03-31", periods=5, freq="QE"),
                "REPORT_DATE": pd.date_range("2025-05-01", periods=5, freq="QE"),
                "CONS_EARLY_DATE": pd.date_range("2025-04-01", periods=5, freq="QE"),
                "CONS_PRINT_DATE": pd.date_range("2025-04-30", periods=5, freq="QE"),
                "ACTUAL": [100, 110, 120, 130, 150],
                "CONS_EARLY": [100, 100, 100, 100, 140],
                "CONS_PRINT": [100, 100, 100, 100, 145],
            }
        )
        result = factset_script.add_surprises(panel)
        self.assertAlmostEqual(result.iloc[-1]["surprise_early"], 10 / 140)
        self.assertEqual(result.iloc[-1]["actual_q4"], 100)
        self.assertNotIn("surprise_early", panel.columns)


class BenchmarkMetricTest(unittest.TestCase):
    def test_combined_skill_is_oos_r2(self):
        frame = pd.DataFrame(
            {
                "ticker": ["A", "B", "C"],
                "true_pct": [-1.0, 0.0, 2.0],
                "fin": [-0.5, 0.5, 1.0],
                "fin+kalshi_ladder": [-0.8, 0.2, 1.4],
                "fin+earnings_call": [-0.4, 0.1, 1.2],
                "fin+kalshi_ladder+earnings_call": [-0.9, 0.0, 1.8],
            }
        )
        statistics = analysis_script.benchmark_statistics(frame)
        combined = analysis_script.metrics(
            frame["fin+kalshi_ladder+earnings_call"], frame["true_pct"]
        )

        self.assertAlmostEqual(statistics[0], combined["corr"])
        self.assertAlmostEqual(statistics[2], combined["r2"])


class CutoffValidationTest(unittest.TestCase):
    def panel(self, candle_ts):
        ladders = [
            {
                "event_ticker": "EVENT",
                "rungs": [
                    {
                        "candle_ts": candle_ts,
                        "market_open_at": "2024-04-01T00:00:00+00:00",
                        "probability": 0.4,
                        "price_source": "last_trade_close",
                    },
                    {
                        "candle_ts": candle_ts,
                        "market_open_at": "2024-04-01T00:00:00+00:00",
                        "probability": 0.2,
                        "price_source": "last_trade_close",
                    },
                ],
            }
        ]
        return pd.DataFrame(
            [
                {
                    "published_at": "2024-05-01T20:00:00Z",
                    "pre_as_of_ts": 1714593540,
                    "pre_cutoff_source": "published_at_minus_buffer",
                    "pre_candle_search_rule": "market_open_to_publication_cutoff",
                    "pre_event_count": 1,
                    "pre_total_priced_rungs": 2,
                    "kalshi_ladders_json": json.dumps(ladders),
                }
            ]
        )

    def test_all_rungs_before_publication_pass(self):
        runner_script.validate_publication_cutoff(self.panel(1714590000))

    def test_rung_after_cutoff_fails(self):
        with self.assertRaises(SystemExit):
            runner_script.validate_publication_cutoff(self.panel(1714593600))


class ResumeTest(unittest.TestCase):
    def test_only_successful_calls_are_reused(self):
        records = [
            {
                "ticker": "TEST",
                "FE_FP_END": "2026-03-31",
                "arm": "fin",
                "repeat": 1,
                "prediction": 1.25,
                "confidence": 70,
                "rationale": "test",
                "estimated_cost_usd": 0.01,
                "error": "",
            },
            {
                "ticker": "TEST",
                "FE_FP_END": "2026-03-31",
                "arm": "fin",
                "repeat": 2,
                "prediction": None,
                "confidence": None,
                "rationale": "",
                "estimated_cost_usd": 0.0,
                "error": "timeout",
            },
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "calls.jsonl"
            path.write_text("".join(json.dumps(record) + "\n" for record in records))
            calls = runner_script.load_successful_calls(path)

        self.assertEqual(len(calls), 1)
        prediction, cost, error = calls[("TEST", "2026-03-31", "fin", 1)]
        self.assertEqual(prediction.predicted_revenue_surprise_pct, 1.25)
        self.assertEqual(cost, 0.01)
        self.assertEqual(error, "")


class BaselineAdapterTest(unittest.TestCase):
    def test_prior_call_uses_the_same_31_day_guard_as_factor1(self):
        documents = pd.DataFrame(
            [
                {
                    "ticker": "TEST",
                    "file_key": "too-recent",
                    "period_end_date": pd.Timestamp("2025-12-31"),
                    "call_at": pd.Timestamp("2026-02-15T20:00:00Z"),
                },
                {
                    "ticker": "TEST",
                    "file_key": "eligible",
                    "period_end_date": pd.Timestamp("2025-09-30"),
                    "call_at": pd.Timestamp("2025-11-01T20:00:00Z"),
                },
            ]
        )
        candidates = runner_script.prior_earnings_call_candidates(
            documents, "TEST", pd.Timestamp("2026-03-01")
        )
        self.assertEqual(candidates["file_key"].tolist(), ["eligible"])

    def test_only_x_arms_receive_raw_ladders(self):
        ladder = json.dumps(
            [
                {
                    "event_ticker": "EVENT",
                    "metric_label": "orders",
                    "period_label": "Q1 2026",
                    "n_priced_rungs": 1,
                    "n_ladder_markets": 1,
                    "monotonicity_violations": 0,
                    "rungs": [
                        {
                            "market_ticker": "EVENT-100",
                            "threshold_operator": ">=",
                            "strike": 100,
                            "probability": 0.4,
                            "price_source": "last_trade_close",
                            "yes_bid": None,
                            "yes_ask": None,
                            "last": 0.4,
                            "previous": 0.3,
                            "spread": None,
                            "candle_at": "2026-02-01T00:00:00+00:00",
                            "daily_volume": 10,
                            "open_interest": 20,
                        }
                    ],
                }
            ]
        )
        row = SimpleNamespace(
            ticker="TEST",
            FE_FP_END=pd.Timestamp("2026-03-31"),
            CONS_EARLY=100,
            pre_as_of_at="2026-02-28T23:59:00+00:00",
            kalshi_ladders_json=ladder,
        )
        history = pd.DataFrame(
            {
                "FE_FP_END": pd.date_range("2025-03-31", periods=3, freq="QE"),
                "ACTUAL": [90, 95, 98],
                "CONS_EARLY": [91, 94, 97],
                "surprise_early": [-0.01, 0.01, 0.01],
            }
        )
        prompts = runner_script.build_prompts(
            {
                "row": row,
                "history": history,
                "ladder_history": pd.DataFrame(),
                "earnings_call_text": "CALL_MARKER",
            }
        )
        self.assertNotIn("KALSHI RAW", prompts["fin"])
        self.assertIn("KALSHI RAW", prompts["fin+kalshi_ladder"])
        self.assertNotIn("CALL_MARKER", prompts["fin+kalshi_ladder"])
        self.assertIn("CALL_MARKER", prompts["fin+earnings_call"])
        self.assertIn("KALSHI RAW", prompts["fin+kalshi_ladder+earnings_call"])


if __name__ == "__main__":
    unittest.main()
