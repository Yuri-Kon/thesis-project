# 毕业论文最终实验设计

更新时间：2026-05-10

## 1. 实验定位

本文档用于把中期阶段的系统验证扩展为毕业论文最终实验方案。实验需要同时服务两个目标：

1. 软工毕设目标：证明系统可用、功能完整、接口稳定、前端与 CLI 能支撑实际操作流程。
2. 算法目标：证明 CEBRA-WP 并非附属实现，而是系统在高代价、长链路、可失败科研工作流中进行自适应规划与恢复的核心机制。

因此最终实验不应只写“测试通过”，也不应只做算法表格。建议采用“双主线”结构：

| 主线 | 回答的问题 | 论文位置 |
|:---|:---|:---|
| 系统可用性与工程验证 | 系统是否能被用户通过 Web / CLI / API 完成任务创建、执行、确认、查看和审计？ | 第五章系统测试与验证 |
| CEBRA-WP 算法验证 | 算法是否可行、是否有必要、相比静态规划是否带来成本/控制/恢复优势？ | 第五章实验结果与算法分析 |

## 2. 实验结论边界

已有 W16 结果提示：当前证据不能直接宣称 `lite_belief_state` 提升最终成功率。最终论文实验需要保留这个边界，避免过强表述。

建议采用三层结论：

| 结论层级 | 可以验证什么 | 需要的证据 |
|:---|:---|:---|
| 可行性 | CEBRA-WP 的 policy mode、runtime_state、rerank、action utility 和 recovery trace 能正常运行 | 单测、集成测试、事件日志、候选 metadata |
| 必要性 | 静态单链或静态门控在失败、预算、高代价步骤前缺少运行时调整能力 | 静态组与动态组的失败/浪费/人工介入对比 |
| 优势 | CEBRA-WP 在特定任务上减少高代价调用、降低无效执行、改善恢复决策质量 | 四组消融、定向 rerun、案例证据 |

强结论门槛：

- 若 `lite_belief_state` 在成功率、恢复成功率、成本控制上均优于对照组，可以写“综合性能更优”。
- 若只在高代价调用数、运行时间、stop_quality 或 rerank_delta 上更好，应写“提升运行时控制能力与成本控制能力”。
- 若成功率不高但日志能解释止损行为，应写“在高风险场景中表现为更保守的损失控制”，不能写“设计质量提升”。

## 3. 研究问题

| 编号 | 研究问题 | 对应实验 |
|:---|:---|:---|
| RQ-S1 | 系统核心功能是否覆盖从任务输入到结果报告的完整流程？ | EXP-S1、EXP-S2、EXP-S5 |
| RQ-S2 | FSM、HITL、快照和事件日志是否保证执行可暂停、可恢复、可审计？ | EXP-S3、EXP-S6、EXP-S7 |
| RQ-S3 | Web 前端和 CLI 是否能支撑用户完成关键操作？ | EXP-S4 |
| RQ-A1 | CEBRA-WP 的运行时策略是否在代码层面可执行、可切换、可追踪？ | EXP-A1 |
| RQ-A2 | 相比静态规划，CEBRA-WP 是否有存在必要性？ | EXP-A2、EXP-A3 |
| RQ-A3 | Lite belief-state 是否相比“动态观测但无 belief-state”带来增量价值？ | EXP-A4 |
| RQ-A4 | 算法是否能通过事件日志和候选解释说明决策依据？ | EXP-A5 |

## 4. 实验总体矩阵

| 实验编号 | 实验名称 | 类型 | 主要验证点 | 关键产物 |
|:---|:---|:---|:---|:---|
| EXP-S1 | 环境与能力就绪验证 | 系统验证 | API 健康、工具能力、远程服务 readiness | health JSON、readiness JSON、启动日志 |
| EXP-S2 | API 合约与任务录入验证 | 系统验证 | task-intake、task 创建、pending-action、report、events | API 响应、pytest log |
| EXP-S3 | FSM / HITL / 快照一致性验证 | 系统验证 | `WAITING_*`、`PendingAction`、`Decision`、快照恢复 | EventLog、snapshot、状态迁移表 |
| EXP-S4 | Web 与 CLI 可用性验证 | 系统可用性 | Dashboard、Task Builder、Task Detail、Timeline、CLI show/watch/report | 页面截图、CLI 输出 |
| EXP-S5 | 正常端到端流程验证 | 系统验证 | 自然语言任务到 `DesignResult` 的完整链路 | task JSON、report、artifact |
| EXP-S6 | 异常输入与安全边界验证 | 系统验证 | 缺字段、错误决策、终态不可变、安全 warn/block | 错误响应、日志 |
| EXP-S7 | 失败恢复流程验证 | 系统验证/算法支撑 | retry -> patch -> replan -> stop/DONE | recovery trace、Plan diff |
| EXP-A1 | CEBRA-WP 机制可行性验证 | 算法验证 | policy mode、runtime delta、rerank、action utility | 单测结果、候选 metadata |
| EXP-A2 | 四组消融主实验 | 算法验证 | static_top1 / static_gate / dynamic_no_belief_state / lite_belief_state | metrics CSV、matrix report |
| EXP-A3 | 静态规划必要性对照 | 算法验证 | 静态组在失败和高代价场景下的不足 | wasted_call、early_failure、case log |
| EXP-A4 | belief-state 增量定向实验 | 算法验证 | dynamic_no_belief_state vs lite_belief_state | rerank_delta、action agreement、stop_quality |
| EXP-A5 | 典型案例分析 | 算法解释性 | 成功案例、局部失败恢复案例、高风险止损案例 | case bundle、事件时间线 |
| EXP-A6 | 外部基线补充实验 | 可选扩展 | ReAct-style / single LLM planner 与内部方法对照 | Inspect / MLflow / promptfoo 产物 |

