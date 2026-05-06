# 核心算法理论深化与实现对照计划

> 日期：2026-05-05  
> 适用仓库：`thesis-project.dev`  
> 设计依据：`../thesis-project.design`  
> 目标：先从理论上得到一个更有深度、可写入毕设论文的方法原理，再把该原理映射到当前系统算法实现中。

---

## 1. 计划定位

本计划不是立即改代码的实现计划，而是面向毕设论文核心算法的理论深化计划。

当前系统已经具备一套可运行的算法骨架：

- 候选工具链生成；
- Top-K 候选排序；
- 静态多目标评分；
- Lite belief-state；
- runtime rerank；
- `continue / patch_local / suffix_replan / stop` 动作选择；
- HITL 决策与事件审计。

但当前理论表达仍偏工程启发式，主要问题是：

1. 核心算法的数学命题还不够集中；
2. 静态评分、运行时状态、动作选择之间的统一理论关系还不够清晰；
3. 现有公式多为启发式加权和，缺少更强的理论解释；
4. 蛋白质设计任务本身的目标函数、证据链和工作流控制之间还没有形成完整闭环；
5. 最新论文与当前算法之间尚未形成系统对照。

本计划的核心任务是把当前算法提升为一个可论文化的方法：

> **面向高代价蛋白质设计工作流的约束化、证据感知、恢复感知自适应工具链规划算法。**

可暂定名称：

> **CEBRA-WP: Constraint- and Evidence-aware Belief-guided Recovery-adaptive Workflow Planning**

名称后续可调整，重要的是方法内核要稳定。

---

## 2. 当前依据

### 2.1 设计侧 SSOT

设计目录位于：

- `../thesis-project.design/`

核心设计文档包括：

- `../thesis-project.design/docs/design/core-algorithm-spec.md`
- `../thesis-project.design/docs/design/runtime-adaptation-formalization.md`
- `../thesis-project.design/docs/design/active-tool-metadata-profile.md`
- `../thesis-project.design/docs/design/de-novo-workflow.md`
- `../thesis-project.design/docs/algorithm-and-llm/core-algorithm-define.md`
- `../thesis-project.design/docs/experiment/algorithm-group-paper-mapping.md`

可用索引工具：

- `.agents/skills/doc-slicer/SKILL.md`
- `.agents/skills/doc-slicer/scripts/docslice`

示例：

```bash
.agents/skills/doc-slicer/scripts/docslice \
  --sid algo.adaptive.optimization_objective \
  --repo-root ../thesis-project.design \
  --max-lines 120
```

### 2.2 设计侧已有核心命题

当前设计文档将算法定义为：

> 在高代价、长链路、可失败、可恢复的蛋白质设计工作流中，动态生成、评估、裁剪并修正工具链，使系统以更低成本获得更高任务成功率。

对应问题不是单纯 ToolKG 检索，而是：

- constraint-aware；
- budget-aware；
- risk-aware；
- recovery-aware；
- human-in-the-loop aware；
- partially observable runtime control。

### 2.3 当前代码侧关键入口

需要对照审查的代码路径：

- `src/agents/planner.py`
  - 静态评分、Top-K gate、runtime shadow decision、candidate scoring。
- `src/agents/candidate_generator/`
  - 候选去重、过滤、排序、多样性选择、默认推荐。
- `src/workflow/belief_state.py`
  - Lite belief-state v1 更新规则。
- `src/workflow/runtime_policy.py`
  - runtime policy 模式选择。
- `src/workflow/recovery.py`
  - 动作选择、恢复路径映射、terminal stop。
- `src/models/runtime_schemas.py`
  - Cost / Risk / Recovery / State / Observation / ActionUtility schema。
- `src/adapters/objective_ranker_adapter.py`
  - posterior objective scoring、目标分量、证据状态、warning。
- `src/kg/protein_tool_kg.json`
  - ToolKG 能力图。

---

## 3. 总体目标

最终需要得到三类产物。

### 3.1 理论产物

形成一个论文中可独立成章的方法原理，包括：

