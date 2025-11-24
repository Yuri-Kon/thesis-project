# 进度规划 2025-11-24

## 11.24 -- 12.08

|时间|主要任务|具体工作内容|输出成果|
|:--|:--------|:-----------|:-------|
|Day1-2|数据契约完善|- 完成核心JSON Schema<br/>- 对图例所有实体写清字段、类型、说明|`data-constract`.md|
|Day3|Agent接口固化|- 为四个Agent智能体写出正式的方法签名<br/>- 不要求实现逻辑|`agent-design.md`更新，包含接口|
|Day4-5|代码骨架搭建|- 创建项目结构<br/>- 写类与方法定义<br/>- 写一个最小的workflow.run流程|第一版可运行的骨架|
|Day6-7|工具适配器原型|- 选ESMFold或ProteinMPNN的其中一个<br/>- 写Adapter类<br/>- 完成一次完整调用<br/>- 对结果存储为StepResult JSON|`esmfold_adapter.py`|
|Day8-9|Planner最小可工作原型|- 使用非常简单的规则实现`_make_plan()`: 例如用户输入包含"Structure"->调用ESMFold<br/>- 输出一个包含1-2步骤的Plan JSON|一个可运行的最小Planner|
|Day10|Executor单步执行逻辑|- 让Executor能执行PlanStep调用正确的Adapter<br/>- 输出StepResult|"单步任务"测试通过|
|Day11|Summarizer 最小原型|- 汇总StepResult<br/>- 输出一个最小报告|`summarizer.py`可输出|
|Day12|ProteinToolKG 原型|- 写一个JSON版的KG<br/>- 包括inputs/outputs/capability/safety_level|`protein_tool_kg.json`|
|Day13-14|模块整合|- 完成一个端到端mini pipeline<br/>- 输出一个可运行原型0.1|可展示的最小运行链|

## 之后的规划


| 时间范围 | 阶段目标 | 主要任务（概括版） | 关键可交付物 |
|---------|----------|----------------------|----------------|
| **第 3–4 周（12 月中旬）** | 系统设计收尾 | 完成全部数据契约<br/>完成所有 Agent 接口定义<br/>完善工具适配器规范<br/>初步整合 ProteinToolKG | 系统设计文档（终稿）<br/>KG 原型（JSON/概念图） |
| **第 5–6 周（12 月底至 1 月上旬）** | 工具模块集成 | 添加更多工具适配器（ProteinMPNN、RDKit）<br/>实现结构预测与功能评估调用流程<br/>完善 Executor 调度逻辑 | 工具链调用原型<br/>Executor v1 |
| **第 7–8 周（1 月中旬）** | Planner/Executor 协同完善 | Planner 实现多步骤任务链生成<br/>Executor 支持顺序执行与容错<br/>接入简单安全规则 | 多步骤 Plan → 执行链路 MVP |
| **第 9–10 周（1 月底）** | Multi-Agent 基础闭环 | 实现 Planner → Executor → Summarizer 完整闭环<br/>实现 Safety 基本检查逻辑<br/>端到端测试 | 多 Agent 闭环原型 v1 |
| **第 11–12 周（2 月上旬）** | 系统增强与扩展 | 扩展工具链：更多 AI 模型/筛选模块<br/>增强任务链逻辑（分支/回退）<br/>扩展 ProteinToolKG 内容 | 系统增强版 v1.5 |
| **第 13–14 周（2 月中旬）** | 典型任务场景落地 | 选择酶设计或抗原设计作为测试场景<br/>运行完整 pipeline<br/>记录全流程实验数据 | 典型任务实验结果 |
| **第 15–16 周（2 月底至 3 月上旬）** | 系统原型定稿 | 性能优化<br/>修复运行错误<br/>准备最终入口（界面或 CLI） | 系统原型 v2（正式版） |
| **第 17 周（3 月中旬）** | 论文实验部分完成 | 运行全套实验：结构预测、序列生成、风险分析<br/>整理评估指标<br/>与基线方法对比 | 实验数据<br/>实验图表 |
| **第 18–20 周（3 月底至 4 月初）** | 论文撰写与答辩准备 | 完成论文正文（方法/系统设计/实验/讨论）<br/>绘制所有系统图、流程图<br/>准备答辩 PPT 与要点 | 论文终稿<br/>答辩 PPT |
