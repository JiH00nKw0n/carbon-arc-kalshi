"""Domain subpackage: dependency-free record types."""
from prediction.domain.records import (
    AltPoint,
    CallRef,
    EvalResult,
    PanelRow,
    Prediction,
    RevenueRecord,
    Target,
)

__all__ = [
    "RevenueRecord",
    "AltPoint",
    "CallRef",
    "PanelRow",
    "Target",
    "Prediction",
    "EvalResult",
]
