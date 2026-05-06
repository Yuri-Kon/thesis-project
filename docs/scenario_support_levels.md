# Scenario Support Levels

本项目的 Task Intake 使用三个场景支持等级：

- `P0`: supported。能力 readiness 会被记录和展示，但第一阶段不阻断正式 Task 创建。
- `P1`: experimental。必需 capability `unavailable` 时只保留 intake 草稿；必需 capability `degraded` 或可选 capability 非 `ready` 时允许创建，但写入 `scenario_gate.degraded` 元数据。
- `P2`: unsupported。任一必需 capability 非 `ready` 时拒绝正式 Task 创建，并返回 `scenario_gate.reject`。

`scenario_gate` 只是一份 intake-time 元数据，不新增或改写正式 Task FSM 状态。当前阶段不实现自动降级到 P0 子任务，也不裁剪 Planner 工具链。

## Capability Hint Contract

公共兼容字段仍为：

```json
"capability_hints": ["binding_design", "docking_scoring"]
```

结构化字段用于 readiness 和展示：

```json
"capability_hint_details": [
  {
    "name": "docking_scoring",
    "io_type": "structure_ligand_to_binding_score",
    "required": true,
    "degraded_message": "Docking scoring is required for binding design evaluation."
  }
]
```

`name` 对应 ToolKG `capabilities[].capability_id`；`io_type` 对应 ToolKG `io_types[].io_type_id` 或工具 `io.io_type_id`。

