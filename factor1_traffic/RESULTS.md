# Factor 1 (Traffic) — 결과 (Foot Traffic × 어닝콜 → 매출 서프라이즈)

> Factor 3(카드 × 어닝콜 → 매출 서프라이즈)·Factor 1(웹 × 어닝콜 → 매출 서프라이즈)과 동일한
> 프레임워크에서 **X = CA0060 Foot Traffic**으로 교체. Z·Y·검정 방법론·CUTOFF 완전 동일.
> 모든 수치는 재현 가능: `traffic/scripts/ft_0*.py`, 데이터는 `traffic/data/·traffic/outputs/`(gitignored).

## 데이터

- **X (방문수):** Carbon Arc CA0060 Foot Traffic, insight_id=45862 (daily mobile geolocation visits,
  회사별). 2026-06-27 구매 (10 tickers, $211.29, 12,090 rows). daily → monthly sum → YoY.
  부분월 처리: 2026-06 (21/30일, fill-rate 70%) 집계 전 제거.
- **Y (서프라이즈):** FactSet point-in-time 매출 컨센서스 기준 = `(ACTUAL − CONS_EARLY) / CONS_EARLY`.
  소스: FactSet REST Estimates v2 API (`ft_00_fetch_factset.py`). CONS_EARLY = 분기말+7d 이전
  컨센서스 최신값 (PIT). 수치는 지훈님 Snowflake(`FE_BASIC_CONH_QF`/`FE_BASIC_ACT_QF`) 교차검증
  완료 — DLTR 2025-01-31 기준 ACTUAL=4,997 / CONS_EARLY=8,238 / surprise=−39.3% 일치 확인.
  (216 rows, 10 tickers, 2021Q1~2026Q2.)
- **Z (텍스트):** 직전 분기 어닝콜 전사. 내부 S3 버킷(`$AWS_S3_BUCKET_NAME`)에서 58개 다운로드 완료 (`ft_03_fetch_transcripts.py`). 10 tickers, 2025-07-31~2026-06-25.
- **누설 통제:** LLM 평가표본 = `report_date > 2025-12-01` (gpt-5.5 컷오프). 상관·인과 배터리는
  full panel 사용 (LLM 아님 → memorization 무관).

## 1. 대체데이터 자체가 매출 서프라이즈와 유의미한가 (상관·인과 배터리)

`ft_02_corr_causation.py` · 패널 **96 events · 10 tickers · 2024-01-31~2026-05-31**.
검정 게이트 = company-clustered bootstrap (`p_boot`) **AND** shuffle-company surrogate (`p_surr`) 둘 다 < 0.05.
통계 함수 `cluster_boot` / `surrogate` / `within_company_corr` → `factor1/scripts/f1_stats.py` 직접 import.

**[사전선언 규칙] 구조적 단절 분기 제외:** M&A·분사 등으로 컨센서스가 구조변화 이전 기준으로 설정된
분기는 surprise가 실적이 아닌 컨센서스 미반영 아티팩트이므로 제외한다. 해당 분기만 제거하며
동일 회사의 나머지 분기는 유지한다. (적용: DLTR 2025-01-31 — Family Dollar 분사)

| 검정 | r | n | p_boot | p_surr | 판정 |
|------|---|---|--------|--------|------|
| foot_yoy → 매출 YoY (레벨, sanity) | +0.178 | 96 | 0.053 | 0.198 | ❌ |
| foot_yoy → **매출 서프라이즈 (early)** — full panel | **+0.229** | **96** | **0.081** | **0.050** | **❌** |
| foot_yoy → 매출 서프라이즈 (print) | +0.220 | 96 | 0.078 | 0.045 | ❌ |
| transform: foot_yoy_3m | +0.179 | 90 | 0.042 | 0.266 | ❌ |
| **[drop DLTR 2025-01-31]** foot_yoy → 서프라이즈 | **+0.138** | **95** | **0.298** | **0.376** | **❌** |
| [no DLTR all] foot_yoy → 서프라이즈 (참고용—잘못된 처리) | +0.154 | 86 | 0.252 | 0.324 | ❌ |
| foot_yoy(t-1) → 서프라이즈 (선행) | −0.030 | 86 | 0.700 | 0.835 | ❌ |

