"""Composition root — resolve registries, wire boundary clients, run the Section-7 flow.

`build_experiment` assembles the dependency-injected clients (LLM, panel cache, result store);
`run` drives one seeded pass over every cell: build the panel once per channel, derive leakage-safe
targets for the cell's Y, predict all arms, fit the classical baselines on the same matched rows,
evaluate (metrics + leak-free calibration + company-clustered resampling), and write the report.
Everything shares ONE event loop so the LLM client's semaphore binds once.

Two leaf-layer signature gaps are reconciled here without touching factor1 or the on-disk leaves:
`_Transcripts.read_text` accepts either a CallRef (as `build_targets` passes) or a path string (as
`prompts/blocks` passes); `_ChannelDescriptions.dataset_description()` pre-binds the channel so the
TOOL variant's `get_alt_data_description` tool can call it with no args. The evaluation frame
reproduces f1_22_eval verbatim, with `lag_y` generalizing its `lag_surprise` and fresh
`default_rng(seed)` per resampling procedure.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from prediction.arms.specs import get_arm
from prediction.channels.specs import ChannelSpec, get_channel
from prediction.config.schema import ExperimentConfig
from prediction.data.altdata_source import CarbonArcCsvSource
from prediction.data.descriptions import DescriptionProvider
from prediction.data.llm_client import LLMConfig, OpenAIStructuredClient
from prediction.data.revenue_source import FactSetJsonSource
from prediction.data.transcripts import TranscriptStore
from prediction.domain.records import EvalResult
from prediction.evaluate.calibration import cross_fit_calibrate
from prediction.evaluate.metrics import metrics
from prediction.evaluate.resampling import boot_synergy, shuffle_company_surrogate
from prediction.baselines.estimators import get_estimator
from prediction.baselines.specs import get_baseline
from prediction.panel.builder import build_panel
from prediction.panel.features import lag_y, sentiment
from prediction.panel.targets import build_targets
from prediction.predict.llm_predictor import predict_arms
from prediction.prompts.variants import get_variant
from prediction.registry import Registry
from prediction.run.grid import Cell, expand
from prediction.run.store import ResultStore
from prediction.seeding import set_seeds
from prediction.targets.ytarget import get_y_target

__all__ = ["Experiment", "build_experiment", "run"]


# --------------------------------------------------------------------------- leaf reconcilers
class _Transcripts:
    """Dual-mode transcript adapter: `read_text` takes a CallRef OR a path string."""

    def __init__(self, store: TranscriptStore, max_chars: int):
        self._store = store
        self._max_chars = max_chars

    def prior_calls(self, ticker, report, k):
        return self._store.prior_calls(ticker, report, k)

    def read_text(self, ref_or_path):
        path = getattr(ref_or_path, "path", ref_or_path)
        try:
            return Path(path).read_text()[: self._max_chars]
        except OSError:
            return None


class _ChannelDescriptions:
    """Binds the channel so `dataset_description()` is callable with no args (used by the TOOL tools)."""

    def __init__(self, provider: DescriptionProvider, channel_name: str):
        self._provider = provider
        self._channel = channel_name

    def company_profile(self, ticker):
        return self._provider.company_profile(ticker)

    def dataset_description(self):
        return self._provider.dataset_description(self._channel)


# --------------------------------------------------------------------------- panel cache
class PanelCache:
    """Builds each channel's panel once per run and reuses that fresh frame across cells."""

    def __init__(self, panel_out: str, screen_csv: str):
        self._dir = Path(panel_out)
        self._screen_csv = screen_csv
        self._cache: dict[str, pd.DataFrame] = {}

    def get_or_build(self, channel: ChannelSpec) -> pd.DataFrame:
        if channel.name not in self._cache:
            self._dir.mkdir(parents=True, exist_ok=True)
            path = self._dir / f"panel_{channel.name}.csv"
            self._cache[channel.name] = self._build(channel, path)
        return self._cache[channel.name]

    def _build(self, channel: ChannelSpec, path: Path) -> pd.DataFrame:
        if channel.kind == "ladder":
            from prediction.data.kalshi_source import KalshiRevenueSource, KalshiLadderSource
            from prediction.panel.ladder_builder import build_ladder_panel
            revenue = KalshiRevenueSource(channel).records()
            alt = KalshiLadderSource(channel).points()
            panel = build_ladder_panel(channel, revenue, alt, self._screen_csv)
        else:
            revenue = FactSetJsonSource(channel).records()
            alt = CarbonArcCsvSource(channel).points()
            panel = build_panel(channel, revenue, alt, self._screen_csv)
        panel.to_csv(path, index=False)
        return panel

