# Issue: feat(algorithm): define single recovery-aware action selection boundary

## 类型

- Priority: P0
- Scope: algorithm / workflow / recovery / runtime
- Phase: CEBRA-WP P0 implementation
- Body language: Chinese
- 状态：待实现
- 本文件定位：P0-4 的唯一实现参考来源；进入编码前以本文为准。

## 1. 背景

CEBRA-WP 理论 v2 将恢复动作选择定义为单一策略：

```text
a_t = HardPriority(U_a, x_t, h_t, C) or argmax_{a∈A_allowed} U_a(a,x_t,Pi_t,h_t)
```

动作空间：

```text
A = {continue, patch_local, suffix_replan, stop}
```

该公式有两个层次：

1. `U_a`：动作效用计算，属于 runtime utility calculation；
2. `HardPriority(...) or argmax(...)`：最终恢复动作策略，属于 recovery-aware action selection。

因此代码中应明确：

```text
RuntimeEvaluator 负责计算 U_a
Recovery selector 负责选择 a_t
```

## 2. 当前代码核查结论

### 2.1 主流程入口

只读核查确认：`src/workflow/plan_runner.py` 当前失败恢复路径中调用的是：

```python
decision = select_workflow_action(
    WorkflowActionSelectorInput(...)
)
```

调用位置：

```text
src/workflow/plan_runner.py::_ensure_step_workflow_action
```

该调用会把结果写入：

```python
step_result.metrics["workflow_action"] = decision.action
step_result.metrics["workflow_action_mapped_flow"] = decision.mapped_flow
step_result.metrics["workflow_action_reason"] = decision.reason
step_result.metrics["workflow_action_evidence"] = dict(decision.evidence_source)
```

这说明当前实际主流程已经偏向：

```text
recovery.select_workflow_action() 是恢复动作主入口
```

### 2.2 recovery selector 当前能力

`src/workflow/recovery.py` 中已有：

```python
@dataclass(frozen=True)
class WorkflowActionSelectorInput:
    phase: str = "execution"
    stage_id: str | None = None
    failure_code: str | None = None
    failure_type: FailureType | str | None = None
    retry_exhausted: bool = False
    safety_blocked: bool = False
    runtime_state_summary: dict[str, Any] | None = None
    suggested_action: str | None = None
    suggested_reason: str | None = None
    runtime_policy: str | None = None
```

```python
@dataclass(frozen=True)
class WorkflowActionSelectorResult:
    action: str
    mapped_flow: str
    reason: str
    evidence_source: dict[str, Any]
```

`select_workflow_action()` 当前已经负责：

- phase allowed actions；
- suggested action 规范化；
- runtime policy 解析；
- runtime summary 归一化；
- safety block hard priority；
- stop guard；
- patch/replan/continue route selection；
- `WorkflowActionRoute` 映射；
- `action_utilities` 写入 evidence_source。

### 2.3 RuntimeEvaluator 当前能力与冲突点

`src/workflow/runtime_evaluator.py` 中已有：

```python
RuntimeEvaluator.compute_action_utilities(...)
RuntimeEvaluator.select_action(...)
RuntimeEvaluator._should_auto_stop(...)
RuntimeEvaluator._best_utility(...)
```

`compute_action_utilities()` 是应保留的效用计算函数。

但 `select_action()` 也包含：

- safety block → suffix_replan；
- auto-stop threshold；
- candidate suggested action 优先；
- best utility fallback；
- stop second-best suppression。

这和 `recovery.select_workflow_action()` 中的选择逻辑重叠。

### 2.4 当前测试情况

已存在测试：

```text
tests/unit/test_runtime_evaluator.py
tests/unit/test_recovery_selector.py
tests/integration/test_workflow_action_selector.py
```

其中：

- `test_recovery_selector.py` 验证 recovery selector；
- `test_workflow_action_selector.py` 验证 workflow 主路径；
- `test_runtime_evaluator.py` 同时测试 runtime rerank、utility formula 和 `select_action()`。

