"""Data arms — which prompt blocks render. Arm chooses blocks only; Y owns schema/extractor.

This orthogonality (arm ⟂ Y) is what makes the grid a clean nested loop: the same four arms
(fin / fin+x / fin+text / fin+x+text) apply under every channel and every Y.
"""
from __future__ import annotations

from dataclasses import dataclass

from prediction.registry import Registry, register_arm


@dataclass(frozen=True)
class ArmSpec:
    """A data arm: the subset of {fin, x, text} blocks to render in the prompt."""
    name: str
    blocks: frozenset[str]


register_arm(ArmSpec(name="fin", blocks=frozenset({"fin"})))
register_arm(ArmSpec(name="fin+x", blocks=frozenset({"fin", "x"})))
register_arm(ArmSpec(name="fin+text", blocks=frozenset({"fin", "text"})))
register_arm(ArmSpec(name="fin+x+text", blocks=frozenset({"fin", "x", "text"})))


def get_arm(name: str) -> ArmSpec:
    """Return the registered ArmSpec named `name` (raises ModelConfigError if unknown)."""
    return Registry.get("arm", name)  # type: ignore[return-value]
