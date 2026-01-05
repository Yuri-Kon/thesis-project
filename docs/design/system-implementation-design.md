---
doc_key: impl
version: 1.0
status: stable
depends_on: [arch, agent]
---

# 系统实现设计文档

> 目标：在现有架构的算法设计基础上，明确技术选型、代码结构、组件职责、运行时流程，指导后续代码编码与集成

## 系统总体概览
<!-- SID:impl.overview.introduction -->

核心Agent与数据契约已在 [ref:SID:agent.overview.introduction] 中定义。本设计文档在此基础上，加入具体框架实现细节。

系统分为五层：输入层、智能规划层、执行层、安全与汇总层、资源层

- 输入层: 用户/脚本, 通过自然语言+结构化约束描述蛋白质设计任务
- 智能规划层：解析任务、查询ProteinToolKG, 生成`Plan` Json
- 执行层：按步骤调用ProteinMPNN等工具
- 安全与汇总层: 贯穿安全审查、生成DesignResult与报告
- 资源层: ProteinToolKG、模型库、数据/日志/中间产物存储

核心Agent与数据契约已经在agent-design中定义。  
本设计文档在此基础上，加入具体框架, 尤其是：  

- 使用LangGraph实现LLM多Agent调度;
- 引入Nextflow作为底层计算工作流引擎；
- 明确ToolAdapter的容器化执行方式；
- 引入Fluent进行交互式可视化
- 设计任务/日志存储、KG访问、API层等

---

## 技术栈与框架选型
<!-- SID:impl.techstack.overview -->

### 关键框架与组件

#### LLM与多Agent调度

- LLM接入：OpenAI API/本地兼容OpenAI接口的服务
- 多Agent调度: LangGraph
  - 将`Planner/Executor/Safety/Summarizer`实现graph节点；
  - 管理对话状态、Plan状态与replan/patch流程

#### 工作流引擎

- Nextflow
  - 管理重计算任务
  - 与容器结合，实现可复现的计算环境

#### Web/API层

- FastAPI
  - 暴露`POST /tasks`、`GET /tasks/{id}`、`GET /tasks/{id}/report`等接口；
  - 与LangGraph驱动的workflow交互

#### 工具知识图谱

- 初期：JSON文件形式
- 后期: 迁移到Neo4j图数据库
  - 使用Neo4j官方的Python dirver
  - 支持I/O兼容性、能力、成本、安全等级等维度的图查询

#### 任务&状态存储

- 数据库：开发阶段用SQLite + SQLAlchemy, 后期可换PostgreSQL;
- 存储内容：任务基本信息、Plan snapshot、StepResult摘要、风险事件等

#### 文件与实验追踪

- 文件：本地目录，结构参考architecture.pdf

#### 交互式可视化工具

FluentPlot: 系统计划引入一类交互式可视化工具，对蛋白质结构、评估指标以及任务执行过程进行图形化呈现。

#### 生物 & 化学工具

- ProteinMPNN
- ESMFold
- RDKit
- BioPython

---

## 模块划分与代码结构

### 顶层目录建议

```text
project-root/
  docs/
    design/
      system-implementation-design.md
      ...
  src/
    api/
      main.py
      schemas.py
    workflow/
      graph.py
      context.py
    agents/
      planner.py
      executor.py
      safety.py
      summarizer.py
    kg/
      protein_tool_kg.json
      kg_client.py
    adapters/
      base_tool_adapter.py
      registry.py
      builtins.py
      dummy_adapter.py
    tools/
      visualization/
        adapter.py
        pipeline.py
      ...
    engines/
      nextfolw_adapter.py
    models/
      contracts.py
      db.py
    storage/
      filestore.py
      log_store.py
  nf/
    main.nf
    modules/
      protein_mpnn.nf
      esmfold.nf
      rdkit_props.nf
  data/
    inputs/
    logs/
  output/
    pdb/
    metrics/
    artifacts/
    reports/
```

---

产物目录统一放在 `output/` 下，按类型分子目录（`pdb/`、`metrics/`、`artifacts/`、`reports/`），文件名需包含 `task_id` 便于检索与追踪。

### ToolAdapter 分层实现与 tools/ 模块

为保持执行层与具体工具实现解耦，适配器采用“两层结构”：

- **Adapter 基础层**：位于 `src/adapters/`
  - 定义 `BaseToolAdapter` 接口与 `AdapterRegistry`
  - 负责适配器注册、检索与统一执行入口
- **工具实现层**：位于 `src/tools/<tool>/`
  - `adapter.py` 实现具体工具的输入解析(`resolve_inputs`)与执行(`run_local`)
  - 工具 pipeline、脚本与产物结构放在同一工具目录内（如 `pipeline.py`）

Executor/StepRunner 只依赖基础层接口，通过 `tool_id`/`adapter_id` 获取适配器执行，
从而避免在执行层直接绑定具体工具细节。

### 数据契约层(`src/models/contracts.py`)

依据 agent-design定义 dataclass/Pydantic:

```python
from pydantic import BaseModel
from typing import Dict, List, Optional

class ProteinDesignTask(BaseModel):
  task_id: str
  goal: str
  constraints: Dict
  metadata: Dict

class PlanStep(BaseModel):
  id: str
  tool: str
  inputs: Dict
  metadata: Dict

class Plan(BaseModel):
  task_id: str
  steps: List[PlanStep]
  constraints: Dict
  metadata: Dict

class StepResult(BaseModel):
    task_id: str
    step_id: str
    tool: str
    status: str       # "success" | "failed" | "skipped"
    outputs: Dict
    metrics: Dict
    risk_flags: List[Dict]
    logs_path: Optional[str]
    timestamp: str

class DesignResult(BaseModel):
    task_id: str
    sequence: Optional[str]
    structure_pdb_path: Optional[str]
    scores: Dict
    risk_flags: List[Dict]
    report_path: str
    metadata: Dictclass
```

#### PendingAction 与 Decision 模型

核心概念定义详见 [ref:SID:arch.contracts.pending_action] 和 [ref:SID:arch.contracts.decision]。以下为 Pydantic 实现：

为了统一建模“等待人工输入”这一行为，本系统在实现层引入 `PendingAction` 与 `Decision`
两个一等数据结构，用于承载 Human-in-the-loop 的交互信息。

- `PendingAction`：描述“系统已经准备好一组候选方案，但需要人来做决策”的状态；
- `Decision`：描述“人类针对某个 PendingAction 做出的具体选择”。

二者与 FSM 的关系如下：

- 当任务状态进入 `WAITING_PLAN_CONFIRM` / `WAITING_PATCH` / `WAITING_REPLAN` 时：
  - 创建一条 `PendingAction` 记录；
  - 任务执行暂停，Executor 不再向前推进；
- 当人类提交决策后：
  - 写入一条 `Decision` 记录；
  - 更新相应的 Plan / PlanPatch / Replan；
  - 驱动 FSM 进行下一步状态转移（如回到 `RUNNING` 或重新进入 `PLANNING`）。

推荐的数据模型示意如下（以 Pydantic 为例）：

```python
from enum import Enum
from datetime import datetime
from pydantic import BaseModel
from typing import Dict, List, Optional


class PendingActionType(str, Enum):
    PLAN_CONFIRM = "plan_confirm"     # 初始 Plan 确认
    PATCH_CONFIRM = "patch_confirm"   # 局部 Patch 应用确认
    REPLAN_CONFIRM = "replan_confirm" # 整体 Replan 确认


class PendingActionStatus(str, Enum):
    PENDING = "pending"
    DECIDED = "decided"
    CANCELLED = "cancelled"


class PendingAction(BaseModel):
    """
    表示一次等待人工决策的挂起动作。
    进入任意 WAITING_* 状态时，必须创建一条 PendingAction。
    """
    id: str
    task_id: str

    action_type: PendingActionType
    status: PendingActionStatus = PendingActionStatus.PENDING

    # 根据 action_type，不同候选可以是 Plan / PlanPatch / Replan 的摘要
    candidates: List[Dict]  # 具体结构在 Planner 部分定义，如 {"id": "...", "summary": "...", ...}

    # 系统给出的默认建议（例如推荐某个候选、建议终止等）
    default_suggestion: Optional[str] = None

    # 由 LLM 生成的补充解释信息，帮助科研人员理解候选差异
    explanation: Optional[str] = None

    created_at: datetime
    decided_at: Optional[datetime] = None
    created_by: str = "system"  # 一般由系统创建
```

