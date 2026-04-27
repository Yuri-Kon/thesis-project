# Specification Index（规范索引）

> 本文档是设计规范的**人类可读索引**，与 `index.json` 对应。
>
> 提供按 Domain 和文档组织的规范清单，便于快速定位和浏览。
>
> **机器可读版本**: [index.json](./index.json)
> **主题视图**: [topic_views.json](./topic_views.json)

---

## 索引总览

**版本**: 1.6
**生成日期**: 2026-04-27
**总规范数**: 204
**文档数**: 20

---

## 文档列表

| doc_key | 标题 | 路径 | 状态 | 依赖 |
|---------|------|------|------|------|
| `arch` | 系统总体架构 | [docs/design/architecture.md](../design/architecture.md) | stable | - |
| `agent` | Agent设计文档 | [docs/design/agent-design.md](../design/agent-design.md) | stable | arch |
| `algo` | 核心算法规范 | [docs/design/core-algorithm-spec.md](../design/core-algorithm-spec.md) | stable | arch, agent, workflow, tools, impl |
| `algo_runtime` | 运行时自适应形式化 | [docs/design/runtime-adaptation-formalization.md](../design/runtime-adaptation-formalization.md) | stable | algo, workflow, tools, impl |
| `de_novo_workflow` | De Novo Workflow：分层与模块化设计 | [docs/design/de-novo-workflow.md](../design/de-novo-workflow.md) | stable | arch, agent, algo, tools |
| `impl` | 系统实现设计 | [docs/design/system-implementation-design.md](../design/system-implementation-design.md) | stable | arch, agent |
| `impl_index` | 实现代码索引与结构化总览 | [docs/impl/implementation_index.md](../impl/implementation_index.md) | stable | impl |
| `impl_llm_provider` | LLM Provider 集成指南 | [docs/impl/llm_provider_guide.md](../impl/llm_provider_guide.md) | stable | impl |
| `impl_planner_llm` | Planner 外部 LLM 接入规范 | [docs/impl/planner_llm_api_integration.md](../impl/planner_llm_api_integration.md) | stable | impl, agent |
| `impl_snapshot_recovery` | Snapshot Recovery for Remote Jobs | [docs/impl/snapshot-recovery.md](../impl/snapshot-recovery.md) | stable | impl |
| `impl_remote_model_invocation` | Remote Model Invocation Service | [docs/impl/remote_model_invocation.md](../impl/remote_model_invocation.md) | stable | impl |
| `tools` | Tools Catalog | [docs/design/tools-catalog.md](../design/tools-catalog.md) | stable | impl, algo |
| `tools_metadata` | 活跃工具元数据画像 | [docs/design/active-tool-metadata-profile.md](../design/active-tool-metadata-profile.md) | stable | tools, algo_runtime, impl |
| `hitl` | Human-in-the-loop 扩展设计 | [docs/design/hitl-extension.md](../design/hitl-extension.md) | stable | arch, agent, impl, algo |
| `interface_surfaces` | 交互入口设计：Web 主界面与 CLI 辅助入口 | [docs/design/interaction-entry-surfaces.md](../design/interaction-entry-surfaces.md) | stable | arch, hitl, impl |
| `interface_web_workspace` | Web 主工作台设计：全信息展示、结构可视化与交互确认 | [docs/design/web-operator-workspace.md](../design/web-operator-workspace.md) | stable | interface_surfaces, impl, hitl, tools |
| `interface_cli_workflow` | CLI 交互设计：无头环境闭环、批处理与 Web 协同 | [docs/design/cli-operator-workflow.md](../design/cli-operator-workflow.md) | stable | interface_surfaces, impl, hitl |
| `algocore` | 核心算法定义 | [docs/algorithm-and-llm/core-algorithm-define.md](../algorithm-and-llm/core-algorithm-define.md) | stable | algo, de_novo_workflow |
| `llmtrain` | Planner 大模型能力要求与专用训练方案 | [docs/algorithm-and-llm/train-llm.md](../algorithm-and-llm/train-llm.md) | stable | algo, impl_llm_provider |
| `experiment_mapping` | 实验分组与论文叙事映射 | [docs/experiment/algorithm-group-paper-mapping.md](../experiment/algorithm-group-paper-mapping.md) | stable | algo, de_novo_workflow |

