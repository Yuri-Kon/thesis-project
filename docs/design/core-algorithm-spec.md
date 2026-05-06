---
doc_key: algo
version: 2.1
status: stable
depends_on: [arch, agent, workflow, tools, impl]
---

# core-algorithm-spec

> 版本：v2.0 / `cebra_wp.v2`
> 角色：本项目核心算法的单一真源（SSOT）
> 方法名：CEBRA-WP, Constraint- and Evidence-aware Belief-guided Recovery-adaptive Workflow Planning
> 配套文档：
> - `runtime-adaptation-formalization.md`
> - `active-tool-metadata-profile.md`
> - `core-algorithm-theory-map.md`
> - `../experiment/algorithm-group-paper-mapping.md`

---

## 0. 版本体系
<!-- SID:algo.version.registry -->

本文档定义算法总版本 `cebra_wp.v2`。总版本不替代各 payload 的 `schema_version`，而是把当前论文算法使用的子公式、schema 与实现引用归档到同一版本下：

```text
cebra_wp.v2
├─ static_score.v1
├─ posterior_score.v1
├─ runtime_adjustment.v1
├─ action_utility.v1
└─ action_bias.v1
```

| 子公式 | schema / payload 版本 | 主要实现引用 |
| --- | --- | --- |
| `static_score.v1` | `score_breakdown.v1` | `impl:planner.score_breakdown.v1` |
| `posterior_score.v1` | `posterior_score.v1`, `posterior_objective.v1` | `impl:posterior_score.v1`, `impl:posterior_objective.v1` |
| `runtime_adjustment.v1` | `runtime_adjustment.v1` | `impl:planner.runtime_adjustment.v1` |
| `action_utility.v1` | `action_utility.v1`, `action_features.v1` | `impl:runtime_evaluator.action_utility.v1`, `impl:workflow.action_features.v1` |
| `action_bias.v1` | `action_bias.v1` | `impl:runtime_evaluator.compute_runtime_delta.v1` |

维护规则：

- 若字段语义、公式含义或 payload 兼容性发生变化，必须先升级对应子版本；
- 若只调整解释文本、注释或图示，不升级算法总版本；
- 代码侧版本 registry 以 `src.models.algorithm_versions` 为实现入口，设计侧以本文档为语义真源。

---

## 1. 范围与非目标
<!-- SID:algo.scope.overview -->

### 1.1 本文档覆盖的内容

本文档定义本项目的核心算法 CEBRA-WP：

**面向高代价蛋白质设计工作流的约束化、证据感知、信念引导、恢复自适应工具链规划算法**

该算法研究的不是“从多个工具里选一个最匹配工具”，而是：

- 在高代价、长链路、可失败、可恢复的科研工作流中生成若干条可执行候选工具链；
- 对这些候选链进行静态多目标排序；
- 在执行中结合运行时观测维护 Lite belief-state；
- 依据运行时状态决定 `continue / patch_local / suffix_replan / stop`；
- 在不破坏 FSM、HITL 与 Agent 边界的前提下，降低无效高代价调用并提高最终成功率。

本文档覆盖：

- 问题建模
- 候选与输出契约
- 静态评分
- posterior objective scoring
- Lite belief-state 的角色
- 运行时重排序
- Top-K diversity
- 动作选择
- `stop` 的算法语义
- HITL 与 Decision 应用逻辑

### 1.2 本文档不覆盖的内容

- API 端点字段与请求响应体
- EventLog / TaskSnapshot 的详细数据模型
- 具体执行后端与异步调度实现
- 训练细节、数据抽取脚本与模型部署细节

这些内容分别以：

- `architecture.md`
- `system-implementation-design.md`
- `de-novo-workflow.md`
- `train-llm.md`

为准。

### 1.3 本文档的边界约束

本算法必须满足以下不可突破约束：

- 不绕过 FSM 合法迁移；
- 不改变 Planner / Executor / Safety / Summarizer 职责边界；
- 不跳过 `retry -> patch -> replan` 恢复顺序；
- 不把 HITL 变成隐式、不可追溯的自动决策；
- 不把运行时状态写回为新的控制器或新的 Agent。

---

## 2. 术语与对象定义
<!-- SID:algo.definitions.overview -->

### 2.1 核心对象

