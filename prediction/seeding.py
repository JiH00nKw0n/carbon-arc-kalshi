"""Deterministic seeding for the whole run."""
import random

import numpy as np


def set_seeds(seed: int) -> np.random.Generator:
    """Seed Python's `random` and NumPy's legacy global, and return a fresh Generator."""
    random.seed(seed)
    np.random.seed(seed)
    return np.random.default_rng(seed)
