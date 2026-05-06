"""PlannerAgent 与 LLM Provider 集成的测试"""

import pytest
from typing import Dict, List

from src.agents.planner import PlannerAgent, ToolSpec
from src.llm.base_llm_provider import BaseProvider, ProviderConfig
from src.llm.baseline_provider import BaselineProvider
from src.llm.provider_payload_parser import ProviderPayloadValidationError
from src.models.contracts import ProteinDesignTask, Plan, PatchRequest, StepResult, now_iso
import src.agents.planner as planner_module


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


# 用于测试的 Mock Provider
class MockProvider(BaseProvider):
    """返回预定义计划的 mock provider"""

    def __init__(self, config: ProviderConfig, mock_plan: Dict | None = None):
        self.config = config
        self.mock_plan = mock_plan
        self.call_count = 0

    def call_planner(
        self,
        task: ProteinDesignTask,
        tool_registry: List[ToolSpec]
    ) -> Dict:
        """返回 mock 计划"""
        self.call_count += 1

        if self.mock_plan:
            return self.mock_plan

        # 默认 mock: 简单的两步计划
        primary_tool = tool_registry[0].id if tool_registry else "unknown_tool"
        secondary_tool = tool_registry[1].id if len(tool_registry) > 1 else primary_tool
        return {
            "task_id": task.task_id,
            "steps": [
                {
                    "id": "S1",
                    "tool": primary_tool,
                    "inputs": {"sequence": task.constraints.get("sequence", "AVILGP")},
                    "metadata": {}
                },
                {
                    "id": "S2",
                    "tool": secondary_tool,
                    "inputs": {"sequence": "S1.sequence"},
                    "metadata": {}
                }
            ],
            "constraints": task.constraints,
            "metadata": {"provider": "mock", "call_count": self.call_count}
        }


@pytest.fixture
def sample_task():
    """测试用的示例任务"""
    return ProteinDesignTask(
        task_id="test_task_001",
        goal="设计一个蛋白质序列",
        constraints={"sequence": "MKTAYIAKQRQISFVKSHFSRQLE"},
        metadata={}
    )


@pytest.fixture
def mock_provider():
    """Mock provider fixture"""
    config = ProviderConfig(model_name="mock")
    return MockProvider(config)


@pytest.fixture
def baseline_provider():
    """Baseline provider fixture"""
    config = ProviderConfig(model_name="baseline")
    return BaselineProvider(config)


class TestPlannerWithoutProvider:
    """测试 PlannerAgent 在没有 provider 时的工作（向后兼容性）"""

    def test_plan_without_provider_uses_default(self, sample_task):
        """没有 provider 的 PlannerAgent 应该使用默认单步计划"""
        planner = PlannerAgent()  # 无 provider
        plan = planner.plan(sample_task)

        assert isinstance(plan, Plan)
        assert plan.task_id == sample_task.task_id
        assert len(plan.steps) == 1
        assert plan.steps[0].id == "S1"
        assert plan.steps[0].tool == "esmfold"  # 注册表中的第一个工具

    def test_plan_preserves_constraints(self, sample_task):
        """默认计划应该保留任务约束"""
        planner = PlannerAgent()
        plan = planner.plan(sample_task)

        assert plan.constraints == sample_task.constraints

    def test_plan_uses_sequence_from_constraints(self, sample_task):
        """默认计划应该使用任务约束中的序列"""
        planner = PlannerAgent()
        plan = planner.plan(sample_task)

        assert plan.steps[0].inputs["sequence"] == sample_task.constraints["sequence"]


def test_planner_logs_provider_validation_failure(sample_task, monkeypatch):
    events = []

    class BrokenProvider(BaseProvider):
        def __init__(self):
            self.config = ProviderConfig(model_name="broken-provider")

        def call_planner(self, task, tool_registry):
            del task, tool_registry
            raise ProviderPayloadValidationError(
                candidate_kind="plan",
                failure_type="SYNTAX_INVALID",
                issues=[
                    {
                        "code": "REFERENCE_SYNTAX_INVALID",
                        "path": "$.steps[1].inputs.sequence",
                        "message": "reference token is not compliant",
                    }
                ],
                attempts=3,
            )

    monkeypatch.setattr(planner_module, "append_event", lambda task_id, event: events.append((task_id, event)))
    planner = PlannerAgent(llm_provider=BrokenProvider())

    with pytest.raises(ProviderPayloadValidationError):
        planner.plan(sample_task)

    assert events
    task_id, event = events[0]
    assert task_id == sample_task.task_id
    assert event["event"] == "PROVIDER_VALIDATION_FAILED"
    assert event["failure_code"] == "SYNTAX_INVALID"
    assert event["data"]["provider_name"] == "broken-provider"


