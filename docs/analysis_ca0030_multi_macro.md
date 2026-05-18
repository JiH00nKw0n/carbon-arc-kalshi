# CA0030 × Multi-Macro 검증 — 13 macros (전체 분석)

> 2026-05-18 갱신. `docs/analysis_ca0030_umich.md` (1차, UMich only) 및 이전 multi-macro 분석 (3 macros) 의 *제대로 된* 후속.  
> 이전 3-macro 분석은 outputs/fred 캐시에 3개 (UMich/RSAFS/PAYEMS) 만 있어서 도달한 한계였음. 본 분석에서 13 macros 까지 확장.  
> 데이터: `outputs/auto/ca0030_clickstream_us_monthly_5y.csv` ($4.99 구매), 매크로는 FRED MCP 캐시. CSV: `outputs/auto/ca0030_multi_macro_corr.csv`.

**한 줄 결론**: CA0030 의 13 macros 전체 검증 결과 — **SUM/Desktop aggregation 에서는 가설 미지지** (다수 macro 가 CA 를 leads), **Mobile 에서는 표면적으로 CA-leads 패턴이 더 많지만 그게 진짜 시그널인지 noise 인지 구분 불가**. 한 마디로 *CA0030 한 데이터셋으로는 lead-lag 가설 입증도 반증도 명료하지 않다* — 단, 가설을 *지지하지는 않는다*.

---

## 1. 분석 범위

| | |
|---|---|
| CA 데이터 | CA0030 Clickstream US monthly, 2021-01 ~ 2026-04 (64 months) |
| Aggregations 시도 | SUM (Desktop + Mobile), Desktop only, Mobile only |
| Macros (FRED) | UMich, Retail Sales, NFP, Core CPI, PCE Price, CPI, INDPRO, Durable Goods, Housing Starts, New Home Sales, JOLTS Quits, PPI, Personal Income |
| 변환 | YoY % change (가장 robust) |
| Lag 범위 | −2 ~ +2 months |

Macros 13개는 754 검증쌍에서 CA0030 이 매칭된 19 unique macro events 중 FRED 에서 fetch 가능한 부분집합. 못 fetch 한 것들: ADP Employment, ISM Services, Services PMI, Existing Home Sales, Consumer Confidence (UMich 대체 가능), Michigan Consumer (UMich 대체), PCE 와 Personal Spending (PCE Price + Personal Income 으로 대체).

## 2. 전체 결과 — SUM aggregation

13 macros, YoY %, sorted by \|best_r\|:

| Macro | best lag | best r | 방향 |
|---|---:|---:|---|
| Retail Sales | −1 | +0.748 | **Macro leads CA** |
| NFP | −1 | +0.682 | **Macro leads CA** |
| PCE Price | +2 | +0.682 | CA leads (positive) |
| PPI | −1 | +0.677 | **Macro leads CA** |
| CPI | −1 | +0.669 | **Macro leads CA** |
| JOLTS Quits | −1 | +0.645 | **Macro leads CA** |
| Core CPI | −1 | +0.614 | **Macro leads CA** |
| New Home Sales | +1 | −0.610 | CA leads (negative) |
| UMich Sentiment | +1 | −0.504 | CA leads (negative) |
| Industrial Production | 0 | +0.455 | Contemporaneous |
| Durable Goods | +2 | +0.440 | CA leads (positive, weak) |
| Personal Income | −1 | −0.422 | Macro leads CA (negative) |
| Housing Starts | +2 | −0.146 | weak |

**Direction 집계 (SUM)**:
- CA leads (lag > 0): 5 macros (PCE Price, New Home Sales, UMich, Durable Goods, Housing Starts)
- Contemporaneous (lag 0): 1 (INDPRO)
- Macro leads CA (lag < 0): 7 macros (Retail Sales, NFP, PPI, CPI, JOLTS, Core CPI, Personal Income)

→ **7 vs 5 로 Macro-leads-CA 가 더 많고**, \|r\| 도 평균적으로 더 큼 (0.6-0.75 범위 vs 0.4-0.6).

## 3. Aggregation 별 비교

