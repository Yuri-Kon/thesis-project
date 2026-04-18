from types import SimpleNamespace

from src.agents.planner import ToolSpec
import src.llm.anthropic_messages_provider as anthropic_provider_module
from src.llm.anthropic_messages_provider import AnthropicMessagesProvider
from src.llm.base_llm_provider import ProviderConfig
from src.models.contracts import PatchRequest, Plan, PlanStep, ProteinDesignTask, ReplanRequest, StepResult, now_iso


def _sample_registry():
    return [
        ToolSpec(
            id="esmfold",
            capabilities=("structure_prediction",),
            inputs=("sequence",),
            outputs=("pdb_path",),
            cost=1,
            safety_level=0,
        ),
        ToolSpec(
            id="protein_mpnn",
            capabilities=("sequence_redesign",),
            inputs=("pdb_path",),
            outputs=("sequence",),
            cost=1,
            safety_level=0,
        ),
    ]


def _sample_task():
    return ProteinDesignTask(
        task_id="task_001",
        goal="design a stable protein",
        constraints={},
        metadata={},
    )


def _sample_patch_request() -> PatchRequest:
    plan = Plan(
        task_id="task_patch",
        steps=[PlanStep(id="S1", tool="esmfold", inputs={"sequence": "AAA"}, metadata={})],
        constraints={},
        metadata={},
    )
    result = StepResult(
        task_id="task_patch",
        step_id="S1",
        tool="esmfold",
        status="failed",
        failure_type="retryable",
        error_message="boom",
        error_details={},
        outputs={},
        metrics={},
        risk_flags=[],
        logs_path=None,
        timestamp=now_iso(),
    )
    return PatchRequest(
        task_id="task_patch",
        original_plan=plan,
        context_step_results=[result],
        safety_events=[],
        reason="retry exhausted",
    )


def _sample_replan_request() -> ReplanRequest:
    plan = Plan(
        task_id="task_replan",
        steps=[PlanStep(id="S1", tool="esmfold", inputs={"sequence": "AAA"}, metadata={})],
        constraints={},
        metadata={},
    )
    return ReplanRequest(
        task_id="task_replan",
        original_plan=plan,
        failed_steps=["S1"],
        safety_events=[],
        reason="patch_failed",
    )


def _fake_response(payload):
    return SimpleNamespace(
        model_dump=lambda mode="python": payload,
    )


def test_anthropic_provider_generates_plan_via_tool_use(monkeypatch):
    calls = {}

    class FakeMessages:
        def create(self, **kwargs):
            calls["kwargs"] = kwargs
            return _fake_response(
                {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "emit_plan",
                            "input": {
                                "task_id": "task_001",
                                "steps": [
                                    {"id": "S1", "tool": "esmfold", "inputs": {"sequence": "AAA"}, "metadata": {}}
                                ],
                                "constraints": {},
                                "metadata": {},
                            },
                        }
                    ]
                }
            )

    class FakeAnthropic:
        def __init__(self, *, api_key, base_url, timeout):
            calls["api_key"] = api_key
            calls["base_url"] = base_url
            calls["timeout"] = timeout
            self.messages = FakeMessages()

    monkeypatch.setattr(anthropic_provider_module, "Anthropic", FakeAnthropic)
    provider = AnthropicMessagesProvider(
        ProviderConfig(
            model_name="glm-5",
            api_key="secret",
            anthropic_version="2023-06-01",
        ),
        endpoint="https://open.bigmodel.cn/api/anthropic",
    )

    plan = provider.call_planner(_sample_task(), _sample_registry())

    assert plan["steps"][0]["tool"] == "esmfold"
    assert plan["metadata"]["provider"] == "anthropic_messages"
    assert calls["base_url"] == "https://open.bigmodel.cn/api/anthropic"
    assert calls["api_key"] == "secret"
    assert calls["kwargs"]["tool_choice"] == {"type": "tool", "name": "emit_plan"}
    assert calls["kwargs"]["extra_headers"]["anthropic-version"] == "2023-06-01"


def test_anthropic_provider_generates_patch_and_replan(monkeypatch):
    payloads = {
        "emit_patch": {
            "content": [
                {
                    "type": "tool_use",
                    "name": "emit_patch",
                    "input": {
                        "task_id": "task_patch",
                        "operations": [
                            {
                                "op": "replace_step",
                                "target": "S1",
                                "step": {
                                    "tool": "protein_mpnn",
                                    "inputs": {"pdb_path": "S1.pdb_path"},
                                    "metadata": {},
                                },
                            }
                        ],
                        "metadata": {"recovery_layer": "tool_level", "reason": "swap"},
                    },
                }
            ]
        },
        "emit_replan": {
            "content": [
                {
                    "type": "tool_use",
                    "name": "emit_replan",
                    "input": {
                        "task_id": "task_replan",
                        "steps": [
                            {"id": "S1", "tool": "protein_mpnn", "inputs": {"pdb_path": "input.pdb"}, "metadata": {}}
                        ],
                        "constraints": {},
                        "metadata": {"replan_mode": "suffix_replan"},
                    },
                }
            ]
        },
    }

    class FakeMessages:
        def create(self, **kwargs):
            tool_name = kwargs["tools"][0]["name"]
            return _fake_response(payloads[tool_name])

    class FakeAnthropic:
        def __init__(self, *, api_key, base_url, timeout):
            del api_key, base_url, timeout
            self.messages = FakeMessages()

    monkeypatch.setattr(anthropic_provider_module, "Anthropic", FakeAnthropic)
    provider = AnthropicMessagesProvider(ProviderConfig(model_name="glm-5", api_key="secret"))

    patch = provider.call_patch(_sample_patch_request(), _sample_registry())
    replan = provider.call_replan(_sample_replan_request(), _sample_registry())

    assert patch is not None
    assert patch["metadata"]["planning_mode"] == "patch"
    assert patch["operations"][0]["op"] == "replace_step"
    assert replan is not None
    assert replan["metadata"]["planning_mode"] == "replan"
    assert replan["steps"][0]["tool"] == "protein_mpnn"
