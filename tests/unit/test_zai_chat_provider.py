import json
from types import SimpleNamespace

from src.agents.planner import ToolSpec
from src.llm.base_llm_provider import ProviderConfig
from src.llm.provider_payload_parser import ProviderPayloadValidationError
import src.llm.zai_chat_provider as provider_module
from src.llm.zai_chat_provider import ZaiChatProvider
from src.models.contracts import PatchRequest, Plan, PlanStep, ProteinDesignTask, ReplanRequest


def _setup_dummy_zai(monkeypatch, *, response_content=None, stream_parts=None):
    calls = {}

    class DummyCompletions:
        def create(self, **kwargs):
            calls["request_kwargs"] = kwargs
            if kwargs.get("stream"):
                parts = stream_parts or []
                return iter(
                    [
                        SimpleNamespace(
                            choices=[
                                SimpleNamespace(
                                    delta=SimpleNamespace(
                                        content=part,
                                        reasoning_content=None,
                                    )
                                )
                            ]
                        )
                        for part in parts
                    ]
                )
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content=response_content)
                    )
                ]
            )

    class DummyZai:
        def __init__(self, **kwargs):
            calls["client_kwargs"] = kwargs
            self.chat = SimpleNamespace(completions=DummyCompletions())

    monkeypatch.setattr(provider_module, "ZAI_AVAILABLE", True)
    monkeypatch.setattr(provider_module, "ZaiClient", DummyZai, raising=False)
    return calls


def _sample_task():
    return ProteinDesignTask(
        task_id="task_001",
        goal="design a protein",
        constraints={},
        metadata={},
    )


def _sample_registry():
    return [
        ToolSpec(
            id="dummy_tool",
            capabilities=("design",),
            inputs=(),
            outputs=(),
            cost=1,
            safety_level=0,
        )
    ]


def test_zai_provider_uses_glm5_defaults(monkeypatch):
    task = _sample_task()
    plan_dict = {
        "task_id": task.task_id,
        "steps": [
            {"id": "S1", "tool": "dummy_tool", "inputs": {}, "metadata": {}}
        ],
        "constraints": {},
        "metadata": {},
    }
    calls = _setup_dummy_zai(monkeypatch, response_content=json.dumps(plan_dict))

    provider = ZaiChatProvider(
        ProviderConfig(
            model_name="glm-5",
            api_key="test-key",
            max_tokens=4000,
            temperature=0.2,
            top_p=1.0,
            structured_output_mode="json_schema",
            extra_body={"thinking": {"type": "enabled"}},
        )
    )

    plan = provider.call_planner(task, _sample_registry())

    assert plan["task_id"] == task.task_id
    assert calls["client_kwargs"]["api_key"] == "test-key"
    request_kwargs = calls["request_kwargs"]
    assert request_kwargs["model"] == "glm-5"
    assert request_kwargs["thinking"] == {"type": "enabled"}
    assert request_kwargs["response_format"]["type"] == "json_schema"
    assert plan["metadata"]["provider"] == "zai_chat"


def test_zai_provider_supports_patch_and_replan(monkeypatch):
    payloads = [
        {
            "task_id": "task_patch",
            "operations": [
                {
                    "op": "replace_step",
                    "target": "S1",
                    "step": {
                        "tool": "dummy_tool",
                        "inputs": {},
                        "metadata": {},
                    },
                }
            ],
            "metadata": {"recovery_layer": "tool_level", "reason": "swap"},
        },
        {
            "task_id": "task_replan",
            "steps": [
                {"id": "S1", "tool": "dummy_tool", "inputs": {}, "metadata": {}}
            ],
            "constraints": {},
            "metadata": {"replan_mode": "suffix_replan"},
        },
    ]
    calls = {"index": 0}

    class DummyCompletions:
        def create(self, **kwargs):
            payload = payloads[calls["index"]]
            calls["index"] += 1
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))]
            )

    class DummyZai:
        def __init__(self, **kwargs):
            del kwargs
            self.chat = SimpleNamespace(completions=DummyCompletions())

    monkeypatch.setattr(provider_module, "ZAI_AVAILABLE", True)
    monkeypatch.setattr(provider_module, "ZaiClient", DummyZai, raising=False)

    provider = ZaiChatProvider(ProviderConfig(model_name="glm-5", api_key="secret"))

    patch = provider.call_patch(
        PatchRequest(
            task_id="task_patch",
            original_plan=Plan(
                task_id="task_patch",
                steps=[
                    PlanStep(
                        id="S1", tool="dummy_tool", inputs={}, metadata={}
                    )
                ],
                constraints={},
                metadata={},
            ),
            context_step_results=[],
            safety_events=[],
            reason="retry exhausted",
        ),
        _sample_registry(),
    )
    replan = provider.call_replan(
        ReplanRequest(
            task_id="task_replan",
            original_plan=Plan(
                task_id="task_replan",
                steps=[
                    PlanStep(
                        id="S1", tool="dummy_tool", inputs={}, metadata={}
                    )
                ],
                constraints={},
                metadata={},
            ),
            failed_steps=["S1"],
            safety_events=[],
            reason="patch_failed",
        ),
        _sample_registry(),
    )

    assert patch is not None
    assert patch["metadata"]["planning_mode"] == "patch"
    assert replan is not None
    assert replan["metadata"]["planning_mode"] == "replan"


