"""
Foot Traffic channel config — plugs into f1_channels.CHANNELS.
Only the `foot` channel is defined here; web/card remain in f1_channels.py untouched.
"""
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_DATA = _ROOT / "data"

# FactSet FSYM_ID → ticker
FOOT_FSYM2TKR = {
    "KFQHFG-R": "CMG",
    "BL5KVX-R": "COST",
    "BDQDB8-R": "DG",
    "MR0PSP-R": "DLTR",
    "GRS9LG-R": "DRI",
    "VPSN43-R": "EAT",
    "VTBLV9-R": "MCD",
    "FJ4NDH-R": "ROST",
    "TWTDGH-R": "SBUX",
    "GM3DBL-R": "ULTA",
}

# structural-break quarters to drop BEFORE any analysis (pre-declared rule)
# format: (ticker, FE_FP_END as string)
STRUCTURAL_BREAKS = {
    ("DLTR", "2025-01-31"),   # Family Dollar spinoff — CONS_EARLY set on pre-split basis
}

FOOT_CHANNEL = dict(
    x_csv=[_DATA / "foot_traffic_monthly.csv"],  # daily→monthly pre-aggregated
    x_val="foot_traffic",
    entity_map=None,          # entity_name IS ticker (same as card)
    entity_drop=set(),
    yoy_lag=12,               # monthly data → 12-month YoY
    factset=_DATA / "factset_foot10_pit.json",
    fsym2tkr=FOOT_FSYM2TKR,
    tx_index=_DATA / "transcript_index_foot.csv",
    screen_dt="foot_traffic",
    x_table_label="FOOT TRAFFIC HISTORY (Carbon Arc CA0060, visits YoY)",
    x_unit="foot_visits_yoy",
    structural_breaks=STRUCTURAL_BREAKS,
)
