# Macro Track 검증쌍 — 자동 도출

> Phase 0 (automated) 의 실행 결과. cheap-first 필터 + 
> authoritative 매크로 list 기반.

## TL;DR

| Stage | 방법 | 개수 |
|---|---|---:|
| Stage A1 — Macro event master list | FMP + FRED union | 123 |
| Stage A2 — Kalshi 시리즈 (전체) | outputs/kalshi_series_all.csv | 10161 |
| Stage A2 — Macro Kalshi (rule match) | title regex 매치 | 151 |
| Stage B — CA × macro Kalshi (timing 평가) | 63 non-WC CA × 151 macro Kalshi | 6795 |
| Stage B — Timing pass (lead ≥ 3d) | 코드 계산 | 5664 |
| Stage C — Mechanism LLM verify | Haiku 4.5 | 5664 |
| **Final 채택 (connected=true)** | — | 754 |

## 방법론

- **Stage A1**: FMP economic_calendar (1,225 release 의 unique event 이름) + 
  FRED indicators (St. Louis Fed 큐레이트) union. 수작업 매크로 list 추가 X.
  → `outputs/auto/macro_event_master_list.csv`
- **Stage A2**: Kalshi 시리즈 (10,161 전부) 의 title 에 master list event 이름 + 
  공식 alias (BLS/BEA/Census 공식 약어) regex 매치. 룰은 
  `docs/macro_matching_rules.md` 에 commit.
  → `outputs/auto/macro_kalshi.csv` (1.5% = 151 series)
- **Stage B**: 63 non-WC CA × 매크로 Kalshi 모든 페어에 
  `lead_window_days = (macro_cadence) − (ca_lag)` 계산. ≥ 3일만 통과.
  → `outputs/auto/timing_pass.csv`
- **Stage C**: Timing-pass 페어에 Anthropic Haiku 4.5 호출, 
  JSON `{connected, channel, caveat}`. `connected=true` 만 최종 채택.
  Temperature=0, single system prompt (cached).
  → `outputs/auto/mechanism_verified.csv`

LLM 호출은 Stage C 만 발생 — 페어 단위 검증. Stage A·B 는 0 LLM.

## Sanity checks

### Anchor pairs

- **CA0030 Clickstream × KXUMICHOVR**: Stage B lead=29d (✅ pass), Stage C ✅ accepted
- **CA0056 Card × KXUSRETAIL**: Stage B lead=27d (✅ pass), Stage C ✅ accepted

### Negative control

⚠️ entertainment/music/sports CA 들 중 46 페어 채택 — 수동 점검 필요

