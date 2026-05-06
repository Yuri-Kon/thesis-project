# Issue: feat(objective): connect posterior objective score to planner ranking

## 类型

- Priority: P0
- Scope: algorithm / objective ranking / planner scoring / evidence-aware planning
- Phase: CEBRA-WP P0 implementation
- Body language: Chinese
- 状态：待实现
- 本文件定位：P0-2 的唯一实现参考来源；进入编码前以本文为准。

## 1. 背景

CEBRA-WP 理论 v2 的核心之一是证据感知后验目标评分：

```text
G_post(π; g, o_t) = Σ_m λ_m(g) · ρ_m(o_t) · q_m(π, o_t)
```

当前 `ObjectiveRankerAdapter` 已经实现了接近该公式的 posterior score：

```text
posterior_score.schema_version = posterior_score.v1
posterior_score.aggregate_score
posterior_score.component_weights
posterior_score.evidence_sufficiency
posterior_score.evidence_status
```

但 planner 主评分 `_score_payload()` 仍然主要使用静态 tool/cost/readiness 启发式：

```python
objective = min(1.0, max(0.0, 1.0 - avg_cost * 0.3 + objective_bonus))
```

因此理论中的 `G_post` 尚未成为 planner ranking 的稳定输入。这个差距会削弱论文论证：系统虽然有 posterior scoring 工具，但主规划排序不一定真正使用它。

本 issue 目标是统一 posterior objective 输出，并把它以受控方式接入 planner `score_breakdown.objective`。

## 2. 当前代码核查结论

### 2.1 ObjectiveRankerAdapter 当前 posterior 输出

文件：

```text
src/adapters/objective_ranker_adapter.py
```

当前组件：

```python
_POSTERIOR_COMPONENTS = (
    "generic_objective",
    "stability",
    "function",
    "novelty",
    "structure_quality",
)
```

当前输出：

```python
return {
    "objective_score": objective_score,
    "aggregate_score": objective_score,
    "posterior_score": posterior_score,
    "score_breakdown": score_breakdown,
    "component_scores": score_breakdown,
    ...
}
```

`posterior_score` 内部包含：

```python
{
    "schema_version": "posterior_score.v1",
    "objective_type": objective_type,
    "generic_objective": ...,
    "stability": ...,
    "function": ...,
    "novelty": ...,
    "structure_quality": ...,
    "aggregate_score": aggregate_score,
    "component_weights": ...,
    "evidence_refs": ...,
    "warnings": ...,
    "evidence_sufficiency": ...,
    "evidence_status": ...,
}
```

### 2.2 binding 语义问题

当前 `_OBJECTIVE_TYPE_WEIGHT_PRESETS` 有：

```python
"binding": {
    "generic_objective": 0.35,
    "function": 0.20,
    "structure_quality": 0.20,
    "stability": 0.15,
    "novelty": 0.10,
}
```

但 `_POSTERIOR_COMPONENTS` 没有 `binding`，`posterior_score` 也没有独立 `binding` component。

这不一定是 bug，因为 binding 目前被折叠到 `generic_objective` 的 docking/binding proxy：

```python
fields = _present_fields(candidate, ("binding_score", "best_pose"))
warning="generic_objective uses binding proxy evidence"
```

但理论/论文表达需要明确：

- 初版不新增独立 binding component；
- binding objective type 通过 `generic_objective` + `function` + `structure_quality` 组合表达；
- metadata 中应显式标记 `binding_proxy_component="generic_objective"`，避免读者以为 binding 丢失。

### 2.3 Planner 当前 score 入口

文件：

```text
src/agents/planner.py::_score_payload
```

当前 score_breakdown：

```python
{
    "feasibility": ...,
    "objective": ...,
    "risk": ...,
    "cost": ...,
    "confidence": ...,
    "tool_readiness": ...,
    "tool_coverage": ...,
    "fallback_depth": ...,
    "recovery_complexity": ...,
    "overall": ...,
}
```

`objective` 是静态启发式，不读取 `posterior_score`。

### 2.4 CandidateBuilder 当前 metadata

文件：

```text
src/agents/candidate_generator/builder.py
```

当前 metadata 中有：

```text
s5_contract
static_score
action_score
runtime_adjustment
final_score
rerank_reason
```

但没有统一：

```text
metadata.posterior_objective
metadata.score_breakdown.objective_source
metadata.score_breakdown.evidence_sufficiency
```

## 3. 目标

实现统一 `posterior_objective` schema，并让 planner ranking 能在有证据时使用 posterior objective score。

具体目标：

1. 统一 posterior objective 输出字段；
2. 让 planner 可从候选 payload/metadata 中读取 posterior score；
3. 将 posterior aggregate score 受控接入 `score_breakdown.objective`；
4. 显式记录 objective score 来源；
5. 把 `evidence_sufficiency` 传播到 candidate metadata / runtime state summary 可消费位置；
6. 明确 binding objective 的初版表达方式。

## 4. 非目标

本 issue 不做：

1. 不改变 ObjectiveRankerAdapter 的核心评分公式权重；
2. 不新增机器学习模型；
3. 不把 objective score 变成一票否决；
4. 不重写 planner；
5. 不要求所有 plan candidate 都必须先经过 objective_ranker；
6. 不改变 runtime delta 公式；只提供 evidence signal。

