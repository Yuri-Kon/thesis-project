# 第六章 系统测试与验证

本章在第五章系统实现的基础上，验证系统功能正确性和工程可用性。与第七章的策略对比实验不同，本章关注系统是否按照第四章定义的架构、状态机、HITL 机制、工具适配机制和恢复机制运行。也就是说，本章先回答“系统能否可靠地承载实验”，第七章再讨论不同规划策略在该系统上的行为差异。

蛋白质设计工作流工具链长、单步代价高、失败路径复杂，仅检查最终完成状态不足以定位问题。本章采用分层测试和证据追踪，覆盖 API、前端、CLI、FSM、HITL、快照恢复、安全边界和端到端执行，并同时关注“可执行”和“可追溯”。

## 6.1 测试策略与验证目标

测试采用多层次、多入口的测试策略。单元测试检查职责边界、相关数据契约、状态迁移和恢复动作；集成测试检查 Planner、Executor、Safety、RuntimeEvaluator、Storage 协作；API、Web 和 CLI 验证实际使用路径。

系统覆盖 API、Web 工作台和 CLI 三种入口。API 是状态事实来源，Web 用于任务录入、候选审查、时间线和报告浏览，CLI 用于自动化场景；三者读取同一任务记录、事件日志和报告产物。

测试用例 TC-S01 至 TC-S13 覆盖环境与能力就绪、任务录入、候选生成、HITL、FSM、快照、前端与 CLI、失败恢复、安全边界和端到端执行。表 6-1 汇总了覆盖范围、执行结果和证据。

| 用例 | 测试类别 | 覆盖验证点 | 执行结果 | 核心证据 |
|:--:|:--:|:--:|:--:|:--:|
| TC-S01 | 环境与能力就绪 | SV-01、SV-27 | 通过 | EVD-API-01、EVD-API-02 |
| TC-S02 | API 合约与任务录入 | SV-02/03/04/07/25/26 | 通过 | EVD-TEST-01、EVD-API-03 至 EVD-API-08 |
| TC-S03 | 计划候选生成 | SV-08/09/10 | 通过 | EVD-TEST-02、EVD-LOG-04 |
| TC-S04 | HITL 决策一致性 | SV-10/11/12/13/15 | 通过 | EVD-TEST-02、FIG-SV-15 |
| TC-S05 | FSM 状态迁移 | SV-14/23/24 | 通过 | EVD-TEST-02、EVD-LOG-03 |
| TC-S06 | 快照持久化与恢复 | SV-14/28/29 | 通过 | EVD-TEST-02、EVD-LOG-01 至 EVD-LOG-03 |
| TC-S07 | Web 前端可用性 | SV-01、SV-30 | 通过 | FIG-SV-01 至 FIG-SV-18、EVD-TEST-01 |
| TC-S08 | CLI可用性 | SV-02/03/25/26/30 | 部分通过 | EVD-CLI-01 至 EVD-CLI-04、EVD-TEST-04 |
| TC-S09 | 端到端任务流程 | SV-16/25/26 | 通过 | EVD-EXP-01、EVD-LOG-05 |
| TC-S10 | 异常输入与安全边界 | SV-04/05/06/11/13/21/24 | 通过 | EVD-TEST-03 |
| TC-S11 | 工具链执行与 I/O | SV-16/17 | 通过 | EVD-TEST-03、EVD-EXP-01 |
| TC-S12 | 失败恢复流程 | SV-18/19/20/22 | 通过 | EVD-TEST-03、EVD-LOG-01 至 EVD-LOG-03 |

表 6-1 系统测试用例覆盖矩阵

表 6-1（续表）

<table>
<colgroup>
<col style="width: 18%" />
<col style="width: 1%" />
<col style="width: 18%" />
<col style="width: 1%" />
<col style="width: 19%" />
<col style="width: 3%" />
<col style="width: 12%" />
<col style="width: 3%" />
<col style="width: 20%" />
</colgroup>
<thead>
<tr>
<th style="text-align: center;">用例</th>
<th colspan="2" style="text-align: center;">测试类别</th>
<th colspan="3" style="text-align: center;">覆盖验证点</th>
<th style="text-align: center;">执行结果</th>
<th colspan="2" style="text-align: center;">核心证据</th>
</tr>
</thead>
<tbody>
<tr>
<td colspan="2">TC-S13</td>
<td colspan="2">恢复止损与审计链路</td>
<td>SV-21/23/25</td>
<td colspan="3">通过</td>
<td>EVD-TEST-02/03、EVD-LOG-03/04</td>
</tr>
</tbody>
</table>

由表 6-1 可见，13 个测试用例中 12 个通过，1 个部分通过。部分通过项为 CLI 可用性验证：intake schema 和 task show 等核心命令可用，timeline show 与 report show 当前仍输出 usage 提示，因此在终稿中作为实现限制说明。