1. 问题定义；
2. 数学符号系统；
3. 优化目标；
4. 约束条件；
5. 状态估计；
6. 候选生成与裁剪；
7. 后验目标评分；
8. 动作效用与恢复决策；
9. 算法伪代码；
10. 复杂度分析；
11. 理论依据与相关工作对照。

### 3.2 设计产物

形成一份设计侧可追踪的深化文档，建议新增到设计仓库或同步到当前仓库：

- `docs/algorithm-and-llm/core-algorithm-theory-v2.md`

其中应明确：

- 当前 v1 启发式公式哪些保留；
- 哪些公式需要重写；
- 哪些字段需要补充；
- 哪些代码路径应对应哪条数学公式。

### 3.3 实现产物

在理论确认后，再进入代码实现，目标是让系统真正体现该核心算法，而不是只在论文里描述。

实现侧目标包括：

- 统一 score / utility / runtime adjustment 的 schema；
- 让 belief-state 更新从“手工加减分”升级为“可解释观测映射”；
- 让 objective scoring 成为后验证据链核心；
- 让 action selector 显式使用 ActionUtility；
- 让日志中能追踪每个数学项的来源。

---

## 4. 核心算法理论深化方向

### 4.1 方法主线

建议将核心算法统一表述为：

> 在部分可观测、高代价、可恢复的蛋白质设计工作流中，系统维护一个轻量 belief-state，并在每个决策点对候选工具链、局部修补和后缀重规划方案进行约束化多目标效用优化，从而在成功率、成本、风险、恢复复杂度与人工介入成本之间取得可解释折中。

也就是说，算法主线不是“LLM 生成 workflow”，而是：

```text
Task + Constraints + ToolKG + Runtime Observations
        ↓
Candidate Workflow Set
        ↓
Feasibility Filter
        ↓
Static Multi-objective Utility
        ↓
Lite Belief-State Update
        ↓
Runtime Adjustment / Posterior Utility
        ↓
Action Utility over {continue, patch_local, suffix_replan, stop}
        ↓
HITL or Automatic Transition
```

### 4.2 数学对象

建议统一符号如下。

#### 任务与约束

- 任务目标：`g`
- 约束集合：`C`
- 工具能力图：`K = (V, E)`
- 当前执行上下文：`h_t`
- 当前观测：`o_t`
- 当前 belief-state：`x_t`

#### 候选集合

在时刻 `t`，系统生成候选集合：

```text
Π_t = Π_t^plan ∪ Π_t^patch ∪ Π_t^replan ∪ Π_t^stop
```

其中：

- `π ∈ Π_t^plan`：初始计划候选；
- `π ∈ Π_t^patch`：局部修补候选；
- `π ∈ Π_t^replan`：后缀重规划候选；
- `π_stop`：终止型重规划候选。

#### 可执行性硬约束

定义：

```text
F(π, C, K, h_t) ∈ {0, 1}
```

只有满足：

```text
F(π, C, K, h_t) = 1
```

的候选才进入效用排序。

硬约束包括：

- 工具存在；
- I/O 闭包；
- 参数合法；
- schema 合法；
- 资源约束；
- 安全约束；
- FSM / HITL 边界约束。

### 4.3 统一效用函数

当前设计已有候选效用：

```text
Utility(π, x_t)
= α · Feasibility
+ β · GoalFit
- γ · Cost
- δ · Risk
- η · RecoveryComplexity
- ζ · HumanInterventionCost
```

建议深化为硬约束 + 软效用的两阶段形式。

#### 第一阶段：硬约束过滤

```text
Π_t^valid = {π ∈ Π_t | F(π, C, K, h_t) = 1}
```

#### 第二阶段：软效用优化

```text
π_t^* = argmax_{π ∈ Π_t^valid} U(π, x_t, o_t, C)
```

其中：

```text
U(π, x_t, o_t, C)
= w_g G(π, g, C)
+ w_s S(π, x_t)
+ w_e E(π, o_t)
- w_c Cst(π, h_t)
- w_r Rsk(π, x_t, o_t)
- w_ρ Rec(π, h_t)
- w_h H(π, h_t)
```

解释：

