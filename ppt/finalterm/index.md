# 毕业设计答辩 PPT 制作梳理

## 1. 时间约束与制作策略

本次答辩口头汇报控制在 8-10 分钟，并预留约 5 分钟提问。因此 PPT 主体控制为：

- 主讲页：16 页（含封面和目录），目标口播 9 分钟左右。
- 备份页：5 页，不主动讲，用于回答算法细节、失败案例、测试证据和实现细节问题。
- 结尾页：1 页，使用 HIT 模板的“谢谢 / Thanks”收尾视觉，放在整套 PPT 最后。
- 每页只保留一个核心判断，复杂公式、长表格和代码细节下沉到备份页或口头说明。

答辩主线保持不变：

> 为什么需要这个系统 → 我设计了什么架构 → 我提出了什么工作流规划机制 → 我如何实现 → 我如何验证它有效。

需要反复守住的边界：

- 本工作不涉及新的蛋白质生成模型训练。
- 本工作不宣称候选蛋白经过湿实验验证。
- 结论限定在工作流层、工程原型层和机制可观测层。
- 软件工程答辩重点放在：架构清楚、本人工作清楚、工程实现可信、测试验证充分、结论不过度夸大。

## 2. PPT 章节安排

| 章节 | 页码 | 目标 | 建议时间 |
|---|---:|---|---:|
| 开场与问题 | 1-5 | 讲清题目、目录、痛点、目标、本人工作 | 1.7 min |
| 架构设计 | 6-8 | 讲清五层架构、Agent 职责、FSM/HITL | 2.0 min |
| 核心机制 | 9-11 | 讲清为什么提出 CEBRA-WP、算法闭环和恢复动作 | 2.0 min |
| 工程实现 | 12-13 | 说明系统落地到代码、运行时和工具适配 | 1.5 min |
| 验证与总结 | 14-16 | 用测试、实验和结论边界收束 | 1.8 min |

总目标：正常讲 9 分钟；若现场催促，可跳过第 7 页部分细节、第 11 页表格细节、第 13 页工具适配细节，压到 8 分钟以内。

## 3. 资料与图件来源

| 来源 | 用途 |
|---|---|
| `docs/final-term/2022112879-郑彦文-基于大模型驱动的agent协作新一代蛋白质设计系统开发.docx` | PPT 主体叙事、结论数字、贡献边界 |
| `paper/figures/` | 架构图、算法图、FSM、HITL、工作流、实验图 |
| `../thesis-project.design/docs/design/architecture.md` | 五层架构、FSM、PendingAction/Decision、TaskSnapshot 设计依据 |
| `../thesis-project.design/docs/design/core-algorithm-spec.md` | CEBRA-WP 形式化、候选过滤、Lite belief-state、恢复动作 |
| `../thesis-project.design/docs/design/system-implementation-design.md` | 实现模块、Workflow/FSM、ToolAdapter、API、前端工作台依据 |
| `../thesis-project.dev/src/` | 实现可信性：`api/`、`models/`、`workflow/`、`agents/`、`adapters/`、`kg/`、`storage/` |
| `../thesis-project.dev/docs/system-validation/` | 13 个测试用例、证据索引、前端截图、API/CLI/日志证据 |
| `../thesis-project.dev/docs/experiment/thesis-final-v1-results.md` | 84-run 四组策略消融结果 |

优先使用的图片：

