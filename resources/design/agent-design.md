---
doc_key: agent
version: 1.0
status: stable
depends_on: [arch]
---

# Agent设计文档

本文档用于定义系统中四类核心Agent(Planner/Executor/Safety/Summarizer)的职责边界、输入输出契约、交互方式以及在整体工作流中的协作关系。

## Agent体系总览
<!-- SID:agent.overview.introduction -->

### 角色列表
<!-- SID:agent.overview.roles -->

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
<!-- SID:agent.contracts.overview -->

### 核心数据结构接口

#### ProteinDesignTask
<!-- SID:agent.contracts.protein_design_task -->

```python
@dataclass
class ProteinDesignTask:
  task_id: str
  goal: str
  constraints: dict # e.g. {"length_range":[int, int]. "organism": str, "structure_template_pdb": str, "safety_level": "S1"}
  metadata: dict #e.g. {"created_by": str, "created_at": iso_datetime, ...}
```

#### Plan(Planner 输出)
<!-- SID:agent.contracts.plan -->

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
<!-- SID:agent.contracts.step_result -->

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
<!-- SID:agent.contracts.design_result -->

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
<!-- SID:agent.contracts.safety_result -->

```python
@dataclass
class RiskFlag:
  level: "ok" | "warn" | "block" # "warn" | "block"
  code : string
  message: string
  scope: "input" | "step" | "output" | "task"
  step_id: optional
  details: dict
  

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
<!-- SID:planner.interface.overview -->

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

## Human-in-the-loop 扩展设计（Agent 行为层）
<!-- SID:agent.hitl.overview -->

本节在不破坏既有多 Agent 自动协作逻辑的前提下，引入 Human-in-the-loop（HITL）机制，
明确各 Agent 在"需要人工决策"的场景下应承担的职责、触发条件与行为边界。

设计原则如下：

- 人类被视为一种**外部决策 Agent（External Decision Agent）**；
- 系统内部 Agent **不直接与人类交互**；
- 所有人工介入均通过结构化的 `PendingAction / Decision` 完成（详见 [ref:SID:arch.contracts.pending_action]）；
- Agent 只负责：
  - 发现问题
  - 生成候选方案
  - 提出系统建议
  而不负责"等待"或"选择"。

---

### 1. PlannerAgent 在 HITL 场景下的职责
<!-- SID:planner.hitl.responsibilities -->

PlannerAgent 仍然是**计划搜索与重规划的唯一负责者**，Human-in-the-loop 不改变其核心算法职责，
仅改变"计划如何被最终确认"的路径。

#### 1.1 初始 Plan 阶段（WAITING_PLAN_CONFIRM）
<!-- SID:planner.hitl.plan_confirm -->

在以下条件之一满足时，PlannerAgent **必须创建 PendingAction(plan_confirm)**，而非直接进入执行：

- 系统配置要求 `require_plan_confirm = true`；
- Plan 中包含高风险 / 高成本工具组合；
- SafetyAgent 对初始 Plan 给出 `warn` 级以上提示。

PlannerAgent 的职责包括：

- 生成一个或多个 Plan 候选（可包含 Top-K 次优解）；
- 为每个候选生成：
  - 结构化摘要（工具链、关键参数、预期产物）
  - 风险等级与成本估计；
- 给出系统默认建议（例如推荐某一 Plan）；
- 将上述信息封装进 `PendingAction(action_type = plan_confirm)`。

<!-- SID:planner.responsibilities.must BEGIN -->
PlannerAgent **必须**：

- 生成一个或多个 Plan 候选（可包含 Top-K 次优解）；
- 为每个候选生成结构化摘要、风险等级与成本估计；
- 给出系统默认建议；
- 将上述信息封装进 `PendingAction`。
<!-- SID:planner.responsibilities.must END -->

<!-- SID:planner.responsibilities.must_not BEGIN -->
PlannerAgent **不得**：

- 在未收到 Decision 的情况下自行选择 Plan；
- 直接修改 Task 状态为 `PLANNED`。
<!-- SID:planner.responsibilities.must_not END -->

---

#### 1.2 重规划阶段（WAITING_REPLAN_CONFIRM）

当执行过程中进入整体 Replan 逻辑时（例如 SafetyAgent 判定高风险）：

- PlannerAgent 负责生成 Replan 候选集合；
- 每个候选通常对应：
  - 新的 Plan 后缀
  - 或整体 Plan 的替换方案；
- PlannerAgent 必须将 Replan 候选封装进 `PendingAction(action_type = replan_confirm)`。

在该阶段，PlannerAgent **只负责“给出选项”**，是否采用 Replan 由人类通过 Decision 决定。

---

### 2. ExecutorAgent 在 HITL 场景下的职责
<!-- SID:executor.hitl.responsibilities -->

ExecutorAgent 负责**执行控制与失败检测**，但不具备决策权。

#### 2.1 Patch 触发与 WAITING_PATCH_CONFIRM
<!-- SID:executor.hitl.patch_confirm -->

当 ExecutorAgent 发现以下情况之一：

- 某步骤超过最大重试次数仍失败；
- 工具返回可修复型错误（例如参数不稳定、输入边界问题）；

ExecutorAgent 应：

1. 停止继续执行后续步骤；
2. 触发 PlannerAgent 生成一个或多个 Patch 候选；
3. 将任务状态推进至 `WAITING_PATCH`（实现层）；
4. 由系统创建 `PendingAction(action_type = patch_confirm)`。

<!-- SID:executor.responsibilities.must BEGIN -->
ExecutorAgent **必须**：

- 停止继续执行后续步骤；
- 触发 PlannerAgent 生成Patch候选；
- 将任务状态推进至 WAITING_PATCH；
- 由系统创建 PendingAction。
<!-- SID:executor.responsibilities.must END -->

<!-- SID:executor.responsibilities.must_not BEGIN -->
ExecutorAgent **不得**：

- 自行决定应用 Patch；
- 在 WAITING_* 状态下继续执行任何工具调用。
<!-- SID:executor.responsibilities.must_not END -->

---

#### 2.2 Decision 生效后的执行恢复

当系统接收到 `Decision` 并完成应用后：

- 若 Decision 导致状态回到 `RUNNING`：
  - ExecutorAgent 从最新 `TaskSnapshot` 恢复执行；
  - 根据内部状态进入 `PATCHING` 或继续原 Plan；
- 若 Decision 导致状态进入 `PLANNING`：
  - ExecutorAgent 结束当前执行上下文，等待 PlannerAgent 重新规划。

---

### 3. SafetyAgent 在 HITL 场景下的职责
<!-- SID:safety.hitl.responsibilities -->

SafetyAgent 是 **HITL 触发的重要信号源**，但仍保持"建议者"角色。

#### 3.1 触发 WAITING_REPLAN_CONFIRM 的条件
<!-- SID:safety.hitl.replan_trigger -->

当 SafetyAgent 在任意阶段返回以下结果之一：

- `block`（明确禁止继续执行）；
- 高置信度 `warn`（例如目标偏离、潜在结构风险、伦理/安全问题）；

SafetyAgent 应：

- 向系统提交风险评估结果；
- 明确标注：
  - 风险来源
  - 风险等级
  - 是否建议 Replan；
- 触发系统进入 `WAITING_REPLAN_CONFIRM`。

<!-- SID:safety.responsibilities.must BEGIN -->
SafetyAgent **必须**：

- 向系统提交风险评估结果；
- 明确标注风险来源、风险等级、是否建议 Replan；
- 触发系统进入 WAITING_REPLAN_CONFIRM。
<!-- SID:safety.responsibilities.must END -->

<!-- SID:safety.responsibilities.must_not BEGIN -->
SafetyAgent **不得**：

- 自行终止任务；
- 自行决定是否 Replan；
- 直接修改 Plan。
<!-- SID:safety.responsibilities.must_not END -->

---

### 4. SummarizerAgent 与 HITL 的关系
<!-- SID:summarizer.hitl.responsibilities -->

SummarizerAgent 不参与任何人工决策流程。

<!-- SID:summarizer.responsibilities.must BEGIN -->
SummarizerAgent **必须**：

- 仅在任务进入 `SUMMARIZING` 后启动；
- 明确区分执行结果（DesignResult）与展示产物（图表、可视化、报告文本）。
<!-- SID:summarizer.responsibilities.must END -->

<!-- SID:summarizer.responsibilities.must_not BEGIN -->
SummarizerAgent **不得**：

- 影响任务的执行结果有效性（即使Summarizer失败，执行结果仍有效）；
- 参与任何人工决策流程。
<!-- SID:summarizer.responsibilities.must_not END -->

---

### 5. Agent 层统一约束（必须遵守）
<!-- SID:agent.hitl.universal_constraints BEGIN -->

为确保 HITL 机制的可控性与一致性，所有 Agent 必须遵守以下规则：

1. Agent **不得直接等待人工输入**；
2. Agent **不得直接与 UI / 人类交互**；
3. 所有人工介入点必须：
   - 显式对应一个 `PendingAction`（详见 [ref:SID:arch.contracts.pending_action]）；
   - 显式对应 FSM 中的 `WAITING_*` 状态（详见 [ref:SID:fsm.states.definitions]）；
4. Agent 的职责边界为：
   - 发现问题
   - 生成候选
   - 给出系统建议
   而非做最终决策；
5. 任意绕过 PendingAction / Decision 的人工干预均视为架构违例。

通过上述设计，Human-in-the-loop 被严格限制在少数高价值、高风险的决策节点，
而系统在绝大多数情况下仍保持全自动执行能力。
<!-- SID:agent.hitl.universal_constraints END -->

