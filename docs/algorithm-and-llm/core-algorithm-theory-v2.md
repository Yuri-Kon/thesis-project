# CEBRA-WP 核心算法理论 v2

- 生成日期：2026-05-05
- 对应计划项：D2 `core-algorithm-theory-v2.md`
- 方法暂名：**CEBRA-WP: Constraint- and Evidence-aware Belief-guided Recovery-adaptive Workflow Planning**
- 中文名：**面向高代价蛋白质设计工作流的约束化、证据感知、信念引导、恢复自适应规划算法**
- 本文定位：可作为论文“方法/核心算法”章节初稿；实现差距将在 D4 单独审查。
- 算法总版本：`cebra_wp.v2`
- 版本 registry：`docs/algorithm-and-llm/algorithm-version-registry.md`

## 摘要

高代价蛋白质设计任务通常由多个异构工具组成，包括序列生成、结构预测、结构相似性检索、稳定性/功能/结合评估与结果汇总等步骤。此类工作流具有长链路、高计算成本、失败模式复杂、证据质量不均、局部恢复价值依赖已执行前缀等特点。直接由大语言模型生成单条工具链容易产生 API 幻觉、I/O 不闭合、无效高代价调用和失败后恢复策略粗糙等问题。

为解决上述问题，本文提出 CEBRA-WP。该算法将蛋白质设计工具链规划建模为一个受约束、部分可观测、证据感知且恢复自适应的工作流决策问题。算法首先基于任务目标、约束和工具能力图生成候选工具链集合；随后使用硬可行性谓词过滤不可执行候选，并以静态效用估计候选的先验质量；在执行过程中，算法维护一个低维 Lite belief-state，用于近似隐藏的工作流可行性、结构性失败压力、恢复余量、剩余成本和证据充分度；最终，算法根据运行时状态对候选效用进行有界修正，并在 continue、patch_local、suffix_replan 和 stop 四类控制动作之间做恢复感知选择。

CEBRA-WP 的核心贡献不是提出新的蛋白生成模型，而是提出一种可解释、可审计、可工程落地的高代价蛋白质设计工具链编排算法。

## 0. 版本体系

本文对应算法总版本 `cebra_wp.v2`。该总版本不替代各 payload 的
`schema_version`，而是把当前论文算法使用的子公式和实现引用归档到同一版本下：

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

代码侧 registry 为 `src.models.algorithm_versions`。若后续任一子公式改变字段语义或公式含义，应先升级子版本，再归档到新的算法总版本。

## 1. 问题定义

### 1.1 工作流规划场景

设一个蛋白质设计任务由以下元素定义：

- `g`：设计目标，例如 de novo binder design、结构稳定性优化、功能位点保留等；
- `C`：任务约束，包括长度范围、目标结构、允许工具、安全等级、预算上限、输出格式等；
- `K`：工具能力图，记录工具的输入输出 schema、能力标签、成本等级、风险等级、可用性、fallback 关系等；
- `h_t`：截至时间步 `t` 的执行历史，包括已完成步骤、失败记录、patch/replan 历史、HITL 决策与快照；
- `o_t`：当前运行时观测，包括 `StepResult`、`SafetyResult`、objective ranker 输出、结构相似性结果、错误细节等；
- `x_t`：运行时 belief-state，用于近似当前工作流的隐藏可行性状态。

算法目标是在每个关键决策点选择：

```text
输出 y_t ∈ {候选工具链 pi, patch_local, suffix_replan, stop, HITL confirmation}
```

使系统在受约束条件下最大化最终任务成功率和有效证据收益，同时降低无效高代价调用、结构性失败传播和恢复复杂度。

### 1.2 与普通 LLM planner 的区别

普通 LLM planner 通常近似为：

```text
pi = LLM(g, C, K)
execute(pi)
```

这存在几个问题：

1. 单候选输出无法表达不确定性；
2. LLM 可能生成不存在工具、错误参数或 I/O 不闭合链路；
3. 执行过程中没有对失败风险和证据质量进行状态估计；
4. 失败后恢复动作常被简化为 retry 或 full replan；
5. 高代价工具调用缺乏预算感知。

CEBRA-WP 改为：

```text
Pi_t = GenerateCandidates(g,C,K,h_t)
Pi_t^F = FeasibilityFilter(Pi_t,C,K,h_t)
S_static(pi) = StaticUtility(pi,g,C,K)
x_{t+1} = BeliefUpdate(x_t,o_t,h_t)
U_pi(pi,x_t) = RuntimeCandidateUtility(S_static(pi),x_t)
a_t = RecoveryAwareActionSelection(x_t,Pi_t^F,h_t)
```

## 2. 候选工具链集合

### 2.1 原始候选生成

令原始候选生成器为：

```text
G_theta(g,C,K,h_t) -> Pi_raw,t
```

其中 `theta` 表示 planner prompt、工具元数据、候选生成规则和任务上下文。候选集合：

