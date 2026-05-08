from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.models.contracts import (
    PendingAction,
    PendingActionCandidate,
    PendingActionType,
    Plan,
    PlanPatch,
    PlanPatchOp,
    PlanStep,
    ProteinDesignTask,
)
from src.models.db import InternalStatus, TaskRecord, to_external_status
from src.workflow.context import WorkflowContext
from src.workflow.errors import FailureType, PlanRunError
from src.infra.thesis_experiment_matrix import (
    _auto_apply_waiting_decision,
    _apply_experiment_plan_overrides,
    _execute_matrix_run,
    build_issue221_run_manifest,
    evaluate_issue221_run_manifest,
    load_issue221_selection,
)
from src.infra.w12_vertical_experiment import stable_hash


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False))
            handle.write("\n")


def _make_plan(task_id: str) -> Plan:
    return Plan(
        task_id=task_id,
        steps=[PlanStep(id="S1", tool="dummy_tool", inputs={"sequence": "ACDE"}, metadata={})],
        constraints={},
        metadata={},
    )


def _make_record(task: ProteinDesignTask, status: InternalStatus) -> TaskRecord:
    return TaskRecord(
        id=task.task_id,
        status=to_external_status(status),
        internal_status=status,
        goal=task.goal,
        constraints=task.constraints,
        metadata=task.metadata,
        plan=None,
        design_result=None,
        safety_events=[],
    )


def test_auto_apply_waiting_decision_accepts_default_plan_candidate() -> None:
    task = ProteinDesignTask(task_id="task_auto_plan", goal="demo", constraints={}, metadata={})
    plan = _make_plan(task.task_id)
    pending_action = PendingAction(
        pending_action_id="pa_auto_plan",
        task_id=task.task_id,
        action_type=PendingActionType.PLAN_CONFIRM,
        candidates=[PendingActionCandidate(candidate_id="plan_a", payload=plan)],
        default_recommendation="plan_a",
        explanation="auto plan",
    )
    context = WorkflowContext(
        task=task,
        status=InternalStatus.WAITING_PLAN_CONFIRM,
        pending_action=pending_action,
    )
    record = _make_record(task, InternalStatus.WAITING_PLAN_CONFIRM)
    record.pending_action = pending_action

    _auto_apply_waiting_decision(task=task, context=context, record=record)

    assert context.status == InternalStatus.PLANNED
    assert context.plan is not None
    assert context.plan.task_id == task.task_id


def test_auto_apply_waiting_decision_uses_continue_for_replan_without_candidate() -> None:
    task = ProteinDesignTask(task_id="task_auto_replan", goal="demo", constraints={}, metadata={})
    pending_action = PendingAction(
        pending_action_id="pa_auto_replan",
        task_id=task.task_id,
        action_type=PendingActionType.REPLAN_CONFIRM,
        candidates=[],
        explanation="auto replan",
    )
    context = WorkflowContext(
        task=task,
        status=InternalStatus.WAITING_REPLAN,
        pending_action=pending_action,
    )
    record = _make_record(task, InternalStatus.WAITING_REPLAN)
    record.pending_action = pending_action

    _auto_apply_waiting_decision(task=task, context=context, record=record)

    assert context.status == InternalStatus.RUNNING


def test_auto_apply_waiting_decision_escalates_repeated_patch_to_replan() -> None:
    task = ProteinDesignTask(task_id="task_auto_patch_repeat", goal="demo", constraints={}, metadata={})
    patch = PlanPatch(
        task_id=task.task_id,
        operations=[
            PlanPatchOp(
                op="replace_step",
                target="S1",
                step=PlanStep(id="S1", tool="dummy_tool", inputs={"sequence": "ACDE"}, metadata={}),
            )
        ],
        metadata={},
    )
    pending_action = PendingAction(
        pending_action_id="pa_auto_patch_repeat",
        task_id=task.task_id,
        action_type=PendingActionType.PATCH_CONFIRM,
        candidates=[PendingActionCandidate(candidate_id="patch_repeat", payload=patch)],
        default_recommendation="patch_repeat",
        explanation="auto patch repeat",
    )
    plan = _make_plan(task.task_id)
    context = WorkflowContext(
        task=task,
        plan=plan,
        status=InternalStatus.WAITING_PATCH,
        pending_action=pending_action,
    )
    record = _make_record(task, InternalStatus.WAITING_PATCH)
    record.plan = plan
    record.pending_action = pending_action

    fingerprint = stable_hash(
        [
            pending_action.action_type.value,
            "patch_repeat",
            "",
            "",
        ]
    )

    _auto_apply_waiting_decision(
        task=task,
        context=context,
        record=record,
        decision_history={fingerprint: 1},
    )

    assert context.status == InternalStatus.WAITING_REPLAN


