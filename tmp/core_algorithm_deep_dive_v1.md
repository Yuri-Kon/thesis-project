# 核心算法深度解读（第一部分）

本文档面向“需要彻底理解当前研究问题与核心算法设计”的读者，目标不是简单复述代码，而是把下面几件事情串成一条完整链路：

1. 当前项目到底在解决什么研究问题；
2. 为什么不能只做一次性静态规划，而必须引入运行时状态与恢复控制；
3. 核心算法由哪些层组成，各层的输入、输出、约束、公式分别是什么；
4. 这些设计是如何落到当前代码实现中的；
5. 目前实现相对设计文档有哪些简化、近似和工程化取舍。

本文档聚焦用户提出的第 1 项需求：帮助你系统理解“研究问题 + 算法设计 + 公式 + 实现”。
第 2 项“参数分层、初始选定、调参方法”将在下一份文档中单独展开。

---

## 1. 先给出一句总定义

这个项目的核心算法，不是“让 LLM 生成一个计划”这么简单，也不是“从 ToolKG 检索工具链”这么简单。

它真正要解决的问题是：

**在高代价、长链路、会失败、且失败后需要可恢复控制的蛋白质设计工作流中，动态生成、评估、裁剪并修正工具链，使系统以更低成本获得更高任务成功率。**

这一定义来自设计文档中的算法 SSOT（single source of truth）：

- `core-algorithm-spec.md` 将其定义为一个 `constraint-aware / budget-aware / risk-aware / recovery-aware` 的工作流级动态规划问题，而不是普通的工具检索问题。
- 输入包括任务目标、约束、工具能力图、当前执行上下文、当前运行时观测；
- 输出不仅可以是“推荐执行链”，还可以是 `patch`、`suffix_replan`、`stop` 这类恢复/控制动作。

对应设计位置：

- `../thesis-project.design/docs/design/core-algorithm-spec.md`
- 关键段落：第 4 节“核心问题建模”、第 5 节“优化目标与六类 Schema”

---

## 2. 当前研究问题是什么

### 2.1 表面问题

从用户视角看，项目像是在做“蛋白质设计任务自动化”：

- 给定自然语言目标和约束；
- 自动生成执行计划；
- 调用一串工具完成序列探索、结构预测、质量过滤、精修、目标打分；
- 最后生成结果报告。

如果只停留在这层理解，很容易误以为：

- 只要让 Planner 输出一个 Plan 即可；
- 只要这条 Plan 能执行就可以；
- 中间失败了再简单重试即可。

### 2.2 真正的问题

设计文档明确指出，真实科研工作流不是低成本的 API 编排，而是有三个困难：

1. **关键风险并不完全可观测**
   - 一次结构预测失败，可能只是偶发噪声；
   - 也可能意味着当前后缀整体不可行。

2. **错误代价高度非线性**
   - 一次高代价步骤调用出错，常常不仅仅损失一步时间；
   - 还会让后续多步都建立在错误前提上，导致整条链白跑。

3. **恢复价值依赖已完成前缀**
   - 失败之后究竟应该 patch 还是 replan，不能只看失败步本身；
   - 必须看“前面已经完成了什么、这些成果值不值得保留”。

这三点是为什么必须引入运行时状态（Lite belief-state）的核心理由。

换句话说，本项目研究的不是“如何找到一条好链路”，而是：

**如何在执行过程中持续判断这条链是否还值得继续，以及失败后如何以最小代价恢复。**

---

## 3. 为什么不能只做静态规划

### 3.1 静态规划能解决什么

静态规划层回答的问题是：

- 哪些候选链路在 I/O、能力覆盖、工具治理层面是可执行的；
- 在还没有消费任何运行时观测之前，哪条链先验上更值得尝试。

这意味着静态规划擅长：

- Tool retrieval；
- Candidate generation；
- Candidate scoring；
- 在初始阶段做 Top-K 排序和默认推荐。

### 3.2 静态规划不能解决什么

一旦真正开始执行，新的信息会不断出现：

- 某一步成功还是失败；
- 失败是局部参数问题，还是结构性问题；
- 安全检查是 `allow`、`warn` 还是 `block`；
- 当前是否已经积累了足够证据去进入下一个昂贵步骤；
- 还剩多少预算暴露和恢复余量；
- 当前是否已经处于“继续不划算、但人工可能还能救”的区间。

