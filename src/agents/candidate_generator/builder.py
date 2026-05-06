from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from src.agents.candidate_generator.filters import (
    normalize_adapter_mode,
    normalize_level,
    object_mapping,
    safe_float,
)
from src.agents.candidate_generator.models import (
    CandidateGenerationInput,
    CandidateGeneratorHooks,
    CandidatePayload,
    Metadata,
    RuntimeShadowDecisionLike,
    ToolSpecLike,
)
from src.agents.candidate_generator.recovery_complexity import (
    RECOVERY_COMPLEXITY_METADATA_KEY,
    derive_recovery_complexity,
)
from src.models.contracts import (
    ACTION_SCORE_METADATA_KEY,
    FINAL_SCORE_METADATA_KEY,
    PendingActionCandidate,
    Plan,
    PlanPatch,
    RERANK_REASON_METADATA_KEY,
    RUNTIME_ADJUSTMENT_METADATA_KEY,
    RUNTIME_STATE_SUMMARY_METADATA_KEY,
    SHADOW_SCORE_METADATA_KEY,
    STATIC_SCORE_METADATA_KEY,
)

_POSTERIOR_OBJECTIVE_SCHEMA_VERSION = "posterior_objective.v1"
_POSTERIOR_SCORE_SCHEMA_VERSION = "posterior_score.v1"
_POSTERIOR_OBJECTIVE_THRESHOLD = 0.30
_POSTERIOR_OBJECTIVE_SOURCE_REFS = [
    "sid:algo.posterior_objective_scoring",
    "impl:posterior_score.v1",
]
_POSTERIOR_COMPONENT_KEYS = (
    "generic_objective",
    "stability",
    "function",
    "novelty",
    "structure_quality",
)


