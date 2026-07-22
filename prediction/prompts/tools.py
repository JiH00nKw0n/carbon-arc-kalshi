"""Lookup tools for the TOOL variant — offered to the model instead of front-loading the text.

Where the retired DESC variant PREPENDED the company profile and alternative-data description
to every prompt, the TOOL variant leaves the BASE prompt byte-identical and instead exposes the
same two facts as on-demand function tools. The model calls them only when it judges the context
worth the tokens, so BASE and TOOL share one prompt and differ only in whether these tools are wired
into the LLM request (a config choice, per the ``variants`` grid axis).

``TOOL_DEFS`` is the OpenAI tool schema list; ``make_tool_dispatch`` binds a channel-scoped
description provider + a ticker into the ``dispatch(name, args) -> str`` callback the LLM client
invokes for each tool call. Both tools take no arguments — the company and the alt-data channel are
already fixed by the target being scored.
"""
from __future__ import annotations

from typing import Callable

__all__ = ["TOOL_DEFS", "make_tool_dispatch"]

_COMPANY_PROFILE = "get_company_profile"
_ALT_DATA_DESCRIPTION = "get_alt_data_description"

# Responses-API tool schema (flat: no nested "function" wrapper). gpt-5.5 only accepts function tools
# alongside reasoning on /v1/responses, so the TOOL variant runs through the Responses path in
# llm_client; `strict` + `additionalProperties:false` keep the (no-arg) schema valid for auto-parse.
TOOL_DEFS = [
    {"type": "function", "name": _COMPANY_PROFILE, "strict": True,
     "description": "Look up the frozen public company-profile description for the company being "
                    "analyzed (business model, sector, what drives its revenue).",
     "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False}},
    {"type": "function", "name": _ALT_DATA_DESCRIPTION, "strict": True,
     "description": "Look up the frozen methodology description of the alternative-data source "
                    "used as the X input for this company (what it measures, coverage, method).",
     "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False}},
]


def make_tool_dispatch(descriptions, ticker: str) -> Callable[[str, dict], str]:
    """Bind a channel-scoped description provider + ticker into a ``dispatch(name, args)`` callback.

    ``descriptions`` is the channel-bound provider (``run.experiment._ChannelDescriptions``): it
    answers ``company_profile(ticker)`` and the no-arg ``dataset_description()``. Missing text
    degrades to a plain "not available" string so a tool call never fails the round.
    """
    def dispatch(name: str, _args: dict) -> str:
        if name == _COMPANY_PROFILE:
            profile = descriptions.company_profile(ticker)
            return profile.strip() if profile else f"No company profile available for {ticker}."
        if name == _ALT_DATA_DESCRIPTION:
            dataset = descriptions.dataset_description()
            return dataset if dataset else "No alternative-data methodology description available."
        return f"Unknown tool: {name}."

    return dispatch
