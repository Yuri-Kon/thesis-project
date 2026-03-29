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
| `planner` | agent-design.md（接口）<br>core-algorithm-spec.md（算法依据）<br>runtime-adaptation-formalization.md（运行时形式化） | PlannerAgent 接口定义在 agent-design.md；候选评分与动作选择依据在 core-algorithm-spec.md；belief-state、schema、runtime_adjustment 与 stop 形式化在 runtime-adaptation-formalization.md |
| `executor` | agent-design.md | ExecutorAgent 接口与职责边界 |
| `safety` | agent-design.md | SafetyAgent 接口与职责边界 |
| `summarizer` | agent-design.md | SummarizerAgent 接口与职责边界 |
| `tools` | tools-catalog.md（目录与适配约束）<br>active-tool-metadata-profile.md（活跃工具元数据） | tools-catalog.md 负责工具目录与 ToolAdapter 约束；active-tool-metadata-profile.md 负责当前活跃工具的成本/风险/恢复先验 |
| `workflow` | de-novo-workflow.md | de novo 工作流分层、模块化与循环控制 |
| `interface` | interaction-entry-surfaces.md | Web 主操纵空间、CLI 辅助入口、无头环境兼容与双入口协同 |
| `api` | system-implementation-design.md | REST API 端点定义与契约 |
| `obs` | system-implementation-design.md | 可观测性（EventLog）、日志模式与约束 |
| `storage` | system-implementation-design.md | 数据存储与持久化 |
| `kg` | system-implementation-design.md | ProteinToolKG 知识图谱模式与实现落点 |
| `impl` | system-implementation-design.md | 实现层总览、技术栈与运行时落点 |
| `algo` | core-algorithm-spec.md（算法依据）<br>runtime-adaptation-formalization.md（公式与 schema） | 核心问题建模、候选结构和主流程在 core-algorithm-spec.md；belief-state、六类 schema 与 runtime 公式在 runtime-adaptation-formalization.md |
| `experiment` | algorithm-group-paper-mapping.md | 历史实现组、外部对照组与论文主结果组的统一映射 |
| `hitl` | hitl-extension.md（差分索引）<br>architecture.md（核心契约）<br>agent-design.md（Agent 行为） | HITL 是跨文档概念：契约在 architecture.md，行为边界在 agent-design.md，hitl-extension.md 负责差分汇总 |

---

## 核心 SID 列表（按 Domain 分组）

### `arch` Domain（SSOT: architecture.md）

| SID | 说明 | 粒度 |
|-----|------|------|
| `SID:arch.overview.layers` | 分层架构 | Section |
| `SID:arch.components.overview` | 组件视图 | Section |
| `SID:arch.execution.nextflow_boundary` | 执行后端边界(Nextflow) | Block |
| `SID:arch.flow.end_to_end` | 运行视图与时序图 | Section |
| `SID:arch.contracts.pending_action` | PendingAction 契约定义 | Spec-Item |
| `SID:arch.contracts.decision` | Decision 契约定义 | Spec-Item |
| `SID:arch.contracts.task_snapshot` | TaskSnapshot 契约定义 | Spec-Item |
| `SID:arch.dataflow.overview` | 数据流概览 | Section |
| `SID:arch.contracts.plan` | Plan 契约定义（架构层视角） | Spec-Item |
| `SID:arch.kg.overview` | ProteinToolKG 在架构中的位置 | Block |

### `fsm` Domain（SSOT: architecture.md）

| SID | 说明 | 粒度 |
|-----|------|------|
| `SID:fsm.lifecycle.overview` | 任务生命周期与状态机 | Section |
| `SID:fsm.states.definitions` | FSM 状态完整定义表 | Block |
| `SID:fsm.states.waiting_plan_confirm` | WAITING_PLAN_CONFIRM 状态定义 | Spec-Item |
| `SID:fsm.states.waiting_patch_confirm` | WAITING_PATCH_CONFIRM 状态定义 | Spec-Item |
| `SID:fsm.states.waiting_replan_confirm` | WAITING_REPLAN_CONFIRM 状态定义 | Spec-Item |
| `SID:fsm.transitions.overview` | 状态转换规则总览 | Spec-Item |

