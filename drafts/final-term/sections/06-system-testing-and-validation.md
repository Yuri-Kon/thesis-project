# 第六章：系统测试与验证（草稿）

> 状态：初稿 · 2026-05-11 · 目标章节文件 `chapters/06-system-testing.tex`
> 证据来源：`docs/system-validation/evidence-index.md`、`test-case-table.md`、`system-validation-checklist.md`
> 本章对应实验设计书的"系统可用性与工程验证"主线（EXP-S1 至 EXP-S7）

---

## 6.1 测试策略与验证目标

本系统的测试与验证围绕一个核心问题展开：**系统是否按照第 4 章定义的设计正确运行？** 该问题与第 7 章的策略对比实验在目标上严格区分——本章关注功能正确性（系统是否做对了该做的事），第 7 章关注算法有效性（CEBRA-WP 是否比基线更好）。

测试采用多层次、多入口的组合策略。在层次上，单元测试验证 Agent 职责边界、状态迁移规则和数据契约；集成测试验证跨模块协作，尤其是 FSM、HITL 和快照恢复的交互链路；API 测试验证 15 个端点的合约一致性和异常边界；手工验证覆盖 Web 前端和 CLI 的实际交互流程。在入口上，测试覆盖 API、Web 工作台和命令行三种用户触达方式，确保不同使用路径下的行为一致。

测试用例以 **TC-S01 至 TC-S13** 编号，覆盖 **30 余个验证点（SV-01 至 SV-30）**，按功能维度可归入七个类别：环境与能力就绪、任务录入与数据契约、人在环路与决策边界、FSM 状态迁移与终态不变性、快照持久化与恢复、前端与 CLI 可用性、失败恢复与安全边界。每个类别对应实验设计书中的一个系统验证实验（EXP-S1 至 EXP-S7）。

证据体系以六类前缀编号：**EVD-API**（API 响应，8 项）、**EVD-TEST**（pytest 执行日志，4 组）、**EVD-CLI**（CLI 输出，4 项）、**FIG-SV**（前端截图，18 张）、**EVD-LOG**（EventLog/Snapshot 样本，8 组）、**EVD-EXP**（实验矩阵聚合，4 项）。所有证据编号均可在 `docs/system-validation/evidence-index.md` 中追溯原始文件路径。

表 6-1 汇总了全部 13 个测试用例的执行结果。

本章以表格和证据编号为主，不在 `paper/figures/` 中新增独立正文图。FIG-SV-01 至 FIG-SV-18 是系统验证证据截图，适合在附录或验证材料索引中引用；若终稿需要正文截图，可从这些证据中选择 Dashboard、Task Builder、Task Detail 或 Timeline 页面单独编号。当前草稿中凡涉及 FIG-SV 的位置均作为证据编号使用，不写成“如图 6-x 所示”，以避免出现前文引用但正文无对应图表的问题。

**表 6-1：系统测试用例汇总**