`Desicion` 用于记录科研人员对 PendingAction 的操作: 

```python
class DecisionChoice(str, Enum):
    ACCEPT = "accept"       # 接受候选方案（如应用 Patch / 采用某个 Plan）
    REJECT = "reject"       # 拒绝当前候选
    REPLAN = "replan"       # 要求重新规划（用于 plan_confirm / patch_confirm 等场景）
    CONTINUE = "continue"   # 继续当前策略（用于 replan_confirm：决定不重规划）
    CANCEL = "cancel"       # 终止任务


class Decision(BaseModel):
    """
    表示针对某个 PendingAction 的一次人工决策。
    """
    id: str
    task_id: str
    pending_action_id: str

    choice: DecisionChoice

    # 若 choice = ACCEPT，则指向被选中的候选 id
    selected_candidate_id: Optional[str] = None

    # 决策人（科研人员）标识，可与外部用户系统对接
    decided_by: str

    comment: Optional[str] = None  # 备注/原因说明
    decided_at: datetime
```

在具体实现中，可以根据需要将 `candidates: List[Dict]` 进一步细化为:

- `PlanCandidate`(封装 Plan 的摘要与关键指标)
- `PatchCandidate`(封装 PlanPatch 的摘要)
- `ReplanCandidate`(封装 Replan 后缀的摘要)

本设计文档中先用 `Dict` 占位，保留实现灵活性

---

#### TaskSnapshot 模型

核心概念定义详见 [ref:SID:arch.contracts.task_snapshot]。以下为 Pydantic 实现：

为支持任务快照与可恢复执行，本系统对每个任务在关键节点写入一份 `TaskSnapshot` 记录，用于在系统重启或显式恢复时还原上下文

`TaskSnapshot` 的核心字段包括:

- 当前任务状态(FSM 状态)
- 当前 Plan 版本及其标识
- 已完成步骤的索引/列表
- 关键 artifacts(中间产物、结果文件) 的存储路径
- 若当前处于等待人工决策阶段，则关联 `pending_action_id`

示例模型:  

```python
class TaskSnapshot(BaseModel):
    """
    任务在某一时间点的最小可恢复上下文。
    """
    id: str
    task_id: str

    # 对应 FSM 中的当前状态，例如 RUNNING / WAITING_PLAN_CONFIRM / WAITING_PATCH 等
    state: str

    # Plan 版本号或哈希，用于指向当前执行的 Plan
    plan_version: Optional[str] = None

    # 当前已执行完成的步骤索引（例如 0-based index）
    current_step_index: int = 0

    # 已完成步骤的 id 列表（可选，用于更精细的恢复）
    completed_step_ids: List[str] = []

    # 关键中间产物、结果文件的路径映射
    # 例如 {"design_dir": "output/task_xxx/", "mpnn_result": "..."}
    artifacts: Dict[str, str] = {}

    # 若当前处于 WAITING_* 状态，可关联当前的 PendingAction
    pending_action_id: Optional[str] = None

    created_at: datetime
```

约束约定:  

- 进入任意的 `WAITING_*` 状态前必须写入一份最新的 `TaskSnapshot`
- 从快照恢复时：
  - 根据 `state` 决定个是否继续执行、继续等待决策、还是直接终止
  - 依赖  `plan_version`/`current_step_index`/`artifacts` 重建执行上下文

后续在执行层设计中，将给出 "何时写入快照" 和 "如何从快照恢复" 的具体流程

### API层(`src/api/main/py`)

API 层对外暴露任务生命周期的访问接口。为保证与内部状态机（FSM）一致，本系统采用一套
统一的任务状态字段、错误响应格式与任务视图结构。

所有API均返回JSON,编码为UTF-8

FastAPI负责对外暴露REST接口：

- `POST /tasks`: 创建新设计任务
  - 请求体：`ProteinDesignTask`(不包含task_id, 由任务生成)
  - 行为：写入DB→调用LangGraph workflow异步启动
- `GET /tasks/{task_id}`
  - 返回：任务基本ixnxi + 当前任务状态(PLANNED/RUNNING/DONE/FAILED) + summary
- `GET /tasks/{task_id}/report`: 返回`DesignResult` + 报告文件路径/内容

TaskAPI在architecture中已经有概念性描述，这里是具体实现

#### 任务状态枚举(对齐FSM)

为支持 Human-in-the-loop（人工审查）并保持架构层 FSM 与实现层 FSM 的一致性，API 层采用
“对外语义状态（ExternalStatus）+ 内部执行状态（InternalStatus）”的双层表示：

- **ExternalStatus**: 对挖暴露给 UI/CLI/用户的语义状态
- **InternalStatus**: 执行引擎内部调度状态(更细粒度，用于实现 patch/replan 流程)

##### ExternalStatus(API 对外暴露)

```json
CREATED
PLANNING
WAITING_PLAN_CONFIRM
PLANNED
RUNNING
WAITING_PATCH_CONFIRM
WAITING_REPLAN_CONFIRM
SUMMARIZING
DONE
FAILED
CANCELLED
```

##### InternalStatus(执行器内部使用，可选暴露)

```json
CREATED
PLANNING
PLANNED
RUNNING
WAITING_PATCH
PATCHING
WAITING_REPLAN
REPLANNING
SUMMARIZING
DONE
FAILED
CANCELLED
```

##### 映射时的状态(Internal → External)

- `WAITING_PATCH` / `PATCHING` 映射为 `WAITING_PATCH_CONFIRM`(对外语义：等待人工输入是否应用Patch)
- `WAITING_REPLAN` / `REPLANNING` 映射为 `WAITING_REPLAN_CONFIRM`(对外语义：等待人工决策是否 Replan)

约束：

- API 响应字段 `status` 必须使用 ExternalStatus
- 若需要调试/追踪，可附加字段 `internal_status`, 但不得替换 `status`
- 当 `status` 为任意 `WAITING_*` 时，响应中必须包含 `pending_action`(见 REST API 规范)

所有接口中返回的字段 `status` 必须严格使用以上枚举值

---

#### REST API 规范
<!-- SID:api.rest.overview -->

##### POST /tasks
<!-- SID:api.rest.create_task -->

创建一个新的蛋白质设计任务。该接口必须快速返回(不等待完整流程)

**请求体**：

```json
{
  "query": "设计一个...",
  "constraints": {
    "target_length": 120,
    "motifs": ["..."],
    "tools_allowed": ["protein_mpnn", "esmfold"]
  },
  "options": {
    "require_plan_confirm": true
  }
}
```

字段说明：

- `query`: 自然语言任务描述
- `constraints`: 结构化约束(可为空)
- `options.require_plan_confirm`: 是否要求初始 Plan 必须经过人工确认(用于强制进入 `WAITING_PLAN_CONFIRM`)

响应(201):

```json
{
  "task_id": "task_20250201_001",
  "status": "CREATED"
}
```

约束：

- 任务创建成功后，Workflow 会将任务推进到 `PLANNING`(异步调度)
- 任务创建失败返回 4xx/5xx, 并提供统一错误格式

处理流程：

1. 生成新的task_id
2. 写入数据库(Task.status = "CREATED")
3. 调用 LangGraph workflow 启动任务(状态变为PLANNING)
4. 返回任务基本信息

响应：

```json
{
  "task_id": "task_20260201_001",
  "status": "CREATED",
  "message": "Task created successfully and planning has started."
}
```

---

##### GET /tasks/{task_id}

查询任务状态(包含Plan、StepResult摘要与Safety事件)。  
该接口用于 "快速响应": 始终返回当前状态与下一步需要的信息。

响应(200)：

```json
{
  "task_id": "task_20250201_001",
  "status": "RUNNING",
  "internal_status": "RUNNING"
  "plan_version": 2,
  "current_step": "S3",
  "steps": [
    {
      "step_id": "S1",
      "tool": "protein_mpnn",
      "status": "success",
      "metrics": {"duration_ms": 5234}
    },
    {
      "step_id": "S2",
      "tool": "esmfold",
      "status": "success",
      "metrics": {"plddt": 0.83}
    }
  ],
  "safety_events": [
    {
      "level": "warn",
      "code": "SEQ_LENGTH_WARNING",
      "message": "Sequence length near upper constraint."
    }
  ],
  "pending_action": null,
  "scores": {"plddt": 0.85, "hydrophobicity": 0.42},
  "risk_flags": [],
  "report_path": "output/reports/task_20250201_001.md"
}
```

