"""Load and strictly validate an experiment YAML into an ExperimentConfig."""
from __future__ import annotations

from pathlib import Path

import yaml

from prediction.config.schema import ExperimentConfig
from prediction.errors import DataUnavailableError


def load(path: str) -> ExperimentConfig:
    """Parse `path` (YAML) into a validated ExperimentConfig; raise if the file is missing."""
    file = Path(path)
    if not file.exists():
        raise DataUnavailableError(f"config file not found: {file}")
    raw = yaml.safe_load(file.read_text())
    return ExperimentConfig(**raw)