## 5. 实验任务集设计

最终任务集不宜只使用一个成功路径。建议固定 8 类任务，每类至少 3 个样本，主实验每组至少重复 3 次；若时间不足，最小集可用每类 1 个样本、每组重复 2 次。

> 2026-05-10 执行状态：最小验证包已跑通。t9 clean run 使用 4 任务（t1/t2/t5/t8）× 4 组 × 1 repeat，16/16 DONE，基础设施和四组矩阵链路确认可用。下一步按最小包策略扩到 8 任务 + 2 repeat。

| 任务类 | 任务目标 | 设计目的 | 预期触发 |
|:---|:---|:---|:---|
| T1 简单 de novo 设计 | 设计 20 到 40 残基的短肽 | 验证基础规划与执行成功路径 | 正常 DONE |
| T2 序列评估 | 给定序列，预测结构并评估稳定性 | 验证输入约束和结构预测链路 | StepResult、report |
| T3 多约束稳定性优化 | 长度、二级结构、稳定性和预算同时约束 | 验证候选过滤和静态门控 | plan candidate 排序 |
| T4 高代价结构预测 | 需要远程结构预测或高成本工具 | 验证高代价调用控制 | high_cost_call_count |
| T5 可修复参数失败 | 人为设置边界参数导致第一次失败 | 验证 retry 与参数级 patch | WAITING_PATCH_CONFIRM |
| T6 工具不可用/降级 | 模拟远程服务不可用或 readiness degraded | 验证工具替换和 degraded feasible | patch/replan |
| T7 结构性失败 | 输入导致后续工具链整体风险升高 | 验证 suffix replan / terminal_stop | WAITING_REPLAN_CONFIRM |
| T8 安全 warn/block | forbidden motif 或安全级别冲突 | 验证 safety 与人工确认边界 | warn acknowledge 或 block |

建议新增一个最终任务集配置：

```text
configs/experiments/thesis_final_task_set.json
```

建议字段：

```json
{
  "task_set_version": "thesis-final-v1",
  "tasks": [
    {
      "task_key": "t1_short_peptide",
      "difficulty": "easy",
      "goal": "设计一个 30 残基的稳定螺旋肽",
      "constraints": {
        "length_range": [25, 35],
        "objective_type": "stability",
        "runtime_policy": "lite_belief_state"
      },
      "expected_focus": ["normal_flow", "report"]
    }
  ]
}
```

## 6. 算法实验分组

内部算法主实验使用现有四组映射，不再新增混乱命名。

| 代码 mode | 论文组名 | 对照意义 | 重点指标 |
|:---|:---|:---|:---|
| `static_top1` | 静态单链基线 | 只采用静态最高分候选 | success_rate、early_failure_rate、high_cost_call_count |
| `static_gate` | 静态门控基线 | 有静态过滤，但无运行时重排 | gate_pass_rate、wasted_call_rate |
| `dynamic_observation_only` | 动态观测但无 belief-state | 有 patch/replan 观测链路，但 runtime adjustment 为 0 | recovery_success_rate、recovery_cost |
| `lite_belief_state` | 完整 CEBRA-WP | 启用 Lite belief-state、runtime adjustment、action utility | rerank_delta、stop_quality、high_cost_call_count、success_rate |

可选外部基线：

| 基线 | 作用 | 是否必须 |
|:---|:---|:---|
| Single LLM Planner | 对比单次规划，无 FSM / HITL / recovery | 可选 |
| ReAct-style Baseline | 对比通用 Agent 范式 | 可选 |
| Manual fixed workflow | 对比固定工具链流程 | 若时间允许，建议补一个 |

论文主结论优先依赖内部四组；外部基线作为补充，不应阻塞毕业论文完成。

## 7. 指标体系

### 7.1 系统可用性指标