- `Task`
  - 一次蛋白设计任务，包含目标、约束、预算和政策配置
- `Plan`
  - 初始可执行计划
- `PlanPatch`
  - 对既有计划做的局部修补
- `Replan`
  - 对未执行后缀或整体策略的替换
- `Candidate`
  - 供自动选择或 HITL 选择的结构化候选对象
- `RuntimeState`
  - 对运行时隐状态的 Lite belief-state 表示
- `Observation`
  - 由 `StepResult`、`SafetyResult`、恢复历史和预算使用情况形成的运行时观测

### 2.2 Candidate（候选）统一模式
<!-- SID:planner.contracts.candidate_schema BEGIN -->

为了支持 Human-in-the-loop，本算法要求 Planner 在关键节点输出候选集合（Top-K）：

- `PlanCandidate` <!-- SID:planner.contracts.plan_candidate -->
- `PatchCandidate` <!-- SID:planner.contracts.patch_candidate -->
- `ReplanCandidate` <!-- SID:planner.contracts.replan_candidate -->

每个 Candidate 必须至少包含：

- `candidate_id`
- `summary`
- `structured_payload`
- `score_breakdown`
- `risk_level`
- `cost_estimate`
- `explanation`
- `source_refs`

推荐追加以下运行时解释字段：

- `runtime_adjustment`
- `runtime_adjustment_breakdown`
- `suggested_action`
- `action_utility`
- `runtime_state_summary`
- `posterior_objective`
- `topk_diversity`

说明：

- `runtime_adjustment*` 只作用于运行时重排序，不改变 Candidate 的静态可执行性；
- `runtime_state_summary` 是当次候选生成时使用的状态摘要，不是新的状态所有者。
<!-- SID:planner.contracts.candidate_schema END -->

### 2.3 `stop` 的候选语义

第一版不强制新增 FSM 状态。

为了兼容现有架构，`stop` 作为一种**终止型重规划语义**存在：

- 运输通道：沿用 `replan_confirm`
- 候选类型：`ReplanCandidate`
- 关键字段：
  - `replan_mode = "terminal_stop"`
  - `preserve_prefix_until_step_index`
  - `terminal_reason`

含义：

- 当前剩余后缀被判定为“不值得继续投入”
- 已验证前缀仍然作为审计资产保留
- 若人接受该候选，则任务进入 `FAILED`
- `CANCELLED` 仅用于用户主动取消，不由算法自动触发

### 2.4 硬可行性与 degraded feasible
<!-- SID:algo.adaptive.feasibility_filter -->

定义硬可行性谓词：

```text
F_h(pi,C,K,h_t) in {0,1}
```

若 `F_h = 0`，候选不得进入自动执行排序。`F_h` 至少包含：

```text
F_h = F_tool and F_schema and F_io and F_safety and F_budget_hard and F_availability
```

其中：

- `F_tool`：候选中所有工具必须存在于工具能力图；
- `F_schema`：输入输出字段必须满足工具 schema；
- `F_io`：跨步骤引用必须闭合；
- `F_safety`：候选不能违反安全等级或 safety block；
- `F_budget_hard`：不能超过不可突破预算或成本上限；
- `F_availability`：关键工具必须可用。

过滤后的候选集合：

```text
Pi_t = { pi in Pi_raw,t | F_h(pi,C,K,h_t)=1 }
```

工程上允许保留 `degraded_feasible` 候选用于解释或 HITL：

- `degraded_feasible` 表示候选未完全满足理想证据、readiness 或 fallback 条件，但未触犯硬禁令；
- `degraded_feasible` 候选必须带 `requires_hitl = true` 或等价保护字段；
- `degraded_feasible` 不得在无 HITL 或无显式策略授权时静默自动执行。

---

## 3. 输入、约束与输出契约
<!-- SID:planner.contracts.io_overview -->

### 3.1 Planner 输入

Planner 至少接收：

- `query`
- `constraints`
- `toolkg_snapshot`
- `context`
  - `current_plan`
  - `current_step_index`
  - `step_results`
  - `safety_events`
  - `failure_context`
  - `runtime_state`
- `policy`
  - `require_plan_confirm`
  - `require_patch_confirm`
  - `require_replan_confirm`
  - `allow_auto_stop`
  - 成本/风险阈值