| 用例 | 测试类别 | 覆盖验证点 | 执行结果 | 核心证据 |
|------|----------|-----------|----------|----------|
| TC-S01 | 环境与能力就绪 | SV-01、SV-27 | 通过 | EVD-API-01、EVD-API-02 |
| TC-S02 | API 合约与任务录入 | SV-02/03/04/07/25/26 | 通过 | EVD-TEST-01、EVD-API-03~08 |
| TC-S03 | 计划候选生成 | SV-08/09/10 | 通过 | EVD-TEST-02、EVD-LOG-04 |
| TC-S04 | HITL 决策一致性 | SV-10/11/12/13/15 | 通过 | EVD-TEST-02、FIG-SV-15 |
| TC-S05 | FSM 状态迁移 | SV-14/23/24 | 通过 | EVD-TEST-02、EVD-LOG-03 |
| TC-S06 | 快照持久化与恢复 | SV-14/28/29 | 通过 | EVD-TEST-02、EVD-LOG-01/02/03 |
| TC-S07 | Web 前端可用性 | SV-01、SV-30 | 通过 | FIG-SV-01~18、EVD-TEST-01 |
| TC-S08 | CLI 可用性 | SV-02/03/25/26/30 | 部分通过 | EVD-CLI-01~04、EVD-TEST-04 |
| TC-S09 | 端到端任务流程 | SV-16/25/26 | 通过 | EVD-EXP-01、EVD-LOG-05 |
| TC-S10 | 异常输入与安全边界 | SV-04/05/06/11/13/21/24 | 通过 | EVD-TEST-03 |
| TC-S11 | 工具链执行与 I/O | SV-16/17 | 通过 | EVD-TEST-03、EVD-EXP-01 |
| TC-S12 | 失败恢复流程 | SV-18/19/20/22 | 通过 | EVD-TEST-03、EVD-LOG-01/02/03 |
| TC-S13 | 恢复止损与审计链路 | SV-21/23/25 | 通过 | EVD-TEST-02/03、EVD-LOG-03/04 |

12 个用例通过，1 个（TC-S08 CLI）部分通过。以下各节按类别详述验证内容、关键证据和发现。

---

## 6.2 API 服务与工具能力就绪验证

系统的基础可用性通过两类端点验证：健康检查（`/health`）提供 API 服务状态和基础元信息；能力就绪检查（`/capabilities/readiness`）提供 15 个蛋白质设计工具的运行可用性评估。

**TC-S01 执行过程**：启动 API 服务后，`/health` 返回 `status=ok`，`task_count=0`，`kg_tool_count=15`，并给出 `paths` 中日志、快照和输出目录的实际路径（EVD-API-01）。`/capabilities/readiness` 返回 15 条能力就绪记录，其中 7 条为 `ready`（可直接调用），1 条为 `degraded`（protgpt2 远程 PLM 服务不可达，但不阻断系统运行），7 条为 `unavailable`（autodock_vina、interproscan 等本环境预期缺失的工具）。每条 degraded 或 unavailable 记录均包含 `error_category` 和 `suggested_recovery` 字段，例如对远程 PLM 不可用的情况给出"检查远程服务端点或切换至本地模型"的恢复建议（EVD-API-02）。

该验证的意义在于：系统的工具能力不是硬编码的静态列表，而是运行时动态评估的结果。Planner 在生成候选计划时可以依据 readiness 状态排除不可用工具或标记 degraded feasible 候选，这为第 4 章设计的"能力驱动的工具链组合"提供了运行时的真实依据。

---

## 6.3 任务录入与数据契约验证

任务录入是用户与系统交互的入口。系统不是简单接收 JSON 并创建任务，而是通过 Task Intake 的渐进式确认链路（draft → supplement → confirm → ProteinDesignTask）确保输入完备性和场景可行性。该链路由 TC-S02 和 TC-S03 联合覆盖。

**TC-S02 验证内容**：自动化测试覆盖了 API 合约的完整边界（EVD-TEST-01，71 passed）。正常路径下，`/task-intakes/schema` 返回 132KB 的完整字段注册表，覆盖所有任务种类的字段定义（EVD-API-03）；自由文本可创建 intake 草稿；缺失必要字段时 confirm 被拒绝（422 响应）；三种创建模式（goal / query / confirmed_task_spec）互斥，同时提交被明确拒绝。手工补充的证据包括：`/tasks/demo_structure_viewer` 返回包含 goal、constraints、scores 和 report_path 的完整任务详情（EVD-API-04）；`/tasks/demo_structure_viewer/events` 返回 11 条事件（含 STATE_TRANSITION、STEP_FINISHED、WAITING_ENTER/EXIT、DECISION_APPLIED，EVD-API-05）；`/tasks/demo_structure_viewer/report` 返回包含 objective_scoring 和 structure_similarity 的报告摘要（EVD-API-06）；`/pending-actions` 对 DONE 任务返回空数组，符合预期（EVD-API-07）。此外，对真实实验任务（`thesis-final-v1-001_dynamic_no_belief_state_t1_trpcage_denovo_short_peptide_r01`）的 events 查询返回 25KB 事件链（EVD-API-08），证明 events API 可直接从 `data/logs/` 读取磁盘日志，不受 TASK_STORE 内存状态的限制。

