# 第六章 系统测试与验证

本章在第五章系统实现的基础上，对系统功能正确性和工程可用性进行验证。与第七章的策略对比实验不同，本章关注的问题是：系统是否按照第四章定义的架构、状态机、HITL 机制、工具适配机制和恢复机制正确运行。换言之，本章验证的是“系统能否可靠地承载实验”，第七章再进一步讨论不同规划策略在该系统之上的效果差异。

蛋白质设计工作流具有工具链长、单步代价高、输入输出格式差异大和失败恢复路径复杂等特点。如果只验证最终任务是否完成，无法判断错误来自任务设计、工具能力、工作流控制还是人工决策边界。因此，本章采用分层测试和证据追踪相结合的方法，将 API 合约、前端交互、命令行入口、有限状态机、HITL、快照恢复、安全边界和端到端执行分别纳入验证范围。科学工作流研究通常强调执行可靠性、数据来源追踪和失败恢复能力[@simmhan2009reliable]，开放环境 Agent 评测也强调真实交互路径中的执行稳健性和状态可观测性[@xie2024osworld]。本文系统验证沿用这一思路，将“是否可执行”和“是否可追溯”同时作为工程验证目标。

## 6.1 测试策略与验证目标

系统测试采用多层次、多入口的组合策略。在层次上，单元测试用于验证 Agent 职责边界、数据契约、状态迁移规则和恢复动作；集成测试用于验证 Planner、Executor、Safety、RuntimeEvaluator、Storage 等模块之间的协作；API 测试用于检查任务创建、事件读取、报告查询和决策提交等接口契约；手工验证与截图证据用于补充 Web 工作台和 CLI 的实际使用路径。

在入口上，系统覆盖 API、Web 工作台和命令行三种访问方式。API 是系统状态的统一事实来源；Web 工作台用于验证任务录入、候选审查、事件时间线和报告浏览；CLI 用于验证自动化或脚本化使用场景。三类入口读取同一任务记录、事件日志和报告产物，因此本章不仅检查单个入口是否可用，也检查同一 `task_id` 在不同入口下的状态一致性。

测试用例以 TC-S01 至 TC-S13 编号，覆盖 30 余个验证点，按功能维度分为环境与能力就绪、任务录入与数据契约、计划候选生成、HITL 决策、有限状态机、快照恢复、前端与 CLI 可用性、失败恢复、安全边界和端到端执行。表 6-1 汇总了各测试用例的覆盖范围、执行结果和核心证据。

**表 6-1 系统测试用例覆盖矩阵**

| 用例 | 测试类别 | 覆盖验证点 | 执行结果 | 核心证据 |
|---|---|---|---|---|
| TC-S01 | 环境与能力就绪 | SV-01、SV-27 | 通过 | EVD-API-01、EVD-API-02 |
| TC-S02 | API 合约与任务录入 | SV-02/03/04/07/25/26 | 通过 | EVD-TEST-01、EVD-API-03 至 EVD-API-08 |
| TC-S03 | 计划候选生成 | SV-08/09/10 | 通过 | EVD-TEST-02、EVD-LOG-04 |
| TC-S04 | HITL 决策一致性 | SV-10/11/12/13/15 | 通过 | EVD-TEST-02、FIG-SV-15 |
| TC-S05 | FSM 状态迁移 | SV-14/23/24 | 通过 | EVD-TEST-02、EVD-LOG-03 |
| TC-S06 | 快照持久化与恢复 | SV-14/28/29 | 通过 | EVD-TEST-02、EVD-LOG-01 至 EVD-LOG-03 |
| TC-S07 | Web 前端可用性 | SV-01、SV-30 | 通过 | FIG-SV-01 至 FIG-SV-18、EVD-TEST-01 |
| TC-S08 | CLI 可用性 | SV-02/03/25/26/30 | 部分通过 | EVD-CLI-01 至 EVD-CLI-04、EVD-TEST-04 |
| TC-S09 | 端到端任务流程 | SV-16/25/26 | 通过 | EVD-EXP-01、EVD-LOG-05 |
| TC-S10 | 异常输入与安全边界 | SV-04/05/06/11/13/21/24 | 通过 | EVD-TEST-03 |
| TC-S11 | 工具链执行与 I/O | SV-16/17 | 通过 | EVD-TEST-03、EVD-EXP-01 |
| TC-S12 | 失败恢复流程 | SV-18/19/20/22 | 通过 | EVD-TEST-03、EVD-LOG-01 至 EVD-LOG-03 |
| TC-S13 | 恢复止损与审计链路 | SV-21/23/25 | 通过 | EVD-TEST-02/03、EVD-LOG-03/04 |

