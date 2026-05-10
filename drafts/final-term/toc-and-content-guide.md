# 毕业论文目录结构与内容指示

> 最后更新：2026-05-11
> 适用范围：软件工程专业本科毕业论文（结题报告）
> 参考模板：`reference/结题报告模板(理工类).docx`、`reference/毛星.docx`
> 实验依据：`docs/experiment/final-thesis-experiment-design.md`（双主线结构）
> 证据依据：`docs/system-validation/evidence-index.md`（FIG-SV-*、EVD-API-*、EVD-TEST-*、EVD-CLI-*、EVD-LOG-*）
> 设计真源：`../thesis-project.design/docs/design/`（architecture.md、agent-design.md、core-algorithm-spec.md 等）

---

## 结构决策说明

当前 `paper/tex/stages/final.tex` 为 7 章结构，将「需求」与「设计」合并在第 3 章。实验设计书明确要求「双主线」——系统验证（Ch6）与算法实验（Ch7）分离。因此建议拆为 **8 章**：

| 章节 | 标题 | 与现状的关系 |
|------|------|-------------|
| 第 1 章 | 绪论 | 保留 |
| 第 2 章 | 相关技术与研究工作 | 保留 |
| 第 3 章 | 系统需求分析 | 从原 Ch3 拆分（3.1 独立成章） |
| 第 4 章 | 系统总体设计 | 从原 Ch3 拆分（3.2 + 3.3 独立成章） |
| 第 5 章 | 系统实现 | 保留 |
| 第 6 章 | 系统测试与验证 | 保留（TC-S01~S13 + SV-* 验证点） |
| 第 7 章 | 策略对比实验与结果分析 | 保留（EXP-A1~A5 + 84-run 矩阵） |
| 第 8 章 | 总结与展望 | 保留 |

一级标题遵循软工专业规范（绪论、相关技术、需求分析、总体设计、系统实现、测试、实验、总结）。二级及以下标题体现系统特点，不使用概括性短语。

---

## 详细目录

### 第 1 章　绪论

> 篇幅建议：8–12 页。最后写。此处仅列结构，内容待论文主体定型后凝练。

1.1　蛋白质计算设计的工程化挑战
1.2　国内外研究现状
　1.2.1　蛋白质设计工具与平台
　1.2.2　LLM 驱动的自动化工作流
　1.2.3　自适应规划与恢复机制
1.3　现有方法的局限与本课题的切入点
1.4　论文主要工作
1.5　论文组织结构

---

### 第 2 章　相关技术与研究工作

> 篇幅建议：10–15 页。可在系统章节完成后写。

2.1　蛋白质设计基础
　2.1.1　蛋白质结构与序列表示
　2.1.2　de novo 蛋白质设计的一般流程
2.2　大语言模型与 Agent 协作框架
　2.2.1　LLM 在科学工作流中的应用
　2.2.2　多 Agent 协作模式
2.3　工作流控制与状态管理
　2.3.1　有限状态机与人在环路
　2.3.2　科学工作流中的故障恢复
2.4　蛋白质设计工具链
　2.4.1　序列生成模型（ProtGPT2、ProteinMPNN）
　2.4.2　结构预测方法（ESMFold、OpenFold）
　2.4.3　质量评估与目标评分工具
2.5　本章小结

---

### 第 3 章　系统需求分析

> 篇幅建议：12–16 页。已有草稿素材（原 Ch3 草稿 §3.1），可直接改写。
> 二级标题不使用「功能需求」「非功能需求」等概括语，而是以系统能力维度命名。

3.1　蛋白质设计工作流的典型问题与需求背景
　—— 固定流水线的局限：工具异构、高代价调用、失败不可恢复
　—— 本课题面向的 de novo 设计场景与工作流控制层定位

3.2　面向科研操作员的交互需求
　—— 自然语言目标到结构化任务的渐进式确认
　—— 高风险节点的候选方案审查与人工决策

3.3　多工具链路下的候选计划生成需求
　—— 从 ProteinToolKG 到可执行 PlanStep 的能力组合
　—— 硬可行性过滤：工具存在性、I/O 闭包、安全等级、预算约束

