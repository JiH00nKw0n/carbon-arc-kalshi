"""Test 1 — leakage guards.

Two rules, tested where each lives:
  * TranscriptStore.prior_calls enforces call_date <= report - 31d (a call at report-10d is excluded).
  * build_targets only emits post-cutoff events (report > cutoff), never in-sample rows.
"""
from datetime import date
from types import SimpleNamespace

import pandas as pd
import pytest

from prediction.data.transcripts import TranscriptStore
from prediction.panel.targets import build_targets
from prediction.targets.ytarget import get_y_target


# --------------------------------------------------------------- 31-day call rule (TranscriptStore)
@pytest.fixture
def call_index(tmp_path):
    """A transcript index with one recent (report-10d) call that must be filtered out."""
    report = date(2026, 2, 1)                      # report - 31d == 2026-01-01
    calls = {
        date(2025, 10, 4): "old.txt",              # report - 120d  (eligible)
        date(2025, 12, 23): "mid.txt",             # report - 40d   (eligible)
        date(2026, 1, 22): "recent.txt",           # report - 10d   (LEAK -> excluded)
    }
    rows = []
    for cd, name in calls.items():
        path = tmp_path / name
        path.write_text(f"call on {cd}")
        rows.append(dict(ticker="AAA", call_date=cd.isoformat(), path=str(path)))
    idx = tmp_path / "transcript_index.csv"
    pd.DataFrame(rows).to_csv(idx, index=False)
    return idx, report


def test_prior_calls_excludes_a_call_inside_31_days(call_index):
    idx, report = call_index
    store = TranscriptStore(SimpleNamespace(tx_index=str(idx)))
    got = store.prior_calls("AAA", report, 3)

    dates = {pd.Timestamp(c.call_date).date() for c in got}
    assert date(2026, 1, 22) not in dates                       # the report-10d call is gone
    cutoff = date(2026, 1, 1)                                    # report - 31d
    assert all(d <= cutoff for d in dates)
    assert dates == {date(2025, 10, 4), date(2025, 12, 23)}


# ------------------------------------------------------------------ cutoff rule (build_targets)
def test_targets_are_only_post_cutoff(leakage_panel, leakage_store, run_cfg):
    targets = build_targets(leakage_panel, leakage_store, get_y_target("surprise_early"), run_cfg)

    assert targets, "expected at least one post-cutoff target"
    for t in targets:
        assert pd.Timestamp(t.report) > pd.Timestamp(run_cfg.cutoff)

    reports = {pd.Timestamp(t.report).date() for t in targets}
    assert reports == {date(2026, 2, 1), date(2026, 5, 1)}       # q7, q8 only
    assert date(2025, 11, 1) not in reports                     # q6 (report <= cutoff) excluded


def test_target_true_reads_the_active_y_column(leakage_panel, leakage_store, run_cfg):
    targets = build_targets(leakage_panel, leakage_store, get_y_target("surprise_early"), run_cfg)
    trues = sorted(round(t.true, 4) for t in targets)
    assert trues == [0.030, 0.050]                              # the two post-cutoff surprise_early


def test_each_target_keeps_at_least_three_history_rows(leakage_panel, leakage_store, run_cfg):
    targets = build_targets(leakage_panel, leakage_store, get_y_target("surprise_early"), run_cfg)
    assert all(len(t.hist) >= 3 for t in targets)
