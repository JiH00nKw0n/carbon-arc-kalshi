# CarbonArc × Kalshi — Macro Pair Candidate Extraction

CarbonArc 의 대안 데이터가 미국 공식 매크로 발표를 시간순으로 *leads* 한다는 *가설* 을 데이터로 검증해 보려고 한다. 검증을 시작하려면 먼저 "검증해 볼 만한 (CA dataset, Kalshi market) 페어" 의 list 가 필요하다. **이 repo 가 만드는 것은 그 list 이지 가설의 입증이 아니다.**

## 용어 (먼저)

| 용어 | 뜻 |
|---|---|
| **CA leads macro by k months** | CA 의 YoY 변동이 macro 의 YoY 변동을 k 개월 *앞섬* (= 작업 가설을 *지지* 하는 방향). lag 양수. 예: CA 의 4월 변동이 macro 의 6월 변동과 상관 → CA leads by 2m |
| **Macro leads CA by k months** | 반대 방향. macro 가 먼저 움직이고 CA 가 따라옴 → 가설을 *반증* (CA 가 macro 의 *결과*) |
| **Contemp** | 동시기 변동, 방향 판정 불가 |
| **\|r\|** | Pearson 상관계수의 절대값. 강 ≥ 0.7, 중 0.5-0.7, 약 < 0.5 |
| **(∗) marker** | best_lag 가 검사 범위 (±2) 끝점 → 진짜 peak 이 ±2 밖일 가능성 |

## 가설 verdict 기준 (per dataset, 13 macros 기준)

| Verdict | 조건 |
|---|---|
| **잠정 지지** | ≥ 7/13 가 CA leads (lag > 0) **AND** 최소 1개 강 시그널 (\|r\|≥0.7) |
| **부분 지지** | CA leads ≥ Macro leads (둘 다 7 미만) **AND** 최소 1개 중-강 시그널 |
| **미지지** | ≥ 7/13 가 Macro leads (lag < 0); 또는 CA leads 가 있어도 모두 약 / endpoint 의심 |

위 verdict 는 모두 *잠정적* — common-trend / multiple testing / endpoint piling / no causality test 의 caveat 적용 (§Caveats).

## 현재 상태

1. **후보 페어 754개 추출 완료** — 10,161 Kalshi 시리즈 × 63 CA 데이터셋 → cheap-first 자동 필터링 후 754개 (`docs/verification_pairs_macro.md`).
2. **3 framework 구매 후 13 macros 실증 검증 (총 $44.41 / $50 promo)**:
   - CA0030 Clickstream $4.99 (사용자 수)
   - CA0056 Credit Card Spend $14.03 (거래 금액)
   - CA0034 Instore POS Volume $25.39 (거래 건수)
3. **결과 — 데이터셋 종류에 강하게 의존** (위 verdict 기준 적용):
   - **CA0030 (사용자 수)**: 미지지 — 7/13 Macro leads. Panel-growth artifact.
   - **CA0056 (거래 $)**: 부분 지지 — 6/13 CA leads, 5/13 Macro leads. PCE/CPI/NFP 가 CA leads 강 시그널.
   - **CA0034 (거래 건수)**: 잠정 지지 — 10/13 CA leads. NFP/Personal Income/Core CPI 에서 \|r\| ≈ 0.8.
   - 자세히는 `docs/analysis_per_dataset.md`.

---

## 무엇을 하려는가

### 등장인물

- **CarbonArc (CA)** — alt-data 마켓플레이스 "Insights Exchange". 신용카드 거래, POS, 매장 방문, 클릭스트림, 의약품 청구, 화물 등 63 개 데이터셋 (non-webcontent — 즉 raw HTML 스크레이핑이 아닌 정량 데이터). 데이터셋마다 publication lag 가 다름 (예: T+1d, T+7d).
- **Kalshi** — 미국 CFTC 규제 prediction market. 전체 10,161 개 시리즈 중 일부가 정부 통계 발표 (BLS / BEA / Census / Fed 등) 로 정산되는 binary contract.
- **공식 매크로 발표** — Nonfarm Payrolls (BLS), Core PCE (BEA), Retail Sales (Census), UMich Consumer Sentiment 등의 정기 정부 통계. 사전 공지된 일정으로 발표되며 위 Kalshi contract 의 정산 트리거.

