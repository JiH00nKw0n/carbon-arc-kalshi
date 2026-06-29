"""
Factor 1 — channel config (X = card | web | …), per EXPERIMENT_SPEC.md.

The whole pipeline (panel → classical baselines → LLM ablation/arch/Z-depth → MSE eval) is
channel-agnostic; only X changes. Select with env `F1_CHANNEL` (default 'web').
Z (transcript) and Y (revenue surprise) are FIXED across channels.
"""
import os
from pathlib import Path

ROOT = Path("/Users/junekwon/Desktop/Projects/carbon_arc")
DATA = ROOT / "factor1" / "data"

# --- web FactSet id→ticker (38) + entity→ticker map (reused from f1_config) ---
import sys  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
from f1_config import FSYM2TKR as WEB_FSYM2TKR, WEB_ENTITY2TKR, WEB_ENTITY_DROP  # noqa: E402

# --- card FactSet id→ticker (99), resolved via stock_server_query 2026-06-28 ---
CARD_FSYM2TKR = {
    "XNM3N2-R": "OLLI", "CSDT95-R": "SFM", "JN801W-R": "ASO", "V2MTKT-R": "CAKE", "K38HHD-R": "MAR",
    "C4C0BL-R": "NFLX", "X44KDF-R": "TXRH", "P36M94-R": "ORLY", "QKJS7V-R": "UAL", "BRWKF0-R": "TSCO",
    "BDQDB8-R": "DG", "XBLNPW-R": "DKNG", "GRS9LG-R": "DRI", "BZPTB8-R": "WSM", "WPKF66-R": "BBY",
    "MRHVBK-R": "BJ", "QD8WKZ-R": "SIG", "KDJSF0-R": "ALK", "JDQ0K1-R": "AZO", "LN3P8B-R": "TPR",
    "KFQHFG-R": "CMG", "LC0H1H-R": "BKNG", "S2YZ7L-R": "FIVE", "J3LDJT-R": "BLMN", "MR0PSP-R": "DLTR",
    "FPP9SL-R": "JWN", "CKHCJ4-R": "DASH", "J1JDGR-R": "CZR", "VC9B6B-R": "ULCC", "MCNYYL-R": "AMZN",
    "NSRFNJ-R": "RVLV", "TWTDGH-R": "SBUX", "J3MHMV-R": "FUN", "HY8GBD-R": "MTCH", "GJZ5YB-R": "KSS",
    "HNZVK6-R": "CCL", "XLT03X-R": "RCL", "JNYJHG-R": "SHAK", "CHKL7S-R": "LOW", "S8ZPBT-R": "TJX",
    "MYZ7WZ-R": "FL", "K8ZVRV-R": "DKS", "W6SXMV-R": "EBAY", "B4Q2S8-R": "RH", "LBWS01-R": "PLAY",
    "MFQVZQ-R": "HLT", "PD98GG-R": "HD", "FCK6QT-R": "EXPE", "VTBLV9-R": "MCD", "HZQYZZ-R": "ABNB",
    "X93SZL-R": "CAVA", "CSMTMQ-R": "WMT", "TWVMYS-R": "H", "RBB7RY-R": "ANF", "MDJCPR-R": "DUOL",
    "W0731Q-R": "NCLH", "CSFJSZ-R": "AAL", "GF26VF-R": "ACI", "GM3DBL-R": "ULTA", "G6QSWR-R": "SG",
    "SSK1W1-R": "GO", "J60ZBD-R": "FND", "PJ91Y0-R": "BMBL", "BFSY5M-R": "LUV", "J994MP-R": "TGT",
    "THXZ97-R": "WING", "BM7J26-R": "BROS", "DGBZCC-R": "DAL", "FJ4NDH-R": "ROST", "BL5KVX-R": "COST",
    "MPXJMM-R": "DIS", "DKJ8VM-R": "DDS", "M79B89-R": "MGM", "BV3N5V-R": "M", "VPSN43-R": "EAT",
    "D1LJ47-R": "AEO", "MH3J5L-R": "CHH", "MWKPV4-R": "LULU", "X5HN6G-R": "SPOT", "VL607C-R": "BURL",
    "R2J99W-R": "KR", "XKTZWR-R": "URBN", "PVBYXV-R": "ETSY", "FBCHQC-R": "BBWI", "DV6B8D-R": "CART",
    "VXQ46D-R": "WEN", "VCNXSP-R": "YUM", "LYB9P1-R": "WH", "H5J55J-R": "W", "TR0FX7-R": "UBER",
    "F05QG0-R": "DPZ", "R5SD3R-R": "JACK", "MGN5FR-R": "PLNT", "CF350L-R": "CHWY", "LVRC60-R": "PTON",
    "R5RD6T-R": "GAP", "Q53D75-R": "GME", "RQSKKH-R": "CASY", "JYQXCG-R": "MTN",
}