当任务处于等待人工决策阶段(`status` 为任意 `WAITING_*`)时， `pending_action` 必须为非空:

```json
{
  "task_id": "task_20250201_002",
  "status": "WAITING_PATCH_CONFIRM",
  "internal_status": "WAITING_PATCH",
  "plan_version": 3,
  "current_step": "S5",
  "steps": [],
  "safety_events": [],
  "pending_action": {
    "pending_action_id": "pa_000123",
    "action_type": "patch_confirm",
    "candidates": [
      {"candidate_id": "patch_a", "summary": "降低采样温度，重跑ProteinMPNN", "risk": "low", "cost_est": "medium"},
      {"candidate_id": "patch_b", "summary": "替换折叠工具为ESMFold-lite", "risk": "medium", "cost_est": "low"}
    ],
    "default_suggestion": "patch_a",
    "explanation": "..."
  },
  "report_path": null
}
```

约束：

- `status`: 必须为 ExternalStatus
- `internal_status`: 可选返回(用于审计/调试), 但不作为对外状态的判断依据
- 若 `status` 为 `WAITING_PLAN_CONFIRM` / `WAITING_PATCH_CONFIRM` / `WAITING_REPLAN_CONFIRM`:
  - `pending_action` 必须存在
  - `pending_action.action_type` 必须与 `status` 匹配

---

##### GET /pending-actions
<!-- SID:api.rest.get_pending_actions -->

列出所有当前等待人工决策的 PendingAction (用于 UI 的待办列表)

查询参数(可选):

- `status`: 默认 `pending`
- `task_id`: 按任务过滤

响应（200）：

```json
[
  {
    "pending_action_id": "pa_000123",
    "task_id": "task_20250201_002",
    "action_type": "patch_confirm",
    "created_at": "2025-02-01T12:00:00Z",
    "summary": "Step S5 重试失败，提供 2 个 Patch 候选"
  }
]
```

约束：

- 仅返回 `PendingActionStatus = pending` 的记录(除非显式过滤)
- 返回内容为摘要，候选详情以 `GET /tasks/{task_id}` 的 `pending_action` 或数据库读取为准

##### POST /pending-actions/{pending_action_id}/decision
<!-- SID:api.rest.submit_decision -->

提交人工决策（Decision），用于解除任务在 `WAITING_*` 状态的挂起，并驱动 FSM 继续执行。

请求体：

```json
{
  "choice": "accept",
  "selected_candidate_id": "patch_a",
  "comment": "先走低风险方案",
  "decided_by": "user_001"
}
```

响应(200):

```json
{
  "task_id": "task_20250201_002",
  "status": "RUNNING",
  "internal_status": "PATCHING",
  "pending_action": null
}
```

约束(必须严格执行):

1. PendingAction 必须存在且 `status = pending`, 否则返回 409
2. Task 当前 ExternalStatus 必须与 PendingAction.action_type 匹配，否则返回 409:
  - `plan_confirm`: `WAITING_PLAN_CONFIRM`
  - `patch_confirm`: `WAITING_PATCH_CONFIRM`
  - `replan_confirm`: `WAITING_REPLAN_CONFIRM`
3. Decision 受 action_type 约束:
  - `plan_confirm`: 允许 `accept` / `replan` / `cancel`
  - `patch_confirm`: 允许 `accept` / `replan` / `cancel`
  - `replan_confirm`: 允许 `accept` / `continue` / `cancel`
4. Side Effects(提交决策后必须发生的持久化动作)
  - 写入 `Decision` 记录
  - 将 PendingAction 标记为 `decided`
  - 追加 EventLog：`DECISION_APPLIED`
  - 更新 TaskSnapshot（至少写一次）：记录新的状态与关键选择
5. 状态转移(外部语义): 
  - `WAITING_PLAN_CONFIRM` + `accept` → `PLANNED`
  - `WAITING_PLAN_CONFIRM` + `replan` → `PLANNING`
  - `WAITING_PATCH_CONFIRM` + `accept` → `RUNNING`（内部进入 PATCHING 后回到 RUNNING）
  - `WAITING_PATCH_CONFIRM` + `replan` → `WAITING_REPLAN_CONFIRM`（或直接 `PLANNING`，由实现策略决定，但必须一致）
  - `WAITING_REPLAN_CONFIRM` + `accept` → `PLANNING`
  - `WAITING_REPLAN_CONFIRM` + `continue` → `RUNNING`
  - 任意 `WAITING_*` + `cancel` → `CANCELLED`

##### GET /tasks/{task_id}/report
<!-- SID:api.rest.get_report -->

在任务完成后返回DesignResult

成功响应：

```json
{
  "task_id": "task_20250201_001",
  "sequence": "MKTW...QG",
  "structure_pdb_path": "output/pdb/task_20250201_001_final.pdb",
  "scores": {
    "plddt": 0.85,
    "hydrophobicity": 0.42
  },
  "risk_flags": [],
  "report_path": "output/reports/task_20250201_001.md"
}
```

若任务尚未完成(非DONE或FAILED)

```json
{
  "error": "Report not available.",
  "status": "RUNNING"
}
```

---

#### 错误模型(Error Model)

所有错误均使用HTTP状态码 + JSON错误结构：

**404--Task Not Found**:

```json
{
  "error": "Task not found",
  "task_id": "task_20250201_999"
}
```

**400--Invalid Request**:

例如字段缺失、非法类型、违反安全输入规则

```json
{
  "error": "Invalid request: goal is required",
  "field": "goal"
}
```

**500--Internal Error**:

包括未捕获异常、工具执行错误：

```json
{
  "error": "Internal server error",
  "message": "Executor failed unexpectedly"
}
```

---

#### 数据库模型(与API & FSM 对齐)

**Task表**:

| 字段名            | 类型       | 说明                     |
| -------------- | -------- | ---------------------- |
| `task_id`      | str      | 主键                     |
| `goal`         | str      | 任务目标（已解析或原始文本）         |
| `constraints`  | JSON     | 任务约束                   |
| `status`       | str      | FSM 状态（CREATED…FAILED） |
| `plan_version` | int      | 当前 Plan 版本号            |
| `created_at`   | datetime |                        |
| `updated_at`   | datetime |                        |
| `last_error`   | str?     | 若任务失败，记录原因摘要           |

**PlannerSnapshot表**:

| 字段         | 说明             |
| ---------- | -------------- |
| task_id    | 外键             |
| plan_json  | 当前 Plan 的 JSON |
| version    | Plan 版本号       |
| created_at |                |

**StepSummary表**:

| 字段           | 说明                |
| ------------ | ----------------- |
| task_id      | 外键                |
| step_id      | 如 S1/S2/S3        |
| tool         | 执行工具              |
| status       | success / failed  |
| metrics_json | 简单指标摘要            |
| risk_level   | ok / warn / block |
| created_at   |                   |

#### API / DB / FSM / 日志的对齐关系

| 概念           | 来源                      | 使用位置                              |
| ------------ | ----------------------- | --------------------------------- |
| FSM 状态枚举     | 状态机设计                   | API.status / DB.status / 日志.state |
| Plan 版本号     | Planner.replan          | DB.plan_version / 日志.plan_version |
| StepSummary  | Executor 微循环            | GET /tasks 返回 steps[]             |
| SafetyEvents | SafetyAgent             | GET /tasks 返回 safety_events[]     |
| 日志流          | Executor+Planner+Safety | 调试 & timeline 回放                  |

API 的行为必须 完全反映内部状态机，不能出现“API 说运行中但内部已失败”等不一致现象。

---

### LangGraph 工作流(`src/workflow/graph.py`)

#### 节点设计

- palnner_node → 调用 `PlannerAgent`
- executor_node → 调用 `ExecutorAgent`
- safety_node → 调用 `SafetyAgent`
- summarizer_node → 调用 `SummarizerAgent`

整体是一个有状态图，执行逻辑与 architecture.pdf中的端到端闭环时序图一致

#### 状态内容

Graph state包含：

- 当前 `ProteinDesignTask`
- 当前 `Plan`
- 已完成 `StepResult`列表
- 最近一次 `SafetyResult`
- 当前任务状态 (PLANNED/RUNNING/WAITING_REPLAN/DONE/FAILED)

