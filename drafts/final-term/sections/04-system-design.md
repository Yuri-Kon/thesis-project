# 第四章：系统总体设计（草稿）

> 状态：从 Ch3 合并稿拆分 · 2026-05-11 · 目标章节文件 `chapters/04-system-design.tex`
> 本章承接第 3 章需求分析，展开五层架构、FSM、六阶段工作流、CEBRA-WP 算法和模块设计。

---

本章在第 3 章需求分析的基础上，展开系统的总体设计。设计围绕四个核心问题：系统如何分层组织各组件（4.1 分层架构），任务的全生命周期如何被有限状态机约束（4.3 FSM），蛋白质设计业务如何被组织为可组合的能力阶段（4.4 六阶段工作流），以及 CEBRA-WP 算法如何嵌入规划与控制层实现运行时自适应（4.5 CEBRA-WP）。最后通过模块划分和协作流程展示各组件在典型任务中的交互关系（4.7-4.8）。

## 4.1 五层分层架构

根据需求分析，系统同时承载自动化执行、人工审查、运行时恢复和实验观测等多重职责。为避免将复杂科研流程固化为不可调整的单一路径，系统采用五层分层架构，如图 4-1 所示。

**输入层**面向用户、Web 工作台、CLI 和 API，负责接收自然语言目标与结构化约束，完成任务草稿、字段补充、确认和创建。实现上对应 FastAPI 接口和 React 工作台的 Dashboard、Task Builder、Pending Review 工作区和 Event Timeline 等页面组件。

**智能规划层**以 PlannerAgent 为中心，包含候选生成器、ProteinToolKG 查询模块和 CEBRA-WP 相关策略（版本 `cebra_wp.v2`）。PlannerAgent 根据任务目标与约束生成 Plan、PlanPatch 或 Replan 候选集合，对候选进行硬可行性过滤（工具存在性、schema 合法性、I/O 闭包、安全等级、预算约束、工具可用性）、静态多目标评分、运行时调整和 Top-K 排序。

**执行层**由 ExecutorAgent、PlanRunner、StepRunner 和恢复控制逻辑组成。ExecutorAgent 根据已确认的计划执行步骤、解析上游引用、调用适配器并记录 StepResult。恢复控制遵循 bounded retry → minimal patch → suffix replan 的层级策略。FSM 和 Workflow 是状态变化的唯一来源（SSOT），Nextflow 等外部流程引擎被限定为单步执行后端，其控制边界不超过单个 PlanStep。

**安全与汇总层**包括 SafetyAgent 和 SummarizerAgent。SafetyAgent 贯穿输入、执行和输出阶段进行风险判定，输出 ok、warn、block 等等级；SummarizerAgent 在任务完成后汇总序列、结构、指标和恢复历史，生成 DesignResult 及报告产物。

**资源层**包括 ToolAdapter 注册表、ProteinToolKG、EventLog、TaskSnapshot 和文件产物管理。ToolAdapter 通过 BaseToolAdapter 抽象接口和 AdapterRegistry 注册机制实现外部工具的接入；ProteinToolKG 以 JSON 形式描述工具能力、输入输出、兼容关系、成本、安全等级和版本信息，为 Planner 提供能力驱动的工具链组合依据。

五层之间以结构化契约传递任务、计划、步骤结果、风险事件和报告信息（核心数据契约详见 4.6 节）。PendingAction 和 Decision 是贯穿输入层、规划层和执行层的横切契约：输入层负责展示和收集，规划层负责生成候选载荷，执行层负责验证和应用。

> **图 4-1**：系统分层架构图，展示五层划分、层间数据流、控制面 SSOT 和可恢复审计链。

## 4.2 核心组件

系统围绕四类 Agent 组织核心逻辑，Agent 角色边界受 `AGENT_CONTRACT.md` 约束，各组件不得越权。

**PlannerAgent** 是计划搜索与恢复候选生成的核心。它读取任务目标与约束，查询 ProteinToolKG，生成初始计划候选；当执行失败或安全阻断发生时，生成局部 patch 或后缀 replan 候选。PlannerAgent 的职责是提出可解释、可执行的候选方案，不得执行工具、直接检查运行时产物或变更任务状态。其输出通过 `PendingActionCandidate` 承载，必须包含 `candidate_id`、`score_breakdown`、`risk_level`、`cost_estimate`、`explanation` 和 `source_refs` 字段（TC-S03 验证通过）。