这些都不是初始规划时能完整知道的。

所以项目采用两层结构：

1. **静态规划层**
   - 先验生成和排序候选；

2. **运行时自适应层**
   - 消费执行观测；
   - 更新轻量状态估计；
   - 对候选重新排序；
   - 选择继续、局部修补、保前缀重规划或止损。

设计文档对此有明确描述：

- 第 6 节将算法拆成“静态规划层 + 运行时自适应层”；
- 第 10 节引入 Lite belief-state；
- 第 11 节定义 runtime reranking；
- 第 12 节定义动作选择；
- 第 13 节定义 HITL gate。

---

## 4. 这个算法不是什么

为了避免误解，需要先澄清几个“不是”。

### 4.1 它不是新的 Agent

Lite belief-state 是内部状态估计模块，不是新的 Agent。
项目的 Agent 边界仍然保持：

- PlannerAgent：产出 Plan / Patch / Replan 候选；
- ExecutorAgent / PlanRunner / PatchRunner：执行与恢复；
- SafetyAgent：只产出 `ok / warn / block` 风险评估；
- SummarizerAgent：做结果汇总。

### 4.2 它不是 full POMDP / full RL 控制器

运行时形式化文档明确写了本课题的建模立场：

- 不做 full POMDP；
- 不做 full RL；
- 不重写整个控制器；
- 必须可解释、可配置、可审计、可复现；
- 必须显式服务于 `retry -> patch -> replan`。

因此当前实现是“规则化的 Lite belief-state + 有界 rerank + 显式状态机”。

### 4.3 它不是绕过 FSM/HITL 的自动决策系统

系统所有控制动作都受 FSM 与 HITL 契约约束：

- `WAITING_*` 语义必须显式；
- 进入等待态前必须写快照；
- 人工决策必须通过 `PendingAction / Decision`；
- 不能跳过等待态偷偷做隐式人工决策。

所以这里的“智能控制”始终运行在强约束的架构边界之内。

---

## 5. 算法的总体结构

设计文档给出的总体流程可以压缩成下面这张概念图：

1. 任务输入
2. Tool retrieval
3. Candidate generation
4. Static scoring
5. Top-K + 默认推荐
6. HITL gate 或自动执行
7. 执行时持续提取观测
8. 更新 `runtime_state`
9. Runtime reranking
10. 动作选择：`continue / patch_local / suffix_replan / stop`
11. 若需要人工参与，则进入 `WAITING_*`
12. 应用 Decision 后继续执行或结束

这条链条里最关键的设计思想是：

**“先验规划”和“运行时控制”被分成两个层，但又通过 `runtime_state` 和 `candidate metadata` 串起来。**

---

## 6. 工作流语境：六阶段 de novo 设计链

算法不是在抽象空间里运行，它服务的是一个六阶段 de novo 工作流。

设计文档中的六阶段是：

1. 序列探索（Sequence Exploration）
2. 结构映射（Structure Projection）
3. 质量门禁（Quality Gate）
4. 结构条件精修（Structure-conditioned Refinement）
5. 目标/功能/物性评估（Objective Scoring）
6. Patch/Replan 控制层（贯穿式控制层）

这 6 个阶段只定义能力分层，不绑定固定工具。Planner 要基于 ToolKG、I/O 契约和治理规则自由组合。

特别重要的是第 6 层：

- 它不是线性流水线的最后一步；
- 而是可以在任意阶段介入的“控制切面”；
- 负责根据失败、风险、预算压力、证据充分度，决定是否继续当前链、局部修补、重规划或止损。

设计文档还明确指出哪些步骤通常是高代价/高暴露步骤：

- 结构映射（如 ESMFold / OpenFold3）
- 结构条件精修（如 ProteinMPNN 多轮采样）
- 重型目标评估

相对而言：

- 序列探索；
- 质量门禁；

更适合做低成本证据积累和早停过滤层。

这直接解释了为什么算法要关心：

- `expected_remaining_cost`
- `evidence_sufficiency`
- `recovery_margin`
- `p_structural_failure`

因为它们正是“是否值得进入下一个高代价步骤”的决策变量。

---

## 7. 优化目标：系统真正想最优化什么

