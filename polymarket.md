# Polymarket — 데이터 카탈로그 & 수집 가이드

Polymarket에서 **무엇을** 얻을 수 있고 **어떻게** 수집하는지. 데이터 수집 관점 정리.
공식 문서 https://docs.polymarket.com/api-reference/introduction 기반, 필드는 라이브 응답으로 확인 (2026-06-03).
코드: `scripts/polymarket/` (`client.py` = read 클라이언트, `smoke_test.py` = 검증).

> 핵심: **읽기(수집)는 키·지갑·인증 전부 불필요.** 주문 실행만 인증 필요(이 문서 범위 밖, 맨 아래 한 줄).

---

## 0. 사용법 빠른 시작 (API + SDK)

### 세 개의 public 호스트
| Host | Base URL | 주는 것 |
| --- | --- | --- |
| **Gamma** | `gamma-api.polymarket.com` | 마켓·이벤트·태그·검색 (메타데이터) |
| **CLOB** | `clob.polymarket.com` | 가격·오더북·**가격 시계열** |
| **Data** | `data-api.polymarket.com` | 포지션·거래·홀더·OI·리더보드 (온체인) |

### 방법 A — 이 프로젝트의 read 클라이언트 (수집 권장)
순수 `requests` 래퍼. 인증 0, 의존성 0. 수집엔 이게 제일 간단.
```python
import sys, json; sys.path.insert(0, "scripts")
from polymarket import PolymarketClient

c = PolymarketClient()

mkts   = c.get_markets(limit=20, active=True, closed=False, order="volumeNum", ascending=False)
m      = mkts[0]
cond   = m["conditionId"]                 # Data API 키
tokens = json.loads(m["clobTokenIds"])    # CLOB 키 (JSON 문자열 → loads)
yes    = tokens[0]

c.get_prices_history(yes, interval="1w", fidelity=60)   # 가격(=확률) 시계열
c.get_trades(market=cond, limit=100)                    # 체결 내역
c.get_holders(cond)                                     # top 홀더
```
검증: `python scripts/polymarket/smoke_test.py` → read 엔드포인트 6종 PASS.

### 방법 B — 공식 SDK `py-clob-client-v2` (CLOB 전용)
설치됨(`requirements.txt` 고정). CLOB의 read 메서드는 **무인증**으로 동작:
```python
from py_clob_client_v2 import ClobClient
clob = ClobClient(host="https://clob.polymarket.com", chain_id=137)   # 키 없이 read OK

clob.get_midpoint(yes)            # {'mid': '0.0035'}
clob.get_price(yes, side)         # best bid/ask
clob.get_order_book(yes)          # 오더북
clob.get_markets()                # CLOB 마켓 목록(페이지네이션)

# 가격 시계열은 타입드 파라미터 객체를 받음:
from py_clob_client_v2 import PricesHistoryParams, PriceHistoryInterval
clob.get_prices_history(PricesHistoryParams(market=yes, interval=PriceHistoryInterval.ONE_WEEK, fidelity=60))
```
> SDK는 CLOB만 커버. **Gamma/Data(마켓 메타·포지션·거래·홀더)는 SDK에 없음** → 방법 A 사용.
> 그래서 이 프로젝트 수집은 방법 A(requests)를 기본으로 함. SDK는 주문 실행 때 주로 필요.

---

## 1. 얻을 수 있는 데이터 — 카탈로그

### 1.1 Gamma — 마켓 & 이벤트 메타데이터

**`/markets`** (마켓 = 단일 질문). 이진 마켓이면 outcome 2개(Yes/No). 라이브 확인 필드:

| 그룹 | 필드 |
| --- | --- |
| 식별 | `id`, `slug`, `conditionId`, `clobTokenIds`(JSON), `questionID` |
| 내용 | `question`, `description`, `outcomes`(JSON), `resolutionSource` |
| 가격 스냅샷 | `outcomePrices`(JSON, =확률), `bestBid`, `bestAsk`, `lastTradePrice`, `spread`, `oneDayPriceChange`, `oneWeekPriceChange` |
| 규모 | `volumeNum`, `volume24hr`, `volume1wk/1mo/1yr`(+`…Clob` 버전), `liquidityNum`, `liquidityClob` |
| 기간 | `startDate`, `endDate`, `endDateIso`, `gameStartTime`, `createdAt`, `updatedAt` |
| 상태 | `active`, `closed`, `archived`, `restricted`, `acceptingOrders`, `enableOrderBook` |
| 해결(오라클) | `umaResolutionStatus(es)`, `resolvedBy`, `umaBond`, `umaReward` |
| 구조 | `negRisk`, `negRiskOther`, `events`(소속 이벤트) |
| 수수료/보상 | `feeType`, `makerBaseFee`, `takerBaseFee`, `rewardsMinSize`, `rewardsMaxSpread`, `orderPriceMinTickSize` |

