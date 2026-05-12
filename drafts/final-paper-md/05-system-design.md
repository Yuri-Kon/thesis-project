# 第四章 系统设计

本章在需求分析的基础上说明系统总体设计。前一章已经将课题目标细化为任务接入、候选计划生成、工具执行、HITL、运行时恢复和审计追踪等需求。基于这些需求，本文系统设计的重点不是把若干工具串接成固定流水线，而是在可执行约束、安全约束和预算约束下，为蛋白质设计任务提供可规划、可恢复、可审计的工作流运行框架。

本章先介绍系统分层架构、核心组件、有限状态机和六阶段蛋白质设计工作流，再定义约束与证据感知、信念引导、恢复自适应工作流规划（Constraint- and Evidence-aware Belief-guided Recovery-adaptive Workflow Planning，CEBRA-WP）。针对 CEBRA-WP，本章给出其在本文系统中的形式化对象、评分函数、运行时状态、恢复动作和实验可验证性。

## 4.1 设计目标与总体架构

蛋白质设计工作流与一般 Web 后端任务存在明显差异。任务目标具有科学语义，用户可能只给出“设计一个稳定短肽”或“提高候选序列结构质量”等高层目标，系统需要将其转换为可执行步骤。工具调用的成本差异也较大：序列质量检查通常较轻，结构预测、重型打分和重设计则可能带来更高计算成本。与此同时，中间失败不一定意味着整个任务失败，参数错误、输入引用缺失、质量门禁未通过和外部工具暂时不可用，都可能通过局部修补或后缀重规划恢复。系统输出还需要面向科研场景保留证据链，包括候选生成依据、人工确认记录、执行结果、失败原因和恢复历史。

基于上述特点，系统采用五层分层架构，如图 4-1 所示。

【图 4-1 系统五层分层架构】
插图文件：`paper/figures/system-architecture.drawio.svg`

输入层面向 Web 工作台、CLI 和 API，负责接收自然语言目标、结构化约束和人工决策。智能规划层以 PlannerAgent、ProteinToolKG 和 CEBRA-WP 策略为核心，负责生成候选计划、进行可行性过滤、评分和恢复候选生成。执行层由 ExecutorAgent、PlanRunner 和 StepRunner 组成，负责按已确认计划调用工具并记录步骤结果。安全与汇总层包括 SafetyAgent 和 SummarizerAgent，分别负责风险判定与最终报告生成。资源层包括 ToolAdapter 注册表、ProteinToolKG、事件日志、任务快照和文件产物管理。

五层之间通过结构化数据契约交换信息。输入层不直接执行工具，规划层不直接修改任务终态，执行层不越过有限状态机进行状态跳转，安全层不直接编辑计划，汇总层不重新执行计算。通过这种职责拆分，候选生成、工具调用、人工确认和恢复动作都能回到对应的契约对象与事件记录，从而保证复杂任务中的可追溯性。

## 4.2 核心组件与职责边界

系统核心逻辑由四类 Agent 和工具适配层共同完成。

PlannerAgent 负责计划生成和恢复候选生成。它读取任务目标、约束、执行历史和 ProteinToolKG，生成初始 PlanCandidate，或在失败后生成局部修补候选与后缀重规划候选。PlannerAgent 的输出必须是结构化候选，而不是无法验证的自然语言建议。每个候选包含候选标识、摘要、结构化载荷、评分分解、风险等级、成本估计、解释文本和来源引用，因此既能被自动策略排序，也能呈现在人工审查界面中。

ExecutorAgent 是工具调用与计划推进组件。它通过 PlanRunner 管理计划级执行流程，通过 StepRunner 处理单个步骤的输入解析、上游引用求解、适配器调用和结果写入。ExecutorAgent 可以识别失败、重试耗尽和安全阻断等信号，但不自行绕过 Planner 生成修补方案，也不在等待人工确认时继续执行工具。

SafetyAgent 是风险信号源。它在输入、执行过程和输出阶段产生安全判定，输出 ok、warn、block 等等级。warn 可触发人工确认，block 可阻断自动推进并触发重规划候选。SafetyAgent 的定位是风险判定与建议，不负责计划搜索和工具执行。

SummarizerAgent 是结果汇总组件。它读取计划、步骤结果、安全事件和恢复历史，生成面向用户的报告和机器可读的 DesignResult。其输出应反映已完成计算和已有证据，不把未验证推断写成实验结论。

ToolAdapter 层为外部工具提供统一调用接口。工具注册表面向执行层，回答“如何调用工具”；ProteinToolKG 面向规划层，回答“哪些工具可用于何种能力、输入输出如何兼容、成本和风险如何估计”。二者共同支撑候选生成与执行验证。ProteinToolKG 的局部结构如图 4-2 所示。