**ExecutorAgent** 是计划执行者，也是唯一的工具调度者。它通过 PlanRunner 驱动完整计划的执行生命周期，通过 StepRunner 处理单个步骤的输入解析、依赖引用和适配器调用。ExecutorAgent 能识别步骤失败和重试耗尽等信号并触发恢复流程，但不自行决定是否应用 patch——该决策由 Planner 生成候选，经 HITL 或自动策略确认。在任何 WAITING_* 状态下，ExecutorAgent 必须停止工具执行。

**SafetyAgent** 是风险信号源。它面向输入、过程和输出执行安全检查，输出 risk_level、risk_code、message 和 scope 等字段。SafetyAgent 的角色是风险判定者和建议者，不得执行工具、编辑计划或覆写工作流结果。block 等级可以阻断自动推进并触发 replan 候选生成，但不直接修改 Plan 或终止任务。

**SummarizerAgent** 是结果汇总组件。它读取任务上下文（计划、步骤结果、安全事件和恢复历史），生成面向用户阅读的报告和机器可读的 DesignResult。其职责边界被限定在汇总与展示，不得重新执行工具或更改计划/状态。

**ToolAdapter 层**通过 BaseToolAdapter 抽象接口（定义 `resolve_inputs`、`run_local`、`run_remote`、`healthcheck`、`normalize_error`、`estimate_cost` 等方法）和 AdapterRegistry 注册机制实现外部工具的接入。Executor 面向统一接口调度工具，具体工具的命令行、远程调用和容器细节被隔离在适配器内部。**ProteinToolKG** 以 JSON 形式描述工具的能力（capability）、输入输出、兼容关系（compat）、成本（cost）、安全等级（safety_level）和版本信息，规划规则包括 I/O 匹配、安全匹配和成本优先三条基本约束。

## 4.3 任务生命周期与有限状态机

系统使用有限状态机描述和控制任务生命周期，如图 4-2 所示。该 FSM 不仅是进度指示器，也编码了决策阶段与人工审查点。对外状态包括 CREATED、PLANNING、WAITING_PLAN_CONFIRM、PLANNED、RUNNING、WAITING_PATCH_CONFIRM、WAITING_REPLAN_CONFIRM、SUMMARIZING、DONE、FAILED 和 CANCELLED 共 11 个状态。其中以 WAITING_ 前缀的状态具有明确语义：系统已暂停推进，等待人类提交结构化 Decision。终态 DONE、FAILED、CANCELLED 不可再变更——该不变性受 `AGENT_CONTRACT.md` 保护，系统验证 TC-S05 已通过。

标准任务流程如下：CREATED → PLANNING，Planner 生成候选计划；若满足自动执行条件（默认策略允许且候选置信度充分），系统自动选择默认建议并进入 PLANNED；若触发人工确认条件（高成本、低置信度、安全警告等），系统创建 `PendingAction(plan_confirm)` 并进入 WAITING_PLAN_CONFIRM。确认后的计划进入 RUNNING，Executor 按步骤推进。正常完成后进入 SUMMARIZING，最终到达 DONE。

恢复路径嵌入执行阶段。当某步骤出现局部失败且重试耗尽后，系统生成 patch 候选并进入 WAITING_PATCH_CONFIRM；当出现安全阻断、结构性失败或恢复余量不足时，系统生成 replan 候选（可包含 terminal_stop）并进入 WAITING_REPLAN_CONFIRM。人工决策接受后，patch 或 replan 被应用，系统恢复执行。

**PendingAction 与 Decision 的契约关系**是 HITL 机制的基础。进入任意 WAITING_* 状态时，系统生成结构化的 PendingAction 对象，包含 action_type、candidates、default_suggestion 和 explanation。人类通过 API 提交 Decision，指定 choice 和 selected_candidate_id。Decision Apply 模块验证绑定的合法性（pending_action 必须属于该 task、必须尚未被决策），通过后应用候选并推动状态迁移。系统验证已覆盖缺失候选 ID（SV-11，400 拒绝）、重复决策（SV-12，409 冲突）和错误绑定（SV-13，拒绝）等异常边界。

