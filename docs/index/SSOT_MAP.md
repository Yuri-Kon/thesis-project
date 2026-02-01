# SSOT Map（单一真源映射表）

> 本文档明确每个 Domain 的**单一真源（Single Source of Truth, SSOT）** 文档及其核心 SID 列表。
>
> **目标**：确保每类规范可追溯到唯一 SSOT，避免后续脚本（如 docslice）或 Claude Code Skills 遇到**同概念多来源**问题。

---

## Domain → SSOT 文档映射

| Domain | SSOT 文档 | 说明 |
|--------|----------|------|
| `arch` | architecture.md | 总体架构、分层设计、核心契约（PendingAction/Decision/TaskSnapshot/Plan） |
| `fsm` | architecture.md | 有限状态机（FSM）状态定义与转换规则 |
| `agent` | agent-design.md | 四类 Agent 的接口、职责边界、数据结构契约 |
| `planner` | agent-design.md（接口）<br>core-algorithm-spec.md（算法） | PlannerAgent 接口定义在 agent-design.md<br>算法细节（候选评分、HITL门控等）在 core-algorithm-spec.md |
| `executor` | agent-design.md | ExecutorAgent 接口与职责边界 |
| `safety` | agent-design.md | SafetyAgent 接口与职责边界 |
| `summarizer` | agent-design.md | SummarizerAgent 接口与职责边界 |
| `tools` | tools-catalog.md | 工具清单、ToolAdapter 约束、集成优先级 |
| `api` | system-implementation-design.md | REST API 端点定义与契约 |
| `obs` | system-implementation-design.md | 可观测性（EventLog）、日志模式与约束 |
| `storage` | system-implementation-design.md | 数据存储与持久化（尚未完整标注 SID） |
| `kg` | system-implementation-design.md | ProteinToolKG 知识图谱模式（尚未完整标注 SID） |
| `impl` | system-implementation-design.md | 实现层总览、技术栈选型 |
| `algo` | core-algorithm-spec.md | 算法规范总览与定义 |
| `hitl` | hitl-extension.md（差分索引）<br>architecture.md（核心契约）<br>agent-design.md（Agent 行为） | HITL 机制为跨文档概念：<br>- 核心契约（PendingAction/Decision/TaskSnapshot）在 architecture.md<br>- Agent 行为约束在 agent-design.md<br>- hitl-extension.md 作为差分索引文档，通过 SID 引用汇总 HITL 相关规范 |

---

## 核心 SID 列表（按 Domain 分组）

### `arch` Domain（SSOT: architecture.md）

| SID | 说明 | 粒度 |
|-----|------|------|
| `SID:arch.overview.layers` | 5 层架构总览 | Section |
| `SID:arch.components.overview` | 核心组件概览 | Section |
| `SID:arch.flow.end_to_end` | 端到端工作流 | Section |
| `SID:arch.execution.nextflow_boundary` | Nextflow 执行后端边界 | Block |
| `SID:arch.dataflow.overview` | 数据流概览 | Section |
| `SID:arch.kg.overview` | ProteinToolKG 在架构层的位置 | Block |
| `SID:arch.contracts.pending_action` | PendingAction 契约定义 | Spec-Item |
| `SID:arch.contracts.decision` | Decision 契约定义 | Spec-Item |
| `SID:arch.contracts.task_snapshot` | TaskSnapshot 契约定义 | Spec-Item |
| `SID:arch.contracts.plan` | Plan 契约定义（架构层视角） | Spec-Item |

**引用规则**：
- 任何文档需要引用 PendingAction/Decision/TaskSnapshot/Plan 契约时，必须引用 architecture.md 中的对应 SID
- 实现层（system-implementation-design.md）可扩展这些契约为 Pydantic 模型，但**不得重新定义**契约语义

---

### `fsm` Domain（SSOT: architecture.md）