def test_auto_apply_waiting_decision_continues_repeated_replan_candidate() -> None:
    task = ProteinDesignTask(task_id="task_auto_replan_repeat", goal="demo", constraints={}, metadata={})
    plan = _make_plan(task.task_id)
    pending_action = PendingAction(
        pending_action_id="pa_auto_replan_repeat",
        task_id=task.task_id,
        action_type=PendingActionType.REPLAN_CONFIRM,
        candidates=[PendingActionCandidate(candidate_id="replan_repeat", payload=plan)],
        default_recommendation="replan_repeat",
        explanation="auto replan repeat",
    )
    context = WorkflowContext(
        task=task,
        plan=plan,
        status=InternalStatus.WAITING_REPLAN,
        pending_action=pending_action,
    )
    record = _make_record(task, InternalStatus.WAITING_REPLAN)
    record.plan = plan
    record.pending_action = pending_action

    fingerprint = stable_hash(
        [
            pending_action.action_type.value,
            "replan_repeat",
            "",
            "",
        ]
    )

    _auto_apply_waiting_decision(
        task=task,
        context=context,
        record=record,
        decision_history={fingerprint: 1},
    )

    assert context.status == InternalStatus.RUNNING


def test_apply_experiment_plan_overrides_rewrites_structure_step_to_openfold_rest() -> None:
    task_id = "task_override_openfold"
    plan = Plan(
        task_id=task_id,
        steps=[
            PlanStep(id="S1", tool="dummy_tool", inputs={"prompt": "demo"}, metadata={}),
            PlanStep(
                id="S2",
                tool="esmfold",
                inputs={"sequence": "S1.sequence"},
                metadata={"stage_id": "S2", "capability": "structure_prediction"},
            ),
        ],
        constraints={},
        metadata={},
    )

    rewritten = _apply_experiment_plan_overrides(
        plan=plan,
        task_constraints={
            "structure_prediction_tool_override": "openfold",
            "structure_prediction_execution_mode": "openfold3_rest",
        },
    )

    assert rewritten.steps[0].tool == "dummy_tool"
    assert rewritten.steps[1].tool == "openfold"
    assert rewritten.steps[1].inputs["execution_mode"] == "openfold3_rest"
    assert rewritten.steps[1].metadata["issue221_structure_override_applied"] is True
    assert rewritten.steps[1].metadata["issue221_structure_tool_original"] == "esmfold"


def test_apply_experiment_plan_overrides_rewrites_dssp_to_biopython_qc() -> None:
    plan = Plan(
        task_id="task_override_secondary_structure",
        steps=[
            PlanStep(
                id="S4",
                tool="dssp",
                inputs={"sequence": "S1.sequence", "pdb_path": "S2.pdb_path"},
                metadata={"capability": "secondary_structure_annotation"},
            )
        ],
        constraints={},
        metadata={},
    )

    rewritten = _apply_experiment_plan_overrides(
        plan=plan,
        task_constraints={
            "secondary_structure_annotation_tool_override": "biopython_qc",
        },
    )

    assert rewritten.steps[0].tool == "biopython_qc"
    assert rewritten.steps[0].metadata["issue221_secondary_structure_override_applied"] is True
    assert rewritten.steps[0].metadata["issue221_secondary_structure_tool_original"] == "dssp"