```text
Pi_raw,t = {pi_1, pi_2, ..., pi_n}
```

每个候选 `pi_i` 是一个工具链：

```text
pi_i = (a_1, a_2, ..., a_m)
```

每个步骤 `a_j` 包含：

```text
(tool_id, inputs, expected_outputs, metadata)
```

在实现中，对应 `Plan`、`PlanPatch` 与 `PendingActionCandidate`。

### 2.2 硬可行性谓词

定义硬可行性谓词：

```text
F_h(pi,C,K,h_t) ∈ {0,1}
```

若 `F_h=0`，候选不得进入自动执行排序。

`F_h` 至少包含：

```text
F_h = F_tool ∧ F_schema ∧ F_io ∧ F_safety ∧ F_budget_hard ∧ F_availability
```

其中：

- `F_tool`：工具必须存在于工具能力图；
- `F_schema`：输入输出字段必须满足工具 schema；
- `F_io`：跨步骤引用必须闭合；
- `F_safety`：候选不能违反安全等级或 safety block；
- `F_budget_hard`：不能超过不可突破的预算/成本上限；
- `F_availability`：关键工具必须可用。

过滤后的候选集合：

```text
Pi_t = { pi ∈ Pi_raw,t | F_h(pi,C,K,h_t)=1 }
```

### 2.3 软可行性分数

硬约束之外，还定义软可行性：

```text
F_s(pi,C,K,h_t) ∈ [0,1]
```

其衡量候选工具链的结构质量，例如：

- 工具覆盖度；
- fallback 深度；
- capability readiness；
- I/O 引用复杂度；
- 前缀复用程度；
- 任务约束匹配程度。

注意：`F_h` 和 `F_s` 必须区分。前者是可执行性边界，后者是排序信号。

## 3. 静态候选效用

### 3.1 静态效用目标

静态评分回答：

> 在尚未消费当前运行时观测之前，哪条候选链先验上更值得尝试？

定义候选静态效用：

```text
S_static(pi) =
    w_f   F_s(pi)
  + w_g   G_prior(pi; g, C)
  - w_c   C_norm(pi)
  - w_r   R_norm(pi)
  - w_rec Rec(pi)
  + w_q   Q(pi)
```

其中：

- `F_s(pi)`：软可行性；
- `G_prior(pi;g,C)`：先验目标匹配度；
- `C_norm(pi)`：归一化成本；
- `R_norm(pi)`：归一化风险；
- `Rec(pi)`：恢复复杂度；
- `Q(pi)`：工程可靠性项，如工具 readiness、coverage、fallback depth；
- `w_*`：非负权重，可按任务约束配置，归一化后求和。

为便于实现，也可以把负项改写为正向分数：

```text
CostScore(pi) = 1 - C_norm(pi)
RiskScore(pi) = 1 - R_norm(pi)
RecoveryScore(pi) = 1 - Rec(pi)
```

则：

```text
S_static(pi) = Σ_k w_k score_k(pi)
```

### 3.2 与当前代码字段对应

| 理论符号 | 当前实现近似字段 | 说明 |
|---|---|---|
| `F_s` | `score_breakdown.feasibility` | 由 tool coverage 与 fallback depth 近似 |
| `G_prior` | `score_breakdown.objective` | 当前主要是低成本偏好 + objective_ranker bonus，需增强 |
| `C_norm` | `1 - score_breakdown.cost` | 成本越高，cost score 越低 |
| `R_norm` | `1 - score_breakdown.risk` | 风险越高，risk score 越低 |
| `Rec` | `score_breakdown.recovery_complexity` | 定义为 `1 - recoverability`，其中 `recoverability = 0.30*retry_budget_ratio + 0.30*local_patchability + 0.25*prefix_preservability + 0.15*evidence_reusability`；`fallback_depth` 仅作为 `retry_budget_ratio` 的兼容输入 |
| `Q` | `confidence/tool_readiness/tool_coverage/fallback_depth` | 工程可靠性补充项 |
| `S_static` | `score_breakdown.overall` / `static_score` | 静态总分 |

### 3.3 静态评分的边界条件

候选评分必须满足：

```text
if F_h(pi,C,K,h_t)=0:
    pi ∉ Pi_t
```

或者在保留展示候选时：

```text
pi ∈ Pi_degraded,t, but pi cannot be auto-selected without HITL
```

这对应工程中的 soft filtered rows。

## 4. 证据感知目标评分

### 4.1 为什么需要 posterior objective scoring

蛋白设计目标通常是多目标的：

- 结构质量；
- 稳定性；
- novel fold / novelty；
- 功能位点保留；
- binding/interface quality；
- developability；
- sequence recovery / diversity；
- 安全性和可制造性。

这些目标的证据质量不同。有些来自 direct evidence，例如 AlphaFold/AlphaFold3/ESMFold 预测、pLDDT、PAE、interface score；有些来自 proxy evidence，例如序列相似性、embedding 相似性、低成本 predictor；有些只是 degraded fallback。

