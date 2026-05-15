# CA0030 Clickstream × UMich Sentiment — 첫 풀패널 분석

> ⚠️ **후속 multi-macro 검증에서 본 분석의 결론이 흔들림.** 같은 CA0030 데이터를 Retail Sales / NFP 와도 검증한 결과, 그쪽은 정반대 방향 (macro leads CA, lag −1, positive r=+0.7) 이 더 강함. UMich 만의 lag +1 negative 는 sentiment-specific 패턴이거나 단순 trend artifact 일 가능성. 자세히는 `docs/analysis_ca0030_multi_macro.md`.

> 2026-05-15 첫 framework 구매 ($4.99, CA0030 5y monthly US) 직후 anchor 페어 검증.
> 데이터: `outputs/auto/ca0030_clickstream_us_monthly_5y.csv` (gitignored).
> 구매 기록: `docs/purchase_log.md`.

**한 줄 결론**: 풀패널에서 CA leads UMich 의 negative 상관 패턴이 raw / MoM Δ / YoY / linear-detrended 4가지 방식 모두에서 lag +1 에 일관되게 나타남. **하지만 이 분석은 여러 methodological 빈틈을 갖고 있어서, 확정 시그널이 아니라 "framework 한 번 더 본 가치가 있다" 수준의 sanity 단서로 해석해야 함**. (그리고 multi-macro 후속 검증에서 그 단서마저도 약함이 드러남 — 위 ⚠️ 참조.)

---

## 1. 데이터

| | |
|---|---|
| Source | `client.explorer.buy_frameworks(fw)` order `3a1c7576-...` |
| Insight | 381 Website Users |
| Entity | United States (carc_id 96, country-rollup) |
| Window | 2021-01 ~ 2026-04 (64 months) |
| Resolution | monthly |
| Aggregate | mean (일별 user count 의 월평균) |
| Platforms | Desktop Site, Mobile Site (2개 row per month) |
| Raw shape | 128 rows × 5 cols |

FRED UMich Consumer Sentiment (`UMCSENT`, `outputs/fred/umich.json`) 와 month-start 단위로 align.

## 2. 했던 작업

```python
ca_total = ca.groupby('date')['website_users'].sum()  # Desktop + Mobile 합
joined = pd.concat([ca_total, umich], axis=1, join='inner').dropna()
# n=63 overlap months
for method in [raw, MoM Δ, YoY %, linear-detrended]:
    for lag in [-3..+3]:
        r = Pearson(ca.shift(lag), umich)
```

## 3. 결과 (있는 그대로)

| Method | n | lag −2 | lag −1 | lag 0 | **lag +1** | lag +2 |
|---|---:|---:|---:|---:|---:|---:|
| Raw levels | 63 | −0.480 | −0.521 | −0.575 | **−0.591** | −0.565 |
| MoM Δ | 62 | +0.164 | +0.126 | −0.112 | **−0.342** | +0.128 |
| YoY % | 51 | −0.376 | −0.432 | −0.478 | **−0.504** | −0.498 |
| Linear detrended | 63 | −0.159 | −0.241 | −0.354 | **−0.454** | −0.415 |

- 모든 방법에서 lag +1 (CA 가 UMich 를 1개월 leads) 이 가장 큰 \|r\|
- 부호 = **negative**: web users ↑ 다음 달 UMich ↓
- 2023+ 만 잘라도 (n=39) lag +1 r = −0.68 — "post-COVID 윈도우" 에서도 살아남음

## 4. **methodological 빈틈 — 이 결과를 그대로 믿으면 안 되는 이유**

### 4.1 Platform 합산은 의미가 깨졌을 가능성
Desktop + Mobile 의 `website_users` 를 sum 했음. 그런데 "Website Users" 는 *사용자 수* — Desktop 과 Mobile 을 둘 다 쓰는 사람은 중복 카운트됨. 올바른 처리는:
- 두 platform 별도로 분석 (Mobile 만, Desktop 만)
- 또는 max(Desktop, Mobile)
- 또는 CA API doc 에서 "Website Users" 의 정확한 정의 확인 후 aggregate 결정

지금 결과는 본질적으로 *유효 사용자 수 + 중복도* 의 혼합 측정.

### 4.2 Panel 자체가 5년간 5.17x 성장 → economic signal 이 아니라 onboarding artifact
- 2021-01: 166,588 users → 2026-04: 860,609
- 미국 인구는 같은 기간 ~330M 거의 정체. 즉 "사람들이 5배 더 인터넷 씀" 은 거짓
- **CA0030 가 panel 에 사용자를 5배 더 모았다 + demographic 구성이 변했다** 라고 봐야 자연스러움
- Linear detrending 으로 일부 제거되지만:
  - Panel composition 변화 (early-adopter → 일반 대중) 는 detrending 으로 못 잡음
  - YoY % change 도 panel 자체가 신규 demographic 으로 가지치기 했으면 의미 다름
- **즉 detrending 으로도 panel-construction artifact 와 진짜 economic signal 을 구분 못함**

### 4.3 Multiple testing
- 4 methods × 7 lags = 28 비교. 우연히 \|r\|≥0.4 나올 확률 무시 못함
- 나는 사후적으로 lag +1 만 골라 발표 — Bonferroni 또는 pre-registered hypothesis 가 옳음

