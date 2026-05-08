"""PlannerAgent单元测试"""
import json
import pytest
import src.agents.planner as planner_module
from src.agents.planner import PlannerAgent, ToolSpec
from src.agents.task_goal_parser import enrich_task_from_goal
from src.llm.base_llm_provider import ProviderConfig
from src.kg.kg_client import ToolKGError
from src.models.contracts import (
    ACTION_SCORE_METADATA_KEY,
    CAPABILITY_READINESS_METADATA_KEY,
    DEFAULT_RECOMMENDATION_REASON_METADATA_KEY,
    FINAL_SCORE_METADATA_KEY,
    PatchRequest,
    PendingActionType,
    Plan,
    PlanPatch,
    PlanPatchOp,
    PlanStep,
    ProteinDesignTask,
    RERANK_REASON_METADATA_KEY,
    ReplanRequest,
    RuntimeState,
    RUNTIME_ADJUSTMENT_METADATA_KEY,
    RUNTIME_STATE_SUMMARY_METADATA_KEY,
    SHADOW_SCORE_METADATA_KEY,
    STATIC_SCORE_METADATA_KEY,
    TOOL_READINESS_METADATA_KEY,
    WAITING_RUNTIME_SUMMARY_METADATA_KEY,
    StepResult,
    now_iso,
)
from src.models.db import ExternalStatus, InternalStatus, TaskRecord
from src.workflow.context import WorkflowContext


@pytest.fixture(autouse=True)
def _disable_catalog_provider_autoload(monkeypatch):
    monkeypatch.setenv("PLANNER_LLM_PROVIDER", "off")
    for env_name in (
        "OPENAI_API_KEY",
        "DASHSCOPE_API_KEY",
        "DEEPSEEK_API_KEY",
        "ZHIPU_API_KEY",
        "NIM_API_KEY",
    ):
        monkeypatch.delenv(env_name, raising=False)


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


class _AutoProvider:
    def __init__(self, model_name: str = "auto-provider") -> None:
        self.config = ProviderConfig(model_name=model_name)

    def call_planner(self, task: ProteinDesignTask, tool_registry: list[ToolSpec]) -> dict:
        tool_id = tool_registry[0].id if tool_registry else "dummy_tool"
        return {
            "task_id": task.task_id,
            "steps": [
                {
                    "id": "S1",
                    "tool": tool_id,
                    "inputs": {"goal": task.goal},
                    "metadata": {},
                }
            ],
            "constraints": task.constraints,
            "metadata": {"provider": self.config.model_name},
        }

    def call_patch(self, request: PatchRequest, tool_registry: list[ToolSpec]) -> dict:
        return {
            "task_id": request.task_id,
            "operations": [
                {
                    "op": "replace_step",
                    "target": request.original_plan.steps[0].id,
                    "step": {
                        "tool": tool_registry[1].id if len(tool_registry) > 1 else tool_registry[0].id,
                        "inputs": {"sequence": "S0.sequence"},
                        "metadata": {},
                    },
                }
            ],
            "metadata": {
                "recovery_layer": "tool_level",
                "reason": "llm_tool_swap",
            },
        }

    def call_replan(self, request: ReplanRequest, tool_registry: list[ToolSpec]) -> dict:
        return {
            "task_id": request.task_id,
            "steps": [
                {
                    "id": "S1",
                    "tool": tool_registry[1].id if len(tool_registry) > 1 else tool_registry[0].id,
                    "inputs": {"sequence": "MKTAYIAK"},
                    "metadata": {},
                }
            ],
            "constraints": request.original_plan.constraints,
            "metadata": {
                "replan_mode": "suffix_replan",
                "preserve_prefix_until_step_index": 0,
            },
        }


class _FailingProvider:
    def __init__(self, model_name: str = "failing-provider") -> None:
        self.config = ProviderConfig(model_name=model_name)

    def call_planner(self, task: ProteinDesignTask, tool_registry: list[ToolSpec]) -> dict:
        raise RuntimeError(f"{self.config.model_name} unavailable")

    def call_patch(self, request: PatchRequest, tool_registry: list[ToolSpec]) -> dict:
        raise RuntimeError(f"{self.config.model_name} unavailable")

    def call_replan(self, request: ReplanRequest, tool_registry: list[ToolSpec]) -> dict:
        raise RuntimeError(f"{self.config.model_name} unavailable")


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
        reason="retry exhausted",
    )


