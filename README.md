# CarbonArc × Kalshi — Macro Pair Candidate Extraction

CarbonArc 의 대안 데이터가 미국 공식 매크로 발표를 시간순으로 *leads* 한다는 *가설* 을 데이터로 검증해 보려고 한다. 검증을 시작하려면 먼저 "검증해 볼 만한 (CA dataset, Kalshi market) 페어" 의 list 가 필요하다. **이 repo 가 만드는 것은 그 list 이지 가설의 입증이 아니다.**

## 현재 상태 (3줄)

1. **후보 페어 754개 추출 완료** — 10,161 Kalshi 시리즈 × 63 CA 데이터셋 → cheap-first 자동 필터링 후 754개 (`docs/verification_pairs_macro.md`).
2. **실증 1차 시도 (1개 데이터셋, $4.99)** — CA0030 Clickstream 5년치 구매 후 13개 매크로 × 3 aggregation 으로 lag correlation 검사.
3. **그 1개에서는 가설 미지지** — 13 macros 중 7개가 *매크로가 CA 를 leads* 의 정반대 방향 (\|r\| 0.6-0.75). Aggregation 에 따라 부호 뒤집힘 = panel 구조 artifact 의 신호. **다른 데이터셋 (특히 card transaction volume) 에서 재검증 필요**.

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
| 0a (manual v1) | 21 CA × 66 Kalshi 수작업 매핑 → 39 페어 | `outputs/leadlag_candidates.csv` | 완료, 0b 가 대체 |
| **0b (automated v2)** | **cheap-first 자동 파이프라인 → 754 후보** | **`scripts/auto/`, `docs/verification_pairs_macro.md`** | **완료, 본 repo 핵심** |
| 1 (sample EDA) | 무료 100행 sample 로 시계열 sanity check | `outputs/eda/PHASE1_REPORT.md` | 완료, statistical evidence 수준 아님 |
| 2 (scenario design) | 4-scenario 백테스트 디자인 (LightGBM + SHAP) | `docs/leadlag_scenarios.md` | 디자인만, 실행 X |
| 3 (LLM unstructured PoC) | CA row → text → Kalshi search 파이프라인 | `prompts/ca_row_to_text.md`, `docs/llm_cost.md` | smoke test 통과 |
| 4 (framework 가격 조사) | 35 unique CA dataset 의 framework 가격 매트릭스 (1y/3y/5y) | `docs/framework_prices.md`, `scripts/auto/s_e_price_all.py` | 완료 |
| **5 (1차 구매 + 실증)** | **CA0030 Clickstream 5y $4.99 구매 → 13 매크로 × lag corr × 3 aggregation** | **`docs/purchase_log.md`, `docs/analysis_ca0030_multi_macro.md`** | **완료, 가설 미지지** |

총괄 진행 로그: `RESEARCH_PROGRESS.md`.

---

## Phase 0b 결과 — 754 후보 페어

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
- v1 의 39 페어 중 26 페어 재현 (66.7%), 13 페어는 v2 가 reject
- 페어별 가격: `docs/framework_prices.md` (단독 $50 이내 구매 가능 14 데이터셋 / 282 페어)

여기서 "lead_window_days" 는 *publication timing* — CA 가 매크로 발표 *후* 며칠 더 일찍 publish 되는가. **데이터 lead** (CA 변동이 매크로 변동을 시간순으로 leads) 와는 별개 개념이며, 후자는 페어별 실증으로만 확인 가능.

---

## Phase 5 결과 — 1차 실증에서 가설 미지지

CA0030 Clickstream 5년치 monthly US (`outputs/auto/ca0030_clickstream_us_monthly_5y.csv`, $4.99) 구매 후 **13 macros** (UMich, Retail Sales, NFP, CPI, Core CPI, PCE Price, INDPRO, Durable Goods, Housing Starts, New Home Sales, JOLTS Quits, PPI, Personal Income) 와 lag correlation 검사. YoY % change 변환.

**Direction 집계 (SUM aggregation, 13 macros)**:

| | 개수 | 평균 \|r\| | 대표 |
|---|---:|---:|---|
| Macro leads CA (lag < 0) | **7** | 0.61 | Retail Sales (r=+0.75 at lag −1), NFP, CPI, PPI, Core CPI 등 |
| Contemporaneous (lag 0) | 1 | 0.46 | Industrial Production |
| CA leads (lag > 0) | 5 | 0.49 | UMich, New Home Sales (negative), PCE, Durable Goods |

**관찰**:
- 다수 macro (7/13) 가 *반대 방향* (매크로 가 CA leads). \|r\| 도 평균 더 큼.
- **Aggregation 에 따라 부호 뒤집힘**: Desktop 은 9/13 Macro leads (panel 성장 4.7x); Mobile 은 9/13 CA leads (panel 4.9x). 깨끗한 시그널이라면 aggregation 영향 없어야 함 → **데이터 구조 artifact 의 신호**
- UMich + New Home Sales 만 모든 aggregation 에서 CA-leads negative — 둘 다 같은 기간 *하락 추세* (UMich 79→53, NHS 변동). CA panel 의 상승 추세와 trend 부호 mismatch 가 만든 *trend artifact* 일 가능성 큼

**결론**: CA0030 한 데이터셋에서는 lead-lag 가설 지지 안 됨. 1차 시도 (3 macros 만 본 분석) 의 "UMich 에서 CA leads" 가 cherry-pick 이었음을 13 macros 확장이 보여줌.

상세: `docs/analysis_ca0030_umich.md` (1차, 3 macros, outdated) → `docs/analysis_ca0030_multi_macro.md` (13 macros 갱신본).

---

