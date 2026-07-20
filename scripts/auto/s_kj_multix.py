#!/usr/bin/env python3
"""
s_kj_multix.py — EXP-5: MULTI-X regression.

Question (user): "put SEVERAL Kalshi markets into X" — instead of one company-KPI
market predicting revenue surprise, stack the company KPI *plus* the macro Kalshi
markets (CPI, NFP) live in that fiscal quarter, and see whether the multi-X model
beats the single-X (company-KPI-only) baseline.

Reality established by the scan: NO company has multiple quarter-resolved KPI ladders
(Apple=47 event-markets but 0 quarterly KPI; Meta/Spotify 2nd KPI is n=2). So the only
way to get a genuine multi-market X with usable n is:
    X1 = company Kalshi implied-KPI revision  (T-1 minus T-60, %),   from kalshi_X.csv
    X2 = macro CPI market revision at the release nearest before report_date
    X3 = macro NFP market revision at the release nearest before report_date
    Y  = revenue surprise  (from kalshi_panel.csv)

We compare, within each name and pooled (z-scored per name):
    single-X : Y ~ X1
    multi-X  : Y ~ X1 + X2 + X3
via OLS, reporting R^2, adjusted-R^2, and coefficient signs. The honest test is whether
the macro markets add explanatory power to the residual the company KPI leaves behind.

Inputs : outputs/kalshi_X.csv, outputs/kalshi_panel.csv, outputs/kalshi_macro_asset.csv
Output : outputs/kalshi_multix_panel.csv  + printed comparison table.
"""
import csv
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
XCSV = ROOT / "outputs" / "kalshi_X.csv"
PANEL = ROOT / "outputs" / "kalshi_panel.csv"
MACRO = ROOT / "outputs" / "kalshi_macro_asset.csv"
OUT = ROOT / "outputs" / "kalshi_multix_panel.csv"


def d(s):
    return datetime.fromisoformat(s[:10]).date()


# ---------- tiny stats (no numpy dependency, matches the rest of the repo) ----------
def mean(v):
    return sum(v) / len(v)


def zscore(v):
    if len(v) < 2:
        return [0.0] * len(v)
    m = mean(v)
    sd = (sum((x - m) ** 2 for x in v) / len(v)) ** 0.5
    return [(x - m) / sd if sd > 0 else 0.0 for x in v]


def ols(X, y):
    """Ordinary least squares with intercept. X = list of rows (each a feature list).
    Returns (betas incl. intercept, r2, adj_r2, n, k_features). Pure-python normal eqs."""
    n = len(y)
    k = len(X[0])  # number of features (excl intercept)
    # design matrix with leading 1
    A = [[1.0] + list(row) for row in X]
    p = k + 1
    # normal equations (A^T A) b = A^T y
    ATA = [[0.0] * p for _ in range(p)]
    ATy = [0.0] * p
    for i in range(n):
        for a in range(p):
            ATy[a] += A[i][a] * y[i]
            for b in range(p):
                ATA[a][b] += A[i][a] * A[i][b]
    # solve via Gauss-Jordan with partial pivoting
    M = [ATA[r][:] + [ATy[r]] for r in range(p)]
    for c in range(p):
        piv = max(range(c, p), key=lambda r: abs(M[r][c]))
        if abs(M[piv][c]) < 1e-12:
            return None  # singular
        M[c], M[piv] = M[piv], M[c]
        pv = M[c][c]
        M[c] = [x / pv for x in M[c]]
        for r in range(p):
            if r != c and abs(M[r][c]) > 0:
                f = M[r][c]
                M[r] = [M[r][j] - f * M[c][j] for j in range(p + 1)]
    beta = [M[r][p] for r in range(p)]
    yhat = [sum(beta[a] * A[i][a] for a in range(p)) for i in range(n)]
    ybar = mean(y)
    ss_res = sum((y[i] - yhat[i]) ** 2 for i in range(n))
    ss_tot = sum((yi - ybar) ** 2 for yi in y)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    adj = 1 - (1 - r2) * (n - 1) / (n - k - 1) if (n - k - 1) > 0 else float("nan")
    return beta, r2, adj, n, k


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = mean(xs), mean(ys)
    cov = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    sx = sum((a - mx) ** 2 for a in xs) ** 0.5
    sy = sum((b - my) ** 2 for b in ys) ** 0.5
    return cov / (sx * sy) if sx and sy else None


