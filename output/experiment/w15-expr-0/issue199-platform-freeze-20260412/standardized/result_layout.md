# Issue #199 Standardized Result Layout

- freeze_id: `issue199-platform-freeze-20260412`
- output_dir: `output/experiment/w15-expr-0/issue199-platform-freeze-20260412`

## Required Roots

- `inspect_ai/`：主平台任务、样例数据与 Inspect 运行清单
- `promptfoo/`：轻量回归配置与 provider bridge
- `standardized/`：标准化样例落盘与 evidence-index 模板

## Required Carry-Forward Fields

- `freeze_id`
- `task_set_version`
- `dataset_version`
- `tool_whitelist.tool_whitelist_version`
- `budget.budget_version`

## User-Owned Preconditions

- `export_provider_api_keys`: Provide the API key environment variables for the chosen external provider alias before live runs.
- `confirm_remote_tool_services`: Confirm PLM REST / OpenFold3 REST endpoints if the allowlist run needs remote tools.
- `confirm_promptfoo_provider_override`: Keep promptfoo on baseline for structural regression, or explicitly override provider_alias before any live-provider regression.

