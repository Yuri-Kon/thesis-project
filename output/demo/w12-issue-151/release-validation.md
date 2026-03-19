# 发布验证（Issue #151）

## 范围

- 候选生成 -> HITL 决策 -> 执行恢复 -> 终态输出
- 审计回放链校验：`PendingAction -> Decision -> EventLog`
- 工具回退回放校验

## 命令集合

```bash
uv run pytest tests/integration/test_s6_control_layer_e2e.py::test_six_stage_waiting_patch_decision_replay_to_done -q
uv run pytest tests/integration/test_recovery_layered_patch.py::test_layered_patch_promotes_remote_to_local_tool_level -q
```

## 门禁结果

- audit_chain_pendingaction_decision_eventlog: PASS
- tool_fallback_switch_recorded: PASS
- e2e_flow_reaches_done: PASS

## 已知问题

- 演示场景由测试驱动并使用 mock runner；该回放证据包不依赖真实远端服务（NIM/Nextflow）。
- 事件顺序依赖时间戳 + 追加序列；跨进程写日志时应保证每个 task ID 仅单写者。