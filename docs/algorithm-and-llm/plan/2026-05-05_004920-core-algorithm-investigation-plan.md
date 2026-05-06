# 核心算法理论深化调查计划

> 创建时间：2026-05-05 00:49:20  
> 计划类型：调查 / 审查 / 理论深化，不包含代码实现  
> 上游依据：`docs/algorithm-and-llm/2026-05-05-core-algorithm-theory-deepening-plan.md`  
> 目标目录：`docs/algorithm-and-llm/plan/`

---

## 1. Goal

本调查的目标是把当前“面向高代价蛋白质设计工作流的自适应工具链规划算法”从工程启发式提升为可写入毕设论文的核心数学方法，并为后续实现提供精确对照。

最终要回答：

1. 当前系统的核心算法到底是什么？
2. 当前设计文档中的数学公式、状态变量、效用函数在代码中分别落在哪里？
3. 哪些部分已经实现，哪些只是设计概念，哪些实现与理论不一致？
4. 如何把现有启发式统一为一个更有理论深度的数学原理？
5. 哪些最新论文能支撑该理论，哪些论文不适合硬套？
6. 后续若实现算法 v2，应优先改哪些文件、以什么验收标准验证？

本阶段不改代码，只产出调查文档和可执行的后续方案。

---

## 2. Current Context / Assumptions

### 2.1 当前仓库

当前代码仓库：

```text
/home/yurikon/Documents/thesis/thesis-project.dev
```

当前设计仓库：

```text
../thesis-project.design
```

### 2.2 已有计划文档

上游理论深化计划已写入：

```text
docs/algorithm-and-llm/2026-05-05-core-algorithm-theory-deepening-plan.md
```

该文档提出暂定方法名：

```text
CEBRA-WP: Constraint- and Evidence-aware Belief-guided Recovery-adaptive Workflow Planning
```

### 2.3 设计侧关键文档

需要调查的设计文档：

```text
../thesis-project.design/docs/design/core-algorithm-spec.md
../thesis-project.design/docs/design/runtime-adaptation-formalization.md
../thesis-project.design/docs/design/active-tool-metadata-profile.md
../thesis-project.design/docs/design/de-novo-workflow.md
../thesis-project.design/docs/algorithm-and-llm/core-algorithm-define.md
../thesis-project.design/docs/experiment/algorithm-group-paper-mapping.md
```

### 2.4 可用设计索引工具

本仓库已有 doc-slicer：

```text
.agents/skills/doc-slicer/SKILL.md
.agents/skills/doc-slicer/scripts/docslice
```

典型命令：

```bash
.agents/skills/doc-slicer/scripts/docslice \
  --sid algo.adaptive.optimization_objective \
  --repo-root ../thesis-project.design \
  --max-lines 120
```

### 2.5 当前代码侧关键路径

本调查重点对照以下代码：

```text
src/agents/planner.py
src/agents/candidate_generator/
src/workflow/belief_state.py
src/workflow/runtime_policy.py
src/workflow/recovery.py
src/models/runtime_schemas.py
src/adapters/objective_ranker_adapter.py
src/kg/protein_tool_kg.json
```

---

## 3. Investigation Deliverables

本调查阶段建议产出 4 份文档。

### D1. 设计-代码可追踪性矩阵

路径：

```text
docs/algorithm-and-llm/core-algorithm-design-code-traceability.md
```

目的：

- 将设计 SID、公式、字段、代码路径逐项对应；
- 标注实现状态：`implemented` / `partial` / `missing` / `drifted`；
- 为后续实现提供定位依据。

### D2. 理论 v2 初稿

路径：

```text
docs/algorithm-and-llm/core-algorithm-theory-v2.md
```

目的：

- 将当前算法写成可用于论文的方法章节；
- 补齐统一符号、目标函数、状态更新、动作效用、后验评分、伪代码；
- 明确与现有 v1 设计的关系。

### D3. 文献映射表

路径：

```text
docs/algorithm-and-llm/core-algorithm-literature-map.md
```

目的：

- 将相关论文映射到算法组件；
- 明确每篇论文支撑的理论点；
- 明确不采用 full POMDP / full RL / pure LLM planner 的原因。

