# EXPERIMENT SPEC — alt-data × earnings-call × LLM → revenue surprise

> **단일 진실 원천(SSOT).** 모든 factor(F3=card, F1=web, 후보=foot/imports/exports)는 **이 문서의 세팅을
> 글자 그대로 동일하게** 따른다. 디자인 선택은 전부 *근거(justification)*와 함께 명시한다 — 정당화 못 하는
> 선택은 쓰지 않는다. 상태: **DRAFT v0 — 사용자 승인 전. 승인 전까지 실험 실행·데이터 구매 금지.**

---

## 0. 연구 질문 · 가설

- **Q.** 정형 대체데이터(X)와 어닝콜 텍스트(Z)를 LLM으로 결합하면, 각각/전통기법보다 **매출 서프라이즈(Y)**를 더 잘 *예측*하는가.
- **H1 (연관):** X 단독이 Y와 유의하게 연관된다.
- **H2 (보완, corr & MSE 양쪽):** 초가산 synergy를 **두 지표로** 검증 — (a) `corr(X+Z) > corr(X)+corr(Z) − base`, (b) **MSE 기반** `skill(X+Z) > skill(X)+skill(Z) − skill(base)` (skill = `1 − MSE/MSE_naive`, R²류). **두 지표 모두 super-additive여야 H2 지지.**
- **H3 (예측력):** 결합모델의 **OOS 예측오차(RMSE)**가 전통 baseline보다 작다.
- 주장 단위 = **예측(prediction)**이므로 **주지표는 MSE/RMSE** (상관은 보조).

## 1. X (대체데이터) — 후보 채널

**Z(어닝콜 transcript)와 Y(매출 서프라이즈)는 고정**하고 **X(대체데이터)만 채널별로 교체**한다.
*("factor"는 부적절한 표현 — X는 하나의 alt-data 채널이고 후보가 여러 개일 뿐이다.)*

| X 채널 | 데이터셋 | 상태 |
|---|---|---|
| **Card spend** | CA0056 (insight 626) | **진행** — 기존 35종목; O/X 스크린 **O=100**(strong 81+moderate 19) |
| **Web traffic** | CA0030 (insight 381, Desktop+Mobile site, **앱 제외**) | **진행** — 33종목 클린 |
| Foot traffic | CA0060 (insight 45862) | 후보 — 미구매 |
| Imports | CA0040I (insight 586) | 후보 — 미구매 |
| Exports | CA0040E (insight 589) | 후보 — 미구매 |

- 사용자 지정 alt-data 후보 4종 = **Web · Foot · Imports · Exports**; Card는 최초 baseline. 현재 **2종(Card·Web) 진행 중**.
- 디렉터리명 `factor1/`(web)·`factor3/`(card)는 레거시이며, 개념상으론 "X 채널"이다.

## 2. 유니버스 선택 (모든 factor 공통 절차)

1. **O/X 스크린:** 해당 alt-data가 회사 **전체 매출의 주요 동인**인지 티커별로 판정 → `strong-O / moderate-O / X`.
   **산출물(committed) = `factor1/data/altdata_ticker_screen.csv`** — **5채널(card/web/foot/imports/exports) 합본, 423행** (전문가 에이전트 스크린 → 적대적 감사 → borderline은 FactSet/FMP 매출믹스로 검증).
   - 컬럼: `data_type, ticker, company, impact(O/X), strength(strong/moderate/weak), est_share, available_company_level, carbonarc_dataset, reason`.
   - O 개수(채널별): **card 100 · foot 59 · imports 50 · web 39 · exports 16**.
   - 이 파일은 **`factor1/data/` 중 유일하게 git에 커밋**되는 산출물(O/X 판정+근거 = 우리 분석물, 라이선스 raw 데이터 아님). 나머지 `factor1/data/`(FactSet·Carbon Arc·transcripts)는 gitignore.
2. **매수 대상 = O 티커**(strong-O ∪ moderate-O). 구매 전 `check_framework_price`로 **가격 보고 → 사용자 컨펌 → 매수**.
3. 결과는 **전체 + 티어별(strong/moderate) 분리** 보고.
   - *근거:* alt-data가 매출을 지배하지 않는 회사(X)에서 null이 나와도 "데이터 무용"이 아니라 "그 회사 매출이 그 채널이 아님"이라 검정이 오염됨 → 지배 종목으로 한정해야 공정.

