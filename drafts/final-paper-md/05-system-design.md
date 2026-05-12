# 第四章 系统设计

本章在需求分析的基础上说明系统总体设计。前一章已经将课题目标细化为任务接入、候选计划生成、工具执行、HITL、运行时恢复和审计追踪等需求。基于这些需求，本文系统设计的重点不是把若干工具串接成固定流水线，而是在可执行约束、安全约束和预算约束下，为蛋白质设计任务提供可规划、可恢复、可审计的工作流运行框架。

本章先介绍系统分层架构、核心组件、有限状态机和六阶段蛋白质设计工作流，再定义约束与证据感知、信念引导、恢复自适应工作流规划（Constraint- and Evidence-aware Belief-guided Recovery-adaptive Workflow Planning，CEBRA-WP）。针对 CEBRA-WP，本章给出其在本文系统中的形式化对象、评分函数、运行时状态、恢复动作和实验可验证性。

## 4.1 设计目标与总体架构

蛋白质设计工作流不同于一般 Web 后端任务：自然语言目标需要转为可执行步骤，结构预测和重型打分成本较高，中间失败也不必然导致任务整体失败。参数错误、输入引用缺失、质量门禁未通过或外部工具暂不可用，都可能通过局部修补或后缀重规划恢复；系统输出还需保留候选依据、人工确认、执行结果和恢复历史。

基于这些特点，系统架构采用五层划分，如图 4-1 所示。

【图 4-1系统五层分层架构】

输入层面向 Web 工作台、CLI 和 API，接收用户的自然语言目标、结构化约束和人工决策。智能规划层以 PlannerAgent、ProteinToolKG 和 CEBRA-WP 策略为核心，承担候选计划生成工作、可行性过滤、评分和恢复候选生成。执行层由 ExecutorAgent、PlanRunner 和 StepRunner 组成，按照已确认的计划调用工具并记录步骤结果。安全与汇总层包含 SafetyAgent 和 SummarizerAgent，分别处理风险判定和最终报告生成。资源层则包括 ToolAdapter 注册表、ProteinToolKG、事件日志、任务快照和文件产物管理。

五层之间依靠结构化数据契约交换信息。输入层不直接执行工具，规划层不直接修改任务终态，执行层不越过有限状态机跳转状态，安全层不直接编辑计划，汇总层也不重新执行计算。经过这样的职责拆分，候选生成、工具调用、人工确认和恢复动作都可以回到相应的契约对象与事件记录中，复杂任务的可追溯性因此有了实现基础。

## 4.2 核心组件与职责边界

系统核心逻辑主要由四类 Agent 和工具适配层共同完成。

PlannerAgent 承担计划生成和恢复候选生成。它读取任务目标、约束、执行历史和 ProteinToolKG，生成初始 PlanCandidate，也会在失败后生成局部修补候选与后缀重规划候选。PlannerAgent 的输出必须是结构化候选，而不是难以验证的自然语言建议。每个候选包含候选标识、摘要、结构化载荷、评分分解、风险等级、成本估计、解释文本和来源引用，因此既能被自动策略排序，也能呈现在人工审查界面中。

ExecutorAgent 主要负责工具调用和计划推进。它通过 PlanRunner 管理计划级执行流程，通过 StepRunner 处理单个步骤的输入解析、上游引用求解、适配器调用和结果写入。ExecutorAgent 能够识别失败、重试耗尽和安全阻断等信号，但不会直接绕过 Planner 生成修补方案，也不会在等待人工确认时继续执行工具。

SafetyAgent 是风险信号源。它在输入、执行过程和输出阶段产生安全判定，输出 ok、warn、block 等等级。warn 可触发人工确认，block 可阻断自动推进并触发重规划候选。SafetyAgent 的定位是风险判定与建议，不负责计划搜索和工具执行。

SummarizerAgent 主要负责结果汇总。它读取计划、步骤结果、安全事件和恢复历史，生成面向用户的报告和机器可读的 DesignResult。该组件的输出只反映已经完成的计算和已有证据，不把未验证推断写成实验结论。

ToolAdapter 层为外部工具提供统一调用接口。工具注册表面向执行层，回答“如何调用工具”；ProteinToolKG 面向规划层，回答“哪些工具可用于何种能力、输入输出如何兼容、成本和风险如何估计”。二者共同支撑候选生成与执行验证。ProteinToolKG 的局部结构如图 4-2 所示。

【图 4-2 ProteinToolKG局部可视化】

图 4-2 展示了 ProtGPT2、ProteinMPNN、ESMFold/OpenFold、Biopython QC、DSSP 和 objective_ranker 等代表性工具之间的能力节点、输入输出字段、成本风险属性和 I/O 兼容边。这里需要说明的是，本文使用的 ProteinToolKG 是轻量工具能力索引，并并不是完整的生物知识图谱。它主要服务于系统中的 Planner 的能力发现、约束校验和候选解释。

## 4.3 任务生命周期、FSM 与 HITL 约束

系统使用有限状态机（Finite State Machine，FSM）控制任务生命周期，如图 4-3 所示。

【图 4-3 FSM状态转移图】

任务对外状态包括 CREATED、PLANNING、WAITING_PLAN_CONFIRM、PLANNED、RUNNING、WAITING_PATCH_CONFIRM、WAITING_REPLAN_CONFIRM、SUMMARIZING、DONE、FAILED 和 CANCELLED。WAITING_\* 状态具有明确语义：系统已经暂停自动推进，等待人类提交结构化 Decision。DONE、FAILED 和 CANCELLED 为终态，进入后不再被自动修改。