#### 控制流规则

1. `planner_node`:
   1. 若无plan: 调用静态规划  → 生成初始`Plan`(调用 core-algorithm-spec中的search)
   2. 若有replan请求：调用Replan逻辑，锁定前缀，重新规划suffix
2. `executor_node`:
   1. 逐步执行Plan中的步骤，将单步循环交给ExecutorAgent
3. `safety_node`:
   1. 在关键节点做检查，返回风险标记
   2. 若risk_flags中包含`block`，向graph发出`request_replan`事件
4. `summarizer_node`
   1. 在任务完成或终止时，汇总所有StepResult + Safety事件，生成一个`DesignResult`

---

### 任务生命周期与状态机设计

为避免在多 Agent 协作与重试 / 再规划过程中出现状态混乱，本系统将蛋白质设计任务的
生命周期形式化为一个有限状态机（Finite State Machine, FSM）。所有 Agent 的行为都只
能在 FSM 允许的状态及状态转移下执行。

#### 任务状态定义

| 状态                 | 含义说明                                                                 |
|----------------------|--------------------------------------------------------------------------|
| `CREATED`            | 任务已在 API 层创建，但尚未进入规划流程。                               |
| `PLANNING`           | PlannerAgent 正在生成初始 Plan。                                        |
| `PLANNED`            | 初始 Plan 已生成，等待执行。                                            |
| `RUNNING`            | ExecutorAgent 正在按 Plan 执行步骤。                                    |
| `WAITING_PATCH`      | 某一步骤多次重试失败，等待 Planner 生成局部 PlanPatch。                |
| `PATCHING`           | PlannerAgent 正在根据 PatchRequest 生成 PlanPatch。                     |
| `WAITING_REPLAN`     | 当前 Plan 无法局部修复，等待 Planner 生成新的子计划（suffix）。        |
| `REPLANNING`         | PlannerAgent 正在根据 ReplanRequest 重新规划未完成子计划。             |
| `SUMMARIZING`        | SummarizerAgent 正在汇总 StepResult 与 Safety 事件，生成 DesignResult。|
| `DONE`               | 任务成功完成，DesignResult 已生成并持久化。                             |
| `FAILED`             | 任务执行失败且无法继续（如多次 replan 仍失败或安全策略永久阻断）。     |

#### 状态转移规则

| 当前状态      | 触发事件                             | 下一状态        | 触发方           |
|---------------|--------------------------------------|-----------------|------------------|
| `CREATED`     | 接收到创建任务请求                  | `PLANNING`      | TaskAPI / Workflow |
| `PLANNING`    | 初始 Plan 生成成功                  | `PLANNED`       | PlannerAgent     |
| `PLANNING`    | 规划失败（超时 / 无可行工具链）     | `FAILED`        | PlannerAgent     |
| `PLANNED`     | 开始执行 Plan                       | `RUNNING`       | ExecutorAgent    |
| `RUNNING`     | 所有步骤成功执行完毕                | `SUMMARIZING`   | ExecutorAgent    |
| `RUNNING`     | 某步重复重试失败                    | `WAITING_PATCH` | ExecutorAgent    |
| `RUNNING`     | SafetyAgent 返回 `block` 风险       | `WAITING_REPLAN`| SafetyAgent      |
| `WAITING_PATCH` | 生成 PatchRequest                 | `PATCHING`      | ExecutorAgent    |
| `PATCHING`    | PlanPatch 应用并继续执行成功        | `RUNNING`       | PlannerAgent / ExecutorAgent |
| `PATCHING`    | Patch 生成失败或应用后仍失败        | `WAITING_REPLAN`| PlannerAgent / ExecutorAgent |
| `WAITING_REPLAN` | 生成 ReplanRequest              | `REPLANNING`    | ExecutorAgent / SafetyAgent |
| `REPLANNING`  | 新 Plan 后缀生成成功                | `RUNNING`       | PlannerAgent     |
| `REPLANNING`  | 无可行后缀（搜索失败）              | `FAILED`        | PlannerAgent     |
| `SUMMARIZING` | DesignResult + 报告生成完成         | `DONE`          | SummarizerAgent  |
| 任意非终止态   | 发生未捕获异常 / 系统级错误         | `FAILED`        | Workflow 监控模块 |

#### 与架构层 FSM 的对应关系与 Human-in-the-loop 扩展

在 [系统架构设计](./architecture.md)中, 任务状态机以 语义级 FSM 的形式对外暴露，用于描述任务所处的阶段(规划 / 执行 / 总结)以及是否需要人工接入决策；本节给出的 FSM 则是 实现级 FSM ，用于指导执行引擎的实际调度与失败恢复，二者之间存在一一映射关系

##### 状态映射关系(架构层 实现层)

| 架构层状态 | 实现层状态/片段（本节）                      | 说明 |
|-------------------------------|----------------------------------------------|------|
| `CREATED`                     | `CREATED`                                    | 一致：任务被 TaskAPI 创建但尚未进入规划。 |
| `PLANNING`                    | `PLANNING` / `REPLANNING`                    | 架构层只看到“处于规划阶段”；实现层细分为初始规划与基于 ReplanRequest 的再规划。 |
| `WAITING_PLAN_CONFIRM`        | （待引入：规划完成后，挂起等待人工确认）      | 实现层将增加一个与架构层对应的 `WAITING_PLAN_CONFIRM` 状态，用于在人为确认初始 Plan 前暂停执行。 |
| `PLANNED`                     | `PLANNED`                                    | 一致：Plan 已被确认，可进入执行阶段。 |
| `RUNNING`                     | `RUNNING` / `WAITING_PATCH` / `WAITING_REPLAN` / `PATCHING` / `REPLANNING` | 架构层对外统一暴露“执行中”；实现层在内部区分是否进入 Patch / Replan 分支以及当前是否处于补救过程。 |
| `WAITING_PATCH_CONFIRM`       | `WAITING_PATCH` → `PATCHING` → `RUNNING`     | 架构层只暴露“等待人工确认是否应用 Patch”；在实现层，`WAITING_PATCH` 时创建 PatchRequest，`PATCHING` 为 Planner 生成并应用 PlanPatch，成功后回到 `RUNNING`。 |
| `WAITING_REPLAN_CONFIRM`      | `WAITING_REPLAN` → `REPLANNING` → (`RUNNING` / `FAILED`) | 架构层只暴露“等待人工决策是否进行整体重规划”；实现层在 `WAITING_REPLAN` 写入 ReplanRequest，`REPLANNING` 阶段由 Planner 搜索新后缀，成功则回到 `RUNNING`，否则进入 `FAILED`。 |
| `SUMMARIZING`                 | `SUMMARIZING`                                | 一致：SummarizerAgent 汇总所有 StepResult 与 Safety 事件。 |
| `DONE`                        | `DONE`                                       | 一致：任务成功完成。 |
| `FAILED`                      | `FAILED`                                     | 一致：任务失败且无法继续。 |
| `CANCELLED`                   | （未来扩展：实现层可引入 `CANCELLED`）       | 架构层允许任务被用户显式终止；实现层可在后续版本中增加 `CANCELLED` 终止状态，并在 API 层暴露。 |

##### 人在环路(Human-in-the-loop) 在 FSM 中的位置

引入 Human-in-the-loop 之后，任务生命周期中的若干状态会成为 "等待人工决策" 的挂起点:

- `WAITING_PLAN_CONFIRM`: 初始 Plan 已经生成，但在执行前需要科研人员确认工具链与关键参数
- `WAITING_PATCH` / `WAITING_PATCH_CONFIRM`：某一步骤多次重试失败，系统生成局部 Patch 候选，需要科研人员确认是否应用该 Patch 或转为整体 Replan；
- `WAITING_REPLAN` / `WAITING_REPLAN_CONFIRM`：SafetyAgent 判定整体风险偏高或目标偏离，Planner 给出 Replan 候选方案集，等待科研人员决定是接受重规划、继续当前策略还是终止任务。

在实现层中，这些“等待人工决策”的状态将统一通过结构化的 `PendingAction` 与 `Decision`
进行建模：

- 当 FSM 转入 `WAITING_*` 状态时：
  - 创建一条 `PendingAction` 记录，写入任务当前状态、候选方案（Plan / PlanPatch / Replan），
    以及系统默认建议与解释信息；
  - 任务执行暂停，执行器不再推进后续步骤；