### D4. 代码差距审查报告

路径：

```text
docs/algorithm-and-llm/core-algorithm-code-gap-review.md
```

目的：

- 基于 D1-D3 审查当前代码与理论 v2 的差距；
- 给出 P0/P1/P2 改进项；
- 形成后续实现计划的输入。

---

## 4. Proposed Approach

本调查采用“四线并行、最后合流”的方法。

### 4.1 设计线

目标：确认设计侧真正定义了什么。

核心动作：

- 用 doc-slicer 按 SID 抽取算法定义；
- 只以设计 SSOT 为准，不依赖记忆；
- 将每条公式和约束拆成可追踪条目。

### 4.2 代码线

目标：确认当前实现到底做了什么。

核心动作：

- 只读审查关键代码；
- 提取评分、状态更新、动作选择、objective scoring 的实际公式；
- 标注代码中的隐式常量、阈值、规则来源。

### 4.3 文献线

目标：确认理论深化可站住脚。

核心动作：

- 分主题检索论文；
- 不追求堆数量，只找能支撑算法组件的论文；
- 对每篇论文标注“可用理论点”和“不适用边界”。

### 4.4 论文表达线

目标：把算法变成毕设中可以写清楚的数学方法。

核心动作：

- 统一符号系统；
- 将工程规则改写成硬约束 + 软效用 + belief-state update；
- 形成算法伪代码和实现映射。

---

## 5. Step-by-step Plan

### Step 1. 抽取设计侧核心 SID

目标：拿到算法设计的单一真源片段。

建议命令：

```bash
.agents/skills/doc-slicer/scripts/docslice \
  --sid algo.adaptive.problem_formulation \
  --repo-root ../thesis-project.design \
  --max-lines 160

.agents/skills/doc-slicer/scripts/docslice \
  --sid algo.adaptive.optimization_objective \
  --repo-root ../thesis-project.design \
  --max-lines 160

.agents/skills/doc-slicer/scripts/docslice \
  --sid planner.algorithm.candidate_scoring \
  --repo-root ../thesis-project.design \
  --max-lines 160

.agents/skills/doc-slicer/scripts/docslice \
  --sid planner.algorithm.runtime_state_estimation \
  --repo-root ../thesis-project.design \
  --max-lines 160

.agents/skills/doc-slicer/scripts/docslice \
  --sid planner.algorithm.runtime_adjustment_formula \
  --repo-root ../thesis-project.design \
  --max-lines 200

.agents/skills/doc-slicer/scripts/docslice \
  --sid planner.algorithm.runtime_action_selection \
  --repo-root ../thesis-project.design \
  --max-lines 200

.agents/skills/doc-slicer/scripts/docslice \
  --sid algo.schema.action_utility \
  --repo-root ../thesis-project.design \
  --max-lines 200
```

输出整理到 D1。

验收：

- 每个 SID 均有原文引用；
- 每条公式被拆成字段级条目；
- 明确设计侧要求是否属于硬约束、评分项、状态项、动作项或审计项。

---

### Step 2. 建立设计-代码映射矩阵

目标：把设计项映射到代码路径。

初始映射：

| 设计对象 | 代码路径 | 调查重点 |
|---|---|---|
| CandidateSet / Top-K | `src/agents/planner.py`, `src/agents/candidate_generator/` | 候选生成、过滤、排序、多样性选择 |
| static scoring | `src/agents/planner.py` | score weights、score_breakdown、overall |
| Lite belief-state | `src/workflow/belief_state.py` | 状态变量、更新规则、观测来源 |
| runtime policy | `src/workflow/runtime_policy.py` | policy mode 与 ablation 模式 |
| runtime rerank | `src/agents/planner.py`, `src/agents/candidate_generator/` | runtime_adjustment、final_score |
| ActionUtility | `src/models/runtime_schemas.py`, `src/workflow/recovery.py` | 动作效用是否实际驱动 selector |
| objective posterior scoring | `src/adapters/objective_ranker_adapter.py` | 多目标分量、证据等级、warning、score trace |
| ToolKG constraints | `src/kg/protein_tool_kg.json` | capability、I/O、cost/risk prior |