| 图件 | 建议用途 |
|---|---|
| `paper/figures/problem-solution-comparison.drawio.png` | 第 3 页：固定流水线 vs 本系统 |
| `paper/figures/system-architecture.drawio.svg` | 第 6 页：系统五层架构 |
| `paper/figures/protein-toolkg-local-view.drawio.svg` | 第 7 或第 13 页：工具能力与 I/O 关系 |
| `paper/figures/fsm-state-transition.drawio.svg` | 第 8 页：任务生命周期 |
| `paper/figures/hitl-decision-conditions.drawio.png` | 第 8 页：HITL 触发边界 |
| `paper/figures/workflow-flowchart.drawio.svg` | 第 9 页：六阶段工作流和算法动机 |
| `paper/figures/algorithm-loop.drawio.svg` | 第 10 页：CEBRA-WP 闭环 |
| `paper/figures/runtime-sequence.drawio.svg` | 第 13 页：运行时执行序列 |
| `paper/figures/workflow-swimlane.drawio.svg` | 第 13 页备选：模块泳道协作 |
| `paper/figures/experiment-design-framework.drawio.svg` | 第 15 页：实验矩阵 |
| `paper/figures/recovery-path-comparison-timeline.drawio.svg` | 备份页：失败与恢复路径解释 |
| `../thesis-project.dev/docs/system-validation/06-ui-screenshots/dashboard-ch.png` | 第 12 页：Web 工作台总览 |
| `../thesis-project.dev/docs/system-validation/06-ui-screenshots/task-detail-ch3.png` | 第 12 页：候选审查 / HITL |
| `../thesis-project.dev/docs/system-validation/06-ui-screenshots/timeline-events.png` | 第 14 页：事件链和审计证据 |

## 4. 主讲 16 页逐页编排

### 1. 封面

| 项目 | 内容 |
|---|---|
| 建议时间 | 15 秒 |
| 标题 | 基于大模型驱动的 Agent 协作新一代蛋白质设计系统开发 |
| 版式 | 居中标题 + 姓名、学号、专业、指导教师、答辩日期 2026年5月26日 |
| 图示 | 可用低透明度系统架构线框或 `hit.png`，不要喧宾夺主 |
| 口播重点 | 这是软件工程系统设计与实现题，重点是多 Agent 协作、工作流规划、工程实现与验证 |

### 2. 目录

| 项目 | 内容 |
|---|---|
| 建议时间 | 15 秒 |
| 标题 | 目录 |
| 版式 | 纵向五段：背景问题、架构边界、规划机制、工程验证、结论备查 |
| 内容 | 每段对应后续一组页面，强调软件工程答辩重点：架构、机制、实现、验证 |
| 图示 | HIT 模板顶栏尾栏 + 简洁列表 |
| 口播重点 | 快速建立听众预期，不展开技术细节 |

### 3. 汇报问题链

| 项目 | 内容 |
|---|---|
| 建议时间 | 20 秒 |
| 标题 | 汇报问题链 |
| 版式 | 横向五段流程：需要系统 -> 架构 -> 机制 -> 实现 -> 验证 |
| 内容 | 每段只放 1 句：多工具高代价工作流；五层 + 多 Agent；CEBRA-WP；API/Workflow/ToolAdapter/Web；13 TC + 84 runs |
| 图示 | 简洁流程线 |
| 口播重点 | 从工程约束出发，依次给出架构、规划机制、实现路径和验证证据 |

### 4. 背景痛点：为什么固定流水线不够

| 项目 | 内容 |
|---|---|
| 建议时间 | 35 秒 |
| 标题 | 蛋白质设计工作流的工程复杂性 |
| 版式 | 左侧“典型流程”，右侧“工程痛点”，底部一句“固定流水线局限” |
| 内容 | 流程：目标描述、候选序列生成、结构预测、质量筛选、目标评分、结果汇总。痛点：接口异构、I/O 约束复杂、高代价调用、运行时失败、关键决策需审查 |
| 图示 | `paper/figures/problem-solution-comparison.drawio.png` |
| 口播重点 | 已有工具有单点能力，但缺少可规划、可恢复、可审计的工作流控制层 |

### 5. 系统目标与本人工作

| 项目 | 内容 |
|---|---|
| 建议时间 | 35 秒 |
| 标题 | 本文解决的是工作流控制问题 |
| 版式 | 左侧“边界”，右侧“四项工作” |
| 内容 | 边界：不训练新模型，不做湿实验验证，不替代生物学工具。本人工作：系统架构、CEBRA-WP、工程实现、测试实验 |
| 图示 | 四象限：架构 / 算法 / 实现 / 验证 |
| 口播重点 | 本人的工作量在于把任务、工具、状态、人工决策、恢复和证据链打通 |

### 6. 总体架构：五层分层设计