---

## 按 Domain 分组的规范索引

### 1. `arch` Domain（总体架构）

**SSOT 文档**: architecture.md

| SID | 标题 | 级别 | 标签 |
|-----|------|------|------|
| `arch.overview.layers` | 分层架构 | Section | arch, overview, layers |
| `arch.components.overview` | 组件视图 | Section | arch, components |
| `arch.execution.nextflow_boundary` | 执行后端边界(Nextflow) | Block | arch, execution, nextflow, boundary |
| `arch.flow.end_to_end` | 运行视图与时序图 | Section | arch, flow, runtime |
| `arch.contracts.pending_action` | PendingAction 契约定义 | Spec-Item | arch, contracts, hitl, pending_action |
| `arch.contracts.decision` | Decision 契约定义 | Spec-Item | arch, contracts, hitl, decision |
| `arch.contracts.task_snapshot` | TaskSnapshot 契约定义 | Spec-Item | arch, contracts, hitl, snapshot |
| `arch.dataflow.overview` | 数据流概览 | Section | arch, dataflow |
| `arch.contracts.plan` | Plan 契约定义（架构层视角） | Spec-Item | arch, contracts, planning |
| `arch.kg.overview` | ProteinToolKG 在架构中的位置 | Block | arch, kg, knowledge_graph |

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

**SSOT 文档**: agent-design.md / core-algorithm-spec.md / runtime-adaptation-formalization.md

| SID | 标题 | 级别 | 标签 |
|-----|------|------|------|
| `planner.interface.overview` | PlannerAgent 接口总览 | Section | planner, interface, agent |
| `planner.hitl.responsibilities` | PlannerAgent HITL 职责 | Section | planner, hitl, responsibilities |
| `planner.hitl.plan_confirm` | 初始 Plan 确认阶段 | Block | planner, hitl, planning |
| `planner.responsibilities.must` | PlannerAgent 必须做的事 | Spec-Item | planner, responsibilities, must |
| `planner.responsibilities.must_not` | PlannerAgent 不得做的事 | Spec-Item | planner, responsibilities, must_not |
| `planner.contracts.candidate_schema` | Candidate 对象模式总览 | Spec-Item | planner, contracts, candidate |
| `planner.contracts.plan_candidate` | PlanCandidate 模式定义 | Spec-Item | planner, contracts, candidate, planning |
| `planner.contracts.patch_candidate` | PatchCandidate 模式定义 | Spec-Item | planner, contracts, candidate, execution |
| `planner.contracts.replan_candidate` | ReplanCandidate 模式定义 | Spec-Item | planner, contracts, candidate, planning |
| `planner.contracts.io_overview` | Planner 输入输出契约 | Block | planner, contracts, io |
| `planner.algorithm.tool_retrieval` | 工具检索算法 | Block | planner, algorithm, tool_retrieval |
| `planner.algorithm.candidate_scoring` | 候选方案评分规则 | Block | planner, algorithm, scoring |
| `planner.algorithm.runtime_state_estimation` | 运行时状态估计（Lite belief-state） | Block | planner, algorithm, runtime_state_estimation |
| `planner.algorithm.runtime_reranking` | 运行时重排序与预算感知裁剪 | Block | planner, algorithm, runtime_reranking |
| `planner.algorithm.runtime_action_selection` | 动作选择与恢复感知控制 | Block | planner, algorithm, runtime_action_selection |
| `planner.algorithm.hitl_gate` | HITL 门控决策规则 | Block | planner, algorithm, hitl |
| `planner.algorithm.decision_application` | Decision 应用逻辑 | Block | planner, algorithm, hitl, decision |
| `planner.runtime.belief_state_schema` | Lite belief-state 模式 | Block | planner, runtime, belief_state, schema |
| `planner.algorithm.runtime_update_rules` | 运行时状态更新规则 | Block | planner, algorithm, runtime, update_rules |
| `planner.algorithm.runtime_adjustment_formula` | runtime_adjustment 公式 | Block | planner, algorithm, runtime_adjustment, scoring |
| `planner.algorithm.action_priority_resolution` | 动作优先级与冲突消解 | Block | planner, algorithm, priority, action_selection |
| `planner.algorithm.stop_semantics` | stop 语义与终止条件 | Block | planner, algorithm, stop, hitl |

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

