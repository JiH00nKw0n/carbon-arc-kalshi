"""Stage Final — Build docs/verification_pairs_macro.md from Stage A·B·C outputs.

Inputs (read-only):
  outputs/auto/macro_event_master_list.csv  (Stage A1)
  outputs/auto/macro_kalshi.csv              (Stage A2)
  outputs/auto/timing_pass.csv               (Stage B)
  outputs/auto/timing_full.csv               (Stage B)
  outputs/auto/mechanism_verified.csv        (Stage C)
  outputs/auto/verification_pairs_macro.csv  (Stage C, connected=true subset)

Output:
  docs/verification_pairs_macro.md
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT_DOCS = ROOT / "docs"
OUT_AUTO = ROOT / "outputs" / "auto"


def load_csv(name: str) -> pd.DataFrame | None:
    p = OUT_AUTO / name
    if not p.exists():
        return None
    return pd.read_csv(p)


def funnel_table() -> str:
    master = load_csv("macro_event_master_list.csv")
    macro_kalshi = load_csv("macro_kalshi.csv")
    timing_full = load_csv("timing_full.csv")
    timing_pass = load_csv("timing_pass.csv")
    mech = load_csv("mechanism_verified.csv")
    accepted = load_csv("verification_pairs_macro.csv")

    rows = [
        ("Stage A1 — Macro event master list", "FMP + FRED union",
         len(master) if master is not None else "—"),
        ("Stage A2 — Kalshi 시리즈 (전체)", "outputs/kalshi_series_all.csv", 10161),
        ("Stage A2 — Macro Kalshi (rule match)", "title regex 매치",
         len(macro_kalshi) if macro_kalshi is not None else "—"),
        ("Stage B — CA × macro Kalshi (timing 평가)", "63 non-WC CA × 151 macro Kalshi",
         len(timing_full) if timing_full is not None else "—"),
        ("Stage B — Timing pass (lead ≥ 3d)", "코드 계산",
         len(timing_pass) if timing_pass is not None else "—"),
        ("Stage C — Mechanism LLM verify", "Haiku 4.5",
         len(mech) if mech is not None else "—"),
        ("**Final 채택 (connected=true)**", "—",
         len(accepted) if accepted is not None else "—"),
    ]
    lines = ["| Stage | 방법 | 개수 |", "|---|---|---:|"]
    for stage, method, n in rows:
        lines.append(f"| {stage} | {method} | {n} |")
    return "\n".join(lines)


def top_accepted_section(top_k: int = 30) -> str:
    accepted = load_csv("verification_pairs_macro.csv")
    if accepted is None or accepted.empty:
        return "_(채택된 페어 없음 — Stage C 미실행 또는 모두 connected=false)_"

    lines = []
    for i, (_, r) in enumerate(accepted.head(top_k).iterrows()):
        lines.append(f"### #{i + 1} — `{r['ca_dataset_id']}` × `{r['kalshi_series_ticker']}`")
        lines.append("")
        lines.append(f"- CA: **{r['ca_name']}**")
        lines.append(f"- Kalshi title: {r['kalshi_title']}")
        lines.append(f"- Matched macro event(s): `{r['matched_events']}`")
        lines.append(f"- Lead window: **{int(r['lead_window_days'])} days**")
        lines.append(f"- Channel: {r.get('channel') or '_(no channel)_' }")
        if r.get('caveat'):
            lines.append(f"- Caveat: _{r['caveat']}_")
        lines.append("")
    return "\n".join(lines)


def matched_events_dist() -> str:
    accepted = load_csv("verification_pairs_macro.csv")
    if accepted is None or accepted.empty:
        return ""
    counts: dict[str, int] = {}
    for s in accepted["matched_events"]:
        for e in str(s).split(","):
            counts[e.strip()] = counts.get(e.strip(), 0) + 1
    sorted_counts = sorted(counts.items(), key=lambda x: -x[1])
    lines = ["| Macro event | 채택 페어 수 |", "|---|---:|"]
    for e, n in sorted_counts[:20]:
        lines.append(f"| {e} | {n} |")
    return "\n".join(lines)


def anchor_sanity() -> str:
    """Check whether the macro anchors made it through each stage."""
    timing_full = load_csv("timing_full.csv")
    accepted = load_csv("verification_pairs_macro.csv")

    anchors = [
        ("CA0030", "UMICHOVR", "CA0030 Clickstream × KXUMICHOVR"),
        ("CA0056", "USRETAIL", "CA0056 Card × KXUSRETAIL"),
    ]
    lines = []
    for ca_id, kal_pattern, label in anchors:
        if timing_full is None:
            lines.append(f"- {label}: timing_full missing")
            continue
        match = timing_full[(timing_full["ca_dataset_id"] == ca_id)
                            & timing_full["kalshi_series_ticker"].astype(str).str.contains(kal_pattern)]
        if match.empty:
            lines.append(f"- {label}: ❌ Stage B 에서 매칭 안 됨 (kalshi pattern 부재 가능)")
            continue
        m = match.iloc[0]
        timing_str = (f"lead={int(m['lead_window_days'])}d "
                      f"({'✅ pass' if m['timing_pass'] else '❌ fail'})")
        # Check Stage C
        if accepted is not None and not accepted.empty:
            acc_match = accepted[(accepted["ca_dataset_id"] == ca_id)
                                 & accepted["kalshi_series_ticker"].astype(str).str.contains(kal_pattern)]
            stage_c = "✅ accepted" if not acc_match.empty else "❌ rejected (connected=false)"
        else:
            stage_c = "— (Stage C 미실행)"
        lines.append(f"- **{label}**: Stage B {timing_str}, Stage C {stage_c}")
    return "\n".join(lines)


def negative_control_sanity() -> str:
    accepted = load_csv("verification_pairs_macro.csv")
    if accepted is None or accepted.empty:
        return "_(Stage C 미실행)_"
    # Check that obviously unrelated CA (entertainment, music) × macro events aren't accepted
    spurious_ca = ["CA0011", "CA0046", "CA003", "CA007", "CA008", "CA0010", "CA0050", "CA004", "CA0036"]
    bad = accepted[accepted["ca_dataset_id"].isin(spurious_ca)]
    if bad.empty:
        return "✅ entertainment/music/sports CA 들이 어떤 매크로 페어에도 채택 안 됨"
    return (f"⚠️ entertainment/music/sports CA 들 중 {len(bad)} 페어 채택 — "
            f"수동 점검 필요\n\n"
            + bad[["ca_dataset_id", "ca_name", "kalshi_series_ticker", "channel"]]
                .head(10).to_markdown(index=False))


def main() -> None:
    md = [
        "# Macro Track 검증쌍 — 자동 도출",
        "",
        "> Phase 0 (automated) 의 실행 결과. cheap-first 필터 + ",
        "> authoritative 매크로 list 기반.",
        "",
        "## TL;DR",
        "",
        funnel_table(),
        "",
        "## 방법론",
        "",
        "- **Stage A1**: FMP economic_calendar (1,225 release 의 unique event 이름) + ",
        "  FRED indicators (St. Louis Fed 큐레이트) union. 수작업 매크로 list 추가 X.",
        "  → `outputs/auto/macro_event_master_list.csv`",
        "- **Stage A2**: Kalshi 시리즈 (10,161 전부) 의 title 에 master list event 이름 + ",
        "  공식 alias (BLS/BEA/Census 공식 약어) regex 매치. 룰은 ",
        "  `docs/macro_matching_rules.md` 에 commit.",
        "  → `outputs/auto/macro_kalshi.csv` (1.5% = 151 series)",
        "- **Stage B**: 63 non-WC CA × 매크로 Kalshi 모든 페어에 ",
        "  `lead_window_days = (macro_cadence) − (ca_lag)` 계산. ≥ 3일만 통과.",
        "  → `outputs/auto/timing_pass.csv`",
        "- **Stage C**: Timing-pass 페어에 Anthropic Haiku 4.5 호출, ",
        "  JSON `{connected, channel, caveat}`. `connected=true` 만 최종 채택.",
        "  Temperature=0, single system prompt (cached).",
        "  → `outputs/auto/mechanism_verified.csv`",
        "",
        "LLM 호출은 Stage C 만 발생 — 페어 단위 검증. Stage A·B 는 0 LLM.",
        "",
        "## Sanity checks",
        "",
        "### Anchor pairs",
        "",
        anchor_sanity(),
        "",
        "### Negative control",
        "",
        negative_control_sanity(),
        "",
        "## 채택된 매크로 이벤트 분포",
        "",
        matched_events_dist(),
        "",
        "## Top 채택 검증쌍 (lead window 큰 순)",
        "",
        top_accepted_section(top_k=30),
        "",
        "---",
        "",
        "## Appendix",
        "",
        "- 매크로 이벤트 master: `outputs/auto/macro_event_master_list.csv`",
        "- 매칭 룰: `docs/macro_matching_rules.md`",
        "- Stage B full: `outputs/auto/timing_full.csv` / `timing_pass.csv`",
        "- Stage C full: `outputs/auto/mechanism_verified.csv`",
        "- 최종 채택 (Stage C connected=true): `outputs/auto/verification_pairs_macro.csv`",
        "- Prompts: `scripts/auto/s_c_mechanism_verify.py` (SYSTEM_PROMPT)",
        "",
        "### 재현 명령",
        "",
        "```bash",
        "python3 scripts/auto/s_a1_macro_list.py",
        "python3 scripts/auto/s_a2_kalshi_macro_match.py",
        "python3 scripts/auto/s_b_timing.py",
        "python3 scripts/auto/s_c_mechanism_verify.py --model claude-haiku-4-5 --workers 12",
        "python3 scripts/auto/s_report.py",
        "```",
    ]

    out = OUT_DOCS / "verification_pairs_macro.md"
    out.write_text("\n".join(md))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
