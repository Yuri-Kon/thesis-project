# CEBRA-WP 论文、design 文稿与 algorithm-and-llm 一致性审查

日期：2026-05-20

## 1. 结论

需要更新 design 文稿，且建议同步更新 `docs/algorithm-and-llm/core-algorithm-theory-v2.md` 的早期概览公式。

核心原因：最终 PDF 论文已经采用更完整的 `S_post + Delta` 口径，即运行时效用先把后验目标评分 `G_post` 替换进基础分 `S_post`，再叠加运行时修正 `Delta(pi, x_t)`；但 design 文稿中仍有若干位置保留旧口径 `S_static + Delta` 或 `RuntimeCandidateUtility(S_static, x_t)`。

这不是实现错误，而是文档口径落后。代码侧的运行时重排仍以 `score_breakdown.overall + runtime_adjustment` 为实现载体；当 `score_breakdown.objective` 已经吸收 `posterior_objective` 时，它等价于论文中的 `S_post` 基础分。因此文档应该把 `score_breakdown.overall` 明确解释为：

```text
无后验证据时：score_breakdown.overall = S_static
有 posterior_objective 时：score_breakdown.overall = S_post
final_score = score_breakdown.overall + runtime_adjustment
```

## 2. PDF 论文中的最终口径

PDF 第四章采用以下结构：

1. 算法版本：`cebra_wp.v2`
2. 子公式：`static_score.v1`、`posterior_score.v1`、`runtime_adjustment.v1`、`action_utility.v1`、`action_bias.v1`
3. 主流程：

```text
Pi_raw,t = GenerateCandidates(g, C, K, h_t)
Pi_t = FeasibilityFilter(Pi_raw,t, C, K, h_t)
S_static = StaticUtility(pi, g, C, K)
x_{t+1} = BeliefUpdate(x_t, o_t, h_t)
G_post = PosteriorObjective(pi, g, o_t)
U_pi = RuntimeCandidateUtility(S_static, G_post, x_{t+1})
a_t = RecoveryAwareActionSelection(x_{t+1}, Pi_t, h_t, C)
```

4. 运行时重排序：

```text
S_post = ReplaceObjectiveTerm(S_static, PosteriorObjective(pi, g, o_t))
U_pi(pi, x_t) = clip(S_post(pi) + Delta(pi, x_t), 0, 1)
```

5. `Delta(pi, x_t)`：

```text
Delta(pi, x_t)
  = k_s(p_succ - 0.5) Conf(pi)
  + k_e(2e_suf - 1) max(Conf(pi), F_s(pi))
  - k_f p_sf (1 - RiskScore(pi))
  + k_r r_rec RecoveryScore(pi)
  - k_c b_press (1 - CostScore(pi))
  + k_a ActionBias(pi, x_t)
```

6. 动作效用：

```text
U_continue = 0.38s + 0.14e + 0.12r - 0.22f - 0.14b
U_patch_local = 0.20s + 0.24r + 0.18l_patch + 0.12e_reuse - 0.14f - 0.12b
U_suffix_replan = 0.18(1-s) + 0.20f + 0.16(1-r) + 0.18p_pres + 0.14b_relief + 0.14g_align
U_stop = 0.32(1-s) + 0.24b + 0.18(1-r) + 0.16s_safe + 0.10(1-v_hitl)
```

## 3. Design 文稿中需要更新的位置

### 3.1 `core-algorithm-spec.md` 闭环概览公式需要更新

位置：

```text
../thesis-project.design/docs/design/core-algorithm-spec.md:310-318
```

当前问题：

```text
U_pi(pi,x_t) = RuntimeCandidateUtility(S_static(pi),x_t)
a_t = RecoveryAwareActionSelection(x_t, Pi_t, h_t)
```

建议改为与 PDF 一致：

