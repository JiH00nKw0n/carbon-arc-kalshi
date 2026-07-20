# Factor 1 (Traffic) — Foot Traffic × Earnings-Call → Revenue Surprise

> 이 실험은 Factor 3(카드 × 어닝콜 → 매출 서프라이즈)·Factor 1(웹 × 어닝콜 → 매출 서프라이즈)의
> **세 번째 대체데이터 케이스**다. X = Carbon Arc CA0060 Foot Traffic (모바일 geolocation 방문수)으로
> 교체, Z·Y·검정 프레임워크는 factor1·factor3과 **완전히 동일**하게 유지한다.
> 변수 표기·검정 방법론은 [`../factor1/`](../factor1/) 및 [`../factor3/DESIGN.md`](../factor3/DESIGN.md)를 따른다.

---

## 0. 왜 Foot Traffic인가

| 채널 | X | 종목군 | 단독 신호 | synergy 여지 |
|------|---|--------|-----------|--------------|
| Factor 3 | 카드 소비 (CA0056) | omni-channel 소비재 35종 | 약 (+0.136) | 재무+카드+텍스트 +0.281 ✅ |
| Factor 1 (웹) | 웹 트래픽 (CA0030) | 온라인/이커머스 33종 | 중 (+0.200) | 재무+웹+텍스트 +0.592 ✅ |
| **이 실험** | **방문수 (CA0060)** | **오프라인 리테일·F&B 10종** | **r=+0.229 (통계 경계)** | **3Q 이후 확인 예정** |

**Foot Traffic의 의미**: 방문수(volume)는 객단가·가격·믹스를 담지 않는다. 따라서
"방문 YoY ↑ → 매출 ↑"는 자명하지 않고, 어닝콜이 가격 레버·프로모 강도·믹스 변화를 제공할 때
비로소 예측이 완성된다 — synergy 가설과 메커니즘이 명확하다.

---

## 1. 변수 정의

- **X**: CA0060 Foot Traffic, daily mobile geolocation visits, insight_id=45862.
  daily → monthly sum → YoY (`foot_yoy = pct_change(12)`).
- **Y**: 매출 서프라이즈 = `(ACTUAL − CONS_EARLY) / CONS_EARLY`.
  CONS_EARLY = FactSet `FE_BASIC_CONH_QF` SQL, `MAX_BY(FE_MEAN, CONS_END_DATE)` where
  `CONS_END_DATE ≤ FQ_end + 7d` — **지훈님(factor1·factor3)과 완전 동일한 소스·쿼리**.
- **Z**: 직전 분기 어닝콜 전사 (factor3 S3 매핑 재사용 예정, 현재 미구현).
- **CUTOFF**: `2026-05-31` (partial month 2026-06 제거). LLM 평가 컷오프 = `2025-12-01`.

---

## 2. 파일럿 유니버스 (10개 티커)

CMG · COST · DG · DLTR · DRI · EAT · MCD · ROST · SBUX · ULTA

선정 기준: (1) 오프라인 매장 비중 높음, (2) Carbon Arc CA0060 데이터 품질 확인됨,
(3) FactSet 분기 컨센서스 존재. 향후 확장 시 ~28개 추가(비용 ~$600) → factor1과 동등한 n 확보 가능.

**DLTR 주의**: 2025Q1 ACTUAL=4,997M vs CONS_EARLY=8,238M (surprise=-39.3%) — Family Dollar
spinoff로 인한 구조적 단절. 컨센서스가 spinoff를 반영하지 않은 데이터 오염이며 시그널 왜곡의 원인.

---

## 3. 스크립트 구조

| 파일 | 역할 | 대응 factor1 |
|------|------|-------------|
| `ft_config.py` | 경로·universe·FSYM2TKR | `f1_config.py` |
| `ft_00_fetch_factset.py` | FactSet REST API 수집 (참고용) | `f1_00_fetch_factset.py` |
| `ft_01_build_panel.py` | CA0060 daily → monthly → YoY × FactSet PIT | `f1_01_build_panel.py` |
| `ft_02_corr_causation.py` | H1 상관·인과 배터리 | `f1_02_corr_causation.py` |

통계 함수(`cluster_boot`, `surrogate`, `within_company_corr`)는 `factor1/scripts/f1_stats.py`를
직접 import — **코드 중복 없음, 완전히 동일한 검정 로직**.

---

## 4. 데이터

| 파일 | 설명 |
|------|------|
| `data/ca0060_foot_traffic_10tkr_daily_3y.csv` | CA0060 raw (12,090 rows, 2023-03-01~2026-06-21) |
| `data/factset_foot10_pit.json` | FactSet PIT (216 rows, `FE_BASIC_CONH_QF` SQL) |
| `outputs/panel_foot.csv` | 분석 패널 (96 events, 10 tickers) |
| `outputs/corr_results.csv` | H1 배터리 결과 |

`data/` 및 `outputs/` 는 `.gitignore`에서 제외 (대용량·민감 데이터).
