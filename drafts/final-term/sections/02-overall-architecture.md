# 总体架构

## 2.1 架构设计目标

根据需求分析，本系统需要同时满足蛋白质设计任务的自动化执行、关键节点的人工审查、运行时失败恢复以及论文实验所需的可观测性。为避免将复杂科研流程固化为不可调整的单一路径，系统采用分层架构和有限状态机相结合的设计方式：分层架构用于划分输入、规划、执行、安全汇总和资源能力；状态机用于约束任务生命周期和人工确认节点；CEBRA-WP 则位于规划与控制层，负责候选生成、运行时重排序和恢复动作选择。

系统架构设计遵循三个原则。第一，控制流与工具实现解耦。Workflow、FSM 和 PlanStep 是多步编排的单一控制来源，具体工具只通过适配器暴露能力，不直接参与全局决策。第二，自动化与可审查并存。系统默认支持自动执行，但在高风险、高成本或证据不足场景下必须通过 `PendingAction / Decision` 暂停并等待人工确认。第三，运行时证据参与决策。系统不把初始计划视为不可变流水线，而是在执行过程中持续消费 StepResult、SafetyResult、预算压力和恢复历史，必要时触发 patch、replan 或 stop 候选。

## 2.2 分层架构

系统整体可划分为五层：输入交互层、智能规划层、执行调度层、安全与汇总层、资源与基础设施层。五层之间以结构化契约传递任务、计划、步骤结果、风险事件和报告信息。

输入交互层面向用户、Web 工作台、CLI 和 API。该层负责接收自然语言目标与结构化约束，完成任务草稿、字段补充、确认和创建。实现中对应 FastAPI 入口、React 工作台页面、Task Builder、Pending Review 工作区和事件时间线等组件。输入层不直接操纵内部执行细节，而是通过 TaskAPI 与后端任务状态交互。

智能规划层由 PlannerAgent、候选生成器、ProteinToolKG 访问模块和 CEBRA-WP 相关策略构成。PlannerAgent 根据任务目标、约束和工具图谱生成 Plan、PlanPatch 或 Replan 候选集合，并对候选进行硬可行性过滤、静态评分、运行时调整和 Top-K 排序。该层是算法与系统交汇最集中的位置：工具链生成由 ProteinToolKG 支持，候选解释与默认建议由 Planner 输出，运行时重排和动作偏置由 `RuntimeState` 与 `RuntimeEvaluator` 支持。

执行调度层由 Workflow、PlanRunner、StepRunner、ExecutorAgent、ToolAdapter Registry 和执行后端组成。ExecutorAgent 不负责重新发明计划，而是根据已确认的 Plan 执行步骤、解析引用、调用适配器并记录 StepResult。Nextflow、远程模型服务或本地工具均被限定为单步执行后端：它们可以完成某个 PlanStep 的计算，但不承担多步工作流决策。

安全与汇总层包括 SafetyAgent、质量门禁、风险标记、SummarizerAgent 和报告生成逻辑。SafetyAgent 在输入、步骤和输出阶段产生 `SafetyResult`，可触发 WAITING_REPLAN_CONFIRM，但不直接修改 Plan 或终止任务。SummarizerAgent 在执行完成后汇总序列、结构、指标、风险和恢复历史，生成 `DesignResult` 及报告产物。

资源与基础设施层包括 ProteinToolKG、配置文件、模型提供方、日志存储、快照存储、文件产物目录和运行时初始化逻辑。当前实现采用 JSON 形式的工具知识图谱、本地文件系统产物、事件日志和快照存储；设计文档中提出的数据库或图数据库迁移属于后续扩展方向，不应作为当前已完成事实表述。

## 2.3 核心组件及职责

系统核心组件围绕四类 Agent 和若干基础模块展开。

PlannerAgent 是计划搜索与恢复候选生成的核心组件。它读取任务目标与约束，查询 ProteinToolKG，生成初始计划候选；当执行失败或安全阻断发生时，它生成局部 patch 或后缀 replan 候选。PlannerAgent 的职责是提出可解释、可执行的候选方案，而不是绕过人工确认直接做最终选择。

ExecutorAgent 是计划执行者。它通过 PlanRunner 和 StepRunner 执行步骤，解析 `PlanStep.inputs` 中的上游引用，调用 AdapterRegistry 中注册的工具适配器，并将输出收敛为 StepResult。ExecutorAgent 能识别步骤失败和重试耗尽等信号，并触发恢复流程，但不自行决定是否应用 patch。

SafetyAgent 是风险信号源。它面向输入、过程和输出执行安全检查，并用 `ok`、`warn`、`block` 等等级表达风险。SafetyAgent 的输出可以阻断自动推进并触发 replan 候选生成，但其角色仍是风险判定者和建议者，而非最终决策者。

SummarizerAgent 是结果汇总组件。它读取任务、计划、中间结果、安全事件和恢复历史，生成面向用户阅读的报告和机器可读的 DesignResult。其职责边界被限定在汇总与展示，不参与工作流控制和人工决策。