各测试用例的设计目的、前置条件、触发方式、预期结果和证据边界见附录 A。正文后续小节只展开与系统正确性论证直接相关的关键路径，避免将测试文档式细节全部放入正文。

本章使用的证据材料按编号前缀组织，如表 6-2所示。正文仅保留必要证据编号，完整文件路径由系统验证材料索引维护。FIG-SV-01 至 FIG-SV-18 属于前端验证截图证据，本章不将其作为正式“图 6-x”编号插图，以避免正文图号与证据截图编号混用。

| 证据前缀 | 证据类型 | 当前数量/范围 | 主要支撑内容 |
|:--:|:--:|:--:|:--:|
| EVD-API | API响应JSON | 8项 | 健康检查、能力readiness、任务详情、事件、报告和pending action接口 |
| EVD-TEST | Pytest执行日志 | 4组 | API、Web smoke、FSM/HITL/快照、安全恢复和 CLI 测试结果 |
| EVD-CLI | CLI 输出日志 | 4项 | intake schema 与 task show 可用，timeline/report 子命令为当前限制 |
| FIG-SV | 前端截图 | 18 张 | Dashboard、Task Builder、Task Detail、Timeline 页面可用性 |

表 6-2 系统验证证据类型索引

表 6-2（续表）

| 证据前缀 | 证据类型 | 当前数量/范围 | 主要支撑内容 |
|:--:|:--:|:--:|:--:|
| EVD-LOG | EventLog/ Snapshot/Report 样本 | 8组 | 状态迁移、恢复闭环、`terminal_stop`、等待态快照与报告产物 |
| EVD-EXP | 实验矩阵与端到端运行聚合 | 4 项 | smoke/clean run 记录、工具链执行结果和端到端流程证据 |

表 6-2 主要用于区分不同证据的论证功能。API 响应主要用于支撑接口契约，pytest 日志支撑自动化验证结果，CLI 输出和前端截图支撑交互入口可用性，EventLog 与 Snapshot 支撑运行时状态可追溯性，实验聚合结果则说明系统可以承载批量端到端任务。

## 6.2 API 服务与任务录入验证

系统重要基础可用性通过健康检查和能力 readiness 接口验证。/health 返回服务状态、任务数、能力数量和数据目录；/capabilities/readiness 返回 15 条能力记录，并区分 ready、degraded 和 unavailable，同时给出错误类别和恢复建议。这样，系统向 Planner 和用户暴露真实的能力边界，而不是假设所有工具始终可用。

TC-S02 验证 Task Intake 和任务创建边界。/task-intakes/schema 会返回字段注册表，自由文本可创建草稿，缺失必要字段的 confirm 会被系统拒绝，goal、query、confirmed_task_spec 三种创建模式互斥。该结果对应第五章的入口校验。

生命周期接口验证包括 /tasks/{task_id}、/events 和 /report。完成任务可读取结果摘要，未完成任务请求报告返回错误；真实实验任务的 events 查询可直接读取磁盘日志，说明事件追踪不依赖当前进程内存。

## 6.3 计划候选与 HITL 验证

计划候选生成通过 TC-S03 覆盖。测试确认 PlannerAgent 生成的 PlanCandidate 包含 candidate_id、score_breakdown、risk_level、cost_estimate、explanation 和 source_refs 等必需字段。候选计划不是简单的可执行步骤列表，还包含可比较、可解释和可审计的评分与风险信息。测试还确认 Planner 只生成候选，不直接执行工具，也不越权改变任务状态；这一边界与第四章的多 Agent 职责划分相一致。

当候选计划置信度不足，或恢复动作需要人工确认时，系统通过 PendingAction 和 Decision 进入 HITL 流程。TC-S04 验证了 PendingAction 的创建、决策提交和异常边界。进入 WAITING_PLAN_CONFIRM、WAITING_PATCH_CONFIRM 或 WAITING_REPLAN_CONFIRM 状态前，系统必须创建对应的 PendingAction；提交 accept 决策时必须包含合法的 selected_candidate_id；对已处理的 PendingAction 重复提交决策会返回冲突；将 Decision 提交到不属于该任务的 PendingAction 会被拒绝。

从这些验证结果来看，HITL 在系统中不是前端界面上的自由触发的按钮，而是受状态机约束的运行时契约。等待态下 Executor 不继续调用工具；决策生效后，系统写入 DECISION_APPLIED 和 WAITING_EXIT 等事件，再按有限状态机规则迁移到后续状态。EVD-LOG-08 记录的 PENDING_ACTION_CREATED -\> WAITING_ENTER -\> DECISION_SUBMITTED -\> DECISION_APPLIED -\> WAITING_EXIT 事件链，展示了人工决策从创建到应用的完整审计路径。

