# RESULTS — Y-switching across 3 Carbon Arc channels

실행: `ys_02_yswitch.py` · 데이터: 이미 구매한 CA framework 무료 재다운로드 + FactSet PIT(120티커).
검정 gate = 지훈 방식(clustered-bootstrap `p_boot`<0.05 AND shuffle-surrogate `p_surr`<0.05).
baseline 참조 = 지훈 factor3 카드 × surprise_early **r=+0.192**.

## 핵심 결과표 (X = x_yoy)

| 채널 | Y | r | p_surr | Spearman | hit | rank-IC | IC-IR | 판정 |
|------|---|-----|--------|----------|-----|---------|-------|------|
| **card** | rev_yoy | **+0.381** | 0.000 | +0.525 | 0.61 | +0.511 | **2.74** | ✅ |
| **card** | surprise_early | **+0.200** | 0.002 | +0.223 | 0.57 | +0.244 | 1.40 | ✅ |
| card | surprise_print | +0.197 | 0.002 | +0.215 | 0.56 | +0.242 | 1.32 | ✅ |
| **foot** | rev_yoy | **+0.387** | 0.000 | +0.408 | 0.70 | +0.410 | 1.19 | ✅ |
| foot | surprise_early | +0.014 | 0.805 | −0.028 | 0.56 | −0.100 | −0.36 | ❌ |
| foot | surprise_print | +0.006 | 0.918 | −0.039 | 0.55 | −0.114 | −0.41 | ❌ |
| click | rev_yoy | +0.058 | 0.192 | +0.146 | 0.61 | +0.364 | 2.81 | ❌* |
| **click** | surprise_early | **+0.121** | 0.001 | +0.197 | 0.60 | +0.233 | 1.25 | ✅ |
| click | surprise_print | +0.081 | 0.033 | +0.178 | 0.60 | +0.213 | 1.47 | ✅ |

\* click×rev_yoy는 pooled Pearson은 약하지만 **cross-sectional rank-IC는 +0.364 / IR 2.81**로 강함 — pooled와 IC가 갈리는 케이스(아래 해설).

## 시나리오별 해설 — 왜 이렇게 갈렸나

### 1. card (CA0056 카드결제) — 지훈 baseline 재현 + 강화 ✅
- **surprise_early r=+0.200** 은 지훈 baseline(+0.192)을 **독립 티커셋(66개, n=588)에서 재현**. 우연이 아님을 뒷받침.
- **rev_yoy r=+0.381 / IC-IR 2.74** — 카드결제 YoY가 매출 YoY를 강하게 추적(당연한 sanity지만 IC-IR가 매우 높음).
- within-company corr=+0.130 (>0) → "어느 기업인지"가 아니라 **"어느 분기인지"를 맞춤** = 진짜 시계열 신호.
- **결론: 카드는 매출·매출서프라이즈 둘 다 예측. 지훈 채널의 정본(canonical) 확인.**

### 2. foot (CA0060 풋트래픽) — 매출엔 붙고 surprise엔 안 붙음 ⚠️
- **rev_yoy r=+0.387 / hit 0.70** — 방문객 수 YoY는 매출 YoY를 잘 추적. **물량(traffic) 프록시로서 정상.**
- 그러나 **surprise_early r=+0.014 (p_surr=0.805) 완전 실패.** within-company corr=+0.019(≈0).
- **전달 메커니즘**: 풋트래픽은 "매출이 오를지"는 알지만 **애널리스트도 이미 아는 정보**라 컨센서스에 선반영됨 → surprise(컨센서스 초과분)엔 정보가 없음. 카드결제(객단가·믹스 포함 금액)와 달리 풋트래픽은 **수량만** 담아 서프라이즈를 못 만든다.
- **결론: 풋트래픽의 올바른 Y는 surprise가 아니라 rev_yoy(또는 SSS). Y-스위칭이 없었으면 "풋트래픽 실패"로 오판할 뻔한 대표 사례.** (지훈 factor1_traffic의 n=96 경계 결과와 정합 — n을 458로 늘려도 surprise엔 안 붙음이 확정됨.)

### 3. click (CA0030 웹트래픽) — surprise에 붙고, lag까지 살아있음 ✅
- **surprise_early r=+0.121 (p_surr=0.001), lag1 r=+0.152 (p_surr=0.015)** — 웹트래픽은 surprise를 예측하고 **직전분기 값도 선행**(카드는 lag 실패, 클릭은 lag PASS).
- within-company corr=+0.117 (>0) → 시계열 신호.
- **rev_yoy는 pooled r=+0.058로 약한데 rank-IC=+0.364/IR=2.81로 강함**: 이커머스 채널은 티커별 성장률 레벨차가 커서(RDDT 등 급성장) pooled Pearson은 아웃라이어에 눌리지만, **분기별 cross-sectional 순위로 보면 강한 신호**. → **여기서 rank-IC를 추가한 값어치가 드러남.** pooled만 봤으면 놓쳤을 신호.
- **결론: 웹트래픽의 최적 Y = surprise_early. 온라인 채널은 카드처럼 금액이 아닌 방문이지만, 이커머스는 "방문=구매의도"라 surprise에 정보가 남음(오프라인 풋트래픽과 대조).**

## 메트릭이 준 추가 통찰

- **rank-IC / IC-IR의 값어치**: click×rev_yoy처럼 **pooled r과 cross-sectional IC가 갈리는 케이스**를 잡아냄. 팩터 실전에선 IC-IR가 신호 안정성의 진짜 지표 — card(2.74)·click(2.81)이 특히 높다.
- **hit-rate**: foot×rev_yoy 0.70이 가장 높음. 방향 베팅 관점에선 풋트래픽→매출이 가장 신뢰.
- **Spearman**: 모든 PASS 케이스에서 Pearson과 부호 일치 → fat-tail 아티팩트 아님 확인.

## 한 줄 요약

| 채널 | 최적 Y | 왜 |
|------|--------|-----|
| **card** | surprise_early **와** rev_yoy | 금액 신호 → 매출·서프라이즈 둘 다 |
| **foot** | rev_yoy (SSS 권장) | 수량 신호 → 매출엔 붙으나 서프라이즈는 컨센서스 선반영 |
| **click** | surprise_early (lag 포함) | 방문=구매의도 → 서프라이즈에 정보 잔존, 선행성까지 |

**Y-스위칭의 결론적 교훈**: 단일 Y(surprise_early)만 봤다면 **풋트래픽을 "실패"로 버리고(실은 rev_yoy에 강함), 클릭의 rev_yoy 신호를 놓쳤을 것**(rank-IC로만 보임). 채널마다 붙는 Y가 다르다 — 알트데이터의 물리적 성격(금액 vs 수량 vs 의도)이 Y 선택을 결정.

## 다음

- **SSS(동일점포매출) Y 추가** — foot 채널의 진짜 최적 Y일 가능성(총매출은 신규출점 오염). FactSet/컨센서스 comps 필요.
- **CA0040 수입/수출** — 현재 stale(reinstate 필요). 확보 시 unit-volume Y(중량·선적수)로 물량 채널 추가.
- **결합 신호(Factor 3 방향)** — card+foot+click orthogonality 확인 후 앙상블.