### 3.2 Planner 输出

Planner 输出分为两类：

1. 自动路径
   - `SelectedOutput`
   - 包含选中的 `Plan / PlanPatch / Replan`
2. HITL 路径
   - `CandidateSetOutput`
   - 包含 `Top-K candidates + default_suggestion + explanation`

### 3.3 必须满足的可执行性约束

任一候选的 `structured_payload` 必须满足：

- 工具可用
- I/O 闭包
- 参数合法
- schema 合法
- 资源与安全约束不冲突

不满足者直接淘汰，不进入排序。

---

## 4. 核心问题建模
<!-- SID:algo.adaptive.problem_formulation -->

本课题中的核心算法定义为：

**在高代价、长链路、可失败、可恢复的蛋白质设计工作流中，动态生成、评估、裁剪并修正工具链，使系统以更低成本获得更高任务成功率。**

形式化输入：

- 设计目标 `g`
- 约束集合 `C`
- 工具能力图 `K`
- 当前执行历史 `h_t`
- 当前运行时观测 `o_t`
- 当前运行时 belief-state `x_t`

形式化输出：

- 当前候选工具链集合 `Pi_t`
- 默认推荐链 `pi*`
- 或局部修补 `patch`
- 或后缀重规划 `suffix_replan`
- 或终止建议 `stop`

本问题不是 ToolKG 检索替代问题，而是：

- `constraint-aware`
- `budget-aware`
- `risk-aware`
- `recovery-aware`

的工作流级动态规划问题。

与普通 LLM planner 的差异是：CEBRA-WP 不直接执行单条 `LLM(g,C,K)` 输出，而是在每个关键决策点维护如下闭环：

```text
Pi_raw,t = GenerateCandidates(g,C,K,h_t)
Pi_t = FeasibilityFilter(Pi_raw,t,C,K,h_t)
S_static(pi) = StaticUtility(pi,g,C,K)
x_{t+1} = BeliefUpdate(x_t,o_t,h_t)
U_pi(pi,x_t) = RuntimeCandidateUtility(S_static(pi),x_t)
a_t = RecoveryAwareActionSelection(x_t,Pi_t,h_t)
```

### 4.1 为什么必须使用运行时状态

高代价科研工作流具有三个现实特征：

1. 关键风险并不完全可观测
   - 例如一次结构预测失败究竟是偶发噪声，还是当前后缀整体不可行
2. 错误代价高度非线性
   - 一次错误的高代价调用常常意味着后续多步浪费
3. 恢复价值依赖已完成前缀
   - 是否值得 patch 或 replan，不能只看当前失败步本身

因此需要一个 Lite belief-state 来承载“对隐状态的可解释估计”，而不是依赖单条规则或单次阈值。

---

## 5. 优化目标与六类 Schema
<!-- SID:algo.adaptive.optimization_objective -->

### 5.1 总体优化目标

算法不是单独最大化某一条静态链的先验分，而是追求：

- 更高最终任务成功率
- 更少无效高代价调用
- 更低恢复复杂度
- 更合理的人机分工

定义候选静态效用：

```text
S_static(pi) =
    w_f   F_s(pi)
  + w_g   G(pi;g,o_t)
  - w_c   C_norm(pi)
  - w_r   R_norm(pi)
  - w_rec Rec(pi)
  + w_q   Q(pi)
```

其中：

- `F_s(pi)` 是软可行性分数，不等同于硬可行性谓词 `F_h`；
- `G(pi;g,o_t)` 是目标匹配度；无后验观测时退化为 `G_prior`，有目标证据时使用 `G_post`；
- `C_norm(pi)` 是归一化成本；
- `R_norm(pi)` 是归一化风险；
- `Rec(pi)` 是恢复复杂度；
- `Q(pi)` 是工程可靠性项，例如工具 readiness、coverage 与 fallback depth；
- 任一静态 infeasible 候选必须直接淘汰。

为便于实现，也可以把负项改写为正向分数：

```text
CostScore(pi) = 1 - C_norm(pi)
RiskScore(pi) = 1 - R_norm(pi)
RecoveryScore(pi) = 1 - Rec(pi)
S_static(pi) = sum_k w_k score_k(pi)
```

### 5.2 六类 Schema

