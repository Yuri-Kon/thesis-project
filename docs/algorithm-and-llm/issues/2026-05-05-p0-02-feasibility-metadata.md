# Issue: feat(planner): add explicit feasibility metadata for CEBRA-WP candidates

## 类型

- Priority: P0
- Scope: algorithm / planner / candidate generation / HITL safety
- Phase: CEBRA-WP P0 implementation
- Body language: Chinese
- 状态：待实现
- 本文件定位：P0-1 的唯一实现参考来源；进入编码前以本文为准。

## 1. 背景

CEBRA-WP 理论 v2 将候选工具链集合定义为：

```text
Π_t = {π ∈ Π_raw,t | F_h(π, C, K, h_t)=1}
```

其中：

- `F_h`：硬可执行性约束；
- `F_s`：软降级可展示约束；
- `requires_hitl`：是否必须人工确认；
- `degraded_feasible`：是否允许作为降级候选展示，但不得自动执行。

当前代码已经具备实际过滤逻辑，但缺少统一 metadata 表达。导致问题是：

1. 论文中的 `F_h / F_s` 无法直接映射到候选对象；
2. UI/API/日志无法稳定解释候选为什么被过滤、为什么是降级候选；
3. soft fallback 行为可能让 `io_not_closed` 或 `tool_unavailable` 候选进入 Top-K，但没有显式 `requires_hitl=true`；
4. 未来自动执行路径缺少统一 guard，存在误把降级候选当作可自动执行候选的风险。

本 issue 的目标是新增统一的 `metadata.candidate_feasibility`，并让 `CandidateGenerator` 在过滤、排序、default recommendation 和 explanation 中使用它。

## 2. 当前代码核查结论

### 2.1 候选生成入口

当前候选生成入口：

```text
src/agents/candidate_generator/generator.py::CandidateGenerator.generate
```

关键流程：

```python
candidate = self._builder.build(...)
reason = self._filter_reason(candidate, payload.payload, request, registry_map)
if reason is not None:
    filter_reasons.append(reason)
    if reason in {"io_not_closed", "tool_unavailable"}:
        soft_filtered_rows.append(row)
    continue
filtered_rows.append(row)
```

说明：

- `filtered_rows` 是正常候选；
- `soft_filtered_rows` 是当前兼容 fallback 候选；
- 当前只有 reason 字符串，没有结构化 feasibility metadata。

### 2.2 当前过滤原因

当前 `_filter_reason()` 覆盖：

```text
missing_tools:<ids>
tool_not_allowed
tool_blocked
safety_level_exceeded
cost_level_exceeded
io_not_closed
tool_unavailable
```

来源：

```text
src/agents/candidate_generator/generator.py::_filter_reason
```

### 2.3 soft fallback 行为

当前 `_available_rows()` 逻辑：

```python
available_rows = list(filtered_rows)
if len(available_rows) < top_k:
    append soft_filtered_rows until top_k
if not available_rows and soft_filtered_rows:
    return list(soft_filtered_rows)
```

这意味着：

- 当正常候选不足时，`io_not_closed` / `tool_unavailable` 可以进入返回候选；
- 当没有任何正常候选时，soft fallback 候选可以成为 `default_candidate = candidates[0]`；
- 当前没有字段阻止它成为 default recommendation。

这不是一定错误，因为它保留了 HITL 展示价值；但必须显式标记为 degraded + requires HITL。

### 2.4 CandidateBuilder 当前 metadata

当前 metadata 在：

```text
src/agents/candidate_generator/builder.py::CandidateBuilder._build_metadata
```

已经包含：

```text
candidate_kind
capability_bucket
tool_id
capability_id
io_type
adapter_mode
generation_note
candidate_generator
s5_contract
static_score
action_score
tool/capability readiness metadata
planner_route
recovery_layer/reason
patch/plan candidate metadata
```

但没有：

```text
metadata.feasibility
metadata.requires_hitl
metadata.degraded_feasible
metadata.hard_feasible
```

## 3. 目标

实现统一 feasibility metadata，使每个返回候选都能明确回答：

1. 它是否满足硬可执行约束？
2. 它是否只是降级可展示候选？
3. 它是否需要 HITL？
4. 它为什么被过滤或降级？
5. 它对应理论中的 `F_h` 还是 `F_s`？
6. 它是否允许成为自动执行路径的候选？

## 4. 非目标

本 issue 不做：

1. 不重写候选生成算法；
2. 不改变 tool registry / KG schema；
3. 不改变已有评分权重；
4. 不接入 posterior objective score；该部分由 P0-2 处理；
5. 不实现自动执行功能；只提供 guard metadata；
6. 不删除 soft fallback；只让其语义显式、安全。

## 5. 设计方案

### 5.1 新增 metadata schema

建议每个返回的 `PendingActionCandidate.metadata` 增加：

