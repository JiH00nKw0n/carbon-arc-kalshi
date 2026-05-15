# CarbonArc × Kalshi — Macro Lead-Lag Verification

> 2026-05-14 CarbonArc 콜랩 미팅을 위한 EDA / feasibility 연구.
> Jack Haverty 의 macro lead-lag 앵글 + Jihoon 의 단계적 검증 방법론.
> 핵심 deliverable: **`docs/verification_pairs_macro.md`** (754 검증쌍 자동 도출).

## TL;DR

자동 파이프라인이 CarbonArc 데이터셋 × Kalshi 매크로 마켓의 검증쌍을 다음과 같이 추출:

| Stage | 방법 | 개수 |
|---|---|---:|
| A1 Macro event master list | FMP economic_calendar + FRED indicators union | 123 |
| A2 Kalshi (전체) | `outputs/kalshi_series_all.csv` | 10,161 |
| A2 Macro Kalshi (rule match) | title regex × alias dict | 151 |
| B CA × macro Kalshi 페어 | 63 non-WC CA × 151 macro Kalshi | 6,795 |
| B Timing pass (lead ≥ 3d) | 코드 계산 | 5,664 |
| C Mechanism verify | Haiku 4.5 (`connected=true/false`) | 5,664 |
| **Final 채택** | connected=true | **754** |

- **v1 수작업 39쌍 재현율 66.7%** (26/39) — methodological cross-check.
- **Anchor 페어 둘 다 통과**: `CA0030 Clickstream × KXUMICHOVR` (lead 29d), `CA0056 Card × KXUSRETAIL` (lead 27d).
- 754 페어에 등장한 CA 데이터셋 35종, 채택 매크로 이벤트 분포는 `docs/verification_pairs_macro.md` 참조.

## Phase 별 상태

| Phase | 산출물 | 상태 | 비고 |
|---|---|---|---|
| **0 (automated v2)** | **`scripts/auto/`, `docs/verification_pairs_macro.md`, 754 검증쌍** | **완료** | **본 repo 핵심 deliverable** |
| 1 (sample EDA) | `outputs/eda/PHASE1_REPORT.md` | 완료 | sample n=20, CA0049×UMich r=−0.79 (statistical evidence X, pipeline sanity only; COVID 빼면 r=−0.19) |
| 2 (scenario design) | `docs/leadlag_scenarios.md` (S1-S4) | 완료, 백테스트 design | 실행 미완 |
| 3 (LLM unstructured PoC) | `prompts/ca_row_to_text.md`, `docs/llm_cost.md`, `scripts/phase3_smoke_test.py` | smoke test 성공 | Sonnet 4.6 cached 예산 ~$1.5-2k/yr |
| **E (framework 가격 조사)** | **`scripts/auto/s_e_price_all.py`, `docs/framework_prices.md`** | **완료** | $50 promo 활용 계획 — 14/35 데이터셋이 단독 $50 이내 (282 페어), CA0056 7y = $19.30 단일 anchor 추천 |

진행 상세는 `RESEARCH_PROGRESS.md` 참조.

## 디렉토리 가이드

```
scripts/auto/                         ← Phase 0 자동 검증쌍 추출
  s_a1_macro_list.py                  FMP + FRED → macro event master (123)
  s_a2_kalshi_macro_match.py          Kalshi 10,161 → macro 151 (rule + alias)
  s_b_timing.py                       63 CA × 151 Kalshi → timing pass 5,664
  s_c_mechanism_verify.py             Haiku 4.5 verify → connected=true 754
  s_d_v1_diff.py                      (legacy) v1 수작업 39쌍과의 diff — 비교용
  s_report.py                         docs/verification_pairs_macro.md 생성
  s_e_price_all.py                    CarbonArc framework 가격 조회 (35 dataset × 1y/3y/5y)

scripts/                              ← Phase 1/3 (EDA + LLM PoC)
  phase1_0_fetch_samples.py           CarbonArc 무료 sample 100행 fetch
  phase1_eda.py                       CA0049/CA0077/CA0053 × FRED 시계열 EDA
  phase3_smoke_test.py                LLM 비정형 시그널 PoC E2E
  build_fred_cache.py / cache_fred.py FRED 시리즈 캐시
  phase0_*.py                         (legacy) 수작업 v1 검증쌍 도출 — s_d_v1_diff 의 입력

docs/
  verification_pairs_macro.md         ← Phase 0 최종 리포트
  ca_datasets_in_verification_pairs.md 754 페어에 등장한 35 CA + 샘플 row
  framework_prices.md                 ← Stage E 가격표 (754 페어 × CarbonArc cost)
  macro_matching_rules.md             Stage A2 alias 사전
  leadlag_scenarios.md                Phase 2 백테스트 S1-S4 디자인
  llm_cost.md                         Phase 3 비용 envelope

prompts/
  ca_row_to_text.md                   CA row → 1-sentence summary system prompt

ANALYSIS.md / DATA.md / RESEARCH_PROGRESS.md  최초 EDA 메모 + 진행 트래커
```

