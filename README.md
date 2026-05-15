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

## 단, "검증쌍" ≠ "alpha 시그널" — 두 번 확인한 사실

이 repo 의 754 페어는 **검증 *후보*** 일 뿐. 두 차례 실증 시도 결과 모두 *자세히 보면 시그널이 약해진다*:

**(1) Phase 1 — 무료 100행 sample EDA (CA0049 × UMich, n=20)**

| 윈도우 | r at lag +1 |
|---|---:|
| Raw 2016-2021 | **−0.79** ← 첫인상 |
| COVID 3개월 (2020-03/04/05) 제외 | **−0.19** ← 무너짐 |

COVID 가 양쪽 시리즈 (제약 청구 폭증 + sentiment 폭락) 에 동시 충격 → spurious common-shock. 리포트 본문 자체가 "pipeline + structural-fit demo, **not statistical evidence**" 라고 명시.

**(2) Phase 5 — 첫 framework 구매 (CA0030 Clickstream 5y monthly US, $4.99, n=63)**

UMich anchor 페어만 봤을 때: 4 detrending method 모두 lag +1 에서 negative 상관 (r ≈ −0.34 ~ −0.59). 첫인상은 "sample EDA 보다 robust 한 시그널" — 상세 `docs/analysis_ca0030_umich.md`.

**(3) Phase 5 후속 — Multi-macro 일관성 검증 (같은 데이터, 추가 비용 0)**

같은 CA0030 데이터로 UMich 외 매크로도 봤더니 **결과가 뒤집힘** — 상세 `docs/analysis_ca0030_multi_macro.md`:

| CA0030 (SUM) × | YoY % change best |r| | 방향 |
|---|---|---|
| UMich Sentiment | 0.50 at lag +1 | CA leads, negative |
| Retail Sales | **0.75 at lag −1** | **Macro leads CA**, positive |
| NFP | **0.68 at lag −1** | **Macro leads CA**, positive |

Retail Sales / NFP 의 경우 **매크로가 CA0030 을 1개월 leads** — lead-lag 가설의 *정반대* 방향. 그것도 \|r\| 가 UMich (0.5) 보다 더 큼 (0.7).

해석: CA0030 의 5y 동안 5.17x panel 성장이 *경기 좋을 때 가속*되는 onboarding artifact — 즉 CA 의 변동은 경제의 *결과*, 원인이 아님. UMich 만 다른 부호 나온 건 UMich 도 같은 기간 79→53 으로 하락 추세라 단순 trend 노이즈 잔여일 가능성.

**→ 핵심 함의**: 754 페어의 `lead_window_days` 는 *publication timing* (CA 가 매크로 발표 *후* 무엇이 일찍 출시되는가) 이지, *데이터 lead* (CA 변동이 매크로 변동을 leads) 가 아님. **두 개념은 다름**. 후자는 페어별 실증 데이터로만 입증 가능.

## Phase 별 상태

| Phase | 산출물 | 상태 | 비고 |
|---|---|---|---|
| **0 (automated v2)** | **`scripts/auto/`, `docs/verification_pairs_macro.md`, 754 검증쌍** | **완료** | **본 repo 핵심** |
| 1 (sample EDA) | `outputs/eda/PHASE1_REPORT.md` | 완료, sanity만 | sample n=20, r=−0.79 가 COVID 제외 시 r=−0.19 로 무너짐 |
| 2 (scenario design) | `docs/leadlag_scenarios.md` (S1-S4) | 완료, 디자인만 | 백테스트 실행 미완 |
| 3 (LLM unstructured PoC) | `prompts/ca_row_to_text.md`, `docs/llm_cost.md`, `scripts/phase3_smoke_test.py` | smoke test 성공 | Sonnet 4.6 cached 예산 ~$1.5-2k/yr |
| E (framework 가격 조사) | `scripts/auto/s_e_price_all.py`, `docs/framework_prices.md` | 완료 | 35 CA 가격 매트릭스. 14개 데이터셋이 단독 $50 이내 (282 페어) |
| **5 (첫 구매 + 검증)** | **`docs/purchase_log.md`, `docs/analysis_ca0030_umich.md`, `docs/analysis_ca0030_multi_macro.md`** | **진행 중** | **CA0030 Clickstream 5y $4.99 구매**. UMich 만 lag +1 negative; Retail Sales / NFP 는 lag −1 positive (**매크로가 CA 를 leads**). 즉 CA0030 panel-growth 가 경제 변수의 결과인 듯 — lead-lag 가설 미입증. promo 잔액 $45.01 |

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
  purchase_log.md                     ← Phase 5 구매 기록 (실제 promo 차감된 거래만)
  analysis_ca0030_umich.md            ← Phase 5 첫 분석 (UMich anchor) + 자체 비판
  analysis_ca0030_multi_macro.md      ← Phase 5 후속 — Retail Sales / NFP 까지 봤더니 가설이 흔들림
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