3.4　高代价步骤的执行控制与恢复需求
　—— 有界重试 → 局部修补 → 后缀重规划的分层恢复
　—— 运行时信念状态对 continue / patch / replan / stop 动作的支撑

3.5　人在环路的可审计暂停需求
　—— PendingAction 与 Decision 的结构化交互契约
　—— 进入等待态前的快照持久化约束

3.6　系统边界与非功能性约束
　—— 可追溯性、可扩展性、可恢复性、安全边界、实验可复现性

3.7　本章小结

**关键证据引用**：TC-S02、TC-S03、TC-S05（测试用例表验证功能需求覆盖）；AGENT_CONTRACT.md（系统不变性约束源）

---

### 第 4 章　系统总体设计

> 篇幅建议：25–35 页。已有完整草稿（原 Ch3 草稿 §3.2 + §3.3），可直接改写。
> 此章是论文最重章节。二级标题体现架构特征。

4.1　五层分层架构与设计原则
　—— 输入层 / 智能规划层 / 执行层 / 安全与汇总层 / 资源层
　—— 控制面与执行面的分离：FSM/Workflow 为状态变化 SSOT
　—— 设计图：图 4-1（系统分层架构）

4.2　多 Agent 职责划分与协作关系
　—— PlannerAgent：候选生成者，不执行工具、不改变状态
　—— ExecutorAgent：唯一工具调度者，等待态下停止执行
　—— SafetyAgent：风险信号源，block 触发但不直接终止
　—— SummarizerAgent：汇总者，不参与工作流控制
　—— 各 Agent 的不变性约束（引自 AGENT_CONTRACT.md §4）

4.3　任务生命周期与有限状态机模型
　—— 11 个对外状态的完整转移路径
　—— 三类 WAITING 决策点：plan_confirm / patch_confirm / replan_confirm
　—— terminal_stop 作为终止型 replan 候选的语义
　—— 终态不可变性
　—— 设计图：图 4-2（FSM 状态转移图）

4.4　六阶段 de novo 蛋白质设计工作流
　—— 序列探索 → 结构映射 → 质量门禁 → 结构条件精修 → 目标评分 → 结果汇总
　—— 阶段间循环与 Safety Gate 的介入位置
　—— 设计图：图 4-3（六阶段工作流与恢复感知控制）

4.5　CEBRA-WP：约束与证据感知的自适应工作流规划算法
　4.5.1　问题形式化：constraint-aware / budget-aware / risk-aware / recovery-aware
　4.5.2　离线候选生成与静态多目标评分（GenerateCandidates → FeasibilityFilter → StaticUtility）
　4.5.3　Lite Belief-State：五个持久化核心状态量
　4.5.4　运行时信念更新与后验目标评分（BeliefUpdate → RuntimeCandidateUtility → Posterior Objective Scoring）
　4.5.5　恢复感知的动作选择（continue / patch_local / suffix_replan / stop）
　4.5.6　四种递增策略组：Static Top-1 → Fixed Threshold Gate → Dynamic Recovery → Lite Belief-State
　—— 设计图：图 4-4（CEBRA-WP 算法闭环）

4.6　核心数据契约与结构
　—— ProteinDesignTask → Plan/PlanStep → StepResult → PendingAction/Decision → TaskSnapshot/RuntimeState → DesignResult
　—— 步骤间 S{id}.{field} 引用语法
　—— 设计图：图 4-5（核心数据契约 UML）

4.7　模块划分与职责定位
　4.7.1　任务接入与交互模块
　4.7.2　规划与候选生成模块
　4.7.3　自适应工作流规划与恢复模块（CEBRA-WP 工程承载）
　4.7.4　工作流执行模块（PlanRunner / StepRunner）
　4.7.5　工具适配与能力管理模块（BaseToolAdapter / AdapterRegistry / ProteinToolKG）
　4.7.6　安全与质量门禁模块（SafetyAgent / 质量门禁）
　4.7.7　存储、日志、快照与结果汇总模块

