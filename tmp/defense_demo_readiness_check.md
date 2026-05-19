# 答辩演示方案问题覆盖与执行清单

更新时间：2026-05-17

依据文件：`tmp/defense_full_flow_demo_design.md`

## 1. 四个问题覆盖情况

| 问题 | 当前方案是否能回答 | 结论 |
|---|---|---|
| 1. 梳理当前系统验证流程，确认需要展示的核心功能链路 | 能 | 已覆盖输入解析、Dashboard、HITL、FSM、事件时间线、报告、结构查看器、readiness、runtime state。 |
| 2. 检查试验脚本是否能从干净环境或固定目录稳定运行 | 能 | `/demo/defense-full-flow` 已实现；启动服务后通过 seed endpoint 注入固定任务。当前已有 `run_demo.py` 和 `run_hitl_candidate_ui_demo.py` 仍可作为临时备份。 |
| 3. 固定输入样例、输出结构截图与日志位置 | 能 | 已固定输入样例、PDB/报告/日志路径；截图目录固定为 `output/demo/defense-full-flow/screenshots/`，seed 时会创建。 |
| 4. 记录可能会被老师追问的试验指标、异常案例与解释口径 | 能 | 已记录 84-run 真实实验口径、demo fixture 边界、不可宣称真实推理、不可宣称成功率显著提升。 |

总体判断：方案已进入可运行实现阶段；剩余工作是录制/截图和可选的浏览器自动截图脚本。

## 2. 需要展示的核心功能链路

建议答辩只展示一条主线：

```text
自然语言/结构化任务输入
  -> 任务状态与字段确认
  -> 计划和候选生成
  -> 高代价步骤前进入 WAITING_PATCH_CONFIRM
  -> PendingAction 候选比较
  -> 人工 Decision
  -> 执行恢复/继续
  -> DesignResult 和报告
  -> PDB 三维结构查看
  -> EventLog 时间线审计
  -> 离线实验矩阵结果收束
```

核心页面：

```text
/ui
/ui/task-builder
/ui/tasks/demo_defense_hitl
/ui/tasks/demo_defense_done
/ui/tasks/demo_defense_done/events
```

核心功能点：

- Task Builder：展示输入解析和结构化字段。
- Dashboard：展示任务列表、状态扫描、待决策入口。
- Task Detail：展示任务快照、状态、pending action、报告、结构。
- Pending Review：展示候选排序、默认推荐、risk、cost、score breakdown、tool readiness。
- Structure Viewer：展示 PDB 加载、旋转、缩放、点击原子。
- Report Explorer：展示 scores、objective scoring、structure similarity。
- Event Timeline：展示 `WAITING_ENTER -> DECISION_APPLIED -> WAITING_EXIT -> DONE`。

## 3. 可运行脚本清单

### 3.1 当前已经存在、可作为备份的脚本

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/run_demo.py --port 8000 --no-smoke-test
```

作用：启动 API + React 工作台。适合现场备用。

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/run_demo.py --port 8000 --exit-after-smoke
```

作用：执行一次 API smoke，检查 `/health`、`POST /tasks`、事件日志是否生成。

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python examples/run_hitl_candidate_ui_demo.py
```

作用：进程内预览 HITL 候选数据，不启动浏览器服务。

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python examples/run_hitl_candidate_ui_demo.py --serve --port 8012
```

作用：启动当前已有的 HITL 候选对比 UI demo。

### 3.2 答辩 fixture 入口

```bash
PROTEIN_ENABLE_DEMO_FIXTURES=1 \
UV_CACHE_DIR=/tmp/uv-cache \
uv run python scripts/run_demo.py --port 8000 --no-smoke-test
```

作用：启动答辩 fixture 模式。

```bash
curl -X POST http://127.0.0.1:8000/demo/defense-full-flow
```

作用：注入 `demo_defense_intake`、`demo_defense_hitl`、`demo_defense_done` 三个固定任务。

可选新增一个封装脚本：

```text
scripts/seed_defense_full_flow_demo.py
```

如果新增，它应通过 HTTP 调用 `/demo/defense-full-flow`，不要尝试直接修改另一个 API 进程内的 `TASK_STORE`。