## 5. 统一输出 schema

建议标准字段名为：

```python
metadata["posterior_objective"] = {
    "schema_version": "posterior_objective.v1",
    "aggregate_score": float,
    "components": {
        "generic_objective": {...},
        "stability": {...},
        "function": {...},
        "novelty": {...},
        "structure_quality": {...},
    },
    "component_weights": dict[str, float],
    "evidence_sufficiency": float,
    "evidence_status": "direct" | "partial" | "proxy" | "degraded",
    "objective_type": str | None,
    "objective_source": "posterior_objective" | "prior_goal_fit" | "degraded_proxy",
    "binding_proxy_component": "generic_objective" | None,
    "warnings": list[str],
    "evidence_refs": list[dict[str, object]],
    "source_refs": [
        "sid:algo.posterior_objective_scoring",
        "impl:posterior_score.v1",
    ],
}
```

注意：

- 旧的 `posterior_score` 可保留兼容；
- 新的 `posterior_objective` 是 planner 消费的稳定 schema；
- `posterior_score` 可以作为 adapter raw output；
- `posterior_objective` 是进入 planner candidate metadata 的规范化版本。

## 6. Planner 接入策略

### 6.1 不直接覆盖 overall

不要让 posterior objective 直接覆盖 `overall`。建议只替换/混合 `score_breakdown.objective`，然后用现有权重重新计算 `overall`。

### 6.2 objective 的三种来源

#### A. posterior objective 可用

条件：

```text
posterior_objective.aggregate_score is valid
posterior_objective.evidence_sufficiency >= threshold
```

建议初版 threshold：

```text
evidence_sufficiency >= 0.30
```

行为：

```python
score_breakdown["objective"] = posterior_objective["aggregate_score"]
score_breakdown["objective_source"] = "posterior_objective"
score_breakdown["evidence_sufficiency"] = posterior_objective["evidence_sufficiency"]
```

因为 `score_breakdown` 当前类型是 `dict[str, float]`，不要把 string 放进去。建议将字符串放入 metadata：

```python
metadata["objective_score_source"] = "posterior_objective"
metadata["objective_evidence_sufficiency"] = 0.73
```

#### B. posterior 不存在，但有静态 goal fit

行为：

```python
score_breakdown["objective"] = current prior objective
metadata["objective_score_source"] = "prior_goal_fit"
metadata["objective_evidence_sufficiency"] = 0.5
```

#### C. posterior 存在但 degraded 严重

条件：

```text
evidence_sufficiency < 0.30
```

行为：

```python
score_breakdown["objective"] = blend(prior_objective, posterior_aggregate)
metadata["objective_score_source"] = "degraded_proxy"
```

建议混合：

```text
objective = 0.70 * prior_objective + 0.30 * posterior_aggregate
```

不要直接使用低证据 posterior，否则会让缺证据候选被误排序。

## 7. 读取 posterior 的位置

候选 payload 可能来源：

1. objective_ranker output row；
2. plan metadata；
3. candidate metadata；
4. completed step outputs。

为控制复杂度，P0 初版建议只支持两类：

```text
payload.metadata.posterior_objective
payload.metadata.posterior_score
```

也就是实现 helper：

```python
def _extract_posterior_objective(payload: Plan | PlanPatch) -> dict[str, object] | None:
    metadata = payload.metadata if isinstance(payload.metadata, dict) else {}
    raw = metadata.get("posterior_objective") or metadata.get("posterior_score")
    ...
```

不建议初版扫描所有 completed outputs；那会引入上下文耦合和不可控排序变化。

## 8. `score_breakdown` 类型约束

当前 `_score_payload()` 返回 `dict[str, float]`。因此：

- 所有非数值解释字段不要放进 `score_breakdown`；
- source/status 应进入 candidate metadata；
- 如果需要把 `evidence_sufficiency` 用于 runtime delta，可把它作为数值字段加入 `score_breakdown`，但要确认所有消费者能接受额外 float key。

建议：

```python
score_breakdown["evidence_sufficiency"] = posterior_evidence_sufficiency
```

同时 metadata：

```python
metadata["posterior_objective"] = normalized_posterior
metadata["objective_score_source"] = "posterior_objective"
```

## 9. 重新计算 overall

当前 `overall` 计算：

```python
overall = weights["feasibility"] * feasibility + weights["objective"] * objective + ...
```

接入 posterior 后应保持同一公式，只替换 `objective` 输入。

不要额外再加 objective bonus，否则会双计。

如果 `objective_bonus` 来自 `objective_ranker` tool 存在，接入 posterior 后应选择：

```text
posterior exists → 不再使用 objective_bonus
posterior absent → 保留 objective_bonus
```

否则同一个 objective_ranker 会既提高 objective，又提供 posterior score，产生双重奖励。

## 10. ObjectiveRankerAdapter 侧改动

### 10.1 保留旧输出

保留：

```text
posterior_score
objective_score
aggregate_score
```

### 10.2 新增规范化别名

新增：