为使该算法可解释、可复现，必须固定以下六类 schema：

1. `Cost Schema`
2. `Risk Schema`
3. `Recovery Schema`
4. `State Schema`
5. `Observation Schema`
6. `Action-Utility Schema`

它们的正式公式与字段说明见：

- [runtime-adaptation-formalization.md](./runtime-adaptation-formalization.md)
- [active-tool-metadata-profile.md](./active-tool-metadata-profile.md)

本文档只保留其在算法层的使用语义。

---

### 5.3 证据感知后验目标评分
<!-- SID:algo.posterior.objective_scoring -->

蛋白设计目标通常是多目标的，包括结构质量、稳定性、novelty、功能位点保留、binding/interface quality、developability 与安全性等。不同目标的证据质量不同，因此 CEBRA-WP 使用 evidence-weighted posterior goal fit：

```text
G_post(pi;g,o_t) = sum_{m in M(g)} lambda_m(g) * rho_m(o_t) * q_m(pi,o_t)
```

其中：

- `M(g)`：任务目标相关的评价维度集合；
- `lambda_m(g)`：目标维度权重；
- `q_m(pi,o_t) in [0,1]`：第 `m` 个目标的归一化分数；
- `rho_m(o_t) in [0,1]`：证据可靠性权重；
- `o_t`：当前已获得观测。

证据状态分为：

```text
z_m in {direct, proxy, degraded, missing}
```

对应可靠性：

```text
rho_m =
  1.00       if z_m = direct
  rho_proxy  if z_m = proxy
  rho_degraded if z_m = degraded
  0.00       if z_m = missing and no fallback allowed
```

当前 `posterior_score.v1` 的显式 component 集合为：

```text
M_v1 = {generic_objective, stability, function, novelty, structure_quality}
```

`binding` 在 v1 中不是独立 component。若任务目标为 binding/interface quality，其权重通过 `objective_type = "binding"` 映射到上述 component，实际 binding 观测 `binding_score` / `best_pose` 作为 `generic_objective` 的 proxy evidence 进入 `G_post`。payload 必须显式记录：

```text
binding_policy = "folded_into_generic_objective"
binding_evidence = {"source": "binding_score|best_pose", "role": "proxy"}
```

若未来版本把 `binding` 拆为独立 component，必须同步升级 `posterior_score` / `posterior_objective` schema version，并重新定义权重与论文公式。

整体证据充分度定义为：

```text
E(o_t) = sum_m lambda_m(g) * rho_m(o_t)
e_t = clip(E(o_t), 0, 1)
```

它进入 Lite belief-state 的 `evidence_sufficiency`。

---

## 6. 核心算法流程

### 6.1 总体流程

算法由两个互相衔接的层组成：

1. 静态规划层
   - Tool retrieval
   - Candidate generation
   - Static scoring
   - HITL gate
2. 运行时自适应层
   - Observation extraction
   - Runtime state update
   - Runtime reranking
   - Action selection

### 6.2 静态规划层

静态规划层负责回答：

- 哪些候选链路是可执行的
- 哪些候选链路在任务先验上更值得尝试

### 6.3 运行时自适应层

运行时层负责回答：

- 这条链在当前已经走到这里时是否仍值得继续
- 当前问题更像局部故障还是结构性偏离
- 是否应该继续、patch、保前缀 replan 或止损

---

## 7. Tool Retrieval
<!-- SID:planner.algorithm.tool_retrieval -->

### 7.1 检索目标

给定任务目标与约束，检索满足以下条件的工具集合：

- 能覆盖目标所需的关键能力
- 工具输入输出可以闭合为可执行链路
- 符合工具治理策略
  - `allowed_tools`
  - `blocked_tools`
  - `safety_level`
  - 成本上限

### 7.2 排序信号

工具检索排序推荐使用：

- `capability_match_score`
- `io_compatibility_score`
- `reliability_prior`
- `step_cost`
- `step_risk`

这些信号由 `active-tool-metadata-profile.md` 中定义的元数据提供先验。

---

## 8. Candidate Generation

### 8.1 PlanCandidate

PlanCandidate 用于初始规划。

候选生成策略允许组合：

- Template-based
- Graph-search-based
- LLM-guided assembly + deterministic validation

### 8.2 PatchCandidate

