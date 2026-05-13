# 系统验证可执行清单

本文档用于支撑论文或项目材料中的“系统测试 / 系统验证”章节。后续执行验证时，可在每个 `SV-*` 用例后补充实际结果、截图路径、接口返回文件、日志路径和结论。

当前集中证据索引见 `docs/system-validation/evidence-index.md`，测试用例汇总见 `docs/system-validation/test-case-table.md`。截至 2026-05-10，已归档 17 张 UI 截图、2 个 API JSON、4 组 pytest focused 日志、4 个 CLI 输出日志，并对已完成 smoke/clean 实验、EventLog、Snapshot、Report 原始产物建立了 `EVD-*` 编号。

## 1. 系统核心功能

| 编号 | 核心功能 | 主要入口 | 期望输出 |
|---|---|---|---|
| F01 | 任务输入与确认 | Web Task Builder、CLI `intake`、API `/task-intakes`、`/tasks` | `TaskIntakeSession`、`ConfirmedTaskSpec`、`TaskRecord` |
| F02 | 计划生成 | `PlannerAgent`、ToolKG、`PlanCandidate` | `Plan` 或 `PendingAction(plan_confirm)` |
| F03 | HITL 人工确认 | `/pending-actions`、`/pending-actions/{id}/decision`、前端 Pending Review | `Decision`、状态转移、事件日志 |
| F04 | FSM 生命周期控制 | `CREATED -> PLANNING -> ... -> DONE/FAILED/CANCELLED` | `TaskRecord.status/internal_status` 一致 |
| F05 | 工具链执行 | `ExecutorAgent`、`PlanRunner`、`StepRunner`、adapter registry | `StepResult`、artifacts、metrics |
| F06 | 安全评估 | `SafetyAgent`、intake safety precheck、运行中 safety events | `allow/warn/block`、risk flags |
| F07 | 失败恢复 | retry -> patch -> replan -> stop | `PendingAction(patch_confirm/replan_confirm)` 或终态 |
| F08 | 快照恢复 | `TaskSnapshot`、`snapshot_store`、recovery | 恢复到 `WAITING_*` 或 `RUNNING` 上下文 |
| F09 | 结果总结 | `SummarizerAgent`、`/tasks/{id}/report` | `DesignResult`、report path、scores |
| F10 | 审计与观测 | `/tasks/{id}/events`、EventLog、timeline | 状态迁移、决策、失败、恢复证据链 |

## 2. 输入、输出与用户角色

### 2.1 输入对象

- 自然语言目标：`goal` / `query`
- 结构化任务：`ConfirmedTaskSpec`
- 约束：`length_range`、`organism`、`sequence`、`safety_level`、预算、工具约束等
- 人工决策：`Decision(choice, selected_candidate_id, decided_by, comment)`
- 工具配置：ToolKG、adapter readiness、远程服务配置

### 2.2 输出对象

- `TaskRecord`
- `Plan` / `PlanPatch`
- `PendingAction`
- `StepResult`
- `SafetyResult`
- `DesignResult`
- `TaskSnapshot`
- `EventLog` / timeline
- API JSON、前端截图、CLI 输出、日志文件

### 2.3 用户角色

| 角色 | 职责 |
|---|---|
| 科研操作员 | 创建任务、确认输入、查看候选、提交人工决策 |
| 审核/导师角色 | 复核风险、成本、工具链、最终报告证据 |
| 系统开发/运维角色 | 启动 API、配置远程模型服务、收集日志与截图 |
| 系统内部 Agent | Planner、Executor、Safety、Summarizer，仅按职责边界工作，不能替代人工确认 |

## 3. 主要业务流程

| 编号 | 流程 | 关键状态/接口 |
|---|---|---|
| P01 | 正常全自动任务：创建任务 -> 规划 -> 执行 -> 总结 -> 完成 | `/tasks`，`CREATED -> PLANNING -> PLANNED -> RUNNING -> SUMMARIZING -> DONE` |
| P02 | 任务输入确认：自由文本 -> intake draft -> 人工确认 -> 创建任务 | `/task-intakes`，`/task-intakes/{id}/confirm` |
| P03 | 初始计划确认：Plan 候选生成 -> 等待人工选择 -> 执行 | `WAITING_PLAN_CONFIRM`，`plan_confirm` |
| P04 | 局部失败修复：步骤失败 -> retry 耗尽 -> Patch 候选 -> 人工确认 | `WAITING_PATCH_CONFIRM`，`patch_confirm` |
| P05 | 整体风险重规划：Safety warn/block 或结构性失败 -> Replan/stop 候选 -> 人工确认 | `WAITING_REPLAN_CONFIRM`，`replan_confirm` |
| P06 | 用户取消：等待态提交 cancel -> 任务终止 | `WAITING_* -> CANCELLED` |
| P07 | 任务失败：恢复耗尽或 terminal stop 接受 -> FAILED | `WAITING_REPLAN_CONFIRM -> FAILED` |
| P08 | 快照恢复：等待态或运行态重启后恢复上下文 | `TaskSnapshot`、EventLog replay |
| P09 | 结果查看：任务详情、报告、timeline、结构产物 | `/tasks/{id}`、`/report`、`/events` |

