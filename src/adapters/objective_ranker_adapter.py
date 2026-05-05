from __future__ import annotations

from time import perf_counter
from typing import Any, Dict, Literal, Tuple, override

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

_POSTERIOR_SCORE_SCHEMA_VERSION = "posterior_score.v1"
_POSTERIOR_OBJECTIVE_SCHEMA_VERSION = "posterior_objective.v1"
_POSTERIOR_OBJECTIVE_SOURCE_REFS = [
    "sid:algo.posterior_objective_scoring",
    "impl:posterior_score.v1",
]
_POSTERIOR_COMPONENTS = (
    "generic_objective",
    "stability",
    "function",
    "novelty",
    "structure_quality",
)
_DEFAULT_WEIGHTS: dict[str, float] = {
    "generic_objective": 0.1,
    "stability": 0.2,
    "function": 0.15,
    "novelty": 0.2,
    "structure_quality": 0.35,
}
_OBJECTIVE_TYPE_WEIGHT_PRESETS: dict[str, dict[str, float]] = {
    "stability": {
        "stability": 0.45,
        "structure_quality": 0.25,
        "novelty": 0.15,
        "function": 0.05,
        "generic_objective": 0.10,
    },
    "structure": {
        "structure_quality": 0.45,
        "stability": 0.25,
        "novelty": 0.15,
        "function": 0.05,
        "generic_objective": 0.10,
    },
    "structure_quality": {
        "structure_quality": 0.45,
        "stability": 0.25,
        "novelty": 0.15,
        "function": 0.05,
        "generic_objective": 0.10,
    },
    "function": {
        "function": 0.45,
        "structure_quality": 0.20,
        "stability": 0.15,
        "novelty": 0.10,
        "generic_objective": 0.10,
    },
    "activity": {
        "function": 0.40,
        "generic_objective": 0.20,
        "structure_quality": 0.20,
        "stability": 0.10,
        "novelty": 0.10,
    },
    "binding": {
        "generic_objective": 0.35,
        "function": 0.20,
        "structure_quality": 0.20,
        "stability": 0.15,
        "novelty": 0.10,
    },
}
_WEIGHT_ALIASES = {
    "quality": "structure_quality",
    "docking": "generic_objective",
    "goal_fit": "generic_objective",
    "custom_score": "generic_objective",
    "objective": "generic_objective",
}
EvidenceStatus = Literal["direct", "proxy", "degraded"]


class ObjectiveRankerAdapter(BaseToolAdapter):
    """对候选进行规则化目标评分。"""

    tool_id: str = "objective_ranker"
    adapter_id: str | None = "objective_ranker"

    @override
    def resolve_inputs(self, step: PlanStep, context: WorkflowContext) -> Dict[str, Any]:
        return resolve_step_inputs(step, context, required_keys=("candidates",))

    @override
    def run_local(self, inputs: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        candidates = inputs.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            raise StepRunError(
                failure_type=FailureType.NON_RETRYABLE,
                message="objective_ranker requires non-empty 'candidates' list",
                code=FailureCode.CANDIDATE_PARAMS_INVALID.value,
            )

        t0 = perf_counter()
        objective_type, raw_weights = _extract_objective_config(inputs)
        weights = _resolve_weights(raw_weights, objective_type=objective_type)
        shared_context = _extract_shared_context(inputs)
        scored_candidates = [
            _score_candidate(
                _merge_candidate_context(candidate, shared_context),
                index=index,
                weights=weights,
                objective_type=objective_type,
            )
            for index, candidate in enumerate(candidates, start=1)
        ]
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
            scored_candidates,
            top_k_candidates=selected,
            default_recommendation=default_recommendation,
            explanation=explanation,
        )
        metrics = build_objective_metrics(
            exec_type="python",
            candidate_count=len(candidates),
        )
        metrics["duration_ms"] = int((perf_counter() - t0) * 1000)
        metrics["weights"] = weights
        metrics["component_weights"] = weights
        if objective_type is not None:
            metrics["objective_type"] = objective_type
        metrics["objective_progress"] = outputs.get("objective_score")
        metrics["objective_gap"] = _objective_gap(scored_candidates)
        metrics["warning_count"] = len(outputs.get("warnings") or [])
        top_posterior = outputs.get("posterior_score")
        if isinstance(top_posterior, dict):
            metrics["evidence_sufficiency"] = top_posterior.get("evidence_sufficiency")
        if default_recommendation:
            metrics["top_candidate_id"] = default_recommendation
        return outputs, metrics