设计文档给出的效用函数是：

`Utility(pi, x_t) = alpha * Feasibility + beta * GoalFit - gamma * Cost - delta * Risk - eta * RecoveryComplexity - zeta * HumanInterventionCost`

这个定义非常重要，因为它说明项目并不是单目标优化。

它同时优化 4 件事：

1. **更高最终任务成功率**
2. **更少无效高代价调用**
3. **更低恢复复杂度**
4. **更合理的人机分工**

因此这个系统绝不是“成功率越高越好”这么简单。
一个方案就算最终成功，如果：

- 它调用了太多高代价步骤；
- 多次进入无效 replan；
- 经常把简单问题升级成复杂恢复；
- 频繁把人拉进来做低价值确认；

那么它仍然不是好方案。

这也是后面很多指标设计的来源。

---

## 8. 六类 Schema：算法为什么能做到“可解释”

设计文档要求固定六类 schema：

1. `Cost Schema`
2. `Risk Schema`
3. `Recovery Schema`
4. `State Schema`
5. `Observation Schema`
6. `Action-Utility Schema`

这里的核心思想是：

- 不把“代价”“风险”“恢复性”“状态”“观测”“动作价值”揉成一个模糊总分；
- 而是把它们显式拆开；
- 让系统在实验、审计、回放时可以解释“为什么当时做了这个动作”。

这也是当前实现中会留下：

- `score_breakdown`
- `runtime_adjustment`
- `shadow_score`
- `final_score`
- `rerank_reason`
- `waiting_runtime_summary`

这类元数据的原因。

---

## 9. 静态规划层：候选是如何被生成与排序的

### 9.1 静态层的职责

静态层负责回答两个问题：

1. 哪些候选链路是可执行的；
2. 哪些候选链路在任务先验上更值得尝试。

它由以下组件组成：

- Tool retrieval
- Candidate generation
- Static scoring
- HITL gate

### 9.2 候选类型

系统支持三类候选：

- `PlanCandidate`
- `PatchCandidate`
- `ReplanCandidate`

其中：

- `PlanCandidate` 用于初始规划；
- `PatchCandidate` 目标是“最小代价恢复执行”；
- `ReplanCandidate` 目标是“保留有效前缀，替换不值得继续的后缀”。

对于 Patch，设计上要求恢复优先级为：

1. 参数级修补
2. 工具级替换
3. 结构级调整

对于 Replan，设计上要求优先级为：

- 默认优先 `suffix_replan`
- 当前缀不可保留时才允许 `full_replan`
- 继续与恢复都不划算时才允许 `terminal_stop`

### 9.3 当前代码如何实现静态评分

在 `src/agents/planner.py` 中，核心静态评分函数是 `_score_payload()`。

它会从候选涉及的工具中抽取：

- `risk_scores`
- `cost_scores`
- `readiness_scores`
- `capabilities`

然后计算：

- `tool_coverage`
- `fallback_depth`
- `tool_readiness`

接着合成：

- `feasibility`
- `objective`
- `risk`
- `cost`
- `confidence`
- `overall`

当前实现中的主要公式是：

- `feasibility = 0.5 + 0.25 * tool_coverage + 0.25 * fallback_depth`
- `objective = 1.0 - 0.3 * avg_cost + objective_bonus`
- `risk = 1.0 - avg_risk`
- `cost = 1.0 - avg_cost`
- `confidence = 0.35 * feasibility + 0.25 * tool_readiness + 0.2 * tool_coverage + 0.2 * fallback_depth`
- `overall = 各项按 score_weights 加权求和`

需要注意两点：

1. 这些是**实现层的工程启发式公式**；
2. 它们不是从某篇论文直接抄来的最终参数，而是对设计文档中静态评分原则的一个可复现实现。

### 9.4 `risk_level` 和 `cost_estimate`

系统会把连续值风险/成本映射为：

- `low`
- `medium`
- `high`

阈值是：

- `< 0.33 -> low`
- `0.33 ~ 0.66 -> medium`
- `>= 0.66 -> high`

这与设计文档中的推荐映射一致。

### 9.5 静态层在代码中的位置

- 候选构造与排序：`src/agents/planner.py`
- 核心入口：
  - `plan_top_k()`
  - `patch_top_k()`
  - `replan_top_k()`
  - `_build_top_k_result()`
  - `_score_payload()`

