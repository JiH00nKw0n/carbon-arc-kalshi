#!/usr/bin/env python3
"""
s_kc_align_Y.py — Y builder + X↔KPI↔Y alignment + pre-LLM gate.

Y = revenue surprise vs POINT-IN-TIME consensus, from FactSet FE_V4 via the
running linq-local MCP server (http://localhost:3035/mcp, factset_query).
  surprise = (ACTUAL_VALUE - pre_report_consensus_mean) / consensus   (factor3 def)
  pre_report = latest FE_BASIC_CONH_QF snapshot with CONS_END_DATE < REPORT_DATE.

Align to X (outputs/kalshi_X.csv) by matching Kalshi close_date to the fiscal
quarter's REPORT_DATE (nearest within tolerance). Then the two gates:
  GATE 1 (already passed in X builder): implied KPI mean vs realized KPI.
  GATE 2 (here): implied KPI (X) -> revenue surprise (Y), within Tesla.

Output: outputs/kalshi_panel.csv  (X joined to Y, one row per name-quarter-snapshot)
        prints gate correlations.
"""
import csv
import json
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
X_CSV = ROOT / "outputs" / "kalshi_X.csv"
OUT = ROOT / "outputs" / "kalshi_panel.csv"
MCP = "http://localhost:3035/mcp"

# FactSet -R regional ids (resolved via SYM_V1.SYM_TICKER_REGION). None -> resolved at runtime.
FSYM = {"Tesla": "Q2YN1N-R", "MetaDAP": "QLGSL2-R", "Netflix": "C4C0BL-R",
        "NYT": "BW92P1-R", "Robinhood": "CSC7N1-R", "Spotify": "X5HN6G-R", "SoFi": "HGZX4Y-R",
        "Uber": "TR0FX7-R", "DoorDash": "CKHCJ4-R", "Boeing": "RXHN9P-R", "Southwest": "BFSY5M-R",
        "SpotifyMAU": "X5HN6G-R"}
TICKER_REGION = {"Tesla": "TSLA-US", "MetaDAP": "META-US", "Netflix": "NFLX-US",
                 "NYT": "NYT-US", "Robinhood": "HOOD-US", "Spotify": "SPOT-US", "SoFi": "SOFI-US",
                 "Uber": "UBER-US", "DoorDash": "DASH-US", "Boeing": "BA-US", "Southwest": "LUV-US",
                 "SpotifyMAU": "SPOT-US"}


def mcp_call(tool, args):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": tool, "arguments": args}}).encode()
    req = urllib.request.Request(MCP, data=body, headers={
        "content-type": "application/json",
        "accept": "application/json, text/event-stream"})
    raw = urllib.request.urlopen(req, timeout=60).read().decode()
    if "data:" in raw and not raw.strip().startswith("{"):
        for line in raw.splitlines():
            if line.startswith("data:"):
                raw = line[5:].strip(); break
    d = json.loads(raw)
    txt = "\n".join(c.get("text", "") for c in d.get("result", {}).get("content", []))
    return json.loads(txt) if txt else d.get("result")


def resolve_rid(ticker_region):
    r = mcp_call("factset_query", {"sql":
        f"SELECT FSYM_ID FROM SYM_V1.SYM_TICKER_REGION WHERE TICKER_REGION = '{ticker_region}'",
        "max_rows": 5})
    rows = r.get("rows", []) if isinstance(r, dict) else []
    return rows[0]["FSYM_ID"] if rows else None


def fetch_surprise(rid):
    """point-in-time revenue surprise per quarter."""
    sql = f"""
    WITH actuals AS (
      SELECT FE_FP_END, ACTUAL_VALUE AS actual_sales, REPORT_DATE
      FROM FACTSET_LISTING.FE_V4.FE_BASIC_ACT_QF
      WHERE FSYM_ID = '{rid}' AND FE_ITEM = 'SALES' AND FE_FP_END >= '2023-06-01'
    ),
    pit AS (
      SELECT a.FE_FP_END, c.FE_MEAN AS cons_sales, c.CONS_END_DATE, c.FE_NUM_EST,
             ROW_NUMBER() OVER (PARTITION BY a.FE_FP_END ORDER BY c.CONS_END_DATE DESC) AS rn
      FROM actuals a
      JOIN FACTSET_LISTING.FE_V4.FE_BASIC_CONH_QF c
        ON c.FSYM_ID = '{rid}' AND c.FE_ITEM = 'SALES'
        AND c.FE_FP_END = a.FE_FP_END AND c.CONS_END_DATE < a.REPORT_DATE
    )
    SELECT a.FE_FP_END, a.REPORT_DATE, a.actual_sales, p.cons_sales, p.FE_NUM_EST,
           (a.actual_sales - p.cons_sales)/NULLIF(p.cons_sales,0) AS surprise
    FROM actuals a LEFT JOIN pit p ON a.FE_FP_END=p.FE_FP_END AND p.rn=1
    ORDER BY a.FE_FP_END
    """
    r = mcp_call("factset_query", {"sql": sql, "max_rows": 40})
    out = []
    for row in (r.get("rows", []) if isinstance(r, dict) else []):
        # Snowflake returns UPPERCASE column keys
        if row.get("ACTUAL_SALES") in (None, "NULL") or row.get("SURPRISE") in (None, "NULL"):
            continue
        out.append({
            "report_date": row["REPORT_DATE"],
            "fp_end": row["FE_FP_END"],
            "actual_sales": float(row["ACTUAL_SALES"]),
            "cons_sales": float(row["CONS_SALES"]),
            "n_est": row.get("FE_NUM_EST"),
            "surprise": float(row["SURPRISE"]),
        })
    return out