def _extract_objective_config(inputs: Dict[str, Any]) -> tuple[str | None, Any]:
    task_constraints = inputs.get("task_constraints")
    objective: Any = None
    if isinstance(task_constraints, dict):
        objective = task_constraints.get("objective")
    if not isinstance(objective, dict):
        objective = inputs.get("objective")
    if not isinstance(objective, dict):
        objective = {}

    objective_type = _normalize_objective_type(
        inputs.get("objective_type") or objective.get("objective_type")
    )
    raw_weights = inputs.get("objective_weights")
    if raw_weights is None:
        raw_weights = objective.get("objective_weights")
    return objective_type, raw_weights


def _normalize_objective_type(raw: Any) -> str | None:
    if isinstance(raw, str) and raw.strip():
        return _normalize_weight_key(raw)
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, str) and item.strip():
                return _normalize_weight_key(item)
    return None


def _normalize_weight_key(raw: str) -> str:
    key = raw.strip().lower()
    return _WEIGHT_ALIASES.get(key, key)


def _resolve_weights(raw: Any, *, objective_type: str | None = None) -> Dict[str, float]:
    base = _OBJECTIVE_TYPE_WEIGHT_PRESETS.get(objective_type or "", _DEFAULT_WEIGHTS)
    if not isinstance(raw, dict):
        return dict(base)

    resolved = {key: 0.0 for key in _POSTERIOR_COMPONENTS}
    for key, value in raw.items():
        normalized_key = _normalize_weight_key(str(key))
        if normalized_key not in resolved:
            continue
        try:
            resolved[normalized_key] = max(0.0, float(value))
        except (TypeError, ValueError):
            continue

    total = sum(resolved.values())
    if total <= 0:
        return dict(base)
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


def _extract_shared_context(inputs: Dict[str, Any]) -> Dict[str, Any]:
    keys = (
        "sequence",
        "structure_pdb",
        "pdb_path",
        "qc_metrics",
        "similarity_hits",
        "structure_similarity_hits",
        "secondary_structure_summary",
        "task_constraints",
    )
    return {key: inputs[key] for key in keys if key in inputs}


def _merge_candidate_context(
    candidate: Any,
    shared_context: Dict[str, Any],
) -> Dict[str, Any]:
    row = dict(candidate) if isinstance(candidate, dict) else {}
    for key, value in shared_context.items():
        row.setdefault(key, value)
    return row


def _score_candidate(
    candidate: Any,
    *,
    index: int,
    weights: Dict[str, float],
    objective_type: str | None,
) -> Dict[str, Any]:
    row = candidate if isinstance(candidate, dict) else {}
    candidate_id = str(
        row.get("candidate_id")
        or row.get("id")
        or f"candidate_{index}"
    )

    structure_quality = _structure_quality_component(row)
    novelty = _novelty_component(row)
    stability = _stability_component(row)
    function = _function_component(row)
    generic_objective = _generic_objective_component(row)
    docking = _docking_score(row)
    posterior_components = {
        "generic_objective": generic_objective,
        "stability": stability,
        "function": function,
        "novelty": novelty,
        "structure_quality": structure_quality,
    }
    score_breakdown = {
        "quality": _component_effective_score(structure_quality),
        "structure_quality": _component_effective_score(structure_quality),
        "novelty": _component_effective_score(novelty),
        "stability": _component_effective_score(stability),
        "function": _component_effective_score(function),
        "generic_objective": _component_effective_score(generic_objective),
        "docking": docking,
    }
    objective_score = round(
        sum(
            _component_effective_score(posterior_components[key]) * weights[key]
            for key in _POSTERIOR_COMPONENTS
        ),
        6,
    )
    warnings = _candidate_warnings(row)
    evidence_refs = _candidate_evidence_refs(row, candidate_id)
    posterior_score = _build_posterior_score(
        aggregate_score=objective_score,
        objective_type=objective_type,
        components=posterior_components,
        component_weights=weights,
        evidence_refs=evidence_refs,
        warnings=warnings,
    )
    posterior_objective = _normalize_posterior_objective(
        posterior_score,
        candidate=row,
    )
    rank_reason = _rank_reason(
        candidate_id=candidate_id,
        objective_score=objective_score,
        score_breakdown=score_breakdown,
        warnings=warnings,
    )

    return {
        **row,
        "candidate_id": candidate_id,
        "objective_score": objective_score,
        "aggregate_score": objective_score,
        "posterior_score": posterior_score,
        "posterior_objective": posterior_objective,
        "score_breakdown": score_breakdown,
        "component_scores": score_breakdown,
        "top_k_rank": index,
        "objective_explanation": (
            f"structure_quality={score_breakdown['structure_quality']:.3f}, "
            f"novelty={score_breakdown['novelty']:.3f}, "
            f"stability={score_breakdown['stability']:.3f}, "
            f"function={score_breakdown['function']:.3f}, "
            f"generic_objective={score_breakdown['generic_objective']:.3f}"
        ),
        "rank_reason": rank_reason,
        "warnings": warnings,
        "evidence_refs": evidence_refs,
    }


