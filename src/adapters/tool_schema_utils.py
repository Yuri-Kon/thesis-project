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
                    message = (
                        f"Failed to resolve input reference '{val}' for step " +
                        f"'{step.id}': step '{step_id}' not found in context"
                    )
                    raise ValueError(message)
                try:
                    resolved[key] = context.get_step_output(step_id, field)
                except KeyError as exc:
                    message = (
                        f"Failed to resolve input reference '{val}' for step " +
                        f"'{step.id}': field '{field}' not found in step " +
                        f"'{step_id}' outputs"
                    )
                    raise ValueError(message) from exc
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


def normalize_structure_similarity_hit(
    raw: Dict[str, Any],
    *,
    rank: int,
    query_structure: str | None = None,
    database: str | None = None,
    artifact_refs: list[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    alignment_length = _to_int(raw.get("alignment_length"))
    query_length = _to_int(raw.get("query_length"))
    target_length = _to_int(raw.get("target_length"))
    query_coverage = _bounded_fraction(alignment_length, query_length)
    target_coverage = _bounded_fraction(alignment_length, target_length)
    tm_score = _to_float(raw.get("tm_score"))
    bitscore = _to_float(raw.get("bitscore"))
    warnings: list[str] = []
    if tm_score is None:
        warnings.append("tm_score missing from structure similarity hit")
    if query_coverage is None:
        warnings.append("query coverage unavailable")
    return {
        "rank": rank,
        "query_id": _to_str(raw.get("query_id")) or "query_1",
        "target_id": _to_str(raw.get("target_id")) or f"structure_{rank}",
        "hit_id": _to_str(raw.get("hit_id"))
        or _to_str(raw.get("target_id"))
        or f"structure_{rank}",
        "query_structure": query_structure,
        "database": database,
        "tm_score": tm_score,
        "query_tm_score": _to_float(raw.get("query_tm_score")),
        "target_tm_score": _to_float(raw.get("target_tm_score")),
        "rmsd": _to_float(raw.get("rmsd")),
        "alignment_score": tm_score if tm_score is not None else bitscore,
        "lddt": _to_float(raw.get("lddt")),
        "probability": _to_float(raw.get("probability")),
        "evalue": _to_float(raw.get("evalue")),
        "e_value": _to_float(raw.get("evalue")),
        "bitscore": bitscore,
        "coverage": query_coverage,
        "query_coverage": query_coverage,
        "target_coverage": target_coverage,
        "alignment_length": alignment_length,
        "query_length": query_length,
        "target_length": target_length,
        "artifact_refs": list(artifact_refs or []),
        "warnings": warnings,
    }


def build_structure_similarity_outputs(
    tool_id: str,
    inputs: Dict[str, Any],
    hits: list[Dict[str, Any]],
) -> Dict[str, Any]:
    artifact_refs = inputs.get("artifact_refs")
    normalized_artifact_refs = (
        [item for item in artifact_refs if isinstance(item, dict)]
        if isinstance(artifact_refs, list)
        else []
    )
    query_structure = _to_str(inputs.get("pdb_path"))
    database = _to_str(inputs.get("database_path"))
    normalized_hits = [
        normalize_structure_similarity_hit(
            hit,
            rank=index,
            query_structure=query_structure,
            database=database,
            artifact_refs=normalized_artifact_refs,
        )
        for index, hit in enumerate(hits, start=1)
    ]
    top_hit = normalized_hits[0] if normalized_hits else None
    return {
        "tool_id": tool_id,
        "capability_id": "structure_similarity_search",
        "io_type": "structure_to_similarity_hits",
        "pdb_path": query_structure,
        "query_structure": query_structure,
        "database_path": database,
        "database": database,
        "structure_similarity_hits": normalized_hits,
        "hit_count": len(normalized_hits),
        "top_hit": top_hit,
        "artifact_refs": normalized_artifact_refs,
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
    top_k_candidates: list[Dict[str, Any]] | None = None,
    default_recommendation: str | None,
    explanation: str,
) -> Dict[str, Any]:
    top_k_rows = top_k_candidates if top_k_candidates is not None else scored_candidates
    top_score = (
        _to_float(top_k_rows[0].get("objective_score"))
        if top_k_rows
        else None
    )
    component_scores = {
        str(row.get("candidate_id") or f"candidate_{index}"): dict(
            row.get("component_scores") or row.get("score_breakdown") or {}
        )
        for index, row in enumerate(scored_candidates, start=1)
    }
    warnings = _unique_strings(
        warning
        for row in scored_candidates
        for warning in row.get("warnings", [])
        if isinstance(row.get("warnings"), list)
    )
    evidence_refs = [
        ref
        for row in scored_candidates
        for ref in row.get("evidence_refs", [])
        if isinstance(row.get("evidence_refs"), list) and isinstance(ref, dict)
    ]
    posterior_scores: dict[str, Dict[str, Any]] = {}
    posterior_objectives: dict[str, Dict[str, Any]] = {}
    for index, row in enumerate(scored_candidates, start=1):
        candidate_id = str(row.get("candidate_id") or f"candidate_{index}")
        posterior_score = row.get("posterior_score")
        if isinstance(posterior_score, dict):
            posterior_scores[candidate_id] = dict(posterior_score)
        posterior_objective = row.get("posterior_objective")
        if isinstance(posterior_objective, dict):
            posterior_objectives[candidate_id] = dict(posterior_objective)
    top_posterior_score: Dict[str, Any] = {}
    top_posterior_objective: Dict[str, Any] = {}
    if top_k_rows:
        raw_top_posterior = top_k_rows[0].get("posterior_score")
        if isinstance(raw_top_posterior, dict):
            top_posterior_score = dict(raw_top_posterior)
        raw_top_posterior_objective = top_k_rows[0].get("posterior_objective")
        if isinstance(raw_top_posterior_objective, dict):
            top_posterior_objective = dict(raw_top_posterior_objective)
    component_weights: Dict[str, Any] = {}
    raw_component_weights = top_posterior_score.get("component_weights")
    if isinstance(raw_component_weights, dict):
        component_weights = dict(raw_component_weights)
    rank_reason = (
        _to_str(scored_candidates[0].get("rank_reason")) if scored_candidates else None
    )
    return {
        "tool_id": tool_id,
        "capability_id": "objective_scoring",
        "io_type": "candidates_to_objective_scores_topk",
        "score_table": scored_candidates,
        "top_k": top_k_rows,
        "component_scores": component_scores,
        "posterior_score": top_posterior_score,
        "posterior_scores": posterior_scores,
        "posterior_objective": top_posterior_objective,
        "posterior_objectives": posterior_objectives,
        "aggregate_score": top_score,
        "component_weights": component_weights,
        "default_recommendation": default_recommendation,
        "objective_score": top_score,
        "score_breakdown": (
            dict(scored_candidates[0].get("score_breakdown", {}))
            if scored_candidates
            else {}
        ),
        "warnings": warnings,
        "evidence_refs": evidence_refs,
        "rank_reason": rank_reason,
        "objective_explanation": explanation,
        "explanation": explanation,
        "candidate_count": len(scored_candidates),
        "top_k_count": len(top_k_rows),
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


def _unique_strings(values: Iterable[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = _to_str(value)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


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