因此定义 evidence-weighted posterior goal fit：

```text
G_post(pi;g,o_t) = Σ_{m∈M(g)} λ_m(g) · ρ_m(o_t) · q_m(pi,o_t)
```

其中：

- `M(g)`：任务目标相关的评价维度集合；
- `λ_m(g)`：目标维度权重；
- `q_m(pi,o_t) ∈ [0,1]`：第 `m` 个目标的归一化分数；
- `ρ_m(o_t) ∈ [0,1]`：证据可靠性权重；
- `o_t`：当前已获得观测。

当前 `posterior_score.v1` 的显式 component 集合为：

```text
M_v1 = {generic_objective, stability, function, novelty, structure_quality}
```

`binding` 在 v1 中不是独立 component。若任务目标为 binding/interface quality，
其权重通过 `objective_type="binding"` 映射到上述 component，实际 binding 观测
`binding_score` / `best_pose` 作为 `generic_objective` 的 proxy evidence 进入
`G_post`。因此 posterior payload 必须显式记录：

```python
"binding_policy": "folded_into_generic_objective"
"binding_evidence": {"source": "binding_score|best_pose", "role": "proxy"}
```

若未来版本要把 `binding` 拆为独立 component，必须同步升级
`posterior_score` / `posterior_objective` schema version，并重新定义权重与论文公式。

### 4.2 证据可靠性

定义证据状态：

```text
z_m ∈ {direct, proxy, degraded, missing}
```

对应可靠性：

```text
ρ_m =
  1.00, if z_m = direct
  ρ_proxy, if z_m = proxy
  ρ_degraded, if z_m = degraded
  0.00, if z_m = missing and no fallback allowed
```

通常：

```text
1.00 > ρ_proxy > ρ_degraded >= 0
```

当前代码中的 direct/proxy/degraded component 可以直接映射到此定义。

### 4.3 证据充分度

定义整体证据充分度：

```text
E(o_t) = Σ_m λ_m(g) · ρ_m(o_t)
```

归一化后：

```text
e_t = clip(E(o_t), 0, 1)
```

它进入 belief-state 的第五维 `evidence_sufficiency`。

### 4.4 与候选效用的关系

在初始阶段，尚无后验观测时使用 `G_prior`；执行过程中使用 `G_post` 修正：

```text
G(pi;g,o_t) =
  G_prior(pi;g,C), if no objective evidence exists
  G_post(pi;g,o_t), otherwise
```

理论上可将静态目标项扩展为：

```text
S_static(pi,o_t) = ... + w_g G(pi;g,o_t) + ...
```

工程上可先保留 `objective_ranker` 作为后验打分工具，并把其输出写入 `StepResult.metrics` 和 belief-state。

## 5. Lite belief-state

### 5.1 状态定义

CEBRA-WP 使用低维 belief-state：

```text
x_t = (s_t, f_t, r_t, c_t, e_t)
```

其中：

- `s_t = p_success`：当前工作流最终成功概率的代理估计；
- `f_t = p_structural_failure`：结构性失败压力；
- `r_t = recovery_margin`：恢复余量；
- `c_t = expected_remaining_cost`：预期剩余成本，保持原始非负成本尺度，可大于 1；
- `e_t = evidence_sufficiency`：当前证据充分度。

取值范围：

```text
s_t, f_t, r_t, e_t ∈ [0,1]
c_t ∈ R_{>=0}
```

预算压力不是核心状态量本身，而是从剩余成本按需派生：

```text
budget_pressure =
  clip(c_t / max(budget_cap, 0.1), 0, 1.5)  if budget_cap is available
  clip(c_t, 0, 1.5)                          otherwise
```

因此 `expected_remaining_cost` 保留原始估计，`budget_pressure` 承担归一化后的预算压力语义。

### 5.2 为什么称为 Lite belief-state

完整 POMDP belief 通常是隐藏状态分布：

```text
b_t(s) = P(S_t=s | h_t,o_t)
```

但蛋白设计工作流的隐藏状态复杂且异质，很难获得可靠转移概率和观测模型。因此 CEBRA-WP 采用低维代理：

```text
x_t = ψ(h_t,o_t)
```

其中 `ψ` 是可解释、确定性、可审计的状态更新器。

论文中应避免声称 `x_t` 是严格 Bayesian posterior。更准确的表述：

> `x_t` is a deterministic low-dimensional belief surrogate inspired by belief-state planning.

### 5.3 状态更新

定义观测特征：

```text
φ_t = φ(o_t,h_t)
```

包括：

- step success/failure/skipped；
- failure type/code；
- retry exhausted；
- safety warn/block；
- objective progress/gap；
- objective evidence sufficiency；
- structure similarity signal；
- completed/total steps；
- recovery action history。

通用更新形式：

```text
x_{t+1} = clip( A x_t + B φ_t + b )
```

