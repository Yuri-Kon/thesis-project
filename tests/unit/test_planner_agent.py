"""PlannerAgent单元测试"""
import json
import pytest
import src.agents.planner as planner_module
from src.agents.planner import PlannerAgent, ToolSpec
from src.kg.kg_client import ToolKGError
from src.models.contracts import (
    PatchRequest,
    Plan,
    PlanPatch,
    PlanStep,
    ProteinDesignTask,
    ReplanRequest,
    StepResult,
    now_iso,
)


def _topk_registry() -> list[ToolSpec]:
    return [
        ToolSpec(
            id="seqgen_local",
            capabilities=("sequence_generation",),
            inputs=("goal",),
            outputs=("sequence",),
            cost=0.2,
            safety_level=1,
            io_type="goal_to_sequence_candidates",
            adapter_mode="local",
            priority="P0",
        ),
        ToolSpec(
            id="protgpt2",
            capabilities=("sequence_generation",),
            inputs=("goal",),
            outputs=("sequence", "sequence_candidates"),
            cost=0.35,
            safety_level=1,
            io_type="goal_to_sequence_candidates",
            adapter_mode="remote",
            priority="P0",
        ),
        ToolSpec(
            id="esmfold",
            capabilities=("structure_prediction",),
            inputs=("sequence",),
            outputs=("pdb_path", "plddt"),
            cost=0.6,
            safety_level=1,
            io_type="sequence_to_structure",
            adapter_mode="local",
            priority="P0",
        ),
        ToolSpec(
            id="nim_esmfold",
            capabilities=("structure_prediction",),
            inputs=("sequence",),
            outputs=("pdb_path", "plddt"),
            cost=0.3,
            safety_level=1,
            io_type="sequence_to_structure",
            adapter_mode="remote",
            priority="P0",
        ),
        ToolSpec(
            id="openfold",
            capabilities=("structure_prediction",),
            inputs=("sequence",),
            outputs=("pdb_path", "plddt"),
            cost=0.8,
            safety_level=1,
            io_type="sequence_to_structure",
            adapter_mode="local",
            priority="P1",
        ),
    ]


def _topk_mock_kg() -> dict:
    return {
        "capabilities": [
            {"capability_id": "sequence_generation", "name": "Sequence Generation", "domain": "protein/design"},
            {"capability_id": "structure_prediction", "name": "Structure Prediction", "domain": "protein/structure"},
        ],
        "io_types": [
            {"io_type_id": "goal_to_sequence_candidates", "input_types": ["goal"], "output_types": ["sequence"], "combinable": True},
            {"io_type_id": "sequence_to_structure", "input_types": ["sequence"], "output_types": ["structure_pdb", "plddt"], "combinable": True},
        ],
        "tools": [
            {
                "id": "seqgen_local",
                "capabilities": ["sequence_generation"],
                "priority": "P0",
                "io": {
                    "io_type_id": "goal_to_sequence_candidates",
                    "inputs": {"goal": "str"},
                    "outputs": {"sequence": "str"},
                },
                "execution": "python",
                "constraints": {},
            },
            {
                "id": "protgpt2",
                "capabilities": ["sequence_generation"],
                "priority": "P0",
                "io": {
                    "io_type_id": "goal_to_sequence_candidates",
                    "inputs": {"goal": "str"},
                    "outputs": {"sequence": "str", "sequence_candidates": "list"},
                },
                "execution": {"backend": "remote_model_service", "provider": "plm_rest"},
                "constraints": {},
            },
            {
                "id": "esmfold",
                "capabilities": ["structure_prediction"],
                "priority": "P0",
                "io": {
                    "io_type_id": "sequence_to_structure",
                    "inputs": {"sequence": "str"},
                    "outputs": {"pdb_path": "path", "plddt": "float"},
                },
                "execution": "nextflow",
                "constraints": {},
            },
            {
                "id": "nim_esmfold",
                "capabilities": ["structure_prediction"],
                "priority": "P0",
                "io": {
                    "io_type_id": "sequence_to_structure",
                    "inputs": {"sequence": "str"},
                    "outputs": {"pdb_path": "path", "plddt": "float"},
                },
                "execution": {"backend": "remote_model_service", "provider": "nvidia_nim"},
                "constraints": {},
            },
            {
                "id": "openfold",
                "capabilities": ["structure_prediction"],
                "priority": "P1",
                "io": {
                    "io_type_id": "sequence_to_structure",
                    "inputs": {"sequence": "str"},
                    "outputs": {"pdb_path": "path", "plddt": "float"},
                },
                "execution": "nextflow",
                "constraints": {},
            },
        ],
    }


