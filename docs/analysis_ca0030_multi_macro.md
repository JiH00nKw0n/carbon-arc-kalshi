# CA0030 × Multi-Macro 검증 — UMich 결과 일관성 점검

> 2026-05-15. `docs/analysis_ca0030_umich.md` 의 후속.
> 동일 CA0030 5y 데이터 (`outputs/auto/ca0030_clickstream_us_monthly_5y.csv`) 를 사용.
> 추가 비용 없음.

**한 줄 결론**: 첫 분석에서 본 "CA0030 leads UMich at lag +1, negative" 가 *방향 일관 신호* 가 **아니다**. Retail Sales 와 NFP 에선 정반대로 **매크로가 CA0030 을 leads (lag −1, positive)**. UMich 한 페어만의 우연이거나 sentiment-specific 패턴.

## 1. 매트릭스 — CA0030 (3 aggregation) × 3 매크로

### YoY % change (가장 robust 변환)

| CA agg | UMich | Retail Sales | NFP |
|---|---|---|---|
| SUM | r=**−0.50** at lag +1 (CA leads, negative) | r=**+0.75** at lag −1 (**macro leads CA**, positive) | r=**+0.68** at lag −1 (**macro leads CA**, positive) |
| Desktop only | r=−0.48 at lag 0 (contemporaneous) | r=+0.72 at lag −1 (**macro leads CA**) | r=+0.70 at lag −1 (**macro leads CA**) |
| Mobile only | r=−0.30 at lag +1 (weak CA leads) | r=+0.64 at lag −2 (**macro leads CA**) | r=+0.60 at lag +2 (CA leads, weak) |

### Linear-detrended levels (대안 변환)

| CA agg | UMich | Retail Sales | NFP |
|---|---|---|---|
| SUM | r=−0.45 at lag +1 (CA leads, negative) | r=+0.34 at lag −1 (macro leads CA, weak) | r=+0.26 at lag 0 (contemporaneous, weak) |
| Desktop | r=−0.41 at lag +1 (CA leads, negative) | r=+0.32 at lag +2 (mixed) | r=+0.21 at lag −2 (weak) |
| Mobile | r=−0.39 at lag +2 (CA leads, weak) | r=+0.43 at lag −2 (macro leads CA) | r=+0.48 at lag +1 (**CA leads**, positive) |

(n=63-64 for detrended, n=51-52 for YoY)

## 2. 결정적 관찰

### (1) UMich 만 lag +1 negative

CA0030 SUM × UMich YoY → r=−0.50 at lag +1 (CA leads). 첫 분석에서 본 핵심 결과.

### (2) Retail Sales 와 NFP 는 반대 방향

CA0030 SUM × Retail Sales YoY → **r=+0.75 at lag −1** — Retail Sales 가 CA0030 을 1개월 leads. \|r\| 가 UMich (0.50) 보다 더 큼.  
CA0030 SUM × NFP YoY → **r=+0.68 at lag −1** — NFP 가 CA0030 을 1개월 leads.

이건 lead-lag 가설의 **정반대**. "alt data 가 macro 를 leads" 가 아니라 "macro 가 alt data 를 leads".

### (3) Aggregation 별 일관성 약함

UMich 의 경우:
- SUM: lag +1
- Desktop: lag 0
- Mobile: lag +1 (weak) 또는 +2

진정한 lead 가 있다면 aggregation 바꿔도 같은 lag 에서 나와야 함. 흔들리는 것 = robust 아님.

### (4) Panel-growth confound 가 진짜로 작동

CA0030 의 panel 사용자 수는 2021-01 의 166K → 2026-04 의 860K (5.17x).

- 동시기에 미국 NFP: 142M → 159M (+12%)
- Retail Sales: $559B → $750B (+34%, nominal)