| ca_dataset_id   | ca_name                                    | kalshi_series_ticker   | channel                                                                                                                                                                                                                                                                                                                                                                                                            |
|:----------------|:-------------------------------------------|:-----------------------|:-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| CA0036          | Secondary Market Ticket Sales and Listings | CPISHELTER             | Secondary market ticket sales reflect consumer spending patterns and demand for entertainment/events, which correlates with discretionary spending behavior that feeds into overall consumer price pressures and shelter-related inflation dynamics through wealth effects and labor market tightness.                                                                                                             |
| CA004           | Secondary Market Ticket Sales - US         | CPISHELTER             | Secondary market ticket sales reflect consumer spending patterns and discretionary income trends that correlate with broader inflation dynamics. Shelter CPI measures housing costs, and ticket sales activity can indicate consumer demand strength and pricing power in the leisure sector, which feeds into overall inflation pressures and consumer behavior patterns that influence housing-related spending. |
| CA004           | Secondary Market Ticket Sales - US         | CPIUSEDCAR             | Secondary market ticket sales reflect consumer spending patterns and discretionary demand, which influences overall consumer price pressures and inflation dynamics captured in CPI. However, the direct causal link is indirect—ticket sales affect entertainment/services inflation, not used car prices specifically.                                                                                           |
| CA004           | Secondary Market Ticket Sales - US         | RETAIL                 | Secondary market ticket sales are a component of retail spending. Changes in ticket resale volumes and prices reflect consumer discretionary spending patterns that feed into broader retail sales figures tracked by Census Bureau.                                                                                                                                                                               |
| CA004           | Secondary Market Ticket Sales - US         | KXEHSHARE              | Secondary market ticket sales activity reflects consumer discretionary spending and confidence, which correlates with housing market strength. However, the direct causal link is indirect—ticket sales measure entertainment demand rather than housing transactions themselves.                                                                                                                                  |
| CA004           | Secondary Market Ticket Sales - US         | KXEHSALES              | Secondary market ticket sales activity reflects consumer discretionary spending and economic confidence, which correlates with housing market demand and existing home sales volumes. Ticket sales trends can serve as a leading indicator of consumer financial health affecting real estate transactions.                                                                                                        |
| CA004           | Secondary Market Ticket Sales - US         | KXCPIAPPAREL           | Secondary market ticket sales reflect consumer spending patterns and demand for discretionary services. Changes in ticket resale activity can indicate shifts in consumer purchasing power and willingness to spend, which feed into broader consumption patterns measured by CPI apparel and overall consumer price indices.                                                                                      |
| CA0036          | Secondary Market Ticket Sales and Listings | KXUSPSPEND             | Secondary market ticket sales reflect discretionary consumer spending behavior. Ticket resales and listings capture real-time consumer demand for entertainment/events, which is a component of personal consumption expenditures measured in official spending data.                                                                                                                                              |
| CA0036          | Secondary Market Ticket Sales and Listings | KXCPISHELTER           | Secondary market ticket sales reflect consumer spending patterns and demand for entertainment/events, which correlates with discretionary spending behavior that influences overall consumer price pressures and shelter-related inflation through wealth effects and labor market dynamics affecting housing demand.                                                                                              |
| CA0036          | Secondary Market Ticket Sales and Listings | RETAIL                 | Secondary market ticket sales are a component of retail sales. Changes in ticket listing volumes and transaction values directly contribute to the retail sales aggregate measured by Census Bureau surveys.                                                                                                                                                                                                       |

## 채택된 매크로 이벤트 분포

| Macro event | 채택 페어 수 |
|---|---:|
| cpi | 278 |
| core cpi | 103 |
| gdp | 70 |
| retail sales | 59 |
| ism services | 42 |
| services pmi | 42 |
| ppi | 32 |
| core pce | 31 |
| pce | 31 |
| consumer sentiment | 30 |
| michigan consumer | 30 |
| consumer confidence | 27 |
| personal spending | 23 |
| existing home sales | 21 |
| durable goods | 13 |
| nonfarm payrolls | 13 |
| new home sales | 12 |
| adp employment | 9 |
| industrial production | 7 |
| jolts | 6 |

## Top 채택 검증쌍 (lead window 큰 순)

### #1 — `CA0077` × `KXGDPSHAREMANU`

- CA: **Commodity Metrics**
- Kalshi title: GDP share manufacturing
- Matched macro event(s): `gdp`
- Lead window: **89 days**
- Channel: Manufacturing output measured by Commodity Metrics (production volumes, input costs) is a direct component of real GDP and manufacturing value-added, which determines the manufacturing share of total GDP reported in official GDP releases.
- Caveat: _Commodity Metrics captures commodity-linked activity but may not fully represent all manufacturing output (services, intangibles); GDP share is calculated from comprehensive national accounts, so the relationship is directional but not one-to-one._

### #2 — `CA009` × `GDP`

- CA: **Digital Advertising**
- Kalshi title: US GDP growth
- Matched macro event(s): `gdp`
- Lead window: **89 days**
- Channel: Digital advertising spending is a component of business investment and consumer spending, both of which directly feed into GDP calculation. Changes in ad spending reflect business confidence and consumer activity, serving as a leading indicator of aggregate demand.
- Caveat: _Digital advertising is a small subset of total GDP; the connection is meaningful but indirect, with substantial noise from other GDP components (government spending, net exports, inventory changes)._