| Aggregation | CA leads | Contemp | Macro leads | 우세 방향 |
|---|---:|---:|---:|---|
| **SUM** | 5 | 1 | 7 | Macro leads (살짝) |
| **Desktop** | 3 | 1 | 9 | **Macro leads (압도)** |
| **Mobile** | 9 | 2 | 2 | CA leads |

**Desktop 은 macro 가 CA 를 leads 하는 방향이 압도적** (9/13). 패널 크기 (153K → 722K, 4.7x 성장) 가 경제와 함께 가속되는 onboarding artifact 의 직접 증거.

**Mobile 은 CA 가 leads 하는 방향이 더 많음** (9/13) — 그런데 best_lag 분포가 +1 / +2 에 흩어져 있어서 진짜 시그널인지, 작은 패널 (12K → 62K, 4.9x 성장) 의 noise 가 ±2 윈도우 내 임의 lag 에 부딪힌 건지 구분 불가.

## 4. 정직한 해석

### (a) 가설 미지지 (또는 weak supported at best)

총 13 macros 중 SUM 기준 **7/13 (54%)** 가 *반대 방향* (macro leads CA). 우연이라면 50% 일 텐데 살짝 더 많고, 그것도 \|r\| 가 더 큼.

만약 가설이 진짜라면: 대부분 macro 에서 CA leads 가 우세해야 하는데 **그 반대 패턴**.

### (b) Aggregation 의 결정적 영향

Desktop vs Mobile 의 정반대 방향 → CA0030 의 데이터 패널 구성이 신호의 *부호* 를 결정. 이건 깨끗한 lead-lag 시그널이 아니라 *데이터 구조 artifact* 의 신호.

만약 CA0030 가 진짜 leading 정보를 가졌다면, aggregation 에 따라 부호가 바뀌면 안 됨.

### (c) UMich 와 New Home Sales 만 일관되게 CA leads (negative)

3 aggregation 모두에서 UMich (r ≈ −0.4 ~ −0.5 at lag +1) 과 New Home Sales (r ≈ −0.4 ~ −0.7 at lag +1) 가 CA-leads, negative. 다른 macros 는 aggregation 따라 부호/방향 흔들림.

UMich + New Home Sales 의 negative 패턴이 진짜라면 가능한 해석: 두 시리즈 모두 2021-2026 기간 *하락 추세*. CA 의 panel 은 상승 → trend 부호 mismatch 가 negative corr 만들고 있을 가능성 큼. 즉 **진짜 lead 아닌 trend artifact**.

### (d) 1차 분석 (3 macros) 의 결론은 cherry-pick 결과였음

이전 `analysis_ca0030_umich.md` 의 "UMich 만 lag +1 negative" 결론은 단 3개 macro 만 본 결과였고, 13개로 확장하니 그 negative 패턴이 UMich + New Home Sales 만의 *trend mismatch* 일 가능성이 더 분명해짐. 나머지 11개 macros 는 다른 방향.

## 5. Methodological 한계 — 더 심각해짐

- **65 comparisons** (3 agg × 13 macro × 5 lag 중 best 선택) → multiple testing 보정 안 됨. 우연히 \|r\| ≥ 0.5 다수 나올 수 있음
- **n=51 (YoY)** ~ 51 monthly obs. 65 comparison 에 비해 작음
- **Pre-2021 데이터 없음** — 진짜 non-COVID/non-inflation 윈도우 비교 불가
- **CarbonArc panel composition 변화 정보 부재** — early adopter → 일반 대중 demographic 변화는 lag corr 로 못 잡음

## 6. 결론 (CA0030 만)

- **CA0030 데이터셋 한 건에서는 alt-data leads macro 가설이 지지 안 됨.** 13 macros 중 7개가 반대 방향
- Aggregation 따라 부호 뒤집힘 → 데이터 구조 artifact 가 진짜 lead 신호를 가림
- 이 결과는 lead-lag 가설 *전체* 의 부정이 아니라 *CA0030 클릭스트림 클래스의 alt-data (user-count 측정) 가 macro forecaster 로 부적합* 임을 시사

→ 후속으로 panel-growth confound 가 적은 transaction-based dataset (CA0056 Card $, CA0034 POS volume) 으로 가설을 재검증함. **CA0034 에서 10/13 CA leads + \|r\|≈0.8 강 시그널 나옴** (Verdict: 잠정 지지). 자세히는 `analysis_per_dataset.md`.
