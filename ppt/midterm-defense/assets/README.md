# 中期答辩图示素材说明

本目录收录当前阶段可直接复用的图示文件，主要服务于中期答辩 PPT 制作。

当前阶段策略：

- 先复用已有结构图、流程图和机制图。
- 实验主结果改用新的 `中期机制验证基准` 图表。
- 界面截图、实验流程截图和补充截图后续再补。

## 素材与推荐用途

### system-architecture-overview

- 推荐页面：
  - 封面弱化背景
  - 已完成工作
- 用途：
  - 展示系统分层架构与整体组织关系

### component-views

- 推荐页面：
  - 已完成工作
- 用途：
  - 展示系统组件与模块之间的关系

### multi-agent-core

- 推荐页面：
  - 已完成工作
- 用途：
  - 展示 Planner / Executor / Safety / Summarizer 的协作结构


### split/multi-agent-core-part-1-core-orchestration

- 推荐页面：
  - 已完成工作（一）：系统骨架
  - 已完成工作（二）：关键机制
- 用途：
  - 保留 `WorkflowRuntime + Planner / Executor / Safety / Summarizer` 主链，是讲系统骨架时最值得放的一张子图

### split/multi-agent-core-part-2-planning-execution

- 推荐页面：
  - 已完成工作（二）：关键运行机制
- 用途：
  - 聚焦 `PlannerAgent / ExecutorAgent / ToolKG / ToolAdapter / Plan / StepResult`，适合讲“生成方案并调用工具执行”这条主链

### split/multi-agent-core-part-3-hitl-audit

- 推荐页面：
  - 实验案例一
  - 已完成工作（三）：工程证据与可展示能力
- 用途：
  - 聚焦 `PendingAction / Decision / EventLog`，适合讲等待态、人工确认和审计回流

### split/multi-agent-core-part-4-artifacts-output

- 推荐页面：
  - 已完成工作（三）：工程证据与可展示能力
  - 实验案例二
- 用途：
  - 聚焦 `EventLog / TaskSnapshot / DesignResult`，适合讲日志、快照和结果文件如何沉淀为可追溯证据

### recovery-hitl-overview

- 推荐页面：
  - 实验案例一
- 用途：
  - 展示 HITL 与恢复控制在同一执行链中的位置
- 当前可用格式：
  - `pdf`

### total-sequence

- 推荐页面：
  - 实验案例一
- 用途：
  - 展示总体执行流程和等待态闭环

### single-step-sequence

- 推荐页面：
  - 实验案例一
  - 实验案例二
- 用途：
  - 展示单步失败后的 Patch / Replan 恢复路径

### core-algorithm-overview

- 推荐页面：
  - 实验案例二
- 用途：
  - 展示实验相关机制与方法路径

## benchmark/ 目录中的新增图表

### benchmark/family_summary.svg

- 推荐页面：
  - 实验案例二主图
- 用途：
  - 展示 5 个实验家族的场景覆盖数、通过率和证据完整性
- 适合讲法：
  - 强调系统已经形成覆盖 Gate、HITL & Audit、Recovery、Planner Routing、Execution & Summary 的稳定机制验证集

### benchmark/capability_coverage.svg

- 推荐页面：
  - 实验案例二补充图
- 用途：
  - 展示关键机制能力的覆盖情况，例如 event_audit、patch_recovery、planner_routing、replan_escalation、result_summarization
- 适合讲法：
  - 强调不是只有单一 demo，而是多个关键能力都被独立验证

### benchmark/artifact_support.svg

- 推荐页面：
  - 实验案例二右下角小图
- 用途：
  - 展示 event_log、snapshot、report 等证据文件的落盘完整率
- 适合讲法：
  - 强调不只是“测试通过”，而且证据链完整可追溯

### benchmark/midterm_mechanism_benchmark_report.md

- 用途：
  - 作为写 PPT 实验页文案和答辩备注时的参考依据
- 不建议：
  - 不要直接截图整页放进 PPT

## 使用建议

- 优先使用 `svg` 版本放入 PPT，以便后续无损缩放和再编辑。
- 对于仅提供 `pdf` 的素材，可直接使用 `pdf` 版本。
- 不建议在同一页放超过 1 张复杂结构图。
- 实验结果页建议采用：1 张主图 + 1 张补充小图 的组合，而不是把所有图一次堆满。
