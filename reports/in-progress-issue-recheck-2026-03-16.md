# 进行中 Issue 二次核对报告（2026-03-16）

## 核对范围
- 项目：`Yuri-Kon/projects/1`
- 筛选条件：状态为 `In Progress` 且仓库为 `Yuri-Kon/thesis-project`
- 共 8 个 issue：`#144 #148 #149 #150 #151 #159 #160 #173`

## 核对方法
- 对照每个 issue 的“范围/任务拆解/验收标准”。
- 对照其关联且已合并 PR（以 `closedByPullRequestsReferences` 为主）。
- 本地复核代码、文档、测试与 `output/` 产物。
- 二次回归测试：
  - `uv run pytest tests/unit/test_planner_agent.py tests/unit/test_decision_validation.py tests/integration/test_s6_control_layer_e2e.py tests/unit/test_run_w12_issue148_sft_qlora.py tests/unit/test_evaluate_w12_issue149_offline_benchmark.py tests/unit/test_log_store_timeline.py tests/integration/test_planner_dual_route_fallback.py tests/unit/test_evaluate_w12_issue173_governance.py tests/integration/test_recovery_layered_patch.py::test_layered_patch_promotes_remote_to_local_tool_level -q`
  - 结果：`59 passed`

## 总览结论
| Issue | 关联已合并 PR | 是否完成 | 是否可关闭 issue | 备注 |
|---|---|---|---|---|
| #144 | #191 | 是 | 是（issue 已 CLOSED） | 项目字段仍是 `In Progress`，建议改为 `Done`（已完成） |
| #148 | #189 | 是 | 是（issue 已 CLOSED） | 项目字段仍是 `In Progress`，建议改为 `Done`（已完成） |
| #149 | #190 | 部分完成 | 否（建议重新打开（reopen）或补充后续 issue） | 评估流程完成，但 RC Gate-B 门禁阈值未达标 |
| #150 | #192 | 是 | 是（issue 已 CLOSED） | 项目字段仍是 `In Progress`，建议改为 `Done`（已完成） |
| #151 | #193 | 是 | 是（issue 已 CLOSED） | 项目字段仍是 `In Progress`，建议改为 `Done`（已完成） |
| #159 | #187 | 是 | 是（issue 已 CLOSED） | 项目字段仍是 `In Progress`，建议改为 `Done`（已完成） |
| #160 | #188 | 是 | 是（issue 已 CLOSED） | 项目字段仍是 `In Progress`，建议改为 `Done`（已完成） |
| #173 | #194 | 是 | 是（issue 已 CLOSED） | 项目字段仍是 `In Progress`，建议改为 `Done`（已完成） |

---

## #144 W11-Observability-1
- 关联 PR：#191（merged）
- 是否完成：是
- 已满足需求与验收标准：
  - 恢复链路关键字段已补齐并统一：`tool_id/capability_id/io_type/adapter_mode/from_tool/to_tool/failure_type/failure_code/candidate_id/decision_source/recovery_layer/recovery_reason`。
  - 任务级回放 API 支持按 `event_type/tool_id/capability_id/adapter_mode` 过滤。
  - 旧日志兼容读取保留（缺字段降级、非严格模式容错）。
  - `PendingAction -> Decision -> EventLog` 相关路径有单测/API测试覆盖。
- 产物所在：
  - 代码：`src/storage/log_store.py`, `src/api/main.py`, `src/workflow/pending_action.py`, `src/workflow/decision_apply.py`, `src/workflow/patch_runner.py`, `src/workflow/plan_runner.py`
  - 测试：`tests/unit/test_log_store_timeline.py`, `tests/api/test_api_endpoints.py`
  - 文档：`scripts/w11-issue-144-recovery-observability.md`
- 是否可以关闭 issue：是（已关闭）
- 进一步补充：项目条目状态应从 `In Progress` 调整为 `Done`（已完成）。