4.8　模块协作流程与算法介入点
4.9　本章小结

**对应草稿**：`drafts/final-term/sections/03-system-requirements-and-design.md`（约 32KB，需按本章结构拆分）
**关键证据引用**：EVD-API-02（readiness 就绪状态）；EVD-LOG-07/08（EventLog/Snapshot 样本）；TC-S03、TC-S06

---

### 第 5 章　系统实现

> 篇幅建议：18–25 页。素材集中于 `drafts/final-term/implementation/`（6 个 Markdown 文件，约 30KB），需大幅压缩。
> 避免逐文件罗列代码，以关键流程和接口说明为主。
> **当前状态：Markdown 初稿已完成**（`sections/05-system-implementation.md`，约 21KB），后续需补齐图表编号并转 LaTeX。

5.1　技术选型与工程结构
　—— Python 3.12 + FastAPI + Pydantic / React 19 + TypeScript + Vite
　—— 自定义 Workflow/FSM（非 LangGraph）的原因与边界
　—— 文件日志与快照存储（原型阶段的设计选择）

5.2　任务接入与后端 API 实现
　—— Task Intake 的渐进式确认链路：draft → confirm → ProteinDesignTask
　—— 15 个核心 API 端点与数据契约映射
　—— PendingAction / Decision 的接口实现

5.3　前端工作台的页面组织与状态加载
　—— Dashboard / Task Builder / Task Detail / Event Timeline 四页面
　—— 交互模块中人工决策的展示与提交流程

5.4　工作流运行时与执行引擎
　—— PlanRunner 与 StepRunner 的实现
　—— PlanStep 引用解析（S{id}.{field} 语法）
　—— 步骤失败分类与 bounded retry 实现

5.5　CEBRA-WP 的工程落点
　—— RuntimeState 更新与持久化
　—— runtime_adjustment 与 posterior_score 的计算链路
　—— 动作选择与恢复闭环的代码映射（patch_local → WAITING_PATCH_CONFIRM 等）

5.6　工具适配器与能力管理
　—— BaseToolAdapter 接口与当前适配器覆盖（ESMFold / OpenFold / ProteinMPNN / ProtGPT2 等）
　—— AdapterRegistry 注册机制
　—— ProteinToolKG 的 JSON 结构与规划规则

5.7　本章小结

**对应素材**：`implementation/01-tech-stack-and-structure.md` 至 `implementation/05-code-snippets.md`
**关键证据引用**：TC-S09、TC-S11（端到端流程与工具链验证）

---

### 第 6 章　系统测试与验证

> 篇幅建议：18–25 页。核心依据：`docs/system-validation/` 下的证据体系。
> 此章回答「系统是否按设计正确工作」，对应实验设计书的「系统可用性与工程验证」主线（EXP-S1~S7）。
> 可直接引用已有证据编号（FIG-SV-*、EVD-API-*、EVD-TEST-*、EVD-CLI-*、EVD-LOG-*）。

6.1　测试策略与验证目标
　—— 双主线定位：本章聚焦系统功能正确性（工程验证），第 7 章聚焦算法有效性（策略实验）
　—— 13 个测试用例（TC-S01~S13）与 30+ 验证点（SV-01~SV-30）的覆盖矩阵

6.2　API 服务与工具能力就绪验证
　—— `/health` 与 `/capabilities/readiness` 的就绪检查
　—— 15 个能力的 ready/degraded/unavailable 状态验证
　—— 证据：EVD-API-01、EVD-API-02、server-startup.log

6.3　任务录入与数据契约验证
　—— Task Intake 的字段注册、缺失字段拒绝、确认创建
　—— Plan candidate 的合约字段完整性（candidate_id、score_breakdown、risk_level、cost_estimate、explanation、source_refs）
　—— 证据：EVD-API-03~08、EVD-TEST-01、TC-S02、TC-S03

