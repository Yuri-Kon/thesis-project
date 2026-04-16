# 全流程功能验证报告

- 基线提交：`40d4d7a`
- 报告时间：`2026-03-19T23:29:09+08:00`
- 报告目的：验证系统从自然语言任务输入到计划生成、执行、恢复、HITL 决策、门控、总结报告的核心功能链路，并给出论文可引用的实验性结论。

## 1. 设计依据

本次验证以设计文档中的以下 SSOT 片段为依据：

- `SID:fsm.states.definitions`
  - 核心要求：任务必须经过 `CREATED -> PLANNING -> WAITING_PLAN_CONFIRM/PLANNED -> RUNNING -> WAITING_* -> SUMMARIZING -> DONE/FAILED/CANCELLED` 的显式状态流。
- `SID:planner.interface.overview`
  - 核心要求：Planner 只生成 `Plan / PlanPatch / Replan`，不执行工具。
- `SID:planner.contracts.patch_candidate`
  - 核心要求：Patch 优先级为参数级修补、工具级替换、结构级调整。
- `SID:executor.hitl.patch_confirm`
  - 核心要求：Executor 在 patch 触发时必须暂停后续执行并进入 `WAITING_PATCH` 相关流程，不能自行越权应用人工决策。
- `SID:workflow.stage.patch_replan_control`
  - 核心要求：Patch/Replan 是贯穿式控制层，可由失败、风险或目标偏离触发。
- `SID:summarizer.responsibilities.must`
  - 核心要求：Summarizer 仅在 `SUMMARIZING` 后启动，且必须区分执行结果与展示产物。
- `SID:planner.algorithm.decision_application`
  - 核心要求：`plan_confirm / patch_confirm / replan_confirm` 的 Decision 应用必须可测试、可固化。

## 2. 覆盖范围与测试矩阵

| 功能点 | 设计依据 | 代码入口 | 验证用例/命令 | 结果 |
|---|---|---|---|---|
| 自然语言任务解析 | `planner.interface.overview` | `src/agents/task_goal_parser.py` | `tests/unit/test_planner_agent.py::TestPlannerAgent::test_enrich_task_from_goal_infers_goal_type_prompt_and_length_range` | 通过 |
| 自然语言中抽取序列与远端偏好 | `planner.interface.overview` | `src/agents/task_goal_parser.py` | `tests/unit/test_planner_agent.py::TestPlannerAgent::test_enrich_task_from_goal_extracts_sequence_without_forcing_de_novo` | 通过 |
| Plan Top-K 门控与 WAITING_PLAN_CONFIRM/自动放行 | `fsm.states.definitions` | `src/agents/planner.py` | `tests/integration/test_candidate_score_gate.py::test_plan_gate_waiting_and_auto_paths` | 通过 |
| Patch Top-K 门控与 WAITING_PATCH_CONFIRM/自动放行 | `executor.hitl.patch_confirm` | `src/agents/planner.py`, `src/workflow/patch_runner.py` | `tests/integration/test_candidate_score_gate.py::test_patch_gate_waiting_and_auto_paths` | 通过 |
| S3 质量门从结构候选中过滤并保留失败样本轨迹 | `workflow.layers.six_stage` / `workflow.stage.quality_gate` | `src/agents/executor.py`, `src/workflow/quality_gate.py` | `tests/integration/test_quality_gate_s3.py` | 通过 |
| Retry 耗尽后触发 Patch | `workflow.stage.patch_replan_control` | `src/workflow/plan_runner.py` | `tests/unit/test_plan_runner.py::test_run_plan_triggers_patch_after_retry_exhausted` | 通过 |
| Patch 失败后自动升级到 Replan 并解决 PendingAction | `planner.algorithm.decision_application` | `src/workflow/plan_runner.py`, `src/workflow/decision_apply.py` | `tests/unit/test_plan_runner.py::test_auto_replan_resolves_pending_action` | 通过 |
| 分层 Patch：参数级 -> 工具级 -> Replan 升级 | `planner.contracts.patch_candidate` | `src/agents/planner.py`, `src/workflow/patch_runner.py` | `tests/integration/test_recovery_layered_patch.py` | 通过 |
| 高风险 Patch 升级为 Replan | `workflow.stage.patch_replan_control` | `src/workflow/patch_runner.py` | `tests/integration/test_recovery_layered_patch.py::test_high_risk_patch_escalates_to_replan` | 通过 |
| HITL 六阶段回放：等待、决策、退出等待、到达 DONE | `fsm.states.definitions` / `planner.algorithm.decision_application` | `src/workflow/*`, `src/storage/log_store.py` | `tests/integration/test_s6_control_layer_e2e.py` 与 `scripts/run_w12_issue151_demo_audit.py` | 通过 |
| WAITING_ENTER / WAITING_EXIT / DECISION_APPLIED 日志闭环 | `arch.contracts.pending_action` / `obs.eventlog` | `src/workflow/pending_action.py`, `src/workflow/decision_apply.py` | `tests/integration/test_event_log_integration.py` | 通过 |
| 执行器 + 远端适配器 + 总结器的完整成功流 | `summarizer.responsibilities.must` | `src/agents/executor.py`, `src/agents/summarizer.py` | `tests/integration/test_mock_remote_full_flow.py` | 通过 |
| ESMFold 执行结果进入总结报告 | `summarizer.responsibilities.must` | `src/agents/summarizer.py` | `tests/integration/test_esmfold_summarizer_integration.py` | 通过 |
| Planner 双路回退（local/external） | 扩展亮点，结合 `workflow.stage.patch_replan_control` | `src/agents/planner.py` | `tests/integration/test_planner_dual_route_fallback.py` | 通过 |
| 真实 LLM provider 规划调用 | Provider 扩展验证 | `src/llm/*`, `scripts/smoke_test_llm_providers.py` | [llm_provider_smoke_report.json](/home/yurikon/文档/thesis/thesis-project.dev/reports/llm_provider_smoke_report.json) | 4/4 成功 |