由表 6-1 可见，13 个测试用例中 12 个通过，1 个部分通过。部分通过项为 CLI 可用性验证：`intake schema` 和 `task show` 等核心命令可用，`timeline show` 与 `report show` 当前仍输出 usage 提示，因此在终稿中作为实现限制说明，而不扩大为完整 CLI 报告浏览能力。

各测试用例的设计目的、前置条件、触发方式、预期结果和证据边界见附录 A。正文后续小节只展开与系统正确性论证直接相关的关键路径，避免将测试文档式细节全部放入正文。

本章使用的证据材料按编号前缀组织，如表 6-2 所示。正文仅保留必要证据编号，完整文件路径由系统验证材料索引维护。需要说明的是，FIG-SV-01 至 FIG-SV-18 是前端验证截图证据，本章不将其作为正式“图 6-x”编号插图，以避免正文图号与证据截图编号混用。

**表 6-2 系统验证证据类型索引**

| 证据前缀 | 证据类型 | 当前数量/范围 | 主要支撑内容 | 典型章节位置 |
|---|---|---|---|---|
| EVD-API | API 响应 JSON | 8 项 | 健康检查、能力 readiness、任务详情、事件、报告和 pending action 接口 | 6.2、6.3、6.4 |
| EVD-TEST | pytest 执行日志 | 4 组 | API、Web smoke、FSM/HITL/快照、安全恢复和 CLI 测试结果 | 6.1 至 6.8 |
| EVD-CLI | CLI 输出日志 | 4 项 | intake schema 与 task show 可用，timeline/report 子命令为当前限制 | 6.5 |
| FIG-SV | 前端截图 | 18 张 | Dashboard、Task Builder、Task Detail、Timeline 页面可用性 | 6.5 或附录 |
| EVD-LOG | EventLog / Snapshot / Report 样本 | 8 组 | 状态迁移、恢复闭环、terminal_stop、等待态快照与报告产物 | 6.4 至 6.8 |
| EVD-EXP | 实验矩阵与端到端运行聚合 | 4 项 | smoke/clean run、工具链执行和端到端流程证据 | 6.7、第七章 |

表 6-2 的作用在于明确不同证据承担的论证功能。API 响应用于证明接口契约，pytest 日志用于证明自动化验证结果，CLI 输出和前端截图用于证明交互入口可用，EventLog 与 Snapshot 用于证明运行时状态可追溯，实验聚合结果则用于证明系统能够承载批量端到端任务。

## 6.2 API 服务与任务录入验证

系统基础可用性首先通过健康检查和能力 readiness 接口验证。健康检查接口返回 `status=ok`、任务数量、ProteinToolKG 中的能力数量，以及日志、快照和输出目录等路径信息。能力 readiness 接口返回 15 条蛋白质设计工具或工具能力的运行状态，其中可直接调用的能力标记为 `ready`，远程服务不可达但不阻断系统运行的能力标记为 `degraded`，当前环境缺失的外部工具标记为 `unavailable`。每条 degraded 或 unavailable 记录均包含错误类别和建议恢复方式。该结果说明，系统并未将工具可用性写死为静态假设，而是在运行时向 Planner 和用户暴露当前环境的真实能力边界。

任务录入验证对应 TC-S02。系统通过 Task Intake 链路将自然语言目标转化为结构化任务规格，主要包括字段 schema 获取、草稿创建、字段补充、场景预检查和确认创建任务几个步骤。`/task-intakes/schema` 返回完整字段注册表，用于支撑前端动态表单；自由文本可以创建 intake 草稿；缺失必要字段时 confirm 请求被拒绝；`goal`、`query` 和 `confirmed_task_spec` 三种创建模式同时出现时被明确拒绝。这些验证对应第五章代码清单 5-1 中的互斥入口校验，说明实现层与测试层在任务边界上保持一致。

