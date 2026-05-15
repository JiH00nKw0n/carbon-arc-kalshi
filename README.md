# CarbonArc × Kalshi — Macro Lead-Lag Verification

대안 데이터(alternative data)가 미국 공식 매크로 발표를 며칠~몇 주 앞서 움직이는지, 그리고 그 lead 가 예측시장(Kalshi)의 정산 직전 가격에 활용 가능한지를 검증하기 위해 **(CarbonArc dataset, Kalshi market)** 검증쌍을 자동으로 추출한 결과물.

## 무엇이고 왜 하는가

### 등장인물

- **CarbonArc (CA)** — "Insights Exchange" 라는 alt-data 마켓플레이스. 신용카드 거래, POS, 매장 방문, 클릭스트림, 의약품 청구, 화물 등 63개 데이터셋(non-webcontent)을 보유. 데이터셋마다 publication lag (예: T+1d, T+7d) 가 다름.
- **Kalshi** — 미국 CFTC 규제 prediction market. 정부 통계 발표마다 "Core CPI YoY 가 2.3% 이상일까", "이번 NFP 가 X 이상일까" 같은 binary contract 가 활발히 거래됨. 전체 10,161개 시리즈 중 약 1.5% (151개) 가 공식 매크로 발표(BLS / BEA / Census / Fed 등) 로 settle.
- **Macro release** — BLS Nonfarm Payrolls, BEA Personal Income & Outlays (Core PCE), Census Retail Sales, UMich Consumer Sentiment 등의 정기 통계 발표. 사전에 알려진 일정으로 발표되고, Kalshi 마켓의 정산 트리거가 됨.

### 가설 (Macro Lead-Lag Thesis)

대안 데이터는 같은 경제 활동을 *민간 채널* 로 실시간 수집한다. 따라서:
- 신용카드 거래 합계 (CA) 는 Census Retail Sales 발표보다 며칠 앞서 측정됨
- 매장 방문 트래픽 (CA) 은 BLS Employment 발표보다 앞서 노동시장 변화를 반영
- 클릭스트림 (CA) 은 UMich Consumer Sentiment 설문보다 소비자 engagement 를 일찍 포착

→ **검증쌍** = 위 가설이 *시간순으로 가능하면서* (CA 가 매크로 발표 전에 publish), *경제 메커니즘이 살아있는* (CA 측정 ↔ 매크로 컨텐츠 연결) 짝.

### 왜 자동으로 뽑는가

수작업 매핑 (이 repo 의 v1: 39 페어) 은 cherry-pick 위험. reviewer 가 "왜 X 는 넣고 Y 는 뺐냐" 라고 물으면 변호 못함. 자동 파이프라인으로:

1. **공신력 source 의 매크로 list 사용** — FMP economic_calendar (1,225 release) + FRED indicators union, 수작업 추가 X
2. **Cheap-first 필터링** — 비싼 LLM 점수 먼저 안 매기고, 룰 매칭 → timing 계산 → LLM verify 순서
3. **Pair-wise mechanism verify** — 페어 단위 LLM 호출 (Anthropic Haiku 4.5), temperature=0, JSON 응답, prompt 와 alias 사전 모두 git commit

## 결과 — funnel

| Stage | 방법 | 개수 |
|---|---|---:|
| A1. Macro event master list | FMP economic_calendar + FRED indicators union | 123 events |
| A2. Kalshi 전체 시리즈 | (기존 inventory) | 10,161 |
| A2. Macro Kalshi (rule match) | title regex + 공식 alias 사전 | **151** |
| B. CA × macro Kalshi 페어 평가 | 63 CA × 151 Kalshi | 6,795 |
| B. Timing pass (lead ≥ 3d) | `lead = macro_cadence − ca_lag` | **5,664** |
| C. Mechanism verify (Haiku 4.5) | `{connected, channel, caveat}` JSON | 5,664 |
| **C. Final 채택** | `connected=true` | **754** |

