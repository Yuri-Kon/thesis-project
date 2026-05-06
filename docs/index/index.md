# Specification Index（规范索引）

> 本文档是设计规范的人类可读索引，与 `index.json` 对应。
>
> **机器可读版本**: [index.json](./index.json)
> **主题视图**: [topic_views.json](./topic_views.json)

---

## 索引总览

**版本**: 1.8
**生成日期**: 2026-05-06
**总规范数**: 216
**文档数**: 22

---

## 文档列表

| doc_key | 标题 | 路径 | 状态 | 依赖 |
|---------|------|------|------|------|
| `arch` | 系统总体架构 | [docs/design/architecture.md](../design/architecture.md) | stable | - |
| `agent` | Agent设计文档 | [docs/design/agent-design.md](../design/agent-design.md) | stable | arch |
| `algo` | 核心算法规范 | [docs/design/core-algorithm-spec.md](../design/core-algorithm-spec.md) | stable | arch, agent, workflow, tools, impl |
| `algo_runtime` | 运行时自适应形式化 | [docs/design/runtime-adaptation-formalization.md](../design/runtime-adaptation-formalization.md) | stable | algo, workflow, tools, impl |
| `algo_theory_map` | CEBRA-WP 理论对象、文献与代码映射 | [docs/design/core-algorithm-theory-map.md](../design/core-algorithm-theory-map.md) | stable | algo, algo_runtime, tools_metadata, impl |
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
| `algocore` | 核心算法定义 | [docs/algorithm-and-llm/core-algorithm-define.md](../algorithm-and-llm/core-algorithm-define.md) | stable | algo, de_novo_workflow |
| `llmtrain` | Planner 大模型能力要求与专用训练方案 | [docs/algorithm-and-llm/train-llm.md](../algorithm-and-llm/train-llm.md) | stable | algo, impl_llm_provider |
| `experiment_mapping` | 实验分组与论文叙事映射 | [docs/experiment/algorithm-group-paper-mapping.md](../experiment/algorithm-group-paper-mapping.md) | stable | algo, de_novo_workflow |
| `interface_web_workspace` | Web 主工作台设计：全信息展示、结构可视化与交互确认 | [docs/design/web-operator-workspace.md](../design/web-operator-workspace.md) | stable | interface_surfaces, impl, hitl, tools |
| `interface_cli_workflow` | CLI 交互设计：无头环境闭环、批处理与 Web 协同 | [docs/design/cli-operator-workflow.md](../design/cli-operator-workflow.md) | stable | interface_surfaces, impl, hitl |
| `structured_task_intake` | 结构化任务输入与用户确认设计稿 | [docs/design/structured-task-intake-design.md](../design/structured-task-intake-design.md) | draft | arch, agent, impl, algo, interface_surfaces, interface_web_workspace |

---

## 按 Domain 分组的规范索引

### `agent` Domain

| SID | 标题 | 文档 | 级别 | 标签 |
|-----|------|------|------|------|
| `agent.overview.introduction` | Agent体系总览 | `agent` | Section | agent, overview |
| `agent.overview.roles` | Agent 角色列表 | `agent` | Block | agent, overview, roles |
| `agent.contracts.overview` | 核心数据结构契约总览 | `agent` | Section | agent, contracts, data_structures |
| `agent.contracts.protein_design_task` | ProteinDesignTask 数据结构 | `agent` | Block | agent, contracts, task |
| `agent.contracts.plan` | Plan 数据结构（Agent 层视角） | `agent` | Block | agent, contracts, planning |
| `agent.contracts.step_result` | StepResult 数据结构 | `agent` | Block | agent, contracts, execution, result |
| `agent.contracts.design_result` | DesignResult 数据结构 | `agent` | Block | agent, contracts, result |
| `agent.contracts.safety_result` | SafetyResult 数据结构 | `agent` | Block | agent, contracts, safety, result |
| `agent.hitl.overview` | HITL 机制在 Agent 层的概述 | `agent` | Section | agent, hitl, overview |
| `agent.hitl.universal_constraints` | Agent 层 HITL 统一约束 | `agent` | Spec-Item | agent, hitl, constraints |

### `algo` Domain

