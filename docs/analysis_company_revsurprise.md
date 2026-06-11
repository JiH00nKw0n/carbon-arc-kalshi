# CA → revenue surprise (clean info test)

> 2026-06-03 · `scripts/auto/s_r_revenue_surprise.py`

```
# Clean causal/information test — CA → REVENUE surprise (actual − consensus)

reports with revenue estimate+actual: 1226 across 35 tickers; 2016-07-21..2026-06-02
revenue-surprise: mean=+0.1085 sd=1.0666 (≈0 ⇒ consensus ~unbiased)
aligned CA_surprise × revenue_surprise: 241 events, 35 tickers

## H_REV — CA_surprise → revenue surprise (does CA beat the revenue consensus?)
  r=-0.065 (n=241) p_boot=0.245 p_surrogate=0.106
  [raw ca_yoy → rev_surprise]: r=+0.082 p_boot=0.536

## sanity(a) revenue_surprise → earnings-day return: r=-0.061 (n=240)  (weak)
## sanity(b) CA_yoy ↔ revenue level corr (should be high): r=+0.190

## H4 — H_REV by card-share tercile
  cardshare=high: r=+0.011 (p0.78, n81)
  cardshare=mid : r=-0.201 (p0.01, n80)
  cardshare=low : r=-0.002 (p0.85, n80)

## VERDICT
  ❌ NULL — CA does NOT predict the revenue surprise (r=-0.065, surrogate p=0.106).
     Closes the information layer: CA carries NO revenue information beyond analyst consensus.
     ⇒ CA at company level = a MEASUREMENT of revenue, already embedded in consensus/price. No edge.
```