- 当科研人员通过外部 UI / CLI 调用 `Decision` API 提交决策后：
  - 系统根据决策内容更新内部 Plan / PlanPatch / Replan；
  - 记录一条 `DECISION_APPLIED` 事件；
  - 驱动 FSM 进行下一步状态转移（如回到 `RUNNING`、重新进入 `PLANNING`、或进入 `CANCELLED`）。

#### 与 LangGraph 的映射关系

在 LangGraph 中，以上状态将作为 `GraphState` 中的 `task_status` 字段存在。各节点的行为遵循：

- `planner_node` 只允许在 `PLANNING`、`PATCHING`、`REPLANNING` 状态下运行，并负责
  将状态更新为 `PLANNED` 或回退到 `FAILED`。
- `executor_node` 只允许在 `PLANNED`、`RUNNING` 状态下运行，根据执行结果更新为
  `RUNNING` / `WAITING_PATCH` / `WAITING_REPLAN` / `SUMMARIZING`。
- `safety_node` 在 `RUNNING` 状态下对步骤进行审查，当发现阻断级风险时将状态置为
  `WAITING_REPLAN`，并产生对应的 SafetyResult。
- `summarizer_node` 仅在 `SUMMARIZING` 状态运行，结束后将任务状态更新为 `DONE`。

通过显式的状态机设计，可以保证多 Agent 协作过程中任务生命周期的可追踪性与可控性，
避免在重试、Patch 与 Replan 交织时出现状态不一致的问题。
工具图G=(T,E)构建规则是：

- 当`tool_j.io.inputs` $\subseteq$ `tool_i.io.outputs`时可以形成i->j的联通边
- 从虚拟起点START指向所有满足输入工具的节点


---

### PlannerAgent实现(`src/agents/planner.py`)

Planner分为两部分：

1. 静态规划(初始Planner)
   1. 直接实现core-algorithm-spec中定义的前向启发搜索
   2. 工具集合来自ProteinToolKG(JSON/Neo4j)
2. 动态调整(Replan与Patch)
   1. Replan: 根据ReplanRequest重新定义TaskSpec', 调用同一search算法生成suffix, 拼接前缀
   2. Patch: 从KG检索候选替换工具，基于cost/safety/error_similarity评分，生成局部PlanPatch
  
Planner还需要一个 LLM子模块，负责对自然语言任务进行解析，转换成TaskSpec中的：

- `goal_capabilities`
- `initial_artifacts`
- `constraints`(如safety_level, max_cost, max_steps)

---

### ExecutorAgent与WorkflowEngineAdapter

#### ExecutorAgent(`src/agents/executor.py`)

负责：

- 按顺序或依赖拓扑执行`Plan.steps`
- 每一步执行"单步微循环"(retry → patch → replan)
- 调用`SafetyAgent.precheck`做预检
- 调用`WorkflowEngineAdapter.run_step(step, context)`触发实际工具执行(通常是Nextflow)

核心伪代码：

```python
for k, step in enumerate(plan, steps):
  if not safety_agent.precheck(step):
    request_replan(...)
    break

  success = False
  for attempt in range(MAX_RETRY):
    result = workflow_engine.run_step(step, context)
    if result.status == "success:
      success = True
      break

  if not success:
    patch = planner.patch(plan, step, context)
    plan = apply_patc(plan,patch)
    result = workflow_engine.run_step(patch_step, context)
    if result.status != "success":
      new_plan = planner.replan(plan, context)
      plan = new_plan
      # 交给LangGraph上层重新驱动
      break
```

#### WorkflowEngineAdapter(`src/engines/nextflow_adapter.py`)

WorkflowEngineAdapter 负责在 Executor 与具体计算后端之间做连接。它不关心多Agent协作，只负责给定一个PlanStep + 上下文，如何实际执行该步骤，并返回统一格式的结果。

##### 职责边界

- 根据 `step.tool` 查找 ProteinToolKG 中的 Tool 定义
- 读取 Tool.execution 字段，选择执行模式
  - `"nextflow"`: 通过 Nextflow 调用容器化工具
  - `"python"`: 调用本地 Python ToolAdapter
  - `"external_api"`: 调用外部 HTTP API
- 与对应 ToolAdapter 协作完成：
  - 输入解析(resolve_inputs)
  - 执行参数构造(build_nf_params 或 直接传入 run_local)
  - 输出解析(parse_nf_outputs)
- 将执行结果封装为统一的 `(outputs, metrics)`, 供 Executor 进一步组装 StepResult

##### 核心流程伪代码

```python
def run_step_via_engine(step: PlanStep, context: WorkflowContext) -> tuple[dict, dict]:
    # 1. 从 KG 获取工具定义
    tool = kg_client.get_tool(step.tool)

    # 2. 选择对应 Adapter
    adapter = adapter_registry.get(tool.id)

    # 3. 解析输入（处理 "Sx.key" 引用）
    inputs = adapter.resolve_inputs(step, context)

    # 4. 根据执行模式分发
    if tool.execution == "nextflow":
        # 构造 Nextflow 参数
        params = adapter.build_nf_params(inputs)
        work_dir = launch_nextflow(tool.id, params)  # 调用 nextflow run，并返回工作目录
        outputs, metrics = adapter.parse_nf_outputs(work_dir)

    elif tool.execution == "python":
        outputs, metrics = adapter.run_local(inputs)

    elif tool.execution == "external_api":
        outputs, metrics = call_external_api(tool, inputs)

    else:
        raise RuntimeError(f"Unsupported execution mode: {tool.execution}")

    return outputs, metrics
```

##### 错误处理与日志约定

在 WorkflowEngineAdapter 层，不直接生成 StepResult , 而是: 

- 对于可预期错误(如 Nextflow 返回非零退出码、输出文件缺失)
  - 记录一条 engine 级日志(包含 task_if, step_id, tool.id, error_detail)
  - 抛出受控异常(例如 StepExecutionError), 由Executor捕获并写入 StepResult.status = "failed"
- 对于不可预期错误(如 Python 运行时异常)：
  - 同样封装为 StepExecutionError, 避免未捕获异常直接终止整个进程

Executor 在调用 `run_step_via_engine`时，只关心：

- 成功 ⇒ `outputs, metrics`
- 异常 ⇒ `记录失败原因并进入 retry/patch/replan 流程

WorkflowEngineAdapter 自身不参与重试策略，重试逻辑统一在 Executor 侧实现

##### 与 ToolAdapter / ProteinToolKG 的关系

- ToolAdapter 负责工具 内部细节(参数如何组织、输出文件如何解析)
- ProteinToolKG 提供工具 元信息(能力、I/O类型、安全等级、执行模式等)
- WorkflowEngineAdapter 负责将两者串起来，形成 PlanStep → 实际计算执行的连接层

这样，未来新增工具时只需要：

- 在 ProteinToolKG 中注册新的 Tool 节点
- 实现对应 ToolAdapter
- 将 Adapter 注册到 adapter_registry

无需修改 Executor 或 WorkflowEngineAdapter 的核心流程逻辑

---

### ToolAdapters（适配器层）

#### ToolAdapters（src/adapters/ 与 src/tools/）设计

为实现 PlanStep → 具体工具执行（本地 Python / Nextflow / 外部 API）的解耦，本系统通过
ToolAdapter 层对每一个具体工具进行适配封装。ToolAdapter 只关心“如何使用某个工具”，
不关心多 Agent 工作流的细节。

适配器层采用分层结构：

- **基础层(Adapter Infra)**：`src/adapters/`
  - 定义 `BaseToolAdapter` 接口与 `AdapterRegistry`
  - 负责注册/检索与执行入口规范
- **工具实现层(Concrete Tool)**：`src/tools/<tool>/adapter.py`
  - 实现具体工具的输入解析与执行封装
  - 对应工具的 pipeline/脚本与产物结构位于同一工具目录

Executor/StepRunner 只依赖基础层接口，通过 `tool_id`/`adapter_id` 获取适配器执行，
避免执行层直接绑定工具细节。

#### BaseToolAdapter 抽象接口

所有具体 ToolAdapter（如 ProteinMPNNAdapter、ESMFoldAdapter）需实现统一接口，通常
位于 `src/tools/<tool>/adapter.py`。这里给出伪代码说明（仅用于设计约定）：

```python
class BaseToolAdapter(Protocol):
    # 对应 ProteinToolKG 中的 tool.id
    tool_id: str

    def resolve_inputs(self, step: PlanStep, context: WorkflowContext) -> dict:
        """
        将 PlanStep.inputs 中的字段解析为具体的参数字典。
        - 处理字面值（如 {"temperature": 0.8}）
        - 处理引用语义（如 {"sequence": "S1.sequence"} → 从 context.step_results["S1"].outputs 中取值）
        - 若必需字段缺失或类型不匹配，应抛出受控异常供上层捕获
        """

    def build_nf_params(self, inputs: dict) -> dict:
        """
        针对 execution == "nextflow" 的工具，将解析后的 inputs 转换为 Nextflow 所需的 params.json 结构，
        包括：
        - 输入文件路径序列化（如将序列写入临时 FASTA 文件）
        - 任务级参数（如随机种子、batch size 等）
        """

    def run_local(self, inputs: dict) -> tuple[dict, dict]:
        """
        针对 execution == "python" 的工具，直接在本地调用对应函数/脚本。
        返回 (outputs, metrics)：
        - outputs: 必须覆盖 ProteinToolKG.io.outputs 中声明的字段
        - metrics: 可选的运行指标（运行时长、loss、收敛情况等）
        """

    def parse_nf_outputs(self, work_dir: Path) -> tuple[dict, dict]:
        """
        针对 execution == "nextflow" 的工具，从 Nextflow 工作目录中解析输出文件。
        返回 (outputs, metrics)，字段语义同 run_local。
        """
