# X 조합 실험 — single vs combined → revenue surprise

원본: `factor1_combine/outputs/combine_report.md`

Y = surprise_early 고정. 결합 = 채널별 x_yoy z-score 평균. 동일 공통-티커 패널에서 비교.
시너지 = combined r > max(single r).

## card+foot  (26 공통티커 · 213 이벤트)

card 단독                    r=+0.260  n=213  p_surr=0.001  rho=+0.313  [PASS]
foot 단독                    r=-0.024  n=213  p_surr=0.764  rho=-0.033  [fail]
card+foot 결합               r=+0.139  n=213  p_surr=0.090  rho=+0.164  [fail]

-> best single r=+0.260, combined r=+0.139, Delta=-0.121  결합이 더 나쁨

## card+web  (6 공통티커 · 52 이벤트)

card 단독                    r=+0.100  n=52  p_surr=0.493  rho=+0.163  [fail]
web 단독                     r=+0.155  n=52  p_surr=0.346  rho=+0.178  [fail]
card+web 결합                r=+0.192  n=52  p_surr=0.313  rho=+0.216  [fail]

-> best single r=+0.155, combined r=+0.192, Delta=+0.037  시너지 방향

## foot+web

패널 없음 (`n` 부족), skip

## card+foot+web

패널 없음 (`n` 부족), skip

