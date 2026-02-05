from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from src.models.db import ExternalStatus, InternalStatus
from src.models.event_log import ActorType, EventLog, EventType


def make_waiting_enter(
    task_id: str,
    pending_action_id: str,
    prev_status: ExternalStatus,
    new_status: ExternalStatus,
    waiting_state: str,
    actor_type: ActorType = ActorType.SYSTEM,
    actor_id: Optional[str] = None,
    internal_status: Optional[InternalStatus] = None,
    data: Optional[Dict[str, Any]] = None,
) -> EventLog:
    """创建 WAITING_ENTER 事件。

    Args:
        task_id: 任务 ID。
        pending_action_id: PendingAction ID。
        prev_status: 进入等待前的状态。
        new_status: 等待状态(必须是 WAITING_* 状态)。
        waiting_state: 等待状态的描述。
        actor_type: 参与者类型,默认为 system。
        actor_id: 参与者标识(可选)。
        internal_status: 内部状态(可选)。
        data: 额外的审计数据(可选)。

    Returns:
        EventLog: 已验证的 WAITING_ENTER 事件。
    """
    event_data = data.copy() if data else {}
    event_data["waiting_state"] = waiting_state

    return EventLog(
        id=str(uuid.uuid4()),
        task_id=task_id,
        event_type=EventType.WAITING_ENTER,
        actor_type=actor_type,
        actor_id=actor_id,
        prev_status=prev_status,
        new_status=new_status,
        internal_status=internal_status,
        pending_action_id=pending_action_id,
        data=event_data,
    )


def make_waiting_exit(
    task_id: str,
    prev_status: ExternalStatus,
    new_status: ExternalStatus,
    waiting_state: str,
    actor_type: ActorType = ActorType.SYSTEM,
    actor_id: Optional[str] = None,
    internal_status: Optional[InternalStatus] = None,
    pending_action_id: Optional[str] = None,
    decision_id: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
) -> EventLog:
    """创建 WAITING_EXIT 事件。

    Args:
        task_id: 任务 ID。
        prev_status: 等待状态(必须是 WAITING_* 状态)。
        new_status: 离开等待后的状态。
        waiting_state: 等待状态的描述。
        actor_type: 参与者类型,默认为 system。
        actor_id: 参与者标识(可选)。
        internal_status: 内部状态(可选)。
        pending_action_id: PendingAction ID(可选)。
        decision_id: Decision ID(可选)。
        data: 额外的审计数据(可选)。

    Returns:
        EventLog: 已验证的 WAITING_EXIT 事件。
    """
    event_data = data.copy() if data else {}
    event_data["waiting_state"] = waiting_state

    return EventLog(
        id=str(uuid.uuid4()),
        task_id=task_id,
        event_type=EventType.WAITING_EXIT,
        actor_type=actor_type,
        actor_id=actor_id,
        prev_status=prev_status,
        new_status=new_status,
        internal_status=internal_status,
        pending_action_id=pending_action_id,
        decision_id=decision_id,
        data=event_data,
    )


def make_decision_applied(
    task_id: str,
    decision_id: str,
    pending_action_id: str,
    prev_status: ExternalStatus,
    new_status: ExternalStatus,
    choice: str,
    actor_type: ActorType = ActorType.HUMAN,
    actor_id: Optional[str] = None,
    internal_status: Optional[InternalStatus] = None,
    data: Optional[Dict[str, Any]] = None,
) -> EventLog:
    """创建 DECISION_APPLIED 事件。

    Args:
        task_id: 任务 ID。
        decision_id: Decision ID。
        pending_action_id: PendingAction ID。
        prev_status: 决策前的状态(必须是 WAITING_* 状态)。
        new_status: 决策后的状态。
        choice: 决策选择。
        actor_type: 参与者类型,默认为 human。
        actor_id: 参与者标识(可选)。
        internal_status: 内部状态(可选)。
        data: 额外的审计数据(可选)。

    Returns:
        EventLog: 已验证的 DECISION_APPLIED 事件。
    """
    event_data = data.copy() if data else {}
    event_data["choice"] = choice

    return EventLog(
        id=str(uuid.uuid4()),
        task_id=task_id,
        event_type=EventType.DECISION_APPLIED,
        actor_type=actor_type,
        actor_id=actor_id,
        prev_status=prev_status,
        new_status=new_status,
        internal_status=internal_status,
        pending_action_id=pending_action_id,
        decision_id=decision_id,
        data=event_data,
    )
