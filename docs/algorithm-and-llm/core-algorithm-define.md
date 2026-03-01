# 核心算法定义
<!-- SID:algollm.core.algorithm_define -->

## 核心算法是什么

一个 "ToolKG 约束下的候选规则-执行-修复闭环"

1. Initial Planning 生成候选Plan
1. 执行中按照 `retry -> patch -> replan` 进行恢复
1. 用 FSM + PendingAction 把关键节点转化为可审计的 HITL 决策点

## 结合当前实现, 现在已经实现的

1. 已有核心闭环骨架:\
   `StepRunner` 已有静态重试(`src/workflow/step_runner.py`), `PatchRunner` 做局部补丁(`src/workflow/patch_runner.py`), `PlanRunner` 做 replan 与状态推进(`src/workflow/plan_runner.py`)
1. Planner 当前偏向 "最小可用":\
   默认单步, de novo 是两步模板(`tests/unit/test_planner_agent.py`), patch/replan 主要是 replace_step(`src/agents/planner.py`)
1. 关键差距在 "候选层":\
   设计要求 Top-K, score_breakdown, risk/cost gate; 当前 `PendingActionCandidate` 只有最小字段(`src/models/contracts.py`), 距离设计的 candidate scoring/selection 还有距离(`~/文档/thesis/thesis-project.design/docs/design/core-algorithm-spec.md`)

## 该算法的主流应用是什么

1. 通用 AI Agent: 代码代理, 运维自动化, 企业流程自动化(本质是 "规划 + 工具调用 + 失败恢复 + 人类审批")
1. 科研工作流: 化学 / 生物多工具编排, 尤其需要审计和人类兜底的场景
1. 蛋白设计场景: 序列生成/逆折叠/结构预测组合流水线

## 该算法的理论模型

可表述为 "约束多目标优化 + 有限状态控制"

1. 在工具图上搜索可执行候选(c), 满足 I/O 闭包与安全约束
1. 对候选做多目标打分, 并设 gate 决定自动执行或 HITL
1. 执行期按照分层恢复策略: 局部修复(path) 优先, 全局修复(replan) 兜底.

## 当前研究现状与改进方向

1. 现状: LLM Agent 的 "思考 + 行动" 范式已经成熟(ReAct/Toolformer/Reflexion), 但真实环境稳定性仍明显不足(如 OSWorld 基准). 蛋白质方向模型能力很强(ProteinMPNN, ESMFold, RFdifussion, AlphaFold3), 但 "系统级闭环优化+可审计决策" 仍然是短板.
1. 项目的下一步该补充的应该是 "算法闭环完整性": 先补充 Top-K 候选与打分门控, 再补充 HITL 前端, 再补充实验评估框架
1. 推荐优先级:
   - P0: 完成 Week6 前端
   - P1: 实现 CandidateSetOutput(Top-k, score_breakdown, risk/cost 阈值门控)
   - P2: 把 patch/replan 从 "最小替换" 升级为 "参数修补 -> 工具替换 -> 结构调整" 的分层策略
   - P3: 引入可复现实验基准(成功率, 平均 replan 次数, 人工介入率, 端到端时延)

## 参考资料

- ReAct: https://openreview.net/forum?id=WE_vluYUL-X
- Toolformer: https://arxiv.org/abs/2302.04761
- Reflexion: https://arxiv.org/abs/2303.11366
- LLM Multi-Agent Survey: https://arxiv.org/abs/2402.01680
- Recent Multi-Agent Survey (2025): https://arxiv.org/abs/2503.21460
- OSWorld benchmark: https://arxiv.org/abs/2404.07972
- ProteinMPNN: https://pubmed.ncbi.nlm.nih.gov/36108050/
- ESMFold: https://pubmed.ncbi.nlm.nih.gov/36927031/
- RFdiffusion: https://www.nature.com/articles/s41586-023-06415-8
- AlphaFold 3: https://www.nature.com/articles/s41586-024-07487-w
- AlphaFold2 vs ESMFold (2025): https://pubmed.ncbi.nlm.nih.gov/39916697/
