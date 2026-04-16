# 回放记录：tool_fallback_remote_to_local

- Task ID：`int_layered_patch_remote_to_local`
- 来源测试：`tests/integration/test_recovery_layered_patch.py::test_layered_patch_promotes_remote_to_local_tool_level`
- 日志副本：`/home/yurikon/文档/thesis/thesis-project.dev/output/demo/w12-issue-151/logs/int_layered_patch_remote_to_local.jsonl`

## 事件序列

1. `PARAM_TWEAK` | ts=2026-03-19T15:40:10+00:00 | summary=PARAM_TWEAK
2. `REPLACE_TOOL` | ts=2026-03-19T15:40:10+00:00 | summary=REPLACE_TOOL
3. `STATE_TRANSITION` | ts=None | summary=RUNNING -> WAITING_PATCH
4. `STATE_TRANSITION` | ts=None | summary=WAITING_PATCH -> PATCHING

## 检查点

- 事件总数：`4`
- 包含 WAITING_ENTER：`False`
- 包含 DECISION_APPLIED：`False`
- 包含 WAITING_EXIT：`False`
- 包含 REPLACE_TOOL：`True`