---

## 10. Lite belief-state：为什么是这 5 个状态

### 10.1 设计思想

Lite belief-state 的目标不是完整重建外部环境，而是只保留“对动作选择真正必要的隐状态”。

设计文档要求保留 5 个核心状态：

1. `p_success`
2. `p_structural_failure`
3. `recovery_margin`
4. `expected_remaining_cost`
5. `evidence_sufficiency`

它们分别回答：

- 继续当前链最终成功的概率大概还有多高？
- 当前是不是已经进入结构性失败区域？
- 不丢失有效前缀的前提下，还剩多少恢复余量？
- 从现在到终止，还剩多少成本暴露？
- 当前证据是否已经足够支持继续进入更昂贵的步骤？

### 10.2 为什么没有把所有量都持久化

设计文档明确规定下面这些量不作为持久化主状态，而是派生量：

- `budget_pressure`
- `intervention_value`
- `local_patchability`
- `prefix_preservability`

原因是：

- 它们对动作选择有用；
- 但更依赖“当前候选集、阶段、策略配置”；
- 如果直接持久化，会让状态过度耦合并更容易漂移。

所以当前项目采取的策略是：

- 只把 5 个主状态持久化到快照；
- 派生量在动作选择现场临时计算。

---

## 11. 运行时观测：系统到底观察了什么

设计文档说“运行时状态更新只允许来自”：

- `StepResult.metrics / outputs / error_details`
- `SafetyResult.risk_flags / action`
- patch/replan 历史
- 预算消耗与剩余后缀
- HITL 决策记录

当前代码中，这些观测主要来自下面 4 类对象：

### 11.1 `StepResult`

包含：

- 步骤是否成功/失败/跳过；
- `failure_type`
- `error_message`
- `error_details`
- `outputs`
- `artifacts`
- `metrics`
- `risk_flags`

这是最核心的执行观测来源。

### 11.2 `SafetyResult`

包含：

- 风险 flag 列表；
- `action = allow / warn / block`

这是运行时风险信号的正式输入。

### 11.3 `RuntimeFailureContext`

从失败步骤进一步归纳出：

- `retry_exhausted`
- `recovery_action`
- patch/replan 相关元数据

它服务于“恢复语义”的抽取和回放。

### 11.4 进度观测

通过：

- `completed_steps`
- `total_steps`

推导：

- 剩余步数
- 完成比例

这会直接影响 `expected_remaining_cost` 和 `evidence_sufficiency`。

---

## 12. `runtime_state` 是如何更新的

当前实现中，`WorkflowContext` 是运行时状态更新的统一入口。

当：

- 新增 `StepResult`
- 新增 `SafetyResult`

时，`WorkflowContext` 会调用 `apply_runtime_state_update()`，进一步调用 `update_runtime_state()`。

因此当前项目没有把 belief-state 更新散落到各个执行模块里，而是尽量通过上下文统一接入。

### 12.1 初始值

当前实现的默认初始值是：

- `p_success = 0.5`
- `p_structural_failure = 0.25`
- `recovery_margin = 0.6`
- `expected_remaining_cost = 1.0` 或剩余步数
- `evidence_sufficiency = 0.5`

这体现的是一种“中性但略保守”的起始假设：

- 系统默认不是特别乐观；
- 也不是直接把失败风险设得很高；
- 而是让状态在后续观测中逐步收敛。

### 12.2 成功/失败对状态的影响

如果一步成功：

- `p_success` 上升；
- `p_structural_failure` 下降；
- `recovery_margin` 上升；
- `cost_reward` 增加；
- 若是结构相关步骤，还会额外提高正向增益。

如果一步失败：

- `p_success` 下降；
- `p_structural_failure` 上升；
- `recovery_margin` 下降；
- `cost_penalty` 增加；
- 若是结构相关步骤，还会额外提高结构失败概率；
- 若重试耗尽，则进一步惩罚。

这些规则体现了非常明确的建模直觉：

- 结构相关失败比普通失败更值得警惕；
- 成功完成关键步骤会降低后续暴露；
- 重试耗尽说明“局部故障不是偶发”，需要更强惩罚。

### 12.3 安全检查对状态的影响