需要调整测试语义：

```text
RuntimeEvaluator.select_action() 不再代表 workflow-level selector
```

它最多是 compatibility helper。

## 3. 核心问题

当前问题不是“系统没有恢复动作选择器”，而是：

```text
主流程已有 selector，但代码中仍存在第二套可选 selector 语义。
```

这带来以下风险：

1. **算法边界不严谨**
   - 论文中 `U_a` 和 `a_t` 是不同层次；代码中 `RuntimeEvaluator.select_action()` 把两者混在一起。

2. **策略漂移风险**
   - stop guard 在 runtime evaluator 和 recovery selector 中各有一套，阈值和条件未来可能不一致。

3. **FSM 风险**
   - `AGENT_CONTRACT.md` 明确 recovery、terminal、HITL 语义不能被隐式改变。多个 selector 会增加隐藏 terminal/replan 行为风险。

4. **测试误导**
   - runtime evaluator 的 `select_action()` 单测可能被误解为验证主流程 action selection。

5. **后续 P0 阻塞**
   - P0-1 feasibility、P0-3 action features、P0-5 source refs 都需要知道 action selection metadata 应挂在哪个主流程对象上。

## 4. 目标设计

采用已确认的 D4 方案 A：

```text
RuntimeEvaluator = score / utility calculator
recovery.select_workflow_action = unique recovery-aware action selector
```

### 4.1 RuntimeEvaluator 的最终职责

保留：

```python
RuntimeEvaluator.evaluate_candidates(...)
RuntimeEvaluator.compute_action_utilities(...)
compute_runtime_delta(...)
```

职责：

```text
1. 对候选做 runtime rerank；
2. 计算四类 ActionUtility；
3. 产出 runtime adjustment / final_score / utility 数值；
4. 不拥有 workflow route、terminal stop、HITL、FSM 状态语义。
```

### 4.2 Recovery selector 的最终职责

`recovery.select_workflow_action()` 是唯一 workflow-level selector。

职责：

```text
1. 接收 failure/runtime context；
2. 接收或兼容计算 action_utilities；
3. 应用 hard priority；
4. 应用 stop guard；
5. 选择 selected_action；
6. 映射 WorkflowActionRoute；
7. 产出 evidence_source；
8. 通过 PlanRunner 进入既有 patch/replan/WAITING_* 闭环。
```

## 5. 推荐实现方案

### 5.1 不删除 `RuntimeEvaluator.select_action()`，先降级

不要在本 issue 中删除：

```python
RuntimeEvaluator.select_action(...)
```

原因：

- 删除会产生无谓兼容风险；
- 当前 `tests/unit/test_runtime_evaluator.py` 覆盖它；
- 可能存在外部或未来未检索路径依赖。

建议处理：

1. 保留函数；
2. 更新 docstring，明确：

```text
Compatibility helper only. Workflow-level action selection is owned by recovery.select_workflow_action().
```

3. 不再把它作为主流程 selector；
4. 后续若确认无调用，可另开 P1 issue 删除。

### 5.2 为 `WorkflowActionSelectorInput` 增加可选 `action_utilities`

推荐 additive schema：

```python
@dataclass(frozen=True)
class WorkflowActionSelectorInput:
    ...
    action_utilities: dict[str, ActionUtility] | None = None
```

注意：

- 这是 additive change；
- 不改变现有字段语义；
- 需要从 `src.models.runtime_schemas import ActionUtility`；
- 若担心循环依赖，应确认 `recovery.py` 当前已经依赖 `RuntimeEvaluator`，因此引入 `ActionUtility` 本身风险较低。

### 5.3 action utilities 选择规则

`select_workflow_action()` 内部应采用如下优先级：