| 项目 | 内容 |
|---|---|
| 建议时间 | 45 秒 |
| 标题 | 系统五层架构 |
| 版式 | 左侧架构图，右侧每层一句职责 |
| 内容 | 输入交互层：Web/CLI/API 与人工决策；智能规划层：PlannerAgent、ProteinToolKG、CEBRA-WP；工作流执行层：ExecutorAgent、PlanRunner、StepRunner；安全与汇总层：SafetyAgent、SummarizerAgent；资源层：ToolAdapter、KG、日志、快照、产物 |
| 图示 | `paper/figures/system-architecture.drawio.svg` |
| 口播重点 | 职责隔离是架构关键：规划不执行工具，执行不越过 FSM，安全不改计划，汇总不重新计算 |

### 7. Agent 职责与数据契约

| 项目 | 内容 |
|---|---|
| 建议时间 | 35 秒 |
| 标题 | 多 Agent 协作如何避免越权 |
| 版式 | 左侧 Agent 职责表，右侧核心契约 |
| 内容 | PlannerAgent 生成候选；ExecutorAgent 执行已确认步骤；SafetyAgent 输出 ok/warn/block；SummarizerAgent 汇总报告；ToolAdapter 屏蔽工具差异；ProteinToolKG 提供能力、I/O、成本、安全约束 |
| 图示 | `paper/figures/uml-contracts.drawio.svg` 或 `paper/figures/protein-toolkg-local-view.drawio.svg` |
| 口播重点 | 通过 Plan、StepResult、PendingAction、Decision、TaskSnapshot 等契约，让 Agent 协作可验证、可审计 |

### 8. FSM 与 HITL：关键决策可控

| 项目 | 内容 |
|---|---|
| 建议时间 | 45 秒 |
| 标题 | 用状态机约束人在环决策 |
| 版式 | 左侧 FSM 状态图，右侧三类 WAITING 状态 |
| 内容 | WAITING_PLAN_CONFIRM：初始计划确认；WAITING_PATCH_CONFIRM：局部失败修补确认；WAITING_REPLAN_CONFIRM：整体风险、结构性失败或 stop 候选确认。人工通过 Decision 提交，系统记录 EventLog 与 Snapshot |
| 图示 | `paper/figures/fsm-state-transition.drawio.svg`，角落放 `paper/figures/hitl-decision-conditions.drawio.png` |
| 口播重点 | HITL 对应 FSM 中可恢复、可审计的等待态机制，前端按钮只是决策入口 |

### 9. 算法动机：为什么需要 CEBRA-WP

| 项目 | 内容 |
|---|---|
| 建议时间 | 35 秒 |
| 标题 | 为什么需要 CEBRA-WP |
| 版式 | 左侧六阶段工作流，右侧三条动机 + 四类动作 |
| 内容 | 阶段划分能说明流程，但不能决定失败后继续、修补、重规划还是止损。CEBRA-WP 在工具链执行过程中，根据约束、证据、成本和失败信息动态选择下一步恢复动作 |
| 图示 | `paper/figures/workflow-flowchart.drawio.svg` |
| 口播重点 | 算法解决的是运行时恢复决策，不涉及底层蛋白质生成模型训练 |

### 10. CEBRA-WP 四步主流程

| 项目 | 内容 |
|---|---|
| 建议时间 | 45 秒 |
| 标题 | CEBRA-WP 怎么做 |
| 版式 | 横向四步流程 + 下方三条与普通 planner 的关键差异 |
| 内容 | 候选生成 -> 硬可行性过滤 -> 状态更新与重排 -> 恢复动作选择。硬约束包含 tool、schema、I/O、safety、budget；运行时只重排已经合法的候选 |
| 图示 | 四步流程图；公式和符号放到口头解释或备份材料 |
| 口播重点 | 硬约束先过滤，运行时只重排合法候选；输出动作再进入 FSM/HITL 审计流程 |

### 11. 算法效果承接

| 项目 | 内容 |
|---|---|
| 建议时间 | 35 秒 |
| 标题 | CEBRA-WP 的效果如何体现 |
| 版式 | 三个关键数字 + 高代价调用柱状图 + 三条解释 |
| 内容 | lite_belief_state 组 21/21 runs 产生 RuntimeState；dynamic/lite 高代价调用为 20 次，fixed 为 28 次；成功率没有形成明显优势，因此结论限定在机制可观测、恢复解释和成本控制 |
| 图示 | 21/21、20、28 三个数字卡片 + fixed/dynamic/lite 柱状图 |
| 口播重点 | 这页把轻量状态和 84-run 结果相连，完整实验矩阵仍在第 15 页展开 |