def _component_effective_score(component: Dict[str, Any]) -> float:
    score = _as_float(component.get("score"))
    if score is not None:
        return score
    proxy_score = _as_float(component.get("proxy_score"))
    if proxy_score is not None:
        return proxy_score
    return 0.5


def _make_component(
    *,
    score: float | None,
    proxy_score: float | None,
    evidence_status: EvidenceStatus,
    source_fields: list[str],
    warning: str | None = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "score": score,
        "proxy_score": proxy_score,
        "effective_score": score if score is not None else proxy_score if proxy_score is not None else 0.5,
        "evidence_status": evidence_status,
        "source_fields": source_fields,
    }
    if warning:
        payload["warning"] = warning
    return payload


def _structure_quality_component(candidate: Dict[str, Any]) -> Dict[str, Any]:
    score = _quality_score(candidate)
    fields = _present_fields(candidate, ("plddt", "metrics", "qc_metrics", "pass_fail"))
    if fields:
        return _make_component(
            score=score,
            proxy_score=None,
            evidence_status="direct",
            source_fields=fields,
        )
    return _make_component(
        score=None,
        proxy_score=score,
        evidence_status="degraded",
        source_fields=[],
        warning="structure_quality uses degraded evidence because pLDDT/QC metrics are missing",
    )


def _novelty_component(candidate: Dict[str, Any]) -> Dict[str, Any]:
    score = _novelty_score(candidate)
    fields = _present_fields(candidate, ("similarity_hits", "structure_similarity_hits", "top_hit"))
    if fields:
        return _make_component(
            score=score,
            proxy_score=None,
            evidence_status="direct",
            source_fields=fields,
        )
    return _make_component(
        score=None,
        proxy_score=score,
        evidence_status="degraded",
        source_fields=[],
        warning="novelty uses degraded evidence because similarity hits are missing",
    )


def _stability_component(candidate: Dict[str, Any]) -> Dict[str, Any]:
    score = _stability_score(candidate)
    if isinstance(candidate.get("stability_metrics"), dict):
        return _make_component(
            score=score,
            proxy_score=None,
            evidence_status="direct",
            source_fields=["stability_metrics"],
        )
    fields = _present_fields(candidate, ("secondary_structure_summary",))
    return _make_component(
        score=None,
        proxy_score=score,
        evidence_status="degraded",
        source_fields=fields,
        warning="stability uses degraded evidence because stability simulation metrics are missing",
    )


def _function_component(candidate: Dict[str, Any]) -> Dict[str, Any]:
    score = _function_score(candidate)
    fields = _present_fields(candidate, ("annotation_summary", "function_terms"))
    if fields:
        return _make_component(
            score=score,
            proxy_score=None,
            evidence_status="direct",
            source_fields=fields,
        )
    return _make_component(
        score=None,
        proxy_score=score,
        evidence_status="degraded",
        source_fields=[],
        warning="function uses degraded evidence because annotation evidence is missing",
    )


def _generic_objective_component(candidate: Dict[str, Any]) -> Dict[str, Any]:
    for field_name in ("generic_objective_score", "goal_fit_score", "custom_score"):
        score = _as_float(candidate.get(field_name))
        if score is not None:
            return _make_component(
                score=round(min(max(score, 0.0), 1.0), 6),
                proxy_score=None,
                evidence_status="direct",
                source_fields=[field_name],
            )
    docking_score = _docking_score(candidate)
    fields = _present_fields(candidate, ("binding_score", "best_pose"))
    if fields:
        return _make_component(
            score=None,
            proxy_score=docking_score,
            evidence_status="proxy",
            source_fields=fields,
            warning="generic_objective uses binding proxy evidence",
        )
    return _make_component(
        score=None,
        proxy_score=0.5,
        evidence_status="degraded",
        source_fields=[],
        warning="generic_objective uses degraded evidence because explicit objective evidence is missing",
    )


