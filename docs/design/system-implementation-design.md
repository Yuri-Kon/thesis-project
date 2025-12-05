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

FastAPI负责对外暴露REST接口：

- `POST /tasks`: 创建新设计任务
  - 请求体：`ProteinDesignTask`(不包含task_id, 由任务生成)
  - 行为：写入DB→调用LangGraph workflow异步启动
- `GET /tasks/{task_id}`
  - 返回：任务基本ixnxi + 当前任务状态(PLANNED/RUNNING/DONE/FAILED) + summary
- `GET /tasks/{task_id}/report`: 返回`DesignResult` + 报告文件路径/内容

TaskAPI在architecture中已经有概念性描述，这里是具体实现

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

这是新加入的关键组件，用于桥接Plan与Nextflow:

- 输入: `PlanStep` + 当前上下文
- 运行过程：
  - 根据step.tool从ProteinToolKG中获取执行类型
    - `execution: "nextflow"/"python"/"exeternal_api"`
  - 若为`"nextflow"`
    - 生成`params.json`, 包括：
      - 序列/pdb_path等输入文件路径
      - 任务级参数
    - 调用`nextflow run ...`
  - 若为`"python"`:
    - 直接调用对应的adapter的`run()`方法

---

### ToolAdapters(`src/adapters/*`)

每个ToolAdapter抽象为同一种接口：

```python
class BaseToolAdapter(Protocol):
  def build_nf_params(self, step: PlanStep, context: Dict) -> Dict:
    ...
  def parse_nf_outputs(self, work_dir: Path) -> Dict:
    ...
```

具体实现：

1. ProteinMPNNAdapter
   1. 输入：目标(goal)、长度范围、结构模板路径
   2. 输出：序列列表、一些简单指标
   3. 对应Nextflow module: `nf/modules/protein_mpnn.nf`
2. ESMFoldAdapter
   1. 输入：序列或FASTA文件路径
   2. 输出：`pdb_path` + `plddt`
3. RDKitPropsAdapter
   1. 输入：序列+pdb_path
   2. 输出：`hydrophobicity`等指标

ToolAdapter的元数据由ProteinToolKG管理

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

职责：

- 对输入、单步输出、最终结果做安全检查：
  - 序列长度、非法字符检查
  - 与高风险序列库的相似度
  - 特定功能关键词/embedding的风险判定
- 输出：`SafetyResult`，包含多条`RiskFlag { level: "ok|warn|block", code, maeeage }`
- 在`level=="block`时，建议Executor中止当前计划并触发Replan流程

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


