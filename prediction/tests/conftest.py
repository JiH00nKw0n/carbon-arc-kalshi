"""Shared pytest fixtures — tiny synthetic panels, fake boundary doubles, a FakeLLMClient.

Everything here is offline and seeded. The fakes are duck-typed against the contracts the plan
documents for the leaf modules (Sections 1/4/7), so tests exercise real behavior without touching
the network or the expensive read-only artifacts under factor1/data.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

# Make `import prediction` resolve when pytest is invoked from anywhere.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from prediction.channels.specs import get_channel  # noqa: E402
from prediction.config.schema import RunCfg  # noqa: E402
from prediction.domain.records import (  # noqa: E402
    AltPoint,
    CallRef,
    PanelRow,
    RevenueRecord,
    Target,
)
from prediction.registry import Registry  # noqa: E402
from prediction.targets.schemas import BPredictSurprise, BPredictYoY  # noqa: E402


# --------------------------------------------------------------------------- fakes
@dataclass
class FakeLLMResult:
    """Stand-in for the boundary LLMResult: only the parsed schema object is load-bearing."""
    parsed: Any
    cost: float = 0.0


class FakeLLMClient:
    """Offline LLM double: hands back canned parsed schema objects in call order (then repeats)."""

    def __init__(self, canned: list[Any]):
        self._canned = list(canned)
        self._i = 0

    def predict_structured(self, *args, **kwargs) -> FakeLLMResult:
        obj = self._canned[self._i % len(self._canned)]
        self._i += 1
        return FakeLLMResult(parsed=obj)


class FakeTranscriptStore:
    """Duck-typed TranscriptStore: enforces the <= report-31d leakage rule over a fixed call list.

    ``texts`` optionally maps a call path to its transcript body, so a test can assert that the
    RIGHT transcript is interleaved into the prompt; unmapped paths fall back to a stable stub.
    """

    def __init__(self, calls: list[CallRef], texts: dict[str, str] | None = None):
        self._calls = sorted(calls, key=lambda c: c.call_date)
        self._texts = texts or {}

    def prior_calls(self, ticker: str, report, k: int) -> list[CallRef]:
        rep = pd.Timestamp(report).date()
        eligible = [c for c in self._calls
                    if c.ticker == ticker and c.call_date <= rep - timedelta(days=31)]
        return eligible[-k:][::-1]  # most-recent first, like factor1 prior_calls

    def read_text(self, path: str) -> str:
        return self._texts.get(path, f"TRANSCRIPT::{path}")


class FakeDescriptions:
    """Duck-typed DescriptionProvider: company_profile() + dataset_description()."""

    def __init__(self, profile: str, dataset: str):
        self._profile = profile
        self._dataset = dataset

    def company_profile(self, ticker: str) -> str:
        return self._profile

    def dataset_description(self, channel: str) -> str:
        return self._dataset


class _ChannelBoundDescriptions:
    """Channel-bound view of a DescriptionProvider double.

    Mirrors ``run.experiment._ChannelDescriptions``: the TOOL variant's ``get_alt_data_description``
    tool calls ``dataset_description()`` with NO args, so the provider's channel arg is pre-bound here.
    """

    def __init__(self, provider: FakeDescriptions, channel_name: str):
        self._provider = provider
        self._channel = channel_name

    def company_profile(self, ticker: str) -> str:
        return self._provider.company_profile(ticker)

    def dataset_description(self) -> str:
        return self._provider.dataset_description(self._channel)


# --------------------------------------------------------------------------- builders
def _panel_row(ticker: str, fp: date, report: date, actual: float,
               cons_early: float, cons_print: float, prior: float | None,
               x_abs: float, x_yoy: float, surprise_early: float) -> PanelRow:
    sp = (actual - cons_print) / cons_print if cons_print else None
    yoy = (actual - prior) / prior if prior else None
    return PanelRow(
        ticker=ticker, fp_end=fp, report_date=report, actual=actual,
        cons_early=cons_early, cons_print=cons_print, prior_year_actual=prior,
        x_abs=x_abs, x_yoy=x_yoy, x_yoy_3m=x_yoy, surprise_early=surprise_early,
        surprise_print=sp, rev_yoy=yoy, lag_surprise=None, strength="strong",
    )


# --------------------------------------------------------------------------- fixtures
@pytest.fixture
def hand_row() -> PanelRow:
    """One hand-computed panel row: actual 110 vs cons_early 100 / cons_print 105 / prior 88."""
    return _panel_row("AAA", date(2025, 12, 31), date(2026, 2, 1), actual=110.0,
                      cons_early=100.0, cons_print=105.0, prior=88.0,
                      x_abs=1.0, x_yoy=0.20, surprise_early=0.10)


@pytest.fixture
def fake_llm() -> FakeLLMClient:
    """A FakeLLMClient whose canned outputs are the two structured schemas at revenue level 110."""
    surprise = BPredictSurprise(predicted_revenue_musd=110.0, consensus_revenue_musd=100.0,
                                predicted_surprise_pct=10.0, confidence=50, rationale="canned")
    yoy = BPredictYoY(predicted_revenue_musd=110.0, prior_year_revenue_musd=88.0,
                      predicted_rev_yoy_pct=25.0, confidence=50, rationale="canned")
    return FakeLLMClient([surprise, yoy])


@pytest.fixture
def leakage_panel() -> pd.DataFrame:
    """Eight quarters for one ticker; reports straddle the 2025-12-01 cutoff (q7/q8 post-cutoff)."""
    quarters = [
        (date(2024, 6, 30), date(2024, 8, 1), 0.010),
        (date(2024, 9, 30), date(2024, 11, 1), 0.011),
        (date(2024, 12, 31), date(2025, 2, 1), 0.012),
        (date(2025, 3, 31), date(2025, 5, 1), 0.013),
        (date(2025, 6, 30), date(2025, 8, 1), 0.014),
        (date(2025, 9, 30), date(2025, 11, 1), 0.015),   # report <= cutoff -> not a target
        (date(2025, 12, 31), date(2026, 2, 1), 0.030),   # post-cutoff target
        (date(2026, 3, 31), date(2026, 5, 1), 0.050),    # post-cutoff target
    ]
    rows = []
    for i, (fp, rep, surp) in enumerate(quarters):
        actual = 100.0 + i
        rows.append(dict(
            ticker="AAA", FE_FP_END=pd.Timestamp(fp), REPORT_DATE=pd.Timestamp(rep),
            ACTUAL=actual, CONS_EARLY=actual / (1 + surp), CONS_PRINT=actual / (1 + surp),
            surprise_early=surp, surprise_print=surp, rev_yoy=0.2, prior_year_actual=actual / 1.2,
            x_abs=1000.0 + i, x_yoy=0.05 + i / 100, x_yoy_3m=0.05, lag_surprise=None,
            strength="strong",
        ))
    return pd.DataFrame(rows)


@pytest.fixture
def leakage_store() -> FakeTranscriptStore:
    """Two calls, both comfortably older than report-31d for every post-cutoff quarter."""
    return FakeTranscriptStore([
        CallRef("AAA", date(2025, 8, 15), "/x/AAA_2025Q2.txt"),
        CallRef("AAA", date(2025, 11, 15), "/x/AAA_2025Q3.txt"),
    ])


@pytest.fixture
def run_cfg() -> RunCfg:
    return RunCfg(cutoff=date(2025, 12, 1))


@pytest.fixture
def revenue_records() -> list[RevenueRecord]:
    """Eight quarterly revenue events for one ticker (enough for pct_change(4) / shift(4))."""
    ends = pd.date_range("2024-03-31", periods=8, freq="QE")
    out = []
    for i, ts in enumerate(ends):
        actual = 100.0 + 10 * i
        out.append(RevenueRecord(
            ticker="AAA", fp_end=ts.date(),
            report_date=(ts + pd.Timedelta(days=30)).date(),
            actual=actual, cons_early=actual * 0.98, cons_print=actual * 0.99,
        ))
    return out


@pytest.fixture
def alt_points() -> list[AltPoint]:
    """Eight quarterly alt-data points on the same dates (card geometry: yoy_lag=4)."""
    ends = pd.date_range("2024-03-31", periods=8, freq="QE")
    return [AltPoint(ticker="AAA", date=ts.date(), value=500.0 + 25 * i)
            for i, ts in enumerate(ends)]


@pytest.fixture
def prompt_target() -> Target:
    """A single post-cutoff Target with four history rows and a uniquely markable transcript."""
    hist = tuple(
        _panel_row("AAA", date(2024, 12, 31), date(2025, 2, 1), 100.0 + i, 98.0 + i, 99.0 + i,
                   80.0 + i, x_abs=1_000_000.0 + i, x_yoy=0.05 + i / 100, surprise_early=0.02 + i / 100)
        for i in range(4)
    )
    row = _panel_row("AAA", date(2025, 12, 31), date(2026, 2, 1), 130.0, 125.0, 126.0, 110.0,
                     x_abs=1_300_000.0, x_yoy=0.18, surprise_early=0.0)
    return Target(
        ticker="AAA", fp=date(2025, 12, 31), report=date(2026, 2, 1),
        true=0.04, x_yoy=0.18, strength="strong", row=row, hist=hist,
        text="ZZTEXTMARKERZZ management discussed strong demand.",
        text2="ZZTEXT2MARKERZZ prior-quarter call.", call_path="/x/AAA_2025Q3.txt",
    )


@pytest.fixture
def descriptions() -> FakeDescriptions:
    return FakeDescriptions(profile="ACMEPROFILEMARKER retailer of goods.",
                            dataset="CARDDATASETMARKER daily card spend.")


@pytest.fixture
def render_prompt():
    """Render a registered prompt variant. Single choke point for the builder call convention.

    Mirrors production wiring (``predict.llm_predictor._predict_arm``): the registered BASE prompt
    builder has the signature ``build(target, transcript_store, description_provider, channel_spec,
    y_target, arm_blocks, n_calls, hist_rows) -> str``. The description provider is channel-bound
    (like ``run.experiment._ChannelDescriptions``) so its ``dataset_description()`` is called with no
    args, and a FakeTranscriptStore stands in for the leakage-safe call reader.
    """
    cfg = RunCfg(cutoff=date(2025, 12, 1))  # source the real n_calls / hist_rows defaults

    def _render(variant: str, target, arm, ytarget, channel, descriptions) -> str:
        builder = Registry.get("prompt", variant)
        store = FakeTranscriptStore([CallRef(target.ticker, date(2024, 11, 15), target.call_path)],
                                    texts={target.call_path: target.text})
        provider = _ChannelBoundDescriptions(descriptions, channel.name)
        return builder(target, store, provider, channel, ytarget,
                       arm.blocks, cfg.n_calls, cfg.hist_rows)  # type: ignore[operator]

    return _render


@pytest.fixture
def card_channel():
    return get_channel("card")
