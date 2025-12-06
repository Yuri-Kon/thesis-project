# 核心算法规约

1. 静态规划：基于工具知识图谱，利用前向启发式搜索生成满足任务能力需求、I/O类型一致、安全等级符合要求的初始Plan
2. 运行时动态调整：在任务执行过程中，根据StepResult与SafetyAgent的审查结果，执行在线再规划(replan)与局部补丁(patch)，实现计划的动态修复与继续执行。

## 任务建模

任务输入被解析为结构化对象`TaskSpec`

```json
TaskSpec:
  goal_capabilities : set[str]  # 需要完成的能力，如 sequence_design
  initial_artifacts : set[str]  # 初始可用 JSON key，如 {"input_sequence"}
  constraints:
      safety_level : int  # 可接受的最大安全等级
      max_cost     : float  # 最大累计成本
      max_steps    : int  # 最大步骤数量
```

## 工具知识图

每个工具的设计参见[系统实现设计](system-implementation-design.md#Tool-节点-Schema)  
图的添加规则也参见[系统实现设计](system-implementation-design.md#KG-图结构与边构建规则(供Planner使用))

## 静态规划算法

静态规划算法负责生成任务的初始Plan,是动态规划的前提

### 搜索状态定义

静态规划算法采用前向启发式搜索，其中的状态结构是：

```text
SearchState:
    path : list[Tool]  # 当前已经选择工具序列
    available_io : set[str]  # 当前可用的JSON key
    capabilities : set[str]  # 当前已经覆盖的能力
    cost : float  # 累计成本
```

初始状态是：

```text
path = []
available_io = task.initial_artifacts
capabilities = 空
cost = 0
```

### 状态扩展规则

从状态S扩展工具t需要同时满足：

1. I/O兼容性(R1)：`t.io.inputs` $\subseteq$ `S.available_io`
2. 安全约束(R2): `t.safety_level <= task.constraints.safety_level`
3. 资源/步数约束: `S.cost + t.cost <= max.cost`  `len(S.path) + 1 <= max_steps`

扩展后的新状态是：

```text
S'.path = S.path + [t]
S'.available_io = S.available_io ∪ t.io.outputs
S'.capabilities = S.capabilities ∪ t.capabilities
S'.cost = S.cost + t.cost
```

### 搜索策略

使用有优先队列，定义估计函数为：

```cmd
f(S) = S.cost + λ * h(S)
```

其中启发式函数h(S)设计为：

```bash
h(S) = |goal_capabilities - S.capabilities|
```

即：

- cost优先
- 其次优先减少未完成能力的数量

伪代码初步设计为：

```python
PQ.push(initial_state)

while PQ not empty:
    S = PQ.pop_min_f()

    if goal_capabilities ⊆ S.capabilities:
        return build_plan_from(S.path)

    for t in T_cand:
        if can_expand(S, t):
            S_new = expand(S, t)
            PQ.push(S_new)

return failure
```

## 动态调整算法

动态调整发生在Plan执行过程中，包括两个核心模块：

1. Replan(带前缀的在线再规划)
2. Patch(局部最小修改的工具替换/插入补丁)

## 动态执行算法


为提高可读性与可维护性，本系统将原本耦合在一起的“重试 → 补丁 → 再规划”流程拆分为
三个层级的执行器：

1. **Step Runner(步骤执行器)**: 负责一次工具调用与结果封装
2. **Patch Runner(补丁执行器)**: 负责在单步失败时控制重试与局部Patch
3. **Plan Runner(计划执行器)**: 负责按顺序或拓扑执行 Plan,并在必要时出发Replan

### Step Runner: 单次工具调用

Step Runner对应一个最小执行单元，其伪代码如下：

```python
def run_step(step: PlanStep, context: WorkflowContext) -> StepResult:
    """
    - 解析 step.inputs 中的引用（如 "S1.sequence"）为实际值；
    - 根据 step.tool 选择对应 ToolAdapter；
    - 调用底层执行引擎（例如 Nextflow 或本地 Python 工具）；
    - 捕获异常并统一封装为 StepResult，status ∈ {"success", "failed"}。
    """
    resolved_inputs = resolve_inputs(step.inputs, context.step_results)
    adapter = select_adapter(step.tool)
    try:
        raw_outputs, metrics = adapter.run(resolved_inputs)
        return StepResult(
            task_id=context.task.task_id,
            step_id=step.id,
            tool=step.tool,
            status="success",
            outputs=raw_outputs,
            metrics=metrics,
            ...
        )
    except Exception as e:
        return StepResult(
            task_id=context.task.task_id,
            step_id=step.id,
            tool=step.tool,
            status="failed",
            outputs={},
            metrics={"error": str(e)},
            ...
        )
```

### Patch Runner: 重试与局部修复

Patch Runner封装重试→Patch的决策逻辑，之对单步负责：

```python
def run_step_with_patch(plan: Plan, step_index: int, context: WorkflowContext -> tuple[Plan, StepResult]):
  # 1. 安全预检
    safety_result = SafetyAgent.precheck_step(step, context)
    if safety_result.action == "block":
        # 由上层 Plan Runner 决定是否触发 Replan
        return plan, build_blocked_step_result(step, safety_result)

    # 2. 重试循环
    for attempt in range(MAX_RETRY):
        result = run_step(step, context)
        if result.status == "success":
            return plan, result

    # 3. 重试失败 → 请求局部 Patch
    patch_request = build_patch_request(plan, step_index, context)
    patch = PlannerAgent.patch(patch_request)  # 生成 PlanPatch

    # 4. 在本地应用 PlanPatch（例如替换工具或插入过滤步骤）
    new_plan = apply_patch(plan, patch)
    patched_step = new_plan.steps[step_index]

    # 5. 对 patched_step 再执行一次 Step Runner
    patched_result = run_step(patched_step, context)
    return new_plan, patched_result
```

Patch Runner的输出可能是 原Plan+成功结果 , 也可能是 "更新后的Plan+失败后结果"  
由上层Plan Runner决定是否继续

### Plan Runner: 完整计划执行与Replan触发

Plan Runner负责按照顺序或依赖拓扑执行整个Plan,并在Patch仍无法修复时触发Replan:

```python
def run_plan(plan: Plan, context: WorkflowContext) -> Plan:
    k = 0
    while k < len(plan.steps):
        plan, step_result = run_step_with_patch(plan, k, context)
        context.step_results[step_result.step_id] = step_result

        # 安全后置检查
        safety_result = SafetyAgent.postcheck_step(step_result, context)
        context.safety_events.append(safety_result)

        if step_result.status != "success" or safety_result.action == "block":
            # 构造 ReplanRequest，锁定已成功的前缀
            replan_request = build_replan_request(plan, context, failed_step_index=k)
            new_plan = PlannerAgent.replan(replan_request)

            if new_plan is None:
                # 无可行新计划 → 交由上层工作流置任务为 FAILED
                break

            plan = new_plan
            k = find_first_unfinished_step_index(plan, context)
            continue

        k += 1

    return plan
```

通过上述三层分离，实现：

- Step Runner专注于如何执行每一步工具
- Patch Runner专注于在局部范围内如何自我修复
- Plan Runner专注于整体计划的推进与何时需要Replan

这使得动态调整算法能在实现层面更易于测试与扩展，也更清晰对应了Planner/Executor/Safety三类Agent的协同职责。

---

## Replan：带前缀锁定的在线再规划

这个过程是从Safety/Executor发起的"request_replan"，用于重新生成未完成的子计划

### ReplanRequest输入

```json
ReplanRequest:
  original_plan      : Plan
  step_results       : dict[step_id -> StepResult]
  safety_events      : list[SafetyEvent]
  failed_steps       : list[int]
```

### 前缀锁定

找到已经成功的前缀

```json
prefix = [s1, s2, ..., sk] where all results = success
```

### 剩余任务的重新定义

```json
remaining_capabilities = goal_capabilities - capabilities(prefix)
```

构建新的TaskSpec':

```json
TaskSpec':
  goal_capabilities = remaining_capabilities
  initial_artifacts = new_initial_io
  constraints: 剩余 cost/steps
  banned_tools = failed_steps ∪ tools_in(safety_block)
```

### 使用静态规划算法重新搜索子计划

调用同一套的前向启发搜索：

```json
suffix_path = search(TaskSpec')
new_plan = prefix + suffix_path
```

## 局部补丁：Patch

Patch是在某一步骤Sk执行失败后，由Executor调用Planner的局部修复窗口。一般只修改1～2个步骤，不改变整体计划结构

### PatchREquest

```json
PatchRequest:
  original_plan
  failed_step_index = k
  context_io        # Sk 前后的可用 JSON keys
  error_pattern     # 执行失败类型，如 input-too-long
  safety_events
```

### 候选替代工具

从KG中检索满足一下条件的工具：

```python
cand = {
  t for t in KG.tools
  if required_capability ∈ t.capabilities
     and t.id != tool(Sk).id
     and t.io.inputs ⊆ available_io_before_Sk
     and t.safety_level ≤ task.safety_level
}
```

### 候选评分

```json
score(t) =
    α * normalized_cost(t)
  + β * safety_penalty(t.safety_level)
  + γ * error_similarity(t, error_pattern)
```

其中，

- cost等级越低越好
- 安全等级越高惩罚越大
- 与失败工具相似度越高惩罚越大

### 生成PlanPatch

包括替换和插入过滤两种

#### 替换步骤

```json
{
  "op": "replace_step",
  "target": "Sk",
  "step": { "tool": "t_new", "inputs": ... }
}
```

#### 插入过滤步骤+替换

```json
[
  { "op": "insert_step_before", "target": "Sk", "step": FilterStep },
  { "op": "replace_step",       "target": "Sk", "step": NewStep     }
]
```

Executor在接受patch后在本地应用，然后继续微循环执行。