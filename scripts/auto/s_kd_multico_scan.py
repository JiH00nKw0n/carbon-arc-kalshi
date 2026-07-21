#!/usr/bin/env python3
"""
s_kd_multico_scan.py — broad multi-company KPI-ladder inventory.

Scans EVERY Kalshi Companies-category series (+ legacy KX-stripped variant) for
quarterly KPI strike ladders, measures resolved-quarter depth and how many
quarters "bracket" the outcome (both yes & no strikes -> recoverable implied mean).

Resilient: shared session, retry w/ backoff, pacing — the naive version tripped
Connection-reset from hammering ~250 prefixes.

Output: outputs/kalshi_multico_inventory.csv, ranked. Flags panel-grade (>=6 KPI q).
"""
import csv
import re
import sys
import time
import collections
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "kalshi_multico_inventory.csv"
BASE = "https://api.elections.kalshi.com/trade-api/v2"
H = {"accept": "application/json", "user-agent": "carbonarc-research/1.0"}

KPI = re.compile(
    r"headcount|deliver|daily active|monthly active|\bDAP\b|\bMAU\b|\bDAU\b|"
    r"subscriber|\btrips\b|revenue|\bsales\b|bookings|\busers\b|units|shipments|"
    r"gross merchandise|\bGMV\b|production|reports? (above|at least)|\bstores\b|"
    r"members|passengers|nights|orders|vehicles|paid|net adds", re.I)

sess = requests.Session()
sess.headers.update(H)


def get(path, params, tries=6):
    for i in range(tries):
        try:
            r = sess.get(f"{BASE}{path}", params=params, timeout=30)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(0.5 * (i + 1)); continue
            return None
        except requests.exceptions.RequestException:
            time.sleep(0.6 * (i + 1))
    return None


def series_markets(pfx):
    rows, cur, pg = [], "", 0
    while pg < 20:
        p = {"series_ticker": pfx, "limit": 1000}
        if cur:
            p["cursor"] = cur
        d = get("/historical/markets", p)
        if d is None:
            break
        rows += d.get("markets", []) or []
        cur = (d.get("cursor") or "").strip(); pg += 1
        if not cur:
            break
    return rows


def main():
    cat = get("/series", {"limit": 20000})
    if not cat or "series" not in cat:
        sys.exit("failed to fetch /series catalog (rate-limited?) — retry in a minute")
    # Company-KPI ladders (Tesla deliveries, Meta DAP, Netflix subs, ...) live under
    # 'Financials', NOT 'Companies' (which is mostly CEO-change/one-off event markets).
    # Include Economics for retail/sales-type KPIs. Also legacy KX-stripped variants.
    CATS = {"Financials", "Companies", "Economics"}
    comp = [s for s in cat["series"] if s.get("category") in CATS]
    prefixes = set()
    for s in comp:
        t = s["ticker"]; prefixes.add(t)
        if t.startswith("KX"):
            prefixes.add(t[2:])
    prefixes = sorted(prefixes)
    print(f"scanning {len(prefixes)} prefixes...", file=sys.stderr)

    results = []
    for i, p in enumerate(prefixes):
        ms = series_markets(p)
        if not ms:
            time.sleep(0.05); continue
        ev = collections.defaultdict(lambda: {"n": 0, "res": 0, "yes": 0, "no": 0, "close": None, "rule": ""})
        for m in ms:
            et = m.get("event_ticker", ""); e = ev[et]; e["n"] += 1
            if m.get("result") == "yes":
                e["res"] += 1; e["yes"] += 1
            elif m.get("result") == "no":
                e["res"] += 1; e["no"] += 1
            ct = (m.get("close_time") or "")[:10]
            if ct and (e["close"] is None or ct > e["close"]):
                e["close"] = ct
            if not e["rule"]:
                e["rule"] = m.get("rules_primary") or ""
        ladders = {k: v for k, v in ev.items() if v["n"] >= 2 and v["res"] >= 1 and KPI.search(v["rule"] or "")}
        if len(ladders) < 2:
            time.sleep(0.05); continue
        brk = sum(1 for v in ladders.values() if v["yes"] and v["no"])
        avg_strk = sum(v["n"] for v in ladders.values()) / len(ladders)
        closes = sorted(v["close"] for v in ladders.values() if v["close"])
        results.append({
            "series": p, "kpi_quarters": len(ladders), "bracketed_quarters": brk,
            "avg_strikes": round(avg_strk, 1),
            "date_min": closes[0] if closes else "", "date_max": closes[-1] if closes else "",
            "sample_rule": (list(ladders.values())[0]["rule"] or "")[:90].replace("\n", " "),
        })
        if (i + 1) % 40 == 0:
            print(f"  ...{i+1}/{len(prefixes)}  found {len(results)}", file=sys.stderr)
        time.sleep(0.05)

    if not results:
        sys.exit(f"no KPI ladders found across {len(prefixes)} prefixes "
                 "(likely rate-limited mid-scan — rerun in a minute)")
    # merge legacy+KX duplicates (same base) — keep the richer
    results.sort(key=lambda r: (-r["kpi_quarters"], -r["bracketed_quarters"]))
    OUT.parent.mkdir(exist_ok=True)
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        w.writeheader(); w.writerows(results)

    print(f"\n{'series':22s} {'KPIq':>4s} {'brkt':>4s} {'strk':>5s} {'range':>23s}  rule")
    print("-" * 115)
    for r in results:
        flag = "  <<PANEL" if r["kpi_quarters"] >= 6 else ("  <usable" if r["kpi_quarters"] >= 4 else "")
        rng = f"{r['date_min']}..{r['date_max']}"
        print(f"{r['series']:22s} {r['kpi_quarters']:4d} {r['bracketed_quarters']:4d} "
              f"{r['avg_strikes']:5.1f} {rng:>23s}  {r['sample_rule'][:45]}{flag}")
    panel = [r["series"] for r in results if r["kpi_quarters"] >= 6]
    usable = [r["series"] for r in results if 4 <= r["kpi_quarters"] < 6]
    print(f"\nwrote {OUT}  ({len(results)} KPI series)")
    print(f"PANEL-GRADE (>=6q): {panel}")
    print(f"USABLE (4-5q):      {usable}")


if __name__ == "__main__":
    main()
