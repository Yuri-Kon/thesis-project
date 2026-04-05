from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from src.models.contracts import ProteinDesignTask

__all__ = [
    "DYNAMIC_OBSERVATION_ONLY_POLICY",
    "LITE_BELIEF_STATE_POLICY",
    "resolve_runtime_policy",
    "runtime_policy_trace",
    "runtime_policy_uses_belief_state",
]

DYNAMIC_OBSERVATION_ONLY_POLICY = "dynamic_observation_only"
LITE_BELIEF_STATE_POLICY = "lite_belief_state"
_NO_BELIEF_STATE_POLICIES = frozenset(
    {
        DYNAMIC_OBSERVATION_ONLY_POLICY,
        "static_single_candidate",
        "static_threshold_gate",
        "none",
        "disabled",
        "off",
    }
)


def resolve_runtime_policy(
    task_or_constraints: ProteinDesignTask | Mapping[str, Any] | None,
) -> str:
    constraints = _extract_constraints(task_or_constraints)
    raw_value = constraints.get("runtime_policy")
    if not isinstance(raw_value, str):
        return LITE_BELIEF_STATE_POLICY
    normalized = raw_value.strip().lower()
    if not normalized:
        return LITE_BELIEF_STATE_POLICY
    return normalized


def runtime_policy_uses_belief_state(
    task_or_constraints: ProteinDesignTask | Mapping[str, Any] | None,
) -> bool:
    return resolve_runtime_policy(task_or_constraints) not in _NO_BELIEF_STATE_POLICIES


def runtime_policy_trace(
    task_or_constraints: ProteinDesignTask | Mapping[str, Any] | None,
) -> dict[str, Any]:
    policy = resolve_runtime_policy(task_or_constraints)
    return {
        "runtime_policy": policy,
        "belief_state_enabled": policy not in _NO_BELIEF_STATE_POLICIES,
    }


def _extract_constraints(
    task_or_constraints: ProteinDesignTask | Mapping[str, Any] | None,
) -> Mapping[str, Any]:
    if task_or_constraints is None:
        return {}
    if isinstance(task_or_constraints, ProteinDesignTask):
        return (
            task_or_constraints.constraints
            if isinstance(task_or_constraints.constraints, Mapping)
            else {}
        )
    if isinstance(task_or_constraints, Mapping):
        return task_or_constraints
    return {}