### 작업 가설 (입증된 사실 아님)

> Alt-data 는 같은 경제 활동을 *민간 채널* 로 실시간 수집한다. 따라서 alt-data 의 변동이 공식 매크로 발표값의 변동보다 시간순으로 앞서 나타날 *수도* 있다.

구체적 *추측 (예시)*:
- 신용카드 거래 합계가 Census Retail Sales 발표 *전에* 측정될 수 있다 — Census 는 사후 집계이므로
- 매장 방문 트래픽이 BLS Employment 변동을 앞설 수 있다 — 매장 채용은 매장 활동과 연동되므로
- 클릭스트림이 UMich Consumer Sentiment 변동을 앞설 수 있다 — 설문은 응답 회수에 시간이 걸리므로

이런 추측들이 *실제로 데이터에서* 맞는지 확인하려면, 먼저 그런 매크로 발표에 정산되는 Kalshi 시리즈 list 와, 그 발표 전에 publish 되는 CA 데이터셋 list 를 매핑해야 한다.

### 검증쌍 (= "후보") 정의

(CA dataset, Kalshi market) 짝 중 다음 셋 모두 만족하는 것:

1. **Settlement** — Kalshi 가 공식 매크로 발표값으로 정산
2. **Timing** — CA 데이터가 그 매크로 발표 *전에* publicly available (publication 순서상 가능)
3. **Mechanism** — CA 측정 대상이 매크로 발표 컨텐츠와 인과적으로 연결됨

세 조건 모두 만족 = **"후보"**. 단순히 가설을 *테스트할 자격이 있는* 페어일 뿐, 가설의 *지지 증거* 가 아님.

### 왜 자동으로 뽑는가

초기 시도 (v1) 는 21 CA × 66 Kalshi 수작업 매칭으로 39 페어를 얻음. 문제: 매핑 기준이 머릿속에 있어 재현 불가. reviewer 가 "왜 X 는 넣고 Y 는 뺐냐" 라고 물으면 답할 수 없음.

→ 자동 파이프라인:

1. **공신력 source 의 매크로 list** — FMP economic_calendar (1,225 release) + FRED indicators union. 수작업 추가 X
2. **Cheap-first 필터링** — 비싼 LLM 점수부터 매기지 않고 룰 매칭 → timing 계산 → LLM verify 순서
3. **Pair-wise mechanism verify** — 페어 단위 LLM 호출 (Anthropic Haiku 4.5, temperature=0, JSON 응답). prompt 와 alias 사전 모두 git commit

---

## 무엇을 했나

| Phase | 한 일 | 산출물 | 상태 |
|---|---|---|---|
| **0 (automated 후보 추출)** | **cheap-first 자동 파이프라인 → 754 후보** | **`scripts/auto/`, `docs/verification_pairs_macro.md`** | **완료, 본 repo 핵심** |
| 1 (sample EDA) | 무료 100행 sample 로 시계열 sanity check | `outputs/eda/PHASE1_REPORT.md` | 완료, statistical evidence 수준 아님 |
| 2 (scenario design) | 4-scenario 백테스트 디자인 (LightGBM + SHAP) | `docs/leadlag_scenarios.md` | 디자인만, 실행 X |
| 3 (LLM unstructured PoC) | CA row → text → Kalshi search 파이프라인 | `prompts/ca_row_to_text.md`, `docs/llm_cost.md` | smoke test 통과 |
| 4 (framework 가격 조사) | 35 unique CA dataset 의 framework 가격 매트릭스 | `docs/framework_prices.md`, `scripts/auto/s_e_price_all.py` | 완료 |
| **5 (3 framework 구매 + 실증)** | **CA0030 + CA0056 + CA0034 × 13 매크로 × multi-aggregation** | **`docs/purchase_log.md`, `docs/analysis_per_dataset.md`** | **완료. 결론은 데이터셋 종류 의존** |