### 8. `workflow` Domain（de novo 工作流）

**SSOT 文档**: de-novo-workflow.md

| SID | 标题 | 级别 | 标签 |
|-----|------|------|------|
| `workflow.overview.scope` | 范围与定位 | Section | workflow, overview, scope |
| `workflow.design.goals` | 设计目标与约束 | Section | workflow, design, goals |
| `workflow.layers.six_stage` | 六阶段分层 | Section | workflow, layers, six_stage |
| `workflow.stage.sequence_exploration` | 序列探索（Sequence Exploration） | Block | workflow, stage, sequence_exploration |
| `workflow.stage.structure_projection` | 结构映射（Structure Projection） | Block | workflow, stage, structure_projection |
| `workflow.stage.quality_gate` | 结构与序列质量门禁（Quality Gate） | Block | workflow, stage, quality_gate |
| `workflow.stage.structure_refinement` | 结构条件下的序列精修（Structure-conditioned Refinement） | Block | workflow, stage, structure_refinement |
| `workflow.stage.objective_scoring` | 目标/功能/物性评估（Objective Scoring） | Block | workflow, stage, objective_scoring |
| `workflow.stage.patch_replan_control` | Patch/Replan 控制层（Control Layer） | Block | workflow, stage, patch_replan_control |
| `workflow.stage.high_cost_control` | 高代价步骤与运行时恢复感知控制 | Block | workflow, stage, high_cost_control |
| `workflow.modules.interface` | 模块化接口与可替换原则 | Section | workflow, modules, interface |
| `workflow.loops.and_crosscut` | 可循环步骤与贯穿步骤 | Section | workflow, loops, crosscut |
| `workflow.integration.responsibilities` | 分工映射（Planner/Executor/Safety） | Section | workflow, integration, responsibilities |
| `workflow.examples.template` | 示例流程模板（非线性） | Section | workflow, examples, template |

---

### 9. `algo` Domain（算法规范）

**SSOT 文档**: core-algorithm-spec.md / runtime-adaptation-formalization.md

| SID | 标题 | 级别 | 标签 |
|-----|------|------|------|
| `algo.scope.overview` | 算法规范范围说明 | Section | algo, scope |
| `algo.definitions.overview` | 算法定义总览 | Section | algo, definitions |
| `algo.adaptive.problem_formulation` | 高代价工作流中的自适应规划问题 | Section | algo, adaptive, problem_formulation |
| `algo.adaptive.optimization_objective` | 优化目标与效用分解 | Block | algo, adaptive, optimization_objective |
| `algo.runtime.formalization` | 运行时自适应形式化 | Section | algo, runtime, formalization |
| `algo.runtime.scope` | 文档目的与适用范围 | Section | algo, runtime, scope |
| `algo.runtime.design_basis` | 建模立场与设计依据 | Block | algo, runtime, design_basis |
| `algo.schemas.overview` | 六类 Schema 总览 | Section | algo, runtime, schemas |
| `algo.schema.cost` | Cost Schema | Block | algo, schema, cost |
| `algo.schema.risk` | Risk Schema | Block | algo, schema, risk |
| `algo.schema.recovery` | Recovery Schema | Block | algo, schema, recovery |
| `algo.schema.state` | State Schema | Block | algo, schema, state, belief_state |
| `algo.schema.observation` | Observation Schema | Block | algo, schema, observation |
| `algo.schema.action_utility` | Action-Utility Schema | Block | algo, schema, action_utility |

