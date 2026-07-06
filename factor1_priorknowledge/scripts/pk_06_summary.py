"""
전체 L0~L2c 종합 — 모든 레벨의 company-fit + 도구패턴을 하나의 표로.

레벨:
  L0  baseline           티커+채널설명만
  L1w oracle(WebSearch)   연구자가 채널믹스/디지털비중 주입
  L1f oracle(FactSet)     연구자가 매출·마진·변동성 주입
  L2  agent(자율)         LLM이 tool로 자유 수집 (다 부름)
  L2b agent(선택강제)     비용 프레이밍 → 선택적 수집
  L2c screen(풀좁히기)    전체→top-N 스크리닝 후 그 안에서

OUT: outputs/summary_all.csv  (channel, level, auc, topk, spearman)  + summary_all.md

Usage:  python pk_06_summary.py  (전제: pk_01/03/04/05 실행 완료)
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pk_config import OUT  # noqa: E402


def get(df, ch, cond, met):
    if df is None or df.empty:
        return None
    r = df[(df.channel == ch) & (df.cond == cond)]
    if not len(r) or met not in r:
        return None
    v = r[met].iloc[0]
    return None if pd.isna(v) else float(v)


def load(name):
    p = OUT / name
    return pd.read_csv(p) if p.exists() else None


def main():
    v1 = load("pk_compare.csv")            # baseline, enriched(web)
    v2 = load("pk_v2_compare.csv")         # baseline, enriched_v2(factset)
    ag = load("pk_agent_compare.csv")      # agent_L2
    va = load("l2_variants_compare.csv")   # L2b_forced, L2c_screen

    LEVELS = [
        ("L0 baseline",        v1, "baseline"),
        ("L1 oracle-WebSearch", v1, "enriched"),
        ("L1 oracle-FactSet",  v2, "enriched_v2"),
        ("L2 agent-free",      ag, "agent_L2"),
        ("L2b agent-forced",   va, "L2b_forced"),
        ("L2c screen-topN",    va, "L2c_screen"),
    ]

    rows = []
    for ch in ["card", "foot", "web"]:
        for lbl, df, cond in LEVELS:
            rows.append({"channel": ch, "level": lbl,
                         "auc": get(df, ch, cond, "auc"),
                         "topk": get(df, ch, cond, "topk_precision"),
                         "spearman": get(df, ch, cond, "rank_spearman")})
    S = pd.DataFrame(rows)
    S.to_csv(OUT / "summary_all.csv", index=False)

    # markdown table per channel (AUC / topk)
    md = ["# 사전지식 실험 — 전체 레벨 종합 (company-fit)\n",
          "L0=정보없음, L1=연구자가 정보 선택(oracle 상한선), L2=LLM 자율, L2b=선택강제, L2c=풀좁히기.\n"]
    for ch in ["card", "foot"]:
        md.append(f"## {ch}\n")
        md.append("| level | AUC | top-k |")
        md.append("|---|---|---|")
        for lbl, df, cond in LEVELS:
            a = get(df, ch, cond, "auc"); t = get(df, ch, cond, "topk_precision")
            af = f"{a:+.3f}" if a is not None else "—"
            tf = f"{t:+.3f}" if t is not None else "—"
            md.append(f"| {lbl} | {af} | {tf} |")
        md.append("")
    (OUT / "summary_all.md").write_text("\n".join(md))
    print("\n".join(md))
    print(f"\nsaved: summary_all.csv, summary_all.md")


if __name__ == "__main__":
    main()