총괄 진행 로그: `RESEARCH_PROGRESS.md`.

---

## Phase 0 결과 — 754 후보 페어

| Stage | 방법 | 개수 |
|---|---|---:|
| A1. Macro event master | FMP economic_calendar + FRED indicators union | 123 events |
| A2. Kalshi 전체 시리즈 | 기존 inventory | 10,161 |
| A2. Macro Kalshi (rule match) | title regex + 공식 alias 사전 | 151 |
| B. CA × macro Kalshi 페어 | 63 CA × 151 Kalshi | 6,795 |
| B. Timing pass (lead ≥ 3d) | `lead = macro_cadence − ca_lag` | 5,664 |
| C. Mechanism verify (Haiku 4.5) | `{connected, channel, caveat}` JSON | 5,664 |
| **C. Final (connected=true)** | LLM 통과 | **754** |

- 754 후보가 사용하는 unique CA 데이터셋 35 종
- 페어별 가격: `docs/framework_prices.md` (단독 $50 이내 구매 가능 14 데이터셋 / 282 페어)

여기서 "lead_window_days" 는 *publication timing* — CA 가 매크로 발표 *후* 며칠 더 일찍 publish 되는가. **데이터 lead** (CA 변동이 매크로 변동을 시간순으로 leads) 와는 별개 개념이며, 후자는 페어별 실증으로만 확인 가능.

---

## Phase 5 결과 — 페어별 verdict

### Test 방법 (모든 페어 동일)

- CA 와 macro 둘 다 **YoY % change** 변환 (12개월 % 변화 → trend 제거)
- Pearson r 을 **lag ∈ [−2, +2] months** 에서 계산
- `best_lag` = \|r\| 가 최대인 lag
- n = 46~51 months (YoY 적용 후 obs 수)
- (verdict 기호 / 강도 정의는 위 §용어 참조)

### Direction 집계

| Dataset (측정 단위) | Aggregation | CA leads | Macro leads | Contemp |
|---|---|---:|---:|---:|
| **CA0030 Clickstream (사용자 수)** | SUM | 5 | **7** | 1 |
| | Mobile | **9** | 2 | 2 |
| **CA0056 Credit Card Spend ($)** | SUM | **6** | 5 | 2 |
| | Online | **10** | 1 | 2 |
| **CA0034 Instore POS Volume (건수)** | SUM | **10** | 3 | 0 |

### CA0030 Clickstream × 13 macros (SUM aggregation)

| Macro | Verdict |
|---|---|
| Retail Sales | ❌ Macro leads −1m, r=+0.75 [강] |
| NFP | ❌ Macro leads −1m, r=+0.68 [중] |
| PCE Price | ✅ CA leads +2m, r=+0.68 [중] (∗) |
| PPI | ❌ Macro leads −1m, r=+0.68 [중] |
| CPI | ❌ Macro leads −1m, r=+0.67 [중] |
| JOLTS Quits | ❌ Macro leads −1m, r=+0.65 [중] |
| Core CPI | ❌ Macro leads −1m, r=+0.61 [중] |
| New Home Sales | ✅ CA leads +1m, r=−0.61 [중] |
| UMich Sentiment | ✅ CA leads +1m, r=−0.50 [중] |
| Industrial Production | ⚪ Contemp, r=+0.46 |
| Durable Goods | ✅ CA leads +2m, r=+0.44 [약] (∗) |
| Personal Income | ❌ Macro leads −1m, r=−0.42 [약] |
| Housing Starts | ✅ CA leads +2m, r=−0.15 [약] (∗) |

