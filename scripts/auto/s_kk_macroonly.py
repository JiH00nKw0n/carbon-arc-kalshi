#!/usr/bin/env python3
"""
s_kk_macroonly.py — EXP-6: MACRO-ONLY multi-X (drop company KPI entirely).

EXP-5 showed the company KPI is dead weight; the only live signal was NFP. So here
we ask the cleaner question the user posed: use ONLY several macro Kalshi markets as X
(CPI + NFP + PCE), predict each company's revenue surprise (Y), and — the key ask —
check whether the sign is CONSISTENT across quarters and across names, not a subset
artifact.

X = macro-market revision (implied_late - implied_early) at the release nearest before
    each company's report_date:
      X_CPI, X_NFP, X_PCE
Y = revenue surprise (kalshi_panel.csv)

Reports:
  (A) pooled within-name z-scored OLS  Y ~ CPI + NFP + PCE
  (B) per-macro univariate pooled correlation
  (C) CONSISTENCY: split the quarters into two halves by report_date (early vs late)
      and re-estimate — does the sign hold out of the estimation window?
  (D) per-name sign table for each macro (how many names share the pooled sign)
  (E) per-quarter scatter dump so we can eyeball stability

Inputs : outputs/kalshi_panel.csv, outputs/kalshi_macro_asset.csv
Output : outputs/kalshi_macroonly_panel.csv
"""
import csv
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PANEL = ROOT / "outputs" / "kalshi_panel.csv"
MACRO = ROOT / "outputs" / "kalshi_macro_asset.csv"
OUT = ROOT / "outputs" / "kalshi_macroonly_panel.csv"

MACROS = ["CPI", "NFP", "PCE"]


def d(s):
    return datetime.fromisoformat(s[:10]).date()


def mean(v):
    return sum(v) / len(v)


def zscore(v):
    if len(v) < 2:
        return [0.0] * len(v)
    m = mean(v)
    sd = (sum((x - m) ** 2 for x in v) / len(v)) ** 0.5
    return [(x - m) / sd if sd > 0 else 0.0 for x in v]


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = mean(xs), mean(ys)
    cov = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    sx = sum((a - mx) ** 2 for a in xs) ** 0.5
    sy = sum((b - my) ** 2 for b in ys) ** 0.5
    return cov / (sx * sy) if sx and sy else None


def ols(X, y):
    n = len(y)
    k = len(X[0])
    A = [[1.0] + list(r) for r in X]
    p = k + 1
    ATA = [[0.0] * p for _ in range(p)]
    ATy = [0.0] * p
    for i in range(n):
        for a in range(p):
            ATy[a] += A[i][a] * y[i]
            for b in range(p):
                ATA[a][b] += A[i][a] * A[i][b]
    M = [ATA[r][:] + [ATy[r]] for r in range(p)]
    for c in range(p):
        piv = max(range(c, p), key=lambda r: abs(M[r][c]))
        if abs(M[piv][c]) < 1e-12:
            return None
        M[c], M[piv] = M[piv], M[c]
        pv = M[c][c]
        M[c] = [x / pv for x in M[c]]
        for r in range(p):
            if r != c and M[r][c]:
                f = M[r][c]
                M[r] = [M[r][j] - f * M[c][j] for j in range(p + 1)]
    beta = [M[r][p] for r in range(p)]
    yhat = [sum(beta[a] * A[i][a] for a in range(p)) for i in range(n)]
    ybar = mean(y)
    ss_res = sum((y[i] - yhat[i]) ** 2 for i in range(n))
    ss_tot = sum((yi - ybar) ** 2 for yi in y)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    adj = 1 - (1 - r2) * (n - 1) / (n - k - 1) if (n - k - 1) > 0 else float("nan")
    return beta, r2, adj, n


def load_macro():
    m = defaultdict(list)
    for r in csv.DictReader(open(MACRO)):
        rev = r.get("revision")
        m[r["macro"]].append((r["release_date"][:10],
                              float(rev) if rev not in (None, "") else None))
    for k in m:
        m[k].sort()
    return m


def nearest_before(lst, report_date, max_gap=95):
    rd = d(report_date)
    best = None
    for date_s, rev in lst:
        if rev is None:
            continue
        rel = d(date_s)
        if rel < rd:
            gap = (rd - rel).days
            if gap <= max_gap and (best is None or gap < best[0]):
                best = (gap, rev, date_s)
    return best


