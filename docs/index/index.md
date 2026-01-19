# Specification Index（规范索引）

> 本文档是设计规范的**人类可读索引**，与 `index.json` 对应。
>
> 提供按 Domain 和文档组织的规范清单，便于快速定位和浏览。
>
> **机器可读版本**: [index.json](./index.json)
> **主题视图**: [topic_views.json](./topic_views.json)

---

## 索引总览

**版本**: 1.0
**生成日期**: 2026-01-11
**总规范数**: 77
**文档数**: 10

---

## 文档列表

| doc_key | 标题 | 路径 | 状态 | 依赖 |
|---------|------|------|------|------|
| `arch` | 系统总体架构 | [docs/design/architecture.md](../design/architecture.md) | stable | - |
| `agent` | Agent设计文档 | [docs/design/agent-design.md](../design/agent-design.md) | stable | arch |
| `algo` | 核心算法规范 | [docs/design/core-algorithm-spec.md](../design/core-algorithm-spec.md) | stable | arch, agent |
| `impl` | 系统实现设计 | [docs/design/system-implementation-design.md](../design/system-implementation-design.md) | stable | arch, agent |
| `impl_index` | 实现代码索引与结构化总览 | [docs/impl/implementation_index.md](../impl/implementation_index.md) | stable | impl |
| `impl_llm_provider` | LLM Provider 集成指南 | [docs/impl/llm_provider_guide.md](../impl/llm_provider_guide.md) | stable | impl |
| `impl_snapshot_recovery` | Snapshot Recovery for Remote Jobs | [docs/impl/snapshot-recovery.md](../impl/snapshot-recovery.md) | stable | impl |
| `impl_remote_model_invocation` | Remote Model Invocation Service | [docs/impl/remote_model_invocation.md](../impl/remote_model_invocation.md) | stable | impl |
| `tools` | Tools Catalog | [docs/design/tools-catalog.md](../design/tools-catalog.md) | stable | impl |
| `hitl` | HITL 扩展设计 | [docs/design/hitl-extension.md](../design/hitl-extension.md) | stable | arch, agent, impl, algo |

---

## 按 Domain 分组的规范索引

### 1. `arch` Domain（总体架构）

**SSOT 文档**: architecture.md

| SID | 标题 | 级别 | 标签 |
|-----|------|------|------|
| `arch.overview.layers` | 分层架构 | Section | arch, overview, layers |
| `arch.components.overview` | 组件视图 | Section | arch, components |
| `arch.flow.end_to_end` | 运行视图与时序图 | Section | arch, flow, runtime |
| `arch.execution.nextflow_boundary` | 执行后端边界(Nextflow) | Block | arch, execution, nextflow, boundary |
| `arch.dataflow.overview` | 数据流概览 | Section | arch, dataflow |
| `arch.kg.overview` | ProteinToolKG 在架构中的位置 | Block | arch, kg, knowledge_graph |
| `arch.contracts.pending_action` | PendingAction 契约定义 | Spec-Item | arch, contracts, hitl, pending_action |
| `arch.contracts.decision` | Decision 契约定义 | Spec-Item | arch, contracts, hitl, decision |
| `arch.contracts.task_snapshot` | TaskSnapshot 契约定义 | Spec-Item | arch, contracts, hitl, snapshot |
| `arch.contracts.plan` | Plan 契约定义（架构层视角） | Spec-Item | arch, contracts, planning |

---

### 2. `fsm` Domain（有限状态机）

**SSOT 文档**: architecture.md

| SID | 标题 | 级别 | 标签 |
|-----|------|------|------|
| `fsm.lifecycle.overview` | 任务生命周期与状态机 | Section | fsm, lifecycle, state_machine |
| `fsm.states.definitions` | FSM 状态完整定义表 | Block | fsm, states, definitions |
| `fsm.states.waiting_plan_confirm` | WAITING_PLAN_CONFIRM 状态定义 | Spec-Item | fsm, states, hitl, planning |
| `fsm.states.waiting_patch_confirm` | WAITING_PATCH_CONFIRM 状态定义 | Spec-Item | fsm, states, hitl, execution |
| `fsm.states.waiting_replan_confirm` | WAITING_REPLAN_CONFIRM 状态定义 | Spec-Item | fsm, states, hitl, planning |
| `fsm.transitions.overview` | 状态转换规则总览 | Spec-Item | fsm, transitions, state_machine |

