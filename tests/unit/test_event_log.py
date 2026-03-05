"""EventLog 模型和工厂函数单元测试"""
import pytest
from pydantic import ValidationError

from src.models.db import ExternalStatus, InternalStatus
from src.models.event_log import ActorType, EventLog, EventType
from src.infra.event_log_factory import (
    make_candidate_validation_failed,
    make_decision_applied,
    make_waiting_enter,
    make_waiting_exit,
)


@pytest.mark.unit
class TestEventLogValidation:
    """EventLog 验证规则测试类"""

    def test_waiting_enter_without_pending_action_id_fails(self):
        """WAITING_ENTER 缺少 pending_action_id 应该验证失败"""
        with pytest.raises(ValidationError, match="pending_action_id"):
            EventLog(
                id="evt_001",
                task_id="task_001",
                event_type=EventType.WAITING_ENTER,
                actor_type=ActorType.SYSTEM,
                prev_status=ExternalStatus.PLANNING,
                new_status=ExternalStatus.WAITING_PLAN_CONFIRM,
                data={"waiting_state": "plan_confirm"},
            )

    def test_waiting_enter_without_waiting_state_fails(self):
        """WAITING_ENTER 缺少 data.waiting_state 应该验证失败"""
        with pytest.raises(ValidationError, match="waiting_state"):
            EventLog(
                id="evt_002",
                task_id="task_001",
                event_type=EventType.WAITING_ENTER,
                actor_type=ActorType.SYSTEM,
                prev_status=ExternalStatus.PLANNING,
                new_status=ExternalStatus.WAITING_PLAN_CONFIRM,
                pending_action_id="pa_001",
                data={},
            )

    def test_waiting_enter_without_prev_status_fails(self):
        """WAITING_ENTER 缺少 prev_status 应该验证失败"""
        with pytest.raises(ValidationError, match="prev_status"):
            EventLog(
                id="evt_003",
                task_id="task_001",
                event_type=EventType.WAITING_ENTER,
                actor_type=ActorType.SYSTEM,
                new_status=ExternalStatus.WAITING_PLAN_CONFIRM,
                pending_action_id="pa_001",
                data={"waiting_state": "plan_confirm"},
            )

    def test_waiting_enter_without_new_status_fails(self):
        """WAITING_ENTER 缺少 new_status 应该验证失败"""
        with pytest.raises(ValidationError, match="new_status"):
            EventLog(
                id="evt_004",
                task_id="task_001",
                event_type=EventType.WAITING_ENTER,
                actor_type=ActorType.SYSTEM,
                prev_status=ExternalStatus.PLANNING,
                pending_action_id="pa_001",
                data={"waiting_state": "plan_confirm"},
            )

    def test_waiting_enter_with_non_waiting_new_status_fails(self):
        """WAITING_ENTER 的 new_status 不是 WAITING_* 状态应该验证失败"""
        with pytest.raises(ValidationError, match="WAITING_\\* state"):
            EventLog(
                id="evt_005",
                task_id="task_001",
                event_type=EventType.WAITING_ENTER,
                actor_type=ActorType.SYSTEM,
                prev_status=ExternalStatus.PLANNING,
                new_status=ExternalStatus.PLANNED,
                pending_action_id="pa_001",
                data={"waiting_state": "plan_confirm"},
            )

    def test_waiting_enter_valid(self):
        """有效的 WAITING_ENTER 事件应该通过验证"""
        event = EventLog(
            id="evt_006",
            task_id="task_001",
            event_type=EventType.WAITING_ENTER,
            actor_type=ActorType.SYSTEM,
            prev_status=ExternalStatus.PLANNING,
            new_status=ExternalStatus.WAITING_PLAN_CONFIRM,
            pending_action_id="pa_001",
            data={"waiting_state": "plan_confirm"},
        )

        assert event.id == "evt_006"
        assert event.task_id == "task_001"
        assert event.event_type == EventType.WAITING_ENTER
        assert event.pending_action_id == "pa_001"
        assert event.data["waiting_state"] == "plan_confirm"

    def test_waiting_exit_without_waiting_state_fails(self):
        """WAITING_EXIT 缺少 data.waiting_state 应该验证失败"""
        with pytest.raises(ValidationError, match="waiting_state"):
            EventLog(
                id="evt_007",
                task_id="task_001",
                event_type=EventType.WAITING_EXIT,
                actor_type=ActorType.SYSTEM,
                prev_status=ExternalStatus.WAITING_PLAN_CONFIRM,
                new_status=ExternalStatus.PLANNED,
                data={},
            )

    def test_waiting_exit_without_prev_status_fails(self):
        """WAITING_EXIT 缺少 prev_status 应该验证失败"""
        with pytest.raises(ValidationError, match="prev_status"):
            EventLog(
                id="evt_008",
                task_id="task_001",
                event_type=EventType.WAITING_EXIT,
                actor_type=ActorType.SYSTEM,
                new_status=ExternalStatus.PLANNED,
                data={"waiting_state": "plan_confirm"},
            )

    def test_waiting_exit_without_new_status_fails(self):
        """WAITING_EXIT 缺少 new_status 应该验证失败"""
        with pytest.raises(ValidationError, match="new_status"):
            EventLog(
                id="evt_009",
                task_id="task_001",
                event_type=EventType.WAITING_EXIT,
                actor_type=ActorType.SYSTEM,
                prev_status=ExternalStatus.WAITING_PLAN_CONFIRM,
                data={"waiting_state": "plan_confirm"},
            )

    def test_waiting_exit_with_non_waiting_prev_status_fails(self):
        """WAITING_EXIT 的 prev_status 不是 WAITING_* 状态应该验证失败"""
        with pytest.raises(ValidationError, match="WAITING_\\* state"):
            EventLog(
                id="evt_010",
                task_id="task_001",
                event_type=EventType.WAITING_EXIT,
                actor_type=ActorType.SYSTEM,
                prev_status=ExternalStatus.PLANNED,
                new_status=ExternalStatus.RUNNING,
                data={"waiting_state": "plan_confirm"},
            )

    def test_waiting_exit_valid(self):
        """有效的 WAITING_EXIT 事件应该通过验证"""
        event = EventLog(
            id="evt_011",
            task_id="task_001",
            event_type=EventType.WAITING_EXIT,
            actor_type=ActorType.HUMAN,
            prev_status=ExternalStatus.WAITING_PLAN_CONFIRM,
            new_status=ExternalStatus.PLANNED,
            data={"waiting_state": "plan_confirm"},
        )

        assert event.id == "evt_011"
        assert event.event_type == EventType.WAITING_EXIT
        assert event.prev_status == ExternalStatus.WAITING_PLAN_CONFIRM

    def test_decision_applied_without_decision_id_fails(self):
        """DECISION_APPLIED 缺少 decision_id 应该验证失败"""
        with pytest.raises(ValidationError, match="decision_id"):
            EventLog(
                id="evt_012",
                task_id="task_001",
                event_type=EventType.DECISION_APPLIED,
                actor_type=ActorType.HUMAN,
                prev_status=ExternalStatus.WAITING_PLAN_CONFIRM,
                new_status=ExternalStatus.PLANNED,
                pending_action_id="pa_001",
                data={"choice": "accept"},
            )

    def test_decision_applied_without_pending_action_id_fails(self):
        """DECISION_APPLIED 缺少 pending_action_id 应该验证失败"""
        with pytest.raises(ValidationError, match="pending_action_id"):
            EventLog(
                id="evt_013",
                task_id="task_001",
                event_type=EventType.DECISION_APPLIED,
                actor_type=ActorType.HUMAN,
                prev_status=ExternalStatus.WAITING_PLAN_CONFIRM,
                new_status=ExternalStatus.PLANNED,
                decision_id="dec_001",
                data={"choice": "accept"},
            )

    def test_decision_applied_without_choice_fails(self):
        """DECISION_APPLIED 缺少 data.choice 应该验证失败"""
        with pytest.raises(ValidationError, match="choice"):
            EventLog(
                id="evt_014",
                task_id="task_001",
                event_type=EventType.DECISION_APPLIED,
                actor_type=ActorType.HUMAN,
                prev_status=ExternalStatus.WAITING_PLAN_CONFIRM,
                new_status=ExternalStatus.PLANNED,
                decision_id="dec_001",
                pending_action_id="pa_001",
                data={},
            )

    def test_decision_applied_without_prev_status_fails(self):
        """DECISION_APPLIED 缺少 prev_status 应该验证失败"""
        with pytest.raises(ValidationError, match="prev_status"):
            EventLog(
                id="evt_015",
                task_id="task_001",
                event_type=EventType.DECISION_APPLIED,
                actor_type=ActorType.HUMAN,
                new_status=ExternalStatus.PLANNED,
                decision_id="dec_001",
                pending_action_id="pa_001",
                data={"choice": "accept"},
            )

    def test_decision_applied_without_new_status_fails(self):
        """DECISION_APPLIED 缺少 new_status 应该验证失败"""
        with pytest.raises(ValidationError, match="new_status"):
            EventLog(
                id="evt_016",
                task_id="task_001",
                event_type=EventType.DECISION_APPLIED,
                actor_type=ActorType.HUMAN,
                prev_status=ExternalStatus.WAITING_PLAN_CONFIRM,
                decision_id="dec_001",
                pending_action_id="pa_001",
                data={"choice": "accept"},
            )

    def test_decision_applied_with_non_waiting_prev_status_fails(self):
        """DECISION_APPLIED 的 prev_status 不是 WAITING_* 状态应该验证失败"""
        with pytest.raises(ValidationError, match="WAITING_\\* state"):
            EventLog(
                id="evt_017",
                task_id="task_001",
                event_type=EventType.DECISION_APPLIED,
                actor_type=ActorType.HUMAN,
                prev_status=ExternalStatus.PLANNED,
                new_status=ExternalStatus.RUNNING,
                decision_id="dec_001",
                pending_action_id="pa_001",
                data={"choice": "accept"},
            )

    def test_decision_applied_valid(self):
        """有效的 DECISION_APPLIED 事件应该通过验证"""
        event = EventLog(
            id="evt_018",
            task_id="task_001",
            event_type=EventType.DECISION_APPLIED,
            actor_type=ActorType.HUMAN,
            prev_status=ExternalStatus.WAITING_PLAN_CONFIRM,
            new_status=ExternalStatus.PLANNED,
            decision_id="dec_001",
            pending_action_id="pa_001",
            data={"choice": "accept"},
        )

        assert event.id == "evt_018"
        assert event.event_type == EventType.DECISION_APPLIED
        assert event.decision_id == "dec_001"
        assert event.pending_action_id == "pa_001"
        assert event.data["choice"] == "accept"

    def test_candidate_validation_failed_requires_failure_payload(self):
        """CANDIDATE_VALIDATION_FAILED 缺少 failure payload 应校验失败。"""
        with pytest.raises(ValidationError, match="failure_code"):
            EventLog(
                id="evt_019",
                task_id="task_001",
                event_type=EventType.CANDIDATE_VALIDATION_FAILED,
                actor_type=ActorType.WORKFLOW,
                data={"failures": []},
            )


