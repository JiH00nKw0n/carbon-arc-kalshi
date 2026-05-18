# Framework Purchase Log

CarbonArc framework 구매 기록. 실제로 promo balance 가 차감된 거래만 기록.

## #1 — CA0030 Clickstream US 5y monthly  (2026-05-15)

| | |
|---|---|
| order_id | `3a1c7576-5f98-451b-a1dd-87f669f6b98e` |
| framework_id | `ad4816c2-907d-4981-b69a-1beb3e9a536a` |
| price | **$4.99** |
| records | 3,892 (full); 128 returned after aggregate (64mo × 2 platforms) |
| insight | `381` Website Users |
| entity | `carc_id=96` United States of America (country) |
| date_range | 2021-01-01 → 2026-04-30 |
| date_resolution | monthly |
| location_resolution | us |
| aggregate | mean |
| columns | date, entity_name, platform_name, website_users, entity_representation |
| ontology_version | 2026.5.1 |
| local file | `outputs/auto/ca0030_clickstream_us_monthly_5y.csv` (gitignored) |

### 선택 근거

- 754 검증쌍에 등장한 35 CA 데이터셋 중 **단위 $ 당 페어 수 최고** ($0.12/pair 3y)
- **CA0030 × KXUMICHOVR (UMich Consumer Sentiment) anchor 페어** 포함
- 1y / 3y / 5y 모두 $4.99 동일 → 5년 풀로 구매
- 19 unique 매크로 이벤트 cover (sentiment / CPI / PCE / NFP / Housing / Industrial 등)

### 데이터 첫인상

- 64 months × 2 platforms (Desktop Site, Mobile Site) = 128 rows
- website_users 5년간 5.17x 성장 (166K → 860K) — 데이터 패널 자체가 늘어난 trend
- UMich Sentiment 같은 기간 79 → 53 으로 하락 (소비자 심리 악화)

### Anchor 검증: CA0030 × UMich Sentiment (n=63 overlap)

De-trending 별 lag +1 (CA leads UMich by 1 month) 상관:

| Method | n | r at lag +1 |
|---|---:|---:|
| Raw levels | 63 | **−0.591** |
| MoM first-difference | 62 | **−0.342** |
| YoY % change | 51 | **−0.504** |
| Linear detrended | 63 | **−0.454** |

**부호 = negative** — web clickstream 늘 때 1달 뒤 UMich sentiment 떨어짐.

가능한 메커니즘:
1. **Anxious browsing**: 경제 불안 시 소비자가 구매 결정 미루고 더 검색
2. **Research-mode**: 낮은 sentiment 가 cheap-substitute 검색 증가시킴
3. **Reverse causality 검토 필요**: lag 0 (−0.48 YoY) 도 강해서 contemporaneous 효과 무시 못함

검증 가능한 후속 (이 framework 한 건으로 가능한 42 페어):
- vs Census Retail Sales (FRED)
- vs Core PCE (FRED)
- vs ADP Employment / NFP
- vs Housing Starts / Existing Home Sales
- vs Industrial Production
- vs Durable Goods Orders
- (다른 36 페어 — `docs/verification_pairs_macro.md` 참조)

### Phase 1 EDA vs full panel — 결정적 차이

| | Phase 1 sample (CA0049 Medline, n=20) | Full panel (CA0030, n=63) |
|---|---|---|
| Raw r at lag +1 | −0.79 | −0.59 |
| COVID 핵심 3개월 제외 시 | **r=−0.19 (붕괴)** | **r=−0.68 (오히려 강화)** |
| Detrending 효과 | 측정 안 함 (n 너무 작음) | r=−0.45 유지 |
| YoY % change | 측정 불가 (gap 많음) | r=−0.50 |

→ **Phase 1 의 r=−0.79 가 COVID 공통충격이었던 반면, 풀패널 CA0030 의 시그널은 detrending + 비COVID 윈도우 다 통과.** 

### 남은 promo

$50.00 → **$45.01** (예상, balance API 미확인). 잔액으로 추가 framework 구매 가능 (예: CA0056 7y $19.30, CA0077 1y $22.96).

---

## #2 — CA0056 Credit Card Spend US 5y monthly (2026-05-18)

| | |
|---|---|
| order_id | `1cc82c16-e3b9-4cd1-871c-b3e77cf7a7bc` |
| framework_id | `4cd55f20-af20-4cc5-9534-b1357397ff73` |
| price | **$14.03** |
| records | 3,892 (full); 128 returned (64mo × 2 transaction methods: Online / Physical) |
| insight | `626` Credit Card Spend |
| entity | US country (carc_id 96) |
| date_range | 2021-01-01 → 2026-04-30 |
| aggregate | sum |
| local file | `outputs/auto/ca0056_card_spend_us_monthly_5y.csv` (gitignored) |

선택 근거: Transaction $ 기반 → panel-growth 영향 약함 (사용자 수가 아니라 거래 *금액*). CA0030 panel artifact 가설의 deflator. 분석 결과는 `docs/analysis_per_dataset.md`.

## #3 — CA0034 Instore POS Volume 5y monthly (2026-05-18)

| | |
|---|---|
| order_id | `5ba83dee-a10f-42b3-a3e3-d66b0c334a0e` |
| framework_id | `848f1b07-5341-441f-9f37-bb5ea0a783c3` |
| price | **$25.39** |
| records | 1,765 (full); 58 returned (single series, 2021-07 ~ 2026-04) |
| insight | `400` POS Volume (Instore Core Panel) |
| entity | US country (carc_id 96) |
| date_range | 2021-01-01 → 2026-04-30 (actual data starts 2021-07) |
| aggregate | sum |
| local file | `outputs/auto/ca0034_pos_instore_us_monthly_5y.csv` (gitignored) |

선택 근거: Transaction volume (건수) — panel-size 의 직접 함수 아님. CA0034 는 754 페어 중 55개로 페어 수 최다 + 매크로 다양성 15.

## 누적

| | |
|---|---|
| Total spent | **$44.41** |
| Promo balance | **$5.59** (≈ 1 추가 framework 한도) |

## 향후 구매 후보 (남은 $5.59 로)

| 후보 | 윈도우 | 가격 | 페어 | 비고 |
|---|---|---:|---:|---|
| CA0058 Card Health Spend | 1y monthly | $4.99 | 18 | Medical CPI 검증 |
| CA0010 OTT Streaming | 5y monthly | $4.99 | 6 | 엔터테인먼트 borderline 검증 |
| CA0030 추가 1y | (이미 산 거 외) | n/a | — | 같은 데이터셋 추가 구매는 의미 X |

(전체 가격표: `docs/framework_prices.md`)
