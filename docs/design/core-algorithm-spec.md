# 核心算法文件

## 算法要解决的问题

### 输入

#### `ProteinDesignTask taks`

- `goal.capabilities`: 需要完成的设计子任务集合（如`["de_novo_sequence", "structure_prediction", "property_eval"]`）
- `constrains`: `safety_level`, `max_cost`, `max_steps`
- `initial_artifacts`: 任务一开始就已经有的数据（比如给定结构、模板、序列等）

#### `ProteinToolKG G`

- 节点：工具`t`，包含：
  - `t.capabilities`: 比如`["sequence_generation"]`
  - `t.io.inputs`/`t.io.outputs`: 输入、输出JSON key类型
  - `t.safety_level`: 工具安全等级
  - `t.cost`: 抽象成本

### 输出

- 一个结构化的`Plan`:
  - `steps = [s1, s2, ..., sl]`
  - 每个 `si`指定：使用哪个工具、输入从哪一步来、输出写到哪些key.
  - 满足：
    - 所有中间步骤 I/O 兼容
    - 所有用到的工具 安全等级 <= task.safety_level(R2)
    - 在满足goal的情况下，令cost足够小

## 核心算法框架

框架采取：前向搜索 + 约束剪枝 + 成本排序

### 阶段0: 任务解析(Task Analysis)

由 `PlannerAgent` 完成。

1. 从自然语言/结构化输入中抽取：
   - `goal_capabilities`(比如需要"序列生成+结构预测+性能评估")
   - 安全约束`safety_level`
   - 资源约束`max_cost`、`max_steps`
2. 归一化为一个内部表示对象`TaskSpec`，供下面的算法使用

### 阶段1: 构建候选工具图(Tool Graph Construction)

1. 按能力召回候选工具
   - 对每个 `cap in goal_capacilities`:
     - 从 `ProteinToolKG` 里查找 `tools_cap[cap] = {t | cap in t.capabilities}`
   - 加上少量辅助工具，形成候选工具集合`T_cand`
2. 应用安全过滤
   - 丢弃所有 `t.safety_level > task.safety_level`的工具
3. 构建I/O兼容图
   - 图的定点是工具 $t \in T_{cand}$, 再加上一个虚拟起点 `START` 
   - 边规则：
     - 从 `START` 到 `t`：当 $t.io.inputs \subset initial_{artifacts}$ 连边
     - 从 `t1` 到 `tj`：当 `ti.io.outputs`覆盖 `tj.io.inputs`时连边
   - 每条边的权重可以简单设置为 `cost(tj)`, 整体cost就是沿path的工具cost之和

### 阶段2：在工具图上做有约束的最优路径搜索

核心算法：在上面的图上，找到一条/若干条路径，使得：

- 沿路径用到的工具集合 `U capabilities` 覆盖 `goal_capabilities`
- 满足 `steps <= max_steps`, `total_cost <= max_cost`
- `total_cost` 最小

目前选择的算法是：前向启发式搜索(best-first search) + 状态包含当前已获得能力集合

**状态定义**：  
每个搜索状态 `S` 包含：

- `S.path`: 已经选择的工具序列 `[t1, t2, t3, ..., tk]`
- `S.avaliable_io`: 目前可用的所有JSON Key(initial_artifacts $\cup$ 各工具 outputs)
- `S.capabilities`: 沿 path 积累获得的 `cap` 集合
- `S.cost`: 积累成本

初始状态：

- `path = []`
- `available_io = initial_artifacts`
- $capabilities = \emptyset$
- `cost = 0`

**扩展规则**：  
从状态 `S` 扩展：

- 遍历所有候选工具 $t \in T_{cand}$
  - (R2) `t.safety_level <= task.safety_level`
  - (R1) `t.io.inputs` $\subset$ `s.available_io`
  - 步数/成本约束：`len(S.path) + 1 <= max_steps` 且 `S.cost + t.cost <= max_cost`
- 对每个满足条件的 `t`:
  - `S' = S`的复制：
    - `S'.path = S.path + [t]`
    - `S'.available_io += t.io.outputs`
    - `S'.capabilities += t.capabilities`
    - `S'.cost = S.cost + t.cost`

**目标判定**:  

- 当 `goal_capabilities` $\subset$ `S.capabilities` 时，认为 `S` 是一个可行计划终点

可以选择：  

- 找到第一条符合条件的(贪心/启发式)
- 或者搜索若干条件候选路径，再做一次后处理排序(结合实际情况指标)

**搜索策略**:  
为了表达R3成本优先，使用一个优先队列(小顶堆)，按照如下的score来选择下一个扩展状态：

$score(S) = S.cost + \lambda * h(s)$

其中`h(S)`是一个简单的启发式函数，例如：

- `h(S) = 未满足的 cap 数 = |goal_capabilities \ S.capabilities|`
- 或者给不同能力加权，比如结构预测重要度更高

$\lambda$是一个权重，用来平衡“立刻满足越多能力”和“保持低成本”的权衡  
这样就有了一个**成本+目标完成度**双重考虑的**best-first**搜索。
