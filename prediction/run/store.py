"""Idempotent, resumable result store keyed by full cell identity.

Cell identity is (channel, Y, variant, model, effort, seed) — the model/effort/seed are folded
into the directory slug so that changing any knob writes a fresh cell instead of silently reusing
stale predictions (plan risk 5). `done` reports whether a cell's report already exists, so a rerun
skips completed cells; `write_preds` also drops a jsonl log of every completed (target, arm) for
observability and partial-resume tooling. Command-query separation: `done`/`report_path` are pure
queries; the `write_*` methods are the only writers.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from prediction.domain.records import EvalResult
from prediction.evaluate.report import write_markdown
from prediction.run.grid import Cell

__all__ = ["ResultStore"]

_META_COLS = ("tkr", "true", "x_yoy", "k")


class ResultStore:
    """Filesystem home for one experiment's cells: report.md, preds.csv, resume.jsonl per cell."""

    def __init__(self, output_dir: str, model: str, effort: str, seed: int):
        self._root = Path(output_dir)
        self._model = model
        self._effort = effort
        self._seed = seed

    def done(self, cell: Cell) -> bool:
        """True once the cell's report has been written (the idempotent skip signal)."""
        return self._report_file(cell).exists()

    def report_path(self, cell: Cell) -> Path:
        """Path to the cell's report, creating the cell directory if needed."""
        return self._cell_dir(cell) / "report.md"

    def write_preds(self, cell: Cell, preds: pd.DataFrame) -> None:
        """Persist the raw per-target arm predictions and the (target, arm) resume log."""
        preds.to_csv(self._cell_dir(cell) / "preds.csv", index=False)
        self._write_resume_log(cell, preds)

    def write_report(self, cell: Cell, result: EvalResult) -> None:
        """Render the cell's evaluation to Markdown (overwrites; byte-stable on rerun)."""
        write_markdown(result, self.report_path(cell))

    def _write_resume_log(self, cell: Cell, preds: pd.DataFrame) -> None:
        arm_cols = [c for c in preds.columns if c not in _META_COLS]
        lines = [json.dumps({"tkr": row["tkr"], "arm": arm})
                 for _, row in preds.iterrows() for arm in arm_cols]
        (self._cell_dir(cell) / "resume.jsonl").write_text("\n".join(lines) + ("\n" if lines else ""))

    def _cell_dir(self, cell: Cell) -> Path:
        directory = self._root / self._slug(cell)
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def _report_file(self, cell: Cell) -> Path:
        return self._root / self._slug(cell) / "report.md"

    def _slug(self, cell: Cell) -> str:
        return f"{cell.channel}.{cell.y}.{cell.variant}.{self._model}.{self._effort}.seed{self._seed}"
