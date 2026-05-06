# Release Candidate Draft (`v0.3.0-rc1`)

> W16 closeout note (`2026-04-26`): 本文件是旧 W12 release draft，保留作历史候选版本记录。当前 `#152` 正式收束口径见 `reports/w12-issue-152/historical_backlog_closeout.md`；W16 证据边界见 `docs/evidence/issue-225/write-back-closeout.md`。

## 变更摘要

- 已具备训练基线、离线评估、双路回退、端到端演示、纵向实验与治理复核的历史基础产物。
- W16 之后，报告证据应优先引用 `#221` 四组实验矩阵、`#222` 聚合分析、`#224` evidence templates、`#225` write-back closeout。

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
- known_issue: W16 结果支持成本/控制边界，不支持宣称 `lite_belief_state` 提升成功率。
- known_issue: case-level 证据仍需最小 bundle 固化；缺失 event log 或 snapshot 时必须显式标记。
- known_issue: `#248` active tool metadata 与 `#249` canonical naming / output mapping 仍为后续依赖。

## 发布建议

- 维持候选版本：`v0.3.0-rc1`
- 当前只建议作为历史候选版本和论文附录追溯材料，不作为 W16 之后的正式 release 结论。