【图 4-2 ProteinToolKG 局部可视化】
插图文件：`paper/figures/protein-toolkg-local-view.drawio.svg`

图 4-2 展示了 ProtGPT2、ProteinMPNN、ESMFold/OpenFold、Biopython QC、DSSP 和 objective_ranker 等代表性工具之间的能力节点、输入输出字段、成本风险属性和 I/O 兼容边。该图强调本文使用的 ProteinToolKG 是轻量工具能力索引，而非完整生物知识图谱。它的主要作用是为 Planner 提供能力发现、约束校验和候选解释依据。

## 4.3 任务生命周期、FSM 与 HITL 约束

系统使用有限状态机（Finite State Machine，FSM）控制任务生命周期，如图 4-3 所示。

【图 4-3 FSM 状态转移图】
插图文件：`paper/figures/fsm-state-transition.drawio.svg`

任务对外状态包括 CREATED、PLANNING、WAITING_PLAN_CONFIRM、PLANNED、RUNNING、WAITING_PATCH_CONFIRM、WAITING_REPLAN_CONFIRM、SUMMARIZING、DONE、FAILED 和 CANCELLED。WAITING_* 状态具有明确语义：系统已经暂停自动推进，等待人类提交结构化 Decision。DONE、FAILED 和 CANCELLED 为终态，进入后不再被自动修改。

人在环决策（Human-in-the-loop，HITL）不是任意插入的人机交互按钮，而是由成本、风险和不确定性共同触发的受控状态。不同等待状态的进入条件见图 4-4。

【图 4-4 HITL 决策条件】
插图文件：`paper/figures/hitl-decision-conditions.drawio.png`

PLANNING 阶段，如果候选置信度不足、即将调用高代价工具或 SafetyAgent 给出 warn，系统进入 WAITING_PLAN_CONFIRM。RUNNING 阶段，如果步骤失败但仍有 retry budget，系统先进行有界重试；若重试耗尽且局部可修复，则进入 WAITING_PATCH_CONFIRM；若出现结构性失败、安全阻断或恢复余量不足，则进入 WAITING_REPLAN_CONFIRM。人工决策通过 Decision 契约提交，Decision Apply 模块验证 pending action 与候选绑定关系，再推动 FSM 合法迁移。

这一设计为后续 CEBRA-WP 算法提供了控制边界：算法可以生成候选、计算分数和提出动作建议，但任务状态仍由 FSM 统一推进；算法建议不能绕过 WAITING_* 状态，也不能把 stop 直接变成不可审计的隐式失败。

## 4.4 六阶段蛋白质设计工作流

蛋白质设计能力被组织为六个阶段，如图 4-5 所示。

【图 4-5 六阶段 de novo 蛋白质设计工作流】
插图文件：`paper/figures/workflow-flowchart.drawio.svg`

六个阶段分别为序列探索、结构映射、质量门禁、结构条件精修、目标评分和结果汇总。序列探索生成候选序列；结构映射将序列转换为结构并产生折叠置信度；质量门禁检查序列合法性、结构完整性和低复杂度等工程质量；结构条件精修根据结构反馈进行重设计；目标评分对候选进行多目标排序；结果汇总生成 DesignResult 和报告。

六阶段是能力分层，而不是不可改变的线性流水线。质量门禁失败可以回到序列探索，目标评分不足可以回到结构条件精修，结构映射与精修之间可以形成迭代闭环。CEBRA-WP 的作用正是在这些可替代路径之间进行约束化选择：当证据不足时延后高代价步骤，当局部失败可修复时优先 `patch_local`（局部修补），当后缀不再可靠时保留有效前缀并进行 `suffix_replan`（后缀重规划）。

## 4.5 CEBRA-WP 的提出背景

上一节给出了蛋白质设计工作流的能力分层和可替代路径，但阶段划分本身并不能回答何时继续执行、何时局部修补、何时后缀重规划以及何时终止止损。CEBRA-WP 的提出，正是为了处理这些运行时决策。

传统固定流水线适合步骤稳定、成本均匀、失败语义简单的任务，但难以覆盖本文场景。蛋白质设计工作流中的关键风险往往具有部分可观测性：一次结构预测失败可能来自工具服务异常，也可能表明上游序列质量不足；一次质量门禁失败可能通过阈值、参数或局部工具替换修复，也可能说明当前候选链路整体失效。系统若只按静态计划执行，会在证据不足时过早调用高代价工具；若只依赖单次 LLM 规划，候选又缺少可复现的约束过滤和恢复依据。

