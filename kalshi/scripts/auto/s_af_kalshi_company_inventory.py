#!/usr/bin/env python3
"""
Build a reproducible inventory of Kalshi KPI-tagged company markets.

Public API only. By default the series endpoint is queried directly with the
official ``tags=KPIs`` filter across every category, then current and archived
markets are flattened for downstream ladder construction.
"""
import argparse
import csv
import re
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[3]
KALSHI_ROOT = ROOT / "kalshi"
BASE = "https://external-api.kalshi.com/trade-api/v2"
H = {"accept": "application/json", "user-agent": "kalshi-kpi-inventory/2.0"}
OUT_AUTO = KALSHI_ROOT / "outputs" / "auto"
OUT_SERIES = OUT_AUTO / "kalshi_company_series.csv"
OUT_MARKETS = OUT_AUTO / "kalshi_company_markets.csv"

SERIES_COLS = [
    "series_ticker", "series_title", "series_category", "series_tags",
    "series_frequency", "series_volume_fp", "contract_terms_url",
    "settlement_sources", "tag_basis", "company_name_guess",
    "matched_ticker", "match_method", "match_company",
]
MARKET_COLS = [
    "series_ticker", "series_title", "series_category", "series_tags",
    "tag_basis", "company_name_guess", "matched_ticker", "match_method",
    "match_company", "event_ticker", "market_ticker", "market_title",
    "yes_sub_title", "no_sub_title", "status", "market_type", "strike_type",
    "floor_strike", "cap_strike", "last_price_dollars", "yes_bid_dollars",
    "yes_ask_dollars", "no_bid_dollars", "no_ask_dollars", "volume_fp",
    "open_interest_fp", "volume_24h_fp", "liquidity_dollars", "open_time",
    "close_time", "expiration_time", "occurrence_datetime", "result",
    "custom_strike_company", "rules_primary", "rules_secondary",
]

MANUAL_ALIASES = {
    "air canada": "ACDVF",
    "airbnb": "ABNB",
    "alphabet": "GOOGL",
    "altria": "MO",
    "altria group": "MO",
    "amazon": "AMZN",
    "apple": "AAPL",
    "aritzia": "ATZ",
    "boeing": "BA",
    "canadian tire": "CDNTF",
    "canadian tire corporation": "CDNTF",
    "carnival": "CCL",
    "carvana": "CVNA",
    "cava": "CAVA",
    "charles schwab": "SCHW",
    "chipotle": "CMG",
    "clear": "YOU",
    "clear secure": "YOU",
    "coinbase": "COIN",
    "coinbase global": "COIN",
    "constellation brands": "STZ",
    "costco": "COST",
    "costco wholesale": "COST",
    "costco wholesale corporation": "COST",
    "disney": "DIS",
    "domino's": "DPZ",
    "domino's pizza": "DPZ",
    "draftkings": "DKNG",
    "doordash": "DASH",
    "dollarama": "DLMAF",
    "ebay": "EBAY",
    "ferrari": "RACE",
    "fedex": "FDX",
    "fedex corporation": "FDX",
    "figma": "FIG",
    "first solar": "FSLR",
    "ford": "F",
    "ford motor": "F",
    "ford motor company": "F",
    "grab": "GRAB",
    "grab holdings": "GRAB",
    "futu": "FUTU",
    "futu holdings": "FUTU",
    "google": "GOOGL",
    "home depot": "HD",
    "hilton": "HLT",
    "hims and hers": "HIMS",
    "hims and hers health": "HIMS",
    "intel": "INTC",
    "jpmorgan": "JPM",
    "jpmorgan chase": "JPM",
    "klarna": "KLAR",
    "loblaw": "L",
    "loblaw companies": "L",
    "lowe's": "LOW",
    "lululemon": "LULU",
    "marriott": "MAR",
    "marriott international": "MAR",
    "match group": "MTCH",
    "mercadolibre": "MELI",
    "lyft": "LYFT",
    "mcdonalds": "MCD",
    "meta": "META",
    "new york times": "NYT",
    "netflix": "NFLX",
    "norwegian cruise line": "NCLH",
    "norwegian cruise line holdings": "NCLH",
    "nu holdings": "NU",
    "nvidia": "NVDA",
    "oracle": "ORCL",
    "palantir": "PLTR",
    "palantir technologies": "PLTR",
    "paramount skydance": "PSKY",
    "petroleo brasileiro": "PETR4",
    "petrobras": "PETR4",
    "philip morris": "PM",
    "philip morris international": "PM",
    "planet fitness": "PLNT",
    "rivian": "RIVN",
    "robinhood": "HOOD",
    "reddit": "RDDT",
    "robinhood markets": "HOOD",
    "roblox": "RBLX",
    "roku": "ROKU",
    "rocket lab": "RKLB",
    "sea": "SE",
    "sea garena": "SE",
    "sea limited": "SE",
    "snap": "SNAP",
    "snapchat": "SNAP",
    "snowflake": "SNOW",
    "shopify": "SHOP",
    "spotify": "SPOT",
    "spotify technology": "SPOT",
    "sofi": "SOFI",
    "southwest": "LUV",
    "southwest airlines": "LUV",
    "starbucks": "SBUX",
    "sweetgreen": "SG",
    "talen energy": "TLN",
    "taiwan semiconductor": "2330",
    "taiwan semiconductor manufacturing": "2330",
    "tsmc": "2330",
    "tesla": "TSLA",
    "target": "TGT",
    "toll brothers": "TOL",
    "toast": "TOST",
    "uber": "UBER",
    "ulta beauty": "ULTA",
    "united airlines": "UAL",
    "united airlines holdings": "UAL",
    "urban outfitters": "URBN",
    "vail resorts": "MTN",
    "visa": "V",
    "walt disney": "DIS",
    "the walt disney company": "DIS",
    "wendy's": "WEN",
    "wingstop": "WING",
    "wyndham hotels and resorts": "WH",
    "walmart": "WMT",
    "webull": "BULL",
    "zeta": "ZETA",
    "zeta global": "ZETA",
    # Legacy/special-purpose series titles whose issuer is still explicit.
    "fb daily active users": "META",
    "nyt subscribers": "NYT",
    "rh gold": "HOOD",
    "sofi new members": "SOFI",
}