## 재현

### 의존성

```bash
pip install -r requirements.txt
```

`.env` 파일 (repo 에 미포함, 직접 작성):
```
ANTHROPIC_API_KEY=sk-ant-...     # Stage C 만 사용
CARBONARC_API_KEY=eyJ...          # phase1_0_fetch_samples / phase3_smoke_test
FMP_API_KEY=...                   # phase0_4_macro_releases / s_a1_macro_list
```

### 사전 fetch (gitignore 된 `_explore/`, `outputs/` 가 비어있을 때)

```bash
# 무료 sample + FRED 캐시 (_explore/samples/*, outputs/fred/* 생성)
python3 scripts/phase1_0_fetch_samples.py
python3 scripts/build_fred_cache.py
python3 scripts/phase1_eda.py                                       # Phase 1 EDA
```

Kalshi 전체 시리즈 inventory (`outputs/kalshi_series_all.csv`) 가 필요한 경우 `scripts/phase0_2_kalshi_inventory.py` 한 번 실행 — 나머지 phase0_*.py 는 v1 수작업 검증쌍 추출 (legacy, s_d_v1_diff 비교 용도 외에는 미사용).

### Phase 0 자동 파이프라인

```bash
python3 scripts/auto/s_a1_macro_list.py
python3 scripts/auto/s_a2_kalshi_macro_match.py
python3 scripts/auto/s_b_timing.py                                   # _explore/datasets_non_webcontent.json 필요
python3 scripts/auto/s_c_mechanism_verify.py --model claude-haiku-4-5 --workers 12
python3 scripts/auto/s_d_v1_diff.py
python3 scripts/auto/s_report.py                                      # docs/verification_pairs_macro.md 생성
python3 scripts/auto/s_e_price_all.py                                 # docs/framework_prices.md (CarbonArc 가격, promo 차감 X)
```

런타임: Stage A·B 합쳐 < 1분, Stage C 는 5,664 페어 × 12 workers ≈ 15-20분. Haiku 비용 ~$2-5. Stage E 는 35 dataset × 3 windows ≈ 3분, $0.

## 결과 검토 포인트

- **Borderline 46건**: entertainment/music/sports CA × 매크로 페어가 Haiku 로 connected=true 통과 (예: Secondary Market Ticket Sales × CPI). `s_report.py:negative_control_sanity()` 에서 자동 flag. 수동 점검 필요.
- **v1-only 13건**: v1 수작업이 채택했지만 v2 자동에서 reject. Haiku 가 과도하게 보수적이었을 가능성 (예: CA0077 × CPI Tobacco 는 통과, CA0077 × 일부 CPI 종목은 reject).
- **Sonnet 재실행 옵션**: `s_c_mechanism_verify.py --model claude-sonnet-4-6` 로 더 엄격한 cut. Haiku/Sonnet 합의한 페어만 채택하는 두 단계 필터링도 가능.

## Limitations

- CA 무료 sample 은 토픽당 100행 — Phase 1 EDA 의 통계는 sanity 시그널 수준 (CA0049 monthly n=20).
- Stage B `lead_window_days = macro_cadence − ca_lag` 는 *typical cadence* 가정 (monthly=30d 등). 정확한 expected_expiration_time 은 Kalshi API 별도 호출 필요.
- Stage C 는 페어 단위 LLM 1회 호출, temperature=0 이지만 prompt-sensitive. 재실행 variance 는 직접 확인 안 함.
- 754 페어가 곧바로 alpha 시그널은 아님 — **검증 *후보*** 일 뿐, 실측 백테스트는 Phase 2 디자인 후 별도 작업.

## License & Note

Private repo. CarbonArc 데이터는 비공개 (Insights Exchange API 로만 접근). 이 repo 의 결과물은 *alt-data feasibility research* 이며 투자 자문이 아님.

---

**계획 파일**: `~/.claude/plans/lazy-mixing-simon.md` (로컬, repo 미포함).
**미팅 컨텍스트**: 2026-05-14 CarbonArc collab. 핵심 동기 = "수작업 cherry-pick 가능성을 제거한 검증쌍 도출".