CEBRA-WP 的设计动机主要来自三类研究。部分可观测规划研究指出，决策不应只依赖瞬时观测，而应维护对隐藏状态的 belief-state 表示[@kaelbling1998pomdp; @shani2024heuristics]。在本文中，隐藏状态不是完整环境模型，而是当前链路是否仍有成功可能、失败是否具有结构性、剩余预算压力和证据是否充分等低维量。预算约束规划与预算强化学习研究强调，成本和风险应作为一等决策变量，而不是执行失败后的附加统计[@carrara2019budgetedrl]；这与蛋白质设计中高代价结构预测和目标评分的治理需求相一致。Tree of Thoughts 强调保留多个候选推理路径并进行搜索[@yao2023tot]，Reflexion 则强调利用失败反馈改进后续任务表现[@shinn2023reflexion]。本文将这两类思想约束到可执行工具链规划中，使候选、恢复动作和人工确认都以结构化对象表达。

基于这些考虑，CEBRA-WP 被定义为一种面向高代价科研工作流的约束化、证据感知、信念引导、恢复自适应规划算法。它不追求训练端到端最优控制器，而是以可解释、可配置、可审计的形式，把候选生成、硬约束过滤、静态效用、运行时状态、后验证据和恢复动作选择组织为一个闭环。

## 4.6 CEBRA-WP 形式化定义

CEBRA-WP 的完整名称为 Constraint- and Evidence-aware Belief-guided Recovery-adaptive Workflow Planning，本文译为“约束与证据感知、信念引导、恢复自适应的工作流规划”。当前论文版本为 `cebra_wp.v2`，其子公式包括 `static_score.v1`、`posterior_score.v1`、`runtime_adjustment.v1`、`action_utility.v1` 和 `action_bias.v1`。

算法总体闭环如图 4-6 所示。

【图 4-6 CEBRA-WP 算法闭环】
插图文件：`paper/figures/algorithm-loop.drawio.svg`

图 4-6 的上半部分是静态规划层：系统根据目标、约束、ProteinToolKG 和历史记录生成候选工具链，随后执行硬可行性过滤与静态评分。图 4-6 的下半部分是运行时自适应层：系统根据 StepResult、SafetyResult、失败上下文、预算消耗和恢复历史更新 Lite belief-state / 轻量信念状态，再对候选进行运行时重排序，并在 `continue`、`patch_local`、`suffix_replan` 和 `stop` 之间选择动作建议。

算法使用的主要符号如表 4-1 所示。

**表 4-1 CEBRA-WP 符号与语义定义**

| 符号 | 含义 | 来源或载体 | 在算法中的作用 |
|---|---|---|---|
| $t$ | 当前决策时间步 | EventLog、RuntimeEvaluator | 索引一次候选生成、状态更新和恢复动作选择 |
| $g$ | 设计目标 | 用户输入、ConfirmedTaskSpec | 定义任务目标与目标权重 |
| $C$ | 约束集合 | 任务约束、策略配置 | 限定长度、安全、预算、工具白名单和输出要求 |
| $K$ | ProteinToolKG | ProteinToolKG | 提供工具能力、I/O schema、兼容关系、成本和风险 |
| $h_t$ | 时间步 $t$ 前的执行历史 | EventLog、TaskSnapshot | 提供已完成步骤、失败记录、恢复历史和人工决策 |
| $o_t$ | 当前运行时观测 | StepResult、SafetyResult、指标、错误细节 | 更新运行时状态并计算后验证据 |
| $x_t$ | Lite belief-state / 轻量信念状态 | RuntimeState | 表示成功概率、结构性失败概率、恢复余量、剩余成本和证据充分度 |
| $x_{t+1}$ | 观测更新后的轻量信念状态 | RuntimeState 更新结果 | 为候选重排和恢复动作选择提供更新后状态 |
| $\Pi_{\mathrm{raw},t}$ | 原始候选集合 | PlannerAgent | 包含初始计划、局部修补或重规划候选 |
| $\Pi_t$ | 过滤后的候选集合 | FeasibilityFilter | 只保留可执行或受保护的 degraded feasible 候选 |
| $\pi$ | 候选工作流 | PlanCandidate、PatchCandidate、ReplanCandidate | 作为过滤、评分和重排序的基本对象 |
| $\pi^\ast$ | 默认候选 | RuntimeEvaluator、Decision | 作为自动执行或 HITL 审查的默认建议 |
| $S_{\mathrm{static}}$ | 静态效用 | score_breakdown | 在运行时观测介入前评价候选先验质量 |
| $G_{\mathrm{post}}$ | 后验目标匹配 | posterior_objective | 根据证据可靠性修正目标评分 |
| $\Delta$ | 运行时修正项 | runtime_adjustment | 根据状态变量修正候选排序 |
| $U_{\pi}$ | 候选运行时效用 | RuntimeEvaluator | 输出 Top-K 和默认候选 |
| $a_t$ | 恢复动作 | action_utility | 在 `continue`、`patch_local`、`suffix_replan`、`stop` 之间选择 |