---

### 10. `api` Domain（REST API）

**SSOT 文档**: system-implementation-design.md

| SID | 标题 | 级别 | 标签 |
|-----|------|------|------|
| `api.rest.overview` | REST API 总览 | Section | api, rest |
| `api.rest.create_task` | POST /tasks 端点 | Spec-Item | api, rest, task |
| `api.rest.get_pending_actions` | GET /pending-actions 端点 | Spec-Item | api, rest, hitl, pending_actions |
| `api.rest.submit_decision` | POST /pending-actions/{id}/decision 端点 | Spec-Item | api, rest, hitl, decision |
| `api.rest.get_report` | GET /tasks/{task_id}/report 端点 | Spec-Item | api, rest, report |

---

### 11. `obs` Domain（可观测性）

**SSOT 文档**: system-implementation-design.md

| SID | 标题 | 级别 | 标签 |
|-----|------|------|------|
| `obs.observability.overview` | 日志与可观测设计 | Block | obs, observability, overview |
| `obs.eventlog.schema` | EventLog 单条日志记录结构 | Block | obs, eventlog, observability |
| `obs.eventlog.mandatory_events` | 事件日志写入约束（必须遵守） | Spec-Item | obs, eventlog, observability, hitl |

---

### 12. `interface` Domain（交互入口）

**SSOT 文档**: interaction-entry-surfaces.md

