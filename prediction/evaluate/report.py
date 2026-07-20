"""Render an EvalResult to an idempotent Markdown report.

Sections: a results table (every arm + baseline, rmse/r2/calib/corr), the super-additivity
synergy block, and the shuffle-company surrogate line. Rewriting the same EvalResult produces
byte-identical output, so reruns are safe.

Expected shapes on the EvalResult (filled by the run layer):
  metrics_table : list of {model, rmse, r2, corr, ...} — one row per arm/baseline.
  calib         : list of {model, calib_r2} — calibrated R²(OOF) per LLM arm (may be empty).
  synergy       : the raw dict returned by `boot_synergy` (lists under r_fwt/skill_fwt/
                  syn_corr/syn_skill); summarized to mean / 95% CI / p(≤0) at render time.
  surrogate     : the surrogate p-value for the headline arm.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from prediction.domain.records import EvalResult

__all__ = ["write_markdown"]

# Synergy rows in factor1's display order: headline level, then the super-additivity contrast.
_SYNERGY_ROWS = (
    ("r_fwt", "corr(fin+x+text)"),
    ("syn_corr", "synergy(corr)"),
    ("skill_fwt", "skill(fin+x+text)"),
    ("syn_skill", "synergy(MSE-skill)"),
)


def write_markdown(result: EvalResult, path) -> None:
    """Write `result` to `path` as Markdown, overwriting any existing file (idempotent)."""
    sections = [
        _title(result),
        _results_table(result.metrics_table, _calib_by_model(result.calib)),
        _synergy_block(result.synergy),
        _surrogate_line(result.surrogate),
    ]
    Path(path).write_text("\n\n".join(sections) + "\n")


def _title(result: EvalResult) -> str:
    return (f"# Evaluation — channel={result.channel} · Y={result.y} · variant={result.variant}\n\n"
            f"Matched post-cutoff test set: n={result.rows} rows.")


def _calib_by_model(calib_rows: list[dict]) -> dict:
    """Map model name -> calibrated R²(OOF), the calib column's source."""
    return {row["model"]: row["calib_r2"] for row in calib_rows}


def _results_table(rows: list[dict], calib_by_model: dict) -> str:
    header = ["## results", "",
              "| model | RMSE | R² | calib R²(OOF) | corr |",
              "|---|---|---|---|---|"]
    body = [_results_row(row, calib_by_model) for row in rows]
    return "\n".join(header + body)


def _results_row(row: dict, calib_by_model: dict) -> str:
    calib = calib_by_model.get(row["model"], row.get("calib"))
    return (f"| {row['model']} | {row['rmse']:.2f} | {row['r2']:+.3f} | "
            f"{_signed(calib)} | {row['corr']:+.3f} |")


def _synergy_block(synergy: dict) -> str:
    lines = ["## synergy — super-additivity (company-clustered bootstrap)", "",
             "| quantity | mean | 95% CI | p(≤0) |", "|---|---|---|---|"]
    for key, label in _SYNERGY_ROWS:
        mean, lo, hi, p = _summarize(synergy[key])
        flag = " ✅" if p < 0.05 else ""
        lines.append(f"| {label} | {mean:+.3f} | [{lo:+.3f}, {hi:+.3f}] | {p:.3f}{flag} |")
    lines += ["",
              "synergy = M(fin+x+text) − [M(fin+x)+M(fin+text)−M(fin)]; >0 ⇒ X and Z super-additive."]
    return "\n".join(lines)


def _surrogate_line(p: float) -> str:
    flag = " ✅ firm-specific" if p < 0.05 else ""
    return f"## shuffle-company surrogate (fin+x+text)\n\np_surr = {p:.3f}{flag}"


def _summarize(values) -> tuple[float, float, float, float]:
    """Bootstrap distribution -> (mean, 2.5th pct, 97.5th pct, fraction ≤ 0)."""
    sample = np.asarray(values, float)
    lo, hi = np.percentile(sample, [2.5, 97.5])
    return float(sample.mean()), float(lo), float(hi), float((sample <= 0).mean())


def _signed(value) -> str:
    return "—" if value is None else f"{value:+.3f}"
