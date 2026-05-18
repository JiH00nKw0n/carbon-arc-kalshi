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
- 19 unique 매크로 이벤트 cover (sentiment / CPI / PCE / NFP / Housing / Industrial 등)
- 1y / 3y / 5y 모두 $4.99 동일 → 5년 풀로 구매
- **CA0030 × KXUMICHOVR (UMich Consumer Sentiment)** 가 Phase 0 의 anchor 페어 중 하나

### 데이터 shape

- 64 months × 2 platforms (Desktop / Mobile) = 128 rows
- website_users: 166K → 860K (5.17x 성장 over 5y) — **panel onboarding 추세, 미국 인터넷 사용량 증가가 아님**

### 검증 결과

13 macros 와 multi-aggregation lag corr 검증 → **가설 미지지** (Macro leads CA 7/13, panel-growth artifact). 자세히는 `docs/analysis_per_dataset.md` (3-dataset 비교) + `docs/analysis_ca0030_multi_macro.md` (CA0030 단독 deep-dive).

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