---

### 3. `agent` Domain（Agent 体系）

**SSOT 文档**: agent-design.md

| SID | 标题 | 级别 | 标签 |
|-----|------|------|------|
| `agent.overview.introduction` | Agent体系总览 | Section | agent, overview |
| `agent.overview.roles` | Agent 角色列表 | Block | agent, overview, roles |
| `agent.contracts.overview` | 核心数据结构契约总览 | Section | agent, contracts, data_structures |
| `agent.contracts.protein_design_task` | ProteinDesignTask 数据结构 | Block | agent, contracts, task |
| `agent.contracts.plan` | Plan 数据结构（Agent 层视角） | Block | agent, contracts, planning |
| `agent.contracts.step_result` | StepResult 数据结构 | Block | agent, contracts, execution, result |
| `agent.contracts.design_result` | DesignResult 数据结构 | Block | agent, contracts, result |
| `agent.contracts.safety_result` | SafetyResult 数据结构 | Block | agent, contracts, safety, result |
| `agent.hitl.overview` | HITL 机制在 Agent 层的概述 | Section | agent, hitl, overview |
| `agent.hitl.universal_constraints` | Agent 层 HITL 统一约束 | Spec-Item | agent, hitl, constraints |

---

### 4. `planner` Domain（Planner Agent）

**SSOT 文档**: agent-design.md（接口）、core-algorithm-spec.md（算法）

#### 接口与职责

| SID | 标题 | 级别 | 标签 |
|-----|------|------|------|
| `planner.interface.overview` | PlannerAgent 接口总览 | Section | planner, interface, agent |
| `planner.hitl.responsibilities` | PlannerAgent HITL 职责 | Section | planner, hitl, responsibilities |
| `planner.hitl.plan_confirm` | 初始 Plan 确认阶段 | Block | planner, hitl, planning |
| `planner.responsibilities.must` | PlannerAgent 必须做的事 | Spec-Item | planner, responsibilities, must |
| `planner.responsibilities.must_not` | PlannerAgent 不得做的事 | Spec-Item | planner, responsibilities, must_not |

#### 算法与契约

| SID | 标题 | 级别 | 标签 |
|-----|------|------|------|
| `planner.contracts.io_overview` | Planner 输入输出契约 | Block | planner, contracts, io |
| `planner.contracts.candidate_schema` | Candidate 对象模式总览 | Block | planner, contracts, candidate |
| `planner.contracts.plan_candidate` | PlanCandidate 模式定义 | Spec-Item | planner, contracts, candidate, planning |
| `planner.contracts.patch_candidate` | PatchCandidate 模式定义 | Spec-Item | planner, contracts, candidate, execution |
| `planner.contracts.replan_candidate` | ReplanCandidate 模式定义 | Spec-Item | planner, contracts, candidate, planning |
| `planner.algorithm.tool_retrieval` | 工具检索算法 | Block | planner, algorithm, tool_retrieval |
| `planner.algorithm.candidate_scoring` | 候选方案评分规则 | Block | planner, algorithm, scoring |
| `planner.algorithm.hitl_gate` | HITL 门控决策规则 | Block | planner, algorithm, hitl |
| `planner.algorithm.decision_application` | Decision 应用逻辑 | Block | planner, algorithm, hitl, decision |

---

### 5. `executor` Domain（Executor Agent）

**SSOT 文档**: agent-design.md

| SID | 标题 | 级别 | 标签 |
|-----|------|------|------|
| `executor.hitl.responsibilities` | ExecutorAgent HITL 职责 | Section | executor, hitl, responsibilities |
| `executor.hitl.patch_confirm` | Patch 触发与确认 | Block | executor, hitl, execution, patch |
| `executor.responsibilities.must` | ExecutorAgent 必须做的事 | Spec-Item | executor, responsibilities, must |
| `executor.responsibilities.must_not` | ExecutorAgent 不得做的事 | Spec-Item | executor, responsibilities, must_not |

