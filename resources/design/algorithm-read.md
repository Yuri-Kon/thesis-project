# 核心算法论文阅读综述（对齐系统设计与规划）

## 1. 阅读目标与范围

本文基于 5 篇代表性工作，目标不是做通用综述，而是回答一个工程问题：
在当前 thesis-project 的约束下，如何把“候选规则生成-执行-修复-人工决策”闭环做得更稳定、可审计、可复现。

覆盖论文：

- Toolformer
- ReAct
- Reflexion
- LLM Multi-Agent Survey
- OSWorld

______________________________________________________________________

## 2. 单篇论文关键结论（面向落地）

| 论文               | 核心贡献                                     | 对本系统可迁移点                                                      | 直接迁移的限制                                       |
| :----------------- | :------------------------------------------- | :-------------------------------------------------------------------- | :--------------------------------------------------- |
| Toolformer         | 自监督学习工具调用时机与参数                 | 证明“工具调用能力可被训练内化”；可用于构建候选过滤信号                | 主要是单工具调用范式，对多步工具链与跨步约束支持不足 |
| ReAct              | Thought/Action 交替，边推理边行动            | 适合 Planner 生成可解释的步骤级理由；有助于失败定位                   | 若无强约束，易出现冗长推理与重复动作                 |
| Reflexion          | 基于文本反馈的回合式修复                     | 与 `retry -> patch -> replan` 恢复链路高度契合，适合做 patch 反馈学习 | 依赖 evaluator 质量；反馈噪声会放大误修复            |
| Multi-Agent Survey | 多智能体在角色分工、通信、演化上的系统化总结 | 支持 Planner/Executor/Safety/Summarizer 分工合理性                    | 多智能体通信成本和一致性治理复杂                     |
| OSWorld            | 真实环境执行评估基准                         | 强调“执行成功率”与“可恢复性”优先于离线文本指标                        | 基准复杂，复现实验成本高                             |

结论：

- 对本项目最关键的不是“更强推理文本”，而是“更可靠的执行闭环 + 可审计决策路径”。

______________________________________________________________________

## 3. 与现有系统契约的映射

### 3.1 Planner 候选层（对应 Toolformer/ReAct）

系统设计已要求 Planner 输出候选集合（Top-K）与结构化字段：

- `candidate_id`
- `structured_payload`
- `score_breakdown`
- `risk_level`
- `cost_estimate`
- `explanation`

这与论文启示一致：

- Toolformer 证明“候选可通过执行信号筛优”；
- ReAct 证明“候选需要可解释轨迹，而不是只给最终答案”。

### 3.2 执行与恢复层（对应 Reflexion/OSWorld）

系统主恢复链路是：

- `retry -> patch -> replan`

这与 Reflexion 的“失败反馈驱动修复”一致，但系统实现是更强约束版本：

- Patch 优先局部最小变更；
- Replan 用于策略级调整；
- 失败处理必须走 FSM 合法状态迁移。

### 3.3 HITL 与审计层（对应 OSWorld 的执行评估导向）

系统已定义等待态和决策对象：

- `WAITING_PLAN_CONFIRM`
- `WAITING_PATCH_CONFIRM`
- `WAITING_REPLAN_CONFIRM`
- `PendingAction` + `Decision`

这保证关键分叉点可审查、可回放、可追责，不依赖隐式模型行为。

### 3.4 与 de novo 六阶段工作流的关系

论文结论与六阶段分层并不冲突，而是补强控制层：

- 论文给出“如何生成/修复候选”；
- 六阶段定义“候选在生物设计流程中的能力位置”；
- Patch/Replan 是贯穿所有阶段的控制层，不是独立单步。

______________________________________________________________________

## 4. 系统现状与差距（截至 2026-03-01）