class CandidateBuilder:
    """构造 PendingActionCandidate 及其审计 metadata。"""

    def __init__(self, hooks: CandidateGeneratorHooks) -> None:
        self._hooks: CandidateGeneratorHooks = hooks

    def build(
        self,
        *,
        payload: CandidatePayload,
        request: CandidateGenerationInput,
        registry_map: Mapping[str, ToolSpecLike],
        score_weights: dict[str, float],
        runtime_state_summary: Metadata | None,
    ) -> PendingActionCandidate:
        primary_tool = registry_map.get(payload.primary_tool_id)
        capability_id = payload.capability_bucket or self._hooks.primary_capability(
            primary_tool
        )
        tool_id = payload.primary_tool_id
        io_type = (
            primary_tool.io_type
            if primary_tool is not None and primary_tool.io_type
            else "unknown"
        )
        adapter_mode = normalize_adapter_mode(
            primary_tool.adapter_mode if primary_tool is not None else "unknown"
        )
        score_breakdown = self._hooks.score_payload(
            payload.payload,
            request.registry,
            score_weights=score_weights,
            runtime_state_summary=runtime_state_summary,
        )
        score_breakdown = self._apply_generation_score_adjustments(
            score_breakdown,
            capability_id=capability_id,
            request=request,
        )
        metadata = self._build_metadata(
            payload=payload,
            request=request,
            capability_id=capability_id,
            tool_id=tool_id,
            io_type=io_type,
            adapter_mode=adapter_mode,
            score_breakdown=score_breakdown,
            score_weights=score_weights,
            runtime_state_summary=runtime_state_summary,
        )
        shadow = self._build_shadow_metadata(
            payload=payload,
            request=request,
            metadata=metadata,
            score_breakdown=score_breakdown,
            runtime_state_summary=runtime_state_summary,
        )
        explanation = (
            f"{request.candidate_kind} candidate with primary tool "
            f"{tool_id} in capability bucket {capability_id}."
        )
        if runtime_state_summary is not None:
            explanation = f"{explanation} {shadow.explanation_fragment}"
        return PendingActionCandidate(
            candidate_id=self._hooks.stable_candidate_id(
                request.candidate_kind,
                payload.payload,
                payload.primary_tool_id,
                payload.capability_bucket,
            ),
            structured_payload=payload.payload,
            score_breakdown=score_breakdown,
            risk_level=normalize_level(
                self._hooks.derive_risk_level(payload.payload, request.registry)
            ),
            cost_estimate=normalize_level(
                self._hooks.derive_cost_estimate(payload.payload, request.registry)
            ),
            explanation=explanation,
            summary=self._hooks.build_candidate_summary(payload.payload),
            tool_id=tool_id,
            capability_id=capability_id,
            io_type=io_type,
            adapter_mode=adapter_mode,
            metadata=metadata,
        )

    def _build_metadata(
        self,
        *,
        payload: CandidatePayload,
        request: CandidateGenerationInput,
        capability_id: str,
        tool_id: str,
        io_type: str,
        adapter_mode: str,
        score_breakdown: dict[str, float],
        score_weights: dict[str, float],
        runtime_state_summary: Metadata | None,
    ) -> Metadata:
        payload_metadata = object_mapping(cast(object, payload.payload.metadata))
        posterior_metadata = objective_metadata_from_payload_metadata(payload_metadata)
        metadata: Metadata = {
            "candidate_kind": request.candidate_kind,
            "capability_bucket": capability_id,
            "tool_id": tool_id,
            "capability_id": capability_id,
            "io_type": io_type,
            "adapter_mode": adapter_mode,
            "generation_note": payload.note,
            "candidate_generator": {
                "module": "src.agents.candidate_generator",
                "policy_mode": request.policy_mode,
                "capability_hints": list(request.capability_hints),
                "budget": object_mapping(request.budget),
                "readiness_context_present": request.readiness is not None,
                "completed_step_count": len(request.completed_step_results),
                "confirmed_task_spec_present": request.confirmed_task_spec is not None,
            },
            "s5_contract": self._hooks.build_s5_scoring_contract(score_weights),
            STATIC_SCORE_METADATA_KEY: self._hooks.build_static_score_summary(
                score_breakdown
            ),
            ACTION_SCORE_METADATA_KEY: self._hooks.build_action_score_summary(
                score_breakdown
            ),
            RECOVERY_COMPLEXITY_METADATA_KEY: derive_recovery_complexity(
                fallback_depth=score_breakdown.get("fallback_depth"),
                runtime_state=runtime_state_summary,
                candidate_summary=_recovery_candidate_summary(posterior_metadata),
            ).to_metadata(),
        }
        metadata.update(
            self._hooks.candidate_readiness_metadata(
                tool_id=tool_id,
                capability_id=capability_id,
            )
        )
        metadata.update(posterior_metadata)
        planner_route = payload_metadata.get("planner_route")
        if isinstance(planner_route, dict):
            metadata["planner_route"] = object_mapping(cast(object, planner_route))
        if payload.recovery_layer:
            metadata["recovery_layer"] = payload.recovery_layer
        if payload.recovery_reason:
            metadata["recovery_reason"] = payload.recovery_reason
        if isinstance(payload.payload, PlanPatch):
            metadata.update(
                self._hooks.extract_patch_candidate_metadata(payload.payload)
            )
        if isinstance(payload.payload, Plan):
            plan_metadata = self._hooks.extract_plan_candidate_metadata(payload.payload)
            if plan_metadata:
                metadata.update(plan_metadata)
                metadata["sequence_confidence"] = score_breakdown.get("confidence")
        return metadata

    def _build_shadow_metadata(
        self,
        *,
        payload: CandidatePayload,
        request: CandidateGenerationInput,
        metadata: Metadata,
        score_breakdown: dict[str, float],
        runtime_state_summary: Metadata | None,
    ) -> RuntimeShadowDecisionLike:
        if runtime_state_summary is None:
            shadow = self._hooks.build_shadow_passthrough_decision(score_breakdown)
        else:
            metadata[RUNTIME_STATE_SUMMARY_METADATA_KEY] = object_mapping(
                runtime_state_summary
            )
            shadow = self._hooks.build_runtime_shadow_decision(
                candidate_kind=request.candidate_kind,
                payload=payload.payload,
                score_breakdown=score_breakdown,
                runtime_state_summary=runtime_state_summary,
            )
            metadata["shadow_action"] = shadow.shadow_action
            metadata["shadow_action_reason"] = shadow.shadow_reason
        metadata[RUNTIME_ADJUSTMENT_METADATA_KEY] = shadow.runtime_adjustment
        metadata[FINAL_SCORE_METADATA_KEY] = shadow.final_score
        metadata[RERANK_REASON_METADATA_KEY] = shadow.rerank_reason
        metadata[SHADOW_SCORE_METADATA_KEY] = shadow.shadow_score
        return shadow

    def _apply_generation_score_adjustments(
        self,
        score_breakdown: dict[str, float],
        *,
        capability_id: str,
        request: CandidateGenerationInput,
    ) -> dict[str, float]:
        adjusted = dict(score_breakdown)
        hints = {str(item) for item in request.capability_hints if str(item)}
        if capability_id in hints:
            adjusted["objective"] = min(1.0, adjusted.get("objective", 0.0) + 0.05)
            adjusted["capability_hint_match"] = 1.0
        elif hints:
            adjusted["capability_hint_match"] = 0.0
        budget_cap = safe_float((request.budget or {}).get("cost_cap"))
        if budget_cap is not None and adjusted.get("cost", 1.0) < budget_cap:
            adjusted["budget_fit"] = 0.0
        elif budget_cap is not None:
            adjusted["budget_fit"] = 1.0
        policy_mode = str(request.policy_mode or "balanced").strip().lower()
        policy_adjustment = 0.0
        if policy_mode in {"conservative", "safe", "low_risk"}:
            policy_adjustment = 0.02 * adjusted.get("risk", 0.0)
        elif policy_mode in {"low_cost", "budget", "cheap", "fast_smoke"}:
            policy_adjustment = 0.02 * adjusted.get("cost", 0.0)
        elif policy_mode in {"exploratory", "aggressive", "high_accuracy"}:
            policy_adjustment = 0.02 * (
                0.6 * adjusted.get("objective", 0.0)
                + 0.4 * adjusted.get("tool_readiness", 0.0)
            )
        adjusted["policy_mode_fit"] = round(policy_adjustment, 6)
        adjusted["overall"] = round(
            min(
                1.0,
                max(
                    0.0,
                    adjusted.get("overall", 0.0)
                    + 0.03 * adjusted.get("capability_hint_match", 0.0)
                    + 0.02 * adjusted.get("budget_fit", 0.0)
                    + policy_adjustment,
                ),
            ),
            6,
        )
        return {key: round(value, 6) for key, value in adjusted.items()}