def _patch_request_for_topk() -> PatchRequest:
    plan = Plan(
        task_id="task_topk_patch",
        steps=[PlanStep(id="S1", tool="esmfold", inputs={"sequence": "S0.sequence"}, metadata={})],
        constraints={},
        metadata={},
    )
    previous = StepResult(
        task_id="task_topk_patch",
        step_id="S0",
        tool="seqgen_local",
        status="success",
        failure_type=None,
        error_message=None,
        error_details={},
        outputs={"sequence": "MKTAYIAK"},
        metrics={},
        risk_flags=[],
        logs_path=None,
        timestamp=now_iso(),
    )
    return PatchRequest(
        task_id=plan.task_id,
        original_plan=plan,
        context_step_results=[previous],
        safety_events=[],
        reason="unit-test",
    )


@pytest.mark.unit
class TestPlannerAgent:
    """PlannerAgent测试类"""

    def test_plan_creates_plan_with_correct_task_id(self, sample_task: ProteinDesignTask):
        """测试计划生成时task_id正确"""
        planner = PlannerAgent()
        plan = planner.plan(sample_task)
        
        assert plan.task_id == sample_task.task_id
        assert isinstance(plan, Plan)

    def test_plan_creates_single_step_by_default(self, sample_task: ProteinDesignTask):
        """测试默认生成单步计划"""
        planner = PlannerAgent()
        plan = planner.plan(sample_task)
        
        assert len(plan.steps) == 1
        assert plan.steps[0].id == "S1"
        assert plan.steps[0].tool == "esmfold"

    def test_plan_includes_sequence_from_constraints(self, sample_task: ProteinDesignTask):
        """测试计划包含约束中的序列"""
        planner = PlannerAgent()
        plan = planner.plan(sample_task)
        
        step = plan.steps[0]
        assert "sequence" in step.inputs
        assert step.inputs["sequence"] == sample_task.constraints.get("sequence")

    def test_plan_creates_de_novo_template(self):
        """de novo 任务应生成两步模板计划"""
        task = ProteinDesignTask(
            task_id="test_denovo",
            goal="de_novo_design",
            constraints={
                "length_range": [40, 60],
                "structure_template_pdb": "data/template.pdb",
            },
            metadata={},
        )
        planner = PlannerAgent()
        plan = planner.plan(task)

        assert len(plan.steps) == 2
        assert [step.id for step in plan.steps] == ["S1", "S2"]
        assert plan.steps[0].tool == "protgpt2"
        assert plan.steps[1].tool == "esmfold"
        assert plan.steps[0].inputs["goal"] == "de_novo_design"
        assert plan.steps[0].inputs["length_range"] == [40, 60]
        assert plan.steps[1].inputs["sequence"] == "S1.sequence"
        assert plan.explanation
        assert "ProteinToolKG" in plan.explanation

    def test_plan_uses_default_sequence_when_missing(self):
        """测试当约束中没有序列时使用默认序列"""
        task = ProteinDesignTask(
            task_id="test_002",
            goal="测试任务",
            constraints={},  # 没有sequence
            metadata={},
        )
        planner = PlannerAgent()
        plan = planner.plan(task)
        
        step = plan.steps[0]
        assert "sequence" in step.inputs
        assert len(step.inputs["sequence"]) > 0  # 有默认值

    def test_plan_preserves_constraints(self, sample_task: ProteinDesignTask):
        """测试计划保留任务约束"""
        planner = PlannerAgent()
        plan = planner.plan(sample_task)
        
        assert plan.constraints == sample_task.constraints

    def test_plan_includes_kg_explanation(self, sample_task: ProteinDesignTask):
        """Planner 计划应包含基于 KG 的解释信息"""
        planner = PlannerAgent()
        plan = planner.plan(sample_task)

        explanation = plan.metadata.get("kg_explanation")
        assert isinstance(explanation, dict)
        steps = explanation.get("steps", [])
        assert steps

        step_entry = steps[0]
        assert step_entry.get("tool_id") == plan.steps[0].tool
        assert step_entry.get("capabilities")
        io_type = step_entry.get("io_type", {})
        assert io_type.get("io_type_id") is not None
        assert "constraints" in step_entry

    def test_plan_step_has_required_fields(self, sample_task: ProteinDesignTask):
        """测试计划步骤包含必需字段"""
        planner = PlannerAgent()
        plan = planner.plan(sample_task)
        
        step = plan.steps[0]
        assert step.id is not None
        assert step.tool is not None
        assert isinstance(step.inputs, dict)
        assert isinstance(step.metadata, dict)

    def test_planner_raises_when_kg_empty(self, monkeypatch):
        """KG 为空时 Planner 应该明确失败"""
        monkeypatch.setattr(planner_module, "load_tool_kg", lambda: {"tools": []})

        with pytest.raises(ToolKGError):
            PlannerAgent()

    def test_replan_replaces_failed_step(self, sample_task: ProteinDesignTask):
        """测试再规划会替换失败步骤的工具"""
        planner = PlannerAgent()
        plan = planner.plan(sample_task)

        request = ReplanRequest(
            task_id=sample_task.task_id,
            original_plan=plan,
            failed_steps=[plan.steps[0].id],
            safety_events=[],
            reason="test_replan",
        )

        replanned_plan = planner.replan(request)

        assert replanned_plan.task_id == sample_task.task_id
        assert replanned_plan.steps[0].tool != plan.steps[0].tool

    def test_plan_top_k_is_deterministic_with_default_k3(self, monkeypatch):
        monkeypatch.setattr(planner_module, "load_tool_kg", lambda: _topk_mock_kg())
        planner = PlannerAgent(tool_registry=_topk_registry())
        task = ProteinDesignTask(
            task_id="task_topk_plan",
            goal="de_novo_design",
            constraints={"length_range": [40, 60]},
            metadata={},
        )

        first = planner.plan_top_k(task)
        second = planner.plan_top_k(task)

        assert len(first.candidates) == 3
        assert [c.candidate_id for c in first.candidates] == [
            c.candidate_id for c in second.candidates
        ]
        assert first.default_recommendation == first.candidates[0].candidate_id
        assert first.explanation

        capability_buckets = {
            candidate.metadata.get("capability_bucket")
            for candidate in first.candidates
        }
        assert len(capability_buckets) >= 2

    def test_patch_top_k_has_v1_fields_and_is_serializable(self, monkeypatch):
        monkeypatch.setattr(planner_module, "load_tool_kg", lambda: _topk_mock_kg())
        planner = PlannerAgent(tool_registry=_topk_registry())
        topk = planner.patch_top_k(_patch_request_for_topk(), k=3)

        assert topk.default_recommendation == topk.candidates[0].candidate_id
        assert 1 <= len(topk.candidates) <= 3
        for candidate in topk.candidates:
            assert isinstance(candidate.structured_payload, PlanPatch)
            assert set(candidate.score_breakdown) == {
                "feasibility",
                "objective",
                "risk",
                "cost",
                "overall",
            }
            assert candidate.risk_level in {"low", "medium", "high"}
            assert candidate.cost_estimate in {"low", "medium", "high"}
            assert candidate.tool_id is not None
            assert candidate.capability_id is not None
            assert candidate.io_type is not None
            assert candidate.adapter_mode is not None
            json.dumps(candidate.model_dump(mode="json"), ensure_ascii=True)

    def test_replan_top_k_order_is_deterministic(self, monkeypatch):
        monkeypatch.setattr(planner_module, "load_tool_kg", lambda: _topk_mock_kg())
        planner = PlannerAgent(tool_registry=_topk_registry())
        original_plan = Plan(
            task_id="task_topk_replan",
            steps=[PlanStep(id="S1", tool="esmfold", inputs={"sequence": "MKT"}, metadata={})],
            constraints={"sequence": "MKT"},
            metadata={},
        )
        request = ReplanRequest(
            task_id=original_plan.task_id,
            original_plan=original_plan,
            failed_steps=["S1"],
            safety_events=[],
            reason="unit-test",
        )

        first = planner.replan_top_k(request, k=3)
        second = planner.replan_top_k(request, k=3)

        assert [c.candidate_id for c in first.candidates] == [
            c.candidate_id for c in second.candidates
        ]
        assert 1 <= len(first.candidates) <= 3
        for candidate in first.candidates:
            assert isinstance(candidate.structured_payload, Plan)
            payload = candidate.structured_payload
            assert payload.metadata.get("replan_mode") == "suffix_replan"