在时间步 $t$，算法输入为 $(g,C,K,h_t,o_t,x_t)$，输出为结构化 Decision 建议：候选集合 $\Pi_t$、默认候选 $\pi^\ast$、候选解释、运行时状态摘要和恢复动作 $a_t$。核心计算过程可概括为：

```tex
\begin{aligned}
\Pi_{\mathrm{raw},t} &= \operatorname{GenerateCandidates}(g,C,K,h_t),\\
\Pi_t &= \operatorname{FeasibilityFilter}(\Pi_{\mathrm{raw},t},C,K,h_t),\\
S_{\mathrm{static}} &= \operatorname{StaticUtility}(\pi,g,C,K),\\
x_{t+1} &= \operatorname{BeliefUpdate}(x_t,o_t,h_t),\\
G_{\mathrm{post}} &= \operatorname{PosteriorObjective}(\pi,g,o_t),\\
U_{\pi} &= \operatorname{RuntimeCandidateUtility}(S_{\mathrm{static}},G_{\mathrm{post}},x_{t+1}),\\
a_t &= \operatorname{RecoveryAwareActionSelection}(x_{t+1},\Pi_t,h_t,C).
\end{aligned}
```

该定义突出两点：一是候选生成与候选选择相互分离，Planner 可以生成多个方案，但只有通过可行性和效用评估的候选才会进入执行或人工确认；二是运行时状态只修正排序和动作建议，不改变 FSM、Agent 职责和硬约束。

## 4.7 候选生成、硬可行性过滤与静态效用

CEBRA-WP 支持三类候选。PlanCandidate 表示初始完整计划；PatchCandidate 表示对当前计划中局部步骤的参数级、工具级或结构级修补；ReplanCandidate 表示对未执行后缀或整体策略的替换，其中 `suffix_replan` 优先保留已验证前缀，`terminal_stop` 表示继续投入不划算时的终止型重规划候选。

候选进入评分前必须先通过硬可行性过滤。对候选 $\pi$ 定义硬可行性谓词：

```tex
\begin{aligned}
F_h(\pi,C,K,h_t)
  &= F_{\mathrm{tool}}\land F_{\mathrm{schema}}\land F_{\mathrm{io}}\land F_{\mathrm{safety}}\\
  &\quad{}\land F_{\mathrm{budget\mbox{-}hard}}\land F_{\mathrm{availability}}.
\end{aligned}
```

其中，$F_h$ 表示硬可行性谓词，$F_{\mathrm{tool}}$ 检查候选中的工具是否存在于能力图或适配器注册表；$F_{\mathrm{schema}}$ 检查输入输出字段是否满足工具 schema；$F_{\mathrm{io}}$ 检查跨步骤引用是否闭合；$F_{\mathrm{safety}}$ 检查是否违反安全等级或触发 safety block；$F_{\mathrm{budget\mbox{-}hard}}$ 检查是否突破不可逾越预算上限；$F_{\mathrm{availability}}$ 检查关键工具是否可用或是否有明确降级路径。过滤后的集合为：

```tex
\Pi_t=\{\pi\in\Pi_{\mathrm{raw},t}\mid F_h(\pi,C,K,h_t)=1\}.
```

硬可行性过滤承担系统边界约束，因此静态评分不能把硬不可行候选“打高分后救回”。工程实现可以保留 degraded feasible 候选用于解释或 HITL 审查，但这类候选必须携带降级原因和人工确认要求。

在候选通过硬过滤后，算法计算静态效用：

```tex
\begin{aligned}
S_{\mathrm{static}}(\pi)
  &= w_f F_s(\pi)
   + w_g G(\pi;g,o_t)
   - w_c C_{\mathrm{norm}}(\pi)\\
  &\quad{}- w_r R_{\mathrm{norm}}(\pi)
   - w_{\mathrm{rec}}\operatorname{Rec}(\pi)
   + w_q Q(\pi).
\end{aligned}
```

$F_s$ 是软可行性分数，表示候选在 schema 完整、工具 readiness、fallback depth 等方面的先验质量；$G$ 是目标匹配度；$C_{\mathrm{norm}}$ 是归一化成本；$R_{\mathrm{norm}}$ 是归一化风险；$\operatorname{Rec}$ 是恢复复杂度；$Q$ 是工程可靠性项。权重 $w_\ast$ 由策略配置给出，用于在不同任务设置下调节目标、成本、风险和恢复难度的相对重要性。

静态效用用于形成执行前的候选先验排序。它可以偏好成本更低、风险更小、恢复更容易的工具链，但无法感知执行中已经发生的失败、证据不足或预算压力变化。因此，静态效用之后还需要 Lite belief-state / 轻量信念状态和后验证据修正。

## 4.8 Lite belief-state 与观测更新