| SID | 标题 | 级别 | 标签 |
|-----|------|------|------|
| `interface.overview.entry_surfaces` | 交互入口总览 | Section | interface, overview, entry_surfaces |
| `interface.scope.positioning` | 范围与定位 | Section | interface, scope, positioning |
| `interface.goals.design_targets` | 设计目标与非目标 | Section | interface, goals, design |
| `interface.architecture.dual_surface` | 双入口架构 | Section | interface, architecture, dual_surface |
| `interface.web.primary_workspace` | Web 端：主操纵空间 | Block | interface, web, primary_workspace |
| `interface.cli.headless_entry` | CLI：控制台与无头环境入口 | Block | interface, cli, headless |
| `interface.cross_surface.relationship` | Web 与 CLI 的协同关系 | Block | interface, web, cli, collaboration |
| `interface.scenarios.applicability` | 适用场景 | Section | interface, scenarios, applicability |
| `interface.scenarios.web_first` | Web 优先场景 | Block | interface, scenarios, web |
| `interface.scenarios.cli_first` | CLI 优先场景 | Block | interface, scenarios, cli |
| `interface.scenarios.hybrid` | 协同切换场景 | Block | interface, scenarios, hybrid |
| `interface.cli.capability_scope` | CLI 功能边界与命令面 | Section | interface, cli, capabilities |
| `interface.cli.headless_guarantee` | CLI 无头环境最小闭环保证 | Block | interface, cli, requirements, headless |
| `interface.cli.web_handoff` | CLI 向 Web 的显式跳转约束 | Block | interface, cli, web, handoff |
| `interface.cli.command_tree` | CLI 建议命令树 | Block | interface, cli, commands |
| `interface.web.capability_scope` | Web 功能边界 | Section | interface, web, capabilities, react, ui_boundary |
| `interface.web.information_architecture` | Web 页面信息架构 | Block | interface, web, information_architecture |
| `interface.constraints.contract_alignment` | 与现有系统契约的对齐要求 | Section | interface, constraints, contract_alignment, react, eventlog |
| `interface.cli.backend_compatibility` | CLI 后端形态兼容性 | Block | interface, cli, requirements, compatibility |
| `interface.integration.api_boundary` | API 集成边界 | Block | interface, api, integration |
| `interface.rollout.milestones` | 演进路线 | Section | interface, rollout, milestones |
| `interface.web_workspace.overview` | Web 主工作台总览 | Section | interface, web, workspace, overview |
| `interface.web_workspace.framework_choice` | Web 框架选择与边界 | Section | interface, web, framework, fastapi, react, typescript |
| `interface.web_workspace.react_ui_boundary` | React UI 组织约束 | Block | interface, web, react, typescript, ui_boundary |
| `interface.web_workspace.design_principles` | Web 设计原则 | Section | interface, web, design, principles |
| `interface.web_workspace.primary_layout` | Web 顶层布局 | Section | interface, web, layout, workspace |
| `interface.web_workspace.page_topology` | Web 页面拓扑 | Block | interface, web, pages, topology |
| `interface.web_workspace.dashboard` | Dashboard 要求 | Block | interface, web, dashboard |
| `interface.web_workspace.task_detail` | Task Detail 要求 | Block | interface, web, task_detail |
| `interface.web_workspace.pending_review` | Pending Review 工作区 | Block | interface, web, pending_review, hitl |
| `interface.web_workspace.model_invocation_panel` | 模型调用工作台 | Block | interface, web, model_invocation, nvidia_nim |
| `interface.web_workspace.structure_visualization` | 结构可视化工作区 | Block | interface, web, structure_visualization, ngl |
| `interface.web_workspace.structure_metric_linking` | 结构与指标联动 | Block | interface, web, structure, metrics, linking |
| `interface.web_workspace.report_explorer` | 报告与产物浏览 | Block | interface, web, report, artifacts |
| `interface.web_workspace.interaction_patterns` | Web 交互模式 | Section | interface, web, interaction, patterns |
| `interface.web_workspace.state_sync` | Web 状态同步约束 | Block | interface, web, state_sync, contracts |
| `interface.web_workspace.visualization_fallback` | 可视化降级与网络约束 | Block | interface, web, visualization, fallback |
| `interface.web_workspace.milestones` | Web MVP 与演进 | Section | interface, web, rollout, milestones |
| `interface.cli_workflow.overview` | CLI 工作流总览 | Section | interface, cli, workflow, overview |
| `interface.cli_workflow.role_boundary` | CLI 定位与职责边界 | Section | interface, cli, role_boundary |
| `interface.cli_workflow.experience_modes` | CLI 体验模式 | Section | interface, cli, experience_modes |
| `interface.cli_workflow.command_groups` | CLI 命令分组 | Section | interface, cli, commands |
| `interface.cli_workflow.submit_flow` | CLI 提交流程 | Section | interface, cli, submit, workflow |
| `interface.cli_workflow.watch_flow` | CLI 轮询与值守流程 | Section | interface, cli, watch, polling |
| `interface.cli_workflow.pending_review` | CLI 待确认审查流程 | Section | interface, cli, pending_review, hitl |
| `interface.cli_workflow.noninteractive_mode` | CLI 非交互模式 | Section | interface, cli, automation, noninteractive |
| `interface.cli_workflow.output_profiles` | CLI 输出契约 | Section | interface, cli, output, json |
| `interface.cli_workflow.web_handoff` | CLI 与 Web 的协同跳转 | Section | interface, cli, web, handoff |
| `interface.cli_workflow.error_mapping` | CLI 错误呈现与恢复提示 | Section | interface, cli, errors, recovery |
| `interface.cli_workflow.headless_recovery` | CLI 无头恢复与审计 | Section | interface, cli, recovery, audit |
| `interface.cli_workflow.progressive_enhancement` | CLI 渐进增强边界 | Section | interface, cli, enhancement |
| `interface.cli_workflow.milestones` | CLI 演进顺序 | Section | interface, cli, rollout, milestones |

---

### 13. `impl` Domain（实现层）

**SSOT 文档**: system-implementation-design.md