### 2.1 Screening agent prompts (verbatim, reproducible)

Two agents per channel. `{CHANNEL}`, `{MEASURES}` (what the data measures), `{O_MEANS}`, and `{SECTORS}` (candidate sectors to consider) are filled per channel from the table below. `{HOUSE}` = the 35 card tickers (§1 card set).

**Screener** (effort=medium, structured output):
> You are an equity analyst screening US-listed companies for whether {CHANNEL} is a dominant driver of TOTAL revenue.
> WHAT IT MEASURES: {MEASURES}
> "O" MEANS: {O_MEANS}
> "X" MEANS: {CHANNEL} is NOT a dominant revenue driver — a minority channel (<~40% of revenue), B2B, or unrelated.
> Consider broadly (not exhaustive): {SECTORS}. Also explicitly screen every name in the house universe: {HOUSE}.
> Produce a comprehensive per-ticker table (38–60 rows): cover the clear O's thoroughly, plus representative X / borderline names. For each ticker give impact (O/X), strength (strong/moderate/weak), est_share (rough channel share of revenue), and a SPECIFIC one-line reason grounded in the company's revenue mix. Judge against TOTAL revenue; a real-but-minority (<~40%) channel → impact X, strength moderate. Verify uncertain O calls with fmp_financials / fmp_company / web_search. Return ONLY the structured object.

**Auditor** (effort=high, adversarial): receives the screener's JSON draft and returns the FINAL corrected list — (1) fix mis-calls (O where the channel is not actually a majority revenue driver → X), (2) catch measurement traps (app vs web; wholesale vs DTC; franchise system-sales vs reported revenue; B2B), (3) add missing obvious O names, (4) dedupe + tighten est_share/reason. Verify uncertain claims with the same tools.

Output schema: `{ticker, company, impact:"O"|"X", strength:"strong"|"moderate"|"weak", est_share, reason}`.

**Per-channel fills of `{MEASURES}` and `{SECTORS}`:**

| channel | `{MEASURES}` | `{SECTORS}` (candidates) |
|---|---|---|
| **Card** (CA0056) | Consumer credit/debit card-spend at the merchant — the $ value of consumer card transactions attributed to the company. | restaurants/QSR, brick & e-com retail, grocery/convenience, online marketplaces, consumer travel/mobility, consumer subscriptions/streaming, DTC brands. X-type: wholesale-led brands, B2B, banks, industrials, enterprise SaaS, healthcare providers, ad-funded, payment networks. |
| **Web** (CA0030) | Website users (Desktop + Mobile **site / browser**); the **app is EXCLUDED**. Top-of-funnel online-demand proxy. | online/e-commerce pure-plays, online travel/marketplaces with heavy web booking, DTC-heavy brands; physical/omnichannel names for contrast. |
| **Foot** (CA0060) | Modeled **physical visits** (mobile geolocation) to company-operated retail/restaurant/venue locations. Visit-volume proxy. | restaurants/QSR, big-box/brick retail, grocery/convenience/gas, gyms/experiences, casinos, theme parks/cinema, drug retail. |
| **Imports** (CA0040I) | US **import** customs bill-of-lading value/count by the **importer of record** (finished goods INTO the US). | furniture/home, apparel/footwear brands, discount/dollar/off-price, toys, consumer-electronics retail, auto parts, tires, appliances/tools. |
| **Exports** (CA0040E) | US **export** customs bill-of-lading value/count by the **exporter of record** (US-produced goods OUT of the US). | agriculture/grains/protein, fertilizer/ag-chem, energy/LNG/refined, coal, chemicals/plastics, industrial machinery, aerospace, metals/forest. |

Full verbatim workflow scripts: `altdata-ticker-screen`, `card-oxscreen`.

## 3. 변수 정의 (정당화 포함)

### X — 대체데이터
- 회사별, 월간(web) 또는 분기(card). **변환 = YoY** = `pct_change(12 months)` 또는 `pct_change(4 quarters)`.
  - *근거:* 계절성 제거 + scale-free. 패널-성장 artifact(레벨)와 분리.
- 분기 정렬: `merge_asof(direction="nearest", tolerance=45d)`로 fiscal-quarter-end에 매핑(offset-FY 안전).
- 보조 변환 = `web_yoy_3m`(3개월 평균 YoY). **기각: `accel`(YoY−추세)** — F1에서 무신호(p>0.7), 사전등록상 보조로만.

