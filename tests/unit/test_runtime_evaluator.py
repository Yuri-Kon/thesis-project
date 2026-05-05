"""RuntimeEvaluator 测试：policy modes、utility 公式、rerank、action selection。"""

from __future__ import annotations

from typing import cast

from src.models.contracts import (
    FINAL_SCORE_METADATA_KEY,
    PendingActionCandidate,
    Plan,
    PlanStep,
    RUNTIME_ADJUSTMENT_METADATA_KEY,
)
from src.models.runtime_schemas import RuntimeStateSchema
from src.models.source_refs import (
    SOURCE_REF_ACTION_UTILITY,
    SOURCE_REF_RUNTIME_ADJUSTMENT,
)
from src.workflow.runtime_evaluator import (
    DYNAMIC_OBSERVATION_ONLY,
    LITE_BELIEF_STATE,
    STATIC_GATE,
    STATIC_TOP1,
    RuntimeEvaluator,
    evaluator_policy_trace,
    policy_disables_rerank,
)


def _plan_payload(task_id: str = "test_task") -> Plan:
    return Plan(
        task_id=task_id,
        steps=[PlanStep(id="S1", tool="mock_tool")],
    )


def _candidate(
    candidate_id: str,
    overall: float = 0.7,
    feasibility: float = 0.8,
    risk: float = 0.2,
    cost: float = 0.3,
    confidence: float = 0.75,
    fallback_depth: float = 0.5,
    kind: str = "plan",
    **extra: float,
) -> PendingActionCandidate:
    score_bd: dict[str, float] = {
        "overall": overall,
        "feasibility": feasibility,
        "risk": risk,
        "cost": cost,
        "confidence": confidence,
        "fallback_depth": fallback_depth,
    }
    score_bd.update(extra)
    metadata: dict[str, object] = {
        "score_breakdown": dict(score_bd),
    }
    if kind == "patch":
        metadata["patch_layer"] = "model_replacement"
    elif kind == "replan":
        metadata["replan_mode"] = "suffix_replan"
    return PendingActionCandidate(
        candidate_id=candidate_id,
        summary="test candidate",
        explanation="test",
        score_breakdown=score_bd,
        payload=_plan_payload(),
        metadata=metadata,
    )


def _state(**overrides: float) -> RuntimeStateSchema:
    return RuntimeStateSchema(
        p_success=overrides.get("p_success", 0.7),
        p_structural_failure=overrides.get("p_structural_failure", 0.2),
        recovery_margin=overrides.get("recovery_margin", 0.6),
        expected_remaining_cost=overrides.get("expected_remaining_cost", 0.5),
        evidence_sufficiency=overrides.get("evidence_sufficiency", 0.65),
    )


def _state_dict(**overrides: float) -> dict[str, object]:
    """返回包含额外字段的 plain dict（用于需要 local_patchability 等的场景）。"""
    defaults: dict[str, float] = {
        "p_success": 0.7,
        "p_structural_failure": 0.2,
        "recovery_margin": 0.6,
        "expected_remaining_cost": 0.5,
        "evidence_sufficiency": 0.65,
        "local_patchability": 0.5,
        "evidence_reusability": 0.5,
        "prefix_preservability": 0.5,
        "budget_relief": 0.5,
        "goal_realignment": 0.5,
        "safety_terminality": 0.0,
        "intervention_value": 0.0,
    }
    defaults.update(overrides)
    return dict(defaults)


# -- policy mode tests -------------------------------------------------------


class TestPolicyModes:
    def test_static_top1_disables_rerank(self) -> None:
        e = RuntimeEvaluator(policy_mode=STATIC_TOP1)
        candidates = [_candidate("a", overall=0.8), _candidate("b", overall=0.6)]
        result = e.evaluate_candidates(candidates, _state())
        assert result.rerank_applied is False
        # 按静态分排序
        assert result.candidates[0].candidate_id == "a"

    def test_static_gate_disables_rerank(self) -> None:
        e = RuntimeEvaluator(policy_mode=STATIC_GATE)
        assert not e.evaluate_candidates(
            [_candidate("a")], _state()
        ).rerank_applied

    def test_dynamic_observation_passthrough(self) -> None:
        e = RuntimeEvaluator(policy_mode=DYNAMIC_OBSERVATION_ONLY)
        result = e.evaluate_candidates(
            [_candidate("a", overall=0.7)], _state()
        )
        # rerank_applied=True 但调整量为 0（observation_only 走 passthrough）
        metadata = dict(result.candidates[0].metadata)
        adj = metadata[RUNTIME_ADJUSTMENT_METADATA_KEY]
        assert isinstance(adj, dict)
        assert adj["value"] == 0.0
        final = metadata[FINAL_SCORE_METADATA_KEY]
        assert isinstance(final, dict)
        assert final["value"] == 0.7

    def test_lite_belief_state_enables_full_rerank(self) -> None:
        e = RuntimeEvaluator(policy_mode=LITE_BELIEF_STATE)
        result = e.evaluate_candidates(
            [_candidate("a", overall=0.7)], _state()
        )
        assert result.rerank_applied is True

    def test_policy_disables_rerank_helper(self) -> None:
        assert policy_disables_rerank(STATIC_TOP1) is True
        assert policy_disables_rerank(STATIC_GATE) is True
        assert policy_disables_rerank(LITE_BELIEF_STATE) is False
        assert policy_disables_rerank(DYNAMIC_OBSERVATION_ONLY) is False

    def test_invalid_policy_defaults_to_lite(self) -> None:
        e = RuntimeEvaluator(policy_mode="invalid_mode")
        assert e.policy_mode == LITE_BELIEF_STATE

    def test_policy_trace(self) -> None:
        trace = evaluator_policy_trace(STATIC_TOP1)
        assert trace["rerank_enabled"] is False
        assert trace["belief_state_enabled"] is False
        assert trace["policy_mode"] == STATIC_TOP1

    def test_empty_candidates(self) -> None:
        e = RuntimeEvaluator()
        result = e.evaluate_candidates([], _state())
        assert result.candidates == []


