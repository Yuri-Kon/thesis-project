# Planner 大模型能力要求与专用训练方案
<!-- SID:algollm.llm.training_plan -->

## 目标

一个核心问题: 当前系统使用外部大模型 API 生成 Plan, 后续是否应训练一个自有 Planner 模型, 以实现更快, 更稳, 更准的规划能力.

## 现状与问题定义

当前系统已经具备执行闭环(retry -> patch -> replan)与 FSM / HITL 控制, 但 Planner 仍已外部模型调用为主.

实践中的主要瓶颈是:

1. 响应时延与调用成本受外部API影响
1. 结构化输出稳定性不足时, 会放大执行层失败
1. 对结构特有规则(ToolKG, Patch 最小化, Replan 保留前缀)的贴合度依赖 prompt 工程, 稳定性有限

## Planner 模型的能力要求

Planner 模型必须具备以下五类能力:

1. 约束满足能力: 严格满足工具可用性, I/O 闭包, 安全与成本约束
1. 结构生成能力: 稳定输出 `Plan/PlanPatch/Replan` 的合法结构
1. 修复规划能力: 在失败上下文下优先生成最小 patch, 必要时 `suffix replan`
1. 候选决策能力: 可输出 Top-K 候选, 风险/成本分解与默认建议
1. 稳定复现能力: 同输入多次生成的一致性高, 便于审计与HITL复核

## 是否自训练: 可行性判断

1. 不建议从零训练通用大模型, 成本极高且不符合项目目标
1. 建议训练 Planner 专用模型, (7B ~ 14B), 并保留外部模型兜底
1. 技术路线已 SFT/QLoRA + 偏好优化(DPO) + 规则校验器为主, 优先提升可执行性与稳定性, 而非追求通用能力上限.

## 训练方案

1. 数据构建: 从任务日志与事件流提取 "任务-约束-工具快照-候选-执行结果-人工决策"
1. 样本规模建议:
   1. SFT样本 2万~5万条(Plan为主, Patch/Replan次之)
   1. 偏好对 5000~15000 对(基于执行成功率与人工选择)
1. 训练阶段:
   1. 第一阶段 SFT: 学习结构化规划与约束遵循
   1. 第二阶段 DPO: 强化 "成功率高, 风险低, 改动小" 的候选偏好
   1. 第三阶段 蒸馏与量化: 降低时延, 支持在线部署
1. 推理阶段: 采用 `constrained decoding + schema verifier + rerank`, 确保 "先合法, 再最优"

## 验收指标

1. Schema 合法率 >= 99.5%
1. 可执行 Plan 率 >= 95%
1. 首轮执行成功率 提升(相对于外部基线至少+10%)
1. Patch 最小性命中率 >= 80%
1. suffix replan 前缀保持率 = 100%
1. Planner 平均响应时延 降低 30% 以上
1. 人工介入率 与 失败后恢复成功率 同时优化

## 部署建议

采用双路架构:

1. 默认走自研 Planner
1. 当置信度低, 风险高或连续失败时自动回退外部强模型
1. 所有决策而保留可追溯性解释, 保证 FSM/HITL 审计一致性

## 参考文献

- https://arxiv.org/abs/2210.03629
- https://arxiv.org/abs/2302.04761
- https://arxiv.org/abs/2305.15334
- https://arxiv.org/abs/2306.05301
- https://arxiv.org/abs/2307.16789
- https://icml.cc/virtual/2025/poster/46593
- https://aclanthology.org/2025.findings-emnlp.1099/
- https://arxiv.org/abs/2305.04091
- https://arxiv.org/abs/2305.10601
- https://arxiv.org/abs/2203.11171
- https://arxiv.org/abs/2106.09685
- https://arxiv.org/abs/2305.14314
- https://arxiv.org/abs/2305.18290
- https://arxiv.org/abs/2203.15556
- https://arxiv.org/abs/2309.06180
- https://arxiv.org/abs/2211.17192
- https://arxiv.org/abs/2404.07972
- https://pubmed.ncbi.nlm.nih.gov/36108050/
- https://pubmed.ncbi.nlm.nih.gov/36927031/
- https://www.nature.com/articles/s41586-023-06415-8
- https://www.nature.com/articles/s41586-021-03819-2
- https://www.nature.com/articles/s41586-024-07487-w