class TestPlannerWithBaselineProvider:
    """使用 BaselineProvider 测试 PlannerAgent"""

    def test_plan_with_baseline_provider(self, sample_task, baseline_provider):
        """使用 baseline provider 的 PlannerAgent 应该生成有效计划"""
        planner = PlannerAgent(llm_provider=baseline_provider)
        plan = planner.plan(sample_task)

        assert isinstance(plan, Plan)
        assert plan.task_id == sample_task.task_id
        assert len(plan.steps) == 1
        assert "provider" in plan.metadata
        assert plan.metadata["provider"] == "baseline"

    def test_baseline_provider_matches_default_behavior(self, sample_task):
        """Baseline provider 应该匹配默认行为"""
        planner_no_provider = PlannerAgent()
        planner_with_baseline = PlannerAgent(
            llm_provider=BaselineProvider(ProviderConfig(model_name="baseline"))
        )

        plan_default = planner_no_provider.plan(sample_task)
        plan_baseline = planner_with_baseline.plan(sample_task)

        # 应该有相同的结构（忽略元数据）
        assert len(plan_default.steps) == len(plan_baseline.steps)
        assert plan_default.steps[0].tool == plan_baseline.steps[0].tool
        assert plan_default.steps[0].inputs == plan_baseline.steps[0].inputs


