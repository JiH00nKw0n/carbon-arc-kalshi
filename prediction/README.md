# prediction — config-driven revenue-surprise nowcasting

A config-driven, tested rewrite of the `factor1/scripts/f1_*` research pipeline. One YAML defines an
entire experiment (channel / target / variant / arm / baseline grid, cutoff, seed, LLM model,
bootstrap counts); every swappable axis self-registers through a decorator registry, and leakage /
calibration / metric guards are enforced in code with regression tests.

## Run

```bash
python -m prediction --config prediction/configs/revenue_surprise_full.yaml
```

- `--render` — `$0` dry run: compose the prompts to `<output_dir>/render/` and exit, no LLM calls.
- `--force` — recompute cells whose report already exists.

The full experiment is defined in `configs/revenue_surprise_full.yaml`; `configs/smoke.yaml` is a
reduced (single channel/target, 2 targets) config for a quick end-to-end check.

Authentication uses `OPENAI_API_KEY` when present. Otherwise it resolves `LLM_GATEWAY_URL` and
`LLM_GATEWAY_API_KEY` from the process environment or sibling server `.env` files.

## Prompt variants — the tool toggle

There is one prompt, **BASE**. Whether the model additionally gets two on-demand lookup tools is a
config choice expressed as the `variants` grid axis:

| variant | prompt | tools |
|---|---|---|
| `BASE` | BASE | none |
| `TOOL` | BASE (identical) | `get_company_profile`, `get_alt_data_description` |

`BASE` and `TOOL` render a **byte-identical** prompt; `TOOL` only wires the tools into the LLM
request, and the client runs a `tool_call → tool_result` loop before the structured parse. The tools
serve the frozen company profile and active channel methodology on demand, so the model pulls that
context only when it judges it worth the tokens. Scalar channels retain their legacy Carbon Arc
descriptions; Kalshi uses `kalshi/data/tool_context.json`. This replaces the retired `DESC` variant,
which front-loaded the same text into every prompt.

To compare with vs. without tools, list both — `variants: [BASE, TOOL]` — and each gets its own report.

## Layout

| area | modules | role |
|---|---|---|
| Config | `config/schema.py`, `config/loader.py` | Pydantic v2 strict models (`extra="forbid"`) |
| Registry | `registry.py` | channel / target / prompt / variant / arm / baseline / llm self-register |
| Panel / features | `panel/` | panel assembly, sentiment / lag_y / x_sent, Y definitions |
| Baselines | `baselines/` | N0–N5 (naive / OLS / GBT) |
| Channel / arm / prompt | `channels/`, `arms/`, `prompts/` | channel config, 4-arm ablation, prompt blocks + variants + tools |
| LLM prediction | `predict/llm_predictor.py`, `data/llm_client.py` | structured-output predictor + tool loop |
| Evaluation | `evaluate/` | MSE / R² / corr, leak-free 5-fold calibration, bootstrap + surrogate, report render |
| Orchestration | `run/` | grid expansion, execution, result store |
| Tests | `tests/` | leakage / calibration / metrics / panel / arm-masking / y-target regression tests |

## Relationship to `factor1/scripts`

`factor1/scripts/f1_*.py` are the original research scripts — the source of the numbers cited in
`RESULTS_UNIFIED.md` and the result charts. `prediction/` is the same paradigm rewritten to be
config-driven, tested, and leakage-guarded in code. Run outputs are written under
`prediction/outputs/` (git-ignored), kept separate from the legacy `factor1/outputs/`.