## #148 W12-Training-1
- 关联 PR：#189（merged）
- 是否完成：是
- 已满足需求与验收标准：
  - 训练脚本与配置已固化，支持 P0-only 与 P0+P1 两套配置。
  - 模型可加载与最小推理冒烟已落盘（`smoke_inference.json`）。
  - 关键训练参数、环境、可复现命令已记录。
  - RC Gate-A 产物齐全：manifest/checksum/model_card/candidate version 命名。
  - Requirement-2 并入项已覆盖：工具分层采样、按工具切片统计、model card 工具覆盖。
- 产物所在：
  - 脚本：`scripts/run_w12_issue148_sft_qlora.py`
  - 配置：`configs/training/w12_issue148_sft_qlora_p0_only.json`, `configs/training/w12_issue148_sft_qlora_p0_p1.json`
  - 测试：`tests/unit/test_run_w12_issue148_sft_qlora.py`
  - 文档：`scripts/w12-issue-148-sft-qlora-baseline.md`
  - 输出：`output/training/w12-issue-148/v0.3.0-rc1/issue148-p0-only/` 与 `.../issue148-p0-p1/`
- 是否可以关闭 issue：是（已关闭）
- 进一步补充：可补充更大样本规模训练记录，降低小样本偏差。

## #149 W12-Evaluation-1
- 关联 PR：#190（merged）
- 是否完成：部分完成
- 已满足需求与验收标准：
  - 评估口径、脚本、可复现命令、输入版本记录齐全。
  - 产出对比表、门禁检查与 `release-benchmark.md`。
  - Requirement-2 工具切片与覆盖分析表已输出。
  - “未达标项+阻断发布”有明确结论（`block release`）。
- 未满足项（关键）：
  - RC Gate-B 指标门禁阈值未全部达成：
    - `patch_minimality_hit_rate` 未达到/缺值
    - `suffix_replan_prefix_preservation_rate` 未达到/缺值
- 产物所在：
  - 脚本：`scripts/evaluate_w12_issue149_offline_benchmark.py`
  - 测试：`tests/unit/test_evaluate_w12_issue149_offline_benchmark.py`
  - 文档：`scripts/w12-issue-149-offline-benchmark.md`
  - 输出：`output/experiment/w12-expr-2/issue149-offline-benchmark/`
- 是否可以关闭 issue：否（按原验收标准“达到最低离线门禁阈值”未满足）
- 进一步补充：建议重新打开（reopen）本 issue 或新增后续 issue，补采样本使两项缺失指标可计算并达标。

## #150 W12-Runtime-1
- 关联 PR：#192（merged）
- 是否完成：是
- 已满足需求与验收标准：
  - 双路推理与阈值触发已接入（schema fail、可执行率下降、连续失败、高风险持续）。
  - 保持 FSM/HITL 语义不变（provider 层路由）。
  - 路由审计事件 `PLANNER_ROUTE_DECISION` 可追溯。
  - RC Gate-C 对齐项已覆盖：默认回退保障、一键熔断、阈值建议与变更记录。
- 产物所在：
  - 代码：`src/agents/planner.py`, `src/storage/log_store.py`, `src/api/main.py`
  - 配置：`configs/runtime/w12_issue150_dual_route_fallback.json`
  - 测试：`tests/integration/test_planner_dual_route_fallback.py`, `tests/unit/test_log_store_timeline.py`
  - 文档：`scripts/w12-issue-150-dual-route-fallback.md`
- 是否可以关闭 issue：是（已关闭）
- 进一步补充：建议补充线上真实配额/网络异常压测记录。

## #151 W12-Demo-1
- 关联 PR：#193（merged）
- 是否完成：是
- 已满足需求与验收标准：
  - 演示链路复现脚本、标准输入、审计回放证据齐全。
  - 回放链路 `PendingAction -> Decision -> EventLog` 已验证。
  - 文档包含命令、输入、预期检查与排障说明。
  - RC Gate-D 产物齐全：`release-validation.md`、至少 1 条回放记录、Known Issues。