---

### 6. `safety` Domain（Safety Agent）

**SSOT 文档**: agent-design.md

| SID | 标题 | 级别 | 标签 |
|-----|------|------|------|
| `safety.hitl.responsibilities` | SafetyAgent HITL 职责 | Section | safety, hitl, responsibilities |
| `safety.hitl.replan_trigger` | 触发 WAITING_REPLAN_CONFIRM 的条件 | Block | safety, hitl, planning |
| `safety.responsibilities.must` | SafetyAgent 必须做的事 | Spec-Item | safety, responsibilities, must |
| `safety.responsibilities.must_not` | SafetyAgent 不得做的事 | Spec-Item | safety, responsibilities, must_not |

---

### 7. `summarizer` Domain（Summarizer Agent）

**SSOT 文档**: agent-design.md

| SID | 标题 | 级别 | 标签 |
|-----|------|------|------|
| `summarizer.hitl.responsibilities` | SummarizerAgent HITL 职责 | Section | summarizer, hitl, responsibilities |
| `summarizer.responsibilities.must` | SummarizerAgent 必须做的事 | Spec-Item | summarizer, responsibilities, must |
| `summarizer.responsibilities.must_not` | SummarizerAgent 不得做的事 | Spec-Item | summarizer, responsibilities, must_not |

---

### 8. `algo` Domain（算法规范）

**SSOT 文档**: core-algorithm-spec.md

| SID | 标题 | 级别 | 标签 |
|-----|------|------|------|
| `algo.scope.overview` | 算法规范范围说明 | Section | algo, scope |
| `algo.definitions.overview` | 算法定义总览 | Section | algo, definitions |

---

### 9. `api` Domain（REST API）

**SSOT 文档**: system-implementation-design.md

| SID | 标题 | 级别 | 标签 |
|-----|------|------|------|
| `api.rest.overview` | REST API 总览 | Section | api, rest |
| `api.rest.create_task` | POST /tasks 端点 | Spec-Item | api, rest, task |
| `api.rest.get_pending_actions` | GET /pending-actions 端点 | Spec-Item | api, rest, hitl, pending_actions |
| `api.rest.submit_decision` | POST /pending-actions/{id}/decision 端点 | Spec-Item | api, rest, hitl, decision |
| `api.rest.get_report` | GET /tasks/{task_id}/report 端点 | Spec-Item | api, rest, report |

---

### 10. `obs` Domain（可观测性）

**SSOT 文档**: system-implementation-design.md

| SID | 标题 | 级别 | 标签 |
|-----|------|------|------|
| `obs.observability.overview` | 日志与可观测设计 | Block | obs, observability, overview |
| `obs.eventlog.schema` | EventLog 单条日志记录结构 | Block | obs, eventlog, observability |
| `obs.eventlog.mandatory_events` | 事件日志写入约束（必须遵守） | Spec-Item | obs, eventlog, observability, hitl |

---

### 11. `impl` Domain（实现层）

**SSOT 文档**: system-implementation-design.md

| SID | 标题 | 级别 | 标签 |
|-----|------|------|------|
| `impl.overview.introduction` | 实现层总览 | Section | impl, overview |
| `impl.techstack.overview` | 技术栈选型 | Block | impl, techstack |
| `impl.planner.tool_resolution` | Planner 工具解析与 KG-only 约束 | Block | impl, planner, tool_resolution, kg |
| `impl.nextflow.control_flow_constraints` | Nextflow 接入边界与控制流约束 | Block | impl, nextflow, control_flow, constraints |
| `impl.index.codebase_overview` | 实现代码索引与结构化总览 | Section | impl, index, codebase, overview |
| `impl.llm_provider.guide` | LLM Provider 集成指南 | Section | impl, llm_provider, guide, overview |
| `impl.llm_provider.external_providers` | OpenAICompatibleProvider | Block | impl, llm_provider, external, openai_compatible |
| `impl.snapshot_recovery.overview` | Snapshot Recovery for Remote Jobs | Section | impl, snapshot_recovery, overview |
| `impl.snapshot_recovery.snapshot_schema` | 快照结构 | Block | impl, snapshot_recovery, snapshot, schema |
| `impl.snapshot_recovery.recovery_flow` | 恢复流程 | Block | impl, snapshot_recovery, recovery, flow |
| `impl.remote_model_invocation.overview` | Remote Model Invocation Service | Section | impl, remote_model_invocation, overview |
| `impl.remote_model_invocation.components` | 核心组件 | Block | impl, remote_model_invocation, components |
| `impl.remote_model_invocation.rest_api` | REST API 规范 | Section | impl, remote_model_invocation, rest_api |