→ **Verdict: 미지지** (7/13 Macro leads, 위 §가설 verdict 기준 적용). CA leads 로 나온 페어들도 부호가 negative (UMich/NHS) 또는 lag ±2 끝점에 몰려 의심.

### CA0056 Card Spend × 13 macros (SUM aggregation)

| Macro | Verdict |
|---|---|
| Retail Sales | ⚪ Contemp, r=+0.84 |
| PCE Price | ✅ CA leads +1m, r=+0.82 [강] |
| CPI | ✅ CA leads +1m, r=+0.82 [강] |
| PPI | ❌ Macro leads −2m, r=+0.81 [강] (∗) |
| NFP | ✅ CA leads +2m, r=+0.79 [강] (∗) |
| Core CPI | ✅ CA leads +2m, r=+0.76 [강] (∗) |
| JOLTS Quits | ❌ Macro leads −1m, r=+0.71 [강] |
| New Home Sales | ❌ Macro leads −2m, r=−0.60 [중] (∗) |
| Industrial Production | ✅ CA leads +1m, r=+0.59 [중] |
| UMich Sentiment | ❌ Macro leads −2m, r=−0.53 [중] (∗) |
| Personal Income | ✅ CA leads +2m, r=−0.52 [중] (∗) |
| Durable Goods | ❌ Macro leads −2m, r=+0.43 [약] (∗) |
| Housing Starts | ⚪ Contemp, r=+0.14 |

→ **Verdict: 부분 지지** (6/13 CA leads, 5/13 Macro leads, 둘 다 7 미만; PCE Price/CPI 가 \|r\|≈0.82 강 CA-leads 시그널). Online aggregation 만 보면 10/13 CA leads (압도). Retail Sales 는 r=0.84 의 강한 *contemp* 상관.

### CA0034 Instore POS Volume × 13 macros

| Macro | Verdict |
|---|---|
| **NFP** | **✅ CA leads +1m, r=+0.81 [강]** |
| **Personal Income** | **✅ CA leads +2m, r=+0.78 [강] (∗)** |
| **Core CPI** | **✅ CA leads +1m, r=+0.78 [강]** |
| UMich Sentiment | ✅ CA leads +2m, r=+0.61 [중] (∗) |
| PCE Price | ❌ Macro leads −2m, r=+0.59 [중] (∗) |
| CPI | ❌ Macro leads −2m, r=+0.57 [중] (∗) |
| JOLTS Quits | ✅ CA leads +2m, r=−0.51 [중] (∗) |
| Industrial Production | ✅ CA leads +2m, r=−0.40 [약] (∗) |
| Housing Starts | ✅ CA leads +2m, r=−0.33 [약] (∗) |
| Durable Goods | ✅ CA leads +2m, r=−0.31 [약] (∗) |
| PPI | ✅ CA leads +2m, r=−0.25 [약] (∗) |
| Retail Sales | ❌ Macro leads −2m, r=+0.18 [약] (∗) |
| New Home Sales | ✅ CA leads +2m, r=−0.08 [약] (∗) |

→ **Verdict: 잠정 지지** (10/13 CA leads ≥ 7 기준 충족, **NFP / Personal Income / Core CPI** 가 lag +1~+2 에서 r ≈ +0.8 강 시그널 ≥ 1 충족). n=46 으로 다른 dataset 보다 작지만 효과 크기 가장 큼.

### Caveats — 모든 verdict 에 동일 적용