人在环决策（Human-in-the-loop，HITL）不是任意插入的人机交互按钮，而是由成本、风险和不确定性共同触发的受控状态。不同等待状态的进入条件见图 4-4。

【图 4-4 HITL 决策条件】

PLANNING 阶段，如果候选置信度不足、即将调用高代价工具或 SafetyAgent 给出 warn，系统进入 WAITING_PLAN_CONFIRM。RUNNING 阶段，如果步骤失败但仍有 retry budget，系统先进行有界重试；若重试耗尽且局部可修复，则进入 WAITING_PATCH_CONFIRM；若出现结构性失败、安全阻断或恢复余量不足，则进入 WAITING_REPLAN_CONFIRM。人工决策通过 Decision 契约提交，Decision Apply 模块验证 pending action 与候选绑定关系，再推动 FSM 合法迁移。

这一设计为 CEBRA-WP 提供了较清晰的控制边界：算法可以生成候选、计算分数和提出动作建议，但任务状态仍由 FSM 统一推进；算法建议不能绕过 WAITING_\* 状态，也不能把 stop 隐式处理为不可审计的失败。

## 4.4 六阶段蛋白质设计工作流

蛋白质设计能力被组织为六个阶段，如图 4-5 所示。

【图 4-5 六阶段 de novo 蛋白质设计工作流】

六个阶段可以依次理解为序列探索、结构映射、质量门禁、结构条件精修、目标评分和结果汇总。序列探索负责产生候选序列；结构映射把序列转换为结构并产生折叠置信度；质量门禁检查序列合法性、结构完整性和低复杂度等工程质量；结构条件精修依据结构反馈开展重设计；目标评分对候选进行多目标排序；结果汇总生成 DesignResult 和报告。

六阶段是能力上的分层，而不是固定流水线。质量门禁失败可以回到序列探索，目标评分不足可以回到结构条件精修。CEBRA-WP 的作用是在可替代路径间进行受约束的选择：证据不足时延后高代价步骤，局部失败可修复时优先 `patch_local`，结构性失败时转向 `suffix_replan` 或 stop。

## 4.5 CEBRA-WP 的提出背景

上一节给出了蛋白质设计工作流的能力分层和可替代路径，但阶段划分本身并不能回答何时继续执行、何时局部修补、何时后缀重规划以及何时终止止损。CEBRA-WP 的提出，正是为了处理这些运行时决策。

固定流水线适合步骤稳定、失败语义简单的任务，但蛋白质设计的关键风险具有部分可观测性。结构预测失败可能来自服务异常，也可能指向上游序列质量不足；质量门禁失败可能局部可修复，也可能意味着候选链路失效。因此，系统需要把运行时证据纳入规划。

CEBRA-WP 的设计动机主要来自三类研究：部分可观测规划强调 belief-state，预算约束研究要求将成本和风险作为重要决策变量[16,25,26]，Tree of Thoughts 与 Reflexion 提供多候选搜索和失败反馈思路[20,21]。本文将这些思想约束到可执行工具链规划中，使候选、恢复动作和人工确认均以结构化对象来表达。

基于这些考虑，CEBRA-WP 被定义为一种面向高代价科研工作流的约束化、证据感知、信念引导、恢复自适应规划算法。它不追求训练端到端最优控制器，而是以可解释、可配置、可审计的形式，把候选生成、硬约束过滤、静态效用、运行时状态、后验证据和恢复动作选择组织为一个闭环。

## 4.6 CEBRA-WP 形式化定义

CEBRA-WP 的完整名称为 Constraint- and Evidence-aware Belief-guided Recovery-adaptive Workflow Planning，本文译为“约束与证据感知、信念引导、恢复自适应的工作流规划”。当前论文版本为 cebra_wp.v2，其子公式包括 static_score.v1、posterior_score.v1、runtime_adjustment.v1、action_utility.v1 和action_bias.v1。

算法总体闭环如图 4-6 所示。

【图 4-6 CEBRA-WP 算法闭环】

图 4-6 上半部分对应静态规划层：系统根据目标、约束、ProteinToolKG 和历史记录生成候选工具链，并完成硬可行性过滤与静态评分。下半部分对应运行时自适应层：系统根据 StepResult、SafetyResult、失败上下文、预算消耗和恢复历史更新 Lite belief-state / 轻量信念状态，再对候选进行运行时重排序，并在 continue、`patch_local`、`suffix_replan` 和 stop 之间给出动作建议。

表 4-1 汇总了算法说明中使用的主要符号。

| 符号 | 含义 | 来源或载体 | 在算法中的作用 |
|:--:|:--:|:--:|:--:|
| t | 当前决策时间步 | EventLog、RuntimeEvaluator | 索引一次候选生成、状态更新和恢复动作选择 |
| g | 设计目标 | 用户输入Con-firmedTaskSpec | 定义任务目标与目标权重 |

表 4-1

表 4-1（续表）

