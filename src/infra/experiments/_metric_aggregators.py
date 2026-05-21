from __future__ import annotations

from collections import defaultdict
from typing import Callable


def group_runs_by_order(
    runs: list[dict[str, object]],
    *,
    group_order: list[str],
    canonicalize_group_id: Callable[[object], str],
) -> dict[str, list[dict[str, object]]]:
    """按 canonical group 聚合 run，保留原有 group_id 回退语义。"""

    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    group_order_set = set(group_order)
    for row in runs:
        group_id = row.get("group_id")
        canonical_group_id = row.get("canonical_group_id") or canonicalize_group_id(group_id)
        if isinstance(canonical_group_id, str) and canonical_group_id in group_order_set:
            grouped[canonical_group_id].append(row)
        elif isinstance(group_id, str):
            grouped[group_id].append(row)
    return dict(grouped)


def build_threshold_gate_checks(
    *,
    summary_row: dict[str, object],
    thresholds: dict[str, float],
) -> list[dict[str, object]]:
    """为组级 summary 生成门禁检查，保留特殊等值阈值规则。"""

    gate_checks: list[dict[str, object]] = []
    for metric_name, threshold in thresholds.items():
        value = summary_row.get(metric_name)
        passed = isinstance(value, (int, float)) and value >= threshold
        if metric_name == "suffix_replan_prefix_preservation_rate":
            passed = isinstance(value, (int, float)) and abs(float(value) - threshold) < 1e-9
        if value is None:
            passed = False
        gate_checks.append(
            {
                "metric": metric_name,
                "threshold": threshold,
                "value": value,
                "passed": passed,
                "reason": None if passed else ("missing_value" if value is None else "below_threshold"),
            }
        )
    return gate_checks