- 2021-2026 윈도우는 *모든 시리즈가 nominal 상승 추세* → YoY 적용에도 common-trend 가 \|r\| 를 부풀릴 가능성. **detrended residual 에서도 lag pattern 살아남는지 미검증**
- (∗) 다수 — best_lag 가 ±2 끝점이면 진짜 peak 이 lag +3 이상일 수 있음. **lag ±4 까지 확장 미실시**
- 3 dataset × 평균 2.7 agg × 13 macros × 5 lag = **520+ comparisons** — Bonferroni / permutation test 미적용
- n=46~51 (YoY) → r=0.7 의 95% CI 가 [0.52, 0.83] 정도. 효과 *방향* 은 의미 있지만 *크기* 는 정밀도 부족
- **r ≠ causation**. Granger-causality test, OOS forecast 정확도 측정이 진짜 lead 검증 — 다 미실시

각 데이터셋별 다른 aggregation (Mobile/Online/Physical) 결과는 `docs/analysis_per_dataset.md`.

---

## 한계

- Phase 0 의 `lead_window_days` 는 publication timing 만 측정. **데이터 lead 와는 별개** (Phase 5 가 이 점을 드러냄)
- Phase 5 결과는 *3 데이터셋 × 13 macros* 의 lag 상관일 뿐. Granger-causality / OOS forecast 미실시 → trade-able edge 입증 아님
- 측정 단위 차이가 verdict 를 좌우 — user-count panel (CA0030) 은 panel-growth artifact 가 dominant, transaction-based panel (CA0056/0034) 만 의미 있음
- Stage C LLM verify 는 temperature=0 이지만 prompt-sensitive. 재실행 variance 직접 확인 안 됨
- 754 후보 중 borderline 46건 (entertainment/sports CA × 매크로) 은 Haiku 가 connected=true 통과시킴 — 수동 점검 후보
- CA 무료 sample 은 토픽당 100행 — Phase 1 EDA 통계는 sanity 수준 (CA0049 monthly n=20, COVID 제외 시 r 붕괴)

---

## 다음에 할 일

**즉시 가능 (추가 비용 0)** — 이미 산 3 framework 로:
1. Detrended residual 에서도 lag +1, +2 패턴 살아남는지 확인 (현재 \|r\| 가 common-trend 영향일 가능성)
2. Granger-causality test (statsmodels) 로 lead 방향 통계 검증
3. Lag ±4 또는 ±6 까지 확장 — lag +2 가 진짜 peak 인지 vs ±2 끝점에 우연 몰림인지
4. Out-of-sample forecast — 2021-2024 fit → 2025+ predict, baseline AR 대비 incremental 정확도 측정

**남은 promo ($5.59) 추가 구매**:
- CA0058 Card Health Spend 1y $4.99 — Medical CPI 검증 (CA0056 와 비교)
- 또는 CA0010 OTT Streaming 5y $4.99 — 엔터테인먼트 borderline 페어 검증

**검증 파이프라인 자체 보완**:
- Borderline 46 페어 수동 triage 또는 Sonnet 재실행으로 두 모델 합의만 채택
- Phase 2 `leadlag_scenarios.md` S1-S4 백테스트 — 단, Phase 5 의 lead 방향 검증 결과 반영 후

---

## 디렉토리

