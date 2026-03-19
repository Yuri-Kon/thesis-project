# W12 实验报告（Issue #169 / #170 / #171）

## 1. 报告信息

- 报告日期：2026-03-16
- 代码仓库：`thesis-project.dev`
- 对应 Issue：#169, #170, #171
- 关联 Issue（依赖/软同步）：#143, #145, #146, #149, #157, #158, #159, #160, #172, #173, #174
- 本次关键冻结版本：
  - Plan Freeze：`w12-midterm-experiment-plan-freeze-20260315T171144Z`
  - Data Freeze：`issue170-remote-batch3-20260316`
  - Vertical Run：`issue171-remote-batch3-r3`

## 2. Issue 目标与验收要求

### 2.1 #169（计划冻结与依赖排程）

目标：冻结 03-16~03-22 的实验节奏，明确 Hard 依赖与可并行关系，保证“数据优先”。

验收点：

1. 所有实验 issue 有明确开始/结束时点。
2. 依赖关系完整、无循环阻塞。
3. 数据 issue（#170）位于关键路径最前。

### 2.2 #170（真实数据快采与版本冻结）

目标：冻结可复现数据版本，覆盖 `D-main/D-recovery/D-hitl` 三类并保证追溯链。

验收点：

1. 三类数据集可复现生成。
2. 样本追溯链完整（`task_id/event_id/pending_action_id`）。
3. 满足 #171 最小样本量要求。

### 2.3 #171（A0-A6 纵向实验与机制增量归因）

目标：按 A0-A6 路径执行并输出可复现指标与机制归因证据。

验收点：

1. A0->A6 指标链路完整可复现。
2. 每个机制增量有对应指标变化证据。
3. 达到离线门槛或明确未达标项与原因。

## 3. 执行环境与远程模型接入

### 3.1 远程 ProtGPT2 访问

本地通过 SSH 隧道访问远程 GPU 服务：

```bash
ssh -fNT -L 8100:127.0.0.1:8100 autodl
```

本地访问地址：

- `http://127.0.0.1:8100/predict`
- `http://127.0.0.1:8100/job/{job_id}`
- `http://127.0.0.1:8100/results/{job_id}`

### 3.2 代码侧远程调用能力

本轮已补齐并测试通过：

- `RESTModelInvocationService` 支持默认请求头透传；
- `ProtGPT2Adapter` 支持：
  - `PLM_REST_BASE_URL` 覆盖 base_url；
  - `PLM_REST_API_TOKEN` + provider auth header 模板；
  - provider timeout 读取。

相关单测：`tests/unit/test_remote_model_service.py`、`tests/unit/test_protgpt2_adapter.py`。

## 4. 实验流程与命令

### 4.1 #169 计划冻结

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/freeze_w12_issue169_plan.py \
  --config configs/experiments/w12_issue169_plan_freeze.json \
  --output-root output/experiment/w12-expr-0
```

### 4.2 #170 数据冻结（挂接 #169 索引校验）

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/freeze_w12_issue170_data.py \
  --gated-samples-path output/experiment/w12-expr-1/_gen_stage_remote/w11-data-2/gated_samples.jsonl \
  --quality-report-path output/experiment/w12-expr-1/_gen_stage_remote/w11-data-2/quality_gate_report.json \
  --output-root output/experiment/w12-expr-1 \
  --freeze-id issue170-remote-batch3-20260316 \
  --time-window-start 2026-03-16T00:00:00+08:00 \
  --time-window-end 2026-03-18T23:59:59+08:00 \
  --plan-index-path output/experiment/w12-expr-0/w12-midterm-experiment-plan-freeze-20260315T171144Z/execution_plan_index.json
```

### 4.3 #171 全量纵向执行 + 评估（A0-A6, repeats=3）

```bash
UV_CACHE_DIR=/tmp/uv-cache PLM_REST_BASE_URL=http://127.0.0.1:8100 \
uv run python scripts/run_w12_vertical_issue171.py \
  --config configs/experiments/w12_issue171_vertical_a0_a6.json \
  --run-id issue171-remote-batch3-r3

UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/evaluate_w12_vertical_issue171.py \
  --run-manifest-path output/experiment/w12-expr-2/issue171-remote-batch3-r3/runs_manifest.json
```

## 5. 产物路径

### 5.1 #169

- `output/experiment/w12-expr-0/w12-midterm-experiment-plan-freeze-20260315T171144Z/execution_plan_index.json`
- `output/experiment/w12-expr-0/w12-midterm-experiment-plan-freeze-20260315T171144Z/execution_plan_index.md`

### 5.2 #170

- `output/experiment/w12-expr-1/issue170-remote-batch3-20260316/dataset_manifest.json`
- `output/experiment/w12-expr-1/issue170-remote-batch3-20260316/d_main.jsonl`
- `output/experiment/w12-expr-1/issue170-remote-batch3-20260316/d_recovery.jsonl`
- `output/experiment/w12-expr-1/issue170-remote-batch3-20260316/d_hitl.jsonl`
- `output/experiment/w12-expr-1/issue170-remote-batch3-20260316/dataset_index.jsonl`