<table>
<colgroup>
<col style="width: 9%" />
<col style="width: 24%" />
<col style="width: 35%" />
<col style="width: 30%" />
</colgroup>
<thead>
<tr>
<th style="text-align: center;">符号</th>
<th style="text-align: center;">含义</th>
<th style="text-align: center;">来源或载体</th>
<th style="text-align: center;">在算法中的作用</th>
</tr>
</thead>
<tbody>
<tr>
<td style="text-align: center;"><span class="math display"><em>C</em></span></td>
<td style="text-align: center;">约束集合</td>
<td style="text-align: center;">任务约束、策略配置</td>
<td style="text-align: center;">限定长度、安全、预算、工具白名单和输出要求</td>
</tr>
<tr>
<td style="text-align: center;"><span class="math display"><em>K</em></span></td>
<td style="text-align: center;">ProteinToolKG</td>
<td style="text-align: center;">ProteinToolKG</td>
<td style="text-align: center;">提供工具能力、I/O schema、兼容关系、成本和风险</td>
</tr>
<tr>
<td style="text-align: center;"><span class="math display"><em>h</em><sub><em>t</em></sub></span></td>
<td style="text-align: center;"><p>时间步 <span class="math inline"><em>t</em></span> 前的执行</p>
<p>历史</p></td>
<td style="text-align: center;">EventLog、TaskSnapshot</td>
<td style="text-align: center;"><p>提供已完成步骤、</p>
<p>失败记录、恢复历</p>
<p>史和人工决策</p></td>
</tr>
<tr>
<td style="text-align: center;"><span class="math display"><em>o</em><sub><em>t</em></sub></span></td>
<td style="text-align: center;">当前运行时观测</td>
<td style="text-align: center;">StepResult、SafetyResult、指标、错误细节</td>
<td style="text-align: center;">更新运行时状态并计算后验证据</td>
</tr>
<tr>
<td style="text-align: center;"><span class="math display"><em>x</em><sub><em>t</em></sub></span></td>
<td style="text-align: center;">Lite belief-state / 轻量信念状态</td>
<td style="text-align: center;">`RuntimeState`</td>
<td style="text-align: center;">表示成功概率、结构性失败概率、恢复余量、剩余成本和证据充分度</td>
</tr>
<tr>
<td style="text-align: center;"><span class="math display"><em>x</em><sub><em>t</em> + 1</sub></span></td>
<td style="text-align: center;">观测更新后的轻量信念状态</td>
<td style="text-align: center;">RuntimeState更新结果</td>
<td style="text-align: center;">为候选重排和恢复动作选择提供更新后状态</td>
</tr>
<tr>
<td style="text-align: center;"><span class="math display"><em>Π</em><sub>raw, <em>t</em></sub></span></td>
<td style="text-align: center;">原始候选集合</td>
<td style="text-align: center;">PlannerAgent</td>
<td style="text-align: center;">包含初始计划、局部修补或重规划候选</td>
</tr>
<tr>
<td style="text-align: center;"><span class="math display"><em>Π</em><sub><em>t</em></sub></span></td>
<td style="text-align: center;">过滤后的候选集合</td>
<td style="text-align: center;">FeasibilityFilter</td>
<td style="text-align: center;">只保留可执行或受保护的 degraded feasible 候选</td>
</tr>
<tr>
<td style="text-align: center;"><span class="math display"><em>π</em></span></td>
<td style="text-align: center;">候选工作流</td>
<td style="text-align: center;">PlanCandidate、PatchCandidate、ReplanCandidate</td>
<td style="text-align: center;">作为过滤、评分和重排序的基本对象</td>
</tr>
<tr>
<td style="text-align: center;"><span class="math display"><em>π</em><sup>*</sup></span></td>
<td style="text-align: center;">默认候选</td>
<td style="text-align: center;">RuntimeEvaluator、Decision</td>
<td style="text-align: center;">作为自动执行或 HITL 审查的默认建议</td>
</tr>
<tr>
<td style="text-align: center;"><span class="math display"><em>S</em><sub><em>s</em><em>t</em><em>a</em><em>t</em><em>i</em><em>c</em></sub></span></td>
<td style="text-align: center;">静态效用</td>
<td style="text-align: center;">score_breakdown</td>
<td style="text-align: center;">在运行时观测介入前评价候选先验质量</td>
</tr>
<tr>
<td style="text-align: center;"><span class="math display"><em>G</em><sub>post</sub></span></td>
<td style="text-align: center;">后验目标匹配</td>
<td style="text-align: center;">posterior_objective</td>
<td style="text-align: center;">根据证据可靠性修正目标评分</td>
</tr>
<tr>
<td style="text-align: center;"><span class="math display"><em>Δ</em></span></td>
<td style="text-align: center;">运行时修正项</td>
<td style="text-align: center;">runtime_adjustment</td>
<td style="text-align: center;">根据状态变量修正候选排序</td>
</tr>
<tr>
<td style="text-align: center;"><span class="math display"><em>U</em><sub><em>π</em></sub></span></td>
<td style="text-align: center;">候选运行时效用</td>
<td style="text-align: center;">RuntimeEvaluator</td>
<td style="text-align: center;">输出 Top-K 和默认候选</td>
</tr>
</tbody>
</table>

表 4-1（续表）

| 符号 | 含义 | 来源或载体 | 在算法中的作用 |
|:--:|:--:|:--:|:--:|
| 
``` math
a_{t}
``` | 恢复动作 | action_utility | 在continue、`patch_local`、`suffix_replan`、stop之间选择 |

在时间步$t$，算法输入为 $\left( g,C,K,h_{t},o_{t},x_{t} \right)$，输出为结构化 Decision 建议：候选集合$\Pi_{t}$、默认候选$\pi^{*}$、候选解释、运行时状态摘要和恢复动作$a_{t}$。核心计算过程可概括为：

| 
``` math
\Pi_{\text{raw},t} = {GenerateCandidates}\left( g,C,K,h_{t} \right)
``` | （4-1） |
|:--:|---:|
| 
``` math
\Pi_{t} = {FeasibilityFilter}\left( \Pi_{\text{raw},t},C,K,h_{t} \right)
``` | （4-2） |
| 
``` math
S_{\text{static}} = {StaticUtility}(\pi,g,C,K)
``` | （4-3） |
| 
``` math
x_{t + 1} = {BeliefUpdate}\left( x_{t},o_{t},h_{t} \right)
``` | （4-4） |
| 
``` math
G_{\text{post}} = PosteriorObjective\left( \pi,g,o_{t} \right)
``` | （4-5） |
| 
``` math
U_{\pi} = RuntimeCandidateUtility\left( S_{\text{static}},G_{\text{post}},x_{t + 1} \right)
``` | （4-6） |
| 
``` math
a_{t} = RecoveryAwareActionSelection\left( x_{t + 1},\Pi_{t},h_{t},C \right)
``` | （4-7） |

