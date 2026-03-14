# Issue #170 实施文档：真实实验数据快采与版本冻结（D-main / D-recovery / D-hitl）

- Issue: https://github.com/Yuri-Kon/thesis-project/issues/170
- 分支：`w12-expr-1/d-main`
- 文档状态：Draft v1
- 更新时间（本地）：2026-03-14

## 1. 背景与目标

本实现对应 Issue #170，目标是在 **2026-03-16 到 2026-03-18** 执行窗口内，形成可复现、可追溯的数据快照与版本冻结，覆盖三类数据集：

- D-main：六阶段主路径样本
- D-recovery：失败/恢复压力样本
- D-hitl：plan/patch/replan 人机决策样本

本阶段交付聚焦“数据与版本”，不输出最终实验对比结论。

## 2. 前置条件与执行边界

- Hard blocked by #169（Issue 当前状态：OPEN，检查时间 2026-03-14）。
- 满足硬依赖后可执行本计划；#145/#146/#157/#158 作为软同步，不阻塞开工。
- 本文仅定义数据实现规则与落盘规范，不修改 FSM、Agent 角色边界与执行语义。

## 3. 数据源与落盘位置

### 3.1 原始数据源

- EventLog：`data/logs/*.jsonl`
- Snapshot：`data/snapshots/*.jsonl`
- 结果与指标：`output/reports/*.json`、`output/metrics/*.json`、`output/pdb/*.pdb`

### 3.2 目标落盘目录（冻结产物）

统一落盘到：`output/experiment/w12-expr-1/`

每次冻结生成一个 `freeze_id` 子目录：

- `output/experiment/w12-expr-1/<freeze_id>/d-main/`
- `output/experiment/w12-expr-1/<freeze_id>/d-recovery/`
- `output/experiment/w12-expr-1/<freeze_id>/d-hitl/`
- `output/experiment/w12-expr-1/<freeze_id>/manifest.json`

## 4. 数据集定义（采样口径）

## 4.1 D-main（六阶段主路径）

纳入规则：

- 任务维度：`task_[0-9a-f]{8}` 命名任务。
- 路径要求：任务事件中可重建主路径：`CREATED -> PLANNING -> PLANNED -> RUNNING -> SUMMARIZING -> DONE`。
- 产物要求：同一 `task_id` 能关联至少一份 report（`output/reports/<task_id>.json`）。

排除规则：

- 命中 `task_decision_*`、`task_demo_*` 的演示/决策专用任务。
- 无法完成路径重建或无对应 report 的任务。

## 4.2 D-recovery（失败/恢复压力）

纳入规则（至少命中其一）：

- EventLog 出现失败/阻断相关记录（如 `failure_type` 非空、失败类 event_type）。
- 存在恢复转移链（如 WAITING/阻断状态回到可执行状态）。
- 存在 patch/replan 驱动的恢复证据（含决策与状态迁移）。

强制追溯字段：

- `task_id`
- `event_id`（映射 EventLog 字段 `id`）
- `pending_action_id`（若该条记录属于等待/决策链路则必填）
- `snapshot_id`（若有 Snapshot 关联）

## 4.3 D-hitl（plan/patch/replan 决策）

纳入规则：

- EventLog 包含 `DECISION_SUBMITTED` + `DECISION_APPLIED` 成对事件。
- 覆盖决策类型：`plan_confirm`、`patch_confirm`、`replan_confirm`（若系统无显式 `replan_confirm`，以 replan 决策路径映射并在 manifest 备注）。
- 每条样本必须可回溯到对应 `pending_action_id` 与（若存在）候选 `selected_candidate_id`。

## 5. 追溯链规范（Task / Event / Snapshot）

统一追溯主键：

- `task_id`：任务主键
- `event_id`：EventLog `id` 字段（无 `id` 时回退为 `task_id:line_no`）
- `snapshot_id`：Snapshot `snapshot_id` 字段
- `pending_action_id`：等待/决策链路主键

最小可追溯链：

- `task_id -> event_id -> pending_action_id -> snapshot_id(可选)`

校验要求：

- D-hitl 样本 `pending_action_id` 非空率应为 100%。
- D-recovery 样本若来自 WAITING/决策恢复链，`pending_action_id` 非空率应为 100%。

## 6. 版本冻结与命名规则

`freeze_id` 命名：

- `w12e1-<yyyymmdd>-<git_short_sha>-r<nn>`
- 示例：`w12e1-20260316-a1b2c3d-r01`

版本元数据（manifest 必填）：

- `freeze_id`
- `generated_at`
- `git_commit`
- `time_window`（固定记录：`2026-03-16` 到 `2026-03-18`）
- `source_roots`（data/logs, data/snapshots, output/reports, output/metrics）
- `dataset_counts`（D-main / D-recovery / D-hitl）
- `coverage`（事件类型覆盖、决策类型覆盖、追溯字段完整率）
- `gaps`（缺口及补齐计划）

## 7. 切分规则与去重规则

## 7.1 切分规则

按 `task_id` 做稳定哈希切分，避免同任务泄漏到多个 split：

- train: 70%
- val: 15%
- test: 15%

实现建议：

- `bucket = sha1(task_id) % 100`
- `0-69 => train, 70-84 => val, 85-99 => test`

## 7.2 去重规则

事件级去重键：

- `(task_id, event_id)`；若 `event_id` 缺失则 `(task_id, event_type/event, ts, line_no)`

快照级去重键：

- `(task_id, snapshot_id)`

决策级去重键：

- `(task_id, pending_action_id, decision_id)`

冲突保留策略：

- 优先保留字段更完整记录；完整度相同时保留 `ts`/`created_at` 最新记录。

## 8. 验收口径（对应 Issue #170）

满足以下条件才可勾选完成：

- 三类数据集均可按固定命令复现。
- 样本追溯链完整（`task_id` / `event_id` / `pending_action_id`）。
- 产出 manifest，包含版本、时间窗、覆盖率与缺口。
- 达到后续纵向/横向实验的最小样本量（阈值在执行日与导师确认后写入 manifest）。

## 9. 当前基线盘点（截至 2026-03-14，本地仓库）

- EventLog 文件：36
- D-main 候选任务：32（`task_[0-9a-f]{8}`）
- D-hitl 候选任务：4（`task_decision_accept_plan`、`task_decision_cancel`、`task_decision_replan`、`task_demo_142`）
- Snapshot 文件：4
- 事件总量：258
- 已带 `pending_action_id` 记录：52
- 已带 `id`（可映射 event_id）记录：26
- 失败类显式记录（`state/to_status/new_status == FAILED`）：0

当前缺口：

- D-recovery 中“失败后恢复”压力样本不足（当前未见 FAILED 显式事件），需在执行窗口内补齐故障注入或失败恢复样本。

## 10. 执行清单（开工即用）

- [ ] 确认 #169 已解除硬阻塞。
- [ ] 按本口径采集 D-main / D-recovery / D-hitl 样本并落盘到 `output/experiment/w12-expr-1/<freeze_id>/`。
- [ ] 生成并校验 `manifest.json`。
- [ ] 复核追溯链完整率与缺口说明。
- [ ] 将 freeze_id 与样本统计回填到 issue #170。