**TC-S03 验证内容**：PlannerAgent 的行为边界通过单元测试确认（EVD-TEST-02，107 passed）。`test_plan_top_k_s1_contract_fields_are_complete` 验证每个 PlanCandidate 必须包含 candidate_id、score_breakdown、risk_level、cost_estimate、explanation 和 source_refs 等合约字段。`test_plan_with_status_waiting_metadata_keeps_runtime_summary_fields` 验证 Planner 只生成候选而不执行工具、不直接改变任务状态。当候选置信度不足时，系统生成 `PendingAction(plan_confirm)` 并进入 WAITING_PLAN_CONFIRM 状态，等待人工确认后方可继续。该边界受 `AGENT_CONTRACT.md` 保护：PlannerAgent 不得执行工具、不得直接检查运行时产物、不得变更任务状态。

---

## 6.4 人在环路与决策边界的正确性

人在环路（HITL）不是系统的附加功能，而是嵌入 FSM 控制流的结构化机制。TC-S04 围绕 PendingAction 和 Decision 的交互契约，验证了四个关键边界。

**PendingAction 的存在性**：进入任意 WAITING_* 状态前，系统必须创建对应的 PendingAction 对象——WAITING_PLAN_CONFIRM 对应 `action_type=plan_confirm`，WAITING_PATCH_CONFIRM 对应 `patch_confirm`，WAITING_REPLAN_CONFIRM 对应 `replan_confirm`。该约束由 FSM/HITL focused suite 覆盖（EVD-TEST-02），前端截图 FIG-SV-15（Task Detail 中文化候选/决策区域）直观展示了候选列表和 Decision 提交界面。

**决策有效性的边界检查**：三个异常边界被验证——accept 决策缺少 `selected_candidate_id` 时返回 400 拒绝（SV-11）；已决策的 PendingAction 再次提交返回 409 冲突（SV-12）；将 Decision 提交到不属于该 task 的 PendingAction 被拒绝（SV-13）。这些边界确保人类决策只能作用于正确的待决策项，且每个决策只生效一次。

**等待态下的执行停止**：在 WAITING_* 状态下，ExecutorAgent 必须停止工具调用。该行为由测试验证（SV-15），确保系统在等待人工输入期间不会自动推进到后续步骤。

决策应用后，系统写入 WAITING_EXIT 和 DECISION_APPLIED 事件，状态按 FSM 规则迁移。EVD-LOG-08（t3_gb1_stability_optimization 事件日志样本）记录了从 PENDING_ACTION_CREATED → WAITING_ENTER → DECISION_SUBMITTED → DECISION_APPLIED → WAITING_EXIT 的完整决策事件链，以及随后的 CANDIDATE_VALIDATION_FAILED → FAILED 路径，直观反映了决策应用后系统继续按 FSM 规则推进的行为。

---

## 6.5 有限状态机的迁移正确性与终态不变性

系统的状态迁移不是松散的事件驱动，而是受 FSM 严格约束。TC-S05 验证了两类核心属性：迁移合法性和终态不可变性。

**迁移合法性**：合法的状态转移路径由 `AGENT_CONTRACT.md` 显式定义——CREATED → PLANNING → (WAITING_PLAN_CONFIRM | PLANNED) → RUNNING → (WAITING_PATCH_CONFIRM | WAITING_REPLAN_CONFIRM | SUMMARIZING)，WAITING_* → (RUNNING | FAILED | CANCELLED)，RUNNING → SUMMARIZING → DONE。任何不在该集合中的迁移被拒绝。EVD-TEST-02 中的状态迁移测试覆盖了全部合法路径和关键非法路径。

