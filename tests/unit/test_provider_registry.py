import json
from pathlib import Path

from src.llm.anthropic_messages_provider import AnthropicMessagesProvider
from src.llm.baseline_provider import BaselineProvider
from src.llm.provider_registry import (
    ProviderSettings,
    create_provider,
    load_provider_catalog,
    resolve_api_key,
)


def test_load_provider_catalog(tmp_path):
    data = {
        "providers": {
            "baseline": {
                "provider_type": "baseline",
                "model_name": "baseline"
            }
        }
    }
    path = tmp_path / "providers.json"
    path.write_text(json.dumps(data))

    catalog = load_provider_catalog(path)

    assert "baseline" in catalog.providers
    settings = catalog.providers["baseline"]
    assert settings.provider_type == "baseline"
    assert settings.model_name == "baseline"


def test_resolve_api_key_from_env(monkeypatch):
    settings = ProviderSettings(
        provider_type="openai_compatible",
        model_name="test-model",
        api_key_env="TEST_API_KEY",
    )
    monkeypatch.setenv("TEST_API_KEY", "secret")

    assert resolve_api_key(settings) == "secret"


def test_create_provider_baseline():
    settings = ProviderSettings(provider_type="baseline", model_name="baseline")
    provider = create_provider(settings)

    assert isinstance(provider, BaselineProvider)


def test_create_provider_anthropic_messages():
    settings = ProviderSettings(
        provider_type="anthropic_messages",
        model_name="glm-5",
        api_key="secret",
        endpoint="https://open.bigmodel.cn/api/anthropic",
        anthropic_version="2023-06-01",
    )

    provider = create_provider(settings)

    assert isinstance(provider, AnthropicMessagesProvider)


def test_load_provider_catalog_keeps_qwen_entry():
    catalog = load_provider_catalog(
        Path(__file__).resolve().parents[2] / "configs" / "llm_providers.json"
    )

    assert "qwen-plus" in catalog.providers
    assert catalog.providers["qwen-plus"].api_key_env == "DASHSCOPE_API_KEY"