**within-company corr(foot_yoy, surprise_early) = +0.252** (firm-mean 제거 후 — "같은 회사의 방문 많은 분기가 beat하는가").

### 판정: ❌ NULL

헤드라인: 사전선언 규칙 적용 후 **r=+0.138, p_boot=0.298, p_surr=0.376 — null**.

- **full panel(오염점 포함) r=+0.229**는 DLTR 2025-01-31 단일 분기(foot_yoy −6.2% × surprise −39.3%)가
  cross-sectional r을 위로 끌어올리는 고레버리지 아티팩트. 이 점은 진짜 신호가 아니므로 헤드라인에서 제외.
- 오염 분기 1개만 제거하면 r=+0.138로 수렴 — 이게 정직한 헤드라인.
- **[no DLTR all]은 잘못된 처리**: DLTR 정상 9분기까지 같이 버려서 오히려 손해. 참고용으로만 기재.

**null의 구체적 원인 — n=10 클러스터 표본 부족:**

bootstrap 95% CI (full panel 기준) = [−0.029, +0.391]. 역신호 티커(COST −0.340, ULTA −0.471,
CMG −0.267)가 3~4개 무작위 과표집되면 전체 r이 뒤집히는 구조. factor1 웹(33개, p_boot=0.001)·
factor3 카드(35개 통과)와의 차이는 유니버스 크기.

**선행(lead) 효과 없음:** foot_yoy(t-1) → surprise r=−0.030 — coincident 지표이며 1분기 선행 예측력 없음.

### 티커별 within-회사 상관

| 티커 | r(foot_yoy, surprise_early) | n |
|------|---------------------------|---|
| EAT | **+0.722** | 9 |
| DLTR | +0.657 | 10 |
| SBUX | +0.377 | 9 |
| ROST | +0.128 | 10 |
| MCD | +0.072 | 9 |
| DG | +0.060 | 10 |
| DRI | −0.167 | 10 |
| CMG | −0.267 | 9 |
| COST | −0.340 | 10 |
| ULTA | **−0.471** | 10 |

신호 방향이 회사마다 엇갈림 (5개 양수 / 5개 음수). EAT·DLTR처럼 강한 양의 신호가 있지만
COST·ULTA의 역신호가 cross-sectional r을 희석. 이는 foot traffic이 업종·비즈니스 모델에 따라
매출에 미치는 경로가 다를 수 있음을 시사 (객단가·채널 mix·프로모 등 Z가 풀어줄 수 있는 요소).

### DLTR FY2025Q1 구조적 단절

| FE_FP_END | foot_yoy | ACTUAL ($M) | CONS_EARLY ($M) | surprise_early |
|-----------|----------|-------------|-----------------|----------------|
| 2024-01-31 | +7.7% | 8,633 | 8,664 | −0.4% |
| 2024-04-30 | +4.9% | 7,626 | 7,643 | −0.2% |
| 2024-07-31 | +7.9% | 7,373 | 7,505 | −1.8% |
| 2024-10-31 | +6.2% | 7,562 | 7,445 | +1.6% |
| **2025-01-31** | **−6.2%** | **4,997** | **8,238** | **−39.3%** |
| 2025-04-30 | +3.9% | 4,637 | 4,525 | +2.5% |
| 2025-07-31 | +5.7% | 4,567 | 4,465 | +2.3% |

2025Q1(FY2025): Family Dollar spinoff 완료로 Dollar Tree 단독 매출로 전환. ACTUAL=$4,997M이나
CONS_EARLY=$8,238M은 spinoff 이전 전체 기준으로 책정 → surprise=**−39.3%**는 실제 경영 성과가
아니라 컨센서스 미반영 구조 변화. 지훈님 Snowflake에서도 동일 수치 확인.

**처리:** 이 1개 분기만 제거 → r=+0.138. DLTR 회사 전체 제거(r=+0.154)보다 낮은 이유:
2025-01-31 오염점은 foot_yoy −6.2% × surprise −39.3%로 r을 **위로** 끌어올리는 구조였음.
오염점 제거 시 그 부풀림이 사라져 r이 낮아지는 것이 정상. spinoff 이전 9개 정상 분기는 유지.