CEBRA-WP 使用 Lite belief-state / 轻量信念状态近似表示执行过程中无法完全观测的工作流状态。它只保留三类变量：对恢复动作选择必要的变量、能够从现有日志稳定更新的变量，以及能够被实验和案例解释的变量。状态向量定义为：

```tex
x_t=\left[
\begin{array}{c}
p_{\mathrm{succ}}\\
p_{\mathrm{sf}}\\
r_{\mathrm{rec}}\\
c_{\mathrm{rem}}\\
e_{\mathrm{suf}}
\end{array}
\right].
```

其中，$p_{\mathrm{succ}}$ 表示任务继续成功概率，$p_{\mathrm{sf}}$ 表示结构性失败概率，$r_{\mathrm{rec}}$ 表示恢复余量，$c_{\mathrm{rem}}$ 表示预期剩余成本，$e_{\mathrm{suf}}$ 表示证据充分度。各状态量的语义如表 4-2 所示。

**表 4-2 Lite belief-state / 轻量信念状态变量**

| 状态量 | 取值范围 | 含义 | 主要更新来源 | 决策作用 |
|---|---|---|---|---|
| $p_{\mathrm{succ}}$（成功概率） | $[0,1]$ | 当前链路继续执行后完成任务的估计概率 | 步骤成功、质量指标、候选静态分、失败记录 | 支持 `continue` 与 `stop` 判断 |
| $p_{\mathrm{sf}}$（结构失败） | $[0,1]$ | 当前链路遭遇结构性失败或后续必须重规划的估计概率 | 结构预测失败、质量门禁失败、安全阻断、重复失败 | 提高 `patch_local`、`suffix_replan`、`stop` 权重 |
| $r_{\mathrm{rec}}$（恢复余量） | $[0,1]$ | 在保留有效前缀前提下继续恢复的余量 | 已完成步骤比例、失败类型、patch/replan 次数 | 区分局部修补与后缀重规划 |
| $c_{\mathrm{rem}}$（剩余成本） | 非负实数 | 从当前状态到任务结束的剩余成本暴露 | 剩余步骤、工具成本先验、预算配置、重试记录 | 派生预算压力并约束高代价动作 |
| $e_{\mathrm{suf}}$（证据充分） | $[0,1]$ | 当前证据是否足以支持进入更高代价步骤 | 质量门禁、结构指标、目标评分、证据可靠性 | 控制高代价步骤推进与人工确认 |

运行时观测 $o_t$ 来自 StepResult、SafetyResult、失败上下文、局部修补/重规划历史、已完成步骤、剩余后缀和 HITL 决策记录。派生量如 $b_{\mathrm{press}}$、$v_{\mathrm{hitl}}$、$\ell_{\mathrm{patch}}$ 和 $p_{\mathrm{pres}}$ 不作为持久化主状态，而是根据当前状态和候选上下文按需计算。这样可以避免把与具体候选强相关的临时判断写入长期状态，从而降低状态漂移风险。

以预算压力为例，$c_{\mathrm{rem}}$ 保留剩余成本原始估计，不直接等同于 $[0,1]$ 区间内的预算压力。若任务给出预算上限 $c_{\mathrm{cap}}$，则：

```tex
b_{\mathrm{press}}
=\operatorname{clip}\left(
\frac{c_{\mathrm{rem}}}{\max(c_{\mathrm{cap}},0.1)},
0,1.5
\right).
```

若任务未给出预算上限，则使用：

```tex
b_{\mathrm{press}}=\operatorname{clip}(c_{\mathrm{rem}},0,1.5).
```

因此，预算压力是由任务上下文派生的动作决策量，而不是 RuntimeState 的持久化字段。该区分使系统既能记录可解释的剩余成本，也能在不同预算设置下统一比较恢复动作。

状态初始化可由首选候选的静态分数、风险分数、恢复复杂度、剩余成本先验和廉价证据覆盖率给出。例如，$p_{\mathrm{succ}}$ 可由静态候选分数裁剪得到，$p_{\mathrm{sf}}$ 可由风险项裁剪得到，$r_{\mathrm{rec}}$ 可由恢复复杂度的反向量估计，$c_{\mathrm{rem}}$ 来自剩余工具成本先验，$e_{\mathrm{suf}}$ 来自低成本质量证据覆盖率。随着执行推进，成功步骤会提升 $p_{\mathrm{succ}}$ 和证据充分度，结构性失败会提高 $p_{\mathrm{sf}}$ 并降低恢复余量，重复失败和预算消耗则会提高剩余成本压力。

该状态设计吸收了部分可观测规划中 belief-state 的思想[@kaelbling1998pomdp]，但在工程上保持轻量：系统不求解完整 POMDP，也不在线训练策略网络，而是使用可解释变量为候选重排和恢复动作提供一致依据。