如果 `SafetyResult.action = warn`：

- `p_success` 小幅下降；
- `p_structural_failure` 上升；
- `recovery_margin` 下降；
- `cost_penalty` 上升。

如果 `action = block`：

- 惩罚更大；
- 表示当前链继续执行的可取性明显下降。

### 12.4 恢复动作对状态的影响

如果恢复动作是：

- `patch_local`：说明仍有局部修复希望，但会额外消耗恢复余量和成本；
- `suffix_replan` / `replan`：说明当前路径已经更偏向结构性问题，因此惩罚更大；
- `stop`：说明恢复余量已基本归零。

### 12.5 `expected_remaining_cost` 的更新

当前实现中有两种模式：

1. 如果知道 `completed_steps` 和 `total_steps`
   - 直接按剩余步数估算基础成本；
   - 再叠加 `cost_penalty`。

2. 如果不知道总步数
   - 基于上一次成本滚动更新；
   - 成功会减小；
   - 失败会增大；
   - 再叠加惩罚和奖励。

这与正式文档中的“在线剩余成本”思想是一致的：

- 不把成本只看成时间；
- 而是看成“从现在到终止还暴露多少资源和恢复开销”。

### 12.6 `evidence_sufficiency` 的更新

当前实现先计算一个 `evidence_signal`，然后做平滑更新：

- `evidence_sufficiency = 0.70 * previous + 0.30 * evidence_signal`

`evidence_signal` 又由三部分组成：

1. `cheap_validation_coverage`
2. `candidate_agreement`
3. `metric_completeness`

分别表示：

- 廉价验证与执行进度覆盖是否足够；
- 当前结果是否支持现有候选链继续成立；
- 当前证据是否足够完整，可以支持后续动作判断。

这说明 `evidence_sufficiency` 不是“看一步成功没成功”这么简单，而是在回答：

**“我们现在手里的证据，是否足以证明继续进入更昂贵步骤是合理的？”**

---

## 13. Runtime reranking：为什么不是直接用静态分

### 13.1 目标

静态评分只能回答：

> “这条链在开始执行前，看起来值不值得试？”

运行时重排序要回答的是：

> “已经执行到现在，这条链还值不值得继续？”

### 13.2 基本形式

设计文档要求：

`final_score = clip(static_score + runtime_adjustment, 0, 1)`

并且要求：

- 不改变 `feasibility = 0` 的淘汰结果；
- 不允许 runtime 项覆盖 I/O / schema / safety 违规；
- 修正范围必须有界，防止 runtime 项吞掉静态排序。

### 13.3 当前实现中的 runtime adjustment

在 `PlannerAgent._build_runtime_shadow_decision()` 中，当前实现从 `runtime_state_summary` 中读取：

- `p_success`
- `p_structural_failure`
- `recovery_margin`
- `expected_remaining_cost`
- `evidence_sufficiency`

再结合候选自身的：

- `overall`
- `confidence`
- `risk`
- `cost`
- `fallback_depth`
- `feasibility`

构造若干影响项：

- `evidence_effect`
- `evidence_sufficiency_effect`
- `risk_effect`
- `recovery_effect`
- `cost_effect`

然后求和得到 `delta`，最终得到：

- `static_score`
- `runtime_adjustment`
- `final_score`

如果运行时判断倾向于：

- `patch_local`
- `suffix_replan`
- `stop`

还会进一步给不同动作附加额外 bonus / penalty。

### 13.4 为什么要同时保留 `static_score`、`shadow_score`、`final_score`

这是为了审计和可解释性：

- `static_score`：静态层原始判断；
- `runtime_adjustment`：运行时修正量；
- `final_score`：实际排序依据；
- `shadow_score`：用于追踪 runtime rerank 的影子决策；
- `rerank_reason`：记录到底是哪些状态项和候选项导致了修正。

因此系统不是只输出一个总分，而是保留“为什么改分”的轨迹。

---

## 14. 动作选择：系统如何决定继续、修补、重规划或止损

设计文档把动作空间限制为：

- `continue`
- `patch_local`
- `suffix_replan`
- `stop`

并给出原则：

- `p_success` 尚可且故障局部化时，优先 `patch_local`
- `p_structural_failure` 高、`recovery_margin` 低时，优先 `suffix_replan`
- `p_success` 低、预算压力高、人工帮助价值低时，允许 `stop`