### 3.3 建议实现后的验收命令

```bash
PROTEIN_ENABLE_DEMO_FIXTURES=1 \
UV_CACHE_DIR=/tmp/uv-cache \
uv run pytest tests/api/test_defense_demo_fixture.py -q
```

建议覆盖：

- demo endpoint 未启用时返回 404。
- demo endpoint 启用后返回三个 task id。
- `demo_defense_hitl` 处于 `WAITING_PATCH_CONFIRM`。
- `demo_defense_hitl` 带 `patch_confirm` pending action。
- `demo_defense_done` 带 report、structure、events。
- `demo_defense_done/events` 包含 `WAITING_ENTER`、`DECISION_APPLIED`、`WAITING_EXIT`、`DONE`。

## 4. 固定输入样例

推荐固定输入：

```text
请评估一个 TRP-cage-like 短肽序列的稳定性，优先使用低成本结构预测路径，并在高代价步骤前展示候选方案给人工确认。
```

固定结构化字段：

```json
{
  "task_kind": "sequence_evaluation",
  "objective_type": "stability",
  "sequence": "NLYIQWLKDGGPSSGRPPPS",
  "length_range": [18, 32],
  "budget_policy": "low_cost_first",
  "runtime_policy": "lite_belief_state",
  "requires_human_review": true,
  "prefer_remote": false
}
```

固定候选：

| candidate_id | 含义 | risk | cost | score |
|---|---|---:|---:|---:|
| `patch_local_openfold` | 本地结构预测替代远程服务，默认推荐 | low | low | 0.86 |
| `suffix_replan_low_cost` | 改用低成本后缀重规划 | low | medium | 0.78 |
| `patch_remote_retry` | 继续重试远程 OpenFold3 REST | medium | high | 0.71 |

## 5. 试验结果目录

### 5.1 答辩 fixture 结果目录

建议新增并固定：

```text
output/demo/defense-full-flow/
```

建议产物：

```text
output/demo/defense-full-flow/demo_defense_done.pdb
output/demo/defense-full-flow/demo_defense_done_report.json
output/demo/defense-full-flow/demo_defense_manifest.json
output/demo/defense-full-flow/screenshots/dashboard.png
output/demo/defense-full-flow/screenshots/task_builder.png
output/demo/defense-full-flow/screenshots/hitl_candidates.png
output/demo/defense-full-flow/screenshots/structure_viewer.png
output/demo/defense-full-flow/screenshots/event_timeline.png
```

事件日志：

```text
data/logs/demo_defense_intake.jsonl
data/logs/demo_defense_hitl.jsonl
data/logs/demo_defense_done.jsonl
```

### 5.2 当前已有 demo 证据目录

```text
output/demo/w12-issue-151/
```

可引用文件：

```text
output/demo/w12-issue-151/release-validation.md
output/demo/w12-issue-151/replay-record-001-six-stage-hitl.md
output/demo/w12-issue-151/replay-record-002-tool-fallback.md
```

### 5.3 当前已有最终实验结果目录

```text
output/experiment/thesis-final-matrix/thesis-final-v1-001/
```

核心文件：

```text
output/experiment/thesis-final-matrix/thesis-final-v1-001/matrix_report.md
output/experiment/thesis-final-matrix/thesis-final-v1-001/matrix_metrics_summary.csv
output/experiment/thesis-final-matrix/thesis-final-v1-001/action_distribution.csv
output/experiment/thesis-final-matrix/thesis-final-v1-001/high_cost_breakdown.csv
output/experiment/thesis-final-matrix/thesis-final-v1-001/abnormal_samples.csv
output/experiment/thesis-final-matrix/thesis-final-v1-001/offline_gate_assessment.json
output/experiment/thesis-final-matrix/thesis-final-v1-001/run_log_index.csv
output/experiment/thesis-final-matrix/thesis-final-v1-001/runs_manifest.json
```

论文级总结文件：

```text
docs/experiment/thesis-final-v1-results.md
```

## 6. 老师可能追问的指标与回答口径

### 6.1 问：这个现场演示是不是实时跑了模型？