| 指标 | 定义 | 数据来源 |
|:---|:---|:---|
| API pass rate | API 合约测试通过比例 | `tests/api/`、接口响应 |
| UI page load success | 关键页面是否成功加载并注入 bootstrap | `tests/api/test_web_smoke.py`、截图 |
| CLI command success | CLI 子命令是否正常输出 JSON/人类可读摘要 | `tests/unit/test_cli.py`、手工命令 |
| task completion rate | 任务从创建到终态的完成比例 | TaskRecord、EventLog |
| evidence completeness | 每个任务是否具备 task、events、snapshot、report 证据 | evidence index |
| user operation count | 完成关键流程所需点击/命令次数 | 手工记录 |
| time to decision | 从进入 `WAITING_*` 到提交 Decision 的耗时 | EventLog |

### 7.2 工程正确性指标

| 指标 | 定义 | 数据来源 |
|:---|:---|:---|
| FSM transition validity | 状态迁移是否符合设计允许路径 | 状态转移测试、EventLog |
| pending-action integrity | 等待态是否都有对应 `PendingAction` | task JSON、pending API |
| decision application correctness | Decision 是否只影响目标 pending action | decision 测试、日志 |
| snapshot recovery correctness | 恢复后是否保持等待态或运行上下文 | snapshot 测试、恢复日志 |
| terminal immutability | DONE/FAILED/CANCELLED 是否不可再变更 | API/单测 |

### 7.3 CEBRA-WP 算法指标

| 指标 | 定义 | 说明 |
|:---|:---|:---|
| plan_valid_rate | 生成候选满足 schema、工具、I/O、预算、安全硬约束的比例 | 证明规划可行性 |
| success_rate | 最终进入 DONE 的比例 | 可作为主结果，但不能单独解释算法质量 |
| first_pass_success_rate | 无 patch/replan 即成功的比例 | 衡量静态规划质量 |
| recovery_success_rate | 触发失败后经 patch/replan 恢复到 DONE 的比例 | 衡量恢复能力 |
| patch_event_count | 每个 run 的 patch 次数 | 衡量局部修复频率 |
| replan_event_count | 每个 run 的 replan 次数 | 衡量结构性调整频率 |
| high_cost_call_count | 高代价工具调用次数 | 论文中很适合证明成本控制 |
| wasted_call_rate | 最终失败或被回滚的高代价调用比例 | 证明静态链路浪费问题 |
| runtime_seconds | 运行耗时 | 需要区分本地模拟和真实 provider |
| rerank_delta | runtime adjustment 改变候选分数的幅度 | 证明 belief-state 起作用 |
| action_agreement | 推荐动作与期望 oracle/人工判断的一致率 | 用于定向任务 |
| stop_quality | stop 发生时是否避免了无效高代价后续调用 | 用于高风险止损场景 |
| evidence_sufficiency | 运行时证据充分度变化 | 解释决策依据 |

## 8. 详细实验设计

### EXP-S1 环境与能力就绪验证

目标：证明系统基础环境、API 服务、工具能力目录和 readiness 机制可用。

覆盖 `SV-01`、`SV-27`。

步骤：

1. 启动 API 服务。
2. 请求 `/health`。
3. 请求 `/capabilities/readiness`。
4. 若远程服务不可用，记录 degraded reason 和 suggested recovery。

建议命令：

```bash
uv run uvicorn src.api.main:app --reload
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/capabilities/readiness
```

通过标准：

- `/health` 返回 `status=ok`。
- readiness 能列出 capability、available_tools、blocked_tools、degraded_reasons。
- 远程不可用时不能静默失败，必须有清晰原因。

### EXP-S2 API 合约与任务录入验证

目标：验证任务输入、确认、创建、查询、报告、事件接口完整可用。

覆盖 `SV-02` 到 `SV-13`、`SV-25`、`SV-26`。

建议命令：

```bash
uv run pytest tests/api/test_api_endpoints.py -q
```

补充手工接口：

- `GET /task-intakes/schema`
- `POST /task-intakes`
- `POST /task-intakes/{id}/confirm`
- `POST /tasks`
- `GET /tasks/{id}`
- `GET /tasks/{id}/events`
- `GET /tasks/{id}/report`
- `GET /pending-actions`
- `POST /pending-actions/{id}/decision`

通过标准：

- 正常输入能创建 intake 和 task。
- 缺字段、错误 pending action、重复 decision 等异常输入返回明确错误。
- 未完成任务请求 report 返回 404。

### EXP-S3 FSM / HITL / 快照一致性验证

目标：验证 `WAITING_PLAN_CONFIRM`、`WAITING_PATCH_CONFIRM`、`WAITING_REPLAN_CONFIRM` 不只是状态名，而是完整的人在环路暂停机制。

覆盖 `SV-10` 到 `SV-15`、`SV-18` 到 `SV-24`、`SV-28`、`SV-29`。

建议命令：

```bash
uv run pytest \
  tests/unit/test_status_transition.py \
  tests/unit/test_decision_validation.py \
  tests/unit/test_decision_apply.py \
  tests/unit/test_task_snapshot.py \
  tests/unit/test_event_log.py \
  tests/integration/test_event_log_integration.py \
  tests/integration/test_snapshot_recovery.py \
  -q
```