def d(s):
    return datetime.fromisoformat(s[:10])


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None, n
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    sx = sum((a - mx) ** 2 for a in xs) ** 0.5
    sy = sum((b - my) ** 2 for b in ys) ** 0.5
    if sx == 0 or sy == 0:
        return None, n
    return cov / (sx * sy), n


def spearman(xs, ys):
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0] * len(v)
        for i, idx in enumerate(order):
            r[idx] = i
        return r
    return pearson(rank(xs), rank(ys))


def main():
    # resolve any missing rids at runtime
    for name in list(FSYM):
        if not FSYM[name]:
            FSYM[name] = resolve_rid(TICKER_REGION[name])
            print(f"{name} -R = {FSYM[name]}", file=sys.stderr)

    # fetch Y per name
    Y = {}
    for name, rid in FSYM.items():
        if not rid:
            print(f"  {name}: no rid, skip", file=sys.stderr); continue
        Y[name] = fetch_surprise(rid)
        print(f"  {name}: {len(Y[name])} quarters of revenue surprise", file=sys.stderr)

    # load X
    Xrows = list(csv.DictReader(open(X_CSV)))

    # align: for each X row (name, close_date, k), find the Y quarter whose report_date
    # is nearest to close_date (Kalshi settles ~ KPI release, close to earnings report).
    panel = []
    for xr in Xrows:
        name = xr["name"]
        if name not in Y or not xr["implied_mean"]:
            continue
        cd = d(xr["close_date"])
        best, bestgap = None, 9999
        for yq in Y[name]:
            gap = abs((d(yq["report_date"]) - cd).days)
            if gap < bestgap:
                best, bestgap = yq, gap
        if best is None or bestgap > 45:   # must be same quarter
            continue
        panel.append({
            "name": name, "event": xr["event"], "close_date": xr["close_date"],
            "k": xr["k"], "n_strikes": xr["n_strikes"], "bracketed": xr["bracketed"],
            "note": xr["note"],
            "implied_mean": float(xr["implied_mean"]),
            "implied_sd": float(xr["implied_sd"]) if xr["implied_sd"] else "",
            "realized_kpi": float(xr["realized_kpi"]) if xr["realized_kpi"] else "",
            "report_date": best["report_date"], "fp_end": best["fp_end"],
            "actual_sales": best["actual_sales"], "cons_sales": best["cons_sales"],
            "rev_surprise": best["surprise"], "match_gap_days": bestgap,
        })

    OUT.parent.mkdir(exist_ok=True)
    cols = ["name", "event", "close_date", "k", "n_strikes", "bracketed", "note",
            "implied_mean", "implied_sd", "realized_kpi", "report_date", "fp_end",
            "actual_sales", "cons_sales", "rev_surprise", "match_gap_days"]
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(panel)
    print(f"\nwrote {OUT}  rows={len(panel)}")

    # ---- GATES ----
    print("\n=== GATE 2: does Kalshi implied KPI (X) predict revenue surprise (Y)? ===")
    for name in FSYM:
        for k in ("1", "7"):
            sub = [r for r in panel if r["name"] == name and r["k"] == k and r["note"] == "ok"]
            if len(sub) < 3:
                continue
            # X signal = implied KPI relative to realized? No — pre-report we only have implied.
            # Use implied_mean as level, and also a KPI-surprise proxy = implied vs its own
            # trailing mean is overkill for n=8; report implied_mean -> rev_surprise directly,
            # plus realized_kpi -> rev_surprise as the "does KPI drive revenue" sanity.
            im = [r["implied_mean"] for r in sub]
            rs = [r["rev_surprise"] for r in sub]
            r_p, n = pearson(im, rs); r_s, _ = spearman(im, rs)
            print(f"  {name:8s} k={k}: implied_KPI -> rev_surprise  "
                  f"Pearson={r_p if r_p is None else round(r_p,3)} Spearman={r_s if r_s is None else round(r_s,3)} (n={n})")
    # KPI->revenue sanity (realized KPI vs revenue surprise), Tesla only (has realized)
    print("\n=== SANITY: realized KPI -> revenue surprise (does volume drive the top line?) ===")
    for name in FSYM:
        sub = [r for r in panel if r["name"] == name and r["k"] == "1"
               and r["realized_kpi"] != "" and r["note"] == "ok"]
        # dedup by quarter
        seen, u = set(), []
        for r in sub:
            if r["event"] in seen: continue
            seen.add(r["event"]); u.append(r)
        if len(u) < 3:
            continue
        rk = [r["realized_kpi"] for r in u]; rs = [r["rev_surprise"] for r in u]
        r_p, n = pearson(rk, rs)
        print(f"  {name:8s}: realized_KPI -> rev_surprise Pearson={r_p if r_p is None else round(r_p,3)} (n={n})")


if __name__ == "__main__":
    main()
