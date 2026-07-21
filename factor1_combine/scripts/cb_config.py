"""
X 조합(combine) 실험 config — Notion 코멘트 "X를 여러 개 조합하면?" 구현.

세팅 (기존과 거의 동일):
  Y = revenue surprise (surprise_early) 고정
  Z = earnings call (여기선 X조합 효과만 보므로 Z는 미사용, Factor 3에서 결합)
  X = 단일(card/foot/web) vs 결합(card+foot 등)

핵심 질문: X를 조합하면 single 대비 Y 예측이 좋아지는가? 어느 조합·어느 회사에서?

데이터 커버리지 현실 (공통 티커):
  card&foot      = 27종목  → 실험 가능 (10개 선정)
  card&web       =  6종목  → 보조
  foot&web       =  1종목  → 불가 (web=이커머스, foot=오프라인이라 안 겹침)
  card&foot&web  =  1종목  → 불가
따라서 실질 조합은 card&foot(메인) + card&web(보조).

기존 코드 재사용: factor1_yswitch/scripts/ys_lib.py 의 build_card/build_foot/build_click,
factor1/scripts/f1_stats.py 의 cluster_boot/surrogate. 새 코드 최소화.
"""
from pathlib import Path

ROOT   = Path(__file__).resolve().parents[1]          # factor1_combine/
OUT    = ROOT / "outputs"
OUT.mkdir(parents=True, exist_ok=True)

YSROOT = ROOT.parent / "factor1_yswitch"               # reuse ys_lib + FactSet Y + X csv
YS_SCRIPTS = YSROOT / "scripts"
F1_STATS   = ROOT.parent / "factor1" / "scripts"

# 조합 정의: 이름 → 결합할 채널 리스트. single 3 + pair(데이터 되는 것) + triple(불가 명시)
COMBOS = {
    "card":            ["card"],
    "foot":            ["foot"],
    "web":             ["web"],
    "card+foot":       ["card", "foot"],
    "card+web":        ["card", "web"],
    "foot+web":        ["foot", "web"],          # n≈1, 실행 시 skip
    "card+foot+web":   ["card", "foot", "web"],  # n≈1, 실행 시 skip
}

MIN_COMMON = 6      # 조합 실행 최소 공통 티커 수 (이하면 skip)
MIN_OBS    = 15     # 검정 최소 관측치