任务创建后的生命周期接口也被纳入验证范围。`/tasks/{task_id}` 返回任务目标、约束、计划、运行状态和报告路径等信息；`/tasks/{task_id}/events` 返回任务事件时间线；`/tasks/{task_id}/report` 在任务完成后返回设计结果摘要，在任务未完成时返回错误响应。对真实实验任务的 events 查询能够直接从磁盘日志读取 25KB 事件链，说明事件接口不依赖当前进程内的内存任务表，具备服务重启后追溯任务过程的基础。

## 6.3 计划候选与 HITL 验证

计划候选生成由 TC-S03 覆盖。测试确认 PlannerAgent 生成的 PlanCandidate 包含 `candidate_id`、`score_breakdown`、`risk_level`、`cost_estimate`、`explanation` 和 `source_refs` 等必需字段。该结果说明，候选计划不仅是可执行步骤列表，还包含可用于比较、解释和审计的评分与风险信息。测试同时确认 Planner 只负责生成候选，不直接执行工具，也不越权改变任务状态；这种边界与第四章的多 Agent 职责划分一致。

当候选计划置信度不足，或恢复动作需要人工确认时，系统通过 PendingAction 和 Decision 进入 HITL 流程。TC-S04 验证了 PendingAction 的创建、决策提交和异常边界。进入 `WAITING_PLAN_CONFIRM`、`WAITING_PATCH_CONFIRM` 或 `WAITING_REPLAN_CONFIRM` 状态前，系统必须创建对应的 PendingAction；提交 accept 决策时必须包含合法的 `selected_candidate_id`；对已处理的 PendingAction 重复提交决策会返回冲突；将 Decision 提交到不属于该任务的 PendingAction 会被拒绝。

这些验证说明，HITL 在系统中不是前端界面上的自由按钮，而是受状态机约束的运行时契约。等待态下 Executor 不会继续调用工具；决策生效后，系统写入 `DECISION_APPLIED` 和 `WAITING_EXIT` 等事件，再按有限状态机规则迁移到后续状态。EVD-LOG-08 中记录的 `PENDING_ACTION_CREATED -> WAITING_ENTER -> DECISION_SUBMITTED -> DECISION_APPLIED -> WAITING_EXIT` 事件链，提供了人工决策从创建到应用的完整审计路径。

## 6.4 状态机、快照与恢复基础验证

有限状态机验证对应 TC-S05。系统允许的状态迁移路径包括从 `CREATED` 到 `PLANNING`，再到 `PLANNED` 或等待人工确认状态；计划执行后进入 `RUNNING`，并根据执行结果进入等待局部修补、等待后缀重规划、总结或终态。测试覆盖了合法迁移和关键非法迁移，确认不在规则集合中的状态转换会被拒绝。DONE、FAILED 和 CANCELLED 作为终态，一旦进入便不可再被普通状态更新覆盖。

快照验证对应 TC-S06。系统要求进入任意 `WAITING_*` 状态前完成 PendingAction 写入、事件日志记录和 TaskSnapshot 保存。该顺序保证了系统即使在等待人工确认期间中断，也可以在恢复后还原 pending action、候选集合、已完成步骤、计划版本和运行时状态。恢复到等待态后，系统不会自动推进执行，而是继续等待人工 Decision，这一点对于保护 HITL 决策边界尤为关键。

快照验证还确认了运行时状态与计划语义字段的隔离。Lite belief-state / 轻量信念状态中的 `p_success`、`budget_pressure`、`recovery_margin` 等字段保存在 snapshot artifacts 的 RuntimeState 中，而 Plan 本身仍保持步骤、输入输出和约束定义。这样的隔离避免了运行时估计污染计划语义，也使不同策略配置可以在同一执行框架下比较。

## 6.5 前端与 CLI 可用性验证

系统的工程可用性不仅取决于后端接口，也取决于用户实际接触的交互入口。TC-S07 验证 Web 工作台，TC-S08 验证 CLI。表 6-3 汇总了两类入口的覆盖范围、证据和限制。

**表 6-3 前端与 CLI 可用性证据汇总**

