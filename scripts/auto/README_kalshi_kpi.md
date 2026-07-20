# Kalshi × FactSet — 예측시장 KPI-nowcast 실험 (s_ka ~ s_ki)

factor3 뼈대에서 **X를 Kalshi 예측시장 implied KPI 분포**로 갈아끼운 실험. 7→12 종목으로 확장.
결과물 CSV는 `outputs/`(gitignore) — 아래 스크립트로 전부 재현 가능.

## 결론 (요약)

**예측시장은 회사 KPI 자체는 정밀하게 예측하지만(GATE1 r≈0.96), 그 정보가 매출·주가로는 이어지지 않는다.** KPI 서프라이즈가 이미 애널리스트 매출 컨센서스에 반영돼 있어, 매출 잔차에는 예측시장이 더할 정보가 남지 않는다(factor3 카드결제 결론과 동일 지점). 유일하게 살아있는 발견은 예측시장 자체의 **중간확률 과대평가**(EXP-3).

## 데이터 소스

- **Kalshi** (public, 인증 불필요): `/historical/markets/{ticker}/candlesticks?period_interval=1|60|1440`
  — 정산 이전 시점(T−k)의 implied 확률. `/historical/markets?series_ticker=`의 last_price는
  정산 후 값이라 누수 → 반드시 candlestick 사용.
- **FactSet** (linq-local MCP, `http://localhost:3035/mcp`, `factset_query`): FE_V4 매출 actual/PIT 컨센.
  stock DB 터널 없이 Snowflake 직접. Tesla -R = Q2YN1N-R 등.
- **FMP** (historical price, 키는 mcp-server .env): 어닝데이/발표일 주가 return.

## 스크립트

| 스크립트 | 역할 | 출력 |
|---|---|---|
| `s_ka_kpi_inventory.py` | Companies 카테고리 KPI 사다리 인벤토리 | kalshi_kpi_inventory.csv |
| `s_kd_multico_scan.py` | Financials 카테고리 확장 스캔 (실제 회사 KPI는 여기 있음) | kalshi_multico_inventory.csv |
| `s_kb_build_X.py` | X 빌더: T-1/7/30/60 implied CDF→모멘트, 누수차단 | kalshi_X.csv, kalshi_X_grid.csv |
| `s_kc_align_Y.py` | Y: FactSet 매출 서프라이즈 + X 정렬 | kalshi_panel.csv |
| `s_ke_gates_multico.py` | GATE1(implied→KPI) + GATE2(revision→매출) | (stdout) |
| `s_kf_leadlag.py` | EXP-1: 예측시장 vs 애널리스트 lead-lag | kalshi_leadlag.csv |
| `s_kg_kpi_return.py` | EXP-2: KPI 서프라이즈 → 어닝데이 주가 | kalshi_kpi_return.csv |
| `s_kh_calibration.py` | EXP-3: 정산 calibration/미스프라이싱 | kalshi_calibration.csv |
| `s_ki_macro_asset.py` | EXP-4: 매크로 예측시장 → 자산 | kalshi_macro_asset.csv |

## 실험 결과

- **기반 (GATE1/GATE2)**: implied→실제 KPI r=0.96 (통과). revision→매출 서프라이즈 pooled r=0.04 (null).
- **EXP-1 lead-lag**: peak lag=0, |r|<0.05. 약한 null.
- **EXP-2 KPI→주가**: ALL corr −0.24. Tesla −0.53("sell the news"), Meta +0.64. 혼재 null.
- **EXP-3 calibration ★**: n=1913, Brier 0.097. **40-60% implied이 실제 32-40%만 정산 (13pp 과대평가)**, 회사·매크로 양쪽. 거래 후보.
- **EXP-4 매크로→자산**: NFP revision→TLT +0.20/SPY −0.22 (경제적 타당, 최강). |r| 0.1-0.2.

## 유니버스 (12종목)

매출 연결 가능 회사 KPI: Tesla(9q), Meta DAP(8q), NYT(7q), Robinhood(7q), Spotify(7q), SoFi(6q),
Netflix(4q) — 통계 가능. Uber/DoorDash/Boeing/Southwest/SpotifyMAU(각 2q) — 관측치만, 통계 불가.

## 재현

```bash
# linq-local MCP 서버 기동 (FactSet), 그다음:
python scripts/auto/s_kd_multico_scan.py   # 인벤토리
python scripts/auto/s_kb_build_X.py        # X
python scripts/auto/s_kc_align_Y.py        # Y
python scripts/auto/s_ke_gates_multico.py  # GATE1/2
python scripts/auto/s_kf_leadlag.py        # EXP-1
python scripts/auto/s_kg_kpi_return.py     # EXP-2
python scripts/auto/s_kh_calibration.py    # EXP-3
python scripts/auto/s_ki_macro_asset.py    # EXP-4
```

## 다음

EXP-3 중간확률 과대평가를 OOS 분할(2024 vs 2025-26) + 거래비용 반영해 실전 backtest.