def _bounded_optional_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if not isinstance(value, int | float | str):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return min(max(parsed, 0.0), 1.0)


def _normalize_posterior_objective(raw: object) -> Metadata | None:
    if not isinstance(raw, Mapping):
        return None
    raw_mapping = cast(Mapping[str, object], raw)
    aggregate_score = _bounded_optional_float(raw_mapping.get("aggregate_score"))
    evidence_sufficiency = _bounded_optional_float(
        raw_mapping.get("evidence_sufficiency")
    )
    if aggregate_score is None or evidence_sufficiency is None:
        return None
    schema_version = raw_mapping.get("schema_version")
    if schema_version == _POSTERIOR_OBJECTIVE_SCHEMA_VERSION:
        normalized = object_mapping(cast(object, raw_mapping))
        normalized["aggregate_score"] = aggregate_score
        normalized["evidence_sufficiency"] = evidence_sufficiency
        return normalized
    if schema_version not in {_POSTERIOR_SCORE_SCHEMA_VERSION, None}:
        return None
    components: Metadata = {}
    for key in _POSTERIOR_COMPONENT_KEYS:
        component = raw_mapping.get(key)
        if isinstance(component, Mapping):
            components[key] = object_mapping(cast(object, component))
    raw_component_weights = raw_mapping.get("component_weights")
    raw_warnings = raw_mapping.get("warnings")
    raw_evidence_refs = raw_mapping.get("evidence_refs")
    raw_evidence_status = raw_mapping.get("evidence_status")
    objective_type = raw_mapping.get("objective_type")
    return {
        "schema_version": _POSTERIOR_OBJECTIVE_SCHEMA_VERSION,
        "aggregate_score": aggregate_score,
        "components": components,
        "component_weights": object_mapping(cast(object, raw_component_weights))
        if isinstance(raw_component_weights, Mapping)
        else {},
        "evidence_sufficiency": evidence_sufficiency,
        "evidence_status": raw_evidence_status
        if isinstance(raw_evidence_status, str)
        else "degraded",
        "objective_type": objective_type if isinstance(objective_type, str) else None,
        "objective_source": "posterior_objective",
        "binding_proxy_component": "generic_objective"
        if objective_type == "binding"
        else None,
        "warnings": list(cast(list[object], raw_warnings))
        if isinstance(raw_warnings, list)
        else [],
        "evidence_refs": list(cast(list[object], raw_evidence_refs))
        if isinstance(raw_evidence_refs, list)
        else [],
        "source_refs": list(_POSTERIOR_OBJECTIVE_SOURCE_REFS),
    }


def objective_metadata_from_payload_metadata(payload_metadata: Metadata) -> Metadata:
    raw = payload_metadata.get("posterior_objective") or payload_metadata.get("posterior_score")
    posterior = _normalize_posterior_objective(raw)
    if posterior is None:
        return {
            "objective_score_source": "prior_goal_fit",
            "objective_evidence_sufficiency": 0.5,
            "objective_evidence_status": "prior",
        }
    evidence_sufficiency = _bounded_optional_float(
        posterior.get("evidence_sufficiency")
    ) or 0.0
    raw_evidence_status = posterior.get("evidence_status")
    objective_source = (
        "posterior_objective"
        if evidence_sufficiency >= _POSTERIOR_OBJECTIVE_THRESHOLD
        else "degraded_proxy"
    )
    return {
        "posterior_objective": posterior,
        "objective_score_source": objective_source,
        "objective_evidence_sufficiency": evidence_sufficiency,
        "objective_evidence_status": raw_evidence_status
        if isinstance(raw_evidence_status, str)
        else "degraded",
    }


def _recovery_candidate_summary(objective_metadata: Metadata) -> Metadata:
    posterior = objective_metadata.get("posterior_objective")
    if isinstance(posterior, Mapping):
        return {"posterior_objective": object_mapping(cast(object, posterior))}
    return {}