| SID | 说明 | 粒度 |
|-----|------|------|
| `SID:fsm.lifecycle.overview` | 任务生命周期总览 | Section |
| `SID:fsm.states.definitions` | FSM 状态完整定义表 | Block |
| `SID:fsm.states.waiting_plan_confirm` | WAITING_PLAN_CONFIRM 状态定义 | Spec-Item |
| `SID:fsm.states.waiting_patch_confirm` | WAITING_PATCH_CONFIRM 状态定义 | Spec-Item |
| `SID:fsm.states.waiting_replan_confirm` | WAITING_REPLAN_CONFIRM 状态定义 | Spec-Item |
| `SID:fsm.transitions.overview` | 状态转换规则总览 | Spec-Item |

**引用规则**：
- 任何文档描述任务状态时，必须引用 `SID:fsm.states.definitions`
- HITL 相关状态的详细说明引用对应的 `SID:fsm.states.waiting_*`

---

### `agent` Domain（SSOT: agent-design.md）

| SID | 说明 | 粒度 |
|-----|------|------|
| `SID:agent.overview.introduction` | Agent 体系总览 | Section |
| `SID:agent.overview.roles` | 四类 Agent 角色列表 | Block |
| `SID:agent.contracts.overview` | 核心数据结构契约总览 | Section |
| `SID:agent.contracts.protein_design_task` | ProteinDesignTask 数据结构 | Block |
| `SID:agent.contracts.plan` | Plan 数据结构（Agent 层视角） | Block |
| `SID:agent.contracts.step_result` | StepResult 数据结构 | Block |
| `SID:agent.contracts.design_result` | DesignResult 数据结构 | Block |
| `SID:agent.contracts.safety_result` | SafetyResult 数据结构 | Block |
| `SID:agent.hitl.overview` | HITL 机制在 Agent 层的概述 | Section |
| `SID:agent.hitl.universal_constraints` | Agent 层 HITL 统一约束 | Spec-Item |

**注意**：
- `SID:agent.contracts.plan` 与 `SID:arch.contracts.plan` 的区分：
  - `arch.contracts.plan`：架构层视角，定义 Plan 在 FSM 与 HITL 机制中的作用
  - `agent.contracts.plan`：Agent 层视角，定义 Plan 的数据结构（Python dataclass 形式）
- 两者互补，非重复

---

### `planner` Domain（SSOT: agent-design.md + core-algorithm-spec.md）

#### 接口与职责（SSOT: agent-design.md）

| SID | 说明 | 粒度 |
|-----|------|------|
| `SID:planner.interface.overview` | PlannerAgent 接口总览 | Section |
| `SID:planner.hitl.responsibilities` | PlannerAgent HITL 职责总览 | Section |
| `SID:planner.hitl.plan_confirm` | Plan 确认阶段职责 | Block |
| `SID:planner.responsibilities.must` | PlannerAgent 必须做的事 | Spec-Item |
| `SID:planner.responsibilities.must_not` | PlannerAgent 不得做的事 | Spec-Item |

#### 算法与契约（SSOT: core-algorithm-spec.md）

| SID | 说明 | 粒度 |
|-----|------|------|
| `SID:planner.contracts.io_overview` | 输入输出契约总览 | Block |
| `SID:planner.contracts.candidate_schema` | Candidate 对象模式总览 | Block |
| `SID:planner.contracts.plan_candidate` | PlanCandidate 模式定义 | Spec-Item |
| `SID:planner.contracts.patch_candidate` | PatchCandidate 模式定义 | Spec-Item |
| `SID:planner.contracts.replan_candidate` | ReplanCandidate 模式定义 | Spec-Item |
| `SID:planner.algorithm.tool_retrieval` | 工具检索算法 | Block |
| `SID:planner.algorithm.candidate_scoring` | 候选方案评分规则 | Block |
| `SID:planner.algorithm.hitl_gate` | HITL 门控决策规则 | Block |
| `SID:planner.algorithm.decision_application` | Decision 应用逻辑 | Block |

