# Kalshi Raw-Ladder Revenue-Surprise Experiment

This directory contains the Kalshi-only replication of the Carbon Arc Factor 1
LLM ablation. The outcome, conventional financial input, prior-call input,
model, prompt contract, matched-sample rule, and metrics are held fixed. Only
`X` changes: Carbon Arc channel history is replaced by raw pre-publication
Kalshi KPI ladders.

## Current result

The direct-FactSet run contains 36 company-quarters across 28 tickers and 144
successful LLM calls. Adding Kalshi reduced RMSE from 3.914 to 3.780 over the
financial arm and from 4.125 to 3.783 over the financial-plus-call arm. Both
company-clustered 95% confidence intervals include zero, so these favorable
point estimates are not statistically robust incremental value.

- Full design: [`EXPERIMENT.md`](EXPERIMENT.md)
- Canonical results: [`RESULTS.md`](RESULTS.md)

## Directory layout

```text
kalshi/
  README.md                 entry point and reproduction commands
  EXPERIMENT.md             frozen design, definitions, and leakage rules
  RESULTS.md                generated universe audit, metrics, and conclusion
  scripts/auto/             data, LLM, and analysis pipeline
  tests/                    focused regression tests
  outputs/auto/             generated data and call logs
```

`outputs/auto` contains API-derived data, licensed direct FactSet data, internal
Stock DB metadata, earnings-call text caches, and per-call logs. These files are
reproducible but ignored or restricted by repository policy. Credentials are
never written to the documentation or source code.

## Pipeline

Run from the repository root:

```bash
python3 kalshi/scripts/auto/s_af_kalshi_company_inventory.py
python3 kalshi/scripts/auto/s_ag_kalshi_company_features.py
python3 kalshi/scripts/auto/s_ai_factset_revsurprise_panel.py
python3 kalshi/scripts/auto/s_ah_kalshi_x_revsurprise.py
python3 kalshi/scripts/auto/s_ak_kalshi_prereport_features.py
python3 kalshi/scripts/auto/s_al_kalshi_llm_ablation.py --eligibility-only
python3 kalshi/scripts/auto/s_al_kalshi_llm_ablation.py
python3 kalshi/scripts/auto/s_an_kalshi_ladder_analysis.py
python3 -m unittest kalshi.tests.test_ladder_pipeline
```

The LLM runner uses one independent call per target and arm, matching the
Carbon Arc Factor 1 benchmark. If a run ends with missing calls, rerun with
`--resume`; only successful records in the existing JSONL are reused.

## Required configuration

The scripts read existing server `.env` files or process environment variables:

- `LLM_GATEWAY_URL` and `LLM_GATEWAY_API_KEY`, or `OPENAI_API_KEY`
- VPN access to `FACTSET_MCP_URL` (default: the internal staging MCP endpoint)
- `STOCK_DB_HOST`, `STOCK_DB_PORT`, `STOCK_DB_NAME`, `STOCK_DB_USER`, and
  `STOCK_DB_PASSWORD` for ticker-to-FactSet-ID and fiscal-label metadata
- one internally consistent AWS access-key bundle, region, and
  `AWS_S3_BUCKET_NAME` for corrected earnings-call documents

AWS access key, secret, and optional session token are selected atomically from
one environment file. They are not mixed across servers.
