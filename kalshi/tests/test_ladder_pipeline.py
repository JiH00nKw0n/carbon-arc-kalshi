import importlib.util
import json
import unittest
from datetime import date
from pathlib import Path

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
inventory_script = load_script("s_af_kalshi_company_inventory")


class CompanyMappingTest(unittest.TestCase):
    def test_explicit_public_company_aliases_are_mapped(self):
        aliases = inventory_script.load_ticker_map()
        for company, ticker in {
            "NVIDIA Corporation": "NVDA",
            "Oracle Corporation": "ORCL",
            "Palantir Technologies Inc.": "PLTR",
            "Snowflake Inc.": "SNOW",
            "SoFi new members": "SOFI",
            "First Solar Inc.": "FSLR",
            "Talen Energy Corporation": "TLN",
        }.items():
            matched, _, _ = inventory_script.match_ticker(company, "", "", aliases)
            self.assertEqual(matched, ticker)

    def test_explicit_series_mapping_survives_a_market_text_conflict(self):
        aliases = inventory_script.load_ticker_map()
        series = {
            "ticker": "KXAMZN", "title": "Amazon KPI", "category": "Companies",
            "tags": ["KPIs"],
        }
        markets = [{"title": "Will Tesla report above 1?", "rules_primary": ""}]
        row = inventory_script.series_row(series, markets, aliases)
        self.assertEqual(row["matched_ticker"], "AMZN")
        self.assertIn("market_conflict", row["match_method"])

    def test_frozen_inventory_mapping_needs_no_carbon_arc_alias_file(self):
        aliases = inventory_script.load_ticker_map()
        inventory = pd.read_csv(
            ROOT / "kalshi" / "outputs" / "auto" / "kalshi_company_series.csv"
        ).fillna("")
        for row in inventory[inventory["matched_ticker"].ne("")].itertuples():
            matched, _, _ = inventory_script.match_ticker(
                row.company_name_guess, row.series_title, row.series_ticker, aliases
            )
            self.assertEqual(matched, row.matched_ticker, row.series_ticker)


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
        panel = pd.DataFrame([
            {
                "ticker": "TEST", "FE_FP_END": "2024-03-31", "FISCAL_YEAR": 2024,
                "FISCAL_QUARTER": 1, "REPORT_DATE": "2024-05-01",
                "published_at": "2024-04-30T20:00:00Z", "surprise_early": 0.01,
            },
            {
                "ticker": "TEST", "FE_FP_END": "2024-06-30", "FISCAL_YEAR": 2024,
                "FISCAL_QUARTER": 2, "REPORT_DATE": "2024-08-01",
                "published_at": "2024-07-31T20:00:00Z", "surprise_early": 0.02,
            },
        ])
        features = pd.DataFrame([
            {
                "matched_ticker": "TEST", "event_ticker": event,
                "feature_date": "2024-06-29T20:00:00Z", "metric_label": metric,
                "period_label": "Q1 2024", "feature_family": "kpi_ladder",
            }
            for event, metric in [("EVENT-A", "users"), ("EVENT-B", "orders")]
        ])
        joined = join_script.map_events_to_targets(panel, features, tolerance_days=90)
        self.assertEqual(len(joined), 2)
        self.assertEqual(set(joined["event_ticker"]), {"EVENT-A", "EVENT-B"})
        self.assertEqual(set(joined["FISCAL_QUARTER"]), {1})


class LadderIdentificationTest(unittest.TestCase):
    def test_greater_or_equal_and_legacy_above_are_ladder_rungs(self):
        rows = pd.DataFrame([
            {"market_ticker": "A", "strike_type": "greater_or_equal", "floor_strike": 100,
             "yes_sub_title": "100 or more"},
            {"market_ticker": "B", "strike_type": "structured", "floor_strike": 110,
             "yes_sub_title": "Above 110"},
            {"market_ticker": "C", "strike_type": None, "floor_strike": None,
             "yes_sub_title": "Above 120 million"},
        ])
        rungs = features_script.survival_rungs(rows)
        self.assertEqual(set(rungs["market_ticker"]), {"A", "B", "C"})
        self.assertEqual(rungs.loc[rungs["market_ticker"].eq("C"), "ladder_strike"].iloc[0], 120_000_000)


class FactSetPanelTest(unittest.TestCase):
    def test_sql_uses_carbon_arc_consensus_timing(self):
        sql = factset_script.factset_sql(["X5HN6G-R"], date(2024, 1, 1))
        self.assertIn("c.CONS_END_DATE <= DATEADD(day, 7, a.FE_FP_END)", sql)
        self.assertIn("c.CONS_END_DATE < a.REPORT_DATE", sql)
        self.assertNotIn("c.CONS_START_DATE <=", sql)

    def test_sse_response_is_parsed(self):
        tool_payload = {"success": True, "rows": [{"FSYM_ID": "X5HN6G-R", "ACTUAL": 1.0}]}
        envelope = {"jsonrpc": "2.0", "id": 1, "result": {"content": [
            {"type": "text", "text": json.dumps(tool_payload)}
        ]}}
        body = "event: message\ndata: " + json.dumps(envelope) + "\n\n"
        self.assertEqual(factset_script.parse_mcp_response(body), tool_payload)

    def test_fiscal_labels_and_surprises_are_computed_without_mutating_inputs(self):
        documents = pd.DataFrame([{
            "stock_id": "ID", "FE_FP_END": "2026-04-30", "name": "Q3 2026 earnings call"
        }])
        periods = factset_script.fiscal_period_map(documents)
        self.assertEqual(periods.iloc[0]["FISCAL_YEAR"], 2026)
        self.assertEqual(periods.iloc[0]["FISCAL_QUARTER"], 3)

        panel = pd.DataFrame({
            "ticker": ["TEST"] * 5,
            "FE_FP_END": pd.date_range("2025-03-31", periods=5, freq="QE"),
            "REPORT_DATE": pd.date_range("2025-05-01", periods=5, freq="QE"),
            "CONS_EARLY_DATE": pd.date_range("2025-04-01", periods=5, freq="QE"),
            "CONS_PRINT_DATE": pd.date_range("2025-04-30", periods=5, freq="QE"),
            "ACTUAL": [100, 110, 120, 130, 150],
            "CONS_EARLY": [100, 100, 100, 100, 140],
            "CONS_PRINT": [100, 100, 100, 100, 145],
        })
        result = factset_script.add_surprises(panel)
        self.assertAlmostEqual(result.iloc[-1]["surprise_early"], 10 / 140)
        self.assertEqual(result.iloc[-1]["actual_q4"], 100)
        self.assertNotIn("surprise_early", panel.columns)


if __name__ == "__main__":
    unittest.main()
