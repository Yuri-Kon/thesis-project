from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import cast

from src.agents.candidate_generator.builder import CandidateBuilder
from src.agents.candidate_generator.filters import (
    candidate_difference_explanation,
    cost_level_exceeds,
    object_mapping,
    parse_safety_level,
    payload_io_closed,
    payload_tool_ids,
    string_set,
)
from src.agents.candidate_generator.models import (
    CandidateGenerationInput,
    CandidateGeneratorHooks,
    CandidatePayload,
    Metadata,
    SortKey,
    ToolSpecLike,
    TopKResult,
)
from src.models.contracts import (
    CAPABILITY_READINESS_METADATA_KEY,
    DEFAULT_RECOMMENDATION_REASON_METADATA_KEY,
    FINAL_SCORE_METADATA_KEY,
    PendingActionCandidate,
    Plan,
    PlanPatch,
    STATIC_SCORE_METADATA_KEY,
    TOOL_READINESS_METADATA_KEY,
)

ScoredRow = tuple[PendingActionCandidate, SortKey, SortKey, str]
RankedRow = tuple[PendingActionCandidate, SortKey, str]

CANDIDATE_FEASIBILITY_METADATA_KEY = "candidate_feasibility"
_SOFT_FEASIBILITY_REASONS = {"io_not_closed", "tool_unavailable"}
_FEASIBILITY_SOURCE_REFS = [
    "sid:algo.adaptive.feasibility_filter",
    "impl:candidate_generator.feasibility.v1",
]
_FEASIBILITY_DESIGN_REF_STATUS = {
    "sid:algo.adaptive.feasibility_filter": "proposed",
}
_HARD_FEASIBILITY_CONSTRAINT_CODES = {
    "tool_not_allowed": "tool.not_allowed",
    "tool_blocked": "tool.blocked",
    "safety_level_exceeded": "safety.exceeded",
    "cost_level_exceeded": "cost.exceeded",
}


def _build_candidate_feasibility_metadata(reason: str | None) -> Metadata:
    """构造候选硬/软可行性审计元数据。"""
    constraint_codes = _constraint_codes_for_filter_reason(reason)
    filter_class = _filter_class_for_reason(reason)
    hard_feasible = reason is None
    degraded_feasible = filter_class == "soft"
    requires_hitl = degraded_feasible
    auto_executable = hard_feasible and not requires_hitl
    allowed_for_top_k = filter_class in {"eligible", "soft"}
    allowed_for_default_recommendation = auto_executable
    return {
        "schema_version": "candidate_feasibility.v1",
        "hard_feasible": hard_feasible,
        "soft_feasible": filter_class in {"eligible", "soft"},
        "degraded_feasible": degraded_feasible,
        "requires_hitl": requires_hitl,
        "auto_executable": auto_executable,
        "filter_class": filter_class,
        "filter_reason": reason,
        "constraint_codes": constraint_codes,
        "blocked_by": _blocked_by_for_filter_reason(reason),
        "allowed_for_top_k": allowed_for_top_k,
        "allowed_for_default_recommendation": allowed_for_default_recommendation,
        "explanation": _feasibility_explanation(reason, filter_class),
        "source_refs": list(_FEASIBILITY_SOURCE_REFS),
        "design_ref_status": dict(_FEASIBILITY_DESIGN_REF_STATUS),
    }


def _filter_class_for_reason(reason: str | None) -> str:
    if reason is None:
        return "eligible"
    if reason in _SOFT_FEASIBILITY_REASONS:
        return "soft"
    return "hard"


def _constraint_codes_for_filter_reason(reason: str | None) -> list[str]:
    if reason is None:
        return []
    if reason == "io_not_closed":
        return ["schema.io_open"]
    if reason == "tool_unavailable":
        return ["tool.unavailable"]
    if reason.startswith("missing_tools:"):
        return ["tool.missing"]
    return [_HARD_FEASIBILITY_CONSTRAINT_CODES.get(reason, "unknown")]


def _blocked_by_for_filter_reason(reason: str | None) -> list[str]:
    if reason is None:
        return []
    if reason.startswith("missing_tools:"):
        missing = reason.split(":", 1)[1]
        return [tool_id for tool_id in missing.split(",") if tool_id]
    return [reason]


def _feasibility_explanation(reason: str | None, filter_class: str) -> str:
    if filter_class == "eligible":
        return "Candidate satisfies hard feasibility constraints and can be auto defaulted."
    if filter_class == "soft":
        return (
            "Candidate is degraded feasible for Top-K display only; "
            f"requires HITL because {reason}."
        )
    return f"Candidate is hard infeasible and excluded from Top-K because {reason}."


