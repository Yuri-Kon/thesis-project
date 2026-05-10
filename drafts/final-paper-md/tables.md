# 终稿表格与代码清单索引

本文档用于固定终稿 Markdown 写作时可使用的表格、代码清单和证据索引。当前只作为参考索引，不直接替代各章正文。后续撰写 `drafts/final-paper-md/` 正文章节时，应根据本文件选择表格，再调整语言、补充参考文献引用和正文衔接。

## 1. 使用规则

- 正文中的“表 X-Y”应先在本文件登记，再写入章节。
- 表格用于承载证据、指标、对照和归纳；图只用于说明结构、流程和机制差异。
- 第五章代码片段应称为“代码清单”，不应大段铺代码。每个清单必须说明“解决的实现问题”和“对应的设计点”。
- 第六章系统验证表格以 `TC-Sxx`、`SV-xx`、`EVD-*` 和 `FIG-SV-*` 为证据主线。
- 第七章实验表格以 `thesis-final-v1-001` 的 84-run 聚合结果为证据主线。
- 进入终稿时，表中涉及文献背景的解释仍需回到 `references.md` 补充 `[@...]` 引用。

## 2. 第五章：系统实现表格与代码清单

| 编号 | 类型 | 标题 | 推荐位置 | 主要来源 | 作用 |
|---|---|---|---|---|---|
| 表 5-1 | 表格 | 后端核心模块与论文架构层对应关系 | 5.1 技术选型与工程结构 | `drafts/final-term/implementation/01-tech-stack-and-structure.md` | 将 `src/api`、`src/workflow`、`src/models`、`src/adapters` 等目录映射到论文中的架构层，避免实现章变成目录罗列。 |
| 代码清单 5-1 | 代码清单 | 任务创建请求的互斥入口校验 | 5.2 任务接入与后端 API 实现 | `../thesis-project.dev/src/api/main.py:166` | 说明 API 边界如何约束 `goal`、`query`、`confirmed_task_spec` 三种创建模式互斥。 |
| 代码清单 5-2 | 代码清单 | ToolAdapter 抽象接口 | 5.6 工具适配器与能力管理 | `../thesis-project.dev/src/adapters/base_tool_adapter.py:14` | 说明系统如何通过统一接口封装本地脚本、远程 REST 服务和外部工具。 |
| 代码清单 5-3 | 代码清单 | WorkflowContext 统一写入步骤结果并触发 RuntimeState 更新 | 5.4 工作流运行时与执行引擎 | `../thesis-project.dev/src/workflow/context.py:90` | 说明 RuntimeState 更新不是分散修改，而是通过运行时上下文集中接入。 |
| 代码清单 5-4 | 代码清单 | StepRunner 的有界重试微循环 | 5.4 工作流运行时与执行引擎 | `../thesis-project.dev/src/workflow/step_runner.py:140` | 说明单步执行如何处理可重试失败、不可重试失败和重试耗尽。 |
| 代码清单 5-5 | 代码清单 | RuntimeEvaluator 候选重排 | 5.5 CEBRA-WP 的工程落点 | `../thesis-project.dev/src/workflow/runtime_evaluator.py:331` | 说明 CEBRA-WP 的 runtime adjustment 与 rerank 如何落地。 |
| 代码清单 5-6 | 代码清单 | 进入 WAITING 状态前写入 PendingAction 与审计信息 | 5.4 或 5.5 | `../thesis-project.dev/src/workflow/pending_action.py:101` | 说明 HITL 是受控工作流状态，不是前端临时按钮。 |
| 代码清单 5-7 | 备选代码清单 | 构建任务快照 | 5.4 恢复闭环或附录 | `../thesis-project.dev/src/workflow/snapshots.py:34` | 用于补充说明快照如何固化 runtime_state、pending_action 和 artifacts。正文篇幅不足时可放附录。 |

正文建议最多放 4 至 6 个代码清单。`PendingReviewWorkspace` 等前端代码片段可作为附录候选，不建议放入正文主线。

## 3. 第六章：系统测试与验证表格

