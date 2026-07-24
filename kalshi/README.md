# Kalshi Raw-Ladder Benchmark

This directory contains the Kalshi-only X substitution for Jihoon's latest `main` revenue
nowcasting benchmark. Carbon Arc data is not mixed into the Kalshi experiment. The shared model,
Y definitions, financial H input, earnings-call Z input, prompt variants, arms, row matching and
evaluation code live in `prediction/`; Kalshi contributes only a raw pre-publication KPI ladder X.
For Table 1, the paper exporter reports source-ablation and tool-use FVU/MAE with
company-clustered bootstrap error bars and writes paste-ready Overleaf row blocks.
For the manuscript's classical Table 2 comparison only, the paper exporter derives a separate
unitless survival-curve AUC scalar without changing the LLM input.

The authoritative manuscript design, current three-repetition results, universe and audit summary
are consolidated in [`PAPER_RESULTS.md`](PAPER_RESULTS.md). [`BENCHMARK.md`](BENCHMARK.md) is the
archived one-run Jihoon-main reproduction that preceded the manuscript rerun. Raw cell artifacts,
lossless call logs and evaluation manifests remain git-ignored under `prediction/outputs/`.

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
python3 -m prediction --config prediction/configs/kalshi_smoke.yaml
python3 -m prediction --config prediction/configs/kalshi_paper.yaml --render
python3 -m prediction --config prediction/configs/kalshi_paper.yaml
python3 kalshi/scripts/auto/s_aw_kalshi_repair_calls.py
python3 kalshi/scripts/auto/s_av_kalshi_paper_artifacts.py
```

Use `prediction/configs/kalshi_smoke.yaml` for one target per Y under the manuscript prompt
protocol (24 BASE + TOOL integration calls).

Use `prediction/configs/kalshi_full.yaml` followed by
`kalshi/scripts/auto/s_au_kalshi_benchmark_report.py` only to reproduce Jihoon's latest main
configuration: one repetition and the shared main-branch prompt protocol.

## Audit outputs

- Screening calls: `kalshi/outputs/auto/kalshi_kpi_firm_screen_calls.jsonl`
- Prediction calls: `prediction/outputs/kalshi_paper/<cell>/calls.jsonl`
- Paper figures: `kalshi/paper/figures/`
- Paper tables: `kalshi/paper/tables/`
- Machine-readable paper data: `kalshi/paper/data/`
- Table 1 source-ablation audit: `kalshi/paper/data/table1_audit.json`
- Table 1 tool-use audit: `kalshi/paper/data/table1_tool_audit.json`
- Table 2 audit: `kalshi/paper/data/table2_audit.json`

Each prediction call records the exact system and user prompt, prompt hash, complete structured
output, confidence, rationale, derived prediction, tool calls and returned text, token usage, cost,
attempt count and error status. The paper artifact exporter refuses to generate outputs if any
target/arm call or rationale is missing. The repair command is a no-op when all calls succeeded; if
the configured retry budget was exhausted, it replays only the exact failed prompt and archives
both records in that cell's `repairs.jsonl`.

## Data boundaries

- Kalshi market inventory and candlesticks come from the public Trade API v2.
- Revenue actuals and point-in-time consensus come directly from FactSet FE_V4 via `factset_query`.
- Stock DB supplies ticker/FactSet identity, fiscal labels and corrected-call metadata.
- Corrected earnings-call HTML is cached from internal S3 and converted to text.
- The frozen Kalshi-only strength screen is `kalshi/data/ticker_screen.csv`.
- TOOL context is frozen under `kalshi/data/tool_context.json`.

Raw/licensed data, transcript text, LLM outputs and run logs remain git-ignored. Credentials are
resolved from process variables or sibling server `.env` files and are never written to artifacts.