| SID | 标题 | 文档 | 级别 | 标签 |
|-----|------|------|------|------|
| `algo.version.registry` | 算法版本体系 | `algo` | Section | algo, version, registry |
| `algo.scope.overview` | 算法规范范围说明 | `algo` | Section | algo, scope |
| `algo.definitions.overview` | 算法定义总览 | `algo` | Section | algo, definitions |
| `algo.adaptive.feasibility_filter` | 硬可行性与 degraded feasible | `algo` | Block | algo, adaptive, feasibility, constraints |
| `algo.adaptive.problem_formulation` | 高代价工作流中的自适应规划问题 | `algo` | Section | algo, adaptive, problem_formulation |
| `algo.adaptive.optimization_objective` | 优化目标与效用分解 | `algo` | Block | algo, adaptive, optimization_objective |
| `algo.posterior.objective_scoring` | 证据感知后验目标评分 | `algo` | Block | algo, posterior_objective, evidence, scoring |
| `algo.theory_map.overview` | CEBRA-WP 理论对象、文献与代码映射 | `algo_theory_map` | Section | algo, theory_map, traceability |
| `algo.theory_map.formula_matrix` | 核心公式覆盖矩阵 | `algo_theory_map` | Block | algo, theory_map, formula, traceability |
| `algo.theory_map.literature_buckets` | 分桶映射 | `algo_theory_map` | Block | algo, theory_map, literature |
| `algo.theory_map.code_reverse_index` | 代码字段反查索引 | `algo_theory_map` | Block | algo, theory_map, code, traceability |
| `algo.runtime.formalization` | 运行时自适应形式化 | `algo_runtime` | Section | algo, runtime, formalization |
| `algo.runtime.scope` | 文档目的与适用范围 | `algo_runtime` | Section | algo, runtime, scope |
| `algo.runtime.design_basis` | 建模立场与设计依据 | `algo_runtime` | Block | algo, runtime, design_basis |
| `algo.schemas.overview` | 六类 Schema 总览 | `algo_runtime` | Section | algo, runtime, schemas |
| `algo.schema.cost` | Cost Schema | `algo_runtime` | Block | algo, schema, cost |
| `algo.schema.risk` | Risk Schema | `algo_runtime` | Block | algo, schema, risk |
| `algo.schema.recovery` | Recovery Schema | `algo_runtime` | Block | algo, schema, recovery |
| `algo.schema.state` | State Schema | `algo_runtime` | Block | algo, schema, state, belief_state |
| `algo.schema.observation` | Observation Schema | `algo_runtime` | Block | algo, schema, observation |
| `algo.schema.action_utility` | Action-Utility Schema | `algo_runtime` | Block | algo, schema, action_utility |

### `algollm` Domain

| SID | 标题 | 文档 | 级别 | 标签 |
|-----|------|------|------|------|
| `algollm.core.algorithm_define` | 核心算法定义 | `algocore` | Section | algo, algorithm_llm, core, planning |
| `algollm.llm.training_plan` | Planner 大模型能力要求与专用训练方案 | `llmtrain` | Section | algo, algorithm_llm, llm, training, planner |

### `api` Domain

| SID | 标题 | 文档 | 级别 | 标签 |
|-----|------|------|------|------|
| `api.rest.overview` | REST API 总览 | `impl` | Section | api, rest |
| `api.rest.create_task` | POST /tasks 端点 | `impl` | Spec-Item | api, rest, task |
| `api.rest.get_pending_actions` | GET /pending-actions 端点 | `impl` | Spec-Item | api, rest, hitl, pending_actions |
| `api.rest.submit_decision` | POST /pending-actions/{id}/decision 端点 | `impl` | Spec-Item | api, rest, hitl, decision |
| `api.rest.get_report` | GET /tasks/{task_id}/report 端点 | `impl` | Spec-Item | api, rest, report |

### `arch` Domain

| SID | 标题 | 文档 | 级别 | 标签 |
|-----|------|------|------|------|
| `arch.overview.layers` | 分层架构 | `arch` | Section | arch, overview, layers |
| `arch.components.overview` | 组件视图 | `arch` | Section | arch, components |
| `arch.execution.nextflow_boundary` | 执行后端边界(Nextflow) | `arch` | Block | arch, execution, nextflow, boundary |
| `arch.flow.end_to_end` | 运行视图与时序图 | `arch` | Section | arch, flow, runtime |
| `arch.contracts.pending_action` | PendingAction 契约定义 | `arch` | Spec-Item | arch, contracts, hitl, pending_action |
| `arch.contracts.decision` | Decision 契约定义 | `arch` | Spec-Item | arch, contracts, hitl, decision |
| `arch.contracts.task_snapshot` | TaskSnapshot 契约定义 | `arch` | Spec-Item | arch, contracts, hitl, snapshot |
| `arch.dataflow.overview` | 数据流概览 | `arch` | Section | arch, dataflow |
| `arch.contracts.plan` | Plan 契约定义（架构层视角） | `arch` | Spec-Item | arch, contracts, planning |
| `arch.kg.overview` | ProteinToolKG 在架构中的位置 | `arch` | Block | arch, kg, knowledge_graph |