**引用规则**：
- 引用 PlannerAgent 接口时 → `SID:planner.interface.overview`
- 引用候选评分算法时 → `SID:planner.algorithm.candidate_scoring`
- 引用 HITL 职责约束时 → `SID:planner.responsibilities.must` / `must_not`

---

### `executor` Domain（SSOT: agent-design.md）

| SID | 说明 | 粒度 |
|-----|------|------|
| `SID:executor.hitl.responsibilities` | ExecutorAgent HITL 职责总览 | Section |
| `SID:executor.hitl.patch_confirm` | Patch 确认阶段职责 | Block |
| `SID:executor.responsibilities.must` | ExecutorAgent 必须做的事 | Spec-Item |
| `SID:executor.responsibilities.must_not` | ExecutorAgent 不得做的事 | Spec-Item |

---

### `safety` Domain（SSOT: agent-design.md）

| SID | 说明 | 粒度 |
|-----|------|------|
| `SID:safety.hitl.responsibilities` | SafetyAgent HITL 职责总览 | Section |
| `SID:safety.hitl.replan_trigger` | 触发 WAITING_REPLAN_CONFIRM 的条件 | Block |
| `SID:safety.responsibilities.must` | SafetyAgent 必须做的事 | Spec-Item |
| `SID:safety.responsibilities.must_not` | SafetyAgent 不得做的事 | Spec-Item |

---

### `summarizer` Domain（SSOT: agent-design.md）

| SID | 说明 | 粒度 |
|-----|------|------|
| `SID:summarizer.hitl.responsibilities` | SummarizerAgent HITL 职责 | Section |
| `SID:summarizer.responsibilities.must` | SummarizerAgent 必须做的事 | Spec-Item |
| `SID:summarizer.responsibilities.must_not` | SummarizerAgent 不得做的事 | Spec-Item |

---

### `tools` Domain（SSOT: tools-catalog.md）

| SID | 说明 | 粒度 |
|-----|------|------|
| `SID:tools.executor.overview` | Executor 可选工具总览 | Section |
| `SID:tools.protgpt2.spec` | ProtGPT2 (PLM) 工具规约 | Block |
| `SID:tools.esmfold.spec` | ESMFold 工具规约 | Block |
| `SID:tools.nim_esmfold.spec` | NIM ESMFold 工具规约 | Block |
| `SID:tools.alphafold.spec` | AlphaFold/OpenFold 工具规约 | Block |
| `SID:tools.adapter.constraints` | ToolAdapter 设计原则与约束 | Spec-Item |

**引用规则**：
- 引用工具规约时 → `SID:tools.<tool_name>.spec`
- 引用 ToolAdapter 约束时 → `SID:tools.adapter.constraints`

---

### `api` Domain（SSOT: system-implementation-design.md）

| SID | 说明 | 粒度 |
|-----|------|------|
| `SID:api.rest.overview` | REST API 总览 | Section |
| `SID:api.rest.create_task` | POST /tasks 端点 | Spec-Item |
| `SID:api.rest.get_pending_actions` | GET /pending-actions 端点 | Spec-Item |
| `SID:api.rest.submit_decision` | POST /pending-actions/{id}/decision 端点 | Spec-Item |
| `SID:api.rest.get_report` | GET /tasks/{task_id}/report 端点 | Spec-Item |

**引用规则**：
- 引用 API 端点定义时，使用对应的 `SID:api.rest.<endpoint_name>`

---

### `obs` Domain（SSOT: system-implementation-design.md）

| SID | 说明 | 粒度 |
|-----|------|------|
| `SID:obs.eventlog.schema` | EventLog 单条日志记录结构 | Block |
| `SID:obs.observability.overview` | 日志与可观测设计总览 | Block |
| `SID:obs.eventlog.mandatory_events` | 事件日志写入约束（必须遵守） | Spec-Item |

