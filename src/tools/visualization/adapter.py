from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import TypeGuard, cast, override

from src.adapters.base_tool_adapter import BaseToolAdapter
from src.models.contracts import PlanStep
from src.storage.log_store import append_event
from src.workflow.context import WorkflowContext
from src.workflow.errors import FailureType, StepRunError
from src.tools.visualization.pipeline import (
    PdbDownloadError,
    VisualizationArtifacts,
    run_visualization,
)

__all__ = ["VisualizationToolAdapter"]

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | JsonObject | JsonArray
type JsonObject = dict[str, JsonValue]
type JsonArray = list[JsonValue]


class VisualizationToolAdapter(BaseToolAdapter):
    """Adapter for structure visualization toolchain."""

    tool_id: str = "visualize_structure"
    adapter_id: str | None = "visualization_tool"

    def __init__(self) -> None:
        self._last_context: JsonObject = {}

    @override
    def resolve_inputs(self, step: PlanStep, context: WorkflowContext) -> JsonObject:
        resolved: JsonObject = {}
        for key, val in _json_items(cast(object, step.inputs)):
            if isinstance(val, str) and "." in val:
                step_id, field = val.split(".", 1)
                if step_id and step_id.startswith("S"):
                    if not context.has_step_result(step_id):
                        message = (
                            f"Failed to resolve input reference '{val}' for step {step.id!r}: "
                            f"step '{step_id}' not found in context"
                        )
                        raise ValueError(
                            message
                        )
                    try:
                        resolved_value = cast(
                            object,
                            context.get_step_output(step_id, field),
                        )
                    except KeyError as exc:
                        message = (
                            f"Failed to resolve input reference '{val}' for step {step.id!r}: "
                            f"field '{field}' not found in step '{step_id}' outputs"
                        )
                        raise ValueError(
                            message
                        ) from exc
                    if _is_json_value(resolved_value):
                        resolved[key] = resolved_value
                    else:
                        resolved[key] = str(resolved_value)
                    continue
            resolved[key] = val

        pdb_id = resolved.get("pdb_id")
        pdb_path = resolved.get("pdb_path")
        if bool(pdb_id) == bool(pdb_path):
            raise ValueError("Exactly one of 'pdb_id' or 'pdb_path' must be provided.")

        out_dir = resolved.get("out_dir")
        if out_dir is None:
            out_dir = Path("output") / context.task.task_id / "visualization"
        resolved["out_dir"] = str(out_dir)

        self._last_context = {
            "task_id": context.task.task_id,
            "step_id": step.id,
            "tool": step.tool,
            "plan_version": _extract_plan_version(context),
            "state": context.status.value,
        }
        return resolved

    @override
    def run_local(self, inputs: Mapping[str, object]) -> tuple[JsonObject, JsonObject]:
        pdb_ref_value = inputs.get("pdb_id") or inputs.get("pdb_path")
        if isinstance(pdb_ref_value, Path):
            pdb_ref = str(pdb_ref_value)
        else:
            pdb_ref = pdb_ref_value
        if not isinstance(pdb_ref, str) or not pdb_ref.strip():
            raise StepRunError(
                failure_type=FailureType.NON_RETRYABLE,
                message="Missing pdb reference in inputs.",
                code="PDB_REF_MISSING",
            )

        out_dir_value = inputs.get("out_dir", "output/visualization")
        out_dir = Path(str(out_dir_value))
        reuse_cache = bool(inputs.get("reuse_cache", True))

        self._log_event(
            "TOOL_START",
            input_summary={
                "pdb_ref": pdb_ref,
                "out_dir": str(out_dir),
                "reuse_cache": reuse_cache,
            },
        )

        try:
            artifacts = run_visualization(
                pdb_ref,
                out_dir,
                reuse_cache=reuse_cache,
            )
        except FileNotFoundError as exc:
            self._log_event("TOOL_ERROR", error=str(exc))
            raise StepRunError(
                failure_type=FailureType.NON_RETRYABLE,
                message=str(exc),
                code="PDB_NOT_FOUND",
                cause=exc,
            ) from exc
        except PdbDownloadError as exc:
            self._log_event("TOOL_ERROR", error=str(exc))
            failure_type = (
                FailureType.RETRYABLE if exc.retryable else FailureType.NON_RETRYABLE
            )
            raise StepRunError(
                failure_type=failure_type,
                message=str(exc),
                code="PDB_DOWNLOAD_FAILED",
                cause=exc,
            ) from exc
        except Exception as exc:
            self._log_event("TOOL_ERROR", error=str(exc))
            raise StepRunError(
                failure_type=FailureType.TOOL_ERROR,
                message=f"Visualization pipeline failed: {exc}",
                code="VISUALIZATION_FAILED",
                cause=exc,
            ) from exc

        self._log_event(
            "TOOL_END",
            artifacts=_artifact_payload(artifacts),
        )
        outputs: JsonObject = {
            "metrics_json_path": str(artifacts.metrics_json_path),
            "plotly_html_path": str(artifacts.plotly_html_path),
            "report_html_path": str(artifacts.report_html_path),
            "assets_dir": str(artifacts.assets_dir),
            "summary_stats": artifacts.summary_stats,
        }
        metrics: JsonObject = {
            "exec_type": "visualization_pipeline",
            "artifact_count": 4,
        }
        return outputs, metrics

    def _log_event(self, event: str, **payload: JsonValue) -> None:
        task_id = self._last_context.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            return
        append_event(
            task_id,
            {
                "event": event,
                "task_id": task_id,
                "step_id": self._last_context.get("step_id"),
                "tool": self._last_context.get("tool"),
                "plan_version": self._last_context.get("plan_version"),
                "state": self._last_context.get("state"),
                **payload,
            },
        )


def _artifact_payload(artifacts: VisualizationArtifacts) -> JsonObject:
    return {
        "metrics_json_path": str(artifacts.metrics_json_path),
        "plotly_html_path": str(artifacts.plotly_html_path),
        "report_html_path": str(artifacts.report_html_path),
        "assets_dir": str(artifacts.assets_dir),
        "pdb_path": str(artifacts.pdb_path),
    }


def _extract_plan_version(context: WorkflowContext) -> str | None:
    plan = context.plan
    if plan is None:
        return None
    metadata = _as_json_object(cast(object, plan.metadata))
    if metadata is None:
        return None
    value = metadata.get("plan_version")
    if value is None:
        return None
    return str(value)


def _json_items(value: object) -> list[tuple[str, JsonValue]]:
    payload = _as_json_object(value)
    if payload is None:
        return []
    return list(payload.items())


def _as_json_object(value: object) -> JsonObject | None:
    if not isinstance(value, dict):
        return None
    result: JsonObject = {}
    for key, item in cast(Mapping[object, object], value).items():
        if isinstance(key, str) and _is_json_value(item):
            result[key] = item
    return result


def _is_json_value(value: object) -> TypeGuard[JsonValue]:
    if value is None or isinstance(value, str | int | float | bool):
        return True
    if isinstance(value, list):
        return all(_is_json_value(item) for item in cast(list[object], value))
    if isinstance(value, dict):
        return all(
            isinstance(key, str) and _is_json_value(item)
            for key, item in cast(Mapping[object, object], value).items()
        )
    return False