为了保持工程可审计性，当前实现采用规则增量：

```text
s_{t+1} = clip(s_t + Δs(o_t,h_t))
f_{t+1} = clip(f_t + Δf(o_t,h_t))
r_{t+1} = clip(r_t + Δr(o_t,h_t))
c_{t+1} = max(0, C_update(c_t,o_t,h_t))
e_{t+1} = clip(0.70 e_t + 0.30 evidence_signal_t)
```

其中：

```text
evidence_signal_t =
    0.40 · cheap_validation_coverage_t
  + 0.30 · candidate_agreement_t
  + 0.30 · metric_completeness_t
```

`B(x_t,o_t,h_t)` 的当前实现是确定性规则表，而不是学习到的
Bayesian transition model。下表与 `src/workflow/belief_state.py`
中的 `BELIEF_STATE_UPDATE_RULES` 对齐，可直接作为论文中 belief update
的工程定义引用。表中 `n_warn` / `n_block` 表示对应安全标记数量；
`p,q,g` 均先裁剪到 `[0,1]`；未列字段保持不变。

| 观测信号 | 触发条件 | `Δs_t` | `Δf_t` | `Δr_t` | `c_t` 更新 | `e_t` 更新 | 解释 |
|---|---|---:|---:|---:|---|---|---|
| `step_result.success` | 任意步骤成功 | `+0.12` | `-0.08` | `+0.06` | `cost_reward += 0.35`；无进度计数时约为 `c_t - 1.35` | 进入平滑项 | 完成一步提高链路可行性并释放恢复余量 |
| `step_result.success@structural` | 结构阶段或结构工具成功 | `+0.04` | `-0.05` | `0` | `0` | 进入平滑项 | 结构验证降低潜在结构失败压力 |
| `step_result.failed` | 任意步骤失败 | `-0.18` | `+0.14` | `-0.12` | `cost_penalty += 0.75`；无进度计数时约为 `c_t + 1.25` | 进入平滑项 | 失败降低当前后缀可信度并增加剩余成本暴露 |
| `step_result.failed@structural` | 结构阶段或结构工具失败 | `0` | `+0.08` | `0` | `0` | 进入平滑项 | 结构失败更强地指向 suffix replan |
| `step_result.retry_exhausted` | 步骤 metrics 标记 retry exhausted | `-0.05` | `0` | `-0.06` | `cost_penalty += 0.40` | 进入平滑项 | retry 耗尽会消耗局部恢复空间 |
| `step_result.skipped` | 步骤被跳过 | `-0.02` | `0` | `0` | `cost_penalty += 0.15` | 进入平滑项 | skipped 是弱负证据与小成本残留 |
| `safety_result.warn` | SafetyAgent 返回 warn | `-0.04 - 0.01 n_warn` | `+0.05` | `-0.03` | `cost_penalty += 0.25` | candidate agreement `-0.08` 后进入平滑项 | 安全警告降低信心但不终止路线 |
| `safety_result.block` | SafetyAgent 返回 block | `-0.18 - 0.02 n_block` | `+0.12 + 0.01 n_block` | `-0.16` | `cost_penalty += 0.75` | candidate agreement `-0.18` 后进入平滑项 | 安全阻断是强负证据和高恢复压力 |
| `failure_context.patch_local` | 恢复动作归一化为 `patch_local` | `-0.04` | `0` | `-0.07` | `cost_penalty += 0.60` | candidate agreement `+0.04` 后进入平滑项 | 局部修补保留前缀但消耗修复余量 |
| `failure_context.suffix_replan` | 恢复动作为 `suffix_replan` 或 `replan` | `-0.10` | `+0.08` | `-0.12` | `cost_penalty += 1.20` | candidate agreement `-0.08` 后进入平滑项 | 后缀重规划承认当前后缀不可靠 |
| `failure_context.stop` | 恢复动作为 `stop` | `-0.15` | `0` | 设为 `0` | `0` | candidate agreement `-0.08` 后进入平滑项 | stop 在语义上耗尽恢复余量 |
| `failure_context.retry_exhausted` | 失败上下文记录 retry exhausted | `-0.03` | `0` | `-0.04` | `cost_penalty += 0.25` | 进入平滑项 | 恢复上下文继续保留 retry 耗尽的成本 |
| `objective_evidence.progress` | objective ranker 给出进展 `p` | `+0.04p` | `0` | `0` | `0` | 平滑前 `e_t += 0.03p` | 目标进展支持当前目标方向 |
| `objective_evidence.sufficiency` | objective ranker 给出证据充分度 `q` | `0` | `0` | `0` | `0` | 平滑前 `e_t += 0.05q` | 直接目标证据提升证据充分度 |
| `objective_evidence.gap` | objective ranker 给出目标差距 `g` | `0` | `0` | `+0.02g` | `0` | 进入平滑项 | 可见目标差距保留有用重排空间 |
| `evidence_signal` | 汇总 cheap validation、candidate agreement、metric completeness | `0` | `0` | `0` | `0` | `clip(0.70e_t + 0.30 evidence_signal)` | 证据采用平滑更新，避免单次观测过度影响 |
| `progress_counters` | 有 `completed_steps,total_steps` | `0` | `0` | `0` | `max(total_steps - completed_steps + cost_penalty,0)` | 进入平滑项 | 显式进度覆盖启发式一步成本衰减 |