## 4. 必须验证的功能点

| ID | 验证点 | 覆盖类型 | 建议证据 | 实际证据路径 | 结论 |
|---|---|---|---|---|---|
| SV-01 | `/health`、UI 首页、任务详情页可访问 | 正常流程 | 接口返回、截图 | EVD-API-01、EVD-TEST-01、FIG-SV-01、FIG-SV-02 | 通过 |
| SV-02 | intake schema 能返回字段注册表 | 正常流程 | `/task-intakes/schema` JSON | EVD-TEST-01、EVD-CLI-01 | 通过 |
| SV-03 | 自由文本创建 intake，未确认前不直接执行正式任务 | 正常流程/一致性 | API 返回、EventLog | EVD-TEST-01、EVD-LOG-04 | 通过 |
| SV-04 | 缺失必要字段时 confirm 失败 | 异常输入 | 422/400 响应 | EVD-TEST-01、EVD-TEST-03 | 通过 |
| SV-05 | safety warn 必须显式 acknowledge | 权限/边界 | API 错误与成功对照 | EVD-TEST-03、FIG-SV-10 | 通过 |
| SV-06 | safety block 不允许创建正式任务 | 权限/安全 | 阻断响应 | EVD-TEST-03 | 通过 |
| SV-07 | `/tasks` 三种创建模式互斥：`goal/query/confirmed_task_spec` | 异常输入 | 422 响应 | EVD-TEST-01 | 通过 |
| SV-08 | `PlannerAgent` 只生成候选，不执行工具、不改状态 | 权限/角色边界 | 单测、日志 | EVD-TEST-02、EVD-LOG-04 | 通过 |
| SV-09 | Plan candidate 必须含候选 ID、payload、评分、风险、成本、解释 | 数据一致性 | JSON、单测 | EVD-TEST-02、EVD-LOG-04 | 通过 |
| SV-10 | `WAITING_PLAN_CONFIRM` 必须有 `PendingAction(plan_confirm)` | 正常/HITL | task JSON、pending JSON | EVD-TEST-02、FIG-SV-15 | 通过 |
| SV-11 | accept 决策缺少 `selected_candidate_id` 必须失败 | 异常输入 | 400 响应 | EVD-TEST-02、EVD-TEST-03 | 通过 |
| SV-12 | 已决策的 PendingAction 再次提交必须 409 | 边界/一致性 | 409 响应 | EVD-TEST-02 | 通过 |
| SV-13 | 错误 task/pending_action 绑定必须拒绝 | 权限/一致性 | 400/409 响应 | EVD-TEST-02、EVD-TEST-03 | 通过 |
| SV-14 | 进入任意 `WAITING_*` 前必须写快照和 WAITING_ENTER 日志 | 数据一致性 | snapshot 文件、timeline | EVD-TEST-02、EVD-LOG-01、EVD-LOG-02、EVD-LOG-03 | 通过 |
| SV-15 | 等待态下 Executor 不继续执行工具 | 权限/角色边界 | 无后续 STEP 日志 | EVD-TEST-02 | 通过 |
| SV-16 | 正常执行步骤产生 `StepResult`、metrics、artifacts | 正常流程 | task JSON、日志、产物 | EVD-EXP-01、EVD-TEST-03、EVD-LOG-05 | 通过 |
| SV-17 | 工具 schema/I-O 引用错误必须淘汰候选或失败 | 异常输入 | candidate validation log | EVD-TEST-03 | 通过 |
| SV-18 | retry 耗尽且局部可修时进入 patch_confirm | 恢复流程 | PendingAction、EventLog | EVD-TEST-03、EVD-LOG-01、EVD-LOG-02 | 通过 |
| SV-19 | Patch accept 后只应用所选 Patch 并恢复执行 | 数据一致性 | Plan diff、timeline | EVD-TEST-03、EVD-LOG-01、EVD-LOG-02 | 通过 |
| SV-20 | Patch replan 选择能转为 replan_confirm | 恢复流程 | 新 PendingAction | EVD-TEST-03、EVD-LOG-03、EVD-LOG-04 | 通过 |
| SV-21 | Safety block 禁止 continue，进入 replan/stop 候选 | 安全边界 | SafetyResult、timeline | EVD-TEST-03、EVD-LOG-03 | 通过 |
| SV-22 | Replan accept 保留可保留前缀，后缀替换正确 | 边界/恢复 | snapshot、Plan | EVD-TEST-03、EVD-LOG-03、EVD-LOG-04 | 通过 |
| SV-23 | terminal_stop 候选接受后进入 FAILED | 终态 | TaskRecord、EventLog | EVD-TEST-02、EVD-TEST-03、EVD-LOG-03 | 通过 |
| SV-24 | DONE/FAILED/CANCELLED 终态不可再变更 | 边界/FSM | 单测、API 响应 | EVD-TEST-02、EVD-TEST-03 | 通过 |
| SV-25 | `/tasks/{id}/events` 支持 event/tool/capability 过滤 | 正常/API | JSON 返回 | EVD-TEST-01、EVD-TEST-04、EVD-LOG-04 | 通过 |
| SV-26 | `/tasks/{id}/report` 在未完成前返回 404 | 边界 | 404 响应 | EVD-TEST-01、EVD-TEST-04 | 通过 |
| SV-27 | 远程 adapter 不可用时 readiness 有清晰状态 | 异常环境 | `/capabilities/readiness` | EVD-API-02、EVD-TEST-01 | 通过 |
| SV-28 | 快照恢复到 `WAITING_*` 不自动推进 | 恢复一致性 | recovery 测试、日志 | EVD-TEST-02、EVD-LOG-01、EVD-LOG-02、EVD-LOG-03 | 通过 |
| SV-29 | runtime_state 只在 snapshot artifacts 持久化，不污染 Plan | 数据边界 | snapshot/plan 对照 | EVD-TEST-02、EVD-LOG-01、EVD-LOG-02、EVD-LOG-03 | 通过 |
| SV-30 | 前端 Dashboard、Task Builder、Task Detail、Timeline 可展示同一任务证据链 | 系统验证 | 运行截图 | FIG-SV-01 至 FIG-SV-17、EVD-TEST-01、EVD-CLI-02 | 通过；Timeline 单独截图待补 |