观察项：

- 进入 `WAITING_*` 前是否写入 snapshot。
- EventLog 是否包含 `WAITING_ENTER`、`DECISION_APPLIED`、`WAITING_EXIT`。
- 等待态下 Executor 是否停止工具调用。
- 终态是否不可变。

通过标准：

- 所有等待态均有 `PendingAction`。
- snapshot 能恢复当前 plan、completed steps、pending action 和 runtime_state。
- Decision 后只发生一次合法状态转移。

### EXP-S4 Web 与 CLI 可用性验证

目标：补齐中期实验未覆盖的前端界面和 CLI 入口，证明系统不是只有后端测试。

覆盖 `SV-30`。

自动验证命令：

```bash
uv run pytest tests/api/test_web_smoke.py tests/unit/test_cli.py -q
```

Web 手工流程：

| 页面 | URL | 验证内容 | 证据 |
|:---|:---|:---|:---|
| Dashboard | `/ui` | 任务列表、状态摘要、能力提示 | 截图 |
| Task Builder | `/ui/task-builder` | 创建 intake、补充字段、确认任务 | 截图、API JSON |
| Task Detail | `/ui/tasks/{task_id}` | 展示任务状态、候选、结果、readiness | 截图 |
| Timeline | `/ui/tasks/{task_id}/events` | 展示事件链、WAITING/DECISION/STEP | 截图 |
| Pending Review | 任务详情中的 pending panel | 比较候选并提交 Decision | 截图、decision JSON |

CLI 手工流程：

```bash
python -m src.cli intake schema --json
python -m src.cli intake create --text "设计一个 30 残基稳定螺旋肽" --json
python -m src.cli intake show <intake_id> --json
python -m src.cli intake confirm <intake_id> --confirmed-by thesis_cli --json
python -m src.cli task show <task_id> --json
python -m src.cli timeline show <task_id> --json
python -m src.cli pending show <pending_action_id>
python -m src.cli report show <task_id>
```

通过标准：

- Web 能完成任务创建、状态查看、人工确认、事件查看。
- CLI 能输出 JSON 和人类可读摘要。
- Web 与 CLI 展示的 task_id、status、pending_action_id、event 数量一致。

### EXP-S5 正常端到端流程验证

目标：验证系统从自然语言任务到结果报告的完整成功路径。

建议命令：

```bash
uv run pytest \
  tests/integration/test_mock_remote_full_flow.py \
  tests/integration/test_esmfold_summarizer_integration.py \
  tests/integration/test_workflow.py \
  -q
```

通过标准：

- 任务进入 `DONE`。
- 至少包含一个 `StepResult`。
- `/tasks/{id}/report` 返回 `DesignResult`。
- 报告包含 scores、risk_flags、report_path 或 structure artifact。

### EXP-S6 异常输入与安全边界验证

目标：验证系统在错误输入和安全风险下不会越权执行。

覆盖：

- 缺失必要字段。
- safety warn 未 acknowledge。
- safety block。
- 错误 task/pending 绑定。
- 终态继续决策。

建议命令：

```bash
uv run pytest \
  tests/unit/test_safety_agent.py \
  tests/unit/test_decision_validation.py \
  tests/api/test_api_endpoints.py \
  -q
```

通过标准：

- warn 必须显式 acknowledge。
- block 不允许创建正式执行任务。
- 错误 decision 被拒绝且不改变任务状态。

### EXP-S7 失败恢复流程验证

目标：验证 retry、patch、replan 是系统主流程的一部分，而不是异常旁路。

建议命令：

```bash
uv run pytest \
  tests/unit/test_plan_runner.py::test_run_plan_triggers_patch_after_retry_exhausted \
  tests/unit/test_plan_runner.py::test_auto_replan_resolves_pending_action \
  tests/integration/test_recovery_layered_patch.py \
  tests/integration/test_s6_control_layer_e2e.py \
  -q --durations=20
```

通过标准：

- retry 耗尽后不直接 FAILED，而是进入 patch/replan 路径。
- patch accept 后只修改目标步骤或后缀。
- replan 保留可保留前缀。
- recovery trace 可从 EventLog 还原。

### EXP-A1 CEBRA-WP 机制可行性验证

目标：验证算法机制在代码层可执行、可切换、可解释。

建议命令：

```bash
uv run pytest \
  tests/unit/test_runtime_evaluator.py \
  tests/unit/test_belief_state.py \
  tests/unit/test_action_features.py \
  tests/unit/test_recovery_selector.py \
  tests/unit/test_planner_posterior_objective_scoring.py \
  -q
```

重点观察：

- 四个 policy mode 顺序和语义稳定。
- `static_top1` / `static_gate` 禁用 rerank。
- `dynamic_observation_only` 保留动态链路但 runtime adjustment 为 0。
- `lite_belief_state` 启用完整 runtime adjustment。
- 候选 metadata 包含 runtime_adjustment、action_utility、rerank_reason。

通过标准：

