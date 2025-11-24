# Agent设计文档

本文档用于定义系统中四类核心Agent(Planner/Executor/Safety/Summarizer)的职责边界、输入输出契约、交互方式以及在整体工作流中的协作关系。

## Agent体系总览

### 角色列表

系统中定义四类核心Agent：

- PlannerAgent
  - 基于LLM+ProteinToolKG的任务规划者
  - 负责任务解析、工具链选择与Plan JSON生成
- ExecutorAgent
  - 计划执行者与调度器
  - 负责解析Plan JSON、构建步骤依赖并调用Tool Adapter
- SafetyAgent
  - 全程安全审查者
  - 负责输入/过程/输出的风险识别与阻断
- SummarizerAgent
  - 结果汇总与报告生成者
  - 负责汇总序列、结构、指标与安全信息，生成`DesignResult`结果汇总与报告

### 生命周期与协作概览

一次标准的任务生命周期：

1. 用户通过TaskAPI提交`ProteinDesignTask`
2. PlannserAgent基于任务与ProteinToolKG生成`Plan`
3. ExecutorAgent执行`Plan.steps`，逐步调用ToolAdapter
4. SafetyAgent在输入、关键步骤及输出阶段执行检查
5. SummarizerAgent汇总中间结果与风险信息，生成`DesignResult`和报告
6. 若执行中发生错误或高风险，PlannserAgent可通过`replan`/`patch`更新计划

## 接口定义

### 核心数据结构接口

#### ProteinDesignTask

```python
@dataclass
class ProteinDesignTask:
  task_id: str
  goal: str
  constraints: dict # e.g. {"length_range":[int, int]. "organism": str, "structure_template_pdb": str, "safety_level": "S1"}
  metadata: dict #e.g. {"created_by": str, "created_at": iso_datetime, ...}
```

#### Plan(Planner 输出)

```python
@dataclass
class PlanStep:
  id: str
  tool: str # 对应ProteinToolKG中的tool.id
  inputs: dict # 支持字面值+引用语法
  metadata: dict # 工具相关参数

@dataclass
class Plan:
  task_id: str
  steps: list[PlanStep]
  constraints: dict
  metadata: dict
```

#### StepResult(执行步骤结果)

```python
@dataclass
class StepResult:
  task_id: str
  step_id: str
  tool: str
  status: str # "success" | "failed" | "skipped"
  outputs: dict # {"sequence": str, "pdb_path": str, "plddt": float}
  metrics: dict
  ris_flags: list[dict] # 来自SafetyAgent
  logs_path: str | None
  timestamp: str # ISO datetime string
```

#### DesignResult(最终结果)

```python
@dataclass
class DesignResult:
  task_id: str
  sequence: str | None
  structure_pdb_path: str | None
  scores: dict
  risk_flags: list[dict]
  report_path: str
  metadata: dict
```

#### SafetyResult(安全检查结果)

```python
@dataclass
class RsikFlag:
  level: str # "warn" | "block"
  type: str
  detail: str

@dataclass
class SafetyResult:
  task_id: str
  phase: str # "input" | "step" | "output"
  scope: str # "task" | f"step:{step_id}" | "result"
  risk_flags: list[RsikFlag]
  action: str # "allow" | "warn" | "block"
  timestamp: str
```

#### WorkfolwContext(内部上下文)

```python
@dataclass
class WorkfolwContext:
  task: ProteinDesignTask
  paln: Plan | None
  step_result: dict[str, StepResult]
  safety_events: list[SafetyResult]
  design_result: DesignResult | None
```

### PlannerAgent接口

#### 对外主接口

##### 生成初始Plan

```python
class PlannerAgent:
  def plan(self, task: ProteinDesignTask) -> Plan:
    """
    输入：ProteinDesignTask
    输出:Plan

    行为：
    - 解析task.goal/task.constraints
    - 查询ProteinToolKG, 按照R1/R2/R3生成工具链
    - 组装Plan.step 与 constraints, metadata
    - 不进行任何工具调用，只构造JSON计划
    """
```

##### 再规划(replan)

```python
@dataclass
class ReplanRequest:
  task_id: str
  original_plan: Plan
  failed_steps: list[str]
  step_results: list[StepResult]
  safety_events: list[SafetyResult]
  reason: str

class PlannerAgent:
  def replan(self, request: ReplanRequest) -> Plan:
    """
      输入：ReplanRequest
      输出：新的Plan

      行为：
      - 分析失败原因
      - 基于ProteinToolKG选择替代工具链或修改约束
      - 维护task_id不变，更新steps/constraints/metadata
```

##### 局部patch(patch)

```python
@dataclass
class PlanPatch:
    task_id: str
    operations: list[dict]   # 例如: {"op": "replace_step", "target": "S2", "step": PlanStep(...)}
    metadata: dict

@dataclass
class PatchRequest:
    task_id: str
    original_plan: Plan
    context_step_results: list[StepResult]
    safety_events: list[SafetyResult]
    reason: str

class PlannerAgent:
    def patch(self, request: PatchRequest) -> PlanPatch:
        """
        输入: PatchRequest
        输出: PlanPatch

        行为:
        - 针对局部问题，生成 minimal change 集合:
          - replace_step
          - insert_step_before/after
          - replace_subplan 等
        - 确保 I/O 依赖不被破坏
        """

```

#### 内部依赖接口

Planner内部使用，不对外暴露，但需要在设计文档中点名

```python
class PlannerAgent:
    def _query_tools(self, capability: str, constraints: dict) -> list[dict]:
        """从 ProteinToolKG 中检索满足能力+约束的工具节点列表"""

    def _validate_io_chain(self, tools: list[dict]) -> bool:
        """校验工具链 I/O 兼容性 (R1)"""

    def _filter_by_safety(self, tools: list[dict], safety_level: str) -> list[dict]:
        """根据 safety_level 过滤工具 (R2)"""

    def _rank_by_cost(self, tool_chains: list[list[dict]]) -> list[list[dict]]:
        """根据 cost 对候选工具链排序 (R3)"""

```


