"""
Y-switching experiment config — mirrors ft_config.py structure.

Goal: hold X (Carbon Arc alt-data) fixed, SWITCH Y across targets, and measure which
Y a given alt-data channel actually predicts. Baseline (지훈, factor3): CA0056 card ×
Revenue Surprise r=+0.192; the same X vs EPS surprise / price return failed. This module
generalizes that Y-switch across 3 channels and adds rank-IC / Spearman / hit-rate / lag metrics.

Channels (X):
  card  = CA0056 credit_card_spend, QUARTERLY, 66 tickers, Online+Physical → YoY = pct_change(4)
  foot  = CA0060 foot_traffic,      MONTHLY,   ~50 tickers → monthly YoY = pct_change(12), align to FQ-end
  click = CA0030 website_users,     MONTHLY,   38 tickers, Mobile+Desktop → monthly YoY, align to FQ-end

Y targets (all from FactSet PIT, same source as factor1/factor3):
  rev_yoy         = pct_change(4) of ACTUAL revenue          (level sanity)
  surprise_early  = (ACTUAL − CONS_EARLY)/CONS_EARLY         (THE test — 지훈 baseline)
  surprise_print  = (ACTUAL − CONS_PRINT)/CONS_PRINT
  + rank-IC, Spearman, hit-rate, lag-curve computed in ys_lib.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT  = ROOT / "outputs"
OUT.mkdir(parents=True, exist_ok=True)

# reuse 지훈's clustered-bootstrap / surrogate verdict gate (no code duplication)
F1_STATS = ROOT.parent / "factor1" / "scripts"

# --- X channel files (reinstated Carbon Arc frameworks, downloaded free) ---
CARD_CSV  = DATA / "ca0056_card_66tkr_quarterly.csv"   # CA0056, quarterly, entity_name=ticker
FOOT_CSVS = [DATA / "ca0060_foot_10tkr_monthly.csv",
             DATA / "ca0060_foot_20tkr_A.csv",
             DATA / "ca0060_foot_24tkr_B.csv"]          # CA0060, monthly, entity_name=ticker
CLICK_CSV = DATA / "ca0030_click_38tkr.csv"            # CA0030, monthly, entity_name=company (needs map)

# Y (FactSet PIT surprise) — fetched by ys_00_fetch_factset.py for the union of all X tickers
FACTSET_JSON = DATA / "factset_yswitch_pit.json"

# clickstream entity_name → US ticker (company-form names in the raw file)
CLICK_NAME2TKR = {
    "Airbnb Inc": "ABNB", "Amazon": "AMZN", "Beyond": "BYON", "Booking Holdings": "BKNG",
    "CARG": "CARG", "CHGG": "CHGG", "CPRT": "CPRT", "Cars.com": "CARS", "Carvana": "CVNA",
    "Chewy Inc": "CHWY", "Coursera": "COUR", "DoorDash": "DASH", "EBAY": "EBAY", "ETSY": "ETSY",
    "Eventbrite": "EB", "Expedia Group Inc": "EXPE", "FIGS": "FIGS", "FIVE": "FIVE",
    "Groupon": "GRPN", "HIMS": "HIMS", "Pinterest": "PINS", "Reddit": "RDDT",
    "Revolve Group": "RVLV", "SEAT": "SEAT", "Stitch Fix Inc": "SFIX", "TDUP": "TDUP",
    "The RealReal": "REAL", "Tripadvisor, Inc.": "TRIP", "Truecar, Inc.": "TRUE",
    "Upwork Inc": "UPWK", "Wayfair Inc": "W", "YELP": "YELP", "ZIP": "ZIP", "Zillow": "ZG",
    # dropped (no clean single US equity / not covered): PetMed Express, Phlur, Qwant,
    # Evereve, goodrx.com — left unmapped so they fall out of the panel.
}

CUTOFF = "2025-12-01"   # LLM eval cutoff (kept for parity; unused in the corr battery)