def main():
    macro = load_macro()
    # panel has 4 rows per quarter (k=1/7/30/60 X-snapshots) but macro X depends only
    # on report_date, so those 4 collapse to the SAME (X,Y). Dedup to one row per
    # (name,event) — otherwise n is 4x inflated and correlations are spuriously strong.
    seen, panel = set(), []
    for r in csv.DictReader(open(PANEL)):
        key = (r["name"], r["event"])
        if key in seen:
            continue
        seen.add(key)
        panel.append((r["name"], r["event"], r["report_date"][:10], float(r["rev_surprise"])))

    rows = []
    for name, event, rd, y in panel:
        rec = {"name": name, "event": event, "report_date": rd, "y_rev_surprise": y}
        ok = True
        for mac in MACROS:
            nb = nearest_before(macro.get(mac, []), rd)
            rec[f"x_{mac}"] = nb[1] if nb else ""
            rec[f"x_{mac}_date"] = nb[2] if nb else ""
            if nb is None:
                ok = False
        rec["_full"] = ok
        rows.append(rec)

    OUT.parent.mkdir(exist_ok=True)
    cols = ["name", "event", "report_date", "y_rev_surprise"] + \
           [f"x_{m}" for m in MACROS] + [f"x_{m}_date" for m in MACROS]
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader(); w.writerows(rows)

    full = [r for r in rows if r["_full"]]
    print(f"wrote {OUT}  rows={len(rows)}  full(all 3 macros)={len(full)}\n")

    by_name = defaultdict(list)
    for r in full:
        by_name[r["name"]].append(r)
    used = [(n, len(v)) for n, v in by_name.items() if len(v) >= 3]
    print("names (n>=3):", used)

    # build pooled within-name z-scored arrays
    def pooled(rows_by_name, names=None):
        Z = {"y": [], "CPI": [], "NFP": [], "PCE": []}
        for name, rs in rows_by_name.items():
            if len(rs) < 3:
                continue
            if names and name not in names:
                continue
            Z["y"] += zscore([r["y_rev_surprise"] for r in rs])
            for m in MACROS:
                Z[m] += zscore([float(r[f"x_{m}"]) for r in rs])
        return Z

    Z = pooled(by_name)
    N = len(Z["y"])
    print(f"pooled N = {N}\n")

    print("=" * 68)
    print("(A) MACRO-ONLY multi-X:  Y ~ CPI + NFP + PCE  (pooled, z-scored)")
    print("=" * 68)
    res = ols([[Z["CPI"][i], Z["NFP"][i], Z["PCE"][i]] for i in range(N)], Z["y"])
    if res:
        b, r2, adj, n = res
        print(f"  intercept={b[0]:+.3f}  CPI={b[1]:+.3f}  NFP={b[2]:+.3f}  PCE={b[3]:+.3f}")
        print(f"  R^2={r2:.3f}  adj_R^2={adj:.3f}  n={n}")

    print("\n(B) per-macro univariate pooled correlation:")
    for m in MACROS:
        print(f"    {m}_rev -> Y : r = {pearson(Z[m], Z['y']):+.3f}")

    print("\n" + "=" * 68)
    print("(C) CONSISTENCY across quarters — split each name's obs by report_date")
    print("    into EARLY half vs LATE half, re-estimate univariate r per macro.")
    print("=" * 68)
    early_by, late_by = defaultdict(list), defaultdict(list)
    for name, rs in by_name.items():
        if len(rs) < 4:  # need >=4 to split and still z-score each half (>=2)
            continue
        srt = sorted(rs, key=lambda r: r["report_date"])
        h = len(srt) // 2
        early_by[name] = srt[:h]
        late_by[name] = srt[h:]
    for m in MACROS:
        Ze = pooled(early_by); Zl = pooled(late_by)
        # relax z-score min: pooled() already skips <3; halves may be small, so pool raw z
        re = pearson(Ze[m], Ze["y"]) if len(Ze["y"]) >= 3 else None
        rl = pearson(Zl[m], Zl["y"]) if len(Zl["y"]) >= 3 else None
        def fmt(x): return "  n/a" if x is None else f"{x:+.3f}"
        agree = ""
        if re is not None and rl is not None:
            agree = " ✓same-sign" if (re > 0) == (rl > 0) else " ✗FLIP"
        print(f"    {m}: early r={fmt(re)} (n={len(Ze['y'])})   "
              f"late r={fmt(rl)} (n={len(Zl['y'])}){agree}")

    print("\n" + "=" * 68)
    print("(D) per-NAME sign of each macro->Y  (consistency across companies)")
    print("=" * 68)
    hdr = "    " + f"{'name':10s}" + "".join(f"{m:>9s}" for m in MACROS) + f"{'n':>5s}"
    print(hdr)
    sign_count = {m: {"+": 0, "-": 0} for m in MACROS}
    for name, rs in sorted(by_name.items()):
        if len(rs) < 3:
            continue
        line = f"    {name:10s}"
        for m in MACROS:
            r = pearson([float(x[f"x_{m}"]) for x in rs], [x["y_rev_surprise"] for x in rs])
            if r is not None:
                sign_count[m]["+" if r > 0 else "-"] += 1
            line += f"{('  n/a' if r is None else f'{r:+.3f}'):>9s}"
        line += f"{len(rs):>5d}"
        print(line)
    print("\n    sign tally across names:")
    for m in MACROS:
        pos, neg = sign_count[m]["+"], sign_count[m]["-"]
        tot = pos + neg
        dom = "+" if pos > neg else "-"
        print(f"      {m}: {pos} pos / {neg} neg  -> dominant {dom} "
              f"({max(pos,neg)}/{tot} = {max(pos,neg)/tot:.0%} agree)")


if __name__ == "__main__":
    main()