### 5.3 #171

- `output/experiment/w12-expr-2/issue171-remote-batch3-r3/runs_manifest.json`
- `output/experiment/w12-expr-2/issue171-remote-batch3-r3/run_log_index.csv`
- `output/experiment/w12-expr-2/issue171-remote-batch3-r3/vertical_metrics_summary.csv`
- `output/experiment/w12-expr-2/issue171-remote-batch3-r3/mechanism_increment_deltas.csv`
- `output/experiment/w12-expr-2/issue171-remote-batch3-r3/patch_replan_breakdown.csv`
- `output/experiment/w12-expr-2/issue171-remote-batch3-r3/offline_gate_assessment.json`
- `output/experiment/w12-expr-2/issue171-remote-batch3-r3/abnormal_samples.jsonl`
- `output/experiment/w12-expr-2/issue171-remote-batch3-r3/vertical_report.md`

## 6. 关键结果

### 6.1 #169 结果

- 拓扑序：`169 -> 170 -> 171 -> 172 -> 173 -> 174`
- 无循环依赖（脚本校验通过）
- 关键路径：`169 -> 170 -> 171 -> 174`（9 天）
- 可并行候选：
  - `171 + 172`（03-19~03-20）
  - `171 + 173`（03-20）
  - `172 + 173`（03-20）

### 6.2 #170 结果

- `downstream_ready.ready = true`
- 样本量：
  - `D-main = 14`（门槛 12）
  - `D-recovery = 10`（门槛 8）
  - `D-hitl = 24`（门槛 8）
- 追溯率：
  - 三类数据 `task_id_rate=1.0`
  - 三类数据 `event_id_rate=1.0`
  - `D-hitl pending_action_id_rate=1.0`（门槛 0.95）
- 与 #169 对齐：`plan_validation.checked = true`

### 6.3 #171 结果

- 全量运行规模：`7 groups * 4 tasks * 3 repeats = 84 runs`
- 状态分布：
  - `FAILED = 36`（A0/A1/A2 各 12）
  - `WAITING_PLAN_CONFIRM = 48`（A3/A4/A5/A6 各 12）
- 指标与 CI：已在 `vertical_metrics_summary.csv`、`mechanism_increment_deltas.csv` 给出。
- 机制增量证据：A0->A6 各相邻组差分已输出（含 CI）。
- 离线门槛判定：
  - `schema_valid_rate` 达标；
  - `executable_plan_rate` 仅 A3-A6 达标；
  - `patch_minimality_hit_rate` 与 `suffix_replan_prefix_preservation_rate` 在多组出现 `missing_value`，未达门槛。

## 7. 验收对照结论

### 7.1 #169

- [x] 开始/结束时点完整
- [x] 依赖无环
- [x] 数据优先在关键路径前段

结论：满足 #169 验收要求。

### 7.2 #170

- [x] 三类数据可复现
- [x] 追溯链完整
- [x] 下游样本量门槛达标

结论：满足 #170 验收要求，并可直接供 #171 消费。

### 7.3 #171

- [x] A0-A6 链路完整可复现（清单、配置快照、日志索引齐全）
- [x] 机制增量证据已产出（含差分与 CI）
- [x] 离线门槛结果明确，并给出未达标原因

结论：满足 #171 验收描述中的“达标或明确未达标原因”要求。

## 8. 风险与后续建议

1. 当前 A3-A6 大量停在 `WAITING_PLAN_CONFIRM`，建议增设批量决策回放脚本形成闭环 DONE 样本，以增强效果指标解释力。
2. `patch_minimality_hit_rate` 与 `suffix_replan_prefix_preservation_rate` 出现 `missing_value`，需补充触发相应机制的任务集，避免统计空洞。
3. 建议在 #171 后追加一次 “闭环补跑”（同 freeze_id），并更新增量差分表用于 #174 图表定稿。

## 9. 可复现实验清单

1. 准备远程 ProtGPT2 服务，并建立本地隧道 `127.0.0.1:8100`。
2. 执行 #169 freeze。
3. 执行 #170 freeze（带 `--plan-index-path`）。
4. 执行 #171 run + evaluate。
5. 使用 `runs_manifest.json` 与 `dataset_manifest.json` 作为唯一版本追踪入口。

## 10. 测试记录

执行命令：

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest \
  tests/unit/test_freeze_w12_issue169_plan.py \
  tests/unit/test_freeze_w12_issue170_data.py \
  tests/unit/test_w12_vertical_experiment.py \
  tests/unit/test_remote_model_service.py \
  tests/unit/test_protgpt2_adapter.py
```

结果：`32 passed`。
