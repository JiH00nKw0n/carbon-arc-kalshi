# Corrected EDGE (windows + consensus-referenced)

> 2026-06-03 · `scripts/auto/s_s_edge_windows.py`

```
# Corrected EDGE — consensus-referenced CA signal, return windows from CA-availability

events: 301 across 35 tickers; 2024-04-29..2026-06-02
CA_vs_cons mean=-0.050 sd=0.112

## INFO layer
  CA_vs_cons → rev_surprise        r=+0.467 (n=301) p_boot=0.001 p_surr=0.000 | L/S mean=+0.0048 t=+1.20

## EDGE by window (the key decomposition)
  CA_vs_cons → ret_PRE (CA-avail→pre-print) r=+0.083 (n=301) p_boot=0.201 p_surr=0.132 | L/S mean=+0.0107 t=+1.63
  CA_vs_cons → ret_PRINT (print-day, old H1) r=+0.019 (n=300) p_boot=0.688 p_surr=0.756 | L/S mean=-0.0026 t=-0.47
  CA_vs_cons → ret_TOTAL (CA-avail→post-print) r=+0.082 (n=300) p_boot=0.175 p_surr=0.170 | L/S mean=+0.0084 t=+0.95

## VERDICT
  ~ CA predicts the revenue surprise but NOT any return window → info real but fully priced (no $).
```