最后统一执行：

```text
s_{t+1}, f_{t+1}, r_{t+1}, e_{t+1} ∈ [0,1]
c_{t+1} = max(c_{t+1}, 0)
```

### 5.4 状态解释

| 状态 | 增加意味着 | 降低意味着 | 决策影响 |
|---|---|---|---|
| `s_t` | 当前链路更可能成功 | 成功希望降低 | 低 `s_t` 提高 replan/stop 倾向 |
| `f_t` | 结构性失败压力升高 | 失败更局部或风险缓解 | 高 `f_t` 提高 suffix_replan 倾向 |
| `r_t` | 仍有恢复空间 | patch/retry/replan 余量不足 | 低 `r_t` 提高 stop 或 suffix_replan 倾向 |
| `c_t` | 剩余成本/预算压力高 | 成本压力缓解 | 高 `c_t` 抑制 continue/patch，提高 stop |
| `e_t` | 证据充分 | 证据不足或 degraded | 高 `e_t` 支持继续，低 `e_t` 支持补证据或谨慎 replan |

## 6. 运行时候选效用

### 6.1 有界运行时修正

执行过程中，观测可能改变候选排序。定义运行时修正：

```text
Δ(pi,x_t) =
    κ_s · (s_t - 0.5) · Conf(pi)
  + κ_e · (2e_t - 1) · max(Conf(pi), F_s(pi))
  - κ_f · f_t · (1 - RiskScore(pi))
  + κ_r · r_t · RecoveryScore(pi)
  - κ_c · bp_t · (1 - CostScore(pi))
  + κ_a · ActionBias(pi,x_t)
```

其中：

```text
bp_t = clip(c_t, 0, 1)
```

`ActionBias` 表示根据候选类型产生的小幅修正：

- patch 候选在 fallback/recovery 充足时加分；
- suffix_replan 在结构性失败压力高且保留前缀可行时加分；
- stop 在低成功、高预算、低恢复余量时作为 terminal action，但对普通候选排序可施加保护性惩罚。

实现中该理论对象由 `runtime_adjustment.action_bias` 承载，包含
`action/value/factors/source_refs`，且 `action_bias.value` 与
`runtime_adjustment.value` 保持一致。

为了避免单次观测过度影响排序，限定：

```text
Δ(pi,x_t) ∈ [-δ_max, δ_max]
```

当前实现中：

```text
δ_max = 0.35
```

### 6.2 最终候选效用

定义最终候选效用：

```text
U_pi(pi,x_t) = clip(S_static(pi) + Δ(pi,x_t), 0, 1)
```

默认候选选择：

```text
pi_t^* = argmax_{pi ∈ Pi_t} U_pi(pi,x_t)
```

若没有 runtime state，则退化为：

```text
pi_t^* = argmax_{pi ∈ Pi_t} S_static(pi)
```

### 6.3 Top-K 输出

CEBRA-WP 不只输出单个 `pi_t^*`，还输出 Top-K：

```text
TopK_t = SelectDiverseTopK(Pi_t, U_pi, k, capability_coverage)
```

其中 `SelectDiverseTopK` 先按 `U_pi` 或 `S_static` 建立稳定排序，再按
capability bucket 执行 round-robin 选择。等价地，可把它理解为在高分候选中加入
能力覆盖约束：

```text
TopK_t = arg top-k under U_pi subject to capability_coverage(TopK_t)
```

这使 Top-K 不只是“分数最高的 k 个候选”，而是同时保留：

- 不同 capability bucket 的替代路径；
- 不同失败恢复路径；
- 不同成本/风险层级下的候选解释空间。

若候选缺少 capability bucket，或所有候选落在同一个 bucket，选择退化为稳定分数排序；
工程 metadata 必须标记该退化路径，避免把纯排序误解释为 diversity 增益。

并记录：

- `static_score`；
- `runtime_adjustment`；
- `final_score`；
- `rerank_reason`；
- `topk_diversity`；
- `default_recommendation_reason`。

这使 HITL 能看到为什么候选被推荐、为什么被 runtime rerank 改变。

## 7. 恢复感知控制动作

### 7.1 动作空间

定义控制动作集合：

```text
A = {continue, patch_local, suffix_replan, stop}
```

含义：

- `continue`：继续当前链路或默认候选；
- `patch_local`：局部修补当前失败步骤或局部参数/schema；
- `suffix_replan`：保留已验证前缀，替换后续链路；
- `stop`：不再投入高代价执行，生成带理由的终止候选。

