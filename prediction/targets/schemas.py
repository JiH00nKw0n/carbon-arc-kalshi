"""LLM structured-output schemas — copied verbatim from the factor1 reference (f1_llm.py).

The decomposition mirrors how each true label is built: predict the revenue LEVEL, echo the
anchor (consensus / prior-year revenue), then derive the percent metric.
"""
from pydantic import BaseModel, Field


class BPredictSurprise(BaseModel):
    """Decomposition (Y = surprise): predict revenue LEVEL + echo consensus + derive surprise %.
    Mirrors how the true label is built: surprise = (actual - consensus)/consensus."""
    predicted_revenue_musd: float = Field(
        description="your best estimate of ACTUAL total revenue for the upcoming quarter, in $M (millions). "
                    "This is the real prediction; it may differ from the consensus shown.")
    consensus_revenue_musd: float = Field(
        description="restate the analyst CONSENSUS revenue shown for that quarter, in $M (grounding).")
    predicted_surprise_pct: float = Field(
        description="implied surprise = (predicted_revenue_musd - consensus_revenue_musd)/consensus_revenue_musd, in %.")
    confidence: int = Field(description="0..100.")
    rationale: str


class BPredictYoY(BaseModel):
    """Decomposition (Y = revenue YoY): predict revenue LEVEL + echo prior-year revenue + derive YoY %.
    Mirrors the true label: yoy = (actual - prior_year_actual)/prior_year_actual."""
    predicted_revenue_musd: float = Field(
        description="your best estimate of ACTUAL total revenue for the upcoming quarter, in $M (millions).")
    prior_year_revenue_musd: float = Field(
        description="restate the SAME-QUARTER revenue one year earlier, in $M (grounding).")
    predicted_rev_yoy_pct: float = Field(
        description="implied growth = (predicted_revenue_musd - prior_year_revenue_musd)/prior_year_revenue_musd, in %.")
    confidence: int = Field(description="0..100.")
    rationale: str