### #3 — `CA0055` × `KXNFPROD`

- CA: **SMB Workforce**
- Kalshi title: US nonfarm productivity exceeds X% YoY in any quarter reported during [year]
- Matched macro event(s): `nonfarm productivity`
- Lead window: **88 days**
- Channel: SMB workforce levels are a direct component of nonfarm employment and hours worked, which are the denominator in nonfarm productivity calculations (output per hour). Changes in SMB staffing patterns precede official BLS productivity releases and reflect underlying labor utilization trends.
- Caveat: _SMB workforce alone does not capture output (numerator); productivity also depends on production volumes, capital utilization, and sectoral composition. Weekly SMB data may not perfectly align with quarterly productivity measurement methodology._

### #4 — `CA0055` × `RECSS`

- CA: **SMB Workforce**
- Kalshi title: Quarter of negative GDP growth by 2022 Q2
- Matched macro event(s): `gdp`
- Lead window: **88 days**
- Channel: SMB workforce levels are a leading indicator of labor market health and aggregate demand; declining SMB employment typically precedes GDP contractions as businesses reduce headcount in response to weakening economic conditions.
- Caveat: _CA0055 measures SMB workforce only, which is a component of total employment; GDP is determined by multiple factors (consumption, investment, government spending, net exports) so SMB workforce alone is not deterministic of GDP growth direction._

### #5 — `CA0055` × `KXRECSS`

- CA: **SMB Workforce**
- Kalshi title: Quarter of negative GDP growth by 2022 Q2
- Matched macro event(s): `gdp`
- Lead window: **88 days**
- Channel: SMB workforce levels are a leading indicator of labor market health and aggregate demand; declining SMB employment typically precedes GDP contractions as businesses reduce headcount in response to weakening economic conditions.
- Caveat: _Weekly SMB workforce data is a partial proxy for total employment; GDP is determined by multiple components (consumption, investment, government spending, net exports) of which labor is only one input. The 2-day publication lag provides minimal lead time relative to quarterly GDP reporting._

### #6 — `CA0056` × `GDP`

- CA: **Credit Card – US Complete Panel**
- Kalshi title: US GDP growth
- Matched macro event(s): `gdp`
- Lead window: **87 days**
- Channel: Credit card spending is a major component of personal consumption expenditures (PCE), which accounts for ~70% of US GDP. Daily credit card transaction data with 3-day lag provides real-time signals of consumer spending trends that directly feed into quarterly GDP calculations.
- Caveat: _Credit card spending captures only a subset of total consumption (excludes cash, checks, digital wallets); GDP is quarterly while CA data is daily, requiring temporal aggregation; publication lag of 3 days is shorter than GDP release cycle but still lags the actual economic activity being measured._

### #7 — `CA0056` × `RECSS`

- CA: **Credit Card – US Complete Panel**
- Kalshi title: Quarter of negative GDP growth by 2022 Q2
- Matched macro event(s): `gdp`
- Lead window: **87 days**
- Channel: Credit card spending is a major component of personal consumption expenditures (PCE), which accounts for ~70% of GDP. Daily credit card transaction data with 3-day lag provides real-time signals of consumer spending trends that directly feed into quarterly GDP calculations.
- Caveat: _Credit card spending is a subset of total consumption (excludes cash, checks, digital wallets); GDP also includes investment, government spending, and net exports. The 3-day lag is shorter than GDP's typical release cycle, but spending trends observed in the quarter are what matters for GDP settlement._

### #8 — `CA0056` × `GDPUSMIN`

- CA: **Credit Card – US Complete Panel**
- Kalshi title: Negative US GDP growth
- Matched macro event(s): `gdp`
- Lead window: **87 days**
- Channel: Credit card spending is a major component of personal consumption expenditures (PCE), which accounts for ~70% of US GDP. Daily credit card transaction data with 3-day lag provides real-time signals of consumer spending trends that directly feed into quarterly GDP calculations.
- Caveat: _Credit card spending is a subset of total consumption (excludes cash, checks, digital wallets); GDP is quarterly while CA data is daily, requiring aggregation; 3-day lag means data reflects very recent activity but GDP revisions occur months later._