def _build_posterior_score(
    *,
    aggregate_score: float,
    objective_type: str | None,
    components: Dict[str, Dict[str, Any]],
    component_weights: Dict[str, float],
    evidence_refs: list[Dict[str, Any]],
    warnings: list[str],
) -> Dict[str, Any]:
    direct_weight = sum(
        component_weights[key]
        for key in _POSTERIOR_COMPONENTS
        if components[key].get("evidence_status") == "direct"
    )
    proxy_weight = sum(
        component_weights[key]
        for key in _POSTERIOR_COMPONENTS
        if components[key].get("evidence_status") == "proxy"
    )
    posterior_warnings = list(warnings)
    for component in components.values():
        warning = component.get("warning")
        if isinstance(warning, str) and warning not in posterior_warnings:
            posterior_warnings.append(warning)
    payload: Dict[str, Any] = {
        "schema_version": _POSTERIOR_SCORE_SCHEMA_VERSION,
        "objective_type": objective_type,
        "generic_objective": components["generic_objective"],
        "stability": components["stability"],
        "function": components["function"],
        "novelty": components["novelty"],
        "structure_quality": components["structure_quality"],
        "aggregate_score": aggregate_score,
        "component_weights": dict(component_weights),
        "evidence_refs": list(evidence_refs),
        "warnings": posterior_warnings,
        "evidence_sufficiency": round(min(direct_weight + (0.5 * proxy_weight), 1.0), 6),
    }
    if posterior_warnings:
        payload["evidence_status"] = "degraded" if direct_weight < 0.8 else "partial"
    else:
        payload["evidence_status"] = "direct"
    return payload


def _normalize_posterior_objective(
    posterior_score: Dict[str, Any],
    *,
    candidate: Dict[str, Any],
) -> Dict[str, Any]:
    objective_type = posterior_score.get("objective_type")
    evidence_sufficiency = _as_float(posterior_score.get("evidence_sufficiency"))
    aggregate_score = _as_float(posterior_score.get("aggregate_score"))
    components = {
        key: dict(posterior_score[key])
        for key in _POSTERIOR_COMPONENTS
        if isinstance(posterior_score.get(key), dict)
    }
    raw_warnings = posterior_score.get("warnings")
    warnings = [
        item for item in raw_warnings if isinstance(item, str)
    ] if isinstance(raw_warnings, list) else []
    binding_proxy_fields: list[str] = []
    binding_proxy_component: str | None = None
    if objective_type == "binding":
        binding_proxy_component = "generic_objective"
        binding_proxy_fields = _present_fields(candidate, ("binding_score", "best_pose"))
        binding_warning = (
            "binding objective is represented through generic_objective proxy in v1"
        )
        if binding_warning not in warnings:
            warnings.append(binding_warning)
    raw_component_weights = posterior_score.get("component_weights")
    component_weights = (
        dict(raw_component_weights) if isinstance(raw_component_weights, dict) else {}
    )
    raw_evidence_refs = posterior_score.get("evidence_refs")
    evidence_refs = (
        list(raw_evidence_refs) if isinstance(raw_evidence_refs, list) else []
    )
    raw_evidence_status = posterior_score.get("evidence_status")
    return {
        "schema_version": _POSTERIOR_OBJECTIVE_SCHEMA_VERSION,
        "aggregate_score": round(min(max(aggregate_score or 0.0, 0.0), 1.0), 6),
        "components": components,
        "component_weights": component_weights,
        "evidence_sufficiency": round(
            min(
                max(
                    evidence_sufficiency if evidence_sufficiency is not None else 0.0,
                    0.0,
                ),
                1.0,
            ),
            6,
        ),
        "evidence_status": raw_evidence_status if isinstance(raw_evidence_status, str) else "degraded",
        "objective_type": objective_type if isinstance(objective_type, str) else None,
        "objective_source": "posterior_objective",
        "binding_proxy_component": binding_proxy_component,
        "binding_proxy_fields": binding_proxy_fields,
        "warnings": warnings,
        "evidence_refs": evidence_refs,
        "source_refs": list(_POSTERIOR_OBJECTIVE_SOURCE_REFS),
    }


def _quality_score(candidate: Dict[str, Any]) -> float:
    plddt = _as_float(candidate.get("plddt"))
    if plddt is None:
        plddt = _as_float(_deep_get(candidate, "metrics", "plddt_mean"))
    qc_metrics = candidate.get("qc_metrics")
    if plddt is None and isinstance(qc_metrics, dict):
        plddt = _as_float(qc_metrics.get("plddt_mean"))
    pass_fail = candidate.get("pass_fail")
    if pass_fail is None and isinstance(qc_metrics, dict):
        pass_fail = qc_metrics.get("pass_fail")

    qc_bonus = 0.15 if pass_fail is True else 0.0
    plddt_score = 0.5 if plddt is None else min(max(plddt / 100.0, 0.0), 1.0)
    return round(min(1.0, plddt_score + qc_bonus), 6)


