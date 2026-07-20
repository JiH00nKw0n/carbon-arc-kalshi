"""Grid expansion — the cross product of the three per-cell axes.

A Cell is (channel × Y × variant): the unit of work that gets one report. Arms, baselines, and
evaluators are NOT axes of the grid — they are applied *within* a cell (all arms share the cell's
matched row-set, all baselines are fit against it), so they come straight from the config, not from
`expand`. This is the orthogonality that keeps the run a clean nested loop.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import product

from prediction.config.schema import ExperimentConfig

__all__ = ["Cell", "expand"]


@dataclass(frozen=True)
class Cell:
    """One unit of evaluation: a channel, a prediction target Y, and a prompt variant."""
    channel: str
    y: str
    variant: str


def expand(config: ExperimentConfig) -> list[Cell]:
    """Every (channel, Y, variant) combination named in the config's grid, in declared order."""
    grid = config.grid
    return [Cell(channel=channel, y=y, variant=variant)
            for channel, y, variant in product(grid.channels, grid.targets, grid.variants)]
