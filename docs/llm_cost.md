# LLM cost envelope — Phase 3 unstructured pipeline

LLM 비정형 시그널 (CA row → text → Kalshi 매칭) 의 연간 비용 예산. 작성 2026-05-14, 현재 *smoke test 통과 후 미실행* 상태 (Phase 3 본 실행은 Phase 5 결과 반영 후).

## Assumptions

- Model: **Claude Sonnet 4.6** (`claude-sonnet-4-6`) with prompt caching.
  - Input (cached read): $0.30 / MTok.
  - Input (uncached): $3.00 / MTok.
  - Output: $15.00 / MTok.
  - 5-minute cache TTL.
- Pipeline = (CA row → summary) → kalshi_search → (per market → relevance score) → optional final betting probability.

## Per-call breakdown

### Stage 1: CA row → 1-sentence summary

- System prompt + few-shot examples ≈ 900 cached input tokens.
- Per row: ~150 uncached input tokens (row JSON + column dict).
- Output: ~60 tokens.
- Cost/row = 900 * 0.30/1M + 150 * 3.00/1M + 60 * 15/1M
  = $0.00027 + $0.00045 + $0.00090 = **$0.00162** ≈ 0.16¢.

### Stage 2: kalshi_search

- Cost = free (Linq MCP).
- Returns top-10 candidate markets per summary.

### Stage 3: Per-market relevance score

- System prompt cached ~600 tokens.
- Per (summary, market) pair: 250 uncached tokens (summary + market title + subtitle + rules text).
- Output: ~15 tokens (a number + 1-line reason).
- Cost/pair = 600 * 0.30/1M + 250 * 3.00/1M + 15 * 15/1M
  = $0.00018 + $0.00075 + $0.000225 = **$0.00115** ≈ 0.12¢/pair.

### Stage 4 (optional): Final probability w/ context

- Used only at *bet-decision time* per market per close.
- System prompt cached ~800 tokens.
- Per call: ~3,000 uncached tokens (5 best summaries + market history + S2 features text).
- Output: ~120 tokens (probability + reasoning).
- Cost/decision = 800 * 0.30/1M + 3000 * 3.00/1M + 120 * 15/1M
  = $0.00024 + $0.009 + $0.0018 = **$0.011** ≈ 1.1¢/decision.

## Annual envelope — research scale

Assume:
- 4 priority datasets (CA0049, CA0030, CA0056, CA0040) bought.
- Each aggregated to (ticker, state, week) — call it 5,000 rows / dataset / year.
- 200 macro/health Kalshi markets actively traded.
- We rerun pipeline daily on the trailing 30-day window.

| Stage | Volume / year | $ per call | Annual $ |
|---|---:|---:|---:|
| 1. CA row → summary | 4 × 5,000 × 52 weeks = 1.04M | $0.00162 | **$1,685** |
| 3. relevance scoring | 1.04M summaries × 10 markets = 10.4M | $0.00115 | **$11,960** |
| 4. final decision | 200 markets × 365 days = 73,000 | $0.011 | **$803** |
| **Total** | | | **≈ $14.5k / year** |

## Reduction levers (if budget tight)

1. **Aggregate before summarizing**: produce 1 summary per (ticker, state, month) instead of weekly → 4× reduction → ~$3.6k.
2. **Cache the relevance scores by (summary_hash, market_ticker)**: same summary often re-applies if window is daily — 5× reduction.
3. **Skip Stage 3 for markets with low Stage-2 search score** (filter K=10 → K=3) → 3× reduction.
4. Combined: realistic **~$1.5-2k/year**, paper-scale only **a few hundred**.

## Comparison to alternatives

- Stage-1 with Haiku 4.5 (cheaper): ~30% cost. But quality of "what's
  noteworthy" framing is much worse — Sonnet's economic-judgment matters
  here. Keep Sonnet for Stage 1.
- Stage-3 with Haiku 4.5: quality OK for relevance scoring; switching saves
  ~70% on that stage → annual drops to ~$5k.
- Stage-4 must stay Sonnet because of calibration.

**Recommendation**: Sonnet 4.6 across the board for the first paper run,
then port Stage 3 to Haiku 4.5 after we validate signal.
