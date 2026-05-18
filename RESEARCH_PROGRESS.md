# CarbonArc × Kalshi Research — Progress Tracker

_Last updated 2026-05-18_

> 진행 로그. 자세한 분석/결과는 `README.md` 와 `docs/` 를 참조. 이 파일은 *연표* + *현재 wip* 위주.

## 현재 상태 (한 줄)

754 후보 페어 추출 완료 → 3 framework 구매 ($44.41 / $50 promo) → 13 macros × 3 dataset lag corr 검증 → **데이터셋 측정 단위 (사용자 수 vs 거래 금액 vs 거래 건수) 가 lead-lag 결과 방향을 좌우**. 다음: 검증 깊이 (Granger / detrend / OOS).

## 연표

| 시점 | 마일스톤 | 핵심 산출물 |
|---|---|---|
| 2026-05-08 | Repo 시작, CarbonArc API 탐색, 데이터 가치 메모 | `ANALYSIS.md`, `DATA.md` |
| 2026-05-11 | 초기 수작업 매핑 시도 (legacy) — 21 CA × 66 Kalshi → 39 페어 | `outputs/leadlag_candidates.csv` |
| 2026-05-12 | Phase 1 sample EDA — CA0049 × UMich r=−0.79 (n=20, COVID 영향, statistical evidence X) | `outputs/eda/PHASE1_REPORT.md` |
| 2026-05-12 | Phase 2 백테스트 디자인 (4 scenarios, LightGBM+SHAP) — 디자인만, 실행 X | `docs/leadlag_scenarios.md` |
| 2026-05-13 | Phase 3 LLM 비정형 PoC smoke test 통과 | `prompts/ca_row_to_text.md`, `docs/llm_cost.md` |
| 2026-05-14 | **Phase 0 자동 파이프라인 완성** — cheap-first 필터로 754 후보 추출 | `scripts/auto/`, `docs/verification_pairs_macro.md` |
| 2026-05-15 | Phase 4 framework 가격 조사 (35 CA × 1y/3y/5y) | `docs/framework_prices.md`, `scripts/auto/s_e_price_all.py` |
| 2026-05-15 | Phase 5 첫 구매 — CA0030 Clickstream 5y, $4.99 | `docs/purchase_log.md` |
| 2026-05-18 | Phase 5 두·세 번째 구매 — CA0056 Card Spend $14.03, CA0034 POS Volume $25.39 | `docs/purchase_log.md` |
| 2026-05-18 | **3 dataset × 13 macros lag corr 검증 완료** — 측정 단위 의존적 결과 | `docs/analysis_per_dataset.md` |

## 결과 요약 (Phase 5)

| Dataset | 측정 단위 | Verdict | 핵심 시그널 |
|---|---|---|---|
| CA0030 Clickstream | 사용자 수 | **미지지** | 7/13 Macro leads (panel-growth artifact) |
| CA0056 Card Spend | 거래 금액 | **부분 지지** | 6/13 CA leads. PCE/CPI/NFP 가 lag +1~+2 에서 \|r\|=0.8 |
| CA0034 Instore POS | 거래 건수 | **잠정 지지** | 10/13 CA leads. NFP/PI/Core CPI \|r\|≈0.8 |

판정 기준 + per-pair table 은 `README.md` 의 §"Phase 5 결과 — 페어별 verdict" 참조.

## 미해결 / Caveats

- **Common-trend 영향 미보정**: 2021-2026 nominal 상승 추세가 YoY 적용에도 잔여 가능성. Detrended residual 에서 lag pattern 재현 검증 필요
- **Multiple testing**: 520+ comparisons, Bonferroni / permutation 미적용
- **Lag ±2 endpoint piling**: best_lag 가 ±2 에 몰림 → lag ±4 까지 확장 필요
- **Causality 미검증**: r ≠ causation. Granger-causality test, OOS forecast 정확도 측정 미실시
- **n=46~51 (YoY)**: 효과 크기 정밀도 부족 (r=0.7 의 95% CI ≈ [0.52, 0.83])
- 754 후보 중 entertainment/sports 46 페어 borderline — 수동 점검 미실시

## 다음 액션 (추가 비용 0)

1. **Detrended (level − linear trend) 에서 lag corr** — 현재 YoY 결과의 robust 검증
2. **Granger-causality test** (`statsmodels.tsa.stattools.grangercausalitytests`)
3. **Lag 범위 ±4 확장** — endpoint piling 해소
4. **Out-of-sample forecast** — 2021-2024 fit → 2025+ predict, baseline AR(1) 대비 incremental 정확도

## 다음 액션 (추가 구매, promo $5.59 남음)

- CA0058 Card Health Spend 1y monthly $4.99 — Medical CPI 검증
- 또는 CA0010 OTT Streaming 5y monthly $4.99 — 엔터테인먼트 borderline 페어 검증

## Repo 구조

자세히는 `README.md`. 핵심 파일:
- `scripts/auto/s_a1..s_g_*.py` — Phase 0 / 4 / 5 파이프라인
- `docs/verification_pairs_macro.md` — Phase 0 메인 (754 후보)
- `docs/framework_prices.md` — Phase 4 가격표
- `docs/analysis_per_dataset.md` — Phase 5 메인
- `docs/purchase_log.md` — 구매 거래 기록
