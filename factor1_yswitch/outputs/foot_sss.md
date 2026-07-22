# foot traffic × SSS surprise

panel: 384 events · 49 tickers · 2024-04-30..2026-05-31
sss_surprise: mean=+0.53pp sd=1.72pp

## foot → SSS surprise  (vs. 총매출 surprise 실패했던 것과 비교)
  ALL foot → sss_surprise                  r=+0.072 n=384 p_surr=0.331 | rho=+0.001 hit=0.53 IC=+0.093 IR=+0.328 nQ=17 [fail]
  within-company corr = -0.027

## 인스토어 subset → SSS surprise
  [strong] foot → sss_surprise (32tkr)     r=+0.123 n=261 p_surr=0.129 | rho=+0.081 hit=0.56 IC=+0.188 IR=+0.589 nQ=17 [fail]
  [moderate] foot → sss_surprise (16tkr)   r=-0.209 n=116 p_surr=0.286 | rho=-0.223 hit=0.46 IC=-0.097 IR=-0.263 nQ= 8 [fail]

## 참고: SSS actual 자체(레벨)와의 상관
  ALL foot → SSS_ACTUAL(level)             r=+0.193 n=384 p_surr=0.014 | rho=+0.178 hit=0.65 IC=+0.299 IR=+1.226 nQ=17 [PASS]