```
scripts/auto/                          ← Phase 0 자동 파이프라인 + Phase 4 가격 + Phase 5 분석
  s_a1_macro_list.py                   FMP + FRED → macro event master (123)
  s_a2_kalshi_macro_match.py           Kalshi 10,161 → macro 151 (rule + alias)
  s_b_timing.py                        63 CA × 151 Kalshi → timing pass 5,664
  s_c_mechanism_verify.py              Haiku 4.5 verify → 754
  s_d_v1_diff.py                       (legacy 비교용) 초기 수작업 39 페어 vs 자동 754
  s_report.py                          docs/verification_pairs_macro.md 생성
  s_e_price_all.py                     CarbonArc framework 가격 조회
  s_f_ca0030_full_check.py             Phase 5 — CA0030 × 13 macros × 3 aggregation lag corr
  s_g_multi_dataset_check.py           Phase 5 — CA0030/0056/0034 × 13 macros × multi-agg

scripts/                               ← Phase 1/3
  phase1_0_fetch_samples.py            무료 sample 100행 fetch
  phase1_eda.py                        sample × FRED 시계열 EDA
  phase3_smoke_test.py                 LLM 비정형 시그널 PoC E2E
  build_fred_cache.py                  FRED 시리즈 캐시
  cache_fred.py                        (early experiment, build_fred_cache 가 대체)

docs/
  verification_pairs_macro.md          Phase 0 메인 리포트 (754 페어 top-30)
  ca_datasets_in_verification_pairs.md 754 페어의 35 CA + sample row
  framework_prices.md                  Phase 4 가격표
  purchase_log.md                      Phase 5 실제 구매 기록 (3건)
  analysis_per_dataset.md              ← Phase 5 핵심 — 3 dataset × 13 macros 비교
  analysis_ca0030_umich.md             Phase 5 deep-dive (UMich anchor)
  analysis_ca0030_multi_macro.md       Phase 5 CA0030 단독 13-macro
  macro_matching_rules.md              Stage A2 alias 사전 (BLS/BEA/Census)
  leadlag_scenarios.md                 Phase 2 백테스트 디자인 (LightGBM + SHAP)
  llm_cost.md                          Phase 3 비용 envelope

prompts/ca_row_to_text.md              CA row → 1-sentence summary prompt

RESEARCH_PROGRESS.md                   진행 트래커 (`ANALYSIS.md`, `DATA.md` 는 초기 EDA 노트, 본 흐름과 독립)
```

`outputs/`, `_explore/` 는 `.gitignore` — script 로 재생성 가능한 데이터 / CarbonArc 원본 캐시 (TOS 상 비공개).

---

## 재현

### 의존성

```bash
pip install -r requirements.txt
```

`.env` (repo 미포함, 직접 작성):
```
ANTHROPIC_API_KEY=sk-ant-...     # Phase 0b Stage C + Phase 3
CARBONARC_API_KEY=eyJ...         # 무료 sample / Phase 4 가격 조회 / Phase 5 구매
FMP_API_KEY=...                  # Phase 0b Stage A1
```

### Phase 0 자동 파이프라인 (754 후보 추출 — 본 repo 핵심)

```bash
python3 scripts/auto/s_a1_macro_list.py
python3 scripts/auto/s_a2_kalshi_macro_match.py
python3 scripts/auto/s_b_timing.py                                      # _explore/datasets_non_webcontent.json 필요
python3 scripts/auto/s_c_mechanism_verify.py --model claude-haiku-4-5 --workers 12
python3 scripts/auto/s_report.py                                         # docs/verification_pairs_macro.md
python3 scripts/auto/s_e_price_all.py                                    # docs/framework_prices.md (Phase 4 가격)
```

런타임: Stage A·B ≈ < 1분, Stage C ≈ 15-20분 (5,664 페어 × 12 workers, Haiku 비용 ~$2-5), Stage E ≈ 3분 ($0).

### Phase 1 sample EDA (선택)

```bash
python3 scripts/phase1_0_fetch_samples.py     # _explore/samples/ 채움
python3 scripts/build_fred_cache.py           # outputs/fred/ 채움
python3 scripts/phase1_eda.py                 # outputs/eda/PHASE1_REPORT.md
```

### Phase 5 (구매 + 검증) 재현

3 framework 구매 (CA0030/0056/0034) 의 framework spec 은 `docs/purchase_log.md` 참조 — entity, insight ID, 날짜 범위, aggregate 다 명시됨. `buy_frameworks()` 호출은 현재 ad-hoc python 으로 진행됨. 구매 후 분석은:

```bash
python3 scripts/auto/s_g_multi_dataset_check.py    # 3 dataset × 13 macros lag corr
```

---

## License & Note

Private repo. CarbonArc 데이터는 비공개 (Insights Exchange API 로만 접근, 본 repo 에는 100행 sample 도 포함 X). 결과물은 alt-data feasibility research 이며 투자 자문이 아님.