- v1 수작업 39 페어 재현율 **66.7%** (26/39) — methodology cross-check
- 🔑 Anchor 페어 둘 다 통과: **`CA0030 Clickstream × KXUMICHOVR`** (lead 29d, UMich Sentiment), **`CA0056 Credit Card US Complete × KXUSRETAIL`** (lead 27d, Retail Sales)
- 754 페어가 사용하는 unique CA 데이터셋 **35종**

핵심 deliverable: **`docs/verification_pairs_macro.md`** (754 페어 ranked) + **`docs/framework_prices.md`** (각 페어의 CarbonArc 구매 가격).

## 단, "검증쌍" ≠ "alpha 시그널"

이 repo 의 754 페어는 **검증 *후보*** 일 뿐. 실제 lead-lag 가 통계적으로 유의한지는 full panel 데이터로 백테스트 해야 함. 무료 100행 sample 로 시도했더니:

- CA0049 Pharmacy × UMich Sentiment monthly **r = −0.79** (n=20) — 처음엔 의미 있어 보였음
- COVID 핵심 3개월 (2020-03~05) 빼면 r = **−0.19** 로 무너짐 → COVID 가 양쪽 시리즈에 동시 충격 → spurious common-shock

→ Phase 1 EDA 리포트는 "pipeline + structural-fit demo, **not statistical evidence**" 라고 명시. 본격적 검증은 framework 구매 ($50 promo 보유) 후의 후속 작업.

## Phase 별 상태

| Phase | 산출물 | 상태 | 비고 |
|---|---|---|---|
| **0 (automated v2)** | **`scripts/auto/`, `docs/verification_pairs_macro.md`, 754 검증쌍** | **완료** | **본 repo 핵심** |
| 1 (sample EDA) | `outputs/eda/PHASE1_REPORT.md` | 완료, sanity만 | sample n=20, r=−0.79 가 COVID 제외 시 r=−0.19 로 무너짐 |
| 2 (scenario design) | `docs/leadlag_scenarios.md` (S1-S4) | 완료, 디자인만 | 백테스트 실행은 framework 구매 후 |
| 3 (LLM unstructured PoC) | `prompts/ca_row_to_text.md`, `docs/llm_cost.md`, `scripts/phase3_smoke_test.py` | smoke test 성공 | Sonnet 4.6 cached 예산 ~$1.5-2k/yr |
| **E (framework 가격 조사)** | **`scripts/auto/s_e_price_all.py`, `docs/framework_prices.md`** | **완료** | $50 promo 활용 계획. 14/35 데이터셋이 단독 $50 이내 (282 페어 cover), **CA0056 7y monthly = $19.30** 단일 anchor 추천 |

총괄 진행 로그는 `RESEARCH_PROGRESS.md`.

## 디렉토리 가이드

```
scripts/auto/                         ← Phase 0 자동 검증쌍 추출 파이프라인
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
  verification_pairs_macro.md         ← Phase 0 최종 리포트 (TL;DR + 754 페어 top-30)
  ca_datasets_in_verification_pairs.md 754 페어에 등장한 35 CA + 샘플 row
  framework_prices.md                 ← Stage E 가격표 (754 페어 × CarbonArc cost)
  macro_matching_rules.md             Stage A2 alias 사전 (BLS/BEA/Census 공식 약어)
  leadlag_scenarios.md                Phase 2 백테스트 S1-S4 디자인 (LightGBM + SHAP)
  llm_cost.md                         Phase 3 비용 envelope

prompts/
  ca_row_to_text.md                   CA row → 1-sentence summary system prompt

ANALYSIS.md / DATA.md / RESEARCH_PROGRESS.md  최초 EDA 메모 + 진행 트래커
```

`outputs/`, `_explore/` 는 `.gitignore` — script 로 재생성 가능한 데이터 / 원본 API 캐시.

## 재현

### 의존성

```bash
pip install -r requirements.txt
```