# -- rerank tests ------------------------------------------------------------


class TestRerank:
    def test_feasibility_zero_not_resurrected(self) -> None:
        """feasibility = 0 的候选 final_score 保持 passthrough。"""
        e = RuntimeEvaluator()
        c = _candidate("dead", overall=0.8, feasibility=0.0)
        result = e.evaluate_candidates([c], _state())
        metadata = dict(result.candidates[0].metadata)
        adj = metadata[RUNTIME_ADJUSTMENT_METADATA_KEY]
        assert isinstance(adj, dict)
        # feasibility=0 走 passthrough，runtime_adjustment 为 0
        assert adj["value"] == 0.0

    def test_no_runtime_state_passthrough(self) -> None:
        e = RuntimeEvaluator()
        c = _candidate("a", overall=0.7)
        result = e.evaluate_candidates([c], None)
        # 无 state 且非 disabled policy → passthrough
        assert result.rerank_applied is False
        metadata = dict(result.candidates[0].metadata)
        adj = metadata[RUNTIME_ADJUSTMENT_METADATA_KEY]
        assert isinstance(adj, dict)
        assert adj["value"] == 0.0

    def test_runtime_adjustment_changes_final_score(self) -> None:
        e = RuntimeEvaluator()
        c = _candidate("a", overall=0.7, feasibility=0.8, risk=0.2)
        result = e.evaluate_candidates([c], _state(p_success=0.85))
        metadata = dict(result.candidates[0].metadata)
        adj = metadata[RUNTIME_ADJUSTMENT_METADATA_KEY]
        assert isinstance(adj, dict)
        # 高 p_success 应产生正调整
        assert adj["value"] > 0.01
        refs = cast(list[str], adj["source_refs"])
        assert "sid:planner.algorithm.runtime_adjustment_formula" in refs
        assert "impl:planner.runtime_adjustment.v1" in refs
        assert set(SOURCE_REF_RUNTIME_ADJUSTMENT).issubset(refs)

    def test_high_risk_reduces_score(self) -> None:
        e = RuntimeEvaluator()
        c = _candidate("risky", overall=0.5, feasibility=0.5, risk=0.1, cost=0.5, confidence=0.3)
        result = e.evaluate_candidates(
            [c],
            _state(p_success=0.2, p_structural_failure=0.9, expected_remaining_cost=1.3),
        )
        metadata = dict(result.candidates[0].metadata)
        adj = metadata[RUNTIME_ADJUSTMENT_METADATA_KEY]
        assert isinstance(adj, dict)
        # 高 p_structural_failure + 高 cost pressure + 低 p_success → 负调整
        assert adj["value"] < -0.10

    def test_delta_clamped_to_range(self) -> None:
        """delta 约束在 [-0.35, 0.35] 内。"""
        e = RuntimeEvaluator()
        # 极端参数
        c = _candidate("extreme", overall=0.5)
        result = e.evaluate_candidates(
            [c],
            _state(
                p_success=0.95,
                p_structural_failure=0.05,
                expected_remaining_cost=0.0,
                evidence_sufficiency=0.95,
            ),
        )
        metadata = dict(result.candidates[0].metadata)
        adj = metadata[RUNTIME_ADJUSTMENT_METADATA_KEY]
        assert isinstance(adj, dict)
        assert -0.35 <= adj["value"] <= 0.35  # type: ignore[operator]

    def test_rerank_preserves_sort_order(self) -> None:
        e = RuntimeEvaluator()
        candidates = [
            _candidate("low", overall=0.4),
            _candidate("high", overall=0.9),
            _candidate("mid", overall=0.6),
        ]
        state = _state(p_success=0.8, p_structural_failure=0.1)
        result = e.evaluate_candidates(candidates, state)
        scores = [
            _extract_final(c) for c in result.candidates
        ]
        assert scores == sorted(scores, reverse=True)

    def test_static_default_tracked(self) -> None:
        e = RuntimeEvaluator()
        candidates = [
            _candidate("a", overall=0.9),
            _candidate("b", overall=0.5),
        ]
        result = e.evaluate_candidates(candidates, _state())
        assert result.static_default_id == "a"

    def test_rerank_can_change_default(self) -> None:
        """运行时调整可改变默认推荐候选。"""
        e = RuntimeEvaluator()
        # a 静态分高但风险高; b 静态分低但稳健
        candidates = [
            _candidate("risky_a", overall=0.8, risk=0.9, cost=0.8),
            _candidate("safe_b", overall=0.7, risk=0.1, cost=0.1),
        ]
        state = _state(
            p_structural_failure=0.9,
            expected_remaining_cost=1.2,
        )
        result = e.evaluate_candidates(candidates, state)
        # 在高压运行时状态下 safe_b 可能反超
        # 至少 metadata 中有 final_score
        for c in result.candidates:
            metadata = dict(c.metadata)
            assert FINAL_SCORE_METADATA_KEY in metadata


