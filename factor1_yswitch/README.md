# Factor 1 (Y-switch) — Carbon Arc X (card / foot / click) × switched Y

> 이 실험은 지훈님 `factor1` / `factor1_traffic` 프레임워크의 **Y-스위칭 확장**이다.
> X(대체데이터 신호)를 고정하고 **Y(예측 타겟)를 바꿔가며** 각 채널이 실제로 무엇을
> 예측하는지 측정한다. 검정 로직(clustered-bootstrap + shuffle-surrogate)은 `factor1/scripts/f1_stats.py`를
> **그대로 import**해서 재사용 — 코드 중복 없음.

## 0. 동기

지훈 factor3 baseline: **CA0056 카드 × Revenue Surprise r=+0.192 (p_surr=0.008 ✅)**.
같은 X를 EPS surprise·주가수익률로 바꾸면 실패했다 (r=+0.065 / +0.044, 유의하지 않음).
즉 **"Y를 바꾸는 실험"은 이미 신호가 있었고**, 알트데이터는 "물리적 실판매"의 프록시라
매출엔 붙고 마진·주가엔 안 붙는다는 해석이 섰다. 이 실험은 그 Y-스위칭을 **3개 채널로 일반화**하고
**팩터 연구용 메트릭(rank-IC / IC-IR / Spearman / hit-rate / lag-curve)**을 추가한다.

## 1. 데이터 (모두 이미 구매한 Carbon Arc framework를 무료 재다운로드)

| 채널 | X | dataset | 주기 | 티커 | 파일 |
|------|---|---------|------|------|------|
| card  | credit_card_spend (Online+Physical 합산) | CA0056 | 분기 | 66 | `data/ca0056_card_66tkr_quarterly.csv` |
| foot  | foot_traffic (월 합산 → YoY) | CA0060 | 월 | 54 | `data/ca0060_foot_*` (10+20+24) |
| click | website_users (Mobile+Desktop 합산) | CA0030 | 월 | 34 | `data/ca0030_click_38tkr.csv` |

- **X 변환**: card는 `pct_change(4)`(분기), foot/click은 월 합산 후 `pct_change(12)` → FQ-end에 `merge_asof`(45d) 정렬.
- **재다운로드는 크레딧 0원.** stale 아닌 지훈 6/27~6/29 구매분(framework_id 계정 귀속) 사용. buy/build 호출 없음.

## 2. Y (FactSet PIT, 지훈과 동일 소스)

| Y | 정의 | 역할 |
|---|------|------|
| `rev_yoy` | `pct_change(4)` of ACTUAL revenue | level sanity |
| `surprise_early` | `(ACTUAL − CONS_EARLY)/CONS_EARLY`, CONS_END ≤ FQ_end+7d | **THE test (지훈 baseline)** |
| `surprise_print` | `(ACTUAL − CONS_PRINT)/CONS_PRINT` | print-time consensus 대비 |

FactSet OAuth `/surprise` + `/rolling-consensus` — 회사 구독이라 CA 크레딧과 무관.

## 3. 메트릭

| 메트릭 | 의미 |
|--------|------|
| `r` + `p_boot` | Pearson, company-clustered bootstrap (지훈 gate) |
| `p_surr` | shuffle-company surrogate (지훈 gate). **PASS = p_boot<0.05 AND p_surr<0.05** |
| `rho` (Spearman) | 순위상관 — surprise/YoY의 fat-tail robustness 크로스체크 |
| `hit_rate` | `P(sign(x)==sign(y))` — 0.50 대비 방향 일치 엣지 |
| `mean_ic` / `ic_ir` / `ic_t` | 분기별 cross-sectional rank-IC 평균 · info-ratio(mean/std) · t-stat. 실전 팩터 지표 |

## 4. 스크립트

| 파일 | 역할 | 대응 (지훈) |
|------|------|-------------|
| `ys_config.py` | 경로·채널 파일·클릭 name2ticker | `ft_config.py` |
| `ys_00_fetch_factset.py` | 121-티커 union FactSet PIT 수집 | `ft_00_fetch_factset.py` |
| `ys_lib.py` | 채널별 X 빌더 + 신규 메트릭 | (신규) |
| `ys_01_build_panels.py` | 채널별 X×Y 패널 3개 빌드 | `ft_01_build_panel.py` |
| `ys_02_yswitch.py` | Y-스위칭 배터리 실행 | `ft_02_corr_causation.py` |

`f1_stats.cluster_boot / surrogate / within_company_corr`는 직접 import.

## 5. 실행

```bash
python ys_00_fetch_factset.py   # Y 수집 (1회)
python ys_01_build_panels.py    # 패널 3개
python ys_02_yswitch.py         # 결과 → outputs/yswitch_report.md + yswitch_results.csv
```

## 6. 주의

- **click 채널 YoY 아웃라이어**: 신규 상장·급성장주(RDDT 등)에서 website_users YoY가 수십 배로 튐
  (max ~35x). Spearman/rank-IC는 순위 기반이라 영향 적으나 Pearson `r`은 왜곡될 수 있어 병기 해석.
- **click name→ticker 매핑**: PetMed·Phlur·Qwant·Evereve·goodrx 등은 단일 US 상장 매핑이 애매해 제외.
- **DLTR 2025-01-31**: Family Dollar spinoff로 surprise=-39% 구조적 단절 (지훈 문서화). foot 패널에 포함되나
  outlier robustness는 지훈 factor1_traffic 결과 참조.
