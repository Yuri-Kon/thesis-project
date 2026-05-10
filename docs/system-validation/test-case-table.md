# 系统验证测试用例表

更新时间：2026-05-10

本文档用于汇总毕业论文第五章“系统测试与验证”的测试用例、执行方式、预期结果和证据路径。它连接 `docs/experiment/final-thesis-experiment-design.md` 中的 `EXP-S1` 到 `EXP-S7` 与 `docs/system-validation/system-validation-checklist.md` 中的 `SV-*` 验证点。

本表只覆盖系统工程验证主线。CEBRA-WP 算法消融实验、四组策略对照和指标统计应单独放入实验结果表，不混入本文的系统测试用例表。

## 1. 状态说明

| 状态 | 含义 | 论文处理方式 |
|---|---|---|
| 待执行 | 用例已设计，但尚未运行或未归档证据 | 不写入最终结论，只保留为计划 |
| 通过 | 实际结果符合预期，证据路径完整 | 可写入系统测试结果表 |
| 部分通过 | 主路径通过，但存在非关键证据缺失或环境降级 | 可写入论文，但需在备注说明限制 |
| 未通过 | 实际结果不符合预期 | 不作为正向证据，需记录修复或原因 |
| 不适用 | 当前运行环境无法验证该项 | 可作为环境限制说明 |

## 2. 论文汇总用例总览

| 用例编号 | 测试用例名称 | 对应实验 | 覆盖验证点 | 测试类型 | 当前状态 | 主要证据 |
|---|---|---|---|---|---|---|
| TC-S01 | 环境与能力就绪验证 | EXP-S1 | SV-01、SV-27 | API / 环境 | 待执行 | health JSON、readiness JSON、启动日志 |
| TC-S02 | 任务录入与 API 合约验证 | EXP-S2 | SV-02、SV-03、SV-04、SV-07、SV-25、SV-26 | API / 自动化 | 通过 | `tests/api/test_api_endpoints.py` pytest 通过；API 响应 JSON 归档待补 |
| TC-S03 | 任务创建与计划候选验证 | EXP-S2、EXP-S5 | SV-08、SV-09、SV-10 | API / 集成 | 通过 | task JSON、pending action JSON、候选 JSON |
| TC-S04 | HITL 决策与 PendingAction 一致性验证 | EXP-S3 | SV-10、SV-11、SV-12、SV-13、SV-15 | 单元 / 集成 / API | 通过 | `test_decision_validation.py`、`test_decision_apply.py` pytest 通过；EventLog/pending JSON 归档待补 |
| TC-S05 | FSM 状态迁移与终态不可变验证 | EXP-S3 | SV-14、SV-23、SV-24 | 单元 / 集成 | 通过 | `test_status_transition.py`、`test_event_log.py`、`test_event_log_integration.py` pytest 通过 |
| TC-S06 | 快照恢复与运行时状态边界验证 | EXP-S3 | SV-14、SV-28、SV-29 | 单元 / 集成 | 通过 | `test_task_snapshot.py`、`test_snapshot_recovery.py` pytest 通过 |
| TC-S07 | Web 关键页面可用性验证 | EXP-S4 | SV-01、SV-30 | UI / 手工 / smoke | 通过 | `tests/api/test_web_smoke.py` pytest 通过；Dashboard、Task Builder、Task Detail、Timeline 截图 |
| TC-S08 | CLI 关键命令可用性验证 | EXP-S4 | SV-02、SV-03、SV-25、SV-26、SV-30 | CLI / 手工 / 自动化 | 通过 | `tests/unit/test_cli.py` pytest 通过；CLI 输出、task JSON、timeline JSON |
| TC-S09 | 正常端到端任务流程验证 | EXP-S5 | SV-16、SV-25、SV-26 | 集成 / API | 部分通过 | t8 四组 smoke run + t9 四组 clean run（16/16 DONE）；API report focused test 待补 |
| TC-S10 | 异常输入与安全 warn/block 验证 | EXP-S6 | SV-04、SV-05、SV-06、SV-11、SV-13、SV-21、SV-24 | 单元 / API | 通过 | `tests/unit/test_safety_agent.py`（含确定性 forbidden_motif block/warn）、`tests/unit/test_step_runner.py`（含安全阻断工具调用验证）、`tests/api/test_api_endpoints.py` |
| TC-S11 | 工具链执行与 I/O 边界验证 | EXP-S5、EXP-S6 | SV-16、SV-17 | 集成 / 单元 | 部分通过 | t8 OpenFold3 REST 成功日志、StepResult、artifact；异常 I/O 边界 focused test 待补 |
| TC-S12 | 失败恢复 retry -> patch -> replan 验证 | EXP-S7 | SV-18、SV-19、SV-20、SV-22 | 单元 / 集成 | 通过 | 恢复专项 pytest 通过；`test_recovery_layered_patch.py`、`test_s6_control_layer_e2e.py` |
| TC-S13 | 恢复止损与审计链路验证 | EXP-S7 | SV-21、SV-23、SV-25 | 集成 / API | 通过 | terminal_stop 记录、FAILED TaskRecord、timeline JSON |

