# Kalshi Raw-Ladder Benchmark

This directory contains the Kalshi-only X substitution for Jihoon's latest `main` revenue
nowcasting benchmark. Carbon Arc data is not mixed into the Kalshi experiment. The shared model,
Y definitions, financial H input, earnings-call Z input, prompt variants, arms, row matching and
evaluation code live in `prediction/`; Kalshi contributes only a raw pre-publication KPI ladder X.

The authoritative design, universe, ticker-quarter manifest, metrics and results are consolidated in
[`BENCHMARK.md`](BENCHMARK.md). Generated cell artifacts and the machine-readable
`evaluation_manifest.csv` are under `prediction/outputs/kalshi_benchmark/` and are git-ignored.

## Run

From the repository root:

```bash
python3 kalshi/scripts/auto/s_af_kalshi_company_inventory.py
python3 kalshi/scripts/auto/s_ag_kalshi_company_features.py
python3 kalshi/scripts/auto/s_ai_factset_revsurprise_panel.py
python3 kalshi/scripts/auto/s_ah_kalshi_x_revsurprise.py
python3 kalshi/scripts/auto/s_ak_kalshi_prereport_features.py
python3 kalshi/scripts/auto/s_ap_kalshi_revenue_screen.py --apply-panel
python3 kalshi/scripts/auto/s_aq_kalshi_screening_agent.py --apply-panel --write-ticker-screen
python3 kalshi/scripts/auto/s_ar_kalshi_transcript_index.py
python3 kalshi/scripts/auto/s_at_kalshi_tool_context.py
python3 -m prediction --config prediction/configs/kalshi_full.yaml --render
python3 -m prediction --config prediction/configs/kalshi_full.yaml
python3 kalshi/scripts/auto/s_au_kalshi_benchmark_report.py
```

Use `prediction/configs/kalshi_smoke.yaml` for one-target BASE + TOOL integration testing.

## Data boundaries

- Kalshi market inventory and candlesticks come from the public Trade API v2.
- Revenue actuals and point-in-time consensus come directly from FactSet FE_V4 via `factset_query`.
- Stock DB supplies ticker/FactSet identity, fiscal labels and corrected-call metadata.
- Corrected earnings-call HTML is cached from internal S3 and converted to text.
- The frozen Kalshi-only strength screen is `kalshi/data/ticker_screen.csv`.
- TOOL context is frozen under `kalshi/data/tool_context.json`.

Raw/licensed data, transcript text, LLM outputs and run logs remain git-ignored. Credentials are
resolved from process variables or sibling server `.env` files and are never written to artifacts.
