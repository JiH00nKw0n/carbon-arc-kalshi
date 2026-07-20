"""YTarget — the prediction target axis (surprise_early / surprise_print / rev_yoy).

One frozen dataclass parameterizes label construction, the percent extractor, the LLM output
schema, and the trailing ask instruction. Removes every hardcoded `surprise_early` assumption:
label reads the precomputed panel column; extract rescales the model's revenue LEVEL by the Y's
anchor (denominator); the ask generalizes factor1's ASK_DECOMP.
"""
from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel

from prediction.registry import Registry, register_y_target
from prediction.targets.schemas import BPredictSurprise, BPredictYoY

# Human phrasing of each anchor column, used to render the ask text.
_ANCHOR_PHRASE = {
    "cons_early": "consensus",
    "cons_print": "consensus",
    "prior_year_actual": "prior-year revenue",
}


@dataclass(frozen=True)
class YTarget:
    """A prediction target: its label column, denominator anchor, LLM schema, and ask noun."""
    name: str
    true_col: str
    anchor_col: str
    schema: type[BaseModel]
    ask_noun: str

    def label(self, row) -> float:
        """True label as a fraction, read from the precomputed panel column."""
        return float(getattr(row, self.true_col))

    def extract(self, pred_rev: float, row) -> float:
        """Convert a predicted revenue LEVEL into the percent metric using the Y's anchor."""
        anchor = float(getattr(row, self.anchor_col))
        return (pred_rev - anchor) / anchor * 100.0

    def ask_text(self, row) -> str:
        """Trailing instruction: predict revenue $M, restate the anchor, derive the percent metric."""
        anchor = _ANCHOR_PHRASE[self.anchor_col]
        return ("\n\nPredict the quarter's TOTAL REVENUE in $M for the quarter marked <- PREDICT — "
                "your own estimate of the ACTUAL revenue (it may differ from consensus). Then restate "
                f"the {anchor} shown and compute the implied {self.ask_noun} = "
                f"(your revenue - {anchor})/{anchor}, in %.")


register_y_target(YTarget(
    name="surprise_early", true_col="surprise_early", anchor_col="cons_early",
    schema=BPredictSurprise, ask_noun="SURPRISE"))

register_y_target(YTarget(
    name="surprise_print", true_col="surprise_print", anchor_col="cons_print",
    schema=BPredictSurprise, ask_noun="SURPRISE"))

register_y_target(YTarget(
    name="rev_yoy", true_col="rev_yoy", anchor_col="prior_year_actual",
    schema=BPredictYoY, ask_noun="YoY GROWTH"))


def get_y_target(name: str) -> YTarget:
    """Return the registered YTarget named `name` (raises ModelConfigError if unknown)."""
    return Registry.get("y_target", name)  # type: ignore[return-value]