## 3. 可执行测试用例明细

| 用例编号 | 前置条件 | 输入与步骤 | 预期结果 | 实际结果 | 证据路径 | 结论 |
|---|---|---|---|---|---|---|
| TC-S01 | API 服务可启动；本地配置文件可读取 | 1. 启动 `uv run uvicorn src.api.main:app --reload`。<br>2. 请求 `GET /health`。<br>3. 请求 `GET /capabilities/readiness`。<br>4. 若远程服务不可用，记录 degraded reason。 | `/health` 返回 `status=ok`；readiness 返回 capability、available_tools、blocked_tools、degraded_reasons；远程不可用时给出明确原因。 | 2026-05-10 执行：`/health` 返回 `status=ok`, 15 tools；`/capabilities/readiness` 返回 15 capability：7 ready、1 degraded（protgpt2 远程 PLM 不可达）、7 unavailable（autodock_vina/interproscan 等本环境预期缺失）；所有 blocked/degraded 均有 `error_category` 和 `suggested_recovery` 说明。 | `docs/system-validation/00-environment/server-startup.log`；`docs/system-validation/05-api-results/health.json`；`docs/system-validation/05-api-results/readiness.json` | 通过 |
| TC-S02 | 测试环境依赖安装完成；API 测试可运行 | 1. 运行 `uv run pytest tests/api/test_api_endpoints.py -q`。<br>2. 手工或脚本请求 task-intake、task、events、report 相关接口。<br>3. 记录正常响应与异常响应。 | intake schema 可返回字段注册表；正常输入可创建 intake/task；缺字段、互斥创建模式、未完成 report 等异常返回明确错误；events 支持查询。 | 2026-05-10 用户执行 focused suite，`tests/api/test_api_endpoints.py` 随同 FSM/HITL/snapshot 用例顺利通过；手工 API JSON 归档尚未补齐。 | `tests/api/test_api_endpoints.py`；建议后续补写 `docs/system-validation/07-test-runs/pytest-api.log` 和 `docs/system-validation/05-api-results/` | 通过 |
| TC-S03 | Planner、ToolKG 和任务创建入口可用 | 1. 使用自由文本或 confirmed task spec 创建任务。<br>2. 触发计划生成。<br>3. 查询 task 与 pending action。 | Planner 只生成候选，不执行工具、不直接改状态；Plan candidate 包含候选 ID、payload、评分、风险、成本、解释；需要确认时进入 `WAITING_PLAN_CONFIRM` 并生成 `PendingAction(plan_confirm)`。 | 已有 `test_plan_with_status_waiting_metadata_keeps_runtime_summary_fields` 和 `test_plan_top_k_s1_contract_fields_are_complete` 覆盖核心路径。 | `tests/unit/test_planner_agent.py`；`tests/integration/test_event_log_integration.py` | 通过 |
| TC-S04 | 存在进入等待态的任务和有效 PendingAction | 1. 运行 decision 相关单测。<br>2. 对 accept 缺少 `selected_candidate_id` 的请求进行验证。<br>3. 对已决策 PendingAction 重复提交。<br>4. 对错误 task/pending 绑定提交 decision。 | accept 缺少候选 ID 被拒绝；重复 decision 返回冲突；错误绑定被拒绝；等待态下 Executor 不继续执行工具；合法 Decision 只应用一次。 | 2026-05-10 用户执行 `test_decision_validation.py` 与 `test_decision_apply.py`，同组 focused suite 顺利通过。 | `tests/unit/test_decision_validation.py`；`tests/unit/test_decision_apply.py`；建议后续补写 `docs/system-validation/07-test-runs/pytest-decision.log` | 通过 |
| TC-S05 | 状态迁移单测和事件日志测试可运行 | 1. 运行 `tests/unit/test_status_transition.py`、`tests/unit/test_event_log.py`。<br>2. 构造或复用 DONE、FAILED、CANCELLED 终态任务。<br>3. 尝试再次提交状态变更或 decision。 | 进入 `WAITING_*` 前写入 snapshot 和 `WAITING_ENTER`；terminal stop 接受后进入 `FAILED`；DONE/FAILED/CANCELLED 不可再变更。 | 2026-05-10 用户执行 `test_status_transition.py`、`test_event_log.py`、`test_event_log_integration.py`，同组 focused suite 顺利通过。 | `tests/unit/test_status_transition.py`；`tests/unit/test_event_log.py`；`tests/integration/test_event_log_integration.py`；建议后续补写 `docs/system-validation/07-test-runs/pytest-fsm.log` | 通过 |
| TC-S06 | snapshot store 可写；存在等待态或运行态任务 | 1. 运行 `tests/unit/test_task_snapshot.py` 和 `tests/integration/test_snapshot_recovery.py`。<br>2. 保存等待态 snapshot。<br>3. 执行恢复流程。<br>4. 对比 Plan 与 snapshot artifacts。 | snapshot 可恢复 plan、completed steps、pending action 和 runtime_state；恢复到 `WAITING_*` 后不自动推进；runtime_state 仅在 snapshot artifacts 持久化，不污染 Plan。 | 2026-05-10 用户执行 `test_task_snapshot.py` 与 `test_snapshot_recovery.py`，同组 focused suite 顺利通过。 | `tests/unit/test_task_snapshot.py`；`tests/integration/test_snapshot_recovery.py`；建议后续补写 `docs/system-validation/07-test-runs/pytest-snapshot-recovery.log` | 通过 |
| TC-S07 | API 服务启动；前端静态资源可访问；至少存在一个测试任务 | 1. 打开 `/ui`。<br>2. 打开 `/ui/task-builder` 并完成 intake 创建/确认。<br>3. 打开 `/ui/tasks/{task_id}`。<br>4. 查看 timeline 和 pending review 面板。 | Dashboard、Task Builder、Task Detail、Timeline 可加载；同一 task_id 的状态、pending_action_id、事件链可在页面展示；人工确认入口可见。 | 2026-05-10 执行：Dashboard/TaskBuilder/TaskDetail 页面均可正常加载；中文界面变体截图一并留存；Timeline 作为 TaskDetail 页内区域呈现，未单独截图。 | `docs/system-validation/06-ui-screenshots/` 共 17 张 PNG（Dashboard、Task Builder、Task Detail 中英文变体） | 通过 |
| TC-S08 | CLI 可通过 `python -m src.cli` 调用；API 或本地存储可访问 | 1. 运行 `python -m src.cli intake schema --json`。<br>2. 创建、查看并确认 intake。<br>3. 查询 task、timeline、pending、report。<br>4. 保存 JSON 与人类可读输出。 | CLI 能输出 JSON 和人类可读摘要；CLI 与 Web/API 展示的 task_id、status、pending_action_id、event 数量一致。 | 2026-05-10 执行：`intake schema --json` 返回 3953 行完整字段注册表；`task show` 输出 task_id/status/DONE、15 capability readiness 及 recovery 建议；`task timeline` 与 `task report` 当前 CLI 未实现子命令（输出 usage 提示，属预期限制）。 | `docs/system-validation/07-test-runs/cli-intake-schema.log`（3953 行）；`cli-task-show.log`；`cli-timeline.log`（usage 输出）；`cli-report.log`（usage 输出） | 部分通过 |
| TC-S09 | mock 或可用远程 provider 就绪；正常任务样例已确定 | 1. 运行 `tests/integration/test_mock_remote_full_flow.py`、`tests/integration/test_esmfold_summarizer_integration.py`、`tests/integration/test_workflow.py`。<br>2. 创建一个正常设计或序列评估任务。<br>3. 查询最终报告。 | 任务进入 `DONE`；至少包含一个 `StepResult`；`/tasks/{id}/report` 返回 `DesignResult`；报告包含 scores、risk_flags、report_path 或 structure artifact。 | 2026-05-10 t8 四组 smoke（4/4 DONE）+ t9 四组 clean run（16/16 DONE）：覆盖 t1（denovo）/ t2（sequence）/ t5（patchable）/ t8（safety），每任务四组策略（static_top1 / fixed_threshold_gate / dynamic_no_belief / lite_belief），全部 success_rate=1.0、schema_valid=1.0、executable_plan=1.0，无 rerun 触发；尚未运行本用例列出的 API/report focused tests。 | `output/experiment/thesis-final-matrix-smoke/thesis-final-smoke-fourgroup-t8-provider-max-001/`；`output/experiment/thesis-final-matrix-smoke/thesis-final-smoke-fourgroup-t9-clean-001/run_log_index.csv`；`output/experiment/thesis-final-matrix-smoke/thesis-final-smoke-fourgroup-t9-clean-001/matrix_metrics_summary.csv` | 部分通过 |
| TC-S10 | 安全规则与异常输入测试可运行 | 1. 运行 `tests/unit/test_safety_agent.py`、`tests/unit/test_decision_validation.py`、`tests/api/test_api_endpoints.py`。<br>2. 提交缺失必要字段的请求。<br>3. 提交 safety warn 未 acknowledge 的请求。<br>4. 提交 safety block 请求。<br>5. 对终态任务继续提交 decision。 | warn 必须显式 acknowledge；block 不允许创建正式执行任务；错误 decision 被拒绝且不改变任务状态；终态不可再决策。 | 2026-05-10 已补确定性安全阻断 focused test：`test_safety_agent.py` 新增 `test_pre_step_block_deterministic_forbidden_motif` + `test_pre_step_allow_when_no_forbidden_motif`（2 个 SafetyAgent 单测）；`test_step_runner.py` 新增 `test_run_step_safety_block_forbidden_motif_prevents_tool_execution` + `test_run_step_safety_warn_allows_execution_with_risk_flag`（2 个 StepRunner 集成测试）。验证：forbidden_motif → block → 工具未调用 + FORBIDDEN_MOTIF_PRESENT risk flag + safety_events 审计链；warn → 执行继续 + risk flag 记录。 | `tests/unit/test_safety_agent.py`；`tests/unit/test_step_runner.py`；`tests/api/test_api_endpoints.py` | 通过 |
| TC-S11 | 工具 registry 与候选校验逻辑可用 | 1. 运行包含工具执行的集成测试。<br>2. 构造正常工具调用，检查 `StepResult`、metrics、artifacts。<br>3. 构造 schema 或 I/O 引用错误候选。 | 正常步骤产生 `StepResult`、metrics 和 artifact；工具 schema/I-O 引用错误必须淘汰候选或产生明确失败，不静默执行。 | 2026-05-10 t8 + t9 正常工具链证据：t8 四组均执行 `openfold`（`execution_mode=openfold3_rest`，`status=success`）；t9 扩展至 4 任务 4 组共 16 run，全部工具调用成功：t1/t2/t5 执行 openfold（S2），t8 执行 protgpt2（S1）+ openfold（S2）+ biopython_qc（S3）；所有 STEP_FINISHED `status=success`，无 DUMMY/ProviderPayloadValidationError；schema/I-O 错误候选淘汰仍需 focused test。 | `data/logs/thesis-final-smoke-fourgroup-t8-provider-max-001_*.jsonl`；`data/logs/thesis-final-smoke-fourgroup-t9-clean-001_*.jsonl`；`output/experiment/thesis-final-matrix-smoke/thesis-final-smoke-fourgroup-t9-clean-001/action_distribution.csv` | 部分通过 |
| TC-S12 | 可触发 retry 耗尽、patch 和 replan 的测试任务可用 | 1. 运行 `test_run_plan_triggers_patch_after_retry_exhausted`。<br>2. 运行 `test_auto_replan_resolves_pending_action`。<br>3. 运行 `tests/integration/test_recovery_layered_patch.py` 和 `tests/integration/test_s6_control_layer_e2e.py`。<br>4. 保存 Plan diff 与 EventLog。 | retry 耗尽后不直接 `FAILED`；局部可修时进入 patch_confirm；patch accept 后只修改目标步骤或后缀；replan 保留可保留前缀。 | 2026-05-10 已补 `test_deterministic_retry_patch_to_done_produces_recovery_metrics`：本地确定性触发 retry exhausted，自动 tool-level patch 后进入 DONE，并用 `extract_run_metrics` 验证 `patch_event_count=1`、`first_pass_success=False`、`replan_event_count=0`；恢复专项复跑 `9 passed, 1 warning`。 | `src/workflow/patch_runner.py`；`tests/integration/test_recovery_layered_patch.py`；`tests/integration/test_s6_control_layer_e2e.py`；建议后续补写 `docs/system-validation/07-test-runs/pytest-recovery.log` | 通过 |
| TC-S13 | 存在安全 block、结构性失败或 terminal_stop 场景 | 1. 触发 safety block 或结构性失败。<br>2. 生成 replan/stop 候选。<br>3. 接受 terminal_stop 候选。<br>4. 查询 task 与 events。 | Safety block 禁止 continue，并进入 replan/stop 候选；terminal_stop 接受后进入 `FAILED`；`/tasks/{id}/events` 可还原恢复与止损链路。 | 2026-05-10 已有 `test_replan_confirm_accept_terminal_stop_transitions_to_failed` + `test_terminal_stop_audit_chain_is_recorded_in_event_log` 覆盖 terminal_stop → FAILED + EventLog 审计链完整验证；safety block 由 `test_step_runner.py` / `test_runtime_evaluator.py` 覆盖。 | `tests/unit/test_decision_apply.py`；`tests/integration/test_event_log_integration.py`；`tests/unit/test_step_runner.py` | 通过 |