### `agent` Domain（SSOT: agent-design.md）

| SID | 说明 | 粒度 |
|-----|------|------|
| `SID:agent.overview.introduction` | Agent体系总览 | Section |
| `SID:agent.overview.roles` | Agent 角色列表 | Block |
| `SID:agent.contracts.overview` | 核心数据结构契约总览 | Section |
| `SID:agent.contracts.protein_design_task` | ProteinDesignTask 数据结构 | Block |
| `SID:agent.contracts.plan` | Plan 数据结构（Agent 层视角） | Block |
| `SID:agent.contracts.step_result` | StepResult 数据结构 | Block |
| `SID:agent.contracts.design_result` | DesignResult 数据结构 | Block |
| `SID:agent.contracts.safety_result` | SafetyResult 数据结构 | Block |
| `SID:agent.hitl.overview` | HITL 机制在 Agent 层的概述 | Section |
| `SID:agent.hitl.universal_constraints` | Agent 层 HITL 统一约束 | Spec-Item |

### `planner` Domain（SSOT: agent-design.md / core-algorithm-spec.md / runtime-adaptation-formalization.md）

| SID | 说明 | 粒度 |
|-----|------|------|
| `SID:planner.interface.overview` | PlannerAgent 接口总览 | Section |
| `SID:planner.hitl.responsibilities` | PlannerAgent HITL 职责 | Section |
| `SID:planner.hitl.plan_confirm` | 初始 Plan 确认阶段 | Block |
| `SID:planner.responsibilities.must` | PlannerAgent 必须做的事 | Spec-Item |
| `SID:planner.responsibilities.must_not` | PlannerAgent 不得做的事 | Spec-Item |
| `SID:planner.contracts.candidate_schema` | Candidate 对象模式总览 | Spec-Item |
| `SID:planner.contracts.plan_candidate` | PlanCandidate 模式定义 | Spec-Item |
| `SID:planner.contracts.patch_candidate` | PatchCandidate 模式定义 | Spec-Item |
| `SID:planner.contracts.replan_candidate` | ReplanCandidate 模式定义 | Spec-Item |
| `SID:planner.contracts.io_overview` | Planner 输入输出契约 | Block |
| `SID:planner.algorithm.tool_retrieval` | 工具检索算法 | Block |
| `SID:planner.algorithm.candidate_scoring` | 候选方案评分规则 | Block |
| `SID:planner.algorithm.runtime_state_estimation` | 运行时状态估计（Lite belief-state） | Block |
| `SID:planner.algorithm.runtime_reranking` | 运行时重排序与预算感知裁剪 | Block |
| `SID:planner.algorithm.runtime_action_selection` | 动作选择与恢复感知控制 | Block |
| `SID:planner.algorithm.hitl_gate` | HITL 门控决策规则 | Block |
| `SID:planner.algorithm.decision_application` | Decision 应用逻辑 | Block |
| `SID:planner.runtime.belief_state_schema` | Lite belief-state 模式 | Block |
| `SID:planner.algorithm.runtime_update_rules` | 运行时状态更新规则 | Block |
| `SID:planner.algorithm.runtime_adjustment_formula` | runtime_adjustment 公式 | Block |
| `SID:planner.algorithm.action_priority_resolution` | 动作优先级与冲突消解 | Block |
| `SID:planner.algorithm.stop_semantics` | stop 语义与终止条件 | Block |

### `executor` Domain（SSOT: agent-design.md）

