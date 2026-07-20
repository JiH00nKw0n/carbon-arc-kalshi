"""Channel definitions (card / web / foot) — one frozen ChannelSpec each, self-registered.

All identifier maps and artifact paths are copied fresh from the factor1 reference
(f1_channels.py, f1_config.py); this package imports nothing from factor1. Paths point at
the existing, read-only factor1/data + outputs/auto artifacts.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from prediction.registry import Registry, register_channel

ROOT = Path("/Users/junekwon/Desktop/Projects/carbon_arc")
DATA = ROOT / "factor1" / "data"

# --- web: FactSet regional-id -> ticker (38), resolved via stock_server_query 2026-06-27 ---
WEB_FSYM2TKR = {
    "SGNT83-R": "PETS", "R5WR5K-R": "CVNA", "DJBQ39-R": "CPRT", "QT424T-R": "CHGG",
    "KKQZ6N-R": "TDUP", "LC0H1H-R": "BKNG", "HDM5JR-R": "GDRX", "F60CN6-R": "CARG",
    "MCNYYL-R": "AMZN", "K115Z0-R": "CARS", "NSRFNJ-R": "RVLV", "XDXV7H-R": "FVRR",
    "C5BK6W-R": "TRUE", "H8DT5P-R": "PINS", "W6SXMV-R": "EBAY", "DT59Y2-R": "YELP",
    "TB9J64-R": "TRIP", "FCK6QT-R": "EXPE", "HZQYZZ-R": "ABNB", "RGHJGD-R": "GRPN",
    "X64Y0M-R": "REAL", "GPXWM3-R": "UPWK", "TJ73WZ-R": "HIMS", "PGMHWX-R": "SFIX",
    "MMC067-R": "ZIP", "LT65S8-R": "ANGI", "PVBYXV-R": "ETSY", "JM5H9L-R": "RDDT",
    "C11243-R": "QNST", "BD3JGP-R": "SEAT", "XCLLKS-R": "EB", "H5J55J-R": "W",
    "VNJWFZ-R": "FIGS", "CF350L-R": "CHWY", "D8NTSF-R": "OPEN", "MRCM8L-R": "EVER",
    "STDTS0-R": "COUR", "WBGJFL-R": "ZG",
}

# Web entity_name -> ticker (clean matches only).
WEB_ENTITY2TKR = {
    "Airbnb Inc": "ABNB", "Amazon": "AMZN", "Booking Holdings": "BKNG", "CARG": "CARG",
    "CHGG": "CHGG", "CPRT": "CPRT", "Cars.com": "CARS", "Carvana": "CVNA", "Chewy Inc": "CHWY",
    "Coursera": "COUR", "EBAY": "EBAY", "ETSY": "ETSY", "Eventbrite": "EB",
    "Expedia Group Inc": "EXPE", "FIGS": "FIGS", "Groupon": "GRPN", "HIMS": "HIMS",
    "PetMed Express": "PETS", "Pinterest": "PINS", "Reddit": "RDDT", "Revolve Group": "RVLV",
    "SEAT": "SEAT", "Stitch Fix Inc": "SFIX", "TDUP": "TDUP", "The RealReal": "REAL",
    "Tripadvisor, Inc.": "TRIP", "Truecar, Inc.": "TRUE", "Upwork Inc": "UPWK",
    "Wayfair Inc": "W", "YELP": "YELP", "ZIP": "ZIP", "Zillow": "ZG", "goodrx.com": "GDRX",
}
# Excluded (mis-resolved by Carbon Arc entity search -> not the intended public company):
WEB_ENTITY_DROP = {"Beyond", "Evereve", "Phlur, Inc", "Qwant", "FIVE", "DoorDash"}

# --- card: FactSet id -> ticker (99), resolved via stock_server_query 2026-06-28 ---
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

# --- foot: strong-O FactSet id -> ticker (34) + moderate-O expansion, CA0060, resolved 2026-06-29 ---
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


@dataclass(frozen=True)
class ChannelSpec:
    """Everything that varies by alt-data channel; Y (surprise) and Z (calls) stay fixed."""
    name: str
    x_csv: list[str]
    x_val: str
    entity_map: Optional[dict]
    entity_drop: set
    yoy_lag: int
    factset: str
    fsym2tkr: dict
    tx_index: str
    screen_dt: str
    x_table_label: str
    x_unit: str


register_channel(ChannelSpec(
    name="web",
    x_csv=[str(DATA / "web_O39_by_company_3y.csv")],
    x_val="website_users",
    entity_map=WEB_ENTITY2TKR,
    entity_drop=WEB_ENTITY_DROP,
    yoy_lag=12,
    factset=str(DATA / "factset_web38_pit.json"),
    fsym2tkr=WEB_FSYM2TKR,
    tx_index=str(DATA / "transcript_index_web.csv"),
    screen_dt="web_traffic",
    x_table_label="WEB-TRAFFIC HISTORY (Carbon Arc, website users YoY)",
    x_unit="web_users_yoy",
))

register_channel(ChannelSpec(
    name="card",
    x_csv=[str(ROOT / "outputs" / "auto" / "ca0056_card_spend_by_ticker_q_3y.csv"),
           str(DATA / "card_O_netnew_q_3y.csv")],
    x_val="credit_card_spend",
    entity_map=None,
    entity_drop=set(),
    yoy_lag=4,
    factset=str(DATA / "factset_card99_pit.json"),
    fsym2tkr=CARD_FSYM2TKR,
    tx_index=str(DATA / "transcript_index_card.csv"),
    screen_dt="card_spend",
    x_table_label="CARD-SPEND HISTORY (Carbon Arc alt-data)",
    x_unit="card_spend_yoy",
))

register_channel(ChannelSpec(
    name="foot",
    x_csv=[str(DATA / "ca0060_foot_strongO_monthly_3y.csv")],
    x_val="foot_traffic",
    entity_map=None,
    entity_drop=set(),
    yoy_lag=12,
    factset=str(DATA / "factset_foot34_pit.json"),
    fsym2tkr=FOOT_FSYM2TKR,
    tx_index=str(DATA / "transcript_index_foot.csv"),
    screen_dt="foot_traffic",
    x_table_label="FOOT-TRAFFIC HISTORY (Carbon Arc CA0060, monthly visits YoY)",
    x_unit="foot_visits_yoy",
))


def get_channel(name: str) -> ChannelSpec:
    """Return the registered ChannelSpec named `name` (raises ModelConfigError if unknown)."""
    return Registry.get("channel", name)  # type: ignore[return-value]