## 4. 证据归档要求

| 证据类型 | 建议文件名或目录 | 归档要求 |
|---|---|---|
| pytest 日志 | `docs/system-validation/07-test-runs/pytest-*.log` | 保留命令、测试数量、通过/失败结果和失败堆栈 |
| API JSON | `docs/system-validation/05-api-results/**.json` | 保留请求对象、响应状态码、响应体和 task_id |
| CLI 输出 | `docs/system-validation/07-test-runs/cli-*.log` | 同时保留 JSON 输出和人类可读输出 |
| 前端截图 | `docs/system-validation/06-ui-screenshots/*.png` | 文件名体现页面和 task_id；避免只截局部无上下文画面 |
| EventLog | `docs/system-validation/04-data-consistency/event-logs/` | 保留 WAITING_ENTER、DECISION_APPLIED、WAITING_EXIT、STEP_FINISHED/FAILED、RECOVERY_ESCALATED 等关键事件 |
| Snapshot | `docs/system-validation/04-data-consistency/snapshots/` | 保留 pending_action_id、completed_step_ids、artifacts.runtime_state |
| Plan diff | `docs/system-validation/04-data-consistency/plan-patch-diff/` | 保留 patch/replan 前后差异，用于证明只修改目标步骤或后缀 |
| 报告产物 | `docs/system-validation/01-core-flows/final-report-flow/` | 保留 `DesignResult`、report path、scores、risk_flags、structure artifact 摘要 |