```text
if selector_input.action_utilities is not None:
    use selector_input.action_utilities
elif runtime_summary:
    RuntimeEvaluator(policy_mode=runtime_policy).compute_action_utilities(runtime_summary)
else:
    action_utilities = {}
```

关键点：

- 传入的 `action_utilities` 是权威 utility input；
- 未传入时保持现有兼容行为；
- 不允许同时“先用传入值决策，后用内部重算值写 evidence”，否则 evidence 与决策可能不一致。

### 5.4 stop guard 的处理

本 issue 不改变 stop guard 阈值。

当前 recovery selector 的 `_should_choose_stop()`：

```python
if "stop" not in allowed_actions:
    return False
if allow_auto_stop and u_stop >= 0.72:
    return True
return (
    p_success <= 0.20
    and budget_pressure >= 0.85
    and recovery_margin <= 0.20
    and intervention_value <= 0.35
)
```

当前 runtime evaluator 的 `_should_auto_stop()`：

```python
if not allow_auto_stop:
    return False
return (
    stop_u.utility >= 0.72
    and s <= threshold
    and b >= threshold
    and r_margin <= threshold
    and iv <= 0.25
)
```

细化结论：

```text
workflow-level stop guard 以 recovery._should_choose_stop() 为准。
RuntimeEvaluator._should_auto_stop() 只服务 compatibility helper，不作为主流程 stop policy。
```

不要在本 issue 中统一阈值；否则会混入策略变更。阈值统一可以作为 P1 或 P0-3 后续子任务。

### 5.5 evidence_source 结构

当前 `evidence_source` 已包含：

```text
phase
basis
stage_id
failure_code
failure_type
retry_exhausted
s6_default_action
budget_pressure
evidence_sufficiency
intervention_value
prefix_preservability
local_patchability
allow_auto_stop
u_stop
runtime_policy
belief_state_enabled
runtime_state_summary
action_utilities
```

建议新增字段，不删除旧字段：

```python
evidence_source.update({
    "selected_action": action,
    "selected_action_mapped_flow": route.mapped_flow,
    "selection_basis": basis,
    "hard_priority_applied": basis == "hard_priority",
    "hard_priority_reason": reason if basis == "hard_priority" else None,
    "action_utility_source": "input" | "computed" | "missing",
    "source_refs": [
        "sid:algo.recovery_aware_action_selection",
        "impl:recovery.select_workflow_action.v1",
    ],
})
```

保留已有 `basis`，新增 `selection_basis` 只是为了更显式；如果担心重复，也可以只保留 `basis` 并加文档说明。但为了可审计，推荐新增 `selection_basis`，不破坏旧消费者。

### 5.6 `RuntimeEvaluator.compute_action_utilities()` 的 source refs

本 issue 可以只要求 action selection 层 source refs。

但建议同步将 `ActionUtility.source_refs` 从：

```text
runtime_evaluator.action_utility.v1
```

逐步改为 P0-5 约定形式：

```text
sid:algo.schema.action_utility
impl:runtime_evaluator.action_utility.v1
```

如果本 issue 不做该改动，必须在 P0-5 中完成。

## 6. 具体实现步骤

### Step 1：添加输入字段

文件：

```text
src/workflow/recovery.py
```

修改：

```python
from src.models.runtime_schemas import ActionUtility
```

并在 `WorkflowActionSelectorInput` 增加：

```python
action_utilities: dict[str, ActionUtility] | None = None
```

如果项目 typing 对 dict 不够严格，可使用：

```python
Mapping[str, ActionUtility] | None
```

但 dataclass frozen 中保留 dict 也可接受，因为当前 `runtime_state_summary` 已是 `dict[str, Any] | None`。

### Step 2：增加 utility source 决策

在 `select_workflow_action()` 末段当前逻辑：

```python
evaluator = RuntimeEvaluator(policy_mode=runtime_policy)
action_utilities = evaluator.compute_action_utilities(
    runtime_summary or {}
) if runtime_summary else {}
```

改为：