输出到：

```text
docs/algorithm-and-llm/core-algorithm-design-code-traceability.md
```

验收：

- 每个关键设计 SID 至少有一个代码路径；
- 每个关键代码路径至少能追溯到一个设计对象；
- 明确 `implemented / partial / missing / drifted`。

---

### Step 3. 审查静态评分与候选生成

目标：确认当前 static scoring 是否能支撑统一效用函数。

调查文件：

```text
src/agents/planner.py
src/agents/candidate_generator/generator.py
src/agents/candidate_generator/builder.py
src/agents/candidate_generator/models.py
src/agents/candidate_generator/filters.py
```

问题清单：

1. 候选集合 `Π_t` 的生成来源有哪些？
2. Plan / Patch / Replan 是否共用统一 Candidate schema？
3. 硬约束过滤是否发生在排序前？
4. 当前 `score_breakdown` 是否包含：
   - feasibility
   - objective
   - risk
   - cost
   - recovery_complexity
   - confidence
   - tool_readiness
   - tool_coverage
5. `overall` 是否是明确公式，而不是散落逻辑？
6. Top-K 的 diversity selection 是否有可解释规则？
7. default recommendation 的理由是否可追踪？

输出到 D1 和 D4。

---

### Step 4. 审查 Lite belief-state

目标：确认当前状态更新是否需要理论 v2 改造。

调查文件：

```text
src/workflow/belief_state.py
src/models/contracts.py
src/models/runtime_schemas.py
```

问题清单：

1. 当前状态向量是否为：

```text
x_t = [p_success, p_structural_failure, recovery_margin, expected_remaining_cost, evidence_sufficiency]
```

2. 当前初始化是否来自 static score / risk / recovery complexity / cost prior？
3. 当前更新是否为线性加减分？
4. 是否已使用 logit-space update？
5. 每个状态变化是否有：
   - delta
   - reason
   - source_fields
   - observation refs
6. `observation_summary` 是否足以支持论文案例分析？
7. 是否可以从 `StepResult` / `SafetyResult` / failure_context 稳定复现？

预期结论：

- 当前 v1 可运行；
- 但理论深度不足；
- v2 应将概率项改为 logit update，将非概率项改为 convex update，并输出 delta trace。

输出到 D4。

---

### Step 5. 审查 runtime rerank 与 final score

目标：确认 runtime adjustment 是否对应设计公式。

调查文件：

```text
src/agents/planner.py
src/agents/candidate_generator/builder.py
src/agents/candidate_generator/generator.py
```

设计公式：

```text
final_score = clip(static_score + runtime_adjustment, 0, 1)
```

调查问题：

1. `static_score` 从哪里来？
2. `runtime_adjustment` 从哪里来？
3. `runtime_adjustment_breakdown` 是否记录：
   - base_runtime_term
   - plan_term / patch_term / replan_term
   - budget_pressure
   - p_success
   - p_structural_failure
   - recovery_margin
   - evidence_sufficiency
4. runtime adjustment 是否只作用于可执行候选？
5. runtime adjustment 是否有上下界？
6. final_score 是否进入 Top-K 排序？
7. rerank reason 是否能被 UI / EventLog /论文案例使用？

输出到 D1 和 D4。

---

### Step 6. 审查 ActionUtility 与 recovery selector

目标：确认动作选择是否已有统一数学基础。

调查文件：

```text
src/models/runtime_schemas.py
src/workflow/recovery.py
src/workflow/patch_runner.py
src/workflow/plan_runner.py
```

设计动作空间：

```text
A = {continue, patch_local, suffix_replan, stop}
```

调查问题：

1. 当前是否显式计算：
   - `U_continue`
   - `U_patch_local`
   - `U_suffix_replan`
   - `U_stop`
2. `select_workflow_action` 是否使用 ActionUtility，还是使用分散规则？
3. 硬约束优先级是否覆盖效用比较？
4. Safety block、retry exhausted、budget pressure、evidence insufficiency 如何影响动作？
5. `stop` 是否始终作为 terminal replan 语义，而不是普通失败？
6. 是否保留 `retry -> patch -> replan` 的恢复顺序？