6.4　人在环路与决策边界的正确性
　—— WAITING_* 状态下的 PendingAction 存在性
　—— 缺失候选 ID 被拒绝（SV-11）、重复决策被拒绝（SV-12）、错误绑定被拒绝（SV-13）
　—— 等待态下 Executor 停止工具执行
　—— 证据：EVD-TEST-02、EVD-LOG-08、TC-S04

6.5　有限状态机的迁移正确性与终态不变性
　—— 11 个状态的合法迁移路径验证
　—— terminal_stop → FAILED 的审计链完整性
　—— DONE/FAILED/CANCELLED 不可再变更
　—— 证据：EVD-TEST-02、EVD-LOG-03、TC-S05

6.6　快照持久化与恢复正确性
　—— 进入 WAITING_* 前的快照写入（pending_action_id、completed_step_ids、artifacts.runtime_state）
　—— 快照恢复到等待态后不自动推进的语义
　—— 证据：EVD-LOG-01、EVD-LOG-02、TC-S06

6.7　前端与 CLI 可用性验证
　—— Dashboard / Task Builder / Task Detail / Timeline 四页面加载与交互
　—— CLI 的 intake schema、task show、timeline show 命令输出一致性
　—— 证据：FIG-SV-01~18（18 张前端截图）、EVD-CLI-01~04（CLI 输出）、TC-S07、TC-S08

6.8　失败恢复流程的正确性
　—— retry 耗尽 → patch_confirm → WAITING_PATCH_CONFIRM 路径
　—— safety block → replan_confirm → WAITING_REPLAN_CONFIRM 路径
　—— patch accept 后仅修改目标步骤或后缀
　—— 证据：EVD-TEST-03、EVD-LOG-01/02/03、TC-S12

6.9　安全边界的有效性
　—— SafetyAgent 在输入/步骤/输出三阶段的 warn/block 判定
　—— block 阻止工具调用但不直接终止任务
　—— forbidden_motif 确定性阻断的验证
　—— 证据：EVD-TEST-03、TC-S10、TC-S13

6.10　本章小结

**证据索引**：`evidence-index.md`（18 张截图、8 个 API JSON、4 组 pytest、4 个 CLI、2 组 EventLog/Snapshot 样本）
**测试用例表**：`test-case-table.md`（TC-S01 至 TC-S13，全部通过或部分通过）

---

### 第 7 章　策略对比实验与结果分析

> 篇幅建议：20–30 页。核心依据：`docs/experiment/final-thesis-experiment-design.md` 与 `docs/experiment/thesis-final-v1-results.md`。
> 此章回答「CEBRA-WP 是否比基线更好」，对应实验设计书的「CEBRA-WP 算法验证」主线（EXP-A1~A5）。
> **当前状态：Markdown 初稿已完成**（`sections/07-experiments-and-analysis.md`，约 23KB）。84-run 正式矩阵已完成，核心结果为 81/84 DONE，四组策略均完成 21 runs。

7.1　实验设计与研究问题
　—— 七个研究问题（RQ-S1~S3 对应系统验证已在第 6 章回答，RQ-A1~A4 由本章回答）
　—— 内部四组消融 + 外部基线（可选）的实验矩阵
　—— 实验任务集：12 个 task_key × 8 类设计场景，基于真实蛋白质结构（Trp-cage 1L2Y、Villin 1VII、GB1 1PGB、Ubiquitin 1UBQ、Top7 1QYS）

7.2　指标体系
　—— 算法正确性指标：plan_valid_rate、first_pass_success_rate、recovery_success_rate
　—— 成本控制指标：high_cost_call_count、wasted_call_rate、runtime_seconds
　—— 恢复质量指标：patch_event_count、replan_event_count、stop_quality
　—— 信念状态指标：rerank_delta、action_agreement、evidence_sufficiency
　—— 系统可用性指标：task_completion_rate、evidence_completeness

7.3　实验环境与执行配置
　—— planner_provider: deepseek-v4-pro
　—— 工具执行环境：OpenFold3 REST（远程）、ProtGPT2 PLM REST（远程）、BioPython QC（本地）
　—— 矩阵执行方式：`scripts/run_thesis_experiment_matrix.py`
　—— 实验 ID：`thesis-final-v1-001`，产物路径：`output/experiment/thesis-final-matrix/thesis-final-v1-001/`