```python
"posterior_objective": normalize_posterior_objective(posterior_score)
```

### 10.3 binding 说明

当 `objective_type == "binding"` 时，posterior_objective 增加：

```python
"binding_proxy_component": "generic_objective"
"binding_proxy_fields": ["binding_score", "best_pose"] if present
```

并在 warnings 或 metadata 中说明：

```text
binding objective is represented through generic_objective proxy in v1
```

## 11. CandidateBuilder / Planner 侧改动

### 11.1 CandidateBuilder 传播 posterior metadata

如果 payload metadata 中存在 posterior，则 candidate metadata 中加入：

```python
metadata["posterior_objective"] = normalized_posterior
metadata["objective_score_source"] = source
metadata["objective_evidence_sufficiency"] = value
```

### 11.2 `_score_payload()` 使用 posterior

建议逻辑：

```python
prior_objective = current_objective_formula(...)
posterior = _extract_posterior_objective(payload)
if posterior is usable:
    objective, source = _resolve_objective_score(prior_objective, posterior)
else:
    objective, source = prior_objective, "prior_goal_fit"
```

由于 `_score_payload()` 只返回 float dict，source 不能从它返回。可以考虑：

- 方案 A：新增 `_score_payload_with_metadata()` 返回 score + metadata；
- 方案 B：在 CandidateBuilder 中单独解析 source metadata；
- 方案 C：短期只让 `_score_payload()` 数值接入，metadata 由 builder 再解析。

推荐方案 C，改动最小。

## 12. 测试计划

### 12.1 ObjectiveRankerAdapter 测试

更新：

```text
tests/unit/test_extended_tool_adapters.py::test_objective_ranker_emits_posterior_score_schema_and_degraded_evidence
```

新增断言：

```python
assert "posterior_objective" in top_k[0]
assert posterior_objective["schema_version"] == "posterior_objective.v1"
assert posterior_objective["aggregate_score"] == posterior["aggregate_score"]
assert posterior_objective["source_refs"] == [
    "sid:algo.posterior_objective_scoring",
    "impl:posterior_score.v1",
]
```

新增 binding 测试：

```text
test_objective_ranker_binding_objective_marks_generic_proxy
```

断言：

```python
posterior_objective["objective_type"] == "binding"
posterior_objective["binding_proxy_component"] == "generic_objective"
```

### 12.2 Planner scoring 测试

新增测试文件或扩展：

```text
tests/unit/test_planner_posterior_objective_scoring.py
```

覆盖：

1. posterior evidence sufficient 时，`score_breakdown.objective == aggregate_score`；
2. posterior evidence degraded 时，objective 与 prior 混合；
3. posterior absent 时，保持 prior goal fit；
4. posterior 接入不改变 feasibility/risk/cost 字段；
5. objective_ranker bonus 不双计。

### 12.3 Candidate metadata 测试

检查 Top-K candidate：

```python
candidate.metadata["posterior_objective"]
candidate.metadata["objective_score_source"]
candidate.metadata["objective_evidence_sufficiency"]
```

## 13. 稳定性考虑

### 13.1 排序变化风险

这是 P0 中最可能改变排序行为的 issue。必须用单测锁定：

- posterior 高但高风险候选不能完全压过安全候选；
- objective 权重仍受 `_DEFAULT_SCORE_WEIGHTS["objective"]` 控制；
- posterior 只替换 objective component，不覆盖 overall。

### 13.2 证据不足风险

缺少 direct evidence 时，不应静默视为 direct。必须设置：

```text
objective_score_source = degraded_proxy
```

### 13.3 与 runtime state 的关系

如果 candidate metadata 有 posterior evidence，可以用于后续更新：

```text
runtime_state.evidence_sufficiency
```

但本 issue 不直接修改 belief update 逻辑，只保证 metadata 可用。

### 13.4 API 兼容

保留旧字段 `posterior_score`，新增 `posterior_objective`，避免破坏 CLI/summarizer 现有读取。

## 14. 设计 SID 对照

需要补齐或确认：

```text
sid:algo.posterior_objective_scoring
```

对应实现：

```text
impl:posterior_score.v1
impl:posterior_objective.v1
impl:planner.objective_score_source.v1
```

## 15. 验收标准

- ObjectiveRankerAdapter 输出 `posterior_objective.v1`；
- planner 能从 payload metadata 读取 posterior objective；
- posterior sufficient 时接入 `score_breakdown.objective`；
- posterior degraded 时使用混合或降级策略，不静默当 direct；
- `objective_score_source` 和 `objective_evidence_sufficiency` 出现在 candidate metadata；
- binding objective 的 proxy 表达被显式标记；
- 排序变化被单测覆盖；
- 旧字段 `posterior_score` 保持兼容。

## 16. 回滚策略

如果接入后排序变化过大：

1. 保留 `posterior_objective` 输出；
2. 临时关闭 planner 使用 posterior 的开关；
3. metadata 中设置：

```python
"objective_score_source": "prior_goal_fit"
"posterior_objective_available": True
"posterior_objective_used_for_ranking": False
```

不建议删除 posterior metadata，因为它对论文解释和后续 runtime state 仍有价值。