조회 파라미터: `limit`, `offset`, `active`, `closed`, `archived`, `order`(예 `volumeNum`), `ascending`, `tag_id`, `condition_ids`, `clob_token_ids`, `slug`.
단건/부가: `/markets/{id}`, `/markets/slug/{slug}`, `/markets/{id}/tags`, `/markets/{id}/description`.

**`/events`** (이벤트 = 관련 마켓 묶음). 필드: `id`, `slug`, `ticker`, `title`, `description`, `markets[]`, `tags[]`, `volume*`, `liquidity`, `openInterest`, `commentCount`, `enableNegRisk`, `startDate`/`endDate`, `active`/`closed`. (변형: `/events/pagination`, `/events/keyset`, `/events/results`(스포츠), `/events/slug/{slug}`)

**탐색용**: `/series`(반복 이벤트 그룹), `/tags`·`/tags/{id}/related-tags`(주제 분류 그래프), `/public-search?q=`(마켓·이벤트·프로필 통합검색), `/comments`(소셜), `/sports`·`/teams`.

### 1.2 CLOB — 가격 & 오더북 (전부 0~1 확률값, **token_id 기준**)

| 엔드포인트 | 내용 |
| --- | --- |
| `/prices-history` ★ | **가격 시계열** `{"history":[{"t":unix,"p":0..1}]}`. `interval`(1m/1h/6h/1d/1w/max) 또는 `startTs`/`endTs`, `fidelity`(분) |
| `/batch-prices-history` | 여러 토큰 한 번에 (POST) |
| `/book`, `/books` | 전체 오더북 (`bids[]`,`asks[]` = price·size) |
| `/price`, `/midpoint`, `/spread` | best 가격 / 중간값 / 스프레드 |
| `/last-trade-price` | 마지막 체결가 |
| `/tick-size`, `/neg-risk`, `/fee-rate` | 호가 단위 / neg-risk / 수수료율 |
| `/clob-markets/{cond}`, `/sampling-markets` | 거래용 마켓 메타 / 보상 있는 활성 마켓 |

### 1.3 Data — 온체인 포지션·거래·홀더 (무인증으로 **남의 지갑도** 조회)

| 엔드포인트 | 파라미터 | 라이브 확인 필드 |
| --- | --- | --- |
| `/trades` ★ | `market`(cond) 또는 `user`, `limit`,`offset`,`side` | `proxyWallet`, `side`, `price`, `size`, `outcome`, `outcomeIndex`, `timestamp`, `transactionHash`, `conditionId`, `title`, `slug`, `eventSlug`, `name`/`pseudonym` |
| `/holders` ★ | `market`(cond), `limit` | token별 `holders[]`: `proxyWallet`, `amount`, `outcomeIndex`, `asset`, `name`/`pseudonym`, `verified` |
| `/positions` | `user`(+`market`) | `conditionId`, `asset`, `outcome`, `size`, `avgPrice`, `curPrice`, `currentValue`, `initialValue`, `totalBought`, `cashPnl`, `realizedPnl`, `percentPnl`, `redeemable`, `endDate`, `title`, `slug` |
| `/closed-positions` | `user` | 청산된 포지션 |
| `/value` | `user` | 포지션 총 USD 가치 |
| `/activity` | `user` | 유저 활동 피드 |
| `/traded` | `user` | 거래한 마켓 수 |
| `/oi`, `/live-volume` | market / event | open interest / 실시간 거래량 |
| `/v1/leaderboard`, `/v1/builders/*` | period 등 | 트레이더/빌더 랭킹·볼륨 |
| `/v1/accounting/snapshot` | | CSV ZIP 일괄 다운로드 |

---

## 2. 핵심 ID 체계 (수집 전 필수)