### `executor` Domain

| SID | 标题 | 文档 | 级别 | 标签 |
|-----|------|------|------|------|
| `executor.hitl.responsibilities` | ExecutorAgent HITL 职责 | `agent` | Section | executor, hitl, responsibilities |
| `executor.hitl.patch_confirm` | Patch 触发与确认 | `agent` | Block | executor, hitl, execution, patch |
| `executor.responsibilities.must` | ExecutorAgent 必须做的事 | `agent` | Spec-Item | executor, responsibilities, must |
| `executor.responsibilities.must_not` | ExecutorAgent 不得做的事 | `agent` | Spec-Item | executor, responsibilities, must_not |

### `experiment` Domain

| SID | 标题 | 文档 | 级别 | 标签 |
|-----|------|------|------|------|
| `experiment.group_mapping.overview` | 实验分组映射总览 | `experiment_mapping` | Section | experiment, group_mapping, overview |
| `experiment.group_mapping.scope` | 实验命名统一范围 | `experiment_mapping` | Section | experiment, group_mapping, scope |
| `experiment.group_mapping.narrative_layers` | 三层实验叙事结构 | `experiment_mapping` | Block | experiment, group_mapping, narrative_layers |
| `experiment.group_mapping.a_to_paper` | 历史组到论文组映射 | `experiment_mapping` | Block | experiment, group_mapping, mapping |
| `experiment.group_mapping.paper_mainline` | 论文主线比较组 | `experiment_mapping` | Block | experiment, group_mapping, paper_mainline |
| `experiment.group_mapping.metric_responsibility` | 组别与指标责任矩阵 | `experiment_mapping` | Block | experiment, group_mapping, metrics |
| `experiment.group_mapping.table_layout` | 论文表格布局建议 | `experiment_mapping` | Block | experiment, group_mapping, table_layout |
| `experiment.group_mapping.naming` | 正文命名规范 | `experiment_mapping` | Block | experiment, group_mapping, naming |
| `experiment.group_mapping.claim_template` | 论文主命题模板 | `experiment_mapping` | Block | experiment, group_mapping, claim_template |

### `fsm` Domain

| SID | 标题 | 文档 | 级别 | 标签 |
|-----|------|------|------|------|
| `fsm.lifecycle.overview` | 任务生命周期与状态机 | `arch` | Section | fsm, lifecycle, state_machine |
| `fsm.states.definitions` | FSM 状态完整定义表 | `arch` | Block | fsm, states, definitions |
| `fsm.states.waiting_plan_confirm` | WAITING_PLAN_CONFIRM 状态定义 | `arch` | Spec-Item | fsm, states, hitl, planning |
| `fsm.states.waiting_patch_confirm` | WAITING_PATCH_CONFIRM 状态定义 | `arch` | Spec-Item | fsm, states, hitl, execution |
| `fsm.states.waiting_replan_confirm` | WAITING_REPLAN_CONFIRM 状态定义 | `arch` | Spec-Item | fsm, states, hitl, planning |
| `fsm.transitions.overview` | 状态转换规则总览 | `arch` | Spec-Item | fsm, transitions, state_machine |

### `impl` Domain