# --------------------------------------------------------------------------- composition root
@dataclass
class Experiment:
    """The wired dependencies shared across all cells of one run."""
    cfg: ExperimentConfig
    llm_client: object
    store: ResultStore
    panels: PanelCache


def build_experiment(cfg: ExperimentConfig) -> Experiment:
    """Resolve boundary clients + caches. The LLM client is skipped on a $0 render pass."""
    client = None if cfg.run.render_only else OpenAIStructuredClient(
        LLMConfig(model=cfg.llm.model, effort=cfg.llm.effort,
                  max_retries=cfg.llm.max_retries, concurrency=cfg.run.concurrency))
    store = ResultStore(cfg.output_dir, cfg.llm.model, cfg.llm.effort, cfg.seed)
    return Experiment(
        cfg=cfg,
        llm_client=client,
        store=store,
        panels=PanelCache(cfg.data.panel_out, cfg.data.screen_csv),
    )


def run(cfg: ExperimentConfig, force: bool = False) -> None:
    """Drive the whole grid in one event loop, re-seeding per repetition."""
    experiment = build_experiment(cfg)
    asyncio.run(_run_all(experiment, force))


async def _run_all(experiment: Experiment, force: bool) -> None:
    for rep in range(experiment.cfg.run.reps):
        seed = experiment.cfg.seed + rep
        set_seeds(seed)
        experiment.store._seed = seed          # persist each rep in its own seed dir (reps must not overwrite)
        for cell in expand(experiment.cfg):
            await _run_cell(experiment, cell, seed, force)


# --------------------------------------------------------------------------- per-cell flow
async def _run_cell(experiment: Experiment, cell: Cell, seed: int, force: bool) -> None:
    cfg = experiment.cfg
    context = _cell_context(experiment, cell)
    panel = _select_strong(experiment.panels.get_or_build(context.channel), cfg.run)
    targets = build_targets(panel, context.transcripts, context.y_target, cfg.run)
    if cfg.run.limit:
        targets = targets[: cfg.run.limit]
    experiment.store.write_manifest(cell.channel, cell.y, targets, cfg.run.hist_rows)
    if experiment.store.done(cell) and not force:
        return

    if cfg.run.render_only:
        _render_cell(cell, targets, context, cfg.run, Path(cfg.output_dir) / "render")
        return
    if not targets:
        print(f"[{cell.channel}·{cell.y}·{cell.variant}] no targets — skipped", flush=True)
        return

    print(f"[{cell.channel}·{cell.y}·{cell.variant}] {len(targets)} targets", flush=True)
    rows = await predict_arms(targets, context.prompt_builder, context.tools, context.arms,
                              context.y_target, context.channel, context.transcripts,
                              context.descriptions, experiment.llm_client, cfg.run)
    if not rows:
        print(f"[{cell.channel}·{cell.y}·{cell.variant}] no predictions — skipped", flush=True)
        return
    preds = pd.DataFrame(rows)
    result = _evaluate_cell(cfg, cell, panel, preds, context, seed)
    experiment.store.write_preds(cell, preds)
    experiment.store.write_report(cell, result)


@dataclass
class _CellContext:
    channel: ChannelSpec
    y_target: object
    prompt_builder: object
    tools: bool
    arms: list
    transcripts: _Transcripts
    descriptions: _ChannelDescriptions


