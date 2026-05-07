# 论文图表清单

更新时间：2026-05-07

## 使用说明

本清单用于管理毕业论文中的图和表。图示源文件优先引用 `asserts/figures/*.drawio`，正文截图或导出图可使用同名 `.png` / `.svg`。编号为建议编号，最终以论文目录结构为准。

## 已有图示清单

| 建议编号 | 图名 | 源文件 | 状态 | 建议章节 | 说明 |
|:---|:---|:---|:---|:---|:---|
| 图 2-1 | 技术路线图 | `asserts/figures/technical-route.drawio` | 已绘制 | 绪论/研究内容 | 展示研究目标、系统设计、算法闭环、实验验证之间的路线 |
| 图 3-1 | 系统总体架构图 | `asserts/figures/system-architecture.drawio` | 已绘制 | 系统需求与总体设计 | 用于说明前端、API、工作流控制、Agent、工具适配器、存储之间的关系 |
| 图 3-2 | 工作流流程图 | `asserts/figures/workflow-flowchart.drawio` | 已绘制 | 系统总体设计 | 展示任务创建、计划生成、确认、执行、恢复、总结的主流程 |
| 图 3-3 | UML 合约图 | `asserts/figures/uml-contracts.drawio` | 已绘制 | 数据模型与接口设计 | 展示 `ProteinDesignTask`、`Plan`、`StepResult`、`PendingAction`、`Decision` 等核心契约 |
| 图 3-4 | FSM 状态转移图 | `asserts/figures/fsm-state-transition.drawio` | 已绘制 | 工作流控制设计 | 对应显式状态机和 `WAITING_*` 人工确认状态 |
| 图 3-5 | 泳道图 | `asserts/figures/workflow-swimlane.drawio` | 已重绘 | 人在环路工作流设计 | 按科研人员、Web UI、API、Planner、Executor、工具、存储等角色划分职责 |
| 图 4-1 | 时序图 | `asserts/figures/runtime-sequence.drawio` | 已重绘 | 系统实现 | 展示对象、生命线、消息和活化，说明一次任务从创建到完成/恢复的执行顺序 |
| 图 4-2 | 算法闭环图 | `asserts/figures/algorithm-loop.drawio` | 已绘制 | 核心算法设计 | 展示候选生成、可行性过滤、运行时状态更新、动作选择、恢复反馈闭环 |
| 图 5-1 | 实验设计框架图 | `asserts/figures/experiment-design-framework.drawio` | 已绘制 | 实验设计 | 展示实验组、对照组、指标、验证路径 |
| 图 5-2 | 系统界面总览图 | 待补充截图 | 待补齐 | 系统实现/实验展示 | 建议从 Dashboard、Task Builder、Task Detail、Pending Review 中选取 |
| 图 5-3 | HITL 决策界面图 | 待补充截图 | 待补齐 | 人在环路验证 | 展示 `PendingAction` 候选比较与人工 `Decision` 提交 |
| 图 5-4 | 失败恢复案例图 | 待补充 | 待补齐 | 实验结果分析 | 可基于一次 retry -> patch -> replan 的事件时间线绘制 |

## 建议新增图示

| 优先级 | 图名 | 用途 | 数据来源 | 备注 |
|:---|:---|:---|:---|:---|
| 高 | 系统界面截图组合图 | 证明系统可交互、可操作 | 前端页面截图 | 建议包含任务构建、任务详情、待决策面板、事件时间线 |
| 高 | 核心算法伪代码框图 | 把算法闭环从架构图转成论文算法表达 | `runtime_evaluator.py`、候选生成器、设计文档 | 可与算法闭环图配套 |
| 高 | 验证覆盖矩阵图 | 展示测试如何覆盖 FSM、HITL、recovery、adapter | `reports/full_flow_validation_report.md`、`tests/` | 可以做成表，也可做热力图 |
| 中 | 工具能力图/ToolKG 示例图 | 展示工具、输入输出、成本、风险、readiness 的关系 | `src/kg/`、`src/adapters/builtins.py` | 若正文强调 ToolKG，建议补充 |
| 中 | 失败恢复事件时间线 | 展示一次失败如何被系统恢复 | EventLog、测试输出、demo audit | 可增强系统可靠性论证 |
| 低 | LLM provider 调用对比图 | 展示多模型规划 smoke 结果 | 验证报告 | 若篇幅有限，可放入表格 |