| SID | 标题 | 文档 | 级别 | 标签 |
|-----|------|------|------|------|
| `impl.runtime.integration_guidelines` | 运行时集成与持久化指南 | `algo_runtime` | Block | impl, runtime, integration, persistence |
| `impl.overview.introduction` | 实现层总览 | `impl` | Section | impl, overview |
| `impl.techstack.overview` | 技术栈选型 | `impl` | Block | impl, techstack |
| `impl.runtime_state.persistence` | RuntimeState / BeliefState 与持久化边界 | `impl` | Block | impl, runtime_state, persistence |
| `impl.nextflow.control_flow_constraints` | Nextflow 接入边界与控制流约束 | `impl` | Block | impl, nextflow, control_flow, constraints |
| `impl.planner.tool_resolution` | Planner 工具解析与 KG-only 约束 | `impl` | Block | impl, planner, tool_resolution, kg |
| `impl.planner.training_and_serving` | Planner 训练与服务化落点 | `impl` | Block | impl, planner, training, serving |
| `impl.index.codebase_overview` | 实现代码索引与结构化总览 | `impl_index` | Section | impl, index, codebase, overview |
| `impl.llm_provider.guide` | LLM Provider 集成指南 | `impl_llm_provider` | Section | impl, llm_provider, guide, overview |
| `impl.llm_provider.external_providers` | OpenAICompatibleProvider | `impl_llm_provider` | Block | impl, llm_provider, external, openai_compatible |
| `impl.planner_llm.overview` | Planner 外部 LLM 接入规范 | `impl_planner_llm` | Section | impl, planner_llm, overview, integration |
| `impl.planner_llm.provider_selection` | Provider 选型与适配层建议 | `impl_planner_llm` | Block | impl, planner_llm, provider_selection |
| `impl.planner_llm.parameter_baseline` | Planner 参数基线 | `impl_planner_llm` | Block | impl, planner_llm, parameters, baseline |
| `impl.planner_llm.structured_output_contract` | 结构化输出契约 | `impl_planner_llm` | Block | impl, planner_llm, structured_output, contract |
| `impl.planner_llm.config_contract` | Provider 配置契约 | `impl_planner_llm` | Block | impl, planner_llm, config, provider |
| `impl.planner_llm.openai` | OpenAI GPT-5.4 接入 | `impl_planner_llm` | Block | impl, planner_llm, openai, gpt_5_4 |
| `impl.planner_llm.anthropic` | Anthropic Claude 接入 | `impl_planner_llm` | Block | impl, planner_llm, anthropic, claude |
| `impl.planner_llm.deepseek` | DeepSeek 接入 | `impl_planner_llm` | Block | impl, planner_llm, deepseek |
| `impl.planner_llm.qwen` | Qwen / DashScope 接入 | `impl_planner_llm` | Block | impl, planner_llm, qwen, dashscope |
| `impl.planner_llm.glm` | GLM / 智谱 接入 | `impl_planner_llm` | Block | impl, planner_llm, glm, zhipu |
| `impl.planner_llm.nemotron` | NVIDIA NIM Nemotron 接入 | `impl_planner_llm` | Block | impl, planner_llm, nvidia_nim, nemotron |
| `impl.planner_llm.validation_and_fallback` | 输出校验、重试与回退 | `impl_planner_llm` | Block | impl, planner_llm, validation, fallback |
| `impl.remote_model_invocation.overview` | Remote Model Invocation Service | `impl_remote_model_invocation` | Section | impl, remote_model_invocation, overview |
| `impl.remote_model_invocation.components` | 核心组件 | `impl_remote_model_invocation` | Block | impl, remote_model_invocation, components |
| `impl.remote_model_invocation.rest_api` | REST API 规范 | `impl_remote_model_invocation` | Section | impl, remote_model_invocation, rest_api |
| `impl.remote_model_invocation.nim_failure_codes` | NVIDIA NIM 失败码定义 | `impl_remote_model_invocation` | Block | impl, remote_model_invocation, nvidia_nim, failure_codes |
| `impl.remote_model_invocation.nvidia_nim` | NVIDIA NIM 集成 | `impl_remote_model_invocation` | Section | impl, remote_model_invocation, nvidia_nim |
| `impl.remote_model_invocation.provider_config` | Provider 配置系统 | `impl_remote_model_invocation` | Block | impl, remote_model_invocation, provider_config, nvidia_nim |
| `impl.snapshot_recovery.overview` | Snapshot Recovery for Remote Jobs | `impl_snapshot_recovery` | Section | impl, snapshot_recovery, overview |
| `impl.snapshot_recovery.snapshot_schema` | 快照结构 | `impl_snapshot_recovery` | Block | impl, snapshot_recovery, snapshot, schema |
| `impl.snapshot_recovery.recovery_flow` | 恢复流程 | `impl_snapshot_recovery` | Block | impl, snapshot_recovery, recovery, flow |

### `interface` Domain