- Stage B `lead_window_days` 는 *publication timing* 만 측정 — CA 가 매크로 발표 *후* 며칠 더 일찍 publish 되는가. **데이터 lead** (CA 변동이 매크로 변동을 시간순으로 leads) 는 별개 개념이며 페어별 실증 데이터로만 확인 가능. Phase 5 multi-macro 분석이 이 두 개념의 차이를 드러냄.
- Stage C 는 페어 단위 LLM 1회 호출, temperature=0 이지만 prompt-sensitive. 재실행 variance 는 직접 확인 안 함.
- **Phase 5 의 CA0030 결과** — `docs/analysis_ca0030_multi_macro.md`:
  - UMich 안 양의 lead (negative r at lag +1) 이 다른 매크로 (Retail Sales, NFP) 에서 재현 안 됨 → trend artifact 가능성
  - Panel 5y 동안 5.17x 성장이 macro-leads-CA 패턴 만들고 있음 (경기 좋을 때 panel onboarding 가속)
  - 즉 CA0030 (clickstream) 은 panel-growth 가 dominant → economic lead 검증의 *깨끗한* 테스트 베드 아님
  - Card transaction (CA0056) 처럼 panel-growth 영향이 적은 데이터셋이 더 적절
- 754 페어는 검증 *후보*. Trade-able edge 는 panel-growth confound 가 적은 데이터셋 (Card / Commodity) 의 framework 구매 + OOS 백테스트로만 입증 가능.

## Next steps

**즉시 가능 (추가 비용 0)** — 같은 CA0030 데이터로:
1. UMich 의 다른 sub-index 와 cross-check (Conference Board Consumer Confidence, UMich inflation expectations) — UMich-specific 패턴인지 확인
2. Mobile aggregation 단독 재분석 (Desktop 의 panel growth 영향 적음)
3. Granger-causality test 로 lead 방향 통계 검증

**다음 framework 구매 결정** ($45.01 promo 남음):
- 최우선 후보: **CA0056 Card Spend US 7y monthly $19.30** — Phase 0b 의 다른 anchor 페어 (KXUSRETAIL). Card transaction 은 panel onboarding 영향이 적을 것 (사용자 수가 아니라 거래 금액) → lead-lag 가설의 더 깨끗한 테스트.
- CA0030 결과가 confound 의 직접 증거이므로 panel-growth 적은 데이터셋에서 가설 재검증 우선.

**검증 파이프라인 자체 보완**:
- Borderline 46 페어 수동 triage 또는 Sonnet 재실행으로 두 모델 합의 페어만 남기기
- Phase 2 `leadlag_scenarios.md` 의 S1-S4 백테스트 디자인 실행 — 단, lead 방향 검증 결과 반영 후

## License & Note

Private repo. CarbonArc 데이터는 비공개 (Insights Exchange API 로만 접근, 본 repo 에는 100행 sample 도 포함 X). 결과물은 *alt-data feasibility research* 이며 투자 자문이 아님.

---

미팅 컨텍스트: 2026-05-14 CarbonArc collab. 핵심 동기 = "수작업 cherry-pick 가능성을 제거한 검증쌍 도출".  
계획 파일: `~/.claude/plans/lazy-mixing-simon.md` (로컬, repo 미포함).