ToolAdapter 层负责外部工具接入。`BaseToolAdapter` 定义统一的输入解析、本地执行、远程执行、能力描述、健康检查、成本估计和错误归一化接口；`AdapterRegistry` 负责根据 tool_id 或 adapter_id 获取具体适配器。该设计使 Executor 可以面向统一接口调度工具，具体工具的命令行、远程调用、容器或脚本细节被隔离在适配器内部。

ProteinToolKG 是规划层的重要资源。它描述工具能力、输入输出、兼容关系、成本、安全等级和版本信息。Planner 依赖这些信息进行能力匹配、I/O 闭包校验、安全过滤和成本排序。工具知识图谱的存在使系统能够从“固定流水线”转向“能力驱动的工具链组合”。

## 2.4 任务生命周期与 FSM

系统使用有限状态机描述任务生命周期。对外状态包括 `CREATED`、`PLANNING`、`WAITING_PLAN_CONFIRM`、`PLANNED`、`RUNNING`、`WAITING_PATCH_CONFIRM`、`WAITING_REPLAN_CONFIRM`、`SUMMARIZING`、`DONE`、`FAILED` 和 `CANCELLED`。实现侧还保留 `PATCHING`、`REPLANNING` 等内部状态，并映射到对外等待确认状态，以兼顾执行细节与用户理解。

标准任务流程为：任务创建后进入规划阶段，Planner 生成候选计划；若满足自动执行条件，系统固化默认计划并进入执行；若触发人工确认，系统创建 `PendingAction(plan_confirm)` 并进入 `WAITING_PLAN_CONFIRM`。执行阶段由 Executor 按步骤推进，正常完成后进入汇总并最终结束。若执行中出现局部失败，系统生成 patch 候选并进入 `WAITING_PATCH_CONFIRM`；若出现整体风险、目标偏离或恢复余量不足，系统生成 replan 候选并进入 `WAITING_REPLAN_CONFIRM`。

所有 `WAITING_*` 状态都具有明确语义：系统已经暂停推进，等待人类提交结构化 Decision。进入等待状态前，系统必须完成 PendingAction 写入、事件日志记录和任务快照保存。这样即使进程在等待期间中断，任务也可以恢复到同一个决策场景，而不会丢失候选、默认建议或执行前缀。

## 2.5 数据流与控制流

系统的数据流以统一契约为核心。用户输入首先被转换为 `ProteinDesignTask`，其中包括任务目标、约束和元数据。Planner 输出 `Plan`，由若干 `PlanStep` 组成；每个步骤声明工具、输入和元数据。Executor 执行后产生 `StepResult`，记录状态、输出、指标、风险标记、错误信息和产物路径。SafetyAgent 产生 `SafetyResult`，SummarizerAgent 最终形成 `DesignResult`。当系统进入人工确认环节时，`PendingActionCandidate` 承载 Plan、PlanPatch 或 Replan 的候选载荷，`Decision` 记录用户选择。

控制流则由 Workflow/FSM 统一约束。PlanRunner 驱动 `PLANNED -> RUNNING -> SUMMARIZING` 的正常路径；PendingAction 工具函数负责进入等待状态前的候选、日志和快照写入；Decision Apply 模块负责将人工决策应用到当前任务记录，并触发后续状态迁移。CEBRA-WP 的运行时动作选择不会绕过这些控制边界，而是映射到既有恢复闭环：`continue` 对应继续执行，`patch_local` 对应局部修补，`suffix_replan` 对应后缀重规划，`stop` 作为终止型 replan 候选进入等待确认。

## 2.6 CEBRA-WP 在架构中的位置

CEBRA-WP 不作为独立外部服务存在，而是嵌入智能规划层和运行时控制层。它的输入来自任务约束、工具知识图谱、候选 payload、StepResult、SafetyResult、失败上下文和 RuntimeState；输出表现为候选排序、默认建议、运行时调整、动作 utility 和恢复动作建议。

在初始规划阶段，CEBRA-WP 负责对候选工具链进行可行性过滤和多目标评分，保证候选不仅与目标相关，还满足工具可用性、I/O 闭包、安全等级和预算限制。在执行阶段，CEBRA-WP 通过 Lite belief-state 消费运行时观测，估计 `p_success`、`p_structural_failure`、`recovery_margin`、`expected_remaining_cost`、`evidence_sufficiency` 和 `budget_pressure` 等变量，并据此调整候选排序或选择恢复动作。在 HITL 阶段，算法输出的解释字段被展示给用户，用于说明为什么推荐某个候选，为什么建议 patch、replan 或 stop。

这种位置安排使算法与系统职责保持一致：算法负责“如何根据约束与证据形成建议”，系统负责“如何执行、等待、记录和恢复”。因此，CEBRA-WP 不是替代 FSM 的新控制器，而是受 FSM、Agent 边界和人工确认机制约束的决策核心。

## 2.7 架构小结

总体而言，本系统采用“分层架构 + 多 Agent 协作 + FSM 控制 + ToolAdapter 接入 + CEBRA-WP 决策”的组合架构。分层设计保证了交互、规划、执行、安全和资源能力的边界清晰；FSM 保证了任务生命周期和人工确认的合法性；ToolAdapter 保证了外部工具的可替换性；CEBRA-WP 则使系统能够从静态工具链执行升级为证据感知、恢复自适应的科研工作流控制。该架构为后续模块设计、详细设计和实验验证提供了统一基础。