```python
if selector_input.action_utilities is not None:
    action_utilities = dict(selector_input.action_utilities)
    action_utility_source = "input"
elif runtime_summary:
    evaluator = RuntimeEvaluator(policy_mode=runtime_policy)
    action_utilities = evaluator.compute_action_utilities(runtime_summary)
    action_utility_source = "computed"
else:
    action_utilities = {}
    action_utility_source = "missing"
```

注意：

- 不要改变 action 决策顺序；
- 本 issue 只是让 evidence 使用同一份 utility；
- 如果未来要让 utility argmax 影响 action，另开子任务，不混入本次。

### Step 3：补 action selection metadata

在返回 `WorkflowActionSelectorResult` 时补字段：

```python
"selected_action": action,
"selected_action_mapped_flow": route.mapped_flow,
"selection_basis": basis,
"hard_priority_applied": basis == "hard_priority",
"hard_priority_reason": reason if basis == "hard_priority" else None,
"action_utility_source": action_utility_source,
"source_refs": [
    "sid:algo.recovery_aware_action_selection",
    "impl:recovery.select_workflow_action.v1",
],
```

### Step 4：更新 `RuntimeEvaluator.select_action()` docstring

文件：

```text
src/workflow/runtime_evaluator.py
```

更新 docstring，明确：

```text
Compatibility helper only. Workflow-level action selection is owned by recovery.select_workflow_action().
This method must not be used as the PlanRunner recovery decision boundary.
```

不要改其行为。

### Step 5：测试

#### 单测 1：传入 action_utilities 时 evidence 使用 input

文件：

```text
tests/unit/test_recovery_selector.py
```

新增测试：

```text
select_workflow_action(input.action_utilities=custom_utilities)
```

断言：

```text
evidence_source["action_utility_source"] == "input"
evidence_source["action_utilities"] 使用 custom utilities
evidence_source["source_refs"] 包含 sid/impl
```

#### 单测 2：未传入但有 runtime summary 时 computed

断言：

```text
evidence_source["action_utility_source"] == "computed"
action_utilities 非空
```

#### 单测 3：无 runtime summary 时 missing

断言：

```text
evidence_source["action_utility_source"] == "missing"
action_utilities == {}
```

#### 单测 4：safety block 仍覆盖 continue suggestion

保留并增强现有测试：

```text
test_selector_safety_block_overrides_continue_suggestion
```

新增断言：

```text
selection_basis == "hard_priority"
hard_priority_applied is True
hard_priority_reason is not None
```

#### 集成测试：PlanRunner 主路径仍走 recovery selector

文件：

```text
tests/integration/test_workflow_action_selector.py
```

断言失败 step metrics 中：

```text
workflow_action_evidence.source_refs
workflow_action_evidence.selected_action
workflow_action_evidence.selection_basis
```

#### RuntimeEvaluator 测试调整

文件：

```text
tests/unit/test_runtime_evaluator.py
```

不必删除 `select_action()` 测试，但需改测试注释/类名，避免写成 workflow-level selector。

建议：

```text
class TestCompatibilitySelectAction
```

或在测试 docstring 中说明它是 compatibility helper。

## 7. 不应在本 issue 中做的事

为控制风险，本 issue 不做：

1. 不删除 `RuntimeEvaluator.select_action()`。
2. 不统一 runtime/recovery 两套 stop 阈值。
3. 不改变 `_should_choose_stop()` 逻辑。
4. 不改变 FSM 状态迁移。
5. 不改变 patch/replan/stop 的 `WorkflowActionRoute`。
6. 不引入新的 action 类型。
7. 不把 `RuntimeEvaluator` 变成调用 recovery selector 的反向依赖。
8. 不改变 `PlanRunner` 的 patch/replan/HITL 处理顺序。

## 8. 验收标准