### #9 — `CA0056` × `KXRECSS`

- CA: **Credit Card – US Complete Panel**
- Kalshi title: Quarter of negative GDP growth by 2022 Q2
- Matched macro event(s): `gdp`
- Lead window: **87 days**
- Channel: Credit card spending is a major component of personal consumption expenditures (PCE), which accounts for ~70% of US GDP. Daily credit card transaction data with 3-day lag provides real-time signals of consumer spending trends that directly feed into quarterly GDP calculations.
- Caveat: _Credit card spending is a subset of total consumption (excludes cash, checks, digital wallets); GDP also includes investment, government spending, and net exports. The 3-day lag is insufficient to predict quarterly GDP with certainty, though it provides directional signals._

### #10 — `CA0056` × `KXGDPYEAR`

- CA: **Credit Card – US Complete Panel**
- Kalshi title: Annual GDP
- Matched macro event(s): `gdp`
- Lead window: **87 days**
- Channel: Credit card spending is a major component of personal consumption expenditures (PCE), which accounts for ~70% of nominal GDP. Daily credit card transaction data with 3-day lag provides real-time signals of consumer spending trends that feed into quarterly GDP calculations.
- Caveat: _Credit card spending captures only a subset of total consumption (excludes cash, checks, services); GDP is quarterly while CA data is daily, requiring temporal aggregation; final GDP revisions occur months after initial release, limiting predictive precision._

### #11 — `CA0056` × `KXGDPUSMIN`

- CA: **Credit Card – US Complete Panel**
- Kalshi title: Negative US GDP growth
- Matched macro event(s): `gdp`
- Lead window: **87 days**
- Channel: Credit card spending is a major component of personal consumption expenditures (PCE), which accounts for ~70% of US GDP. Daily credit card transaction data with 3-day lag provides real-time signals of consumer spending trends that directly feed into quarterly GDP calculations.
- Caveat: _Credit card spending is a subset of total consumption (excludes cash, checks, digital wallets); GDP settlement occurs quarterly while CA data is daily, requiring aggregation; lag structure means most recent spending may not be captured before GDP release._

### #12 — `CA0047` × `RECSS`

- CA: **POS – Supermarket**
- Kalshi title: Quarter of negative GDP growth by 2022 Q2
- Matched macro event(s): `gdp`
- Lead window: **86 days**
- Channel: Supermarket POS sales are a real-time consumption indicator that feeds into PCE (personal consumption expenditures), which comprises ~70% of GDP. Weekly supermarket sales data with 4-day lag can signal demand weakness that precedes or correlates with quarterly GDP growth rates.
- Caveat: _Supermarket sales alone are insufficient to determine GDP sign; GDP includes investment, government spending, and net exports. The 4-day lag is useful for nowcasting but GDP is revised multiple times after initial release._

### #13 — `CA0047` × `GDP`

- CA: **POS – Supermarket**
- Kalshi title: US GDP growth
- Matched macro event(s): `gdp`
- Lead window: **86 days**
- Channel: Supermarket POS sales are a real-time proxy for consumer spending on food and household goods, which comprises a material portion of personal consumption expenditures (PCE). PCE is a major component of GDP calculation, so supermarket sales trends should precede and inform GDP estimates.
- Caveat: _Supermarket sales capture only food/grocery retail, not total consumption; GDP also includes services, investment, and net exports. The 4-day lag means data arrives after the week closes, limiting predictive power for same-quarter GDP revisions._

### #14 — `CA0047` × `KXGDPUSMIN`

