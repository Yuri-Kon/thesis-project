# Release Candidate Draft (`v0.3.0-rc1`)

## 变更摘要

- 已具备训练基线、离线评估、双路回退、端到端演示、纵向实验与治理复核的基础产物。

## 兼容性说明

- 不新增 FSM 状态。
- 不改变 HITL 决策所有权。
- 发布默认开启外部回退兜底，可用紧急熔断环境变量切回外部基线。

## 评估摘要（来自 #149）

- release_blocked: `yes`
- blocked_metrics: `patch_minimality_hit_rate=-, suffix_replan_prefix_preservation_rate=-`

## 回退策略（来自 #150）

- force_external_only: `False`
- circuit_breaker_env: `PLANNER_FORCE_EXTERNAL_FALLBACK`

## 验证证据与已知问题（来自 #151 与当前实验）

- demo_scenarios: `six_stage_hitl_replay, tool_fallback_remote_to_local`
- demo_checks: `{'audit_chain_pendingaction_decision_eventlog': True, 'tool_fallback_switch_recorded': True, 'e2e_flow_reaches_done': True}`
- known_issue: `#172` 横向对比延期，`#174` 当前仅能形成中期版草稿。
- known_issue: RC Gate-B 仍被 patch/suffix_replan 指标空值阻断。
- known_issue: 主实验 WAITING 链指标为 0，治理展示需依赖标准回放样例。

## 发布建议

- 维持候选版本：`v0.3.0-rc1`
- 当前只建议作为答辩演示与论文附录证据包，不建议进入正式 release 流程。
