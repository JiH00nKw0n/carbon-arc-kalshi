> **상태 (2026-05-18)**: 이 파일은 repo 시작 시점 (2026-05-08) 의 CarbonArc 플랫폼 가치 메모. 현재 진행 결과는 `README.md` 와 `docs/analysis_per_dataset.md` 를 참조. 이 메모의 데이터 카테고리 분류 + ontology / framework 모델 설명은 여전히 유효함.

---

## 12. 데이터 가치 분석 — 무엇을 어디에 쓸까

여기는 docstring이 아니라 **편향된 의견**. Carbon Arc × Polymarket/Kalshi 맥락에서 (1) 무슨 데이터가 있고 (2) 각 자산이 본질적으로 무엇이며 (3) 어떤 게 *값어치 있는지* 정리.

### 12.1 Carbon Arc이 실제로 파는 것

3가지 레이어를 같이 사야 가치가 산다:

1. **Ontology 자체** — 326,448개 entity × 4축(`entity / domain / representation / id`)으로 *이미 해소된* 매핑. 다른 alt-data 벤더에서 "이 SKU/브랜드/티커가 같은 회사인가?" 확인하느라 며칠 까먹는 일이 사라짐. 회사·브랜드·서비스·소매점 banner·웹사이트·차종·자회사·티커가 한 그래프.
2. **Insight 추상화 (896개)** — "Same-Store Sales", "Card Spend", "Foot Traffic" 같이 *벤더-중립적인 metric 계약*. 업스트림 source가 바뀌어도 동일 컬럼명. 이게 Bloomberg/Refinitiv가 못하는 거.
3. **Framework 단위 과금** — `(entities, insight, filters)` 별 가격. 즉 "MSFT의 미국 주별 카드 소비량 2024-01~2026-04 월별 mean"만 사면 됨. 데이터셋 통째로 사는 LSEG/FactSet 모델보다 *연구자 친화적*. $50 promo로도 의미 있는 실험 가능.

### 12.2 데이터셋을 본질로 묶기 (63개 비-webcontent)

| 묶음 | 구성 | 본질 |
|---|---|---|
| **카드/POS/POP** (10개) | CA0028/0056/0042/0058/0031, CA0029/0048/0078/0047/0034, CA0044 | 소비자가 *얼마를 어디에* 쓰는지. 미국·유럽·신흥국 패널이 다 있음 |
| **헬스케어** (2개) | CA0049 의약/처방, CA0041 메디케어 | 환자 단위 처방·청구 |
| **모바일 / 웹 / 광고** (4개) | CA0054 앱, CA0013 앱카테고리, CA0030 클릭스트림, CA009 디지털광고 | 디지털 어텐션 (DAU, 페이지뷰, 광고 노출) |
| **노동시장** (3개 + WC 130+) | CA0053 잡 무브먼트, CA0043A 잡 오프닝, CA0055 SMB 워크포스 | 채용 / 이직 / 임금 |
| **펀더멘털 / 가격** (5개) | CA0065S 주가, CA0065C/CA0038 actuals, CA0032 filings, CA0051 FFIEC | 회사 재무 + 주가 (이건 FactSet/Compustat에도 있음) |
| **무역 / 화물** (5개) | CA0022 미국 수출입, CA0040 7개국 무역, CA0025 N/A 화물, CA0025B 트럭, CA0080 해운 | 수송 + 무역 명세 |
| **매크로 / 인구** (4개) | CA0015 FRED, CA0019 Census, CA0026 헬스 prevalence, CA0077 원자재 | 공공 데이터를 ontology로 정렬한 버전 |
| **부동산 / 모빌리티 / 매장** (5개) | CA002 건축허가, CA0060 풋트래픽, CA001 POI, CA005 차량등록, CA0023 연료 | 물리적 활동 |
| **엔터테인먼트** (10개) | CA007/CA0046/CA003 음악, CA0011/CA0016 박스오피스, CA0010 OTT, CA008 스포츠, CA004/CA0036/CA0050 티켓 | "뭐가 인기 있나" |
| **기타** (3개) | CA0035 뉴스 (티커별 이벤트 빈도), CA0052 리뷰, CA0062 코호트, CA0037/CA0059 날씨, CA0020 광산 | 보조 |

**Web Content 133개**는 본질적으로 다 같은 상품: *회사별 잡포스팅 / 매장위치 / 제품카탈로그 스크래퍼*. 가치 = high-frequency, 아래 세 type 중 하나로 분류:
- **Job Postings** (~80개) — Microsoft, Stripe, Workday, Oracle, Neurocrine, Uber 등. 컬럼 예: `title`, `team`, `primaryLocation`, `primaryLocationMinPay`, `primaryLocationMaxPay`, `date`. → 채용 의도, 임금 트렌드, 신규 라인 시그널.
- **Store / Facility Locations** (~40개) — Verizon 서비스 커버리지, EXP 부동산 에이전트, Heidelberg 공장 등. 점포 오픈/클로징.
- **Product Catalog** (~15개) — Xero 마켓플레이스, Starlink 키트, Duolingo 컨텐츠. SKU·가격 라이프사이클.