| SID | 标题 | 级别 | 标签 |
|-----|------|------|------|
| `impl.runtime.integration_guidelines` | 运行时集成与持久化指南 | Block | impl, runtime, integration, persistence |
| `impl.overview.introduction` | 实现层总览 | Section | impl, overview |
| `impl.techstack.overview` | 技术栈选型 | Block | impl, techstack |
| `impl.runtime_state.persistence` | RuntimeState / BeliefState 与持久化边界 | Block | impl, runtime_state, persistence |
| `impl.nextflow.control_flow_constraints` | Nextflow 接入边界与控制流约束 | Block | impl, nextflow, control_flow, constraints |
| `impl.planner.tool_resolution` | Planner 工具解析与 KG-only 约束 | Block | impl, planner, tool_resolution, kg |
| `impl.planner.training_and_serving` | Planner 训练与服务化落点 | Block | impl, planner, training, serving |
| `impl.index.codebase_overview` | 实现代码索引与结构化总览 | Section | impl, index, codebase, overview |
| `impl.llm_provider.guide` | LLM Provider 集成指南 | Section | impl, llm_provider, guide, overview |
| `impl.llm_provider.external_providers` | OpenAICompatibleProvider | Block | impl, llm_provider, external, openai_compatible |
| `impl.planner_llm.overview` | Planner 外部 LLM 接入规范 | Section | impl, planner_llm, overview, integration |
| `impl.planner_llm.provider_selection` | Provider 选型与适配层建议 | Block | impl, planner_llm, provider_selection |
| `impl.planner_llm.parameter_baseline` | Planner 参数基线 | Block | impl, planner_llm, parameters, baseline |
| `impl.planner_llm.structured_output_contract` | 结构化输出契约 | Block | impl, planner_llm, structured_output, contract |
| `impl.planner_llm.config_contract` | Provider 配置契约 | Block | impl, planner_llm, config, provider |
| `impl.planner_llm.openai` | OpenAI GPT-5.4 接入 | Block | impl, planner_llm, openai, gpt_5_4 |
| `impl.planner_llm.anthropic` | Anthropic Claude 接入 | Block | impl, planner_llm, anthropic, claude |
| `impl.planner_llm.deepseek` | DeepSeek 接入 | Block | impl, planner_llm, deepseek |
| `impl.planner_llm.qwen` | Qwen / DashScope 接入 | Block | impl, planner_llm, qwen, dashscope |
| `impl.planner_llm.glm` | GLM / 智谱 接入 | Block | impl, planner_llm, glm, zhipu |
| `impl.planner_llm.nemotron` | NVIDIA NIM Nemotron 接入 | Block | impl, planner_llm, nvidia_nim, nemotron |
| `impl.planner_llm.validation_and_fallback` | 输出校验、重试与回退 | Block | impl, planner_llm, validation, fallback |
| `impl.snapshot_recovery.overview` | Snapshot Recovery for Remote Jobs | Section | impl, snapshot_recovery, overview |
| `impl.snapshot_recovery.snapshot_schema` | 快照结构 | Block | impl, snapshot_recovery, snapshot, schema |
| `impl.snapshot_recovery.recovery_flow` | 恢复流程 | Block | impl, snapshot_recovery, recovery, flow |
| `impl.remote_model_invocation.overview` | Remote Model Invocation Service | Section | impl, remote_model_invocation, overview |
| `impl.remote_model_invocation.components` | 核心组件 | Block | impl, remote_model_invocation, components |
| `impl.remote_model_invocation.rest_api` | REST API 规范 | Section | impl, remote_model_invocation, rest_api |
| `impl.remote_model_invocation.nim_failure_codes` | NVIDIA NIM 失败码定义 | Block | impl, remote_model_invocation, nvidia_nim, failure_codes |
| `impl.remote_model_invocation.nvidia_nim` | NVIDIA NIM 集成 | Section | impl, remote_model_invocation, nvidia_nim |
| `impl.remote_model_invocation.provider_config` | Provider 配置系统 | Block | impl, remote_model_invocation, provider_config, nvidia_nim |

---

### 14. `tools` Domain（工具集成）

**SSOT 文档**: tools-catalog.md / active-tool-metadata-profile.md

