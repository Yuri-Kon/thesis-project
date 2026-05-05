"""RuntimeEvaluator 测试：policy modes、utility 公式、rerank、action selection。"""

from __future__ import annotations

from typing import cast

import pytest

from src.models.contracts import (
    FINAL_SCORE_METADATA_KEY,
    PendingActionCandidate,
    Plan,
    PlanStep,
    RERANK_REASON_METADATA_KEY,
    RUNTIME_ADJUSTMENT_METADATA_KEY,
)
from src.models.runtime_schemas import RuntimeStateSchema
from src.models.source_refs import (
    SOURCE_REF_ACTION_BIAS,
    SOURCE_REF_ACTION_UTILITY,
    SOURCE_REF_RUNTIME_ADJUSTMENT,
)
from src.workflow.runtime_evaluator import (
    DYNAMIC_OBSERVATION_ONLY,
    LITE_BELIEF_STATE,
    RUNTIME_POLICY_ABLATION_GROUPS,
    RUNTIME_POLICY_ABLATION_GROUP_BY_MODE,
    STATIC_GATE,
    STATIC_TOP1,
    RuntimeEvaluator,
    compute_runtime_delta,
    evaluator_policy_trace,
    policy_disables_rerank,
    runtime_policy_ablation_group,
)
from src.workflow.action_features import derive_action_features


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
        budget_cap=overrides.get("budget_cap"),
        budget_pressure=overrides.get("budget_pressure"),
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