- 单测全部通过。
- `lite_belief_state` 的候选能产生非零 runtime adjustment 或清晰的 rerank trace。
- 未知 policy mode 回退行为可解释。

### EXP-A2 四组消融主实验

目标：在同一任务集、同一预算、同一工具白名单下比较四个内部组，验证 CEBRA-WP 与静态/半动态策略的差异。

建议使用现有矩阵入口：

```bash
uv run python scripts/run_thesis_experiment_matrix.py \
  --config configs/experiments/adaptive_strategy_experiment_matrix.json \
  --output-root output/experiment/thesis-final-matrix \
  --run-id thesis-final-v1
```

若先做试跑：

```bash
uv run python scripts/run_thesis_experiment_matrix.py \
  --config configs/experiments/adaptive_strategy_experiment_matrix.json \
  --output-root output/experiment/thesis-final-matrix-dry \
  --run-id thesis-final-dry \
  --dry-run
```

结果表：

| 组 | success_rate | first_pass_success_rate | recovery_success_rate | high_cost_call_mean | wasted_call_rate | runtime_seconds_mean | stop_quality | rerank_delta_mean |
|:---|---:|---:|---:|---:|---:|---:|---:|---:|
| static_top1 | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 | 0 |
| fixed_threshold_gate | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 | 0 |
| dynamic_no_belief_state | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 | 0 |
| lite_belief_state | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 |

当前 smoke 执行记录：

| run_id | 日期 | planner_provider | task_key | selection | runs | success | rerun_candidates | abnormal_samples | 结论 |
|:---|:---|:---|:---|:---|---:|---:|---:|---:|:---|
| `thesis-final-smoke-fourgroup-t8-provider-max-001` | 2026-05-09 | `deepseek-v4-pro` | `t2_trpcage_sequence_eval` | `four-group-t8-provider-max-selection.json` | 4 | 4 | 0 | 0 | 四组 smoke 通过；provider max_tokens 与 OpenFold3 REST 链路恢复正常 |
| `thesis-final-smoke-fourgroup-t9-clean-001` | 2026-05-10 | `deepseek-v4-pro` | t1/t2/t5/t8 | `four-group-t9-clean-selection.json` | 16 | 16 | 0 | 0 | 四组 × 四任务 clean run 通过；基础设施无阻塞问题 |

t8 smoke 结果表（单任务 `t2_trpcage_sequence_eval`）：

| group_id | runs | success_rate | first_pass_success_rate | executable_plan_rate | duration_ms_mean | tool_usage | trace_ref |
|:---|---:|---:|---:|---:|---:|:---|:---|
| `static_top1` | 1 | 1.0000 | 1.0000 | 1.0000 | 183000.0 | `openfold=1, biopython_qc=1, mda_analysis=1` | `output/experiment/thesis-final-matrix-smoke/thesis-final-smoke-fourgroup-t8-provider-max-001/run_level_results.jsonl` |
| `fixed_threshold_gate` | 1 | 1.0000 | 1.0000 | 1.0000 | 290000.0 | `openfold=1` | `output/experiment/thesis-final-matrix-smoke/thesis-final-smoke-fourgroup-t8-provider-max-001/run_level_results.jsonl` |
| `dynamic_no_belief_state` | 1 | 1.0000 | 1.0000 | 1.0000 | 207000.0 | `openfold=1` | `output/experiment/thesis-final-matrix-smoke/thesis-final-smoke-fourgroup-t8-provider-max-001/run_level_results.jsonl` |
| `lite_belief_state` | 1 | 1.0000 | 1.0000 | 1.0000 | 253000.0 | `openfold=1` | `output/experiment/thesis-final-matrix-smoke/thesis-final-smoke-fourgroup-t8-provider-max-001/run_level_results.jsonl` |

t9 clean run 结果表（4 任务 `t1/t2/t5/t8`，每组 4 runs）：

| group_id | runs | success_rate | first_pass | schema_valid | executable | high_cost_mean | patch | replan | duration_ms_mean |
|:---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `static_top1` | 4 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 203500.0 |
| `fixed_threshold_gate` | 4 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 172750.0 |
| `dynamic_no_belief_state` | 4 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 209000.0 |
| `lite_belief_state` | 4 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 225500.0 |

t9 关键发现：

