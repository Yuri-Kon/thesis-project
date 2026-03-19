# 回放记录：six_stage_hitl_replay

- Task ID：`int_s6_patch_decision_replay_done`
- 来源测试：`tests/integration/test_s6_control_layer_e2e.py::test_six_stage_waiting_patch_decision_replay_to_done`
- 日志副本：`/home/yurikon/文档/thesis/thesis-project.dev/output/demo/w12-issue-151/logs/int_s6_patch_decision_replay_done.jsonl`

## 事件序列

1. `STEP_FINISHED` | ts=2026-03-19T15:40:07+00:00 | summary=Step finished (S1)
2. `STEP_FINISHED` | ts=2026-03-19T15:40:07+00:00 | summary=Step finished (S2)
3. `STEP_FINISHED` | ts=2026-03-19T15:40:07+00:00 | summary=Step finished (S3)
4. `STEP_FINISHED` | ts=2026-03-19T15:40:07+00:00 | summary=Step finished (S4)
5. `WAITING_ENTER` | ts=2026-03-19T15:40:08+00:00 | summary=Enter waiting state
6. `DECISION_APPLIED` | ts=2026-03-19T15:40:08+00:00 | summary=Decision applied (accept)
7. `WAITING_EXIT` | ts=2026-03-19T15:40:08+00:00 | summary=Exit waiting state
8. `STEP_FINISHED` | ts=2026-03-19T15:40:08+00:00 | summary=Step finished (S5)
9. `STATE_TRANSITION` | ts=None | summary=PLANNED -> RUNNING
10. `PENDING_ACTION_CREATED` | ts=None | summary=PendingAction created (patch_confirm)
11. `STATE_TRANSITION` | ts=None | summary=RUNNING -> WAITING_PATCH
12. `DECISION_SUBMITTED` | ts=None | summary=DECISION_SUBMITTED
13. `STATE_TRANSITION` | ts=None | summary=WAITING_PATCH -> PATCHING
14. `STATE_TRANSITION` | ts=None | summary=PATCHING -> RUNNING
15. `DECISION_APPLIED` | ts=None | summary=Decision applied (accept)
16. `STATE_TRANSITION` | ts=None | summary=RUNNING -> SUMMARIZING
17. `STATE_TRANSITION` | ts=None | summary=SUMMARIZING -> DONE

## 检查点

- 事件总数：`17`
- 包含 WAITING_ENTER：`True`
- 包含 DECISION_APPLIED：`True`
- 包含 WAITING_EXIT：`True`
- 包含 REPLACE_TOOL：`False`
