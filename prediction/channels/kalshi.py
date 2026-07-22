"""The `kalshi` channel — a ladder-kind alt-data channel (X = pre-publication KPI market ladder).

Registered exactly like card/web/foot, but `kind="ladder"` routes it to the Kalshi sources and the
ladder panel builder (run/experiment.py + panel/ladder_builder.py) instead of the scalar carbon-arc
path. Y (revenue surprise) and Z (earnings call) stay the shared, channel-agnostic pipeline.

The scalar-channel fields (x_csv, x_val, fsym2tkr, factset, yoy_lag) are unused for a ladder channel
and left empty; `ladder_panel` and `revenue_panel` point at the already-leak-safe Kalshi artifacts.
"""
from __future__ import annotations

from pathlib import Path

from prediction.channels.specs import ChannelSpec
from prediction.registry import register_channel

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "kalshi" / "outputs" / "auto"

register_channel(ChannelSpec(
    name="kalshi",
    x_csv=[],
    x_val="",
    entity_map=None,
    entity_drop=set(),
    yoy_lag=4,
    factset="",
    fsym2tkr={},
    tx_index=str(OUT / "transcript_index_kalshi.csv"),
    screen_dt="kalshi_kpi",
    x_table_label="KALSHI PRE-PUBLICATION KPI MARKET LADDER",
    x_unit="kalshi_implied_value",
    kind="ladder",
    ladder_panel=str(OUT / "kalshi_prereport_ladder_panel_firmscreened.csv"),
    revenue_panel=str(OUT / "kalshi_factset_revenue_surprise_panel.csv"),
))