该定义突出两点：一是候选生成与候选选择相互分离，Planner 可以生成多个方案，但只有通过可行性和效用评估的候选才会进入执行或人工确认；二是运行时状态只修正排序和动作建议，不改变 FSM、Agent 职责和硬约束。

## 4.7 候选生成、硬可行性过滤与静态效用

CEBRA-WP 支持三类候选。PlanCandidate 表示初始完整计划；PatchCandidate 表示对当前计划中局部步骤的参数级、工具级或结构级修补；ReplanCandidate 表示对未执行后缀或整体策略的替换，其中 `suffix_replan` 优先保留已验证前缀，`terminal_stop` 表示继续投入不划算时的终止型重规划候选。

候选进入评分前必须先通过硬可行性过滤。对候选 $\pi$ 定义硬可行性谓词：

| 
``` math
F_{h}\left( \pi,C,K,h_{t} \right) = F_{tool} \land F_{schema} \land F_{io} \land F_{safety} \land F_{budget\text{-}hard} \land F_{availability}
``` | （4-8） |
|----|----|

式中，$F_{h}$——硬可行性谓词；

$F_{tool}$——工具存在性约束；

$F_{schema}$——输入输出 schema 约束；

$F_{io}$——跨步骤 I/O 闭合约束；

$F_{safety}$——安全约束；

$F_{budget - hard}$——硬预算约束；

$F_{availability}$——关键工具可用性或降级路径约束；

其中，$F_{h}$ 为硬可行性谓词，$F_{tool}$ 检查候选中的工具是否存在于能力图或适配器注册表；$F_{schema}$ 检查输入输出字段是否满足工具 schema；$F_{io}$ 检查跨步骤引用是否闭合；$F_{safety}$ 检查是否违反安全等级或触发 safety block；$F_{budget - hard}$ 检查是否突破不可逾越预算上限；$F_{availability}$ 检查关键工具是否可用或是否有明确降级路径。过滤后的集合为：

| 
``` math
\Pi_{t} = \text{\{}\pi \in \Pi_{\text{raw},t} \mid F_{h}\left( \pi,C,K,h_{t} \right) = 1\text{\}}
``` | （4-9） |
|----|----|

硬可行性过滤承担系统边界约束，因此静态评分不能把硬不可行候选“打高分后救回”。工程实现可以保留 degraded feasible 候选用于解释或 HITL 审查，但这类候选必须携带降级原因和人工确认要求。

在候选通过硬过滤后，算法计算静态效用：

| 
``` math
S_{static}(\pi) = w_{f}F_{s}(\pi) + w_{g}G\left( \pi;g,o_{t} \right) - w_{c}C_{norm}(\pi) - w_{r}R_{norm}(\pi) - w_{rec}Rec(\pi) + w_{q}Q(\pi)
``` | （4-10） |  |
|----|----|----|

式中，$F_{s}(\pi)$——候选$\pi$的软可行性分数；

$G\left( \pi;g,o_{t} \right)$——目标适配度；

$C_{norm}(\pi)$——归一化成本；

$R_{norm}(\pi)$——归一化风险；

$Rec(\pi)$——恢复复杂度；

$Q(\pi)$——工程可靠性项；

$w_{f},w_{g},w_{c}$——目标、可行性和成本相关权重；

$w_{r},w_{rec},w_{q}$——风险、恢复复杂度和工程可靠性相关权重；

$F_{s}$是软可行性分数，表示候选在 schema 完整、工具 readiness、fallback depth 等方面的先验质量；$G$是目标匹配度；$C_{norm}$ 是归一化成本；$R_{norm}$

是归一化风险；$Rec$ 是恢复复杂度；$Q$ 是工程可靠性项。权重 $w_{*}$ 由策略配置给出，用于在不同任务设置下调节目标、成本、风险和恢复难度的相对重要性。

静态效用用于形成执行前的候选先验排序。它可以偏好成本更低、风险更小、恢复更容易的工具链，但无法感知执行中已经发生的失败、证据不足或预算压力变化。因此，静态效用之后还需要 Lite belief-state / 轻量信念状态和后验证据修正。

## 4.8 Lite belief-state 与观测更新

CEBRA-WP ，使用 Lite belief-state / 轻量信念状态近似表示执行过程中无法完全观测的工作流状态。它只保留三类变量：对恢复动作选择必要的变量、能从现有日志稳定更新的变量，以及可由实验和案例解释的变量。状态向量定义为：

|                         
 ``` math                 
 x_{t} = \begin{bmatrix}  
 p_{\text{succ}} \\       
 p_{\text{sf}} \\         
 r_{\text{rec}} \\        
 c_{\text{rem}} \\        
 e_{\text{suf}}           
 \end{bmatrix}            
 ```                      | （4-11） |
|-------------------------|----------|

各状态量的语义如表 4-2 所示。