| 入口 | 覆盖范围 | 证据编号 | 结论 | 限制 |
|---|---|---|---|---|
| Web Dashboard | 任务列表、状态摘要、能力提示 | FIG-SV-01、FIG-SV-02、EVD-TEST-01 | 通过 | 以截图和 smoke test 为主，不代表复杂浏览器兼容性测试。 |
| Task Builder | 字段注册表、草稿补充、安全预检查、任务确认 | FIG-SV-03 至 FIG-SV-11、EVD-API-03 | 通过 | 字段语义由 API schema 支撑，截图只作为交互证据。 |
| Task Detail | 任务状态、运行上下文、候选决策、报告与结构区域 | FIG-SV-12 至 FIG-SV-17、EVD-API-04、EVD-API-06 | 通过 | 结构区域应表述为产物入口与展示区域，不扩大为完整三维结构分析平台。 |
| Event Timeline | 状态迁移、步骤完成、等待进入、决策应用、等待退出 | FIG-SV-18、EVD-API-05 | 通过 | 当前以单任务样本展示全生命周期。 |
| CLI | intake schema、task show、timeline/report 命令 | EVD-CLI-01 至 EVD-CLI-04、EVD-TEST-04 | 部分通过 | timeline 和 report 子命令当前仅输出 usage，需作为限制说明。 |

Web 工作台的验证覆盖四类页面。Dashboard 展示任务列表、状态摘要和能力提示；Task Builder 覆盖从自由文本输入到字段补充、安全预检查和任务确认的流程；Task Detail 展示任务状态、运行上下文、候选决策区域、报告与结构产物入口；Event Timeline 展示状态迁移、步骤完成、等待进入、决策应用和等待退出事件。前端 smoke 测试和截图证据共同说明，用户可以通过 Web 入口完成任务查看、候选审查和事件追踪。

CLI 验证显示，`intake schema --json` 可以输出完整字段注册表，`task show` 可以展示任务 ID、状态、15 条能力 readiness 和恢复建议。CLI 自动化测试覆盖 16 个用例并全部通过。但 `timeline show` 和 `report show` 当前尚未提供完整展示能力，因此 TC-S08 标记为部分通过。该限制不影响 Web 和 API 对事件与报告的访问，但在终稿中需要如实说明。

## 6.6 失败恢复与安全边界验证

蛋白质设计工作流中，工具失败、输出缺失、远程服务不可达和安全风险都可能导致任务中断。本文系统将失败处理拆分为有界重试、局部修补、后缀重规划和终止止损几个层次。TC-S12 和 TC-S13 分别验证恢复流程和止损审计，TC-S10 验证安全边界。表 6-4 汇总了恢复与安全相关的主要证据。

**表 6-4 恢复与安全边界验证证据表**

| 验证主题 | 覆盖用例 | 关键行为 | 主要证据 | 结论边界 |
|---|---|---|---|---|
| 有界重试 | TC-S12 | 可重试失败进入有限重试，耗尽后交给恢复逻辑 | EVD-TEST-03、EVD-LOG-01 | 证明 retry 机制可达，不等同于所有工具失败都可恢复。 |
| 局部修补 | TC-S12 | retry exhausted 后生成 `patch_local` 候选并进入 `WAITING_PATCH_CONFIRM` | EVD-TEST-03、EVD-LOG-01、EVD-LOG-02 | 证明局部修补路径可执行，具体成功依赖失败类型。 |
| 后缀重规划/止损 | TC-S12、TC-S13 | 结构性失败或 `terminal_stop` 通过 FSM 进入重规划确认或 FAILED | EVD-TEST-02、EVD-TEST-03、EVD-LOG-03 | 证明 `stop` 不绕过 FSM/HITL。 |
| 安全 block | TC-S10、TC-S13 | forbidden motif 在 pre-step 阶段阻断工具调用 | EVD-TEST-03 | 矩阵实验未充分触发 safety block，结论主要来自 focused tests。 |
| 安全 warn | TC-S10 | warn 放行但记录风险标记和安全事件 | EVD-TEST-03、FIG-SV-10 | 证明风险可记录，不宣称自动生物安全判定完备。 |