| SID | 标题 | 文档 | 级别 | 标签 |
|-----|------|------|------|------|
| `interface.cli_workflow.overview` | CLI 工作流总览 | `interface_cli_workflow` | Section | interface, cli, workflow, overview |
| `interface.cli_workflow.role_boundary` | CLI 定位与职责边界 | `interface_cli_workflow` | Section | interface, cli, role_boundary |
| `interface.cli_workflow.experience_modes` | CLI 体验模式 | `interface_cli_workflow` | Section | interface, cli, experience_modes |
| `interface.cli_workflow.command_groups` | CLI 命令分组 | `interface_cli_workflow` | Section | interface, cli, commands |
| `interface.cli_workflow.submit_flow` | CLI 提交流程 | `interface_cli_workflow` | Section | interface, cli, submit, workflow |
| `interface.cli_workflow.watch_flow` | CLI 轮询与值守流程 | `interface_cli_workflow` | Section | interface, cli, watch, polling |
| `interface.cli_workflow.pending_review` | CLI 待确认审查流程 | `interface_cli_workflow` | Section | interface, cli, pending_review, hitl |
| `interface.cli_workflow.noninteractive_mode` | CLI 非交互模式 | `interface_cli_workflow` | Section | interface, cli, automation, noninteractive |
| `interface.cli_workflow.output_profiles` | CLI 输出契约 | `interface_cli_workflow` | Section | interface, cli, output, json |
| `interface.cli_workflow.web_handoff` | CLI 与 Web 的协同跳转 | `interface_cli_workflow` | Section | interface, cli, web, handoff |
| `interface.cli_workflow.error_mapping` | CLI 错误呈现与恢复提示 | `interface_cli_workflow` | Section | interface, cli, errors, recovery |
| `interface.cli_workflow.headless_recovery` | CLI 无头恢复与审计 | `interface_cli_workflow` | Section | interface, cli, recovery, audit |
| `interface.cli_workflow.progressive_enhancement` | CLI 渐进增强边界 | `interface_cli_workflow` | Section | interface, cli, enhancement |
| `interface.cli_workflow.milestones` | CLI 演进顺序 | `interface_cli_workflow` | Section | interface, cli, rollout, milestones |
| `interface.overview.entry_surfaces` | 交互入口总览 | `interface_surfaces` | Section | interface, overview, entry_surfaces |
| `interface.scope.positioning` | 范围与定位 | `interface_surfaces` | Section | interface, scope, positioning |
| `interface.goals.design_targets` | 设计目标与非目标 | `interface_surfaces` | Section | interface, goals, design |
| `interface.architecture.dual_surface` | 双入口架构 | `interface_surfaces` | Section | interface, architecture, dual_surface |
| `interface.web.primary_workspace` | Web 端：主操纵空间 | `interface_surfaces` | Block | interface, web, primary_workspace |
| `interface.cli.headless_entry` | CLI：控制台与无头环境入口 | `interface_surfaces` | Block | interface, cli, headless |
| `interface.cross_surface.relationship` | Web 与 CLI 的协同关系 | `interface_surfaces` | Block | interface, web, cli, collaboration |
| `interface.scenarios.applicability` | 适用场景 | `interface_surfaces` | Section | interface, scenarios, applicability |
| `interface.scenarios.web_first` | Web 优先场景 | `interface_surfaces` | Block | interface, scenarios, web |
| `interface.scenarios.cli_first` | CLI 优先场景 | `interface_surfaces` | Block | interface, scenarios, cli |
| `interface.scenarios.hybrid` | 协同切换场景 | `interface_surfaces` | Block | interface, scenarios, hybrid |
| `interface.cli.capability_scope` | CLI 功能边界与命令面 | `interface_surfaces` | Section | interface, cli, capabilities |
| `interface.cli.headless_guarantee` | CLI 无头环境最小闭环保证 | `interface_surfaces` | Block | interface, cli, requirements, headless |
| `interface.cli.web_handoff` | CLI 向 Web 的显式跳转约束 | `interface_surfaces` | Block | interface, cli, web, handoff |
| `interface.cli.command_tree` | CLI 建议命令树 | `interface_surfaces` | Block | interface, cli, commands |
| `interface.web.capability_scope` | Web 功能边界 | `interface_surfaces` | Section | interface, web, capabilities, react, ui_boundary |
| `interface.web.information_architecture` | Web 页面信息架构 | `interface_surfaces` | Block | interface, web, information_architecture |
| `interface.constraints.contract_alignment` | 与现有系统契约的对齐要求 | `interface_surfaces` | Section | interface, constraints, contract_alignment, react, eventlog |
| `interface.cli.backend_compatibility` | CLI 后端形态兼容性 | `interface_surfaces` | Block | interface, cli, requirements, compatibility |
| `interface.integration.api_boundary` | API 集成边界 | `interface_surfaces` | Block | interface, api, integration |
| `interface.rollout.milestones` | 演进路线 | `interface_surfaces` | Section | interface, rollout, milestones |
| `interface.task_intake.draft_recovery` | 草稿恢复与导航保护 | `structured_task_intake` | Section | interface, intake, draft, recovery, navigation-guard |
| `interface.web_workspace.overview` | Web 主工作台总览 | `interface_web_workspace` | Section | interface, web, workspace, overview |
| `interface.web_workspace.framework_choice` | Web 框架选择与边界 | `interface_web_workspace` | Section | interface, web, framework, fastapi, react, typescript |
| `interface.web_workspace.react_ui_boundary` | React UI 组织与实现参考 | `interface_web_workspace` | Block | interface, web, react, typescript, ui_boundary |
| `interface.web_workspace.design_principles` | Web 设计原则 | `interface_web_workspace` | Section | interface, web, design, principles |
| `interface.web_workspace.primary_layout` | Web 顶层布局 | `interface_web_workspace` | Section | interface, web, layout, workspace |
| `interface.web_workspace.page_topology` | Web 页面拓扑 | `interface_web_workspace` | Block | interface, web, pages, topology |
| `interface.web_workspace.dashboard` | Dashboard 要求 | `interface_web_workspace` | Block | interface, web, dashboard |
| `interface.web_workspace.task_detail` | Task Detail 要求 | `interface_web_workspace` | Block | interface, web, task_detail |
| `interface.web_workspace.pending_review` | Pending Review 工作区 | `interface_web_workspace` | Block | interface, web, pending_review, hitl |
| `interface.web_workspace.model_invocation_panel` | 模型调用工作台 | `interface_web_workspace` | Block | interface, web, model_invocation, nvidia_nim |
| `interface.web_workspace.structure_visualization` | 结构可视化工作区 | `interface_web_workspace` | Block | interface, web, structure_visualization, ngl |
| `interface.web_workspace.structure_metric_linking` | 结构与指标联动 | `interface_web_workspace` | Block | interface, web, structure, metrics, linking |
| `interface.web_workspace.report_explorer` | 报告与产物浏览 | `interface_web_workspace` | Block | interface, web, report, artifacts |
| `interface.web_workspace.interaction_patterns` | Web 交互模式 | `interface_web_workspace` | Section | interface, web, interaction, patterns |
| `interface.web_workspace.state_sync` | Web 状态同步约束 | `interface_web_workspace` | Block | interface, web, state_sync, contracts |
| `interface.web_workspace.visualization_fallback` | 可视化降级与网络约束 | `interface_web_workspace` | Block | interface, web, visualization, fallback |
| `interface.web_workspace.milestones` | Web MVP 与演进 | `interface_web_workspace` | Section | interface, web, rollout, milestones |
| `interface.web_workspace.inspector_reorder` | Inspector 卡片拖拽重排 | `interface_web_workspace` | Section | interface, web, inspector, drag-and-drop, ux |
| `interface.web_workspace.card_density` | 卡片空间密度与视口填充 | `interface_web_workspace` | Section | interface, web, layout, scrolling, responsive |
| `interface.web_workspace.draft_protection` | Task Builder 草稿保护与恢复 | `interface_web_workspace` | Section | interface, web, task-builder, draft, ux |