## 4.1 当前证据编号覆盖

本节用于把第 4 节的 `SV-*` 验证点映射到可直接引用的测试用例与证据编号。第 4 节原表保留为逐点执行清单；论文写作和归档时优先使用本节编号。

| 验证点 | 对应用例 | 当前证据编号 | 当前判定 |
|---|---|---|---|
| SV-01、SV-27 | TC-S01 | EVD-API-01、EVD-API-02、EVD-TEST-01、FIG-SV-01、FIG-SV-02 | 通过 |
| SV-02、SV-03、SV-04、SV-07、SV-25、SV-26 | TC-S02 | EVD-TEST-01、EVD-CLI-01、EVD-API-01、EVD-API-02 | 通过；典型 task/pending/events/report API JSON 建议补齐 |
| SV-08、SV-09、SV-10 | TC-S03 | EVD-TEST-02、EVD-LOG-04、EVD-EXP-01 | 通过 |
| SV-10、SV-11、SV-12、SV-13、SV-15 | TC-S04 | EVD-TEST-02、FIG-SV-15 | 通过 |
| SV-14、SV-23、SV-24 | TC-S05 | EVD-TEST-02、EVD-LOG-03 | 通过 |
| SV-14、SV-28、SV-29 | TC-S06 | EVD-TEST-02、EVD-LOG-01、EVD-LOG-02、EVD-LOG-03 | 通过 |
| SV-01、SV-30 | TC-S07 | FIG-SV-01 至 FIG-SV-17、EVD-TEST-01 | 通过；单独 Timeline 截图待补 |
| SV-02、SV-03、SV-25、SV-26、SV-30 | TC-S08 | EVD-TEST-04、EVD-CLI-01、EVD-CLI-02、EVD-CLI-03、EVD-CLI-04 | 部分通过；CLI timeline/report 子命令未实现 |
| SV-16、SV-25、SV-26 | TC-S09 | EVD-EXP-01、EVD-LOG-05、FIG-SV-16、FIG-SV-17 | 通过；84-run 正式矩阵完成后更新最终实验证据 |
| SV-04、SV-05、SV-06、SV-11、SV-13、SV-21、SV-24 | TC-S10 | EVD-TEST-03、FIG-SV-10 | 通过 |
| SV-16、SV-17 | TC-S11 | EVD-TEST-03、EVD-EXP-01、EVD-API-02 | 通过 |
| SV-18、SV-19、SV-20、SV-22 | TC-S12 | EVD-TEST-03、EVD-LOG-01、EVD-LOG-02、EVD-LOG-03 | 通过；Plan diff 样本建议集中归档 |
| SV-21、SV-23、SV-25 | TC-S13 | EVD-TEST-02、EVD-TEST-03、EVD-LOG-03、EVD-LOG-04 | 通过 |