- 产物所在：
  - 脚本：`scripts/run_w12_issue151_demo_audit.py`
  - 示例：`examples/w12_issue151/`
  - 测试：`tests/integration/test_recovery_layered_patch.py`（新增场景）
  - 文档：`scripts/w12-issue-151-demo-audit.md`
  - 输出：`output/demo/w12-issue-151/`
- 是否可以关闭 issue：是（已关闭）
- 进一步补充：可增加“真实远端服务参与”的演示证据链作为补充材料。

## #159 W12-Req1-S5
- 关联 PR：#187（merged）
- 是否完成：是
- 已满足需求与验收标准：
  - S5 多目标打分、权重配置、Top-K 稳定排序已实现。
  - `score_breakdown` 与 `metadata.s5_contract` 提供可解释分解与契约化输出。
  - 输出可被 HITL 直接消费（`default_recommendation` + 候选集结构）。
  - 已补充稳定性/单调性/排序正确性相关单测。
- 产物所在：
  - 代码：`src/agents/planner.py`, `src/models/validation.py`, `src/workflow/patch_runner.py`
  - 测试：`tests/unit/test_planner_agent.py`, `tests/unit/test_decision_validation.py`
  - 文档：`scripts/w12-issue-159-s5-objective-scoring-topk.md`
- 是否可以关闭 issue：是（已关闭）
- 进一步补充：建议补充跨数据分布下权重灵敏度基准（非阻塞）。

## #160 W12-Req1-S6
- 关联 PR：#188（merged）
- 是否完成：是
- 已满足需求与验收标准：
  - S6 阶段感知触发矩阵已实现（失败码 -> patch/replan）。
  - WAITING 决策回流与审计字段已补齐（`data.s6`）。
  - 不新增 FSM 状态、不改变 agent 边界。
  - 六阶段 E2E 回放路径已通过（WAITING_PATCH_CONFIRM -> RUNNING -> DONE）。
- 产物所在：
  - 代码：`src/workflow/recovery.py`, `src/workflow/patch_runner.py`, `src/workflow/plan_runner.py`, `src/workflow/workflow.py`
  - 测试：`tests/integration/test_s6_control_layer_e2e.py`
  - 文档：`scripts/w12-issue-160-s6-control-layer-runbook.md`
- 是否可以关闭 issue：是（已关闭）
- 进一步补充：建议增加 S1/S2/S4/S5 每阶段失败的回放样例测试（增强覆盖，不阻塞验收）。

## #173 W12-Experiment-4
- 关联 PR：#194（merged）
- 是否完成：是
- 已满足需求与验收标准：
  - 审计链完整率/回放成功率/失败追溯率可复现计算。
  - 失败追溯可定位到关键上下文（`step_id/tool/failure_code`）。
  - 治理指标与纵向结果合并输出，可直接用于图表。
  - 标准回放样例与治理报告已沉淀。
- 产物所在：
  - 脚本：`scripts/evaluate_w12_issue173_governance.py`
  - 测试：`tests/unit/test_evaluate_w12_issue173_governance.py`
  - 文档：`scripts/w12-issue-173-governance-review.md`
  - 输出：`output/experiment/w12-expr-2/issue173-governance-review/`
- 是否可以关闭 issue：是（已关闭）
- 进一步补充：当前 `waiting_chain_complete_rate/replay_success_rate=0`，建议补采含完整 WAITING 决策链的数据集用于治理改进迭代。

---

## 建议动作
1. 将项目中上述 8 个条目状态从 `In Progress` 更新为 `Done`（已完成，至少 #144/#148/#150/#151/#159/#160/#173）。
2. 对 #149 进行决策：
   - 方案 A：重新打开（reopen）#149，继续补齐 RC Gate-B 未达标项；
   - 方案 B：保持关闭，但新建阻断 issue 专门跟踪门禁阈值达标。