**终态不可变性**：DONE、FAILED 和 CANCELLED 三个终态一旦进入便不可再变更。该不变性通过测试验证：对已处于终态的任务再次提交状态变更或 decision 均被拒绝。此外，terminal_stop 作为终止型 replan 候选接受后，任务进入 FAILED 的审计链由 EVD-LOG-03（S6 控制层 E2E 日志）完整记录——WAITING_REPLAN_CONFIRM → DECISION_APPLIED(terminal_stop) → FAILED，事件链包含决策前后的状态快照和决策依据。

---

## 6.6 快照持久化与恢复正确性

快照（TaskSnapshot）是系统可恢复性的基础设施。TC-S06 验证了快照的三个关键约束。

**进入等待态前的持久化**：SV-14 规定，进入任意 WAITING_* 状态前必须完成 PendingAction 写入、事件日志记录和 TaskSnapshot 保存。EVD-TEST-02 中的快照测试确认了该顺序：快照写入先于状态迁移，因此如果进程在等待期间崩溃，重启后可以从快照中恢复到完整的等待场景——包括 pending_action_id、completed_step_ids、plan_version 和 artifacts.runtime_state。

**恢复后不自动推进**：SV-28 规定，快照恢复到 WAITING_* 状态后，系统不得自动推进执行，必须等待人工 Decision。该语义对于 HITL 的可靠性至关重要——如果恢复后自动跳过人工确认，则快照失去了保护决策边界的意义。

**运行时状态的隔离**：SV-29 规定，runtime_state 仅在 snapshot artifacts 中持久化，不污染 Plan 的语义字段。EVD-LOG-01（确定性 retry patch 样本）的快照展示了这一隔离：artifacts.runtime_state 包含 p_success、budget_pressure 等运行时估计，而 Plan 本身仅包含步骤定义和约束，两者互不污染。

---

## 6.7 前端与 CLI 可用性验证

系统的工程完整性不能仅由后端测试证明——用户实际接触的是 Web 界面和命令行。TC-S07 和 TC-S08 分别验证这两个交互入口。

**TC-S07 Web 前端**：通过自动化 smoke 测试（EVD-TEST-01）和手工截图验证覆盖了四个关键页面。Dashboard（FIG-SV-01/02）展示任务列表、状态摘要和能力提示。Task Builder（FIG-SV-03~11，共 9 张中英文截图）覆盖从自由文本输入到字段补充、安全预检查和任务确认的完整流程。Task Detail（FIG-SV-12~17，共 6 张截图）展示任务状态、快照/运行上下文、候选决策区域、报告/结构区域和证据面板。单独 Timeline 页面（FIG-SV-18）展示 11 个事件的全生命周期：STATE_TRANSITION（CREATED→PLANNING→PLANNED→RUNNING）、STEP_FINISHED（×2）、PENDING_ACTION_CREATED、WAITING_ENTER、DECISION_APPLIED、WAITING_EXIT、STATE_TRANSITION（RUNNING→SUMMARIZING→DONE）。所有页面在不同 task_id 下展示的状态、pending_action_id 和事件链保持一致，Web smoke 测试覆盖了页面加载和 bootstrap 注入的正确性。

**TC-S08 CLI**：`intake schema --json` 返回 3953 行完整字段注册表（EVD-CLI-01），`task show` 输出 task_id、状态、15 条能力 readiness 和恢复建议（EVD-CLI-02）。CLI 自动化测试覆盖 16 个用例（EVD-TEST-04，16 passed）。但 `timeline show` 和 `report show` 两个子命令当前仅输出 usage 提示（EVD-CLI-03/04），属于当前实现的限制。TC-S08 因此标记为"部分通过"——主路径可用，timeline 和 report 可通过 Web 和 API 替代获取。