## 6.4 状态机、快照与恢复基础验证

有限状态机验证主要对应 TC-S05。系统允许的状态迁移路径包括从 CREATED 到 PLANNING，再到 PLANNED 或等待人工确认状态；计划执行后进入 RUNNING，并根据执行结果进入等待局部修补、等待后缀重规划、总结或终态。测试覆盖合法迁移和关键非法迁移，确认不在规则集合中的状态转换会被系统拒绝。DONE、FAILED 和 CANCELLED 作为终态，一旦进入便不可再被普通状态更新覆盖。

快照验证对应， TC-S06。系统要求在进入任意 WAITING_\* 状态前完成 PendingAction 写入、事件日志记录和 TaskSnapshot 保存。这一顺序保证系统即使在等待人工确认期间中断，恢复后仍能还原 pending action、候选集合、已完成步骤、计划版本和运行时状态。恢复到等待态后，系统不会自动推进执行，而是继续等待人工 Decision；这正是 HITL 决策边界需要保护的地方。

快照验证还关注运行时状态与计划语义字段之间是否保持隔离。Lite belief-state / 轻量信念状态中的相关状态量写入 snapshot artifacts 的 `RuntimeState`，而 Plan 继续保存步骤、输入输出和约束定义。这样处理可以避免运行时估计污染计划语义，也便于在同一执行框架下比较不同策略配置。

## 6.5 前端与 CLI 可用性验证

系统的工程可用性不仅取决于后端接口，也取决于用户实际接触的交互入口。TC-S07 验证 Web 工作台，TC-S08 验证 CLI。表 6-3 汇总了两类入口的覆盖范围、证据和限制。

| 入口 | 覆盖范围 | 证据编号 | 结论 | 限制 |
|:--:|:--:|:--:|:--:|:--:|
| Web Dashboard | 任务列表、状态摘要、能力提示 | FIG-SV-01、FIG-SV-02、EVD-TEST-01 | 通过 | 以截图和 smoke test 为主，复杂浏览器兼容性仍需另行验证 |
| Task Builder | 字段注册表、草稿补充、安全预检查、任务确认 | FIG-SV-03 至 FIG-SV-11、EVD-API-03 | 通过 | 字段语义由 API schema 支撑，截图只作为交互证据。 |
| Task Detail | 任务状态、运行上下文、候选决策、报告与结构区域 | FIG-SV-12 至 FIG-SV-17、EVD-API-04、EVD-API-06 | 通过 | 结构区域应表述为产物入口与展示区域，不扩大为完整三维结构分析平台。 |
| Event Timeline | 状态迁移、步骤完成、等待进入、决策应用、等待退出 | FIG-SV-18、EVD-API-05 | 通过 | 当前以单任务样本展示全生命周期。 |
| CLI | intake schema、task show、timeline/report 命令 | EVD-CLI-01 至 EVD-CLI-04、EVD-TEST-04 | 部分通过 | timeline 和 report 子命令当前仅输出 usage，需作为限制说明。 |

表 6-3 前端与 CLI 可用性证据汇总

Web 工作台验证覆盖 Dashboard、Task Builder、Task Detail 和 Event Timeline。前端 smoke 测试和截图证据表明，用户可以查看任务状态、补充任务字段、审查候选、读取报告并追踪事件。

CLI 验证显示，intake schema --json 能输出完整字段注册表，task show 能展示任务 ID、状态、15 条能力 readiness 和恢复建议。CLI 自动化测试覆盖 16 个用例并全部通过。但在本文场景中，timeline show 和 report show 目前尚未提供完整展示能力，因此 TC-S08 标记为部分通过。该限制不影响 Web 和 API 对事件与报告的访问，但终稿需要如实保留。

## 6.6 失败恢复与安全边界验证

蛋白质设计工作流中，工具失败、输出缺失、远程服务不可达和安全风险都可能导致任务中断。本文系统将失败处理拆分为有界重试、局部修补、后缀重规划和终止止损几个层次。TC-S12 和 TC-S13 分别验证恢复流程和止损审计，TC-S10 验证安全边界。表 6-4 汇总了恢复与安全相关的主要证据。

| 验证主题 | 覆盖用例 | 关键行为 | 主要证据 | 结论边界 |
|:--:|:--:|:--:|:--:|:--:|
| 有界重试 | TC-S12 | 可重试失败进入有限重试，耗尽后交给恢复逻辑 | EVD-TEST-03、EVD-LOG-01 | 证明 retry 机制可达，不等同于所有工具失败都可恢复。 |
| 局部修补 | TC-S12 | retry exhausted 后生成 `patch_local` 候选并进入 WAITING_PATCH_CONFIRM | EVD-TEST-03、EVD-LOG-01、EVD-LOG-02 | 证明局部修补路径可执行，具体成功依赖失败类型。 |

