# W12 Issue #169/#170 联合实施文档：时间排程冻结 + 数据快采版本冻结

- Issues:
  - #169: https://github.com/Yuri-Kon/thesis-project/issues/169
  - #170: https://github.com/Yuri-Kon/thesis-project/issues/170
- 分支：`w12-expr-timeline`
- 文档状态：Draft v2（在原 `issue-170-data-snapshot-freeze-plan.md` 基础上扩展并重命名）
- 更新时间（本地）：2026-03-14
- 覆盖执行窗口：
  - #169：2026-03-16 至 2026-03-22
  - #170：2026-03-16 至 2026-03-18

## 1. 目标与边界

本联合文档用于一次性落实两个 issue 的执行口径：

- #169：冻结 W12 中期实验时间计划、依赖链、并行策略与关键路径。
- #170：完成 D-main / D-recovery / D-hitl 数据快采与版本冻结，作为后续 #171/#172/#173 的统一输入基线。

非目标：

- 不新增算法功能；
- 不调整 FSM、Agent 角色边界、`retry -> patch -> replan` 契约；
- 不替代 #171/#172/#173/#174 的具体实验与报告产出。

## 2. 依赖链与参考 Issue（用于 #169 排程）

## 2.1 硬依赖链（Hard blocked by）

- `#169` 无硬阻塞，可立即启动。
- `#170` 硬依赖 `#169`。
- `#171`/`#172` 硬依赖 `#170`。
- `#173` 硬依赖 `#170` + `#144`。
- `#174` 硬依赖 `#171` + `#172` + `#173`。
- `#152` 硬依赖 `#149` + `#150` + `#151` + `#174`。

关键路径（Data 优先）：

`#169 -> #170 -> (#171/#172/#173) -> #174 -> #152`

结论：当前依赖关系可构成有向无环链路，无循环阻塞。

## 2.2 软同步链（Soft sync，需在执行中对齐）

- #169 soft sync：#170/#171/#172/#173/#174。
- #170 soft sync：#145/#146/#157/#158。
- 对 #170 的直接参考用途：
  - #145：抽取链路与样本映射字段（`context/candidates/selected/outcome/audit_trace`）。
  - #146：schema/缺失/去重/切分门禁规则。
  - #157：S3 质量门禁样本与拒绝码来源。
  - #158：S4 精修闭环样本与迭代 lineage 来源。
- 对 #169 的下游消费：
  - #171/#172 使用 #170 冻结版本作为统一输入；
  - #173 复用同一版本做审计链完整性核验；
  - #174/#152 复用证据索引与口径。

## 3. 时间排程冻结（#169 验收映射）

## 3.1 每日计划与产出（2026-03-16 至 2026-03-22）

| 日期 | 执行重点 | 对应 Issue | 当日产出（必须落盘） | 退出门槛 |
| --- | --- | --- | --- | --- |
| 2026-03-16 | 冻结分组与依赖，启动数据快采 | #169, #170 | 冻结版排程表、依赖图、`freeze_id` 首版目录 | #170 可开工且口径不再变更 |
| 2026-03-17 | D-main / D-recovery / D-hitl 采样与门禁 | #170, #145, #146 | 三类数据子集 + 质量报告 + 缺口清单 | 三类集均可复现重建 |
| 2026-03-18 | 数据冻结收口，发布 manifest | #170 | `manifest.json`（版本/覆盖/缺口/追溯率） | #171/#172/#173 输入版本锁定 |
| 2026-03-19 | 纵向主点 + 横向启动 | #171, #172 | A0/A2/A4/A6 首轮结果，E0/E1/E2 启动记录 | 指标口径一致 |
| 2026-03-20 | 补机制增量 + 横向收口 + 治理核验启动 | #171, #172, #173 | A1/A3/A5 + 横向结果 + 治理中间表 | 统计输入完整 |
| 2026-03-21 | 治理复核与审计回放样例 | #173, #151 | 审计链样例、失败追溯率统计 | 治理指标可复算 |
| 2026-03-22 | 汇总实验章节与证据索引 | #174 | 图表包与证据索引初稿 | 可并入 #152 |

## 3.2 不可并行项（#169 要求）

- 未完成 #169 的时间与依赖冻结前，不允许开始 #170 正式 freeze。
- 同一 `freeze_id` 一旦标记发布，不允许追加样本；新增样本必须升 `rNN`。
- #171/#172/#173 必须基于同一冻结版本输入，不得混用不同 `freeze_id`。
- #174 只能在 #171/#172/#173 均完成后启动正式汇总。

## 3.3 可并行项（在门槛内允许）

- #170 内部可并行：D-main 与 D-hitl 抽取、统计、去重。
- D-recovery 的故障注入样本生成可与 D-main 同时进行，但发布前统一进入同一门禁。
- #171 与 #172 可并行执行，但必须共享 #170 冻结输入与统一预算口径。

## 4. 数据快采与冻结细则（#170 执行规范）

## 4.1 数据源与目标目录

原始数据源：

- EventLog：`data/logs/*.jsonl`
- Snapshot：`data/snapshots/*.jsonl`
- 结果与指标：`output/reports/*.json`、`output/metrics/*.json`、`output/pdb/*.pdb`

冻结目录：`output/experiment/w12-expr-1/<freeze_id>/`

- `d-main/`
- `d-recovery/`
- `d-hitl/`
- `manifest.json`
- `quality-gate-report.json`（建议新增，承接 #146）
- `evidence-index.json`（建议新增，供 #173/#174/#152）

## 4.2 三类数据集纳入规则

### D-main（六阶段主路径）

纳入：

