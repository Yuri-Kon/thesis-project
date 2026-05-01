"""Planner ConfirmedTaskSpec 边界测试 — 验证 Planner 消费已确认结构化输入。"""

from __future__ import annotations

from typing import cast

from src.agents.planner import (
    _confirmed_task_spec_for_task,
    _candidate_generation_constraints,
    _extract_confirmed_task_spec,
    _prepare_task_for_planning,
    _project_confirmed_task_for_planner,
)
from src.models.contracts import ProteinDesignTask


def _task(**overrides: object) -> ProteinDesignTask:
    defaults: dict[str, object] = {
        "task_id": "test_task",
        "goal": "design a de novo protein around 100 aa",
        "constraints": {
            "task_kind": "de_novo_design",
            "length_range": [90, 110],
        },
        "metadata": {},
    }
    defaults.update(overrides)
    return ProteinDesignTask.model_validate(defaults)


# -- extract_confirmed_task_spec --------------------------------------------


class TestExtractConfirmedTaskSpec:
    def test_extracts_from_metadata(self) -> None:
        spec = _extract_confirmed_task_spec({
            "metadata": {
                "confirmed_task_spec": {
                    "goal": "design binding protein",
                    "constraints": {"length_range": [50, 80]},
                },
            },
        })
        assert spec is not None
        assert spec["goal"] == "design binding protein"

    def test_extracts_from_top_level_constraints(self) -> None:
        spec = _extract_confirmed_task_spec({
            "confirmed_task_spec": {
                "goal": "evaluate sequence",
            },
        })
        assert spec is not None
        assert spec["goal"] == "evaluate sequence"

    def test_returns_none_when_absent(self) -> None:
        assert _extract_confirmed_task_spec({}) is None
        assert _extract_confirmed_task_spec({"metadata": {}}) is None

    def test_metadata_takes_priority(self) -> None:
        spec = _extract_confirmed_task_spec({
            "confirmed_task_spec": {"goal": "top_level"},
            "metadata": {"confirmed_task_spec": {"goal": "metadata_level"}},
        })
        assert spec is not None
        assert spec["goal"] == "metadata_level"


# -- confirmed_task_spec_for_task -------------------------------------------


class TestConfirmedTaskSpecForTask:
    def test_finds_in_metadata(self) -> None:
        t = _task(metadata={"confirmed_task_spec": {"goal": "from metadata"}})
        spec = _confirmed_task_spec_for_task(t)
        assert spec is not None
        assert spec.get("goal") == "from metadata"

    def test_finds_in_constraints(self) -> None:
        t = _task(constraints={"confirmed_task_spec": {"goal": "from constraints"}})
        spec = _confirmed_task_spec_for_task(t)
        assert spec is not None
        assert spec.get("goal") == "from constraints"

    def test_returns_none_when_missing(self) -> None:
        assert _confirmed_task_spec_for_task(_task()) is None

    def test_metadata_wins_over_constraints(self) -> None:
        t = _task(
            metadata={"confirmed_task_spec": {"goal": "meta"}},
            constraints={"confirmed_task_spec": {"goal": "constr"}},
        )
        spec = _confirmed_task_spec_for_task(t)
        assert spec is not None
        assert spec.get("goal") == "meta"


# -- project_confirmed_task_for_planner -------------------------------------


class TestProjectConfirmedTaskForPlanner:
    def test_passes_through_without_confirmed_spec(self) -> None:
        t = _task(goal="original goal")
        projected = _project_confirmed_task_for_planner(t)
        assert projected.goal == "original goal"
        assert "confirmed_task_spec" not in cast(dict[str, object], projected.constraints)

    def test_overrides_goal_from_confirmed_spec(self) -> None:
        t = _task(
            goal="user raw text",
            metadata={
                "confirmed_task_spec": {
                    "goal": "design de novo protein 100 aa",
                    "constraints": {"length_range": [80, 120]},
                    "objective": {"objective_type": "stability"},
                    "inputs": {"sequence": "ACDEF"},
                },
            },
        )
        projected = _project_confirmed_task_for_planner(t)
        assert projected.goal == "design de novo protein 100 aa"

    def test_merges_objective_into_constraints(self) -> None:
        t = _task(
            metadata={
                "confirmed_task_spec": {
                    "objective": {"objective_type": "stability"},
                },
            },
        )
        projected = _project_confirmed_task_for_planner(t)
        constraints = cast(dict[str, object], projected.constraints)
        assert constraints.get("objective") == {"objective_type": "stability"}

    def test_merges_inputs_into_constraints(self) -> None:
        t = _task(
            metadata={
                "confirmed_task_spec": {
                    "inputs": {"sequence": "ACDEF", "template": "1abc"},
                },
            },
        )
        projected = _project_confirmed_task_for_planner(t)
        constraints = cast(dict[str, object], projected.constraints)
        assert constraints.get("inputs") == {"sequence": "ACDEF", "template": "1abc"}

    def test_injects_capability_hints(self) -> None:
        t = _task(
            metadata={
                "confirmed_task_spec": {
                    "metadata": {
                        "planner_capability_hints": ["structure_prediction", "sequence_generation"],
                    },
                },
            },
        )
        projected = _project_confirmed_task_for_planner(t)
        constraints = cast(dict[str, object], projected.constraints)
        assert constraints.get("capability_hints") == [
            "structure_prediction",
            "sequence_generation",
        ]

    def test_copies_initial_artifacts(self) -> None:
        t = _task(
            metadata={
                "confirmed_task_spec": {
                    "initial_artifacts": [
                        {"kind": "template", "path": "input/1abc.pdb"},
                    ],
                },
            },
        )
        projected = _project_confirmed_task_for_planner(t)
        constraints = cast(dict[str, object], projected.constraints)
        assert constraints.get("initial_artifacts") == [
            {"kind": "template", "path": "input/1abc.pdb"},
        ]

    def test_confirmed_constraints_preserved_in_metadata(self) -> None:
        t = _task(
            metadata={
                "confirmed_task_spec": {
                    "constraints": {"length_range": [50, 80], "design_count": 3},
                },
            },
        )
        projected = _project_confirmed_task_for_planner(t)
        assert "confirmed_task_spec" in cast(dict[str, object], projected.metadata)

    def test_empty_goal_in_confirmed_spec_preserves_original(self) -> None:
        t = _task(
            goal="keep me",
            metadata={"confirmed_task_spec": {"goal": ""}},
        )
        projected = _project_confirmed_task_for_planner(t)
        assert projected.goal == "keep me"


