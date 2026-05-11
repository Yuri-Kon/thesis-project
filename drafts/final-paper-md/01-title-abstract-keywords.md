# 题目、摘要与关键词

## 论文题目

基于大模型驱动的agent协作新一代蛋白质设计系统开发

## 摘要

蛋白质计算设计通常需要将序列生成、结构预测、质量控制、目标评分和结果汇总等多个环节组合为连续工作流。现有蛋白质设计工具在单点能力上已有较好基础，但在实际任务中仍面临工具接口异构、输入输出约束复杂、高代价步骤不宜盲目调用、运行时失败需要恢复、关键决策需要人工审查等问题。针对这些问题，本文围绕“基于大模型驱动的agent协作新一代蛋白质设计系统开发”这一主题，设计并实现了一个面向蛋白质设计任务的大模型驱动多 Agent 协作与自适应工作流规划系统，目标是在已有工具和远程模型服务之上构建可规划、可执行、可恢复和可审计的工作流控制框架。

系统采用分层架构组织输入交互、智能规划、工作流执行、安全汇总和资源管理等模块。PlannerAgent 负责生成候选工具链和解释，ExecutorAgent 负责执行已确认的步骤，SafetyAgent 提供风险信号，SummarizerAgent 生成结果报告。系统通过 ProteinToolKG 描述工具能力、输入输出、成本和风险信息，通过有限状态机（Finite State Machine，FSM）约束任务生命周期，并通过人在环决策（Human-in-the-loop，HITL）机制处理高风险、高成本或不确定性较强的候选选择。为支持运行时恢复，本文进一步提出约束与证据感知、信念引导、恢复自适应工作流规划（Constraint- and Evidence-aware Belief-guided Recovery-adaptive Workflow Planning，CEBRA-WP）算法。该算法在工作流层综合任务约束、工具知识、执行历史、运行时观测和 Lite belief-state / 轻量信念状态，对候选工作流进行硬可行性过滤、静态评分、后验目标适配、运行时重排序和恢复动作选择。

在工程实现方面，系统后端基于 Python、FastAPI 和 Pydantic 构建，前端基于 React、TypeScript 和 Vite 实现轻量 Web 工作台，工具侧通过 ToolAdapter 封装结构预测、序列生成、质量控制和目标评分等能力。

本文的主要贡献在于：构建了一个面向蛋白质设计工作流的可恢复、可审计原型系统；提出并实现了 CEBRA-WP 工作流规划算法；建立了从系统验证到策略消融的证据链；并对高代价科研工作流中的运行时恢复、成本控制和审计解释进行了有边界的实验分析。

## 关键词

蛋白质设计；大模型驱动；多 Agent 协作；自适应工作流规划；CEBRA-WP；人在环决策

## English Title

Development of a Next-Generation Protein Design System Based on LLM-Driven Agent Collaboration

## Abstract

Computational protein design often requires a workflow that combines sequence generation, structure prediction, quality control, objective scoring, and result summarization. Although existing protein design tools provide useful single-step capabilities, practical design tasks still face heterogeneous tool interfaces, complex input-output constraints, costly computation steps, runtime failures, and the need for human review at uncertain or high-risk decision points. Under the topic of developing a next-generation protein design system based on LLM-driven agent collaboration, this thesis designs and implements an LLM-driven multi-agent collaborative and adaptive workflow planning system for protein design tasks. The system aims to organize existing tools and remote model services into a workflow control framework that is plannable, executable, recoverable, and auditable.

The system adopts a layered architecture covering input interaction, intelligent planning, workflow execution, safety and summarization, and resource management. PlannerAgent generates candidate toolchains and explanations; ExecutorAgent executes confirmed workflow steps; SafetyAgent provides risk signals; and SummarizerAgent produces final reports. ProteinToolKG is used to describe tool capabilities, input-output schemas, costs, and risks. A finite state machine (FSM) constrains the task lifecycle, while human-in-the-loop (HITL) decisions are used for high-cost, high-risk, or uncertain choices. To support runtime recovery, this thesis further proposes Constraint- and Evidence-aware Belief-guided Recovery-adaptive Workflow Planning (CEBRA-WP). At the workflow layer, CEBRA-WP combines task constraints, tool knowledge, execution history, runtime observations, and a lite belief-state to perform feasibility filtering, static scoring, posterior objective adaptation, runtime reranking, and recovery-aware action selection.

The backend is implemented with Python, FastAPI, and Pydantic, while the frontend is built with React, TypeScript, and Vite. External capabilities such as structure prediction, sequence generation, quality control, and objective scoring are wrapped through ToolAdapter interfaces. System validation covers API contracts, task intake, candidate generation, FSM transitions, HITL decisions, snapshot recovery, frontend and CLI entry points, failure recovery, safety boundaries, and end-to-end execution. Among 13 test cases, 12 pass and one CLI-related case partially passes. The experimental evaluation uses the `thesis-final-v1-001` 84-run internal ablation matrix to compare four strategies: `static_top1`, `fixed_threshold_gate`, `dynamic_no_belief_state`, and `lite_belief_state`. The results show that 81 out of 84 runs reach DONE and 3 reach FAILED. The `lite_belief_state` group produces valid RuntimeState records in 21/21 runs, with a runtime_state_observable_rate of 1.0000. The `fixed_threshold_gate` group triggers 6 real local patches and reaches a total of 28 high-cost calls, while both `dynamic_no_belief_state` and `lite_belief_state` have 20 high-cost calls. Within the scope of this thesis, the results indicate that the CEBRA-WP mechanism is implemented and observable, fixed-threshold recovery introduces additional execution cost, and lite belief-state provides traceable information for runtime recovery decisions.

The main contributions of this thesis are: a recoverable and auditable prototype system for protein design workflows; the design and implementation of the CEBRA-WP workflow planning algorithm; an evidence chain from system validation to strategy ablation; and a bounded experimental analysis of runtime recovery, cost control, and auditability in high-cost scientific workflows.

## Keywords

protein design; LLM-driven system; multi-agent collaboration; adaptive workflow planning; CEBRA-WP; human-in-the-loop
