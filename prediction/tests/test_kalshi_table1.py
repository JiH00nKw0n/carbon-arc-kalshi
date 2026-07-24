import pandas as pd

from kalshi.scripts.auto import s_ay_kalshi_table1_ablation as table1


def _predictions():
    rows = []
    for target in range(21):
        for seed in (1, 2, 3):
            rows.append({
                "ticker": f"T{target:02d}",
                "fp": pd.Timestamp("2026-03-31"),
                "seed": seed,
                "true_pct": float(target),
                "exact_two_call_eligible": target < 19,
                "fin": target + seed,
                "fin+x": target + seed / 2,
                "fin+text": target - seed / 2,
                "fin+x+text": target - seed,
            })
    return pd.DataFrame(rows)


def _tool_records():
    records = []
    for variant, offset in (("BASE", 2.0), ("TOOL", -2.0)):
        for seed in (1, 2, 3):
            records.append({
                "seed": seed,
                "y": "rev_yoy",
                "variant": variant,
                "preds": pd.DataFrame({
                    "tkr": [f"T{target:02d}" for target in range(21)],
                    "fp": ["2026-03-31"] * 21,
                    "true": [target / 100 for target in range(21)],
                    "fin+x+text": [
                        target + offset + seed / 10 for target in range(21)
                    ],
                }),
            })
    return records


def test_average_repetitions_preserves_both_frozen_samples():
    averaged = table1.average_repetitions(_predictions(), expected_reps=3)

    counts = averaged.groupby("sample").size().to_dict()
    assert counts == {"exact_two_call_19": 19, "full_21": 21}
    first = averaged[
        averaged["sample"].eq("full_21") & averaged["ticker"].eq("T00")
    ].iloc[0]
    assert first["fin"] == 2.0
    assert first["fin+x"] == 1.0
    assert first["fin+text"] == -1.0
    assert first["fin+x+text"] == -2.0


def test_table1_bootstrap_and_latex_are_reproducible(tmp_path):
    averaged = table1.average_repetitions(_predictions(), expected_reps=3)
    first = table1.company_cluster_bootstrap(averaged, reps=10, seed=7)
    second = table1.company_cluster_bootstrap(averaged, reps=10, seed=7)

    pd.testing.assert_frame_equal(first, second)
    summary = table1.summarize(averaged, first)
    table1.render_table1_latex(summary, tmp_path)

    primary = (tmp_path / "kalshi_ablation.tex").read_text()
    rows = (tmp_path / "kalshi_ablation_overleaf_rows.tex").read_text()
    assert r"\pm" in primary
    assert "company-clustered bootstrap" in primary
    assert "Kalshi prediction markets" in rows
    assert r"$H+X+Z$" in rows


def test_tool_use_error_bars_match_current_overleaf_layout(tmp_path):
    averaged = table1.average_tool_settings(
        _tool_records(),
        _predictions(),
        expected_reps=3,
    )
    bootstrap = table1.company_cluster_bootstrap(
        averaged,
        reps=10,
        seed=7,
        methods=table1.TOOL_SETTINGS,
    )
    summary = table1.summarize(
        averaged,
        bootstrap,
        methods=table1.TOOL_SETTINGS,
    )
    table1.render_tool_use_latex(summary, tmp_path)

    counts = averaged.groupby("sample").size().to_dict()
    assert counts == {"exact_two_call_19": 19, "full_21": 21}
    rows = (tmp_path / "kalshi_tool_fvu_mae_overleaf_rows.tex").read_text()
    assert "Without tool use" in rows
    assert "With tool use" in rows
    assert r"\pm" in rows
