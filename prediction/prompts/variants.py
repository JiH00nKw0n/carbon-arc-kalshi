"""Prompt builder (BASE) + variant specs (BASE / TOOL) — the tool toggle lives here.

There is now ONE prompt: BASE — the channel/Y-neutral ``timeline_body`` closed by the Y's ask
(generalized from factor1's ``ASK_DECOMP`` via ``YTarget.ask_text``). The retired DESC variant, which
front-loaded the FMP company profile + Carbon Arc dataset blurb into the prompt, is gone.

Whether the model gets those two facts is now a CONFIG choice, expressed as a variant spec rather
than a second prompt:

  * ``BASE`` -> the BASE prompt, no tools.
  * ``TOOL`` -> the SAME BASE prompt, plus two lookup tools (``prompts/tools.TOOL_DEFS``) the model
    may call on demand (see ``predict.llm_predictor`` / ``data.llm_client``).

Both variants therefore render a byte-identical prompt; they differ only in whether the tools are
wired into the LLM request. The grid's ``variants`` axis selects them by name, so BASE-vs-TOOL is a
one-line config edit and each still gets its own report.

``build_base`` keeps the uniform builder signature ``build(target, transcript_store,
description_provider, channel_spec, y_target, arm_blocks, n_calls, hist_rows) -> str`` (unused params
accepted so the registry can dispatch any prompt builder uniformly).
"""
from __future__ import annotations

from dataclasses import dataclass

from prediction.prompts.blocks import HIST_ROWS, timeline_body
from prediction.registry import Registry, register_prompt, register_variant

__all__ = ["build_base", "VariantSpec", "get_variant"]


@register_prompt("BASE")
def build_base(target, transcript_store, description_provider, channel_spec, y_target,
               arm_blocks, n_calls: int, hist_rows: int = HIST_ROWS) -> str:
    """Neutral timeline body + the Y-specific ask. (``description_provider`` unused by the prompt.)"""
    body = timeline_body(target, transcript_store, channel_spec, y_target,
                         arm_blocks, n_calls, hist_rows)
    return body + y_target.ask_text(target.row)


@dataclass(frozen=True)
class VariantSpec:
    """A grid variant: which prompt builder to use and whether to offer the lookup tools.

    Both registered variants share ``prompt="BASE"``; only ``tools`` differs, so the rendered prompt
    is identical and the variant purely toggles tool availability.
    """
    name: str
    prompt: str
    tools: bool = False


register_variant(VariantSpec(name="BASE", prompt="BASE", tools=False))
register_variant(VariantSpec(name="TOOL", prompt="BASE", tools=True))


def get_variant(name: str) -> VariantSpec:
    """Return the registered VariantSpec named `name` (raises ModelConfigError if unknown)."""
    return Registry.get("variant", name)  # type: ignore[return-value]