## 3. 执行命令

### 3.1 核心功能覆盖矩阵

```bash
uv run pytest \
  tests/unit/test_planner_agent.py::TestPlannerAgent::test_enrich_task_from_goal_infers_goal_type_prompt_and_length_range \
  tests/unit/test_planner_agent.py::TestPlannerAgent::test_enrich_task_from_goal_extracts_sequence_without_forcing_de_novo \
  tests/integration/test_candidate_score_gate.py \
  tests/integration/test_quality_gate_s3.py \
  tests/integration/test_recovery_layered_patch.py \
  tests/integration/test_s6_control_layer_e2e.py \
  tests/integration/test_event_log_integration.py \
  tests/integration/test_mock_remote_full_flow.py \
  tests/integration/test_esmfold_summarizer_integration.py \
  tests/integration/test_planner_dual_route_fallback.py \
  -q --durations=20
```

结果：`21 passed, 1 warning in 27.67s`

主要耗时热点：

1. `test_plan_gate_waiting_and_auto_paths`：`13.61s`
2. `test_patch_gate_waiting_and_auto_paths`：`3.66s`
3. `test_high_risk_patch_escalates_to_replan`：`2.12s`
4. `test_layered_patch_promotes_remote_to_local_tool_level`：`2.09s`
5. `test_layered_patch_promotes_from_parameter_to_tool_level`：`1.99s`
6. `test_layered_patch_failure_escalates_to_replan_with_trace`：`1.97s`
7. `test_six_stage_waiting_patch_decision_replay_to_done`：`1.96s`

### 3.2 Retry / Patch / Replan 主链补充

```bash
uv run pytest \
  tests/unit/test_plan_runner.py::test_run_plan_triggers_patch_after_retry_exhausted \
  tests/unit/test_plan_runner.py::test_auto_replan_resolves_pending_action \
  -q --durations=10
```

结果：`2 passed, 1 warning in 8.11s`

### 3.3 端到端审计演示

```bash
UV_CACHE_DIR=.uv-cache uv run python scripts/run_w12_issue151_demo_audit.py
```

实测耗时：`4.139s`

产物位置：

- [demo-summary.json](/home/yurikon/文档/thesis/thesis-project.dev/output/demo/w12-issue-151/demo-summary.json)
- [release-validation.md](/home/yurikon/文档/thesis/thesis-project.dev/output/demo/w12-issue-151/release-validation.md)
- [replay-record-001-six-stage-hitl.md](/home/yurikon/文档/thesis/thesis-project.dev/output/demo/w12-issue-151/replay-record-001-six-stage-hitl.md)
- [replay-record-002-tool-fallback.md](/home/yurikon/文档/thesis/thesis-project.dev/output/demo/w12-issue-151/replay-record-002-tool-fallback.md)

门禁结果：

- `audit_chain_pendingaction_decision_eventlog = PASS`
- `tool_fallback_switch_recorded = PASS`
- `e2e_flow_reaches_done = PASS`