| SID | 标题 | 级别 | 标签 |
|-----|------|------|------|
| `tools.executor.overview` | Executor 可选择的工具 | Section | tools, executor |
| `tools.protgpt2.spec` | ProtGPT2 (PLM) 工具规约 | Block | tools, protgpt2, sequence_generation, plm |
| `tools.esmfold.spec` | ESMFold 工具规约 | Block | tools, esmfold, structure_prediction |
| `tools.nim_esmfold.spec` | NIM ESMFold 工具规约 | Block | tools, nim_esmfold, structure_prediction, nvidia_nim |
| `tools.alphafold.spec` | AlphaFold/OpenFold 工具规约 | Block | tools, alphafold, structure_prediction |
| `tools.integration.priority` | 工具集成优先级 | Block | tools, integration, priority |
| `tools.kg_extension.draft` | KG 扩展草案 | Block | tools, kg, extension, draft |
| `tools.adapter.constraints` | ToolAdapter 设计原则与约束 | Spec-Item | tools, adapter, constraints |
| `tools.metadata.active_profile` | 活跃工具元数据画像 | Section | tools, metadata, profile |
| `tools.metadata.scope` | 工具元数据范围与用途 | Section | tools, metadata, scope |
| `tools.metadata.schema` | 工具元数据字段规范 | Block | tools, metadata, schema |
| `tools.metadata.assignment_principles` | 元数据赋值原则 | Block | tools, metadata, assignment |
| `tools.metadata.active_table` | 活跃工具元数据表 | Block | tools, metadata, table, active_tools |
| `tools.metadata.derived_metrics` | 派生指标计算 | Block | tools, metadata, derived_metrics |
| `tools.metadata.usage_rules` | 工具元数据使用规则 | Block | tools, metadata, usage_rules |

---

### 15. `experiment` Domain（实验叙事映射）

**SSOT 文档**: algorithm-group-paper-mapping.md

| SID | 标题 | 级别 | 标签 |
|-----|------|------|------|
| `experiment.group_mapping.overview` | 实验分组映射总览 | Section | experiment, group_mapping, overview |
| `experiment.group_mapping.scope` | 实验命名统一范围 | Section | experiment, group_mapping, scope |
| `experiment.group_mapping.narrative_layers` | 三层实验叙事结构 | Block | experiment, group_mapping, narrative_layers |
| `experiment.group_mapping.a_to_paper` | 历史组到论文组映射 | Block | experiment, group_mapping, mapping |
| `experiment.group_mapping.paper_mainline` | 论文主线比较组 | Block | experiment, group_mapping, paper_mainline |
| `experiment.group_mapping.metric_responsibility` | 组别与指标责任矩阵 | Block | experiment, group_mapping, metrics |
| `experiment.group_mapping.table_layout` | 论文表格布局建议 | Block | experiment, group_mapping, table_layout |
| `experiment.group_mapping.naming` | 正文命名规范 | Block | experiment, group_mapping, naming |
| `experiment.group_mapping.claim_template` | 论文主命题模板 | Block | experiment, group_mapping, claim_template |

---

## 按文档分组的规范统计

| 文档 | Section | Block | Spec-Item | 总计 |
|------|---------|-------|-----------|------|
| architecture.md | 5 | 3 | 8 | 16 |
| agent-design.md | 8 | 9 | 9 | 26 |
| core-algorithm-spec.md | 3 | 9 | 4 | 16 |
| runtime-adaptation-formalization.md | 3 | 13 | 0 | 16 |
| de-novo-workflow.md | 7 | 7 | 0 | 14 |
| system-implementation-design.md | 2 | 7 | 5 | 14 |
| implementation_index.md | 1 | 0 | 0 | 1 |
| llm_provider_guide.md | 1 | 1 | 0 | 2 |
| planner_llm_api_integration.md | 1 | 11 | 0 | 12 |
| snapshot-recovery.md | 1 | 2 | 0 | 3 |
| remote_model_invocation.md | 3 | 3 | 0 | 6 |
| tools-catalog.md | 1 | 6 | 1 | 8 |
| active-tool-metadata-profile.md | 2 | 5 | 0 | 7 |
| hitl-extension.md | 0 | 0 | 0 | 0 |
| interaction-entry-surfaces.md | 9 | 12 | 0 | 21 |
| web-operator-workspace.md | 6 | 10 | 0 | 16 |
| cli-operator-workflow.md | 14 | 0 | 0 | 14 |
| core-algorithm-define.md | 1 | 0 | 0 | 1 |
| train-llm.md | 1 | 0 | 0 | 1 |
| algorithm-group-paper-mapping.md | 2 | 7 | 0 | 9 |
| **总计** | **71** | **105** | **27** | **203** |