Web 和 CLI 的一致性由 TC-S02 交叉验证：同一 task_id 在 Web 页面、CLI 输出和 API JSON 中的状态、pending_action_id 和事件数量相同。

---

## 6.8 失败恢复流程的正确性

蛋白质设计工作流的高代价特征使得失败恢复不是异常旁路，而是主流程的核心能力。TC-S12 验证了第 4 章设计的 retry → patch → replan 分层恢复策略。

**有界重试**：步骤失败后，Executor 优先进行有界重试（bounded retry）。若重试成功，工作流继续推进；若重试耗尽，系统进入恢复路径而非直接宣告 FAILED。该行为由 `test_run_plan_triggers_patch_after_retry_exhausted` 验证。

**局部修补**：retry 耗尽后，系统生成 patch 候选并进入 WAITING_PATCH_CONFIRM。`test_deterministic_retry_patch_to_done_produces_recovery_metrics` 通过本地确定性触发 retry exhausted，自动 tool-level patch 后进入 DONE，提取的运行时指标显示 `patch_event_count=1`、`first_pass_success=False`、`replan_event_count=0`，验证了局部修补的触发条件和执行效果。EVD-LOG-01（确定性 retry patch 样本）提供了事件链和快照的完整记录。

**后缀重规划**：当局部修补不足以恢复时，系统生成 replan 候选（优先 suffix_replan，仅在前缀不可保留时允许 full_replan）。TC-S12 的集成测试验证了 replan 的触发逻辑和前级保留行为。EVD-LOG-02（分层 patch 样本）和 EVD-LOG-03（S6 控制层 E2E 样本）覆盖了从局部 patch 到远程/本地 fallback 再到高风险 replan 的多层恢复场景。

---

## 6.9 安全边界的有效性

安全边界是确保系统不会在风险场景下越权执行的关键机制。TC-S10 和 TC-S13 联合覆盖了从风险检测到止损执行的全链路。

**安全判定链路**：SafetyAgent 在输入、步骤和输出三个阶段执行安全检查。2026-05-10 新增的 4 个确定性 focused test 覆盖了完整的判定链路：`test_pre_step_block_deterministic_forbidden_motif` 验证 forbidden_motif 在 pre_step 阶段被检测并返回 block；`test_run_step_safety_block_forbidden_motif_prevents_tool_execution` 验证 block 阻止了工具调用（SpyAdapter 未被 invoke）；`test_pre_step_allow_when_no_forbidden_motif` 验证无误报；`test_run_step_safety_warn_allows_execution_with_risk_flag` 验证 warn 放行但记录 FORBIDDEN_MOTIF_PRESENT risk flag 和安全审计事件。这些测试在 SafetyAgent + StepRunner 层覆盖了从安全判定到执行阻断的完整路径（EVD-TEST-03）。

**止损机制**：TC-S13 验证了 terminal_stop 作为终止型恢复动作的完整审计链。`test_replan_confirm_accept_terminal_stop_transitions_to_failed` 确认接受 terminal_stop 候选后任务进入 FAILED 终态；`test_terminal_stop_audit_chain_is_recorded_in_event_log` 确认事件日志中记录了从 WAITING_ENTER → DECISION_APPLIED → WAITING_EXIT 的完整审计链，可通过 `/tasks/{id}/events` 还原。safety block 触发 replan 候选生成的路径由 StepRunner 和 RuntimeEvaluator 的集成测试覆盖。

需要注意的是，t9 clean run 中 t8（安全探测任务）四组均正常执行完毕，safety_terminality=0.0，未触发阻断。这不是安全机制的缺失，而是实验任务设计未能将 forbidden_motif 作为 plan constraint 传入 step.metadata——确定性 focused test 已在代码层验证了阻断路径的可用性，矩阵实验中的安全触发需要强化任务约束。

---

## 6.10 端到端流程验证

TC-S09 和 TC-S11 验证了从自然语言任务到 DesignResult 的完整成功路径，以及工具链执行和 I/O 边界的正确性。

