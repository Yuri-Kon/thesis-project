from __future__ import annotations

from collections import Counter
from typing import Any, Dict, Iterable

from src.models.contracts import PlanStep
from src.workflow.context import WorkflowContext

__all__ = [
    "build_docking_metrics",
    "build_docking_outputs",
    "build_function_annotation_metrics",
    "build_function_annotation_outputs",
    "build_objective_metrics",
    "build_objective_outputs",
    "build_similarity_outputs",
    "build_similarity_metrics",
    "build_stability_metrics",
    "build_stability_outputs",
    "build_structure_similarity_metrics",
    "build_structure_similarity_outputs",
    "build_secondary_structure_outputs",
    "build_secondary_structure_metrics",
    "normalize_similarity_hit",
    "normalize_structure_similarity_hit",
    "q3_bucket",
    "resolve_step_inputs",
    "summarize_secondary_structure",
]

_HELIX_Q8 = {"H", "G", "I"}
_SHEET_Q8 = {"E", "B"}


def resolve_step_inputs(
    step: PlanStep,
    context: WorkflowContext,
    *,
    required_keys: Iterable[str] = (),
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
                    resolved[key] = context.get_step_output(step_id, field)
                except KeyError as exc:
                    raise ValueError(
                        f"Failed to resolve input reference '{val}' "
                        f"for step '{step.id}': field '{field}' not found in step '{step_id}' outputs"
                    ) from exc
                continue
        resolved[key] = val

    for key in required_keys:
        if key not in resolved:
            raise ValueError(f"Missing required input '{key}' for step '{step.id}'")

    resolved["task_id"] = context.task.task_id
    resolved["step_id"] = step.id
    return resolved


def normalize_similarity_hit(raw: Dict[str, Any], *, rank: int) -> Dict[str, Any]:
    alignment_length = _to_int(raw.get("alignment_length"))
    query_length = _to_int(raw.get("query_length"))
    target_length = _to_int(raw.get("target_length"))
    query_coverage = _bounded_fraction(alignment_length, query_length)
    target_coverage = _bounded_fraction(alignment_length, target_length)
    coverage = query_coverage

    return {
        "rank": rank,
        "query_id": _to_str(raw.get("query_id")) or "query_1",
        "target_id": _to_str(raw.get("target_id")) or f"target_{rank}",
        "identity": _to_float(raw.get("identity")),
        "coverage": coverage,
        "query_coverage": query_coverage,
        "target_coverage": target_coverage,
        "evalue": _to_float(raw.get("evalue")),
        "bitscore": _to_float(raw.get("bitscore")),
        "alignment_length": alignment_length,
        "query_start": _to_int(raw.get("query_start")),
        "query_end": _to_int(raw.get("query_end")),
        "target_start": _to_int(raw.get("target_start")),
        "target_end": _to_int(raw.get("target_end")),
        "query_length": query_length,
        "target_length": target_length,
    }


def build_similarity_outputs(
    tool_id: str,
    inputs: Dict[str, Any],
    hits: list[Dict[str, Any]],
) -> Dict[str, Any]:
    normalized_hits = [
        normalize_similarity_hit(hit, rank=index)
        for index, hit in enumerate(hits, start=1)
    ]
    top_hit = normalized_hits[0] if normalized_hits else None
    return {
        "tool_id": tool_id,
        "capability_id": "sequence_similarity_search",
        "io_type": "sequence_to_similarity_hits",
        "sequence": _to_str(inputs.get("sequence")),
        "query_id": _to_str(inputs.get("query_id")) or "query_1",
        "database_path": _to_str(inputs.get("database_path")),
        "similarity_hits": normalized_hits,
        "hit_count": len(normalized_hits),
        "top_hit": top_hit,
    }


def build_similarity_metrics(
    *,
    exec_type: str,
    hit_count: int,
    command: list[str] | None = None,
) -> Dict[str, Any]:
    metrics: Dict[str, Any] = {
        "exec_type": exec_type,
        "hit_count": hit_count,
        "requirement2": {
            "capability_id": "sequence_similarity_search",
            "io_type": "sequence_to_similarity_hits",
        },
    }
    if command:
        metrics["command"] = list(command)
    return metrics


def normalize_structure_similarity_hit(raw: Dict[str, Any], *, rank: int) -> Dict[str, Any]:
    return {
        "rank": rank,
        "query_id": _to_str(raw.get("query_id")) or "query_1",
        "target_id": _to_str(raw.get("target_id")) or f"structure_{rank}",
        "tm_score": _to_float(raw.get("tm_score")),
        "lddt": _to_float(raw.get("lddt")),
        "evalue": _to_float(raw.get("evalue")),
        "bitscore": _to_float(raw.get("bitscore")),
        "alignment_length": _to_int(raw.get("alignment_length")),
        "query_length": _to_int(raw.get("query_length")),
        "target_length": _to_int(raw.get("target_length")),
    }


def build_structure_similarity_outputs(
    tool_id: str,
    inputs: Dict[str, Any],
    hits: list[Dict[str, Any]],
) -> Dict[str, Any]:
    normalized_hits = [
        normalize_structure_similarity_hit(hit, rank=index)
        for index, hit in enumerate(hits, start=1)
    ]
    top_hit = normalized_hits[0] if normalized_hits else None
    return {
        "tool_id": tool_id,
        "capability_id": "structure_similarity_search",
        "io_type": "structure_to_similarity_hits",
        "pdb_path": _to_str(inputs.get("pdb_path")),
        "database_path": _to_str(inputs.get("database_path")),
        "structure_similarity_hits": normalized_hits,
        "hit_count": len(normalized_hits),
        "top_hit": top_hit,
    }


def build_structure_similarity_metrics(
    *,
    exec_type: str,
    hit_count: int,
    command: list[str] | None = None,
) -> Dict[str, Any]:
    metrics: Dict[str, Any] = {
        "exec_type": exec_type,
        "hit_count": hit_count,
        "requirement2": {
            "capability_id": "structure_similarity_search",
            "io_type": "structure_to_similarity_hits",
        },
    }
    if command:
        metrics["command"] = list(command)
    return metrics


def q3_bucket(q8_code: str) -> str:
    if q8_code in _HELIX_Q8:
        return "H"
    if q8_code in _SHEET_Q8:
        return "E"
    return "C"


def summarize_secondary_structure(rows: list[Dict[str, Any]]) -> Dict[str, Any]:
    q8_codes = [str(row.get("q8") or "C") for row in rows]
    q8_counts = Counter(q8_codes)
    q3_counts = Counter(q3_bucket(code) for code in q8_codes)
    residue_count = len(rows)
    return {
        "residue_count": residue_count,
        "q8_counts": dict(q8_counts),
        "q8_fraction": {
            code: round(count / residue_count, 6)
            for code, count in sorted(q8_counts.items())
        } if residue_count else {},
        "q3_counts": dict(q3_counts),
        "q3_fraction": {
            code: round(count / residue_count, 6)
            for code, count in sorted(q3_counts.items())
        } if residue_count else {},
    }


def build_secondary_structure_outputs(
    tool_id: str,
    inputs: Dict[str, Any],
    rows: list[Dict[str, Any]],
) -> Dict[str, Any]:
    summary = summarize_secondary_structure(rows)
    return {
        "tool_id": tool_id,
        "capability_id": "secondary_structure_annotation",
        "capabilities": ["secondary_structure_annotation", "quality_qc"],
        "io_type": "sequence_structure_to_qc_metrics",
        "sequence": _to_str(inputs.get("sequence")),
        "pdb_path": _to_str(inputs.get("pdb_path")),
        "secondary_structure": rows,
        "secondary_structure_summary": summary,
        "qc_metrics": {
            "secondary_structure_summary": summary,
        },
    }


def build_secondary_structure_metrics(
    *,
    exec_type: str,
    residue_count: int,
    command: list[str] | None = None,
) -> Dict[str, Any]:
    metrics: Dict[str, Any] = {
        "exec_type": exec_type,
        "residue_count": residue_count,
        "requirement2": {
            "capability_id": "quality_qc",
            "io_type": "sequence_structure_to_qc_metrics",
            "additional_capabilities": ["secondary_structure_annotation"],
        },
    }
    if command:
        metrics["command"] = list(command)
    return metrics


def build_function_annotation_outputs(
    tool_id: str,
    inputs: Dict[str, Any],
    function_terms: list[Dict[str, Any]],
) -> Dict[str, Any]:
    analysis_counts = Counter(
        str(item.get("analysis") or "unknown")
        for item in function_terms
    )
    return {
        "tool_id": tool_id,
        "capability_id": "function_annotation",
        "io_type": "sequence_or_structure_to_function_terms",
        "sequence": _to_str(inputs.get("sequence")),
        "pdb_path": _to_str(inputs.get("pdb_path")),
        "function_terms": function_terms,
        "annotation_summary": {
            "term_count": len(function_terms),
            "analysis_counts": dict(analysis_counts),
        },
    }


def build_function_annotation_metrics(
    *,
    exec_type: str,
    term_count: int,
    command: list[str] | None = None,
) -> Dict[str, Any]:
    metrics: Dict[str, Any] = {
        "exec_type": exec_type,
        "term_count": term_count,
        "requirement2": {
            "capability_id": "function_annotation",
            "io_type": "sequence_or_structure_to_function_terms",
        },
    }
    if command:
        metrics["command"] = list(command)
    return metrics


def build_objective_outputs(
    tool_id: str,
    inputs: Dict[str, Any],
    scored_candidates: list[Dict[str, Any]],
    *,
    default_recommendation: str | None,
    explanation: str,
) -> Dict[str, Any]:
    top_score = (
        _to_float(scored_candidates[0].get("objective_score"))
        if scored_candidates
        else None
    )
    return {
        "tool_id": tool_id,
        "capability_id": "objective_scoring",
        "io_type": "candidates_to_objective_scores_topk",
        "score_table": scored_candidates,
        "top_k": scored_candidates,
        "default_recommendation": default_recommendation,
        "objective_score": top_score,
        "score_breakdown": (
            dict(scored_candidates[0].get("score_breakdown", {}))
            if scored_candidates
            else {}
        ),
        "objective_explanation": explanation,
        "explanation": explanation,
        "candidate_count": len(scored_candidates),
        "input_candidate_count": _to_int(inputs.get("input_candidate_count")) or len(scored_candidates),
    }


def build_objective_metrics(
    *,
    exec_type: str,
    candidate_count: int,
) -> Dict[str, Any]:
    return {
        "exec_type": exec_type,
        "candidate_count": candidate_count,
        "requirement2": {
            "capability_id": "objective_scoring",
            "io_type": "candidates_to_objective_scores_topk",
        },
    }


def build_stability_outputs(
    tool_id: str,
    inputs: Dict[str, Any],
    stability_metrics: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "tool_id": tool_id,
        "capability_id": "stability_simulation",
        "io_type": "trajectory_to_stability_metrics",
        "pdb_path": _to_str(inputs.get("pdb_path")),
        "trajectory_path": _to_str(inputs.get("trajectory_path")),
        "stability_metrics": stability_metrics,
    }


def build_stability_metrics(
    *,
    exec_type: str,
    frame_count: int,
) -> Dict[str, Any]:
    return {
        "exec_type": exec_type,
        "frame_count": frame_count,
        "requirement2": {
            "capability_id": "stability_simulation",
            "io_type": "trajectory_to_stability_metrics",
        },
    }


def build_docking_outputs(
    tool_id: str,
    inputs: Dict[str, Any],
    poses: list[Dict[str, Any]],
) -> Dict[str, Any]:
    best_pose = poses[0] if poses else None
    best_affinity = _to_float(best_pose.get("affinity")) if isinstance(best_pose, dict) else None
    return {
        "tool_id": tool_id,
        "capability_id": "docking_scoring",
        "io_type": "structure_ligand_to_binding_score",
        "receptor_path": _to_str(inputs.get("receptor_path")),
        "ligand_path": _to_str(inputs.get("ligand_path")),
        "docking_poses": poses,
        "best_pose": best_pose,
        "binding_score": best_affinity,
    }


def build_docking_metrics(
    *,
    exec_type: str,
    pose_count: int,
    command: list[str] | None = None,
) -> Dict[str, Any]:
    metrics: Dict[str, Any] = {
        "exec_type": exec_type,
        "pose_count": pose_count,
        "requirement2": {
            "capability_id": "docking_scoring",
            "io_type": "structure_ligand_to_binding_score",
        },
    }
    if command:
        metrics["command"] = list(command)
    return metrics


def _to_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.strip():
        try:
            return int(float(value))
        except ValueError:
            return None
    return None


def _to_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _to_str(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _bounded_fraction(numerator: int | None, denominator: int | None) -> float | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return round(min(max(numerator / denominator, 0.0), 1.0), 6)