### `obs` Domain

| SID | 标题 | 文档 | 级别 | 标签 |
|-----|------|------|------|------|
| `obs.observability.overview` | 日志与可观测设计 | `impl` | Block | obs, observability, overview |
| `obs.eventlog.schema` | EventLog 单条日志记录结构 | `impl` | Block | obs, eventlog, observability |
| `obs.eventlog.mandatory_events` | 事件日志写入约束（必须遵守） | `impl` | Spec-Item | obs, eventlog, observability, hitl |

### `planner` Domain

| SID | 标题 | 文档 | 级别 | 标签 |
|-----|------|------|------|------|
| `planner.interface.overview` | PlannerAgent 接口总览 | `agent` | Section | planner, interface, agent |
| `planner.hitl.responsibilities` | PlannerAgent HITL 职责 | `agent` | Section | planner, hitl, responsibilities |
| `planner.hitl.plan_confirm` | 初始 Plan 确认阶段 | `agent` | Block | planner, hitl, planning |
| `planner.responsibilities.must` | PlannerAgent 必须做的事 | `agent` | Spec-Item | planner, responsibilities, must |
| `planner.responsibilities.must_not` | PlannerAgent 不得做的事 | `agent` | Spec-Item | planner, responsibilities, must_not |
| `planner.contracts.candidate_schema` | Candidate 对象模式总览 | `algo` | Spec-Item | planner, contracts, candidate |
| `planner.contracts.plan_candidate` | PlanCandidate 模式定义 | `algo` | Spec-Item | planner, contracts, candidate, planning |
| `planner.contracts.patch_candidate` | PatchCandidate 模式定义 | `algo` | Spec-Item | planner, contracts, candidate, execution |
| `planner.contracts.replan_candidate` | ReplanCandidate 模式定义 | `algo` | Spec-Item | planner, contracts, candidate, planning |
| `planner.contracts.io_overview` | Planner 输入输出契约 | `algo` | Block | planner, contracts, io |
| `planner.algorithm.tool_retrieval` | 工具检索算法 | `algo` | Block | planner, algorithm, tool_retrieval |
| `planner.algorithm.candidate_scoring` | 候选方案评分规则 | `algo` | Block | planner, algorithm, scoring |
| `planner.algorithm.topk_diversity` | Top-K diversity | `algo` | Block | planner, algorithm, topk, diversity |
| `planner.algorithm.runtime_state_estimation` | 运行时状态估计（Lite belief-state） | `algo` | Block | planner, algorithm, runtime_state_estimation |
| `planner.algorithm.runtime_reranking` | 运行时重排序与预算感知裁剪 | `algo` | Block | planner, algorithm, runtime_reranking |
| `planner.algorithm.runtime_action_selection` | 动作选择与恢复感知控制 | `algo` | Block | planner, algorithm, runtime_action_selection |
| `planner.algorithm.hitl_gate` | HITL 门控决策规则 | `algo` | Block | planner, algorithm, hitl |
| `planner.algorithm.decision_application` | Decision 应用逻辑 | `algo` | Block | planner, algorithm, hitl, decision |
| `planner.runtime.belief_state_schema` | Lite belief-state 模式 | `algo_runtime` | Block | planner, runtime, belief_state, schema |
| `planner.algorithm.runtime_update_rules` | 运行时状态更新规则 | `algo_runtime` | Block | planner, algorithm, runtime, update_rules |
| `planner.algorithm.runtime_adjustment_formula` | runtime_adjustment 公式 | `algo_runtime` | Block | planner, algorithm, runtime_adjustment, scoring |
| `planner.algorithm.action_priority_resolution` | 动作优先级与冲突消解 | `algo_runtime` | Block | planner, algorithm, priority, action_selection |
| `planner.algorithm.stop_semantics` | stop 语义与终止条件 | `algo_runtime` | Block | planner, algorithm, stop, hitl |