```text
G_post(pi; g, o_t) = PosteriorObjective(pi, g, o_t)
S_post(pi) = ReplaceObjectiveTerm(S_static(pi), G_post(pi; g, o_t))
U_pi(pi, x_{t+1}) = RuntimeCandidateUtility(S_post(pi), x_{t+1})
a_t = RecoveryAwareActionSelection(x_{t+1}, Pi_t, h_t, C)
```

说明：

- PDF 明确把 `G_post` 纳入主流程；
- `x_{t+1}` 是观测更新后的状态，design 概览不应继续用旧的 `x_t`；
- 动作选择也应包含约束集合 `C`，与 PDF 算法 4-1 一致。

### 3.2 `core-algorithm-spec.md` Runtime Reranking 公式需要更新

位置：

```text
../thesis-project.design/docs/design/core-algorithm-spec.md:728-735
```

当前问题：

```text
U_pi(pi,x_t) = clip(S_static(pi) + Delta(pi,x_t), 0, 1)
```

建议改为：

```text
U_pi(pi,x_t) = clip(S_post(pi) + Delta(pi,x_t), 0, 1)
```

并补充：

```text
S_post(pi) = S_static(pi) with its objective term replaced by G_post(pi; g, o_t)
```

实现映射建议写清楚：

```text
在实现中，`score_breakdown.overall` 是当前用于 rerank 的基础分：
- 无 posterior evidence 时对应 `S_static`
- 有 posterior_objective 时对应 `S_post`
`metadata.static_score` 保留该基础分，`metadata.final_score` 对应 `S_post + runtime_adjustment`
```

### 3.3 `core-algorithm-spec.md` 伪代码需要更新

位置：

```text
../thesis-project.design/docs/design/core-algorithm-spec.md:888-895
```

当前问题：

```text
S_static(pi) <- StaticUtility(pi, g, C, K)
x_{t+1} <- BeliefUpdate(x_t, o_t, h_t)
Delta(pi,x_{t+1}) <- RuntimeAdjustment(pi, x_{t+1})
U_pi(pi,x_{t+1}) <- clip(S_static(pi)+Delta(pi,x_{t+1}),0,1)
```

建议改为：

```text
S_static(pi) <- StaticUtility(pi, g, C, K)
S_post(pi) <- ReplaceObjectiveTerm(S_static(pi), PosteriorObjective(pi, g, o_t))
x_{t+1} <- BeliefUpdate(x_t, o_t, h_t)
Delta(pi,x_{t+1}) <- RuntimeAdjustment(pi, x_{t+1})
U_pi(pi,x_{t+1}) <- clip(S_post(pi)+Delta(pi,x_{t+1}),0,1)
```

## 4. `runtime-adaptation-formalization.md` 需要同步修正

位置：

```text
../thesis-project.design/docs/design/runtime-adaptation-formalization.md:771-775
```

当前问题：

```text
U_pi(pi,x_t) = clip(S_static(pi)+Delta(pi,x_t),0,1)
```

建议改为：

```text
U_pi(pi,x_t) = clip(S_post(pi)+Delta(pi,x_t),0,1)
```

并补充实现映射：

```text
`S_post` is represented by `score_breakdown.overall` after posterior objective binding.
When no posterior objective exists, `S_post = S_static`.
```

## 5. `docs/algorithm-and-llm` 也有一处旧口径

位置：

```text
docs/algorithm-and-llm/core-algorithm-theory-v2.md:83-89
```

当前问题：

```text
U_pi(pi,x_t) = RuntimeCandidateUtility(S_static(pi),x_t)
```

建议同步改为：

```text
G_post(pi;g,o_t) = PosteriorObjective(pi,g,o_t)
S_post(pi) = ReplaceObjectiveTerm(S_static(pi),G_post(pi;g,o_t))
U_pi(pi,x_{t+1}) = RuntimeCandidateUtility(S_post(pi),x_{t+1})
```

另一个位置：

```text
docs/algorithm-and-llm/core-algorithm-theory-v2.md:560-565
```

该处也写成：

```text
U_pi(pi,x_t) = clip(S_static(pi) + Delta(pi,x_t), 0, 1)
```