答：

```text
不是。现场演示为了稳定性使用本地确定性 fixture，不调用远程 LLM、PLM REST 或 OpenFold3 REST。它展示的是系统交互、FSM、HITL、结构查看和审计链路。真实实验结果已离线完成并保存在 thesis-final-v1-001 目录。
```

### 6.2 问：真实实验规模是多少？

答：

```text
最终主实验 thesis-final-v1-001 覆盖 12 个 task key、4 组策略、84 次运行，81 次 DONE，完成率 96.4%。每组 21 次运行。
```

### 6.3 问：哪组成功率最好？

答：

```text
static_top1 在该矩阵中成功率为 100%，其他三组为 95.2%。因此我不会声称 CEBRA-WP 显著提升最终成功率。它的主要价值体现在运行时可观测、恢复决策、高代价调用控制和审计解释。
```

### 6.4 问：CEBRA-WP 的证据在哪里？

答：

```text
lite_belief_state 组的 runtime_state_observable_rate 为 1.0，说明 21 次运行都产生了 runtime state 和 action utility。fixed_threshold_gate 触发了 6 次 patch，说明恢复控制链可观测。高代价调用方面，fixed 组 high_cost_mean 为 1.333，而 dynamic/lite 为 0.952。
```

### 6.5 问：为什么 fixed 组高代价调用更多？

答：

```text
fixed_threshold_gate 是运行时拦截后再 patch，因此会产生额外结构预测调用。lite_belief_state 更偏预防性 rerank，减少进入 patch 的机会，但当前结果仍不能证明它提升最终成功率。
```

### 6.6 问：失败案例是什么？

答：

```text
84 次运行中有 3 次 FAILED。一个是 fixed_threshold_gate 在 t2_ubiquitin 上进入 patch 循环直到 auto decision loop exhausted；一个是 lite_belief_state 在同类任务上也出现 patch 循环；一个是 dynamic_no_belief_state 在 t3_gb1 上触发 CANDIDATE_IO_CLOSURE_BROKEN。它们分别说明固定门控的循环风险、belief-state 仍需更强升级策略、以及候选 I/O 校验能阻止不可执行计划进入执行。
```

### 6.7 问：安全边界有没有真实触发？

答：

```text
t8 矩阵任务没有形成阻断统计，这是实验输入没有把 forbidden motif 传入实际 step metadata 的问题，不是安全机制完全缺失。SafetyAgent 和 StepRunner 层已有确定性 focused tests 覆盖 block/warn。
```

### 6.8 问：为什么不现场跑 84 次实验？

答：

```text
完整主实验约 6 小时，且涉及高代价工具和远程服务。答辩现场应展示可复现交互和证据链，真实实验结果用冻结产物和报告说明。
```

## 7. 展示用说明要点

5 分钟讲法压缩版：

1. 系统定位：这是蛋白质设计场景下的 LLM 多智能体工作流系统，不是单次模型调用。
2. 入口能力：任务输入会收敛到结构化字段，包括 sequence、objective、budget 和 runtime policy。
3. 控制能力：系统在高代价步骤前进入 `WAITING_PATCH_CONFIRM`，生成 `PendingAction`，等待人类决策。
4. 候选解释：候选按 score、risk、cost、readiness 和 runtime state 排序，默认推荐可解释。
5. 恢复链路：人工接受 patch 后，系统继续执行，最后进入 `DONE`。
6. 结果展示：`DesignResult` 包含序列、PDB、评分、报告和风险标记；结构查看器可直接加载 PDB。
7. 审计能力：事件时间线记录从创建、规划、等待、决策、恢复到完成的完整链路。
8. 实验证据：真实主实验是 84 runs，81 DONE；CEBRA-WP 的主要证据是 runtime state 可观测、patch/recovery 可审计、高代价调用控制，而不是成功率显著提升。

## 8. 后续收口项

优先级从高到低：

1. 手工启动服务并检查四个页面和结构查看器 canvas。
2. 截图保存到 `output/demo/defense-full-flow/screenshots/`。
3. 录制 5 分钟视频。
4. 可选新增 Playwright 自动截图脚本。
