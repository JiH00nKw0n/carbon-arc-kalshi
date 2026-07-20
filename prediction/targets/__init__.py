"""Targets subpackage: LLM output schemas + YTarget instances self-register on import."""
from prediction.targets.schemas import BPredictSurprise, BPredictYoY
from prediction.targets.ytarget import YTarget, get_y_target

__all__ = ["BPredictSurprise", "BPredictYoY", "YTarget", "get_y_target"]