- `G`：目标对齐度；
- `S`：当前 belief-state 下的成功潜力；
- `E`：已有证据支持度；
- `Cst`：剩余成本暴露；
- `Rsk`：执行和结构风险；
- `Rec`：恢复复杂度；
- `H`：人工介入成本。

这个形式比原来的加权和更适合论文，因为它明确区分：

- 任务目标；
- 运行时状态；
- 后验证据；
- 成本；
- 风险；
- 恢复性；
- HITL。

### 4.4 Lite belief-state 理论化

当前设计中的状态向量为：

```text
x_t = [p_success,
       p_structural_failure,
       recovery_margin,
       expected_remaining_cost,
       evidence_sufficiency]
```

理论深化方向：

1. 将其明确为 full belief-state 的低维充分近似，而非真实环境状态；
2. 将更新规则从“加减分”解释为“观测驱动的有界贝叶斯式更新近似”；
3. 对概率项使用 logit-space update，以避免线性加减导致边界附近不稳定；
4. 对非概率项使用指数滑动更新或 convex update，保证可解释与可复现。

建议形式：

```text
x_t = Φ(x_{t-1}, o_t, a_{t-1}, π_{t-1})
```

其中 `Φ` 是可审计的状态更新器。

对概率项：

```text
logit(p_success_t)
= clip(logit(p_success_{t-1})
       + λ_s · success_signal_t
       - λ_f · failure_signal_t
       - λ_b · budget_penalty_t,
       l_min, l_max)
```

```text
p_success_t = sigmoid(logit(p_success_t))
```

这比当前代码中的线性增减更有理论说服力。

### 4.5 后验目标评分理论化

当前 `objective_ranker_adapter.py` 已经将候选分解为：

- `generic_objective`
- `stability`
- `function`
- `novelty`
- `structure_quality`

并记录：

- direct evidence；
- proxy evidence；
- degraded evidence；
- warnings；
- evidence sufficiency。

建议将其提升为后验证据评分模型：

```text
Q(π | D_t)
= Σ_i ω_i · q_i(π | D_t)
```

其中：

- `D_t` 是当前已获得的执行证据；
- `q_i` 是不同目标分量；
- `ω_i` 由任务目标和约束决定；
- 每个 `q_i` 必须携带证据等级 `e_i ∈ {direct, proxy, degraded}`。

进一步加入证据可信度折扣：

```text
Q'(π | D_t)
= Σ_i ω_i · κ(e_i) · q_i(π | D_t)
```

其中：

```text
κ(direct) > κ(proxy) > κ(degraded)
```

这能把当前代码里的 warning / evidence_status 转化为论文中的数学机制。

### 4.6 Action Utility 理论化

当前动作空间：

```text
A = {continue, patch_local, suffix_replan, stop}
```

建议把动作选择写成：

```text
a_t^* = argmax_{a ∈ A_t^{valid}} U_A(a | x_t, h_t, Π_t)
```

其中 `A_t^{valid}` 由 FSM、Safety、阶段、失败上下文决定。

设计侧已有公式：

```text
U_continue
= 0.38s + 0.14e + 0.12r - 0.22f - 0.14b
```

```text
U_patch_local
= 0.20s + 0.24r + 0.18 local_patchability
  + 0.12 evidence_reusability - 0.14f - 0.12b
```

```text
U_suffix_replan
= 0.18(1-s) + 0.20f + 0.16(1-r)
  + 0.18 prefix_preservability + 0.14 budget_relief
  + 0.14 goal_realignment
```

```text
U_stop
= 0.32(1-s) + 0.24b + 0.18(1-r)
  + 0.16 safety_terminality + 0.10(1-intervention_value)
```

需要补强的是：

1. 每个派生量的定义；
2. 每个系数的来源；
3. 硬约束优先级；
4. 与 `retry -> patch -> replan` 的恢复顺序兼容性；
5. 与 HITL 的关系：高 utility 不一定自动执行，可能进入人工确认。

---

## 5. 最新论文与理论背景调研计划

### 5.1 文献分组

文献不应只按“蛋白质设计”检索，而应按算法组成拆分。

#### A. 部分可观测规划与 belief-state

目标：支撑 Lite belief-state 的必要性。

已有设计侧参考：

