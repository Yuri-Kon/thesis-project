from __future__ import annotations

from time import perf_counter
from typing import Any, Dict, Tuple

from src.adapters.base_tool_adapter import BaseToolAdapter
from src.adapters.tool_schema_utils import (
    build_objective_metrics,
    build_objective_outputs,
    resolve_step_inputs,
)
from src.models.contracts import PlanStep
from src.workflow.context import WorkflowContext
from src.workflow.errors import FailureCode, FailureType, StepRunError

__all__ = ["ObjectiveRankerAdapter"]

_DEFAULT_WEIGHTS = {
    "quality": 0.35,
    "novelty": 0.2,
    "stability": 0.2,
    "function": 0.15,
    "docking": 0.1,
}


class ObjectiveRankerAdapter(BaseToolAdapter):
    """对候选进行规则化目标评分。"""

    tool_id = "objective_ranker"
    adapter_id = "objective_ranker"

    def resolve_inputs(self, step: PlanStep, context: WorkflowContext) -> Dict[str, Any]:
        return resolve_step_inputs(step, context, required_keys=("candidates",))

    def run_local(self, inputs: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        candidates = inputs.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            raise StepRunError(
                failure_type=FailureType.NON_RETRYABLE,
                message="objective_ranker requires non-empty 'candidates' list",
                code=FailureCode.CANDIDATE_PARAMS_INVALID.value,
            )

        t0 = perf_counter()
        weights = _resolve_weights(inputs.get("objective_weights"))
        scored_candidates = [_score_candidate(candidate, index=index, weights=weights) for index, candidate in enumerate(candidates, start=1)]
        scored_candidates.sort(
            key=lambda item: (
                float(item.get("objective_score", 0.0)),
                float(item.get("score_breakdown", {}).get("quality", 0.0)),
            ),
            reverse=True,
        )

        top_k = _resolve_top_k(inputs.get("top_k"), default=len(scored_candidates))
        selected = scored_candidates[:top_k]
        for rank, item in enumerate(selected, start=1):
            item["top_k_rank"] = rank
        default_recommendation = (
            str(selected[0]["candidate_id"])
            if selected
            else None
        )
        explanation = (
            "objective_ranker combined quality, novelty, stability, function, "
            "and docking proxy signals."
        )
        outputs = build_objective_outputs(
            self.tool_id,
            {**inputs, "input_candidate_count": len(candidates)},
            selected,
            default_recommendation=default_recommendation,
            explanation=explanation,
        )
        metrics = build_objective_metrics(
            exec_type="python",
            candidate_count=len(candidates),
        )
        metrics["duration_ms"] = int((perf_counter() - t0) * 1000)
        metrics["weights"] = weights
        return outputs, metrics


def _resolve_weights(raw: Any) -> Dict[str, float]:
    if not isinstance(raw, dict):
        return dict(_DEFAULT_WEIGHTS)

    resolved = dict(_DEFAULT_WEIGHTS)
    for key, value in raw.items():
        if key not in resolved:
            continue
        try:
            resolved[key] = max(0.0, float(value))
        except (TypeError, ValueError):
            continue

    total = sum(resolved.values())
    if total <= 0:
        return dict(_DEFAULT_WEIGHTS)
    return {
        key: round(value / total, 6)
        for key, value in resolved.items()
    }


def _resolve_top_k(raw: Any, *, default: int) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = default
    return max(1, value)


def _score_candidate(
    candidate: Any,
    *,
    index: int,
    weights: Dict[str, float],
) -> Dict[str, Any]:
    row = candidate if isinstance(candidate, dict) else {}
    candidate_id = str(
        row.get("candidate_id")
        or row.get("id")
        or f"candidate_{index}"
    )

    quality = _quality_score(row)
    novelty = _novelty_score(row)
    stability = _stability_score(row)
    function = _function_score(row)
    docking = _docking_score(row)
    score_breakdown = {
        "quality": quality,
        "novelty": novelty,
        "stability": stability,
        "function": function,
        "docking": docking,
    }
    objective_score = round(
        sum(score_breakdown[key] * weights[key] for key in score_breakdown),
        6,
    )

    return {
        **row,
        "candidate_id": candidate_id,
        "objective_score": objective_score,
        "score_breakdown": score_breakdown,
        "top_k_rank": index,
        "objective_explanation": (
            f"quality={quality:.3f}, novelty={novelty:.3f}, stability={stability:.3f}, "
            f"function={function:.3f}, docking={docking:.3f}"
        ),
    }


def _quality_score(candidate: Dict[str, Any]) -> float:
    plddt = _as_float(candidate.get("plddt"))
    if plddt is None:
        plddt = _as_float(_deep_get(candidate, "metrics", "plddt_mean"))
    qc_metrics = candidate.get("qc_metrics")
    pass_fail = candidate.get("pass_fail")
    if pass_fail is None and isinstance(qc_metrics, dict):
        pass_fail = qc_metrics.get("pass_fail")

    qc_bonus = 0.15 if pass_fail is True else 0.0
    plddt_score = 0.5 if plddt is None else min(max(plddt / 100.0, 0.0), 1.0)
    return round(min(1.0, plddt_score + qc_bonus), 6)


def _novelty_score(candidate: Dict[str, Any]) -> float:
    identity = _extract_similarity_value(candidate, "identity")
    if identity is None:
        return 0.55
    if identity > 1:
        identity = identity / 100.0
    return round(min(max(1.0 - identity, 0.0), 1.0), 6)


def _stability_score(candidate: Dict[str, Any]) -> float:
    stability_metrics = candidate.get("stability_metrics")
    if not isinstance(stability_metrics, dict):
        return 0.5
    rg = _as_float(stability_metrics.get("radius_of_gyration"))
    span = _as_float(stability_metrics.get("coordinate_span"))
    base = 0.75
    if rg is not None:
        base -= min(rg / 100.0, 0.2)
    if span is not None:
        base -= min(span / 200.0, 0.15)
    return round(min(max(base, 0.0), 1.0), 6)


def _function_score(candidate: Dict[str, Any]) -> float:
    summary = candidate.get("annotation_summary")
    if isinstance(summary, dict):
        term_count = summary.get("term_count")
        if isinstance(term_count, int):
            return round(min(term_count / 10.0, 1.0), 6)
    function_terms = candidate.get("function_terms")
    if isinstance(function_terms, list):
        return round(min(len(function_terms) / 10.0, 1.0), 6)
    return 0.4


def _docking_score(candidate: Dict[str, Any]) -> float:
    binding_score = _as_float(candidate.get("binding_score"))
    if binding_score is None:
        best_pose = candidate.get("best_pose")
        if isinstance(best_pose, dict):
            binding_score = _as_float(best_pose.get("affinity"))
    if binding_score is None:
        return 0.4
    if binding_score >= 0:
        return 0.0
    return round(min(abs(binding_score) / 15.0, 1.0), 6)


def _extract_similarity_value(candidate: Dict[str, Any], key: str) -> float | None:
    top_hit = candidate.get("top_hit")
    if isinstance(top_hit, dict):
        value = _as_float(top_hit.get(key))
        if value is not None:
            return value
    hits = candidate.get("similarity_hits")
    if isinstance(hits, list) and hits and isinstance(hits[0], dict):
        return _as_float(hits[0].get(key))
    structure_hits = candidate.get("structure_similarity_hits")
    if isinstance(structure_hits, list) and structure_hits and isinstance(structure_hits[0], dict):
        return _as_float(structure_hits[0].get(key))
    return None


def _deep_get(candidate: Dict[str, Any], *path: str) -> Any:
    current: Any = candidate
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _as_float(value: Any) -> float | None:
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