def _cell_context(experiment: Experiment, cell: Cell) -> _CellContext:
    channel = get_channel(cell.channel)
    store = TranscriptStore(channel, experiment.cfg.run.max_transcript_chars)
    variant = get_variant(cell.variant)                       # VariantSpec: prompt name + tools flag
    return _CellContext(
        channel=channel,
        y_target=get_y_target(cell.y),
        prompt_builder=Registry.get("prompt", variant.prompt),
        tools=variant.tools,
        arms=[get_arm(arm.name) for arm in experiment.cfg.grid.arms],
        transcripts=_Transcripts(store, experiment.cfg.run.max_transcript_chars),
        descriptions=_ChannelDescriptions(DescriptionProvider(channel.name), channel.name))


def _select_strong(panel: pd.DataFrame, run_cfg) -> pd.DataFrame:
    """Restrict to the strong-O tier when requested (matches the ~$490 basis)."""
    if run_cfg.strong_only and "strength" in panel.columns:
        return panel[panel["strength"] == "strong"].copy()
    return panel


def _render_cell(cell: Cell, targets, context: _CellContext, run_cfg, render_dir: Path) -> None:
    """Write the first target's composed prompt for every arm under `render_dir` ($0, no LLM)."""
    if not targets:
        print(f"[render {cell.channel}·{cell.y}·{cell.variant}] no targets", flush=True)
        return
    render_dir.mkdir(parents=True, exist_ok=True)
    target = targets[0]
    for arm in context.arms:
        prompt = context.prompt_builder(target, context.transcripts, context.descriptions,
                                        context.channel, context.y_target, arm.blocks,
                                        run_cfg.n_calls, run_cfg.hist_rows)
        name = f"PROMPT.{cell.channel}.{cell.y}.{cell.variant}.{arm.name}.txt".replace("+", "_")
        (render_dir / name).write_text(prompt)
    print(f"[render {cell.channel}·{cell.y}·{cell.variant}] {target.ticker} "
          f"-> {len(context.arms)} prompts in {render_dir}", flush=True)


# --------------------------------------------------------------------------- evaluation frame
def _evaluate_cell(cfg, cell, panel, preds, context, seed) -> EvalResult:
    features = _feature_table(panel, context.transcripts, context.y_target, context.channel.kind)
    train, test = _train_test(features, preds, cfg.run.cutoff, context.channel.kind)
    _assert_matched(test, cfg.evaluate.synergy_arms)
    base = _baseline_predictions(train, test, cfg.grid.baselines, context.channel.kind)
    return _build_result(cell, test, base, cfg.evaluate, seed)


def _feature_table(panel: pd.DataFrame, transcripts: _Transcripts, y_target,
                   kind: str = "scalar") -> pd.DataFrame:
    """The f1_22_eval event table, Y-parameterized: tkr/ticker, true, x_yoy, lag_y, sent, report.

    A ladder channel has no defensible dense scalar YoY, so it keeps label-bearing rows with x_yoy
    missing. X-dependent classical baselines are reported N/A downstream; the raw ladder reaches the
    LLM through x_payload. Scalar channels retain the original x_yoy behavior."""
    frame = panel.copy().astype({"FE_FP_END": "datetime64[ns]", "REPORT_DATE": "datetime64[ns]"})
    frame = frame.sort_values(["ticker", "FE_FP_END"])
    frame.loc[:, "true"] = frame[y_target.true_col]
    frame.loc[:, "lag_y"] = lag_y(frame, y_target.true_col)
    frame = frame.dropna(subset=(["true"] if kind == "ladder" else ["x_yoy", "true"])).copy()
    frame.loc[:, "x_yoy"] = (float("nan") if kind == "ladder"
                              else frame["x_yoy"].fillna(0.0))
    frame.loc[:, "sent"] = [_row_sentiment(transcripts, row.ticker, row.REPORT_DATE)
                            for row in frame.itertuples()]
    frame.loc[:, "sent"] = frame["sent"].fillna(0.0)
    frame.loc[:, "tkr"] = frame["ticker"]
    frame.loc[:, "fp"] = frame["FE_FP_END"]
    frame.loc[:, "report"] = frame["REPORT_DATE"]
    return frame[["tkr", "ticker", "fp", "report", "x_yoy", "true", "lag_y", "sent"]]


