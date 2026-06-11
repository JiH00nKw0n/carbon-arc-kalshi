# CA → EPS surprise (FactSet point-in-time)

> 2026-06-04 · `scripts/auto/s_u_epssurprise_factset.py`

```
# Clean test — CA → EPS surprise, FactSet POINT-IN-TIME consensus (mirror of revenue test)

events: 304 across 35 tickers; 2024-02-29..2026-05-31
(dropped |EPS|<0.05; surprise winsorized at 1/99%)
eps surprise_early: mean=+0.0803 sd=0.3627
eps beat-rate (actual>cons_early): 0.74

## INFO — does CA predict the EPS surprise? (X=ca_yoy CLEAN, no artifact)
  ca_yoy → eps_surprise_early : r=+0.065 (n=304) p_boot=0.302 p_surr=0.235
  ca_yoy → eps_surprise_print : r=+0.057 (n=304) p_boot=0.418 p_surr=0.391

## RETURN edge (artifact-free)
  (ca_yoy − cons_early) → earnings-day return: r=-0.048 (n=181) p_boot=0.371 p_surr=0.439
  sanity: EPS surprise → return r=+0.146 (n=296)

## CROSS-CHECK — CA's EPS edge vs its revenue edge (same X, same tickers)
  (revenue result for reference: ca_yoy → revenue surprise_early r≈+0.19 p_surr≈0.008 — see analysis_company_revsurprise_factset.md)

## VERDICT
  ❌ NULL — CA does NOT predict the EPS surprise (r=+0.065, surr p=0.235).
     Expected: CA card spend is a REVENUE/demand proxy. EPS adds margins, costs, taxes, buybacks,
     one-offs — none visible to card data. So even though CA modestly beats the REVENUE consensus
     (r≈0.19), that edge does NOT survive into EPS, which is what actually drives the stock.
```