| 发现 | 说明 |
|:---|:---|
| 基础设施通过 | 16/16 DONE，无 rerun、无 abnormal_samples |
| 成功率无区分度 | 所有四组 success_rate=1.0，n=1 无法支撑统计检验 |
| 恢复机制未触发 | t5（patchable_length_failure）未能诱发 patch/replan，所有步骤 `status=success` |
| 恢复 focused test 已补 | `test_deterministic_retry_patch_to_done_produces_recovery_metrics` 确定性触发 retry exhausted -> tool-level patch -> DONE，并验证 `patch_event_count=1` |
| API/report 与 I/O 边界 focused test 已补 | `test_task_report_endpoint_done_contract_and_unfinished_404` 覆盖 DONE report 与未完成 404；`test_validate_plan_executability_reports_candidate_schema_and_io_boundary` 覆盖候选 schema/I-O 结构化拒绝 |
| lite_belief_state 有效观测 | `runtime_state_summary` 非 null，`budget_pressure` source=`observed`（其他组 fallback 到 `default=1.0`），`action_utility_source`=`computed`（其他组 `missing`） |
| 安全任务未阻断 | t8 四组均正常执行，`safety_terminality=0.0`，forbidden_motif 未触发越权阻断 |
| 时序反直觉 | `fixed_threshold_gate` 最快（172.75s），`static_top1` 因 dual-route planning 反而更慢（203.5s） |
| suffix_replan 计数口径已修正 | 重算后四组 `suffix_replan_events_total=0.0`；`action_utilities.suffix_replan` 仅作为候选效用证据，不计入真实恢复事件 |

Provider 与 OpenFold3 修复验证（t8 + t9 联合）：

| 验证项 | 观察结果 | 证据 |
|:---|:---|:---|
| DeepSeek V4 `max_tokens` 上限 | 未再出现 `Invalid max_tokens value` 或 `provider_invocation_failed` | t8 + t9 `run_log_index.csv` |
| OpenFold3 输入序列 | 未再出现 `DUMMY`；t8 输入为 `NLYIQWLKDGGPSSGRPPPS`，t9 为正常生成序列 | t8 + t9 event logs |
| OpenFold3 REST 执行 | t8 + t9 共 20 runs，所有 `openfold` 调用 `execution_mode=openfold3_rest`，`status=success` | `requirement2_tool_capability_slices.csv` |
| 工具链完整性 | t9 覆盖 `openfold`(S2) + `protgpt2`(S1) + `biopython_qc`(S3)，全部通过 | `action_distribution.csv` |

限制说明：t8 是单任务 smoke，t9 是 4 任务 × 1 repeat 的 clean run。两次结果均 100% 成功率，可用于证明链路可用和修复生效。正式论文主结果仍需扩大任务数（8 类）、增加 repeats（n≥2）、并引入能诱发恢复/安全阻断的任务变体。高代价计数口径已修正，所有 run 均记录 `high_cost_call_mean=1.0`。

---

**v1 正式矩阵结果**（`thesis-final-v1-001`，2026-05-10）：12 任务 × 4 组 × max 2 repeats = 84 runs，81/84 DONE（96.4%），3 FAILED。

v1 结果表：

| group_id | runs | success_rate | first_pass | schema_valid | executable | high_cost_mean | patch_mean | replan_mean | duration_ms_mean |
|:---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `static_top1` | 21 | **1.0000** | **1.0000** | 1.0000 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 241905 |
| `fixed_threshold_gate` | 21 | 0.9524 | 0.9048 | 1.0000 | 0.9524 | **1.3333** | **0.2857** | 0.0000 | 300238 |
| `dynamic_no_belief_state` | 21 | 0.9524 | 0.9524 | 0.9524 | 1.0000 | **0.9524** | 0.0000 | 0.0000 | **226571** |
| `lite_belief_state` | 21 | 0.9524 | 0.9524 | 1.0000 | 1.0000 | **0.9524** | 0.0000 | 0.0000 | 272095 |

v1 关键发现：

| 发现 | 说明 |
|:---|:---|
| 成功率首次出现差异化 | static=1.0, 其余三组=0.9524（各 20/21 DONE），打破了 t9 的天花板效应 |
| fixed 是唯一触发真实 patch 的组 | 6 次 tool-level patch（patch_mean=0.29），高代价调用因此涨到 1.33/run |
| dynamic/lite 省高代价调用 | high_cost_mean=0.95 vs static=1.0 vs fixed=1.33，lite 在成功率持平 fixed 时少 28.6% |
| lite belif-state 持续有效 | 21/21 runs runtime_state_observable=1.0, action_utility_source=computed |
| 3 个 FAILED 各不同因 | fixed: patch loop 耗尽（t2_ubiquitin r02）；lite: patch loop 耗尽（t2_ubiquitin r01, 36 次）；dynamic: IO_CLOSURE_BROKEN（t3_gb1 r01） |
| t2_ubiquitin（76aa 大蛋白）是主要压力点 | 在 2/4 组失败，是展示策略差异的最佳案例任务 |
| lite 的"预防性"优势 | lite 通过 runtime rerank 避免了进入 patch 状态（0 patch vs fixed 6 patch），而 fixed 在运行时才发现问题 |

v1 论文叙事框架：

- **成功率**：static_top1=100%，诚实表述，不以此作为 CEBRA-WP 主优势
- **恢复能力**：fixed_threshold_gate 的 6 次 patch 证明拦截-修复可用，但 loop 耗尽也暴露无 runtime rerank 的局限（必要性证据）
- **成本控制**：lite/dynamic 比 fixed 少 28.6% 高代价调用，比 static 少 5%（量化优势）
- **belief-state 价值**：lite 通过"预防性 rerank"避免触发 patch，而非在运行时拦截

