"""Test 2 — arm masking and the BASE/TOOL variant contract.

The arm's block set is the ONLY thing that toggles the x table and the transcript in the rendered
prompt; the Y and channel are orthogonal. There is now a single prompt (BASE); the TOOL variant
reuses that same prompt and differs only in exposing lookup tools, so BASE and TOOL are byte-identical
as prompts — the tool availability is a config flag, verified against the registered VariantSpec.

Markers used (robust to exact formatting):
  * x block   -> the channel's own x_table_label (comes straight from the ChannelSpec)
  * text block-> the transcript's unique content marker carried on Target.text
"""
import pytest

from prediction.arms.specs import get_arm
from prediction.prompts.tools import TOOL_DEFS, make_tool_dispatch
from prediction.prompts.variants import get_variant
from prediction.targets.ytarget import get_y_target

PROFILE_MARKER = "ACMEPROFILEMARKER"
DATASET_MARKER = "CARDDATASETMARKER"
TEXT_MARKER = "ZZTEXTMARKERZZ"

ARMS = ["fin", "fin+x", "fin+text", "fin+x+text"]


@pytest.mark.parametrize("arm_name", ARMS)
def test_x_block_present_iff_x_in_arm(arm_name, render_prompt, prompt_target,
                                      card_channel, descriptions):
    arm = get_arm(arm_name)
    prompt = render_prompt("BASE", prompt_target, arm, get_y_target("surprise_early"),
                           card_channel, descriptions)
    assert (card_channel.x_table_label in prompt) == ("x" in arm.blocks)


@pytest.mark.parametrize("arm_name", ARMS)
def test_transcript_block_present_iff_text_in_arm(arm_name, render_prompt, prompt_target,
                                                  card_channel, descriptions):
    arm = get_arm(arm_name)
    prompt = render_prompt("BASE", prompt_target, arm, get_y_target("surprise_early"),
                           card_channel, descriptions)
    assert (TEXT_MARKER in prompt) == ("text" in arm.blocks)


def test_base_and_tool_variants_share_the_same_prompt(render_prompt, prompt_target,
                                                      card_channel, descriptions):
    """Both variants use prompt='BASE', so a fixed arm renders a byte-identical prompt."""
    arm = get_arm("fin+x+text")
    y = get_y_target("surprise_early")
    base_spec, tool_spec = get_variant("BASE"), get_variant("TOOL")
    assert base_spec.prompt == tool_spec.prompt == "BASE"
    assert base_spec.tools is False and tool_spec.tools is True

    base = render_prompt(base_spec.prompt, prompt_target, arm, y, card_channel, descriptions)
    tool = render_prompt(tool_spec.prompt, prompt_target, arm, y, card_channel, descriptions)
    assert base == tool


def test_prompt_never_front_loads_description_matter(render_prompt, prompt_target,
                                                     card_channel, descriptions):
    """The retired DESC front-matter is gone: profile/dataset text never appears in the prompt."""
    arm = get_arm("fin+x+text")
    y = get_y_target("surprise_early")
    prompt = render_prompt("BASE", prompt_target, arm, y, card_channel, descriptions)
    assert PROFILE_MARKER not in prompt
    assert DATASET_MARKER not in prompt


def test_tool_dispatch_serves_profile_and_dataset(card_channel, descriptions):
    """The TOOL lookups return the channel-bound provider's profile / dataset text."""
    from prediction.tests.conftest import _ChannelBoundDescriptions

    provider = _ChannelBoundDescriptions(descriptions, card_channel.name)
    dispatch = make_tool_dispatch(provider, "AAA")
    names = {t["name"] for t in TOOL_DEFS}   # Responses-API flat tool schema (no nested "function")
    assert names == {"get_company_profile", "get_alt_data_description"}
    assert PROFILE_MARKER in dispatch("get_company_profile", {})
    assert DATASET_MARKER in dispatch("get_alt_data_description", {})