- 任务可重建路径：`CREATED -> PLANNING -> PLANNED -> RUNNING -> SUMMARIZING -> DONE`。
- 同 `task_id` 可关联至少一份 report（`output/reports/<task_id>.json`）。

排除：

- `task_decision_*`、`task_demo_*` 等演示型任务；
- 路径不完整或报告缺失任务。

### D-recovery（失败/恢复压力）

纳入命中任一：

- 失败/阻断事件（`failure_type` 或等效失败标记）；
- WAITING/决策回流到 RUNNING 的恢复链；
- patch/replan 驱动恢复证据。

强制追溯字段：`task_id`、`event_id`、`pending_action_id`（若属决策链）、`snapshot_id`（若存在）。

### D-hitl（plan/patch/replan 决策）

纳入：

- `DECISION_SUBMITTED` + `DECISION_APPLIED` 成对事件；
- 覆盖 `plan_confirm`、`patch_confirm`、`replan_confirm` 三类；
- 可追溯 `pending_action_id` 与（若存在）`selected_candidate_id`。

## 4.3 追溯链与兼容性约束

统一主键：

- `task_id`
- `event_id`（优先 EventLog `id`；缺失时回退 `task_id:line_no`）
- `pending_action_id`
- `snapshot_id`

最小追溯链：

`task_id -> event_id -> pending_action_id -> snapshot_id(可选)`

完整率门槛：

- D-hitl 的 `pending_action_id` 非空率 = 100%。
- D-recovery 中 WAITING/决策恢复样本的 `pending_action_id` 非空率 = 100%。
- 与 #144 / #173 对齐：失败样本应可定位 `step_id + tool_id + failure_code`（字段缺失必须在 `gaps` 说明）。

## 4.4 切分与去重（与 #146 对齐）

切分：按 `task_id` 稳定哈希，避免同任务泄漏到多个 split。

- train: 70%
- val: 15%
- test: 15%

去重键：

- 事件级：`(task_id, event_id)`；若缺失则 `(task_id, event_type/event, ts, line_no)`
- 快照级：`(task_id, snapshot_id)`
- 决策级：`(task_id, pending_action_id, decision_id)`

冲突保留：字段更完整优先；完整度相同时保留时间戳更新者。

## 4.5 freeze_id 与版本命名

命名规则：`w12e1-<yyyymmdd>-<git_short_sha>-r<nn>`

示例：`w12e1-20260316-a1b2c3d-r01`

发布规则：

- 修订仅允许 `rNN` 递增；
- 同一 `freeze_id` 不可变更内容（冻结语义）；
- `manifest.json` 必须记录上游依赖状态快照（至少 #169、#145、#146、#157、#158）。

## 4.6 manifest 字段基线（v2）

必填：

- `freeze_id`
- `generated_at`
- `git_commit`
- `time_window`（固定：`2026-03-16` 至 `2026-03-18`）
- `source_roots`
- `dataset_counts`
- `split_counts`
- `coverage`（事件类型、决策类型、追溯字段完整率）
- `quality_gate`（通过率、缺失率、重复率）
- `dependency_snapshot`（#169/#145/#146/#157/#158 状态快照）
- `downstream_ready`（是否满足 #171/#172/#173 最小输入）
- `gaps`（缺口与补齐计划）

建议新增：

- `tool_coverage_matrix`（承接 #145/#146 Requirement-2 工具字段）
- `evidence_index_refs`（指向 #173/#174 证据文件）

## 5. #169 与 #170 验收对齐清单

## 5.1 Issue #169 清单映射

- [ ] 固化 2026-03-16 ~ 2026-03-22 节奏与每日产出（见 3.1）。
- [ ] 明确实验 issue 的 blocked-by 依赖链（见 2.1/2.2）。
- [ ] 形成不可并行 / 可并行清单（见 3.2/3.3）。
- [ ] 建立执行顺序 Data -> Vertical/Horizontal -> Governance -> Report（见 2.1 + 3.1）。

## 5.2 Issue #170 清单映射

- [ ] D-main 采样与落盘。
- [ ] D-recovery 压力样本采样与标注。
- [ ] D-hitl 决策样本补齐。
- [ ] 发布 manifest（版本、时间窗、覆盖率、缺口）。
- [ ] 确认三类数据可复现、可追溯、可供 #171/#172/#173 直接消费。

## 6. 当前基线盘点（2026-03-14）

已观察到的本地基线：

- EventLog 文件：36
- D-main 候选任务：32（`task_[0-9a-f]{8}`）
- D-hitl 候选任务：4（`task_decision_accept_plan`、`task_decision_cancel`、`task_decision_replan`、`task_demo_142`）
- Snapshot 文件：4
- 事件总量：258
- 含 `pending_action_id` 记录：52
- 含 EventLog `id` 记录：26
- 显式 `FAILED` 转移记录：0

已识别缺口：

- D-recovery 的“失败后恢复”覆盖不足；需要在 2026-03-16 至 2026-03-18 执行窗口内补齐故障注入/失败恢复样本。

## 7. 执行与回填要求

- 每次 freeze 完成后，将以下信息回填到 #169、#170：
  - `freeze_id`
  - 三类数据量与追溯完整率
  - 质量门禁摘要
  - 缺口与下一步补齐计划
- #171/#172/#173 启动时，必须引用同一个 `freeze_id`。
- #174 汇总时，必须引用 `evidence-index.json`，确保“指标 -> 日志 -> 配置 -> 产物”可追溯。

## 8. 契约一致性声明

本实施文档仅涉及实验排程与数据资产冻结，不引入系统语义变更：

- 不新增 FSM 状态；
- 不改变 Planner/Executor/Safety/Summarizer 角色边界；
- 不改变 `WAITING_*` 决策所有权；
- 不改变 `retry -> patch -> replan` 顺序。