Patch 的目标是：

**最小代价恢复执行**

优先级必须保持：

1. 参数级修补
2. 工具级替换
3. 结构级调整

PatchCandidate 必须显式说明：

- `patch_target`
- `patch_type`
- `patch_ops`
- `post_patch_validation`
- `patch_locality`

### 8.3 ReplanCandidate

Replan 的目标是：

**在保留有效前缀的前提下替换不值得继续的后缀**

第一版支持三种模式：

- `suffix_replan`
- `full_replan`
- `terminal_stop`

优先级：

- 默认优先 `suffix_replan`
- 只有当前缀不可保留时才允许 `full_replan`
- 只有在继续与恢复都不划算时才允许 `terminal_stop`

---

## 9. Candidate Scoring（静态）
<!-- SID:planner.algorithm.candidate_scoring -->

### 9.1 静态评分原则

静态评分回答：

**在还没消费运行时观测之前，哪条链先验上更值得尝试？**

推荐评分项：

- `feasibility_score`
- `objective_score`
- `risk_penalty`
- `cost_penalty`
- `recovery_penalty`
- `stability_bonus`

理论符号与当前实现字段的对应关系：

| 理论符号 | 实现近似字段 | 说明 |
| --- | --- | --- |
| `F_s` | `score_breakdown.feasibility` | 由 tool coverage、readiness 与 fallback depth 近似 |
| `G_prior` / `G_post` | `score_breakdown.objective`, `posterior_objective` | 初始阶段用先验目标匹配；执行后可用证据加权后验目标 |
| `C_norm` | `1 - score_breakdown.cost` | 成本越高，cost score 越低 |
| `R_norm` | `1 - score_breakdown.risk` | 风险越高，risk score 越低 |
| `Rec` | `score_breakdown.recovery_complexity` | `1 - recoverability` |
| `Q` | `confidence`, `tool_readiness`, `tool_coverage`, `fallback_depth` | 工程可靠性补充项 |
| `S_static` | `score_breakdown.overall` / `static_score` | 静态总分 |

### 9.2 `score_breakdown`

每个候选必须至少输出：

- `feasibility`
- `objective`
- `risk`
- `cost`
- `recovery_complexity`
- `overall`

推荐同时输出：

- `static_score`
- `recoverability`
- `candidate_feasibility`
- `posterior_objective`（若已有 objective evidence）
- `source_refs`

### 9.3 风险和成本等级映射

推荐固定映射：

- `value < 0.33 -> low`
- `0.33 <= value < 0.66 -> medium`
- `value >= 0.66 -> high`

这些阈值必须在实现中作为常量或配置项固定。

### 9.4 Top-K diversity
<!-- SID:planner.algorithm.topk_diversity -->

CEBRA-WP 不只输出单个 `pi_t*`，还输出 Top-K：

```text
TopK_t = SelectDiverseTopK(Pi_t, U_pi, k, capability_coverage)
```

选择规则：

- 先按 `U_pi` 或 `S_static` 建立稳定排序；
- 再按 capability bucket 执行 round-robin 选择；
- 当候选缺少 capability bucket 或全部落入同一 bucket 时，退化为稳定分数排序；
- 退化路径必须写入 metadata，避免把纯排序误解释为 diversity 增益。

Top-K metadata 至少应记录：

- `strategy`
- `coverage_fields`
- `selected_bucket`
- `degraded_to_score_sort`
- `source_refs`

---

## 10. Lite Belief-State
<!-- SID:planner.algorithm.runtime_state_estimation -->

### 10.1 状态变量

CEBRA-WP v2 的 Lite belief-state 采用 5 维核心状态：

```text
x_t = (s_t, f_t, r_t, c_t, e_t)
```

其中：

- `s_t = p_success`：当前工作流最终成功概率的代理估计；
- `f_t = p_structural_failure`：结构性失败压力；
- `r_t = recovery_margin`：恢复余量；
- `c_t = expected_remaining_cost`：预期剩余成本，保持原始非负成本尺度，可大于 1；
- `e_t = evidence_sufficiency`：当前证据充分度。

说明：

- `intervention_value` 不进入持久化主状态，而作为派生量；
- `budget_pressure` 不进入持久化主状态，而从 `expected_remaining_cost` 和预算上限派生；
- 这样既能表达“现在该不该继续”，又能维持状态边界稳定。