7.4　CEBRA-WP 机制可行性验证（EXP-A1）
　—— 四个 policy mode 的机制链路验证
　—— lite_belief_state 是唯一产生 runtime_state_summary 和 action_utility 的策略组
　—— 候选 metadata 中的 runtime_adjustment、action_utility、rerank_reason 字段
　—— 当前证据：84-run 中 lite_belief_state 的 runtime_state_observable_rate=1.0，action_utility_source=computed

7.5　四组策略消融主实验（EXP-A2）
　—— static_top1 / fixed_threshold_gate / dynamic_no_belief_state / lite_belief_state
　—— 主结果：static_top1 成功率 1.0000；fixed_threshold_gate、dynamic_no_belief_state、lite_belief_state 成功率均为 0.9524
　—— 重点叙事：不夸大 lite 的成功率优势，转向机制可观测性、恢复开销与高代价调用控制
　—— 表 7-1：四组消融主实验结果

7.6　静态规划的必要性分析（EXP-A3）
　—— static_top1 是唯一 100% 成功组，但缺少运行时恢复与信念观测机制
　—— fixed_threshold_gate 触发 6 次真实 patch 与额外高代价调用，证明固定门控会带来恢复开销
　—— 3 个 FAILED run 用于分析固定门控循环、belief-state 确定性不足和候选 I/O 闭包失败

7.7　信念状态的增量价值分析（EXP-A4）
　—— dynamic_no_belief_state vs lite_belief_state 的定向对比
　—— lite_belief_state 在全部 21 runs 中产生 runtime_state 与 action_utility，可作为 CEBRA-WP 可执行性的最强证据
　—— lite/dynamic 相比 fixed_threshold_gate 减少高代价调用；lite 通过预防性 rerank 避免 fixed 的 patch 触发

7.8　典型案例分析（EXP-A5）
　—— 案例选取：fixed/t2_ubiquitin patch 循环耗尽；lite/t2_ubiquitin belief-state 观测但未稳定打破循环；dynamic/t3_gb1 candidate I/O closure hard-fail
　—— 这些案例用于说明机制边界，而非回避失败结果

7.9　外部基线对照（EXP-A6，可选）
　—— ReAct-style / ToT-style / Reflexion-style 与内部方法对比
　—— 当前状态：尚未执行，不作为论文通过的必要条件

7.10　结论边界与限制说明
　—— n=2 统计效力有限，避免强统计显著性声称
　—— t5/t8 未触发预期 patch/safety 行为，需以 focused tests 作为补充机制证据
　—— lite_belief_state 未体现成功率优势，论文主结论应落在机制可观测性、运行时控制和成本/恢复开销差异

7.11　本章小结

**实验设计依据**：`docs/experiment/final-thesis-experiment-design.md`（12 实验 × 7 RQ × 指标体系 × 三层结论边界）
**任务集设计**：`docs/experiment/final-task-set-design.md`（12 task_key，8 类设计场景，6 个真实蛋白质结构来源）
**完整结果依据**：`docs/experiment/thesis-final-v1-results.md`（84-run，81/84 DONE，四组策略消融与机制增量分析）

---

### 第 8 章　总结与展望

> 篇幅建议：5–8 页。最后写。

8.1　论文工作总结
8.2　主要贡献
8.3　不足与局限
8.4　未来工作展望

---

## 图清单