## 한계

- Phase 0b 의 `lead_window_days` 는 publication timing 만 측정. **데이터 lead 와는 별개** (Phase 5 가 이 점을 드러냄)
- Phase 5 의 negative 결과는 *데이터셋 1건* 의 결과. panel-growth confound 가 적은 다른 데이터셋에서 가설 재검증해야 일반화 가능
- Stage C LLM verify 는 temperature=0 이지만 prompt-sensitive. 재실행 variance 직접 확인 안 됨
- 754 후보 중 borderline 46건 (entertainment/sports CA × 매크로) 은 Haiku 가 connected=true 통과시킴 — 수동 점검 후보
- CA 무료 sample 은 토픽당 100행 — Phase 1 EDA 통계는 sanity 수준 (CA0049 monthly n=20, COVID 제외 시 r 붕괴)

---

## 다음에 할 일

**즉시 가능 (추가 비용 0)** — 이미 산 CA0030 데이터로:
1. Desktop / Mobile platform 별도 lag corr — Desktop 의 panel growth 영향 적은 Mobile 만 단독으로
2. Granger-causality test 로 lead 방향 통계 검증
3. 같은 데이터로 추가 매크로 (Core PCE / Industrial Production / Housing Starts) lag corr — UMich 만 다른 부호인 게 sentiment-specific 인지 trend artifact 인지 분리

**다음 framework 구매** ($45.01 promo 잔존):
- 최우선 후보: **CA0056 Card Spend US 7y monthly $19.30** — card transaction 은 panel size 의 직접 함수가 아닌 거래 금액이므로 panel-growth confound 가 작을 *것으로 추정*. Phase 0b 의 다른 anchor 페어 (× Census Retail Sales) 임. CA0030 에서 reverse direction 이 나왔으니 카드에서도 같은지 / 다른지 확인 필요
- 차선: CA0077 Commodity 1y $22.96 — commodity 가격은 panel-size 와 무관 (가격 자체) 이라 더 깨끗한 lead-lag 테스트 가능

**검증 파이프라인 자체 보완**:
- Borderline 46 페어 수동 triage 또는 Sonnet 재실행으로 두 모델 합의만 채택
- Phase 2 `leadlag_scenarios.md` S1-S4 백테스트 — 단, Phase 5 의 lead 방향 검증 결과 반영 후

---

## 디렉토리

```
scripts/auto/                          ← Phase 0b 자동 파이프라인 + Phase 4 가격 조회
  s_a1_macro_list.py                   FMP + FRED → macro event master (123)
  s_a2_kalshi_macro_match.py           Kalshi 10,161 → macro 151 (rule + alias)
  s_b_timing.py                        63 CA × 151 Kalshi → timing pass 5,664
  s_c_mechanism_verify.py              Haiku 4.5 verify → 754
  s_d_v1_diff.py                       v1 39쌍과의 diff
  s_report.py                          docs/verification_pairs_macro.md 생성
  s_e_price_all.py                     CarbonArc framework 가격 조회
  s_f_ca0030_full_check.py             Phase 5 — CA0030 × 13 macros × 3 aggregation lag corr

scripts/                               ← Phase 1/3 + 0a legacy
  phase1_0_fetch_samples.py            무료 sample 100행 fetch
  phase1_eda.py                        sample × FRED 시계열 EDA
  phase3_smoke_test.py                 LLM 비정형 시그널 PoC E2E
  build_fred_cache.py                  FRED 시리즈 캐시
  cache_fred.py                        (early experiment, build_fred_cache 가 대체)
  phase0_*.py                          (0a legacy) 수작업 v1 검증쌍 도출

docs/
  verification_pairs_macro.md          Phase 0b 메인 리포트 (754 페어 top-30)
  ca_datasets_in_verification_pairs.md 754 페어의 35 CA + sample row
  framework_prices.md                  Phase 4 가격표
  purchase_log.md                      Phase 5 실제 구매 기록
  analysis_ca0030_umich.md             Phase 5 1차 분석 + 자체 비판
  analysis_ca0030_multi_macro.md       Phase 5 multi-macro inversion
  macro_matching_rules.md              Stage A2 alias 사전 (BLS/BEA/Census)
  leadlag_scenarios.md                 Phase 2 백테스트 디자인 (LightGBM + SHAP)
  llm_cost.md                          Phase 3 비용 envelope

prompts/ca_row_to_text.md              CA row → 1-sentence summary prompt

ANALYSIS.md / DATA.md                  초기 EDA / Kalshi inventory 메모 (Phase 0a 시대)
RESEARCH_PROGRESS.md                   진행 트래커
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

### Phase 0b 자동 파이프라인 (754 후보 추출 — 본 repo 핵심)

```bash
python3 scripts/auto/s_a1_macro_list.py
python3 scripts/auto/s_a2_kalshi_macro_match.py
python3 scripts/auto/s_b_timing.py                                      # _explore/datasets_non_webcontent.json 필요
python3 scripts/auto/s_c_mechanism_verify.py --model claude-haiku-4-5 --workers 12
python3 scripts/auto/s_d_v1_diff.py
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

### Phase 5 (1차 구매 + 검증) 재현

`scripts/auto/s_e_price_all.py` 의 `buy_frameworks` 호출 부분을 별도 스크립트로 분리해야 함 (현재는 ad-hoc Python). 자세히는 `docs/purchase_log.md` 의 framework spec 참조.

---

## License & Note

Private repo. CarbonArc 데이터는 비공개 (Insights Exchange API 로만 접근, 본 repo 에는 100행 sample 도 포함 X). 결과물은 alt-data feasibility research 이며 투자 자문이 아님.