| 编号 | 标题 | 推荐位置 | 主要来源 | 作用 |
|---|---|---|---|---|
| 表 6-1 | 系统测试用例覆盖矩阵 | 6.1 测试策略与验证目标 | `../thesis-project.dev/docs/system-validation/test-case-table.md` | 汇总 TC-S01 至 TC-S13、验证点、执行结果和核心证据。 |
| 表 6-2 | 系统验证证据类型索引 | 6.1 或 6.2 前 | `../thesis-project.dev/docs/system-validation/evidence-index.md` | 解释 EVD-API、EVD-TEST、EVD-CLI、FIG-SV、EVD-LOG、EVD-EXP 的含义和用途。 |
| 表 6-3 | 前端与 CLI 可用性证据汇总 | 6.7 前端与 CLI 可用性验证 | `evidence-index.md`、`test-case-table.md` | 将 FIG-SV-01 至 FIG-SV-18 和 EVD-CLI-01 至 EVD-CLI-04 汇总，说明 Web 通过、CLI 部分通过。 |
| 表 6-4 | 恢复与安全边界验证证据表 | 6.8 至 6.9 | `test-case-table.md`、`evidence-index.md` | 汇总 retry、patch、replan、terminal_stop、安全 warn/block 的测试与证据。 |

第六章正文可保留表 6-1 和表 6-2 为主表，表 6-3、表 6-4 可按篇幅放入正文或附录。

## 4. 第七章：实验与结果分析表格

| 编号 | 标题 | 推荐位置 | 主要来源 | 作用 |
|---|---|---|---|---|
| 表 7-1 | 实验矩阵配置表 | 7.1 实验设计与研究问题或 7.3 实验环境 | `../thesis-project.dev/docs/experiment/thesis-final-v1-results.md` | 固定 run_id、freeze_id、planner_provider、12 task_keys、4 组、84 runs、repeats 和产物路径。 |
| 表 7-2 | 四组消融主实验结果 | 7.5 四组策略消融主实验 | `thesis-final-v1-results.md` | 展示 success_rate、first_pass_success_rate、schema_valid_rate、high_cost_call_mean、duration、patch/replan 等核心指标。 |
| 表 7-3 | 按任务难度与预算分层的成功率 | 7.5.2 分层分析 | `thesis-final-v1-results.md` | 说明失败集中在 medium/standard 层，避免只看总体均值。 |
| 表 7-4 | 机制增量配对对比 | 7.5.3 机制增量配对对比 | `thesis-final-v1-results.md` | 展示 static→fixed、fixed→dynamic、dynamic→lite 的 paired delta。 |
| 表 7-5 | 高代价调用与运行时间对比 | 7.6 或 7.7 | `thesis-final-v1-results.md` | 支撑“lite/dynamic 比 fixed 低 28.6% 高代价调用”等成本控制叙事。 |
| 表 7-6 | Lite belief-state 机制可观测性对比 | 7.7 信念状态增量价值分析 | `thesis-final-v1-results.md` | 展示 runtime_state_summary、budget_pressure source、action_utility_source 等机制证据。 |
| 表 7-7 | 失败案例归因表 | 7.8 典型案例分析 | `thesis-final-v1-results.md` | 汇总 3 个 FAILED run 的策略、任务、失败类型、根因和论文解释。 |
| 表 7-8 | 实验证据产物索引 | 7.3 或 7.9 | `thesis-final-v1-results.md`、实验输出目录 | 说明 matrix summary、event log、snapshot、report、action distribution 等产物分别支撑哪些结论。 |

当前不建议新增“四组消融主实验结果图”。第七章应以表 7-1 至表 7-8 承载量化证据，以图 7-1 和图 7-2 承担框架和机制解释。

## 5. 结论强度边界

| 可写结论 | 证据表 | 表述边界 |
|---|---|---|
| 系统工程闭环完整，能够支撑任务创建、执行、HITL、报告和审计 | 表 6-1、表 6-2、表 7-1 | 可写“验证通过”或“实验中可追溯”，不要写成生产级可靠性。 |
| CEBRA-WP 机制已实现且可观测 | 表 7-2、表 7-6、代码清单 5-5 | 可写“机制链路可执行、可追踪”，不要写“性能全面最优”。 |
| fixed_threshold_gate 暴露了无 runtime rerank 的恢复代价 | 表 7-4、表 7-5、表 7-7 | 可写“提供必要性证据”，不要写成严格因果证明。 |
| lite_belief_state 的增量价值主要体现在机制可解释和预算感知 | 表 7-6、表 7-7 | 可写“机制优势已验证，性能增益仍受任务规模限制”。 |
| 成本控制存在方向性证据 | 表 7-5 | 可写“趋势”或“在本实验设置下”，不要写统计显著结论。 |