def test_zai_provider_strips_markdown_json_fence(monkeypatch):
    task = _sample_task()
    plan_dict = {
        "task_id": task.task_id,
        "steps": [
            {"id": "S1", "tool": "dummy_tool", "inputs": {}, "metadata": {}}
        ],
        "constraints": {},
        "metadata": {},
    }
    fenced_content = f"```json\n{json.dumps(plan_dict, ensure_ascii=False, indent=2)}\n```"
    _setup_dummy_zai(monkeypatch, response_content=fenced_content)

    provider = ZaiChatProvider(
        ProviderConfig(
            model_name="glm-5",
            api_key="test-key",
            structured_output_mode="json_schema",
        )
    )

    plan = provider.call_planner(task, _sample_registry())

    assert plan["task_id"] == task.task_id
    assert plan["steps"][0]["tool"] == "dummy_tool"


def test_zai_provider_empty_response_raises_with_diagnostic_summary(monkeypatch):
    task = _sample_task()
    _setup_dummy_zai(monkeypatch, response_content="")

    provider = ZaiChatProvider(
        ProviderConfig(
            model_name="glm-5",
            api_key="test-key",
            structured_output_mode="json_schema",
            extra_body={"thinking": {"type": "enabled"}},
        )
    )

    try:
        provider.call_planner(task, _sample_registry())
    except ProviderPayloadValidationError as exc:
        payload = exc.as_event_payload()
    else:
        raise AssertionError("expected ProviderPayloadValidationError")

    assert payload["failure_code"] == "empty_response"
    failure = payload["failures"][0]
    assert failure["code"] == "EMPTY_PROVIDER_RESPONSE"
    observed = failure["observed"]
    assert observed["provider"] == "zai_chat"
    assert observed["model"] == "glm-5"
    assert observed["request"]["response_format_type"] == "json_schema"
    assert observed["request"]["has_thinking"] is True
    assert observed["request"]["prompt"]["user"]["chars"] > 0
    assert "content_length" in observed["response"]
    assert "structured_output_mode_may_be_unsupported_or_unsatisfied" in observed["possible_causes"]


def test_zai_provider_invocation_failure_raises_with_diagnostic_summary(monkeypatch):
    task = _sample_task()
    calls = {}

    class DummyCompletions:
        def create(self, **kwargs):
            calls["request_kwargs"] = kwargs
            raise ConnectionError("Connection refused")

    class DummyZai:
        def __init__(self, **kwargs):
            calls["client_kwargs"] = kwargs
            self.chat = SimpleNamespace(completions=DummyCompletions())

    monkeypatch.setattr(provider_module, "ZAI_AVAILABLE", True)
    monkeypatch.setattr(provider_module, "ZaiClient", DummyZai, raising=False)

    provider = ZaiChatProvider(
        ProviderConfig(
            model_name="glm-5",
            api_key="test-key",
            max_tokens=1048576,
            structured_output_mode="json_schema",
            extra_body={"thinking": {"type": "enabled"}},
        )
    )

    try:
        provider.call_planner(task, _sample_registry())
    except ProviderPayloadValidationError as exc:
        payload = exc.as_event_payload()
    else:
        raise AssertionError("expected ProviderPayloadValidationError")

    assert payload["failure_code"] == "provider_invocation_failed"
    failure = payload["failures"][0]
    assert failure["code"] == "PROVIDER_INVOCATION_FAILED"
    observed = failure["observed"]
    assert observed["provider"] == "zai_chat"
    assert observed["model"] == "glm-5"
    assert observed["request"]["max_tokens"] == 1048576
    assert observed["exception"]["type"] == "ConnectionError"
    assert "provider_connection_failure" in observed["possible_causes"]