### Y — 매출 서프라이즈 (point-in-time)
- `surprise_early = (ACTUAL − CONS_EARLY)/CONS_EARLY`.
- `ACTUAL` = FactSet `FE_BASIC_ACT_QF`, `FE_ITEM='SALES'`.
- `CONS_EARLY` = `FE_BASIC_CONH_QF` 컨센서스 스냅샷 중 **`CONS_END_DATE ≤ fiscal_quarter_end + 7d`**의 최신값.
  - *근거:* **발표 후 컨센서스 수정 누설 차단** + alt-data 가용 시점(분기말 직후)과 정합. (표준 PIT beat/miss; FactSet 문서 §point-in-time.)
- 보조: `surprise_print` = `CONS_END_DATE < REPORT_DATE`의 최신(발표 직전 컨센서스).

### Z — 어닝콜 텍스트
- **직전분기 콜** = `event_date ≤ report_date − 31d`인 가장 최근 콜.
  - *근거:* Q-1 콜(발표 전, point-in-time), 31일 버퍼로 offset-FY에서도 같은분기 콜 오매핑 방지.
- 발견: `stock_documents`(linq) `doc_type='earnings_call' AND file_key LIKE '%_corrected.html' AND fiscal_date IS NOT NULL`(← 컨퍼런스 발표 제외). 다운로드: S3 `$AWS_S3_BUCKET_NAME`.
- **텍스트화 = `html_to_text`**: `<script>/<style>` 블록 제거 → **모든 `<태그>` 제거** → HTML 엔티티 unescape → 공백 정리. (저장본 `.txt`에 **HTML 태그 0개** 검증 완료.) 이후 **48,000자 절단**(`MAX_TRANSCRIPT_CHARS`).
- 동명 외국기업 충돌(PETS/REAL/ZIP 등)은 미국 발행사 이름으로 필터.

## 4. 누설 통제 (모든 factor 동일)

- **LLM 평가표본 = `report_date > 모델 지식컷오프`** (gpt-5.5-2026-04-23 → **2025-12-01**). 코드 `assert`로 강제.
- **전통(OLS/naive)** = `report_date ≤ 컷오프`로 **적합(train)** → **컷오프 이후로 예측(test)**. → LLM과 **동일 test 표본**, 동일 누설 프레임.
- 모든 입력 point-in-time(과거만). f1_02식 *상관·인과*는 전체 패널 사용(예측 아님, 암기 무관)이며 **별도 표기**.

## 5. 모델 (전부 **동일한 n-matched test 표본**에서 평가)

> **n-matching 규칙:** test 이벤트 = `{X_yoy, FactSet surprise, 직전콜 transcript, 과거 ≥3분기, lag_surprise}` **전부 존재**하는 post-cutoff 이벤트의 교집합. 모든 모델(전통+LLM)이 **정확히 같은 이벤트 집합**에서 평가됨. factor별 n을 명시.

**전통 (pre-cutoff 적합 → post-cutoff 예측):**
- `N0 naive` = 회사별 과거 서프라이즈 평균(track record).
- `N1 X-OLS` = `surprise ~ X_yoy`.
- `N2 sent-OLS` = `surprise ~ 감성점수(직전콜)`.
- `N3 X+sent`, `N3b X+sent+lag` (lag = 직전분기 서프라이즈).

**감성점수 (N2/N3/N3b) — 사전·전처리·출처 명시 (paper-grade):**
- **사전 = Loughran-McDonald Master Dictionary (1993–2025, 2026-03 갱신)** — 금융 텍스트(10-K·어닝콜) 감성의 도메인 표준.
  - 출처: 사용자 제공 Google Drive CSV (= LM Master Dictionary) ⇄ 정본 `https://sraf.nd.edu/loughranmcdonald-master-dictionary/`.
  - 로컬: `lm_master_dictionary.csv` (루트, 9.1MB, **gitignore** — 공개·재생성가능) → 전처리 `lm_sentiment.json` (루트, 카테고리별 소문자 단어목록).