## 4.9 后验目标评分与运行时重排序

蛋白质设计目标通常是多目标的，包括结构质量、稳定性、功能、novelty 和安全性等。不同目标的证据来源不同，证据可靠性也不同。为避免把弱证据与直接证据等价处理，CEBRA-WP 使用证据加权后验目标匹配：

```tex
G_{\mathrm{post}}(\pi;g,o_t)
=\sum_m \lambda_m(g)\rho_m(o_t)q_m(\pi,o_t).
```

其中，$m$ 表示目标维度，$\lambda_m(g)$ 是由任务目标 $g$ 决定的目标权重，$q_m(\pi,o_t)$ 是候选 $\pi$ 在该维度上的归一化分数，$\rho_m(o_t)$ 是观测 $o_t$ 对目标维度 $m$ 的证据可靠性权重。证据状态分为 direct、proxy、degraded 和 missing：direct evidence 指已产生的结构质量指标，proxy evidence 指由轻量质量门禁推断出的间接信号，degraded evidence 表示工具降级或证据覆盖不完整，missing 表示当前没有可用证据。整体证据充分度可写为：

```tex
e_t=\operatorname{clip}\left(\sum_m \lambda_m(g)\rho_m(o_t),0,1\right).
```

该值进入 $e_{\mathrm{suf}}$，影响是否继续进入高代价步骤。若证据不足而候选下一步成本较高，运行时重排序会降低该候选；若已有充分低成本证据支持，则候选可以更合理地进入结构预测或目标评分。

将 $G_{\mathrm{post}}$ 替换静态效用中的目标匹配项后，得到包含后验证据的基础分 $S_{\mathrm{post}}$。运行时重排序定义为：

```tex
U_{\pi}(\pi,x_t)=\operatorname{clip}\left(S_{\mathrm{post}}(\pi)+\Delta(\pi,x_t),0,1\right).
```

其中 $\Delta(\pi,x_t)$ 是有界运行时修正项，取值范围控制在 $[-0.35,0.35]$。其一般形式为：

```tex
\begin{aligned}
\Delta(\pi,x_t)
  &= k_s\,(p_{\mathrm{succ}}-0.5)\operatorname{Conf}(\pi)\\
  &\quad{}+k_e\,(2e_{\mathrm{suf}}-1)
       \max(\operatorname{Conf}(\pi),F_s(\pi))\\
  &\quad{}-k_f\,p_{\mathrm{sf}}\,(1-\operatorname{RiskScore}(\pi))\\
  &\quad{}+k_r\,r_{\mathrm{rec}}\operatorname{RecoveryScore}(\pi)\\
  &\quad{}-k_c\,b_{\mathrm{press}}\,(1-\operatorname{CostScore}(\pi))\\
  &\quad{}+k_a\,\operatorname{ActionBias}(\pi,x_t).
\end{aligned}
```

其中，$\operatorname{Conf}(\pi)$ 表示候选置信度，$\operatorname{RiskScore}(\pi)$ 和 $\operatorname{CostScore}(\pi)$ 为候选的风险与成本质量分数，$\operatorname{RecoveryScore}(\pi)$ 表示候选恢复友好度，$\operatorname{ActionBias}(\pi,x_t)$ 表示候选与当前恢复动作偏好的匹配程度。其直观含义是：当 $p_{\mathrm{sf}}$ 和预算压力升高时，算法降低高成本、低可恢复候选的排序；当 $p_{\mathrm{succ}}$、$r_{\mathrm{rec}}$ 和 $e_{\mathrm{suf}}$ 较高时，算法提高继续执行或低风险候选的排序。

运行时重排序有两个边界：一是只作用于已经通过可行性校验的候选，不能覆盖工具不存在、schema 错误、I/O 不闭合和安全阻断；二是修正幅度存在上界，避免一次异常观测完全覆盖静态目标匹配和工程可靠性判断。借助这两个边界，算法在适应运行时变化的同时仍能保持可复现和可审计。

## 4.10 恢复动作选择与 HITL 映射

CEBRA-WP 将恢复动作限定为四类：`continue`、`patch_local`、`suffix_replan` 和 `stop`。四类动作与 FSM/HITL 的映射如表 4-3 所示。

**表 4-3 恢复动作与 FSM/HITL 映射**