<table>
<caption><p>表 4-2 Lite belief-state/轻量信念状态变量</p></caption>
<colgroup>
<col style="width: 19%" />
<col style="width: 19%" />
<col style="width: 19%" />
<col style="width: 19%" />
<col style="width: 21%" />
</colgroup>
<thead>
<tr>
<th style="text-align: center;">状态量</th>
<th style="text-align: center;">取值范围</th>
<th style="text-align: center;">含义</th>
<th style="text-align: center;">主要更新来源</th>
<th style="text-align: center;">决策作用</th>
</tr>
</thead>
<tbody>
<tr>
<td style="text-align: center;"><p><span class="math display"><em>p</em><sub><em>s</em><em>u</em><em>c</em><em>c</em></sub></span></p>
<p>成功概率</p></td>
<td style="text-align: center;"><span class="math display">[0, 1]</span></td>
<td style="text-align: center;">当前链路继续执行后完成任务的估计概率</td>
<td style="text-align: center;">步骤成功、质量指标、候选静态分、失败记录</td>
<td style="text-align: center;">支持 continue 与 stop 判断</td>
</tr>
<tr>
<td style="text-align: center;"><p><span class="math display"><em>p</em><sub><em>s</em><em>f</em></sub></span></p>
<p>结构失败</p></td>
<td style="text-align: center;"><span class="math display">[0, 1]</span></td>
<td style="text-align: center;">当前链路遭遇结构性失败或后续必须重规划的估计概率</td>
<td style="text-align: center;">结构预测失败、质量门禁失败、安全阻断、重复失败</td>
<td style="text-align: center;">提高 `patch_local`、`suffix_replan`、stop 权重</td>
</tr>
</tbody>
</table>

表 4-2（续表）

<table>
<colgroup>
<col style="width: 19%" />
<col style="width: 20%" />
<col style="width: 20%" />
<col style="width: 20%" />
<col style="width: 20%" />
</colgroup>
<thead>
<tr>
<th style="text-align: center;">状态量</th>
<th style="text-align: center;">取值范围</th>
<th style="text-align: center;">含义</th>
<th style="text-align: center;">主要更新来源</th>
<th style="text-align: center;">决策作用</th>
</tr>
</thead>
<tbody>
<tr>
<td style="text-align: center;"><p><span class="math display"><em>r</em><sub><em>r</em><em>e</em><em>c</em></sub></span></p>
<p>恢复余量</p></td>
<td style="text-align: center;"><span class="math display">[0, 1]</span></td>
<td style="text-align: center;">在保留有效前缀前提下继续恢复的余量</td>
<td style="text-align: center;">已完成步骤比例、失败类型、patch/replan 次数</td>
<td style="text-align: center;">区分局部修补与后缀重规划</td>
</tr>
<tr>
<td style="text-align: center;"><p><span class="math display"><em>c</em><sub><em>r</em><em>e</em><em>m</em></sub></span></p>
<p>剩余成本</p></td>
<td style="text-align: center;">非负实数</td>
<td style="text-align: center;">从当前状态到任务结束的剩余成本暴露</td>
<td style="text-align: center;">剩余步骤、工具成本先验、预算配置、重试记录</td>
<td style="text-align: center;">派生预算压力并约束高代价动作</td>
</tr>
<tr>
<td style="text-align: center;"><p><span class="math display"><em>e</em><sub><em>s</em><em>u</em><em>f</em></sub></span></p>
<p>证据充分</p></td>
<td style="text-align: center;"><span class="math display">[0, 1]</span></td>
<td style="text-align: center;">当前证据是否足以支持进入更高代价步骤</td>
<td style="text-align: center;">质量门禁、结构指标、目标评分、证据可靠性</td>
<td style="text-align: center;">控制高代价步骤推进与人工确认</td>
</tr>
</tbody>
</table>

运行时观测 $o_{t}$ 来自 StepResult、SafetyResult、失败上下文、局部修补/重规划历史、已完成步骤、剩余后缀和 HITL 决策记录。派生量如$b_{\text{press}}$、$v_{\text{hitl}}$、$l_{\text{patch}}$ 和 $p_{\text{pres}}$ 不作为持久化主状态，而是根据当前状态和候选上下文按需计算。这样可以避免把与具体候选强相关的临时判断写入长期状态，从而降低状态漂移风险。

以预算压力为例，$c_{\text{rem}}$ 保留剩余成本原始估计，不直接等同于 $\lbrack 0,1\rbrack$ 区间内的预算压力。若任务给出预算上限 $c_{\text{cap}}$，则：

| 
``` math
b_{\text{press}} = \text{clip}\left( \frac{c_{\text{rem}}}{\max\left( c_{\text{cap}},0.1 \right)},0,1.5 \right)
``` | （4-12） |
|----|----|

若任务未给出预算上限，则使用：

|                                                              
 ``` math                                                      
 b_{\text{press}} = {clip}\left( c_{\text{rem}},0,1.5 \right)  
 ```                                                           | （4-13） |
|--------------------------------------------------------------|----------|

式中，$b_{press}$——预算压力；

$c_{cap}$——任务预算上限；

$clip(.)$——裁剪函数；

因此，预算压力是由任务上下文派生的动作决策量，而不是 `RuntimeState` 的持久化字段。该区分使系统既能记录可解释的剩余成本，也能在不同预算设置下统一比较恢复动作。

状态初始化可由首选候选的静态分数、风险分数、恢复复杂度、剩余成本先验和廉价证据覆盖率给出。例如，$p_{\text{succ}}$ 可由静态候选分数裁剪得到，$p_{\text{sf}}$ 可由风险项裁剪得到，$r_{\text{rec}}$ 可由恢复复杂度的反向量估计，$c_{\text{rem}}$ 来自剩余工具成本先验，$e_{\text{suf}}$ 来自低成本质量证据覆盖率。随着执行推进，成功步骤会提升 $p_{\text{succ}}$ 和证据充分度，结构性失败会提高 $p_{\text{sf}}$ 并降低恢复余量，重复失败和预算消耗则会提高剩余成本压力。