### 12. 工程实现总览

| 项目 | 内容 |
|---|---|
| 建议时间 | 40 秒 |
| 标题 | 从设计到代码的模块落点 |
| 版式 | 左侧目录映射，右侧放 2 张前端截图小图 |
| 内容 | `src/api/` 输入和 HITL 接口；`src/models/` Pydantic 契约；`src/agents/` 多 Agent；`src/workflow/` FSM、PlanRunner、StepRunner、RuntimeEvaluator、恢复与快照；`src/adapters/` ToolAdapter；`src/kg/` ProteinToolKG；`src/storage/` 事件日志和快照 |
| 图示 | 目录树 + `dashboard-ch.png`、`task-detail-ch3.png` |
| 口播重点 | 系统按契约、状态、工具和审计分层实现，不按单脚本 demo 组织 |

### 13. 运行时执行与工具适配

| 项目 | 内容 |
|---|---|
| 建议时间 | 40 秒 |
| 标题 | 可恢复执行如何落地 |
| 版式 | 左侧运行时序图，右侧 ToolAdapter / ProteinToolKG 小结 |
| 内容 | WorkflowContext 保存任务、计划、步骤结果、安全事件、RuntimeState、PendingAction；PlanRunner 推进计划和 FSM；StepRunner 做输入解析、ToolAdapter 调用、有界重试、错误归一化；ToolAdapter 统一本地/远程工具调用，ProteinToolKG 保存能力、I/O、成本、安全等级 |
| 图示 | `paper/figures/runtime-sequence.drawio.svg`，可在角落放 `paper/figures/protein-toolkg-local-view.drawio.svg` 缩略图 |
| 口播重点 | 难点在于失败不能散落为异常，而要归一化为可恢复状态和可审计事件 |

### 14. 系统测试：工程实现是否可信

| 项目 | 内容 |
|---|---|
| 建议时间 | 40 秒 |
| 标题 | 13 个测试用例覆盖关键路径 |
| 版式 | 测试类别矩阵 + 结果卡片 |
| 内容 | TC-S01 至 TC-S13 覆盖环境/API、任务录入、候选生成、HITL、FSM、快照恢复、Web/CLI、失败恢复、安全边界、端到端。结果：12 个通过，1 个 CLI 相关用例部分通过；证据包括 8 个 API JSON、4 组 pytest 日志、18 张截图、EventLog/Snapshot 样本 |
| 图示 | 重绘表 6-1 为热力矩阵；角落放 `../thesis-project.dev/docs/system-validation/06-ui-screenshots/timeline-events.png` |
| 口播重点 | 测试重点是状态迁移、候选绑定、终态不可变、等待态恢复和安全阻断，而不只是页面能打开 |

### 15. 实验验证：CEBRA-WP 机制是否有效

| 项目 | 内容 |
|---|---|
| 建议时间 | 55 秒 |
| 标题 | 84-run 四组消融实验 |
| 版式 | 上半部分实验矩阵，下半部分三张数字卡片 |
| 内容 | 四组策略：static_top1、fixed_threshold_gate、dynamic_no_belief_state、lite_belief_state。12 个 task_keys，84 runs，每组 21 runs。结果：81/84 DONE；lite_belief_state 21/21 产生 RuntimeState；dynamic/lite 高代价调用总数 20，fixed 为 28，相比 fixed 节省 28.6%；fixed 触发 6 次真实局部修补，也暴露 patch 循环成本 |
| 图示 | `paper/figures/experiment-design-framework.drawio.svg` + 简化柱状图：DONE、high_cost_total、runtime_state_observable_rate |
| 口播重点 | 诚实表述：static 成功率最高；CEBRA-WP 的主要证据是机制可观测、恢复控制、候选解释和高代价调用控制 |

### 16. 总结与边界