- [ ] `WorkflowActionSelectorInput` 支持可选 `action_utilities`。
- [ ] `select_workflow_action()` 使用传入 utilities 时不再重复计算并覆盖 evidence。
- [ ] `evidence_source` 包含：
  - `selected_action`
  - `selected_action_mapped_flow`
  - `selection_basis`
  - `hard_priority_applied`
  - `hard_priority_reason`
  - `action_utility_source`
  - `source_refs`
- [ ] `source_refs` 包含：
  - `sid:algo.recovery_aware_action_selection`
  - `impl:recovery.select_workflow_action.v1`
- [ ] `RuntimeEvaluator.select_action()` docstring 明确 compatibility helper，不是 workflow 主入口。
- [ ] 现有 recovery selector 测试通过。
- [ ] 现有 workflow action selector 集成测试通过。
- [ ] 没有改变 stop/patch/replan/continue 的既有 route 映射。
- [ ] 没有新增、删除、重命名 FSM 状态。

## 9. 建议验证命令

聚焦测试：

```bash
uv run pytest tests/unit/test_recovery_selector.py
uv run pytest tests/integration/test_workflow_action_selector.py
uv run pytest tests/unit/test_runtime_evaluator.py
```

如果修改了 schema import 或 typing，补充：

```bash
uv run basedpyright src/workflow/recovery.py src/workflow/runtime_evaluator.py
```

如果改动影响 PlanRunner metrics，补充：

```bash
uv run pytest tests/unit/test_plan_runner.py
```

## 10. 风险与回滚

### 风险 1：传入 utilities 与 runtime_summary 不一致

例如调用方传入的 `action_utilities` 与 `runtime_state_summary` 不是同一时刻计算出来的。

处理：

- 在 evidence 中记录 `action_utility_source`；
- 初期仅 PlanRunner 内部或测试传入；
- 未来如需强一致，可增加 `runtime_state_version`。

### 风险 2：source_refs 影响 API 快照

新增 metadata 可能影响 API 或测试快照。

处理：

- additive only；
- 不删除旧字段；
- 更新测试期望。

### 风险 3：误以为本 issue 已完成 P0-3

本 issue 只整理 action selection 边界。`_derive_runtime_action_features()` 的 value/source/reason schema 属于 P0-3，不在本 issue 完成。

### 风险 4：RuntimeEvaluator.select_action 继续被误用

处理：

- docstring 明确；
- 若后续发现主流程调用，必须改到 recovery selector；
- 可在 P1 中考虑 deprecation warning 或删除。

## 11. 回滚策略

如果行为回归：

1. 保留新增字段，不删除；
2. 将 `select_workflow_action()` 的 utility 选择逻辑恢复为内部计算；
3. `action_utilities` 字段保留但暂不使用；
4. metadata 新字段可保留，因为是 additive；
5. 不需要回滚 FSM 或 route。

## 12. 相关文件

实现文件：

```text
src/workflow/recovery.py
src/workflow/runtime_evaluator.py
src/workflow/plan_runner.py
```

测试文件：

```text
tests/unit/test_recovery_selector.py
tests/integration/test_workflow_action_selector.py
tests/unit/test_runtime_evaluator.py
tests/unit/test_plan_runner.py
```

相关 schema：

```text
src/models/runtime_schemas.py::ActionUtility
```

## 13. 设计 SID 对照

当前设计文档中已存在相关 SID：

```text
planner.algorithm.action_priority_resolution
planner.algorithm.stop_semantics
algo.schema.action_utility
```

本 issue 推荐新增或确认 alias：

```text
algo.recovery_aware_action_selection
```

推荐最终设计文档更新：

```text
algo.recovery_aware_action_selection
  depends_on:
    - algo.schema.action_utility
    - planner.algorithm.action_priority_resolution
    - planner.algorithm.stop_semantics
```

代码对照：

```text
sid:algo.recovery_aware_action_selection
impl:recovery.select_workflow_action.v1
src/workflow/recovery.py::select_workflow_action
```