### 14.1 当前实现中的派生特征

在 `src/workflow/recovery.py` 中，动作选择器会先从主状态派生出：

- `budget_pressure`
- `local_patchability`
- `prefix_preservability`
- `intervention_value`
- `u_stop`

这些量正是设计文档中“不建议长期持久化，而应现场派生”的那些量。

它们的含义分别是：

- `budget_pressure`：剩余成本压力有多大；
- `local_patchability`：当前问题是否仍然局部可修；
- `prefix_preservability`：已完成前缀值不值得保留；
- `intervention_value`：现在让人介入到底有多大价值；
- `u_stop`：止损动作的效用是否已经足够高。

### 14.2 选择顺序

当前动作选择器 `select_workflow_action()` 的逻辑大致是：

1. 先看是否被 `Safety block` 硬阻断；
2. 再看是否有来自候选 rerank 的建议动作；
3. 如果没有明显失败信号，则继续；
4. 如果满足自动 stop 条件，则选择 `stop`；
5. 如果局部可修，优先 `patch_local`；
6. 如果结构失败压力高，选择 `suffix_replan`；
7. 否则继续。

这体现了设计文档强调的两个原则：

- 动作选择服务于恢复闭环，而不是替代恢复闭环；
- 硬约束优先于效用比较。

### 14.3 `stop` 为什么仍然要走 HITL

设计文档明确规定：

- 自动 stop 只有在非常严格的条件下才允许；
- 如果 `stop` 合理但不满足自动终止门槛，则要把它包装成 `terminal_stop` 候选，进入 `replan_confirm` 等待人工确认。

当前代码中，`build_terminal_stop_candidate()` 就是在做这件事。

这保证了：

- 系统可以提出止损建议；
- 但不会轻易把一个高价值科研任务在后台偷偷终止。

---

## 15. HITL gate：什么时候必须让人看

### 15.1 设计原则

候选生成与排序之后，如果满足以下任一条件，就进入 HITL：

1. 系统配置要求确认；
2. `risk` 超阈值；
3. `cost` 超阈值；
4. `SafetyAgent.action = block`；
5. 推荐动作是 `stop`，但不满足自动终止条件。

### 15.2 当前实现中的门控

当前实现中的 `PlannerAgent.evaluate_top_k_gate()` 主要检查：

- 是否强制确认；
- 是否高风险；
- 是否低置信度；
- 是否高成本但收益不足。

如果触发任一条件：

- 不会直接自动执行；
- 而是构造 `PendingAction`；
- 进入 `WAITING_*`；
- 等待 `Decision`。

### 15.3 为什么 HITL gate 很关键

这一步的意义不是“人不放心所以都让人看”，而是：

- 把高风险、高成本、低置信度的控制节点显式暴露出来；
- 让系统在自动化和人工判断之间做合理分工；
- 同时保留完整审计链。

这正是效用函数里 `HumanInterventionCost` 之所以是一等量的原因：

- 人工介入不是免费；
- 但它在某些边界情况下是必要且高价值的。

---

## 16. FSM、PendingAction、Snapshot：为什么算法必须和架构绑定

项目的核心算法并不是独立运行的小模块，而是被强绑定在 FSM / HITL / Snapshot 体系内。

### 16.1 为什么必须绑定状态机

因为 `patch`、`replan`、`stop` 不是普通返回值，它们会改变任务生命周期。

所以系统必须明确区分：

- 还在执行；
- 已经暂停等待人工确认；
- 正在补丁；
- 正在重规划；
- 已经总结完成；
- 已失败或取消。

### 16.2 PendingAction 的意义

`PendingAction` 统一表示“系统已经准备好候选方案，但需要人决定”的场景。

对应关系是：

- `WAITING_PLAN_CONFIRM -> plan_confirm`
- `WAITING_PATCH_CONFIRM -> patch_confirm`
- `WAITING_REPLAN_CONFIRM -> replan_confirm`

这让 HITL 不再是“人临时改一下变量”，而成为显式的可追踪控制对象。

### 16.3 Snapshot 的意义

进入任何 `WAITING_*` 前，都必须先写：