```

上述接口与ProteinToolKG Schema保持一致：

- `tool_id`必须等于KG中的`Tool.id`
- 返回的`outputs`字段必须至少包含`io.outputs`中声明的所有键
- 若工具产生额外信息，可放入`metrics`或`metadata`

#### Adapter与PlanStep/WorkflotContext的关系

在执行某个PlanStep之前，Executor将：

1. 根据`step.tool`从ProteinToolKG中找到对应的Tool定义
2. 根据Tool.execution字段选择执行模式(`"nextflow"|"python"|"external_api"`)
3. 从 AdapterRegistry 中获取对应的 ToolAdapter 实例
4. 调用`adapter.resolve_inputs(step, context)`完成输入解析

这样可以保证：

- PlanStep中仍然只关注 逻辑上的输入引用
- 输入解析逻辑集中在 Adapter层，方便针对不同工具做定制转换

#### 具体工具适配器示例

##### ProteinMPNNAdapter（`src/tools/protein_mpnn/adapter.py`）

- 对应Tool.id: `"protein_mpnn"`
- 典型输入：
  - `goal`: 设计目标描述
  - `length_range`: [min, max]
  - `structure_template_pdb`: 模板结构路径
- 典型输出：
  - `sequence`: 选定的一条候选序列
  - `candidates`: 备选序列列表及简单打分
- 执行方式：
  - 若Tool.execution == "nextflow": 通过Nextflow module调用底层容器
  - 若Tool.execution == "python": 直接调用本地Python封装

##### ESMFoldAdapter（`src/tools/esmfold/adapter.py`）

- Tool.id: `"esmfold"`
- 输入：
  - `sequence`：蛋白质序列
- 输出：
  - `pdb_path`: 预测结构文件路径
  - `plddt`: 结构置信度评分
- 通常使用 `execution = "nextflow"`以容器方式运行

具体适配器实现时，需要确保：

- 输入字段名与ProteinToolKG.io.inputs对齐
- 输出字段名与ProteinToolKG.io.outputs对齐
- 在发生错误时，抛出受控异常或返回明确的错误信息，方便Executor记录StepResult

---

### ProteinToolKG Schema 设计(统一规范)

本系统对蛋白质设计工具的结构化描述采用统一Schema进行建模，所有KG节点均遵循以下字段设计：

---

#### Tool 节点 Schema

每个工具在图谱中对应一个 Tool节点，字段如下：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `id` | str | 工具唯一标识，例如 `"protein_mpnn"` |
| `name` | str | 工具可读名称 |
| `capabilities` | List[str] | 工具可提供的能力，如 `"sequence_design"`、`"structure_prediction"` |
| `io.inputs` | Dict[str, str] | 必须输入的字段及类型，如 `"sequence": "str"` |
| `io.outputs` | Dict[str, str] | 工具输出字段及类型，如 `"pdb_path": "path"` |
| `constraints` | Dict[str, Any] | 工具级约束，如最大序列长度、是否需要结构模板 |
| `execution` | `"nextflow"` | `"python"` | `"external_api"` | 执行方式，由 Executor 分发 |
| `cost_score` | float | 0.0–1.0 的资源消耗指标，越小越优 |
| `safety_level` | int | 工具使用的最低安全等级（0=最严格、1=默认） |
| `compat.from` | List[str] | 推荐或常见的上游输入来源，如 `"protein_mpnn.sequence"` |
| `failure_modes` | List[str] | 常见失败模式，如 `"input_too_long"`, `"timeout"` |
| `preferred_next` | List[str] | 可能的下游工具推荐（用于 Planner 排序优化） |
| `version` | str | 工具版本号 |

---

#### Tool 节点示例

```json
{
  "id": "esmfold",
  "name": "ESMFold",
  "capabilities": ["structure_prediction"],
  "io": {
    "inputs": {
      "sequence": "str"
    },
    "outputs": {
      "pdb_path": "path",
      "plddt": "float"
    }
  },
  "constraints": {
    "max_length": 2000,
    "requires_sequence": true
  },
  "execution": "nextflow",
  "cost_score": 0.6,
  "safety_level": 1,
  "compat": {
    "from": ["protein_mpnn.sequence"]
  },
  "failure_modes": ["nan_output", "timeout"],
  "preferred_next": ["rdkit_props"],
  "version": "1.0.0"
}
```

---

#### KG 图结构与边构建规则(供Planner使用)

##### 工具图G=(T, E)

- T 为工具节点集合
- E 为工具可连接的有向边集合

##### 边构建规则

若满足：`tool_j.io.inputs ⊆ tool_i.io.outputs`  
则加入有向边：`tool_i → tool_j`

##### 安全过滤规则

Planner 在选用工具链时必须满足：

```json
tool.safety_level ≤ task.constraints.safety_level
```

##### 成本排序规则

构造候选链路C后，对链路按照以下值排序：

```json
TotalCost(chain) = Σ cost_score(tool_i)
```

越小越优

---

#### KG查询接口(供Planner与Executor使用)

由`kg_client.py`提供统一API：

```python
find_tools_by_capability(cap: str, constraints: dict) -> List[Tool]
find_compatible_next(tool: Tool) -> List[Tool]
find_alternative_tools(failed_tool, context_io, safety_level) -> List[Tool]
build_tool_graph(task_spec) -> ToolGraph
```

以上接口均基于统一的Schema进行查询与过滤

#### ProteinToolKG扩展：Fluent可视化工具

##### FluentPlot Tool

FluentPlot Tool是一类封装好的交互式可视化工具，用于对蛋白质结构、评估指标以及任务执行过程进行图形化呈现。

##### Tool定位

- 类型: 可视化工具
- 所属层级: Execution Layer
- 调用方式: 通过 ToolAdapter 由 ExecutorAgent 调用
- 主要用途：
  - 结构预测结果可视化
  - 多候选方案评估对比
  - 任务执行过程与安全审查结果展示

---

### ProteinToolKG访问层(`src/kg/kg_client.py`)

职责：

- 从JSON或Neo4j获取工具定义
  - `id`, `capabilities`, `io.inputs`, `io.outputs`, `cost`, `safety_level`
- 提供查询接口给Planner和Executor:
  - `find_tools_by_capability(capability, constraints)`
  - `find_alternative_tools(failed_tool, contex_io, safety_level, error_pattern)`
- 支持静态规划图构建：根据I/O关系构建Tool图G=(T, E)

---

### SafetyAgent(`src/agents/safety.py`)

SafetyAgent 负责在任务输入、Plan执行过程及最终的DesignResult生成阶段进行生物安全与合规性检查。

#### 安全结果与风险标记结构

SafetyAgent 的统一输出为 SafetyResult, 其中包含多条RiskFlag.

```python
class RiskFlag(BaseModel):
    level: Literal["ok", "warn", "block"]
    code: str            # 机器可读的风险代码，如 "SEQ_TOO_LONG"、"TOXIN_SIMILARITY_HIGH"
    message: str         # 人类可读的说明
    scope: Literal["input", "step", "output", "task"]
    step_id: Optional[str]  # 若针对某一步骤，则记录对应 step_id
    details: Dict[str, Any] = {}