| SID | 说明 | 粒度 |
|-----|------|------|
| `SID:executor.hitl.responsibilities` | ExecutorAgent HITL 职责 | Section |
| `SID:executor.hitl.patch_confirm` | Patch 触发与确认 | Block |
| `SID:executor.responsibilities.must` | ExecutorAgent 必须做的事 | Spec-Item |
| `SID:executor.responsibilities.must_not` | ExecutorAgent 不得做的事 | Spec-Item |

### `safety` Domain（SSOT: agent-design.md）

| SID | 说明 | 粒度 |
|-----|------|------|
| `SID:safety.hitl.responsibilities` | SafetyAgent HITL 职责 | Section |
| `SID:safety.hitl.replan_trigger` | 触发 WAITING_REPLAN_CONFIRM 的条件 | Block |
| `SID:safety.responsibilities.must` | SafetyAgent 必须做的事 | Spec-Item |
| `SID:safety.responsibilities.must_not` | SafetyAgent 不得做的事 | Spec-Item |

### `summarizer` Domain（SSOT: agent-design.md）

| SID | 说明 | 粒度 |
|-----|------|------|
| `SID:summarizer.hitl.responsibilities` | SummarizerAgent HITL 职责 | Section |
| `SID:summarizer.responsibilities.must` | SummarizerAgent 必须做的事 | Spec-Item |
| `SID:summarizer.responsibilities.must_not` | SummarizerAgent 不得做的事 | Spec-Item |

### `workflow` Domain（SSOT: de-novo-workflow.md）

| SID | 说明 | 粒度 |
|-----|------|------|
| `SID:workflow.overview.scope` | 范围与定位 | Section |
| `SID:workflow.design.goals` | 设计目标与约束 | Section |
| `SID:workflow.layers.six_stage` | 六阶段分层 | Section |
| `SID:workflow.stage.sequence_exploration` | 序列探索（Sequence Exploration） | Block |
| `SID:workflow.stage.structure_projection` | 结构映射（Structure Projection） | Block |
| `SID:workflow.stage.quality_gate` | 结构与序列质量门禁（Quality Gate） | Block |
| `SID:workflow.stage.structure_refinement` | 结构条件下的序列精修（Structure-conditioned Refinement） | Block |
| `SID:workflow.stage.objective_scoring` | 目标/功能/物性评估（Objective Scoring） | Block |
| `SID:workflow.stage.patch_replan_control` | Patch/Replan 控制层（Control Layer） | Block |
| `SID:workflow.stage.high_cost_control` | 高代价步骤与运行时恢复感知控制 | Block |
| `SID:workflow.modules.interface` | 模块化接口与可替换原则 | Section |
| `SID:workflow.loops.and_crosscut` | 可循环步骤与贯穿步骤 | Section |
| `SID:workflow.integration.responsibilities` | 分工映射（Planner/Executor/Safety） | Section |
| `SID:workflow.examples.template` | 示例流程模板（非线性） | Section |

### `interface` Domain（SSOT: interaction-entry-surfaces.md）

| SID | 说明 | 粒度 |
|-----|------|------|
| `SID:interface.overview.entry_surfaces` | 交互入口总览 | Section |
| `SID:interface.scope.positioning` | 范围与定位 | Section |
| `SID:interface.goals.design_targets` | 设计目标与非目标 | Section |
| `SID:interface.architecture.dual_surface` | 双入口架构 | Section |
| `SID:interface.web.primary_workspace` | Web 端：主操纵空间 | Block |
| `SID:interface.cli.headless_entry` | CLI：控制台与无头环境入口 | Block |
| `SID:interface.cross_surface.relationship` | Web 与 CLI 的协同关系 | Block |
| `SID:interface.scenarios.applicability` | 适用场景 | Section |
| `SID:interface.scenarios.web_first` | Web 优先场景 | Block |
| `SID:interface.scenarios.cli_first` | CLI 优先场景 | Block |
| `SID:interface.scenarios.hybrid` | 协同切换场景 | Block |
| `SID:interface.cli.capability_scope` | CLI 功能边界与命令面 | Section |
| `SID:interface.cli.headless_guarantee` | CLI 无头环境最小闭环保证 | Block |
| `SID:interface.cli.web_handoff` | CLI 向 Web 的显式跳转约束 | Block |
| `SID:interface.cli.command_tree` | CLI 建议命令树 | Block |
| `SID:interface.web.capability_scope` | Web 功能边界 | Section |
| `SID:interface.web.information_architecture` | Web 页面信息架构 | Block |
| `SID:interface.constraints.contract_alignment` | 与现有系统契约的对齐要求 | Section |
| `SID:interface.cli.backend_compatibility` | CLI 后端形态兼容性 | Block |
| `SID:interface.integration.api_boundary` | API 集成边界 | Block |
| `SID:interface.rollout.milestones` | 演进路线 | Section |