CA0030 의 5x 성장 중 대부분은 panel onboarding (CA 가 사용자 모으는 속도) 인데, 그 onboarding 자체가 **경기 좋을 때 가속**되는 듯:
- 경기 좋음 → 사람들이 인터넷 사용↑ → panel 가입↑ → CA 측정치↑
- = macro lead CA, 즉 **CA 의 변동은 경제의 *결과*, 원인이 아님**

이건 우리가 분석 시작 때 우려했던 panel-growth confound 의 직접 증거.

## 3. UMich 만 다른 부호인 이유 추정

UMich Sentiment 도 같은 기간 79 → 53 으로 **하락**. 즉:
- NFP, Retail Sales: 상승 추세
- UMich: 하락 추세
- CA0030 panel: 상승 추세

→ "CA0030 ↑ ↔ UMich ↓" 의 negative 상관은 단순히 **반대 방향 trend** 의 산물. detrending 후에도 잔존하는 부분이 있지만 (r=−0.45), 그것조차 *trend 노이즈 잔여* 일 가능성.

→ UMich 결과는 spurious. 다른 sentiment-related 매크로 (Conference Board Consumer Confidence, Michigan Inflation Expectations) 로 cross-check 필요.

## 4. Lead-lag 가설에 대한 함의

이 repo 의 핵심 가설 "alt data leads macro release":
- **CA0030 (Clickstream) 에는 적용 안 됨** — 오히려 reverse direction 이 더 강함
- 754 페어 전체에 적용 *안 될 수도 있음* — Phase 0b 가 "lead window > 3d" 를 *publication timing* 으로 평가했지, *데이터 lead* 로 평가한 게 아님
- Publication timing (= CA 가 매크로 전에 publish) 와 데이터 lead (= CA 변동이 매크로 변동 전에 일어남) 는 **다른 개념**

즉 **검증쌍 754개의 "lead_window_days" 는 거래일 단위 publish 순서이지, alpha 의 lead 여부가 아님**. 후자는 페어별 실증 데이터로만 확인 가능.

## 5. 무엇을 더 해야 하나

### (a) Direction-aware 재분류
754 페어 중 "데이터 lead 방향이 alt → macro" 인 것 vs "macro → alt" 인 것을 사후적으로 구분. Direction granger-causality test 가 더 적합.

### (b) UMich 패턴 confirm 시도
- Mobile aggregation 만으로 (lag +1 r=−0.30) → 약하지만 살아남음 → desktop 의 panel growth confound 제거 후 mobile 만으로 재분석
- 다른 sentiment 시리즈와 cross-check (Conference Board, UMich inflation expectations sub-index)

### (c) 다른 CA 데이터셋 검증
- CA0056 (Card Spend) × Retail Sales — Phase 0 의 다른 anchor 페어. **카드 거래는 panel-growth 영향 적을 듯** (사용자 수가 아니라 거래 금액). 진짜 lead 가 있다면 여기서 보여야 함
- $19.30 (7y) 또는 $4.99 (1y) 로 구매 가능. **CA0030 결과가 panel-growth confound 의 증거인 이상, panel-growth 가 적은 카드 transaction 패널이 lead-lag 가설의 더 깨끗한 테스트**

### (d) 754 페어의 lead 정의 명확화
`s_b_timing.py` 의 `lead_window_days` 가 **publication 시간 lead** 임을 README 와 verification_pairs_macro.md 에 명시. 실제 *데이터* lead 는 페어별 실증 필요.

## 6. 결론 (정직하게)

- **첫 분석 (`docs/analysis_ca0030_umich.md`) 의 "CA leads UMich" 결과는 trend artifact 가능성 큼**. 같은 데이터로 Retail Sales / NFP 보면 정반대 방향이 더 강함.
- 754 페어의 "lead_window_days" 는 publication timing — alpha 의 데이터 lead 가 아님. 둘 구분 명시 필요.
- 다음 검증은 **CA0056 Card Spend 같은 panel-growth 가 적은 데이터셋** 에서 해야 의미 있음.
- 진정한 lead-lag 입증은 멀리 있음. 이 repo 의 754 검증쌍은 *후보 list* 일 뿐.