**引用规则**：
- 引用日志模式时 → `SID:obs.eventlog.schema`
- 引用可观测设计总览时 → `SID:obs.observability.overview`
- 引用日志写入约束时 → `SID:obs.eventlog.mandatory_events`

---

### `impl` Domain（SSOT: system-implementation-design.md）

| SID | 说明 | 粒度 |
|-----|------|------|
| `SID:impl.overview.introduction` | 实现层总览 | Section |
| `SID:impl.techstack.overview` | 技术栈选型 | Block |
| `SID:impl.nextflow.control_flow_constraints` | Nextflow 接入边界与控制流约束 | Block |

---

### `algo` Domain（SSOT: core-algorithm-spec.md）

| SID | 说明 | 粒度 |
|-----|------|------|
| `SID:algo.scope.overview` | 算法规范范围说明 | Section |
| `SID:algo.definitions.overview` | 算法定义总览 | Section |

---

### `hitl` Domain（跨文档概念，差分索引在 hitl-extension.md）

**HITL 机制为跨文档概念，分散在多个 SSOT 文档中：**

| 规约类别 | SSOT 文档 | 核心 SID |
|---------|----------|---------|
| HITL 核心契约（PendingAction/Decision/TaskSnapshot） | architecture.md | `SID:arch.contracts.pending_action`<br>`SID:arch.contracts.decision`<br>`SID:arch.contracts.task_snapshot` |
| HITL FSM 状态 | architecture.md | `SID:fsm.states.waiting_plan_confirm`<br>`SID:fsm.states.waiting_patch_confirm`<br>`SID:fsm.states.waiting_replan_confirm` |
| Agent 层 HITL 职责边界 | agent-design.md | `SID:planner.hitl.responsibilities`<br>`SID:executor.hitl.responsibilities`<br>`SID:safety.hitl.responsibilities`<br>`SID:summarizer.hitl.responsibilities`<br>`SID:agent.hitl.universal_constraints` |
| HITL 算法（门控、决策应用） | core-algorithm-spec.md | `SID:planner.algorithm.hitl_gate`<br>`SID:planner.algorithm.decision_application` |
| HITL API 端点 | system-implementation-design.md | `SID:api.rest.get_pending_actions`<br>`SID:api.rest.submit_decision` |
| EventLog 约束（HITL 事件） | system-implementation-design.md | `SID:obs.eventlog.mandatory_events` |

**引用规则**：
- **hitl-extension.md 是差分索引文档**，不定义新规约，仅通过 `[ref:SID:...]` 语法汇总上述 SSOT 中的 HITL 相关规范
- 任何需要引用 HITL 机制的文档，应直接引用对应 SSOT 中的 SID，而非引用 hitl-extension.md

---

## 使用规则

### 1. SSOT 原则

- **定义一次，引用多次**：每个概念只在其 SSOT 文档中定义，其他文档通过 `[ref:SID:...]` 引用
- **禁止重新定义**：实现层可扩展（如添加 Pydantic 字段），但不得改变语义定义

### 2. SID 引用优先级

```markdown
高优先级：[ref:SID:domain.topic.name]
次优先级：DOC:<doc_key>#<anchor>（仅在 SID 未分配时使用）
禁止使用：纯文本章节标题引用（如"详见架构设计章节"）
```

### 3. Claude Code Skill 集成规则

- 当 Skills 使用 `--topic` 聚合规范时，**默认只使用 SSOT SID**
- 避免从多个来源提取同一概念，导致规范冲突

### 4. Docslice 脚本约定

- `docslice` 脚本应优先从 SSOT 文档中提取规范
- 检测到重复 SID 时，应报错并指出冲突文档

---

## 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| 1.0 | 2025-12-31 | 初始版本，定义 12 个 Domain 的 SSOT 文档映射与核心 SID 列表 |

---

**本文档是 Milestone "Addressable Design Docs & Spec Retrieval Skill" 的基础索引文件，任何修改应通过正式的 PR 流程并更新版本历史。**