- CA: **POS – Supermarket**
- Kalshi title: Negative US GDP growth
- Matched macro event(s): `gdp`
- Lead window: **86 days**
- Channel: Supermarket POS sales are a real-time consumption indicator that feeds into PCE (personal consumption expenditures), which comprises ~70% of US GDP. Weekly supermarket sales trends can signal consumer demand weakness that precedes or correlates with quarterly GDP growth rates.
- Caveat: _GDP is quarterly and published with significant lag; weekly POS data is too high-frequency to directly predict GDP direction with certainty. Supermarket sales are only one consumption component and do not capture services, investment, or net exports._

### #15 — `CA0047` × `GDPUSMIN`

- CA: **POS – Supermarket**
- Kalshi title: Negative US GDP growth
- Matched macro event(s): `gdp`
- Lead window: **86 days**
- Channel: Supermarket POS sales are a real-time consumption indicator that feeds into PCE (personal consumption expenditures), which comprises ~70% of US GDP. Weekly supermarket sales trends can signal consumer demand weakness that precedes or correlates with negative GDP growth.
- Caveat: _Supermarket sales alone are insufficient to determine GDP direction; GDP also depends on investment, government spending, and net exports. The 4-day lag means data arrives after the week closes, limiting predictive power for near-term GDP forecasts._

### #16 — `CA0060` × `KXRECSS`

- CA: **Foot Traffic**
- Kalshi title: Quarter of negative GDP growth by 2022 Q2
- Matched macro event(s): `gdp`
- Lead window: **85 days**
- Channel: Foot traffic is a real-time proxy for consumer spending and economic activity; sustained declines in foot traffic precede weakness in consumption data that feeds into GDP calculations, particularly the personal consumption expenditures component.
- Caveat: _Foot traffic alone is insufficient to determine GDP direction—investment, net exports, and government spending also matter significantly. The 5-day publication lag limits predictive advantage for quarterly GDP releases._

### #17 — `CA0060` × `KXFRGDPYOYP`

- CA: **Foot Traffic**
- Kalshi title: France GDP Growth Rate YoY Prel (quarterly)
- Matched macro event(s): `gdp`
- Lead window: **85 days**
- Channel: Foot traffic is a real-time proxy for consumer spending and economic activity, which directly feeds into GDP consumption components (C). Daily foot traffic aggregated over quarters can signal demand trends that precede or correlate with official GDP growth rates.
- Caveat: _Foot traffic alone captures only retail/service consumption; GDP includes investment, government spending, and net exports. The 5-day publication lag is short but quarterly GDP settlement occurs weeks after quarter-end, reducing predictive value. France-specific foot traffic data quality and coverage across regions/sectors will materially affect signal strength._

### #18 — `CA0060` × `KXGDPUSMIN`

- CA: **Foot Traffic**
- Kalshi title: Negative US GDP growth
- Matched macro event(s): `gdp`
- Lead window: **85 days**
- Channel: Foot traffic is a real-time proxy for consumer activity and business operations, which directly feed into GDP components (consumption, investment). Declining foot traffic typically precedes or coincides with reduced economic output measured in official GDP releases.
- Caveat: _Foot traffic captures only a subset of GDP (primarily services consumption); it excludes investment, government spending, and net exports. The 5-day publication lag means CA0060 data arrives after some economic activity has already occurred, limiting its predictive power for GDP revisions._

### #19 — `CA0060` × `RECSS`

- CA: **Foot Traffic**
- Kalshi title: Quarter of negative GDP growth by 2022 Q2
- Matched macro event(s): `gdp`
- Lead window: **85 days**
- Channel: Foot traffic is a real-time proxy for consumer spending and economic activity. Sustained declines in foot traffic precede weakness in retail sales and personal consumption expenditures, which are major components of GDP.
- Caveat: _Foot traffic alone is insufficient to determine GDP direction; it captures only consumer-facing activity and misses investment, government spending, and net exports. The 5-day publication lag limits predictive advantage for quarterly GDP releases._

### #20 — `CA0060` × `GDP`