SUFFIX_RE = re.compile(
    r"\b(incorporated|inc|corp|corporation|co|company|companies|holdings|holding|"
    r"group|global|plc|ltd|limited|class|ordinary|common|the)\b"
)


def clean_text(v):
    return re.sub(r"\s+", " ", str(v or "").replace("\n", " ")).strip()


def norm_name(v):
    s = clean_text(v).lower()
    s = s.replace("&", " and ")
    s = re.sub(r"['.]", "", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = SUFFIX_RE.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def load_ticker_map():
    aliases = {}
    for name, ticker in MANUAL_ALIASES.items():
        aliases[norm_name(name)] = (ticker, "manual_alias", name)
    return aliases


def phrase_in(needle, haystack):
    if not needle or not haystack:
        return False
    return re.search(rf"(^| ){re.escape(needle)}( |$)", haystack) is not None


def match_ticker(company, series_title, series_ticker, aliases):
    candidates = [norm_name(company), norm_name(series_title)]
    for candidate in candidates:
        if candidate in aliases:
            return aliases[candidate]
    ranked = sorted(aliases.items(), key=lambda kv: len(kv[0]), reverse=True)
    for candidate in candidates:
        if len(candidate) < 3:
            continue
        for alias, match in ranked:
            if len(alias) < 3:
                continue
            if phrase_in(alias, candidate) or phrase_in(candidate, alias):
                return match

    hint = re.sub(r"^KX", "", clean_text(series_ticker).upper())
    for _alias, match in aliases.items():
        ticker = match[0].upper()
        if hint == ticker or (len(ticker) >= 3 and hint.startswith(ticker)):
            return ticker, "series_ticker_hint", match[2]
    return "", "", ""


def get_json(sess, base_url, path, params=None):
    for attempt in range(5):
        try:
            r = sess.get(f"{base_url}{path}", params=params or {}, timeout=30)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(0.5 * (attempt + 1))
                continue
            print(f"[warn] {path} {params or {}} -> HTTP {r.status_code}: {r.text[:160]}")
            return None
        except requests.RequestException as e:
            print(f"[warn] {path} {params or {}} -> {e}")
            time.sleep(0.5 * (attempt + 1))
    return None


def fetch_series(sess, base_url, category="", tags=""):
    rows, seen, cursor, pages = [], set(), "", 0
    while pages < 80:
        params = {"include_volume": "true"}
        if category:
            params["category"] = category
        if tags:
            params["tags"] = tags
        if cursor:
            params["cursor"] = cursor
        d = get_json(sess, base_url, "/series", params)
        if not d:
            break
        for s in d.get("series", []) or []:
            ticker = s.get("ticker")
            if ticker and ticker not in seen:
                seen.add(ticker)
                rows.append(s)
        cursor = clean_text(d.get("cursor"))
        pages += 1
        if not cursor:
            break
    return rows


def candidate_basis(s):
    tags = {clean_text(t).lower() for t in (s.get("tags") or [])}
    basis = []
    if "companies" in tags:
        basis.append("tag:Companies")
    if "kpis" in tags:
        basis.append("tag:KPIs")
    if clean_text(s.get("category")).lower() == "companies":
        basis.append("category:Companies")
    return basis


def fetch_markets(sess, base_url, series_ticker, endpoint="/markets", max_pages=30):
    rows, seen, cursor, pages = [], set(), "", 0
    while pages < max_pages:
        params = {"series_ticker": series_ticker, "limit": 1000}
        if cursor:
            params["cursor"] = cursor
        d = get_json(sess, base_url, endpoint, params)
        if not d:
            break
        for m in d.get("markets", []) or []:
            ticker = m.get("ticker")
            if ticker and ticker not in seen:
                seen.add(ticker)
                rows.append(m)
        cursor = clean_text(d.get("cursor"))
        pages += 1
        if not cursor:
            break
    return rows


def infer_company_from_market(market):
    text = " ".join([
        clean_text(market.get("title")),
        clean_text(market.get("rules_primary")),
    ])
    patterns = [
        r"\bWill\s+(.+?)\s+report\b",
        r"\bIf\s+(.+?)\s+reports?\b",
        r"\bWill\s+(.+?)\s+have\b",
        r"\bWill\s+(.+?)\s+(?:launch|produce|deliver|sell)\b",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.I)
        if m:
            return clean_text(m.group(1))
    return ""


def infer_company_from_series(series):
    title = clean_text(series.get("title"))
    cleaned = re.sub(r"\bAnnual KPI\b", "", title, flags=re.I)
    cleaned = re.sub(r"\bKPI\b", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\bnew CEO\b", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\bbe acquired\b", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\bpaid rides per week\b", "", cleaned, flags=re.I)
    return clean_text(cleaned)


def settlement_sources(series):
    return "|".join(clean_text(s.get("name")) for s in (series.get("settlement_sources") or []))


def series_row(series, markets, aliases):
    basis = candidate_basis(series)
    if any((m.get("custom_strike") or {}).get("company") for m in markets):
        basis.append("market:custom_strike.company")
    market_company = ""
    for m in markets:
        market_company = infer_company_from_market(m)
        if market_company:
            break
    series_company = infer_company_from_series(series)
    series_ticker, series_method, series_match_company = match_ticker(
        series_company, series.get("title", ""), series.get("ticker", ""), aliases
    )
    market_ticker, market_method, market_match_company = match_ticker(
        market_company, "", "", aliases
    ) if market_company else ("", "", "")

    company = market_company or series_company
    if market_ticker and series_ticker and market_ticker != series_ticker:
        basis.append("quality:series_market_company_conflict")
        company = f"{market_company} (series: {series_company})"
        # The series-level issuer is explicit and stable; a stray historical contract can contain
        # a conflicting company phrase. Preserve the explicit series mapping and retain the flag.
        ticker, method = series_ticker, f"{series_method}_market_conflict"
        match_company = f"{series_match_company}|market:{market_match_company}"
    elif market_ticker:
        ticker, method, match_company = market_ticker, market_method, market_match_company
    else:
        ticker, method, match_company = match_ticker(
            series_company, series.get("title", ""), series.get("ticker", ""), aliases
        )
    return {
        "series_ticker": clean_text(series.get("ticker")),
        "series_title": clean_text(series.get("title")),
        "series_category": clean_text(series.get("category")),
        "series_tags": "|".join(clean_text(t) for t in (series.get("tags") or [])),
        "series_frequency": clean_text(series.get("frequency")),
        "series_volume_fp": clean_text(series.get("volume_fp")),
        "contract_terms_url": clean_text(series.get("contract_terms_url")),
        "settlement_sources": settlement_sources(series),
        "tag_basis": "|".join(sorted(set(basis))),
        "company_name_guess": company,
        "matched_ticker": ticker,
        "match_method": method,
        "match_company": match_company,
    }


def market_row(series_info, market):
    custom = market.get("custom_strike") or {}
    return {
        **{k: series_info.get(k, "") for k in SERIES_COLS if k not in ("contract_terms_url", "settlement_sources", "series_frequency", "series_volume_fp")},
        "event_ticker": clean_text(market.get("event_ticker")),
        "market_ticker": clean_text(market.get("ticker")),
        "market_title": clean_text(market.get("title")),
        "yes_sub_title": clean_text(market.get("yes_sub_title") or market.get("subtitle")),
        "no_sub_title": clean_text(market.get("no_sub_title")),
        "status": clean_text(market.get("status")),
        "market_type": clean_text(market.get("market_type")),
        "strike_type": clean_text(market.get("strike_type")),
        "floor_strike": clean_text(market.get("floor_strike")),
        "cap_strike": clean_text(market.get("cap_strike")),
        "last_price_dollars": clean_text(market.get("last_price_dollars")),
        "yes_bid_dollars": clean_text(market.get("yes_bid_dollars")),
        "yes_ask_dollars": clean_text(market.get("yes_ask_dollars")),
        "no_bid_dollars": clean_text(market.get("no_bid_dollars")),
        "no_ask_dollars": clean_text(market.get("no_ask_dollars")),
        "volume_fp": clean_text(market.get("volume_fp")),
        "open_interest_fp": clean_text(market.get("open_interest_fp")),
        "volume_24h_fp": clean_text(market.get("volume_24h_fp")),
        "liquidity_dollars": clean_text(market.get("liquidity_dollars")),
        "open_time": clean_text(market.get("open_time")),
        "close_time": clean_text(market.get("close_time")),
        "expiration_time": clean_text(market.get("expiration_time")),
        "occurrence_datetime": clean_text(market.get("occurrence_datetime")),
        "result": clean_text(market.get("result")),
        "custom_strike_company": clean_text(custom.get("company")),
        "rules_primary": clean_text(market.get("rules_primary")),
        "rules_secondary": clean_text(market.get("rules_secondary")),
    }


def write_csv(path, cols, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(
            f, fieldnames=cols, extrasaction="ignore", lineterminator="\n"
        )
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=BASE)
    ap.add_argument(
        "--categories",
        default="",
        help="optional comma-separated category restriction; blank means every category",
    )
    ap.add_argument("--tags", default="KPIs", help="official /series tag filter")
    ap.add_argument("--out-series", type=Path, default=OUT_SERIES)
    ap.add_argument("--out-markets", type=Path, default=OUT_MARKETS)
    ap.add_argument(
        "--include-historical",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="merge archived markets from /historical/markets (default: enabled)",
    )
    ap.add_argument("--sleep", type=float, default=0.03)
    args = ap.parse_args()

    aliases = load_ticker_map()
    sess = requests.Session()
    sess.headers.update(H)

    categories = [c.strip() for c in args.categories.split(",") if c.strip()]
    raw_series, seen_series = [], set()
    scopes = categories or [""]
    for category in scopes:
        got = fetch_series(sess, args.base_url, category, args.tags)
        print(f"[series] category={category or 'all'} tags={args.tags or 'none'} rows={len(got)}")
        for s in got:
            ticker = s.get("ticker")
            if ticker and ticker not in seen_series:
                seen_series.add(ticker)
                raw_series.append(s)

    candidates = [s for s in raw_series if candidate_basis(s)]
    print(f"[series] candidates={len(candidates)} / raw={len(raw_series)}")

    series_rows, market_rows = [], []
    for i, s in enumerate(candidates, 1):
        ticker = s.get("ticker")
        markets = fetch_markets(sess, args.base_url, ticker, "/markets")
        if args.include_historical:
            historical = fetch_markets(sess, args.base_url, ticker, "/historical/markets")
            by_ticker = {m.get("ticker"): m for m in markets if m.get("ticker")}
            for m in historical:
                if m.get("ticker") not in by_ticker:
                    markets.append(m)
        info = series_row(s, markets, aliases)
        series_rows.append(info)
        for m in markets:
            market_rows.append(market_row(info, m))
        if i % 25 == 0 or i == len(candidates):
            print(f"[markets] {i}/{len(candidates)} series, market_rows={len(market_rows)}")
        time.sleep(args.sleep)

    series_rows.sort(key=lambda row: row["series_ticker"])
    market_rows.sort(
        key=lambda row: (
            row["series_ticker"],
            row["event_ticker"],
            row["market_ticker"],
        )
    )
    write_csv(args.out_series, SERIES_COLS, series_rows)
    write_csv(args.out_markets, MARKET_COLS, market_rows)
    print(f"[written] {args.out_series}")
    print(f"[written] {args.out_markets}")
    print(
        f"series={len(series_rows)} markets={len(market_rows)} "
        f"mapped_series={sum(bool(row.get('matched_ticker')) for row in series_rows)}"
    )


if __name__ == "__main__":
    main()
