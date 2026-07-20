"""CLI: python -m prediction --config CONFIG [--render] [--force].

Loads and strictly validates the YAML (Pydantic), seeds the run, and dispatches to the composition
root. `--render` flips render_only for a $0 dry pass (prompts to scratchpad, no LLM); `--force`
rewrites cells whose report already exists. Importing this module imports the `prediction` package,
which runs every @register_* decorator so the registries are populated before the grid expands.
"""
from __future__ import annotations

import argparse

from prediction.config.loader import load
from prediction.run.experiment import run
from prediction.seeding import set_seeds


def main() -> None:
    args = _parse_args()
    cfg = load(args.config)
    if args.render:
        cfg.run.render_only = True
    set_seeds(cfg.seed)
    run(cfg, force=args.force)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="prediction",
                                     description="config-driven revenue-surprise nowcasting")
    parser.add_argument("--config", required=True, help="path to an experiment YAML")
    parser.add_argument("--render", action="store_true", help="dry render prompts to scratchpad ($0)")
    parser.add_argument("--force", action="store_true", help="rewrite cells even if a report exists")
    return parser.parse_args()


if __name__ == "__main__":
    main()
