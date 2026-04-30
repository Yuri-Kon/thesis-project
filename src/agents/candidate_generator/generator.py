from __future__ import annotations

from typing import Any, Sequence

from src.agents.candidate_generator.builder import CandidateBuilder
from src.agents.candidate_generator.filters import (
    candidate_difference_explanation,
    parse_safety_level,
    payload_io_closed,
    payload_tool_ids,
    string_set,
)
from src.agents.candidate_generator.models import (
    CandidateGenerationInput,
    CandidateGeneratorHooks,
    CandidatePayload,
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


class CandidateGenerator:
    """统一生成 Plan/Patch/Replan Top-K 候选。

    CandidateGenerator 只负责候选过滤、评分、排序和 HITL 展示元数据；
    原始 payload 的领域构造仍由 PlannerAgent 完成，避免改变 Agent 边界。
    """

    def __init__(self, hooks: CandidateGeneratorHooks) -> None:
        self._hooks = hooks
        self._builder = CandidateBuilder(hooks)

    def generate(self, request: CandidateGenerationInput) -> TopKResult:
        """生成稳定 Top-K、default_suggestion 和候选差异解释。"""
        if not request.payloads:
            raise ValueError(f"No payload candidates generated for {request.candidate_kind}")

        registry_map = {spec.id: spec for spec in request.registry}
        unique_payloads = self._dedupe_payloads(request.payloads)
        scored_rows: list[tuple[PendingActionCandidate, tuple, tuple, str]] = []
        filtered_rows: list[tuple[PendingActionCandidate, tuple, tuple, str]] = []
        soft_filtered_rows: list[tuple[PendingActionCandidate, tuple, tuple, str]] = []
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
            row = (
                candidate,
                static_sort_key,
                effective_sort_key,
                candidate.capability_id or "unknown",
            )
            scored_rows.append(row)
            reason = self._filter_reason(candidate, payload.payload, request, registry_map)
            if reason is not None:
                filter_reasons.append(reason)
                if reason in {"io_not_closed", "tool_unavailable"}:
                    soft_filtered_rows.append(row)
                continue
            filtered_rows.append(row)

        available_rows = self._available_rows(
            filtered_rows=filtered_rows,
            soft_filtered_rows=soft_filtered_rows,
            scored_rows=scored_rows,
            top_k=request.top_k,
        )
        if not available_rows:
            raise ValueError(f"No feasible payload candidates generated for {request.candidate_kind}")

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
        default_candidate = candidates[0] if candidates else None
        static_default_candidate = static_candidates[0] if static_candidates else None
        default_recommendation = (
            default_candidate.candidate_id if default_candidate is not None else None
        )
        if default_candidate is not None:
            default_candidate.metadata[DEFAULT_RECOMMENDATION_REASON_METADATA_KEY] = (
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

    def _filter_reason(
        self,
        candidate: PendingActionCandidate,
        payload: Plan | PlanPatch,
        request: CandidateGenerationInput,
        registry_map: dict[str, Any],
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
                if spec is not None and int(getattr(spec, "safety_level", 1)) > max_safety_level:
                    return "safety_level_exceeded"
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
        metadata = candidate.metadata if isinstance(candidate.metadata, dict) else {}
        tool_readiness = metadata.get(TOOL_READINESS_METADATA_KEY)
        capability_readiness = metadata.get(CAPABILITY_READINESS_METADATA_KEY)
        for item in (tool_readiness, capability_readiness):
            if isinstance(item, dict) and item.get("status") == "unavailable":
                return True
        return False

    def _sort_key(
        self,
        candidate_kind: str,
        candidate: PendingActionCandidate,
        primary_tool: Any | None,
        payload: Plan | PlanPatch,
        score_metadata_key: str,
    ) -> tuple:
        priority_rank = self._hooks.priority_rank(primary_tool.priority if primary_tool else None)
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
        filtered_rows: Sequence[tuple[PendingActionCandidate, tuple, tuple, str]],
        soft_filtered_rows: Sequence[tuple[PendingActionCandidate, tuple, tuple, str]],
        scored_rows: Sequence[tuple[PendingActionCandidate, tuple, tuple, str]],
        top_k: int,
    ) -> list[tuple[PendingActionCandidate, tuple, tuple, str]]:
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
        if not available_rows:
            return list(scored_rows)
        return available_rows

    def _select_diverse_top_k(
        self,
        *,
        ranked_rows: Sequence[tuple[PendingActionCandidate, tuple, str]],
        top_k: int,
    ) -> list[tuple[PendingActionCandidate, tuple, str]]:
        bucket_rows: dict[str, list[tuple[PendingActionCandidate, tuple, str]]] = {}
        bucket_order: list[str] = []
        for row in ranked_rows:
            bucket = row[2] or "unknown"
            if bucket not in bucket_rows:
                bucket_rows[bucket] = []
                bucket_order.append(bucket)
            bucket_rows[bucket].append(row)

        selected: list[tuple[PendingActionCandidate, tuple, str]] = []
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
        runtime_state_summary: dict[str, Any] | None,
    ) -> str:
        ranking_basis = "final_score" if runtime_state_summary is not None else "static_score"
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
                f"{explanation} Filtering would remove all candidates, so the generator "
                "returned the scored fallback set for compatibility."
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