### 12.3 가치 등급 (Polymarket/Kalshi 리서치 기준)

#### S급: 즉시 알파 가능, 다른 곳에서 못 사는 것

| 데이터셋 | 왜 S급인가 |
|---|---|
| **CA0028/0056 Credit Card US** | 일별·zip·brand·payment_type 단위 카드소비. earnings nowcast의 정석. CA0058(Health spend)은 약가/병원지출 분리. EU(0042) + EM POP(0044)도 같이 있음 — 글로벌 커버리지가 2nd Measure / Earnest를 능가하는 측면. **Polymarket 수익(예: "Q3 NFLX 가입자")시장에 직접 인풋.** |
| **CA0049 Medical & Pharmacy Claims** | brand_id로 약품과 회사를 join — Lilly, Novo, Pfizer 종목 nowcast. **"FDA approval by date" / "drug X sales > Y" 시장에 직격.** |
| **CA0030 Clickstream** | 27M opt-in 패널. brand × country × overlap. 경쟁사 cross-shopper 분석 가능 (예: YouTube ↔ TikTok). **미디어/광고 종목 prediction에 우위.** |
| **CA0040 Trade Claims (HS code-level, 7개국)** | shipper·consignee·HS코드 단위. 2022+. **"Tesla 중국 출하 X대 초과" / "특정 supply chain 충격" 시장.** Vortexa·Kpler·ImportGenius가 노리는 자리지만 ontology join이 큼. |
| **CA0053 Job Movements + WC Job Postings (130개)** | 누가 어디로 옮겼는가 + 회사가 무엇을 채용 중인가. AI/반도체 인재 배치 추적. **Polymarket에 "Anthropic > $X funding" / "OpenAI restructuring" 같은 시장에 사이드 시그널.** |
| **CA0060 Foot Traffic** | 일별·zip·brand 단위 traffic + store_count. SafeGraph/Placer 영역인데 ontology가 강함. **"Q3 같은 매장 매출" 시장.** |
| **CA009 Digital Advertising** | DMA·ticker별 ad_spend / ad_impression. 마케팅 사이클 nowcast. **"NFLX, META 광고 매출 X 초과" 시장.** |

#### A급: 특정 그림에 결정적

| 데이터셋 | 왜 |
|---|---|
| **CA0054 App Intelligence + CA0013 Mobile App** | 850+ 앱 일별 DAU/downloads. "DASH가 UBER 따라잡나" 같은 설문에 즉답. Sensor Tower / Apptopia보다 Carbon Arc가 우위는 *티커 매핑* + Ontology join. |
| **CA0035 Financial News & Data (티커별 이벤트)** | 27 토픽: Analyst 코멘트, M&A, 가이던스, 거래 아이디어 등. 타임스탬프와 티커가 묶임 → 이벤트 스터디용 베이스라인. **"Will X be acquired by Y" 시장.** |
| **CA0052 Brand Reviews** | 1.7M+ 리뷰, 별점·리뷰어 회사. B2B 소프트웨어 리뷰 플랫폼 (Atlassian × Rogers 같은 행) — *고객 관계*까지 잡힘. |
| **CA0011 Concert Box Office + CA0050 Rising Artists Tickets + CA004/CA0036 2차시장** | Ticketmaster 내부 데이터에 가까움. Live Nation / MSGE earnings + "Taylor Swift Eras 누적 매출 > X" 시장. |
| **CA0016 Movie Box Office** | 1972~. 신작 시장(예: "Avatar 3가 $X 돌파") + 업종 nowcast. |
| **CA0043C Technology Detections** | 회사가 어떤 SaaS를 깔았는지. *Snowflake/Databricks/HubSpot* 신규 도입 추적. |
| **CA0043A Job Openings + CA0043D Product Launches** | C-suite 임원의 "we're hiring 1000 engineers" 발언이 사실인가? **AI 기업 가치평가 시장에 직접.** |
| **CA0023 Locations - US Transportation (alternative_fuel_score)** | EV 인프라 지수. **"State X EV 충전소 > Y개" 시장.** |
| **CA0044 POP - Emerging Markets** | 신흥국 카드패널은 희귀. 인도/멕시코 매크로 nowcast. |

#### B급: 있으면 좋고, 단독으로 alpha는 약함

