# Framework Prices — 754 검증쌍 × CarbonArc cost

> Stage E (`scripts/auto/s_e_price_all.py`) 산출물. `outputs/auto/verification_pairs_macro.csv` 의 754 페어가 쓰는 35개 unique CA 데이터셋에 대해 `check_framework_price` 호출 결과 (promo 차감 X).

## 요약

- **Total unique CA datasets**: 35
- **Successfully priced @ 3y monthly US**: 19
- **Under $50 @ 3y monthly US**: 14 datasets, covering 282 pairs
- **No national rollup priceable**: 15 datasets (entity-level만 가능; 별도 견적 필요)
- **Promo balance**: $50.00 → $5.59 (Phase 5 에서 $44.41 사용, 자세히는 `purchase_log.md`)

## 가격 모델 메모

- CarbonArc 가격 = **framework 단위** (= dataset 슬라이스 + entity + 기간 + aggregate).
- 동일 dataset 의 day/week/month resolution 은 같은 row 수 → 같은 가격. resolution 으로 절약 불가.
- 일부 dataset 은 country-level US rollup 이 안 됨 (예: 박스오피스, App 등) — entity 별 구매만 가능. 표에서 `note` 에 표시.
- 모든 price 는 `check_framework_price` 호출 결과 (promo 사용 X). 실제 구매는 `buy_frameworks()`.

## 35 CA 데이터셋 가격표 (monthly US, 표준화 윈도우)

| CA | Pair # | Name | Insight | 1y | 3y | 5y | rows@3y | updated | note |
|---|---:|---|---|---:|---:|---:|---:|---|---|
| `CA0034` | 55 | POS - Instore and Online | `400.0` POS Volume | $6.96 | $17.48 | $25.38 | 1,215 | 2026-04-29 | nan |
| `CA0077` | 53 | Commodity Metrics | `108408.0` Price Value | — | — | — | — | — | HTTP 500 |
| `CA0047` | 47 | POS – Supermarket | `550.0` POS Spend Per Transaction | $173.98 | $436.22 | $698.09 | 1,216 | 2026-05-07 | nan |
| `CA0056` | 45 | Credit Card – US Complete Panel | `629.0` Credit Card Average Transaction Amount | $4.99 | $8.77 | $14.03 | 2,432 | 2026-05-10 | nan |
| `CA0054` | 43 | App Intelligence | `775.0` App Downloads | $43.34 | $78.99 | $78.99 | 1,757 | 2026-05-11 | nan |
| `CA0030` | 42 | Clickstream | `381.0` Website Users | $4.99 | $4.99 | $4.99 | 2,432 | 2026-05-12 | nan |
| `CA0031` | 41 | Credit Card - US and CAN General Panel | `363.0` Credit Card Spend | — | — | — | — | — | HTTP 404 |
| `CA0028` | 39 | Credit Card – US Detailed Panel | `348.0` Credit Card Transactions | $13.65 | $54.72 | $95.90 | 3,667 | 2025-08-29 | nan |
| `CA0060` | 37 | Foot Traffic | `45863.0` Store Count | $11.59 | $29.05 | $46.49 | 1,216 | 2026-05-09 | nan |
| `CA0042` | 33 | Credit Card – EU Detailed Panel | `82.0` Credit Card Spend Per Transaction | — | — | — | — | — | HTTP 400 |
| `CA0029` | 32 | POS - Convenience Stores | `390.0` POS Average Unit Price | $10.39 | $26.04 | $41.67 | 1,216 | 2026-05-14 | nan |
| `CA0078` | 32 | POS – Premium Culinary Retail | `97929.0` Culinary POS Transactions | — | — | — | — | — | HTTP 404 |
| `CA0048` | 28 | POS – Independent Convenience | `559.0` POS Spend Per Transaction | — | — | — | — | — | HTTP 404 |
| `CA004` | 20 | Secondary Market Ticket Sales - US | `14.0` Number of Secondary Tickets Per Event | $12.86 | $32.23 | $51.48 | 2,425 | 2027-05-09 | nan |
| `CA0049` | 20 | Medical & Pharmacy Open Claims | `45523.0` Average Charge Amount | — | $136.59 | — | 2,841 | 2026-05-12 | entity=company:ACI Healthcare USA, Inc. |
| `CA0013` | 20 | Mobile App | `258.0` App Users | — | — | — | — | — | no insight/us entity |
| `CA0055` | 19 | SMB Workforce | `5382.0` Month to Date Worker Count | $91.27 | $231.44 | $371.42 | 9,656 | 2026-05-11 | nan |
| `CA0036` | 19 | Secondary Market Ticket Sales and Listings | `268.0` Secondary Tickets Sold | — | — | — | — | — | HTTP 404 |
| `CA0058` | 18 | Credit Card – Health Spend | `93212.0` Credit Card Spend | $4.99 | $8.74 | $13.99 | 1,216 | 2026-05-11 | nan |
| `CA0025` | 16 | Freight Volume - North America | `312.0` Rail Volume | — | — | — | — | — | no insight/us entity |
| `CA009` | 15 | Digital Advertising | `7.0` Indexed Advertising Spend Per Impression | $0 ⚠ | $0 ⚠ | $0 ⚠ | 0 | — | Oops Invalid Framework. No tables found for framework request after filtering. |
| `CA0035` | 13 | Financial News & Data | `491.0` News Event | — | — | — | — | — | no insight/us entity |
| `CA0053` | 10 | Job Movements | `693.0` Average Duration | — | $4.99 | — | 2 | 2026-12-31 | entity=retailer:A.C. Moore |
| `CA0045B` | 10 | TikTok Shop | `nan` nan | — | — | — | — | — | no insight/us entity |
| `CA0052` | 9 | Brand Reviews | `635.0` Review Count | — | $4.99 | — | 1 | 2026-05-14 | entity=company:AARP Services Inc. |
| `CA0059` | 8 | Extreme Weather Data | `nan` nan | — | — | — | — | — | no insight/us entity |
| `CA0080` | 7 | Maritime Data | `nan` nan | — | — | — | — | — | no insight/us entity |
| `CA0010` | 6 | OTT Entertainment Streaming | `310.0` OTT Views | $4.99 | $4.99 | $4.99 | 1,214 | 2026-05-08 | nan |
| `CA0016` | 5 | Movie Box Office | `263.0` Box Office Revenue | $4.99 | $4.99 | $4.99 | 173 | 2026-05-08 | nan |
| `CA0040` | 4 | Trade Claims | `589.0` Total Estimated Dollar Value | — | — | — | — | — | no insight/us entity |
| `CA0022` | 4 | Import/Export - US | `273.0` Trade Total Value | — | — | — | — | — | no insight/us entity |
| `CA0046` | 1 | Music Data | `292.0` Monthly Listeners | $4.99 | $4.99 | $4.99 | 1,224 | 2026-05-13 | nan |
| `CA0043C` | 1 | Technology Detections | `11678.0` Number of Days | — | — | — | — | — | HTTP 400 |
| `CA0037` | 1 | Weather Data | `502.0` Average Daily Rainfall | $4.99 | $8.94 | $14.31 | 1,216 | 2026-05-12 | nan |
| `CA005` | 1 | Vehicle Registration | `309.0` Vehicle Registration | $4.99 | $4.99 | $4.99 | 78 | 2026-03-31 | nan |

## 실제 구매 이력 (Phase 5)

| # | Framework | 윈도우 | 가격 | 결과 |
|---:|---|---|---:|---|
| 1 | CA0030 Clickstream | 5y monthly | $4.99 | 가설 미지지 (`analysis_per_dataset.md`) |
| 2 | CA0056 Card Spend | 5y monthly | $14.03 | 부분 지지 |
| 3 | CA0034 Instore POS Volume | 5y monthly | $25.39 | 잠정 지지 |
| | **누적** | | **$44.41** | |

남은 promo $5.59 — 후보: CA0058 Card Health Spend 1y $4.99 (Medical CPI), CA0010 OTT Streaming 5y $4.99 (borderline 검증).

자세히는 `docs/purchase_log.md`, 분석 결과는 `docs/analysis_per_dataset.md`.

## $50 단독 cover 가능한 데이터셋 (3y monthly US)

| CA | pairs | price 3y | rows | name |
|---|---:|---:|---:|---|
| `CA005` | 1 | $4.99 | 78 | Vehicle Registration |
| `CA0030` | 42 | $4.99 | 2,432 | Clickstream |
| `CA0052` | 9 | $4.99 | 1 | Brand Reviews |
| `CA0016` | 5 | $4.99 | 173 | Movie Box Office |
| `CA0046` | 1 | $4.99 | 1,224 | Music Data |
| `CA0010` | 6 | $4.99 | 1,214 | OTT Entertainment Streaming |
| `CA0053` | 10 | $4.99 | 2 | Job Movements |
| `CA0058` | 18 | $8.74 | 1,216 | Credit Card – Health Spend |
| `CA0056` | 45 | $8.77 | 2,432 | Credit Card – US Complete Panel |
| `CA0037` | 1 | $8.94 | 1,216 | Weather Data |
| `CA0034` | 55 | $17.48 | 1,215 | POS - Instore and Online |
| `CA0029` | 32 | $26.04 | 1,216 | POS - Convenience Stores |
| `CA0060` | 37 | $29.05 | 1,216 | Foot Traffic |
| `CA004` | 20 | $32.23 | 2,425 | Secondary Market Ticket Sales - US |

---

## 전체 754 페어 (lead window 큰 순)

_총 754행. price 컬럼은 해당 CA dataset 3y monthly US 가격. 검증할 페어 우선순위 결정에 사용._