# --- foot strong-O FactSet id→ticker (34), CA0060, resolved 2026-06-29 ---
FOOT_FSYM2TKR = {
    "GF26VF-R": "ACI", "JN801W-R": "ASO", "J3LDJT-R": "BLMN", "BM7J26-R": "BROS", "VL607C-R": "BURL",
    "V2MTKT-R": "CAKE", "X93SZL-R": "CAVA", "KFQHFG-R": "CMG", "BL5KVX-R": "COST", "BDQDB8-R": "DG",
    "MR0PSP-R": "DLTR", "GRS9LG-R": "DRI", "VPSN43-R": "EAT", "S2YZ7L-R": "FIVE", "SSK1W1-R": "GO",
    "PD98GG-R": "HD", "R2J99W-R": "KR", "CHKL7S-R": "LOW", "VTBLV9-R": "MCD", "XNM3N2-R": "OLLI",
    "FJ4NDH-R": "ROST", "TWTDGH-R": "SBUX", "CSDT95-R": "SFM", "G6QSWR-R": "SG", "JNYJHG-R": "SHAK",
    "J994MP-R": "TGT", "S8ZPBT-R": "TJX", "BRWKF0-R": "TSCO", "X44KDF-R": "TXRH", "GM3DBL-R": "ULTA",
    "CSMTMQ-R": "WMT", "LNDJN4-R": "BOOT", "DF2CV6-R": "CNK", "H2VPCM-R": "VLO",
    # moderate foot-O (all-O expansion, 2026-06-29)
    "P36M94-R": "ORLY", "WPKF66-R": "BBY", "JDQ0K1-R": "AZO", "DKJ8VM-R": "DDS", "MRHVBK-R": "BJ",
    "J1JDGR-R": "CZR", "GJZ5YB-R": "KSS", "J75B2X-R": "BYD", "K8ZVRV-R": "DKS", "SDDH43-R": "WBA",
    "RBB7RY-R": "ANF", "THXZ97-R": "WING", "M79B89-R": "MGM", "BV3N5V-R": "M", "D1LJ47-R": "AEO",
    "XKTZWR-R": "URBN", "FBCHQC-R": "BBWI", "VXQ46D-R": "WEN", "R5RD6T-R": "GAP", "RQSKKH-R": "CASY",
}

CHANNELS = {
    "web": dict(
        x_csv=[DATA / "web_O39_by_company_3y.csv"], x_val="website_users",
        entity_map=WEB_ENTITY2TKR, entity_drop=WEB_ENTITY_DROP, yoy_lag=12,
        factset=DATA / "factset_web38_pit.json", fsym2tkr=WEB_FSYM2TKR,
        tx_index=DATA / "transcript_index_web.csv", screen_dt="web_traffic",
        x_table_label="WEB-TRAFFIC HISTORY (Carbon Arc, website users YoY)", x_unit="web_users_yoy",
    ),
    "card": dict(
        x_csv=[ROOT / "outputs" / "auto" / "ca0056_card_spend_by_ticker_q_3y.csv",
               DATA / "card_O_netnew_q_3y.csv"], x_val="credit_card_spend",
        entity_map=None, entity_drop=set(), yoy_lag=4,
        factset=DATA / "factset_card99_pit.json", fsym2tkr=CARD_FSYM2TKR,
        tx_index=DATA / "transcript_index_card.csv", screen_dt="card_spend",
        x_table_label="CARD-SPEND HISTORY (Carbon Arc alt-data)", x_unit="card_spend_yoy",
    ),
    "foot": dict(
        # headline universe = strong-O (foot-dominant). moderate-O CSV / factset_foot54 exist for the
        # all-O tier-dilution check (§11) but are NOT the canonical eval basis.
        x_csv=[DATA / "ca0060_foot_strongO_monthly_3y.csv"], x_val="foot_traffic",
        entity_map=None, entity_drop=set(), yoy_lag=12,
        factset=DATA / "factset_foot34_pit.json", fsym2tkr=FOOT_FSYM2TKR,
        tx_index=DATA / "transcript_index_foot.csv", screen_dt="foot_traffic",
        x_table_label="FOOT-TRAFFIC HISTORY (Carbon Arc CA0060, monthly visits YoY)", x_unit="foot_visits_yoy",
    ),
}


def active() -> str:
    ch = os.getenv("F1_CHANNEL", "web")
    assert ch in CHANNELS, f"unknown F1_CHANNEL={ch}"
    return ch


def cfg() -> dict:
    return CHANNELS[active()]