### `algo` Domain（SSOT: core-algorithm-spec.md / runtime-adaptation-formalization.md）

| SID | 说明 | 粒度 |
|-----|------|------|
| `SID:algo.scope.overview` | 算法规范范围说明 | Section |
| `SID:algo.definitions.overview` | 算法定义总览 | Section |
| `SID:algo.adaptive.problem_formulation` | 高代价工作流中的自适应规划问题 | Section |
| `SID:algo.adaptive.optimization_objective` | 优化目标与效用分解 | Block |
| `SID:algo.runtime.formalization` | 运行时自适应形式化 | Section |
| `SID:algo.runtime.scope` | 文档目的与适用范围 | Section |
| `SID:algo.runtime.design_basis` | 建模立场与设计依据 | Block |
| `SID:algo.schemas.overview` | 六类 Schema 总览 | Section |
| `SID:algo.schema.cost` | Cost Schema | Block |
| `SID:algo.schema.risk` | Risk Schema | Block |
| `SID:algo.schema.recovery` | Recovery Schema | Block |
| `SID:algo.schema.state` | State Schema | Block |
| `SID:algo.schema.observation` | Observation Schema | Block |
| `SID:algo.schema.action_utility` | Action-Utility Schema | Block |

### `api` Domain（SSOT: system-implementation-design.md）

| SID | 说明 | 粒度 |
|-----|------|------|
| `SID:api.rest.overview` | REST API 总览 | Section |
| `SID:api.rest.create_task` | POST /tasks 端点 | Spec-Item |
| `SID:api.rest.get_pending_actions` | GET /pending-actions 端点 | Spec-Item |
| `SID:api.rest.submit_decision` | POST /pending-actions/{id}/decision 端点 | Spec-Item |
| `SID:api.rest.get_report` | GET /tasks/{task_id}/report 端点 | Spec-Item |

### `obs` Domain（SSOT: system-implementation-design.md）

| SID | 说明 | 粒度 |
|-----|------|------|
| `SID:obs.observability.overview` | 日志与可观测设计 | Block |
| `SID:obs.eventlog.schema` | EventLog 单条日志记录结构 | Block |
| `SID:obs.eventlog.mandatory_events` | 事件日志写入约束（必须遵守） | Spec-Item |

### `impl` Domain（SSOT: system-implementation-design.md）