完整分析：`docs/experiment/thesis-final-v1-results.md`

通过标准：

- 四组均能生成 run manifest。
- 每个 run 有 run_config、event_log_path、snapshot_path、report_path 或失败原因。
- 结果可聚合为 overall、difficulty-stratified、recovery/high-cost 三类表。

论文结论规则：

- 若 `lite_belief_state` 成功率最高，可以讨论成功率优势。
- 若它主要减少高代价调用或运行时间，应以“成本控制与运行时止损”为主结论。
- 若结果出现负例，应保留失败分析，不能删除对算法不利的结果。

### EXP-A3 静态规划必要性对照

目标：证明 CEBRA-WP 的存在必要性，即静态 Top-1 或静态门控在高代价、可失败流程中不够。

任务选择：

- T4 高代价结构预测。
- T5 可修复参数失败。
- T6 工具不可用/降级。
- T7 结构性失败。

对照组：

- `static_top1`
- `static_gate`
- `lite_belief_state`

重点指标：

- early_failure_rate
- high_cost_call_count
- wasted_call_rate
- recovery_success_rate
- terminal_stop_count

判定：

- 如果静态组在失败后更容易进入 FAILED 或产生更多无效高代价调用，则可证明“运行时调整有必要”。
- 如果静态组成功率更高但成本也更高，应写成“CEBRA-WP 提供成本/风险权衡”，而不是简单胜出。

### EXP-A4 belief-state 增量定向实验

目标：专门回答 `dynamic_observation_only` 与 `lite_belief_state` 的差异。这个实验是最终论文最应该补的算法实验，因为旧结果对此证据不足。

设计原则：

- 任务必须包含可影响决策的运行时观测。
- 任务不能只靠固定规则就能轻易判断。
- 至少包含一个候选在静态分较高但运行时风险升高，另一个候选静态分略低但恢复余量更好。

推荐任务场景：

| 场景 | 运行时观测 | 期望 CEBRA-WP 行为 |
|:---|:---|:---|
| 低 p_success + 高结构失败压力 | 上一步结构预测低置信或失败 | 降低 continue，提升 patch/replan |
| 高预算压力 + 低证据充分度 | 剩余预算不足且证据不充分 | 避免高代价调用，倾向 stop/replan |
| 高恢复余量 + 可局部修补 | 失败可由参数或工具替换修复 | 倾向 patch_local |
| 目标偏离 + 后缀可替换 | 前缀可保留，后缀风险高 | 倾向 suffix_replan |

对照组：

- `dynamic_observation_only`
- `lite_belief_state`

重点指标：

- rerank_delta_mean
- top1_changed_rate
- action_agreement
- high_cost_call_count
- stop_quality
- recovery_success_rate

通过标准：

- `dynamic_observation_only` 的 runtime adjustment 应为 0。
- `lite_belief_state` 应在至少部分任务中改变候选排序或动作推荐。
- 事件日志和候选 metadata 能解释改变原因。

### EXP-A5 典型案例分析

目标：用少量高质量案例支撑论文叙事，弥补纯表格难以说明机制的问题。

建议选择 3 个案例：

| 案例 | 目的 | 必备证据 |
|:---|:---|:---|
| C1 正常成功案例 | 展示系统主流程可用 | task JSON、report、timeline、UI 截图 |
| C2 局部失败恢复案例 | 展示 retry -> patch -> DONE | EventLog、PlanPatch、snapshot |
| C3 高风险止损/重规划案例 | 展示 CEBRA-WP 的运行时决策 | runtime_state、action_utility、rerank trace |

每个 case bundle 至少包含：

- run_config
- task JSON
- event log
- snapshot
- pending action / decision JSON
- report 或失败原因
- UI 截图
- 一段论文可用的案例解释

### EXP-A6 外部基线补充实验

目标：如果时间允许，引入外部基线说明系统不是只和自己对比。

可复用现有平台接入：

- Inspect AI
- MLflow
- promptfoo
- ReAct-style baseline

建议命令：

```bash
uv run python scripts/benchmarks/prepare_benchmark_platform_adapters.py \
  --config configs/experiments/benchmark_platform_adapters.json
```

注意：

- 外部基线不作为毕业论文必需项。
- 若 API key 或工具接入不稳定，保留为“补充实验”或“未来工作”。
- 不应让外部基线阻塞内部四组主实验。

## 9. 与 system-validation checklist 的映射

