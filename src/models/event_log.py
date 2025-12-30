from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from .db import ExternalStatus, InternalStatus


def now_iso() -> str:
    """Generate ISO8601 timestamp strings."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class EventType(str, Enum):
    """EventLog 事件类型枚举。"""

    WAITING_ENTER = "WAITING_ENTER"
    WAITING_EXIT = "WAITING_EXIT"
    DECISION_APPLIED = "DECISION_APPLIED"


class ActorType(str, Enum):
    """EventLog 参与者类型枚举。"""

    SYSTEM = "system"
    HUMAN = "human"
    API = "api"
    WORKFLOW = "workflow"


class EventLog(BaseModel):
    """EventLog 数据模型，用于记录 HITL 关键事件。

    每个 WAITING_* 转换必须记录:
    - 一个 WAITING_ENTER 事件(进入等待状态时)
    - 一个 WAITING_EXIT 事件(离开等待状态时)

    Attributes:
        id: 事件唯一标识。
        task_id: 关联的任务 ID。
        event_type: 事件类型。
        ts: 事件时间戳。
        actor_type: 参与者类型。
        actor_id: 参与者标识(可选)。
        prev_status: 事件发生前的外部状态(可选)。
        new_status: 事件发生后的外部状态(可选)。
        internal_status: 内部状态(可选)。
        pending_action_id: 关联的 PendingAction ID(可选)。
        decision_id: 关联的 Decision ID(可选)。
        data: 可扩展的审计/回放数据载荷。
    """

    id: str
    task_id: str
    event_type: EventType
    ts: str = Field(default_factory=now_iso)
    actor_type: ActorType
    actor_id: Optional[str] = None
    prev_status: Optional[ExternalStatus] = None
    new_status: Optional[ExternalStatus] = None
    internal_status: Optional[InternalStatus] = None
    pending_action_id: Optional[str] = None
    decision_id: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_event_constraints(self) -> EventLog:
        """根据事件类型验证必需字段和约束。"""
        if self.event_type == EventType.WAITING_ENTER:
            self._validate_waiting_enter()
        elif self.event_type == EventType.WAITING_EXIT:
            self._validate_waiting_exit()
        elif self.event_type == EventType.DECISION_APPLIED:
            self._validate_decision_applied()

        return self

    def _validate_waiting_enter(self) -> None:
        """验证 WAITING_ENTER 事件的约束。"""
        if not self.pending_action_id:
            raise ValueError("WAITING_ENTER requires pending_action_id")

        if "waiting_state" not in self.data:
            raise ValueError("WAITING_ENTER requires data.waiting_state")

        if not self.prev_status:
            raise ValueError("WAITING_ENTER requires prev_status")

        if not self.new_status:
            raise ValueError("WAITING_ENTER requires new_status")

        # new_status 必须是 WAITING_* 状态
        if not self.new_status.value.startswith("WAITING_"):
            raise ValueError(
                f"WAITING_ENTER requires new_status to be a WAITING_* state, "
                f"got {self.new_status.value}"
            )

    def _validate_waiting_exit(self) -> None:
        """验证 WAITING_EXIT 事件的约束。"""
        if "waiting_state" not in self.data:
            raise ValueError("WAITING_EXIT requires data.waiting_state")

        if not self.prev_status:
            raise ValueError("WAITING_EXIT requires prev_status")

        if not self.new_status:
            raise ValueError("WAITING_EXIT requires new_status")

        # prev_status 必须是 WAITING_* 状态
        if not self.prev_status.value.startswith("WAITING_"):
            raise ValueError(
                f"WAITING_EXIT requires prev_status to be a WAITING_* state, "
                f"got {self.prev_status.value}"
            )

    def _validate_decision_applied(self) -> None:
        """验证 DECISION_APPLIED 事件的约束。"""
        if not self.decision_id:
            raise ValueError("DECISION_APPLIED requires decision_id")

        if not self.pending_action_id:
            raise ValueError("DECISION_APPLIED requires pending_action_id")

        if "choice" not in self.data:
            raise ValueError("DECISION_APPLIED requires data.choice")

        if not self.prev_status:
            raise ValueError("DECISION_APPLIED requires prev_status")

        if not self.new_status:
            raise ValueError("DECISION_APPLIED requires new_status")

        # prev_status 必须是 WAITING_* 状态
        if not self.prev_status.value.startswith("WAITING_"):
            raise ValueError(
                f"DECISION_APPLIED requires prev_status to be a WAITING_* state, "
                f"got {self.prev_status.value}"
            )