`.env` 파일 (repo 미포함, 직접 작성):
```
ANTHROPIC_API_KEY=sk-ant-...     # Stage C, Phase 3 만 사용
CARBONARC_API_KEY=eyJ...         # sample fetch, Stage E, phase3 smoke test
FMP_API_KEY=...                  # Stage A1, phase0_4
```

### 사전 fetch (`_explore/`, `outputs/` 가 비어있을 때)

```bash
# 무료 sample + FRED 캐시 (_explore/samples/*, outputs/fred/* 생성)
python3 scripts/phase1_0_fetch_samples.py
python3 scripts/build_fred_cache.py
python3 scripts/phase1_eda.py                                       # Phase 1 EDA
```

Kalshi 전체 시리즈 inventory (`outputs/kalshi_series_all.csv`) 가 필요한 경우 `scripts/phase0_2_kalshi_inventory.py` 한 번 실행. 나머지 `phase0_*.py` 는 v1 수작업 검증쌍 추출 (legacy, `s_d_v1_diff` 비교 용도 외에는 미사용).

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

런타임: Stage A·B 합쳐 < 1분, Stage C 는 5,664 페어 × 12 workers ≈ 15-20분 (Haiku 비용 ~$2-5), Stage E ≈ 3분 ($0, `check_framework_price` 만 호출).

## 결과 검토 시 짚어볼 점

- **Borderline 46건**: entertainment / music / sports CA × 매크로 페어가 Haiku 로 connected=true 통과 (예: Secondary Market Ticket Sales × CPI Apparel). `s_report.py:negative_control_sanity()` 가 자동 flag. 수동 점검 후보.
- **v1-only 13건**: v1 수작업이 채택했지만 v2 자동에서 reject. Haiku 가 과도하게 보수적이었을 가능성. v1 의 mechanism 직관이 살아있는 페어들.
- **Sonnet 재실행 옵션**: `s_c_mechanism_verify.py --model claude-sonnet-4-6` 으로 더 엄격한 cut 가능. Haiku/Sonnet 두 모델이 동의한 페어만 채택하는 2단계 필터링도 시도해 볼 수 있음.

## Limitations

- CA 무료 sample 은 토픽당 100행 — Phase 1 EDA 의 통계는 sanity 시그널 수준 (CA0049 monthly n=20, COVID 빼면 r=−0.19).
- Stage B `lead_window_days = macro_cadence − ca_lag` 는 *typical cadence* 가정 (monthly = 30d 등). Kalshi 시장별 정확한 expected_expiration_time 은 API 추가 호출 필요.
- Stage C 는 페어 단위 LLM 1회 호출, temperature=0 이지만 prompt-sensitive. 재실행 variance 는 직접 확인 안 함.
- **754 페어는 검증 *후보***. 실측 lead-lag 와 trade-able edge 는 framework 구매 후 백테스트로만 확인 가능.

## Next steps (제안)

1. **CA0056 7y monthly framework 구매 ($19.30, $30.70 promo 잔존)** → Census Retail Sales 와 cross-checked 백테스트, COVID 분리 가능한 84 monthly obs 확보
2. 결과 보고 promo 잔액으로 **CA0077 commodity 1y ($22.96)** 또는 **CA0030 Clickstream 5y ($4.99)** 추가 구매
3. Phase 2 `leadlag_scenarios.md` S1-S4 백테스트 디자인 실행 (LightGBM + SHAP)
4. Borderline 46 페어 수동 triage 또는 Sonnet 재실행으로 두 모델 합의 페어만 남기기

## License & Note

Private repo. CarbonArc 데이터는 비공개 (Insights Exchange API 로만 접근, 본 repo 에는 100행 sample 도 포함 X). 결과물은 *alt-data feasibility research* 이며 투자 자문이 아님.

---

미팅 컨텍스트: 2026-05-14 CarbonArc collab. 핵심 동기 = "수작업 cherry-pick 가능성을 제거한 검증쌍 도출".  
계획 파일: `~/.claude/plans/lazy-mixing-simon.md` (로컬, repo 미포함).