**TC-S09 正常端到端流程**：t8 四组 smoke（4 runs，单任务 t2_trpcage_sequence_eval）和 t9 四组 clean run（16 runs，覆盖 t1 denovo / t2 sequence / t5 patchable / t8 safety 四类任务）全部以 DONE 终态完成（EVD-EXP-01）。所有 run 的 success_rate=1.0、schema_valid=1.0、executable_plan=1.0。每个 DONE 任务均包含至少一个 StepResult，`/tasks/{id}/report` 返回包含 scores、risk_flags、report_path 或 structure artifact 的有效 DesignResult（EVD-LOG-05、EVD-API-06）。`test_task_report_endpoint_done_contract_and_unfinished_404` 额外验证了 DONE 任务的 report 合约完整性和未完成任务请求 report 返回 404 的边界行为。

**TC-S11 工具链执行与 I/O 边界**：t8 和 t9 共 20 runs 中，所有工具调用（openfold、protgpt2、biopython_qc）均以 `status=success` 完成（EVD-EXP-01 的 `action_distribution.csv`）。OpenFold3 REST 执行模式验证通过，未出现 DUMMY 输入或 ProviderPayloadValidationError。`test_validate_plan_executability_reports_candidate_schema_and_io_boundary` 确定性验证了候选 schema 不匹配和上游 I/O 引用错误被结构化拒绝，不进入静默执行（EVD-TEST-03）。

---

## 6.11 本章小结

本章通过 13 个测试用例和 30 余个验证点对系统进行了多层次的工程验证。结果表明：

（1）API 服务稳定可用，15 个工具能力中有 7 个 ready，降级和不可用工具均有明确的 error_category 和 suggested_recovery 说明，为 Planner 的候选生成提供了运行时的能力依据。

（2）任务录入的渐进式确认链路（draft → confirm → task）工作正常，API 合约的异常边界（缺字段、互斥模式、未完成 report 请求等）均返回明确错误，PlannerAgent 生成的候选满足 candidate_id、score_breakdown 等 8 项必需合约字段。

（3）人在环路机制以 PendingAction/Decision 为契约基础，功能正确且边界严格——缺失候选 ID、重复决策和错误绑定均被拒绝，等待态下工具执行停止，决策应用后状态按 FSM 规则迁移，从 WAITING_ENTER 到 DECISION_APPLIED 到 WAITING_EXIT 的事件链完整可审计。

（4）FSM 的迁移路径合法，DONE/FAILED/CANCELLED 终态不可变。快照持久化在进入等待态前完成，恢复后不自动推进，runtime_state 与 Plan 语义隔离。

（5）Web 前端四个关键页面和 CLI 核心命令可用。18 张前端截图和 4 个 CLI 输出日志构成了跨入口的证据链，同一 task 在 Web、CLI 和 API 中的状态一致。CLI 的 timeline 和 report 子命令尚未实现，为当前限制。

（6）失败恢复的 retry → patch → replan 分层策略在单元和集成测试层面通过确定性触发验证。安全边界从判定（SafetyAgent block/warn）到执行（工具调用阻止）到审计（EventLog 记录）的全链路通过 4 个 focused test 覆盖。

系统功能正确性的验证为第 7 章的算法策略对比实验提供了可靠的基础设施——实验矩阵中出现的任何指标差异可以归因于策略配置的不同，而非系统本身的正确性缺陷。

---

## 图表清单

| 类型 | 编号 | 标题 | 来源 |
|------|------|------|------|
| 表 | 表 6-1 | 系统测试用例汇总 | `docs/system-validation/test-case-table.md`、`docs/system-validation/evidence-index.md` |
| 证据截图 | FIG-SV-01~18 | 前端验证截图，作为证据编号保留，当前不作为正文图编号 | `../thesis-project.dev/docs/system-validation/06-ui-screenshots/` |