class SafetyResult(BaseModel):
    task_id: str
    flags: List[RiskFlag]
    overall_level: Literal["ok", "warn", "block"]
    timestamp: str
```

- `overall_level` 由所有 `flags` 聚合计算而来(例如存在任意`block`则overall为`block`)
- `scope`用于区分风险作用的阶段，便于Executor/Planner决定如何处置

#### 安全规则插件(SafetyRule)抽象

每项具体安全检查被建模为一个 SafetyRule, 遵循统一接口：

```python
class SafetyRule(Protocol):
  rule_id: str
  scope: Literal["inputs", "step", "output", "task"]

  def check(self, context, WorkflowContext, target: Any) -> List[RiskFlag]:

    """
    - context: 在当前任务的上下文(包括 task、plan、step_results、历史safety_events 等)
    - target: 根据scoope不同，可能是:
      - 输入阶段: ProteinDesignTask / 原始自然语言请求
      - 步骤阶段：PlanStep 或 StepResult
    - 返回：0或多条RiskFlag
    """
```

SafetyAgent 内部维护一个规则列表：

```python
class SafetyAgent:
  def __init__(self, rules: List[SafetyRule]):
    self.rules = rules
```

不同规则关注不同维度，例如：

|规则示例|scope|检查内容|
|:-------|:----|:-------|
|`SeqLengthRule`|`input`/`step`|序列长度是否超出任务约束或工具约束|
|`SeqCharsetRule`|`input`/`step`|是否仅包含合法氨基酸字母|
|`ToxinSimilarityRule`|`step`/`task`|与高风险序列库的相似度|
|`KeywokdFunctionRule`|`input`|是否出现敏感功能关键词|
|`EmbeddingRiskRule`|`step`/`output`|基于向量表征的功能风险预测|

未来新增安全策略，只需要新增实现 SafetyRule的类并在初始化时注册，无需修改SafetyAgent的核心逻辑

#### 在任务生命中期中的调用方式

SafetyAgent在三个关键阶段被调用：

##### 输入阶段(Pre-input Check)

在任务创建时，对自然语言描述与结构化约束进行检查：

```python
def check_task_input(task: ProteinDesignTask, context: WorkflowContext) -> SafetyResult:
  # 仅运行 scope == "input"的规则
```

- 若overall_level == "block", API 层直接拒绝受理任务
- 若为 "warn", 记录风险但允许继续，由用户 / 上层 Agent决定是否继续

##### 步骤执行阶段(Pre/Post Step Check)

在 Executor 执行Plan中的每一步前后调用：

```python
def precheck_step(step: PlanStep, context: WorkflowContext) -> SafetyResult:
  # 运行scope in {"input", "step"} 且适用于当前工具的规则

def postcheck_step(result: StepResult, context: WorkflowCOntext) -> SafetyResult:
  # 运行 scope == "step" 的规则，对当前输出进行检查
```

- 若 `precheck_step`的overall_level为"block"
  - Executor不执行该step, 而是构建ReplanRequest, 交给Planner重新规划
- 若`postcheck_step`发现block级风险：
  - Executor终止当前Plan执行，将任务状态更改为WAITING_REPLAN, 由Planner决定更新工具链

##### 结果生成阶段(Final Output Check)

SummarizerAgent在生成DesignResult后，SafetyAgent对其进行最终检查：

```python
def check_final_result(design_result: DesignResult, context: WorkflowContext) -> SafetyResult:
    # 运行 scope in {"output", "task"} 的规则