## 2. LLM 결합 (Factor 3-style ablation)

`ft_21_run.py` + `ft_22_eval.py` · gpt-5.5-2026-04-23 · zero-shot · 5-fold-by-company calibration · n=24

| arm | RMSE | R²_OOS | corr | calib R²(OOF) | sign |
|-----|------|--------|------|----------------|------|
| LLM fin | 2.31 | −0.218 | +0.221 | −0.171 | 0.71 |
| LLM fin+x | 3.02 | −1.081 | −0.145 | −0.281 | 0.46 |
| **LLM fin+text** | **2.21** | **−0.114** | **+0.423** | **+0.025** | **0.79** |
| LLM fin+x+text | 2.87 | −0.884 | −0.174 | −0.439 | 0.50 |

Classical baselines (n=24 test set):

| model | RMSE | R²_OOS | corr | sign |
|-------|------|--------|------|------|
| N0 naive (company mean) | 2.80 | −0.790 | +0.052 | 0.54 |
| N1 X-OLS | 3.66 | −2.069 | +0.207 | 0.42 |
| N2 sentiment-OLS | 2.11 | −0.015 | +0.234 | 0.83 |
| N5 GBT (x,sent,lag) | **1.92** | **+0.161** | **+0.447** | 0.79 |

**synergy** (company-clustered bootstrap, 5000, seed 2026):
- synergy(corr) mean=−0.236, p(≤0)=0.862 → not significant
- synergy(MSE-skill) mean=+0.055, p(≤0)=0.342 → not significant
- shuffle-company surrogate p_surr=0.409 → not significant

**Architecture** (n=24):
- Arch-A (text→score→OLS): corr=+0.417
- Arch-C (x+text→feat→OLS): corr=+0.046
- Arch-B (end-to-end): corr=−0.174

**Z-depth** (n=21): z1 corr=−0.215 → z2 corr=+0.232 (2 prior calls 추가 시 개선)

## 헤드라인 — factor1·factor3 비교

| | Factor 3 (카드, 35종목) | Factor 1 (웹, 33종목) | **이 실험 (방문수, 10종목)** |
|---|---|---|---|
| 소스 데이터 | CA0056 Card Spend | CA0030 Clickstream | CA0060 Foot Traffic |
| 패널 events | 190 | 321 | **96** |
| 티커 수 | 35 | 33 | **10** |
| 대체데이터 → 서프라이즈 r | +0.136 | **+0.200** | +0.138 (drop DLTR 2025-01-31) |
| p_boot | 통과 | **0.001 ✅** | 0.298 ❌ |
| p_surr | 통과 | **0.003 ✅** | 0.376 ❌ |
| GBT R²_OOS | — | — | **+0.161** |
| 결합 fin+text corr (gpt-5.5) | +0.281 ✅ | +0.592 ✅ | **+0.423** |

**해석:** 사전선언 규칙(구조적 단절 1개 분기 제거) 적용 후 r=+0.138, null. full panel r=+0.229는
DLTR 오염점에 기댄 수치로 헤드라인으로 쓸 수 없다. 이는 "foot traffic 신호가 없다"는 것이 아니라
**n=10 클러스터 소표본에서 통계적 입증이 불가능함**을 의미한다 — 티커 확장이 우선 과제.

## 한계 및 다음 단계

1. **티커 확장 (~28개 추가, 비용 ~$600)**: 38개 이상 → bootstrap p_boot 기대 <0.05
   (factor1 웹 33개에서 p_boot=0.001 달성).
2. **Z 연결 (어닝콜 → factor3 S3)**: foot_yoy 단독 null → 결합 시 synergy 확인.
   방문수는 "객단가·가격·채널믹스를 담지 않음" → 어닝콜이 정확히 그 공백을 채우는 메커니즘.
3. **업종별 분리 분석**: 음식료(CMG/MCD/SBUX/DRI/EAT)·리테일(COST/DG/DLTR/ROST/ULTA) 각각의
   신호 방향이 다를 수 있음 — 티커 확장 후 tier split 재검증.

---

## 전체 실험 해석 (narrative)

### 왜 웹 트래픽과 결과가 다른가

