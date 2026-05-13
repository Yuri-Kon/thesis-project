# Benchmark Platform Adapters Runbook

## 1. 目标

本 runbook 对应 issue `#199`，用于在不修改主执行链路的前提下，冻结并生成：

- `Inspect AI` 主平台接入骨架；
- `MLflow` tracking / artifact 记录骨架；
- `promptfoo` 轻量回归骨架；
- 可供 `#172` / `#221` 直接复用的标准化目录、样例落盘和 evidence-index 模板。

这部分只负责平台接入层、结果标准化和复现依据，不负责完整的 `E0/E1/E2` 实验实现。

## 2. 设计边界

- 不修改 FSM / HITL / Agent 边界。
- 不替代内部四组方法的主实验执行。
- 所有外部基线都必须沿用同一组字段：
  - `freeze_id`
  - `task_set_version`
  - `dataset_version`
  - `tool_whitelist.tool_whitelist_version`
  - `budget.budget_version`

## 3. 冻结配置

主配置文件：

- `configs/experiments/benchmark_platform_adapters.json`

当前冻结内容：

- 主平台：`Inspect AI`
- tracking 平台：`MLflow`
- 轻量回归：`promptfoo`
- 外部最小基线：`ReAct-style`
- 统一字段：`freeze_id / budget / tool whitelist / dataset version`

## 4. 生成旁路包

执行：

```bash
uv run python scripts/benchmarks/prepare_benchmark_platform_adapters.py \
  --config configs/experiments/benchmark_platform_adapters.json
```

默认输出目录：

- `output/experiment/w15-expr-0/<freeze_id>/`

核心产物：

- `platform_adapter_manifest.json`
- `platform_adapter_report.md`
- `inspect_ai/inspect_react_samples.jsonl`
- `inspect_ai/inspect_react_smoke.py`
- `inspect_ai/inspect_eval_manifest.json`
- `mlflow/mlflow_react_samples.jsonl`
- `mlflow/mlflow_react_eval.py`
- `mlflow/mlflow_eval_manifest.json`
- `promptfoo/promptfooconfig.yaml`
- `promptfoo/promptfoo_react_provider.py`
- `standardized/normalized_run.sample.json`
- `standardized/summary_row.sample.json`
- `standardized/evidence-index.sample.json`
- `standardized/result_layout.md`

## 5. Inspect AI 最小链路

先确认本地可用：

```bash
uv tool run --from 'inspect-ai[openai]' inspect info version
```

最小执行命令参考：

```bash
DEEPSEEK_BASE_URL=https://api.deepseek.com \
BENCHMARK_INSPECT_DATASET=/abs/path/to/output/experiment/w15-expr-0/<freeze_id>/inspect_ai/inspect_react_samples.jsonl \
uv tool run --from inspect-ai --with openai inspect eval \
  output/experiment/w15-expr-0/<freeze_id>/inspect_ai/inspect_react_smoke.py \
  --model openai-api/deepseek/deepseek-chat
```

说明：

- `#199` 阶段的 Inspect 任务验证主平台是否能完成 sample 装载、provider 初始化、sample execution、日志落盘，以及回答协议检查。
- 它不是 `#172` 的正式 scorer，只是把平台层的真实执行链路先跑通并固化。
- 真正的 domain tool bridging 和 `E0/E1/E2` 差异实现由 `#172` 接管。

## 6. MLflow tracking 链路

先确认本地 CLI：

```bash
uv tool run --from mlflow mlflow --version
```

执行：

```bash
MLFLOW_TRACKING_URI=file:///abs/path/to/output/experiment/w15-expr-0/<freeze_id>/mlflow/mlruns \
BENCHMARK_MLFLOW_DATASET=/abs/path/to/output/experiment/w15-expr-0/<freeze_id>/mlflow/mlflow_react_samples.jsonl \
uv run --with mlflow python \
  output/experiment/w15-expr-0/<freeze_id>/mlflow/mlflow_react_eval.py
```

说明：

- `MLflow` 在本项目里作为“tracking / artifact 记录层”，不替代主平台执行。
- 它会把冻结字段、派生 smoke 指标、以及每个 sample 的 payload artifact 记录到同一 experiment store。
- 这层最适合给后续 `#172` / `#221` 做 run-level 对比、结果版本化和追溯索引。