### `safety` Domain

| SID | 标题 | 文档 | 级别 | 标签 |
|-----|------|------|------|------|
| `safety.hitl.responsibilities` | SafetyAgent HITL 职责 | `agent` | Section | safety, hitl, responsibilities |
| `safety.hitl.replan_trigger` | 触发 WAITING_REPLAN_CONFIRM 的条件 | `agent` | Block | safety, hitl, planning |
| `safety.responsibilities.must` | SafetyAgent 必须做的事 | `agent` | Spec-Item | safety, responsibilities, must |
| `safety.responsibilities.must_not` | SafetyAgent 不得做的事 | `agent` | Spec-Item | safety, responsibilities, must_not |

### `summarizer` Domain

| SID | 标题 | 文档 | 级别 | 标签 |
|-----|------|------|------|------|
| `summarizer.hitl.responsibilities` | SummarizerAgent HITL 职责 | `agent` | Section | summarizer, hitl, responsibilities |
| `summarizer.responsibilities.must` | SummarizerAgent 必须做的事 | `agent` | Spec-Item | summarizer, responsibilities, must |
| `summarizer.responsibilities.must_not` | SummarizerAgent 不得做的事 | `agent` | Spec-Item | summarizer, responsibilities, must_not |

### `tools` Domain

| SID | 标题 | 文档 | 级别 | 标签 |
|-----|------|------|------|------|
| `tools.metadata.active_profile` | 活跃工具元数据画像 | `tools_metadata` | Section | tools, metadata, profile |
| `tools.metadata.scope` | 工具元数据范围与用途 | `tools_metadata` | Section | tools, metadata, scope |
| `tools.metadata.schema` | 工具元数据字段规范 | `tools_metadata` | Block | tools, metadata, schema |
| `tools.metadata.assignment_principles` | 元数据赋值原则 | `tools_metadata` | Block | tools, metadata, assignment |
| `tools.metadata.active_table` | 活跃工具元数据表 | `tools_metadata` | Block | tools, metadata, table, active_tools |
| `tools.metadata.derived_metrics` | 派生指标计算 | `tools_metadata` | Block | tools, metadata, derived_metrics |
| `tools.metadata.usage_rules` | 工具元数据使用规则 | `tools_metadata` | Block | tools, metadata, usage_rules |
| `tools.executor.overview` | Executor 可选择的工具 | `tools` | Section | tools, executor |
| `tools.protgpt2.spec` | ProtGPT2 (PLM) 工具规约 | `tools` | Block | tools, protgpt2, sequence_generation, plm |
| `tools.esmfold.spec` | ESMFold 工具规约 | `tools` | Block | tools, esmfold, structure_prediction |
| `tools.nim_esmfold.spec` | NIM ESMFold 工具规约 | `tools` | Block | tools, nim_esmfold, structure_prediction, nvidia_nim |
| `tools.alphafold.spec` | AlphaFold/OpenFold 工具规约 | `tools` | Block | tools, alphafold, structure_prediction |
| `tools.integration.priority` | 工具集成优先级 | `tools` | Block | tools, integration, priority |
| `tools.kg_extension.draft` | KG 扩展草案 | `tools` | Block | tools, kg, extension, draft |
| `tools.adapter.constraints` | ToolAdapter 设计原则与约束 | `tools` | Spec-Item | tools, adapter, constraints |