def _row_sentiment(transcripts: _Transcripts, ticker: str, report_date) -> float:
    calls = transcripts.prior_calls(ticker, pd.Timestamp(report_date).date(), 1)
    return sentiment(calls[0].path) if calls else float("nan")


def _train_test(features: pd.DataFrame, preds: pd.DataFrame, cutoff,
                kind: str = "scalar") -> tuple[pd.DataFrame, pd.DataFrame]:
    """Pre-cutoff training rows plus LLM rows joined by exact company/fiscal-quarter identity."""
    cutoff_ts = pd.Timestamp(cutoff)
    required = ["true"] if kind == "ladder" else ["x_yoy", "true"]
    train = features[features["report"] <= cutoff_ts].dropna(subset=required).copy()
    fill = train["true"].mean()
    train.loc[:, "lag_y"] = train["lag_y"].fillna(fill)

    test = preds.copy().astype({"fp": "datetime64[ns]"})
    keyed = features[["tkr", "fp", "sent", "lag_y"]].drop_duplicates(["tkr", "fp"])
    test = test.merge(keyed, on=["tkr", "fp"], how="left", validate="one_to_one")
    test.loc[:, "lag_y"] = test["lag_y"].fillna(fill)
    test.loc[:, "sent"] = test["sent"].fillna(0.0)
    test.loc[:, "ticker"] = test["tkr"]
    test.loc[:, "x_yoy"] = (float("nan") if kind == "ladder"
                             else test["x_yoy"].fillna(0.0))
    train.loc[:, "x_sent"] = train["x_yoy"] * train["sent"]
    test.loc[:, "x_sent"] = test["x_yoy"] * test["sent"]
    return train, test


def _assert_matched(test: pd.DataFrame, arms: list[str]) -> None:
    for arm in arms:
        assert arm in test.columns and not test[arm].isna().any(), \
            f"arm '{arm}' is missing/NaN in the matched set — arms must share rows"


def _baseline_predictions(train, test, names: list[str], kind: str = "scalar") -> dict:
    predictions = {}
    for name in names:
        spec = get_baseline(name)
        predictions[name] = (None if kind == "ladder" and "x_yoy" in spec.features
                             else _fit_predict(spec, train, test))
    return predictions


def _fit_predict(spec, train, test) -> np.ndarray:
    estimator = get_estimator(spec.estimator)
    if spec.estimator == "naive":
        return estimator(train)(test)
    if spec.estimator == "gbt":
        return estimator(train, test, spec.features, spec.params)
    return estimator(train, test, spec.features)


# --------------------------------------------------------------------------- result assembly
def _build_result(cell, test, base, eval_cfg, seed) -> EvalResult:
    true_pct = test["true"].values * 100
    arms = eval_cfg.synergy_arms
    table = [_metric_row(name, pred, true_pct) for name, pred in base.items()]
    table += [_metric_row(arm, test[arm].values, true_pct) for arm in arms]
    calib = [{"model": arm,
              "calib_r2": metrics(cross_fit_calibrate(test, arm, np.random.default_rng(seed),
                                                       eval_cfg.calib_folds), true_pct)["r2"]}
             for arm in arms]
    return EvalResult(
        channel=cell.channel, y=cell.y, variant=cell.variant, rows=len(test),
        metrics_table=table, calib=calib,
        synergy=boot_synergy(test, np.random.default_rng(seed), eval_cfg.bootstrap),
        surrogate=shuffle_company_surrogate(test, eval_cfg.headline_arm,
                                            np.random.default_rng(seed), eval_cfg.surrogate_n))


def _metric_row(name: str, pred, true_pct) -> dict:
    if pred is None:
        return {"model": name, "available": False, "calib": None}
    m = metrics(pred, true_pct)
    return {"model": name, "available": True,
            "rmse": m["rmse"], "r2": m["r2"], "corr": m["corr"],
            "corr2": m["corr2"], "mae": m["mae"], "sign": m["sign"], "calib": None}
