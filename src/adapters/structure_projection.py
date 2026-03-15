from __future__ import annotations

from typing import Any, Dict

from src.workflow.errors import FailureCode, FailureType, StepRunError

__all__ = ["normalize_structure_projection_outputs"]


def normalize_structure_projection_outputs(
    outputs: Dict[str, Any],
    *,
    tool_id: str,
) -> Dict[str, Any]:
    """Normalize structure projection adapter outputs to S2 contract."""
    if not isinstance(outputs, dict):
        raise StepRunError(
            failure_type=FailureType.NON_RETRYABLE,
            message="Structure projection outputs must be a dict",
            code=FailureCode.OUTPUT_NOT_DICT.value,
        )

    normalized = dict(outputs)
    pdb_path = normalized.get("pdb_path")
    if not isinstance(pdb_path, str) or not pdb_path:
        raise StepRunError(
            failure_type=FailureType.NON_RETRYABLE,
            message="Structure projection output missing 'pdb_path'",
            code=FailureCode.OUTPUT_MISSING.value,
        )

    metrics = normalized.get("metrics")
    if not isinstance(metrics, dict):
        metrics = {}

    plddt_value = _extract_plddt_value(normalized, metrics)
    if plddt_value is None:
        raise StepRunError(
            failure_type=FailureType.NON_RETRYABLE,
            message="Structure projection output missing confidence 'plddt'",
            code=FailureCode.OUTPUT_MISSING.value,
        )

    confidence_level = _derive_confidence_level(plddt_value)
    metrics.setdefault("plddt_mean", plddt_value)
    metrics.setdefault("confidence", confidence_level)
    normalized["metrics"] = metrics
    normalized["plddt"] = plddt_value
    normalized["confidence"] = {
        "plddt_mean": plddt_value,
        "level": confidence_level,
    }
    normalized["stage_id"] = "S2"
    normalized["lineage"] = {
        "stage_id": "S2",
        "tool_id": tool_id,
        "io_type": "sequence_to_structure",
    }
    return normalized


def _extract_plddt_value(outputs: Dict[str, Any], metrics: Dict[str, Any]) -> float | None:
    for key in ("plddt", "pLDDT", "plddt_mean", "mean_plddt", "mean_pLDDT"):
        value = outputs.get(key)
        parsed = _to_float(value)
        if parsed is not None:
            return parsed

    for key in ("plddt", "pLDDT", "plddt_mean", "mean_plddt", "mean_pLDDT"):
        value = metrics.get(key)
        parsed = _to_float(value)
        if parsed is not None:
            return parsed
    return None


def _to_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, list):
        parsed = [float(item) for item in value if isinstance(item, (int, float))]
        if parsed:
            return sum(parsed) / len(parsed)
    return None


def _derive_confidence_level(plddt: float) -> str:
    if plddt <= 1.0:
        if plddt >= 0.85:
            return "high"
        if plddt >= 0.65:
            return "medium"
        return "low"
    if plddt >= 85:
        return "high"
    if plddt >= 65:
        return "medium"
    return "low"
