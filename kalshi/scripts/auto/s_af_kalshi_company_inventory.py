#!/usr/bin/env python3
"""
Build a reproducible inventory of Kalshi company-tagged markets.

Public API only. The inventory is intentionally broad at the series layer:
series tagged Companies/KPIs or filed under Companies are listed, then each
series' markets are fetched and flattened for downstream feature building.
"""
import argparse
import csv
import re
import time
from collections import Counter, defaultdict
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[3]
KALSHI_ROOT = ROOT / "kalshi"
BASE = "https://external-api.kalshi.com/trade-api/v2"
H = {"accept": "application/json", "user-agent": "carbonarc-kalshi-company-x/1.0"}
SCREEN = ROOT / "factor1" / "data" / "altdata_ticker_screen.csv"
OUT_AUTO = KALSHI_ROOT / "outputs" / "auto"
OUT_SERIES = OUT_AUTO / "kalshi_company_series.csv"
OUT_MARKETS = OUT_AUTO / "kalshi_company_markets.csv"
OUT_MD = KALSHI_ROOT / "docs" / "analysis_kalshi_company_inventory.md"

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
    "airbnb": "ABNB",
    "alphabet": "GOOG",
    "amazon": "AMZN",
    "apple": "AAPL",
    "boeing": "BA",
    "carnival": "CCL",
    "carvana": "CVNA",
    "cava": "CAVA",
    "chipotle": "CMG",
    "coinbase": "COIN",
    "coinbase global": "COIN",
    "doordash": "DASH",
    "ebay": "EBAY",
    "ferrari": "RACE",
    "fedex": "FDX",
    "fedex corporation": "FDX",
    "ford": "F",
    "ford motor": "F",
    "ford motor company": "F",
    "futu": "FUTU",
    "futu holdings": "FUTU",
    "google": "GOOG",
    "home depot": "HD",
    "intel": "INTC",
    "jpmorgan": "JPM",
    "jpmorgan chase": "JPM",
    "lyft": "LYFT",
    "mcdonalds": "MCD",
    "meta": "META",
    "netflix": "NFLX",
    "planet fitness": "PLNT",
    "rivian": "RIVN",
    "robinhood": "HOOD",
    "robinhood markets": "HOOD",
    "roku": "ROKU",
    "rocket lab": "RKLB",
    "southwest": "LUV",
    "southwest airlines": "LUV",
    "starbucks": "SBUX",
    "sweetgreen": "SG",
    "tesla": "TSLA",
    "toll brothers": "TOL",
    "toast": "TOST",
    "uber": "UBER",
    "walmart": "WMT",
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


def load_ticker_map(path):
    aliases = {}
    for name, ticker in MANUAL_ALIASES.items():
        aliases[norm_name(name)] = (ticker, "manual_alias", name)
    if not path.exists():
        return aliases
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            company = row.get("company", "")
            ticker = row.get("ticker", "")
            if not company or not ticker:
                continue
            key = norm_name(company)
            aliases.setdefault(key, (ticker, "altdata_screen", company))
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


def fetch_series(sess, base_url, category):
    rows, seen, cursor, pages = [], set(), "", 0
    while pages < 80:
        params = {"include_volume": "true"}
        if category:
            params["category"] = category
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
    series_ticker, _, series_match_company = match_ticker(
        series_company, series.get("title", ""), series.get("ticker", ""), aliases
    )
    market_ticker, market_method, market_match_company = match_ticker(
        market_company, "", "", aliases
    ) if market_company else ("", "", "")

    company = market_company or series_company
    if market_ticker and series_ticker and market_ticker != series_ticker:
        basis.append("quality:series_market_company_conflict")
        company = f"{market_company} (series: {series_company})"
        ticker, method, match_company = "", "conflict_series_market", f"{market_match_company}|{series_match_company}"
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
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def write_report(series_rows, market_rows, categories, include_historical, out_series, out_markets, out_md):
    tag_counts = Counter()
    for r in series_rows:
        for tag in r["series_tags"].split("|"):
            if tag:
                tag_counts[tag] += 1
    by_company = defaultdict(lambda: [0, 0.0, set()])
    for r in market_rows:
        key = r.get("matched_ticker") or r.get("company_name_guess") or "(unmatched)"
        by_company[key][0] += 1
        try:
            by_company[key][1] += float(r.get("volume_fp") or 0)
        except ValueError:
            pass
        if r.get("event_ticker"):
            by_company[key][2].add(r["event_ticker"])
    top = sorted(by_company.items(), key=lambda kv: kv[1][1], reverse=True)[:20]

    lines = [
        "# Kalshi company-tagged inventory",
        "",
        f"> Generated by `kalshi/scripts/auto/s_af_kalshi_company_inventory.py`.",
        "",
        "## Scope",
        f"- categories fetched: {', '.join(categories)}",
        f"- include historical endpoint: {include_historical}",
        f"- series rows: {len(series_rows):,}",
        f"- market rows: {len(market_rows):,}",
        f"- matched tickers: {sum(bool(r.get('matched_ticker')) for r in series_rows):,}/{len(series_rows):,} series",
        "",
        "## Tag counts",
    ]
    for tag, n in tag_counts.most_common(20):
        lines.append(f"- {tag}: {n}")
    lines += ["", "## Top companies / series by market volume", ""]
    lines.append("| key | markets | events | volume_fp |")
    lines.append("|---|---:|---:|---:|")
    for key, (n_markets, vol, events) in top:
        lines.append(f"| {key} | {n_markets} | {len(events)} | {vol:.2f} |")
    lines += [
        "",
        "## Outputs",
        f"- `{out_series.relative_to(ROOT)}`",
        f"- `{out_markets.relative_to(ROOT)}`",
        "",
        "Notes: ticker matching is heuristic. Downstream tests should treat blank or low-confidence matches as unmapped until manually reviewed.",
    ]
    out_md.write_text("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=BASE)
    ap.add_argument("--categories", default="Financials,Companies")
    ap.add_argument("--screen", type=Path, default=SCREEN)
    ap.add_argument("--out-series", type=Path, default=OUT_SERIES)
    ap.add_argument("--out-markets", type=Path, default=OUT_MARKETS)
    ap.add_argument("--out-md", type=Path, default=OUT_MD)
    ap.add_argument("--include-historical", action="store_true")
    ap.add_argument("--sleep", type=float, default=0.03)
    args = ap.parse_args()

    aliases = load_ticker_map(args.screen)
    sess = requests.Session()
    sess.headers.update(H)

    categories = [c.strip() for c in args.categories.split(",") if c.strip()]
    raw_series, seen_series = [], set()
    for category in categories:
        got = fetch_series(sess, args.base_url, category)
        print(f"[series] category={category} rows={len(got)}")
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

    write_csv(args.out_series, SERIES_COLS, series_rows)
    write_csv(args.out_markets, MARKET_COLS, market_rows)
    write_report(series_rows, market_rows, categories, args.include_historical, args.out_series, args.out_markets, args.out_md)
    print(f"[written] {args.out_series}")
    print(f"[written] {args.out_markets}")
    print(f"[written] {args.out_md}")


if __name__ == "__main__":
    main()
