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

每个工具被设计为：

```json
Tool:
  id              : string
  capabilities    : set[str]  # 工具提供的能力
  io.inputs       : set[str]  # 需要的 JSON key
  io.outputs      : set[str]  # 产生的 JSON key
  cost            : float  # 资源/时间成本
  safety_level    : int  # 安全等级
```

工具图G=(T,E)构建规则是：

- 当`tool_j.io.inputs` $\subseteq$ `tool_i.io.outputs`时可以形成i->j的联通边
- 从虚拟起点START指向所有满足输入工具的节点

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

## 单步执行微循环

这个过程由Executor驱动，过程如：

1. 对Sk调用SafetyAgent进行预先审查
2. 若通过则执行工具
3. 若失败，则进入：retry->patch->fail的流程

伪代码如下：

```python
for k in range(len(plan.steps)):
    step = plan.steps[k]

    if not SafetyAgent.precheck(step):
        return request_replan()

    for attempt in range(MAX_RETRY):
        result = execute(step)
        if result.success:
            continue main_loop
        # 否则重试

    # 重试失败
    patch = Planner.patch(step)
    apply_patch(plan, patch)

    # 再次执行 patched step
    result = execute(step)
    if result.success:
        continue main_loop

    # patch 仍失败 → 触发 replan
    new_plan = Planner.replan(current_context)
    plan = new_plan
```

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