- Kaelbling, Littman, Cassandra, 1998, *Planning and Acting in Partially Observable Stochastic Domains*。
- Shani, 2024, *Heuristics for Partially Observable Stochastic Contingent Planning*。

需要补充：

- POMDP 近似规划；
- belief-state compression；
- heuristic contingent planning；
- online replanning。

#### B. Budgeted / risk-aware decision making

目标：支撑成本、预算、风险作为一等决策变量。

已有设计侧参考：

- Carrara et al., 2019, *Budgeted Reinforcement Learning in Continuous State Space*。

需要补充：

- constrained MDP；
- risk-sensitive planning；
- budget-aware workflow scheduling；
- scientific workflow reliability。

#### C. Agent workflow planning 与 tool use

目标：支撑“工具调用本身是决策对象”。

已有设计侧参考：

- Toolformer, 2023；
- Reflexion, 2023；
- Tree of Thoughts, 2023；
- OSWorld, 2024。

需要补充：

- LLM agent planning；
- tool-augmented reasoning；
- human-in-the-loop agent control；
- workflow automation benchmark。

#### D. 蛋白质设计与后验评估

目标：支撑目标函数中的结构质量、稳定性、功能、novelty 等分量。

需要覆盖：

- ProteinMPNN / inverse folding；
- ESMFold / structure prediction confidence；
- RFdiffusion / generative protein design；
- protein language models, e.g. ProGen / ESM；
- multi-objective protein design；
- stability / function / novelty scoring。

#### E. 科学工作流与 provenance

目标：支撑审计、恢复、快照、事件链。

已有设计侧参考：

- Simmhan et al., 2009, *Reliable Data Pipelines Using Scientific Workflows*。

需要补充：

- scientific workflow systems；
- provenance tracking；
- failure recovery；
- reproducibility in computational biology pipelines。

### 5.2 检索方法

使用两类检索。

#### arXiv

```bash
curl -s "https://export.arxiv.org/api/query?search_query=all:protein+design+inverse+folding&max_results=10&sortBy=submittedDate&sortOrder=descending"
```

#### Semantic Scholar

```bash
curl -s "https://api.semanticscholar.org/graph/v1/paper/search?query=protein%20design%20multi%20objective%20optimization&limit=10&fields=title,authors,year,citationCount,externalIds,abstract"
```

### 5.3 文献筛选标准

每篇论文只看是否能支撑以下任一问题：

1. 为什么需要候选集而不是单路径？
2. 为什么需要 belief-state？
3. 为什么要预算/风险/恢复感知？
4. 为什么 protein design 需要多目标后验评分？
5. 为什么需要 HITL？
6. 有没有可迁移到本系统的数学形式？

不满足这些问题的论文即使很新，也不应进入主线。

---

## 6. 当前代码审查重点

### 6.1 `src/agents/planner.py`

审查问题：

- `_DEFAULT_SCORE_WEIGHTS` 是否与理论效用函数一致；
- `_score_payload` 是否区分硬约束与软效用；
- runtime shadow decision 是否只是调分，还是已经可解释地对应公式；
- candidate gate 是否能被写成数学阈值策略；
- Plan / Patch / Replan 的评分是否共用统一 schema。

预计问题：

- 评分项已经较完整，但理论命名和字段边界需要统一；
- 部分公式可能分散在 helper 中，不利于论文和审计；
- runtime adjustment 的每个分量需要更明确 source fields。

### 6.2 `src/workflow/belief_state.py`

审查问题：

- 当前更新是否仍是线性加减；
- 是否能改写为 logit-space / convex update；
- 每次 update 是否能产生 delta explanation；
- `observation_summary` 是否足以追溯每个状态变化来源。

预计问题：

- v1 规则可运行，但理论深度不足；
- 需要升级为 v2：状态值 + delta + reason + source_fields。

### 6.3 `src/models/runtime_schemas.py`

审查问题：

- Cost / Risk / Recovery / State / Observation / ActionUtility 是否已经完整；
- 是否每个 schema 都有数学公式对应；
- 是否可被 Planner、belief_state、recovery 共同复用。

预计问题：

- schema 已具备雏形；
- 需要检查是否只是数据模型，而不是算法实际使用的统一接口。