### 3.4 真实 provider smoke

```bash
UV_CACHE_DIR=.uv-cache uv run python scripts/smoke_test_llm_providers.py \
  --providers qwen-plus,deepseek-chat,glm-5,nemotron \
  --per-provider-timeout 15 \
  --output reports/llm_provider_smoke_report.json
```

结果：4 个 provider 全部成功。

## 4. 关键验证结论

### 4.1 从自然语言到 Plan 的起点已成立

- 系统能够从自然语言目标中抽取：
  - `goal_type`
  - `length_range`
  - `sequence`
  - `prefer_remote`
- 这意味着 Planner 的输入并不局限于结构化 JSON 约束，具备从论文实验描述或自然语言需求直接启动规划的能力。

### 4.2 HITL 不是附属功能，而是主流程中的一等机制

- `WAITING_PLAN_CONFIRM`
- `WAITING_PATCH_CONFIRM`
- `WAITING_REPLAN_CONFIRM`

这三个等待态都已经通过测试和回放产物验证，不仅状态存在，而且具备：

- `PendingAction`
- `Decision`
- `WAITING_ENTER / WAITING_EXIT / DECISION_APPLIED`
- 人工批准后恢复执行或升级控制流

这点是系统区别于普通“单次调用 LLM + 工具执行器”的核心亮点之一。

### 4.3 Patch/Replan 控制层是本系统最强的恢复亮点

分层 Patch 已验证以下路径：

1. 参数级最小修补
2. 工具级替换
3. 失败后升级到 Replan
4. 高风险候选直接升级到 Replan

这与设计文档要求完全一致，也解释了为什么系统不仅能“做成功路径”，还能对失败、偏离和风险进行结构化恢复。

### 4.4 Summarizer 与执行链路已经完成闭环

- 执行器可产生 `StepResult`
- 总结器可将其汇总为 `DesignResult`
- 结果中包含：
  - `structure_pdb_path`
  - 分数/置信度
  - 报告路径
  - 元数据

这使得系统不仅能执行，还能输出适合科研记录和论文附录使用的产物。

### 4.5 多 provider 规划已经达到真实可用

关闭代理后，`qwen-plus`、`deepseek-chat`、`glm-5`、`nemotron` 全部通过真实 smoke，且都产出了稳定的 3 步规划链：

`protgpt2 -> nim_esmfold -> biopython_qc`

这表明多 provider 能力不再只是静态代码支持，而是已经具备真实调用可用性。

## 5. 当前瓶颈

### 5.1 规划门控路径耗时最高

从测试耗时看，当前最慢的是：

- `test_plan_gate_waiting_and_auto_paths`：`13.61s`
- `test_patch_gate_waiting_and_auto_paths`：`3.66s`

说明候选生成、打分、门控和状态推进是当前本地验证中最重的控制路径。若后续要进一步加大 Top-K 候选数或引入更多 provider，Planner 侧可能首先成为控制面瓶颈。

### 5.2 真实 provider 的主要瓶颈转为响应时延

真实 smoke 的耗时排序为：

1. `deepseek-chat`：`13.503s`
2. `glm-5`：`9.347s`
3. `nemotron`：`5.258s`
4. `qwen-plus`：`4.680s`

因此，当前真实部署场景下的主要外部瓶颈已不再是连通性，而是 provider 延迟差异。

## 6. 论文可用表述建议

可直接提炼为以下结论：

1. 系统已验证从自然语言任务描述到结构化 `Plan` 生成的完整入口能力。
2. 系统支持显式 FSM 与 HITL 决策状态，人工确认不是旁路操作，而是系统状态机的一部分。
3. 系统具备分层恢复能力，能够在 `retry -> patch -> replan` 的渐进式控制策略下处理执行失败与高风险场景。
4. 系统具备从执行结果到 `DesignResult` 与报告产物的闭环汇总能力。
5. 多 provider 规划路径已在真实 smoke 中验证可用，外部差异主要体现为响应时延而非计划结构不稳定。

## 7. 残余边界

本次验证已经覆盖核心控制链路，但仍有两类边界未纳入本报告主结论：

- 依赖真实外部结构预测/远端服务的专用 E2E，如 OpenFold3 远端 REST 测试。
- API 端点级别的 HTTP 合约测试。

这两类并非系统核心机制缺失，而是本次报告聚焦于“任务生命周期与恢复控制链”的功能验证范围。
