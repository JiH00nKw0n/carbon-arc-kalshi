# Factor 1 — 결과 (Web 트래픽 × 어닝콜 → 매출 서프라이즈)

> Factor 3의 패러다임(대체데이터 X × 어닝콜 Z → 매출 서프라이즈 Y)을 **X = 카드 → 웹 트래픽**으로
> 바꿔 재현. 단 종목을 **웹이 매출의 주채널인 회사**(이커머스·온라인 마켓플레이스)로 골랐다.
> 모든 수치는 재현 가능: `factor1/scripts/f1_0*.py`, 데이터·로그는 `factor1/data`·`factor1/outputs`(gitignored).

## 데이터

- **X (웹):** Carbon Arc CA0030 Clickstream, insight 381 "website users"(Desktop+Mobile **사이트**, 앱 제외),
  회사별 월간. 2026-06-27 구매(39개사 web-O, $78.52). 엔티티 오매칭 6개 제외 → **클린 33종목**.
- **Y (서프라이즈):** FactSet point-in-time 매출 컨센서스 기준 = (ACTUAL − CONS_EARLY)/CONS_EARLY.
  `FE_BASIC_ACT_QF` + `FE_BASIC_CONH_QF`(분기말+7d 스냅샷). 38 FSYM, 595 분기.
- **Z (텍스트):** 직전분기 어닝콜 전사. factor3 SQL(`stock_documents.file_key`, `fiscal_date IS NOT NULL`)로
  발견 → S3 다운로드. 30종목 × 112콜.
- **누설 통제:** LLM 평가표본 = report_date > 2025-12-01 (gpt-5.5 컷오프). 상관/인과는 전체 패널 사용(LLM 아님).

## 1. 대체데이터 자체가 매출과 유의미한가 (상관·인과 배터리)

`f1_02_corr_causation.py` · 패널 321 event · 33종목 · 2023Q4~2026Q1. 검정 게이트 = 회사-클러스터
부트스트랩(p_boot) **AND** shuffle-company surrogate(p_surr) 둘 다 <0.05.

| 검정 | r | n | p_boot | p_surr | 판정 |
|---|---|---|---|---|---|
| web_yoy → **매출 서프라이즈**(early) | **+0.200** | 321 | 0.001 | 0.003 | ✅ |
| web_yoy → 매출 서프라이즈(print) | +0.139 | 321 | 0.007 | 0.017 | ✅ |
| web_yoy → 매출 YoY (레벨, sanity) | +0.185 | 317 | 0.041 | 0.008 | ✅ |
| [strong tier] web_yoy → 서프라이즈 | +0.237 | 150 | 0.011 | 0.034 | ✅ |
| [moderate tier] web_yoy → 서프라이즈 | +0.203 | 161 | 0.012 | 0.049 | ✅ |
| web_yoy(t-1) → 서프라이즈 (선행) | +0.229 | 288 | 0.000 | 0.004 | ✅ |
| transform: web_yoy / web_yoy_3m | ✅ / ✅ | | | | robust |
| transform: web_accel (가속) | −0.017 | 256 | 0.735 | 0.795 | ❌ |

**판정: ✅ 웹-지배 유니버스에서 웹트래픽은 매출(서프라이즈 포함)과 유의하게 연관.** YoY 레벨이 신호,
가속(accel)은 무신호. 전(前)-실험 카드(서프라이즈 r=+0.192)보다 오히려 깨끗 — 종목을 "웹이 매출 대부분"으로
고른 효과. within-company corr=+0.135(약하지만 양수).

## 2. LLM 결합 (Factor 3-style 4-arm ablation)

`f1_05_ablation.py` · gpt-5.5-2026-04-23 · n=**60** post-cutoff event · 29종목 · **$12.36**. 전 arm 동일
재무 baseline 테이블, web/text 유무만 변경.

| arm | corr | R² | MAE | sign-hit | p_perm |
|---|---|---|---|---|---|
| fin (재무 track record) | +0.494 | 0.244 | 2.04 | 0.75 | 0.001 |
| fin+web | +0.548 | 0.301 | 2.58 | 0.65 | 0.000 |
| fin+text | +0.470 | 0.220 | 2.05 | 0.83 | 0.002 |
| **fin+web+text** | **+0.592** | **0.350** | 2.24 | 0.77 | 0.000 |

web 단독 X(web_yoy)→true = +0.276. 보완: web adds Δ+0.055, text adds Δ−0.024, **web on text Δ+0.122**,
text on web Δ+0.043, **초가산 synergy = +0.067**.

## 3. 검증 (`f1_06_validate.py`, $0)

**#1 shuffle-company surrogate:** 전 arm 통과(surr_p≤0.003) → firm-specific, 공통추세 artifact 아님.
단 within-company는 약함(fin+web +0.009, 나머지 음수) → 신호가 주로 **between-company**(어느 회사가 beat하나).

**#3 company-clustered bootstrap (5000):**

| 지표 | mean | 95% CI | p(≤0) |
|---|---|---|---|
| **결합 절대상관 r_fwt** | **+0.605** | [+0.39, +0.82] | **0.000 ✅** |
| web_on_text | +0.131 | [−0.06, +0.36] | 0.082 |
| text_on_web | +0.069 | [−0.10, +0.30] | 0.263 |
| **초가산 synergy** | +0.081 | [−0.06, +0.27] | 0.141 ❌ |

## 헤드라인 — F3와 무엇이 다른가

| | Factor 3 (카드, 35종목) | **Factor 1 (웹, 웹-지배 33종목)** |
|---|---|---|
| 재무 baseline 단독 | +0.077 (null) | **+0.494 (강함)** |
| 대체데이터 단독 → 서프라이즈 | 카드 +0.14 (약) | **웹 +0.276 / 패널 +0.20 (유의)** |
| 결합 fin+X+text | +0.281 | **+0.592** |
| 결합 절대 예측력 (cluster-boot CI) | 0 포함 (비유의) | **+0.605, CI 0 제외 (유의) ✅** |
| 초가산 synergy | **+0.214, p=0.010 ✅** | +0.081, p=0.141 (비유의) |

**해석.** 웹-지배 유니버스에서는 (1) **웹트래픽이 단독으로도 매출 서프라이즈의 유의한 신호**이고,
(2) **재무+웹+텍스트 결합이 매출 서프라이즈를 강하게(r≈0.6) 예측**한다(F3엔 없던 *절대* 예측력).
다만 (3) 재무 track record가 이미 강해 **"부분의 합을 넘는" 초가산 synergy는 유의하지 않다**(p=0.14).
즉 F3가 "단독은 무력하나 결합이 살아난다(synergy)"였다면, F1은 **"웹은 그 자체로 강한 매출 신호이고
결합 모델이 최고 성능"**이라는, 결이 다른(그러나 실용적으로 더 강한) 증거다.

**한계:** n=60 단일 post-cutoff 구간, within-company 변동(시점) 신호는 약함(주로 cross-sectional),
종목 30개. Zillow(ZG)는 transcript 부재로 제외. 카드와 동일하게 *매출* nowcasting이지 거래 시그널은 아님.