### 7.2 动作效用

令：

```text
s = s_t = p_success
f = f_t = p_structural_failure
r = r_t = recovery_margin
e = e_t = evidence_sufficiency
b = budget_pressure
```

派生量：

- `lp`：local_patchability，局部可修复性；
- `er`：evidence_reusability，已获得证据可复用性；
- `pp`：prefix_preservability，已验证前缀可保留性；
- `br`：budget_relief，replan 后预算缓解程度；
- `gr`：goal_realignment，replan 后目标重新对齐能力；
- `st`：safety_terminality，安全问题是否具有终止性；
- `iv`：intervention_value，人工介入预期价值。

定义四类动作效用：

```text
U_continue = 0.38s + 0.14e + 0.12r - 0.22f - 0.14b
```

```text
U_patch_local = 0.20s + 0.24r + 0.18lp + 0.12er - 0.14f - 0.12b
```

```text
U_suffix_replan = 0.18(1-s) + 0.20f + 0.16(1-r) + 0.18pp + 0.14br + 0.14gr
```

```text
U_stop = 0.32(1-s) + 0.24b + 0.18(1-r) + 0.16st + 0.10(1-iv)
```

归一化：

```text
U_a ∈ [0,1]
```

### 7.3 硬优先级

动作选择不是纯 `argmax`。以下硬优先级优先：

1. **Safety block**：禁止 `continue`；一般升级为 `suffix_replan`，除非满足 stop 门槛。
2. **Schema/I-O/tool availability 违规**：候选不得自动执行。
3. **Retry exhausted 且局部可修**：优先 `patch_local`，避免不必要 full/suffix replan。
4. **结构性失败压力高且恢复余量低**：优先 `suffix_replan`。
5. **Auto-stop guard**：只有满足严格门槛才能自动 stop。

### 7.4 stop 门槛

自动 stop 必须满足：

```text
allow_auto_stop = true
U_stop >= τ_stop
s <= τ_s
b >= τ_b
r <= τ_r
iv <= τ_iv
```

当前建议阈值：

```text
τ_stop = 0.72
τ_s = 0.20
τ_b = 0.85
τ_r = 0.20
τ_iv = 0.25
```

若 `U_stop` 高但不满足自动终止条件，则进入 HITL：

```text
terminal_stop ∈ ReplanCandidateSet
```

### 7.5 动作选择

定义硬约束处理函数：

```text
H(a,x_t,h_t,C) ∈ {allowed, blocked, forced}
```

最终动作选择：

```text
if exists forced action by hard priority:
    a_t = forced action
else:
    a_t = argmax_{a ∈ A_allowed} U_a(a,x_t,Pi_t,h_t)
```

如果 `a_t = continue`：

```text
execute pi_t^*
```

如果 `a_t = patch_local`：

```text
generate/apply local patch candidate
```

如果 `a_t = suffix_replan`：

```text
preserve verified prefix; generate suffix candidates
```

如果 `a_t = stop`：

```text
create terminal_stop candidate and route through HITL or terminal policy
```

## 8. CEBRA-WP 完整算法

### 8.1 输入输出

输入：

```text
(g, C, K, h_t, o_t, x_t, budget_state, runtime_policy)
```

输出：

```text
Decision_t = {
  top_k_candidates,
  default_recommendation,
  selected_action,
  action_utility,
  runtime_state_summary,
  explanation,
  evidence_refs
}
```

### 8.2 伪代码

```text
Algorithm CEBRA-WP(g, C, K, h_t, o_t, x_t)

1:  Pi_raw,t ← GenerateCandidates(g, C, K, h_t)
2:  Pi_t ← ∅
3:  Pi_degraded,t ← ∅

4:  for each pi in Pi_raw,t do
5:      feasibility ← EvaluateHardFeasibility(pi, C, K, h_t)
6:      if feasibility = hard_infeasible then
7:          discard pi with reason
8:      else if feasibility = degraded_feasible then
9:          Pi_degraded,t ← Pi_degraded,t ∪ {pi}
10:     else
11:         Pi_t ← Pi_t ∪ {pi}
12:     end if
13: end for

14: if Pi_t = ∅ and Pi_degraded,t ≠ ∅ then
15:     Pi_t ← Pi_degraded,t
16:     mark all candidates as requiring HITL confirmation
17: end if

18: for each pi in Pi_t do
19:     S_static(pi) ← StaticUtility(pi, g, C, K)
20: end for

21: x_{t+1} ← BeliefUpdate(x_t, o_t, h_t)

22: for each pi in Pi_t do
23:     Δ(pi,x_{t+1}) ← RuntimeAdjustment(pi, x_{t+1})
24:     U_pi(pi,x_{t+1}) ← clip(S_static(pi)+Δ(pi,x_{t+1}),0,1)
25: end for

26: TopK_t ← SelectDiverseTopK(Pi_t, U_pi, k, capability_coverage)
27: pi_t^* ← argmax_{pi∈TopK_t} U_pi(pi,x_{t+1})

28: for each a in {continue, patch_local, suffix_replan, stop} do
29:     U_a(a) ← ActionUtility(a, x_{t+1}, TopK_t, h_t)
30: end for

31: a_t ← ApplyHardPrioritiesAndSelectAction(U_a, x_{t+1}, h_t, C)

32: if a_t = continue then
33:     return Decision(continue, pi_t^*, TopK_t)
34: else if a_t = patch_local then
35:     return Decision(patch_local, GeneratePatchCandidate(...), TopK_t)
36: else if a_t = suffix_replan then
37:     return Decision(suffix_replan, GenerateSuffixReplan(...), TopK_t)
38: else if a_t = stop then
39:     return Decision(terminal_stop, BuildTerminalStopCandidate(...), TopK_t)
40: end if
```