### 4.4 "COVID 제외" 는 거짓말
- 2023-2026 도 COVID aftermath:
  - 인플레이션 surge → 금리 5-5.5% (40년 만의 최고)
  - 은행 위기 (SVB)
  - AI 붐 → tech web traffic 폭증 (clickstream 의 무관한 dominant trend)
- 진짜 non-COVID 매크로 환경은 *없음* (CA0030 history 가 2021-01 부터)
- "2023+ 컷" 은 다른 종류의 거시 충격 시기일 뿐

### 4.5 인과 vs 단순 상관
- 두 시리즈 모두 인플레이션 또는 Fed 정책에 끌려다닐 가능성
- CA0030 의 panel 성장이 inflation-driven (사람들이 가격 비교 더 검색) 이면 → UMich 와 negative corr 은 *공통 confounder* 결과
- Lead +1 의 의미는 inflation 충격이 web behavior 에 더 빨리, sentiment 에 느리게 반영된 거일 수도

### 4.6 "Anxious browsing 가설" 은 post-hoc storytelling
- 부호가 negative 로 나온 *후에* 내가 만든 설명
- 사전에 "CA 가 UMich 를 양의 부호로 lead 한다" 가설이 있었으면 negative 는 "가설 기각" 으로 해석돼야 함
- 지금은 *방향성 자유도* 가 있는 상태 — 어떤 부호든 후처리로 합리화 가능

### 4.7 Phase 1 EDA 와의 비교가 apples-to-oranges
- Phase 1 = CA0049 (Medline pharmacy claims, single brand) × UMich
- 이번 = CA0030 (clickstream panel) × UMich
- **다른 데이터셋, 다른 mechanism**. "Phase 1 시그널은 무너졌는데 이건 안 무너졌다" 라고 쓴 건 misleading — 둘은 독립 테스트, 강도 비교 불가
- 정확한 비교는 "CA0030 sample EDA r" vs "CA0030 full panel r" — sample 이 single-day 라 불가능했어서 비교 자체가 없음

### 4.8 aggregate=mean 의 의미 미확인
- CarbonArc API 의 monthly mean(daily users) 가 무엇을 측정하는지 doc 확인 안 함
- "월평균 일일 사용자" 인지, "월간 unique 사용자" 인지에 따라 시계열 해석 달라짐
- sum 으로 다시 받았으면 어떤 값일지 모름

## 5. 그래서 무엇이 살아남나

위 8개 결함을 다 고려해도 *완전히* 무의미한 결과는 아님. 살아남는 관찰:

1. **Lag +1 의 \|r\| 가 lag 0 보다 일관되게 큼** (4 method 중 3 method) — 우연이라면 50% 확률로 lag 0 > lag +1 이어야 함. 약하지만 lead 방향 증거
2. **부호가 4 method 모두 negative** — 단순 sample variance 만으론 우연 일치 가능, 하지만 일관성은 sanity check 통과
3. **Phase 1 sample (n=20) 의 r=−0.19 보다 풀패널 r=−0.45 가 정량적으로 더 큰 effect size** — 일관성 신호 (적어도 풀패널 시그널이 sample 보다 약하지는 않음)

## 6. 진짜 검증하려면 해야 할 것

### 6.1 Aggregation 재검토
- API doc 또는 metadata 에서 Website Users 의 정의 확인
- Desktop, Mobile, 합산, max 각각 분석 후 robust check
- 또는 다른 CA0030 insight 시도 (`page_views`, `sessions` 가 있는지 확인)

### 6.2 Panel growth normalize
- `website_users / total_panel_size` 로 normalize (만약 panel size meta 가 노출돼 있으면)
- 또는 CA0030 의 다른 demographic-stable subset 으로 검증

### 6.3 Pre-registered protocol
- 사전 가설: "lag k=1 에서 \|r\| ≥ 0.3 이면 confirm"
- Bonferroni 보정 후 p-value 계산
- Permutation test (시간 순서 random shuffle 후 r 분포)

### 6.4 Out-of-sample forecast
- 2021-2024 fit → 2025+ predict
- 단순 AR(1) baseline 대비 incremental 정보 측정
- 이게 진짜 "lead 시그널 alpha" 의 정의

### 6.5 추가 페어 검증
- CA0030 × Retail Sales (FRED RETAIL_SALES), Core PCE, NFP 등 42 페어 전체
- 만약 UMich 만 lead 하고 다른 매크로엔 안 한다면 → spurious
- 여러 매크로에 일관된 lead 패턴이 보이면 → real signal

## 7. 결론 (정직하게)

- 이 분석은 **"$4.99 짜리 framework 한 번 사봤더니 sample EDA 보다 약간 더 robust 한 패턴 보인다"** 정도
- "Lead-lag thesis 입증" 도 아니고, "alpha 시그널 발견" 도 아니고, "anxious browsing 메커니즘 확인" 도 아님
- 다음 단계: **(a) aggregation 재검토 (Desktop/Mobile 분리), (b) panel growth normalize 시도, (c) CA0030 의 다른 매크로 페어 (Retail Sales, PCE, NFP) 도 검증해서 lead 패턴이 sentiment 만의 우연인지 일관 신호인지 확인** — 그래야 framework 한 건 더 살 가치가 있는지 판단 가능

핵심: **이 결과 갖고 paper 쓰거나 trading 결정 내리면 안 됨**. 이건 검증쌍 도출 파이프라인이 *진짜 데이터로 동작은 하더라* 라는 확인일 뿐.
