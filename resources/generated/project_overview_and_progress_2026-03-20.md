# 中期论文准备：项目概览与当前进度判断

- 生成时间：`2026-03-20`
- 依据来源：
  - 代码仓库：`README.md`、`AGENT_CONTRACT.md`
  - 设计文档：`../thesis-project.design/docs/design/*.md`
  - 实验与验证文档：`reports/`、`docs/algorithm-and-llm/`、`examples/`
  - GitHub：`gh issue list`、`gh pr list`、`gh issue view`

## 1. 项目一句话定位

本项目是一个面向蛋白质设计任务的 LLM 驱动多 Agent 系统：以显式 FSM 为控制核心，以 Planner/Executor/Safety/Summarizer 四类 Agent 为职责边界，以 ToolKG 和工具适配层为执行基础，支持 HITL 决策、失败恢复、可审计日志与实验评估。

## 2. 可用于论文的系统主线

### 2.1 架构主线

- 输入层：自然语言任务/API 请求进入统一任务对象。
- 智能规划层：Planner 基于 ToolKG 生成 `Plan / PlanPatch / Replan`。
- 执行层：Executor 调用工具适配器，负责重试、patch、replan 触发。
- 安全与汇总层：Safety 做风险判定，Summarizer 输出报告与结果摘要。
- 资源层：ToolKG、日志、快照、输出产物统一沉淀到本地资源目录。

### 2.2 方法主线

- 系统不是“单次 LLM + 工具调用”。
- 系统核心是“候选集决策 + 显式状态机 + HITL + 分层恢复”。
- 论文方法亮点可围绕四点展开：
  - 显式 FSM 与 WAITING 语义；
  - Top-K 候选与门禁决策；
  - `retry -> patch -> replan` 分层恢复；
  - 审计链、回放与证据沉淀。

### 2.3 工作流主线

- de novo 设计被拆成六阶段能力层：
  - S1 序列探索
  - S2 结构映射
  - S3 质量门禁
  - S4 结构条件精修
  - S5 多目标打分
  - S6 Patch/Replan 控制层
- 该六阶段设计支持回环，而不是固定直线流水线。

## 3. 目前已经比较扎实的部分

### 3.1 系统能力

- FSM / HITL 主链已经稳定，且有设计文档、测试、回放样例三重证据。
- Planner Top-K、候选校验、门禁、默认建议机制已经实现。
- S1-S6 六阶段中的关键能力均已有落地 issue 与合并 PR。
- 双路规划回退、治理复核、全流程展示手册已经补齐。

### 3.2 工程证据

- `reports/full_flow_validation_report.md` 可支撑“核心功能链路已打通”。
- `reports/usability_validation_report.md` 可支撑“API、真实 provider、远端 REST 工具链可用性”。
- `reports/llm_provider_validation_report.md` 可支撑“多 provider 真实可用”。
- `reports/showcase/full_flow_showcase_guide.md` 可支撑“答辩演示路径”。

### 3.3 近期交付节奏

- `gh pr list` 显示 PR `#181` 到 `#205` 已连续合并，集中完成了：
  - 六阶段能力补齐
  - 纵向实验执行管线
  - 离线评估与治理复核
  - 中期报告草稿包
  - Requirement-2 工具接入

## 4. GitHub 进度判断

### 4.1 W11/W12 近期 issue 总览

`gh issue list` 结果显示，`#144` 之后的近期 issue 共 `25` 个：

- 已关闭：`20`
- 仍打开：`5`

当前打开 issue：

- `#152` `W12-Docs-2: 三周成果报告与下一阶段计划`
- `#172` `W12-Experiment-3: 横向对比 E0/E1/E2`
- `#174` `W12-Experiment-5: 中期报告实验章节与图表证据包定稿`
- `#199` `W12-Experiment-3b: 横向对比平台接入与复现模板`
- `#200` `W12-Req2-Tools-3: 多工具接入统一验收与门禁自动化`

其中仍打开的 `priority:p0` issue 为：

- `#152`
- `#174`
- `#200`

### 4.2 已完成但对论文最关键的 issue

- `#171` 纵向实验：已关闭。
- `#173` 治理指标复核：已关闭，Project 状态为 `Done`。
- `#197` P0 结构预测扩展与 QC 接入：已关闭，Project 状态为 `Done`。
- `#198` MMseqs2 / BLASTP / DSSP 接入：已关闭，Project 状态为 `Done`。

### 4.3 当前卡点

- `#172` 横向对比仍为 `OPEN`，Project 状态是 `Todo`。
- `#174` 中期实验章节定稿仍为 `OPEN`，Project 状态是 `Todo`。
- `#152` 三周成果收官文档仍为 `OPEN`，Project 状态是 `Todo`。
- `#200` 多工具统一验收与门禁自动化仍为 `OPEN`，Project 状态是 `Todo`。

### 4.4 一个重要异常

- `#149` 离线评估 issue 在 GitHub 上是 `CLOSED`，但 Project 状态仍为 `In Progress`。
- 结合本地 `reports/in-progress-issue-recheck-2026-03-16.md` 与 `reports/w12-issue-152/release_candidate_draft.md`，更合理的判断是：
  - 评估脚本与报告已经完成；
  - 但离线门禁结论仍是阻断发布；
  - 因而“工程交付完成”和“发布标准达标”是两件事。

## 5. 当前阶段的总体判断

### 5.1 可以明确说“已完成”的

- 系统架构与核心契约已经稳定。
- FSM/HITL/恢复控制链已具备完整实现与回放证据。
- 六阶段方法主体已经实现，不再停留在概念设计。
- 中期答辩所需的展示链路、验证报告、治理证据基本具备。

### 5.2 可以说“基本完成但仍需收尾”的

- 中期文档打包与图表证据整理。
- Requirement-2 的统一验收与自动化门禁。
- 项目板状态与 issue 实际进度的一致性清理。

### 5.3 不能夸大为“已完成”的

- 横向对比 E0/E1/E2 尚未完成。
- 离线门禁尚未达到正式 release 标准。
- 中期实验章节的正式定稿仍缺横向部分与最终统一图表。

## 6. 对中期论文写作的建议表述

- 可以把项目定位为“核心系统与工程证据已形成闭环，实验比较部分仍处于阶段性完成”。
- 不宜把当前版本写成“方法效果已经被完整证明”。
- 更稳妥的写法是：
  - 已完成系统实现、控制机制与审计能力验证；
  - 已完成纵向实验框架与治理复核；
  - 横向对比与最终发布门禁仍在后续阶段推进。

## 7. 最适合论文主线的叙述框架

1. 研究问题：现有 LLM Agent 缺乏显式控制、恢复和治理能力。
2. 方法设计：提出基于 FSM + HITL + 六阶段能力分层的多 Agent 系统。
3. 工程实现：通过 ToolKG、适配器、日志、快照和 API 落地。
4. 验证证据：功能验证、可用性验证、治理复核、实验设计。
5. 阶段结论：系统工程闭环已建立，实验对比仍在继续完善。