```python
metadata["feasibility"] = {
    "schema_version": "candidate_feasibility.v1",
    "hard_feasible": bool,
    "soft_feasible": bool,
    "degraded_feasible": bool,
    "requires_hitl": bool,
    "auto_executable": bool,
    "filter_reason": str | None,
    "filter_class": "none" | "hard" | "soft",
    "constraint_codes": list[str],
    "blocked_by": list[str],
    "allowed_for_top_k": bool,
    "allowed_for_default_recommendation": bool,
    "explanation": str,
    "source_refs": [
        "sid:algo.adaptive.feasibility_filter",
        "impl:candidate_generator.feasibility.v1",
    ],
}
```

字段语义：

| 字段 | 语义 |
|---|---|
| `hard_feasible` | 满足硬约束 `F_h`，可进入正常排序 |
| `soft_feasible` | 满足软展示约束 `F_s` |
| `degraded_feasible` | 不满足 `F_h`，但可作为降级候选展示 |
| `requires_hitl` | 是否必须人工确认，不得自动执行 |
| `auto_executable` | 是否允许自动执行。必须等价于 `hard_feasible and not requires_hitl` |
| `filter_reason` | 当前 `_filter_reason()` 的原始 reason |
| `filter_class` | `none` / `hard` / `soft` |
| `constraint_codes` | 归一化约束代码 |
| `blocked_by` | 具体工具、能力或字段 |
| `allowed_for_top_k` | 是否可进入返回的 Top-K |
| `allowed_for_default_recommendation` | 是否可成为默认推荐 |
| `explanation` | 面向 UI/API/日志的短解释 |
| `source_refs` | 理论 SID 与实现引用 |

### 5.2 三态语义

#### A. 正常可执行候选

条件：`_filter_reason() is None`

```python
{
    "hard_feasible": True,
    "soft_feasible": True,
    "degraded_feasible": False,
    "requires_hitl": False,
    "auto_executable": True,
    "filter_reason": None,
    "filter_class": "none",
    "allowed_for_top_k": True,
    "allowed_for_default_recommendation": True,
}
```

#### B. 降级可展示候选

条件：

```text
filter_reason in {"io_not_closed", "tool_unavailable"}
```

```python
{
    "hard_feasible": False,
    "soft_feasible": True,
    "degraded_feasible": True,
    "requires_hitl": True,
    "auto_executable": False,
    "filter_class": "soft",
    "allowed_for_top_k": True,
    "allowed_for_default_recommendation": False,
}
```

注意：

- 可以进入 Top-K 展示；
- 不应成为 default recommendation；
- 如果所有候选都是 degraded，则 `default_recommendation` 应为 `None`，或设置为单独的 `hitl_required_recommendation`，但不得伪装成自动 default。

#### C. 硬不可行候选

条件：

```text
missing_tools
tool_not_allowed
tool_blocked
safety_level_exceeded
cost_level_exceeded
```

```python
{
    "hard_feasible": False,
    "soft_feasible": False,
    "degraded_feasible": False,
    "requires_hitl": False,
    "auto_executable": False,
    "filter_class": "hard",
    "allowed_for_top_k": False,
    "allowed_for_default_recommendation": False,
}
```

硬不可行候选不进入返回的 `candidates`。如果要用于审计，只能进入内部 filter summary，不进入 Top-K。

## 6. Reason 到 feasibility 的映射

建议实现一个纯函数：

```python
def build_candidate_feasibility_metadata(reason: str | None, *, blocked_by: list[str] | None = None) -> dict[str, object]:
    ...
```

映射表：

| reason | filter_class | hard_feasible | degraded_feasible | requires_hitl | constraint_codes |
|---|---:|---:|---:|---:|---|
| `None` | `none` | true | false | false | `[]` |
| `io_not_closed` | `soft` | false | true | true | `schema.io_open` |
| `tool_unavailable` | `soft` | false | true | true | `tool.unavailable` |
| `missing_tools:<ids>` | `hard` | false | false | false | `tool.missing` |
| `tool_not_allowed` | `hard` | false | false | false | `tool.not_allowed` |
| `tool_blocked` | `hard` | false | false | false | `tool.blocked` |
| `safety_level_exceeded` | `hard` | false | false | false | `safety.exceeded` |
| `cost_level_exceeded` | `hard` | false | false | false | `cost.exceeded` |
| unknown reason | `hard` | false | false | false | `unknown` |

未知 reason 默认 hard，是保守安全选择。

## 7. 推荐实现步骤

### Step 1：增加 helper，不改排序

在 `src/agents/candidate_generator/generator.py` 或新文件中增加：

```python
_SOFT_FEASIBILITY_REASONS = {"io_not_closed", "tool_unavailable"}
_HARD_FEASIBILITY_REASONS = {...}

def _build_feasibility_metadata(reason: str | None) -> dict[str, object]:
    ...
```

第一步仅把 metadata 附到 candidate 上，不改变当前 `_available_rows()` 行为。

### Step 2：在 `generate()` 里给每个 candidate 附 feasibility

当前 candidate 是 builder 构造后再过滤：

```python
candidate = self._builder.build(...)
reason = self._filter_reason(...)
```

建议在 reason 计算后更新：

```python
candidate.metadata["feasibility"] = _build_feasibility_metadata(reason)
```