> **图 4-2**：FSM 状态转移图，展示 11 个对外状态、三类 WAITING 决策点和恢复路径。

## 4.4 六阶段 de novo 工作流

蛋白质设计的业务能力被组织为六个阶段，如图 4-3 所示。六阶段是能力分层而非固定流水线：Planner 可根据任务类型按 I/O 契约自由拼接，同一阶段允许多个工具实现并支持 patch 级别的替换。

1. **序列探索**（Sequence Exploration）：生成多样化候选序列，覆盖目标空间。典型工具包括 ProtGPT2、ProteinMPNN。
2. **结构映射**（Structure Projection）：将候选序列映射为结构并给出折叠置信度。典型工具包括 ESMFold、OpenFold、NIM ESMFold。
3. **质量门禁**（Quality Gate）：执行硬性可行性与质量过滤，检查序列合法性、结构完整性、低复杂度等。典型工具包括 BioPython QC、DSSP。
4. **结构条件精修**（Structure-conditioned Refinement）：基于结构反馈进行序列重设计。典型工具包括 ProteinMPNN redesign。
5. **目标评分**（Objective Scoring）：对候选进行多目标排序和最终评价。典型工具包括 objective_ranker。
6. **结果汇总**（Summarization）：汇总序列、结构、指标、风险和安全事件，生成 DesignResult 与报告。

六阶段之间允许多种流转：质量门禁可将不通过候选回送至序列探索阶段重新生成；目标评分不足的候选可回送至精修阶段；结构映射与精修之间可形成迭代闭环。Safety Gate 从各阶段收集风险信号，Patch/Replan 控制层在高代价步骤（结构映射、结构精修、重型目标评分）前后介入。系统验证中，t9 clean run 的 16 个任务均按六阶段能力分层执行完毕并产出有效 DesignResult（TC-S09 通过）。

> **图 4-3**：六阶段 de novo 工作流与恢复感知控制流程图。

## 4.5 CEBRA-WP：算法设计与策略体系

CEBRA-WP（Constraint- and Evidence-aware Belief-guided Recovery-adaptive Workflow Planning，约束与证据感知、信念引导、恢复自适应的工作流规划）是嵌入智能规划层和运行时控制层的核心算法，当前版本 `cebra_wp.v2`。其子公式体系包括 `static_score.v1`、`posterior_score.v1`、`runtime_adjustment.v1`、`action_utility.v1` 和 `action_bias.v1`，分别对应静态评分、证据加权后验目标评分、运行时调整、动作效用估计和动作偏置五个计算阶段。

与普通 LLM planner 的关键差异在于：CEBRA-WP 不直接执行单条 `LLM(g, C, K)` 输出，而是在每个关键决策点维护闭环——GenerateCandidates → FeasibilityFilter → StaticUtility → BeliefUpdate → RuntimeCandidateUtility → RecoveryAwareActionSelection，如图 4-4 所示。

### 4.5.1 离线候选生成与评分

Planner 读取任务目标 `g`、约束 `C`、工具知识图谱 `K` 和执行历史 `h_t`，生成候选集合 Π_raw。FeasibilityFilter 对候选执行六维硬可行性过滤：F_tool（工具存在性）、F_schema（schema 合法性）、F_io（I/O 闭包）、F_safety（安全等级）、F_budget-hard（预算硬约束）、F_availability（工具可用性），淘汰不可行候选后输出 Π_t。StaticUtility 对候选进行多维评分：可行性 `F_s`、目标匹配度 `G`（无后验观测时使用先验 G_prior）、归一化成本 `C_norm`、归一化风险 `R_norm`、恢复复杂度 `Rec` 和工程可靠性 `Q`（含工具 readiness、coverage、fallback depth）。

### 4.5.2 在线信念更新与后验评分

Runtime Observation 模块从 StepResult、SafetyResult 和预算消耗中提取观测 `o_t`。BeliefUpdate 将观测映射为 RuntimeState `x_t`，持久化五个核心状态量（p_success、p_structural_failure、recovery_margin、expected_remaining_cost、evidence_sufficiency），写入快照和事件日志。在信念更新的基础上，算法计算两阶段评分调整：