def _patch_request_for_tool(
    *,
    task_id: str,
    tool_id: str,
    inputs: dict,
    previous_outputs: dict,
) -> PatchRequest:
    plan = Plan(
        task_id=task_id,
        steps=[PlanStep(id="S1", tool=tool_id, inputs=inputs, metadata={})],
        constraints={},
        metadata={},
    )
    previous = StepResult(
        task_id=task_id,
        step_id="S0",
        tool="seed",
        status="success",
        failure_type=None,
        error_message=None,
        error_details={},
        outputs=previous_outputs,
        metrics={},
        risk_flags=[],
        logs_path=None,
        timestamp=now_iso(),
    )
    failed = StepResult(
        task_id=task_id,
        step_id="S1",
        tool=tool_id,
        status="failed",
        failure_type="TOOL_ERROR",
        error_message="boom",
        error_details={},
        outputs={},
        metrics={"retry_exhausted": True},
        risk_flags=[],
        logs_path=None,
        timestamp=now_iso(),
    )
    return PatchRequest(
        task_id=task_id,
        original_plan=plan,
        context_step_results=[previous, failed],
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
        """de novo 任务应生成包含 S4 规范的模板计划"""
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

        assert len(plan.steps) == 4
        assert [step.id for step in plan.steps] == ["S1", "S2", "S4", "S2R"]
        assert plan.steps[0].tool == "protgpt2"
        assert plan.steps[1].tool == "esmfold"
        assert plan.steps[2].tool == "protein_mpnn"
        assert plan.steps[3].tool == "esmfold"
        assert plan.steps[0].inputs["goal"] == "de_novo_design"
        assert plan.steps[0].inputs["length_range"] == [40, 60]
        assert plan.steps[1].inputs["sequence"] == "S1.sequence"
        assert plan.steps[2].inputs["pdb_path"] == "S2.pdb_path"
        assert plan.steps[3].inputs["sequence"] == "S4.sequence"
        assert plan.steps[2].metadata["stage_id"] == "S4"
        assert plan.steps[2].metadata["stop_conditions"]["max_iterations"] == 3
        assert plan.explanation
        assert "ProteinToolKG" in plan.explanation

    def test_confirmed_task_spec_blocks_unconfirmed_goal_inference(self, monkeypatch):
        """确认后的结构化字段优先于自由文本 goal。"""
        monkeypatch.setattr(planner_module, "load_tool_kg", lambda: _topk_mock_kg())
        confirmed = {
            "goal": "Evaluate the confirmed input sequence",
            "inputs": {"sequence": "MKTAYIAKQRQISFVKSHFSRQ"},
            "constraints": {
                "task_kind": "sequence_evaluation",
                "run_profile": "fast_smoke",
            },
            "metadata": {
                "intake_id": "intake_issue283_sequence",
                "planner_capability_hints": [
                    "sequence_evaluation",
                    "quality_qc",
                ],
                "intake_summary": {"field_count": 3},
            },
        }
        task = ProteinDesignTask(
            task_id="issue283_confirmed_sequence",
            goal="Design a de novo protein, length 200-300 aa, with not_in_kg_tool",
            constraints={},
            metadata={"confirmed_task_spec": confirmed},
        )
        planner = PlannerAgent(tool_registry=_topk_registry())

        plan = planner.plan(task)

        assert plan.constraints["task_kind"] == "sequence_evaluation"
        assert plan.constraints["sequence"] == "MKTAYIAKQRQISFVKSHFSRQ"
        assert "length_range" not in plan.constraints
        assert "prompt" not in plan.constraints
        assert "goal_type" not in plan.constraints
        assert all(step.tool != "not_in_kg_tool" for step in plan.steps)
        assert plan.steps[0].inputs["sequence"] == "MKTAYIAKQRQISFVKSHFSRQ"

    @pytest.mark.parametrize(
        ("task_kind", "spec_inputs", "spec_constraints", "expected_tools"),
        [
            (
                "de_novo_design",
                {},
                {"length_range": [40, 60]},
                {"seqgen_local", "protgpt2", "esmfold", "nim_esmfold", "protein_mpnn"},
            ),
            (
                "sequence_evaluation",
                {"sequence": "MKTAYIAKQRQISFVKSHFSRQ"},
                {},
                {"esmfold", "nim_esmfold", "biopython_qc"},
            ),
            (
                "template_constrained_design",
                {"template_pdb": "data/template.pdb"},
                {"length_range": [80, 120]},
                {"protein_mpnn", "esmfold", "nim_esmfold", "biopython_qc"},
            ),
        ],
    )
    def test_confirmed_task_spec_p0_task_kinds_plan_from_toolkg(
        self,
        monkeypatch,
        task_kind,
        spec_inputs,
        spec_constraints,
        expected_tools,
    ):
        """P0 场景从 ConfirmedTaskSpec 路由，且工具来自 ToolKG。"""
        monkeypatch.setattr(planner_module, "load_tool_kg", lambda: _topk_mock_kg())
        confirmed = {
            "goal": f"Confirmed {task_kind}",
            "inputs": spec_inputs,
            "constraints": {
                "task_kind": task_kind,
                "run_profile": "balanced",
                **spec_constraints,
            },
            "metadata": {
                "intake_id": f"intake_issue283_{task_kind}",
                "planner_capability_hints": ["structure_prediction"],
            },
        }
        task = ProteinDesignTask(
            task_id=f"issue283_{task_kind}",
            goal="Free text should not select tools",
            constraints={},
            metadata={"confirmed_task_spec": confirmed},
        )
        planner = PlannerAgent(tool_registry=_topk_registry())

        plan = planner.plan(task)

        assert plan.constraints["task_kind"] == task_kind
        assert {step.tool for step in plan.steps}.issubset(expected_tools)
        assert all(step.tool in {spec.id for spec in _topk_registry()} for step in plan.steps)

    def test_tool_policy_is_validated_against_toolkg(self, monkeypatch):
        """tools_allowed / tools_excluded 必须是 ToolKG 中的 tool_id。"""
        monkeypatch.setattr(planner_module, "load_tool_kg", lambda: _topk_mock_kg())
        confirmed = {
            "goal": "Confirmed de novo task",
            "constraints": {
                "task_kind": "de_novo_design",
                "length_range": [40, 60],
                "tools_allowed": ["missing_tool"],
            },
            "metadata": {
                "intake_id": "intake_issue283_policy",
                "planner_capability_hints": ["sequence_generation"],
            },
        }
        task = ProteinDesignTask(
            task_id="issue283_bad_policy",
            goal="Confirmed task",
            constraints={},
            metadata={"confirmed_task_spec": confirmed},
        )
        planner = PlannerAgent(tool_registry=_topk_registry())

        with pytest.raises(ValueError, match="tools_allowed contains unknown ToolKG tool_id"):
            planner.plan(task)

    def test_confirmed_hints_and_run_profile_only_adjust_candidates(self, monkeypatch):
        """capability_hints / run_profile 进入候选元数据和评分，不直接绑定 tool_id。"""
        monkeypatch.setattr(planner_module, "load_tool_kg", lambda: _topk_mock_kg())
        confirmed = {
            "goal": "Confirmed smoke de novo task",
            "constraints": {
                "task_kind": "de_novo_design",
                "length_range": [40, 60],
                "run_profile": "fast_smoke",
                "tools_excluded": ["seqgen_local"],
            },
            "metadata": {
                "intake_id": "intake_issue283_hints",
                "planner_capability_hints": [
                    "sequence_generation",
                    "structure_prediction",
                ],
            },
        }
        task = ProteinDesignTask(
            task_id="issue283_hints",
            goal="Use seqgen_local directly",
            constraints={},
            metadata={"confirmed_task_spec": confirmed},
        )
        planner = PlannerAgent(tool_registry=_topk_registry())

        topk = planner.plan_top_k(task, k=3)

        assert topk.candidates
        assert all(
            "seqgen_local"
            not in {step.tool for step in candidate.structured_payload.steps}
            for candidate in topk.candidates
            if isinstance(candidate.structured_payload, Plan)
        )
        for candidate in topk.candidates:
            generator = candidate.metadata["candidate_generator"]
            assert generator["policy_mode"] == "fast_smoke"
            assert generator["confirmed_task_spec_present"] is True
            assert generator["capability_hints"] == [
                "sequence_generation",
                "structure_prediction",
            ]
            assert "policy_mode_fit" in candidate.score_breakdown

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
        default_metadata = first.candidates[0].metadata
        assert default_metadata[DEFAULT_RECOMMENDATION_REASON_METADATA_KEY]["code"] == "plan_ranked_first"
        assert default_metadata[DEFAULT_RECOMMENDATION_REASON_METADATA_KEY]["selection_basis"] == "static_score"
        assert default_metadata[ACTION_SCORE_METADATA_KEY]["source"] == "score_breakdown.overall"
        assert default_metadata[STATIC_SCORE_METADATA_KEY]["value"] == pytest.approx(
            first.candidates[0].score_breakdown["overall"]
        )
        assert default_metadata[RUNTIME_ADJUSTMENT_METADATA_KEY]["value"] == pytest.approx(0.0)
        assert default_metadata[FINAL_SCORE_METADATA_KEY]["value"] == pytest.approx(
            first.candidates[0].score_breakdown["overall"]
        )
        assert default_metadata[RERANK_REASON_METADATA_KEY]["code"] == "shadow_passthrough"
        assert default_metadata[SHADOW_SCORE_METADATA_KEY]["source"] == "score_breakdown.overall_passthrough"

    def test_plan_with_status_waiting_metadata_keeps_runtime_summary_fields(self, monkeypatch):
        monkeypatch.setattr(planner_module, "load_tool_kg", lambda: _topk_mock_kg())
        planner = PlannerAgent(tool_registry=_topk_registry())
        task = ProteinDesignTask(
            task_id="task_waiting_runtime_summary",
            goal="de_novo_design",
            constraints={
                "length_range": [40, 60],
                "require_plan_confirm": True,
            },
            metadata={},
        )
        context = WorkflowContext(
            task=task,
            status=InternalStatus.CREATED,
            plan=None,
            step_results={},
            safety_events=[],
            pending_action=None,
            design_result=None,
            runtime_state=RuntimeState(
                p_success=0.58,
                p_structural_failure=0.21,
                recovery_margin=0.36,
                expected_remaining_cost=1.4,
                last_update_source="unit_test",
            ),
        )
        record = TaskRecord(
            id=task.task_id,
            goal=task.goal,
            status=ExternalStatus.CREATED,
            internal_status=InternalStatus.CREATED,
            plan=None,
            pending_action=None,
            design_result=None,
        )

        planner.plan_with_status(task, context, record=record)

        assert context.pending_action is not None
        waiting_summary = context.pending_action.metadata[WAITING_RUNTIME_SUMMARY_METADATA_KEY]
        assert waiting_summary["selected_candidate_id"] == context.pending_action.default_recommendation
        assert waiting_summary["default_recommendation_reason"]["code"] == "plan_ranked_first"
        assert waiting_summary["default_recommendation_reason"]["selection_basis"] == "final_score"
        assert waiting_summary["default_recommendation_reason"]["rerank_applied"] is True
        assert waiting_summary["final_score"]["value"] == pytest.approx(
            waiting_summary["shadow_score"]["value"]
        )
        assert waiting_summary["action_score"]["source"] == "score_breakdown.overall"
        assert waiting_summary["runtime_state_summary"]["p_success"] == pytest.approx(0.58)
        assert waiting_summary["runtime_state_summary"]["evidence_sufficiency"] == pytest.approx(0.5)
        assert waiting_summary["shadow_score"]["source"].startswith(
            "score_breakdown.overall+runtime_state.continue"
        )

    def test_plan_top_k_has_s5_contract_and_stable_weights(self, monkeypatch):
        monkeypatch.setattr(planner_module, "load_tool_kg", lambda: _topk_mock_kg())
        planner = PlannerAgent(tool_registry=_topk_registry())
        task = ProteinDesignTask(
            task_id="task_topk_s5_contract",
            goal="de_novo_design",
            constraints={
                "length_range": [40, 60],
                "score_weights": {
                    "objective": 2.0,
                    "risk": 1.0,
                    "cost": 1.0,
                    "feasibility": 1.0,
                    "confidence": 1.0,
                    "tool_readiness": 1.0,
                    "tool_coverage": 1.0,
                },
            },
            metadata={},
        )

        first = planner.plan_top_k(task, k=3)
        second = planner.plan_top_k(task, k=3)

        assert [c.candidate_id for c in first.candidates] == [
            c.candidate_id for c in second.candidates
        ]
        for first_candidate, second_candidate in zip(first.candidates, second.candidates):
            assert first_candidate.score_breakdown == second_candidate.score_breakdown
            contract = first_candidate.metadata.get("s5_contract")
            assert isinstance(contract, dict)
            assert contract.get("stage_id") == "S5"
            assert contract.get("stage_name") == "objective_scoring"
            weights = contract.get("weights")
            assert isinstance(weights, dict)
            assert pytest.approx(sum(weights.values()), rel=1e-6) == 1.0
            assert {
                "feasibility",
                "objective",
                "risk",
                "cost",
                "confidence",
                "tool_readiness",
                "tool_coverage",
            }.issubset(set(weights))

    def test_score_candidate_payload_respects_weight_bias(self, monkeypatch):
        monkeypatch.setattr(planner_module, "load_tool_kg", lambda: _topk_mock_kg())
        planner = PlannerAgent(tool_registry=_topk_registry())
        payload = Plan(
            task_id="task_score_weights",
            steps=[
                PlanStep(
                    id="S5",
                    tool="objective_ranker",
                    inputs={"candidates": [{"id": "c1"}]},
                    metadata={"stage_id": "S5", "stage_name": "objective_scoring"},
                )
            ],
            constraints={},
            metadata={},
        )

        objective_weighted = planner.score_candidate_payload(
            payload,
            task_constraints={"score_weights": {"objective": 8.0, "risk": 1.0}},
        )
        risk_weighted = planner.score_candidate_payload(
            payload,
            task_constraints={"score_weights": {"objective": 1.0, "risk": 8.0}},
        )

        assert objective_weighted["objective"] > objective_weighted["risk"]
        assert objective_weighted["overall"] > risk_weighted["overall"]

    def test_plan_top_k_runtime_rerank_updates_default_recommendation(self, monkeypatch):
        monkeypatch.setattr(planner_module, "load_tool_kg", lambda: _topk_mock_kg())
        planner = PlannerAgent(tool_registry=_topk_registry())
        task = ProteinDesignTask(
            task_id="task_topk_runtime_shadow_plan",
            goal="de_novo_design",
            constraints={"length_range": [40, 60]},
            metadata={},
        )
        baseline = planner.plan_top_k(task, k=3)
        baseline_default = baseline.default_recommendation

        def _mock_runtime_shadow_decision(*, payload, score_breakdown, candidate_kind, runtime_state_summary):
            tool_id = payload.steps[0].tool if isinstance(payload, Plan) and payload.steps else "unknown"
            final_scores = {
                "seqgen_local": 0.52,
                "protgpt2": 0.94,
                "protein_mpnn": 0.61,
                "esmfold": 0.57,
                "nim_esmfold": 0.56,
                "openfold": 0.49,
                "biopython_qc": 0.58,
                "objective_ranker": 0.55,
            }
            final_value = final_scores.get(tool_id, 0.5)
            static_value = score_breakdown["overall"]
            delta = round(final_value - static_value, 6)
            return planner_module._RuntimeShadowDecision(
                shadow_score={
                    "value": final_value,
                    "source": f"score_breakdown.overall+runtime_state.mock_{tool_id}.v1",
                },
                final_score={
                    "value": final_value,
                    "source": f"static_score+runtime_adjustment.mock_{tool_id}.v1",
                },
                runtime_adjustment={
                    "value": delta,
                    "source": f"planner.runtime_adjustment.mock_{tool_id}.v1",
                    "formula_version": "v1",
                    "shadow_only": False,
                },
                rerank_reason={
                    "code": f"rerank_{tool_id}",
                    "message": "Runtime rerank promotes lower-cost and lower-risk continuation.",
                    "shadow_only": False,
                    "runtime_state_fields": [
                        "runtime_state.p_success",
                        "runtime_state.expected_remaining_cost",
                    ],
                    "candidate_metric_fields": [
                        "score_breakdown.overall",
                        "score_breakdown.cost",
                        "score_breakdown.risk",
                    ],
                    "tool_metadata_fields": [],
                    "factors": [
                        {
                            "category": "cost",
                            "signal": "expected_remaining_cost",
                            "source": "runtime_state.expected_remaining_cost+score_breakdown.cost",
                            "contribution": round(min(0.0, delta), 6),
                            "message": "remaining cost pressure",
                        },
                        {
                            "category": "risk",
                            "signal": "p_structural_failure",
                            "source": "runtime_state.p_structural_failure+score_breakdown.risk",
                            "contribution": round(max(0.0, delta), 6),
                            "message": "risk adjustment",
                        },
                        {
                            "category": "recovery",
                            "signal": "recovery_margin",
                            "source": "runtime_state.recovery_margin+score_breakdown.fallback_depth",
                            "contribution": 0.02,
                            "message": "recovery margin",
                        },
                    ],
                },
                shadow_action="continue",
                shadow_reason="runtime rerank favors the lower-exposure candidate",
                explanation_fragment=(
                    f"Runtime rerank records static_score={static_value:.2f}, "
                    f"runtime_adjustment={delta:.2f}, final_score={final_value:.2f}."
                ),
            )

        monkeypatch.setattr(
            planner_module,
            "_build_runtime_shadow_decision",
            _mock_runtime_shadow_decision,
        )
        runtime_state = RuntimeState(
            p_success=0.62,
            p_structural_failure=0.18,
            recovery_margin=0.44,
            expected_remaining_cost=1.8,
            last_update_source="unit_test",
        )

        topk = planner.plan_top_k(task, k=3, runtime_state=runtime_state)

        assert topk.default_recommendation == topk.candidates[0].candidate_id
        assert topk.candidates[0].tool_id == "protgpt2"
        if topk.default_recommendation == baseline_default:
            assert (
                topk.candidates[0].metadata[FINAL_SCORE_METADATA_KEY]["value"]
                > topk.candidates[0].metadata[STATIC_SCORE_METADATA_KEY]["value"]
            )
            assert "Runtime rerank reasons include" in topk.explanation
        else:
            assert topk.default_recommendation != baseline_default
            assert "Runtime rerank updated default recommendation" in topk.explanation
        for candidate in topk.candidates:
            assert candidate.metadata[RUNTIME_STATE_SUMMARY_METADATA_KEY]["p_success"] == pytest.approx(0.62)
            assert candidate.metadata[RUNTIME_STATE_SUMMARY_METADATA_KEY]["evidence_sufficiency"] == pytest.approx(0.5)
            assert candidate.metadata["shadow_action"] == "continue"
            assert candidate.metadata[STATIC_SCORE_METADATA_KEY]["value"] == pytest.approx(
                candidate.score_breakdown["overall"]
            )
            assert candidate.metadata[FINAL_SCORE_METADATA_KEY]["value"] == pytest.approx(
                candidate.metadata[SHADOW_SCORE_METADATA_KEY]["value"]
            )
            assert candidate.metadata[RERANK_REASON_METADATA_KEY]["shadow_only"] is False
            categories = {
                factor["category"]
                for factor in candidate.metadata[RERANK_REASON_METADATA_KEY]["factors"]
            }
            assert {"cost", "risk", "recovery"}.issubset(categories)
            assert candidate.explanation and "Runtime rerank records static_score" in candidate.explanation
        default_reason = topk.candidates[0].metadata[DEFAULT_RECOMMENDATION_REASON_METADATA_KEY]
        assert default_reason["selection_basis"] == "final_score"
        assert default_reason["rerank_applied"] is True
        assert default_reason["static_candidate_id"] == baseline_default

    def test_patch_top_k_emits_suffix_replan_shadow_action_from_runtime_state(self, monkeypatch):
        monkeypatch.setattr(planner_module, "load_tool_kg", lambda: _topk_mock_kg())
        planner = PlannerAgent(tool_registry=_topk_registry())

        topk = planner.patch_top_k(
            _patch_request_for_topk(),
            k=3,
            runtime_state={
                "schema_version": 1,
                "p_success": 0.34,
                "p_structural_failure": 0.82,
                "recovery_margin": -0.15,
                "expected_remaining_cost": 3.6,
            },
        )

        assert topk.default_recommendation == topk.candidates[0].candidate_id
        first = topk.candidates[0]
        assert first.metadata["shadow_action"] == "suffix_replan"
        assert "structural failure pressure is high" in first.metadata["shadow_action_reason"]
        assert first.metadata[SHADOW_SCORE_METADATA_KEY]["source"].startswith(
            "score_breakdown.overall+runtime_state.suffix_replan"
        )
        assert first.metadata[RUNTIME_STATE_SUMMARY_METADATA_KEY]["p_structural_failure"] == pytest.approx(0.82)

    def test_replan_top_k_can_emit_stop_shadow_action_with_runtime_rerank(self, monkeypatch):
        monkeypatch.setattr(planner_module, "load_tool_kg", lambda: _topk_mock_kg())
        planner = PlannerAgent(tool_registry=_topk_registry())
        original = Plan(
            task_id="task_topk_runtime_shadow_replan",
            steps=[
                PlanStep(id="S1", tool="seqgen_local", inputs={"goal": "demo"}, metadata={}),
                PlanStep(id="S2", tool="esmfold", inputs={"sequence": "S1.sequence"}, metadata={}),
            ],
            constraints={"goal_type": "de_novo_design"},
            metadata={},
        )
        request = ReplanRequest(
            task_id=original.task_id,
            original_plan=original,
            failed_steps=["S2"],
            safety_events=[],
            reason="replan_after_failure",
        )
        baseline = planner.replan_top_k(request, k=3)

        topk = planner.replan_top_k(
            request,
            k=3,
            runtime_state={
                "schema_version": 1,
                "p_success": 0.12,
                "p_structural_failure": 0.63,
                "recovery_margin": -0.25,
                "expected_remaining_cost": 4.8,
            },
        )

        assert "Runtime rerank" in topk.explanation
        assert topk.candidates[0].metadata[DEFAULT_RECOMMENDATION_REASON_METADATA_KEY]["selection_basis"] == "final_score"
        assert all(candidate.metadata["shadow_action"] == "stop" for candidate in topk.candidates)
        assert all(
            candidate.metadata[SHADOW_SCORE_METADATA_KEY]["source"].startswith(
                "score_breakdown.overall+runtime_state.stop"
            )
            for candidate in topk.candidates
        )

    def test_patch_top_k_candidates_sorted_by_layer_then_overall(self, monkeypatch):
        monkeypatch.setattr(planner_module, "load_tool_kg", lambda: _topk_mock_kg())
        planner = PlannerAgent(tool_registry=_topk_registry())
        topk = planner.patch_top_k(_patch_request_for_topk(), k=6)

        layer_rank = {
            "parameter_level": 0,
            "tool_level": 1,
            "structure_level": 2,
        }
        ranks = [
            layer_rank.get(candidate.metadata.get("recovery_layer"), 999)
            for candidate in topk.candidates
        ]
        assert ranks == sorted(ranks)
        for rank in sorted(set(ranks)):
            grouped = [
                candidate.score_breakdown["overall"]
                for candidate, candidate_rank in zip(topk.candidates, ranks)
                if candidate_rank == rank
            ]
            assert grouped == sorted(grouped, reverse=True)
        assert topk.default_recommendation == topk.candidates[0].candidate_id

    def test_plan_top_k_s1_contract_fields_are_complete(self, monkeypatch):
        monkeypatch.setattr(planner_module, "load_tool_kg", lambda: _topk_mock_kg())
        planner = PlannerAgent(tool_registry=_topk_registry())
        task = ProteinDesignTask(
            task_id="task_topk_s1_fields",
            goal="de_novo_design",
            constraints={
                "length_range": [40, 60],
                "prompt": "helix-rich",
                "structure_template_pdb": "/tmp/template.pdb",
            },
            metadata={},
        )

        topk = planner.plan_top_k(task, k=3)
        assert topk.candidates

        for candidate in topk.candidates:
            payload = candidate.structured_payload
            assert isinstance(payload, Plan)
            s1 = payload.steps[0]
            assert s1.metadata.get("stage_id") == "S1"
            assert s1.metadata.get("stage_name") == "sequence_exploration"
            contract = s1.metadata.get("s1_contract")
            assert isinstance(contract, dict)
            inputs = contract.get("inputs", {})
            outputs = contract.get("outputs", {})
            assert set(inputs.keys()) == {"goal", "length_range", "prompt", "template"}
            assert set(outputs.keys()) == {
                "sequence",
                "candidates",
                "candidate_confidence",
                "candidate_source",
            }
            lineage = s1.metadata.get("lineage")
            assert isinstance(lineage, dict)
            assert lineage.get("stage_id") == "S1"
            assert lineage.get("primary_tool_id")
            assert lineage.get("selected_tool_id")
            assert isinstance(lineage.get("fallback_tool_ids"), list)

            assert candidate.metadata.get("stage_id") == "S1"
            assert candidate.metadata.get("lineage")
            assert candidate.metadata.get("sequence_confidence") == candidate.score_breakdown.get("confidence")

    def test_plan_top_k_includes_primary_and_fallback_sequence_sources(self, monkeypatch):
        monkeypatch.setattr(planner_module, "load_tool_kg", lambda: _topk_mock_kg())
        planner = PlannerAgent(tool_registry=_topk_registry())
        task = ProteinDesignTask(
            task_id="task_topk_s1_sources",
            goal="de_novo_design",
            constraints={"length_range": [35, 55]},
            metadata={},
        )

        topk = planner.plan_top_k(task, k=3)
        sources = {candidate.metadata.get("sequence_source") for candidate in topk.candidates}
        assert "primary" in sources
        assert "fallback" in sources

    def test_plan_top_k_raises_when_base_plan_has_no_steps(self, monkeypatch):
        monkeypatch.setattr(planner_module, "load_tool_kg", lambda: _topk_mock_kg())
        planner = PlannerAgent(tool_registry=_topk_registry())
        task = ProteinDesignTask(
            task_id="task_topk_empty_plan",
            goal="de_novo_design",
            constraints={"length_range": [20, 30]},
            metadata={},
        )
        monkeypatch.setattr(
            planner,
            "plan",
            lambda _task: Plan(
                task_id=_task.task_id,
                steps=[],
                constraints=_task.constraints,
                metadata={},
            ),
        )

        with pytest.raises(ValueError, match="Plan is empty; cannot build Top-K candidates"):
            planner.plan_top_k(task, k=3)

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

    def test_patch_top_k_uses_layered_priority_and_matrix_metadata(self, monkeypatch):
        monkeypatch.setattr(planner_module, "load_tool_kg", lambda: _topk_mock_kg())
        planner = PlannerAgent(tool_registry=_topk_registry())
        topk = planner.patch_top_k(_patch_request_for_topk(), k=6)

        assert topk.candidates
        first = topk.candidates[0]
        assert first.metadata.get("recovery_layer") == "parameter_level"
        assert first.metadata.get("capability_id") == "structure_prediction"

        tool_level = [
            candidate
            for candidate in topk.candidates
            if candidate.metadata.get("recovery_layer") == "tool_level"
        ]
        assert tool_level, "expected at least one tool-level fallback candidate"
        assert any(candidate.metadata.get("to_tool") == "nim_esmfold" for candidate in tool_level)
        assert any(
            candidate.metadata.get("from_tool") == "esmfold"
            and candidate.metadata.get("to_tool") == "nim_esmfold"
            for candidate in tool_level
        )

    def test_patch_top_k_respects_structure_prediction_tool_override(self, monkeypatch):
        monkeypatch.setattr(planner_module, "load_tool_kg", lambda: _topk_mock_kg())
        planner = PlannerAgent(tool_registry=_topk_registry())
        request = _patch_request_for_topk()
        request.original_plan = request.original_plan.model_copy(
            update={
                "constraints": {
                    **request.original_plan.constraints,
                    "structure_prediction_tool_override": "esmfold",
                }
            },
            deep=True,
        )
        request.reason = "plan_high_cost_low_benefit"

        with pytest.raises(ValueError, match="No patch candidate found"):
            planner.patch_top_k(request, k=6)

    def test_patch_top_k_allows_explicit_fallbacks_for_pinned_structure_tool(self, monkeypatch):
        monkeypatch.setattr(planner_module, "load_tool_kg", lambda: _topk_mock_kg())
        planner = PlannerAgent(tool_registry=_topk_registry())
        request = _patch_request_for_topk()
        request.original_plan = request.original_plan.model_copy(
            update={
                "constraints": {
                    **request.original_plan.constraints,
                    "structure_prediction_tool_override": "esmfold",
                    "fallback_tool_ids": ["nim_esmfold"],
                }
            },
            deep=True,
        )
        request.reason = "plan_high_cost_low_benefit"

        topk = planner.patch_top_k(request, k=6)

        tool_level = [
            candidate
            for candidate in topk.candidates
            if candidate.metadata.get("recovery_layer") == "tool_level"
        ]
        assert tool_level
        assert all(candidate.metadata.get("to_tool") == "nim_esmfold" for candidate in tool_level)

    def test_patch_top_k_rewrites_structure_patch_inputs_to_sequence_refs(self, monkeypatch):
        monkeypatch.setattr(planner_module, "load_tool_kg", lambda: _topk_mock_kg())
        planner = PlannerAgent(tool_registry=_topk_registry())
        request = _patch_request_for_tool(
            task_id="task_patch_seq_ref",
            tool_id="openfold",
            inputs={"sequence": "S0.candidates"},
            previous_outputs={
                "sequence": "MKTAYIAK",
                "candidates": [{"sequence": "MKTAYIAK", "score": -0.1}],
            },
        )

        topk = planner.patch_top_k(request, k=3)

        tool_level = next(
            candidate
            for candidate in topk.candidates
            if candidate.metadata.get("recovery_layer") == "tool_level"
            and candidate.metadata.get("to_tool") == "nim_esmfold"
        )
        patch = tool_level.structured_payload
        op = patch.operations[0]

        assert op.step.tool == "nim_esmfold"
        assert op.step.inputs == {"sequence": "S0.sequence"}

    def test_patch_top_k_skips_structure_guard_that_depends_on_failed_step_outputs(self, monkeypatch):
        monkeypatch.setattr(planner_module, "load_tool_kg", lambda: _topk_mock_kg())
        planner = PlannerAgent(tool_registry=_topk_registry())
        request = _patch_request_for_tool(
            task_id="task_patch_no_invalid_guard",
            tool_id="openfold",
            inputs={"sequence": "S0.sequence"},
            previous_outputs={"sequence": "MKTAYIAK"},
        )

        topk = planner.patch_top_k(request, k=6)

        assert topk.candidates
        assert all(
            candidate.metadata.get("recovery_layer") != "structure_level"
            for candidate in topk.candidates
        )

    def test_patch_top_k_supports_requirement2_qc_and_objective_replacements(self, monkeypatch):
        kg = {
            "capabilities": [
                {"capability_id": "quality_qc", "name": "Quality QC", "domain": "protein/qc"},
                {"capability_id": "objective_scoring", "name": "Objective", "domain": "protein/score"},
            ],
            "io_types": [
                {
                    "io_type_id": "sequence_structure_to_qc_metrics",
                    "input_types": ["sequence", "pdb_path"],
                    "output_types": ["qc_metrics"],
                    "combinable": True,
                },
                {
                    "io_type_id": "candidates_to_objective_scores_topk",
                    "input_types": ["candidates"],
                    "output_types": ["score_table", "top_k"],
                    "combinable": True,
                },
            ],
            "tools": [
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
                    "id": "dssp",
                    "capabilities": ["quality_qc"],
                    "priority": "P1",
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
                {
                    "id": "objective_ranker_v2",
                    "capabilities": ["objective_scoring"],
                    "priority": "P1",
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
        monkeypatch.setattr(planner_module, "load_tool_kg", lambda: kg)
        planner = PlannerAgent(
            tool_registry=[
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
                    id="dssp",
                    capabilities=("quality_qc",),
                    inputs=("sequence", "pdb_path"),
                    outputs=("qc_metrics",),
                    cost=0.3,
                    safety_level=1,
                    io_type="sequence_structure_to_qc_metrics",
                    adapter_mode="local",
                    priority="P1",
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
                ToolSpec(
                    id="objective_ranker_v2",
                    capabilities=("objective_scoring",),
                    inputs=("candidates",),
                    outputs=("score_table", "top_k"),
                    cost=0.35,
                    safety_level=1,
                    io_type="candidates_to_objective_scores_topk",
                    adapter_mode="local",
                    priority="P1",
                ),
            ]
        )

        qc_topk = planner.patch_top_k(
            _patch_request_for_tool(
                task_id="task_patch_qc",
                tool_id="biopython_qc",
                inputs={"sequence": "S0.sequence", "pdb_path": "S0.pdb_path"},
                previous_outputs={"sequence": "MKT", "pdb_path": "/tmp/a.pdb"},
            ),
            k=4,
        )
        assert any(
            candidate.metadata.get("to_tool") == "dssp"
            and candidate.metadata.get("recovery_layer") == "tool_level"
            for candidate in qc_topk.candidates
        )

        objective_topk = planner.patch_top_k(
            _patch_request_for_tool(
                task_id="task_patch_objective",
                tool_id="objective_ranker_v2",
                inputs={"candidates": "S0.candidates"},
                previous_outputs={"candidates": [{"id": "c1"}]},
            ),
            k=4,
        )
        assert any(
            candidate.metadata.get("to_tool") == "objective_ranker"
            and candidate.metadata.get("recovery_layer") == "tool_level"
            for candidate in objective_topk.candidates
        )

    def test_patch_top_k_normalizes_candidate_capability_metadata_when_payload_differs(
        self, monkeypatch
    ):
        monkeypatch.setattr(planner_module, "load_tool_kg", lambda: _topk_mock_kg())
        payload = PlanPatch(
            task_id="task_patch_provider_mismatch",
            operations=[
                PlanPatchOp(
                    op="replace_step",
                    target="S5",
                    step=PlanStep(
                        id="S5",
                        tool="objective_ranker",
                        inputs={"candidates": "S4.candidates"},
                        metadata={},
                    ),
                )
            ],
            metadata={
                "capability_id": "structure_prediction",
                "recovery_layer": "tool_level",
                "reason": "provider_patch_candidate",
                "from_tool": "openfold",
                "to_tool": "objective_ranker",
            },
        )

        topk = planner_module._build_top_k_result(
            payloads=[
                planner_module._CandidatePayload(
                    payload=payload,
                    primary_tool_id="objective_ranker",
                    capability_bucket="objective_scoring",
                    note="provider_patch:mismatch",
                    recovery_layer="tool_level",
                    recovery_reason="provider_patch_candidate",
                )
            ],
            registry=_topk_registry(),
            candidate_kind="patch",
            top_k=1,
            task_constraints={},
            runtime_state=None,
        )

        candidate = topk.candidates[0]
        assert candidate.capability_id == "objective_scoring"
        assert candidate.metadata.get("capability_id") == "objective_scoring"
        assert candidate.metadata.get("target_capability_id") == "structure_prediction"

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

    def test_score_candidate_payload_uses_capability_readiness_matrix(
        self,
        monkeypatch,
    ):
        """unavailable capability 应让 Planner 不再隐式信任该工具链。"""
        registry = [
            ToolSpec(
                id="seqgen_local",
                capabilities=("sequence_generation",),
                inputs=("goal",),
                outputs=("sequence",),
                adapter_mode="local",
                priority="P0",
            )
        ]
        planner = PlannerAgent(tool_registry=registry)
        monkeypatch.setattr(
            planner_module,
            "build_capability_readiness_snapshot",
            lambda capability_id: {
                "capability_id": capability_id,
                "status": "unavailable",
                "reason": "adapter missing",
                "degraded_reasons": ["seqgen_local: adapter_missing"],
                "tools": [
                    {
                        "tool_id": "seqgen_local",
                        "status": "unavailable",
                        "reason": "adapter not registered",
                    }
                ],
            },
        )

        score = planner.score_candidate_payload(
            Plan(
                task_id="capability_readiness_score",
                steps=[
                    PlanStep(
                        id="S1",
                        tool="seqgen_local",
                        inputs={"goal": "design"},
                        metadata={},
                    )
                ],
                constraints={},
                metadata={},
            )
        )

        assert score["tool_readiness"] == pytest.approx(0.0)

    def test_candidate_readiness_metadata_uses_capability_matrix(
        self,
        monkeypatch,
    ):
        monkeypatch.setattr(
            planner_module,
            "build_capability_readiness_snapshot",
            lambda capability_id: {
                "capability_id": capability_id,
                "status": "degraded",
                "reason": "primary tool unavailable; fallback tool is ready",
                "degraded_reasons": ["seqgen_local: adapter_missing"],
                "suggested_recovery": "Use fallback tool.",
                "last_checked_at": "2026-04-27T00:00:00+00:00",
                "tools": [
                    {
                        "tool_id": "seqgen_local",
                        "status": "unavailable",
                        "reason": "adapter not registered",
                    }
                ],
            },
        )

        metadata = planner_module._candidate_readiness_metadata(
            tool_id="seqgen_local",
            capability_id="sequence_generation",
        )

        assert metadata[TOOL_READINESS_METADATA_KEY]["tool_id"] == "seqgen_local"
        capability = metadata[CAPABILITY_READINESS_METADATA_KEY]
        assert capability["source"] == "capability_readiness_matrix"
        assert capability["selected_tool_id"] == "seqgen_local"
        assert capability["degraded_reasons"] == ["seqgen_local: adapter_missing"]

    def test_enrich_task_from_goal_infers_goal_type_prompt_and_length_range(self):
        task = ProteinDesignTask(
            task_id="nl_task_001",
            goal="设计一个长度为50的本地蛋白质，并给出结构预览",
            constraints={},
            metadata={},
        )

        enriched = enrich_task_from_goal(task)

        assert enriched.constraints["goal_type"] == "de_novo_design"
        assert enriched.constraints["prompt"] == task.goal
        assert enriched.constraints["length_range"] == [50, 50]
        assert enriched.constraints["prefer_remote"] is False
        assert enriched.metadata["nl_parse"]["source"] == "task_goal_parser_v1"

    def test_enrich_task_from_goal_extracts_sequence_without_forcing_de_novo(self):
        sequence = "MKFLKFSLLTAVLLSVVFAFSSCGDDDDTGYLPPSQAIQDLLKRMKV"
        task = ProteinDesignTask(
            task_id="nl_task_seq_001",
            goal=f"Please predict the structure for this protein sequence using remote tools if available: {sequence}",
            constraints={},
            metadata={},
        )

        enriched = enrich_task_from_goal(task)

        assert enriched.constraints["sequence"] == sequence
        assert enriched.constraints["prompt"] == task.goal
        assert enriched.constraints["prefer_remote"] is True
        assert "goal_type" not in enriched.constraints

    def test_planner_uses_sequence_extracted_from_natural_language_goal(self):
        sequence = "MKFLKFSLLTAVLLSVVFAFSSCGDDDDTGYLPPSQAIQDLLKRMKV"
        task = ProteinDesignTask(
            task_id="nl_task_seq_002",
            goal=f"Please predict the structure for this protein sequence: {sequence}",
            constraints={},
            metadata={},
        )

        planner = PlannerAgent()
        plan = planner.plan(task)

        assert plan.steps[0].inputs["sequence"] == sequence

    def test_planner_uses_natural_language_task_to_build_de_novo_plan(self, monkeypatch):
        monkeypatch.setattr(planner_module, "load_tool_kg", lambda: _topk_mock_kg())
        planner = PlannerAgent(tool_registry=_topk_registry())

        task = ProteinDesignTask(
            task_id="nl_task_002",
            goal="Design a stable mini-protein of length 40-60 aa and produce a structure preview locally.",
            constraints={},
            metadata={},
        )

        plan = planner.plan(task)

        assert len(plan.steps) >= 4
        assert [step.id for step in plan.steps[:4]] == ["S1", "S2", "S4", "S2R"]
        assert plan.steps[0].tool == "seqgen_local"
        assert plan.steps[1].tool == "esmfold"
        assert plan.steps[2].tool == "protein_mpnn"
        assert plan.constraints["goal_type"] == "de_novo_design"
        assert plan.constraints["length_range"] == [40, 60]
        assert plan.steps[0].inputs["goal"] == task.goal
        assert plan.steps[0].inputs["prompt"] == task.goal

    def test_plan_with_status_persists_enriched_natural_language_constraints(self, monkeypatch):
        monkeypatch.setattr(planner_module, "load_tool_kg", lambda: _topk_mock_kg())
        planner = PlannerAgent(tool_registry=_topk_registry())
        task = ProteinDesignTask(
            task_id="nl_task_003",
            goal="Design a stable protein sequence of length 55 aa for local structure prediction.",
            constraints={"min_candidate_confidence": 0.2, "require_plan_confirm": False},
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
        assert context.task.constraints["goal_type"] == "de_novo_design"
        assert context.task.constraints["length_range"] == [55, 55]
        assert record.constraints["goal_type"] == "de_novo_design"
        assert context.plan is not None
        assert context.plan.constraints["goal_type"] == "de_novo_design"

    def test_planner_autoloads_llm_provider_from_catalog(self, monkeypatch):
        monkeypatch.delenv("PLANNER_LLM_PROVIDER", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setattr(planner_module, "load_tool_kg", lambda: _topk_mock_kg())
        monkeypatch.setattr(planner_module, "load_provider_catalog", lambda _path: type("Catalog", (), {"providers": {"openai": object()}})())
        auto_provider = _AutoProvider("catalog-openai")
        monkeypatch.setattr(planner_module, "create_provider", lambda _settings: auto_provider)

        planner = PlannerAgent(tool_registry=_topk_registry())
        task = ProteinDesignTask(
            task_id="llm_auto_001",
            goal="Design a stable protein with structure preview.",
            constraints={},
            metadata={},
        )

        plan = planner.plan(task)

        assert planner._llm_provider is auto_provider
        assert plan.metadata["provider"] == "catalog-openai"
        assert plan.steps[0].inputs["goal"] == task.goal

    def test_planner_autoloads_domestic_llm_provider_from_catalog(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("PLANNER_LLM_PROVIDER", raising=False)
        monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
        monkeypatch.setattr(planner_module, "load_tool_kg", lambda: _topk_mock_kg())
        catalog = type(
            "Catalog",
            (),
            {
                "providers": {
                    "baseline": object(),
                    "qwen-flash": type("Settings", (), {"api_key": None, "api_key_env": "DASHSCOPE_API_KEY"})(),
                    "openai": type("Settings", (), {"api_key": None, "api_key_env": "OPENAI_API_KEY"})(),
                }
            },
        )()
        monkeypatch.setattr(planner_module, "load_provider_catalog", lambda _path: catalog)
        auto_provider = _AutoProvider("catalog-qwen")
        monkeypatch.setattr(planner_module, "create_provider", lambda _settings: auto_provider)

        planner = PlannerAgent(tool_registry=_topk_registry())
        task = ProteinDesignTask(
            task_id="llm_auto_cn_001",
            goal="Design a stable protein with structure preview.",
            constraints={},
            metadata={},
        )

        plan = planner.plan(task)

        assert planner._llm_provider is auto_provider
        assert plan.metadata["provider"] == "catalog-qwen"

    def test_planner_falls_back_to_next_catalog_provider_when_primary_call_fails(self, monkeypatch):
        monkeypatch.delenv("PLANNER_LLM_PROVIDER", raising=False)
        monkeypatch.setenv("DASHSCOPE_API_KEY", "qwen-key")
        monkeypatch.setenv("ZHIPU_API_KEY", "glm-key")
        monkeypatch.setattr(planner_module, "load_tool_kg", lambda: _topk_mock_kg())
        catalog = type(
            "Catalog",
            (),
            {
                "providers": {
                    "qwen-flash": type("Settings", (), {"api_key": None, "api_key_env": "DASHSCOPE_API_KEY"})(),
                    "glm-5": type("Settings", (), {"api_key": None, "api_key_env": "ZHIPU_API_KEY"})(),
                }
            },
        )()
        monkeypatch.setattr(planner_module, "load_provider_catalog", lambda _path: catalog)
        provider_queue = iter([_FailingProvider("catalog-qwen"), _AutoProvider("catalog-glm")])
        monkeypatch.setattr(planner_module, "create_provider", lambda _settings: next(provider_queue))

        planner = PlannerAgent(tool_registry=_topk_registry())
        task = ProteinDesignTask(
            task_id="llm_auto_fallback_001",
            goal="Design a stable protein with structure preview.",
            constraints={},
            metadata={},
        )

        plan = planner.plan(task)

        assert plan.metadata["provider"] == "catalog-glm"
        assert planner._llm_provider.config.model_name == "catalog-glm"

    def test_planner_prefers_qwen_when_multiple_domestic_keys_are_present(self, monkeypatch):
        monkeypatch.delenv("PLANNER_LLM_PROVIDER", raising=False)
        monkeypatch.setenv("DASHSCOPE_API_KEY", "qwen-key")
        monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-key")
        monkeypatch.setenv("ZHIPU_API_KEY", "glm-key")
        monkeypatch.setattr(planner_module, "load_tool_kg", lambda: _topk_mock_kg())
        catalog = type(
            "Catalog",
            (),
            {
                "providers": {
                    "baseline": object(),
                    "deepseek-chat": type("Settings", (), {"api_key": None, "api_key_env": "DEEPSEEK_API_KEY"})(),
                    "glm-5": type("Settings", (), {"api_key": None, "api_key_env": "ZHIPU_API_KEY"})(),
                    "qwen-flash": type("Settings", (), {"api_key": None, "api_key_env": "DASHSCOPE_API_KEY"})(),
                }
            },
        )()
        monkeypatch.setattr(planner_module, "load_provider_catalog", lambda _path: catalog)

        assert planner_module._resolve_local_provider_alias(catalog) == "qwen-flash"

    def test_planner_materializes_missing_llm_inputs_from_constraints_and_prior_steps(self, monkeypatch):
        monkeypatch.setattr(planner_module, "load_tool_kg", lambda: _topk_mock_kg())

        class _SparseInputProvider(_AutoProvider):
            def call_planner(self, task: ProteinDesignTask, tool_registry: list[ToolSpec]) -> dict:
                return {
                    "task_id": task.task_id,
                    "steps": [
                        {"id": "S1", "tool": "nim_esmfold", "inputs": {}, "metadata": {}},
                        {"id": "S2", "tool": "biopython_qc", "inputs": {}, "metadata": {}},
                    ],
                    "constraints": {},
                    "metadata": {"provider": self.config.model_name},
                }

        planner = PlannerAgent(
            tool_registry=_topk_registry(),
            llm_provider=_SparseInputProvider("sparse-llm"),
        )
        task = ProteinDesignTask(
            task_id="llm_sparse_inputs_001",
            goal="Predict structure and QC for the provided sequence.",
            constraints={"sequence": "MKTAYIAK"},
            metadata={},
        )

        plan = planner.plan(task)

        assert plan.constraints["sequence"] == "MKTAYIAK"
        assert plan.steps[0].inputs["sequence"] == "MKTAYIAK"
        assert plan.steps[1].inputs["sequence"] == "MKTAYIAK"
        assert plan.steps[1].inputs["pdb_path"] == "S1.pdb_path"

    def test_planner_can_disable_catalog_llm_provider_with_env(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("PLANNER_LLM_PROVIDER", "off")
        monkeypatch.setattr(planner_module, "load_tool_kg", lambda: _topk_mock_kg())
        monkeypatch.setattr(planner_module, "load_provider_catalog", lambda _path: (_ for _ in ()).throw(AssertionError("should not load catalog")))

        planner = PlannerAgent(tool_registry=_topk_registry())
        task = ProteinDesignTask(
            task_id="llm_auto_002",
            goal="simple task",
            constraints={"sequence": "MKTAYIAK"},
            metadata={},
        )

        plan = planner.plan(task)

        assert planner._llm_provider is None
        assert len(plan.steps) == 1

    def test_patch_top_k_includes_llm_generated_patch_candidate(self, monkeypatch):
        monkeypatch.setattr(planner_module, "load_tool_kg", lambda: _topk_mock_kg())
        planner = PlannerAgent(
            tool_registry=_topk_registry(),
            llm_provider=_AutoProvider("patch-llm"),
        )

        topk = planner.patch_top_k(_patch_request_for_topk(), k=4)

        assert any(
            candidate.metadata.get("planner_route", {}).get("provider_name") == "patch-llm"
            for candidate in topk.candidates
        )
        assert any(
            candidate.metadata.get("recovery_layer") == "tool_level"
            and candidate.metadata.get("recovery_reason") == "llm_tool_swap"
            for candidate in topk.candidates
        )

    def test_replan_top_k_includes_llm_generated_replan_candidate(self, monkeypatch):
        monkeypatch.setattr(planner_module, "load_tool_kg", lambda: _topk_mock_kg())
        planner = PlannerAgent(
            tool_registry=_topk_registry(),
            llm_provider=_AutoProvider("replan-llm"),
        )
        original = Plan(
            task_id="task_topk_replan_llm",
            steps=[
                PlanStep(id="S1", tool="seqgen_local", inputs={"goal": "demo"}, metadata={}),
                PlanStep(id="S2", tool="esmfold", inputs={"sequence": "S1.sequence"}, metadata={}),
            ],
            constraints={"goal_type": "de_novo_design"},
            metadata={},
        )
        request = ReplanRequest(
            task_id=original.task_id,
            original_plan=original,
            failed_steps=["S2"],
            safety_events=[],
            reason="replan_after_failure",
        )

        topk = planner.replan_top_k(request, k=3)

        assert any(
            candidate.metadata.get("planner_route", {}).get("provider_name") == "replan-llm"
            for candidate in topk.candidates
        )
