# 系统功能与模块盘点

更新时间：2026-05-07

## 盘点范围

本盘点面向毕业论文撰写，关注“系统已经实现了什么、哪些模块有验证依据、哪些内容仍需补齐或谨慎表述”。主要参考：

- 代码实现：`src/`、`tests/`、`frontend/`、`scripts/`
- 设计依据：`AGENT_CONTRACT.md`、`../thesis-project.design/docs/design/`
- 验证材料：`README.md`、`reports/full_flow_validation_report.md`、`docs/experiment/algorithm-group-paper-mapping.md`
- 已绘制图示：`asserts/figures/`

状态说明：

| 状态 | 含义 |
|:---|:---|
| 已完成 | 有明确实现，并有测试、验证报告或可运行入口支撑 |
| 部分完成 | 核心代码或入口已存在，但依赖外部环境、真实服务、数据规模或补充实验 |
| 待补齐 | 论文可作为后续工作、限制条件或待完善模块表述，不建议写成已完成能力 |

## 系统现有功能概览

系统已经形成一个面向蛋白质设计任务的 LLM 驱动多智能体工作流平台。核心闭环为：自然语言任务录入，结构化任务解析，Planner 生成候选工具链，FSM 管理执行生命周期，Executor 调度工具适配器，运行时状态评估失败风险，必要时触发 retry、patch、replan 与 HITL 确认，最终由 Summarizer 汇总报告。

当前实现最突出的论文主线是“高代价、长链路、可失败科研工作流中的自适应规划与人在环路控制”。这条主线已经有较完整的代码、设计契约和测试证据支撑。

## 已完成模块

| 模块 | 主要路径 | 完成度 | 论文表述重点 | 证据/备注 |
|:---|:---|:---|:---|:---|
| 任务录入与结构化解析 | `src/models/task_intake.py`、`src/api/main.py`、`frontend/src/pages/TaskBuilderPage.tsx` | 已完成 | 支持从用户目标、约束、预算、安全级别等信息构建 `ProteinDesignTask` | API 存在 task-intakes、intent-drafts、confirm/cancel 等端点 |
| 工作流状态机 FSM | `src/workflow/`、`src/models/task.py`、`src/storage/` | 已完成 | 显式生命周期：`CREATED -> PLANNING -> WAITING_* -> RUNNING -> SUMMARIZING -> DONE` | 设计约束要求 `WAITING_*` 前持久化快照；测试与验证报告覆盖等待、决策、恢复 |
| 人在环路 HITL | `src/workflow/decision_*`、`src/api/main.py`、`frontend/src/components/PendingActionList.tsx` | 已完成 | `PendingAction` 暴露待决策项，`Decision` 驱动状态恢复或终止 | 已覆盖计划确认、补丁确认、重规划确认和决策日志 |
| Planner 候选生成 | `src/agents/candidate_generator/`、`src/agents/planner/` | 已完成 | 生成 Plan/Patch/Replan 候选，支持 Top-K、风险、成本、解释字段 | 设计要求候选包含 score、risk、cost、explanation；实现与测试已覆盖 |
| 执行与依赖解析 | `src/workflow/plan_runner.py`、`src/agents/executor/`、`src/adapters/` | 已完成 | Executor 是唯一工具执行者，负责步骤调度、输入引用解析、失败检测 | `StepResult`、工具适配器、执行后汇总已落地 |
| 失败恢复链路 | `src/workflow/patch_runner.py`、`src/workflow/recovery.py`、`src/workflow/runtime_evaluator.py` | 已完成 | 有界 retry 后进入 patch，再根据风险进入 replan 或终止候选 | 验证报告覆盖 retry exhausted、patch failure、high-risk replan 等路径 |
| 运行时状态评估 | `src/workflow/runtime_evaluator.py`、`src/models/runtime_state.py` | 已完成 | 使用 Lite belief-state 表征成功概率、结构失败压力、恢复余量、剩余成本、证据充分度 | 设计中五维状态已与实现对应，适合放入核心算法章节 |
| 工具适配器体系 | `src/adapters/`、`src/tools/`、`src/engines/`、`src/kg/` | 已完成 | 将 ESMFold、ProteinMPNN、ProtGPT2、BioPythonQC 等能力封装为统一工具接口 | 部分远程/商业服务依赖环境变量或外部服务，见待补齐项 |
| 安全检查与风险标记 | `src/agents/safety/`、`src/models/safety.py` | 已完成 | SafetyAgent 只输出 ok/warn/block，不执行工具、不修改状态 | 与 Agent 边界契约一致 |
| 总结报告生成 | `src/agents/summarizer/`、`src/api/main.py` | 已完成 | 汇总候选序列、结构路径、评分、风险、运行日志 | API 提供 task report 入口 |
| 事件日志与快照 | `src/storage/` | 已完成 | 状态迁移、PendingAction、执行进度和 artifacts 可审计、可恢复 | 论文可作为可靠性设计小节 |
| Web 工作台 | `frontend/src/`、`src/api/static/` | 已完成 | 包含任务构建、任务详情、事件时间线、待决策面板、候选比较、能力就绪面板等 | 可用于论文系统界面截图 |
| 系统验证用例 | `tests/`、`reports/full_flow_validation_report.md` | 已完成 | 覆盖核心 FSM、HITL、patch/replan、LLM provider smoke、远程适配器成功路径 | README 记录基线为 `792 passed, 11 skipped`，其中一个 Nextflow 集成失败 FSM 用例被排除 |

