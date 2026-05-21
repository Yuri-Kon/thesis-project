from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.models.contracts import StepResult

_AA_ALPHABET = set("ACDEFGHIKLMNPQRSTVWY")

def build_step_trace_data(step_result: StepResult) -> dict[str, Any]:
    outputs = step_result.outputs
    stage_id = _stage_id(outputs)
    data = _base_trace_fields(step_result, stage_id=stage_id)
    _attach_metric_section(data, step_result, "patch", _patch_trace)
    _attach_metric_section(data, step_result, "recovery", _recovery_trace)
    _attach_metric_section(data, step_result, "fallback", _fallback_trace)
    _attach_workflow_action(data, step_result)
    _attach_s6_action(data, step_result)
    if stage_id == "S3":
        data.update(_quality_gate_trace(step_result, outputs))
    if outputs.get("capability_id") == "objective_scoring":
        data["objective_scoring"] = _objective_scoring_trace(step_result, outputs)
    return data


def _base_trace_fields(step_result: StepResult, *, stage_id: str | None) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for field_name in (
        "tool_id",
        "adapter_id",
        "execution_mode",
        "provider",
        "endpoint_type",
        "remote_job_id",
    ):
        value = getattr(step_result, field_name, None)
        if isinstance(value, str) and value:
            data[field_name] = value
    if stage_id:
        data["stage_id"] = stage_id
    _attach_error_details(data, step_result)
    return data


def _attach_error_details(data: dict[str, Any], step_result: StepResult) -> None:
    error_details = step_result.error_details
    failure_code = error_details.get("failure_code")
    if isinstance(failure_code, str) and failure_code:
        data["failure_code"] = failure_code
    remote_job_id = error_details.get("remote_job_id")
    if isinstance(remote_job_id, str) and remote_job_id and "remote_job_id" not in data:
        data["remote_job_id"] = remote_job_id


def _stage_id(outputs: dict[str, Any]) -> str | None:
    stage_id = outputs.get("stage_id")
    if isinstance(stage_id, str) and stage_id:
        return stage_id
    return None


def _attach_metric_section(
    data: dict[str, Any],
    step_result: StepResult,
    metric_key: str,
    builder: Callable[[dict[str, Any]], dict[str, Any]],
) -> None:
    metric = step_result.metrics.get(metric_key)
    if isinstance(metric, dict) and metric:
        data[metric_key] = builder(metric)


def _patch_trace(patch_meta: dict[str, Any]) -> dict[str, Any]:
    return {
        "layer": patch_meta.get("layer"),
        "from_tool": patch_meta.get("from_tool"),
        "to_tool": patch_meta.get("to_tool"),
        "capability_id": patch_meta.get("capability_id"),
        "io_type": patch_meta.get("io_type"),
        "adapter_mode": patch_meta.get("adapter_mode"),
        "reason": patch_meta.get("reason"),
        "ops": patch_meta.get("ops"),
        "patched_status": patch_meta.get("patched_status"),
    }


def _recovery_trace(recovery_meta: dict[str, Any]) -> dict[str, Any]:
    return {
        "layer": recovery_meta.get("recovery_layer"),
        "from_tool": recovery_meta.get("from_tool"),
        "to_tool": recovery_meta.get("to_tool"),
        "capability_id": recovery_meta.get("capability_id"),
        "io_type": recovery_meta.get("io_type"),
        "adapter_mode": recovery_meta.get("adapter_mode"),
        "candidate_id": recovery_meta.get("candidate_id"),
        "reason": recovery_meta.get("reason"),
        "upgrade_reason": recovery_meta.get("upgrade_reason"),
    }


def _fallback_trace(fallback_meta: dict[str, Any]) -> dict[str, Any]:
    return {
        "fallback_kind": fallback_meta.get("fallback_kind"),
        "reason": fallback_meta.get("reason"),
        "from_tool_id": fallback_meta.get("from_tool_id"),
        "to_tool_id": fallback_meta.get("to_tool_id"),
        "from_execution_mode": fallback_meta.get("from_execution_mode"),
        "to_execution_mode": fallback_meta.get("to_execution_mode"),
        "from_adapter_id": fallback_meta.get("from_adapter_id"),
        "to_adapter_id": fallback_meta.get("to_adapter_id"),
        "capability_preserved": fallback_meta.get("capability_preserved"),
    }


def _attach_workflow_action(data: dict[str, Any], step_result: StepResult) -> None:
    workflow_action = step_result.metrics.get("workflow_action")
    if isinstance(workflow_action, str) and workflow_action:
        data["action_name"] = workflow_action
        data["workflow_action_reason"] = step_result.metrics.get(
            "workflow_action_reason"
        )
        data["evidence_source"] = step_result.metrics.get(
            "workflow_action_evidence"
        )


