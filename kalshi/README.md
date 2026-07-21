# Kalshi Raw-Ladder Revenue-Surprise Experiment

This directory contains the Kalshi-only replication of the Carbon Arc Factor 1
LLM ablation. The outcome, conventional financial input, prior-call transcripts,
model, prompt contract, matched-sample rule, and metrics are held fixed. Only
`X` changes: Carbon Arc channel history is replaced by raw pre-publication
Kalshi KPI ladders.

## Current status

The paper-aligned two-transcript rule yields 32 eligible company-quarters across
28 tickers for both independently constructed target manifests. Both full runs
are complete: 32 targets x 4 arms x 3 independent repeats = 384 successful calls
per target definition, with no remaining errors.

The early-surprise result is not statistically robust: the ladder worsens RMSE
by 0.136 points over financial history and improves it by 0.269 points after
prior calls, but both company-bootstrap intervals include zero. The YoY result
does not satisfy the paper's cross-source synergy definition.

- Full design: [`EXPERIMENT.md`](EXPERIMENT.md)
- Early-surprise results: [`RESULTS.md`](RESULTS.md)
- Revenue-YoY results: [`YOY_RESULTS.md`](YOY_RESULTS.md)

## Directory layout

```text
kalshi/
  README.md                 entry point and reproduction commands
  EXPERIMENT.md             frozen design, definitions, and leakage rules
  RESULTS.md                generated early-surprise audit and results
  YOY_RESULTS.md            generated paper-format revenue-YoY results
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
python3 kalshi/scripts/auto/s_al_kalshi_llm_ablation.py --target surprise --eligibility-only
python3 kalshi/scripts/auto/s_al_kalshi_llm_ablation.py --target yoy --eligibility-only
python3 kalshi/scripts/auto/s_al_kalshi_llm_ablation.py --target surprise
python3 kalshi/scripts/auto/s_al_kalshi_llm_ablation.py --target yoy
python3 kalshi/scripts/auto/s_an_kalshi_ladder_analysis.py
python3 kalshi/scripts/auto/s_ao_kalshi_paper_tables.py
python3 -m unittest kalshi.tests.test_ladder_pipeline
```

The runner writes target-specific artifacts by default. Surprise eligibility,
predictions, and call logs contain `_surprise`; the corresponding YoY files
contain `_yoy`. Each row and call-log record also carries an explicit `target`
field, and resume mode ignores records from any other target.

The LLM runner uses three independent calls per target and arm and reports their
mean, matching the paper. If a run ends with missing calls, rerun with
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
