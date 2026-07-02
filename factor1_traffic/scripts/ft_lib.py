"""
Foot Traffic — thin wrapper over f1_lib.
Sets F1_ROOT / F1_OUT / F1_SCREEN / F1_LM env vars before f1_lib is imported,
then overrides cfg()/active() to return the foot channel config.
"""
import os
import sys
import types
from pathlib import Path

import pandas as pd

# ── paths ─────────────────────────────────────────────────────────────────────
_REPO_ROOT  = Path(__file__).resolve().parents[2]   # carbon-arc-kalshi/ (has lm_sentiment.json)
_FOOT_ROOT  = Path(__file__).resolve().parents[1]   # factor1_traffic/
_FOOT_OUT   = _FOOT_ROOT / "outputs"
_FOOT_SCREEN = _REPO_ROOT / "factor1" / "data" / "altdata_ticker_screen.csv"
_F1_SCRIPTS = _REPO_ROOT / "factor1" / "scripts"
_FOOT_OUT.mkdir(parents=True, exist_ok=True)

# set env vars BEFORE any f1_* import
os.environ["F1_ROOT"]   = str(_REPO_ROOT)
os.environ["F1_OUT"]    = str(_FOOT_OUT)
os.environ["F1_SCREEN"] = str(_FOOT_SCREEN)
os.environ["F1_LM"]     = str(_REPO_ROOT / "lm_sentiment.json")

sys.path.insert(0, str(_F1_SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))

# ── foot channel config ───────────────────────────────────────────────────────
from ft_channels import FOOT_CHANNEL, FOOT_FSYM2TKR  # noqa: E402

def _foot_cfg():   return FOOT_CHANNEL
def _foot_active(): return "foot"

# ── inject f1_config stub (f1_channels imports it at module level) ────────────
_cfg_stub = types.ModuleType("f1_config")
_cfg_stub.ROOT           = _REPO_ROOT
_cfg_stub.DATA           = _FOOT_ROOT / "data"
_cfg_stub.OUT            = _FOOT_OUT
_cfg_stub.SCREEN         = _FOOT_SCREEN
_cfg_stub.CUTOFF         = pd.Timestamp("2025-12-01")
_cfg_stub.WEB_CSV        = _FOOT_ROOT / "data" / "foot_traffic_monthly.csv"
_cfg_stub.FACTSET        = _FOOT_ROOT / "data" / "factset_foot10_pit.json"
_cfg_stub.FSYM2TKR       = FOOT_FSYM2TKR
_cfg_stub.WEB_FSYM2TKR   = FOOT_FSYM2TKR
_cfg_stub.WEB_ENTITY2TKR = None
_cfg_stub.WEB_ENTITY_DROP = set()
sys.modules.setdefault("f1_config", _cfg_stub)

# ── inject f1_channels stub ───────────────────────────────────────────────────
_ch_stub = types.ModuleType("f1_channels")
_ch_stub.cfg             = _foot_cfg
_ch_stub.active          = _foot_active
_ch_stub.CHANNELS        = {"foot": FOOT_CHANNEL}
_ch_stub.FOOT_FSYM2TKR   = FOOT_FSYM2TKR
_ch_stub.WEB_FSYM2TKR    = FOOT_FSYM2TKR
_ch_stub.WEB_ENTITY2TKR  = None
_ch_stub.WEB_ENTITY_DROP  = set()
sys.modules.setdefault("f1_channels", _ch_stub)

# ── now safe to import f1_lib ─────────────────────────────────────────────────
import f1_lib as _f1  # noqa: E402

# patch module-level globals (f1_lib already imported them from env, but patch for safety)
_f1.OUT    = _FOOT_OUT
_f1.SCREEN = _FOOT_SCREEN
_f1.cfg    = _foot_cfg
_f1.active = _foot_active

# ── re-export ─────────────────────────────────────────────────────────────────
from f1_lib import (  # noqa: E402, F401
    CUTOFF, HIST_ROWS, MAX_TRANSCRIPT_CHARS,
    sentiment, prior_calls, read_text,
    load_txindex, build_targets,
    fin_table, x_table, metrics,
)

OUT    = _FOOT_OUT
SCREEN = _FOOT_SCREEN


# ── build_panel with structural-break filter ──────────────────────────────────
def build_panel():
    p = _f1.build_panel()
    breaks = FOOT_CHANNEL.get("structural_breaks", set())
    if breaks:
        p["FE_FP_END"] = pd.to_datetime(p["FE_FP_END"])
        mask = pd.Series(False, index=p.index)
        for tkr, fp in breaks:
            mask |= (p["ticker"] == tkr) & (p["FE_FP_END"] == pd.Timestamp(fp))
        n_drop = mask.sum()
        p = p[~mask].copy()
        print(f"[structural-break filter] dropped {n_drop} row(s): {list(breaks)}")
    return p


def active():  return "foot"
def cfg():     return FOOT_CHANNEL