# -- prepare_task_for_planning ----------------------------------------------


class TestPrepareTaskForPlanning:
    def test_uses_confirmed_spec_when_present(self) -> None:
        t = _task(
            goal="raw user text",
            metadata={
                "confirmed_task_spec": {
                    "goal": "confirmed goal text",
                    "constraints": {"length_range": [60, 100]},
                },
            },
        )
        prepared = _prepare_task_for_planning(t)
        assert prepared.goal == "confirmed goal text"

    def test_falls_back_to_enrich_when_no_confirmed_spec(self) -> None:
        t = _task(goal="design a stable de novo protein around 120 aa")
        prepared = _prepare_task_for_planning(t)
        # 应通过 enrich_task_from_goal 解析
        assert prepared.goal == t.goal
        # 解析后应填充 constraints
        constraints = cast(dict[str, object], prepared.constraints)
        assert "task_kind" in constraints or len(constraints) > len(t.constraints or {})

    def test_enrich_does_not_override_explicit_constraints(self) -> None:
        t = _task(
            goal="design binding protein 150 aa",
            constraints={"design_count": 16},
        )
        prepared = _prepare_task_for_planning(t)
        constraints = cast(dict[str, object], prepared.constraints)
        assert constraints["design_count"] == 16


# -- candidate_generation_constraints ---------------------------------------


class TestCandidateGenerationConstraints:
    def test_passes_confirmed_spec_from_metadata(self) -> None:
        gen = _candidate_generation_constraints(
            constraints={},
            metadata={
                "confirmed_task_spec": {
                    "constraints": {"length_range": [100, 200]},
                },
            },
        )
        assert "confirmed_task_spec" in gen

    def test_passes_confirmed_spec_from_top_level_constraints(self) -> None:
        gen = _candidate_generation_constraints(
            constraints={
                "confirmed_task_spec": {"objective": {"objective_type": "stability"}},
            },
            metadata={},
        )
        assert "confirmed_task_spec" in gen

    def test_no_confirmed_spec_no_injection(self) -> None:
        gen = _candidate_generation_constraints(constraints={}, metadata={})
        assert "confirmed_task_spec" not in gen


# -- raw_query 隔离 ---------------------------------------------------------


class TestRawQueryIsolation:
    """未确认 raw_query 不得覆盖已确认结构化字段。"""

    def test_raw_query_preserved_in_metadata_not_constraints(self) -> None:
        t = _task(
            goal="design toxin-like protein 300 aa",
            metadata={
                "confirmed_task_spec": {
                    "goal": "design de novo stability 100 aa",
                    "constraints": {"length_range": [80, 120]},
                },
            },
        )
        projected = _project_confirmed_task_for_planner(t)
        # ConfirmedSpec 的 goal 覆盖原始 goal
        assert projected.goal == "design de novo stability 100 aa"
        # 原始文本不在 constraints 中
        constraints = cast(dict[str, object], projected.constraints)
        assert constraints.get("length_range") == [80, 120]

    def test_raw_text_not_injected_as_field(self) -> None:
        """原始自然语言不得作为 Planner 的隐含自由输入。"""
        t = _task(
            goal="user wants a 500 aa megaprotein",
            metadata={
                "confirmed_task_spec": {
                    "constraints": {"length_range": [60, 90]},
                },
            },
        )
        projected = _project_confirmed_task_for_planner(t)
        constraints = cast(dict[str, object], projected.constraints)
        # 必须以 confirmed spec 为准
        assert constraints.get("length_range") == [60, 90]