### 8.3 算法性质

#### 性质 1：硬不可行候选不被自动执行

若：

```text
F_h(pi,C,K,h_t)=0
```

则：

```text
pi ∉ Pi_t
```

因此 `pi` 不会成为自动默认推荐。

工程例外：若候选被标为 `degraded_feasible`，只能进入 HITL 或 fallback 解释路径，不能静默自动执行。

#### 性质 2：运行时观测影响有界

由于：

```text
Δ(pi,x_t) ∈ [-δ_max, δ_max]
```

所以：

```text
|U_pi(pi,x_t) - S_static(pi)| <= δ_max
```

这保证单次运行时观测不会无界推翻静态结构质量。

#### 性质 3：stop 是受保护动作

即使 `U_stop` 为最高，也只有满足 auto-stop 门槛时才能自动 stop。否则必须进入 HITL。

因此：

```text
stop_auto ⇒ allow_auto_stop ∧ U_stop≥τ_stop ∧ s≤τ_s ∧ b≥τ_b ∧ r≤τ_r ∧ iv≤τ_iv
```

#### 性质 4：恢复动作保留前缀价值

`suffix_replan` 不等价于 full replan。它通过 `prefix_preservability` 和 `preserve_prefix_until_step_index` 保留已验证前缀，降低重复高代价调用。

## 9. 与当前代码的理论映射

| 理论模块 | 实现位置 | 当前状态 |
|---|---|---|
| `GenerateCandidates` | `src/agents/candidate_generator/generator.py` | 已实现 Plan/Patch/Replan Top-K |
| `F_h` | `CandidateGenerator._filter_reason()` | 已实现工具、约束、安全、成本、I/O、readiness 过滤 |
| `S_static` | `src/agents/planner.py::_score_payload()` | 已实现静态 score_breakdown |
| `x_t` | `src/workflow/belief_state.py::update_runtime_state()` | 已实现五维 Lite belief-state |
| `Δ(pi,x_t)` | `src/workflow/runtime_evaluator.py::compute_runtime_delta()` | 已实现 bounded runtime adjustment |
| `ActionBias(pi,x_t)` | `metadata.runtime_adjustment.action_bias` | 已实现 action/value/factors/source_refs 统一承载 |
| `U_pi` | `final_score = static_score + runtime_adjustment` | 已实现候选 rerank |
| `U_a` | `RuntimeEvaluator.compute_action_utilities()` | 已实现四动作效用公式 |
| hard priorities | `src/workflow/recovery.py::select_workflow_action()` | 已实现 safety/stop/patch/replan 规则 |
| terminal stop | `build_terminal_stop_candidate()` | 已实现 terminal_policy=stop |
| posterior goal evidence | `src/adapters/objective_ranker_adapter.py` | 已实现 direct/proxy/degraded components，但需更强整合 |

## 10. 本文贡献点建议写法

### 10.1 中文版本

本文提出 CEBRA-WP，一种面向高代价蛋白质设计工作流的约束化、证据感知、信念引导、恢复自适应工具链规划算法。与直接由 LLM 生成单条工具链不同，CEBRA-WP 首先生成 Top-K 候选工具链，并通过工具能力图和任务约束执行硬可行性过滤；随后使用成本、风险、目标匹配、恢复复杂度和工程可靠性构造静态候选效用；执行过程中，算法维护一个低维 Lite belief-state，以可解释方式融合步骤结果、安全检查、目标证据和失败上下文；最后，算法基于运行时状态对候选进行有界重排，并在 continue、patch_local、suffix_replan 和 stop 之间选择恢复感知控制动作。该方法提高了高代价工具调用的审慎性，降低了无效后缀执行和失败恢复成本，并为人机协同确认提供了可审计候选和理由。

### 10.2 English version