### 10.2 初始化来源

状态初始化来自：

- 默认推荐候选的静态评分
- 候选的恢复复杂度
- 当前后缀的工具成本/风险元数据
- 高代价前证据层覆盖情况

### 10.3 更新来源

状态更新只允许来自：

- `StepResult.metrics / outputs / error_details`
- `SafetyResult.risk_flags / action`
- patch/replan 历史
- 预算消耗与剩余后缀
- HITL 决策记录

正式更新公式见 [runtime-adaptation-formalization.md](./runtime-adaptation-formalization.md)。

---

## 11. Runtime Reranking
<!-- SID:planner.algorithm.runtime_reranking -->

### 11.1 目标

运行时重排序回答：

**在当前已经走到这里时，这条候选是否仍值得继续？**

### 11.2 公式

运行时重排序遵循：

```text
U_pi(pi,x_t) = clip(S_static(pi) + Delta(pi,x_t), 0, 1)
```

其中：

- `static_score` 是静态评分器输出；
- `Delta(pi,x_t)` 是运行时状态与候选形状共同作用的有界修正项；
- `Delta(pi,x_t)` 只作用于已通过可执行性校验的候选。

无 runtime state 时退化为：

```text
pi_t* = argmax_{pi in Pi_t} S_static(pi)
```

有 runtime state 时：

```text
pi_t* = argmax_{pi in Pi_t} U_pi(pi,x_t)
```

### 11.3 设计约束

运行时重排序必须满足：

- 不改变 `feasibility = 0` 候选的淘汰结果
- 不用 runtime 项覆盖静态 I/O / schema / safety 违规
- 总修正范围有限，防止 runtime 项吞掉静态排序

正式公式见 [runtime-adaptation-formalization.md](./runtime-adaptation-formalization.md)。

---

## 12. 动作选择
<!-- SID:planner.algorithm.runtime_action_selection -->

### 12.1 动作空间

第一版动作空间限定为：

- `continue`
- `patch_local`
- `suffix_replan`
- `stop`

### 12.2 选择逻辑

动作选择应服务于恢复闭环，而不是替代恢复闭环。

基本偏好：

- `p_success` 尚可、故障局部化时，优先 `patch_local`
- `p_structural_failure` 高、`recovery_margin` 低时，优先 `suffix_replan`
- `p_success` 低、预算压力高、人工帮助价值低时，允许 `stop`

动作效用的正式公式见 [runtime-adaptation-formalization.md](./runtime-adaptation-formalization.md)。本文档只固定动作空间、硬优先级和 HITL 边界。

### 12.3 硬优先级

以下规则优先于效用比较：

1. `Safety block`
   - 禁止 `continue`
2. schema / I-O / tool availability 违规
   - 当前候选直接淘汰
3. `retry_exhausted` 且局部可修
   - `patch_local` 先于 `suffix_replan`
4. `prefix_preservability >= 0.40`
   - `suffix_replan` 先于 `full_replan`

### 12.4 `stop` 的选择门槛

只有满足以下条件时才允许自动 stop：

- `allow_auto_stop = true`
- `U_stop >= 0.72`
- `p_success <= 0.20`
- `budget_pressure >= 0.85`
- `recovery_margin <= 0.20`
- `intervention_value <= 0.25`

否则：

- 若 `stop` 有效但不满足自动终止条件，应作为 `replan_confirm` 候选之一进入 HITL；
- 其形式为 `ReplanCandidate(replan_mode="terminal_stop")`。

---

## 13. HITL Gate
<!-- SID:planner.algorithm.hitl_gate -->

### 13.1 触发条件

完成候选生成与排序后，只要满足以下任一条件，就进入 HITL：

1. 系统配置要求确认
2. `risk >= risk_threshold`
3. `cost >= cost_threshold`
4. `SafetyAgent.action = block`
5. 推荐动作为 `stop`，但不满足自动 stop 条件

### 13.2 输出要求

- 默认 `K = 3`
- 候选按 `final_score` 排序
- 必须给出 `default_suggestion`
- 必须给出对候选集总体差异的解释

---

## 14. Decision 应用与固化
<!-- SID:planner.algorithm.decision_application -->

### 14.1 `plan_confirm`