---

### 12. `tools` Domain（工具集成）

**SSOT 文档**: tools-catalog.md

| SID | 标题 | 级别 | 标签 |
|-----|------|------|------|
| `tools.executor.overview` | Executor 可选择的工具 | Section | tools, executor |
| `tools.esmfold.spec` | ESMFold 工具规约 | Block | tools, esmfold, structure_prediction |
| `tools.alphafold.spec` | AlphaFold/OpenFold 工具规约 | Block | tools, alphafold, structure_prediction |
| `tools.adapter.constraints` | ToolAdapter 设计原则与约束 | Spec-Item | tools, adapter, constraints |

---

## 按文档分组的规范统计

| 文档 | Section | Block | Spec-Item | 总计 |
|------|---------|-------|-----------|------|
| architecture.md | 5 | 3 | 8 | 16 |
| agent-design.md | 8 | 9 | 9 | 26 |
| core-algorithm-spec.md | 2 | 6 | 3 | 11 |
| system-implementation-design.md | 2 | 4 | 5 | 11 |
| implementation_index.md | 1 | 0 | 0 | 1 |
| llm_provider_guide.md | 1 | 1 | 0 | 2 |
| snapshot-recovery.md | 1 | 2 | 0 | 3 |
| remote_model_invocation.md | 2 | 1 | 0 | 3 |
| tools-catalog.md | 1 | 2 | 1 | 4 |
| hitl-extension.md | 0 | 0 | 0 | 0 (differential index) |
| **总计** | **23** | **28** | **26** | **77** |

**注**: hitl-extension.md 是差分索引文档，不包含独立定义的 SID，仅通过引用汇总其他文档的规范。

---

## 粒度分布

| 粒度 | 数量 | 占比 |
|------|------|------|
| Section | 23 | 30% |
| Block | 28 | 36% |
| Spec-Item | 26 | 34% |

---

## 按主题快速索引

详见 [topic_views.json](./topic_views.json) 获取以下主题的规范聚合：

- **hitl**: Human-in-the-loop 相关规范
- **planning**: 任务规划相关规范
- **execution**: 执行相关规范
- **observability**: 可观测性相关规范
- **llm_provider**: LLM Provider 接入与使用
- **snapshot_recovery**: 快照恢复与断点续跑
- **remote_model_invocation**: 远程模型调用与适配器接入

---

## 使用说明

### 1. 查找特定规范

**通过 SID 查找**：
1. 在本文档中搜索 SID（如 `arch.contracts.pending_action`）
2. 查看对应的文档路径和行号
3. 使用 locator 信息精确定位

**通过标签查找**：
1. 确定你关心的标签（如 `hitl`, `planning`, `execution`）
2. 查看 [topic_views.json](./topic_views.json) 获取聚合列表

### 2. 机器检索

**使用 index.json**：
```bash
# 提取所有 HITL 相关规范
jq '.specs[] | select(.tags | contains(["hitl"]))' index.json

# 查找特定 SID 的定位信息
jq '.specs[] | select(.sid == "arch.contracts.pending_action")' index.json
```

### 3. 依赖追踪

每个规范的 `depends_on` 字段列出了其依赖的其他 SID。可用于：
- 理解规范之间的关系
- 检测循环依赖
- 确定最小注入上下文

---

## 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| 1.0 | 2026-01-11 | 索引 77 个规范，覆盖 10 个文档（新增 Remote Model Invocation 索引） |

---

**本文档由 `index.json` 生成，任何修改应同步更新 JSON 索引。**