### `workflow` Domain

| SID | 标题 | 文档 | 级别 | 标签 |
|-----|------|------|------|------|
| `workflow.overview.scope` | 范围与定位 | `de_novo_workflow` | Section | workflow, overview, scope |
| `workflow.design.goals` | 设计目标与约束 | `de_novo_workflow` | Section | workflow, design, goals |
| `workflow.layers.six_stage` | 六阶段分层 | `de_novo_workflow` | Section | workflow, layers, six_stage |
| `workflow.stage.sequence_exploration` | 序列探索（Sequence Exploration） | `de_novo_workflow` | Block | workflow, stage, sequence_exploration |
| `workflow.stage.structure_projection` | 结构映射（Structure Projection） | `de_novo_workflow` | Block | workflow, stage, structure_projection |
| `workflow.stage.quality_gate` | 结构与序列质量门禁（Quality Gate） | `de_novo_workflow` | Block | workflow, stage, quality_gate |
| `workflow.stage.structure_refinement` | 结构条件下的序列精修（Structure-conditioned Refinement） | `de_novo_workflow` | Block | workflow, stage, structure_refinement |
| `workflow.stage.objective_scoring` | 目标/功能/物性评估（Objective Scoring） | `de_novo_workflow` | Block | workflow, stage, objective_scoring |
| `workflow.stage.patch_replan_control` | Patch/Replan 控制层（Control Layer） | `de_novo_workflow` | Block | workflow, stage, patch_replan_control |
| `workflow.stage.high_cost_control` | 高代价步骤与运行时恢复感知控制 | `de_novo_workflow` | Block | workflow, stage, high_cost_control |
| `workflow.modules.interface` | 模块化接口与可替换原则 | `de_novo_workflow` | Section | workflow, modules, interface |
| `workflow.loops.and_crosscut` | 可循环步骤与贯穿步骤 | `de_novo_workflow` | Section | workflow, loops, crosscut |
| `workflow.integration.responsibilities` | 分工映射（Planner/Executor/Safety） | `de_novo_workflow` | Section | workflow, integration, responsibilities |
| `workflow.examples.template` | 示例流程模板（非线性） | `de_novo_workflow` | Section | workflow, examples, template |

---

## 文档统计

| 文档 | Section | Block | Spec-Item | 总计 |
|------|---------|-------|-----------|------|
| architecture.md | 5 | 3 | 8 | 16 |
| agent-design.md | 8 | 9 | 9 | 26 |
| core-algorithm-spec.md | 4 | 12 | 4 | 20 |
| runtime-adaptation-formalization.md | 3 | 13 | 0 | 16 |
| core-algorithm-theory-map.md | 1 | 3 | 0 | 4 |
| de-novo-workflow.md | 7 | 7 | 0 | 14 |
| system-implementation-design.md | 2 | 7 | 5 | 14 |
| implementation_index.md | 1 | 0 | 0 | 1 |
| llm_provider_guide.md | 1 | 1 | 0 | 2 |
| planner_llm_api_integration.md | 1 | 11 | 0 | 12 |
| snapshot-recovery.md | 1 | 2 | 0 | 3 |
| remote_model_invocation.md | 3 | 3 | 0 | 6 |
| tools-catalog.md | 1 | 6 | 1 | 8 |
| active-tool-metadata-profile.md | 2 | 5 | 0 | 7 |
| interaction-entry-surfaces.md | 9 | 12 | 0 | 21 |
| core-algorithm-define.md | 1 | 0 | 0 | 1 |
| train-llm.md | 1 | 0 | 0 | 1 |
| algorithm-group-paper-mapping.md | 2 | 7 | 0 | 9 |
| web-operator-workspace.md | 9 | 11 | 0 | 20 |
| cli-operator-workflow.md | 14 | 0 | 0 | 14 |
| structured-task-intake-design.md | 1 | 0 | 0 | 1 |

---

## 使用方式

```bash
.agents/skills/doc-slicer/scripts/docslice --sid planner.algorithm.runtime_adjustment_formula
.agents/skills/doc-slicer/scripts/docslice --topic planning --max-lines 300
.agents/skills/doc-slicer/scripts/docslice --lint
```
