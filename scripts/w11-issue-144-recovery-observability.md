# W11 Issue #144：恢复链路可观测性增强

## 目标

增强恢复/审计可观测性，使训练样本抽取、审计对账与故障定位能够按任务维度与工具维度回放关键决策与恢复节点。

## 已交付范围

- 存储层时间线归一化已扩展恢复可观测字段。
- 时间线 API 端点支持用于回放视图的筛选参数。
- 恢复/决策事件写入补充了更完整的工具链与决策来源上下文。
- 新字段缺失时，旧日志仍可正常读取。

## 新增时间线字段

事件级归一化字段（可用时）：

- `tool_id`, `capability_id`, `io_type`, `adapter_mode`
- `from_tool`, `to_tool`
- `failure_type`, `failure_code`
- `candidate_id`, `decision_source`
- `recovery_layer`, `recovery_reason`

## API 查询扩展

`GET /tasks/{task_id}/events`

可选查询参数：

- `event_type`
- `tool_id`
- `capability_id`
- `adapter_mode`

示例：

```bash
curl "http://127.0.0.1:8000/tasks/<task_id>/events?tool_id=esmfold&adapter_mode=remote"
```

## 关键事件字段字典（恢复链路）

- 失败追踪：
  - `failure_type`, `failure_code`
- 候选与决策追踪：
  - `candidate_id`, `decision_source`
- 恢复层级追踪：
  - `recovery_layer`, `recovery_reason`
- 工具链追踪：
  - `tool_id`, `capability_id`, `io_type`, `adapter_mode`, `from_tool`, `to_tool`

## 兼容性说明

旧日志即使不包含上述字段，仍会被解析并返回；缺失字段以 `null` 表示。非严格模式下会跳过非法 JSON 行。

## 验证

- 单元测试：
  - `tests/unit/test_log_store_timeline.py`
- API 行为测试：
  - `tests/api/test_api_endpoints.py::TestTaskEndpoints::test_get_task_events_timeline_mapping_and_order`
- 集成保障测试：
  - `tests/integration/test_event_log_integration.py`