| 动作 | 触发背景 | 系统效果 | FSM/HITL 映射 | 审计结果 |
|---|---|---|---|---|
| `continue` | 成功概率较高、证据充分、风险和预算压力可接受 | 继续执行当前计划后续步骤 | RUNNING 内自动推进或维持 PLANNED/RUNNING | 记录动作效用与继续原因 |
| `patch_local` | 局部失败、重试耗尽、前缀仍有效、局部可修复性较高 | 生成局部 PlanPatch，替换参数或局部工具 | WAITING_PATCH_CONFIRM 或策略允许的受控自动 patch | 记录 patch 候选、失败上下文和应用结果 |
| `suffix_replan` | 结构性失败概率升高、后缀可靠性不足、前缀可保留 | 保留已验证前缀，替换未执行后缀 | WAITING_REPLAN_CONFIRM | 记录 replan 候选、前缀保留位置和新后缀 |
| `stop` | 成功概率低、预算压力高、恢复余量低、人工介入价值有限 | 生成终止型 ReplanCandidate | WAITING_REPLAN_CONFIRM；接受后进入 FAILED | 记录 terminal_reason 与已保留证据 |

动作效用由状态量和派生量共同计算。为便于表示，记 $s=p_{\mathrm{succ}}$，$f=p_{\mathrm{sf}}$，$r=r_{\mathrm{rec}}$，$e=e_{\mathrm{suf}}$，$b=b_{\mathrm{press}}$。局部可修复性、证据可复用性、前缀可保留性、预算缓解度、目标重对齐收益和人工介入价值，分别记为 $\ell_{\mathrm{patch}}$、$e_{\mathrm{reuse}}$、$p_{\mathrm{pres}}$、$b_{\mathrm{relief}}$、$g_{\mathrm{align}}$ 和 $v_{\mathrm{hitl}}$。动作效用可写为：

```tex
\begin{aligned}
U_{\mathrm{continue}}
  &=0.38s+0.14e+0.12r-0.22f-0.14b,\\
U_{\mathrm{patch\_local}}
  &=0.20s+0.24r+0.18\ell_{\mathrm{patch}}
    +0.12e_{\mathrm{reuse}}\\
  &\quad{}-0.14f-0.12b,\\
U_{\mathrm{suffix\_replan}}
  &=0.18(1-s)+0.20f+0.16(1-r)
    +0.18p_{\mathrm{pres}}\\
  &\quad{}+0.14b_{\mathrm{relief}}
    +0.14g_{\mathrm{align}},\\
U_{\mathrm{stop}}
  &=0.32(1-s)+0.24b+0.18(1-r)
    +0.16s_{\mathrm{safe}}\\
  &\quad{}+0.10(1-v_{\mathrm{hitl}}).
\end{aligned}
```

其中，$s_{\mathrm{safe}}$ 表示安全终止性。这组效用函数体现了四类动作的不同偏好：`continue` 对较高成功概率、证据充分度和恢复余量更敏感；`patch_local` 更依赖局部可修复性、证据可复用性和较低结构性失败概率；`suffix_replan` 偏向于结构性失败概率较高、当前成功概率较低但前缀仍可保留的场景；`stop` 只有在继续价值低、预算压力高、恢复余量低且人工介入价值不足时才会成为强候选。

`stop` 不是用户主动取消，也不是执行异常崩溃，而是算法提出的终止型重规划候选。其载体为 `ReplanCandidate(replan_mode="terminal_stop")`，通过 `replan_confirm` 通道进入 WAITING_REPLAN_CONFIRM。只有在人工接受或策略显式允许时，系统才将任务推进到 FAILED；已完成前缀、产物和解释字段仍被保留为审计资产。

综合上述设计，CEBRA-WP 主流程可写为算法 4-1。

**算法 4-1 CEBRA-WP 主流程**

```text
Input:
  g: 设计目标
  C: 约束集合
  K: ProteinToolKG
  h_t: 执行历史
  o_t: 当前观测
  x_t: Lite belief-state

Output:
  Decision_t: 候选集合、默认候选、恢复动作、解释和证据引用

1.  Pi_raw,t <- GenerateCandidates(g, C, K, h_t)
2.  Pi_t <- FeasibilityFilter(Pi_raw,t, C, K, h_t)
3.  if Pi_t is empty and degraded_feasible candidates exist:
4.      Pi_t <- degraded_feasible candidates
5.      mark candidates as requiring HITL confirmation
6.  for each pi in Pi_t:
7.      S_static(pi) <- StaticUtility(pi, g, C, K)
8.      S_post(pi) <- ReplaceObjectiveTerm(S_static(pi), PosteriorObjective(pi, g, o_t))
9.  x_t+1 <- BeliefUpdate(x_t, o_t, h_t)
10. for each pi in Pi_t:
11.     Delta(pi, x_t+1) <- RuntimeAdjustment(pi, x_t+1)
12.     U_pi(pi, x_t+1) <- clip(S_post(pi) + Delta(pi, x_t+1), 0, 1)
13. TopK_t <- SelectDiverseTopK(Pi_t, U_pi, capability_coverage)
14. U_a <- ComputeActionUtility(continue, patch_local, suffix_replan, stop)
15. a_t <- ApplyHardPrioritiesAndSelectAction(U_a, x_t+1, h_t, C)
16. return Decision_t(TopK_t, a_t, explanations, evidence_refs)
```

