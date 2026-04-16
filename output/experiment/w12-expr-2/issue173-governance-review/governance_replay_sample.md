# 治理回放样例

- task_id：`int_s6_patch_decision_replay_done`
- source_log：`/home/yurikon/文档/thesis/thesis-project.dev/output/demo/w12-issue-151/logs/int_s6_patch_decision_replay_done.jsonl`

## 事件轨迹

1. `STEP_FINISHED` | pending_action_id=None | decision_id=None
2. `STEP_FINISHED` | pending_action_id=None | decision_id=None
3. `STEP_FINISHED` | pending_action_id=None | decision_id=None
4. `STEP_FINISHED` | pending_action_id=None | decision_id=None
5. `WAITING_ENTER` | pending_action_id=pa_847db4ed | decision_id=None
6. `DECISION_APPLIED` | pending_action_id=pa_847db4ed | decision_id=decision_int_s6_patch_decision_replay_done
7. `WAITING_EXIT` | pending_action_id=pa_847db4ed | decision_id=None
8. `STEP_FINISHED` | pending_action_id=None | decision_id=None
9. `STATE_TRANSITION` | pending_action_id=None | decision_id=None
10. `PENDING_ACTION_CREATED` | pending_action_id=pa_847db4ed | decision_id=None
11. `STATE_TRANSITION` | pending_action_id=None | decision_id=None
12. `DECISION_SUBMITTED` | pending_action_id=pa_847db4ed | decision_id=decision_int_s6_patch_decision_replay_done
13. `STATE_TRANSITION` | pending_action_id=None | decision_id=None
14. `STATE_TRANSITION` | pending_action_id=None | decision_id=None
15. `DECISION_APPLIED` | pending_action_id=pa_847db4ed | decision_id=decision_int_s6_patch_decision_replay_done
16. `STATE_TRANSITION` | pending_action_id=None | decision_id=None
17. `STATE_TRANSITION` | pending_action_id=None | decision_id=None
