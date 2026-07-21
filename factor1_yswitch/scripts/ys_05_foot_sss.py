"""
foot traffic × SSS surprise — foot 채널의 "정답 Y" 검정.

sss_surprise = SSS_ACTUAL(%) − SSS_CONS(%)   (둘 다 % comps → 단순 차이)
foot x_yoy 를 no-lookahead(x_date<REPORT_DATE)로 SSS 이벤트에 정렬 후 검정.

OUT: outputs/foot_sss.md  +  outputs/panel_foot_sss.csv

Usage:  python ys_05_foot_sss.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "factor1" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from f1_stats import cluster_boot, surrogate, within_company_corr  # noqa: E402
from ys_config import DATA, FOOT_CSVS, OUT  # noqa: E402
import ys_lib as L  # noqa: E402

SCREEN = Path(__file__).resolve().parents[2] / "factor1" / "data" / "altdata_ticker_screen.csv"
md = []


def log(s=""):
    print(s); md.append(s)


def test(d, x, y, tag):
    r, pb, n = cluster_boot(d, x, y)
    ps = surrogate(d, x, y, r) if not np.isnan(r) else np.nan
    rho, _, _ = L.spearman_panel(d, x, y)
    hr, _ = L.hit_rate(d, x, y)
    ic = L.rank_ic(d, x, y)
    v = "PASS" if (not np.isnan(ps) and ps < 0.05 and pb < 0.05) else ("n/a" if np.isnan(ps) else "fail")
    log(f"  {tag:40s} r={r:+.3f} n={n:>3} p_surr={ps:.3f} | rho={rho:+.3f} hit={hr:.2f} "
        f"IC={ic['mean_ic']:+.3f} IR={ic['ic_ir']:+.3f} nQ={ic['n_quarters']:>2} [{v}]")


def main():
    sss = pd.DataFrame(json.load(open(DATA / "factset_sss_pit.json"))["rows"])
    for c in ("SSS_ACTUAL", "SSS_CONS"):
        sss[c] = pd.to_numeric(sss[c], errors="coerce")
    sss["FE_FP_END"]   = pd.to_datetime(sss["FE_FP_END"])
    sss["REPORT_DATE"] = pd.to_datetime(sss["REPORT_DATE"])
    sss = sss.dropna(subset=["SSS_ACTUAL", "SSS_CONS"])
    sss["sss_surprise"] = sss["SSS_ACTUAL"] - sss["SSS_CONS"]   # both in %

    x = L.build_foot(FOOT_CSVS).sort_values(["ticker", "date"])

    # align x_yoy → each SSS event, no-lookahead
    rows = []
    for t in sorted(set(x.ticker) & set(sss.ticker)):
        e = sss[sss.ticker == t].sort_values("FE_FP_END")
        a = x[x.ticker == t].dropna(subset=["x_yoy"]).sort_values("date")
        if a.empty:
            continue
        m = pd.merge_asof(e, a[["date", "x_yoy"]].rename(columns={"date": "x_date"}),
                          left_on="FE_FP_END", right_on="x_date",
                          direction="nearest", tolerance=pd.Timedelta(days=45))
        rows.append(m)
    p = pd.concat(rows, ignore_index=True).dropna(subset=["x_yoy"])
    p = p[p["x_date"] < p["REPORT_DATE"]]   # no-lookahead

    strength = (pd.read_csv(SCREEN).query("data_type=='foot_traffic'")
                .set_index("ticker")["strength"].to_dict())
    p["strength"] = p["ticker"].map(strength).fillna("?")
    p.to_csv(OUT / "panel_foot_sss.csv", index=False)

    log("# foot traffic × SSS surprise\n")
    log(f"panel: {len(p)} events · {p.ticker.nunique()} tickers · "
        f"{p.FE_FP_END.min().date()}..{p.FE_FP_END.max().date()}")
    log(f"sss_surprise: mean={p.sss_surprise.mean():+.2f}pp sd={p.sss_surprise.std():.2f}pp\n")

    log("## foot → SSS surprise  (vs. 총매출 surprise 실패했던 것과 비교)")
    test(p, "x_yoy", "sss_surprise", "ALL foot → sss_surprise")
    wc = within_company_corr(p, "x_yoy", "sss_surprise")
    log(f"  within-company corr = {wc:+.3f}")

    log("\n## 인스토어 subset → SSS surprise")
    for s in ["strong", "moderate"]:
        sub = p[p.strength == s]
        if sub.ticker.nunique() >= 4 and len(sub) >= 10:
            test(sub, "x_yoy", "sss_surprise", f"[{s}] foot → sss_surprise ({sub.ticker.nunique()}tkr)")

    log("\n## 참고: SSS actual 자체(레벨)와의 상관")
    test(p, "x_yoy", "SSS_ACTUAL", "ALL foot → SSS_ACTUAL(level)")

    (OUT / "foot_sss.md").write_text("\n".join(md))
    print(f"\nsaved: {OUT/'foot_sss.md'}  +  {OUT/'panel_foot_sss.csv'}")


if __name__ == "__main__":
    main()
