# Per-Dataset Analysis — CA0030 / CA0056 / CA0034 × 13 Macros

> 2026-05-18. Phase 5 후속 — 두 framework 추가 구매 후 데이터셋별 lead-lag 패턴 비교.  
> 데이터: 모두 monthly US, 2021-01 ~ 2026-04 (CA0034 만 2021-07 시작).  
> CSVs: `outputs/auto/ca{0030,0056,0034}_multi_macro_corr.csv`.

**한 줄 결론**: **데이터셋 종류에 따라 결과가 완전히 다름**. User-count panel (CA0030) 은 가설 미지지 (panel-growth confound). **Transaction-based panels (CA0056 Card $, CA0034 POS volume) 은 가설 지지** — 13 macros 중 10/13 (CA0034), 6/13 (CA0056 SUM), 10/13 (CA0056 Online) 에서 CA 가 매크로를 leads. 단, 모든 시리즈가 nominal $ 로 상승 추세인 2021-2026 윈도우의 common-trend 가 \|r\| 를 부풀리고 있을 가능성 — methodological caveats §5 참조.

---

## 1. 구매한 3 framework 비교

| Framework | Insight | 측정 단위 | 가격 | 데이터 shape | Panel size 의존? |
|---|---|---|---:|---|---|
| **CA0030** Clickstream | Website Users | 사용자 수 | $4.99 | 64 mo × Desktop/Mobile | **Yes (직접적)** |
| **CA0056** Credit Card Spend US | Card Spend (sum) | $ 거래 금액 | $14.03 | 64 mo × Online/Physical | 약함 (금액 기반) |
| **CA0034** POS Instore | POS Volume (sum) | 거래 건수 | $25.39 | 58 mo, single series | 약함 (건수 기반) |

총 사용: $44.41 / $50 promo (잔액 $5.59).

## 2. Direction summary — 13 macros, YoY % change, lag ∈ [−2, +2]

| Dataset | Aggregation | n macros | CA leads (lag>0) | Contemp (lag=0) | Macro leads (lag<0) | avg \|r\| CA leads | avg \|r\| Macro leads |
|---|---|---:|---:|---:|---:|---:|---:|
| **CA0030** Clickstream | SUM | 13 | 5 | 1 | 7 | 0.48 | **0.64** |
| | Desktop | 13 | 3 | 1 | 9 | 0.46 | **0.61** |
| | Mobile | 13 | 9 | 2 | 2 | 0.50 | 0.67 |
| **CA0056** Card Spend | SUM | 13 | **6** | 2 | 5 | **0.72** | 0.61 |
| | Online | 13 | **10** | 2 | 1 | 0.49 | 0.44 |
| | Physical | 13 | 5 | 2 | 6 | 0.62 | 0.64 |
| **CA0034** POS Instore | SUM | 13 | **10** | 0 | 3 | 0.49 | 0.45 |

**해석**:
- CA0030 user-count: Desktop 에서 Macro-leads 9/13 (강), SUM 7/13 (약). **Panel growth artifact 확인**
- CA0056 transaction $ (SUM, Online): **CA leads 우세**. \|r\| 도 큼
- CA0034 POS volume: **10/13 CA leads** — 가장 강한 패턴

## 3. CA0034 Instore POS Volume — Top 5 (n=46 YoY obs)

| Macro | best_lag | best_r | 방향 |
|---|---:|---:|---|
| **NFP** | **+1** | **+0.810** | CA leads (1mo) |
| **Personal Income** | **+2** | **+0.778** | CA leads (2mo) |
| **Core CPI** | **+1** | **+0.776** | CA leads (1mo) |
| UMich Sentiment | +2 | +0.612 | CA leads (2mo) |
| PCE Price | −2 | +0.591 | Macro leads (2mo) |

NFP / Personal Income / Core CPI 에서 **\|r\| ≈ 0.8** 의 강한 CA-leads 패턴. 통계적으로 의미 있어 보임. **단 n=46 (YoY 적용 후)** 으로 작아서 효과 크기 신뢰구간 넓다.

## 4. CA0056 Online Card Spend — Top 5 (n=51 YoY obs)

| Macro | best_lag | best_r | 방향 |
|---|---:|---:|---|
| Personal Income | +2 | **−0.660** | CA leads (negative) |
| Industrial Production | +1 | **+0.637** | CA leads |
| JOLTS Quits | +1 | **+0.620** | CA leads |
| Retail Sales | +1 | **+0.592** | CA leads |
| PPI | +2 | **+0.560** | CA leads |

13 macros 중 **10개가 lag +1 또는 +2 에서 best**. 가장 깨끗한 CA-leads 패턴. Personal Income 만 negative (이게 잠재적 spurious).

## 5. Methodological caveats — \|r\| 를 액면 그대로 믿지 말 것