@pytest.mark.unit
class TestEventLogFactoryHelpers:
    """EventLog 工厂辅助函数测试类"""

    def test_make_waiting_enter_creates_valid_event(self):
        """make_waiting_enter 应该创建有效的 WAITING_ENTER 事件"""
        event = make_waiting_enter(
            task_id="task_001",
            pending_action_id="pa_001",
            prev_status=ExternalStatus.PLANNING,
            new_status=ExternalStatus.WAITING_PLAN_CONFIRM,
            waiting_state="plan_confirm",
        )

        assert event.task_id == "task_001"
        assert event.event_type == EventType.WAITING_ENTER
        assert event.pending_action_id == "pa_001"
        assert event.prev_status == ExternalStatus.PLANNING
        assert event.new_status == ExternalStatus.WAITING_PLAN_CONFIRM
        assert event.data["waiting_state"] == "plan_confirm"
        assert event.actor_type == ActorType.SYSTEM

    def test_make_waiting_enter_with_optional_fields(self):
        """make_waiting_enter 应该正确处理可选字段"""
        event = make_waiting_enter(
            task_id="task_002",
            pending_action_id="pa_002",
            prev_status=ExternalStatus.RUNNING,
            new_status=ExternalStatus.WAITING_PATCH_CONFIRM,
            waiting_state="patch_confirm",
            actor_type=ActorType.WORKFLOW,
            actor_id="workflow_001",
            internal_status=InternalStatus.WAITING_PATCH,
            data={"extra_field": "extra_value"},
        )

        assert event.actor_type == ActorType.WORKFLOW
        assert event.actor_id == "workflow_001"
        assert event.internal_status == InternalStatus.WAITING_PATCH
        assert event.data["waiting_state"] == "patch_confirm"
        assert event.data["extra_field"] == "extra_value"

    def test_make_waiting_exit_creates_valid_event(self):
        """make_waiting_exit 应该创建有效的 WAITING_EXIT 事件"""
        event = make_waiting_exit(
            task_id="task_001",
            prev_status=ExternalStatus.WAITING_PLAN_CONFIRM,
            new_status=ExternalStatus.PLANNED,
            waiting_state="plan_confirm",
        )

        assert event.task_id == "task_001"
        assert event.event_type == EventType.WAITING_EXIT
        assert event.prev_status == ExternalStatus.WAITING_PLAN_CONFIRM
        assert event.new_status == ExternalStatus.PLANNED
        assert event.data["waiting_state"] == "plan_confirm"
        assert event.actor_type == ActorType.SYSTEM

    def test_make_decision_applied_creates_valid_event(self):
        """make_decision_applied 应该创建有效的 DECISION_APPLIED 事件"""
        event = make_decision_applied(
            task_id="task_001",
            decision_id="dec_001",
            pending_action_id="pa_001",
            prev_status=ExternalStatus.WAITING_PLAN_CONFIRM,
            new_status=ExternalStatus.PLANNED,
            choice="accept",
        )

        assert event.task_id == "task_001"
        assert event.event_type == EventType.DECISION_APPLIED
        assert event.decision_id == "dec_001"
        assert event.pending_action_id == "pa_001"
        assert event.prev_status == ExternalStatus.WAITING_PLAN_CONFIRM
        assert event.new_status == ExternalStatus.PLANNED
        assert event.data["choice"] == "accept"
        assert event.actor_type == ActorType.HUMAN

    def test_make_candidate_validation_failed_creates_valid_event(self):
        event = make_candidate_validation_failed(
            task_id="task_001",
            failure_code="CANDIDATE_TOOL_UNAVAILABLE",
            failures=[
                {
                    "code": "CANDIDATE_TOOL_UNAVAILABLE",
                    "message": "tool missing",
                    "step_id": "S1",
                }
            ],
        )

        assert event.task_id == "task_001"
        assert event.event_type == EventType.CANDIDATE_VALIDATION_FAILED
        assert event.data["failure_code"] == "CANDIDATE_TOOL_UNAVAILABLE"
        assert isinstance(event.data["failures"], list)


