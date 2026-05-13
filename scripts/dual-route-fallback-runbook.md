# Dual Route Fallback Runbook

## 目标

在不改变 FSM/HITL 决策边界的前提下，引入运行时安全的双路策略（`本地默认 + 外部回退`）。

## 已交付范围

- 在 provider 层实现双路路由与阈值触发。
- 默认保持外部回退保障开启。
- 提供一键熔断：
  - 运行时配置：`runtime_fallback.force_external_only=true`
  - 环境变量：`PLANNER_FORCE_EXTERNAL_FALLBACK=1`
- 路由决策审计事件包含必需字段：
  - `from_tool`, `to_tool`, `capability_id`, `trigger_threshold`
- 集成测试覆盖触发与恢复路径。

## 触发条件

满足任一条件时，路由可切换到外部 provider：

1. `schema_fail_streak >= schema_fail_threshold`
2. `candidate_executable_rate < executable_rate_threshold`
3. `candidate_executable_drop >= executable_drop_threshold`
4. `consecutive_execution_failures >= consecutive_failure_threshold`
5. `sustained_high_risk >= sustained_high_risk_threshold`

## 配置

参考配置：

- `configs/runtime/dual_route_fallback.json`

任务级覆盖示例（`task.constraints.runtime_fallback`）：

```json
{
  "runtime_fallback": {
    "enable_dual_route": true,
    "force_external_only": false,
    "schema_fail_threshold": 2,
    "executable_rate_threshold": 0.95,
    "executable_drop_threshold": 0.05,
    "consecutive_failure_threshold": 2,
    "sustained_high_risk_threshold": 2,
    "fallback_capability": "planner_generation"
  }
}
```

## 可观测性

路由决策事件 `PLANNER_ROUTE_DECISION` 输出：

- 顶层字段：`from_tool`, `to_tool`, `capability_id`
- `data.trigger_reason`
- `data.trigger_threshold`

## 验证

```bash
uv run pytest \
  tests/integration/test_planner_dual_route_fallback.py \
  tests/unit/test_log_store_timeline.py \
  tests/unit/test_planner_with_provider.py -q
```