- **CA0015 FRED**, **CA0019 Census**, **CA0026 Health Measures** — 공공 데이터를 ontology로 정렬한 정도. 단독 가치는 낮지만 *다른 데이터와 join할 때* 가치 폭발. Fed prediction market 직결.
- **CA0065S 주가, CA0065C/CA0038 펀더멘털, CA0051 FFIEC** — Bloomberg/FactSet 영역. Carbon Arc에서 사기엔 비효율. 단, *이 안에서 join*하려면 필요.
- **CA0032 Financial Filing Forms** — SEC 파일링은 EDGAR 무료. 굳이 쓸 이유 = ontology + 사전 파싱.
- **CA003 / CA0046 / CA007 Music** — Spotify Charts API + Last.fm 같은 무료 자료가 더 신선.
- **CA0037 / CA0059 Weather** — NOAA 직접 더 좋음. ontology join이 메리트.
- **CA005 Vehicle Registration**, **CA0020 Mine Hours**, **CA002 Housing Permits** — 산업별 niche, 특정 thesis가 있을 때만.

#### C급: 우리 콜랩에선 잘 안쓸 듯

- **CA0062 Cohort Attributes** (Enterprise tier만), **CA0057 Menu Data**, **CA0055 SMB Workforce** (단독으론 너무 microscopic) — 컨슈머 인사이트 보고서엔 좋은데 prediction market엔 노이즈.

### 12.4 Kalshi/Polymarket 마켓 카테고리별 매핑

리서치 페이퍼 앵글 잡을 때 시작점:

| 시장 카테고리 | 필요한 Carbon Arc 데이터 | 페이퍼 앵글 |
|---|---|---|
| **Fed/CPI/매크로** | CA0015 + CA0040 + CA0053 + CA0049 | "Alt-data가 FOMC 결정을 예측하는가" — Kalshi Fed rate 마켓 backtesting |
| **선거/지정학** | CA0019 + CA0026 + CA0035 + CA0030 | County 단위 인구 + 헬스 + 뉴스 flow + 클릭스트림으로 swing 예측. 카본아크 ontology가 county·zip·DMA를 다 갖춤 |
| **기업 어닝** | CA0028/0056 + CA009 + CA0030 + CA0049 + CA0054 + CA0043A | Polymarket "Q3 [TICKER] EPS beat" 시장 — 회사별 alt-data feature engineering |
| **신제품/M&A** | CA0043D + CA0043B + CA0035 + CA0084 (webcontent) | 잡포스팅 + 제품 출시 + 뉴스를 묶어 *언제 일어날지*가 아니라 *얼마나 빠르게 일어나는지* |
| **스포츠/엔터** | CA0011 + CA0016 + CA004/CA0036 + CA008 | 박스오피스 prediction market과 secondary ticket spread |
| **상품/원자재** | CA0077 + CA0040 + CA0080 + CA0015 (FRED commodities) | "WTI > $X by date" — 해운 + 원자재 가격 + 무역 세관신고 결합 |
| **AI/테크 제품** | CA0084 (130 잡포스팅 webcontent) + CA0043C + CA0054 | "Claude 5 출시 < date" — Anthropic 잡포스팅 변화 + 데이터센터 증설 + 앱 다운로드 |

### 12.5 $50 promo로 뭘 살까 — 실용 추천

- **무료** (`get_data_sample`로 100행 보기): 모든 56개 데이터셋의 컬럼·예시 행 → 이미 §4.6에 정리됨.
- **첫 구매 후보** (가격 미확인, 보통 framework 1개당 $1~수십 단위 추정):
  1. CA0028 (Credit Card US Detailed) — 5~10개 ticker × 2년 monthly = 입문용 PoC
  2. CA0049 (Medical Claims) — Lilly + Novo + Pfizer × drug × month
  3. CA0040 (Trade Claims) — Tesla + AAPL × HS코드 7204 (반도체) × week
  4. CA0030 (Clickstream) — META vs ByteDance overlap × month
- **함정**:
  - "Historic" 데이터셋 (CA0028/0044/CA006/CA0041 등 7개)은 frozen — 라이브 prediction market엔 못 씀, 백테스트 전용.
  - Web Content는 `get_data_sample`이 404 → framework로만 접근. 잡포스팅 130개는 framework 한 번에 entity wildcard로 묶어 사는 게 효율적.
  - Catalog (`/v2/catalog`) 잠금 → tier 2/3 자산은 보이지 않음. 콜랩 시 "tier 2도 풀어달라" 협상 포인트.

### 12.6 핵심 thesis (콜랩 키노트 한 줄)

> "Bloomberg/FactSet 위에 Polymarket·Kalshi가 alpha를 줄 거라고 믿는다면, **두 사이의 lag을 메우는 alt-data**는 거의 다 Carbon Arc의 ontology로 정렬되어 있고, *시장 단위로 시그널을 분리·결합할 수 있는 유일한 인터페이스가 framework abstraction이다.*"

CA0028 + CA0049 + CA0030 + CA0040 + CA0084-job 5개 묶음만으로도 페이퍼 한 편 + 셀사이드 데모 한 회는 만든다.
