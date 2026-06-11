# Track A — CarbonArc card → company revenue

> 2026-06-03 · `scripts/auto/s_p_revenue_nowcast.py`

```
# Track A — CarbonArc card spend → company revenue (nowcast)

aligned company-quarters: 453 across 35 tickers; date 2023-02-12..2026-05-10

## H1 (levels) & H2 (YoY growth): per-company correlation
  LEVELS  median r = +0.798 | frac r>0.5: 74% | frac r>0: 94%
  GROWTH  median r = +0.458 | frac r>0.3: 63% | frac r>0: 89%

## Pooled (company-clustered bootstrap + shuffle-company surrogate)
  H1 LEVELS pooled r=+0.933 CI[+0.69,+0.99] p_boot=0.000
  H2 GROWTH pooled r=+0.498 CI[+0.28,+0.72] p_boot=0.000  p_surrogate=0.000

## H4 timing: contemporaneous vs lagged CA
  contemp  CA_yoy(Q)   vs rev_yoy(Q): r=+0.498 p=0.000  (CA known ~weeks before the Q print → nowcast)
  lagged   CA_yoy(Q-1) vs rev_yoy(Q): r=+0.494 p=0.000

## H3 sector breakdown (pooled YoY growth corr)
  apparel_specialty  n= 53 tickers= 6  r(ca_yoy,rev_yoy)=+0.727
  bigbox_retail      n= 46 tickers= 5  r(ca_yoy,rev_yoy)=+0.541
  discount           n= 53 tickers= 6  r(ca_yoy,rev_yoy)=+0.085
  ecom_digital       n= 44 tickers= 5  r(ca_yoy,rev_yoy)=+0.461
  restaurant         n= 81 tickers= 9  r(ca_yoy,rev_yoy)=+0.608
  travel_gig         n= 36 tickers= 4  r(ca_yoy,rev_yoy)=+0.890

## per-company table
ticker            sector  nq  level_corr  yoy_corr
  ROST          discount  13    0.797858  0.956241
   MCD        restaurant  13    0.718411  0.932052
   CMG        restaurant  13    0.248080  0.895390
   ANF apparel_specialty  13    0.931939  0.886895
   LOW     bigbox_retail  13    0.569412  0.843857
  CAVA        restaurant  13    0.217983  0.840476
   TJX          discount  13    0.906932  0.786477
   WEN        restaurant  13    0.686566  0.715443
  AMZN      ecom_digital  13    0.909225  0.701268
  ABNB        travel_gig  13    0.203824  0.675548
   WMT     bigbox_retail  13    0.907583  0.672856
   TGT     bigbox_retail  13    0.932237  0.651001
   DPZ        restaurant  13    0.031824  0.647768
   DAL        travel_gig  13   -0.461099  0.616468
   AEO apparel_specialty  13    0.966772  0.572943
   BBY          discount  13    0.954863  0.564431
   NKE apparel_specialty  13    0.829929  0.490068
    KR          discount  12    0.088059  0.458316
  ETSY      ecom_digital  13    0.974362  0.437754
  NFLX      ecom_digital  13    0.964618  0.426980
  DASH        travel_gig  13    0.983872  0.346163
   DRI        restaurant  13    0.511380  0.339510
  TXRH        restaurant  13    0.809137  0.246206
    DG          discount  13    0.504111  0.229011
  UBER        travel_gig  13    0.961735  0.213831
   GAP apparel_specialty  13    0.843996  0.206586
  SBUX        restaurant  13    0.633363  0.203347
  LULU apparel_specialty  12    0.891673  0.162823
  URBN apparel_specialty  13    0.905767  0.159932
    HD     bigbox_retail  13    0.525833  0.039329
   YUM        restaurant  13   -0.486949  0.027164
  DLTR          discount  13    0.061367 -0.159182
  CHWY      ecom_digital  12    0.890382 -0.258013
  AAPL      ecom_digital  13    0.705270 -0.550659
  COST     bigbox_retail  14    0.257788 -0.667895
```
