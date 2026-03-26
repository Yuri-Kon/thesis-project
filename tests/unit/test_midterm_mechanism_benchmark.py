from __future__ import annotations

from src.infra.midterm_mechanism_benchmark import (
    ScenarioResult,
    evaluate_signal,
    render_capability_coverage_svg,
    render_family_summary_svg,
    summarize_capabilities,
    summarize_families,
)


def test_evaluate_signal_waiting_chain_complete_and_done_transition() -> None:
    events = [
        {"seq": 1, "event_type": "WAITING_ENTER"},
        {"seq": 2, "event_type": "DECISION_APPLIED"},
        {"seq": 3, "event_type": "WAITING_EXIT"},
        {"seq": 4, "event_type": "STATE_TRANSITION", "to_status": "PATCHING"},
        {"seq": 5, "event_type": "STATE_TRANSITION", "to_status": "DONE"},
    ]

    assert evaluate_signal("waiting_chain_complete", events) is True
    assert evaluate_signal("patching_transition", events) is True
    assert evaluate_signal("done_transition", events) is True


def test_evaluate_signal_recovery_specific_checks() -> None:
    events = [
        {"seq": 1, "event_type": "REPLACE_TOOL"},
        {"seq": 2, "event_type": "RECOVERY_ESCALATED", "data": {"reason": "patch_failed"}},
        {"seq": 3, "event_type": "STEP_FAILED", "data": {"s6": {"action": "replan"}}},
    ]

    assert evaluate_signal("replace_tool_event", events) is True
    assert evaluate_signal("recovery_escalated_patch_failed", events) is True
    assert evaluate_signal("s6_replan_step_failed", events) is True


def test_family_and_capability_summaries_and_svg_rendering() -> None:
    results = [
        ScenarioResult(
            scenario_id="s1",
            label="Scenario 1",
            family="Recovery",
            runner="pytest",
            target="a",
            passed=True,
            duration_sec=1.2,
            capabilities=("patch_recovery", "tool_fallback"),
            artifacts_expected=1,
            artifacts_present=1,
            signals_expected=2,
            signals_passed=2,
            evidence_complete=True,
            stdout_path="stdout1",
            stderr_path="stderr1",
        ),
        ScenarioResult(
            scenario_id="s2",
            label="Scenario 2",
            family="HITL & Audit",
            runner="pytest",
            target="b",
            passed=True,
            duration_sec=2.5,
            capabilities=("event_audit", "hitl_decision"),
            artifacts_expected=0,
            artifacts_present=0,
            signals_expected=0,
            signals_passed=0,
            evidence_complete=True,
            stdout_path="stdout2",
            stderr_path="stderr2",
        ),
    ]

    family_rows = summarize_families(results)
    capability_rows = summarize_capabilities(results)

    assert [row["family"] for row in family_rows] == ["HITL & Audit", "Recovery"]
    assert any(row["capability"] == "patch_recovery" for row in capability_rows)

    family_svg = render_family_summary_svg(family_rows)
    capability_svg = render_capability_coverage_svg(capability_rows)
    assert "Midterm Mechanism Benchmark: Family Coverage" in family_svg
    assert "Validated Mechanism Coverage" in capability_svg