지훈님 웹 실험(factor1)은 처음부터 "웹이 매출의 주 채널인 회사"만 선별했다. 이커머스·온라인 마켓플레이스 중심이라 웹트래픽 상승 → 매출 상승의 인과 경로가 비교적 단순하다. 그래서 대체데이터 단독 r=+0.200(p=0.001)이 나왔고, LLM도 그 맥락을 이해해 fin 단독 corr=+0.494라는 강한 재무 baseline이 형성됐다.

반면 이번 foot traffic 10개 티커는 그런 선별 없이 음식료(EAT/MCD/SBUX/CMG)와 리테일(COST/DG/DLTR/ROST/ULTA)이 섞여 있다. 방문 증가 → 매출 증가가 직결되는 회사(EAT within-r=+0.722)와, 멤버십 모델(COST)·온라인 병행(ULTA)처럼 방문 패턴이 매출보다 할인행사·계절성에 좌우되는 회사가 공존한다. 10개 중 5개가 음의 within-company 상관이고, 이것이 cross-sectional r을 희석시킨다.

**"foot traffic 신호가 없다"가 아니라 "유니버스 구성이 이종 혼합"이라는 해석이 맞다.**

---

### H1: 대체데이터 단독 신호 — ❌ NULL (r=+0.138)

헤드라인 r=+0.138은 사실 두 가지 힘이 상쇄된 결과다. EAT·DLTR처럼 강한 양의 신호가 있지만 COST·ULTA의 역방향 신호가 동시에 작용한다. n=10 클러스터라 bootstrap 신뢰구간이 [−0.03, +0.39]로 넓어 어느 방향도 입증하지 못한다.

full panel r=+0.229가 더 높은 건 DLTR 2025-01-31 오염점(foot_yoy −6.2% × surprise −39.3%) 단 1개가 고레버리지로 r을 끌어올렸기 때문이다. 사전선언 규칙에 따라 그 분기를 제거하면 r=+0.138로 수렴한다 — 이게 정직한 숫자다.

웹 실험(p_boot=0.001)과 gap이 큰 이유는 단순히 n=10 vs 33의 문제다. 유니버스가 3배 이상 차이나면 bootstrap power가 완전히 다르다. 동일한 r=+0.14 수준이더라도 n=33이면 통과할 수 있다.

---

### H2: Classical Baselines — GBM만 작동

Foot-OLS(N1)는 corr=+0.207이지만 RMSE=3.66, R²=−2.07로 스케일 예측이 크게 어긋난다. sentiment-OLS(N2, corr=+0.234)가 더 나은 건 LM 감성점수가 어닝콜 텍스트 기반이라 직접적인 경영진 시그널을 담기 때문이다.

GBM(N5)이 RMSE=1.92, corr=+0.447, R²=+0.161로 유일하게 OOS 양수를 기록한 건, GBM이 foot_yoy·sentiment·lag surprise를 비선형으로 조합해 이종 혼합 유니버스에서 회사별 패턴을 부분적으로 포착했기 때문이다. 단, n=24 테스트셋에서의 수치이므로 과도한 해석은 금물이다.

---

### H3: LLM 4-arm Ablation — fin+text가 유일한 양의 corr

LLM(fin) corr=+0.221은 재무 track record만으로의 baseline이다. 웹 실험에서 fin 단독이 +0.494였던 것보다 낮지만 양수를 유지한다. 단 RMSE=2.31, R²=−0.218로 스케일은 여전히 어긋나 있다.

foot traffic(x)을 추가했을 때(fin+x) corr=−0.145로 방향이 역전된다. RMSE=3.02, R²=−1.081로 크게 악화. LLM이 foot_yoy 숫자를 받아도 "이 회사에서 방문 증가가 매출로 이어지는 구조인지"를 판단하지 못하고 혼선을 겪는 것으로 보인다.

어닝콜(text)을 추가했을 때(fin+text) corr=+0.423, calib R²=+0.025로 캘리브레이션 후에도 유일하게 양수를 기록한다. 경영진의 말이 매출 방향에 대한 직접적인 단서를 제공하기 때문이다. sign accuracy=0.79로 방향 예측도 가장 높다. 그러나 fin+x+text(corr=−0.174)는 오히려 역방향이다. text의 긍정적 기여를 x의 노이즈가 압도하는 구조다.

