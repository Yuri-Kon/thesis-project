# 系统实现设计文档

> 目标：在现有架构的算法设计基础上，明确技术选型、代码结构、组件职责、运行时流程，指导后续代码编码与集成

## 系统总体概览

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
- 设计任务/日志存储、KG访问、API层等

---

## 技术栈与框架选型

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
      protein_mpnn_adapter.py
      esmfold_adapter.py
      rdkit_props_adapter.py
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
    output/
      pdb/
      metrics/
      artifacts/
      reports/
    data/
      inputs/
      logs/
```

---

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

---

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

API层使用与内部FSM完全一致的枚举值：

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
```

所有接口中返回的字段 `status` 必须严格使用以上枚举值

---

#### REST API 规范

##### POST /tasks

创建一个新的蛋白质设计任务

**请求体**：

```json
{
  "goal": "design a stable 120aa enzyme",
  "constraints": {
    "length_range": [100, 140],
    "safety_level": 1
  },
  "metadata": {
    "user": "demo"
  }
}
```

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

查询任务状态(包含Plan、StepResult摘要与Safety事件)

响应：

```json
{
  "task_id": "task_20250201_001",
  "status": "RUNNING",
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
  "summary_available": false
}
```

字段说明：

| 字段                  | 含义                                     |
| ------------------- | -------------------------------------- |
| `status`            | 任务当前状态（FSM 一致）                         |
| `plan_version`      | 当前 Plan 的版本号（初始为 0，每次 Replan +1）       |
| `current_step`      | 正在执行或即将执行的步骤                           |
| `steps[]`           | StepSummary 从数据库读取的摘要                  |
| `safety_events[]`   | 历史 SafetyResult 的摘要                    |
| `summary_available` | 若为 true，则可访问 `/tasks/{task_id}/report` |

---

##### GET /tasks/{task_id}/report

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

### ToolAdapters(`src/adapters/*`)

### ToolAdapters（src/adapters/*）设计

为实现 PlanStep → 具体工具执行（本地 Python / Nextflow / 外部 API）的解耦，本系统通过
ToolAdapter 层对每一个具体工具进行适配封装。ToolAdapter 只关心“如何使用某个工具”，
不关心多 Agent 工作流的细节。

#### BaseToolAdapter 抽象接口

所有具体 ToolAdapter（如 ProteinMPNNAdapter、ESMFoldAdapter）需实现统一接口。这里给出
伪代码说明（仅用于设计约定）：

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
3. 从AdapterRegistry中获取对应的ToolAdapter实例
4. 调用`adapter.resolve_inputs(step, context)`完成输入解析

这样可以保证：

- PlanStep中仍然只关注 逻辑上的输入引用
- 输入解析逻辑集中在 Adapter层，方便针对不同工具做定制转换

#### 具体工具适配器示例

##### ProteinMPNNAdapter

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

##### ESMFoldAdapter

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

为支持多Agent协作任务的调试、回访与故障排查，本系统在数据库持久化之外，引入统一的日志与追踪规范。所有与任务执行相关的事件会以JSON Lines的形式写入`data/logs/{task_id}.jsonl`文件，并与状态机 / 数据库中的记录保持一致。

#### 单条日志记录结构

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

若未来新增事件类型，应追加到该列表中，并保持语义稳定。

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