**注**: `hitl-extension.md` 是差分索引文档，不包含独立定义的 SID，仅通过引用汇总其他文档的规范。

---

## 粒度分布

| 粒度 | 数量 | 占比 |
|------|------|------|
| Section | 71 | 35% |
| Block | 105 | 52% |
| Spec-Item | 27 | 13% |

---

## 按主题快速索引

详见 [topic_views.json](./topic_views.json) 获取以下主题的规范聚合：

- **hitl**: Human-in-the-Loop
- **fsm**: Finite State Machine
- **planning**: Task Planning
- **execution**: Task Execution
- **de_novo_workflow**: De Novo Workflow
- **observability**: Observability & Monitoring
- **llm_provider**: LLM Provider 集成
- **snapshot_recovery**: Snapshot 恢复
- **remote_model_invocation**: 远程模型调用
- **algorithm_llm**: Core Algorithm and LLM Training
- **experiment**: Experiment Narrative Mapping
- **interaction**: Web/CLI Interaction Surfaces
- **web_workspace**: Web Operator Workspace
- **cli_workflow**: CLI Workflow

---

## 使用说明

### 1. 查找特定规范

**通过 SID 查找**：
1. 在本文档中搜索 SID（如 `planner.algorithm.runtime_adjustment_formula`）
2. 查看对应的文档路径
3. 使用 `index.json` 中的 locator 信息精确定位

**通过主题查找**：
1. 确定你关心的主题（如 `planning`, `execution`, `observability`, `experiment`）
2. 查看 [topic_views.json](./topic_views.json) 获取聚合列表

### 2. 机器检索

**使用 index.json**：
```bash
# 查找特定 SID 的定位信息
jq ".specs[] | select(.sid == "planner.algorithm.runtime_adjustment_formula")" index.json

# 提取 experiment 相关规范
jq ".specs[] | select(.tags | contains(["experiment"]))" index.json
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
| 1.6 | 2026-04-27 | 明确 Web 可采用 FastAPI 托管的 React + TypeScript 静态前端；新增 React UI 组织约束 SID，并强调前端不得复制 FSM、合成 EventLog 或绕过 Decision API（总计 204） |
| 1.5 | 2026-04-05 | 新增 web-operator-workspace.md 与 cli-operator-workflow.md；细化 Web 主工作台、结构可视化、模型调用工作台与 CLI 无头工作流，并新增 web_workspace / cli_workflow topics（总计 203） |
| 1.4 | 2026-03-29 | 新增 interaction-entry-surfaces.md，纳入 interface 域与 interaction topic，并再生索引统计（总计 173） |
| 1.3 | 2026-03-29 | 纳入运行时形式化、活跃工具元数据和实验映射文档；再生全部 locator；扩展 planning/execution/observability 并新增 experiment topic（总计 152） |
| 1.2 | 2026-03-24 | 纳入自适应规划新 SID，修复 docslice locator 漂移，更新 planning/execution/observability 索引统计（总计 117） |
| 1.1 | 2026-02-01 | 新增 ProtGPT2 工具规约，更新 tools 索引与统计（总计 83） |
| 1.0 | 2026-01-11 | 索引 77 个规范，覆盖 10 个文档（新增 Remote Model Invocation 索引） |

---

**本文档由 `index.json` 再生，任何修改应同步更新 JSON 索引。**