该状态设计参考了部分可观测规划中的 belief-state 思想[16]，但工程实现上保持轻量：系统不求解完整 POMDP，也不在线训练策略网络，而是借助一组可解释变量支撑候选重排和恢复动作选择。

## 4.9 后验目标评分与运行时重排序

蛋白质设计目标通常是多目标的，包括结构质量、稳定性、功能、novelty 和安全性等。不同目标的证据来源不同，证据可靠性也不同。为避免把弱证据与直接证据等价处理，CEBRA-WP 使用证据加权后验目标匹配：

| 
``` math
G_{\text{post}}\left( \pi;g,o_{t} \right) = \sum_{m}^{}{\lambda_{m}(g)\rho_{m}\left( o_{t} \right)q_{m}\left( \pi,o_{t} \right)}
``` | （4-14） |
|----|----|

这里，$m$ 为目标维度，$\lambda_{m}(g)$ 是由任务目标 $g$ 会决定的目标权重，$q_{m}\left( \pi,o_{t} \right)$ 是候选 $\pi$ 在该维度上的归一化分数，$\rho_{m}\left( o_{t} \right)$ 是观测 $o_{t}$ 对目标维度 $m$ 的证据可靠性权重。证据状态分为 direct、proxy、degraded 和 missing：direct evidence 指已产生的结构质量指标，proxy evidence 指由轻量质量门禁推断出的间接信号，degraded evidence 表示工具降级或证据覆盖不完整，missing 表示当前没有可用证据。整体证据充分度可写为：

| 
``` math
e_{t} = {clip}\left( \sum_{m}^{}{\lambda_{m}(g)\rho_{m}\left( o_{t} \right)},0,1 \right)
``` | （4-15） | 
``` math
G_{\text{post}}\left( \pi;g,o_{t} \right) = \sum_{m}^{}{\lambda_{m}(g)\rho_{m}\left( o_{t} \right)q_{m}\left( \pi,o_{t} \right)}
``` | （4-16） |
|----|----|----|----|

式中，$e_{t}$——时间步 $t$ 的整体证据充分度；

该值进入 $e_{\text{suf}}$，影响是否继续进入高代价步骤。若证据不足而候选下一步成本较高，运行时重排序会降低该候选；若已有充分低成本证据支持，则候选可以更合理地进入结构预测或目标评分。

将 $G_{\text{post}}$ 替换静态效用中的目标匹配项后，得到包含后验证据的基础分 $S_{\text{post}}$。运行时重排序定义为：

| 
``` math
U_{\pi}\left( \pi,x_{t} \right) = {clip}\left( S_{\text{post}}(\pi) + \Delta\left( \pi,x_{t} \right),0,1 \right)
``` | （4-17） | 
``` math
G_{\text{post}}\left( \pi;g,o_{t} \right) = \sum_{m}^{}{\lambda_{m}(g)\rho_{m}\left( o_{t} \right)q_{m}\left( \pi,o_{t} \right)}
``` | （4-18） |
|----|----|----|----|

式中，$S_{\text{post}}(\pi)$——替换后验目标项后的基础分；

其中 \Delta(\pi,x_t) 是有界运行时修正项，取值范围控制在 [-0.35,0.35]。其一般形式为：

| 
``` math
\Delta\left( \pi,x_{t} \right) = k_{s}\left( p_{\text{succ}} - 0.5 \right)\text{Conf}(\pi) + k_{e}\left( 2e_{\text{suf}} - 1 \right)\max\left( \text{Conf}(\pi),F_{s}(\pi) \right) - k_{f}p_{\text{sf}}\left( 1 - \text{RiskScore}(\pi) \right) + k_{r}r_{\text{rec}}\text{RecoveryScore}(\pi) - k_{c}b_{\text{press}}\left( 1 - \text{CostScore}(\pi) \right) + k_{a}\text{ActionBias}\left( \pi,x_{t} \right)
``` | （4-19） | 
``` math
G_{\text{post}}\left( \pi;g,o_{t} \right) = \sum_{m}^{}{\lambda_{m}(g)\rho_{m}\left( o_{t} \right)q_{m}\left( \pi,o_{t} \right)}
``` | （4-20） |
|----|----|----|----|

其中，Conf(pi) 表示候选置信度，RiskScore(pi) 和 CostScore(pi) 分别表示候选的风险质量分数和成本质量分数，RecoveryScore(pi) 表示候选的恢复友好度，ActionBias(pi, x_t) 表示候选与当前恢复动作偏好的匹配程度。直观来看，当结构性失败风险和预算压力升高时，算法会降低高成本、低可恢复性候选的排序；当成功概率、恢复余量和证据充分性较高时，算法会提高继续执行或低风险候选的排序。

运行时重排序有两个边界：一是只作用于已经通过可行性校验的候选，不能覆盖工具不存在、schema 错误、I/O 不闭合和安全阻断；二是修正幅度存在上界，避免一次异常观测完全覆盖静态目标匹配和工程可靠性判断。借助这两个边界，算法在适应运行时变化的同时仍能保持可复现和能够审计。

## 4.10 恢复动作选择与 HITL 映射

CEBRA-WP 将恢复动作限定为四类：continue、`patch_local`、`suffix_replan` 和 stop。四类动作与 FSM/HITL 的映射如表 4-3 所示。