def _attach_s6_action(data: dict[str, Any], step_result: StepResult) -> None:
    s6_action = step_result.metrics.get("s6_recovery_action")
    if not isinstance(s6_action, str) or not s6_action:
        return
    data.setdefault("action_name", s6_action)
    data["s6"] = {
        "action": s6_action,
        "trigger_stage_id": step_result.metrics.get("s6_trigger_stage_id"),
        "trigger_failure_code": step_result.metrics.get("s6_trigger_failure_code"),
    }


def _quality_gate_trace(
    step_result: StepResult,
    outputs: dict[str, Any],
) -> dict[str, Any]:
    data: dict[str, Any] = {}
    input_summary = summarize_quality_gate_inputs(step_result.inputs)
    if input_summary:
        data["input_summary"] = input_summary
    reject_counts = outputs.get("reject_code_counts")
    data["quality_gate"] = {
        "pass_count": outputs.get("pass_count"),
        "fail_count": outputs.get("fail_count"),
        "pass_fail": outputs.get("pass_fail"),
        "reject_code_counts": reject_counts if isinstance(reject_counts, dict) else {},
        "failed_samples": _failed_quality_samples(outputs.get("failed_samples")),
    }
    return data


def _failed_quality_samples(failed_rows: object) -> list[dict[str, Any]]:
    failed_samples: list[dict[str, Any]] = []
    if not isinstance(failed_rows, list):
        return failed_samples
    for item in failed_rows:
        if isinstance(item, dict):
            failed_samples.append(
                {
                    "candidate_id": item.get("candidate_id"),
                    "reject_codes": item.get("reject_codes"),
                    "reason": item.get("reason"),
                }
            )
    return failed_samples


def _objective_scoring_trace(
    step_result: StepResult,
    outputs: dict[str, Any],
) -> dict[str, Any]:
    return {
        "objective_score": outputs.get("objective_score"),
        "objective_gap": step_result.metrics.get("objective_gap"),
        "objective_progress": step_result.metrics.get("objective_progress"),
        "default_recommendation": outputs.get("default_recommendation"),
        "rank_reason": outputs.get("rank_reason"),
        "warning_count": step_result.metrics.get("warning_count"),
    }

def summarize_quality_gate_inputs(inputs: Any) -> dict[str, Any]:
    if not isinstance(inputs, dict):
        return {}

    summary: dict[str, Any] = {}
    if "sequence" in inputs:
        summary["sequence"] = summarize_sequence_input(inputs.get("sequence"))
    if "pdb_path" in inputs:
        summary["pdb_path"] = summarize_path_input(inputs.get("pdb_path"))

    structure_results = inputs.get("structure_results")
    if isinstance(structure_results, list):
        structure_summary: dict[str, Any] = {
            "type": "list",
            "count": len(structure_results),
        }
        first_item = next(
            (item for item in structure_results if isinstance(item, dict)),
            None,
        )
        if first_item is not None:
            structure_summary["first_candidate"] = {
                "candidate_id": first_item.get("candidate_id"),
                "sequence": summarize_sequence_input(first_item.get("sequence")),
                "pdb_path": summarize_path_input(first_item.get("pdb_path")),
            }
        summary["structure_results"] = structure_summary
    return summary


def summarize_sequence_input(value: Any) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "type": type(value).__name__,
    }
    if not isinstance(value, str):
        if isinstance(value, list):
            summary["count"] = len(value)
        return summary

    trimmed = value.strip()
    uppercase = trimmed.upper()
    invalid_chars = [
        char
        for char in uppercase
        if char and char not in _AA_ALPHABET
    ]
    summary.update(
        {
            "length": len(value),
            "preview": value[:48],
            "symbolic_reference_like": looks_like_symbolic_reference(value),
            "valid_aa_chars": bool(trimmed) and not invalid_chars,
            "invalid_char_count": len(invalid_chars),
        }
    )
    return summary


def summarize_path_input(value: Any) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "type": type(value).__name__,
    }
    if not isinstance(value, str):
        return summary

    symbolic_reference_like = looks_like_symbolic_reference(value)
    summary.update(
        {
            "value": value,
            "symbolic_reference_like": symbolic_reference_like,
            "exists": False if symbolic_reference_like else Path(value).exists(),
        }
    )
    return summary


def looks_like_symbolic_reference(value: str) -> bool:
    if "/" in value or "\\" in value:
        return False
    dot_count = value.count(".")
    if dot_count >= 2:
        return True
    if dot_count == 1:
        head = value.split(".", 1)[0]
        return head.startswith("S")
    return False
