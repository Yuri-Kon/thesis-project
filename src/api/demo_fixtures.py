from __future__ import annotations

import json
from collections.abc import MutableMapping
from pathlib import Path
from typing import Literal

from src.models.contracts import (
    DEFAULT_RECOMMENDATION_REASON_METADATA_KEY,
    RUNTIME_STATE_SUMMARY_METADATA_KEY,
    TOOL_READINESS_METADATA_KEY,
    WAITING_RUNTIME_SUMMARY_METADATA_KEY,
    DesignResult,
    PendingAction,
    PendingActionCandidate,
    PendingActionStatus,
    PendingActionType,
    Plan,
    PlanPatch,
    PlanPatchOp,
    PlanStep,
    RiskFlag,
    now_iso,
)
from src.models.db import ExternalStatus, InternalStatus, JsonObject, JsonValue, TaskRecord
from src.storage.log_store import append_event

DEMO_FIXTURE_SOURCE = "defense_demo_fixture"
DEMO_OUTPUT_SUBDIR = Path("demo") / "defense-full-flow"
DEMO_INTAKE_TASK_ID = "demo_defense_intake"
DEMO_HITL_TASK_ID = "demo_defense_hitl"
DEMO_DONE_TASK_ID = "demo_defense_done"
DEMO_PENDING_ACTION_ID = "pa_demo_defense_patch"