| 维度       | 现状                                                     | 差距                                                          |
| :--------- | :------------------------------------------------------- | :------------------------------------------------------------ |
| 闭环骨架   | 已有 `StepRunner/PatchRunner/PlanRunner`，恢复主链路存在 | 候选层仍偏“最小可用”，Top-K 与细粒度打分不足                  |
| 结构化契约 | Plan/StepResult/PendingAction/FSM 已定义                 | `score_breakdown` 与风险/成本门控未形成稳定策略               |
| HITL       | WAITING\_\* 与 Decision 路径完整                         | 前端交互和审查效率仍是系统瓶颈                                |
| 工具约束   | ToolKG 已成为事实来源                                    | 候选选择对 KG 事实利用深度不足（特别是成本/风险维度）         |
| 评估体系   | 有 Demo 与最小链路验证                                   | 缺少统一 benchmark：成功率、replan 率、人工介入率、端到端时延 |

______________________________________________________________________

## 5. 调整后的算法结构（建议版本）

### 5.1 闭环主流程

1. Tool Retrieval（KG 约束过滤）
1. Candidate Generation（生成 Plan/Patch/Replan Top-K）
1. Candidate Scoring（成功概率、风险、成本、多目标加权）
1. HITL Gate（按阈值自动执行或进入 WAITING\_\*）
1. Execution（按步骤执行并记录 StepResult）
1. Recovery（按 `retry -> patch -> replan` 分层恢复）
1. Summarization（输出可追溯报告）

### 5.2 核心优化点

- 从“单候选”升级为“候选集决策”：默认至少 K=3。
- Patch 策略分层化：
  - 参数级修补
  - 工具级替换
  - 结构级调整
- Replan 默认 `suffix_replan`：优先保留成功前缀，降低重算成本。
- 解释字段与 KG 事实绑定：避免空泛自然语言解释。

### 5.3 理论抽象（工程可解释）

可将系统视为“约束多目标优化 + 有限状态控制”：

`best_candidate = argmax Score(candidate | constraints, context)`

其中约束来自：

- ToolKG 可用性与 I/O 闭包
- 安全/成本策略
- 当前执行上下文（失败类型、重试历史、已成功前缀）

______________________________________________________________________

## 6. 与已有规划（Week 3-9）的衔接

已完成或已立项方向：

- Week 3：Planner LLM Provider 可插拔、恢复与失败治理
- Week 4-5：KG-only 规划与最小 de novo 闭环
- Week 7：FSM/HITL 可视化与可演示路径
- Week 8：KG 扩展与 Planner 解释增强
- Week 9：执行后端抽象与可复现性增强

在此基础上的下一步优先级建议：

- P0：补齐候选层（Top-K + score_breakdown + risk/cost gate）
- P1：补齐评估层（统一 benchmark 与运行清单）
- P2：强化 patch/replan 的分层策略与可解释性
- P3：将论文结论沉淀为可复现实验报告模板

______________________________________________________________________

## 7. 验收指标（建议）

算法层最低验收口径：

- Plan schema 合法率
- 候选可执行率
- 首轮执行成功率
- 平均 patch 次数 / replan 次数
- 人工介入率
- 端到端时延
- 决策可追溯完整率（PendingAction -> Decision -> EventLog）

建议将上述指标写入统一实验表，按“基线 vs 改进策略”做 A/B 记录。

______________________________________________________________________

## 8. 风险与边界

- 不应把论文中的通用智能体结论直接等价为蛋白设计可用能力。
- 不应引入绕过 FSM/HITL 的“隐式自动决策捷径”。
- 不应在缺少结构化验证器时过早放大 LLM 自由度。

______________________________________________________________________

## 9. 参考文献

- ReAct: https://openreview.net/forum?id=WE_vluYUL-X
- Toolformer: https://arxiv.org/abs/2302.04761
- Reflexion: https://arxiv.org/abs/2303.11366
- LLM Multi-Agent Survey: https://arxiv.org/abs/2402.01680
- Recent Multi-Agent Survey (2025): https://arxiv.org/abs/2503.21460
- OSWorld benchmark: https://arxiv.org/abs/2404.07972