## 部分完成模块

| 模块 | 当前情况 | 论文写法建议 | 后续动作 |
|:---|:---|:---|:---|
| 外部真实工具服务 | 本地/模拟/部分远程适配器已实现；NIM、OpenFold3、AlphaFold2 等依赖密钥、REST 服务或远程环境 | 写成“支持可插拔远程工具适配器，并完成部分服务联调” | 补充真实服务运行记录、失败样例和环境说明 |
| 动态优化算法的学习化部分 | Lite belief-state、候选重排序、恢复动作选择已实现；目前更偏规则化/启发式闭环 | 写成“轻量运行时状态驱动的自适应规划”，避免夸大为大规模学习优化器 | 若要增强论文贡献，可补充 ablation 和参数敏感性实验 |
| 实验数据与统计显著性 | 已有实验设计和映射文档，但最终论文用数据集、重复次数、统计表仍需冻结 | 写成“实验框架已搭建” | 固定实验配置，导出最终结果表和图 |
| 前端可用性验证 | UI 模块完整，但缺少正式用户研究或可用性量化报告 | 写成“提供交互式工作台支持人工确认” | 截取关键页面，补充一次端到端演示记录 |
| ToolKG 图数据库化 | 当前能力图可支撑工具发现和校验，但不是完整知识图谱数据库系统 | 写成“轻量工具能力图/工具目录” | 如论文需要“知识图谱”表述，应补充 schema、样例和查询机制说明 |
| 自动图表导出流程 | `.drawio` 源文件和部分导出文件已存在，脚本已开始按图拆分 | 写成“论文图示已绘制，源文件可维护” | 后续每张图保持独立脚本，避免覆盖人工修改 |

## 缺失或待补齐模块

| 缺失项 | 影响 | 建议处理 |
|:---|:---|:---|
| Nextflow failure FSM 集成用例尚未纳入主基线 | 影响“所有执行后端失败语义均已验证”的强表述 | 论文中写为“核心执行链路已验证，特定 Nextflow 失败集成场景仍待补充” |
| 大规模真实蛋白质任务基准 | 影响算法效果的统计说服力 | 至少补充小规模可复现实验集、失败恢复对比组和成本指标 |
| 与人工专家决策质量相关的评测 | 影响 HITL 有效性量化 | 可用案例分析替代正式用户研究，明确论文限制 |
| 生产级权限、多用户与审计安全 | 对论文原型系统影响较小，但不宜写成生产系统能力 | 放入系统局限与未来工作 |
| 完整模型服务稳定性监控 | 当前有能力就绪和事件日志，但缺少长期 SLA 监控 | 论文中不扩展为运维平台能力 |
| 自动化论文结果包生成 | 图、表、验证材料分散在多个目录；本目录是初步整理 | 后续可新增 `docs/reports/final-experiment-pack.md` |

## 可直接支撑论文的功能点

1. 显式 FSM 与 `WAITING_*` 状态将执行暂停、人工确认和恢复语义统一建模。
2. `PendingAction`/`Decision` 把人类决策从隐式操作变成可审计数据契约。
3. Lite belief-state 让 patch、replan、continue、stop 等动作选择具有运行时依据。
4. 工具适配器层将蛋白质设计工具封装为可组合、可替换、可验证的执行单元。
5. 验证报告显示核心路径已经覆盖：Top-K 计划确认、补丁确认、重规划、失败恢复、远程适配器成功流和多 LLM provider smoke。

## 下一步建议

| 优先级 | 动作 | 产物 |
|:---|:---|:---|
| 高 | 固化论文实验配置和最终测试命令 | 实验设置表、结果汇总表 |
| 高 | 为关键 UI 页面导出截图 | 系统界面图、HITL 决策界面图 |
| 中 | 补充真实工具服务案例 | 成功案例、失败恢复案例 |
| 中 | 梳理核心算法伪代码 | 算法流程表或算法框 |
| 低 | 将本盘点同步到论文第四章实现小节 | 正文章节草稿 |