| SID | 说明 | 粒度 |
|-----|------|------|
| `SID:impl.runtime.integration_guidelines` | 运行时集成与持久化指南 | Block |
| `SID:impl.overview.introduction` | 实现层总览 | Section |
| `SID:impl.techstack.overview` | 技术栈选型 | Block |
| `SID:impl.runtime_state.persistence` | RuntimeState / BeliefState 与持久化边界 | Block |
| `SID:impl.nextflow.control_flow_constraints` | Nextflow 接入边界与控制流约束 | Block |
| `SID:impl.planner.tool_resolution` | Planner 工具解析与 KG-only 约束 | Block |
| `SID:impl.planner.training_and_serving` | Planner 训练与服务化落点 | Block |
| `SID:impl.index.codebase_overview` | 实现代码索引与结构化总览 | Section |
| `SID:impl.llm_provider.guide` | LLM Provider 集成指南 | Section |
| `SID:impl.llm_provider.external_providers` | OpenAICompatibleProvider | Block |
| `SID:impl.planner_llm.overview` | Planner 外部 LLM 接入规范 | Section |
| `SID:impl.planner_llm.provider_selection` | Provider 选型与适配层建议 | Block |
| `SID:impl.planner_llm.parameter_baseline` | Planner 参数基线 | Block |
| `SID:impl.planner_llm.structured_output_contract` | 结构化输出契约 | Block |
| `SID:impl.planner_llm.config_contract` | Provider 配置契约 | Block |
| `SID:impl.planner_llm.openai` | OpenAI GPT-5.4 接入 | Block |
| `SID:impl.planner_llm.anthropic` | Anthropic Claude 接入 | Block |
| `SID:impl.planner_llm.deepseek` | DeepSeek 接入 | Block |
| `SID:impl.planner_llm.qwen` | Qwen / DashScope 接入 | Block |
| `SID:impl.planner_llm.glm` | GLM / 智谱 接入 | Block |
| `SID:impl.planner_llm.nemotron` | NVIDIA NIM Nemotron 接入 | Block |
| `SID:impl.planner_llm.validation_and_fallback` | 输出校验、重试与回退 | Block |
| `SID:impl.snapshot_recovery.overview` | Snapshot Recovery for Remote Jobs | Section |
| `SID:impl.snapshot_recovery.snapshot_schema` | 快照结构 | Block |
| `SID:impl.snapshot_recovery.recovery_flow` | 恢复流程 | Block |
| `SID:impl.remote_model_invocation.overview` | Remote Model Invocation Service | Section |
| `SID:impl.remote_model_invocation.components` | 核心组件 | Block |
| `SID:impl.remote_model_invocation.rest_api` | REST API 规范 | Section |
| `SID:impl.remote_model_invocation.nim_failure_codes` | NVIDIA NIM 失败码定义 | Block |
| `SID:impl.remote_model_invocation.nvidia_nim` | NVIDIA NIM 集成 | Section |
| `SID:impl.remote_model_invocation.provider_config` | Provider 配置系统 | Block |

### `tools` Domain（SSOT: tools-catalog.md / active-tool-metadata-profile.md）

| SID | 说明 | 粒度 |
|-----|------|------|
| `SID:tools.executor.overview` | Executor 可选择的工具 | Section |
| `SID:tools.protgpt2.spec` | ProtGPT2 (PLM) 工具规约 | Block |
| `SID:tools.esmfold.spec` | ESMFold 工具规约 | Block |
| `SID:tools.nim_esmfold.spec` | NIM ESMFold 工具规约 | Block |
| `SID:tools.alphafold.spec` | AlphaFold/OpenFold 工具规约 | Block |
| `SID:tools.integration.priority` | 工具集成优先级 | Block |
| `SID:tools.kg_extension.draft` | KG 扩展草案 | Block |
| `SID:tools.adapter.constraints` | ToolAdapter 设计原则与约束 | Spec-Item |
| `SID:tools.metadata.active_profile` | 活跃工具元数据画像 | Section |
| `SID:tools.metadata.scope` | 工具元数据范围与用途 | Section |
| `SID:tools.metadata.schema` | 工具元数据字段规范 | Block |
| `SID:tools.metadata.assignment_principles` | 元数据赋值原则 | Block |
| `SID:tools.metadata.active_table` | 活跃工具元数据表 | Block |
| `SID:tools.metadata.derived_metrics` | 派生指标计算 | Block |
| `SID:tools.metadata.usage_rules` | 工具元数据使用规则 | Block |

### `experiment` Domain（SSOT: algorithm-group-paper-mapping.md）

