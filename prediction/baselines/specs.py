"""Baseline specifications N0..N5 (data only) — estimator + feature columns + hyperparameters.

Each spec names one estimator ({naive, ols, gbt}) and the columns it consumes from the
evaluation frame. Feature vocabulary (all scalar, all leakage-safe at prediction time):
  x_yoy  — alt-data year-over-year signal
  sent   — earnings-call sentiment (Loughran-McDonald)
  lag_y  — one-period lag of the ACTIVE target Y (autoregressive term)
  x_sent — x_yoy x sent interaction
Feature lists mirror factor1 f1_22_eval verbatim; `lag_y` generalizes its `lag_surprise`.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from prediction.registry import Registry, register_baseline

GBT_PARAMS = {"n_estimators": 150, "max_depth": 2, "learning_rate": 0.05}


@dataclass(frozen=True)
class BaselineSpec:
    """A classical baseline: which estimator to fit, on which features, with which params."""
    name: str
    estimator: str
    features: list[str]
    params: dict = field(default_factory=dict)


register_baseline(BaselineSpec(name="N0", estimator="naive", features=[]))
register_baseline(BaselineSpec(name="N1", estimator="ols", features=["x_yoy"]))
register_baseline(BaselineSpec(name="N2", estimator="ols", features=["sent"]))
register_baseline(BaselineSpec(name="N3", estimator="ols", features=["x_yoy", "sent"]))
register_baseline(BaselineSpec(name="N4", estimator="ols", features=["x_yoy", "sent", "x_sent"]))
register_baseline(BaselineSpec(name="N3b", estimator="ols", features=["x_yoy", "sent", "lag_y"]))
register_baseline(BaselineSpec(name="N4b", estimator="ols", features=["x_yoy", "sent", "lag_y", "x_sent"]))
register_baseline(BaselineSpec(name="N5", estimator="gbt", features=["x_yoy", "sent", "lag_y"], params=GBT_PARAMS))


def get_baseline(name: str) -> BaselineSpec:
    """Return the registered BaselineSpec named `name` (raises ModelConfigError if unknown)."""
    return Registry.get("baseline", name)  # type: ignore[return-value]