有界重试验证确认，StepRunner 遇到可重试失败时会在限定次数内重试；若重试成功，工作流继续推进；若重试耗尽，则返回结构化失败结果，由上层恢复逻辑决定是否进入局部修补或后缀重规划。局部修补验证通过确定性触发 retry exhausted，随后生成 `patch_local` 候选并进入等待人工确认状态。相关日志显示，任务完成后可提取 `patch_event_count=1`、`first_pass_success=False`、`replan_event_count=0` 等恢复指标，说明恢复事件能够被后续实验统计利用。

当局部修补不足以恢复任务时，系统进入后缀重规划或止损路径。后缀重规划优先保留已完成前缀，仅替换失败后的后续步骤；`terminal_stop` 则作为终止型候选进入 HITL 确认。测试确认，接受 `terminal_stop` 后任务进入 FAILED 终态，并在事件日志中记录等待进入、决策应用和等待退出链路。这说明止损不是绕过状态机的异常退出，而是可审计的工作流决策。

安全边界验证覆盖输入、步骤和输出阶段的风险处理。focused tests 确认 forbidden motif 在 pre-step 阶段可以触发 block，并阻止工具调用；无 forbidden motif 时不会误阻断；warn 场景下系统允许继续执行，但会记录风险标记和安全事件。需要说明的是，批量实验中的安全探测任务未充分触发 safety block，因此安全机制的可达性主要由确定性测试支撑，不能扩大为对所有生物安全风险的自动判定能力。

## 6.7 端到端流程与工具链验证

端到端流程验证由 TC-S09 和 TC-S11 覆盖。TC-S09 关注从任务输入到 DesignResult 的完整成功路径，TC-S11 关注工具链执行和 I/O 边界。t8 四组 smoke run 和 t9 四组 clean run 共覆盖 20 次运行，涉及 denovo、sequence evaluation、patchable 和 safety 等任务类型，全部以 DONE 终态完成；对应证据为 EVD-EXP-01、EVD-LOG-05 和第七章表 7-8 所列实验产物。聚合结果显示，这些运行的 success rate、schema valid rate 和 executable plan rate 均为 1.0。

每个 DONE 任务至少包含一个 StepResult，报告接口可以返回 scores、risk flags、report path 或 structure artifact 等结果字段。未完成任务请求 report 时返回 404，这一边界避免了系统将中间状态误呈现为最终结果。工具链执行方面，实验运行中的 openfold、protgpt2、biopython_qc 等工具调用均以 success 状态完成，未出现 dummy 输入或 provider payload validation error。针对候选 schema 不匹配和上游 I/O 引用错误的确定性测试也确认，系统会在执行前结构化拒绝无效候选，而不是让错误在工具调用阶段静默扩散。

端到端验证的意义在于，它说明前述 API、状态机、HITL、快照、恢复和工具适配机制能够在完整任务中协同工作。第七章的 84-run 策略对比实验正是在这一工程验证基础上展开，因此实验结果中的差异可以优先归因于策略配置，而不是基本系统功能失效。

## 6.8 本章小结

本章围绕系统功能正确性和工程可用性，对 13 个测试用例、30 余个验证点和六类证据材料进行了整理。验证结果表明，系统在 API 服务、任务录入、候选生成、HITL 决策、有限状态机、快照恢复、前端入口、CLI 核心命令、失败恢复、安全边界和端到端执行方面均具备可追溯证据。

从执行结果看，TC-S01 至 TC-S07、TC-S09 至 TC-S13 均通过，TC-S08 部分通过。主要限制包括：CLI 的 timeline/report 子命令尚未完整实现；前端截图能够证明关键页面可用，但不等同于全面浏览器兼容性测试；安全 block 路径主要由确定性 focused tests 支撑，批量实验中的安全任务未充分触发阻断。上述限制不会否定系统作为实验平台的基本可用性，但需要在论文结论中保留边界。

总体而言，本章验证了系统能够在本文测试范围内承载任务创建、运行时控制、人工决策、工具执行、恢复处理和审计追踪。该结果为第七章的 CEBRA-WP 策略对比实验提供了工程基础：只有在系统执行链路和证据链路可用的前提下，后续关于成功率、首次成功率、高代价调用次数、恢复事件和运行时间的比较才具有解释意义。