表 6-4 恢复与安全边界验证证据表

表 6-4（续表）

| 验证主题 | 覆盖用例 | 关键行为 | 主要证据 | 结论边界 |
|:--:|:--:|:--:|:--:|:--:|
| 后缀重规划/止损 | TC-S12、TC-S13 | 结构性失败或 `terminal_stop` 通过 FSM 进入重规划确认或 FAILED | EVD-TEST-02、EVD-TEST-03、EVD-LOG-03 | 证明 stop 不绕过 FSM/HITL。 |
| 安全 block | TC-S10、TC-S13 | forbidden motif 在 pre-step 阶段阻断工具调用 | EVD-TEST-03 | 矩阵实验未充分触发 safety block，结论主要来自 focused tests。 |
| 安全 warn | TC-S10 | warn 放行但记录风险标记和安全事件 | EVD-TEST-03、FIG-SV-10 | 证明风险可记录，不宣称自动生物安全判定完备。 |

恢复验证确认：StepRunner 对可重试失败进行有界重试；重试耗尽后返回结构化失败，由上层决定 `patch_local` 或 `suffix_replan`。确定性样本触发 `patch_local` 并进入人工确认，日志可提取 patch_event_count=1、first_pass_success=False、replan_event_count=0 等指标。

当局部修补仍不足以让任务恢复时，系统会转入后缀重规划或止损路径。后缀重规划尽量保留已完成前缀，只替换失败之后的步骤；`terminal_stop` 则作为终止型候选进入 HITL 确认。测试结果显示，接受 `terminal_stop` 后任务进入 FAILED 终态，并在事件日志中保留等待进入、决策应用和等待退出链路，说明止损也属于可审计的工作流决策。

安全边界验证覆盖输入、步骤和输出阶段的风险处理。focused tests 确认 forbidden motif 在 pre-step 阶段可以触发 block 并阻止工具调用；无 forbidden motif 时不会误阻断；warn 场景下系统允许继续执行，同时记录风险标记和安全事件。批量实验中的安全探测任务未充分触发 safety block，因此安全机制的可以达到性主要由确定性测试支撑，不能扩大为对所有生物安全风险的自动判定能力。

## 6.7 端到端流程与工具链验证

端到端流程验证由 TC-S09 和 TC-S11 覆盖。TC-S09 关注从任务输入到 DesignResult 的完整成功路径，TC-S11 关注工具链执行和 I/O 边界。t8 四组 smoke run 和 t9 四组 clean run 共覆盖 20 次运行，涉及 denovo、sequence evaluation、patchable 和 safety 等任务类型，全部以 DONE 终态完成；对应证据为 EVD-EXP-01、EVD-LOG-05 和第七章表 7-8 所列实验产物。聚合结果显示，这些运行的 success rate、schema valid rate 和 executable plan rate 均为 1.0。

端到端验证要求 DONE 任务至少包含一个 StepResult，报告接口返回 scores、risk flags、report path 或 structure artifact；未完成任务请求 report 返回 404。实验中的 openfold、protgpt2、biopython_qc 等调用均为 success，候选 schema 不匹配和上游 I/O 引用错误也能在执行前被结构化拒绝。

端到端验证说明，API、状态机、HITL、快照、恢复和工具适配等机制可以在完整任务中协同工作。第七章的 84-run 策略对比实验建立在这一工程验证重要基础上，因此实验结果中的差异可以优先从策略配置解释，而不是归因于基本系统功能失效。

## 6.8 本章小结

本章围绕系统功能正确性和工程可用性，整理了 13 个测试用例、30 余个验证点和六类证据材料。结果表明，系统在 API 服务、任务录入、候选生成、HITL 决策、有限状态机、快照恢复、前端入口、CLI 核心命令、失败恢复、安全边界和端到端执行方面均具备可追溯证据。

综合执行记录来看，TC-S01 至 TC-S07、TC-S09 至 TC-S13 均通过，TC-S08 为部分通过。主要限制包括：CLI 的 timeline/report 子命令尚未完整实现；前端截图证明了关键页面可用，但不能等同于全面浏览器兼容性测试；安全 block 路径主要由确定性 focused tests 支撑，批量实验中的安全任务未充分触发阻断。这些限制不影响系统作为实验平台的基本可用性，但论文结论需要保留相应边界。

在本文测试范围内，系统可以承载任务创建、运行时控制、人工决策、工具执行、恢复处理和审计追踪。这个结果为第七章的 CEBRA-WP 策略对比实验提供了工程重要基础：只有执行链路和证据链路可用，后续关于成功率、首次成功率、高代价调用次数、恢复事件和运行时间的比较才具备解释意义。
