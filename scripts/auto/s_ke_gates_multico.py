#!/usr/bin/env python3
"""
s_ke_gates_multico.py — the two gates, across ALL companies, using revision-X.

GATE 1: Kalshi implied KPI mean (T-1) vs realized KPI          [X sanity]
GATE 2: revision-X (implied KPI late - early) -> revenue surprise  [the experiment]

revision-X uses early implied (T-30 or T-60) as the market's PRIOR expectation and
late implied (T-1/T-7) as post-channel-info expectation. factor3 residual logic:
the surprise-vs-prior predicts the revenue surprise, the absolute level does not.

Reads outputs/kalshi_X.csv (has T-1/7/30/60 implied_mean per quarter) and
outputs/kalshi_panel.csv (revenue surprise Y). Prints a per-company table +
pooled within-name correlation.
"""
import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
X = ROOT / "outputs" / "kalshi_X.csv"
PANEL = ROOT / "outputs" / "kalshi_panel.csv"


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
    def rk(v):
        o = sorted(range(len(v)), key=lambda i: v[i]); r = [0] * len(v)
        for i, idx in enumerate(o):
            r[idx] = i
        return r
    return pearson(rk(xs), rk(ys))


def zscore(vals):
    n = len(vals)
    m = sum(vals) / n
    sd = (sum((v - m) ** 2 for v in vals) / n) ** 0.5
    return [(v - m) / sd if sd > 0 else 0.0 for v in vals]


def main():
    # implied_mean per (name,event,k)
    im = defaultdict(dict)
    realized = {}
    for r in csv.DictReader(open(X)):
        if r["implied_mean"]:
            im[(r["name"], r["event"])][r["k"]] = float(r["implied_mean"])
        if r["realized_kpi"]:
            realized[(r["name"], r["event"])] = float(r["realized_kpi"])
    # revenue surprise Y per (name,event)
    Y = {}
    for r in csv.DictReader(open(PANEL)):
        Y[(r["name"], r["event"])] = float(r["rev_surprise"])

    names = sorted({k[0] for k in im})

    print("=" * 78)
    print("GATE 1 — Kalshi implied KPI (T-1) vs realized KPI")
    print("=" * 78)
    for name in names:
        xs, ys = [], []
        for key in im:
            if key[0] != name or key not in realized:
                continue
            if "1" in im[key]:
                xs.append(im[key]["1"]); ys.append(realized[key])
        r, n = pearson(xs, ys)
        if n >= 3:
            print(f"  {name:10s} implied->realized  Pearson={r if r is None else round(r,3):>6} (n={n})")
        else:
            print(f"  {name:10s} (n={n}, need realized KPI — Meta/subs report 'Yes' not a number)")

    print("\n" + "=" * 78)
    print("GATE 2 — revision-X (late implied - early implied) -> revenue surprise")
    print("=" * 78)
    # revision definitions to test
    defs = [("T1-T60", "1", "60"), ("T1-T30", "1", "30"), ("T7-T30", "7", "30"),
            ("T1 level", "1", None)]
    per_name_best = {}
    for name in names:
        print(f"\n  {name}")
        for label, late, early in defs:
            xs, ys = [], []
            for key in im:
                if key[0] != name or key not in Y:
                    continue
                d = im[key]
                if late not in d:
                    continue
                if early is None:
                    xv = d[late]
                else:
                    if early not in d or d[early] == 0:
                        continue
                    xv = (d[late] - d[early]) / abs(d[early])  # % revision
                xs.append(xv); ys.append(Y[key])
            r, n = pearson(xs, ys); rs, _ = spearman(xs, ys)
            flag = ""
            if r is not None and label != "T1 level":
                if name not in per_name_best or abs(r) > abs(per_name_best[name][1]):
                    per_name_best[name] = (label, r, n)
            rp = "  None" if r is None else f"{round(r,3):>6}"
            rsp = "  None" if rs is None else f"{round(rs,3):>6}"
            print(f"    {label:9s}: Pearson={rp}  Spearman={rsp}  (n={n})")

    print("\n" + "=" * 78)
    print("POOLED within-name — revision-X (best per name is T1-T60), z-scored per company")
    print("=" * 78)
    # pool T1-T60 %revision across names, z-scoring X and Y within each name to remove
    # scale differences, then one correlation across the stacked panel.
    pooled_x, pooled_y = [], []
    for name in names:
        xs, ys = [], []
        for key in im:
            if key[0] != name or key not in Y:
                continue
            d = im[key]
            if "1" in d and "60" in d and d["60"] != 0:
                xs.append((d["1"] - d["60"]) / abs(d["60"])); ys.append(Y[key])
        if len(xs) >= 3:
            pooled_x += zscore(xs); pooled_y += zscore(ys)
    r, n = pearson(pooled_x, pooled_y); rs, _ = spearman(pooled_x, pooled_y)
    print(f"  pooled T1-T60 %revision -> rev_surprise: Pearson={round(r,3) if r else None} "
          f"Spearman={round(rs,3) if rs else None} (n={n} quarter-obs across {len(names)} names)")

    print("\n  Per-company best revision correlation:")
    for name in names:
        if name in per_name_best:
            lbl, r, n = per_name_best[name]
            print(f"    {name:10s} {lbl:8s} r={round(r,3):>6} (n={n})")


if __name__ == "__main__":
    main()
