# 中期答辩 PPT 简明指南

本目录用于制作中期答辩 PPT。当前版本按你已经确定的 `14` 页结构整理，只保留每一页需要放什么内容、配什么图、讲什么重点。

## 总体要求

- 总时长控制在 `7` 分钟以内。
- 每页只保留 `3~5` 条要点，不堆长段文字。
- 实验部分统一口径：
  - `实验案例一` 是机制回放，不是统计结果页。
  - `实验案例二` 是答辩补充机制验证，不宣称最终生物效果最优。

## 页面结构

### 第 1 页：标题

- 内容：
  - 论文题目
  - 姓名、学号、学院、导师
  - 中期答辩
- 图示：
  - 可不放图
  - 如需背景图，可弱化使用 `assets/system-architecture-overview.svg`

### 第 2 页：目录

- 内容：
  - 预定计划的执行情况
  - 已完成工作
  - 实验案例
  - 后期计划
  - 困难与按时完成的可能性
- 图示：
  - 不建议放图

### 第 3 页：预定计划的执行情况

- 内容：
  - 对应“预定执行计划与当前推进情况”
  - 建议做成时间线
- 图示：
  - 自制时间线图

### 第 4 页：已完成工作：系统骨架与角色分工

- 文案：
  - 已建立统一的任务运行框架，由 `WorkflowRuntime` 负责组织整个流程
  - 已完成 `Planner`、`Executor`、`Safety`、`Summarizer` 四类 Agent 的职责拆分
  - 已把任务执行过程拆成明确阶段，而不是依赖模型自由推进
  - 已形成从任务输入、流程编排到结果汇总的基本闭环
  - 已为后续人工确认、失败恢复和实验验证预留统一接口
- 图示：
  - `assets/split/multi-agent-core-part-1-core-orchestration.svg`

### 第 5 页：已完成工作：关键运行机制

- 文案：
  - 已完成方案生成、工具选择和执行结果返回的主链
  - 已完成关键节点的等待确认机制，系统可以暂停并接收人工决策
  - 已完成失败后的分层处理逻辑，包括 `retry -> patch -> replan`
  - 已完成工具切换、局部修补和重新规划之间的切换逻辑
  - 已完成执行过程中的事件记录，支持后续回放和分析
- 图示：
  - `assets/split/multi-agent-core-part-2-planning-execution.svg`

### 第 6 页：已完成工作：工程证据沉淀

- 文案：
  - 已形成事件日志 `EventLog`
  - 已形成任务快照 `TaskSnapshot`
  - 已形成最终结果对象 `DesignResult`
  - 已具备可回放、可追溯、可解释的证据基础
- 图示：
  - `assets/split/multi-agent-core-part-4-artifacts-output.svg`

### 第 7 页：实验案例一：人工确认与失败案例回放

- 文案：
  - 在关键节点，系统会显式进入 `WAITING_*` 状态，而不是隐式继续执行
  - 人工决策会写入 `PendingAction -> Decision -> EventLog` 证据链
  - 遇到失败时，系统优先尝试局部修补，必要时再升级为 `replan`
  - 在收到决策并完成恢复后，任务能够继续执行并收敛到终态
- 图示：
  - `assets/recovery-hitl-overview.pdf`

### 第 8 页：实验案例一：人工确认与失败案例回放

- 内容：
  - 展示人工决策页面
- 图示：
  - `asserts/hitl-decision.pdf`

### 第 9 页：实验案例一：人工确认与失败案例回放

- 内容：
  - 展示事件时间线视图
- 图示：
  - `asserts/timeline-split.pdf`

### 第 10 页：实验案例二：中期机制验证基准结果

- 文案：
  - 共 `17` 个可复现场景，覆盖 `5` 个实验家族
  - 家族层面全部通过：Execution & Summary `3/3`，Gate `2/2`，HITL & Audit `4/4`，Planner Routing `3/3`，Recovery `5/5`
  - 证据文件完整率 `100%`：`event_log 6/6`，`snapshot 2/2`，`report 3/3`
- 图示：
  - `assets/benchmark/family_summary.svg`
- 图例口径：
  - `Scenario Count` 表示场景数量
  - `Pass Rate` 表示通过比例
  - `Evidence Complete Rate` 表示证据完整比例

### 第 11 页：实验案例二：中期机制验证基准结果

- 文案：
  - 与第 10 页保持一致
- 图示：
  - `assets/benchmark/artifact_support.svg`
- 图例口径：
  - `Expected Count` 表示理论应产出数量
  - `Present Count` 表示实际落盘数量
  - `Present Rate` 表示证据落盘比例

### 第 12 页：后期计划

- 文案：
  - `3月21日-3月31日`：补齐横向实验与统一评估
  - 完成 `E0/E1/E2` 横向对比
  - 统一纵向实验、治理复核和图表口径
  - `4月1日-4月22日`：推进外部模型训练与系统收口
  - 启动外部模型专用训练
  - 完成训练后评估
  - 完成多工具统一验收与门禁完善
  - `4月22日-4月30日`：进行前端页面的完善
  - 对齐后台接口与前端显示
  - 直观展示程序设计结果
  - `5月1日-5月30日`：完成论文与答辩材料定稿
  - 完善实验章节、问题分析和结论
  - 统一图表、术语和版式
  - 完成最终论文和答辩展示材料
- 图示：
  - 自制时间线或路线图

### 第 13 页：困难与按时完成的可能性

- 文案：
  - 存在的困难：横向对比实验尚未完成
  - 统一评估口径和图表结果仍需继续收口
  - 外部模型专用训练尚未启动
  - 多工具真实运行受远程平台和资源条件影响
  - 工程材料向论文表达的转写仍需继续整理
  - 可行性与进度：系统主体、关键控制机制、主要运行链路已经基本完成
  - 剩余工作边界清楚，主要属于实验补齐、评估收口和论文整理
  - 总体判断：具备按时完成论文与参加答辩的现实基础
- 图示：
  - 可不放图
  - 或放简化风险/可行性对照框

### 第 14 页：结束页

- 内容：
  - 感谢各位老师聆听
  - 请老师批评指正
- 图示：
  - 可不放图

## 当前最重要的图示文件

- `assets/split/multi-agent-core-part-1-core-orchestration.svg`
- `assets/split/multi-agent-core-part-2-planning-execution.svg`
- `assets/split/multi-agent-core-part-4-artifacts-output.svg`
- `assets/recovery-hitl-overview.pdf`
- `assets/benchmark/family_summary.svg`
- `assets/benchmark/artifact_support.svg`

## 使用提醒

- 第 `10` 页和第 `11` 页统一说法：
  - 这是答辩补充机制验证
  - 它验证的是系统机制闭环
  - 它不等于最终生物效果评价
- 第 `8` 页和第 `9` 页是截图页，讲述时重点解释图中关键区域，不要逐项读界面文字。