| SID | 说明 | 粒度 |
|-----|------|------|
| `SID:experiment.group_mapping.overview` | 实验分组映射总览 | Section |
| `SID:experiment.group_mapping.scope` | 实验命名统一范围 | Section |
| `SID:experiment.group_mapping.narrative_layers` | 三层实验叙事结构 | Block |
| `SID:experiment.group_mapping.a_to_paper` | 历史组到论文组映射 | Block |
| `SID:experiment.group_mapping.paper_mainline` | 论文主线比较组 | Block |
| `SID:experiment.group_mapping.metric_responsibility` | 组别与指标责任矩阵 | Block |
| `SID:experiment.group_mapping.table_layout` | 论文表格布局建议 | Block |
| `SID:experiment.group_mapping.naming` | 正文命名规范 | Block |
| `SID:experiment.group_mapping.claim_template` | 论文主命题模板 | Block |

### `hitl` Domain（跨文档概念，差分索引在 hitl-extension.md）

**HITL 机制为跨文档概念，分散在多个 SSOT 文档中：**

| 规约类别 | SSOT 文档 | 核心 SID |
|---------|----------|---------|
| HITL 核心契约（PendingAction/Decision/TaskSnapshot） | architecture.md | `SID:arch.contracts.pending_action`<br>`SID:arch.contracts.decision`<br>`SID:arch.contracts.task_snapshot` |
| FSM 等待态语义 | architecture.md | `SID:fsm.states.waiting_plan_confirm`<br>`SID:fsm.states.waiting_patch_confirm`<br>`SID:fsm.states.waiting_replan_confirm` |
| Agent 行为边界 | agent-design.md | `SID:agent.hitl.universal_constraints`<br>`SID:planner.hitl.responsibilities`<br>`SID:executor.hitl.patch_confirm`<br>`SID:safety.hitl.replan_trigger` |
| 算法门控与 stop 语义 | core-algorithm-spec.md<br>runtime-adaptation-formalization.md | `SID:planner.algorithm.hitl_gate`<br>`SID:planner.algorithm.decision_application`<br>`SID:planner.algorithm.stop_semantics` |

## 使用规则

### 1. SSOT 原则

- 同一概念只允许一个权威来源。
- 支撑文档可以补充说明，但不得重定义 SSOT 语义。
- 当正文迁移时，必须同步更新 `index.json`、`topic_views.json` 与本映射表。

### 2. SID 引用优先级

- 引用契约、状态、算法公式时，优先使用 SSOT 文档中的 SID。
- 说明性文档可引用 SSOT，但不应替代 SSOT。
- 若新增支撑文档承载正式公式或表格，应在本映射表显式声明。

### 3. Claude Code Skill 集成规则

- `docslice --sid` 应直接命中 SSOT 中的 SID。
- `docslice --topic` 应优先返回 topic view 中标记为 `critical` / `high` 的核心规范。
- 当 topic 需要跨文档组合时，以本映射表的 SSOT 定义为准。

### 4. Docslice 脚本约定

- `docslice` 脚本应优先从 SSOT 文档中提取规范。
- 若 locator 与文档边界漂移，应优先修复索引，而不是依赖长期 fallback。
- 新增 SID 后必须同时更新 `index.json`、`topic_views.json` 和本映射表。

## 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| 1.4 | 2026-03-29 | 新增 interface 域及 interaction-entry-surfaces.md，定义 Web/CLI 双入口定位、最小 CLI 闭环与双入口协同边界 |
| 1.3 | 2026-03-29 | 纳入 runtime-adaptation-formalization、active-tool-metadata-profile 与 algorithm-group-paper-mapping；新增 experiment 域并对齐 planning/execution/observability 的 SSOT 入口 |
| 1.2 | 2026-03-24 | 新增自适应规划相关 SID，补充 workflow/impl/algo 映射，并对齐 docslice 检索入口 |
| 1.1 | 2026-01-11 | 首版 SSOT 映射，覆盖架构、FSM、Agent、工具、实现与 HITL 概念 |