def _novelty_score(candidate: Dict[str, Any]) -> float:
    similarity = _extract_novelty_similarity(candidate)
    if similarity is None:
        return 0.55
    if similarity > 1:
        similarity = similarity / 100.0
    return round(min(max(1.0 - similarity, 0.0), 1.0), 6)


def _stability_score(candidate: Dict[str, Any]) -> float:
    stability_metrics = candidate.get("stability_metrics")
    if not isinstance(stability_metrics, dict):
        secondary = candidate.get("secondary_structure_summary")
        if isinstance(secondary, dict):
            coil_fraction = _as_float(secondary.get("coil_fraction"))
            if coil_fraction is None:
                coil_fraction = _as_float(secondary.get("coil"))
            if coil_fraction is not None:
                return round(
                    min(max(0.75 - min(coil_fraction, 1.0) * 0.25, 0.0), 1.0),
                    6,
                )
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


def _extract_novelty_similarity(candidate: Dict[str, Any]) -> float | None:
    identity = _extract_similarity_value(candidate, "identity")
    if identity is not None:
        return identity
    tm_score = _extract_similarity_value(candidate, "tm_score")
    if tm_score is not None:
        return tm_score
    top_hit = candidate.get("top_hit")
    if isinstance(top_hit, dict):
        return _as_float(top_hit.get("alignment_score"))
    return None


def _candidate_warnings(candidate: Dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    qc_metrics = candidate.get("qc_metrics")
    qc_plddt = (
        _as_float(qc_metrics.get("plddt_mean")) if isinstance(qc_metrics, dict) else None
    )
    if _as_float(candidate.get("plddt")) is None and _as_float(
        _deep_get(candidate, "metrics", "plddt_mean")
    ) is None and qc_plddt is None:
        warnings.append("structure_quality uses degraded evidence because pLDDT/QC metrics are missing")
    if _extract_novelty_similarity(candidate) is None:
        warnings.append("novelty uses degraded evidence because similarity hits are missing")
    if not isinstance(candidate.get("stability_metrics"), dict) and not isinstance(
        candidate.get("secondary_structure_summary"),
        dict,
    ):
        warnings.append("stability uses degraded evidence because stability simulation metrics are missing")
    if not isinstance(candidate.get("annotation_summary"), dict) and not isinstance(
        candidate.get("function_terms"),
        list,
    ):
        warnings.append("function uses degraded evidence because annotation evidence is missing")
    if _as_float(candidate.get("binding_score")) is None and not isinstance(
        candidate.get("best_pose"),
        dict,
    ):
        warnings.append("generic_objective uses degraded evidence because explicit objective evidence is missing")
    return warnings


def _candidate_evidence_refs(
    candidate: Dict[str, Any],
    candidate_id: str,
) -> list[Dict[str, Any]]:
    refs: list[Dict[str, Any]] = []
    field_groups = {
        "structure_quality": ("plddt", "metrics", "qc_metrics", "pass_fail"),
        "novelty": ("similarity_hits", "structure_similarity_hits", "top_hit"),
        "stability": ("stability_metrics", "secondary_structure_summary"),
        "function": ("annotation_summary", "function_terms"),
        "generic_objective": ("generic_objective_score", "goal_fit_score", "custom_score", "binding_score", "best_pose"),
    }
    for component, fields in field_groups.items():
        present_fields = _present_fields(candidate, fields)
        if present_fields:
            refs.append(
                {
                    "candidate_id": candidate_id,
                    "component": component,
                    "fields": present_fields,
                }
            )
    return refs


def _present_fields(candidate: Dict[str, Any], fields: tuple[str, ...]) -> list[str]:
    return [field for field in fields if candidate.get(field) is not None]


def _rank_reason(
    *,
    candidate_id: str,
    objective_score: float,
    score_breakdown: Dict[str, float],
    warnings: list[str],
) -> str:
    strongest = sorted(
        score_breakdown.items(),
        key=lambda item: item[1],
        reverse=True,
    )[:2]
    strengths = ", ".join(f"{key}={value:.3f}" for key, value in strongest)
    warning_suffix = "" if not warnings else f"; warnings={len(warnings)}"
    return (
        f"{candidate_id} ranks by objective_score={objective_score:.3f} "
        f"with strongest components {strengths}{warning_suffix}"
    )


def _objective_gap(scored_candidates: list[Dict[str, Any]]) -> float | None:
    if not scored_candidates:
        return None
    if len(scored_candidates) == 1:
        return 0.0
    top = _as_float(scored_candidates[0].get("objective_score")) or 0.0
    runner_up = _as_float(scored_candidates[1].get("objective_score")) or 0.0
    return round(top - runner_up, 6)


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