We propose CEBRA-WP, a constraint- and evidence-aware, belief-guided, recovery-adaptive workflow planning algorithm for orchestrating expensive protein design tools. Instead of committing to a single LLM-generated tool chain, CEBRA-WP generates a bounded Top-K candidate set, filters infeasible candidates using task constraints and a tool capability graph, estimates static workflow utility from goal fit, cost, risk, recoverability, and engineering reliability, and maintains a low-dimensional deterministic belief surrogate during execution. Runtime observations induce bounded candidate reranking, while a recovery-aware control policy selects among continuing, local patching, suffix replanning, and terminal stopping. The algorithm provides auditable decisions for high-cost scientific workflows under partial observability and heterogeneous evidence quality.

## 11. 理论边界与诚实表述

需要避免过度宣称：

1. 不要说 CEBRA-WP 是严格 POMDP 最优策略；它是受 POMDP 启发的低维 belief surrogate。
2. 不要说当前权重是学习得到或理论最优；当前是可解释启发式权重，可通过实验校准。
3. 不要说 posterior objective 是真实实验验证；它是基于模型/工具输出的 evidence-weighted computational score。
4. 不要说 stop 是自动失败；stop 是经济性/恢复性终止建议，默认需要严格门槛或 HITL。
5. 不要把本文贡献写成新蛋白生成模型；贡献是工具链编排与恢复感知规划。

## 12. 后续实现优化方向

这些不是本文档要直接改代码的内容，但 D4 可据此审查：

1. 把 `F_h`、`F_s`、`degraded_feasible` 明确编码到候选 metadata。
2. 将 `recovery_complexity` 纳入静态评分权重，或明确用 `fallback_depth` 等价替代。
3. 将 `objective_ranker_adapter` 的 posterior score 与 planner objective 统一。
4. 为 `local_patchability/evidence_reusability/prefix_preservability/budget_relief/goal_realignment` 补充稳定派生逻辑。
5. 确认 `RuntimeEvaluator.select_action()` 与 `recovery.select_workflow_action()` 的主从关系。
6. 为 `runtime_adjustment_formula` 补充设计文档正文，避免 SID 只有标题。
7. 用实验对照验证 `static_top1`、`static_gate`、`dynamic_observation_only`、`lite_belief_state` 的差异。

## 13. 可直接放入论文的核心公式汇总

```text
Pi_raw,t = G_theta(g,C,K,h_t)
```

```text
Pi_t = { pi ∈ Pi_raw,t | F_h(pi,C,K,h_t)=1 }
```

```text
S_static(pi) =
    w_f F_s(pi)
  + w_g G(pi;g,o_t)
  - w_c C_norm(pi)
  - w_r R_norm(pi)
  - w_rec Rec(pi)
  + w_q Q(pi)
```

```text
G_post(pi;g,o_t) = Σ_{m∈M(g)} λ_m(g) · ρ_m(o_t) · q_m(pi,o_t)
```

```text
x_t = (s_t, f_t, r_t, c_t, e_t)
```

```text
x_{t+1} = B(x_t,o_t,h_t)
```

```text
Δ(pi,x_t) =
    κ_s(s_t-0.5)Conf(pi)
  + κ_e(2e_t-1)max(Conf(pi),F_s(pi))
  - κ_f f_t(1-RiskScore(pi))
  + κ_r r_t RecoveryScore(pi)
  - κ_c bp_t(1-CostScore(pi))
  + κ_a ActionBias(pi,x_t)
```

```text
U_pi(pi,x_t) = clip(S_static(pi)+Δ(pi,x_t),0,1)
```

```text
pi_t^* = argmax_{pi∈Pi_t} U_pi(pi,x_t)
```

```text
A = {continue, patch_local, suffix_replan, stop}
```

```text
U_continue = 0.38s + 0.14e + 0.12r - 0.22f - 0.14b
```

```text
U_patch_local = 0.20s + 0.24r + 0.18lp + 0.12er - 0.14f - 0.12b
```

```text
U_suffix_replan = 0.18(1-s) + 0.20f + 0.16(1-r) + 0.18pp + 0.14br + 0.14gr
```

```text
U_stop = 0.32(1-s) + 0.24b + 0.18(1-r) + 0.16st + 0.10(1-iv)
```

```text
a_t = HardPriority(U_a,x_t,h_t,C) or argmax_{a∈A_allowed} U_a(a,x_t,Pi_t,h_t)
```

```text
stop_auto ⇒ allow_auto_stop ∧ U_stop≥0.72 ∧ s≤0.20 ∧ b≥0.85 ∧ r≤0.20 ∧ iv≤0.25
```

## 14. 小结

CEBRA-WP 的理论核心可以概括为：

```text
约束过滤保证能不能执行；
静态效用估计先验值不值得执行；
证据加权目标评分判断科学目标达成度；
Lite belief-state 估计当前链路是否还值得继续；
runtime adjustment 用有界方式修正候选排序；
恢复动作效用决定继续、修补、重规划还是止损。
```

这个版本已经能支撑论文中的“核心算法设计”章节。下一步 D4 应检查当前代码与该理论 v2 的具体差距，并按 P0/P1/P2 给出实现优化建议。