# ---------- load company KPI revision X1 ----------
def load_company_x():
    """(name,event) -> pct revision of implied KPI (T-1 vs T-60), plus report_date & Y."""
    im = defaultdict(dict)
    for r in csv.DictReader(open(XCSV)):
        if r["implied_mean"]:
            im[(r["name"], r["event"])][r["k"]] = float(r["implied_mean"])
    x1 = {}
    for key, dd in im.items():
        if "1" in dd and "60" in dd and dd["60"] != 0:
            x1[key] = (dd["1"] - dd["60"]) / abs(dd["60"])
        elif "1" in dd and "30" in dd and dd["30"] != 0:   # fallback shorter revision
            x1[key] = (dd["1"] - dd["30"]) / abs(dd["30"])
    return x1


def load_panel():
    """(name,event) -> {rev_surprise, report_date}."""
    out = {}
    for r in csv.DictReader(open(PANEL)):
        out[(r["name"], r["event"])] = {
            "y": float(r["rev_surprise"]),
            "report_date": r["report_date"][:10],
        }
    return out


def load_macro():
    """macro -> sorted list of (date, implied_late, revision)."""
    m = defaultdict(list)
    for r in csv.DictReader(open(MACRO)):
        rev = r.get("revision")
        late = r.get("implied_late")
        m[r["macro"]].append((
            r["release_date"][:10],
            float(late) if late not in (None, "") else None,
            float(rev) if rev not in (None, "") else None,
        ))
    for k in m:
        m[k].sort()
    return m


def nearest_before(macro_list, report_date, max_gap_days=95):
    """most recent macro release strictly before report_date, within one quarter."""
    rd = d(report_date)
    best = None
    for date_s, late, rev in macro_list:
        rel = d(date_s)
        if rel < rd:
            gap = (rd - rel).days
            if gap <= max_gap_days and (best is None or gap < best[0]):
                best = (gap, late, rev, date_s)
    return best  # (gap, late, rev, date) or None


