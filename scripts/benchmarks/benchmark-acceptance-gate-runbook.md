# Benchmark Acceptance Gate Runbook

## 1. 目标

本 runbook 对应 issue `#200`，用于在不修改主执行控制流的前提下，提供：

- 本地一键验收入口；
- 可复用于 `#172 / #221 / #224` 的 gate summary / blockers / evidence-index；
- CI 一键门禁入口。

本阶段只负责门禁、一致性校验和可消费产物，不负责横向实验主体执行。

## 2. 设计边界

- 不修改 FSM / HITL / Agent 边界。
- 不把门禁逻辑混入主 workflow 执行链路。
- 所有检查围绕同一组冻结字段：
  - `freeze_id`
  - `task_set_version`
  - `dataset_version`
  - `tool_whitelist.tool_whitelist_version`
  - `budget.budget_version`

## 3. 冻结配置

当前共享配置：

- `configs/experiments/benchmark_platform_adapters.json`

门禁检查最少覆盖：

- ToolKG / Adapter / Provider / experiment config 完整性
- allowlisted tool / capability 一致性
- budget carry-forward 一致性
- sample task 输入版本一致性
- 可直接给下游 issue 复用的 summary / blockers / evidence-index

## 4. 本地一键验收

执行：

```bash
UV_CACHE_DIR=/tmp/uv-cache \
uv run python scripts/benchmarks/run_benchmark_acceptance_suite.py \
  --config configs/experiments/benchmark_platform_adapters.json \
  --output-root output/experiment/benchmark-acceptance-local
```

说明：

- 该入口会先运行 focused pytest：
  - `tests/unit/test_benchmark_acceptance_gate.py`
  - `tests/unit/test_benchmark_platform_adapters.py`
- 然后执行 benchmark gate runner。
- 任一 focused test 失败，或 gate 出现 `block`，命令都会返回非零。

## 5. 仅运行 Gate

如果只想做冻结配置和依赖一致性检查，可直接运行：

```bash
UV_CACHE_DIR=/tmp/uv-cache \
uv run python scripts/benchmarks/run_benchmark_acceptance_gate.py \
  --config configs/experiments/benchmark_platform_adapters.json \
  --output-root output/experiment/benchmark-acceptance-gate-only
```

## 6. 输出产物

默认输出目录：

- `output/experiment/<...>/<freeze_id>/`

关键产物：

- `benchmark_acceptance_suite.json`
- `benchmark_acceptance_gate_report.json`
- `benchmark_acceptance_gate_summary.md`
- `benchmark_gate_summary.json`
- `benchmark_gate_blockers.json`
- `benchmark_gate_evidence_index.json`

用途说明：

- `benchmark_acceptance_suite.json`：本地/CI 一键验收总入口结果
- `benchmark_acceptance_gate_report.json`：完整 checks report
- `benchmark_gate_summary.json`：给 `#172 / #221 / #224` 直接消费的门禁摘要
- `benchmark_gate_blockers.json`：阻断项与修复建议清单
- `benchmark_gate_evidence_index.json`：按 evidence-index 风格整理的门禁产物索引

## 7. CI 入口

仓库工作流：

- `.github/workflows/benchmark-acceptance-gate.yml`

触发方式：

- `workflow_dispatch`
- 对 benchmark 相关配置/脚本/测试文件的 `pull_request`

CI 中执行的入口与本地一致：

```bash
uv run python scripts/benchmarks/run_benchmark_acceptance_suite.py \
  --output-root output/experiment/benchmark-acceptance-ci \
  --freeze-id benchmark-ci-<run_id>
```

产物会作为 GitHub Actions artifact 上传，便于直接附到报告或 downstream issue。

## 8. 通过/阻断语义

通过态：

- focused tests 全通过
- gate `overall_status=pass`
- `benchmark_gate_summary.json.ready_for_downstream=true`

阻断态：

- focused tests 任一失败；或
- gate 发现关键冻结字段、白名单、provider 配置、输入口径不一致

下游使用约定：

- 优先引用 `benchmark_gate_summary.json`
- 修复问题时优先查看 `benchmark_gate_blockers.json`
- 需要追溯时查看 `benchmark_gate_evidence_index.json`

## 9. 常见故障

`uv` 缓存目录权限问题：

- 本地可显式设置 `UV_CACHE_DIR=/tmp/uv-cache`

gate 阻断 `tool_whitelist_known_tools`：

- 核对白名单工具 ID 是否与 `src/kg/protein_tool_kg.json` 当前 `tool.id` 对齐

gate 阻断 `adapter_registration`：

- 核对 `src/adapters/builtins.py` 是否完成默认注册

gate 阻断 `llm_provider_catalog`：

- 核对 `configs/llm_providers.json` 的 alias 是否与实验配置一致

CI 无产物：

- 检查 workflow 日志中 `output/experiment/benchmark-acceptance-ci` 是否成功生成