| ID | 예시 | 출처 | 쓰는 곳 |
| --- | --- | --- | --- |
| `slug` | `microstrategy-sells-...` | Gamma | URL 키, 단건 조회 |
| `conditionId` | `0x3733…` (66 hex) | Gamma `conditionId` | **Data** `market=`, CLOB `clob-markets` |
| `clobTokenIds` | `["2571…","3192…"]` | Gamma `clobTokenIds` (JSON 문자열!) | **CLOB** book/price/**history** (`token_id`/`market=`) |
| wallet | `0x…` (40 hex) | trades/holders의 `proxyWallet` | **Data** positions/value |

⚠️ 가장 헷갈리는 점:
- `clobTokenIds`·`outcomes`·`outcomePrices`는 Gamma가 **JSON 문자열**로 줌 → `json.loads()` 필수.
- CLOB `prices-history`의 `market=`는 conditionId가 **아니라** clobTokenId(개별 outcome 토큰).
- 반대로 Data API `market=`는 **conditionId**.
- 이진 마켓: outcome 2개 → 토큰 2개. 가격 = 확률(0~1), Yes+No ≈ 1.

---

## 3. 수집 레시피 (→ `outputs/` CSV, Kalshi `s_k0_*` 파이프라인과 동형)

### 3.1 주제(태그)별 마켓 목록 덤프
```python
import csv, json, sys; sys.path.insert(0, "scripts")
from polymarket import PolymarketClient
c = PolymarketClient()

rows = []
for m in c.iter_markets(active=True, closed=False, order="volumeNum", ascending=False):
    rows.append({
        "conditionId": m["conditionId"], "slug": m["slug"], "question": m["question"],
        "tokens": m.get("clobTokenIds",""), "outcomes": m.get("outcomes",""),
        "outcomePrices": m.get("outcomePrices",""), "volumeNum": m.get("volumeNum"),
        "liquidityNum": m.get("liquidityNum"), "endDate": m.get("endDate"),
        "umaResolutionStatus": m.get("umaResolutionStatus"),
    })
with open("outputs/polymarket_markets.csv","w",newline="") as f:
    w = csv.DictWriter(f, fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
```

### 3.2 한 마켓의 가격(확률) 시계열
```python
m = c.get_market_by_slug("some-market-slug")
yes, no = json.loads(m["clobTokenIds"])
hist = c.get_prices_history(yes, interval="max", fidelity=60)["history"]   # [{t,p}, ...]
# t=unix초, p=Yes 확률. no 토큰도 동일하게 받아 합≈1 검증 가능.
```

### 3.3 체결 내역 / 홀더 (온체인 미시구조)
```python
trades  = c.get_trades(market=m["conditionId"], limit=500)   # 체결 단위 (지갑·가격·수량·시각)
holders = c.get_holders(m["conditionId"])                    # outcome별 top 홀더
```

### 3.4 수집 팁
- Gamma 페이지네이션은 `limit`+`offset` (Kalshi cursor와 다름) → `iter_markets()`가 자동 순회.
- rate limit 백오프는 `client.get()`에 내장. 대량이면 `fidelity` 키워 포인트 수 조절.
- `active=true&closed=false`로 활성만; 해결된 마켓 연구엔 `closed=true`로 따로 수집.
- 시계열의 `market=`엔 **clobTokenId**를 넣을 것 (자주 하는 실수).

---

## 4. carbon_arc 연구 연결
- **확률 시계열**: Kalshi outcome study(`s_k_*`)와 동형으로 이벤트 전후 가격 경로 분석. 정치/크립토/거시 마켓 다수 (Kalshi에 없는 것).
- **교차검증**: 동일 사건(CPI·금리·대선)을 Kalshi vs Polymarket 가격으로 → lead-lag / 괴리(arb). 기존 `s_h~s_j` lead-lag에 2차 시장 소스 추가.
- **온체인 미시구조**: `/trades`·`/holders`·`/positions` → 스마트머니 추종·집중도·포지셔닝 (Kalshi엔 없음).

---

## 5. (범위 밖) 주문 실행
주문/취소는 인증 필요 → `PolymarketClient.trading_client()` (`py-clob-client-v2` + `.env`의 `POLYMARKET_PRIVATE_KEY`).
수집과 무관하므로 여기선 생략. 필요해지면 별도 정리.

---
참고: 공식 docs `https://docs.polymarket.com`, OpenAPI `/api-spec/{gamma,data,clob}-openapi.yaml`, SDK `github.com/Polymarket/py-clob-client-v2`.
