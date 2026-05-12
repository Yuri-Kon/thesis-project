# 题目、摘要与关键词

## 论文题目

基于大模型驱动的agent协作新一代蛋白质设计系统开发

## 摘要

蛋白质计算设计通常需要将序列生成、结构预测、质量控制、目标评分和结果汇总等多个环节组合为连续工作流。现有蛋白质设计工具在单点能力上已有较好基础，但是在实际任务中仍面临着接口异构、输入输出约束复杂、高代价步骤不宜盲目调用、运行时失败需要恢复、关键决策需要人工审阅等问题。针对这些问题，本文围绕“基于大模型驱动的agent协作新一代蛋白质设计系统开发”这一主题，设计并实现了一个面向蛋白质设计任务的大模型驱动多Agent协作与自适应工作流规划系统，目标是在已有工具和远程模型服务之上构建可规划、可执行、可恢复和可审计的工作流控制框架。

系统以分层架构组织输入交互、智能规划、工作流执行、安全汇总和资源管理等模块。PlannerAgent 生成候选工具链和解释，ExecutorAgent 执行已经确认的步骤，SafetyAgent 提供风险信号，SummarizerAgent 生成结果报告。系统用 ProteinToolKG 描述工具能力、输入输出、成本和风险信息，用有限状态机（Finite State Machine，FSM）约束任务生命周期，并通过人在环决策（Human-in-the-loop，HITL）处理高风险、高成本或不确定性较强的候选选择。为了支持运行时恢复，本文进一步给出约束与证据感知、信念引导、恢复自适应工作流规划（Constraint-and-Evidence-aware Belief-guided Recovery-adaptive Workflow Planning，CEBRA-WP）算法。该算法在工作流层综合任务约束、工具知识、执行历史、运行时观测和 Lite belief-state / 轻量信念状态，对候选工作流进行硬性可行性过滤、静态评分、后验目标适配、运行时重排序和恢复动作选择。

工程实现上，后端采用 Python、FastAPI 和 Pydantic，前端采用 React、TypeScript 和 Vite 构建轻量 Web 工作台；工具侧则通过 ToolAdapter 封装结构预测、序列生成、质量控制和目标评分等能力。

本文的主要贡献在于：构建了一个面向蛋白质设计工作流的可恢复、可审计原型系统；提出并实现了CEBRA-WP工作流规划算法；建立了从系统验证到策略消融的证据链；并对高代价科研工作流中的运行时恢复、成本控制和审计解释进行了有边界的实验分析。

## 关键词

蛋白质设计；大模型驱动；多Agent协作；自适应工作流规划；人在环决策

## English Title

Development of a Next-Generation Protein Design System Based on Large-Scale Model-Driven Agent Collaboration

## Abstract

Computational protein design usually requires a continuous workflow that integrates sequence generation, structure prediction, quality control, objective scoring, and result summarization. Existing protein design tools have established useful capabilities for individual steps, but practical design tasks still face several workflow-level challenges, including heterogeneous tool interfaces, complex input-output constraints, high-cost steps that should not be invoked blindly, runtime failures that require recovery, and critical decisions that need human review. Focusing on the development of a next-generation protein design system based on large language model (LLM)-driven Agent collaboration, this thesis designs and implements an LLM-driven multi-Agent collaboration and adaptive workflow planning system for protein design tasks. The goal is to build, on top of existing tools and remote model services, a workflow control framework that is plannable, executable, recoverable, and auditable.

The system adopts a layered architecture that organizes input interaction, intelligent planning, workflow execution, safety summarization, and resource management. PlannerAgent generates candidate toolchains and explanations, ExecutorAgent executes confirmed workflow steps, SafetyAgent provides risk signals, and SummarizerAgent produces result reports. ProteinToolKG is used to describe tool capabilities, input-output contracts, cost information, and risk information. A finite state machine (FSM) constrains the task lifecycle, and a human-in-the-loop (HITL) mechanism is introduced to handle candidate selection under high risk, high cost, or strong uncertainty. To support runtime recovery, this thesis further proposes Constraint- and Evidence-aware Belief-guided Recovery-adaptive Workflow Planning (CEBRA-WP). At the workflow layer, CEBRA-WP combines task constraints, tool knowledge, execution history, runtime observations, and a Lite belief-state to perform hard feasibility filtering, static scoring, posterior objective adaptation, runtime reranking, and recovery action selection.

In terms of implementation, the backend is built with Python, FastAPI, and Pydantic, while the frontend is implemented as a lightweight Web workbench using React, TypeScript, and Vite. External capabilities such as structure prediction, sequence generation, quality control, and objective scoring are encapsulated through ToolAdapter interfaces.

The main contributions of this thesis are as follows: it constructs a recoverable and auditable prototype system for protein design workflows; proposes and implements the CEBRA-WP workflow planning algorithm; establishes an evidence chain from system validation to strategy ablation; and provides a bounded experimental analysis of runtime recovery, cost control, and audit explanation in high-cost scientific workflows.

## Keywords

protein design; LLM-driven system; multi-agent collaboration; adaptive workflow planning; CEBRA-WP; human-in-the-loop