@pytest.mark.unit
class TestHITLReplayFragment:
    """HITL 回放片段测试：WAITING_ENTER → DECISION_APPLIED → WAITING_EXIT"""

    def test_valid_hitl_replay_fragment(self):
        """有效的 HITL 回放片段应该通过验证"""
        # 1. WAITING_ENTER: PLANNING → WAITING_PLAN_CONFIRM
        enter_event = make_waiting_enter(
            task_id="task_replay_001",
            pending_action_id="pa_replay_001",
            prev_status=ExternalStatus.PLANNING,
            new_status=ExternalStatus.WAITING_PLAN_CONFIRM,
            waiting_state="plan_confirm",
        )

        assert enter_event.event_type == EventType.WAITING_ENTER
        assert enter_event.new_status == ExternalStatus.WAITING_PLAN_CONFIRM
        assert enter_event.pending_action_id == "pa_replay_001"

        # 2. DECISION_APPLIED: 人工决策应用
        decision_event = make_decision_applied(
            task_id="task_replay_001",
            decision_id="dec_replay_001",
            pending_action_id="pa_replay_001",
            prev_status=ExternalStatus.WAITING_PLAN_CONFIRM,
            new_status=ExternalStatus.PLANNED,
            choice="accept",
            actor_id="user_001",
        )

        assert decision_event.event_type == EventType.DECISION_APPLIED
        assert decision_event.decision_id == "dec_replay_001"
        assert decision_event.prev_status == ExternalStatus.WAITING_PLAN_CONFIRM
        assert decision_event.new_status == ExternalStatus.PLANNED
        assert decision_event.data["choice"] == "accept"

        # 3. WAITING_EXIT: WAITING_PLAN_CONFIRM → PLANNED
        exit_event = make_waiting_exit(
            task_id="task_replay_001",
            prev_status=ExternalStatus.WAITING_PLAN_CONFIRM,
            new_status=ExternalStatus.PLANNED,
            waiting_state="plan_confirm",
            pending_action_id="pa_replay_001",
            decision_id="dec_replay_001",
        )

        assert exit_event.event_type == EventType.WAITING_EXIT
        assert exit_event.prev_status == ExternalStatus.WAITING_PLAN_CONFIRM
        assert exit_event.new_status == ExternalStatus.PLANNED

        # 验证事件序列的一致性
        assert enter_event.task_id == decision_event.task_id == exit_event.task_id
        assert enter_event.pending_action_id == decision_event.pending_action_id

    def test_valid_patch_confirm_replay_fragment(self):
        """有效的 Patch 确认回放片段"""
        task_id = "task_patch_001"
        pa_id = "pa_patch_001"
        dec_id = "dec_patch_001"

        # RUNNING → WAITING_PATCH_CONFIRM
        enter = make_waiting_enter(
            task_id=task_id,
            pending_action_id=pa_id,
            prev_status=ExternalStatus.RUNNING,
            new_status=ExternalStatus.WAITING_PATCH_CONFIRM,
            waiting_state="patch_confirm",
        )

        # 人工决策: accept
        decision = make_decision_applied(
            task_id=task_id,
            decision_id=dec_id,
            pending_action_id=pa_id,
            prev_status=ExternalStatus.WAITING_PATCH_CONFIRM,
            new_status=ExternalStatus.RUNNING,
            choice="accept",
        )

        # WAITING_PATCH_CONFIRM → RUNNING
        exit_evt = make_waiting_exit(
            task_id=task_id,
            prev_status=ExternalStatus.WAITING_PATCH_CONFIRM,
            new_status=ExternalStatus.RUNNING,
            waiting_state="patch_confirm",
            pending_action_id=pa_id,
            decision_id=dec_id,
        )

        assert enter.new_status == ExternalStatus.WAITING_PATCH_CONFIRM
        assert decision.prev_status == ExternalStatus.WAITING_PATCH_CONFIRM
        assert exit_evt.prev_status == ExternalStatus.WAITING_PATCH_CONFIRM
        assert exit_evt.new_status == ExternalStatus.RUNNING

    def test_valid_replan_confirm_replay_fragment(self):
        """有效的 Replan 确认回放片段"""
        task_id = "task_replan_001"
        pa_id = "pa_replan_001"
        dec_id = "dec_replan_001"

        # RUNNING → WAITING_REPLAN_CONFIRM
        enter = make_waiting_enter(
            task_id=task_id,
            pending_action_id=pa_id,
            prev_status=ExternalStatus.RUNNING,
            new_status=ExternalStatus.WAITING_REPLAN_CONFIRM,
            waiting_state="replan_confirm",
        )

        # 人工决策: accept
        decision = make_decision_applied(
            task_id=task_id,
            decision_id=dec_id,
            pending_action_id=pa_id,
            prev_status=ExternalStatus.WAITING_REPLAN_CONFIRM,
            new_status=ExternalStatus.PLANNING,
            choice="accept",
        )

        # WAITING_REPLAN_CONFIRM → PLANNING
        exit_evt = make_waiting_exit(
            task_id=task_id,
            prev_status=ExternalStatus.WAITING_REPLAN_CONFIRM,
            new_status=ExternalStatus.PLANNING,
            waiting_state="replan_confirm",
            pending_action_id=pa_id,
            decision_id=dec_id,
        )

        assert enter.new_status == ExternalStatus.WAITING_REPLAN_CONFIRM
        assert decision.prev_status == ExternalStatus.WAITING_REPLAN_CONFIRM
        assert exit_evt.prev_status == ExternalStatus.WAITING_REPLAN_CONFIRM
        assert exit_evt.new_status == ExternalStatus.PLANNING
