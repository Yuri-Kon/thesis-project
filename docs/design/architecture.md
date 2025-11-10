# 系统总体架构

## 分层架构

- 输入层：User/API：自然语言目标、约束、数据引用
- 智能规划层：Planner+KG：任务解析、KG约束推理、计划JSON
- 执行层：Executor+ToolAdapters：工具编排执行、I/O标准化
- 安全与汇总层：Safety+Summarizer：风险识别/阻断、报告生成/反馈
- 资源层：ProteinToolKG/Models/Storage：KG、模型、数据/日志/工作持久化

```mermaid
graph TB
A[输入层] --> B[智能规划层] --> C[执行层] --> D[安全与汇总层] --> E[资源层]
```

**目录映射**

- 输入层：CLI/脚本(`run_demo.py`)
- 智能规划层：`src/agents/planner.py` + `src/kg/protein_tool_kg.json`
- 执行层：`src/agents/executor.py` + `src/models/adapters/*`
- 安全与汇总层：`src/agents/safety.py`, `src/agents/summarizer.py`
- 资源层：`src/kg/`, `output/`, `data`, 模型、权重等

## 组件视图

### Interface & Core

- `TaskAPI`: 创建/执行任务；加载/保存计划与报告
- `Workflow`: 编排入口，驱动Planner->Executor->Safety->Summarizer
- `DataContract`: 统一任务与结果契约(`ProteinDesignTask`/`DesignResult`)

### Agents

- **PlannerAgent**: 解析任务与约束，基于KG产生计划JSON
- **ExecutorAgent**: 解析计划；按顺序加载ToolAdapter；写入中间产物与指标
- **SafetyAgent**: 对输入/过程/输出进行分级校验与阻断/告警
- **SummarizerAgent**: 汇总数据与元信息 -> `output/reports/*.json|md`

### ToolAdapters(适配器层)

- `ProteinMPNNAdapter`: 序列生成(结构引导/目标引导)
- `ESMFoldAdapter`: 序列->结构预测(输出`pdb_path`,`plddt`)
- `RDKitPropsAdapter`: 理化性质与二次分析(输出指标字典)

### Knowledge & Storage

- **ProteinToolKG**: 工具节点与兼容关系
- **Storage**: `output/`、`data/logs`、`data/inputs`

```mermaid
graph LR
subgraph "Interface & Core"
  TA["TaskAPI\n(CLI)"]
  WF[Workflow]
  DC["DataContract\n(ProteinDesignTask / DesignResult)"]
end

subgraph "Agents"
  PL[PlannerAgent]
  EX[ExecutorAgent]
  SA[SafetyAgent]
  SU[SummarizerAgent]
end

subgraph "Tool Adapters"
  MPN[ProteinMPNNAdapter]
  ESM[ESMFoldAdapter]
  RDK[RDKitPropsAdapter]
end

subgraph "Knowledge"
  KG["ProteinToolKG\n(json → later Neo4j)"]
end

subgraph "Storage"
  REP["output/reports/*.json | *.md"]
  ART["output/{pdb, metrics, artifacts}"]
  LOG["data/logs/*.jsonl"]
  INP["data/inputs"]
end

TA --> WF
WF --> PL
WF --> EX
WF --> SA
WF --> SU

PL --> KG
PL --> EX

EX --> MPN
EX --> ESM
EX --> RDK

SU --> REP
EX --> ART
EX --> LOG
TA --> INP

classDef core fill:#E0E7FF,stroke:#6366F1,stroke-width:1.2px,color:#111827;
classDef agent fill:#DCFCE7,stroke:#16A34A,stroke-width:1.2px,color:#052e16;
classDef adapter fill:#FFE4E6,stroke:#DC2626,stroke-width:1.2px,color:#450a0a;
classDef knowledge fill:#E0F2FE,stroke:#0284C7,stroke-width:1.2px,color:#0c4a6e;
classDef storage fill:#F1F5F9,stroke:#334155,stroke-width:1.2px,color:#0f172a;

class TA,WF,DC core;
class PL,EX,SA,SU agent;
class MPN,ESM,RDK adapter;
class KG knowledge;
class REP,ART,LOG,INP storage;

```

## 运行视图与时序图

端到端LLM调控闭环

```mermaid
sequenceDiagram
  autonumber
  participant U as User/CLI
  participant T as TaskAPI
  participant P as PlannerAgent(LLM)
  participant KG as ProteinToolKG
  participant E as ExecutorAgent
  participant A1 as Tool: ProteinMPNN
  participant A2 as Tool: ESMFold
  participant A3 as Tool: RDKitProps
  participant S as SafetyAgent
  participant R as SummarizerAgent
  participant D as DataStore(Logs/Artifacts)

  Note over U,T: 用户给出“目标+约束”(自然语言/结构化)
  U->>T: create_task(goal, constraints)
  T->>P: ProteinDesignTask

  Note over P,KG: LLM读取KG的工具语义/I-O兼容/安全级
  P->>KG: query(capability, io, safety, cost)
  KG-->>P: candidate_tools + constraints
  P-->>T: Plan JSON(steps S1...Sn, deps, safety=S1)
```