输出到 D4。

---

### Step 7. 审查 posterior objective scoring

目标：把 objective scoring 变成理论 v2 的后验证据核心。

调查文件：

```text
src/adapters/objective_ranker_adapter.py
src/adapters/tool_schema_utils.py
src/models/contracts.py
```

当前分量：

```text
generic_objective
stability
function
novelty
structure_quality
```

调查问题：

1. 当前 posterior score 是否为：

```text
Q(π | D_t) = Σ_i ω_i · q_i(π | D_t)
```

2. direct / proxy / degraded evidence 是否只用于 warning，还是进入最终分数？
3. 是否需要 evidence discount：

```text
Q'(π | D_t) = Σ_i ω_i · κ(e_i) · q_i(π | D_t)
```

4. `κ(direct) > κ(proxy) > κ(degraded)` 是否适合当前系统？
5. objective weights 是否根据 task objective 自动调整？
6. warnings 是否会降低 evidence_sufficiency？
7. 该 adapter 输出是否能回流 belief-state？

输出到 D2 和 D4。

---

### Step 8. 文献检索与筛选

目标：为理论 v2 建立可靠论文依据。

文献分组：

1. 部分可观测规划 / belief-state；
2. budgeted / risk-aware decision making；
3. LLM tool-use / agent workflow planning；
4. HITL / human-centered agent control；
5. protein design / inverse folding / structure prediction / objective scoring；
6. scientific workflow / provenance / recovery。

建议检索关键词：

```text
POMDP belief state heuristic contingent planning
budgeted reinforcement learning constrained MDP risk-aware planning
LLM agents tool use workflow planning human in the loop
protein design inverse folding multi objective optimization
protein design objective scoring stability novelty structure quality
scientific workflow recovery provenance reliable pipelines
```

每篇论文记录字段：

| 字段 | 说明 |
|---|---|
| title | 论文标题 |
| year | 年份 |
| venue/source | 会议、期刊、arXiv 等 |
| link | DOI / arXiv / Semantic Scholar |
| component | 支撑哪个算法组件 |
| usable idea | 可采用的理论点 |
| limitation | 不适合直接采用的地方 |
| citation role | 背景 / 方法依据 / 对比 / 不采用说明 |

输出到：

```text
docs/algorithm-and-llm/core-algorithm-literature-map.md
```

验收：

- 候选论文 20–30 篇；
- 核心精读 8–12 篇；
- 每个算法模块至少有 1–2 篇支撑；
- 明确 full POMDP / full RL / pure LLM planner 不采用的理由。

---

### Step 9. 写理论 v2 初稿

目标：形成论文方法章节雏形。

目标路径：

```text
docs/algorithm-and-llm/core-algorithm-theory-v2.md
```

建议结构：

1. 核心命题；
2. 问题定义；
3. 符号系统；
4. 候选集合；
5. 硬约束过滤；
6. 静态多目标效用；
7. Lite belief-state；
8. 观测映射与状态更新；
9. 后验目标评分；
10. runtime adjustment；
11. action utility；
12. HITL gate；
13. 算法伪代码；
14. 复杂度分析；
15. 与现有系统实现映射；
16. 理论边界与取舍。

关键公式至少包括：

```text
Π_t = Π_t^plan ∪ Π_t^patch ∪ Π_t^replan ∪ Π_t^stop
```

```text
Π_t^valid = {π ∈ Π_t | F(π, C, K, h_t) = 1}
```

```text
π_t^* = argmax_{π ∈ Π_t^valid} U(π, x_t, o_t, C)
```

```text
x_t = Φ(x_{t-1}, o_t, a_{t-1}, π_{t-1})
```

```text
logit(p_success_t)
= clip(logit(p_success_{t-1})
       + λ_s · success_signal_t
       - λ_f · failure_signal_t
       - λ_b · budget_penalty_t,
       l_min, l_max)
```

```text
Q'(π | D_t) = Σ_i ω_i · κ(e_i) · q_i(π | D_t)
```