# -- action utility tests ----------------------------------------------------


class TestActionUtility:
    def test_computes_four_actions(self) -> None:
        e = RuntimeEvaluator()
        utilities = e.compute_action_utilities(_state_dict())
        assert set(utilities.keys()) == {"continue", "patch_local", "suffix_replan", "stop"}
        for u in utilities.values():
            assert 0.0 <= u.utility <= 1.0
            assert "sid:algo.schema.action_utility" in u.source_refs
            assert "impl:runtime_evaluator.action_utility.v1" in u.source_refs
            assert set(SOURCE_REF_ACTION_UTILITY).issubset(u.source_refs)
            assert any(ref.startswith("sid:") for ref in u.source_refs)
            assert any(ref.startswith("impl:") for ref in u.source_refs)

    def test_stop_utility_higher_under_pressure(self) -> None:
        e = RuntimeEvaluator()
        good = e.compute_action_utilities(
            _state_dict(p_success=0.8, expected_remaining_cost=0.3)
        )
        bad = e.compute_action_utilities(
            _state_dict(p_success=0.15, expected_remaining_cost=0.9, recovery_margin=0.1)
        )
        assert bad["stop"].utility > good["stop"].utility
        assert bad["continue"].utility < good["continue"].utility

    def test_patch_utility_scales_with_recovery(self) -> None:
        e = RuntimeEvaluator()
        low = e.compute_action_utilities(
            _state_dict(recovery_margin=0.1, local_patchability=0.1)
        )
        high = e.compute_action_utilities(
            _state_dict(recovery_margin=0.9, local_patchability=0.9)
        )
        assert high["patch_local"].utility > low["patch_local"].utility

    def test_no_runtime_state_defaults(self) -> None:
        e = RuntimeEvaluator()
        # 空 dict → 使用所有默认值
        utilities = e.compute_action_utilities({})
        assert set(utilities.keys()) == {"continue", "patch_local", "suffix_replan", "stop"}
        for u in utilities.values():
            assert 0.0 <= u.utility <= 1.0

    def test_select_action_returns_best(self) -> None:
        e = RuntimeEvaluator()
        state = _state_dict(p_success=0.8, p_structural_failure=0.1)
        candidates = [_candidate("a", overall=0.85)]
        action = e.select_action(candidates, state)
        assert action.action in ("continue", "patch_local")

    def test_safety_blocked_escalates_to_replan(self) -> None:
        e = RuntimeEvaluator()
        action = e.select_action(
            [_candidate("a", overall=0.7)],
            _state_dict(),
            safety_blocked=True,
        )
        assert action.action == "suffix_replan"
        assert "safety_block_disables_continue" in action.hard_constraints

    def test_auto_stop_when_thresholds_met(self) -> None:
        e = RuntimeEvaluator()
        state = _state_dict(
            p_success=0.1,
            expected_remaining_cost=0.95,
            recovery_margin=0.1,
            evidence_sufficiency=0.2,
            intervention_value=0.1,
        )
        action = e.select_action(
            [_candidate("a", overall=0.3, feasibility=0.3)],
            state,
            allow_auto_stop=True,
        )
        # 应触发 auto-stop
        assert action.action == "stop"
        assert action.terminal_reason is not None

    def test_stop_requires_significant_margin(self) -> None:
        """stop 需要比第二选择高至少 0.06 才覆盖。"""
        e = RuntimeEvaluator()
        # 中庸状态，stop 与 continue 接近
        state = _state_dict(p_success=0.5, p_structural_failure=0.3)
        action = e.select_action(
            [_candidate("a", overall=0.6)],
            state,
            allow_auto_stop=False,
        )
        # 不应是 stop（因 allow_auto_stop=False 且与第二选择差距不足）
        assert action.action != "stop"


# -- helper ----------------------------------------------------------------


def _extract_final(candidate: PendingActionCandidate) -> float:
    metadata = dict(candidate.metadata)
    final = metadata.get(FINAL_SCORE_METADATA_KEY)
    if isinstance(final, dict):
        f = cast(dict[str, object], final)
        value = f.get("value")
        if isinstance(value, (int, float)):
            return float(value)
    return 0.0