- 当前 plan / patch / replan 版本；
- 已完成步骤；
- 关键 artifacts；
- 当前 `runtime_state`；
- 当前 `PendingAction`

这样即使系统重启，也能恢复到一致的等待决策上下文。

### 16.4 当前实现中的关键模块

- `src/workflow/pending_action.py`
  - `build_pending_action()`
  - `enter_waiting_state()`

- `src/workflow/snapshots.py`
  - 将 `runtime_state` 和 `runtime_observation_summary` 注入快照 artifacts

- `src/workflow/decision_apply.py`
  - 应用 `Decision`
  - 更新 Plan / Patch / Replan
  - 驱动状态转移

这说明算法的控制动作最终都必须“落进”状态机与快照体系中，才能满足架构契约。

---

## 17. 当前代码中的关键实现路径

下面给出一个“从任务输入到恢复控制”的实现路径导览。

### 17.1 Planner 层

文件：`src/agents/planner.py`

关键职责：

- 构造 Plan / Patch / Replan Top-K 候选；
- 计算静态分数；
- 消费 `runtime_state_summary` 做 rerank；
- 产出 `final_score`、`shadow_action`、`rerank_reason`；
- 对候选进行 gate 决策；
- 在需要时创建 `PendingAction`。

关键入口：

- `plan_top_k()`
- `patch_top_k()`
- `replan_top_k()`
- `evaluate_top_k_gate()`

### 17.2 执行层

文件：

- `src/workflow/plan_runner.py`
- `src/workflow/patch_runner.py`

关键职责：

- 执行步骤；
- 捕获失败；
- 预估 `runtime_state_preview`；
- 触发 patch 或 replan 流；
- 在需要时进入 `WAITING_PATCH` / `WAITING_REPLAN`。

### 17.3 状态更新层

文件：

- `src/workflow/context.py`
- `src/workflow/belief_state.py`

关键职责：

- 汇集 `StepResult` / `SafetyResult`；
- 更新 `runtime_state`；
- 保证 belief-state 更新路径集中而可测试。

### 17.4 动作选择层

文件：`src/workflow/recovery.py`

关键职责：

- 从 `runtime_state_summary` 派生动作特征；
- 结合失败码、阶段、重试耗尽、安全阻断等信号；
- 选择 `continue / patch_local / suffix_replan / stop`；
- 构造 `terminal_stop` 候选。

### 17.5 HITL / Snapshot 层

文件：

- `src/workflow/pending_action.py`
- `src/workflow/snapshots.py`
- `src/workflow/decision_apply.py`

关键职责：

- 把“候选集等待确认”的场景结构化；
- 把运行时状态与等待态固化进快照；
- 保证重启后可恢复；
- 保证决策应用可追踪。

---

## 18. 质量门与目标打分：为什么算法还要关心这些领域指标

虽然项目的核心算法是“控制与规划算法”，但它必须消费领域指标，才能判断当前链值不值得继续。

### 18.1 质量门（S3）

质量门会检查：

- 序列是否存在；
- 长度是否在约束范围内；
- 字符是否合法；
- 结构文件是否存在；
- `pLDDT` 是否过阈值；
- 是否存在低复杂度组成或重复片段；

并输出：

- `pass_count`
- `fail_count`
- `pass_rate`
- `reject_code_counts`
- `pass_fail`

这一步是“硬门禁”，不是软打分。

### 18.2 目标打分（S5）

目标打分会把候选拆成多个维度，例如：

- `quality`
- `novelty`
- `stability`
- `function`
- `docking`

然后综合排序。

对核心算法来说，这些领域指标的重要性在于：

- 它们构成 `StepResult.outputs / metrics` 的一部分；
- 会反馈到 `evidence_sufficiency`、候选静态分、runtime rerank；
- 决定当前链是“证据充分地值得继续”，还是“只是形式上还能跑”。

---

## 19. 这个算法的必要性：为什么不是“过度设计”

如果系统只有：

- 一次性静态规划；
- 简单失败重试；
- 没有显式状态和恢复控制；

在低成本任务里也许够用。

但当前项目面对的是：

- 高代价步骤；
- 长链路；
- 中途可失败；
- 失败后恢复价值高度依赖前缀；
- 还要求审计、复现和 HITL。

在这种任务里，不做当前这套算法，会出现几个严重问题：