- `accept`：固化所选 Plan
- `replan`：重新进入 planning
- `cancel`：进入 `CANCELLED`

### 14.2 `patch_confirm`

- `accept`：应用 Patch，回到 `RUNNING`
- `replan`：进入 `replan_confirm`
- `cancel`：进入 `CANCELLED`

### 14.3 `replan_confirm`

- `accept`
  - `suffix_replan`：保留前缀并替换后缀
  - `full_replan`：生成新整体 Plan
  - `terminal_stop`：进入 `FAILED`
- `continue`：继续原计划
- `cancel`：进入 `CANCELLED`

### 14.4 `terminal_stop` 的记录要求

若接受 `terminal_stop`：

- 必须写快照
- 必须写终止原因
- 必须将原因编码为结构化 `terminal_reason`
- 不得把系统止损误记为用户取消

---

## 15. 算法验收约束

CEBRA-WP 的完整决策流程必须满足以下伪代码结构：

```text
Algorithm CEBRA-WP(g, C, K, h_t, o_t, x_t)

1:  Pi_raw,t <- GenerateCandidates(g, C, K, h_t)
2:  Pi_t <- FeasibilityFilter(Pi_raw,t, C, K, h_t)
3:  if Pi_t is empty and degraded_feasible candidates exist then
4:      Pi_t <- degraded_feasible candidates
5:      mark candidates as requiring HITL confirmation
6:  end if
7:  for each pi in Pi_t do
8:      S_static(pi) <- StaticUtility(pi, g, C, K)
9:  end for
10: x_{t+1} <- BeliefUpdate(x_t, o_t, h_t)
11: for each pi in Pi_t do
12:     Delta(pi,x_{t+1}) <- RuntimeAdjustment(pi, x_{t+1})
13:     U_pi(pi,x_{t+1}) <- clip(S_static(pi)+Delta(pi,x_{t+1}),0,1)
14: end for
15: TopK_t <- SelectDiverseTopK(Pi_t, U_pi, k, capability_coverage)
16: compute U_a for continue / patch_local / suffix_replan / stop
17: a_t <- ApplyHardPrioritiesAndSelectAction(U_a, x_{t+1}, h_t, C)
18: return Decision_t with candidates, selected_action, explanations, evidence_refs
```

以下约束必须可测试：

1. 候选可执行性
2. Candidate ID 稳定性
3. Decision 幂等性
4. Patch 最小性
5. `suffix_replan` 的前缀保持
6. `stop` 语义的可追溯性
7. runtime adjustment 的常量、阈值、优先级冲突处理可复现
8. 硬不可行候选不会自动执行
9. runtime adjustment 有界，不会覆盖静态可执行性
10. `degraded_feasible` 候选默认进入 HITL 或解释路径
11. Top-K diversity 退化路径有 metadata 标记
12. posterior objective 不被表述为湿实验真值

---

## 16. 与论文叙事的关系

本算法在论文中的主命题建议表述为：

**在相近或更好的成功率下，Lite belief-state 驱动的动态工具链规划，能够更少地进入无效高代价调用，并更合理地分配 `patch / suffix_replan / stop`。**

推荐英文贡献表述：

> We propose CEBRA-WP, a constraint- and evidence-aware, belief-guided, recovery-adaptive workflow planning algorithm for orchestrating expensive protein design tools. Instead of committing to a single LLM-generated tool chain, CEBRA-WP generates a bounded Top-K candidate set, filters infeasible candidates using task constraints and a tool capability graph, estimates static workflow utility from goal fit, cost, risk, recoverability, and engineering reliability, and maintains a low-dimensional deterministic belief surrogate during execution.

实验分组与论文叙事的正式映射见：

- [../experiment/algorithm-group-paper-mapping.md](../experiment/algorithm-group-paper-mapping.md)
- [core-algorithm-theory-map.md](./core-algorithm-theory-map.md)

---

## 17. 一致性声明

本规范与现有系统的一致性如下：

- 不要求把 Planner 变成 controller
- 不新增必须的新 FSM 状态
- 不改变 `retry -> patch -> replan`
- 允许 `stop` 作为终止型重规划语义接入现有 `replan_confirm`
- Lite belief-state 是内部状态估计模块，而不是新的 Agent