- CA: **Foot Traffic**
- Kalshi title: US GDP growth
- Matched macro event(s): `gdp`
- Lead window: **85 days**
- Channel: Foot traffic is a real-time proxy for consumer spending and economic activity. Changes in foot traffic precede or correlate with retail sales and services consumption, which are major components of GDP expenditure.
- Caveat: _Foot traffic captures only a subset of GDP (primarily services and retail); it excludes investment, government spending, and net exports. The 5-day publication lag may limit predictive value for quarterly GDP releases._

### #21 — `CA0060` × `GDPUSMIN`

- CA: **Foot Traffic**
- Kalshi title: Negative US GDP growth
- Matched macro event(s): `gdp`
- Lead window: **85 days**
- Channel: Foot traffic is a real-time proxy for consumer spending and economic activity. Reduced foot traffic precedes lower retail sales and services consumption, which are major components of GDP; elevated foot traffic signals demand strength that feeds into GDP growth.
- Caveat: _Foot traffic captures only a subset of GDP (primarily services and retail consumption); it does not directly measure investment, government spending, or net exports. The 5-day publication lag means CA0060 data arrives after some economic activity has already occurred, limiting its predictive power for GDP revisions._

### #22 — `CA0034` × `KXGDP`

- CA: **POS - Instore and Online**
- Kalshi title: US GDP growth
- Matched macro event(s): `gdp`
- Lead window: **83 days**
- Channel: Point-of-sale spending (instore and online) is a direct component of personal consumption expenditures (PCE), which accounts for ~70% of US GDP. Weekly POS data provides a real-time proxy for consumer demand that feeds into quarterly GDP calculations.
- Caveat: _GDP is quarterly and includes investment, government spending, and net exports; POS captures only retail consumption. Weekly POS data has a 7-day lag, while GDP revisions occur months after the quarter ends, limiting real-time predictive precision._

### #23 — `CA0034` × `GDPUSMAX`

- CA: **POS - Instore and Online**
- Kalshi title: US GDP peak 
- Matched macro event(s): `gdp`
- Lead window: **83 days**
- Channel: POS sales data (both instore and online) directly measures consumer spending, which is the largest component of GDP (personal consumption expenditures). Weekly sales trends with 7-day lag provide leading/concurrent signals of consumption patterns that feed into quarterly GDP calculations.
- Caveat: _GDP is quarterly while POS data is weekly; settlement on 'GDP peak' is an event-based outcome rather than a point estimate, requiring interpretation of whether consumption trends support peak identification. POS captures only retail sales, not all consumption (services, healthcare, etc.)._

### #24 — `CA0031` × `GDPUSMIN`

- CA: **Credit Card - US and CAN General Panel**
- Kalshi title: Negative US GDP growth
- Matched macro event(s): `gdp`
- Lead window: **83 days**
- Channel: Credit card spending is a major component of personal consumption expenditures (PCE), which accounts for ~70% of US GDP. Declining credit card transaction volumes can signal weakening consumer demand and precede negative GDP growth.
- Caveat: _CA0031 covers only credit card transactions; GDP includes investment, government spending, and net exports. The 7-day publication lag may limit real-time predictive power for quarterly GDP releases._

### #25 — `CA0031` × `KXRECSS`

- CA: **Credit Card - US and CAN General Panel**
- Kalshi title: Quarter of negative GDP growth by 2022 Q2
- Matched macro event(s): `gdp`
- Lead window: **83 days**
- Channel: Credit card spending is a major component of personal consumption expenditures (PCE), which accounts for ~70% of US GDP. Declining credit card transaction volumes signal reduced consumer spending, a leading indicator of negative GDP growth.
- Caveat: _CA0031 covers US and Canada while KXRECSS settles on US GDP only; publication lag of 7 days means data arrives after spending occurs but before GDP release; credit card spending is a subset of total consumption and does not capture all GDP components (investment, government, net exports)._

### #26 — `CA0031` × `KXGDPUSMIN`

