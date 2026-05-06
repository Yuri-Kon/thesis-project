# Field Extension Governance

新增 Task Intake 字段或场景 profile 时按这个顺序落地：

1. 在 `TASK_FIELD_REGISTRY.fields` 注册字段，明确 `group`、`ui_control`、`validators`、`maps_to`、`support_level` 和 `audit_visibility`。
2. 在对应 `task_profiles` 中声明 `required`、`optional` 或 `conditional_required`。
3. 保持 `capability_hints` 为字符串兼容视图；如场景依赖工具能力，新增 `capability_hint_details`。
4. 确认每个 `capability_hint_details[].name` 能回链 ToolKG `capability_id`；如使用 `io_type`，确认 ToolKG 或工具节点存在相应 `io_type_id`。
5. 更新 Web/CLI/API 展示测试，确保 schema、ConfirmedTaskSpec metadata 和 TaskRecord metadata 来自同一份 registry。
6. 行为改变时优先添加 focused tests，再运行相关 `uv run pytest ...` 和 touched module 的 `basedpyright`。

不要把字段扩展和执行语义变更混在同一阶段。自动降级、工具链裁剪、确认边界变化都属于系统决策，需要单独设计和确认。