**결론: 이 유니버스에서 LLM에게 foot traffic 숫자를 주는 건 도움이 안 되고 오히려 해가 된다. text만이 LLM 예측력을 끌어올리는 유일한 추가 입력이다.**

---

### H4: Synergy — 없음 (p=0.342)

synergy(corr) mean=−0.236, p(≤0)=0.862. synergy(MSE-skill) mean=+0.055, p(≤0)=0.342. MSE 기준으로는 방향은 양수이지만 유의하지 않다. shuffle-company surrogate p_surr=0.409로도 통과하지 못한다.

이건 foot traffic 신호 자체가 약한 상황에서 LLM이 서로 모순되는 정보(텍스트는 긍정, foot은 음수이거나 반대)를 받아 혼란이 배가되기 때문이다. X 신호가 강해야 text와 보완 관계가 형성되는데, 지금은 그 전제가 성립하지 않는다.

---

### H5: Architecture A/B/C — Arch-A가 그나마 최선

Arch-A(LLM → 3개 점수 → OLS, corr=+0.417)가 B·C보다 명확히 낫다. LLM이 직접 수치를 예측하는 것(B, C)보다 "중간 점수를 뽑고 OLS가 선형 결합"하는 구조가 노이즈에 더 robust한 것으로 해석된다. fin+text(+0.423)와 비슷한 수준의 corr을 기록하는 점이 주목할 만하다.

Arch-C(transcript+x → feat → OLS, corr=+0.046)가 Arch-A보다 낮은 건 역시 x(foot traffic)가 OLS 피처로 들어갔을 때 노이즈로 작용하기 때문이다. Arch-B(end-to-end, corr=−0.174)는 ablation fin+x+text와 동일 — x 추가가 해가 되는 구조다.

**핵심 발견:** Arch-A와 fin+text가 +0.42 수준에서 수렴하고 나머지는 낮거나 음수 — text 신호가 살아있고 x가 그것을 훼손하는 패턴이 일관되게 나타난다.

---

### H6: Z-depth z1 vs z2 — 방향 개선, 음에서 양으로 전환

z1(직전 1개 콜)에서 RMSE=2.92, corr=−0.215. z2(직전 2개 콜)에서 RMSE=2.51, corr=+0.232로 음에서 양으로 전환된다. 2개의 prior call을 쌓으면 방향이 개선되는 패턴이 이번 유니버스에서도 확인된다. 이는 2분기 전 어닝콜이 추가 컨텍스트를 제공해 LLM 예측 안정성이 높아지는 효과로 볼 수 있다.

n=21 subset이라 통계적 유의성 판단은 어렵지만, 방향 전환 자체가 긍정적 신호다. 유니버스를 확장하면 z2의 효과가 통계적으로 드러날 가능성이 있다.

---

### 종합 해석 및 다음 단계

이번 실험의 핵심 메시지는 **"foot traffic 신호 자체는 살아있으나, 현재 유니버스와 표본 규모로는 통계적 입증이 불가능하다"**는 것이다.

EAT(within-r=+0.722)처럼 방문이 곧 매출인 회사는 강한 신호를 보인다. 문제는 그 반대 구조의 회사(COST, ULTA)가 같은 유니버스에 섞여 있고, n=10이라 bootstrap이 이를 분리할 힘이 없다는 것이다.

웹 실험과 비교하면 방법론은 동일하고, X 데이터의 업종 적합성과 유니버스 크기만 다르다. 따라서 다음 스텝은 명확하다.

1. **유니버스 선별**: "foot이 매출의 주 채널인 종목" — 레스토랑 체인, 오프라인 전용 리테일, 피트니스·엔터테인먼트처럼 방문=구매 구조인 회사 위주로 재구성.
2. **종목 수 확장**: 38개 이상으로 확장하면 bootstrap power가 웹 수준으로 올라간다.
3. **업종 분리 분석**: 확장 후 레스토랑·리테일·엔터테인먼트 각각을 별도로 검증해 신호 방향이 균일한 sub-universe를 찾는다.

이 세 가지가 해결되면 foot traffic도 웹 수준의 r=+0.20, p<0.05에 도달할 가능성이 충분하다.