| 项目 | 内容 |
|---|---|
| 建议时间 | 25 秒 |
| 标题 | 贡献、局限与展望 |
| 版式 | 左侧四点贡献，右侧三点局限 |
| 内容 | 贡献：可恢复可审计多 Agent 工作流原型；CEBRA-WP；FSM/HITL/快照/事件日志约束 Agent 行为；测试与 84-run 消融证据链。局限：实验矩阵有限；真实后缀重规划在批量实验中不足；系统仍为原型，持久化、KG 动态更新、远程服务探活可继续完善 |
| 图示 | 第 3 页问题链的收束版 |
| 口播重点 | 结论限定在工作流层：系统验证规划、执行、恢复和审计机制；候选蛋白生物学有效性留待后续实验 |

## 5. 备份页建议

备份页不计入 8-10 分钟主讲，用于 5 分钟提问。建议放在正式 PPT 末尾，标题可标为“Backup”或“附：答辩问答备查”。

| 备份页 | 用途 | 内容与图示 |
|---|---|---|
| B1 失败样本概览 | 回答“失败样本是否可解释” | fixed_threshold_gate、lite_belief_state、dynamic_no_belief_state 三类失败概览，强调可恢复、可审计和硬约束边界 |
| B2 失败案例时间线 | 回答“失败样本说明什么” | `paper/figures/recovery-path-comparison-timeline.drawio.svg`；fixed patch loop、lite 可观测但未完全打破循环、dynamic I/O closure failure |
| B3 测试证据索引 | 回答“测试是否充分” | 13 个 TC 对应证据编号，包含 EVD-API、EVD-TEST、EVD-LOG、FIG-SV |
| B4 前端与接口截图 | 回答“系统是否真的可用” | Dashboard、Task Builder、Task Detail、Timeline 四张截图 |
| B5 局限与后续改进 | 回答“下一步如何做” | 扩大任务矩阵、强化 suffix_replan 和 safety block 批量触发、完善持久化和 ToolKG 动态更新 |

备份页之后保留 HIT 模板结尾页，用于最终收尾或问答后结束展示。

## 6. 8 分钟压缩讲法

如果现场时间明显偏紧，按以下方式压缩：

| 合并/快过 | 处理方式 |
|---|---|
| 第 7 页 Agent 职责 | 只讲 Planner / Executor / Safety 三个核心边界，Summarizer 和 ToolAdapter 一句话带过 |
| 第 11 页算法效果 | 只讲 21/21、20、28 三个数字和“成功率不作为主要结论” |
| 第 13 页运行时与工具适配 | 只讲 StepRunner 有界重试和 ToolAdapter 屏蔽异构工具 |
| 第 14 页测试 | 只报 13 TC、12 通过、1 部分通过、证据类型 |
| 第 16 页总结 | 只讲结论边界，不展开局限 |

8 分钟版本要保留的 5 个数字：

- 13 个测试用例；
- 12 个通过、1 个 CLI 相关用例部分通过；
- 84 runs；
- 81/84 DONE；
- lite_belief_state 21/21 产生 RuntimeState，dynamic/lite 相比 fixed 节省 28.6% 高代价调用。

## 7. 避免过度表述

| 避免说法 | 推荐说法 |
|---|---|
| “系统证明了设计蛋白有效” | “系统验证了工作流层的规划、执行、恢复和审计机制” |
| “CEBRA-WP 提高成功率” | “CEBRA-WP 的机制链路可执行、可观测，并在本实验中提供运行时解释与高代价调用控制” |
| “HITL 是人工按钮” | “HITL 是由 FSM、PendingAction、Decision、EventLog 和 Snapshot 共同约束的等待态机制” |
| “Agent 自动决定所有事情” | “Agent 生成候选和建议，关键选择通过结构化 Decision 完成” |
| “ToolKG 是完整生物知识图谱” | “ProteinToolKG 是轻量工具能力索引，服务于能力发现、I/O 校验和候选解释” |

## 8. 制作注意事项

1. 主讲页必须少字。每页标题下最多 3-4 个短句，详细解释放讲稿或备份页。
2. 第 6、8、10、13、15 页是答辩的技术核心页，图必须清楚，避免缩到看不见。
3. 第 9 页负责讲“算法为什么难”，不要放公式，讲问题复杂性。
4. 第 15 页必须诚实呈现实验结果：static 成功率最高，CEBRA-WP 的亮点在机制可观测和高代价控制。
5. 全文视觉关键词保持统一：可规划、可执行、可恢复、可审计。
