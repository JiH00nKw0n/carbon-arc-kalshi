import hashlib
from types import SimpleNamespace

import pandas as pd
import pytest

from kalshi.scripts.auto import s_av_kalshi_paper_artifacts as artifacts
from kalshi.scripts.auto import s_aw_kalshi_repair_calls as repair
from prediction.targets.ytarget import get_y_target


def _metric(y, variant, model, value):
    return {
        "y": y,
        "variant": variant,
        "model": model,
        "rmse": value,
        "r2": value,
        "calib_r2": value,
        "corr": value,
        "mae": value,
        "sign": value,
    }


def test_validate_calls_requires_complete_rationale():
    preds = pd.DataFrame([{
        "tkr": "AAA",
        "fp": "2026-03-31",
        "fin": 1.0,
        "fin+x": 1.0,
        "fin+text": 1.0,
        "fin+x+text": 1.0,
    }])
    calls = [{
        "status": "ok",
        "seed": 2026,
        "target": "rev_yoy",
        "variant": "TOOL",
        "ticker": "AAA",
        "fiscal_period_end": "2026-03-31",
        "arm": arm,
        "prompt_protocol": "paper",
        "system_prompt": artifacts.get_y_target("rev_yoy").paper_system_prompt,
        "user_prompt": "prompt",
        "prompt_sha256": "a" * 64,
        "parsed_output": {
            "predicted_revenue_musd": 100.0,
            "confidence": 50,
            "rationale": "reason",
        },
    } for arm in artifacts.ARMS]
    for call in calls:
        call["user_prompt"] = (
            "| quarter | revenue ($M) | revenue YoY |\n"
            "|---|---|---|\n"
            "| 2026-03-31 | ??? | PREDICT <- |"
        )
        call["prompt_sha256"] = hashlib.sha256(
            call["user_prompt"].encode("utf-8")
        ).hexdigest()

    artifacts.validate_calls(calls, preds, 2026, "rev_yoy", "TOOL")
    calls[-1]["parsed_output"]["rationale"] = ""

    with pytest.raises(RuntimeError, match="rationale"):
        artifacts.validate_calls(calls, preds, 2026, "rev_yoy", "TOOL")


def test_validate_variant_prompt_identity_requires_byte_identical_prompts():
    base = {
        "seed": 2026,
        "y": "rev_yoy",
        "variant": "BASE",
        "calls": [{
            "ticker": "AAA",
            "fiscal_period_end": "2026-03-31",
            "arm": "fin",
            "user_prompt": "same",
        }],
    }
    tool = {
        **base,
        "variant": "TOOL",
        "calls": [{**base["calls"][0], "user_prompt": "same"}],
    }
    artifacts.validate_variant_prompt_identity([base, tool])
    tool["calls"][0]["user_prompt"] = "different"

    with pytest.raises(RuntimeError, match="differ"):
        artifacts.validate_variant_prompt_identity([base, tool])


def test_repair_reconstructs_one_matched_target_row():
    calls = [{
        "status": "ok",
        "ticker": "AAA",
        "fiscal_period_end": "2026-03-31",
        "report_date": "2026-05-01",
        "arm": arm,
        "derived_prediction_pct": float(index),
        "tool_calls": ["get_company_profile"] if index else [],
    } for index, arm in enumerate(repair.ARMS)]
    panel_row = SimpleNamespace(
        surprise_print=0.05,
        x_yoy=0.10,
        CONS_PRINT=100.0,
    )

    row = repair.reconstructed_row(
        calls, panel_row, get_y_target("surprise_print")
    )

    assert row["tkr"] == "AAA"
    assert row["true"] == pytest.approx(0.05)
    assert row["fin+x+text"] == pytest.approx(3.0)
    assert row["tool_calls__fin+x"] == "get_company_profile"
    assert repair.extract_prediction(
        get_y_target("surprise_print"), 110.0, panel_row
    ) == pytest.approx(10.0)


def test_accuracy_reports_analyst_and_method_mae():
    records = [{
        "seed": 2026,
        "y": "surprise_early",
        "variant": "TOOL",
        "preds": pd.DataFrame({
            "true": [0.10, -0.20],
            artifacts.HEADLINE: [8.0, -15.0],
        }),
    }]

    per_rep, mean = artifacts.accuracy(records)

    assert per_rep.iloc[0]["analyst_mae"] == pytest.approx(15.0)
    assert per_rep.iloc[0]["method_mae"] == pytest.approx(3.5)
    assert mean.iloc[0]["analyst_mae"] == pytest.approx(15.0)
    assert mean.iloc[0]["method_mae"] == pytest.approx(3.5)


def test_exact_two_call_manifest_keeps_one_matched_target_set():
    rows = []
    for y in artifacts.TARGET_LABELS:
        rows.extend([
            {
                "y": y,
                "ticker": "AAA",
                "FE_FP_END": "2026-03-31",
                "earnings_call_count": 2,
            },
            {
                "y": y,
                "ticker": "BBB",
                "FE_FP_END": "2025-12-31",
                "earnings_call_count": 1,
            },
        ])

    selected = artifacts.exact_two_call_manifest(pd.DataFrame(rows))

    assert len(selected) == 3
    assert set(selected["ticker"]) == {"AAA"}
    assert selected.groupby("y").size().eq(1).all()
    assert selected["earnings_call_count"].eq(2).all()


