# Issue #199 Platform Adapter Freeze

- schema_version: `w15.issue199.platform-adapters.v1`
- freeze_id: `issue199-platform-freeze-20260412`
- generated_at: `2026-04-12T16:01:45+00:00`
- task_set_version: `issue209-taskset-v1`
- dataset_version: `issue170-remote-batch3-20260316`
- difficulty_scheme_version: `issue209-difficulty-v1`

## Platforms

- primary: `{"platform_id": "inspect_ai", "role": "primary_platform", "baseline_family": "react_style_external", "status": "scaffolded_for_issue172", "install_hint": "uv tool run --from 'inspect-ai[openai]' inspect info version"}`
- regression: `{"platform_id": "promptfoo", "role": "lightweight_regression", "status": "ready_for_local_cli", "install_hint": "npx promptfoo@latest --version"}`
- external_baseline: `{"baseline_id": "react_style_external", "owner_issue": 172, "notes": "Issue #199 only prepares the adapter package and reproducibility bundle."}`

## Tool Whitelist

- tool_whitelist_version: `issue199-tool-whitelist-v1`
- allowed_tool_ids: `protgpt2, biopython_qc, dssp, objective_ranker, esmfold, openfold3, protein_mpnn`
- allowed_capability_ids: `sequence_generation, quality_qc, secondary_structure_annotation, objective_scoring, structure_prediction, sequence_design`

## Budget Contract

- budget_version: `issue199-budget-v1`
- max_plan_steps: `3`
- max_high_cost_steps: `1`
- max_llm_calls: `1`
- max_tool_calls: `3`
- max_wall_clock_seconds: `180`

## User Actions

- `export_provider_api_keys` (user / before_live_run): Provide the API key environment variables for the chosen external provider alias before live runs.
  details: At minimum this means the env var referenced by configs/llm_providers.json for the selected provider alias.
- `confirm_remote_tool_services` (user / before_live_run): Confirm PLM REST / OpenFold3 REST endpoints if the allowlist run needs remote tools.
  details: Default ports remain 8100 and 8200, but the final URL must be fixed in the run environment and reused by external baselines.
- `confirm_promptfoo_provider_override` (user / before_regression_gate): Keep promptfoo on baseline for structural regression, or explicitly override provider_alias before any live-provider regression.
  details: The generated promptfoo suite is deterministic by default and uses provider_alias=baseline. Only switch to a live provider when you intentionally want a costed regression run under the same freeze contract.

## Generated Artifacts

- output_dir: `output/experiment/w15-expr-0/issue199-platform-freeze-20260412`
- report_path: `/home/yurikon/文档/thesis/thesis-project.dev/output/experiment/w15-expr-0/issue199-platform-freeze-20260412/issue199_platform_adapter_report.md`
- inspect_eval_manifest_path: `/home/yurikon/文档/thesis/thesis-project.dev/output/experiment/w15-expr-0/issue199-platform-freeze-20260412/inspect_ai/inspect_eval_manifest.json`
- promptfoo_config_path: `/home/yurikon/文档/thesis/thesis-project.dev/output/experiment/w15-expr-0/issue199-platform-freeze-20260412/promptfoo/promptfooconfig.yaml`
- normalized_run_sample_path: `/home/yurikon/文档/thesis/thesis-project.dev/output/experiment/w15-expr-0/issue199-platform-freeze-20260412/standardized/normalized_run.sample.json`
- summary_row_sample_path: `/home/yurikon/文档/thesis/thesis-project.dev/output/experiment/w15-expr-0/issue199-platform-freeze-20260412/standardized/summary_row.sample.json`
- evidence_index_sample_path: `/home/yurikon/文档/thesis/thesis-project.dev/output/experiment/w15-expr-0/issue199-platform-freeze-20260412/standardized/evidence-index.sample.json`

## Validation Coverage

- `Inspect AI`: validates real sample loading, provider initialization, live model execution, eval log persistence, and the issue #199 answer contract.
- `promptfoo`: validates adapter JSON structure, metadata propagation, budget guardrails, and allowlist compliance as a lightweight regression gate.
- Neither tool alone proves the final E0/E1/E2 result quality; that remains owned by issue #172.

## Notes

- Issue #199 freezes adapter contracts and reproducibility docs only.
- Full E0/E1/E2 implementation remains owned by issue #172.
- Run-level outputs must carry freeze_id, budget, tool whitelist, and dataset version unchanged.