| checklist 范围 | 对应实验 | 说明 |
|:---|:---|:---|
| F01 任务输入与确认 | EXP-S2、EXP-S4 | API、Web、CLI 都要覆盖 |
| F02 计划生成 | EXP-S5、EXP-A1 | 候选结构和规划入口 |
| F03 HITL 人工确认 | EXP-S3、EXP-S4 | PendingAction 与 Decision |
| F04 FSM 生命周期控制 | EXP-S3、EXP-S7 | 状态合法性和恢复 |
| F05 工具链执行 | EXP-S5、EXP-S7 | StepResult、artifact、metrics |
| F06 安全评估 | EXP-S6 | warn/block 边界 |
| F07 失败恢复 | EXP-S7、EXP-A3 | retry、patch、replan |
| F08 快照恢复 | EXP-S3 | snapshot recovery |
| F09 结果总结 | EXP-S5、EXP-S4 | report API、CLI、UI |
| F10 审计与观测 | EXP-S3、EXP-A5 | EventLog、timeline、case bundle |

## 10. 证据目录建议

系统验证证据继续放在 `docs/system-validation/`，实验配置和论文实验设计放在 `docs/experiment/`。

建议结构：

```text
docs/experiment/
├── algorithm-group-paper-mapping.md
├── final-thesis-experiment-design.md
├── final-task-set-design.md
└── final-result-claim-boundary.md

docs/system-validation/
├── system-validation-checklist.md
├── final-validation-results.md
├── 00-environment/
├── 01-core-flows/
├── 02-hitl/
├── 03-exceptions-boundaries/
├── 04-data-consistency/
├── 05-api-results/
├── 06-ui-screenshots/
└── 07-test-runs/
```

算法运行产物建议放在：

```text
output/experiment/thesis-final-*/
```

但最终论文引用时，应在 `docs/experiment/` 或 `docs/system-validation/` 中保留一个 tracked manifest，记录 output、data/logs、data/snapshots 的路径和摘要。

## 11. 最小可交付实验包

如果时间紧，最低限度建议完成以下 6 项：

1. 运行 API / Web / CLI 系统验证，补充截图和 CLI 输出。 ✅ 已完成（2026-05-10）
2. 运行 FSM / HITL / recovery focused tests，保存 pytest log。 ✅ 已完成（2026-05-10）
3. 运行 CEBRA-WP 机制单测，证明四组 policy mode 可切换。 ✅ 已完成
4. 运行一次四组矩阵，哪怕任务数较少，也要保留 manifest 和 metrics。 ✅ 已完成 — t9 clean run（16/16）+ v1 正式矩阵（81/84 DONE，12 任务 × 4 组）
5. 专门补一次 `dynamic_observation_only` vs `lite_belief_state` 定向对照。 ⬜ 待执行 — v1 已包含两组 21 runs 对比数据，但缺定向任务设计
6. 打包 3 个典型案例：正常成功、局部失败恢复、高风险重规划或止损。 🔄 部分 — v1 提供 t2_ubiquitin lite r01（36 次 patch 循环）；其余待打包

最小包可以支撑的论文结论：

- 系统具备完整工程闭环。
- CEBRA-WP 机制已实现并可执行。
- CEBRA-WP 在运行时控制、失败恢复和高代价调用治理上具有必要性。
- 若未观察到成功率优势，应诚实表述为“成本/控制优势”，并在讨论中解释限制。

## 12. 推荐执行顺序

| 顺序 | 动作 | 输出 | 状态 |
|:---|:---|:---|:---|
| 1 | 冻结最终任务集和工具白名单 | `thesis_final_task_set.json`、配置 hash | ✅ 已完成 |
| 2 | 运行系统验证 focused tests | pytest logs | ✅ 已完成 |
| 3 | 启动 API，补 Web / CLI 手工证据 | 截图、CLI 输出、API JSON | ✅ 已完成 |
| 4 | 运行 CEBRA-WP 机制测试 | policy mode 和 runtime trace 证据 | ✅ 已完成 |
| 5 | 运行四组消融矩阵 | metrics CSV、matrix report | ✅ v1 正式矩阵完成（81/84 DONE）；完整分析见 `docs/experiment/thesis-final-v1-results.md` |
| 6 | 运行 belief-state 定向对照 | incremental value table | ⬜ 待执行 |
| 7 | 选择 3 个案例并打包证据 | case bundle | ⬜ 待执行 |
| 8 | 写 `final-result-claim-boundary.md` | 论文结果表述边界 | ⬜ 待执行 |

## 13. 论文图表产出

| 图表 | 来源实验 | 用途 |
|:---|:---|:---|
| 系统验证用例覆盖表 | EXP-S1 到 EXP-S7 | 证明软工测试充分性 |
| Web/CLI 操作截图 | EXP-S4 | 证明系统可用性 |
| 四组消融结果表 | EXP-A2 | 主算法结果 |
| 高代价调用对比柱状图 | EXP-A2、EXP-A3 | 证明成本控制 |
| 恢复成功率与 patch/replan 次数表 | EXP-A3 | 证明失败恢复能力 |
| rerank_delta 分布图 | EXP-A4 | 证明 belief-state 影响候选排序 |
| 典型案例事件时间线 | EXP-A5 | 解释算法闭环 |
| 结论边界表 | EXP-A2、EXP-A4 | 避免过强算法 claim |
