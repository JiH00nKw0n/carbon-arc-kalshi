# foot traffic — Y target 탐색

panel: 434 events · 54 tickers
strength coverage: {'?': 1, 'moderate': 19, 'strong': 33, 'weak': 1}

## 기준선 (전체 foot)
  ALL foot → rev_yoy                           r=+0.385 n=434 p_surr=0.000 | rho=+0.403 hit=0.69 IC=+0.372 IR=+1.103 nQ=20 [PASS]
  ALL foot → surprise_early                    r=+0.015 n=434 p_surr=0.785 | rho=-0.026 hit=0.56 IC=-0.071 IR=-0.269 nQ=20 [fail]

## 실험 1 — 인스토어 비중 subset → surprise_early
  가설: 방문=매출인 종목만 보면 방문 정보가 surprise에도 남는다.
  [strong] foot → surprise_early (33tkr)       r=+0.143 n=269 p_surr=0.037 | rho=+0.135 hit=0.58 IC=+0.126 IR=+0.527 nQ=17 [PASS]
  [moderate] foot → surprise_early (19tkr)     r=-0.194 n=150 p_surr=0.045 | rho=-0.260 hit=0.51 IC=-0.165 IR=-0.476 nQ=16 [fail]
  [strong] foot → rev_yoy (참고)                 r=+0.464 n=269 p_surr=0.000 | rho=+0.523 hit=0.74 IC=+0.526 IR=+2.410 nQ=17 [PASS]

## 실험 2 — '잔차 서프라이즈' (컨센서스가 놓친 성장분)
  cons_growth = (CONS_EARLY − ACTUAL_{t-4}) / ACTUAL_{t-4}  (컨센서스가 기대한 YoY 성장)
  resid = rev_yoy − cons_growth  (실제 성장 − 기대 성장 = 컨센서스가 놓친 성장)
  ALL foot → resid_surprise                    r=-0.108 n=218 p_surr=0.145 | rho=-0.133 hit=0.54 IC=-0.026 IR=-0.083 nQ= 9 [fail]
  [strong] foot → resid_surprise               r=-0.010 n=137 p_surr=0.921 | rho=-0.002 hit=0.53 IC=+0.126 IR=+0.375 nQ= 9 [fail]