| # | CA | CA name | Kalshi | Kalshi title | macro events | lead | price 3y | rows |
|---:|---|---|---|---|---|---:|---:|---:|
| 1 | `CA0077` | Commodity Metrics | `KXGDPSHAREMANU` | GDP share manufacturing | gdp | 89d | — | — |
| 2 | `CA009` | Digital Advertising | `GDP` | US GDP growth | gdp | 89d | $0 ⚠ | 0 |
| 3 | `CA0055` | SMB Workforce | `KXNFPROD` | US nonfarm productivity exceeds X% YoY in any quar | nonfarm productivity | 88d | $231.44 | 9,656 |
| 4 | `CA0055` | SMB Workforce | `KXRECSS` | Quarter of negative GDP growth by 2022 Q2 | gdp | 88d | $231.44 | 9,656 |
| 5 | `CA0055` | SMB Workforce | `RECSS` | Quarter of negative GDP growth by 2022 Q2 | gdp | 88d | $231.44 | 9,656 |
| 6 | `CA0056` | Credit Card – US Complete Panel | `GDP` | US GDP growth | gdp | 87d | $8.77 | 2,432 |
| 7 | `CA0056` | Credit Card – US Complete Panel | `RECSS` | Quarter of negative GDP growth by 2022 Q2 | gdp | 87d | $8.77 | 2,432 |
| 8 | `CA0056` | Credit Card – US Complete Panel | `GDPUSMIN` | Negative US GDP growth | gdp | 87d | $8.77 | 2,432 |
| 9 | `CA0056` | Credit Card – US Complete Panel | `KXRECSS` | Quarter of negative GDP growth by 2022 Q2 | gdp | 87d | $8.77 | 2,432 |
| 10 | `CA0056` | Credit Card – US Complete Panel | `KXGDPYEAR` | Annual GDP | gdp | 87d | $8.77 | 2,432 |
| 11 | `CA0056` | Credit Card – US Complete Panel | `KXGDPUSMIN` | Negative US GDP growth | gdp | 87d | $8.77 | 2,432 |
| 12 | `CA0047` | POS – Supermarket | `RECSS` | Quarter of negative GDP growth by 2022 Q2 | gdp | 86d | $436.22 | 1,216 |
| 13 | `CA0047` | POS – Supermarket | `GDP` | US GDP growth | gdp | 86d | $436.22 | 1,216 |
| 14 | `CA0047` | POS – Supermarket | `KXGDPUSMIN` | Negative US GDP growth | gdp | 86d | $436.22 | 1,216 |
| 15 | `CA0047` | POS – Supermarket | `GDPUSMIN` | Negative US GDP growth | gdp | 86d | $436.22 | 1,216 |
| 16 | `CA0060` | Foot Traffic | `RECSS` | Quarter of negative GDP growth by 2022 Q2 | gdp | 85d | $29.05 | 1,216 |
| 17 | `CA0060` | Foot Traffic | `GDPUSMIN` | Negative US GDP growth | gdp | 85d | $29.05 | 1,216 |
| 18 | `CA0060` | Foot Traffic | `GDP` | US GDP growth | gdp | 85d | $29.05 | 1,216 |
| 19 | `CA0060` | Foot Traffic | `KXFRGDPYOYP` | France GDP Growth Rate YoY Prel (quarterly) | gdp | 85d | $29.05 | 1,216 |
| 20 | `CA0060` | Foot Traffic | `KXGDPUSMIN` | Negative US GDP growth | gdp | 85d | $29.05 | 1,216 |
| 21 | `CA0060` | Foot Traffic | `KXRECSS` | Quarter of negative GDP growth by 2022 Q2 | gdp | 85d | $29.05 | 1,216 |
| 22 | `CA0025` | Freight Volume - North America | `KXRECSS` | Quarter of negative GDP growth by 2022 Q2 | gdp | 83d | — | — |
| 23 | `CA0034` | POS - Instore and Online | `GDPUSMIN` | Negative US GDP growth | gdp | 83d | $17.48 | 1,215 |
| 24 | `CA0034` | POS - Instore and Online | `RECSS` | Quarter of negative GDP growth by 2022 Q2 | gdp | 83d | $17.48 | 1,215 |
| 25 | `CA0034` | POS - Instore and Online | `KXGDPUSMIN` | Negative US GDP growth | gdp | 83d | $17.48 | 1,215 |
| 26 | `CA0025` | Freight Volume - North America | `GDP` | US GDP growth | gdp | 83d | — | — |
| 27 | `CA0025` | Freight Volume - North America | `KXGDPNOM` | Nominal GDP  | gdp | 83d | — | — |
| 28 | `CA0025` | Freight Volume - North America | `RECSS` | Quarter of negative GDP growth by 2022 Q2 | gdp | 83d | — | — |
| 29 | `CA0025` | Freight Volume - North America | `GDPUSMIN` | Negative US GDP growth | gdp | 83d | — | — |
| 30 | `CA0025` | Freight Volume - North America | `KXGDPUSMIN` | Negative US GDP growth | gdp | 83d | — | — |
| 31 | `CA0034` | POS - Instore and Online | `KXRECSS` | Quarter of negative GDP growth by 2022 Q2 | gdp | 83d | $17.48 | 1,215 |
| 32 | `CA0031` | Credit Card - US and CAN General | `KXGDP` | US GDP growth | gdp | 83d | — | — |
| 33 | `CA0028` | Credit Card – US Detailed Panel | `KXGDPYEAR` | Annual GDP | gdp | 83d | $54.72 | 3,667 |
| 34 | `CA0028` | Credit Card – US Detailed Panel | `GDP` | US GDP growth | gdp | 83d | $54.72 | 3,667 |
| 35 | `CA0028` | Credit Card – US Detailed Panel | `GDPUSMIN` | Negative US GDP growth | gdp | 83d | $54.72 | 3,667 |
| 36 | `CA0028` | Credit Card – US Detailed Panel | `KXGDPUSMIN` | Negative US GDP growth | gdp | 83d | $54.72 | 3,667 |
| 37 | `CA0028` | Credit Card – US Detailed Panel | `KXGDP` | US GDP growth | gdp | 83d | $54.72 | 3,667 |
| 38 | `CA0028` | Credit Card – US Detailed Panel | `RECSS` | Quarter of negative GDP growth by 2022 Q2 | gdp | 83d | $54.72 | 3,667 |
| 39 | `CA0031` | Credit Card - US and CAN General | `KXGDPNOM` | Nominal GDP  | gdp | 83d | — | — |
| 40 | `CA0031` | Credit Card - US and CAN General | `GDP` | US GDP growth | gdp | 83d | — | — |
| 41 | `CA0031` | Credit Card - US and CAN General | `KXGDPYEAR` | Annual GDP | gdp | 83d | — | — |
| 42 | `CA0042` | Credit Card – EU Detailed Panel | `KXDEGDPYOYF` | Germany GDP Growth Rate YoY Flash (quarterly) | gdp | 83d | — | — |
| 43 | `CA0042` | Credit Card – EU Detailed Panel | `KXFRGDPYOYP` | France GDP Growth Rate YoY Prel (quarterly) | gdp | 83d | — | — |
| 44 | `CA0042` | Credit Card – EU Detailed Panel | `KXGDPEU` | European Union GDP growth | gdp | 83d | — | — |
| 45 | `CA0028` | Credit Card – US Detailed Panel | `KXRECSS` | Quarter of negative GDP growth by 2022 Q2 | gdp | 83d | $54.72 | 3,667 |
| 46 | `CA0042` | Credit Card – EU Detailed Panel | `KXESGDPYOYF` | Spain GDP Growth Rate YoY | gdp | 83d | — | — |
| 47 | `CA0034` | POS - Instore and Online | `KXGDP` | US GDP growth | gdp | 83d | $17.48 | 1,215 |
| 48 | `CA0034` | POS - Instore and Online | `GDPUSMAX` | US GDP peak  | gdp | 83d | $17.48 | 1,215 |
| 49 | `CA0031` | Credit Card - US and CAN General | `GDPUSMIN` | Negative US GDP growth | gdp | 83d | — | — |
| 50 | `CA0031` | Credit Card - US and CAN General | `KXRECSS` | Quarter of negative GDP growth by 2022 Q2 | gdp | 83d | — | — |
| 51 | `CA0031` | Credit Card - US and CAN General | `KXGDPUSMIN` | Negative US GDP growth | gdp | 83d | — | — |
| 52 | `CA0031` | Credit Card - US and CAN General | `RECSS` | Quarter of negative GDP growth by 2022 Q2 | gdp | 83d | — | — |
| 53 | `CA0025` | Freight Volume - North America | `KXGDP` | US GDP growth | gdp | 83d | — | — |
| 54 | `CA0034` | POS - Instore and Online | `GDP` | US GDP growth | gdp | 83d | $17.48 | 1,215 |
| 55 | `CA0025` | Freight Volume - North America | `GDPUSMAX` | US GDP peak  | gdp | 83d | — | — |
| 56 | `CA0034` | POS - Instore and Online | `KXGDPNOM` | Nominal GDP  | gdp | 83d | $17.48 | 1,215 |
| 57 | `CA0042` | Credit Card – EU Detailed Panel | `GDPEU` | European Union GDP growth | gdp | 83d | — | — |
| 58 | `CA0034` | POS - Instore and Online | `KXGDPYEAR` | Annual GDP | gdp | 83d | $17.48 | 1,215 |
| 59 | `CA0042` | Credit Card – EU Detailed Panel | `KXEZGDPQOQF` | Euro Area GDP Growth Rate QoQ | gdp | 83d | — | — |
| 60 | `CA0042` | Credit Card – EU Detailed Panel | `KXESGDPQOQF` | Spain GDP Growth Rate QoQ Flash (quarterly) | gdp | 83d | — | — |
| 61 | `CA0042` | Credit Card – EU Detailed Panel | `KXITGDPQOQA` | Italy GDP Growth Rate QoQ Adv (quarterly) | gdp | 83d | — | — |
| 62 | `CA0042` | Credit Card – EU Detailed Panel | `KXITGDPYOYA` | Italy GDP Growth Rate YoY Adv (quarterly) | gdp | 83d | — | — |
| 63 | `CA0042` | Credit Card – EU Detailed Panel | `KXEZGDPYOYF` | Euro Area GDP Growth Rate YoY Flash | gdp | 83d | — | — |
| 64 | `CA0042` | Credit Card – EU Detailed Panel | `KXFRGDPQOQP` | France GDP Growth Rate QoQ Prel (quarterly) | gdp | 83d | — | — |
| 65 | `CA0042` | Credit Card – EU Detailed Panel | `KXDEGDPQOQF` | Germany GDP Growth Rate QoQ Flash (quarterly) | gdp | 83d | — | — |
| 66 | `CA0025` | Freight Volume - North America | `KXGDPYEAR` | Annual GDP | gdp | 83d | — | — |
| 67 | `CA0022` | Import/Export - US | `KXRECSS` | Quarter of negative GDP growth by 2022 Q2 | gdp | 60d | — | — |
| 68 | `CA0043C` | Technology Detections | `KXNFPROD` | US nonfarm productivity exceeds X% YoY in any quar | nonfarm productivity | 60d | — | — |
| 69 | `CA0022` | Import/Export - US | `GDPUSMIN` | Negative US GDP growth | gdp | 60d | — | — |
| 70 | `CA005` | Vehicle Registration | `RECSS` | Quarter of negative GDP growth by 2022 Q2 | gdp | 60d | $4.99 | 78 |
| 71 | `CA0022` | Import/Export - US | `GDP` | US GDP growth | gdp | 60d | — | — |
| 72 | `CA0022` | Import/Export - US | `RECSS` | Quarter of negative GDP growth by 2022 Q2 | gdp | 60d | — | — |
| 73 | `CA0030` | Clickstream | `PCECORE` | US Core PCE inflation | core pce,pce | 29d | $4.99 | 2,432 |
| 74 | `CA0048` | POS – Independent Convenience | `KXECONSTATCORECPIYOY` | year over year core inflation | core cpi | 29d | — | — |
| 75 | `CA0077` | Commodity Metrics | `KXUSISMSERV` | United States ISM Services PMI | ism services,services pmi | 29d | — | — |
| 76 | `CA0048` | POS – Independent Convenience | `KXCPIFOOD` | CPI on food | cpi | 29d | — | — |
| 77 | `CA0048` | POS – Independent Convenience | `KXUSMICHCSP` | United States Michigan Consumer Sentiment Prel  | consumer sentiment,michigan cons | 29d | — | — |
| 78 | `CA0048` | POS – Independent Convenience | `KXUSPPIYOY` | US PPI YoY in [month] | ppi | 29d | — | — |
| 79 | `CA0048` | POS – Independent Convenience | `KXTRUFEGGS` | Truflation US CPI Eggs Index | cpi | 29d | — | — |
| 80 | `CA0048` | POS – Independent Convenience | `CPICOREYOY` | Core inflation | core cpi | 29d | — | — |
| 81 | `CA0030` | Clickstream | `CPISHELTER` | CPI on shelter | cpi | 29d | $4.99 | 2,432 |
| 82 | `CA0078` | POS – Premium Culinary Retail | `KXCPICOMBO` | CPI Combo | cpi | 29d | — | — |
| 83 | `CA0077` | Commodity Metrics | `PPISEMI` | Semiconductor PPI | ppi | 29d | — | — |
| 84 | `CA0030` | Clickstream | `RETAIL` | Retail sales growth | retail sales | 29d | $4.99 | 2,432 |
| 85 | `CA0078` | POS – Premium Culinary Retail | `KXUSPPI` | United States PPI MoM | ppi | 29d | — | — |
| 86 | `CA0048` | POS – Independent Convenience | `KXISMSERVICES` | ISM Services PMI | ism services,services pmi | 29d | — | — |
| 87 | `CA0048` | POS – Independent Convenience | `RETAIL` | Retail sales growth | retail sales | 29d | — | — |
| 88 | `CA0048` | POS – Independent Convenience | `KXTRUFCPIYE` | Truflation U.S. CPI Inflation Index EOY | cpi | 29d | — | — |
| 89 | `CA0030` | Clickstream | `KXJOLTS` | Job openings | jolts | 29d | $4.99 | 2,432 |
| 90 | `CA0030` | Clickstream | `KXCPICOREA` | Core CPI annually | core cpi,cpi | 29d | $4.99 | 2,432 |
| 91 | `CA0030` | Clickstream | `KXDEGFK` | Germany GfK Consumer Confidence | consumer confidence | 29d | $4.99 | 2,432 |
| 92 | `CA0030` | Clickstream | `KXEHSALES` | Existing home sales in time period | existing home sales | 29d | $4.99 | 2,432 |
| 93 | `CA0077` | Commodity Metrics | `KXTOBACCPI` | Tobacco CPI higher in [month]? | cpi | 29d | — | — |
| 94 | `CA0030` | Clickstream | `KXCANHOUSTART` | Canada housing starts above X in [year]? | housing starts | 29d | $4.99 | 2,432 |
| 95 | `CA0048` | POS – Independent Convenience | `CPI` | CPI | cpi | 29d | — | — |
| 96 | `CA0078` | POS – Premium Culinary Retail | `ACPICORE-` | US annual core inflation | core cpi | 29d | — | — |
| 97 | `CA0077` | Commodity Metrics | `KXCPICOREA` | Core CPI annually | core cpi,cpi | 29d | — | — |
| 98 | `CA0078` | POS – Premium Culinary Retail | `KXPCECORE` | US Core PCE inflation | core pce,pce | 29d | — | — |
| 99 | `CA0030` | Clickstream | `KXCPISHELTER` | CPI on shelter | cpi | 29d | $4.99 | 2,432 |
| 100 | `CA0030` | Clickstream | `KXISMSERVICES` | ISM Services PMI | ism services,services pmi | 29d | $4.99 | 2,432 |
| 101 | `CA0078` | POS – Premium Culinary Retail | `CPIDELAY` | CPI data released | cpi | 29d | — | — |
| 102 | `CA0048` | POS – Independent Convenience | `KXAUWPCC` | Australia Westpac Consumer Confidence Change | consumer confidence | 29d | — | — |
| 103 | `CA0030` | Clickstream | `KXUSPSPEND` | United States Personal Spending MoM | personal spending | 29d | $4.99 | 2,432 |
| 104 | `CA0078` | POS – Premium Culinary Retail | `KXUSPPIYOY` | US PPI YoY in [month] | ppi | 29d | — | — |
| 105 | `CA0048` | POS – Independent Convenience | `KXCPI` | CPI | cpi | 29d | — | — |
| 106 | `CA0030` | Clickstream | `KXUSIPMOM` | US industrial production MoM | industrial production | 29d | $4.99 | 2,432 |
| 107 | `CA0048` | POS – Independent Convenience | `KXUSPPI` | United States PPI MoM | ppi | 29d | — | — |
| 108 | `CA0077` | Commodity Metrics | `KXPCECORE` | US Core PCE inflation | core pce,pce | 29d | — | — |
| 109 | `CA0030` | Clickstream | `KXUSEDCARCPI` | US used cars and trucks CPI in [month] | cpi | 29d | $4.99 | 2,432 |
| 110 | `CA0048` | POS – Independent Convenience | `KXCOREUND` | Will Core CPI fall below x.x% in 2026? | core cpi,cpi | 29d | — | — |
| 111 | `CA0048` | POS – Independent Convenience | `KXTOBACCPI` | Tobacco CPI higher in [month]? | cpi | 29d | — | — |
| 112 | `CA0078` | POS – Premium Culinary Retail | `KXCPICORE220` | Will the BLS Core CPI YoY print below 2.20%  | core cpi,cpi | 29d | — | — |
| 113 | `CA0048` | POS – Independent Convenience | `KXUSNFP` | US nonfarm payrolls in [month] | nonfarm payrolls | 29d | — | — |
| 114 | `CA0030` | Clickstream | `KXTRUFEGGS` | Truflation US CPI Eggs Index | cpi | 29d | $4.99 | 2,432 |
| 115 | `CA0078` | POS – Premium Culinary Retail | `CPICOREYOY` | Core inflation | core cpi | 29d | — | — |
| 116 | `CA0030` | Clickstream | `KXCPIAPPAREL` | CPI on apparel | cpi | 29d | $4.99 | 2,432 |
| 117 | `CA0030` | Clickstream | `KXUSPPIYOY` | US PPI YoY in [month] | ppi | 29d | $4.99 | 2,432 |
| 118 | `CA0030` | Clickstream | `CPIAPPAREL` | CPI on apparel | cpi | 29d | $4.99 | 2,432 |
| 119 | `CA0048` | POS – Independent Convenience | `KXUSPSPEND` | United States Personal Spending MoM | personal spending | 29d | — | — |
| 120 | `CA0048` | POS – Independent Convenience | `PCECORE` | US Core PCE inflation | core pce,pce | 29d | — | — |
| 121 | `CA0078` | POS – Premium Culinary Retail | `KXCPIFOOD` | CPI on food | cpi | 29d | — | — |
| 122 | `CA0030` | Clickstream | `KXRETAIL` | Retail sales growth | retail sales | 29d | $4.99 | 2,432 |
| 123 | `CA0048` | POS – Independent Convenience | `KXUSISMSERV` | United States ISM Services PMI | ism services,services pmi | 29d | — | — |
| 124 | `CA0078` | POS – Premium Culinary Retail | `RETAIL` | Retail sales growth | retail sales | 29d | — | — |
| 125 | `CA0078` | POS – Premium Culinary Retail | `KXPPICPI` | PPI YoY exceeds CPI YoY for [time period] | cpi,ppi | 29d | — | — |
| 126 | `CA0078` | POS – Premium Culinary Retail | `KXISMSERVICES` | ISM Services PMI | ism services,services pmi | 29d | — | — |
| 127 | `CA0048` | POS – Independent Convenience | `CPIFOOD` | CPI on food | cpi | 29d | — | — |
| 128 | `CA0078` | POS – Premium Culinary Retail | `KXUSRETAIL` | US retail sales MoM | retail sales | 29d | — | — |
| 129 | `CA0048` | POS – Independent Convenience | `KXRETAIL` | Retail sales growth | retail sales | 29d | — | — |
| 130 | `CA0078` | POS – Premium Culinary Retail | `KXTRUFEGGS` | Truflation US CPI Eggs Index | cpi | 29d | — | — |
| 131 | `CA0078` | POS – Premium Culinary Retail | `KXECONSTATCORECPIYOY` | year over year core inflation | core cpi | 29d | — | — |
| 132 | `CA0078` | POS – Premium Culinary Retail | `KXTRUFCPI` | Truflation US CPI Inflation Index | cpi | 29d | — | — |
| 133 | `CA0048` | POS – Independent Convenience | `KXCPICOMBO` | CPI Combo | cpi | 29d | — | — |
| 134 | `CA0030` | Clickstream | `KXEHSHARE` | Existing home sales in time period | existing home sales | 29d | $4.99 | 2,432 |
| 135 | `CA0078` | POS – Premium Culinary Retail | `KXCACPIYOY` | Canada Inflation Rate YoY | cpi | 29d | — | — |
| 136 | `CA0077` | Commodity Metrics | `KXUSGASCPI` | US gasoline CPI in [month] | cpi | 29d | — | — |
| 137 | `CA0077` | Commodity Metrics | `KXCPIUSEDCAR` | CPI on used cars | cpi | 29d | — | — |
| 138 | `CA0077` | Commodity Metrics | `KXCPIAPPAREL` | CPI on apparel | cpi | 29d | — | — |
| 139 | `CA0077` | Commodity Metrics | `KXUSEDCAR` | US CPI print on used cars | cpi | 29d | — | — |
| 140 | `CA0048` | POS – Independent Convenience | `KXCPICOREA` | Core CPI annually | core cpi,cpi | 29d | — | — |
| 141 | `CA0048` | POS – Independent Convenience | `KXCPICORE220` | Will the BLS Core CPI YoY print below 2.20%  | core cpi,cpi | 29d | — | — |
| 142 | `CA0048` | POS – Independent Convenience | `KXUSGASCPI` | US gasoline CPI in [month] | cpi | 29d | — | — |
| 143 | `CA0030` | Clickstream | `KXUMICHOVR` | Michigan consumer sentiment above X in [year]? | consumer sentiment,michigan cons | 29d | $4.99 | 2,432 |
| 144 | `CA0030` | Clickstream | `KXHOME` | New home sales | new home sales | 29d | $4.99 | 2,432 |
| 145 | `CA0077` | Commodity Metrics | `KXPPISEMI` | Semiconductor PPI | ppi | 29d | — | — |
| 146 | `CA0077` | Commodity Metrics | `KXCPIGAS` | CPI on gas | cpi | 29d | — | — |
| 147 | `CA0077` | Commodity Metrics | `KXPPIVSCPI` | PPI YoY exceeds CPI YoY for [time period] | cpi,ppi | 29d | — | — |
| 148 | `CA0046` | Music Data | `KXAUWPCC` | Australia Westpac Consumer Confidence Change | consumer confidence | 29d | $4.99 | 1,224 |
| 149 | `CA0077` | Commodity Metrics | `KXCPICORE220` | Will the BLS Core CPI YoY print below 2.20%  | core cpi,cpi | 29d | — | — |
| 150 | `CA0010` | OTT Entertainment Streaming | `KXAUWPCC` | Australia Westpac Consumer Confidence Change | consumer confidence | 29d | $4.99 | 1,214 |
| 151 | `CA0078` | POS – Premium Culinary Retail | `ACPICORE` | Annual core inflation | core cpi | 29d | — | — |
| 152 | `CA0077` | Commodity Metrics | `KXTRUFHOUCPI` | Truflation US CPI Housing Inflation Index | cpi | 29d | — | — |
| 153 | `CA0010` | OTT Entertainment Streaming | `KXDEGFK` | Germany GfK Consumer Confidence | consumer confidence | 29d | $4.99 | 1,214 |
| 154 | `CA0077` | Commodity Metrics | `KXAIRFARECPI` | US airline fares CPI in [month] | cpi | 29d | — | — |
| 155 | `CA0077` | Commodity Metrics | `KXADP` | ADP employment change | adp employment | 29d | — | — |
| 156 | `CA0030` | Clickstream | `KXUSISMSERV` | United States ISM Services PMI | ism services,services pmi | 29d | $4.99 | 2,432 |
| 157 | `CA0010` | OTT Entertainment Streaming | `KXUSPSPEND` | United States Personal Spending MoM | personal spending | 29d | $4.99 | 1,214 |
| 158 | `CA0010` | OTT Entertainment Streaming | `KXISMSERVICES` | ISM Services PMI | ism services,services pmi | 29d | $4.99 | 1,214 |
| 159 | `CA0030` | Clickstream | `KXJPCONCONF` | Japan Consumer Confidence | consumer confidence | 29d | $4.99 | 2,432 |
| 160 | `CA0077` | Commodity Metrics | `RETAIL` | Retail sales growth | retail sales | 29d | — | — |
| 161 | `CA0010` | OTT Entertainment Streaming | `KXUSMICHCSP` | United States Michigan Consumer Sentiment Prel  | consumer sentiment,michigan cons | 29d | $4.99 | 1,214 |
| 162 | `CA0010` | OTT Entertainment Streaming | `KXUSISMSERV` | United States ISM Services PMI | ism services,services pmi | 29d | $4.99 | 1,214 |
| 163 | `CA0030` | Clickstream | `KXUSMICHCSP` | United States Michigan Consumer Sentiment Prel  | consumer sentiment,michigan cons | 29d | $4.99 | 2,432 |
| 164 | `CA0048` | POS – Independent Convenience | `KXUSRETAIL` | US retail sales MoM | retail sales | 29d | — | — |
| 165 | `CA0016` | Movie Box Office | `KXUSPSPEND` | United States Personal Spending MoM | personal spending | 29d | $4.99 | 173 |
| 166 | `CA0077` | Commodity Metrics | `KXCACPIYOY` | Canada Inflation Rate YoY | cpi | 29d | — | — |
| 167 | `CA0077` | Commodity Metrics | `KXRETAIL` | Retail sales growth | retail sales | 29d | — | — |
| 168 | `CA0077` | Commodity Metrics | `KXUSRETAIL` | US retail sales MoM | retail sales | 29d | — | — |
| 169 | `CA0077` | Commodity Metrics | `KXEHSHARE` | Existing home sales in time period | existing home sales | 29d | — | — |
| 170 | `CA0016` | Movie Box Office | `KXRETAIL` | Retail sales growth | retail sales | 29d | $4.99 | 173 |
| 171 | `CA0077` | Commodity Metrics | `KXJOLTS` | Job openings | jolts | 29d | — | — |
| 172 | `CA0077` | Commodity Metrics | `KXDEGFK` | Germany GfK Consumer Confidence | consumer confidence | 29d | — | — |
| 173 | `CA0077` | Commodity Metrics | `KXISMSERVICES` | ISM Services PMI | ism services,services pmi | 29d | — | — |
| 174 | `CA0077` | Commodity Metrics | `KXEHSALES` | Existing home sales in time period | existing home sales | 29d | — | — |
| 175 | `CA0077` | Commodity Metrics | `CPIUSEDCAR` | CPI on used cars | cpi | 29d | — | — |
| 176 | `CA0077` | Commodity Metrics | `KXPPICPI` | PPI YoY exceeds CPI YoY for [time period] | cpi,ppi | 29d | — | — |
| 177 | `CA0077` | Commodity Metrics | `KXACPICORE-` | US annual core inflation | core cpi | 29d | — | — |
| 178 | `CA0077` | Commodity Metrics | `KXCANHOUSTART` | Canada housing starts above X in [year]? | housing starts | 29d | — | — |
| 179 | `CA0016` | Movie Box Office | `RETAIL` | Retail sales growth | retail sales | 29d | $4.99 | 173 |
| 180 | `CA0016` | Movie Box Office | `KXAUWPCC` | Australia Westpac Consumer Confidence Change | consumer confidence | 29d | $4.99 | 173 |
| 181 | `CA0077` | Commodity Metrics | `KXACPICORE` | Annual core inflation | core cpi | 29d | — | — |
| 182 | `CA0077` | Commodity Metrics | `CPIFOOD` | CPI on food | cpi | 29d | — | — |
| 183 | `CA0077` | Commodity Metrics | `PCECORE` | US Core PCE inflation | core pce,pce | 29d | — | — |
| 184 | `CA0077` | Commodity Metrics | `KXUSPSPEND` | United States Personal Spending MoM | personal spending | 29d | — | — |
| 185 | `CA0077` | Commodity Metrics | `KXBUILDPERMS` | Building permits for month | building permits | 29d | — | — |
| 186 | `CA0016` | Movie Box Office | `KXUSRETAIL` | US retail sales MoM | retail sales | 29d | $4.99 | 173 |
| 187 | `CA0077` | Commodity Metrics | `KXUSIPMOM` | US industrial production MoM | industrial production | 29d | — | — |
| 188 | `CA0077` | Commodity Metrics | `KXUSEDCARCPI` | US used cars and trucks CPI in [month] | cpi | 29d | — | — |
| 189 | `CA0077` | Commodity Metrics | `KXCPIFOOD` | CPI on food | cpi | 29d | — | — |
| 190 | `CA0048` | POS – Independent Convenience | `KXCACPIYOY` | Canada Inflation Rate YoY | cpi | 29d | — | — |
| 191 | `CA0077` | Commodity Metrics | `KXEZCPIYOYF` | Euro Area Inflation Rate YoY Flash | cpi | 29d | — | — |
| 192 | `CA0077` | Commodity Metrics | `KXTRUFCPIYE` | Truflation U.S. CPI Inflation Index EOY | cpi | 29d | — | — |
| 193 | `CA0048` | POS – Independent Convenience | `KXPCECORE` | US Core PCE inflation | core pce,pce | 29d | — | — |
| 194 | `CA0077` | Commodity Metrics | `KXUSDURABLE` | United States Durable Goods Orders MoM | durable goods | 29d | — | — |
| 195 | `CA0078` | POS – Premium Culinary Retail | `KXRETAIL` | Retail sales growth | retail sales | 29d | — | — |
| 196 | `CA0030` | Clickstream | `KXUKCPIYOY` | United Kingdom Inflation Rate YoY | cpi | 29d | $4.99 | 2,432 |
| 197 | `CA0078` | POS – Premium Culinary Retail | `KXCPICOREA` | Core CPI annually | core cpi,cpi | 29d | — | — |
| 198 | `CA0077` | Commodity Metrics | `KXAUWPCC` | Australia Westpac Consumer Confidence Change | consumer confidence | 29d | — | — |
| 199 | `CA004` | Secondary Market Ticket Sales -  | `KXUSPSPEND` | United States Personal Spending MoM | personal spending | 29d | $32.23 | 2,425 |
| 200 | `CA004` | Secondary Market Ticket Sales -  | `KXISMSERVICES` | ISM Services PMI | ism services,services pmi | 29d | $32.23 | 2,425 |
| 201 | `CA0077` | Commodity Metrics | `KXTRUFEGGS` | Truflation US CPI Eggs Index | cpi | 29d | — | — |
| 202 | `CA0077` | Commodity Metrics | `CPIAPPAREL` | CPI on apparel | cpi | 29d | — | — |
| 203 | `CA0077` | Commodity Metrics | `KXUKCPIYOY` | United Kingdom Inflation Rate YoY | cpi | 29d | — | — |
| 204 | `CA0077` | Commodity Metrics | `KXECONSTATCORECPIYOY` | year over year core inflation | core cpi | 29d | — | — |
| 205 | `CA0077` | Commodity Metrics | `KXUSPPIYOY` | US PPI YoY in [month] | ppi | 29d | — | — |
| 206 | `CA0077` | Commodity Metrics | `HOME` | New home sales | new home sales | 29d | — | — |
| 207 | `CA0077` | Commodity Metrics | `KXUSPPI` | United States PPI MoM | ppi | 29d | — | — |
| 208 | `CA0077` | Commodity Metrics | `KXCPICOMBO` | CPI Combo | cpi | 29d | — | — |
| 209 | `CA0077` | Commodity Metrics | `KXNHSALES` | New home sales in time period | new home sales | 29d | — | — |
| 210 | `CA0077` | Commodity Metrics | `USEDCAR` | US CPI print on used cars | cpi | 29d | — | — |
| 211 | `CA0030` | Clickstream | `KXTRUFCPIYE` | Truflation U.S. CPI Inflation Index EOY | cpi | 29d | $4.99 | 2,432 |
| 212 | `CA0052` | Brand Reviews | `CPIAPPAREL` | CPI on apparel | cpi | 29d | $4.99 | 1 |
| 213 | `CA004` | Secondary Market Ticket Sales -  | `KXRETAIL` | Retail sales growth | retail sales | 29d | $32.23 | 2,425 |
| 214 | `CA0035` | Financial News & Data | `KXCPIUSEDCAR` | CPI on used cars | cpi | 29d | — | — |
| 215 | `CA004` | Secondary Market Ticket Sales -  | `KXUSEDCARCPI` | US used cars and trucks CPI in [month] | cpi | 29d | $32.23 | 2,425 |
| 216 | `CA0052` | Brand Reviews | `KXAUWPCC` | Australia Westpac Consumer Confidence Change | consumer confidence | 29d | $4.99 | 1 |
| 217 | `CA0036` | Secondary Market Ticket Sales an | `KXUSRETAIL` | US retail sales MoM | retail sales | 29d | — | — |
| 218 | `CA0036` | Secondary Market Ticket Sales an | `KXUSEDCAR` | US CPI print on used cars | cpi | 29d | — | — |
| 219 | `CA0036` | Secondary Market Ticket Sales an | `KXAUWPCC` | Australia Westpac Consumer Confidence Change | consumer confidence | 29d | — | — |
| 220 | `CA004` | Secondary Market Ticket Sales -  | `KXUSMICHCSP` | United States Michigan Consumer Sentiment Prel  | consumer sentiment,michigan cons | 29d | $32.23 | 2,425 |
| 221 | `CA0052` | Brand Reviews | `USEDCAR` | US CPI print on used cars | cpi | 29d | $4.99 | 1 |
| 222 | `CA0036` | Secondary Market Ticket Sales an | `USEDCAR` | US CPI print on used cars | cpi | 29d | — | — |
| 223 | `CA004` | Secondary Market Ticket Sales -  | `KXUSISMSERV` | United States ISM Services PMI | ism services,services pmi | 29d | $32.23 | 2,425 |
| 224 | `CA0052` | Brand Reviews | `KXUSDURABLE` | United States Durable Goods Orders MoM | durable goods | 29d | $4.99 | 1 |
| 225 | `CA0036` | Secondary Market Ticket Sales an | `KXCPIUSEDCAR` | CPI on used cars | cpi | 29d | — | — |
| 226 | `CA0036` | Secondary Market Ticket Sales an | `KXAIRFARECPI` | US airline fares CPI in [month] | cpi | 29d | — | — |
| 227 | `CA0036` | Secondary Market Ticket Sales an | `KXTRUFHOUCPI` | Truflation US CPI Housing Inflation Index | cpi | 29d | — | — |
| 228 | `CA0035` | Financial News & Data | `KXADP` | ADP employment change | adp employment | 29d | — | — |
| 229 | `CA0036` | Secondary Market Ticket Sales an | `CPIAPPAREL` | CPI on apparel | cpi | 29d | — | — |
| 230 | `CA0080` | Maritime Data | `KXUSPPIYOY` | US PPI YoY in [month] | ppi | 29d | — | — |
| 231 | `CA0036` | Secondary Market Ticket Sales an | `KXUSEDCARCPI` | US used cars and trucks CPI in [month] | cpi | 29d | — | — |
| 232 | `CA0036` | Secondary Market Ticket Sales an | `CPISHELTER` | CPI on shelter | cpi | 29d | — | — |
| 233 | `CA009` | Digital Advertising | `KXCPICOMBO` | CPI Combo | cpi | 29d | $0 ⚠ | 0 |
| 234 | `CA004` | Secondary Market Ticket Sales -  | `CPISHELTER` | CPI on shelter | cpi | 29d | $32.23 | 2,425 |
| 235 | `CA004` | Secondary Market Ticket Sales -  | `CPIUSEDCAR` | CPI on used cars | cpi | 29d | $32.23 | 2,425 |
| 236 | `CA0035` | Financial News & Data | `KXAIRFARECPI` | US airline fares CPI in [month] | cpi | 29d | — | — |
| 237 | `CA004` | Secondary Market Ticket Sales -  | `RETAIL` | Retail sales growth | retail sales | 29d | $32.23 | 2,425 |
| 238 | `CA004` | Secondary Market Ticket Sales -  | `KXEHSHARE` | Existing home sales in time period | existing home sales | 29d | $32.23 | 2,425 |
| 239 | `CA004` | Secondary Market Ticket Sales -  | `KXEHSALES` | Existing home sales in time period | existing home sales | 29d | $32.23 | 2,425 |
| 240 | `CA004` | Secondary Market Ticket Sales -  | `KXCPIAPPAREL` | CPI on apparel | cpi | 29d | $32.23 | 2,425 |
| 241 | `CA0036` | Secondary Market Ticket Sales an | `KXUSPSPEND` | United States Personal Spending MoM | personal spending | 29d | — | — |
| 242 | `CA0036` | Secondary Market Ticket Sales an | `KXCPISHELTER` | CPI on shelter | cpi | 29d | — | — |
| 243 | `CA0036` | Secondary Market Ticket Sales an | `RETAIL` | Retail sales growth | retail sales | 29d | — | — |
| 244 | `CA0036` | Secondary Market Ticket Sales an | `KXEHSHARE` | Existing home sales in time period | existing home sales | 29d | — | — |
| 245 | `CA0036` | Secondary Market Ticket Sales an | `KXRETAIL` | Retail sales growth | retail sales | 29d | — | — |
| 246 | `CA0036` | Secondary Market Ticket Sales an | `KXCPIAPPAREL` | CPI on apparel | cpi | 29d | — | — |
| 247 | `CA0036` | Secondary Market Ticket Sales an | `KXUSMICHCSP` | United States Michigan Consumer Sentiment Prel  | consumer sentiment,michigan cons | 29d | — | — |
| 248 | `CA0035` | Financial News & Data | `KXUSGASCPI` | US gasoline CPI in [month] | cpi | 29d | — | — |
| 249 | `CA009` | Digital Advertising | `PCECORE` | US Core PCE inflation | core pce,pce | 29d | $0 ⚠ | 0 |
| 250 | `CA009` | Digital Advertising | `KXEHSHARE` | Existing home sales in time period | existing home sales | 29d | $0 ⚠ | 0 |
| 251 | `CA009` | Digital Advertising | `KXUSPSPEND` | United States Personal Spending MoM | personal spending | 29d | $0 ⚠ | 0 |
| 252 | `CA009` | Digital Advertising | `KXUSISMSERV` | United States ISM Services PMI | ism services,services pmi | 29d | $0 ⚠ | 0 |
| 253 | `CA009` | Digital Advertising | `KXUSMICHCSP` | United States Michigan Consumer Sentiment Prel  | consumer sentiment,michigan cons | 29d | $0 ⚠ | 0 |
| 254 | `CA009` | Digital Advertising | `KXUSRETAIL` | US retail sales MoM | retail sales | 29d | $0 ⚠ | 0 |
| 255 | `CA009` | Digital Advertising | `HOME` | New home sales | new home sales | 29d | $0 ⚠ | 0 |
| 256 | `CA009` | Digital Advertising | `KXUSPPI` | United States PPI MoM | ppi | 29d | $0 ⚠ | 0 |
| 257 | `CA0036` | Secondary Market Ticket Sales an | `KXEHSALES` | Existing home sales in time period | existing home sales | 29d | — | — |
| 258 | `CA009` | Digital Advertising | `KXPCECORE` | US Core PCE inflation | core pce,pce | 29d | $0 ⚠ | 0 |
| 259 | `CA009` | Digital Advertising | `KXCACPIYOY` | Canada Inflation Rate YoY | cpi | 29d | $0 ⚠ | 0 |
| 260 | `CA0036` | Secondary Market Ticket Sales an | `CPIUSEDCAR` | CPI on used cars | cpi | 29d | — | — |
| 261 | `CA009` | Digital Advertising | `KXJOLTS` | Job openings | jolts | 29d | $0 ⚠ | 0 |
| 262 | `CA009` | Digital Advertising | `KXISMSERVICES` | ISM Services PMI | ism services,services pmi | 29d | $0 ⚠ | 0 |
| 263 | `CA0078` | POS – Premium Culinary Retail | `PCECORE` | US Core PCE inflation | core pce,pce | 29d | — | — |
| 264 | `CA0030` | Clickstream | `USEDCAR` | US CPI print on used cars | cpi | 29d | $4.99 | 2,432 |
| 265 | `CA0078` | POS – Premium Culinary Retail | `KXUSISMSERV` | United States ISM Services PMI | ism services,services pmi | 29d | — | — |
| 266 | `CA0030` | Clickstream | `KXAUWPCC` | Australia Westpac Consumer Confidence Change | consumer confidence | 29d | $4.99 | 2,432 |
| 267 | `CA0030` | Clickstream | `KXCPIFOOD` | CPI on food | cpi | 29d | $4.99 | 2,432 |
| 268 | `CA0037` | Weather Data | `KXUSGASCPI` | US gasoline CPI in [month] | cpi | 29d | $8.94 | 1,216 |
| 269 | `CA0078` | POS – Premium Culinary Retail | `KXUSMICHCSP` | United States Michigan Consumer Sentiment Prel  | consumer sentiment,michigan cons | 29d | — | — |
| 270 | `CA0080` | Maritime Data | `KXUSDURABLE` | United States Durable Goods Orders MoM | durable goods | 29d | — | — |
| 271 | `CA0030` | Clickstream | `KXPCECORE` | US Core PCE inflation | core pce,pce | 29d | $4.99 | 2,432 |
| 272 | `CA0052` | Brand Reviews | `KXUSMICHCSP` | United States Michigan Consumer Sentiment Prel  | consumer sentiment,michigan cons | 29d | $4.99 | 1 |
| 273 | `CA0052` | Brand Reviews | `KXJPCONCONF` | Japan Consumer Confidence | consumer confidence | 29d | $4.99 | 1 |
| 274 | `CA0030` | Clickstream | `KXUSEDCAR` | US CPI print on used cars | cpi | 29d | $4.99 | 2,432 |
| 275 | `CA0030` | Clickstream | `KXCACPIYOY` | Canada Inflation Rate YoY | cpi | 29d | $4.99 | 2,432 |
| 276 | `CA0030` | Clickstream | `KXUSRETAIL` | US retail sales MoM | retail sales | 29d | $4.99 | 2,432 |
| 277 | `CA0030` | Clickstream | `KXUSDURABLE` | United States Durable Goods Orders MoM | durable goods | 29d | $4.99 | 2,432 |
| 278 | `CA0030` | Clickstream | `KXADP` | ADP employment change | adp employment | 29d | $4.99 | 2,432 |
| 279 | `CA0030` | Clickstream | `KXCPICORE220` | Will the BLS Core CPI YoY print below 2.20%  | core cpi,cpi | 29d | $4.99 | 2,432 |
| 280 | `CA0030` | Clickstream | `KXCPIUSEDCAR` | CPI on used cars | cpi | 29d | $4.99 | 2,432 |
| 281 | `CA0030` | Clickstream | `KXSHELTERCPI` | US shelter CPI in [month] | cpi | 29d | $4.99 | 2,432 |
| 282 | `CA0030` | Clickstream | `KXAIRFARECPI` | US airline fares CPI in [month] | cpi | 29d | $4.99 | 2,432 |
| 283 | `CA0078` | POS – Premium Culinary Retail | `KXECONSTATCPICORE` | month over month core inflation | core cpi | 29d | — | — |
| 284 | `CA0078` | POS – Premium Culinary Retail | `KXCOREUND` | Will Core CPI fall below x.x% in 2026? | core cpi,cpi | 29d | — | — |
| 285 | `CA0078` | POS – Premium Culinary Retail | `CPICORE` | CPI core | cpi | 29d | — | — |
| 286 | `CA0078` | POS – Premium Culinary Retail | `CPIFOOD` | CPI on food | cpi | 29d | — | — |
| 287 | `CA0078` | POS – Premium Culinary Retail | `CPI` | CPI | cpi | 29d | — | — |
| 288 | `CA0030` | Clickstream | `KXECONSTATCORECPIYOY` | year over year core inflation | core cpi | 29d | $4.99 | 2,432 |
| 289 | `CA004` | Secondary Market Ticket Sales -  | `KXADP` | ADP employment change | adp employment | 29d | $32.23 | 2,425 |
| 290 | `CA0078` | POS – Premium Culinary Retail | `KXCPI` | CPI | cpi | 29d | — | — |
| 291 | `CA0030` | Clickstream | `KXNHSALES` | New home sales in time period | new home sales | 29d | $4.99 | 2,432 |
| 292 | `CA0078` | POS – Premium Culinary Retail | `KXCPIDELAY` | CPI data released | cpi | 29d | — | — |
| 293 | `CA0078` | POS – Premium Culinary Retail | `KXACPICORE` | Annual core inflation | core cpi | 29d | — | — |
| 294 | `CA004` | Secondary Market Ticket Sales -  | `KXUSRETAIL` | US retail sales MoM | retail sales | 29d | $32.23 | 2,425 |
| 295 | `CA004` | Secondary Market Ticket Sales -  | `USEDCAR` | US CPI print on used cars | cpi | 29d | $32.23 | 2,425 |
| 296 | `CA0080` | Maritime Data | `KXCHIPYOY` | China Industrial Production YoY | industrial production | 29d | — | — |
| 297 | `CA0077` | Commodity Metrics | `CPIGAS` | CPI on gas | cpi | 29d | — | — |
| 298 | `CA0080` | Maritime Data | `KXTRUFEGGS` | Truflation US CPI Eggs Index | cpi | 29d | — | — |
| 299 | `CA0080` | Maritime Data | `KXISMSERVICES` | ISM Services PMI | ism services,services pmi | 29d | — | — |
| 300 | `CA0078` | POS – Premium Culinary Retail | `KXUSPSPEND` | United States Personal Spending MoM | personal spending | 29d | — | — |
| 301 | `CA0080` | Maritime Data | `KXUSIPMOM` | US industrial production MoM | industrial production | 29d | — | — |
| 302 | `CA0030` | Clickstream | `HOME` | New home sales | new home sales | 29d | $4.99 | 2,432 |
| 303 | `CA004` | Secondary Market Ticket Sales -  | `KXAIRFARECPI` | US airline fares CPI in [month] | cpi | 29d | $32.23 | 2,425 |
| 304 | `CA0052` | Brand Reviews | `KXUSEDCARCPI` | US used cars and trucks CPI in [month] | cpi | 29d | $4.99 | 1 |
| 305 | `CA0035` | Financial News & Data | `KXTOBACCPI` | Tobacco CPI higher in [month]? | cpi | 29d | — | — |
| 306 | `CA0035` | Financial News & Data | `KXJPCONCONF` | Japan Consumer Confidence | consumer confidence | 29d | — | — |
| 307 | `CA004` | Secondary Market Ticket Sales -  | `KXCPIUSEDCAR` | CPI on used cars | cpi | 29d | $32.23 | 2,425 |
| 308 | `CA0080` | Maritime Data | `KXUSEDCARCPI` | US used cars and trucks CPI in [month] | cpi | 29d | — | — |
| 309 | `CA009` | Digital Advertising | `KXUKCPIYOY` | United Kingdom Inflation Rate YoY | cpi | 29d | $0 ⚠ | 0 |
| 310 | `CA004` | Secondary Market Ticket Sales -  | `CPIAPPAREL` | CPI on apparel | cpi | 29d | $32.23 | 2,425 |
| 311 | `CA004` | Secondary Market Ticket Sales -  | `KXUSEDCAR` | US CPI print on used cars | cpi | 29d | $32.23 | 2,425 |
| 312 | `CA0035` | Financial News & Data | `KXCANHOUSTART` | Canada housing starts above X in [year]? | housing starts | 29d | — | — |
| 313 | `CA0035` | Financial News & Data | `KXDEGFK` | Germany GfK Consumer Confidence | consumer confidence | 29d | — | — |
| 314 | `CA0035` | Financial News & Data | `KXUSEDCARCPI` | US used cars and trucks CPI in [month] | cpi | 29d | — | — |
| 315 | `CA0035` | Financial News & Data | `KXAUWPCC` | Australia Westpac Consumer Confidence Change | consumer confidence | 29d | — | — |
| 316 | `CA0052` | Brand Reviews | `KXISMSERVICES` | ISM Services PMI | ism services,services pmi | 29d | $4.99 | 1 |
| 317 | `CA0035` | Financial News & Data | `KXEHSHARE` | Existing home sales in time period | existing home sales | 29d | — | — |
| 318 | `CA0035` | Financial News & Data | `KXTRUFEGGS` | Truflation US CPI Eggs Index | cpi | 29d | — | — |
| 319 | `CA0035` | Financial News & Data | `KXUSPSPEND` | United States Personal Spending MoM | personal spending | 29d | — | — |
| 320 | `CA0052` | Brand Reviews | `KXCPIAPPAREL` | CPI on apparel | cpi | 29d | $4.99 | 1 |
| 321 | `CA004` | Secondary Market Ticket Sales -  | `KXUSDURABLE` | United States Durable Goods Orders MoM | durable goods | 29d | $32.23 | 2,425 |
| 322 | `CA0055` | SMB Workforce | `KXUSISMSERV` | United States ISM Services PMI | ism services,services pmi | 28d | $231.44 | 9,656 |
| 323 | `CA0055` | SMB Workforce | `KXUSNFP` | US nonfarm payrolls in [month] | nonfarm payrolls | 28d | $231.44 | 9,656 |
| 324 | `CA0013` | Mobile App | `KXUSEDCARCPI` | US used cars and trucks CPI in [month] | cpi | 28d | — | — |
| 325 | `CA0055` | SMB Workforce | `KXECONSTATU3` | UNEMPLOYMENT RATE MONTHLY | unemployment rate | 28d | $231.44 | 9,656 |
| 326 | `CA0055` | SMB Workforce | `KXJOLTS` | Job openings | jolts | 28d | $231.44 | 9,656 |
| 327 | `CA0055` | SMB Workforce | `KXJOBSRELEASE` | When will the BLS release a jobs report? | nonfarm payrolls | 28d | $231.44 | 9,656 |
| 328 | `CA0055` | SMB Workforce | `KX25U3SEP` | september 2025 u3 extension | unemployment rate | 28d | $231.44 | 9,656 |
| 329 | `CA0055` | SMB Workforce | `KXADP` | ADP employment change | adp employment | 28d | $231.44 | 9,656 |
| 330 | `CA0055` | SMB Workforce | `KXISMSERVICES` | ISM Services PMI | ism services,services pmi | 28d | $231.44 | 9,656 |
| 331 | `CA0055` | SMB Workforce | `KXPAYROLLSREV` | Previous jobs numbers revised above <X> in the nex | nonfarm payrolls | 28d | $231.44 | 9,656 |
| 332 | `CA0055` | SMB Workforce | `KXPAYROLLCANCEL` | Payrolls cancelled | nonfarm payrolls | 28d | $231.44 | 9,656 |
| 333 | `CA0055` | SMB Workforce | `KXUSDURABLE` | United States Durable Goods Orders MoM | durable goods | 28d | $231.44 | 9,656 |
| 334 | `CA0055` | SMB Workforce | `KXUSPSPEND` | United States Personal Spending MoM | personal spending | 28d | $231.44 | 9,656 |
| 335 | `CA0055` | SMB Workforce | `KXUSMICHCSP` | United States Michigan Consumer Sentiment Prel  | consumer sentiment,michigan cons | 28d | $231.44 | 9,656 |
| 336 | `CA0013` | Mobile App | `KXAUWPCC` | Australia Westpac Consumer Confidence Change | consumer confidence | 28d | — | — |
| 337 | `CA0013` | Mobile App | `KXADP` | ADP employment change | adp employment | 28d | — | — |
| 338 | `CA0013` | Mobile App | `KXUSRETAIL` | US retail sales MoM | retail sales | 28d | — | — |
| 339 | `CA0013` | Mobile App | `KXUSDURABLE` | United States Durable Goods Orders MoM | durable goods | 28d | — | — |
| 340 | `CA0013` | Mobile App | `KXISMSERVICES` | ISM Services PMI | ism services,services pmi | 28d | — | — |
| 341 | `CA0013` | Mobile App | `KXUSISMSERV` | United States ISM Services PMI | ism services,services pmi | 28d | — | — |
| 342 | `CA0013` | Mobile App | `KXJPCONCONF` | Japan Consumer Confidence | consumer confidence | 28d | — | — |
| 343 | `CA0013` | Mobile App | `KXCACPIYOY` | Canada Inflation Rate YoY | cpi | 28d | — | — |
| 344 | `CA0013` | Mobile App | `KXJOLTS` | Job openings | jolts | 28d | — | — |
| 345 | `CA0013` | Mobile App | `KXUSPSPEND` | United States Personal Spending MoM | personal spending | 28d | — | — |
| 346 | `CA0013` | Mobile App | `KXUSMICHCSP` | United States Michigan Consumer Sentiment Prel  | consumer sentiment,michigan cons | 28d | — | — |
| 347 | `CA0013` | Mobile App | `KXUSEDCAR` | US CPI print on used cars | cpi | 28d | — | — |
| 348 | `CA0013` | Mobile App | `KXUMICHOVR` | Michigan consumer sentiment above X in [year]? | consumer sentiment,michigan cons | 28d | — | — |
| 349 | `CA0013` | Mobile App | `KXEHSHARE` | Existing home sales in time period | existing home sales | 28d | — | — |
| 350 | `CA0013` | Mobile App | `KXCANHOUSTART` | Canada housing starts above X in [year]? | housing starts | 28d | — | — |
| 351 | `CA0013` | Mobile App | `RETAIL` | Retail sales growth | retail sales | 28d | — | — |
| 352 | `CA0013` | Mobile App | `KXRETAIL` | Retail sales growth | retail sales | 28d | — | — |
| 353 | `CA0013` | Mobile App | `KXEHSALES` | Existing home sales in time period | existing home sales | 28d | — | — |
| 354 | `CA0040` | Trade Claims | `KXUSEDCARCPI` | US used cars and trucks CPI in [month] | cpi | 27d | — | — |
| 355 | `CA0045B` | TikTok Shop | `KXCPIAPPAREL` | CPI on apparel | cpi | 27d | — | — |
| 356 | `CA0045B` | TikTok Shop | `KXRETAIL` | Retail sales growth | retail sales | 27d | — | — |
| 357 | `CA0040` | Trade Claims | `KXAUWPCC` | Australia Westpac Consumer Confidence Change | consumer confidence | 27d | — | — |
| 358 | `CA0040` | Trade Claims | `KXUSDURABLE` | United States Durable Goods Orders MoM | durable goods | 27d | — | — |
| 359 | `CA0056` | Credit Card – US Complete Panel | `KXACPICORE-` | US annual core inflation | core cpi | 27d | $8.77 | 2,432 |
| 360 | `CA0045B` | TikTok Shop | `RETAIL` | Retail sales growth | retail sales | 27d | — | — |
| 361 | `CA0045B` | TikTok Shop | `KXUSISMSERV` | United States ISM Services PMI | ism services,services pmi | 27d | — | — |
| 362 | `CA0056` | Credit Card – US Complete Panel | `KXECONSTATCORECPIYOY` | year over year core inflation | core cpi | 27d | $8.77 | 2,432 |
| 363 | `CA0056` | Credit Card – US Complete Panel | `CPICORE` | CPI core | cpi | 27d | $8.77 | 2,432 |
| 364 | `CA0045B` | TikTok Shop | `PCECORE` | US Core PCE inflation | core pce,pce | 27d | — | — |
| 365 | `CA0045B` | TikTok Shop | `KXUSPSPEND` | United States Personal Spending MoM | personal spending | 27d | — | — |
| 366 | `CA0056` | Credit Card – US Complete Panel | `KXUSPPI` | United States PPI MoM | ppi | 27d | $8.77 | 2,432 |
| 367 | `CA0056` | Credit Card – US Complete Panel | `KXCPICOMBO` | CPI Combo | cpi | 27d | $8.77 | 2,432 |
| 368 | `CA0056` | Credit Card – US Complete Panel | `KXAIRFARECPI` | US airline fares CPI in [month] | cpi | 27d | $8.77 | 2,432 |
| 369 | `CA0056` | Credit Card – US Complete Panel | `ACPICORE` | Annual core inflation | core cpi | 27d | $8.77 | 2,432 |
| 370 | `CA0056` | Credit Card – US Complete Panel | `KXTRUFCPIYE` | Truflation U.S. CPI Inflation Index EOY | cpi | 27d | $8.77 | 2,432 |
| 371 | `CA0056` | Credit Card – US Complete Panel | `CPICOREYOY` | Core inflation | core cpi | 27d | $8.77 | 2,432 |
| 372 | `CA0056` | Credit Card – US Complete Panel | `USEDCAR` | US CPI print on used cars | cpi | 27d | $8.77 | 2,432 |
| 373 | `CA0056` | Credit Card – US Complete Panel | `CPIDELAY` | CPI data released | cpi | 27d | $8.77 | 2,432 |
| 374 | `CA0056` | Credit Card – US Complete Panel | `KXTRUFCPI` | Truflation US CPI Inflation Index | cpi | 27d | $8.77 | 2,432 |
| 375 | `CA0056` | Credit Card – US Complete Panel | `CPIAPPAREL` | CPI on apparel | cpi | 27d | $8.77 | 2,432 |
| 376 | `CA0056` | Credit Card – US Complete Panel | `KXPCECORE` | US Core PCE inflation | core pce,pce | 27d | $8.77 | 2,432 |
| 377 | `CA0056` | Credit Card – US Complete Panel | `KXCPIFOOD` | CPI on food | cpi | 27d | $8.77 | 2,432 |
| 378 | `CA0056` | Credit Card – US Complete Panel | `KXUSPPIYOY` | US PPI YoY in [month] | ppi | 27d | $8.77 | 2,432 |
| 379 | `CA0056` | Credit Card – US Complete Panel | `KXECONSTATCPICORE` | month over month core inflation | core cpi | 27d | $8.77 | 2,432 |
| 380 | `CA0056` | Credit Card – US Complete Panel | `KXCPICORE220` | Will the BLS Core CPI YoY print below 2.20%  | core cpi,cpi | 27d | $8.77 | 2,432 |
| 381 | `CA0056` | Credit Card – US Complete Panel | `KXCPICOREA` | Core CPI annually | core cpi,cpi | 27d | $8.77 | 2,432 |
| 382 | `CA0056` | Credit Card – US Complete Panel | `KXRETAIL` | Retail sales growth | retail sales | 27d | $8.77 | 2,432 |
| 383 | `CA0056` | Credit Card – US Complete Panel | `KXRELEASECPI` | Will the BLS release October CPI data? | cpi | 27d | $8.77 | 2,432 |
| 384 | `CA0056` | Credit Card – US Complete Panel | `KXEHSHARE` | Existing home sales in time period | existing home sales | 27d | $8.77 | 2,432 |
| 385 | `CA0056` | Credit Card – US Complete Panel | `RETAIL` | Retail sales growth | retail sales | 27d | $8.77 | 2,432 |
| 386 | `CA0056` | Credit Card – US Complete Panel | `KXCPICOREYOY` | Core inflation | core cpi | 27d | $8.77 | 2,432 |
| 387 | `CA0056` | Credit Card – US Complete Panel | `KXCPIAPPAREL` | CPI on apparel | cpi | 27d | $8.77 | 2,432 |
| 388 | `CA0056` | Credit Card – US Complete Panel | `KXUSISMSERV` | United States ISM Services PMI | ism services,services pmi | 27d | $8.77 | 2,432 |
| 389 | `CA0056` | Credit Card – US Complete Panel | `KXUSPSPEND` | United States Personal Spending MoM | personal spending | 27d | $8.77 | 2,432 |
| 390 | `CA0056` | Credit Card – US Complete Panel | `KXUSMICHCSP` | United States Michigan Consumer Sentiment Prel  | consumer sentiment,michigan cons | 27d | $8.77 | 2,432 |
| 391 | `CA0056` | Credit Card – US Complete Panel | `CPI` | CPI | cpi | 27d | $8.77 | 2,432 |
| 392 | `CA0056` | Credit Card – US Complete Panel | `KXCOREUND` | Will Core CPI fall below x.x% in 2026? | core cpi,cpi | 27d | $8.77 | 2,432 |
| 393 | `CA0056` | Credit Card – US Complete Panel | `KXUMICHOVR` | Michigan consumer sentiment above X in [year]? | consumer sentiment,michigan cons | 27d | $8.77 | 2,432 |
| 394 | `CA0056` | Credit Card – US Complete Panel | `PCECORE` | US Core PCE inflation | core pce,pce | 27d | $8.77 | 2,432 |
| 395 | `CA0045B` | TikTok Shop | `KXISMSERVICES` | ISM Services PMI | ism services,services pmi | 27d | — | — |
| 396 | `CA0056` | Credit Card – US Complete Panel | `KXISMSERVICES` | ISM Services PMI | ism services,services pmi | 27d | $8.77 | 2,432 |
| 397 | `CA0056` | Credit Card – US Complete Panel | `KXCPICORE` | CPI core | cpi | 27d | $8.77 | 2,432 |
| 398 | `CA0045B` | TikTok Shop | `KXUSRETAIL` | US retail sales MoM | retail sales | 27d | — | — |
| 399 | `CA0045B` | TikTok Shop | `KXUSDURABLE` | United States Durable Goods Orders MoM | durable goods | 27d | — | — |
| 400 | `CA0045B` | TikTok Shop | `CPIAPPAREL` | CPI on apparel | cpi | 27d | — | — |
| 401 | `CA0056` | Credit Card – US Complete Panel | `KXUSRETAIL` | US retail sales MoM | retail sales | 27d | $8.77 | 2,432 |
| 402 | `CA0056` | Credit Card – US Complete Panel | `KXCPI` | CPI | cpi | 27d | $8.77 | 2,432 |
| 403 | `CA0056` | Credit Card – US Complete Panel | `KXCPIDELAY` | CPI data released | cpi | 27d | $8.77 | 2,432 |
| 404 | `CA0056` | Credit Card – US Complete Panel | `KXACPICORE` | Annual core inflation | core cpi | 27d | $8.77 | 2,432 |
| 405 | `CA0056` | Credit Card – US Complete Panel | `ACPICORE-` | US annual core inflation | core cpi | 27d | $8.77 | 2,432 |
| 406 | `CA0054` | App Intelligence | `KXUSMICHCSP` | United States Michigan Consumer Sentiment Prel  | consumer sentiment,michigan cons | 26d | $78.99 | 1,757 |
| 407 | `CA0047` | POS – Supermarket | `KXRETAIL` | Retail sales growth | retail sales | 26d | $436.22 | 1,216 |
| 408 | `CA0054` | App Intelligence | `KXUSPSPEND` | United States Personal Spending MoM | personal spending | 26d | $78.99 | 1,757 |
| 409 | `CA0047` | POS – Supermarket | `RETAIL` | Retail sales growth | retail sales | 26d | $436.22 | 1,216 |
| 410 | `CA0054` | App Intelligence | `KXCANHOUSTART` | Canada housing starts above X in [year]? | housing starts | 26d | $78.99 | 1,757 |
| 411 | `CA0054` | App Intelligence | `KXBUILDPERMS` | Building permits for month | building permits | 26d | $78.99 | 1,757 |
| 412 | `CA0047` | POS – Supermarket | `KXUSMICHCSP` | United States Michigan Consumer Sentiment Prel  | consumer sentiment,michigan cons | 26d | $436.22 | 1,216 |
| 413 | `CA0047` | POS – Supermarket | `KXCPICOMBO` | CPI Combo | cpi | 26d | $436.22 | 1,216 |
| 414 | `CA0054` | App Intelligence | `KXJPCONCONF` | Japan Consumer Confidence | consumer confidence | 26d | $78.99 | 1,757 |
| 415 | `CA0047` | POS – Supermarket | `CPICOREYOY` | Core inflation | core cpi | 26d | $436.22 | 1,216 |
| 416 | `CA0054` | App Intelligence | `KXHOME` | New home sales | new home sales | 26d | $78.99 | 1,757 |
| 417 | `CA0047` | POS – Supermarket | `KXUKCPIYOY` | United Kingdom Inflation Rate YoY | cpi | 26d | $436.22 | 1,216 |
| 418 | `CA0047` | POS – Supermarket | `ACPICORE` | Annual core inflation | core cpi | 26d | $436.22 | 1,216 |
| 419 | `CA0047` | POS – Supermarket | `KXUSPPIYOY` | US PPI YoY in [month] | ppi | 26d | $436.22 | 1,216 |
| 420 | `CA0047` | POS – Supermarket | `KXTRUFEGGS` | Truflation US CPI Eggs Index | cpi | 26d | $436.22 | 1,216 |
| 421 | `CA0047` | POS – Supermarket | `KXISMSERVICES` | ISM Services PMI | ism services,services pmi | 26d | $436.22 | 1,216 |
| 422 | `CA0054` | App Intelligence | `ACPICORE-` | US annual core inflation | core cpi | 26d | $78.99 | 1,757 |
| 423 | `CA0047` | POS – Supermarket | `KXTRUFCPI` | Truflation US CPI Inflation Index | cpi | 26d | $436.22 | 1,216 |
| 424 | `CA0054` | App Intelligence | `KXUSPPIYOY` | US PPI YoY in [month] | ppi | 26d | $78.99 | 1,757 |
| 425 | `CA0054` | App Intelligence | `KXDEGFK` | Germany GfK Consumer Confidence | consumer confidence | 26d | $78.99 | 1,757 |
| 426 | `CA0054` | App Intelligence | `KXUSIPMOM` | US industrial production MoM | industrial production | 26d | $78.99 | 1,757 |
| 427 | `CA0054` | App Intelligence | `RETAIL` | Retail sales growth | retail sales | 26d | $78.99 | 1,757 |
| 428 | `CA0054` | App Intelligence | `KXEHSALES` | Existing home sales in time period | existing home sales | 26d | $78.99 | 1,757 |
| 429 | `CA0054` | App Intelligence | `CPIUSEDCAR` | CPI on used cars | cpi | 26d | $78.99 | 1,757 |
| 430 | `CA0054` | App Intelligence | `KXACPICORE-` | US annual core inflation | core cpi | 26d | $78.99 | 1,757 |
| 431 | `CA0047` | POS – Supermarket | `KXUSISMSERV` | United States ISM Services PMI | ism services,services pmi | 26d | $436.22 | 1,216 |
| 432 | `CA0047` | POS – Supermarket | `KXCPICOREYOY` | Core inflation | core cpi | 26d | $436.22 | 1,216 |
| 433 | `CA0047` | POS – Supermarket | `KXITCPIPREL` | Italy Inflation Rate YoY Prel | cpi | 26d | $436.22 | 1,216 |
| 434 | `CA0054` | App Intelligence | `KXEHSHARE` | Existing home sales in time period | existing home sales | 26d | $78.99 | 1,757 |
| 435 | `CA0054` | App Intelligence | `KXCPIAPPAREL` | CPI on apparel | cpi | 26d | $78.99 | 1,757 |
| 436 | `CA0047` | POS – Supermarket | `KXACPICORE` | Annual core inflation | core cpi | 26d | $436.22 | 1,216 |
| 437 | `CA0054` | App Intelligence | `KXJOLTS` | Job openings | jolts | 26d | $78.99 | 1,757 |
| 438 | `CA0054` | App Intelligence | `KXUSEDCARCPI` | US used cars and trucks CPI in [month] | cpi | 26d | $78.99 | 1,757 |
| 439 | `CA0054` | App Intelligence | `KXUMICHOVR` | Michigan consumer sentiment above X in [year]? | consumer sentiment,michigan cons | 26d | $78.99 | 1,757 |
| 440 | `CA0054` | App Intelligence | `KXISMSERVICES` | ISM Services PMI | ism services,services pmi | 26d | $78.99 | 1,757 |
| 441 | `CA0054` | App Intelligence | `KXUSISMSERV` | United States ISM Services PMI | ism services,services pmi | 26d | $78.99 | 1,757 |
| 442 | `CA0054` | App Intelligence | `KXRETAIL` | Retail sales growth | retail sales | 26d | $78.99 | 1,757 |
| 443 | `CA0047` | POS – Supermarket | `KXUKRETAIL` | UK retail sales MoM | retail sales | 26d | $436.22 | 1,216 |
| 444 | `CA0047` | POS – Supermarket | `CPIFOOD` | CPI on food | cpi | 26d | $436.22 | 1,216 |
| 445 | `CA0054` | App Intelligence | `PCECORE` | US Core PCE inflation | core pce,pce | 26d | $78.99 | 1,757 |
| 446 | `CA0047` | POS – Supermarket | `KXCPIDELAY` | CPI data released | cpi | 26d | $436.22 | 1,216 |
| 447 | `CA0047` | POS – Supermarket | `KXACPICORE-` | US annual core inflation | core cpi | 26d | $436.22 | 1,216 |
| 448 | `CA0047` | POS – Supermarket | `KXECONSTATCORECPIYOY` | year over year core inflation | core cpi | 26d | $436.22 | 1,216 |
| 449 | `CA0047` | POS – Supermarket | `KXUSPSPEND` | United States Personal Spending MoM | personal spending | 26d | $436.22 | 1,216 |
| 450 | `CA0047` | POS – Supermarket | `CPIDELAY` | CPI data released | cpi | 26d | $436.22 | 1,216 |
| 451 | `CA0054` | App Intelligence | `CPIAPPAREL` | CPI on apparel | cpi | 26d | $78.99 | 1,757 |
| 452 | `CA0047` | POS – Supermarket | `ACPICORE-` | US annual core inflation | core cpi | 26d | $436.22 | 1,216 |
| 453 | `CA0047` | POS – Supermarket | `KXCPICORE` | CPI core | cpi | 26d | $436.22 | 1,216 |
| 454 | `CA0047` | POS – Supermarket | `CPI` | CPI | cpi | 26d | $436.22 | 1,216 |
| 455 | `CA0047` | POS – Supermarket | `KXCPICOREA` | Core CPI annually | core cpi,cpi | 26d | $436.22 | 1,216 |
| 456 | `CA0047` | POS – Supermarket | `CPICORE` | CPI core | cpi | 26d | $436.22 | 1,216 |
| 457 | `CA0047` | POS – Supermarket | `KXECONSTATCPICORE` | month over month core inflation | core cpi | 26d | $436.22 | 1,216 |
| 458 | `CA0047` | POS – Supermarket | `PCECORE` | US Core PCE inflation | core pce,pce | 26d | $436.22 | 1,216 |
| 459 | `CA0054` | App Intelligence | `KXUSRETAIL` | US retail sales MoM | retail sales | 26d | $78.99 | 1,757 |
| 460 | `CA0047` | POS – Supermarket | `KXCOREUND` | Will Core CPI fall below x.x% in 2026? | core cpi,cpi | 26d | $436.22 | 1,216 |
| 461 | `CA0054` | App Intelligence | `KXPCECORE` | US Core PCE inflation | core pce,pce | 26d | $78.99 | 1,757 |
| 462 | `CA0054` | App Intelligence | `USEDCAR` | US CPI print on used cars | cpi | 26d | $78.99 | 1,757 |
| 463 | `CA0047` | POS – Supermarket | `KXUSPPI` | United States PPI MoM | ppi | 26d | $436.22 | 1,216 |
| 464 | `CA0047` | POS – Supermarket | `KXJPCPIYOY` | Japan Inflation Rate YoY | cpi | 26d | $436.22 | 1,216 |
| 465 | `CA0054` | App Intelligence | `KXCPICOMBO` | CPI Combo | cpi | 26d | $78.99 | 1,757 |
| 466 | `CA0054` | App Intelligence | `KXAUWPCC` | Australia Westpac Consumer Confidence Change | consumer confidence | 26d | $78.99 | 1,757 |
| 467 | `CA0054` | App Intelligence | `KXCACPIYOY` | Canada Inflation Rate YoY | cpi | 26d | $78.99 | 1,757 |
| 468 | `CA0054` | App Intelligence | `KXADP` | ADP employment change | adp employment | 26d | $78.99 | 1,757 |
| 469 | `CA0054` | App Intelligence | `KXUSEDCAR` | US CPI print on used cars | cpi | 26d | $78.99 | 1,757 |
| 470 | `CA0054` | App Intelligence | `KXCPIUSEDCAR` | CPI on used cars | cpi | 26d | $78.99 | 1,757 |
| 471 | `CA0054` | App Intelligence | `KXNHSALES` | New home sales in time period | new home sales | 26d | $78.99 | 1,757 |
| 472 | `CA0054` | App Intelligence | `KXAIRFARECPI` | US airline fares CPI in [month] | cpi | 26d | $78.99 | 1,757 |
| 473 | `CA0054` | App Intelligence | `KXSHELTERCPI` | US shelter CPI in [month] | cpi | 26d | $78.99 | 1,757 |
| 474 | `CA0054` | App Intelligence | `HOME` | New home sales | new home sales | 26d | $78.99 | 1,757 |
| 475 | `CA0047` | POS – Supermarket | `KXCPIFOOD` | CPI on food | cpi | 26d | $436.22 | 1,216 |
| 476 | `CA0054` | App Intelligence | `KXECONSTATCORECPIYOY` | year over year core inflation | core cpi | 26d | $78.99 | 1,757 |
| 477 | `CA0054` | App Intelligence | `KXUSDURABLE` | United States Durable Goods Orders MoM | durable goods | 26d | $78.99 | 1,757 |
| 478 | `CA0047` | POS – Supermarket | `KXAUWPCC` | Australia Westpac Consumer Confidence Change | consumer confidence | 26d | $436.22 | 1,216 |
| 479 | `CA0047` | POS – Supermarket | `KXFRCPIPREL` | France Inflation Rate YoY Prel  | cpi | 26d | $436.22 | 1,216 |
| 480 | `CA0047` | POS – Supermarket | `KXPCECORE` | US Core PCE inflation | core pce,pce | 26d | $436.22 | 1,216 |
| 481 | `CA0054` | App Intelligence | `KXUSGASCPI` | US gasoline CPI in [month] | cpi | 26d | $78.99 | 1,757 |
| 482 | `CA0054` | App Intelligence | `KXCHIPYOY` | China Industrial Production YoY | industrial production | 26d | $78.99 | 1,757 |
| 483 | `CA0047` | POS – Supermarket | `KXCACPIYOY` | Canada Inflation Rate YoY | cpi | 26d | $436.22 | 1,216 |
| 484 | `CA0047` | POS – Supermarket | `KXCPI` | CPI | cpi | 26d | $436.22 | 1,216 |
| 485 | `CA0047` | POS – Supermarket | `KXCPICORE220` | Will the BLS Core CPI YoY print below 2.20%  | core cpi,cpi | 26d | $436.22 | 1,216 |
| 486 | `CA0047` | POS – Supermarket | `KXRELEASECPI` | Will the BLS release October CPI data? | cpi | 26d | $436.22 | 1,216 |
| 487 | `CA0047` | POS – Supermarket | `KXTRUFCPIYE` | Truflation U.S. CPI Inflation Index EOY | cpi | 26d | $436.22 | 1,216 |
| 488 | `CA0047` | POS – Supermarket | `KXUSRETAIL` | US retail sales MoM | retail sales | 26d | $436.22 | 1,216 |
| 489 | `CA0054` | App Intelligence | `KXUKCPIYOY` | United Kingdom Inflation Rate YoY | cpi | 26d | $78.99 | 1,757 |
| 490 | `CA0054` | App Intelligence | `KXTRUFEGGS` | Truflation US CPI Eggs Index | cpi | 26d | $78.99 | 1,757 |
| 491 | `CA0047` | POS – Supermarket | `KXPPIVSCPI` | PPI YoY exceeds CPI YoY for [time period] | cpi,ppi | 26d | $436.22 | 1,216 |
| 492 | `CA0060` | Foot Traffic | `KXHOME` | New home sales | new home sales | 25d | $29.05 | 1,216 |
| 493 | `CA0060` | Foot Traffic | `KXJPCONCONF` | Japan Consumer Confidence | consumer confidence | 25d | $29.05 | 1,216 |
| 494 | `CA0060` | Foot Traffic | `KXUSMICHCSP` | United States Michigan Consumer Sentiment Prel  | consumer sentiment,michigan cons | 25d | $29.05 | 1,216 |
| 495 | `CA0060` | Foot Traffic | `KXUSISMSERV` | United States ISM Services PMI | ism services,services pmi | 25d | $29.05 | 1,216 |
| 496 | `CA0058` | Credit Card – Health Spend | `KXCPICORE220` | Will the BLS Core CPI YoY print below 2.20%  | core cpi,cpi | 25d | $8.74 | 1,216 |
| 497 | `CA0058` | Credit Card – Health Spend | `KXTRUFCPIYE` | Truflation U.S. CPI Inflation Index EOY | cpi | 25d | $8.74 | 1,216 |
| 498 | `CA0058` | Credit Card – Health Spend | `KXCPICOMBO` | CPI Combo | cpi | 25d | $8.74 | 1,216 |
| 499 | `CA0060` | Foot Traffic | `KXCPIFOOD` | CPI on food | cpi | 25d | $29.05 | 1,216 |
| 500 | `CA0058` | Credit Card – Health Spend | `KXTRUFCPI` | Truflation US CPI Inflation Index | cpi | 25d | $8.74 | 1,216 |
| 501 | `CA0058` | Credit Card – Health Spend | `KXUSRETAIL` | US retail sales MoM | retail sales | 25d | $8.74 | 1,216 |
| 502 | `CA0058` | Credit Card – Health Spend | `CPIDELAY` | CPI data released | cpi | 25d | $8.74 | 1,216 |
| 503 | `CA0058` | Credit Card – Health Spend | `KXPCECORE` | US Core PCE inflation | core pce,pce | 25d | $8.74 | 1,216 |
| 504 | `CA0060` | Foot Traffic | `KXUSNFP` | US nonfarm payrolls in [month] | nonfarm payrolls | 25d | $29.05 | 1,216 |
| 505 | `CA0060` | Foot Traffic | `KXAUWPCC` | Australia Westpac Consumer Confidence Change | consumer confidence | 25d | $29.05 | 1,216 |
| 506 | `CA0060` | Foot Traffic | `HOME` | New home sales | new home sales | 25d | $29.05 | 1,216 |
| 507 | `CA0060` | Foot Traffic | `KXJOBSRELEASE` | When will the BLS release a jobs report? | nonfarm payrolls | 25d | $29.05 | 1,216 |
| 508 | `CA0060` | Foot Traffic | `KXUKRETAIL` | UK retail sales MoM | retail sales | 25d | $29.05 | 1,216 |
| 509 | `CA0058` | Credit Card – Health Spend | `KXECONSTATCORECPIYOY` | year over year core inflation | core cpi | 25d | $8.74 | 1,216 |
| 510 | `CA0060` | Foot Traffic | `KXUSPSPEND` | United States Personal Spending MoM | personal spending | 25d | $29.05 | 1,216 |
| 511 | `CA0060` | Foot Traffic | `KXISMSERVICES` | ISM Services PMI | ism services,services pmi | 25d | $29.05 | 1,216 |
| 512 | `CA0060` | Foot Traffic | `KXPCECORE` | US Core PCE inflation | core pce,pce | 25d | $29.05 | 1,216 |
| 513 | `CA0060` | Foot Traffic | `KXCACPIYOY` | Canada Inflation Rate YoY | cpi | 25d | $29.05 | 1,216 |
| 514 | `CA0060` | Foot Traffic | `KXUSDURABLE` | United States Durable Goods Orders MoM | durable goods | 25d | $29.05 | 1,216 |
| 515 | `CA0060` | Foot Traffic | `KXCPICORE220` | Will the BLS Core CPI YoY print below 2.20%  | core cpi,cpi | 25d | $29.05 | 1,216 |
| 516 | `CA0060` | Foot Traffic | `KXADP` | ADP employment change | adp employment | 25d | $29.05 | 1,216 |
| 517 | `CA0060` | Foot Traffic | `PCECORE` | US Core PCE inflation | core pce,pce | 25d | $29.05 | 1,216 |
| 518 | `CA0060` | Foot Traffic | `KXNHSALES` | New home sales in time period | new home sales | 25d | $29.05 | 1,216 |
| 519 | `CA0060` | Foot Traffic | `KXCPICOREA` | Core CPI annually | core cpi,cpi | 25d | $29.05 | 1,216 |
| 520 | `CA0060` | Foot Traffic | `KXUMICHOVR` | Michigan consumer sentiment above X in [year]? | consumer sentiment,michigan cons | 25d | $29.05 | 1,216 |
| 521 | `CA0060` | Foot Traffic | `CPIAPPAREL` | CPI on apparel | cpi | 25d | $29.05 | 1,216 |
| 522 | `CA0060` | Foot Traffic | `KXEHSALES` | Existing home sales in time period | existing home sales | 25d | $29.05 | 1,216 |
| 523 | `CA0060` | Foot Traffic | `CPISHELTER` | CPI on shelter | cpi | 25d | $29.05 | 1,216 |
| 524 | `CA0060` | Foot Traffic | `CPIDELAY` | CPI data released | cpi | 25d | $29.05 | 1,216 |
| 525 | `CA0060` | Foot Traffic | `KXCPICOMBO` | CPI Combo | cpi | 25d | $29.05 | 1,216 |
| 526 | `CA0049` | Medical & Pharmacy Open Claims | `KXUSISMSERV` | United States ISM Services PMI | ism services,services pmi | 25d | $136.59 | 2,841 |
| 527 | `CA0060` | Foot Traffic | `KXUSRETAIL` | US retail sales MoM | retail sales | 25d | $29.05 | 1,216 |
| 528 | `CA0058` | Credit Card – Health Spend | `PCECORE` | US Core PCE inflation | core pce,pce | 25d | $8.74 | 1,216 |
| 529 | `CA0049` | Medical & Pharmacy Open Claims | `KXUSMICHCSP` | United States Michigan Consumer Sentiment Prel  | consumer sentiment,michigan cons | 25d | $136.59 | 2,841 |
| 530 | `CA0060` | Foot Traffic | `KXRETAIL` | Retail sales growth | retail sales | 25d | $29.05 | 1,216 |
| 531 | `CA0049` | Medical & Pharmacy Open Claims | `KXTRUFCPI` | Truflation US CPI Inflation Index | cpi | 25d | $136.59 | 2,841 |
| 532 | `CA0049` | Medical & Pharmacy Open Claims | `CPICOREYOY` | Core inflation | core cpi | 25d | $136.59 | 2,841 |
| 533 | `CA0049` | Medical & Pharmacy Open Claims | `KXUSPPIYOY` | US PPI YoY in [month] | ppi | 25d | $136.59 | 2,841 |
| 534 | `CA0049` | Medical & Pharmacy Open Claims | `KXISMSERVICES` | ISM Services PMI | ism services,services pmi | 25d | $136.59 | 2,841 |
| 535 | `CA0049` | Medical & Pharmacy Open Claims | `KXPCECORE` | US Core PCE inflation | core pce,pce | 25d | $136.59 | 2,841 |
| 536 | `CA0049` | Medical & Pharmacy Open Claims | `KXTRUFCPIYE` | Truflation U.S. CPI Inflation Index EOY | cpi | 25d | $136.59 | 2,841 |
| 537 | `CA0049` | Medical & Pharmacy Open Claims | `KXUSPPI` | United States PPI MoM | ppi | 25d | $136.59 | 2,841 |
| 538 | `CA0049` | Medical & Pharmacy Open Claims | `KXCPICOMBO` | CPI Combo | cpi | 25d | $136.59 | 2,841 |
| 539 | `CA0049` | Medical & Pharmacy Open Claims | `KXACPICORE-` | US annual core inflation | core cpi | 25d | $136.59 | 2,841 |
| 540 | `CA0049` | Medical & Pharmacy Open Claims | `PCECORE` | US Core PCE inflation | core pce,pce | 25d | $136.59 | 2,841 |
| 541 | `CA0049` | Medical & Pharmacy Open Claims | `KXCPI` | CPI | cpi | 25d | $136.59 | 2,841 |
| 542 | `CA0049` | Medical & Pharmacy Open Claims | `KXUSPSPEND` | United States Personal Spending MoM | personal spending | 25d | $136.59 | 2,841 |
| 543 | `CA0060` | Foot Traffic | `RETAIL` | Retail sales growth | retail sales | 25d | $29.05 | 1,216 |
| 544 | `CA0049` | Medical & Pharmacy Open Claims | `CPI` | CPI | cpi | 25d | $136.59 | 2,841 |
| 545 | `CA0060` | Foot Traffic | `KXEHSHARE` | Existing home sales in time period | existing home sales | 25d | $29.05 | 1,216 |
| 546 | `CA0049` | Medical & Pharmacy Open Claims | `KXACPICORE` | Annual core inflation | core cpi | 25d | $136.59 | 2,841 |
| 547 | `CA0058` | Credit Card – Health Spend | `KXUMICHOVR` | Michigan consumer sentiment above X in [year]? | consumer sentiment,michigan cons | 25d | $8.74 | 1,216 |
| 548 | `CA0049` | Medical & Pharmacy Open Claims | `ACPICORE-` | US annual core inflation | core cpi | 25d | $136.59 | 2,841 |
| 549 | `CA0058` | Credit Card – Health Spend | `KXUSPPIYOY` | US PPI YoY in [month] | ppi | 25d | $8.74 | 1,216 |
| 550 | `CA0058` | Credit Card – Health Spend | `KXUSPSPEND` | United States Personal Spending MoM | personal spending | 25d | $8.74 | 1,216 |
| 551 | `CA0049` | Medical & Pharmacy Open Claims | `KXCACPIYOY` | Canada Inflation Rate YoY | cpi | 25d | $136.59 | 2,841 |
| 552 | `CA0058` | Credit Card – Health Spend | `ACPICORE-` | US annual core inflation | core cpi | 25d | $8.74 | 1,216 |
| 553 | `CA0058` | Credit Card – Health Spend | `KXCPI` | CPI | cpi | 25d | $8.74 | 1,216 |
| 554 | `CA0049` | Medical & Pharmacy Open Claims | `KXCPICOREA` | Core CPI annually | core cpi,cpi | 25d | $136.59 | 2,841 |
| 555 | `CA0058` | Credit Card – Health Spend | `KXCPIDELAY` | CPI data released | cpi | 25d | $8.74 | 1,216 |
| 556 | `CA0049` | Medical & Pharmacy Open Claims | `KXCPICORE220` | Will the BLS Core CPI YoY print below 2.20%  | core cpi,cpi | 25d | $136.59 | 2,841 |
| 557 | `CA0058` | Credit Card – Health Spend | `CPI` | CPI | cpi | 25d | $8.74 | 1,216 |
| 558 | `CA0058` | Credit Card – Health Spend | `KXCOREUND` | Will Core CPI fall below x.x% in 2026? | core cpi,cpi | 25d | $8.74 | 1,216 |
| 559 | `CA0058` | Credit Card – Health Spend | `KXUSMICHCSP` | United States Michigan Consumer Sentiment Prel  | consumer sentiment,michigan cons | 25d | $8.74 | 1,216 |
| 560 | `CA0060` | Foot Traffic | `KXCPIAPPAREL` | CPI on apparel | cpi | 25d | $29.05 | 1,216 |
| 561 | `CA0028` | Credit Card – US Detailed Panel | `RETAIL` | Retail sales growth | retail sales | 23d | $54.72 | 3,667 |
| 562 | `CA0028` | Credit Card – US Detailed Panel | `KXCPIAPPAREL` | CPI on apparel | cpi | 23d | $54.72 | 3,667 |
| 563 | `CA0028` | Credit Card – US Detailed Panel | `CPICOREYOY` | Core inflation | core cpi | 23d | $54.72 | 3,667 |
| 564 | `CA0031` | Credit Card - US and CAN General | `KXUSMICHCSP` | United States Michigan Consumer Sentiment Prel  | consumer sentiment,michigan cons | 23d | — | — |
| 565 | `CA0028` | Credit Card – US Detailed Panel | `CPICORE` | CPI core | cpi | 23d | $54.72 | 3,667 |
| 566 | `CA0028` | Credit Card – US Detailed Panel | `KXCPI` | CPI | cpi | 23d | $54.72 | 3,667 |
| 567 | `CA0028` | Credit Card – US Detailed Panel | `KXUSPSPEND` | United States Personal Spending MoM | personal spending | 23d | $54.72 | 3,667 |
| 568 | `CA0028` | Credit Card – US Detailed Panel | `PCECORE` | US Core PCE inflation | core pce,pce | 23d | $54.72 | 3,667 |
| 569 | `CA0028` | Credit Card – US Detailed Panel | `KXCPICOREA` | Core CPI annually | core cpi,cpi | 23d | $54.72 | 3,667 |
| 570 | `CA0028` | Credit Card – US Detailed Panel | `KXISMSERVICES` | ISM Services PMI | ism services,services pmi | 23d | $54.72 | 3,667 |
| 571 | `CA0028` | Credit Card – US Detailed Panel | `CPI` | CPI | cpi | 23d | $54.72 | 3,667 |
| 572 | `CA0028` | Credit Card – US Detailed Panel | `KXACPICORE` | Annual core inflation | core cpi | 23d | $54.72 | 3,667 |
| 573 | `CA0028` | Credit Card – US Detailed Panel | `KXUMICHOVR` | Michigan consumer sentiment above X in [year]? | consumer sentiment,michigan cons | 23d | $54.72 | 3,667 |
| 574 | `CA0028` | Credit Card – US Detailed Panel | `KXRETAIL` | Retail sales growth | retail sales | 23d | $54.72 | 3,667 |
| 575 | `CA0028` | Credit Card – US Detailed Panel | `KXCPICORE` | CPI core | cpi | 23d | $54.72 | 3,667 |
| 576 | `CA0028` | Credit Card – US Detailed Panel | `ACPICORE-` | US annual core inflation | core cpi | 23d | $54.72 | 3,667 |
| 577 | `CA0028` | Credit Card – US Detailed Panel | `KXUSMICHCSP` | United States Michigan Consumer Sentiment Prel  | consumer sentiment,michigan cons | 23d | $54.72 | 3,667 |
| 578 | `CA0028` | Credit Card – US Detailed Panel | `KXTRUFCPIYE` | Truflation U.S. CPI Inflation Index EOY | cpi | 23d | $54.72 | 3,667 |
| 579 | `CA0042` | Credit Card – EU Detailed Panel | `RETAIL` | Retail sales growth | retail sales | 23d | — | — |
| 580 | `CA0028` | Credit Card – US Detailed Panel | `ACPICORE` | Annual core inflation | core cpi | 23d | $54.72 | 3,667 |
| 581 | `CA0028` | Credit Card – US Detailed Panel | `KXTRUFCPI` | Truflation US CPI Inflation Index | cpi | 23d | $54.72 | 3,667 |
| 582 | `CA0031` | Credit Card - US and CAN General | `KXUSISMSERV` | United States ISM Services PMI | ism services,services pmi | 23d | — | — |
| 583 | `CA0028` | Credit Card – US Detailed Panel | `CPIAPPAREL` | CPI on apparel | cpi | 23d | $54.72 | 3,667 |
| 584 | `CA0028` | Credit Card – US Detailed Panel | `KXUSPPIYOY` | US PPI YoY in [month] | ppi | 23d | $54.72 | 3,667 |
| 585 | `CA0028` | Credit Card – US Detailed Panel | `USEDCAR` | US CPI print on used cars | cpi | 23d | $54.72 | 3,667 |
| 586 | `CA0028` | Credit Card – US Detailed Panel | `KXCPICOMBO` | CPI Combo | cpi | 23d | $54.72 | 3,667 |
| 587 | `CA0028` | Credit Card – US Detailed Panel | `KXUSPPI` | United States PPI MoM | ppi | 23d | $54.72 | 3,667 |
| 588 | `CA0031` | Credit Card - US and CAN General | `KXCPICOREYOY` | Core inflation | core cpi | 23d | — | — |
| 589 | `CA0028` | Credit Card – US Detailed Panel | `KXUSISMSERV` | United States ISM Services PMI | ism services,services pmi | 23d | $54.72 | 3,667 |
| 590 | `CA0028` | Credit Card – US Detailed Panel | `KXCPICOREYOY` | Core inflation | core cpi | 23d | $54.72 | 3,667 |
| 591 | `CA0042` | Credit Card – EU Detailed Panel | `KXCPIDELAY` | CPI data released | cpi | 23d | — | — |
| 592 | `CA0042` | Credit Card – EU Detailed Panel | `KXDECPIPREL` | Germany Inflation Rate YoY Prel | cpi | 23d | — | — |
| 593 | `CA0028` | Credit Card – US Detailed Panel | `KXACPICORE-` | US annual core inflation | core cpi | 23d | $54.72 | 3,667 |
| 594 | `CA0042` | Credit Card – EU Detailed Panel | `KXRETAIL` | Retail sales growth | retail sales | 23d | — | — |
| 595 | `CA0042` | Credit Card – EU Detailed Panel | `KXUKRETAIL` | UK retail sales MoM | retail sales | 23d | — | — |
| 596 | `CA0042` | Credit Card – EU Detailed Panel | `KXACPICORE` | Annual core inflation | core cpi | 23d | — | — |
| 597 | `CA0042` | Credit Card – EU Detailed Panel | `KXCPI` | CPI | cpi | 23d | — | — |
| 598 | `CA0042` | Credit Card – EU Detailed Panel | `KXCOREUND` | Will Core CPI fall below x.x% in 2026? | core cpi,cpi | 23d | — | — |
| 599 | `CA0042` | Credit Card – EU Detailed Panel | `KXUKCPIYOY` | United Kingdom Inflation Rate YoY | cpi | 23d | — | — |
| 600 | `CA0034` | POS - Instore and Online | `KXPCECORE` | US Core PCE inflation | core pce,pce | 23d | $17.48 | 1,215 |
| 601 | `CA0042` | Credit Card – EU Detailed Panel | `CPICOREYOY` | Core inflation | core cpi | 23d | — | — |
| 602 | `CA0042` | Credit Card – EU Detailed Panel | `KXDEGFK` | Germany GfK Consumer Confidence | consumer confidence | 23d | — | — |
| 603 | `CA0042` | Credit Card – EU Detailed Panel | `KXISMSERVICES` | ISM Services PMI | ism services,services pmi | 23d | — | — |
| 604 | `CA0042` | Credit Card – EU Detailed Panel | `KXCPIAPPAREL` | CPI on apparel | cpi | 23d | — | — |
| 605 | `CA0034` | POS - Instore and Online | `KXTRUFCPIYE` | Truflation U.S. CPI Inflation Index EOY | cpi | 23d | $17.48 | 1,215 |
| 606 | `CA0042` | Credit Card – EU Detailed Panel | `CPI` | CPI | cpi | 23d | — | — |
| 607 | `CA0053` | Job Movements | `KXUSMICHCSP` | United States Michigan Consumer Sentiment Prel  | consumer sentiment,michigan cons | 23d | $4.99 | 2 |
| 608 | `CA0028` | Credit Card – US Detailed Panel | `KXPCECORE` | US Core PCE inflation | core pce,pce | 23d | $54.72 | 3,667 |
| 609 | `CA0042` | Credit Card – EU Detailed Panel | `KXCPICOMBO` | CPI Combo | cpi | 23d | — | — |
| 610 | `CA0029` | POS - Convenience Stores | `KXCPICORE220` | Will the BLS Core CPI YoY print below 2.20%  | core cpi,cpi | 23d | $26.04 | 1,216 |
| 611 | `CA0042` | Credit Card – EU Detailed Panel | `KXFRCPIPREL` | France Inflation Rate YoY Prel  | cpi | 23d | — | — |
| 612 | `CA0042` | Credit Card – EU Detailed Panel | `KXITCPIPREL` | Italy Inflation Rate YoY Prel | cpi | 23d | — | — |
| 613 | `CA0031` | Credit Card - US and CAN General | `CPI` | CPI | cpi | 23d | — | — |
| 614 | `CA0053` | Job Movements | `KXUSNFP` | US nonfarm payrolls in [month] | nonfarm payrolls | 23d | $4.99 | 2 |
| 615 | `CA0042` | Credit Card – EU Detailed Panel | `KXCPICOREYOY` | Core inflation | core cpi | 23d | — | — |
| 616 | `CA0042` | Credit Card – EU Detailed Panel | `KXEZCPIYOYF` | Euro Area Inflation Rate YoY Flash | cpi | 23d | — | — |
| 617 | `CA0053` | Job Movements | `KXUSISMSERV` | United States ISM Services PMI | ism services,services pmi | 23d | $4.99 | 2 |
| 618 | `CA0053` | Job Movements | `KX25U3SEP` | september 2025 u3 extension | unemployment rate | 23d | $4.99 | 2 |
| 619 | `CA0053` | Job Movements | `KXPAYROLLSREV` | Previous jobs numbers revised above <X> in the nex | nonfarm payrolls | 23d | $4.99 | 2 |
| 620 | `CA0029` | POS - Convenience Stores | `KXCPIGAS` | CPI on gas | cpi | 23d | $26.04 | 1,216 |
| 621 | `CA0031` | Credit Card - US and CAN General | `KXTRUFCPIYE` | Truflation U.S. CPI Inflation Index EOY | cpi | 23d | — | — |
| 622 | `CA0042` | Credit Card – EU Detailed Panel | `CPIAPPAREL` | CPI on apparel | cpi | 23d | — | — |
| 623 | `CA0029` | POS - Convenience Stores | `KXUSGASCPI` | US gasoline CPI in [month] | cpi | 23d | $26.04 | 1,216 |
| 624 | `CA0034` | POS - Instore and Online | `KXUSISMSERV` | United States ISM Services PMI | ism services,services pmi | 23d | $17.48 | 1,215 |
| 625 | `CA0031` | Credit Card - US and CAN General | `KXCPICOMBO` | CPI Combo | cpi | 23d | — | — |
| 626 | `CA0034` | POS - Instore and Online | `KXUSDURABLE` | United States Durable Goods Orders MoM | durable goods | 23d | $17.48 | 1,215 |
| 627 | `CA0028` | Credit Card – US Detailed Panel | `KXUSRETAIL` | US retail sales MoM | retail sales | 23d | $54.72 | 3,667 |
| 628 | `CA0034` | POS - Instore and Online | `KXCPICOREYOY` | Core inflation | core cpi | 23d | $17.48 | 1,215 |
| 629 | `CA0031` | Credit Card - US and CAN General | `KXPCECORE` | US Core PCE inflation | core pce,pce | 23d | — | — |
| 630 | `CA0053` | Job Movements | `KXPAYROLLCANCEL` | Payrolls cancelled | nonfarm payrolls | 23d | $4.99 | 2 |
| 631 | `CA0031` | Credit Card - US and CAN General | `KXUSRETAIL` | US retail sales MoM | retail sales | 23d | — | — |
| 632 | `CA0031` | Credit Card - US and CAN General | `KXCPICORE220` | Will the BLS Core CPI YoY print below 2.20%  | core cpi,cpi | 23d | — | — |
| 633 | `CA0053` | Job Movements | `KXEHSHARE` | Existing home sales in time period | existing home sales | 23d | $4.99 | 2 |
| 634 | `CA0028` | Credit Card – US Detailed Panel | `KXCPICORE220` | Will the BLS Core CPI YoY print below 2.20%  | core cpi,cpi | 23d | $54.72 | 3,667 |
| 635 | `CA0053` | Job Movements | `KXADP` | ADP employment change | adp employment | 23d | $4.99 | 2 |
| 636 | `CA0053` | Job Movements | `KXJOBSRELEASE` | When will the BLS release a jobs report? | nonfarm payrolls | 23d | $4.99 | 2 |
| 637 | `CA0053` | Job Movements | `KXISMSERVICES` | ISM Services PMI | ism services,services pmi | 23d | $4.99 | 2 |
| 638 | `CA0034` | POS - Instore and Online | `KXCPICORE220` | Will the BLS Core CPI YoY print below 2.20%  | core cpi,cpi | 23d | $17.48 | 1,215 |
| 639 | `CA0034` | POS - Instore and Online | `KXUSRETAIL` | US retail sales MoM | retail sales | 23d | $17.48 | 1,215 |
| 640 | `CA0034` | POS - Instore and Online | `KXTRUFHOUCPI` | Truflation US CPI Housing Inflation Index | cpi | 23d | $17.48 | 1,215 |
| 641 | `CA0034` | POS - Instore and Online | `KXRELEASECPI` | Will the BLS release October CPI data? | cpi | 23d | $17.48 | 1,215 |
| 642 | `CA0029` | POS - Convenience Stores | `KXUSPPIYOY` | US PPI YoY in [month] | ppi | 23d | $26.04 | 1,216 |
| 643 | `CA0034` | POS - Instore and Online | `KXUSPPI` | United States PPI MoM | ppi | 23d | $17.48 | 1,215 |
| 644 | `CA0029` | POS - Convenience Stores | `KXTRUFCPI` | Truflation US CPI Inflation Index | cpi | 23d | $26.04 | 1,216 |
| 645 | `CA0034` | POS - Instore and Online | `KXAUWPCC` | Australia Westpac Consumer Confidence Change | consumer confidence | 23d | $17.48 | 1,215 |
| 646 | `CA0034` | POS - Instore and Online | `KXCPIFOOD` | CPI on food | cpi | 23d | $17.48 | 1,215 |
| 647 | `CA0034` | POS - Instore and Online | `CPIDELAY` | CPI data released | cpi | 23d | $17.48 | 1,215 |
| 648 | `CA0029` | POS - Convenience Stores | `CPICOREYOY` | Core inflation | core cpi | 23d | $26.04 | 1,216 |
| 649 | `CA0031` | Credit Card - US and CAN General | `KXCACPIYOY` | Canada Inflation Rate YoY | cpi | 23d | — | — |
| 650 | `CA0028` | Credit Card – US Detailed Panel | `KXECONSTATCORECPIYOY` | year over year core inflation | core cpi | 23d | $54.72 | 3,667 |
| 651 | `CA0029` | POS - Convenience Stores | `CPIGAS` | CPI on gas | cpi | 23d | $26.04 | 1,216 |
| 652 | `CA0028` | Credit Card – US Detailed Panel | `KXCOREUND` | Will Core CPI fall below x.x% in 2026? | core cpi,cpi | 23d | $54.72 | 3,667 |
| 653 | `CA0034` | POS - Instore and Online | `KXCPICORE` | CPI core | cpi | 23d | $17.48 | 1,215 |
| 654 | `CA0029` | POS - Convenience Stores | `KXCPI` | CPI | cpi | 23d | $26.04 | 1,216 |
| 655 | `CA0029` | POS - Convenience Stores | `KXRETAIL` | Retail sales growth | retail sales | 23d | $26.04 | 1,216 |
| 656 | `CA0029` | POS - Convenience Stores | `KXUSPSPEND` | United States Personal Spending MoM | personal spending | 23d | $26.04 | 1,216 |
| 657 | `CA0029` | POS - Convenience Stores | `PCECORE` | US Core PCE inflation | core pce,pce | 23d | $26.04 | 1,216 |
| 658 | `CA0029` | POS - Convenience Stores | `CPIFOOD` | CPI on food | cpi | 23d | $26.04 | 1,216 |
| 659 | `CA0029` | POS - Convenience Stores | `KXUSISMSERV` | United States ISM Services PMI | ism services,services pmi | 23d | $26.04 | 1,216 |
| 660 | `CA0029` | POS - Convenience Stores | `KXTRUFCPIYE` | Truflation U.S. CPI Inflation Index EOY | cpi | 23d | $26.04 | 1,216 |
| 661 | `CA0029` | POS - Convenience Stores | `KXCPIDELAY` | CPI data released | cpi | 23d | $26.04 | 1,216 |
| 662 | `CA0029` | POS - Convenience Stores | `KXCPICOREA` | Core CPI annually | core cpi,cpi | 23d | $26.04 | 1,216 |
| 663 | `CA0029` | POS - Convenience Stores | `KXCOREUND` | Will Core CPI fall below x.x% in 2026? | core cpi,cpi | 23d | $26.04 | 1,216 |
| 664 | `CA0029` | POS - Convenience Stores | `CPICORE` | CPI core | cpi | 23d | $26.04 | 1,216 |
| 665 | `CA0029` | POS - Convenience Stores | `RETAIL` | Retail sales growth | retail sales | 23d | $26.04 | 1,216 |
| 666 | `CA0029` | POS - Convenience Stores | `KXUSMICHCSP` | United States Michigan Consumer Sentiment Prel  | consumer sentiment,michigan cons | 23d | $26.04 | 1,216 |
| 667 | `CA0029` | POS - Convenience Stores | `CPI` | CPI | cpi | 23d | $26.04 | 1,216 |
| 668 | `CA0034` | POS - Instore and Online | `KXCPIDELAY` | CPI data released | cpi | 23d | $17.48 | 1,215 |
| 669 | `CA0029` | POS - Convenience Stores | `KXACPICORE-` | US annual core inflation | core cpi | 23d | $26.04 | 1,216 |
| 670 | `CA0034` | POS - Instore and Online | `KXCPI` | CPI | cpi | 23d | $17.48 | 1,215 |
| 671 | `CA0029` | POS - Convenience Stores | `KXPCECORE` | US Core PCE inflation | core pce,pce | 23d | $26.04 | 1,216 |
| 672 | `CA0034` | POS - Instore and Online | `KXACPICORE` | Annual core inflation | core cpi | 23d | $17.48 | 1,215 |
| 673 | `CA0034` | POS - Instore and Online | `KXUKRETAIL` | UK retail sales MoM | retail sales | 23d | $17.48 | 1,215 |
| 674 | `CA0029` | POS - Convenience Stores | `KXACPICORE` | Annual core inflation | core cpi | 23d | $26.04 | 1,216 |
| 675 | `CA0031` | Credit Card - US and CAN General | `KXACPICORE-` | US annual core inflation | core cpi | 23d | — | — |
| 676 | `CA0029` | POS - Convenience Stores | `KXCPIFOOD` | CPI on food | cpi | 23d | $26.04 | 1,216 |
| 677 | `CA0034` | POS - Instore and Online | `PCECORE` | US Core PCE inflation | core pce,pce | 23d | $17.48 | 1,215 |
| 678 | `CA0034` | POS - Instore and Online | `KXUSPSPEND` | United States Personal Spending MoM | personal spending | 23d | $17.48 | 1,215 |
| 679 | `CA0034` | POS - Instore and Online | `CPI` | CPI | cpi | 23d | $17.48 | 1,215 |
| 680 | `CA0029` | POS - Convenience Stores | `KXTOBACCPI` | Tobacco CPI higher in [month]? | cpi | 23d | $26.04 | 1,216 |
| 681 | `CA0029` | POS - Convenience Stores | `KXUSRETAIL` | US retail sales MoM | retail sales | 23d | $26.04 | 1,216 |
| 682 | `CA0034` | POS - Instore and Online | `KXUSMICHCSP` | United States Michigan Consumer Sentiment Prel  | consumer sentiment,michigan cons | 23d | $17.48 | 1,215 |
| 683 | `CA0029` | POS - Convenience Stores | `KXCACPIYOY` | Canada Inflation Rate YoY | cpi | 23d | $26.04 | 1,216 |
| 684 | `CA0029` | POS - Convenience Stores | `CPIDELAY` | CPI data released | cpi | 23d | $26.04 | 1,216 |
| 685 | `CA0034` | POS - Instore and Online | `KXECONSTATCPICORE` | month over month core inflation | core cpi | 23d | $17.48 | 1,215 |
| 686 | `CA0034` | POS - Instore and Online | `KXCPICOREA` | Core CPI annually | core cpi,cpi | 23d | $17.48 | 1,215 |
| 687 | `CA0034` | POS - Instore and Online | `CPICORE` | CPI core | cpi | 23d | $17.48 | 1,215 |
| 688 | `CA0034` | POS - Instore and Online | `KXCOREUND` | Will Core CPI fall below x.x% in 2026? | core cpi,cpi | 23d | $17.48 | 1,215 |
| 689 | `CA0034` | POS - Instore and Online | `KXRETAIL` | Retail sales growth | retail sales | 23d | $17.48 | 1,215 |
| 690 | `CA0034` | POS - Instore and Online | `KXUSEDCARCPI` | US used cars and trucks CPI in [month] | cpi | 23d | $17.48 | 1,215 |
| 691 | `CA0034` | POS - Instore and Online | `KXUSPPIYOY` | US PPI YoY in [month] | ppi | 23d | $17.48 | 1,215 |
| 692 | `CA0034` | POS - Instore and Online | `KXUKCPIYOY` | United Kingdom Inflation Rate YoY | cpi | 23d | $17.48 | 1,215 |
| 693 | `CA0034` | POS - Instore and Online | `ACPICORE` | Annual core inflation | core cpi | 23d | $17.48 | 1,215 |
| 694 | `CA0034` | POS - Instore and Online | `ACPICORE-` | US annual core inflation | core cpi | 23d | $17.48 | 1,215 |
| 695 | `CA0034` | POS - Instore and Online | `KXTRUFCPI` | Truflation US CPI Inflation Index | cpi | 23d | $17.48 | 1,215 |
| 696 | `CA0034` | POS - Instore and Online | `KXTRUFEGGS` | Truflation US CPI Eggs Index | cpi | 23d | $17.48 | 1,215 |
| 697 | `CA0034` | POS - Instore and Online | `CPIFOOD` | CPI on food | cpi | 23d | $17.48 | 1,215 |
| 698 | `CA0029` | POS - Convenience Stores | `KXECONSTATCORECPIYOY` | year over year core inflation | core cpi | 23d | $26.04 | 1,216 |
| 699 | `CA0034` | POS - Instore and Online | `KXECONSTATCORECPIYOY` | year over year core inflation | core cpi | 23d | $17.48 | 1,215 |
| 700 | `CA0034` | POS - Instore and Online | `CPIAPPAREL` | CPI on apparel | cpi | 23d | $17.48 | 1,215 |
| 701 | `CA0034` | POS - Instore and Online | `USEDCAR` | US CPI print on used cars | cpi | 23d | $17.48 | 1,215 |
| 702 | `CA0034` | POS - Instore and Online | `KXCPICOMBO` | CPI Combo | cpi | 23d | $17.48 | 1,215 |
| 703 | `CA0025` | Freight Volume - North America | `KXUSDURABLE` | United States Durable Goods Orders MoM | durable goods | 23d | — | — |
| 704 | `CA0034` | POS - Instore and Online | `CPICOREYOY` | Core inflation | core cpi | 23d | $17.48 | 1,215 |
| 705 | `CA0034` | POS - Instore and Online | `RETAIL` | Retail sales growth | retail sales | 23d | $17.48 | 1,215 |
| 706 | `CA0034` | POS - Instore and Online | `KXCPIAPPAREL` | CPI on apparel | cpi | 23d | $17.48 | 1,215 |
| 707 | `CA0034` | POS - Instore and Online | `KXACPICORE-` | US annual core inflation | core cpi | 23d | $17.48 | 1,215 |
| 708 | `CA0034` | POS - Instore and Online | `KXISMSERVICES` | ISM Services PMI | ism services,services pmi | 23d | $17.48 | 1,215 |
| 709 | `CA0029` | POS - Convenience Stores | `KXUSPPI` | United States PPI MoM | ppi | 23d | $26.04 | 1,216 |
| 710 | `CA0034` | POS - Instore and Online | `KXJOBSRELEASE` | When will the BLS release a jobs report? | nonfarm payrolls | 23d | $17.48 | 1,215 |
| 711 | `CA0042` | Credit Card – EU Detailed Panel | `KXECONSTATCORECPIYOY` | year over year core inflation | core cpi | 23d | — | — |
| 712 | `CA0031` | Credit Card - US and CAN General | `KXCPIAPPAREL` | CPI on apparel | cpi | 23d | — | — |
| 713 | `CA0025` | Freight Volume - North America | `KXUSPPIYOY` | US PPI YoY in [month] | ppi | 23d | — | — |
| 714 | `CA0031` | Credit Card - US and CAN General | `RETAIL` | Retail sales growth | retail sales | 23d | — | — |
| 715 | `CA0031` | Credit Card - US and CAN General | `KXEHSHARE` | Existing home sales in time period | existing home sales | 23d | — | — |
| 716 | `CA0025` | Freight Volume - North America | `KXUSIPMOM` | US industrial production MoM | industrial production | 23d | — | — |
| 717 | `CA0031` | Credit Card - US and CAN General | `KXUMICHOVR` | Michigan consumer sentiment above X in [year]? | consumer sentiment,michigan cons | 23d | — | — |
| 718 | `CA0031` | Credit Card - US and CAN General | `CPIAPPAREL` | CPI on apparel | cpi | 23d | — | — |
| 719 | `CA0031` | Credit Card - US and CAN General | `KXECONSTATCORECPIYOY` | year over year core inflation | core cpi | 23d | — | — |
| 720 | `CA0029` | POS - Convenience Stores | `KXCPICOMBO` | CPI Combo | cpi | 23d | $26.04 | 1,216 |
| 721 | `CA0025` | Freight Volume - North America | `KXCACPIYOY` | Canada Inflation Rate YoY | cpi | 23d | — | — |
| 722 | `CA0031` | Credit Card - US and CAN General | `PCECORE` | US Core PCE inflation | core pce,pce | 23d | — | — |
| 723 | `CA0031` | Credit Card - US and CAN General | `KXISMSERVICES` | ISM Services PMI | ism services,services pmi | 23d | — | — |
| 724 | `CA0025` | Freight Volume - North America | `KXCPICOMBO` | CPI Combo | cpi | 23d | — | — |
| 725 | `CA0025` | Freight Volume - North America | `KXUSPPI` | United States PPI MoM | ppi | 23d | — | — |
| 726 | `CA0031` | Credit Card - US and CAN General | `KXRETAIL` | Retail sales growth | retail sales | 23d | — | — |
| 727 | `CA0031` | Credit Card - US and CAN General | `KXUSPPIYOY` | US PPI YoY in [month] | ppi | 23d | — | — |
| 728 | `CA0031` | Credit Card - US and CAN General | `ACPICORE` | Annual core inflation | core cpi | 23d | — | — |
| 729 | `CA0031` | Credit Card - US and CAN General | `KXTRUFCPI` | Truflation US CPI Inflation Index | cpi | 23d | — | — |
| 730 | `CA0031` | Credit Card - US and CAN General | `KXUSPSPEND` | United States Personal Spending MoM | personal spending | 23d | — | — |
| 731 | `CA0031` | Credit Card - US and CAN General | `KXCOREUND` | Will Core CPI fall below x.x% in 2026? | core cpi,cpi | 23d | — | — |
| 732 | `CA0031` | Credit Card - US and CAN General | `CPICOREYOY` | Core inflation | core cpi | 23d | — | — |
| 733 | `CA0031` | Credit Card - US and CAN General | `CPICORE` | CPI core | cpi | 23d | — | — |
| 734 | `CA0031` | Credit Card - US and CAN General | `KXECONSTATCPICORE` | month over month core inflation | core cpi | 23d | — | — |
| 735 | `CA0031` | Credit Card - US and CAN General | `KXCPI` | CPI | cpi | 23d | — | — |
| 736 | `CA0025` | Freight Volume - North America | `KXUSNFP` | US nonfarm payrolls in [month] | nonfarm payrolls | 23d | — | — |
| 737 | `CA0031` | Credit Card - US and CAN General | `KXCPICORE` | CPI core | cpi | 23d | — | — |
| 738 | `CA0031` | Credit Card - US and CAN General | `KXACPICORE` | Annual core inflation | core cpi | 23d | — | — |
| 739 | `CA0031` | Credit Card - US and CAN General | `ACPICORE-` | US annual core inflation | core cpi | 23d | — | — |
| 740 | `CA0034` | POS - Instore and Online | `KXCACPIYOY` | Canada Inflation Rate YoY | cpi | 23d | $17.48 | 1,215 |
| 741 | `CA0031` | Credit Card - US and CAN General | `KXCPICOREA` | Core CPI annually | core cpi,cpi | 23d | — | — |
| 742 | `CA0059` | Extreme Weather Data | `KXTRUFEGGS` | Truflation US CPI Eggs Index | cpi | 16d | — | — |
| 743 | `CA0059` | Extreme Weather Data | `KXUSMICHCSP` | United States Michigan Consumer Sentiment Prel  | consumer sentiment,michigan cons | 16d | — | — |
| 744 | `CA0059` | Extreme Weather Data | `KXUSGASCPI` | US gasoline CPI in [month] | cpi | 16d | — | — |
| 745 | `CA0059` | Extreme Weather Data | `KXTRUFHOUCPI` | Truflation US CPI Housing Inflation Index | cpi | 16d | — | — |
| 746 | `CA0059` | Extreme Weather Data | `KXAIRFARECPI` | US airline fares CPI in [month] | cpi | 16d | — | — |
| 747 | `CA0059` | Extreme Weather Data | `KXEHSHARE` | Existing home sales in time period | existing home sales | 16d | — | — |
| 748 | `CA0059` | Extreme Weather Data | `KXEHSALES` | Existing home sales in time period | existing home sales | 16d | — | — |
| 749 | `CA0059` | Extreme Weather Data | `KXUSEDCARCPI` | US used cars and trucks CPI in [month] | cpi | 16d | — | — |
| 750 | `CA0055` | SMB Workforce | `KXJOBLESSCLAIMS` | Weekly initial jobless claims | initial jobless | 5d | $231.44 | 9,656 |
| 751 | `CA0055` | SMB Workforce | `JOBLESS` | Initial jobless claims | initial jobless | 5d | $231.44 | 9,656 |
| 752 | `CA0013` | Mobile App | `KXJOBLESSCLAIMS` | Weekly initial jobless claims | initial jobless | 5d | — | — |
| 753 | `CA0055` | SMB Workforce | `KXJOBLESS` | Initial jobless claims | initial jobless | 5d | $231.44 | 9,656 |
| 754 | `CA0040` | Trade Claims | `KXJOBLESSCLAIMS` | Weekly initial jobless claims | initial jobless | 4d | — | — |