## 5. 论文可用汇总表模板

完成测试后，论文正文可压缩为如下表格；详细证据保留在本文和证据目录中。

| 测试类别 | 对应用例 | 覆盖内容 | 执行结果 | 主要证据 |
|---|---|---|---|---|
| 环境与能力验证 | TC-S01 | API 健康检查、能力目录、readiness 降级说明 | 通过 | `server-startup.log`、`health.json`、`readiness.json`：15 capability，7 ready，degraded/unavailable 均有 `error_category` 和 `suggested_recovery` |
| API 合约验证 | TC-S02、TC-S03 | intake、task、pending action、events、report、计划候选 | 通过 | `tests/api/test_api_endpoints.py` + `test_planner_agent.py` 覆盖 API 合约与计划候选 |
| FSM 与 HITL 验证 | TC-S04、TC-S05、TC-S06 | 等待态、人工决策、快照恢复、终态不可变 | 通过 | status、decision、event_log、snapshot focused tests |
| Web / CLI 可用性验证 | TC-S07、TC-S08 | 前端页面、CLI 命令、同一任务证据展示 | 部分通过 | 17 张 Web 截图（Dashboard/TaskBuilder/TaskDetail 中英文）；CLI intake schema/task show 可用，timeline/report 子命令未实现 |
| 端到端流程验证 | TC-S09、TC-S11 | 正常任务执行、StepResult、DesignResult、工具 I/O | 部分通过 | t8 四组 smoke（4/4 DONE）+ t9 四组 clean run（16/16 DONE），覆盖 4 类任务 × 4 组策略；API report focused tests 待补 |
| 异常与安全边界验证 | TC-S10、TC-S13 | 缺字段、错误决策、安全 warn/block、止损 | 通过 | TC-S10 新增确定性 forbidden_motif block/warn focused test（4 个用例，含 StepRunner 工具调用阻断验证）；TC-S13 terminal_stop 审计链 tests 通过 |
| 失败恢复验证 | TC-S12、TC-S13 | retry、patch、replan、terminal stop、恢复审计链 | 部分通过 | TC-S12 恢复专项 8 passed；TC-S13 terminal stop API 链路待补 |

## 6. 与论文结论的对应关系

| 论文结论 | 支撑用例 | 必需证据 |
|---|---|---|
| 系统具备从任务输入到结果报告的完整工程闭环 | TC-S02、TC-S03、TC-S07、TC-S08、TC-S09 | API 响应、Web 截图、CLI 输出、DesignResult |
| FSM 和 HITL 机制能够保证执行可暂停、可确认、可恢复 | TC-S04、TC-S05、TC-S06 | PendingAction、Decision、snapshot、EventLog |
| 系统对异常输入、安全风险和终态约束具备边界保护 | TC-S10、TC-S13 | 错误响应、SafetyResult、状态未变更记录 |
| 失败恢复不是异常旁路，而是可审计的主流程能力 | TC-S12、TC-S13 | retry/patch/replan trace、Plan diff、timeline |
| Web、CLI、API 能围绕同一任务形成一致证据链 | TC-S02、TC-S07、TC-S08、TC-S09 | task_id/status 对照、截图、CLI JSON、API JSON |