| 动作 | 触发背景 | 系统效果 | FSM/HITL 映射 | 审计结果 |
|:--:|:--:|:--:|:--:|:--:|
| continue | 成功概率较高、证据充分、风险和预算压力可接受 | 继续执行当前计划后续步骤 | RUNNING内自动推进或维持 PLANNED/RUNNING | 记录动作效用与继续原因 |
| `patch_local` | 局部失败、重试耗尽、前缀仍有效、局部可修复性较高 | 生成局部 PlanPatch，替换参数或局部工具 | WAITING_PATCH_CONFIRM 或策略允许的受控自动 patch | 记录 patch 候选、失败上下文和应用结果 |

表 4-3 恢复动作与FSM/HITL映射

表 4-3（续表）

| 动作 | 触发背景 | 系统效果 | FSM/HITL 映射 | 审计结果 |
|:--:|:--:|:--:|:--:|:--:|
| `suffix_replan` | 结构性失败概率升高、后缀可靠性不足、前缀可保留 | 保留已验证前缀，替换未执行后缀 | WAITING_REPLAN_CONFIRM | 记录 replan 候选、前缀保留位置和新后缀 |
| stop | 成功概率低、预算压力高、恢复余量低、人工介入价值有限 | 生成终止型 ReplanCandidate | WAITING_REPLAN_CONFIRM；接受后进入 FAILED | 记录 terminal_reason 与已保留证据 |

动作效用由状态量和派生量共同计算。为便于表示，记 $s = p_{\text{succ}}$，$f = p_{\text{sf}}$，$r = r_{\text{rec}}$，$e = e_{\text{suf}}$，$b = b_{\text{press}}$。局部可修复性、证据可复用性、前缀可保留性、预算缓解度、目标重对齐收益和人工介入价值，分别记为 $l_{\text{patch}}$、$e_{\text{reuse}}$、$p_{\text{pres}}$、$b_{\text{relief}}$、$g_{\text{align}}$ 和 $v_{\text{hitl}}$。动作效用可写为：

| 
``` math
U_{\text{continue}} = 0.38s + 0.14e + 0.12r - 0.22f - 0.14b
``` | （4-21） |
|:--:|---:|
| 
``` math
U_{\text{`patch_local`}} = 0.20s + 0.24r + 0.18l_{\text{patch}} + 0.12e_{\text{reuse}} - 0.14f - 0.12b
``` | （4-22） |
| 
``` math
U_{\text{`suffix_replan`}} = 0.18(1 - s) + 0.20f + 0.16(1 - r) + 0.18p_{\text{pres}} + 0.14b_{\text{relief}} + 0.14g_{\text{align}}
``` | （4-23） |
| 
``` math
U_{\text{stop}} = 0.32(1 - s) + 0.24b + 0.18(1 - r) + 0.16s_{\text{safe}} + 0.10\left( 1 - v_{\text{hitl}} \right)
``` | （4-24） |

其中，$s_{\text{safe}}$ 为安全终止性。这组效用函数区分了四类动作的不同偏好：continue 对较高成功概率、证据充分度和恢复余量更敏感；`patch_local` 更依赖局部可修复性、证据可复用性和较低结构性失败概率；`suffix_replan` 偏向于结构性失败概率较高、当前成功概率较低但前缀仍可保留的场景；stop 只有在继续价值低、预算压力高、恢复余量低且人工介入价值不足时才会成为强候选。

stop 不是用户主动取消，也不是执行异常崩溃，而是算法提出的终止型重规划候选。其载体为 ReplanCandidate(replan_mode="`terminal_stop`")，通过 replan_confirm 通道进入 WAITING_REPLAN_CONFIRM。只有在人工接受或策略显式允许时，系统才将任务推进到 FAILED；已完成前缀、产物和解释字段仍被保留为审计资产。

综合上述设计，CEBRA-WP 主流程可写为算法 41。

<table>
<caption><p>算法 4-1CEBRA-WP 主流程</p></caption>
<colgroup>
<col style="width: 100%" />
</colgroup>
<thead>
<tr>
<th><p>输入：</p>
<p>    g：设计目标；</p>
<p>    C：约束集合；</p>
<p>    K：ProteinToolKG；</p>
<p>    h_t：执行历史；</p>
<p>    o_t：当前观测；</p>
<p>x_t：轻量信念状态。</p>
<p>输出：</p>
<p>Decision_t：候选集合、默认候选、恢复动作、解释信息和证据引用。</p>
<p>1. Pi_raw,t &lt;- GenerateCandidates(g, C, K, h_t)</p>
<p>2. Pi_t &lt;- FeasibilityFilter(Pi_raw,t, C, K, h_t)</p>
<p>3. if Pi_t is empty and degraded_feasible candidates exist:</p>
<p>4. Pi_t &lt;- degraded_feasible candidates</p>
<p>5. mark candidates as requiring HITL confirmation</p>
<p>6. for each pi in Pi_t:</p>
<p>7. S_static(pi) &lt;- StaticUtility(pi, g, C, K)</p>
<p>8. S_post(pi) &lt;- ReplaceObjectiveTerm(S_static(pi), PosteriorObjective(pi, g, o_t))</p>
<p>9. x_t+1 &lt;- BeliefUpdate(x_t, o_t, h_t)</p>
<p>10. for each pi in Pi_t:</p>
<p>11. Delta(pi, x_t+1) &lt;- RuntimeAdjustment(pi, x_t+1)</p>
<p>12. U_pi(pi, x_t+1) &lt;- clip(S_post(pi) + Delta(pi, x_t+1), 0, 1)</p>
<p>13. TopK_t &lt;- SelectDiverseTopK(Pi_t, U_pi, capability_coverage)</p>
<p>14. U_a &lt;- ComputeActionUtility(continue, `patch_local`, `suffix_replan`, stop)</p>
<p>15. a_t &lt;- ApplyHardPrioritiesAndSelectAction(U_a, x_t+1, h_t, C)</p>
<p>16. return Decision_t(TopK_t, a_t, explanations, evidence_refs)</p></th>
</tr>
</thead>
<tbody>
</tbody>
</table>

