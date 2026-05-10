import pytest

from src.models.contracts import PendingActionCandidate, Plan, PlanStep, ProteinDesignTask
from src.models.validation import (
    CandidateExecutionValidationError,
    validate_plan_executability,
)


def _task() -> ProteinDesignTask:
    return ProteinDesignTask(
        task_id="candidate_validation_task",
        goal="validate candidate executability",
        constraints={},
        metadata={},
    )


def _kg() -> dict[str, object]:
    return {
        "capabilities": [
            {"capability_id": "sequence_generation"},
            {"capability_id": "structure_prediction"},
        ],
        "io_types": [
            {"io_type_id": "goal_to_sequence"},
            {"io_type_id": "sequence_to_structure"},
        ],
        "tools": [
            {
                "id": "seq_tool",
                "capabilities": ["sequence_generation"],
                "io": {
                    "io_type_id": "goal_to_sequence",
                    "inputs": {"goal": "str"},
                    "outputs": {"sequence": "str"},
                },
                "execution": "python",
                "constraints": {"limits": {"max_length": 256}},
            },
            {
                "id": "fold_tool",
                "capabilities": ["structure_prediction"],
                "io": {
                    "io_type_id": "sequence_to_structure",
                    "inputs": {"sequence": "str"},
                    "outputs": {"pdb_path": "path"},
                },
                "execution": "nextflow",
                "constraints": {"limits": {"max_length": 1024}},
            },
        ],
    }


def _adapter_resolver(tool_id: str) -> object:
    if tool_id in {"seq_tool", "fold_tool"}:
        return object()
    raise KeyError(tool_id)


@pytest.mark.unit
def test_validate_plan_executability_rejects_missing_tool() -> None:
    task = _task()
    plan = Plan(
        task_id=task.task_id,
        steps=[
            PlanStep(
                id="S1",
                tool="missing_tool",
                inputs={"goal": task.goal},
                metadata={},
            )
        ],
        constraints={},
        metadata={},
    )

    with pytest.raises(CandidateExecutionValidationError) as exc_info:
        validate_plan_executability(
            plan,
            task,
            kg_loader=_kg,
            adapter_resolver=_adapter_resolver,
        )

    assert exc_info.value.issues
    assert exc_info.value.issues[0].code == "CANDIDATE_TOOL_UNAVAILABLE"


@pytest.mark.unit
def test_validate_plan_executability_rejects_broken_io_closure() -> None:
    task = _task()
    plan = Plan(
        task_id=task.task_id,
        steps=[
            PlanStep(
                id="S1",
                tool="seq_tool",
                inputs={"goal": task.goal},
                metadata={},
            ),
            PlanStep(
                id="S2",
                tool="fold_tool",
                inputs={"sequence": "S1.pdb_path"},
                metadata={},
            ),
        ],
        constraints={},
        metadata={},
    )

    with pytest.raises(CandidateExecutionValidationError) as exc_info:
        validate_plan_executability(
            plan,
            task,
            kg_loader=_kg,
            adapter_resolver=_adapter_resolver,
        )

    assert any(
        issue.code == "CANDIDATE_IO_CLOSURE_BROKEN" and issue.step_id == "S2"
        for issue in exc_info.value.issues
    )


@pytest.mark.unit
def test_validate_plan_executability_rejects_invalid_params() -> None:
    task = _task()
    plan = Plan(
        task_id=task.task_id,
        steps=[
            PlanStep(
                id="S1",
                tool="fold_tool",
                inputs={"sequence": 123},
                metadata={},
            )
        ],
        constraints={},
        metadata={},
    )

    with pytest.raises(CandidateExecutionValidationError) as exc_info:
        validate_plan_executability(
            plan,
            task,
            kg_loader=_kg,
            adapter_resolver=_adapter_resolver,
        )

    assert any(issue.code == "CANDIDATE_PARAMS_INVALID" for issue in exc_info.value.issues)


@pytest.mark.unit
def test_validate_plan_executability_reports_candidate_schema_and_io_boundary() -> None:
    task = _task()
    plan = Plan(
        task_id=task.task_id,
        steps=[
            PlanStep(
                id="S1",
                tool="seq_tool",
                inputs={"goal": task.goal},
                metadata={},
            ),
            PlanStep(
                id="S2",
                tool="fold_tool",
                inputs={"sequence": "S1.pdb_path"},
                metadata={},
            ),
        ],
        constraints={},
        metadata={},
    )
    candidate = PendingActionCandidate(
        candidate_id="bad_io_candidate",
        payload=plan,
        tool_id="fold_tool",
        capability_id="sequence_generation",
        io_type="goal_to_sequence",
        adapter_id="fold_tool",
    )

    with pytest.raises(CandidateExecutionValidationError) as exc_info:
        validate_plan_executability(
            plan,
            task,
            candidate=candidate,
            kg_loader=_kg,
            adapter_resolver=_adapter_resolver,
        )

    issues = exc_info.value.issues
    assert any(
        issue.code == "CANDIDATE_SCHEMA_INVALID"
        and issue.tool_id == "fold_tool"
        and issue.capability_id == "sequence_generation"
        and issue.io_type == "goal_to_sequence"
        for issue in issues
    )
    assert any(
        issue.code == "CANDIDATE_IO_CLOSURE_BROKEN"
        and issue.step_id == "S2"
        and issue.tool_id == "fold_tool"
        and issue.details == {"input_key": "sequence", "reference": "S1.pdb_path"}
        for issue in issues
    )