### 6.4 `src/workflow/recovery.py`

审查问题：

- `select_workflow_action` 是否真正基于 ActionUtility；
- 硬约束优先级是否清晰；
- `stop` 是否严格作为 terminal replan，而不是异常失败；
- recovery action 是否和 `retry -> patch -> replan` 顺序一致。

### 6.5 `src/adapters/objective_ranker_adapter.py`

审查问题：

- posterior score 是否可写成多目标后验评分公式；
- direct/proxy/degraded evidence 是否进入最终分数，而不只是 warning；
- 是否需要引入 evidence discount；
- objective weights 是否应由任务类型、约束、实验模式共同决定。

预计问题：

- 当前已经具备很好基础；
- 最关键的深化点是把 evidence quality 显式纳入 score，而不只是解释字段。

---

## 7. 分阶段执行计划

### 阶段 0：建立审查索引

目标：建立设计文档与代码路径的对照表。

任务：

1. 使用 `docslice` 抽取以下 SID：
   - `algo.adaptive.problem_formulation`
   - `algo.adaptive.optimization_objective`
   - `planner.algorithm.candidate_scoring`
   - `planner.algorithm.runtime_state_estimation`
   - `planner.algorithm.runtime_adjustment_formula`
   - `planner.algorithm.runtime_action_selection`
   - `algo.schema.action_utility`
2. 建立 SID → 代码路径 → 当前实现状态的表。
3. 标注每个公式是否已实现、部分实现、未实现。

产出：

- `docs/algorithm-and-llm/core-algorithm-design-code-traceability.md`

验收：

- 每个关键 SID 至少对应一个代码路径；
- 每个关键代码路径至少对应一个设计公式或设计约束。

### 阶段 1：理论主线重写

目标：把算法从工程启发式提升为统一数学模型。

任务：

1. 定义统一符号系统；
2. 定义硬约束过滤；
3. 定义候选集合；
4. 定义多目标效用函数；
5. 定义 Lite belief-state；
6. 定义后验评分；
7. 定义 ActionUtility；
8. 写算法伪代码。

产出：

- `docs/algorithm-and-llm/core-algorithm-theory-v2.md`

验收：

- 能直接作为毕设论文“核心算法设计”章节初稿；
- 包含完整公式、变量说明和算法伪代码；
- 不依赖代码细节才能读懂。

### 阶段 2：文献对照与理论依据补强

目标：让每个理论组件都有合理依据。

任务：

1. 检索并筛选 20–30 篇候选论文；
2. 精读 8–12 篇核心论文；
3. 按组件建立映射：
   - belief-state；
   - budget/risk-aware planning；
   - tool-use agent；
   - HITL；
   - protein design objective scoring；
   - scientific workflow recovery。
4. 写出“本系统不是简单照搬 POMDP/RL，而是可审计轻量近似”的论证。

产出：

- `docs/algorithm-and-llm/core-algorithm-literature-map.md`

验收：

- 每个算法模块至少有 1–2 篇论文支撑；
- 明确哪些论文只是背景，哪些直接影响公式设计；
- 明确哪些高级方法不采用，以及原因。

### 阶段 3：代码差距审查

目标：评估当前实现与理论 v2 的差距。

任务：

1. 审查 `planner.py` 的静态评分和 runtime adjustment；
2. 审查 `belief_state.py` 的状态更新；
3. 审查 `runtime_schemas.py` 的 schema 使用情况；
4. 审查 `recovery.py` 的 action selection；
5. 审查 `objective_ranker_adapter.py` 的 posterior scoring；
6. 输出缺口分级：P0 / P1 / P2。

产出：

- `docs/algorithm-and-llm/core-algorithm-code-gap-review.md`

验收：

- 每个差距都有代码路径、理论依据、建议改法；
- 不直接改代码；
- 给出最小实现路线。

### 阶段 4：实现方案设计

目标：在理论确认后，写可交给实现代理的具体计划。

任务：

1. 设计 `belief_state_v2` 更新器；
2. 设计 `ActionUtility` 统一计算模块；
3. 设计 `PosteriorObjectiveScore` 或 evidence discount；
4. 设计日志和解释字段；
5. 设计测试和实验指标。

