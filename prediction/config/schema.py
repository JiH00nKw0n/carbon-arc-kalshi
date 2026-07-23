"""Pydantic v2 experiment config: strict (extra='forbid') so scope-edit typos fail loudly."""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RunCfg(_Strict):
    concurrency: int = 192
    reps: int = 1
    limit: int = 0
    strong_only: bool = True
    drop_outlier_pct: float = 0
    render_only: bool = False
    cutoff: date
    n_calls: int = 2
    hist_rows: int = 6
    max_transcript_chars: int = 48000
    prompt_protocol: Literal["jihoon_main", "paper"] = "jihoon_main"


class LlmCfg(_Strict):
    model: str
    effort: str = "medium"
    max_retries: int = 6


class DataCfg(_Strict):
    panel_out: str
    screen_csv: str
    sentiment_json: str


class ArmCfg(_Strict):
    name: str
    blocks: list[str]


class GridCfg(_Strict):
    channels: list[str]
    targets: list[str]
    variants: list[str]
    arms: list[ArmCfg]
    baselines: list[str]


class EvalCfg(_Strict):
    headline_arm: str
    synergy_arms: list[str]
    bootstrap: int = 5000
    surrogate_n: int = 5000
    calib_folds: int = 5


class ExperimentConfig(_Strict):
    name: str
    seed: int
    output_dir: str
    run: RunCfg
    llm: LlmCfg
    data: DataCfg
    grid: GridCfg
    evaluate: EvalCfg
