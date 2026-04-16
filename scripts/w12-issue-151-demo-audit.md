# W12 Issue #151：端到端演示与审计回放操作手册

## 目标

提供可复现的演示链路与审计回放证据：

- 候选生成 -> HITL 决策 -> 执行恢复 -> 终态输出
- 审计链校验：`PendingAction -> Decision -> EventLog`
- 工具回退回放证据（`from_tool -> to_tool`）

## 标准输入

- `examples/w12_issue151/six_stage_waiting_patch_input.json`
- `examples/w12_issue151/tool_fallback_remote_to_local_input.json`

## 复现命令

```bash
uv run python scripts/run_w12_issue151_demo_audit.py
```

脚本会执行两个确定性集成场景：

1. `tests/integration/test_s6_control_layer_e2e.py::test_six_stage_waiting_patch_decision_replay_to_done`
2. `tests/integration/test_recovery_layered_patch.py::test_layered_patch_promotes_remote_to_local_tool_level`

## 输出产物

生成目录：`output/demo/w12-issue-151/`

- `release-validation.md`
- `demo-summary.json`
- `replay-record-001-six-stage-hitl.md`
- `replay-record-002-tool-fallback.md`
- `logs/int_s6_patch_decision_replay_done.jsonl`
- `logs/int_layered_patch_remote_to_local.jsonl`

## 预期检查项

- `audit_chain_pendingaction_decision_eventlog = PASS`
- `tool_fallback_switch_recorded = PASS`
- `e2e_flow_reaches_done = PASS`

## 排障

- 若回放日志缺失：
  - 先单独执行 `uv run pytest <target> -q` 确认用例通过
  - 确认测试后 `data/logs/<task_id>.jsonl` 存在
- 若环境存在旧日志污染：
  - 重新执行命令；每个场景会清理并重写任务日志
- 若本机无 `uv`：
  - 先安装/激活项目运行时后重试