def main():
    x1 = load_company_x()
    panel = load_panel()
    macro = load_macro()

    # build multi-X panel
    rows = []
    for key, pv in panel.items():
        name, event = key
        if key not in x1:
            continue
        rd = pv["report_date"]
        cpi = nearest_before(macro.get("CPI", []), rd)
        nfp = nearest_before(macro.get("NFP", []), rd)
        rows.append({
            "name": name, "event": event, "report_date": rd,
            "y_rev_surprise": pv["y"],
            "x1_kpi_revision": x1[key],
            "x2_cpi_revision": cpi[2] if cpi and cpi[2] is not None else "",
            "x2_cpi_date": cpi[3] if cpi else "",
            "x3_nfp_revision": nfp[2] if nfp and nfp[2] is not None else "",
            "x3_nfp_date": nfp[3] if nfp else "",
        })

    OUT.parent.mkdir(exist_ok=True)
    cols = ["name", "event", "report_date", "y_rev_surprise", "x1_kpi_revision",
            "x2_cpi_revision", "x2_cpi_date", "x3_nfp_revision", "x3_nfp_date"]
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)
    print(f"wrote {OUT}  rows={len(rows)}\n")

    # keep only rows with all three X present
    full = [r for r in rows if r["x2_cpi_revision"] != "" and r["x3_nfp_revision"] != ""]
    print(f"rows with X1+X2+X3 all present: {len(full)}\n")

    # ---- pooled within-name z-scored regression ----
    # z-score Y and each X *within name* to strip per-company scale, then stack.
    by_name = defaultdict(list)
    for r in full:
        by_name[r["name"]].append(r)

    Zy, Zx1, Zx2, Zx3 = [], [], [], []
    used_names = []
    for name, rs in by_name.items():
        if len(rs) < 3:
            continue  # need >=3 to z-score meaningfully
        used_names.append((name, len(rs)))
        Zy += zscore([r["y_rev_surprise"] for r in rs])
        Zx1 += zscore([r["x1_kpi_revision"] for r in rs])
        Zx2 += zscore([float(r["x2_cpi_revision"]) for r in rs])
        Zx3 += zscore([float(r["x3_nfp_revision"]) for r in rs])

    print("names used (n>=3, all-X):", used_names)
    N = len(Zy)
    print(f"pooled N = {N} quarter-obs\n")
    if N < 6:
        print("!! too few pooled observations for a meaningful multi-X regression.")
        print("   (company KPI markets simply don't co-exist with enough macro-matched")
        print("    quarters — this is the honest data-constraint result.)")
        # still report the simple correlations we can
        if N >= 3:
            print(f"\n  corr(X1 kpi_rev,  Y) = {pearson(Zx1, Zy)}")
            print(f"  corr(X2 cpi_rev,  Y) = {pearson(Zx2, Zy)}")
            print(f"  corr(X3 nfp_rev,  Y) = {pearson(Zx3, Zy)}")
        return

    print("=" * 70)
    print("SINGLE-X   Y ~ X1 (company KPI revision only)")
    print("=" * 70)
    s1 = ols([[a] for a in Zx1], Zy)
    if s1:
        beta, r2, adj, n, k = s1
        print(f"  beta_intercept={beta[0]:+.3f}  beta_X1={beta[1]:+.3f}")
        print(f"  R^2={r2:.3f}  adj_R^2={adj:.3f}  n={n}")

    print("\n" + "=" * 70)
    print("MULTI-X    Y ~ X1 + X2(CPI) + X3(NFP)")
    print("=" * 70)
    sm = ols([[a, b, c] for a, b, c in zip(Zx1, Zx2, Zx3)], Zy)
    if sm:
        beta, r2m, adjm, n, k = sm
        print(f"  beta_intercept={beta[0]:+.3f}  beta_X1(KPI)={beta[1]:+.3f}  "
              f"beta_X2(CPI)={beta[2]:+.3f}  beta_X3(NFP)={beta[3]:+.3f}")
        print(f"  R^2={r2m:.3f}  adj_R^2={adjm:.3f}  n={n}")

    if s1 and sm:
        print("\n" + "-" * 70)
        print(f"VERDICT: adj_R^2  single={s1[2]:.3f}  ->  multi={sm[2]:.3f}  "
              f"(Δ={sm[2]-s1[2]:+.3f})")
        if sm[2] > s1[2] + 0.02:
            print("  => macro markets ADD explanatory power to the residual.")
        elif sm[2] < s1[2] - 0.02:
            print("  => adding macro markets HURTS (overfit / noise). single-X better.")
        else:
            print("  => macro markets add ~nothing. multi-X ≈ single-X (honest null).")

    # ---- ROBUSTNESS ----
    print("\n" + "=" * 70)
    print("ROBUSTNESS")
    print("=" * 70)
    print("\n[1] univariate correlations (pooled, z-scored):")
    print(f"    X1 KPI_rev -> Y : r = {pearson(Zx1, Zy):+.3f}")
    print(f"    X2 CPI_rev -> Y : r = {pearson(Zx2, Zy):+.3f}")
    print(f"    X3 NFP_rev -> Y : r = {pearson(Zx3, Zy):+.3f}")

    print("\n[2] does the COMPANY KPI matter at all? macro-only vs full:")
    macro_only = ols([[b, c] for b, c in zip(Zx2, Zx3)], Zy)
    if macro_only:
        print(f"    macro-only  Y ~ X2+X3     : adj_R^2={macro_only[2]:+.3f}")
    print(f"    full        Y ~ X1+X2+X3  : adj_R^2={sm[2]:+.3f}")
    print("    (if macro-only ≈ full, the company KPI adds nothing — it's purely a macro effect)")

    print("\n[3] drop NFP (the big/suspicious coef): Y ~ X1 + CPI")
    x1cpi = ols([[a, b] for a, b in zip(Zx1, Zx2)], Zy)
    if x1cpi:
        print(f"    Y ~ X1+CPI  : adj_R^2={x1cpi[2]:+.3f}  betas KPI={x1cpi[0][1]:+.3f} CPI={x1cpi[0][2]:+.3f}")

    print("\n[4] per-name sign of NFP->Y (is -0.362 driven by one name?):")
    for name, rs in by_name.items():
        if len(rs) < 3:
            continue
        r = pearson([float(x["x3_nfp_revision"]) for x in rs],
                    [x["y_rev_surprise"] for x in rs])
        print(f"    {name:10s} n={len(rs)}  corr(NFP_rev, Y) = "
              f"{'  None' if r is None else f'{r:+.3f}'}")

    print("\n[5] leave-one-name-out on multi-X adj_R^2 (stability):")
    allrows = []
    for name, rs in by_name.items():
        if len(rs) >= 3:
            allrows.append((name, rs))
    for drop, _ in allrows:
        zy, zx1, zx2, zx3 = [], [], [], []
        for name, rs in allrows:
            if name == drop:
                continue
            zy += zscore([r["y_rev_surprise"] for r in rs])
            zx1 += zscore([r["x1_kpi_revision"] for r in rs])
            zx2 += zscore([float(r["x2_cpi_revision"]) for r in rs])
            zx3 += zscore([float(r["x3_nfp_revision"]) for r in rs])
        m = ols([[a, b, c] for a, b, c in zip(zx1, zx2, zx3)], zy)
        if m:
            print(f"    drop {drop:10s} -> multi adj_R^2={m[2]:+.3f} (n={m[3]})")


if __name__ == "__main__":
    main()