class TestPlannerWithMockProvider:
    """使用 MockProvider 测试 PlannerAgent"""

    def test_plan_with_mock_provider(self, sample_task, mock_provider):
        """PlannerAgent 应该使用 provider 生成计划"""
        planner = PlannerAgent(llm_provider=mock_provider)
        plan = planner.plan(sample_task)

        assert isinstance(plan, Plan)
        assert plan.task_id == sample_task.task_id
        assert len(plan.steps) == 2  # Mock 返回 2 个步骤
        assert mock_provider.call_count == 1

    def test_provider_receives_correct_parameters(self, sample_task):
        """Provider 应该接收到正确的任务和工具注册表"""
        config = ProviderConfig(model_name="test")

        # 捕获参数的自定义 mock
        class CapturingMockProvider(BaseProvider):
            def __init__(self, config):
                self.config = config
                self.received_task = None
                self.received_registry = None

            def call_planner(self, task, tool_registry):
                self.received_task = task
                self.received_registry = tool_registry
                tool_id = tool_registry[0].id if tool_registry else "unknown_tool"
                return {
                    "task_id": task.task_id,
                    "steps": [{
                        "id": "S1",
                        "tool": tool_id,
                        "inputs": {},
                        "metadata": {}
                    }],
                    "constraints": {},
                    "metadata": {}
                }

        provider = CapturingMockProvider(config)
        planner = PlannerAgent(llm_provider=provider)
        plan = planner.plan(sample_task)

        assert provider.received_task == sample_task
        assert provider.received_registry is not None
        assert len(provider.received_registry) > 0

    def test_provider_plan_normalizes_semantically_wrong_reference_fields(self, sample_task):
        class WrongRefProvider(BaseProvider):
            def __init__(self):
                self.config = ProviderConfig(model_name="wrong-ref")

            def call_planner(self, task, tool_registry):
                del tool_registry
                return {
                    "task_id": task.task_id,
                    "steps": [
                        {
                            "id": "S1",
                            "tool": "protgpt2",
                            "inputs": {"goal": task.goal},
                            "metadata": {},
                        },
                        {
                            "id": "S2",
                            "tool": "openfold",
                            "inputs": {"sequence": "S1.candidates"},
                            "metadata": {},
                        },
                        {
                            "id": "S3",
                            "tool": "objective_ranker",
                            "inputs": {"candidates": "S1.sequence"},
                            "metadata": {},
                        },
                    ],
                    "constraints": task.constraints,
                    "metadata": {},
                }

        planner = PlannerAgent(llm_provider=WrongRefProvider())
        plan = planner.plan(sample_task)

        assert plan.steps[1].inputs["sequence"] == "S1.sequence"
        assert plan.steps[2].inputs["candidates"] == "S1.candidates"

    def test_provider_plan_normalizes_tool_name_and_step_alias_references(self, sample_task):
        class WrongRefProvider(BaseProvider):
            def __init__(self):
                self.config = ProviderConfig(model_name="wrong-ref-alias")

            def call_planner(self, task, tool_registry):
                del tool_registry
                return {
                    "task_id": task.task_id,
                    "steps": [
                        {
                            "id": "S1",
                            "tool": "protgpt2",
                            "inputs": {"goal": task.goal},
                            "metadata": {},
                        },
                        {
                            "id": "S2",
                            "tool": "openfold",
                            "inputs": {"sequence": "protgpt2.sequence"},
                            "metadata": {},
                        },
                        {
                            "id": "S3",
                            "tool": "biopython_qc",
                            "inputs": {
                                "sequence": "step_1.sequence",
                                "pdb_path": "openfold.output.pdb_path",
                            },
                            "metadata": {},
                        },
                    ],
                    "constraints": task.constraints,
                    "metadata": {},
                }

        planner = PlannerAgent(llm_provider=WrongRefProvider())
        plan = planner.plan(sample_task)

        assert plan.steps[1].inputs["sequence"] == "S1.sequence"
        assert plan.steps[2].inputs["sequence"] == "S1.sequence"
        assert plan.steps[2].inputs["pdb_path"] == "S2.pdb_path"

    def test_provider_plan_normalizes_named_placeholders_to_prior_step_outputs(self, sample_task):
        class PlaceholderProvider(BaseProvider):
            def __init__(self):
                self.config = ProviderConfig(model_name="placeholder-ref")

            def call_planner(self, task, tool_registry):
                del task, tool_registry
                return {
                    "task_id": sample_task.task_id,
                    "steps": [
                        {
                            "id": "S1",
                            "tool": "protgpt2",
                            "inputs": {"goal": sample_task.goal},
                            "metadata": {},
                        },
                        {
                            "id": "S2",
                            "tool": "openfold",
                            "inputs": {"sequence": "<generated_sequence>"},
                            "metadata": {},
                        },
                        {
                            "id": "S3",
                            "tool": "biopython_qc",
                            "inputs": {
                                "sequence": "<generated_sequence>",
                                "pdb_path": "<predicted_pdb>",
                            },
                            "metadata": {},
                        },
                    ],
                    "constraints": sample_task.constraints,
                    "metadata": {},
                }

        planner = PlannerAgent(llm_provider=PlaceholderProvider())
        plan = planner.plan(sample_task)

        assert plan.steps[1].inputs["sequence"] == "S1.sequence"
        assert plan.steps[2].inputs["sequence"] == "S1.sequence"
        assert plan.steps[2].inputs["pdb_path"] == "S2.pdb_path"

    def test_provider_plan_normalizes_dollar_placeholders_to_prior_step_outputs(self, sample_task):
        class PlaceholderProvider(BaseProvider):
            def __init__(self):
                self.config = ProviderConfig(model_name="placeholder-dollar-ref")

            def call_planner(self, task, tool_registry):
                del task, tool_registry
                return {
                    "task_id": sample_task.task_id,
                    "steps": [
                        {
                            "id": "S1",
                            "tool": "protgpt2",
                            "inputs": {"goal": sample_task.goal},
                            "metadata": {},
                        },
                        {
                            "id": "S2",
                            "tool": "openfold",
                            "inputs": {"sequence": "$CANDIDATES"},
                            "metadata": {},
                        },
                        {
                            "id": "S3",
                            "tool": "biopython_qc",
                            "inputs": {
                                "sequence": "$CANDIDATES",
                                "pdb_path": "$STEP_2",
                            },
                            "metadata": {},
                        },
                        {
                            "id": "S4",
                            "tool": "objective_ranker",
                            "inputs": {"candidates": "$CANDIDATES"},
                            "metadata": {},
                        },
                    ],
                    "constraints": sample_task.constraints,
                    "metadata": {},
                }

        planner = PlannerAgent(llm_provider=PlaceholderProvider())
        plan = planner.plan(sample_task)

        assert plan.steps[1].inputs["sequence"] == "S1.sequence"
        assert plan.steps[2].inputs["sequence"] == "S1.sequence"
        assert plan.steps[2].inputs["pdb_path"] == "S2.pdb_path"
        assert plan.steps[3].inputs["candidates"] == "S1.candidates"

    def test_provider_plan_normalizes_bare_placeholder_tokens(self, sample_task):
        class PlaceholderProvider(BaseProvider):
            def __init__(self):
                self.config = ProviderConfig(model_name="placeholder-bare-ref")

            def call_planner(self, task, tool_registry):
                del task, tool_registry
                return {
                    "task_id": sample_task.task_id,
                    "steps": [
                        {
                            "id": "S1",
                            "tool": "protgpt2",
                            "inputs": {"goal": sample_task.goal},
                            "metadata": {},
                        },
                        {
                            "id": "S2",
                            "tool": "openfold",
                            "inputs": {"sequence": "CANDIDATES"},
                            "metadata": {},
                        },
                        {
                            "id": "S3",
                            "tool": "biopython_qc",
                            "inputs": {
                                "sequence": "CANDIDATES",
                                "pdb_path": "auto",
                            },
                            "metadata": {},
                        },
                    ],
                    "constraints": sample_task.constraints,
                    "metadata": {},
                }

        planner = PlannerAgent(llm_provider=PlaceholderProvider())
        plan = planner.plan(sample_task)

        assert plan.steps[1].inputs["sequence"] == "S1.sequence"
        assert plan.steps[2].inputs["sequence"] == "S1.sequence"
        assert plan.steps[2].inputs["pdb_path"] == "S2.pdb_path"

    def test_provider_patch_normalizes_semantically_wrong_reference_fields(self, sample_task):
        class WrongPatchProvider(BaseProvider):
            def __init__(self):
                self.config = ProviderConfig(model_name="wrong-patch")

            def call_planner(self, task, tool_registry):
                del tool_registry
                return {
                    "task_id": task.task_id,
                    "steps": [
                        {
                            "id": "S1",
                            "tool": "protgpt2",
                            "inputs": {"goal": task.goal},
                            "metadata": {},
                        },
                        {
                            "id": "S2",
                            "tool": "openfold",
                            "inputs": {"sequence": "S1.sequence"},
                            "metadata": {},
                        },
                    ],
                    "constraints": task.constraints,
                    "metadata": {},
                }

            def call_patch(self, request, tool_registry):
                del request, tool_registry
                return {
                    "task_id": sample_task.task_id,
                    "operations": [
                        {
                            "op": "replace_step",
                            "target": "S2",
                            "step": {
                                "id": "S2",
                                "tool": "nim_esmfold",
                                "inputs": {"sequence": "S1.candidates"},
                                "metadata": {},
                            },
                        }
                    ],
                    "metadata": {"from_tool": "openfold", "to_tool": "nim_esmfold"},
                }

        provider = WrongPatchProvider()
        planner = PlannerAgent(llm_provider=provider)
        plan = planner.plan(sample_task)
        previous = StepResult(
            task_id=sample_task.task_id,
            step_id="S1",
            tool="protgpt2",
            status="success",
            failure_type=None,
            error_message=None,
            error_details={},
            outputs={"sequence": "ACDEFGHIK", "candidates": [{"sequence": "ACDEFGHIK"}]},
            metrics={},
            risk_flags=[],
            logs_path=None,
            timestamp=now_iso(),
        )
        failed = StepResult(
            task_id=sample_task.task_id,
            step_id="S2",
            tool="openfold",
            status="failed",
            failure_type="TOOL_ERROR",
            error_message="boom",
            error_details={},
            outputs={},
            metrics={},
            risk_flags=[],
            logs_path=None,
            timestamp=now_iso(),
        )
        request = PatchRequest(
            task_id=sample_task.task_id,
            original_plan=plan,
            context_step_results=[previous, failed],
            safety_events=[],
            reason="unit-test",
        )

        topk = planner.patch_top_k(request, k=1)
        patch = topk.candidates[0].structured_payload

        assert patch.operations[0].step.inputs["sequence"] == "S1.sequence"

    def test_provider_patch_normalizes_tool_name_and_step_alias_references(self, sample_task):
        class WrongPatchProvider(BaseProvider):
            def __init__(self):
                self.config = ProviderConfig(model_name="wrong-patch-alias")

            def call_planner(self, task, tool_registry):
                del tool_registry
                return {
                    "task_id": task.task_id,
                    "steps": [
                        {
                            "id": "S1",
                            "tool": "protgpt2",
                            "inputs": {"goal": task.goal},
                            "metadata": {},
                        },
                        {
                            "id": "S2",
                            "tool": "openfold",
                            "inputs": {"sequence": "S1.sequence"},
                            "metadata": {},
                        },
                    ],
                    "constraints": task.constraints,
                    "metadata": {},
                }

            def call_patch(self, request, tool_registry):
                del request, tool_registry
                return {
                    "task_id": sample_task.task_id,
                    "operations": [
                        {
                            "op": "replace_step",
                            "target": "step_2",
                            "step": {
                                "id": "step_2",
                                "tool": "nim_esmfold",
                                "inputs": {"sequence": "protgpt2.output.sequence"},
                                "metadata": {},
                            },
                        }
                    ],
                    "metadata": {"from_tool": "openfold", "to_tool": "nim_esmfold"},
                }

        provider = WrongPatchProvider()
        planner = PlannerAgent(llm_provider=provider)
        plan = planner.plan(sample_task)
        previous = StepResult(
            task_id=sample_task.task_id,
            step_id="S1",
            tool="protgpt2",
            status="success",
            failure_type=None,
            error_message=None,
            error_details={},
            outputs={"sequence": "ACDEFGHIK", "candidates": [{"sequence": "ACDEFGHIK"}]},
            metrics={},
            risk_flags=[],
            logs_path=None,
            timestamp=now_iso(),
        )
        failed = StepResult(
            task_id=sample_task.task_id,
            step_id="S2",
            tool="openfold",
            status="failed",
            failure_type="TOOL_ERROR",
            error_message="boom",
            error_details={},
            outputs={},
            metrics={},
            risk_flags=[],
            logs_path=None,
            timestamp=now_iso(),
        )
        request = PatchRequest(
            task_id=sample_task.task_id,
            original_plan=plan,
            context_step_results=[previous, failed],
            safety_events=[],
            reason="unit-test",
        )

        topk = planner.patch_top_k(request, k=1)
        patch = topk.candidates[0].structured_payload

        assert patch.operations[0].target == "S2"
        assert patch.operations[0].step.id == "S2"
        assert patch.operations[0].step.inputs["sequence"] == "S1.sequence"

    def test_plan_with_custom_tool_registry(self, sample_task, mock_provider):
        """PlannerAgent 应该拒绝不在默认 KG 中的自定义工具"""
        custom_registry = [
            ToolSpec(
                id="custom_tool",
                capabilities=("design",),
                inputs=("sequence",),
                outputs=("result",),
                cost=1,
                safety_level=0
            )
        ]

        planner = PlannerAgent(
            tool_registry=custom_registry,
            llm_provider=mock_provider
        )
        with pytest.raises(ValueError):
            planner.plan(sample_task)

    def test_plan_with_invalid_provider_response(self, sample_task):
        """如果 provider 返回无效计划，PlannerAgent 应该抛出错误"""
        config = ProviderConfig(model_name="invalid")

        class InvalidProvider(BaseProvider):
            def __init__(self, config):
                self.config = config

            def call_planner(self, task, tool_registry):
                # 返回无效结构（缺少必需字段）
                return {"invalid": "data"}

        provider = InvalidProvider(config)
        planner = PlannerAgent(llm_provider=provider)

        with pytest.raises(Exception):  # 应该抛出验证错误
            planner.plan(sample_task)

    def test_plan_rejects_unknown_tools_from_provider(self, sample_task):
        """PlannerAgent 应该拒绝不在 KG 注册表中的工具"""
        config = ProviderConfig(model_name="test")

        class UnknownToolProvider(BaseProvider):
            def __init__(self, config):
                self.config = config

            def call_planner(self, task, tool_registry):
                return {
                    "task_id": task.task_id,
                    "steps": [{
                        "id": "S1",
                        "tool": "unknown_tool",
                        "inputs": {},
                        "metadata": {}
                    }],
                    "constraints": {},
                    "metadata": {}
                }

        planner = PlannerAgent(llm_provider=UnknownToolProvider(config))

        with pytest.raises(ValueError):
            planner.plan(sample_task)

    def test_plan_resolves_unknown_tool_by_capability(self, sample_task):
        """PlannerAgent 应该通过 capability 解析未知工具"""
        config = ProviderConfig(model_name="test")

        class CapabilityProvider(BaseProvider):
            def __init__(self, config):
                self.config = config

            def call_planner(self, task, tool_registry):
                return {
                    "task_id": task.task_id,
                    "steps": [{
                        "id": "S1",
                        "tool": "unknown",
                        "inputs": {"sequence": task.constraints.get("sequence", "")},
                        "metadata": {"capability": "structure_prediction"}
                    }],
                    "constraints": task.constraints,
                    "metadata": {}
                }

        planner = PlannerAgent(llm_provider=CapabilityProvider(config))
        plan = planner.plan(sample_task)

        assert isinstance(plan, Plan)
        assert plan.steps[0].tool == "esmfold"

    def test_plan_resolves_capability_name_text(self, sample_task):
        """PlannerAgent 应该解析自然语言 capability 名称"""
        config = ProviderConfig(model_name="test")

        class CapabilityNameProvider(BaseProvider):
            def __init__(self, config):
                self.config = config

            def call_planner(self, task, tool_registry):
                return {
                    "task_id": task.task_id,
                    "steps": [{
                        "id": "S1",
                        "tool": "unknown",
                        "inputs": {"sequence": task.constraints.get("sequence", "")},
                        "metadata": {"capability": "Structure Prediction"}
                    }],
                    "constraints": task.constraints,
                    "metadata": {}
                }

        planner = PlannerAgent(llm_provider=CapabilityNameProvider(config))
        plan = planner.plan(sample_task)

        assert plan.steps[0].tool == "esmfold"

    def test_plan_validates_provider_output(self, sample_task):
        """PlannerAgent 应该根据 Plan schema 验证 provider 输出"""
        config = ProviderConfig(model_name="test")

        # 返回有效结构的 Provider
        valid_provider = MockProvider(config, mock_plan={
            "task_id": sample_task.task_id,
            "steps": [{
                "id": "S1",
                "tool": "esmfold",
                "inputs": {"sequence": "AVILGP"},
                "metadata": {}
            }],
            "constraints": {},
            "metadata": {}
        })

        planner = PlannerAgent(llm_provider=valid_provider)
        plan = planner.plan(sample_task)

        # 应该成功验证并返回 Plan 对象
        assert isinstance(plan, Plan)
        assert plan.task_id == sample_task.task_id


class TestProviderValidation:
    """测试 provider 验证方法"""

    def test_validate_plan_with_valid_dict(self):
        """Provider 应该验证正确的计划 dict"""
        config = ProviderConfig(model_name="test")
        provider = BaselineProvider(config)

        valid_plan = {
            "task_id": "test",
            "steps": [{
                "id": "S1",
                "tool": "dummy_tool",
                "inputs": {},
                "metadata": {}
            }],
            "constraints": {},
            "metadata": {}
        }

        assert provider.validate_plan(valid_plan) is True

    def test_validate_plan_with_invalid_dict(self):
        """Provider 应该拒绝无效的计划 dict"""
        config = ProviderConfig(model_name="test")
        provider = BaselineProvider(config)

        invalid_plan = {
            "invalid": "structure"
        }

        assert provider.validate_plan(invalid_plan) is False
