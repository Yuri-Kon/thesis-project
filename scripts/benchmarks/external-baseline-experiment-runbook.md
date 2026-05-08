# External Baseline Experiment Runbook

## 1. 目标

本 runbook 对应 issue `#172`，用于在统一公平性约束下运行并评估三组外部基线：

- `E0`：`ReAct-style` 单轨迹
- `E1`：`ToT-style` 多分支
- `E2`：`Reflexion-style` 反思恢复

统一约束来源：

- 平台冻结：`configs/experiments/benchmark_platform_adapters.json`
- 任务冻结：`configs/experiments/baseline_experiment_contract.json`
- 实验配置：`configs/experiments/external_baseline_experiment.json`

## 2. 设计边界

- 不修改 FSM / HITL / Agent 边界。
- 不把外部横向实验与内部 `A0-A6` 主表混在同一主实验里。
- 所有 `E0/E1/E2` run 都必须沿用同一组冻结字段：
  - `freeze_id`
  - `dataset_version`
  - `task_set_version`
  - `tool_whitelist.tool_whitelist_version`
  - `budget_contract.budget_version`

## 3. 先做本地 dry-run

这一步不调用外部 LLM，也不访问远端工具服务，只验证：

- run manifest 生成
- run config 落盘
- 评估与汇总产物
- evidence / traceability 索引

执行：

```bash
uv run python scripts/run_external_baseline_experiment.py \
  --config configs/experiments/external_baseline_experiment.json \
  --run-id external-baseline-local-dryrun \
  --output-root /tmp/external-baseline \
  --dry-run
```

核心产物：

- `runs_manifest.json`
- `run_log_index.csv`
- `horizontal_metrics_summary.csv`
- `mechanism_increment_deltas.csv`
- `requirement2_tool_capability_slices.csv`
- `lite_belief_state_vs_e0_e2.csv`
- `horizontal_report.md`
- `validation_summary.json`

## 4. Live run 前置条件

真正执行 `E0/E1/E2` 前，需要先由用户确认以下外部依赖：

1. `PLANNER_LLM_PROVIDER` 对应 alias 可用，且已设置所需 API key。
2. 如果需要远程结构工具，确认：
   - `PLM_REST_BASE_URL`
   - `OPENFOLD3_REST_BASE_URL`
3. 如果要把结果写入共享 tracking，而不是本地文件：
   - `MLFLOW_TRACKING_URI`

当前默认假设：

- 外部基线实验的 planner 走 `configs/llm_providers.json`
- 结构预测步骤按配置改写到 `openfold` + `openfold3_rest`
- 二级结构注释步骤改写到 `biopython_qc`

## 5. 发起 live run

示例：

```bash
PLANNER_LLM_PROVIDER=glm-5 \
PLM_REST_BASE_URL=http://<remote-host>:8100 \
OPENFOLD3_REST_BASE_URL=http://<remote-host>:8200 \
uv run python scripts/run_external_baseline_experiment.py \
  --config configs/experiments/external_baseline_experiment.json \
  --run-id external-baseline-live-r1 \
  --planner-provider glm-5
```

如果只想先跑少量样本验证链路：

```bash
PLANNER_LLM_PROVIDER=glm-5 \
uv run python scripts/run_external_baseline_experiment.py \
  --config configs/experiments/external_baseline_experiment.json \
  --run-id external-baseline-smoke-r1 \
  --planner-provider glm-5 \
  --max-runs 3
```

## 6. 结果解读

优先查看：

- `horizontal_metrics_summary.csv`
  - 三组效果 / 机制 / 代价 / 治理指标总表
- `mechanism_increment_deltas.csv`
  - `E0 -> E1 -> E2` 的增量差异与 CI
- `lite_belief_state_vs_e0_e2.csv`
  - 内部参考组与外部三组的横向摘要
- `rerun_candidates.json`
  - 缺 artifact、失败或异常样本的重跑建议

## 7. 常见故障

`planner provider` 初始化失败：

- 核对 `configs/llm_providers.json`
- 核对 alias 是否在 `provider_allowlist.allowed_aliases`
- 核对对应 `api_key_env` 是否已设置

远程工具服务不可达：

- 核对 `../remote-server/README.md`
- 核对 `PLM_REST_BASE_URL` / `OPENFOLD3_REST_BASE_URL`

产物不完整：

- 看 `validation_summary.json`
- 看 `rerun_candidates.json`
- 看 `run_traceability_index.csv`

## 8. 当前状态

- 本地 `dry-run + evaluate` 已打通。
- 真正的 `live` 横向实验仍依赖外部 provider 和远端工具服务确认后再执行。