1. **高代价盲冲**
   - 明明证据不足，仍然进入昂贵步骤。

2. **局部问题升级成全局重跑**
   - 缺乏 patch / suffix replan 的细粒度恢复。

3. **恢复动作不可解释**
   - 说不清为什么这次 patch、下次 replan、再下次 stop。

4. **人工介入不可追踪**
   - 人改了什么、为什么改、对结果有何影响，无法审计。

5. **系统重启后上下文丢失**
   - WAITING 态和恢复决策断裂。

所以这套算法的必要性，不是来自“追求学术炫技”，而是来自：

**只有把规划、运行时状态、恢复控制、HITL、Snapshot 串起来，系统才真正适合高代价科研工作流。**

---

## 20. 当前实现相对理想设计的工程化取舍

为了帮助后续研究，这里明确指出当前实现不是最终形态，而是“第一版可解释、可复现、可回放”的工程实现。

### 20.1 当前已经做到的

- 将算法拆分为静态层和运行时层；
- 固定 5 维 Lite belief-state；
- 使用显式 `runtime_adjustment` 与 `final_score`；
- 将动作空间限制在 `continue / patch_local / suffix_replan / stop`；
- 把算法控制动作绑定到 FSM / HITL / Snapshot；
- 能通过日志、快照、候选元数据回放决策过程。

### 20.2 当前仍然是启发式近似的地方

- 静态评分公式中的权重与系数；
- belief-state 更新中的增减幅度；
- runtime rerank 中各影响项系数；
- 动作选择中的阈值和派生量公式；
- 高代价规则的默认划分。

这些量目前主要是工程启发式，而不是数据拟合得到的最优参数。

### 20.3 为什么先做成启发式仍然合理

因为项目当前阶段首先需要：

- 一套结构上正确的算法闭环；
- 可测试、可回放、可审计；
- 能稳定支撑论文中的机制分析；
- 能为后续参数调优和数据驱动校准提供基线。

也就是说，**先把“结构正确”做出来，再去做“参数最优”**，是这个项目目前非常合理的路线。

---

## 21. 阅读源码的建议顺序

如果你接下来准备真正读代码，建议顺序如下：

1. `src/models/contracts.py`
   - 先理解 `Plan / StepResult / RuntimeState / PendingAction`

2. `src/workflow/context.py`
   - 理解 `runtime_state` 是怎么接入上下文的

3. `src/workflow/belief_state.py`
   - 理解 5 维状态是怎么从观测中更新出来的

4. `src/agents/planner.py`
   - 理解静态评分、runtime rerank、Top-K、gate

5. `src/workflow/recovery.py`
   - 理解动作选择和 `terminal_stop`

6. `src/workflow/plan_runner.py` 与 `src/workflow/patch_runner.py`
   - 理解执行失败后如何进入 patch / replan

7. `src/workflow/pending_action.py`、`src/workflow/snapshots.py`、`src/workflow/decision_apply.py`
   - 理解算法如何真正落地为 WAITING、快照和决策应用

---

## 22. 本文档的结论

可以把当前项目的核心算法压缩成一句更完整的话：

**这是一个运行在显式 FSM 与 HITL 契约之内的、面向高代价蛋白质设计工作流的动态工具链规划与恢复控制算法。它先用静态评分挑出可执行且先验合理的候选链，再用 Lite belief-state 根据运行时观测持续修正候选价值，并在 `continue / patch_local / suffix_replan / stop` 之间做恢复感知决策，最终通过 PendingAction、Decision 与 TaskSnapshot 保证控制过程可审计、可恢复、可复现。**

如果只看 Planner，它像一个“会排序候选链”的模块；
如果只看 belief-state，它像一个“会更新状态”的模块；
如果只看 recovery，它像一个“会选动作”的模块。

但只有把它们和 FSM / HITL / Snapshot 一起看，才能真正理解这套算法的研究意义和工程必要性。

---

## 23. 下一份文档建议内容

下一份文档将聚焦参数层，建议至少回答下面这些问题：

1. 当前算法包含哪些参数；
2. 参数如何按层次分类；
3. 每类参数分别影响什么；
4. 哪些参数来自设计公式，哪些是实现启发式；
5. 当前默认值是怎么来的；
6. 后续应该如何做系统化调参与校准。