| 图号 | 所在章 | 标题 | 源文件 |
|------|--------|------|--------|
| 图 3-1 | 第 3 章 | 问题-方案对照：固定流水线 vs 本系统 | `paper/figures/problem-solution-comparison.drawio.svg` |
| 图 4-1 | 第 4 章 | 系统五层分层架构 | `paper/figures/system-architecture.drawio.svg` |
| 图 4-2 | 第 4 章 | ProteinToolKG 局部可视化 | `paper/figures/protein-toolkg-local-view.drawio.svg` |
| 图 4-3 | 第 4 章 | FSM 状态转移图 | `paper/figures/fsm-state-transition.drawio.svg` |
| 图 4-4 | 第 4 章 | HITL 触发条件与决策逻辑 | `paper/figures/hitl-decision-conditions.drawio.png` |
| 图 4-5 | 第 4 章 | 六阶段 de novo 工作流与恢复感知控制 | `paper/figures/workflow-flowchart.drawio.svg` |
| 图 4-6 | 第 4 章 | CEBRA-WP 算法闭环 | `paper/figures/algorithm-loop.drawio.svg` |
| 图 4-7 | 第 4 章 | 核心数据契约 UML | `paper/figures/uml-contracts.drawio.svg` |
| 图 4-8 | 第 4 章 | t1 Trp-cage-like 短肽任务实例走查 | `paper/figures/t1-trpcage-instance-walkthrough.drawio.svg` |
| 图 5-1 | 第 5 章 | 运行时执行序列 | `paper/figures/runtime-sequence.drawio.svg` |
| 图 5-2 | 第 5 章 | 工作流泳道式模块协作 | `paper/figures/workflow-swimlane.drawio.svg` |
| 图 7-1 | 第 7 章 | 实验设计框架 | `paper/figures/experiment-design-framework.drawio.svg` |
| 图 7-2 | 第 7 章 | 恢复路径对比 | `paper/figures/recovery-path-comparison-timeline.drawio.svg` |

> 第 6 章当前使用表 6-1 和 FIG-SV 证据编号，不单独设置正文图号；FIG-SV-01~18 可在附录或证据索引中引用。当前 `paper/figures/` 中没有“四组消融主实验结果”的独立图像，主结果以表 7-1 至表 7-3 呈现。

---

## 表清单

| 表号 | 所在章 | 标题 | 数据来源 |
|------|--------|------|----------|
| 表 3-1 | 第 3 章 | 系统功能需求与验证点映射 | `test-case-table.md` |
| 表 4-1 | 第 4 章 | FSM 状态转移规则 | `AGENT_CONTRACT.md`、`architecture.md` |
| 表 6-1 | 第 6 章 | 测试用例汇总（TC-S01~S13） | `test-case-table.md` |
| 表 7-1 | 第 7 章 | 四组消融主实验结果 | `thesis-final-v1-001` 84-run 矩阵 |
| 表 7-2 | 第 7 章 | 实验任务集 | `final-task-set-design.md` |
| 表 7-3 | 第 7 章 | 指标体系定义 | `final-thesis-experiment-design.md` §7 |
| 表 7-4 | 第 7 章 | FAILED run 典型案例分析 | `thesis-final-v1-results.md` §4 |

---

## 写作状态

| 章 | 草稿 | LaTeX | 可开始写 |
|----|------|-------|----------|
| 第 1 章 绪论 | — | 占位符 | 系统与实验章节定型后写 |
| 第 2 章 相关技术 | — | 占位符 | 可在第 3-7 章后补写 |
| **第 3 章 需求分析** | 🟡 需从 Ch3 草稿拆分 | 待创建 | ✅ 立即可 |
| **第 4 章 总体设计** | 🟡 需从 Ch3 草稿拆分 | 待创建 | ✅ 立即可 |
| **第 5 章 系统实现** | ✅ Markdown 初稿完成 | 待创建 | 待转 LaTeX |
| **第 6 章 测试与验证** | ✅ Markdown 初稿完成 | 待创建 | 待转 LaTeX |
| **第 7 章 策略实验** | ✅ Markdown 初稿完成 | 待创建 | 待转 LaTeX |
| 第 8 章 总结展望 | — | 占位符 | 最后写 |

> **当前重点**：第 5、6、7 章已完成 Markdown 初稿；下一步应拆分第 3/4 章，并同步 `final.tex` 为 8 章结构。
> **第三章草稿**（`sections/03-system-requirements-and-design.md`，约 32KB）在拆分前可作为第 3+4 章的共享素材。