产出：

- `docs/algorithm-and-llm/core-algorithm-v2-implementation-plan.md`

验收：

- 每个任务有文件路径；
- 每个任务有测试策略；
- 每个公式能映射到代码函数；
- 可以交给 Codex 实现。

### 阶段 5：实现与验证

此阶段必须在用户确认方案后再开始。

实现方向初步包括：

1. `belief_state.py`
   - 从线性增减升级为 logit-space + convex update；
   - 输出 delta trace。
2. `runtime_schemas.py`
   - 增强 `ActionUtility` 与状态字段解释能力。
3. `recovery.py`
   - 使用统一 ActionUtility 计算动作，而不是散落规则。
4. `objective_ranker_adapter.py`
   - 引入 evidence discount；
   - 输出 posterior score trace。
5. `planner.py`
   - 对齐 static score、runtime adjustment 和 final score 的字段定义。

验证：

- 单元测试；
- 集成测试；
- 固定任务 replay；
- static / dynamic observation-only / lite belief-state / theory-v2 横向比较。

---

## 8. 论文叙事建议

毕设论文中建议把核心算法章节组织为：

1. 问题背景：蛋白质设计工作流的高代价与不确定性；
2. 问题定义：约束化工具链规划；
3. 候选生成：Plan / Patch / Replan；
4. 可执行性过滤：硬约束；
5. 多目标效用：目标、成本、风险、恢复性；
6. Lite belief-state：部分可观测运行时控制；
7. 后验目标评分：结构质量、稳定性、功能、novelty；
8. 动作选择：continue / patch / replan / stop；
9. 算法伪代码；
10. 实现映射；
11. 实验与消融。

核心论点：

> 本系统的核心贡献不是提出新的蛋白质生成模型，而是提出并实现了一种面向高代价蛋白质设计工作流的自适应工具链规划与恢复控制算法，使多个异构模型和评估工具能够在可解释、可恢复、可审计的框架下协同工作。

这个定位比“我做了一个调用多个模型的系统”更有算法深度。

---

## 9. 初步风险与取舍

### 9.1 不建议做 full POMDP / full RL

原因：

- 毕设周期不适合；
- 训练数据不足；
- 工程成本过高；
- 可解释性和审计性会下降；
- 当前系统更需要稳定可复现的规则化控制。

正确做法是：

> 用 POMDP / budgeted decision making 的理论解释 Lite belief-state，而不是真的实现完整 POMDP 求解器。

### 9.2 不建议把核心算法变成 LLM prompt

LLM 可以辅助候选生成，但核心算法必须保持：

- 显式输入；
- 显式候选；
- 显式公式；
- 显式约束；
- 显式审计。

否则论文中的算法贡献会变弱。

### 9.3 不建议只堆 protein design 论文

蛋白质设计论文支撑目标函数和工具选择，但无法单独支撑“工作流级自适应控制”。

文献必须同时覆盖：

- 蛋白质设计；
- planning / belief-state；
- budget / risk；
- tool-use agents；
- scientific workflow recovery。

---

## 10. 下一步立即行动

建议下一步按以下顺序执行：

1. 产出 `core-algorithm-design-code-traceability.md`；
2. 产出 `core-algorithm-theory-v2.md` 初稿；
3. 做文献检索与 `core-algorithm-literature-map.md`；
4. 做代码差距审查 `core-algorithm-code-gap-review.md`；
5. 用户确认理论与方案后，再写实现计划。

当前不会直接改代码。

---

## 11. 成功标准

本计划完成后，应能回答以下问题：

1. 这个系统的核心算法到底是什么？
2. 它解决的是蛋白质设计中的哪个工作流级问题？
3. 为什么需要 belief-state？
4. 为什么不是简单 ToolKG 检索或 LLM 规划？
5. 目标函数如何定义？
6. 每个数学项如何从代码和日志中得到？
7. 最新论文如何支撑这些设计？
8. 代码实现与理论还有哪些差距？
9. 后续最小改动如何让系统更贴合理论？

只有这些问题能被清楚回答，核心算法才足以支撑毕设论文。