def test_apply_experiment_plan_overrides_keeps_plan_when_no_override_requested() -> None:
    plan = Plan(
        task_id="task_no_override",
        steps=[
            PlanStep(
                id="S2",
                tool="openfold",
                inputs={"sequence": "ACDE"},
                metadata={"capability": "structure_prediction"},
            )
        ],
        constraints={},
        metadata={},
    )

    rewritten = _apply_experiment_plan_overrides(plan=plan, task_constraints={})

    assert rewritten is plan


def test_issue221_run_manifest_materializes_run_configs_for_selected_subset(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    selection_path = tmp_path / "selection.json"
    selection_path.write_text(
        json.dumps(
            {
                "runs": [
                    {
                        "group_id": "lite_belief_state",
                        "task_key": "enzyme_like_fold",
                        "replicate": 1,
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    selection = load_issue221_selection(selection_path)

    manifest, run_dir = build_issue221_run_manifest(
        config={
            "issue_id": 221,
            "baseline_freeze_config_path": str(
                repo_root / "configs/experiments/baseline_experiment_contract.json"
            ),
            "output_root": str(tmp_path / "out"),
            "repeats": 2,
            "base_constraints": {"prefer_remote": False},
            "group_overrides": {
                "dynamic_no_belief_state": {
                    "supports_current_repo": True,
                    "implementation_status": "implemented",
                },
                "lite_belief_state": {
                    "supports_current_repo": True,
                    "implementation_status": "implemented",
                },
            },
        },
        config_path=repo_root / "configs/experiments/adaptive_strategy_experiment_matrix.json",
        output_root=tmp_path / "out",
        run_id="issue221-dry-run",
        dry_run=True,
        selection=selection,
    )

    assert manifest["freeze_id"] == "issue209-baseline-freeze-20260326"
    assert manifest["run_manifest_path"] == str(run_dir / "runs_manifest.json")
    assert len(manifest["runs"]) == 1
    run = manifest["runs"][0]
    assert run["group_id"] == "lite_belief_state"
    assert run["task_key"] == "enzyme_like_fold"
    assert run["status_external"] == "DRY_RUN"
    assert Path(run["run_config_path"]).exists()
    assert (run_dir / "runs_manifest.json").exists()
    assert (run_dir / "run_log_index.csv").exists()


def test_issue221_run_manifest_can_use_external_task_set_config(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    selection_path = tmp_path / "selection.json"
    selection_path.write_text(
        json.dumps(
            {
                "runs": [
                    {
                        "group_id": "lite_belief_state",
                        "task_key": "t2_trpcage_sequence_eval",
                        "replicate": 1,
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    selection = load_issue221_selection(selection_path)

    manifest, _run_dir = build_issue221_run_manifest(
        config={
            "issue_id": 221,
            "baseline_freeze_config_path": str(
                repo_root / "configs/experiments/baseline_experiment_contract.json"
            ),
            "task_set_config_path": str(
                repo_root / "configs/experiments/thesis_final_task_set.json"
            ),
            "output_root": str(tmp_path / "out"),
            "repeats": 1,
            "group_overrides": {
                "dynamic_no_belief_state": {
                    "supports_current_repo": True,
                    "implementation_status": "implemented",
                },
                "lite_belief_state": {
                    "supports_current_repo": True,
                    "implementation_status": "implemented",
                },
            },
        },
        config_path=repo_root / "configs/experiments/thesis_final_experiment_matrix.json",
        output_root=tmp_path / "out",
        run_id="thesis-final-dry-run",
        dry_run=True,
        selection=selection,
    )

    assert manifest["task_set_version"] == "thesis-final-v1"
    assert manifest["task_source"]["uses_baseline_freeze_tasks"] is False
    assert manifest["runs"][0]["task_key"] == "t2_trpcage_sequence_eval"

    run_config = json.loads(Path(manifest["runs"][0]["run_config_path"]).read_text())
    assert run_config["task"]["task_class"] == "T2"
    assert run_config["task"]["oracle_action"] == (
        "continue_when_structure_prediction_available"
    )
    assert run_config["constraints"]["goal_type"] == "sequence_evaluation"
    assert run_config["constraints"]["sequence"] == "NLYIQWLKDGGPSSGRPPPS"
    assert run_config["constraints"]["inputs"] == {
        "sequence": "NLYIQWLKDGGPSSGRPPPS"
    }
    assert run_config["lineage"]["task_source_config_path"].endswith(
        "configs/experiments/thesis_final_task_set.json"
    )


def test_issue221_evaluator_writes_rerun_candidates_and_traceability_outputs(
    tmp_path: Path,
) -> None:
    run_config_path = tmp_path / "run_configs" / "success.json"
    run_config_path.parent.mkdir(parents=True, exist_ok=True)
    run_config_path.write_text("{}", encoding="utf-8")

    log_path = tmp_path / "logs" / "success.jsonl"
    snapshot_path = tmp_path / "snapshots" / "success.jsonl"
    report_path = tmp_path / "reports" / "success.json"
    _write_jsonl(
        log_path,
        [
            {
                "event": "STEP_FINISHED",
                "task_id": "task_success",
                "step_id": "S2",
                "tool": "esmfold",
                "status": "success",
                "timestamp": "2026-04-16T12:00:01+00:00",
                "data": {
                    "action_name": "continue",
                    "shadow_action": "continue",
                },
            },
            {
                "event": "TASK_STATUS_CHANGED",
                "task_id": "task_success",
                "from_status": "SUMMARIZING",
                "to_status": "DONE",
                "timestamp": "2026-04-16T12:00:02+00:00",
            },
        ],
    )
    _write_jsonl(
        snapshot_path,
        [
            {
                "task_id": "task_success",
                "artifacts": {
                    "runtime_state": {"p_success": 0.71},
                    "decision_summary": {
                        "shadow_action": "continue",
                        "shadow_score": {"value": 0.83},
                    },
                },
            }
        ],
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("{}", encoding="utf-8")

    kg_path = tmp_path / "protein_tool_kg.json"
    kg_path.write_text(
        json.dumps(
            {
                "tools": [
                    {
                        "id": "esmfold",
                        "capabilities": ["structure_prediction"],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    manifest = {
        "issue_id": 221,
        "config_path": str(tmp_path / "runs_manifest_config.json"),
        "run_manifest_path": str(tmp_path / "actual_runs_manifest.json"),
        "freeze_id": "issue209-baseline-freeze-20260326",
        "high_cost_rules": [],
        "groups": [
            {"id": "static_top1"},
            {"id": "lite_belief_state"},
        ],
        "artifact_policy": {
            "all_runs_required": ["run_config_path", "event_log_path"],
            "success_runs_required": ["snapshot_path", "report_path"],
            "waiting_runs_required": ["snapshot_path"],
            "failed_runs_required": [],
        },
        "rerun_policy": {"max_attempts": 2},
        "runs": [
            {
                "run_id": "success_run",
                "task_id": "task_success",
                "task_key": "enzyme_like_fold",
                "group_id": "lite_belief_state",
                "replicate": 1,
                "attempt_number": 1,
                "freeze_id": "issue209-baseline-freeze-20260326",
                "task_set_version": "issue209-taskset-v1",
                "difficulty": "medium",
                "budget_tier": "standard",
                "runtime_policy": "lite_belief_state",
                "run_config_path": str(run_config_path),
                "event_log_path": str(log_path),
                "snapshot_path": str(snapshot_path),
                "report_path": str(report_path),
                "status_external": "DONE",
            },
            {
                "run_id": "failed_run",
                "task_id": "task_failed",
                "task_key": "binding_scaffold",
                "group_id": "static_top1",
                "replicate": 1,
                "attempt_number": 1,
                "freeze_id": "issue209-baseline-freeze-20260326",
                "task_set_version": "issue209-taskset-v1",
                "difficulty": "hard",
                "budget_tier": "high_cost_sensitive",
                "runtime_policy": "static_single_candidate",
                "run_config_path": "",
                "event_log_path": "",
                "snapshot_path": "",
                "report_path": "",
                "status_external": "FAILED",
            },
        ],
    }

    result = evaluate_issue221_run_manifest(
        manifest=manifest,
        output_dir=tmp_path / "evaluation",
        kg_path=kg_path,
        bootstrap_iterations=200,
        seed=7,
    )

    assert len(result["run_level_results"]) == 2
    success_row = next(
        row for row in result["run_level_results"] if row["run_id"] == "success_run"
    )
    assert success_row["artifact_complete"] is True
    assert success_row["action_continue_count"] == 1

    assert len(result["rerun_candidates"]) == 1
    candidate = result["rerun_candidates"][0]
    assert candidate["run_id"] == "failed_run"
    assert "status:FAILED" in candidate["reasons"]

    evaluation_dir = tmp_path / "evaluation"
    assert (evaluation_dir / "run_level_results.jsonl").exists()
    assert (evaluation_dir / "matrix_metrics_summary.csv").exists()
    assert (evaluation_dir / "rerun_selection.json").exists()
    assert (evaluation_dir / "evidence_index.json").exists()
    matrix_report = (evaluation_dir / "matrix_report.md").read_text(encoding="utf-8")
    assert "Four-Group Experiment Matrix Report" in matrix_report
    assert "Vertical Experiment Report (A0-A6)" not in matrix_report
    assert str(tmp_path / "actual_runs_manifest.json") in matrix_report
    assert str(tmp_path / "runs_manifest_config.json") in matrix_report


def test_execute_matrix_run_continues_after_waiting_replan_plan_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)

    class FakePlannerAgent:
        def plan_with_status(self, task, context, record=None):
            plan = _make_plan(task.task_id)
            context.status = InternalStatus.PLANNED
            if record is not None:
                record.plan = plan
                record.internal_status = InternalStatus.PLANNED
                record.status = to_external_status(InternalStatus.PLANNED)
            return plan

    class FakeExecutorAgent:
        instances: list["FakeExecutorAgent"] = []

        def __init__(self) -> None:
            self.run_calls = 0
            self.__class__.instances.append(self)

        def run_plan(
            self,
            plan,
            context,
            *,
            record=None,
            finalize_status=False,
            resume_from_existing=False,
        ):
            self.run_calls += 1
            if self.run_calls == 1:
                pending_action = PendingAction(
                    pending_action_id="pa_test_replan",
                    task_id=context.task.task_id,
                    action_type=PendingActionType.REPLAN_CONFIRM,
                    candidates=[],
                    explanation="test waiting replan",
                )
                context.pending_action = pending_action
                context.status = InternalStatus.WAITING_REPLAN
                if record is not None:
                    record.pending_action = pending_action
                    record.internal_status = InternalStatus.WAITING_REPLAN
                    record.status = to_external_status(InternalStatus.WAITING_REPLAN)
                raise PlanRunError(
                    failure_type=FailureType.NON_RETRYABLE,
                    message="test waiting replan",
                    step_id="S1",
                    code="TEST_WAITING_REPLAN",
                )

            assert resume_from_existing is True
            context.status = InternalStatus.RUNNING
            if record is not None:
                record.internal_status = InternalStatus.RUNNING
                record.status = to_external_status(InternalStatus.RUNNING)
            return plan

        def summarize_and_finalize(self, context, record, summarizer) -> None:
            context.status = InternalStatus.DONE
            if record is not None:
                record.internal_status = InternalStatus.DONE
                record.status = to_external_status(InternalStatus.DONE)

    class FakeSummarizerAgent:
        pass

    monkeypatch.setattr("src.adapters.builtins.ensure_builtin_adapters", lambda: None)
    monkeypatch.setattr("src.agents.planner.PlannerAgent", FakePlannerAgent)
    monkeypatch.setattr("src.agents.executor.ExecutorAgent", FakeExecutorAgent)
    monkeypatch.setattr("src.agents.summarizer.SummarizerAgent", FakeSummarizerAgent)

    result = _execute_matrix_run(
        task_id="task_waiting_replan_resume",
        goal="demo",
        constraints={},
        metadata={},
    )

    assert result[0] == "DONE"
    assert result[1] == "DONE"
    assert result[4] is None
    assert FakeExecutorAgent.instances[0].run_calls == 2

    log_path = tmp_path / "data/logs/task_waiting_replan_resume.jsonl"
    events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert any(event.get("event") == "DECISION_SUBMITTED" for event in events)
    assert any(event.get("event") == "DECISION_APPLIED" for event in events)
