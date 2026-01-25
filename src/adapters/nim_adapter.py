"""
NIMESMFoldAdapter - NVIDIA NIM ESMFold adapter.
"""
from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Any, Dict, Optional, Tuple

from src.adapters.base_tool_adapter import BaseToolAdapter
from src.engines.nim_client import NvidiaNIMClient
from src.models.contracts import PlanStep
from src.workflow.context import WorkflowContext
from src.workflow.errors import FailureCode, FailureType, StepRunError

__all__ = ["NIMESMFoldAdapter"]


class NIMESMFoldAdapter(BaseToolAdapter):
    """ESMFold adapter via NVIDIA NIM (sync)."""

    tool_id = "esmfold"
    adapter_id = "nim_esmfold"

    def __init__(
        self,
        *,
        client: Optional[NvidiaNIMClient] = None,
        output_dir: str | Path | None = None,
        model_id: str = "nvidia/esmfold",
    ) -> None:
        self.client = client or NvidiaNIMClient(model_id=model_id)
        self.output_dir = Path(output_dir or "output/pdb")
        self.model_id = model_id

    def resolve_inputs(
        self,
        step: PlanStep,
        context: WorkflowContext,
    ) -> Dict[str, Any]:
        resolved: Dict[str, Any] = {}
        for key, val in step.inputs.items():
            if isinstance(val, str) and "." in val:
                step_id, field = val.split(".", 1)
                if step_id and step_id.startswith("S"):
                    if not context.has_step_result(step_id):
                        raise ValueError(
                            f"Failed to resolve input reference '{val}' "
                            f"for step '{step.id}': step '{step_id}' not found in context"
                        )
                    try:
                        resolved_value = context.get_step_output(step_id, field)
                    except KeyError as exc:
                        raise ValueError(
                            f"Failed to resolve input reference '{val}' "
                            f"for step '{step.id}': field '{field}' not found in step '{step_id}' outputs"
                        ) from exc
                    resolved[key] = resolved_value
                    continue
            resolved[key] = val

        if "sequence" not in resolved:
            raise ValueError(
                f"Missing required input 'sequence' for ESMFold step '{step.id}'"
            )

        resolved["task_id"] = context.task.task_id
        resolved["step_id"] = step.id
        return resolved

    def run_local(
        self,
        inputs: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        t0 = perf_counter()
        sequence = inputs.get("sequence")
        if not sequence:
            raise StepRunError(
                failure_type=FailureType.NON_RETRYABLE,
                message="Missing required input 'sequence'",
                code=FailureCode.INPUT_RESOLUTION_FAILED.value,
            )

        payload = {"sequence": sequence}
        response = self.client.call_sync(payload)
        response_data = _unwrap_response(response)

        pdb_text = _extract_pdb_text(response_data)
        if not pdb_text:
            raise StepRunError(
                failure_type=FailureType.TOOL_ERROR,
                message="NIM response missing PDB content",
                code=FailureCode.NIM_INVALID_RESPONSE.value,
            )

        plddt = _extract_plddt(response_data)
        if plddt is None:
            plddt = _infer_plddt_from_pdb_text(pdb_text)
        if plddt is None:
            raise StepRunError(
                failure_type=FailureType.TOOL_ERROR,
                message="NIM response missing pLDDT value",
                code=FailureCode.NIM_INVALID_RESPONSE.value,
            )

        task_id = inputs.get("task_id", "unknown")
        step_id = inputs.get("step_id", "unknown")

        self.output_dir.mkdir(parents=True, exist_ok=True)
        pdb_filename = f"nim_{task_id}_{step_id}.pdb"
        pdb_path = self.output_dir / pdb_filename
        pdb_path.write_text(pdb_text, encoding="utf-8")

        outputs = {
            "pdb_path": str(pdb_path.resolve()),
            "plddt": plddt,
            "metrics": {"plddt_mean": plddt},
        }
        duration_ms = int((perf_counter() - t0) * 1000)
        metrics = {
            "exec_type": "nvidia_nim",
            "duration_ms": duration_ms,
            "provider": "nvidia_nim",
            "model_id": self.model_id,
        }
        return outputs, metrics


def _unwrap_response(response: Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(response.get("outputs"), dict):
        return response["outputs"]
    if isinstance(response.get("output"), dict):
        return response["output"]
    return response


def _extract_pdb_text(data: Dict[str, Any]) -> Optional[str]:
    for key in ("pdb", "pdb_string", "pdb_text", "pdb_content", "structure"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value
    pdbs = data.get("pdbs")
    if isinstance(pdbs, list) and pdbs:
        first = pdbs[0]
        if isinstance(first, str) and first.strip():
            return first
    return None


def _extract_plddt(data: Dict[str, Any]) -> Optional[float]:
    for key in ("plddt", "pLDDT", "plddt_mean", "mean_plddt", "mean_pLDDT"):
        if key in data:
            return _normalize_plddt(data[key])

    metrics = data.get("metrics")
    if isinstance(metrics, dict):
        for key in ("plddt", "pLDDT", "plddt_mean", "mean_plddt", "mean_pLDDT"):
            if key in metrics:
                return _normalize_plddt(metrics[key])
    return None


def _normalize_plddt(value: Any) -> Optional[float]:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, list):
        numbers = [float(item) for item in value if isinstance(item, (int, float))]
        if not numbers:
            return None
        return sum(numbers) / len(numbers)
    if isinstance(value, dict):
        for key in ("mean", "avg", "average"):
            if key in value and isinstance(value[key], (int, float)):
                return float(value[key])
    return None


def _infer_plddt_from_pdb_text(pdb_text: str) -> Optional[float]:
    values: list[float] = []
    for line in pdb_text.splitlines():
        if not (line.startswith("ATOM") or line.startswith("HETATM")):
            continue
        if len(line) < 66:
            continue
        b_factor_str = line[60:66].strip()
        if not b_factor_str:
            continue
        try:
            values.append(float(b_factor_str))
        except ValueError:
            continue
    if not values:
        return None
    return sum(values) / len(values)