## 7. promptfoo 回归链路

先确认本地 CLI：

```bash
npx promptfoo@latest --version
```

执行：

```bash
npx promptfoo@latest eval \
  -c output/experiment/w15-expr-0/<freeze_id>/promptfoo/promptfooconfig.yaml
```

当前回归项覆盖：

- 结构：返回值必须是 JSON
- 字段：必须含 `plan / budget / tool_whitelist`
- 预算：`planned_steps` 与 `high_cost_planned_steps` 不得超过冻结上限
- 质量：使用可解释的规则化 rubric，检查约束传递、步数最小性、输入结构和白名单一致性

说明：

- `promptfoo_react_provider.py` 会复用仓库内的 `configs/llm_providers.json` 和 `provider_registry`。
- 默认 provider alias 是 `baseline`，因此不依赖 API key 就能先验证回归链路结构。
- 切换到真实 provider 时，只需改 `promptfooconfig.yaml` 里的 `provider_alias`，并提供对应环境变量。
- 在本项目里，`promptfoo` 的角色是“轻量回归闸门”，不是主评测平台。
- 它用于尽快发现接入层是否破坏了结构、字段、预算和白名单约束；真正的主平台日志与横向执行仍由 `Inspect AI` 和后续实验脚本负责。

## 7.1 三个平台分别验证什么

`Inspect AI` 验证：

- 主平台是否能真实执行外部基线样本
- provider 凭据与模型调用是否可用
- 是否产生 sample-level 日志与 eval log
- 回答是否遵守 `#199` 约定的回答协议

`MLflow` 验证：

- 冻结字段、provider alias 与样例级派生指标是否能进入统一 tracking store
- per-sample payload artifact 是否可回链到样例输入和 freeze contract
- 后续横向实验是否具备 run-level 对比与版本追踪入口

`promptfoo` 验证：

- adapter 输出是否仍为约定 JSON 结构
- `freeze_id / dataset_version / tool_whitelist_version` 是否被正确透传
- budget 与 allowlist 约束是否在接入层被破坏
- 在不依赖主平台日志的前提下，快速发现回归

这三个平台当前不能单独证明：

- 正式横向实验结论
- `E0/E1/E2` 的最终效果优劣
- 与内部四组方法的论文级比较

## 8. 用户协助项

以下部分必须由用户或实验操作者协助完成：

1. 提供最终参与对比的 provider API key 环境变量。
2. 决定 `MLFLOW_TRACKING_URI` 使用本地 file backend 还是共享 tracking 服务。
3. 如果需要远程工具服务，确认 `PLM_REST_BASE_URL` / `OPENFOLD3_REST_BASE_URL` 可访问。
4. 在 `#172` 正式落地时，将相同 `freeze_id / budget / tool whitelist / dataset version` 带入真实横向实验。

## 9. 标准化落盘约定

`standardized/normalized_run.sample.json` 定义 run-level 模板。

最少必须保留：

- `platform`
- `baseline_family`
- `task_key`
- `task_set_version`
- `dataset_version`
- `tool_whitelist`
- `budget`
- `raw_artifacts`
- `normalized_metrics`
- `traceability`

`standardized/summary_row.sample.json` 定义统一 summary row 的最小字段。

`standardized/evidence-index.sample.json` 定义图表/案例的最小追溯模板。

## 10. 常见故障

`inspect` 命令不存在：

- 先执行 `uv tool run --from 'inspect-ai[openai]' inspect info version`
- 如果使用 OpenAI-compatible provider，还需要 `uv tool run --from inspect-ai --with openai ...`

`promptfoo` 命令不存在：

- 使用 `npx promptfoo@latest ...`

`mlflow` 命令不存在：

- 使用 `uv tool run --from mlflow mlflow --version`
- 运行脚本时使用 `uv run --with mlflow python ...`

真实 provider 缺 API key：

- 对照 `configs/llm_providers.json` 中的 `api_key_env`

远程工具服务不可达：

- 核对 `../remote-server/README.md`
- 核对 `PLM_REST_BASE_URL` / `OPENFOLD3_REST_BASE_URL`

回归链路预算断言失败：

- 先看 `promptfoo` 输出中的 `planned_steps` 和 `high_cost_planned_steps`
- 再决定是调整 smoke budget，还是收紧外部基线提示词