### 5.1 Common-trend 의 의심
- 2021-2026 윈도우는 *모든 시리즈가 nominal $ 로 강한 상승 추세*:
  - Card Spend (CA0056): +50%+ nominal growth
  - POS Volume (CA0034): 상승 추세
  - CPI / PCE: +20-25% (인플레이션)
  - NFP: +12% (고용 회복)
  - Personal Income: +35%
- YoY % change 가 trend 를 제거한다고 가정했지만, **YoY 자체가 cyclical** — 2022 인플레이션 충격기에 모든 시리즈 YoY 가 동시에 spike → 우연히 lag +1, +2 에 큰 \|r\| 만들 수 있음
- 진짜 lead-lag 라면 detrended residual 에서도 \|r\| 가 살아남아야 함 — *아직 검증 안 함*

### 5.2 Multiple testing
- 3 dataset × 평균 2.7 aggregation × 13 macros × 5 lag = **520+ comparisons**
- Bonferroni 보정 시 α=0.05/520 → 매우 엄격한 \|r\| 기준 필요
- 현재 발표한 \|r\|=0.7-0.8 은 raw correlation. p-value, permutation test 안 함

### 5.3 작은 sample
- CA0034: 46 YoY 가능 obs
- CA0030, CA0056: 51 YoY obs
- n=51 의 Pearson r=0.6 의 95% CI 는 [0.40, 0.75]. r=0.8 의 95% CI 는 [0.67, 0.88]
- 즉 효과 크기는 의미 있지만 정밀도는 모자람

### 5.4 lag +2 의 의심
- CA0034 의 Personal Income / UMich, CA0056 Online 의 PCE / PPI / CPI 등 다수가 lag +2 best
- ±2 윈도우 끝점에 몰리면 진짜 lead 가 아니라 wider 효과의 단편일 가능성. lag +3 / +4 도 봐야 lag +2 가 진짜 peak 인지 확인 가능
- 본 분석은 ±2 만 봄

### 5.5 Direction 자체의 의미
- "CA leads at lag +k" = CA 의 YoY 변동이 매크로 YoY 변동을 k개월 앞섬
- 하지만 이게 *forecast value* 인지 *contemporaneous proxy* 인지 구분 필요
- Granger-causality test, OOS forecast 정확도 측정이 진짜 lead 검증

### 5.6 한 데이터셋 = n=1
- CA0030 / 0056 / 0034 셋이지만 셋 다 같은 미국 거시환경 (2021-2026 single business cycle window). 다른 시기/국가에서 같은 패턴 보이는지 미확인

## 6. 잠정 결론

| 가설 | 데이터셋별 평가 |
|---|---|
| **"Alt data leads macro release"** | |
| → CA0030 (user-count clickstream) | **미지지** — panel-growth confound 가 dominant |
| → CA0056 (card transaction $) | **약하게 지지** — SUM 6/13, Online 10/13 CA leads. 단 단순 \|r\| 비교는 common-trend 영향 |
| → CA0034 (POS transaction volume) | **잠정 지지** — 10/13 CA leads. Top 3 (NFP, Personal Income, Core CPI) 가 \|r\| ≈ 0.8 |

**중요**: CA0034 와 CA0056 의 강한 CA-leads 결과는 *encouraging* 하지만, 위 caveats (특히 common-trend / multiple testing) 가 미해결이라 **확정 시그널은 아님**. 다음에 할 일:

1. Detrended residual 에서도 lag +1, +2 패턴 살아남는지 확인
2. Out-of-sample forecast — 2021-2024 fit → 2025+ predict, baseline AR 대비 incremental 정확도 측정
3. Granger-causality test (statsmodels) — F-stat 으로 lead 통계 검증
4. ±4 또는 ±6 까지 lag 확장 — lag +2 가 진짜 peak 인지

이 후속 작업들은 *추가 비용 0*. 현재 데이터로 가능.

## 7. 데이터셋별 매크로 페어 (754 검증쌍 중)

### CA0030 (42 페어, 19 unique macros)
이미 검증된 13 macros 외 미검증: ADP Employment, Consumer Confidence, ISM Services, Services PMI, Existing Home Sales, Michigan Consumer (≈UMich 중복).

→ FRED 에 미존재 매크로 (ISM, ADP, etc.) 가 핵심 누락. 754 페어 중 *모든* 페어 검증은 추가 데이터 fetch 필요.

### CA0056 (45 페어, 13 unique macros)
754 페어의 CA0056 매크로: consumer sentiment, core cpi, core pce, cpi, existing home sales, gdp, ism services, michigan consumer, pce, personal spending, ppi, retail sales (+1 더).

→ Existing Home Sales / ISM Services 외 모두 검증. GDP 는 분기 데이터라 monthly 와 다름.

### CA0034 (55 페어, 15 unique macros)
754 페어의 CA0034 매크로: consumer confidence, consumer sentiment, core cpi, core pce, cpi, durable goods, gdp, ism services, michigan consumer, nonfarm payrolls, pce, ppi, retail sales, services pmi 등.

→ 다양한 카테고리 (sentiment / inflation / employment / GDP). FRED 캐시 13 macros 로 14/15 cover.
