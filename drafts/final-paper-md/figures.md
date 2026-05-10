# 终稿图表清单

本文档用于固定 `drafts/final-paper-md/` 终稿正文中的图表编号、图题、文件路径和插入位置。正文写作时应以本文件为准，不临时更改图号；如需新增图表，应先更新本文件，再写入对应章节。

## 1. 使用规则

- 正文引用图表时使用固定编号，例如“如图 4-1 所示”“见表 6-1”。
- 每处“如图/如表所示”后，应在同一小节内插入对应图表，并在图表后解释该图表支持的论点。
- drawio 图优先使用 SVG 文件；若 SVG 不存在，则使用 PNG 文件。
- 第六章验证截图使用证据编号 `FIG-SV-xx`，不纳入正式论文图号，除非后续决定单独作为论文插图。
- 旧 Mermaid 图仅作历史参考，终稿正文不引用。

## 2. 正式插图

| 图号 | 图题 | 插入文件 | 推荐插入位置 | 图后解释要点 |
|---|---|---|---|---|
| 图 2-1 | 技术路线概览 | `paper/figures/technical-route.drawio.svg` | 第二章“相关技术与理论基础”末尾。 | 说明蛋白质设计工具、科学工作流、LLM Agent 和运行时恢复控制之间的关系，并为第三章需求分析提供技术背景承接。 |
| 图 3-1 | 固定流水线与本文系统的问题-方案对照 | `paper/figures/problem-solution-comparison.drawio.svg` | 第三章“需求分析”中问题背景或需求归纳之后。 | 解释固定流水线在工具约束、运行时恢复、人工决策和审计追踪上的不足，并引出本文系统的需求来源。 |
| 图 4-1 | 系统五层分层架构 | `paper/figures/system-architecture.drawio.svg` | 第四章“系统总体架构设计”开头。 | 说明输入层、智能规划层、执行层、安全与汇总层和资源层之间的分工，突出控制面与执行面的分离。 |
| 图 4-2 | ProteinToolKG 局部可视化 | `paper/figures/protein-toolkg-local-view.drawio.svg` | 第四章 ProteinToolKG 与知识约束设计小节。 | 说明工具能力、输入输出、约束、成本、适用场景和 evidence 类型如何被组织为候选生成与筛选依据。 |
| 图 4-3 | FSM 状态转移图 | `paper/figures/fsm-state-transition.drawio.svg` | 第四章运行时状态控制或 FSM 设计小节。 | 解释任务从创建、候选生成、等待人工决策、执行、恢复到终止的受控状态变化，强调 WAITING 类状态和恢复路径。 |
| 图 4-4 | HITL 触发条件与决策逻辑 | `paper/figures/hitl-decision-conditions.drawio.png` | 第四章 HITL 设计小节。 | 说明何时需要人工确认、选择或终止，强调 HITL 不绕过 FSM，而是在风险、成本、失败和证据不足时提供边界控制。 |
| 图 4-5 | 六阶段 de novo 蛋白质设计工作流 | `paper/figures/workflow-flowchart.drawio.svg` | 第四章工作流设计小节。 | 说明任务定义、候选生成、工具执行、结果评估、恢复控制和输出归档的阶段关系。 |
| 图 4-6 | CEBRA-WP 算法闭环 | `paper/figures/algorithm-loop.drawio.svg` | 第四章 CEBRA-WP 算法定义小节。 | 说明候选生成、硬可行性筛选、静态评分、Lite belief-state / 轻量信念状态更新、运行时重排序和恢复动作选择之间的闭环关系。 |
| 图 4-7 | 核心数据契约 UML | `paper/figures/uml-contracts.drawio.svg` | 第四章数据模型或核心契约小节。 | 解释 ProteinDesignTask、Plan、StepResult、PendingAction、Decision、TaskSnapshot、RuntimeState 和 DesignResult 等核心对象之间的结构关系，连接算法定义与工程实现。 |
| 图 4-8 | t1 任务实例走查 | `paper/figures/t1-trpcage-instance-walkthrough.drawio.svg` | 第四章设计章末，作为算法与工作流的实例化说明。 | 通过 t1/TRP-cage 类任务展示候选生成、证据获取、失败恢复和人工决策如何在一个具体任务中串联。 |
| 图 5-1 | 运行时执行序列 | `paper/figures/runtime-sequence.drawio.svg` | 第五章运行时实现或任务执行链路小节。 | 说明前端、API、运行时服务、工具适配器、状态机和审计记录在一次任务推进中的调用顺序。 |
| 图 5-2 | 工作流泳道式模块协作 | `paper/figures/workflow-swimlane.drawio.svg` | 第五章模块协作或核心流程实现小节。 | 说明用户侧、Agent 规划、运行时控制、工具执行和结果归档在系统实现中的责任边界。 |
| 图 7-1 | 实验设计框架 | `paper/figures/experiment-design-framework.drawio.svg` | 第七章实验设计小节。 | 说明任务集、对照组、评价指标、证据输出和结果表格之间的关系，避免实验章节只堆表格。 |
| 图 7-2 | 固定修补与 Lite belief-state 重排序的恢复路径对比 | `paper/figures/recovery-path-comparison-timeline.drawio.svg` | 第七章恢复能力分析小节。 | 对比固定后处理修补与 Lite belief-state 运行时重排序在失败识别、恢复动作选择和剩余成本控制上的差异。 |

说明：`hitl-decision-conditions.drawio` 目前只有 PNG 渲染产物，终稿正文使用 `paper/figures/hitl-decision-conditions.drawio.png`。若后续补导出 SVG，本文件再同步改为 SVG。

## 3. 表格与代码清单

正式表格与代码清单已迁入 `drafts/final-paper-md/tables.md` 统一维护。本文档只负责插图和截图证据，避免图号、表号混在一起造成编号漂移。

当前 `paper/figures/` 中没有“四组消融主实验结果”的独立图片文件。第七章应使用 `tables.md` 中的表 7-1 至表 7-8 承载实验配置、主结果、分层结果、机制对比、成本分析、可观测性、失败归因和证据索引，不引用不存在的图 7-x。

## 4. 验证截图证据

系统测试截图位于 `../thesis-project.dev/docs/system-validation/06-ui-screenshots/`。这些截图可在第六章作为验证证据编号引用，建议使用 `FIG-SV-01` 至 `FIG-SV-18`，不占用正式论文图号。

引用方式示例：

```md
登录成功后的任务列表页面见验证证据 FIG-SV-03。该截图用于说明用户完成认证后能够进入任务管理入口。
```

若后续决定将某张截图作为正式论文插图，应为其重新分配图号，并在本文件“正式插图”中登记。

## 5. 正文插入模板

```md
如图 4-6 所示，CEBRA-WP 将候选生成、硬可行性筛选、静态评分、Lite belief-state / 轻量信念状态更新和恢复动作选择组织为一个运行时闭环。

【图 4-6 CEBRA-WP 算法闭环】
插图文件：`paper/figures/algorithm-loop.drawio.svg`

图 4-6 的核心作用是说明算法并不直接替代底层蛋白质设计算法，而是在工作流层根据约束、证据和运行时状态对候选方案进行筛选、重排序和恢复控制。
```

## 6. 文件存在性检查

截至 2026-05-11，正式插图对应文件均已存在于 `paper/figures/`。其中大多数图同时具备 `.drawio`、`.svg` 和 `.png`，`hitl-decision-conditions.drawio` 当前仅具备 `.drawio` 和 `.png`。
