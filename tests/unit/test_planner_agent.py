"""PlannerAgent单元测试"""
import json
import pytest
import src.agents.planner as planner_module
from src.agents.planner import PlannerAgent, ToolSpec
from src.kg.kg_client import ToolKGError
from src.models.contracts import (
    PatchRequest,
    PendingActionType,
    Plan,
    PlanPatch,
    PlanStep,
    ProteinDesignTask,
    ReplanRequest,
    StepResult,
    now_iso,
)
from src.models.db import ExternalStatus, InternalStatus, TaskRecord
from src.workflow.context import WorkflowContext


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
        ToolSpec(
            id="protein_mpnn",
            capabilities=("sequence_design",),
            inputs=("pdb_path",),
            outputs=("sequence",),
            cost=0.4,
            safety_level=1,
            io_type="structure_to_sequence",
            adapter_mode="remote",
            priority="P0",
        ),
        ToolSpec(
            id="biopython_qc",
            capabilities=("quality_qc",),
            inputs=("sequence", "pdb_path"),
            outputs=("qc_metrics",),
            cost=0.2,
            safety_level=1,
            io_type="sequence_structure_to_qc_metrics",
            adapter_mode="local",
            priority="P0",
        ),
        ToolSpec(
            id="objective_ranker",
            capabilities=("objective_scoring",),
            inputs=("candidates",),
            outputs=("score_table", "top_k"),
            cost=0.25,
            safety_level=1,
            io_type="candidates_to_objective_scores_topk",
            adapter_mode="local",
            priority="P0",
        ),
    ]