1. **RuntimeCandidateUtility** 计算 `final_score = static_score + runtime_adjustment`，其中 runtime_adjustment 根据当前信念状态调整候选评分：高结构失败概率和高预算压力压低高成本候选的最终得分，充分证据和良好恢复路径产生正向调整。
2. **Posterior Objective Scoring** 使用证据加权后验目标匹配：`G_post = Σ λ_m(g) · ρ_m(o_t) · q_m(π, o_t)`，其中 `λ_m` 是目标维度权重，`q_m` 是归一化分数，`ρ_m` 是证据可靠性权重（direct=1.00、proxy、degraded 或 missing=0.00）。整体证据充分度 `e_t = Σ λ_m · ρ_m` 进入 belief-state 的 evidence_sufficiency 字段。当前 v1 的显式组件集合为 generic_objective、stability、function、novelty 和 structure_quality。

RecoveryAwareActionSelection 将候选和信念状态映射为四类动作（continue、patch_local、suffix_replan、stop），并通过 HITL Gate 决定是否需要人工确认。CEBRA-WP 不是替代 FSM 的新控制器：动作输出被映射到系统已有的恢复闭环（patch_local → WAITING_PATCH_CONFIRM，suffix_replan → WAITING_REPLAN_CONFIRM，stop → terminal_stop 候选），受 FSM、Agent 边界和人工确认机制的约束。

### 4.5.3 四组实验策略

为在实验中分离各机制的贡献，系统支持四种策略配置，对应算法介入深度的递增：

- **Static Top-1**：单候选、无运行时自适应，仅依赖静态评分选择最优候选，为最弱内部基线。
- **Fixed Threshold Gate**：在静态评分基础上引入固定阈值门控，对成本或风险超限的候选强制人工确认，但不建模隐状态。
- **Dynamic Recovery（No Belief-State）**：启用分层 patch/replan 和六阶段增强恢复，但不维护显式信念状态——运行时决策仅依赖当前失败类型和重试状态等直接观测。
- **Lite Belief-State**：完整启用 CEBRA-WP 全部机制，以信念状态驱动运行时重排序、后验目标评分、动作效用估计和恢复动作选择。

这四种策略构成论文实验的主结果组，分别回答"静态单链是否足够"、"固定门控是否够用"、"动态恢复是否已有主要增益"、"信念状态是否带来额外价值"四个递进问题。

> **图 4-4**：CEBRA-WP 算法闭环图，展示候选生成、可行性过滤、静态评分、信念更新、运行时重排序和恢复动作选择。

## 4.6 核心数据契约

系统以统一的数据契约贯穿各层，如图 4-5 所示。ProteinDesignTask 是任务入口契约，包含 task_id、goal 和约束字段。Plan 由若干 PlanStep 组成，步骤间通过 `S{id}.{field}` 引用语法建立数据依赖。StepResult 记录每个步骤的执行状态、输出、指标、产物路径和失败信息。PendingAction 和 Decision 构成 HITL 交互的双向契约：PendingAction 承载候选集合和默认建议，Decision 记录用户选择、决策人和时间戳。TaskSnapshot 在进入等待状态和状态变更时写入，保存计划版本、已完成步骤和运行时状态摘要（artifacts.runtime_state），是系统从快照恢复执行的唯一来源。RuntimeState 作为横切对象嵌入多个契约，其持久化字段仅为五个核心状态量，派生量（如 budget_pressure、intervention_value、local_patchability）按需计算而不持久化。DesignResult 是最终输出契约，包含 sequence、structure_pdb_path、scores、risk_flags、report_path 和 metadata。

> **图 4-5**：UML 核心数据契约图，展示 ProteinDesignTask、Plan、StepResult、PendingAction、Decision、TaskSnapshot、RuntimeState 和 DesignResult 的结构与关系。

---

## 4.7 模块设计

系统模块以"职责单一、契约稳定、可替换、可审计"为划分原则，围绕任务生命周期中的关键行为组织为七类模块。

### 4.7.1 任务接入与交互模块

