"""
Foot Traffic (CA0060) channel config — mirrors f1_config.py structure exactly.

X  = foot traffic YoY (daily visits aggregated to monthly, then YoY), per company.
Z  = prior-quarter earnings-call transcript (same as F1/F3).
Y  = revenue surprise = (ACTUAL − point-in-time consensus) / consensus  (FactSet PIT).

Leakage frame identical to F1/F3: LLM eval set = report_date > 2025-12-01.
"""
from pathlib import Path
import pandas as pd

ROOT   = Path(__file__).resolve().parents[1]
DATA   = ROOT / "data"
OUT    = ROOT / "outputs"
OUT.mkdir(parents=True, exist_ok=True)

FOOT_CSV  = DATA / "ca0060_foot_traffic_10tkr_daily_3y.csv"   # CA0060, 10 entities, daily 3Y
FACTSET   = DATA / "factset_foot10_pit.json"                  # FactSet PIT SALES (to be fetched)
SCREEN    = Path(__file__).resolve().parents[2] / "factor1" / "data" / "altdata_ticker_screen.csv"

CUTOFF = pd.Timestamp("2025-12-01")   # gpt-5.5 knowledge cutoff (LLM eval only)

# entity_id → ticker (from Carbon Arc purchase)
FOOT_ENTITY2TKR = {
    "CMG":  "CMG",
    "COST": "COST",
    "DG":   "DG",
    "DLTR": "DLTR",
    "DRI":  "DRI",
    "EAT":  "EAT",
    "MCD":  "MCD",
    "ROST": "ROST",
    "SBUX": "SBUX",
    "ULTA": "ULTA",
}

# FactSet FSYM_ID → ticker (from ft_00_fetch_factset.py output)
FSYM2TKR: dict[str, str] = {
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
