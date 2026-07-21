#!/usr/bin/env python3
"""
s_ka_kpi_inventory.py — data-driven universe discovery for the Kalshi×FactSet
KPI-nowcasting experiment (X = Kalshi implied KPI distribution, factor3 skeleton).

Problem: the design doc's series tickers were placeholders. We do NOT guess.
We enumerate the Companies category from /series, then for every candidate series
measure how many RESOLVED quarterly events (strike ladders) it actually has.
Only series with resolved_quarters >= MIN_Q survive as a usable panel.

Public, unauthenticated:
  /series                       -> full catalog (one page, ~11k series)
  /historical/markets?series_ticker=PREFIX -> resolved archived markets (strike ladder)

Output: outputs/kalshi_kpi_inventory.csv  (one row per candidate series)
        + stdout ranked table of survivors.
"""
import csv
import re
import sys
import time
import collections
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "kalshi_kpi_inventory.csv"
BASE = "https://api.elections.kalshi.com/trade-api/v2"
H = {"accept": "application/json", "user-agent": "carbonarc-research/1.0"}

MIN_Q = 4  # report everything with >=4 resolved events; flag >=6 as "panel-grade"

# KPI-ladder markets phrase their rules as "reports above/at least N <unit>".
# Non-KPI Companies markets (CEO change, "who joins X", lawsuits) do NOT.
# We detect ladders structurally: an event with >=2 strikes that resolved yes/no.
KPI_HINT = re.compile(
    r"headcount|deliver|daily active|monthly active|\bDAP\b|\bMAU\b|\bDAU\b|"
    r"subscriber|\btrips\b|revenue|\bsales\b|bookings|users|units|shipments|"
    r"gross merchandise|\bGMV\b|production|reports? (above|at least)",
    re.I,
)

sess = requests.Session()
sess.headers.update(H)


def get(path, params, tries=4):
    for i in range(tries):
        try:
            r = sess.get(f"{BASE}{path}", params=params, timeout=30)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (429, 500, 502, 503):
                time.sleep(0.4 * (i + 1))
                continue
            return None
        except Exception:
            time.sleep(0.4 * (i + 1))
    return None


def list_company_series():
    d = get("/series", {"limit": 20000})
    if not d:
        sys.exit("failed to pull /series catalog")
    return [s for s in d.get("series", []) if s.get("category") == "Companies"]


def pull_markets(prefix):
    """all archived markets for a series prefix (paginated)."""
    rows, cursor, pages = [], "", 0
    while pages < 30:
        params = {"series_ticker": prefix, "limit": 1000}
        if cursor:
            params["cursor"] = cursor
        d = get("/historical/markets", params)
        if not d:
            break
        rows.extend(d.get("markets", []) or [])
        cursor = (d.get("cursor") or "").strip()
        pages += 1
        if not cursor:
            break
    return rows


def summarize(prefix, markets):
    """group markets into events; count resolved multi-strike (=quarter/period) events."""
    ev = collections.defaultdict(lambda: {"strikes": 0, "resolved": 0, "close": None, "rule": ""})
    for m in markets:
        et = m.get("event_ticker", "")
        e = ev[et]
        e["strikes"] += 1
        if m.get("result") in ("yes", "no"):
            e["resolved"] += 1
        ct = (m.get("close_time") or "")[:10]
        if ct and (e["close"] is None or ct > e["close"]):
            e["close"] = ct
        if not e["rule"]:
            e["rule"] = (m.get("rules_primary") or "")
    # a usable KPI period = ladder (>=2 strikes) fully/mostly resolved
    ladder_events = {k: v for k, v in ev.items() if v["strikes"] >= 2 and v["resolved"] >= 1}
    kpi_events = {k: v for k, v in ladder_events.items() if KPI_HINT.search(v["rule"] or "")}
    closes = sorted(v["close"] for v in kpi_events.values() if v["close"])
    return {
        "series": prefix,
        "n_markets": len(markets),
        "n_events_total": len(ev),
        "n_ladder_events": len(ladder_events),
        "n_kpi_events": len(kpi_events),
        "date_min": closes[0] if closes else "",
        "date_max": closes[-1] if closes else "",
        "sample_rule": next(iter(kpi_events.values()))["rule"][:120].replace("\n", " ") if kpi_events else "",
    }


def candidate_prefixes(series_list):
    """
    Company KPI ladders live under a base prefix (e.g. KXTESLA, KXMETADAP).
    The catalog lists the KX-prefixed series; legacy (no-KX) history hangs off
    the same base minus 'KX'. We probe both.
    """
    prefixes = set()
    for s in series_list:
        t = s.get("ticker", "")
        prefixes.add(t)
        if t.startswith("KX"):
            prefixes.add(t[2:])  # legacy variant holds older quarters
    # also add the known quarterly bases the catalog may label differently
    for extra in ("KXTESLA", "TESLA", "KXMETADAP", "METADAP", "KXUBERTRIPS",
                  "KXNETFLIXSUBS", "NETFLIXSUBS", "KXMETAHEADCOUNT"):
        prefixes.add(extra)
    return sorted(prefixes)


def main():
    series_list = list_company_series()
    print(f"Companies category: {len(series_list)} series", file=sys.stderr)
    prefixes = candidate_prefixes(series_list)
    print(f"probing {len(prefixes)} candidate prefixes (incl. legacy variants)...", file=sys.stderr)

    results = []
    for i, p in enumerate(prefixes):
        mk = pull_markets(p)
        if not mk:
            continue
        r = summarize(p, mk)
        if r["n_kpi_events"] >= 1:
            results.append(r)
        if (i + 1) % 25 == 0:
            print(f"  ...{i+1}/{len(prefixes)}", file=sys.stderr)
        time.sleep(0.02)

    results.sort(key=lambda r: (-r["n_kpi_events"], r["series"]))
    OUT.parent.mkdir(exist_ok=True)
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].keys()) if results else
                           ["series", "n_markets", "n_events_total", "n_ladder_events",
                            "n_kpi_events", "date_min", "date_max", "sample_rule"])
        w.writeheader()
        w.writerows(results)

    print(f"\n{'series':22s} {'kpiQ':>4s} {'ladQ':>4s} {'range':>23s}  rule")
    print("-" * 110)
    for r in results:
        flag = "  <-- PANEL" if r["n_kpi_events"] >= 6 else ("  <- usable" if r["n_kpi_events"] >= MIN_Q else "")
        rng = f"{r['date_min']}..{r['date_max']}"
        print(f"{r['series']:22s} {r['n_kpi_events']:4d} {r['n_ladder_events']:4d} {rng:>23s}{flag}")
    print(f"\nwrote {OUT}  ({len(results)} series with >=1 KPI quarter)")
    panel = [r for r in results if r["n_kpi_events"] >= 6]
    print(f"PANEL-GRADE (>=6 resolved KPI quarters): {[r['series'] for r in panel]}")


if __name__ == "__main__":
    main()