应同步改为 `S_post + Delta`。

## 6. 无需更新或基本一致的部分

### 6.1 算法版本体系一致

design、algorithm-and-llm、PDF 均使用：

```text
cebra_wp.v2
static_score.v1
posterior_score.v1
runtime_adjustment.v1
action_utility.v1
action_bias.v1
```

### 6.2 Lite belief-state 五维定义一致

三处均为：

```text
x_t = (p_success, p_structural_failure, recovery_margin, expected_remaining_cost, evidence_sufficiency)
```

设计上仍应保留：

```text
budget_pressure 是派生量，不是五维主状态之一。
```

但 UI/demo 可以展示 `budget_pressure`，因为它是从 `expected_remaining_cost` 和 `budget_cap` 派生出的解释字段。

### 6.3 action utility 公式与代码一致

PDF、`runtime-adaptation-formalization.md` 和 `src/workflow/runtime_evaluator.py` 中四个动作效用权重一致：

```text
continue:      0.38, 0.14, 0.12, -0.22, -0.14
patch_local:   0.20, 0.24, 0.18, 0.12, -0.14, -0.12
suffix_replan: 0.18, 0.20, 0.16, 0.18, 0.14, 0.14
stop:          0.32, 0.24, 0.18, 0.16, 0.10
```

stop guard 阈值也一致：

```text
U_stop >= 0.72
p_success <= 0.20
budget_pressure >= 0.85
recovery_margin <= 0.20
intervention_value <= 0.25
```

### 6.4 runtime adjustment 主公式基本一致

`runtime-adaptation-formalization.md` 与 PDF 的 `Delta(pi,x_t)` 结构一致。需要注意的只是基础分应改为 `S_post`，而不是 `S_static`。

## 7. 实现代码与公式的解释口径

代码中的核心映射如下：

```text
src/agents/planner.py::_score_payload
  -> 生成 score_breakdown，包括 feasibility、objective、risk、cost、confidence、recoverability、overall

src/workflow/belief_state.py::update_runtime_state
  -> 生成 / 更新 RuntimeState 五维状态和派生 budget_pressure

src/workflow/runtime_evaluator.py::compute_runtime_delta
  -> 实现 Delta(pi,x_t)，并附带 action_bias factors

src/workflow/runtime_evaluator.py::compute_action_utilities
  -> 实现 continue / patch_local / suffix_replan / stop 四类动作效用
```

需要在设计文稿里说明：

```text
`static_score` 在 metadata 命名上保留历史名称；在 posterior evidence 已绑定时，它代表用于 runtime adjustment 的基础分，可解释为论文公式中的 `S_post`。
```

否则老师或后续维护者容易追问：论文写 `S_post + Delta`，代码和旧设计文档为什么写 `static_score + runtime_adjustment`。

## 8. 推荐更新优先级

P0：必须更新，保持 PDF 与 design 公式一致。

1. `core-algorithm-spec.md` 的闭环概览公式。
2. `core-algorithm-spec.md` 的 Runtime Reranking 公式。
3. `core-algorithm-spec.md` 的 CEBRA-WP 伪代码。
4. `runtime-adaptation-formalization.md` 的最终候选效用公式。
5. `docs/algorithm-and-llm/core-algorithm-theory-v2.md` 的早期概览公式与最终候选效用公式。

P1：建议更新，提高解释质量。

1. 在 design 中补一段“实现字段映射”：
   - `score_breakdown.overall`
   - `metadata.static_score`
   - `metadata.runtime_adjustment`
   - `metadata.final_score`
   - `posterior_objective`
2. 明确 `budget_pressure` 是派生解释字段，可出现在 UI/runtime summary，但不改变五维主状态定义。

P2：可选。

1. 将 `goal_misalignment` 统一为 `goal_realignment`，因为动作效用公式中使用的是 `goal_realignment`。
2. 在 demo 讲稿里解释 `S_static -> S_post -> final_score` 的链路。