```text
a_t^* = argmax_{a ∈ A_t^valid} U_A(a | x_t, h_t, Π_t)
```

验收：

- 能作为毕设论文核心算法章节初稿；
- 所有变量均定义；
- 所有公式均有直观解释；
- 明确与代码实现的关系；
- 不夸大为完整 POMDP/RL。

---

### Step 10. 写代码差距审查报告

目标：形成后续实现计划的输入。

目标路径：

```text
docs/algorithm-and-llm/core-algorithm-code-gap-review.md
```

建议结构：

1. 总体结论；
2. 已实现能力；
3. 部分实现能力；
4. 未实现能力；
5. 理论-代码 drift；
6. P0 必须改；
7. P1 建议改；
8. P2 可选增强；
9. 测试与实验建议；
10. 实现风险。

差距分级标准：

| 等级 | 含义 |
|---|---|
| P0 | 不改会影响核心算法论证 |
| P1 | 改了会显著增强理论-实现一致性 |
| P2 | 可选增强，不影响毕设主线 |

验收：

- 每个差距都有代码路径；
- 每个差距都有理论依据；
- 每个差距都有建议改法；
- 不直接实施修改。

---

## 6. Files Likely to be Read

### 6.1 设计文档

```text
../thesis-project.design/docs/index/index.md
../thesis-project.design/docs/index/index.json
../thesis-project.design/docs/index/topic_views.json
../thesis-project.design/docs/design/core-algorithm-spec.md
../thesis-project.design/docs/design/runtime-adaptation-formalization.md
../thesis-project.design/docs/design/active-tool-metadata-profile.md
../thesis-project.design/docs/design/de-novo-workflow.md
../thesis-project.design/docs/algorithm-and-llm/core-algorithm-define.md
../thesis-project.design/docs/experiment/algorithm-group-paper-mapping.md
```

### 6.2 代码文件

```text
src/agents/planner.py
src/agents/candidate_generator/builder.py
src/agents/candidate_generator/filters.py
src/agents/candidate_generator/generator.py
src/agents/candidate_generator/models.py
src/workflow/belief_state.py
src/workflow/runtime_policy.py
src/workflow/recovery.py
src/workflow/runtime_evaluator.py
src/workflow/patch_runner.py
src/workflow/plan_runner.py
src/models/contracts.py
src/models/runtime_schemas.py
src/models/validation.py
src/adapters/objective_ranker_adapter.py
src/adapters/tool_schema_utils.py
src/kg/protein_tool_kg.json
```

### 6.3 测试文件

只读审查，预计会参考：

```text
tests/unit/test_planner_agent.py
tests/unit/test_decision_validation.py
tests/unit/test_runtime_schemas.py
tests/unit/test_objective_ranker_adapter.py
tests/integration/test_candidate_score_gate.py
tests/integration/test_recovery_layered_patch.py
tests/integration/test_s6_control_layer_e2e.py
```

具体测试文件名需以实际仓库搜索结果为准。

---

## 7. Files Likely to be Created by This Investigation

本调查阶段只建议创建文档，不改代码。

```text
docs/algorithm-and-llm/core-algorithm-design-code-traceability.md
docs/algorithm-and-llm/core-algorithm-theory-v2.md
docs/algorithm-and-llm/core-algorithm-literature-map.md
docs/algorithm-and-llm/core-algorithm-code-gap-review.md
```

可选补充：

```text
docs/algorithm-and-llm/core-algorithm-v2-implementation-plan.md
```

该文件仅在用户确认理论 v2 和差距审查后再写。

---

## 8. Validation Plan

本调查阶段的验证不是跑测试，而是验证文档质量和可追踪性。

### 8.1 Traceability 验证

检查项：

- 每个关键 SID 是否有设计原文引用；
- 每个关键 SID 是否映射到代码路径；
- 每个关键代码路径是否有设计依据；
- 每个状态变量、评分项、动作效用项是否有来源。

### 8.2 理论完整性验证

检查项：

