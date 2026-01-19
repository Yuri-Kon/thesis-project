import json
from types import SimpleNamespace

from src.agents.planner import ToolSpec
from src.llm.base_llm_provider import ProviderConfig
from src.models.contracts import ProteinDesignTask
import src.llm.openai_compatible_provider as provider_module


def _setup_dummy_openai(monkeypatch, *, response_content=None, stream_parts=None):
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

    class DummyOpenAI:
        def __init__(self, **kwargs):
            calls["client_kwargs"] = kwargs
            self.chat = SimpleNamespace(completions=DummyCompletions())

    monkeypatch.setattr(provider_module, "OPENAI_AVAILABLE", True)
    monkeypatch.setattr(provider_module, "OpenAI", DummyOpenAI, raising=False)
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


def test_openai_provider_uses_config_options(monkeypatch):
    task = _sample_task()
    plan_dict = {
        "task_id": task.task_id,
        "steps": [
            {"id": "S1", "tool": "dummy_tool", "inputs": {}, "metadata": {}}
        ],
        "constraints": {},
        "metadata": {},
    }
    calls = _setup_dummy_openai(monkeypatch, response_content=json.dumps(plan_dict))

    config = ProviderConfig(
        model_name="test-model",
        api_key="test-key",
        timeout=12,
        max_tokens=123,
        temperature=0.9,
        top_p=0.5,
        extra_body={"foo": "bar"},
    )
    provider = provider_module.OpenAICompatibleProvider(
        config,
        endpoint="http://example.test/v1",
    )

    plan = provider.call_planner(task, _sample_registry())

    assert plan["task_id"] == task.task_id
    assert calls["client_kwargs"]["api_key"] == "test-key"
    assert calls["client_kwargs"]["base_url"] == "http://example.test/v1"

    request_kwargs = calls["request_kwargs"]
    assert request_kwargs["model"] == "test-model"
    assert request_kwargs["temperature"] == 0.9
    assert request_kwargs["top_p"] == 0.5
    assert request_kwargs["max_tokens"] == 123
    assert request_kwargs["timeout"] == 12
    assert request_kwargs["extra_body"] == {"foo": "bar"}
    assert request_kwargs["response_format"] == {"type": "json_object"}


def test_openai_provider_streams_content(monkeypatch):
    task = _sample_task()
    plan_dict = {
        "task_id": task.task_id,
        "steps": [
            {"id": "S1", "tool": "dummy_tool", "inputs": {}, "metadata": {}}
        ],
        "constraints": {},
        "metadata": {},
    }
    content = json.dumps(plan_dict)
    calls = _setup_dummy_openai(
        monkeypatch,
        stream_parts=[content[:10], content[10:]],
    )

    config = ProviderConfig(
        model_name="test-model",
        api_key="test-key",
        stream=True,
        use_response_format=False,
    )
    provider = provider_module.OpenAICompatibleProvider(config)

    plan = provider.call_planner(task, _sample_registry())

    assert plan["task_id"] == task.task_id
    request_kwargs = calls["request_kwargs"]
    assert request_kwargs["stream"] is True
    assert "response_format" not in request_kwargs


def test_openai_provider_includes_tool_details_in_prompt(monkeypatch):
    task = _sample_task()
    plan_dict = {
        "task_id": task.task_id,
        "steps": [
            {"id": "S1", "tool": "dummy_tool", "inputs": {}, "metadata": {}}
        ],
        "constraints": {},
        "metadata": {},
    }
    calls = _setup_dummy_openai(monkeypatch, response_content=json.dumps(plan_dict))

    config = ProviderConfig(
        model_name="test-model",
        api_key="test-key",
    )
    provider = provider_module.OpenAICompatibleProvider(config)

    provider.call_planner(task, _sample_registry())

    user_prompt = calls["request_kwargs"]["messages"][1]["content"]
    assert "可用工具" in user_prompt
    assert "dummy_tool" in user_prompt


def test_openai_provider_stream_ignores_empty_choices(monkeypatch):
    task = _sample_task()
    plan_dict = {
        "task_id": task.task_id,
        "steps": [
            {"id": "S1", "tool": "dummy_tool", "inputs": {}, "metadata": {}}
        ],
        "constraints": {},
        "metadata": {},
    }
    content = json.dumps(plan_dict)
    calls = {}

    class DummyCompletions:
        def create(self, **kwargs):
            calls["request_kwargs"] = kwargs
            return iter(
                [
                    SimpleNamespace(choices=[]),
                    SimpleNamespace(
                        choices=[
                            SimpleNamespace(
                                delta=SimpleNamespace(content=content, reasoning_content=None)
                            )
                        ]
                    ),
                ]
            )

    class DummyOpenAI:
        def __init__(self, **kwargs):
            calls["client_kwargs"] = kwargs
            self.chat = SimpleNamespace(completions=DummyCompletions())

    monkeypatch.setattr(provider_module, "OPENAI_AVAILABLE", True)
    monkeypatch.setattr(provider_module, "OpenAI", DummyOpenAI, raising=False)

    config = ProviderConfig(
        model_name="test-model",
        api_key="test-key",
        stream=True,
        use_response_format=False,
    )
    provider = provider_module.OpenAICompatibleProvider(config)

    plan = provider.call_planner(task, _sample_registry())

    assert plan["task_id"] == task.task_id
