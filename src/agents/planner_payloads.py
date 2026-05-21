from __future__ import annotations

from collections.abc import Mapping


def build_candidate_generation_constraints(
    *,
    constraints: Mapping[str, object],
    metadata: Mapping[str, object] | None,
) -> dict[str, object]:
    """合成候选生成约束，隐藏 metadata/confirmed spec 的兼容合并细节。"""

    generation_constraints = dict(constraints)
    if not metadata:
        return generation_constraints

    generation_constraints["metadata"] = dict(metadata)
    confirmed = metadata.get("confirmed_task_spec")
    if isinstance(confirmed, dict):
        _ = generation_constraints.setdefault("confirmed_task_spec", dict(confirmed))
    hints = metadata.get("planner_capability_hints")
    if isinstance(hints, (list, tuple, set)):
        _ = generation_constraints.setdefault("capability_hints", list(hints))
    return generation_constraints