class CandidateGenerator:
    """统一生成 Plan/Patch/Replan Top-K 候选。

    CandidateGenerator 只负责候选过滤、评分、排序和 HITL 展示元数据；
    原始 payload 的领域构造仍由 PlannerAgent 完成，避免改变 Agent 边界。
    """

    def __init__(self, hooks: CandidateGeneratorHooks) -> None:
        self._hooks: CandidateGeneratorHooks = hooks
        self._builder: CandidateBuilder = CandidateBuilder(hooks)

    def generate(self, request: CandidateGenerationInput) -> TopKResult:
        """生成稳定 Top-K、default_suggestion 和候选差异解释。"""
        if not request.payloads:
            raise ValueError(f"No payload candidates generated for {request.candidate_kind}")

        registry_map: dict[str, ToolSpecLike] = {
            spec.id: spec for spec in request.registry
        }
        unique_payloads = self._dedupe_payloads(request.payloads)
        filtered_rows: list[ScoredRow] = []
        soft_filtered_rows: list[ScoredRow] = []
        filter_reasons: list[str] = []

        score_weights = self._hooks.resolve_score_weights(request.task_constraints or {})
        runtime_state_summary = self._hooks.normalize_runtime_state_summary_input(
            request.runtime_state
        )

        for payload in unique_payloads:
            candidate = self._builder.build(
                payload=payload,
                request=request,
                registry_map=registry_map,
                score_weights=score_weights,
                runtime_state_summary=runtime_state_summary,
            )
            static_sort_key = self._sort_key(
                request.candidate_kind,
                candidate,
                registry_map.get(payload.primary_tool_id),
                payload.payload,
                score_metadata_key=STATIC_SCORE_METADATA_KEY,
            )
            effective_sort_key = self._sort_key(
                request.candidate_kind,
                candidate,
                registry_map.get(payload.primary_tool_id),
                payload.payload,
                score_metadata_key=FINAL_SCORE_METADATA_KEY,
            )
            reason = self._filter_reason(candidate, payload.payload, request, registry_map)
            candidate = self._with_candidate_feasibility(candidate, reason)
            row = (
                candidate,
                static_sort_key,
                effective_sort_key,
                candidate.capability_id or "unknown",
            )
            if reason is not None:
                filter_reasons.append(reason)
                if reason in _SOFT_FEASIBILITY_REASONS:
                    soft_filtered_rows.append(row)
                continue
            filtered_rows.append(row)

        available_rows = self._available_rows(
            filtered_rows=filtered_rows,
            soft_filtered_rows=soft_filtered_rows,
            top_k=request.top_k,
        )
        if not available_rows:
            raise ValueError(
                f"No feasible payload candidates generated for {request.candidate_kind}"
            )

        static_rows = sorted(
            [(row[0], row[1], row[3]) for row in available_rows],
            key=lambda row: row[1],
        )
        static_selected_rows = self._select_diverse_top_k(
            ranked_rows=static_rows,
            top_k=request.top_k,
        )
        static_selected_rows = sorted(static_selected_rows, key=lambda row: row[1])
        selected_rows = static_selected_rows
        if runtime_state_summary is not None:
            effective_rows = sorted(
                [(row[0], row[2], row[3]) for row in available_rows],
                key=lambda row: row[1],
            )
            selected_rows = self._select_diverse_top_k(
                ranked_rows=effective_rows,
                top_k=request.top_k,
            )
            selected_rows = sorted(selected_rows, key=lambda row: row[1])

        candidates = [row[0] for row in selected_rows]
        static_candidates = [row[0] for row in static_selected_rows]
        default_candidate = self._first_default_recommendation_candidate(candidates)
        static_default_candidate = self._first_default_recommendation_candidate(
            static_candidates
        )
        default_recommendation = (
            default_candidate.candidate_id if default_candidate is not None else None
        )
        if default_candidate is not None:
            default_metadata = default_candidate.metadata
            default_metadata[DEFAULT_RECOMMENDATION_REASON_METADATA_KEY] = (
                self._hooks.build_default_recommendation_reason(
                    candidate_kind=request.candidate_kind,
                    candidate_id=default_candidate.candidate_id,
                    default_candidate=default_candidate,
                    static_candidate=static_default_candidate,
                    rerank_applied=runtime_state_summary is not None,
                )
            )

        return TopKResult(
            candidates=candidates,
            default_recommendation=default_recommendation,
            explanation=self._build_explanation(
                request=request,
                candidates=candidates,
                default_candidate=default_candidate,
                static_default_candidate=static_default_candidate,
                filter_reasons=filter_reasons,
                used_filtered_rows=bool(filtered_rows),
                runtime_state_summary=runtime_state_summary,
            ),
        )

    def _with_candidate_feasibility(
        self,
        candidate: PendingActionCandidate,
        reason: str | None,
    ) -> PendingActionCandidate:
        metadata = dict(candidate.metadata or {})
        metadata[CANDIDATE_FEASIBILITY_METADATA_KEY] = (
            _build_candidate_feasibility_metadata(reason)
        )
        return candidate.model_copy(update={"metadata": metadata})

    def _first_default_recommendation_candidate(
        self,
        candidates: Sequence[PendingActionCandidate],
    ) -> PendingActionCandidate | None:
        for candidate in candidates:
            metadata = object_mapping(cast(object, candidate.metadata))
            feasibility = object_mapping(
                metadata.get(CANDIDATE_FEASIBILITY_METADATA_KEY)
            )
            if feasibility.get("allowed_for_default_recommendation") is True:
                return candidate
        return None

    def _degraded_candidate_reasons(
        self,
        candidates: Sequence[PendingActionCandidate],
    ) -> list[str]:
        reasons: list[str] = []
        for candidate in candidates:
            metadata = object_mapping(cast(object, candidate.metadata))
            feasibility = object_mapping(
                metadata.get(CANDIDATE_FEASIBILITY_METADATA_KEY)
            )
            if feasibility.get("degraded_feasible") is not True:
                continue
            raw_reason = feasibility.get("filter_reason")
            reason = raw_reason if isinstance(raw_reason, str) else "unknown"
            if reason not in reasons:
                reasons.append(reason)
        return reasons

    def _filter_reason(
        self,
        candidate: PendingActionCandidate,
        payload: Plan | PlanPatch,
        request: CandidateGenerationInput,
        registry_map: Mapping[str, ToolSpecLike],
    ) -> str | None:
        constraints = request.task_constraints or {}
        tool_ids = payload_tool_ids(payload)
        missing_tools = [tool_id for tool_id in tool_ids if tool_id not in registry_map]
        if missing_tools:
            return f"missing_tools:{','.join(sorted(missing_tools))}"
        allowed_tools = string_set(
            constraints.get("allowed_tools") or constraints.get("tools_allowed")
        )
        if allowed_tools and any(tool_id not in allowed_tools for tool_id in tool_ids):
            return "tool_not_allowed"
        blocked_tools = string_set(
            constraints.get("blocked_tools") or constraints.get("tools_excluded")
        )
        if blocked_tools and any(tool_id in blocked_tools for tool_id in tool_ids):
            return "tool_blocked"
        max_safety_level = parse_safety_level(constraints.get("safety_level"))
        if max_safety_level is not None:
            for tool_id in tool_ids:
                spec = registry_map.get(tool_id)
                if spec is not None and spec.safety_level > max_safety_level:
                    return "safety_level_exceeded"
        max_cost_level = constraints.get("max_cost_level") or constraints.get(
            "max_cost_estimate"
        )
        normalized_max_cost_level = (
            max_cost_level.strip() if isinstance(max_cost_level, str) else None
        )
        if cost_level_exceeds(candidate.cost_estimate, normalized_max_cost_level):
            return "cost_level_exceeded"
        if not payload_io_closed(
            payload,
            registry_map,
            request.completed_step_results,
            constraints,
        ):
            return "io_not_closed"
        if self._candidate_unavailable(candidate):
            return "tool_unavailable"
        return None

    def _candidate_unavailable(self, candidate: PendingActionCandidate) -> bool:
        metadata = object_mapping(cast(object, candidate.metadata))
        tool_readiness = metadata.get(TOOL_READINESS_METADATA_KEY)
        capability_readiness = metadata.get(CAPABILITY_READINESS_METADATA_KEY)
        for item in (tool_readiness, capability_readiness):
            readiness = object_mapping(item)
            if readiness.get("status") == "unavailable":
                return True
        return False

    def _sort_key(
        self,
        candidate_kind: str,
        candidate: PendingActionCandidate,
        primary_tool: ToolSpecLike | None,
        payload: Plan | PlanPatch,
        score_metadata_key: str,
    ) -> SortKey:
        priority_rank = self._hooks.priority_rank(
            primary_tool.priority if primary_tool else None
        )
        patch_layer_rank = self._hooks.patch_layer_rank(payload)
        score_value = self._hooks.extract_score_value(candidate, score_metadata_key)
        capability_id = candidate.capability_id or "unknown"
        tool_id = candidate.tool_id or "unknown"
        if candidate_kind == "patch":
            return (
                patch_layer_rank,
                -score_value,
                priority_rank,
                capability_id,
                tool_id,
                candidate.candidate_id,
            )
        return (
            -score_value,
            priority_rank,
            capability_id,
            tool_id,
            candidate.candidate_id,
        )

    def _dedupe_payloads(
        self,
        payloads: Sequence[CandidatePayload],
    ) -> list[CandidatePayload]:
        unique_payloads: list[CandidatePayload] = []
        seen_fingerprints: set[str] = set()
        for payload in payloads:
            fingerprint = self._hooks.canonical_payload_fingerprint(
                payload.payload,
                payload.primary_tool_id,
                payload.capability_bucket,
            )
            if fingerprint in seen_fingerprints:
                continue
            seen_fingerprints.add(fingerprint)
            unique_payloads.append(payload)
        return unique_payloads

    def _available_rows(
        self,
        *,
        filtered_rows: Sequence[ScoredRow],
        soft_filtered_rows: Sequence[ScoredRow],
        top_k: int,
    ) -> list[ScoredRow]:
        available_rows = list(filtered_rows)
        if len(available_rows) < top_k:
            seen_ids = {row[0].candidate_id for row in available_rows}
            for row in soft_filtered_rows:
                if row[0].candidate_id in seen_ids:
                    continue
                available_rows.append(row)
                seen_ids.add(row[0].candidate_id)
                if len(available_rows) >= top_k:
                    break
        if not available_rows and soft_filtered_rows:
            return list(soft_filtered_rows)
        return available_rows

    def _select_diverse_top_k(
        self,
        *,
        ranked_rows: Sequence[RankedRow],
        top_k: int,
    ) -> list[RankedRow]:
        bucket_rows: dict[str, list[RankedRow]] = {}
        bucket_order: list[str] = []
        for row in ranked_rows:
            bucket = row[2] or "unknown"
            if bucket not in bucket_rows:
                bucket_rows[bucket] = []
                bucket_order.append(bucket)
            bucket_rows[bucket].append(row)

        selected: list[RankedRow] = []
        while len(selected) < top_k:
            progressed = False
            for bucket in bucket_order:
                rows = bucket_rows[bucket]
                if not rows:
                    continue
                selected.append(rows.pop(0))
                progressed = True
                if len(selected) >= top_k:
                    break
            if not progressed:
                break
        return selected

    def _build_explanation(
        self,
        *,
        request: CandidateGenerationInput,
        candidates: Sequence[PendingActionCandidate],
        default_candidate: PendingActionCandidate | None,
        static_default_candidate: PendingActionCandidate | None,
        filter_reasons: Sequence[str],
        used_filtered_rows: bool,
        runtime_state_summary: Metadata | None,
    ) -> str:
        ranking_basis = (
            "final_score" if runtime_state_summary is not None else "static_score"
        )
        explanation = (
            f"{request.candidate_kind} Top-K generated by CandidateGenerator "
            f"(requested={request.top_k}, returned={len(candidates)}). "
            f"Ranking uses {ranking_basis} desc + stable tie-break; "
            "selection uses capability-bucket round-robin."
        )
        if default_candidate is not None:
            explanation = (
                f"{explanation} default_suggestion={default_candidate.candidate_id}."
            )
            if runtime_state_summary is not None:
                explanation = self._append_rerank_explanation(
                    explanation=explanation,
                    default_candidate=default_candidate,
                    static_default_candidate=static_default_candidate,
                )
        elif candidates:
            explanation = (
                f"{explanation} No hard-feasible default recommendation exists; "
                "returned degraded candidates require HITL."
            )
        degraded_reasons = self._degraded_candidate_reasons(candidates)
        if degraded_reasons:
            explanation = (
                f"{explanation} Returned degraded candidates require HITL because: "
                f"{', '.join(degraded_reasons)}."
            )
        difference = candidate_difference_explanation(candidates)
        if difference:
            explanation = f"{explanation} Candidate differences: {difference}."
        if filter_reasons and used_filtered_rows:
            explanation = (
                f"{explanation} Filtered candidates before ranking by "
                f"{', '.join(sorted(set(filter_reasons)))}."
            )
        elif filter_reasons:
            explanation = (
                f"{explanation} Filtering found only degraded soft fallback candidates; "
                "returned candidates require HITL and are not eligible for automatic default."
            )
        if len(candidates) < request.top_k:
            explanation = (
                f"{explanation} Degraded to available candidates because registry "
                "constraints did not produce enough unique options."
            )
        return explanation

    def _append_rerank_explanation(
        self,
        *,
        explanation: str,
        default_candidate: PendingActionCandidate,
        static_default_candidate: PendingActionCandidate | None,
    ) -> str:
        if (
            static_default_candidate is not None
            and static_default_candidate.candidate_id != default_candidate.candidate_id
        ):
            explanation = (
                f"{explanation} Runtime rerank updated default recommendation "
                f"from {static_default_candidate.candidate_id} "
                f"to {default_candidate.candidate_id}."
            )
        else:
            explanation = (
                f"{explanation} Runtime rerank kept default recommendation "
                f"at {default_candidate.candidate_id}."
            )
        return f"{explanation} {self._hooks.summarize_rerank_reason(default_candidate)}"