- 变量是否全部定义；
- 公式是否维度一致；
- 硬约束和软效用是否明确分离；
- belief-state 是否解释为轻量近似，而不是虚假完整 POMDP；
- posterior scoring 是否解释 evidence quality；
- action utility 是否和 recovery/FSM/HITL 一致。

### 8.3 文献质量验证

检查项：

- 不是只堆 protein design 论文；
- 每篇论文都标注用途；
- 每个算法组件都有依据；
- 明确哪些高级方法不采用；
- 引用能支撑论文叙事。

### 8.4 代码差距审查验证

检查项：

- 每个 gap 有文件路径；
- 每个 gap 有理论依据；
- 每个 gap 有严重程度；
- 每个 gap 有后续改造建议；
- 没有在调查阶段直接改代码。

---

## 9. Risks, Tradeoffs, and Open Questions

### 9.1 风险：理论过度包装

风险：把简单启发式包装成过强的理论贡献。

控制方式：

- 明确本方法是 POMDP / budgeted decision making 的轻量近似；
- 不声称求解全局最优；
- 强调可解释、可审计、工程可复现。

### 9.2 风险：文献主线发散

风险：protein design、LLM agent、POMDP、workflow recovery 都能查很多论文，容易失控。

控制方式：

- 文献必须绑定算法组件；
- 不服务于公式或论证的论文不进入主线；
- 核心精读控制在 8–12 篇。

### 9.3 风险：算法贡献定位不清

风险：论文被理解为“只是集成多个蛋白质设计工具”。

控制方式：

- 明确贡献是 workflow-level adaptive planning and recovery control；
- 蛋白生成模型只是工具层；
- 核心算法是候选、约束、belief-state、效用、恢复控制。

### 9.4 风险：理论 v2 与现有代码差距过大

风险：理论写得很好，但实现周期不够。

控制方式：

- D4 中明确 P0/P1/P2；
- P0 只保留支撑毕设主线的最小改动；
- 优先改解释字段、schema 对齐和 score trace，而不是重写系统。

### 9.5 Open Questions

1. 方法名称是否采用 `CEBRA-WP`，还是换成更短、更论文友好的中文/英文名？
2. 论文中是否要把 protein design objective scoring 作为核心算法的一部分，还是作为后验评估模块？
3. `objective_ranker` 是否需要在理论 v2 中引入 evidence discount？
4. belief-state v2 是否必须实现 logit update，还是只在论文中作为理论建议？
5. 实验对照组是否已有足够数据支持 static / dynamic / lite-state 的横向比较？

---

## 10. Recommended Execution Order

建议按以下顺序执行，不要跳步：

```text
1. D1: core-algorithm-design-code-traceability.md
2. D3: core-algorithm-literature-map.md
3. D2: core-algorithm-theory-v2.md
4. D4: core-algorithm-code-gap-review.md
5. 用户审阅确认
6. core-algorithm-v2-implementation-plan.md
7. 进入代码实现
```

理由：

- 先 traceability，避免理论脱离现有系统；
- 再文献，避免公式没有依据；
- 再 theory v2，保证论文表达完整；
- 最后 code gap，转化为可实现任务。

---

## 11. Definition of Done

本调查阶段完成的标准：

- [ ] D1 完成：设计 SID 与代码路径可追踪；
- [ ] D2 完成：理论 v2 可作为论文方法章节初稿；
- [ ] D3 完成：核心文献与算法组件完成映射；
- [ ] D4 完成：代码差距按 P0/P1/P2 分级；
- [ ] 明确是否需要实现 belief-state v2；
- [ ] 明确是否需要改 objective scoring；
- [ ] 明确后续最小实现路径；
- [ ] 用户确认后再进入实现计划。

---

## 12. Notes

当前 `docs/algorithm-and-llm/*` 在 `.gitignore` 中被忽略。如果需要提交本目录下的计划或调查文档，需要使用：

```bash
git add -f docs/algorithm-and-llm/plan/2026-05-05_004920-core-algorithm-investigation-plan.md
```

本计划只定义调查工作，不包含代码实现。任何代码改动都应在理论 v2、文献 map、代码 gap 审查完成并经用户确认后再进行。