```

- 若 overall_level为"block", 则：
  - 将结果标记为高风险，不对外直接暴露，仅保留在内部存档
  - 向 Summarizer 添加明确风险说明，要求人工复核

##### 与 Executor / Planner 的协作约定

- Executor:
  - 在单步微循环中必须调用`precheck_step`与`postcheck_step`
  - 当任一SafetyResult.overall_level为"block"时，停止本轮执行并出发Replan流程
- Planner:
  - 在Replan时可以将SafetyResult中的风险信息写入`banned_tools`/`safety_block`集合
  - 可根据历史SafetyEvents调整工具选择与cost权重

通过上述插件化设计，SafetyAgent既可以支撑当前的序列长度 / 字符合法性 / 相似度检查。  
也便于未来引入更复杂的嵌入风险模型或策略规则，同时保证了多Agent协作中安全控制层的独立性与可扩展性。

---

### SummarizerAgent(`src/agents/summarizer.py`)

职责：

- 汇总所有StepResult+安全事件
- 选择最终一个或多个候选序列与结构，计算综合评分
- 输出`DesignResult`，写入：
  - `output/reports/{task_id}.json`
  - `output/reports/(task_id).md`(方便人工阅读)
- 可选：生成简单可视化视图

---

### 存储与日志(`src/models/db.py`, `src/storage/log_store.py`)

- DB模型：
  - `Task`: `trak_id, goal, status, created_at, updated_at`
  - `PlannerSnapshot`: `task_id, plan_json, version, created_at`
  - `StepSummary`: `task_id, step_id, tool, status, metrics_json, risk_level`
- 日志：
  - 所有详细事件(步骤执行、重试、patch、replan等)写入`data/logs/{task_id}.jsonl`

### 日志与可观测设计
<!-- SID:obs.overview -->

为支持多Agent协作任务的调试、回访与故障排查，本系统在数据库持久化之外，引入统一的日志与追踪规范。所有与任务执行相关的事件会以JSON Lines的形式写入`data/logs/{task_id}.jsonl`文件，并与状态机 / 数据库中的记录保持一致。

#### 单条日志记录结构
<!-- SID:obs.eventlog.schema -->

每条日志记录为一个JSON对象，对象字段定义如下：

```jsonc
{
  "timestamp": "2026-02-01T12:34:56.789Z",
  "task_id": "demo_001",
  "event": "STEP_FINISHED",
  "agent": "Executor",          // "Planner" | "Executor" | "Safety" | "Summarizer" | "System"
  "level": "info",              // "debug" | "info" | "warn" | "error"
  "state": "RUNNING",           // 当前任务状态（与 FSM 一致）
  "step_id": "S2",              // 若相关则填入，否则为 null
  "plan_version": 1,            // 当前 Plan 版本号（初始为 0，每次 Replan +1）
  "message": "step S2 finished",
  "data": {                     // 事件相关的结构化数据摘录
    "tool": "esmfold",
    "status": "success",
    "duration_ms": 12345
  },
  "trace_id": "c20d...e8",      // 整个任务的追踪 ID
  "span_id": "9b3a...12"        // 本次事件的局部 ID，便于与外部追踪系统集成
}
```

关键字段说明：

- `task_id`: 与数据库Task表主键一致
- `state`: 与任务状态机中定义的状态一致(CREATED / PLANNING / RUNNING / WAITING_PATCH / WAITING_REPLAN / SUMMARIZING / DONE / FAILED等)
- `plan_version`: 每次Planner.replan成功后自增，用于区分不同版本的计划
- `data`: 只存放与该事件最相关的摘要信息，完整结果仍由StepResult/SafetyResult/DesignResult持久化到数据库或独立文件中

#### 事件类型规范

为便于离线分析与可视化，本系统对`event`字段使用有限集合，常见类型包括：

| 事件类型                   | 触发方        | 含义说明                       |
| ---------------------- | ---------- | -------------------------- |
| `TASK_CREATED`         | API/System | 收到新任务请求，进入 CREATED 状态      |
| `PLANNING_STARTED`     | Planner    | 开始生成初始 Plan                |
| `PLANNING_FINISHED`    | Planner    | 初始 Plan 生成完成，进入 PLANNED 状态 |
| `STEP_STARTED`         | Executor   | 开始执行某一步骤                   |
| `STEP_FINISHED`        | Executor   | 某一步骤执行完成（成功或失败）            |
| `STEP_RETRY`           | Executor   | 针对当前步骤进行一次重试               |
| `STEP_PATCH_REQUESTED` | Executor   | 针对当前步骤请求局部 Patch           |
| `STEP_PATCH_APPLIED`   | Planner    | PlanPatch 已应用到当前 Plan      |
| `REPLAN_REQUESTED`     | Executor   | 构造 ReplanRequest，准备整体再规划   |
| `REPLAN_FINISHED`      | Planner    | 新 Plan 后缀生成完成              |
| `SAFETY_CHECK`         | Safety     | 执行一次安全检查（输入/步骤/输出）         |
| `SAFETY_BLOCK`         | Safety     | 安全规则判定为 block，建议中止当前 Plan  |
| `SUMMARY_STARTED`      | Summarizer | 开始生成 DesignResult / 报告     |
| `SUMMARY_FINISHED`     | Summarizer | 结果汇总完成，进入 DONE 状态          |
| `TASK_FAILED`          | System     | 任务因错误终止，进入 FAILED 状态       |
| `PENDING_ACTION_CREATED` | System (Planner/Executor/Safety) | 创建待人工决策对象（PendingAction）。进入任意 `WAITING_*` 状态前必须记录该事件。 |
| `PENDING_ACTION_UPDATED` | System | PendingAction 候选方案或解释信息更新（例如 Planner 生成新的候选集合覆盖旧集合）。 |
| `PENDING_ACTION_CANCELLED` | System/Human | PendingAction 被取消（例如任务被取消、或决策切换导致旧 PendingAction 作废）。 |
| `DECISION_SUBMITTED` | Human/API | 人类提交 Decision（请求到达 API 层并通过基础校验）。 |
| `DECISION_APPLIED` | System | Decision 被系统应用（写入存储、更新 Plan/PlanPatch/Replan、驱动状态转移）。注意：该事件必须在状态转移成功后写入。 |
| `TASK_CANCELLED_BY_USER` | Human/API | 用户显式取消任务，任务进入 `CANCELLED` 终止态。 |

若未来新增事件类型，应追加到该列表中，并保持语义稳定。

#### 事件日志与快照写入约束（必须遵守）
<!-- SID:obs.eventlog.mandatory_events -->

本系统的“可追溯执行”依赖于 **事件日志（EventLog）** 与 **任务快照（TaskSnapshot）** 的配合。
为确保任务可恢复、可审计、可回放，实现必须严格遵循以下约束。

##### 1) 写入原则（Write-Ahead + 原子性）

- **写前日志（Write-Ahead）**：任何会改变任务外部可见行为的操作（状态变更、应用决策、开始/结束执行步骤）
  必须先写入 EventLog（或与状态写入在同一事务中提交），不得仅在内存中推进状态。
- **原子提交**：一次“关键动作”要求在同一事务中完成：
  - Task 状态更新（ExternalStatus / 可选 InternalStatus）
  - EventLog 追加
  - 必要时的 TaskSnapshot 写入
  - 必要时的 PendingAction / Decision 状态更新
- 若底层存储不支持事务，则必须通过“幂等事件 + 重放修复”策略实现等价一致性（本期实现建议优先选可事务的存储方案）。

##### 2) 必须写事件的关键节点（Mandatory Events）

下列节点必须写 EventLog（缺失视为实现错误）：

1. **状态变更**：任何 Task 状态变化必须记录 `STATE_CHANGED`（若你已有该事件类型）或等价事件。
2. **进入等待人工决策**：
   - 在任务即将进入 `WAITING_PLAN_CONFIRM` / `WAITING_PATCH` / `WAITING_REPLAN` 之前：
     - 必须写入 `PENDING_ACTION_CREATED`
     - 必须写入最新 `TaskSnapshot`
     - 然后才允许更新 Task 状态为对应 `WAITING_*`
3. **提交人工决策**：
   - API 接收到并通过校验：写 `DECISION_SUBMITTED`
   - 系统将决策真正应用并完成状态转移：写 `DECISION_APPLIED`
4. **任务取消**：
   - 用户取消任务：写 `TASK_CANCELLED_BY_USER`，并将 Task 状态置为 `CANCELLED`

##### 3) 必须写快照的关键节点（Mandatory Snapshots）

以下场景必须写入 TaskSnapshot（缺失视为不可恢复风险）：

- 初始 Plan 固化（从 `PLANNING` 结束并进入 `PLANNED` 或 `WAITING_PLAN_CONFIRM`）
- 每次将要进入任意 `WAITING_*` 状态之前（与 `PENDING_ACTION_CREATED` 配套）
- 每次应用 Patch 或接受 Replan 并导致 Plan 发生变化之后
- Summarizer 输出最终结果（进入 `DONE` 前）

> 备注：快照并不要求记录所有中间过程，但必须保证“最小可恢复上下文”完整：
> `state + plan_version + current_step_index + artifacts + pending_action_id(可选)`。

---

#### 事件字段与记录格式（推荐）

建议 EventLog 结构满足“可读 + 可检索 + 可回放”三类需求：

```python
class EventLog(BaseModel):
    id: str
    task_id: str

    event_type: str                 # 例如 PENDING_ACTION_CREATED / DECISION_APPLIED
    ts: datetime                    # 事件时间戳

    actor_type: str                 # system / human / api / workflow
    actor_id: Optional[str] = None  # user_id 或组件名（PlannerAgent/SafetyAgent 等）

    # 事件相关上下文字段（用于审计、回放与调试）
    prev_status: Optional[str] = None         # ExternalStatus
    new_status: Optional[str] = None          # ExternalStatus
    internal_status: Optional[str] = None     # InternalStatus（可选）

    pending_action_id: Optional[str] = None
    decision_id: Optional[str] = None

    # 任意扩展信息（必须是可序列化 JSON）
    data: Dict[str, Any] = {}
```

推荐的 `data` 内容约定（按事件类型）：
- `PENDING_ACTION_CREATED`：
  - `action_type`
  - `candidate_ids`
  - `default_suggestion`
  - `risk_summary`（可选）
- `DECISION_SUBMITTED` / `DECISION_APPLIED`：
  - `choice`
  - `selected_candidate_id`
  - `comment`（可选）
- `STATE_CHANGED`：
  - `reason`（可选，例如 “executor_step_failed”, “safety_block”,“decision_applied”）

#### 与 PendingAction / Decision 的一致性约束（必须遵守）

以下一致性规则用于防止“状态已变更但待办仍挂起”等错误：

1. 若 Task 外部状态为任意 `WAITING_*`：
   - 必须存在 `PendingActionStatus = pending` 的 PendingAction；
   - `pending_action.action_type` 必须与当前 `WAITING_*` 匹配；
   - EventLog 中必须能找到一条最近的 `PENDING_ACTION_CREATED`，且其 `pending_action_id` 与当前一致。

2. 当 `Decision` 被应用（`DECISION_APPLIED` 写入成功）后：
   - 对应 PendingAction 必须从 `pending` 变更为 `decided`（或 `cancelled`）；
   - Task 外部状态必须离开 `WAITING_*`（进入 `PLANNING` / `PLANNED` / `RUNNING` / `CANCELLED` 等）；
   - 必须写入一条新的 `TaskSnapshot`（至少记录决策结果与新状态）。

3. 若任务进入 `FAILED` 或 `CANCELLED` 终止态：
   - 所有仍处于 `pending` 的 PendingAction 必须被标记为 `cancelled`；
   - 必须写入 `PENDING_ACTION_CANCELLED`（若存在待办）与终止原因事件（例如 `TASK_FAILED` 或 `TASK_CANCELLED_BY_USER`）。

以上约束作为实现验收标准：任何违反均视为不可追溯或不可恢复缺陷，应在测试中覆盖。

#### 与状态机/数据库的关系

- 状态机(FSM):
  - 每次任务变更都应记录一条事件日志，`state`字段反映变更后的状态
  - 可通过按时间排序的日志流重建完整的状态迁移时间线
- 数据库记录：
  - Task表保存任务最终状态和关键摘要信息
  - StepSummary/PlannerSnapshot表保存每个步骤的结构化结果与Plan版本
  - 日志文件主要用于过程回放和问题排查，不承担最终结果的唯一存储职责

#### 可观测性与时间线重建

基于上述日志结构，可以对每个任务进行时间线分析，例如：

- 统计每个工具的平均耗时(根据`STEP_FINISHED`的`data.duration_ms`)
- 识别高频失败步骤及其常见`failure_modes`
- 将日志转换为可视化的甘特图/时序图