## 论文表格清单

| 建议编号 | 表名 | 状态 | 建议章节 | 数据来源/备注 |
|:---|:---|:---|:---|:---|
| 表 2-1 | 相关工作对比表 | 待补齐 | 相关技术 | 对比普通 LLM Agent、传统工作流系统、蛋白质设计工具链、HITL 系统 |
| 表 3-1 | 系统功能模块表 | 已整理 | 系统总体设计 | 可从 [system-feature-inventory.md](./system-feature-inventory.md) 提取 |
| 表 3-2 | 核心数据契约表 | 待整理 | 数据模型设计 | `ProteinDesignTask`、`Plan`、`PlanStep`、`StepResult`、`PendingAction`、`Decision`、`RuntimeState` |
| 表 3-3 | FSM 状态定义表 | 已有设计依据 | 工作流控制设计 | `CREATED`、`PLANNING`、`WAITING_*`、`RUNNING`、`SUMMARIZING`、终态 |
| 表 3-4 | Agent 职责边界表 | 待整理 | 多智能体协作设计 | Planner、Executor、Safety、Summarizer 的 must/must_not |
| 表 3-5 | 工具适配器清单 | 待整理 | 工具执行层设计 | ESMFold、ProteinMPNN、ProtGPT2、BioPythonQC、MMseqs2、BlastP、DSSP、ObjectiveRanker 等 |
| 表 4-1 | Lite belief-state 变量表 | 待整理 | 核心算法设计 | `p_success`、`p_structural_failure`、`recovery_margin`、`expected_remaining_cost`、`evidence_sufficiency` |
| 表 4-2 | 恢复动作选择表 | 待整理 | 核心算法设计 | continue、retry、patch、replan、stop 的触发条件和约束 |
| 表 4-3 | 关键 API 端点表 | 待整理 | 系统实现 | `/tasks`、`/pending-actions`、`/task-intakes`、`/intent-drafts` 等 |
| 表 5-1 | 实验组设计表 | 部分已有 | 实验设计 | 可参考 `docs/experiment/algorithm-group-paper-mapping.md` |
| 表 5-2 | 评价指标表 | 待补齐 | 实验设计 | 成功率、恢复成功率、成本、运行时、人工介入次数、证据充分度 |
| 表 5-3 | 测试覆盖与验证结果表 | 部分已有 | 实验结果 | 可整理 `reports/full_flow_validation_report.md` 和 README 测试基线 |
| 表 5-4 | 消融实验结果表 | 待补齐 | 实验结果 | 对比无 HITL、无 runtime state、无 patch/replan 等配置 |
| 表 5-5 | 典型案例分析表 | 待补齐 | 实验结果 | 选取成功执行、局部失败恢复、重规划终止三个案例 |
| 表 6-1 | 系统局限与未来工作表 | 待补齐 | 总结与展望 | 外部服务、真实任务规模、用户研究、生产级安全等 |

## 图表收口检查清单

| 检查项 | 当前状态 | 下一步 |
|:---|:---|:---|
| `.drawio` 源文件齐全 | 已完成 | 保持每张图独立脚本，避免覆盖人工修改 |
| 图示编号与正文一致 | 待补齐 | 论文目录确定后统一编号 |
| 图片导出格式齐全 | 部分完成 | 最终提交前统一导出 PNG 或 SVG |
| 表格有数据来源 | 部分完成 | 每张表标注来源文件或实验命令 |
| 实验图表可复现 | 待补齐 | 固化实验脚本、随机种子、输出目录 |
| 人工修改图示被保护 | 进行中 | 新增图脚本时只写目标图文件 |