算法第， 1 至 8 行完成候选生成与评价，第 9 至 12 行依据运行时状态修正候选效用，第 13 行保留 Top-K 多样性，第 14 至 15 行选择恢复动作。第 15 行中的硬优先级包括安全阻断优先、schema/I/O/tool availability 违规淘汰、重试耗尽后优先局部修补、前缀可保留时优先后缀重规划等约束。借助这些优先级，动作选择服从系统控制边界，而不是简单按连续效用值排序。

## 4.11 策略组与实验可验证性

为了验证 CEBRA-WP 各组成机制的作用，系统将算法能力拆分为四组策略开关。四组策略不是四套独立系统，而是在同一在工程实现方面逐步打开静态评分、固定阈值门控、动态恢复和 Lite belief-state 的内部消融配置，如表 4-4 所示。

<table>
<caption><p>表 4-4 四组消融策略与算法机制开关</p></caption>
<colgroup>
<col style="width: 16%" />
<col style="width: 9%" />
<col style="width: 13%" />
<col style="width: 8%" />
<col style="width: 9%" />
<col style="width: 12%" />
<col style="width: 8%" />
<col style="width: 21%" />
</colgroup>
<thead>
<tr>
<th style="text-align: center;">策略组</th>
<th style="text-align: center;">静态评分</th>
<th style="text-align: center;">固定阈值门控</th>
<th style="text-align: center;">动态观测</th>
<th style="text-align: center;">Lite belief-state</th>
<th style="text-align: center;">Runtime rerank</th>
<th style="text-align: center;">恢复动作效用</th>
<th style="text-align: center;">主要实验问题</th>
</tr>
</thead>
<tbody>
<tr>
<td style="text-align: center;">`static_top1`</td>
<td style="text-align: center;">启用</td>
<td style="text-align: center;">未启用</td>
<td style="text-align: center;">未启用</td>
<td style="text-align: center;">未启用</td>
<td style="text-align: center;">未启用</td>
<td style="text-align: center;">未启用</td>
<td style="text-align: center;">单一静态最优候选是否足以完成任务</td>
</tr>
<tr>
<td style="text-align: center;"><p>fixed</p>
<p>_threshold</p>
<p>_gate</p></td>
<td style="text-align: center;">启用</td>
<td style="text-align: center;">启用</td>
<td style="text-align: center;">有限使用</td>
<td style="text-align: center;">未启用</td>
<td style="text-align: center;">未启用</td>
<td style="text-align: center;">未启用</td>
<td style="text-align: center;">固定阈值是否能控制风险与成本</td>
</tr>
<tr>
<td style="text-align: center;"><p>dynamic</p>
<p>_no_belief</p>
<p>_stat</p></td>
<td style="text-align: center;">启用</td>
<td style="text-align: center;">启用</td>
<td style="text-align: center;">启用</td>
<td style="text-align: center;">未启用</td>
<td style="text-align: center;">部分启用</td>
<td style="text-align: center;">部分启用</td>
<td style="text-align: center;">直接运行时观测是否已能支撑恢复</td>
</tr>
<tr>
<td style="text-align: center;"><p>lite_belief</p>
<p>_state</p></td>
<td style="text-align: center;">启用</td>
<td style="text-align: center;">启用</td>
<td style="text-align: center;">启用</td>
<td style="text-align: center;">启用</td>
<td style="text-align: center;">启用</td>
<td style="text-align: center;">启用</td>
<td style="text-align: center;">显式状态是否带来更好的解释、预算感知和恢复决策</td>
</tr>
</tbody>
</table>

该策略设计使第， 7 章可以分别考察：静态计划是否足够，固定阈值门控是否带来额外成本，以及在已有动态恢复时 Lite belief-state 的增量价值。本文不把 CEBRA-WP 论证为所有指标最优算法，而是验证其机制链路是否可执行、可观测、可审计。

## 4.12 数据契约与模块协作

系统以统一数据契约支撑算法与工程实现之间的衔接。核心契约关系如图 4-7 所示。

【图 4-7 核心数据契约UML】

ProteinDesignTask 记录 task_id、goal 和约束字段；Plan 由 PlanStep 组成，并用 S{id}.{field} 建立依赖；StepResult 保存执行状态、输出、指标和失败信息；PendingAction/Decision 管理人工确认；TaskSnapshot 保存可恢复状态。

图 4-8 展示了典型任务 t1 的贯穿示例。

【图 4-8 t1任务实例走查】

该示例从任务创建开始，依次经过， Planner 生成候选计划、用户确认、Executor 调用工具、StepResult 写入、`RuntimeState` 更新和必要的恢复候选触发，最后由 Summarizer 汇总为 DesignResult。CEBRA-WP 在这里不是孤立算法模块，而是嵌入任务生命周期的规划与恢复层：算法输出通过 PendingAction、PlanPatch、ReplanCandidate 和 `RuntimeState` 等契约进入系统，任务状态仍由 FSM 和 Workflow 控制。

## 4.13 本章小结

本章给出系统总体设计和 CEBRA-WP 算法定义。系统采用五层架构，并以 FSM、HITL、ProteinToolKG 和六阶段工作流约束任务推进；算法层则定义候选生成、硬可行性过滤、静态评分、Lite belief-state 更新、运行时重排序和恢复动作选择。