def seed_defense_full_flow_demo(
    task_store: MutableMapping[str, TaskRecord],
    *,
    output_dir: Path,
    log_dir: Path,
) -> dict[str, JsonValue]:
    """创建答辩本地演示 fixture。

    Args:
        task_store: API 进程内任务存储。
        output_dir: 运行时输出根目录。
        log_dir: 运行时事件日志目录。

    Returns:
        演示任务、URL 与产物路径清单。
    """

    artifact_dir = output_dir / DEMO_OUTPUT_SUBDIR
    screenshots_dir = artifact_dir / "screenshots"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    pdb_path = artifact_dir / "demo_defense_done.pdb"
    report_path = artifact_dir / "demo_defense_done_report.json"
    manifest_path = artifact_dir / "demo_defense_manifest.json"

    _ = pdb_path.write_text(_demo_structure_pdb_text(), encoding="utf-8")

    created_at = now_iso()
    runtime_summary = _runtime_state_summary()
    objective_scoring = _objective_scoring()
    structure_similarity = _structure_similarity()

    records = {
        DEMO_INTAKE_TASK_ID: _build_intake_record(created_at=created_at),
        DEMO_HITL_TASK_ID: _build_hitl_record(
            created_at=created_at,
            runtime_summary=runtime_summary,
        ),
        DEMO_DONE_TASK_ID: _build_done_record(
            created_at=created_at,
            pdb_path=pdb_path,
            report_path=report_path,
            objective_scoring=objective_scoring,
            structure_similarity=structure_similarity,
        ),
    }
    task_store.update(records)

    report_payload: dict[str, JsonValue] = {
        "task_id": DEMO_DONE_TASK_ID,
        "source": DEMO_FIXTURE_SOURCE,
        "sequence": "NLYIQWLKDGGPSSGRPPPS",
        "structure_pdb_path": str(pdb_path),
        "scores": {
            "plddt_mean": 88.2,
            "stability_proxy": 0.81,
            "sequence_length": 20,
            "qc_pass": True,
        },
        "objective_scoring": objective_scoring,
        "structure_similarity": structure_similarity,
    }
    _ = report_path.write_text(
        json.dumps(report_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    _write_demo_events(log_dir=log_dir, runtime_summary=runtime_summary)

    manifest = _build_manifest(
        pdb_path=pdb_path,
        report_path=report_path,
        manifest_path=manifest_path,
        screenshots_dir=screenshots_dir,
    )
    _ = manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest


def _build_manifest(
    *,
    pdb_path: Path,
    report_path: Path,
    manifest_path: Path,
    screenshots_dir: Path,
) -> dict[str, JsonValue]:
    screenshot_paths: JsonObject = {
        "dashboard": str(screenshots_dir / "dashboard.png"),
        "task_builder": str(screenshots_dir / "task_builder.png"),
        "hitl_candidates": str(screenshots_dir / "hitl_candidates.png"),
        "structure_viewer": str(screenshots_dir / "structure_viewer.png"),
        "event_timeline": str(screenshots_dir / "event_timeline.png"),
    }
    return {
        "source": DEMO_FIXTURE_SOURCE,
        "tasks": {
            "intake": DEMO_INTAKE_TASK_ID,
            "hitl": DEMO_HITL_TASK_ID,
            "done": DEMO_DONE_TASK_ID,
        },
        "urls": {
            "dashboard": "/ui",
            "task_builder": "/ui/task-builder",
            "hitl_task": f"/ui/tasks/{DEMO_HITL_TASK_ID}",
            "done_task": f"/ui/tasks/{DEMO_DONE_TASK_ID}",
            "done_events": f"/ui/tasks/{DEMO_DONE_TASK_ID}/events",
            "structure": f"/tasks/{DEMO_DONE_TASK_ID}/structure",
        },
        "artifacts": {
            "pdb": str(pdb_path),
            "report": str(report_path),
            "manifest": str(manifest_path),
            "screenshots_dir": str(screenshots_dir),
            "screenshots": screenshot_paths,
        },
        "notes": [
            "Local deterministic fixture; no LLM or remote model service is called.",
            "PDB and report artifacts are for UI and audit-chain demonstration only.",
        ],
    }


def _build_intake_record(*, created_at: str) -> TaskRecord:
    return TaskRecord(
        id=DEMO_INTAKE_TASK_ID,
        status=ExternalStatus.DONE,
        internal_status=InternalStatus.DONE,
        created_at=created_at,
        updated_at=created_at,
        goal=(
            "Evaluate a TRP-cage-like peptide sequence under a low-cost "
            "structure-first workflow, compare candidate tools, and generate "
            "a structure report."
        ),
        constraints=_demo_constraints(),
        metadata={
            "source": DEMO_FIXTURE_SOURCE,
            "fixture_role": "input_intake",
            "free_text_input": (
                "请评估一个 TRP-cage-like 短肽序列的稳定性，优先使用低成本结构预测路径，"
                "并在高代价步骤前展示候选方案给人工确认。"
            ),
            "extracted_fields": {
                "sequence": "NLYIQWLKDGGPSSGRPPPS",
                "objective_type": "stability",
                "budget_policy": "low_cost_first",
                "runtime_policy": "lite_belief_state",
            },
            "confirmed_task_spec": {
                "confirmed_by": "demo_operator",
                "confirmed_at": created_at,
            },
        },
        plan=_build_plan(DEMO_INTAKE_TASK_ID),
        design_result=DesignResult(
            task_id=DEMO_INTAKE_TASK_ID,
            sequence="NLYIQWLKDGGPSSGRPPPS",
            structure_pdb_path=None,
            scores={"intake_fields_confirmed": True},
            risk_flags=[],
            report_path="output/demo/defense-full-flow/demo_defense_intake.json",
            metadata={"source": DEMO_FIXTURE_SOURCE},
        ),
    )


def _build_hitl_record(
    *,
    created_at: str,
    runtime_summary: JsonObject,
) -> TaskRecord:
    pending_action = PendingAction(
        pending_action_id=DEMO_PENDING_ACTION_ID,
        task_id=DEMO_HITL_TASK_ID,
        action_type=PendingActionType.PATCH_CONFIRM,
        status=PendingActionStatus.PENDING,
        candidates=_build_candidates(DEMO_HITL_TASK_ID, runtime_summary),
        explanation=(
            "Remote structure service is degraded before a high-cost step; "
            "compare patch candidates before resuming execution."
        ),
        default_recommendation="patch_local_openfold",
        created_at=created_at,
        metadata={
            "source": DEMO_FIXTURE_SOURCE,
            "workflow_action_reason": (
                "Budget pressure and degraded remote readiness make local patch preferable."
            ),
            WAITING_RUNTIME_SUMMARY_METADATA_KEY: {
                "selected_candidate_id": "patch_local_openfold",
                "default_recommendation": "patch_local_openfold",
                "waiting_reason": "remote_structure_service_degraded",
                RUNTIME_STATE_SUMMARY_METADATA_KEY: runtime_summary,
                DEFAULT_RECOMMENDATION_REASON_METADATA_KEY: {
                    "code": "budget_aware_local_patch",
                    "message": (
                        "Local patch keeps the workflow recoverable while avoiding a degraded "
                        "remote high-cost call."
                    ),
                    "selection_basis": "final_score",
                    "rerank_applied": True,
                    "static_candidate_id": "patch_remote_retry",
                    "static_score_gap": 0.15,
                    "shadow_candidate_id": "patch_local_openfold",
                    "shadow_score_gap": 0.08,
                    "shadow_only": False,
                },
                "final_score": {
                    "value": 0.86,
                    "source": "defense_demo_fixture.candidate_rerank",
                    "source_refs": ["demo_defense_hitl"],
                },
            },
            "evidence_refs": [
                {
                    "type": "event_log",
                    "path": f"data/logs/{DEMO_HITL_TASK_ID}.jsonl",
                }
            ],
        },
    )
    return TaskRecord(
        id=DEMO_HITL_TASK_ID,
        status=ExternalStatus.WAITING_PATCH_CONFIRM,
        internal_status=InternalStatus.WAITING_PATCH,
        created_at=created_at,
        updated_at=created_at,
        goal="Defense demo: HITL patch candidate comparison before structure prediction",
        constraints=_demo_constraints(),
        metadata={"source": DEMO_FIXTURE_SOURCE, "fixture_role": "hitl_patch_confirm"},
        plan=_build_plan(DEMO_HITL_TASK_ID),
        pending_action=pending_action,
    )


def _build_done_record(
    *,
    created_at: str,
    pdb_path: Path,
    report_path: Path,
    objective_scoring: JsonObject,
    structure_similarity: JsonObject,
) -> TaskRecord:
    return TaskRecord(
        id=DEMO_DONE_TASK_ID,
        status=ExternalStatus.DONE,
        internal_status=InternalStatus.DONE,
        created_at=created_at,
        updated_at=created_at,
        goal="Defense demo: completed local fixture with report and structure viewer artifact",
        constraints=_demo_constraints(),
        metadata={"source": DEMO_FIXTURE_SOURCE, "fixture_role": "done_replay"},
        plan=_build_plan(DEMO_DONE_TASK_ID),
        design_result=DesignResult(
            task_id=DEMO_DONE_TASK_ID,
            sequence="NLYIQWLKDGGPSSGRPPPS",
            structure_pdb_path=str(pdb_path),
            scores={
                "plddt_mean": 88.2,
                "stability_proxy": 0.81,
                "sequence_length": 20,
                "qc_pass": True,
            },
            risk_flags=[
                RiskFlag(
                    level="warn",
                    code="demo_fixture",
                    message=(
                        "This structure is a deterministic demo artifact, "
                        "not remote model output."
                    ),
                    scope="output",
                )
            ],
            report_path=str(report_path),
            metadata={
                "source": DEMO_FIXTURE_SOURCE,
                "objective_scoring": objective_scoring,
                "structure_similarity": structure_similarity,
            },
        ),
    )


def _demo_constraints() -> JsonObject:
    return {
        "task_kind": "sequence_evaluation",
        "objective_type": "stability",
        "sequence": "NLYIQWLKDGGPSSGRPPPS",
        "length_range": [18, 32],
        "budget_policy": "low_cost_first",
        "runtime_policy": "lite_belief_state",
        "requires_human_review": True,
        "prefer_remote": False,
    }


def _build_plan(task_id: str) -> Plan:
    return Plan(
        task_id=task_id,
        steps=[
            PlanStep(
                id="S1",
                tool="protgpt2",
                inputs={
                    "prompt": "TRP-cage-like stable peptide",
                    "num_candidates": 3,
                },
                metadata={
                    "capability_id": "sequence_generation",
                    "io_type": "prompt_to_sequence",
                },
            ),
            PlanStep(
                id="S2",
                tool="openfold3_rest",
                inputs={"sequence_ref": "S1.sequence"},
                metadata={
                    "capability_id": "structure_prediction",
                    "io_type": "sequence_to_structure",
                    "high_cost_flag": True,
                },
            ),
            PlanStep(
                id="S3",
                tool="biopython_qc",
                inputs={"pdb_ref": "S2.pdb_path"},
                metadata={
                    "capability_id": "quality_control",
                    "io_type": "structure_to_qc_report",
                },
            ),
        ],
        constraints=_demo_constraints(),
        metadata={"source": DEMO_FIXTURE_SOURCE},
    )


def _build_candidates(
    task_id: str,
    runtime_summary: JsonObject,
) -> list[PendingActionCandidate]:
    return [
        _candidate(
            task_id=task_id,
            candidate_id="patch_local_openfold",
            step_tool="openfold",
            summary="Use local OpenFold-compatible structure prediction for stable demo execution.",
            explanation="Avoids a degraded remote high-cost call and preserves the successful prefix.",
            risk_level="low",
            cost_estimate="low",
            score_breakdown={
                "feasibility": 0.88,
                "objective": 0.82,
                "risk": 0.90,
                "cost": 0.86,
                "overall": 0.86,
            },
            tool_id="openfold",
            adapter_mode="local",
            runtime_summary=runtime_summary,
            final_score=0.86,
        ),
        _candidate(
            task_id=task_id,
            candidate_id="suffix_replan_low_cost",
            step_tool="esmfold",
            summary="Switch the suffix to a lower-cost structure and QC path.",
            explanation="Reduces cost exposure while keeping a reportable structure artifact.",
            risk_level="low",
            cost_estimate="medium",
            score_breakdown={
                "feasibility": 0.80,
                "objective": 0.76,
                "risk": 0.84,
                "cost": 0.74,
                "overall": 0.78,
            },
            tool_id="esmfold",
            adapter_mode="local",
            runtime_summary=runtime_summary,
            final_score=0.78,
        ),
        _candidate(
            task_id=task_id,
            candidate_id="patch_remote_retry",
            step_tool="openfold3_rest",
            summary="Retry the remote OpenFold3 REST candidate.",
            explanation="Keeps the original plan but remains exposed to degraded remote readiness.",
            risk_level="medium",
            cost_estimate="high",
            score_breakdown={
                "feasibility": 0.72,
                "objective": 0.84,
                "risk": 0.54,
                "cost": 0.42,
                "overall": 0.71,
            },
            tool_id="openfold3_rest",
            adapter_mode="remote",
            runtime_summary=runtime_summary,
            final_score=0.71,
        ),
    ]


def _candidate(
    *,
    task_id: str,
    candidate_id: str,
    step_tool: str,
    summary: str,
    explanation: str,
    risk_level: Literal["low", "medium", "high"],
    cost_estimate: Literal["low", "medium", "high"],
    score_breakdown: dict[str, float],
    tool_id: str,
    adapter_mode: Literal["local", "remote", "mock", "hybrid", "unknown"],
    runtime_summary: JsonObject,
    final_score: float,
) -> PendingActionCandidate:
    patch = PlanPatch(
        task_id=task_id,
        operations=[
            PlanPatchOp(
                op="replace_step",
                target="S2",
                step=PlanStep(
                    id="S2",
                    tool=step_tool,
                    inputs={"sequence_ref": "S1.sequence"},
                    metadata={
                        "source": DEMO_FIXTURE_SOURCE,
                        "capability_id": "structure_prediction",
                        "io_type": "sequence_to_structure",
                    },
                ),
            )
        ],
        metadata={
            "source": DEMO_FIXTURE_SOURCE,
            "candidate_id": candidate_id,
            "recovery_layer": "tool_level_patch",
        },
    )
    return PendingActionCandidate(
        candidate_id=candidate_id,
        payload=patch,
        summary=summary,
        explanation=explanation,
        risk_level=risk_level,
        cost_estimate=cost_estimate,
        score_breakdown=score_breakdown,
        tool_id=tool_id,
        capability_id="structure_prediction",
        io_type="sequence_to_structure",
        adapter_mode=adapter_mode,
        execution_mode=tool_id,
        provider=tool_id,
        endpoint_type="local" if adapter_mode == "local" else "rest",
        metadata={
            "source": DEMO_FIXTURE_SOURCE,
            "affected_steps": ["S2"],
            "expected_effect": "Preserve S1 and patch S2 before resuming.",
            "recovery_semantics": "patch_local",
            RUNTIME_STATE_SUMMARY_METADATA_KEY: runtime_summary,
            "final_score": {
                "value": final_score,
                "source": "defense_demo_fixture.score_breakdown",
                "source_refs": [candidate_id],
            },
            TOOL_READINESS_METADATA_KEY: {
                "status": "degraded" if adapter_mode == "remote" else "ready",
                "reason": (
                    "Remote REST health is intentionally marked degraded for demo."
                    if adapter_mode == "remote"
                    else "Local deterministic fixture is available."
                ),
            },
        },
    )


def _runtime_state_summary() -> JsonObject:
    return {
        "schema_version": 1,
        "p_success": 0.64,
        "p_structural_failure": 0.31,
        "recovery_margin": 0.72,
        "expected_remaining_cost": 1.35,
        "evidence_sufficiency": 0.58,
        "budget_pressure": 1.12,
        "budget_cap": 1.2,
    }


def _objective_scoring() -> JsonObject:
    return {
        "objective_score": 0.84,
        "posterior_score": {
            "aggregate_score": 0.84,
            "evidence_status": "sufficient_for_demo",
        },
        "top_k": [
            {
                "candidate_id": "patch_local_openfold",
                "objective_score": 0.86,
                "posterior_score": {"evidence_status": "supported"},
            },
            {
                "candidate_id": "suffix_replan_low_cost",
                "objective_score": 0.78,
                "posterior_score": {"evidence_status": "supported"},
            },
            {
                "candidate_id": "patch_remote_retry",
                "objective_score": 0.71,
                "posterior_score": {"evidence_status": "degraded_remote_readiness"},
            },
        ],
        "warnings": ["demo fixture; no remote inference was executed"],
        "evidence_refs": [
            {"type": "event_log", "path": f"data/logs/{DEMO_DONE_TASK_ID}.jsonl"},
            {
                "type": "pdb",
                "path": "output/demo/defense-full-flow/demo_defense_done.pdb",
            },
        ],
    }


def _structure_similarity() -> JsonObject:
    return {
        "hit_count": 3,
        "top_hit": {
            "hit_id": "TRP_CAGE_REFERENCE",
            "tm_score": 0.73,
            "rmsd": 2.1,
        },
    }


def _write_demo_events(
    *,
    log_dir: Path,
    runtime_summary: JsonObject,
) -> None:
    for task_id in (DEMO_INTAKE_TASK_ID, DEMO_HITL_TASK_ID, DEMO_DONE_TASK_ID):
        log_path = log_dir / f"{task_id}.jsonl"
        if log_path.exists():
            log_path.unlink()

    _append_events(
        DEMO_INTAKE_TASK_ID,
        log_dir=log_dir,
        events=[
            _event("TASK_CREATED"),
            _event("TASK_INTAKE_CONFIRMED"),
            _transition("CREATED", "PLANNING"),
            _event("PLAN_CANDIDATES_GENERATED"),
            _transition("PLANNING", "PLANNED"),
            _transition("PLANNED", "RUNNING"),
            _transition("RUNNING", "SUMMARIZING"),
            _event("SUMMARY_CREATED"),
            _transition("SUMMARIZING", "DONE"),
        ],
    )
    _append_events(
        DEMO_HITL_TASK_ID,
        log_dir=log_dir,
        events=[
            _event("TASK_CREATED"),
            _event("TASK_INTAKE_CONFIRMED"),
            _transition("CREATED", "PLANNING"),
            _event("PLAN_CANDIDATES_GENERATED"),
            _transition("PLANNING", "PLANNED"),
            _transition("PLANNED", "RUNNING"),
            _step("S1", "protgpt2"),
            _event(
                "TOOL_READINESS_DEGRADED",
                tool="openfold3_rest",
                tool_id="openfold3_rest",
                data={"reason": "remote REST endpoint is not used in defense demo"},
            ),
            _event("RUNTIME_STATE_UPDATED", data={"runtime_state_summary": runtime_summary}),
            _event(
                "PENDING_ACTION_CREATED",
                pending_action_id=DEMO_PENDING_ACTION_ID,
                action_type="patch_confirm",
                data={"runtime_state_summary": runtime_summary},
            ),
            _event(
                "WAITING_ENTER",
                data={"waiting_runtime_summary": {"runtime_state_summary": runtime_summary}},
            ),
            _transition("RUNNING", "WAITING_PATCH_CONFIRM"),
        ],
    )
    _append_events(
        DEMO_DONE_TASK_ID,
        log_dir=log_dir,
        events=[
            _event("TASK_CREATED"),
            _event("TASK_INTAKE_CONFIRMED"),
            _transition("CREATED", "PLANNING"),
            _event("PLAN_CANDIDATES_GENERATED"),
            _transition("PLANNING", "PLANNED"),
            _transition("PLANNED", "RUNNING"),
            _step("S1", "protgpt2"),
            _event(
                "TOOL_READINESS_DEGRADED",
                tool="openfold3_rest",
                tool_id="openfold3_rest",
                data={"reason": "remote REST endpoint is not used in defense demo"},
            ),
            _event("RUNTIME_STATE_UPDATED", data={"runtime_state_summary": runtime_summary}),
            _event(
                "PENDING_ACTION_CREATED",
                pending_action_id=DEMO_PENDING_ACTION_ID,
                action_type="patch_confirm",
                data={"runtime_state_summary": runtime_summary},
            ),
            _event(
                "WAITING_ENTER",
                data={"waiting_runtime_summary": {"runtime_state_summary": runtime_summary}},
            ),
            _event(
                "DECISION_SUBMITTED",
                pending_action_id=DEMO_PENDING_ACTION_ID,
                decision_id="decision_demo_defense_accept_patch",
                candidate_id="patch_local_openfold",
                data={"choice": "accept", "selected_candidate_id": "patch_local_openfold"},
            ),
            _event(
                "DECISION_APPLIED",
                pending_action_id=DEMO_PENDING_ACTION_ID,
                decision_id="decision_demo_defense_accept_patch",
                candidate_id="patch_local_openfold",
                choice="accept",
                data={"choice": "accept", "selected_candidate_id": "patch_local_openfold"},
            ),
            _event("WAITING_EXIT", pending_action_id=DEMO_PENDING_ACTION_ID),
            _transition("WAITING_PATCH_CONFIRM", "RUNNING"),
            _step("S2", "openfold", tool_id="openfold"),
            _step("S3", "biopython_qc", tool_id="biopython_qc"),
            _transition("RUNNING", "SUMMARIZING"),
            _event("SUMMARY_CREATED"),
            _transition("SUMMARIZING", "DONE"),
        ],
    )


def _append_events(
    task_id: str,
    *,
    log_dir: Path,
    events: list[JsonObject],
) -> None:
    for index, event in enumerate(events, start=1):
        payload = {"task_id": task_id, "ts": now_iso(), "seq_hint": index, **event}
        append_event(task_id, payload, log_dir=log_dir)


def _event(
    event_type: str,
    *,
    pending_action_id: str | None = None,
    decision_id: str | None = None,
    candidate_id: str | None = None,
    action_type: str | None = None,
    tool: str | None = None,
    tool_id: str | None = None,
    choice: str | None = None,
    data: JsonObject | None = None,
) -> JsonObject:
    payload: JsonObject = {"event_type": event_type, "data": data or {}}
    optional_fields: dict[str, str | None] = {
        "pending_action_id": pending_action_id,
        "decision_id": decision_id,
        "candidate_id": candidate_id,
        "action_type": action_type,
        "tool": tool,
        "tool_id": tool_id,
        "choice": choice,
    }
    for key, value in optional_fields.items():
        if value is not None:
            payload[key] = value
    return payload


def _transition(from_status: str, to_status: str) -> JsonObject:
    return {
        "event_type": "STATE_TRANSITION",
        "from_status": from_status,
        "to_status": to_status,
        "data": {"from_status": from_status, "to_status": to_status},
    }


def _step(step_id: str, tool: str, *, tool_id: str | None = None) -> JsonObject:
    resolved_tool_id = tool_id or tool
    return {
        "event_type": "STEP_FINISHED",
        "step_id": step_id,
        "tool": tool,
        "tool_id": resolved_tool_id,
        "data": {
            "step_id": step_id,
            "tool_id": resolved_tool_id,
            "status": "success",
        },
    }


def _demo_structure_pdb_text() -> str:
    residues = (
        "ASN", "LEU", "TYR", "ILE", "GLN", "TRP", "LEU", "LYS",
        "ASP", "GLY", "GLY", "PRO", "SER", "SER", "GLY", "ARG",
        "PRO", "PRO", "PRO", "SER",
    )
    lines = [
        "HEADER    DEFENSE FULL FLOW DEMO",
        "TITLE     SYNTHETIC TRP-CAGE-LIKE HELIX FIXTURE, NO MODEL INFERENCE",
    ]
    serial = 1
    for index, residue_name in enumerate(residues, start=1):
        base_x = index * 1.45
        base_y = 4.0 * ((index % 5) - 2) / 2.0
        base_z = 2.2 * ((index % 7) - 3) / 3.0
        atoms = (
            ("N", base_x, base_y, base_z),
            ("CA", base_x + 0.55, base_y + 0.75, base_z + 0.30),
            ("C", base_x + 1.25, base_y + 0.10, base_z + 0.85),
            ("O", base_x + 1.75, base_y - 0.70, base_z + 0.45),
            ("CB", base_x + 0.35, base_y + 1.35, base_z - 0.75),
        )
        for atom_name, x, y, z in atoms:
            element = atom_name[0]
            atom_line = (
                f"ATOM  {serial:5d} {atom_name:<4} {residue_name:>3} A{index:4d}    "
                f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00 88.20           {element:>2}"
            )
            lines.append(atom_line)
            serial += 1
    lines.append("TER")
    lines.append("END")
    return "\n".join(lines) + "\n"