算法第 1 至 8 行生成并评价候选，第 9 至 12 行根据运行时状态修正候选效用，第 13 行保留 Top-K 多样性，第 14 至 15 行选择恢复动作。第 15 行的硬优先级包括安全阻断优先、schema/I/O/tool availability 违规淘汰、重试耗尽后优先局部修补、前缀可保留时优先后缀重规划等约束。借助这些优先级，动作选择遵循系统控制边界，而不是只按连续效用值排序。

## 4.11 策略组与实验可验证性

为验证 CEBRA-WP 各组成机制的作用，系统将算法能力拆分为四组策略开关。四组策略并非四套不同系统，而是在同一工程实现上逐步打开静态评分、固定阈值门控、动态恢复和 Lite belief-state 的内部消融配置，如表 4-4 所示。

**表 4-4 四组消融策略与算法机制开关**

| 策略组 | 静态评分 | 固定阈值门控 | 动态观测 | Lite belief-state | Runtime rerank | 恢复动作效用 | 主要实验问题 |
|---|---|---|---|---|---|---|---|
| `static_top1` | 启用 | 未启用 | 未启用 | 未启用 | 未启用 | 未启用 | 单一静态最优候选是否足以完成任务 |
| `fixed_threshold_gate` | 启用 | 启用 | 有限使用 | 未启用 | 未启用 | 未启用 | 固定阈值是否能控制风险与成本 |
| `dynamic_no_belief_state` | 启用 | 启用 | 启用 | 未启用 | 部分启用 | 部分启用 | 直接运行时观测是否已能支撑恢复 |
| `lite_belief_state` | 启用 | 启用 | 启用 | 启用 | 启用 | 启用 | 显式状态是否带来更好的解释、预算感知和恢复决策 |

该策略设计使第 7 章实验能够分别回答三个问题：静态计划是否足够；固定阈值门控是否会带来额外成本；在动态恢复已经存在时，Lite belief-state 的增量价值体现在哪里。根据已有实验设置，本文不把 CEBRA-WP 论证为所有指标上的性能最优算法，而是重点验证其机制链路是否可执行、状态是否可观测、成本控制是否具有方向性证据，以及恢复决策是否具有可解释依据。

## 4.12 数据契约与模块协作

系统以统一数据契约支撑算法与工程实现之间的衔接。核心契约关系如图 4-7 所示。

【图 4-7 核心数据契约 UML】
插图文件：`paper/figures/uml-contracts.drawio.svg`

ProteinDesignTask 是任务入口契约，包含 task_id、goal 和约束字段。Plan 由多个 PlanStep 组成，步骤之间通过 `S{id}.{field}` 引用语法建立数据依赖。StepResult 记录每个步骤的执行状态、输出、指标、产物路径和失败信息。PendingAction 与 Decision 构成 HITL 的双向契约：前者承载候选集合、默认建议和解释，后者记录用户选择、决策人和时间戳。TaskSnapshot 保存计划版本、已完成步骤、pending_action_id 和 runtime_state 摘要。RuntimeState 持久化 CEBRA-WP 的五个核心状态量。DesignResult 是最终输出契约，包含序列、结构路径、评分、风险标记、报告路径和元数据。

图 4-8 给出了典型任务 t1 的贯穿示例。

【图 4-8 t1 任务实例走查】
插图文件：`paper/figures/t1-trpcage-instance-walkthrough.drawio.svg`

该示例从任务创建开始，经 Planner 生成候选计划、用户确认、Executor 调用工具、StepResult 写入、RuntimeState 更新和必要的恢复候选触发，最后由 Summarizer 汇总为 DesignResult。CEBRA-WP 在这一过程中并非孤立算法模块，而是嵌入任务生命周期的规划与恢复层：算法输出通过 PendingAction、PlanPatch、ReplanCandidate 和 RuntimeState 等契约进入系统，系统状态则仍由 FSM 和 Workflow 控制。

## 4.13 本章小结

本章完成了系统总体设计和 CEBRA-WP 算法定义。系统采用五层架构组织输入、规划、执行、安全汇总和资源管理，并通过 FSM 与 HITL 契约约束任务状态推进。蛋白质设计能力被组织为六阶段工作流，ProteinToolKG 则负责支持工具能力发现和 I/O 兼容校验。在算法层面，CEBRA-WP 将候选生成、硬可行性过滤、静态效用、后验目标评分、Lite belief-state、运行时重排序和恢复动作选择组合成闭环，用于高代价、部分可观测、可失败的科研工作流恢复规划。下一章将在该设计基础上说明后端 API、工作流执行、RuntimeState 更新、工具适配和前端交互等工程实现。