- CA: **Credit Card - US and CAN General Panel**
- Kalshi title: Negative US GDP growth
- Matched macro event(s): `gdp`
- Lead window: **83 days**
- Channel: Credit card spending is a major component of personal consumption expenditures (PCE), which accounts for ~70% of US GDP. Changes in aggregate credit card transaction volumes signal shifts in consumer demand that directly feed into quarterly GDP calculations.
- Caveat: _CA0031 is historic/lagged data with 7-day publication lag; real-time predictive power for GDP direction depends on timeliness relative to BEA's advance/preliminary/final GDP release schedule. Panel data may not capture full economy-wide spending if sample composition or coverage differs from BEA's PCE universe._

### #27 — `CA0031` × `RECSS`

- CA: **Credit Card - US and CAN General Panel**
- Kalshi title: Quarter of negative GDP growth by 2022 Q2
- Matched macro event(s): `gdp`
- Lead window: **83 days**
- Channel: Credit card spending is a major component of personal consumption expenditures (PCE), which accounts for ~70% of US GDP. Declining credit card transaction volumes signal reduced consumer spending, a leading indicator of negative GDP growth.
- Caveat: _CA0031 covers US and Canada while RECSS settles on US GDP only; publication lag of 7 days means data arrives after spending occurs but before GDP release; credit card spending is a subset of total consumption and does not capture all GDP components (investment, government, net exports)._

### #28 — `CA0025` × `KXGDP`

- CA: **Freight Volume - North America**
- Kalshi title: US GDP growth
- Matched macro event(s): `gdp`
- Lead window: **83 days**
- Channel: Freight volume is a real-time proxy for goods movement and economic activity; changes in North American freight precede or contemporaneously reflect changes in goods production and consumption that directly feed into GDP accounting.
- Caveat: _CA0025 is North American (includes Canada/Mexico) while Kalshi settles on US GDP only; 7-day publication lag means CA data arrives after some economic activity has already occurred; freight is a component of economic activity but not a direct input to official GDP calculations._

### #29 — `CA0034` × `GDP`

- CA: **POS - Instore and Online**
- Kalshi title: US GDP growth
- Matched macro event(s): `gdp`
- Lead window: **83 days**
- Channel: POS sales data (instore and online) directly measures consumer spending, which is the largest component of GDP (personal consumption expenditures ~70%). Weekly sales trends with 7-day lag provide leading/coincident signals for quarterly GDP growth rates.
- Caveat: _POS data captures retail only, missing services, investment, and government spending; GDP settlement is quarterly while POS is weekly, requiring temporal aggregation; final GDP revisions occur months later, creating potential settlement timing mismatches._

### #30 — `CA0025` × `GDPUSMAX`

- CA: **Freight Volume - North America**
- Kalshi title: US GDP peak 
- Matched macro event(s): `gdp`
- Lead window: **83 days**
- Channel: Freight volume is a real-time proxy for economic activity and goods movement. Changes in North American freight volume precede or coincide with GDP revisions, as transportation of goods is a direct component of production and consumption measured in GDP.
- Caveat: _Freight volume is a cyclical indicator but not a direct GDP component; GDP includes services (majority of US economy) which freight volume does not capture. The 7-day publication lag means CA0025 may not lead official GDP releases by sufficient margin for predictive utility._


---

## Appendix

- 매크로 이벤트 master: `outputs/auto/macro_event_master_list.csv`
- 매칭 룰: `docs/macro_matching_rules.md`
- Stage B full: `outputs/auto/timing_full.csv` / `timing_pass.csv`
- Stage C full: `outputs/auto/mechanism_verified.csv`
- 최종 채택 (Stage C connected=true): `outputs/auto/verification_pairs_macro.csv`
- Prompts: `scripts/auto/s_c_mechanism_verify.py` (SYSTEM_PROMPT)

### 재현 명령

```bash
python3 scripts/auto/s_a1_macro_list.py
python3 scripts/auto/s_a2_kalshi_macro_match.py
python3 scripts/auto/s_b_timing.py
python3 scripts/auto/s_c_mechanism_verify.py --model claude-haiku-4-5 --workers 12
python3 scripts/auto/s_report.py
```