def _topk_mock_kg() -> dict:
    return {
        "capabilities": [
            {"capability_id": "sequence_generation", "name": "Sequence Generation", "domain": "protein/design"},
            {"capability_id": "structure_prediction", "name": "Structure Prediction", "domain": "protein/structure"},
            {"capability_id": "sequence_design", "name": "Sequence Design", "domain": "protein/design"},
            {"capability_id": "quality_qc", "name": "Quality QC", "domain": "protein/qc"},
            {"capability_id": "objective_scoring", "name": "Objective Scoring", "domain": "protein/score"},
        ],
        "io_types": [
            {"io_type_id": "goal_to_sequence_candidates", "input_types": ["goal"], "output_types": ["sequence"], "combinable": True},
            {"io_type_id": "sequence_to_structure", "input_types": ["sequence"], "output_types": ["structure_pdb", "plddt"], "combinable": True},
            {"io_type_id": "structure_to_sequence", "input_types": ["structure_pdb"], "output_types": ["sequence"], "combinable": True},
            {"io_type_id": "sequence_structure_to_qc_metrics", "input_types": ["sequence", "structure_pdb"], "output_types": ["qc_metrics"], "combinable": True},
            {"io_type_id": "candidates_to_objective_scores_topk", "input_types": ["candidates"], "output_types": ["score_table", "top_k"], "combinable": True},
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
            {
                "id": "protein_mpnn",
                "capabilities": ["sequence_design"],
                "priority": "P0",
                "io": {
                    "io_type_id": "structure_to_sequence",
                    "inputs": {"pdb_path": "path"},
                    "outputs": {"sequence": "str"},
                },
                "execution": {"backend": "remote_model_service", "provider": "nvidia_nim"},
                "constraints": {},
            },
            {
                "id": "biopython_qc",
                "capabilities": ["quality_qc"],
                "priority": "P0",
                "io": {
                    "io_type_id": "sequence_structure_to_qc_metrics",
                    "inputs": {"sequence": "str", "pdb_path": "path"},
                    "outputs": {"qc_metrics": "dict"},
                },
                "execution": "python",
                "constraints": {},
            },
            {
                "id": "objective_ranker",
                "capabilities": ["objective_scoring"],
                "priority": "P0",
                "io": {
                    "io_type_id": "candidates_to_objective_scores_topk",
                    "inputs": {"candidates": "list"},
                    "outputs": {"score_table": "dict", "top_k": "list"},
                },
                "execution": "python",
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
            assert {
                "feasibility",
                "objective",
                "risk",
                "cost",
                "overall",
            }.issubset(set(candidate.score_breakdown))
            assert {
                "confidence",
                "tool_readiness",
                "tool_coverage",
                "fallback_depth",
            }.issubset(set(candidate.score_breakdown))
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

    def test_plan_with_status_enters_waiting_plan_confirm_when_low_confidence(self, monkeypatch):
        monkeypatch.setattr(planner_module, "load_tool_kg", lambda: _topk_mock_kg())
        planner = PlannerAgent(tool_registry=_topk_registry())
        task = ProteinDesignTask(
            task_id="task_plan_waiting",
            goal="de_novo_design",
            constraints={
                "length_range": [30, 50],
                "require_plan_confirm": False,
                "min_candidate_confidence": 0.99,
            },
            metadata={},
        )
        context = WorkflowContext(
            task=task,
            plan=None,
            step_results={},
            safety_events=[],
            design_result=None,
            status=InternalStatus.CREATED,
        )
        record = TaskRecord(
            id=task.task_id,
            status=ExternalStatus.CREATED,
            internal_status=InternalStatus.CREATED,
            goal=task.goal,
            constraints=task.constraints,
            metadata=task.metadata,
            plan=None,
        )

        planner.plan_with_status(task, context, record=record)

        assert context.status == InternalStatus.WAITING_PLAN_CONFIRM
        assert context.pending_action is not None
        assert context.pending_action.action_type == PendingActionType.PLAN_CONFIRM
        assert context.pending_action.default_recommendation is not None
        assert record.status == ExternalStatus.WAITING_PLAN_CONFIRM

    def test_plan_with_status_auto_planned_when_gate_passes(self, monkeypatch):
        monkeypatch.setattr(planner_module, "load_tool_kg", lambda: _topk_mock_kg())
        planner = PlannerAgent(tool_registry=_topk_registry())
        task = ProteinDesignTask(
            task_id="task_plan_auto",
            goal="de_novo_design",
            constraints={
                "length_range": [30, 50],
                "require_plan_confirm": False,
                "min_candidate_confidence": 0.2,
            },
            metadata={},
        )
        context = WorkflowContext(
            task=task,
            plan=None,
            step_results={},
            safety_events=[],
            design_result=None,
            status=InternalStatus.CREATED,
        )
        record = TaskRecord(
            id=task.task_id,
            status=ExternalStatus.CREATED,
            internal_status=InternalStatus.CREATED,
            goal=task.goal,
            constraints=task.constraints,
            metadata=task.metadata,
            plan=None,
        )

        planner.plan_with_status(task, context, record=record)

        assert context.status == InternalStatus.PLANNED
        assert context.pending_action is None
        assert context.plan is not None
        assert record.status == ExternalStatus.PLANNED

    def test_remote_structure_prediction_has_higher_risk_than_local(self, monkeypatch):
        monkeypatch.setattr(planner_module, "load_tool_kg", lambda: _topk_mock_kg())
        planner = PlannerAgent(tool_registry=_topk_registry())
        topk = planner.patch_top_k(_patch_request_for_topk(), k=3)

        by_tool = {c.tool_id: c for c in topk.candidates}
        assert "nim_esmfold" in by_tool
        assert "openfold" in by_tool
        assert by_tool["nim_esmfold"].score_breakdown["risk"] <= by_tool["openfold"].score_breakdown["risk"]

    def test_p0_combo_scores_include_tool_dimensions(self, monkeypatch):
        monkeypatch.setattr(planner_module, "load_tool_kg", lambda: _topk_mock_kg())
        planner = PlannerAgent(tool_registry=_topk_registry())

        protgpt2_esmfold = Plan(
            task_id="score_combo_1",
            steps=[
                PlanStep(id="S1", tool="protgpt2", inputs={"goal": "de_novo_design"}, metadata={}),
                PlanStep(id="S2", tool="esmfold", inputs={"sequence": "S1.sequence"}, metadata={}),
            ],
            constraints={},
            metadata={},
        )
        protein_mpnn_esmfold = Plan(
            task_id="score_combo_2",
            steps=[
                PlanStep(id="S1", tool="protein_mpnn", inputs={"pdb_path": "/tmp/input.pdb"}, metadata={}),
                PlanStep(id="S2", tool="esmfold", inputs={"sequence": "S1.sequence"}, metadata={}),
            ],
            constraints={},
            metadata={},
        )
        qc_objective = Plan(
            task_id="score_combo_3",
            steps=[
                PlanStep(
                    id="S1",
                    tool="biopython_qc",
                    inputs={"sequence": "MKT", "pdb_path": "/tmp/input.pdb"},
                    metadata={},
                ),
                PlanStep(
                    id="S2",
                    tool="objective_ranker",
                    inputs={"candidates": "S1.qc_metrics"},
                    metadata={},
                ),
            ],
            constraints={},
            metadata={},
        )

        score_1 = planner.score_candidate_payload(protgpt2_esmfold)
        score_2 = planner.score_candidate_payload(protein_mpnn_esmfold)
        score_3 = planner.score_candidate_payload(qc_objective)

        for score in (score_1, score_2, score_3):
            assert "tool_readiness" in score
            assert "tool_coverage" in score
            assert "fallback_depth" in score
            assert "confidence" in score
            assert 0.0 <= score["overall"] <= 1.0

        assert score_3["objective"] >= score_1["objective"]