- **멤버십 규칙 = 카테고리 컬럼 값 `> 0`** (값 = 단어가 *추가된 연도*; **음수 = 제거된 연도 → 제외**, SRAF 명시). 결과 **Positive 347 / Negative 2345** 단어. (`!= 0` 규칙은 제거단어 17개를 오포함[354/2355] → **폐기**.)
- 점수 = `net = (#pos − #neg)/(#pos + #neg)` (콜당). 전처리: 소문자화, 단어경계 토큰화, 구두점 strip 후 LM 소문자 목록과 매칭.
- v0 **미적용(명시적 기본값)**: negation 처리·tf-idf 가중·기타 카테고리(uncertainty/litigious/modal/constraining은 JSON에 보관만, N2 점수엔 미사용).
- 인용: **Loughran, T. & McDonald, B. (2011), "When is a Liability not a Liability? Textual Analysis, Dictionaries, and 10-Ks," *J. Finance* 66(1):35-65.** 라이선스: **학술연구 무료** (상용 → loughranmcdonald@gmail.com); 본 연구 = 학술.
- *근거:* 임의 손선택 리스트(폐기) 대신 공개·인용가능·표준 사전으로 정당화.

**LLM (`gpt-5.5-2026-04-23`, reasoning effort=medium, structured output, zero-shot):**
- 4-arm ablation: `fin / fin+X / fin+text / fin+X+text`. 동일 재무표(`HIST_ROWS=6`).
- 아키텍처: `A`(text→score) / `C`(X+text→features) / `B`(end-to-end float). *근거:* "증류 점수 vs end-to-end" (F3 시그니처).
- 프롬프트·시스템문구는 factor 간 X 라벨만 교체, 그 외 동일(`f1_llm.py`/`f1_05`/`f1_07`).

## 6. 지표 (**주지표 = MSE/RMSE**)

| 지표 | 정의 | 역할 |
|---|---|---|
| **RMSE** | `sqrt(mean((pred−true)²))` (단위 %, OOS) | **주** |
| **R²_OOS** | `1 − SSE/SST` (= 1 − MSE/Var) | **주** |
| corr²(보정상한) | Pearson corr² = 최적 선형 재척도 시 달성가능 R² | 정보 vs 보정 분리 |
| corr, sign-hit, MAE | — | 보조 |

- *주의:* LLM 출력은 미보정 %라 raw RMSE에서 불리. **raw RMSE/R²와 corr²(보정상한)을 함께** 보고해 *정보력*과 *보정*을 분리. OLS는 SSE-적합이라 raw가 곧 보정후. 이 비대칭을 표에 명시.
- **인풋-매칭 주의(중요):** OLS(가공 스칼라) vs LLM(raw 표+텍스트)은 *인풋이 다름* → "동일인풋 모델비교" 아님, **시스템 대 시스템** 비교로 라벨. 추가로, 텍스트 제외 *구조화-only*에서 `LLM(fin+X)` vs `OLS(동일 구조화 피처: X 6분기+lag들+컨센성장률)`로 **인풋-매칭 비교**를 별도 제공.

## 7. 검증 (모든 factor 동일)

- **#1 shuffle-company surrogate** — firm-specific vs 공통추세 artifact.
- **#3 company-clustered bootstrap (5000)** — 초가산 synergy를 **corr·MSE-skill 양쪽**에서 + 결합 절대 예측력(RMSE/R²) CI.
- **Z-depth** — 직전 1콜 vs 2콜.
- 게이트(상관·인과 H1): `p_boot<0.05 AND p_surr<0.05`.

## 8. 재현성

- **난수 시드 = 2026 (전 실험 단일 고정)**: bootstrap·shuffle-company surrogate·label-permutation 전부 `np.random.default_rng(2026)`. 패키지: openai 2.43 / boto3 1.43 / pydantic 2.13 / pandas.
- 라이선스 데이터(FactSet/CarbonArc/transcripts)는 **gitignore**(`factor1/data`,`factor3/data`,`**/transcripts`). 코드/스크립트로 재생성(쿼리·API 문서화). 비밀·버킷명은 `.env`.

## 9. 미결 결정 (사용자 컨펌 필요)

1. **유니버스 = strong-O만 vs O 전체(strong+moderate)?** (현재 F1은 O 전체 39 매수)
2. **card 추가 매수?** card도 O/X 스크린 → card-O 전체 매수할지. **개수·가격 먼저 산출·보고 → 컨펌 후 매수.**
3. **LM 사전 negation/카테고리 처리** v0 미적용으로 고정 OK?
4. **LLM MSE 보정** = raw + corr²(보정상한) 2개 보고로 충분한지(별도 OOS 보정셋은 LLM pre-cutoff 예측이 누설이라 불가).

---
*변경 이력: v0 (2026-06-28) 초안.*