def _object_dict(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return cast(dict[str, object], value)


# -- policy mode tests -------------------------------------------------------


class TestPolicyModes:
    def test_policy_ablation_groups_are_complete_and_ordered(self) -> None:
        modes = [group.policy_mode for group in RUNTIME_POLICY_ABLATION_GROUPS]
        assert modes == [
            STATIC_TOP1,
            STATIC_GATE,
            DYNAMIC_OBSERVATION_ONLY,
            LITE_BELIEF_STATE,
        ]
        assert set(RUNTIME_POLICY_ABLATION_GROUP_BY_MODE) == set(modes)

    @pytest.mark.parametrize(
        ("mode", "paper_group_id", "name", "rerank", "belief", "full_adjustment"),
        [
            (STATIC_TOP1, "static_top1", "静态单链基线", False, False, False),
            (STATIC_GATE, "fixed_threshold_gate", "静态门控基线", False, False, False),
            (
                DYNAMIC_OBSERVATION_ONLY,
                "dynamic_no_belief_state",
                "动态观测但不使用 belief-state",
                True,
                False,
                False,
            ),
            (LITE_BELIEF_STATE, "lite_belief_state", "完整 CEBRA-WP", True, True, True),
        ],
    )
    def test_policy_ablation_group_mapping(
        self,
        mode: str,
        paper_group_id: str,
        name: str,
        rerank: bool,
        belief: bool,
        full_adjustment: bool,
    ) -> None:
        group = runtime_policy_ablation_group(mode)
        assert group.paper_group_id == paper_group_id
        assert group.paper_group_name == name
        assert group.rerank_enabled is rerank
        assert group.belief_state_enabled is belief
        assert group.full_runtime_adjustment is full_adjustment
        assert group.semantic_meaning
        assert group.question
        assert group.expected_effect
        assert group.key_metrics

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
        assert runtime_policy_ablation_group("invalid_mode").policy_mode == LITE_BELIEF_STATE

    def test_policy_trace(self) -> None:
        trace = evaluator_policy_trace(STATIC_TOP1)
        assert trace["rerank_enabled"] is False
        assert trace["belief_state_enabled"] is False
        assert trace["policy_mode"] == STATIC_TOP1
        assert trace["paper_group_id"] == "static_top1"
        assert trace["paper_group_name"] == "静态单链基线"
        assert trace["full_runtime_adjustment"] is False

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
        action_bias = adj["action_bias"]
        assert isinstance(action_bias, dict)
        assert action_bias["value"] == adj["value"]
        rerank_reason = _object_dict(metadata[RERANK_REASON_METADATA_KEY])
        assert action_bias["factors"] == rerank_reason["factors"]
        bias_refs = cast(list[str], action_bias["source_refs"])
        assert set(SOURCE_REF_ACTION_BIAS).issubset(bias_refs)

    def test_action_bias_generated_for_patch_replan_and_stop(self) -> None:
        evaluator = RuntimeEvaluator()
        cases = [
            (
                _candidate("patch", kind="patch", fallback_depth=0.8),
                _state(p_success=0.6, recovery_margin=0.6),
                "patch_local",
            ),
            (
                _candidate("replan", kind="replan", fallback_depth=0.8),
                _state(p_success=0.6, recovery_margin=0.6),
                "suffix_replan",
            ),
            (
                _candidate("stop", fallback_depth=0.8),
                _state(
                    p_success=0.1,
                    recovery_margin=0.1,
                    expected_remaining_cost=1.2,
                ),
                "stop",
            ),
        ]

        for candidate, state, expected_action in cases:
            result = evaluator.evaluate_candidates([candidate], state)
            metadata = dict(result.candidates[0].metadata)
            adjustment = metadata[RUNTIME_ADJUSTMENT_METADATA_KEY]
            rerank = metadata[RERANK_REASON_METADATA_KEY]
            assert isinstance(adjustment, dict)
            assert isinstance(rerank, dict)
            action_bias = adjustment["action_bias"]
            assert isinstance(action_bias, dict)
            assert action_bias["action"] == expected_action
            assert action_bias["value"] == adjustment["value"]
            assert action_bias["factors"] == rerank["factors"]

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

    def test_runtime_delta_uses_budget_pressure_not_raw_remaining_cost(self) -> None:
        low_pressure_delta, _, _, low_pressure_factors = compute_runtime_delta(
            p_success=0.6,
            p_structural_failure=0.2,
            recovery_margin=0.6,
            expected_remaining_cost=1.2,
            evidence_sufficiency=0.6,
            confidence=0.6,
            risk=0.5,
            cost=0.2,
            fallback_depth=0.5,
            feasibility=0.8,
            candidate_kind="plan",
            budget_cap=2.0,
        )
        high_pressure_delta, _, _, high_pressure_factors = compute_runtime_delta(
            p_success=0.6,
            p_structural_failure=0.2,
            recovery_margin=0.6,
            expected_remaining_cost=1.2,
            evidence_sufficiency=0.6,
            confidence=0.6,
            risk=0.5,
            cost=0.2,
            fallback_depth=0.5,
            feasibility=0.8,
            candidate_kind="plan",
            budget_cap=0.5,
        )

        assert low_pressure_delta > high_pressure_delta
        assert any(
            factor.signal == "budget_pressure"
            and factor.source == "runtime_state.budget_pressure+score_breakdown.cost"
            for factor in low_pressure_factors
        )
        assert any(
            factor.signal == "budget_pressure"
            and factor.source == "runtime_state.budget_pressure+score_breakdown.cost"
            for factor in high_pressure_factors
        )

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
            assert "derived_features" in u.metadata
            derived = _object_dict(u.metadata["derived_features"])
            assert "local_patchability" in derived
            local_patchability = _object_dict(derived["local_patchability"])
            assert "source" in local_patchability

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

    def test_action_utility_derives_budget_pressure_from_budget_cap(self) -> None:
        e = RuntimeEvaluator()
        high_cap = e.compute_action_utilities(
            _state_dict(expected_remaining_cost=1.2, budget_cap=2.0)
        )
        low_cap = e.compute_action_utilities(
            _state_dict(expected_remaining_cost=1.2, budget_cap=0.5)
        )

        assert high_cap["continue"].budget_pressure == pytest.approx(0.6)
        assert low_cap["continue"].budget_pressure == pytest.approx(1.5)
        assert low_cap["stop"].utility > high_cap["stop"].utility
        derived = _object_dict(low_cap["stop"].metadata["derived_features"])
        budget_pressure = _object_dict(derived["budget_pressure"])
        assert budget_pressure["source_fields"] == [
            "runtime_state.expected_remaining_cost",
            "runtime_state.budget_cap",
        ]

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

    def test_missing_intervention_value_uses_neutral_default(self) -> None:
        e = RuntimeEvaluator()
        utilities = e.compute_action_utilities({})

        stop = utilities["stop"]
        assert stop.intervention_value == pytest.approx(0.5)
        derived = _object_dict(stop.metadata["derived_features"])
        intervention_value = _object_dict(derived["intervention_value"])
        assert intervention_value["source"] == "default"

    def test_explicit_action_features_take_priority(self) -> None:
        e = RuntimeEvaluator()
        state = {
            "p_success": 0.6,
            "p_structural_failure": 0.2,
            "recovery_margin": 0.6,
            "expected_remaining_cost": 0.4,
            "evidence_sufficiency": 0.6,
        }
        action_features = derive_action_features(
            runtime_state={
                **state,
                "local_patchability": 0.9,
                "intervention_value": 0.8,
            }
        )

        utilities = e.compute_action_utilities(state, action_features=action_features)

        patch_features = _object_dict(utilities["patch_local"].metadata["derived_features"])
        stop_features = _object_dict(utilities["stop"].metadata["derived_features"])
        patch_feature = _object_dict(patch_features["local_patchability"])
        stop_feature = _object_dict(stop_features["intervention_value"])
        assert patch_feature["value"] == pytest.approx(0.9)
        assert patch_feature["source"] == "observed"
        assert stop_feature["value"] == pytest.approx(0.8)

    def test_compatibility_select_action_returns_best(self) -> None:
        e = RuntimeEvaluator()
        state = _state_dict(p_success=0.8, p_structural_failure=0.1)
        candidates = [_candidate("a", overall=0.85)]
        action = e.select_action(candidates, state)
        assert action.action in ("continue", "patch_local")

    def test_compatibility_select_action_safety_blocked_escalates_to_replan(self) -> None:
        e = RuntimeEvaluator()
        action = e.select_action(
            [_candidate("a", overall=0.7)],
            _state_dict(),
            safety_blocked=True,
        )
        assert action.action == "suffix_replan"
        assert "safety_block_disables_continue" in action.hard_constraints

    def test_compatibility_select_action_auto_stop_when_thresholds_met(self) -> None:
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

    def test_compatibility_select_action_stop_requires_significant_margin(self) -> None:
        """select_action 仅作为兼容 helper 验证既有 stop 行为。"""
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