任务接入与交互模块负责将用户意图转化为可执行任务并在关键节点向用户呈现决策信息。实现上对应 FastAPI 接口（`/task-intakes`、`/tasks`、`/pending-actions`、`/tasks/{id}/events` 等 15 个端点）和 React 工作台的四个主要页面区域（Dashboard、Task Builder、Task Detail、Event Timeline）。输入可以是自然语言 goal、自由文本 query 或已确认的 ConfirmedTaskSpec。系统首先创建任务草稿，允许用户补充缺失字段，再通过确认接口生成正式任务——这一渐进式流程更适合科研任务的实际输入习惯。系统验证中，Task Builder 的 6 张中英文截图和 Dashboard 的 2 张截图证实了交互链路的完整性（FIG-SV-02 至 FIG-SV-11）。

### 4.7.2 规划与候选生成模块

规划与候选生成模块以 PlannerAgent 为中心，依赖 ProteinToolKG 和工具 readiness 信息，输出 PlanCandidate、PatchCandidate 或 ReplanCandidate。当前实现将候选生成逻辑拆分为 candidate_generator 的模型调用、过滤、构造和排序逻辑。初始规划时，Planner 根据任务类型和能力提示选择相应阶段能力；恢复规划时，Planner 根据失败上下文（失败类型、失败码、已完成步骤、运行时状态摘要）进行局部或全局搜索。每个 Candidate 必须包含 candidate_id、summary、structured_payload、score_breakdown、risk_level、cost_estimate、explanation 和 source_refs。系统验证中，TC-S03 验证了这些必需字段的存在。

### 4.7.3 自适应工作流规划与恢复模块

该模块是 CEBRA-WP 的工程承载。RuntimeState 以轻量级信念状态持久化五个核心变量，由 StepResult、SafetyResult、失败上下文、已完成步骤数和预算上限等观测更新。运行时调整通过 `compute_runtime_delta` 和 RuntimeEvaluator 将静态候选评分转化为证据感知排序；后验目标评分通过 `posterior_objective.v1` 计算 evidence-weighted goal fit。动作选择模块将算法动作映射到系统恢复闭环，结合阶段触发矩阵、失败类型、重试耗尽、安全阻断和运行时状态摘要进行综合判断。系统验证中，EVD-LOG-08 样本记录了从 WAITING_PLAN_CONFIRM → DECISION_APPLIED → CANDIDATE_VALIDATION_FAILED → FAILED 的完整决策循环。

### 4.7.4 工作流执行模块

工作流执行模块负责将已确认计划推进为实际计算过程。PlanRunner 驱动从 PLANNED 到 SUMMARIZING 的状态推进；StepRunner 处理单个步骤的输入解析、引用求解和适配器调用。步骤执行的关键是引用解析：PlanStep 可直接包含字面值，也可通过 `S{id}.{field}` 语法引用上游输出；若引用不存在或类型不匹配，系统产生可诊断错误。工具调用成功后，模块将输出、指标、产物路径和调用元数据写入 StepResult；失败时记录 failure_type、error_details 和重试上下文。系统验证中，t8 和 t9 smoke/clean run 的工具调用全部成功（TC-S09 通过，TC-S11 通过）。

### 4.7.5 工具适配与能力管理模块

工具适配与能力管理模块通过 BaseToolAdapter 抽象接口和 AdapterRegistry 注册机制实现外部工具的统一接入。AdapterRegistry 维护 tool_id 到适配器实例的映射。ProteinToolKG 从规划视角描述工具能力、输入输出和兼容关系。二者分工不同：Registry 面向运行时调用，ToolKG 面向规划与约束推理。系统验证中，`/capabilities/readiness` 返回 15 条能力就绪记录，包含 ready、degraded 和 unavailable 三种状态及对应的 error_category 和 suggested_recovery（EVD-API-02）。

### 4.7.6 安全与质量门禁模块

安全与质量门禁模块包括 SafetyAgent、RiskFlag、SafetyResult 和质量门禁逻辑。SafetyAgent 在输入、步骤和输出阶段执行安全检查，输出 ok、warn、block 等等级判定。质量门禁负责序列合法性、结构完整性、低复杂度检测等工程性质量控制。二者互补：质量门禁可产生步骤级失败或过滤原因，SafetyAgent 从风险治理角度给出是否允许继续的结论。系统验证中，安全阻断触发的 WAITING_REPLAN_CONFIRM 路径由 TC-S10 和 TC-S13 覆盖。