## 4.2 当前证据缺口

| 缺口 | 影响范围 | 后续处理 |
|---|---|---|
| 单独 Timeline 页面截图缺失 | SV-30、TC-S07 | 已由 Web smoke 和 Task Detail 截图间接覆盖；论文若需要 UI 图，补 `FIG-SV-18` |
| 典型任务 API 响应未全部单独归档 | SV-02、SV-03、SV-10、SV-25、SV-26、TC-S02、TC-S03 | 当前由 EVD-TEST-01/EVD-TEST-02 支撑；建议补 `/task-intakes/schema`、`/tasks/{id}`、`/pending-actions/{id}`、`/tasks/{id}/events`、`/tasks/{id}/report` JSON |
| Snapshot/Plan diff 样本未集中复制到 `docs/system-validation/04-data-consistency/` | SV-14、SV-18 至 SV-22、SV-28、SV-29、TC-S06、TC-S12 | 已建立路径索引；可按论文附录需要再复制关键样本 |
| 84-run 正式矩阵尚未形成最终聚合 | TC-S09、TC-S11、实验章节 | 当前只作为进行中证据；最终结论等待完整 `matrix_metrics_summary`、`run_level_results` 和 `matrix_report` |

## 5. 验证材料清单

| 材料类型 | 内容 | 建议保存位置 |
|---|---|---|
| 测试用例表 | `SV-*`、前置条件、步骤、输入、预期输出、实际结果、证据路径、结论 | `docs/system-validation/test-case-table.md` 或本文件第 4 节 |
| API 返回结果 | `health`、`task-intakes`、`tasks`、`pending-actions`、`decision`、`events`、`report` | `docs/system-validation/05-api-results/` |
| 前端截图 | Dashboard、Task Builder、Task Detail、Pending Review、Timeline、Report/Structure 面板 | `docs/system-validation/06-ui-screenshots/` |
| 控制台输出 | pytest、API server 启动、CLI help/调用输出 | `docs/system-validation/07-test-runs/` |
| 日志证据 | EventLog timeline、WAITING_ENTER/EXIT、DECISION_APPLIED、STEP_FINISHED/FAILED、RECOVERY_ESCALATED | `docs/system-validation/04-data-consistency/event-logs/` |
| 快照证据 | `TaskSnapshot` JSON，尤其是 `pending_action_id`、`completed_step_ids`、`artifacts.runtime_state` | `docs/system-validation/04-data-consistency/snapshots/` |
| 产物证据 | 报告路径、PDB/结构文件、scores、objective scoring、structure similarity | `docs/system-validation/01-core-flows/final-report-flow/` |

## 6. 建议执行命令

```bash
python -m src.cli --help
uv run pytest tests/unit/test_status_transition.py tests/unit/test_decision_validation.py tests/unit/test_decision_apply.py
uv run pytest tests/unit/test_task_snapshot.py tests/unit/test_event_log.py
uv run pytest tests/integration/test_workflow.py tests/integration/test_snapshot_recovery.py
uv run pytest tests/api/test_api_endpoints.py tests/api/test_web_smoke.py
```

如需启动 API 进行手工系统验证：

```bash
uv run uvicorn src.api.main:app --reload
```

## 7. 证据目录结构建议

```text
docs/system-validation/
├── system-validation-checklist.md
├── test-case-table.md
├── 00-environment/
│   ├── env-info.txt
│   ├── dependency-check.txt
│   └── server-startup.log
├── 01-core-flows/
│   ├── normal-task-flow/
│   ├── intake-confirm-flow/
│   └── final-report-flow/
├── 02-hitl/
│   ├── plan-confirm/
│   ├── patch-confirm/
│   └── replan-confirm/
├── 03-exceptions-boundaries/
│   ├── invalid-input/
│   ├── invalid-decision/
│   ├── terminal-state/
│   └── safety-block/
├── 04-data-consistency/
│   ├── snapshots/
│   ├── event-logs/
│   ├── plan-patch-diff/
│   └── runtime-state/
├── 05-api-results/
│   ├── health.json
│   ├── tasks/
│   ├── pending-actions/
│   ├── decisions/
│   └── timelines/
├── 06-ui-screenshots/
│   ├── dashboard.png
│   ├── task-builder.png
│   ├── task-detail.png
│   ├── pending-review.png
│   └── timeline.png
└── 07-test-runs/
    ├── pytest-unit.log
    ├── pytest-integration.log
    ├── pytest-api.log
    └── basedpyright-focused.log
```
