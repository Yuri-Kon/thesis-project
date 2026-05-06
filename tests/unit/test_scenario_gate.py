from __future__ import annotations

from src.infra.scenario_gate import evaluate_scenario_gate
from src.infra.tool_readiness import batch_check_capability_hints
from src.models.task_intake import CapabilityHint


def test_batch_check_capability_hints_applies_effective_tool_filters() -> None:
    """tools_allowed 应参与 capability 的 effective readiness。"""

    hints: list[CapabilityHint] = [
        {
            "name": "objective_scoring",
            "io_type": "candidates_to_objective_scores_topk",
            "required": True,
        }
    ]

    readiness = batch_check_capability_hints(
        hints,
        tools_allowed=["esmfold"],
    )

    snapshot = readiness["objective_scoring:candidates_to_objective_scores_topk"]
    assert snapshot["status"] == "unavailable"
    assert "allowed tool filter" in snapshot["reason"]
    assert snapshot["effective_filters"]["tools_allowed"] == ["esmfold"]


def test_scenario_gate_p0_allows_unavailable_capability() -> None:
    """P0 不阻断正式创建，但仍携带 readiness 元数据。"""

    hints: list[CapabilityHint] = [
        {"name": "missing_capability_for_p0", "required": True}
    ]

    gate = evaluate_scenario_gate(support_level="P0", capability_hints=hints)

    assert gate["status"] == "allow"
    assert gate["blocked_hints"] == ["missing_capability_for_p0"]


def test_scenario_gate_p1_required_unavailable_becomes_draft_only() -> None:
    """P1 必需能力不可用时只能保留草稿。"""

    hints: list[CapabilityHint] = [
        {"name": "motif_scaffolding", "required": True}
    ]

    gate = evaluate_scenario_gate(support_level="P1", capability_hints=hints)

    assert gate["status"] == "draft_only"
    assert gate["blocked_hints"] == ["motif_scaffolding"]


def test_scenario_gate_p1_optional_unavailable_is_degraded() -> None:
    """P1 非必需能力不可用只生成降级提示。"""

    hints: list[CapabilityHint] = [
        {"name": "objective_scoring", "required": True},
        {"name": "missing_optional_capability", "required": False},
    ]

    gate = evaluate_scenario_gate(support_level="P1", capability_hints=hints)

    assert gate["status"] == "degraded"
    assert gate["blocked_hints"] == []
    assert gate["degraded_hints"] == ["missing_optional_capability"]


def test_scenario_gate_p2_required_degraded_or_unavailable_rejects() -> None:
    """P2 只要必需能力非 ready 就拒绝正式创建。"""

    hints: list[CapabilityHint] = [
        {"name": "binding_design", "required": True}
    ]

    gate = evaluate_scenario_gate(support_level="P2", capability_hints=hints)

    assert gate["status"] == "reject"
    assert gate["blocked_hints"] == ["binding_design"]