### 4.7.7 存储、日志、快照与结果汇总模块

存储与审计模块为系统可追溯和可恢复提供基础。事件日志记录 WAITING_ENTER、DECISION_APPLIED、WAITING_EXIT、STEP_FINISHED、STEP_FAILED、RECOVERY_ESCALATED 等关键事件类型。系统验证中，EVD-LOG-07 和 EVD-LOG-08 两个固定样本分别展示了成功生命周期和 HITL 决策循环。

快照记录了 pending_action_id、completed_step_ids、plan_version 和 artifacts.runtime_state。进入任意等待状态前先写快照的约束（`AGENT_CONTRACT.md`）保证了恢复的可靠性：如果系统在等待期间中断，可以从快照恢复到完整的等待场景而不会丢失候选、默认建议或执行前缀。系统验证中，TC-S06 验证了快照恢复在等待态下不自动推进的语义。

结果汇总模块由 SummarizerAgent 承担，生成 DesignResult 并写入 report_path、sequence、structure_pdb_path、scores 和 risk_flags。系统验证中 `/tasks/demo_structure_viewer/report` 返回了含 objective_scoring 和 structure_similarity 的完整报告结构（EVD-API-06）。

## 4.8 模块协作流程

一次典型任务的模块协作过程如下。用户通过任务接入模块提交目标并确认约束，系统生成 ProteinDesignTask。规划模块读取任务和 ToolKG，生成 Top-K Plan 候选；若需要人工确认，交互模块展示 PendingAction 并由用户提交 Decision。确认后的 Plan 进入执行模块，Executor 按步骤调用适配器并产生 StepResult。安全与质量门禁模块对关键输入输出进行检查。

如果某步成功，BeliefUpdate 根据观测更新 RuntimeState，后验目标评分调整候选排序，工作流继续推进。如果某步失败且可重试，执行模块优先进行有界重试；若重试耗尽或质量门禁拒绝结果，自适应恢复模块根据失败上下文和运行时信念状态计算动作 utility，选择 patch 或 replan 路径。Planner 生成相应候选，系统进入等待确认。用户接受后，Decision Apply 模块应用候选，Workflow 恢复执行。所有步骤完成后，Summarizer 汇总结果，任务进入 DONE。

## 4.9 本章小结

本章完成了系统的总体设计。架构方面，提出了五层分层架构（输入层、智能规划层、执行层、安全与汇总层、资源层），明确了四类 Agent 的职责边界和系统不变性约束，设计了包含 11 个状态的 FSM 生命周期模型和六阶段 de novo 能力分层。算法方面，将 CEBRA-WP（版本 `cebra_wp.v2`）嵌入规划与控制层，覆盖候选生成、六维硬可行性过滤、静态多目标评分、信念更新、后验目标评分、运行时重排序和恢复动作选择的全链路，并定义了四种递增策略组用于实验分离各机制的贡献。模块方面，以七类模块覆盖从任务接入到结果汇总的完整闭环。本章为后续系统实现（第 5 章）和实验验证（第 7 章）提供了统一的设计基线。

---

## 图的清单

| 图号 | 标题 | 源文件 |
|------|------|--------|
| 图 4-1 | 系统五层架构：输入/智能规划/执行/安全与汇总/资源层 | `asserts/figures/system-architecture.drawio` |
| 图 4-2 | FSM 状态转移图：11 个状态与三类 WAITING 决策点 | `asserts/figures/fsm-state-transition.drawio` |
| 图 4-3 | 六阶段 de novo 工作流与恢复感知控制 | `asserts/figures/workflow-flowchart.drawio` |
| 图 4-4 | CEBRA-WP 算法闭环：候选生成、可行性过滤、静态评分、信念更新、后验评分、运行时重排序、动作选择 | `asserts/figures/algorithm-loop.drawio` |
| 图 4-5 | UML 核心数据契约：ProteinDesignTask 至 DesignResult | `asserts/figures/uml-contracts.drawio` |
