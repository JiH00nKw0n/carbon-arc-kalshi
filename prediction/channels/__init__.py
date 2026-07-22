"""Channels subpackage: card / web / foot / kalshi self-register on import."""
from prediction.channels.specs import ChannelSpec, get_channel
from prediction.channels import kalshi as _kalshi  # noqa: F401  (self-registers the kalshi channel)

__all__ = ["ChannelSpec", "get_channel"]