def test_paper_renderers_write_html_and_latex(tmp_path, monkeypatch):
    figures = tmp_path / "figures"
    tables = tmp_path / "tables"
    monkeypatch.setattr(artifacts, "FIGURES", figures)
    monkeypatch.setattr(artifacts, "TABLES", tables)

    accuracy = pd.DataFrame([
        {
            "target": "surprise_early",
            "n": 22,
            "analyst_rmse": 4.5,
            "method_rmse": 3.5,
            "win_rate_pct": 55.0,
        },
        {
            "target": "surprise_print",
            "n": 22,
            "analyst_rmse": 3.8,
            "method_rmse": 3.6,
            "win_rate_pct": 54.0,
        },
    ])
    artifacts.render_accuracy(accuracy)
    artifacts.render_qualitative([{
        "ticker": "AAA",
        "target": "surprise_early",
        "representative_seed": 2026,
        "actual_revenue_musd": 110.0,
        "actual_surprise_pct": 10.0,
        "anchor_revenue_musd": 100.0,
        "prior_year_revenue_musd": 90.0,
        "model_revenue_musd": 108.0,
        "model_surprise_pct": 8.0,
        "without_x_revenue_musd": 102.0,
        "without_x_surprise_pct": 2.0,
        "ladder_summary": "KPI above 10: 70%",
        "rationale": "The Kalshi market probability supports demand.",
        "metric_label": "company KPI",
    }])
    artifacts.render_screen([{
        "company_name": "AAA Corp",
        "ticker": "AAA",
        "metric_label": "company KPI",
        "impact": "O",
        "reason": "The KPI is a clean revenue driver.",
    }])

    rows = []
    for index, model in enumerate(artifacts.ARMS):
        rows.append(_metric("rev_yoy", "TOOL", model, 0.1 + index / 10))
    rows.extend([
        _metric("rev_yoy", "TOOL", "N0", 0.2),
        _metric("rev_yoy", "TOOL", "N2", 0.3),
        _metric("rev_yoy", "BASE", artifacts.HEADLINE, 0.4),
    ])
    screen = pd.DataFrame([
        {"ticker": "AAA", "metric_label": "company KPI", "impact": "O"},
        {"ticker": "AAA", "metric_label": "vanity KPI", "impact": "X"},
    ])
    metric_screen = pd.DataFrame([
        {"ticker": "AAA", "impact": "O"},
        {"ticker": "AAA", "impact": "X"},
    ])
    auto = tmp_path / "auto"
    auto.mkdir()
    metric_screen.to_csv(auto / "kalshi_kpi_revenue_screen.csv", index=False)
    monkeypatch.setattr(artifacts, "AUTO", auto)
    manifest = pd.DataFrame([
        {"y": "surprise_early", "ticker": "AAA"},
        {"y": "surprise_print", "ticker": "AAA"},
        {"y": "rev_yoy", "ticker": "AAA"},
    ])
    synergy = {
        "syn_corr": {"mean": 0.1, "ci_low": -0.1, "ci_high": 0.3},
        "syn_skill": {"mean": 0.2, "ci_low": -0.2, "ci_high": 0.4},
    }
    artifacts.render_tables(
        pd.DataFrame(rows), {("rev_yoy", "TOOL"): synergy}, screen, manifest
    )
    table2_rows = []
    for sample_name, n in (("full_21", 21), ("exact_two_call_19", 19)):
        for index, (method, label) in enumerate((
            ("historical_average", "Historical Avg."),
            ("ols", "OLS"),
            ("gbt", "GBT"),
            ("ensembled_llm", "Ensembled LLM"),
            ("our_method", "Our Method"),
        )):
            table2_rows.append({
                "sample": sample_name,
                "method": method,
                "label": label,
                "n": n,
                "firms": 16,
                "fvu": 0.5 - index / 20,
                "fvu_bootstrap_sd": 0.05,
                "mae": 5.0 - index / 2,
                "mae_bootstrap_sd": 0.5,
            })
    artifacts.render_table2_latex(pd.DataFrame(table2_rows), tables)
    artifacts.render_exact_two_call_tables(
        pd.DataFrame(rows), {("rev_yoy", "TOOL"): synergy}, 19
    )

    assert "Kalshi" in (figures / "kalshi_accuracy_chart.html").read_text()
    assert "Model rationale" in (figures / "kalshi_qualitative_figure.html").read_text()
    assert "Screening rationale" in (figures / "kalshi_screen_figure.html").read_text()
    assert "Ensembled LLM" in (tables / "kalshi_baselines.tex").read_text()
    assert "FVU" in (tables / "kalshi_baselines.tex").read_text()
    assert "19 company-quarters" in (
        tables / "kalshi_baselines_exact_two_call.tex"
    ).read_text()
    assert "three independent runs" in (tables / "kalshi_tool.tex").read_text()
    for name in ("kalshi_synergy.tex", "kalshi_baselines.tex", "kalshi_tool.tex"):
        assert "MAE" in (tables / name).read_text()
    assert "Latest-consensus revenue surprise" in (
        tables / "kalshi_full_grid.tex"
    ).read_text()
    assert "MAE" in (tables / "kalshi_exact_two_call.tex").read_text()
    assert "exact-two-call sensitivity" in (
        tables / "kalshi_exact_two_call_full_grid.tex"
    ).read_text()