如果 Pydantic model 或 frozen 约束导致不宜原地改，应创建 shallow copy：

```python
candidate = candidate.model_copy(update={"metadata": new_metadata})
```

不要让 metadata 原地 mutation 破坏测试隔离。

### Step 3：禁止 degraded candidate 成为 default recommendation

当前：

```python
default_candidate = candidates[0] if candidates else None
```

应改为：

```python
default_candidate = first candidate where metadata.feasibility.allowed_for_default_recommendation is True
```

如果不存在：

```python
default_candidate = None
default_recommendation = None
```

同时 explanation 应说明：

```text
All returned candidates require HITL; default recommendation suppressed.
```

### Step 4：保留 Top-K 展示兼容

`soft_filtered_rows` 可以继续进入 Top-K，但 explanation 必须明确：

```text
Returned degraded candidates require HITL because: io_not_closed/tool_unavailable.
```

### Step 5：传播到 waiting runtime metadata

`planner._build_pending_action_runtime_metadata()` 目前会传播有限 keys。建议把 feasibility 加入传播列表：

```python
"feasibility"
```

但要注意这里是候选 metadata，不是 score_breakdown 的 `feasibility` 数值。命名可能冲突，建议使用：

```text
candidate_feasibility
```

更稳妥方案：

```python
metadata["candidate_feasibility"] = {...}
```

而不是 `metadata["feasibility"]`。

## 8. 命名决策

为避免与 `score_breakdown["feasibility"]` 混淆，本 issue 最终建议字段名为：

```python
metadata["candidate_feasibility"]
```

理由：

- `score_breakdown.feasibility` 是连续评分；
- `candidate_feasibility` 是约束判定；
- 二者语义不同，不能共用 `feasibility`。

最终 schema：

```python
metadata["candidate_feasibility"] = {
    "schema_version": "candidate_feasibility.v1",
    ...
}
```

## 9. 测试计划

### 9.1 更新 `tests/unit/test_candidate_generator.py`

新增测试：

1. 正常候选带 `candidate_feasibility.hard_feasible=true`；
2. blocked tool 候选不进入 Top-K，explanation 仍记录 filter reason；
3. `io_not_closed` 候选可进入 degraded Top-K，但：
   - `hard_feasible=false`
   - `degraded_feasible=true`
   - `requires_hitl=true`
   - `auto_executable=false`
   - `allowed_for_default_recommendation=false`
4. 当只有 degraded candidate 时：
   - `candidates` 非空；
   - `default_recommendation is None`；
   - explanation 说明 requires HITL。

### 9.2 更新 planner Top-K 测试

现有测试：

```text
tests/unit/test_candidate_generator.py::test_plan_top_k_filters_blocked_tools_before_default_selection
```

应补充断言：

```python
candidate.metadata["candidate_feasibility"]["hard_feasible"] is True
candidate.metadata["candidate_feasibility"]["auto_executable"] is True
```

### 9.3 可能需要新增 fixture

为了制造 `io_not_closed`，可构造 payload 的 required inputs 不被 completed outputs 满足。

为了制造 `tool_unavailable`，可让 readiness metadata 中 `status="unavailable"`。

## 10. 稳定性考虑

### 10.1 不改变 hard filter 行为

硬不可行候选仍不进入 Top-K，避免扩大行为面。

### 10.2 default recommendation 安全收紧

唯一行为变化：degraded candidate 不再成为 default recommendation。

这是必要安全收紧。若 UI 依赖 default always exists，需要同步适配：

```text
default_recommendation=None 表示需要人工确认，不代表没有候选。
```

### 10.3 避免 schema 破坏

不修改 `PendingActionCandidate` model 字段，只加 metadata。这样 API 兼容性最好。

### 10.4 不把 HITL 语义写散

统一以 `candidate_feasibility.requires_hitl` 为准，不再让 UI/API 自行推断。

## 11. 设计 SID 对照

需要设计文档补齐或确认：

```text
sid:algo.adaptive.feasibility_filter
```

对应实现：

```text
impl:candidate_generator.feasibility.v1
impl:candidate_generator.filter_reason.v1
```

如果设计文档暂无该 SID，应在 P0-5 中补到设计 SID 对照表。

## 12. 验收标准

- 每个返回候选都包含 `metadata.candidate_feasibility`；
- hard infeasible 不进入 Top-K；
- degraded feasible 可以展示，但必须 `requires_hitl=true`；
- degraded feasible 不得成为 `default_recommendation`；
- default recommendation 总是 hard feasible + auto executable；
- explanation 能区分 hard filter 与 degraded fallback；
- 相关单测覆盖正常、hard filtered、soft degraded、only degraded 四类场景；
- 不改变业务代码外部 schema，只新增 metadata。

## 13. 回滚策略

如果上线后发现 UI/API 依赖 degraded default：

1. 保留 `candidate_feasibility`；
2. 临时恢复 default 选择逻辑；
3. 但 default metadata 必须加：

```python
"requires_hitl": True
"auto_executable": False
```

不建议回滚 `candidate_feasibility` 字段本身，因为它是后续 P0-2/P0-5 的基础。
