import json
from pathlib import Path

from src.llm.anthropic_messages_provider import AnthropicMessagesProvider
from src.llm.baseline_provider import BaselineProvider
from src.llm.zai_chat_provider import ZaiChatProvider
from src.llm.provider_registry import (
    ProviderSettings,
    create_provider,
    load_provider_catalog,
    resolve_api_key,
    resolve_endpoint,
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
        model_name="MiniMax-M2.7",
        api_key="secret",
        endpoint="https://api.minimaxi.com/anthropic",
        anthropic_version="2023-06-01",
    )

    provider = create_provider(settings)

    assert isinstance(provider, AnthropicMessagesProvider)


def test_create_provider_zai_chat():
    settings = ProviderSettings(
        provider_type="zai_chat",
        model_name="glm-5",
        api_key="secret",
    )

    provider = create_provider(settings)

    assert isinstance(provider, ZaiChatProvider)


def test_resolve_endpoint_from_env(monkeypatch):
    settings = ProviderSettings(
        provider_type="anthropic_messages",
        model_name="MiniMax-M2.7",
        endpoint_env="MINIMAX_BASE_URL",
    )
    monkeypatch.setenv("MINIMAX_BASE_URL", "https://api.minimaxi.com/anthropic")

    assert resolve_endpoint(settings) == "https://api.minimaxi.com/anthropic"


def test_load_provider_catalog_keeps_qwen_entry():
    catalog = load_provider_catalog(
        Path(__file__).resolve().parents[2] / "configs" / "llm_providers.json"
    )

    assert "qwen-flash" in catalog.providers
    assert catalog.providers["qwen-flash"].api_key_env == "DASHSCOPE_API_KEY"
    assert catalog.providers["qwen-flash"].model_name == "qwen3.6-flash"
    assert "qwen-plus" in catalog.providers
    assert catalog.providers["qwen-plus"].api_key_env == "DASHSCOPE_API_KEY"
    assert catalog.providers["qwen-plus"].model_name == "qwen3.6-plus"


def test_load_provider_catalog_keeps_minimax_entry():
    catalog = load_provider_catalog(
        Path(__file__).resolve().parents[2] / "configs" / "llm_providers.json"
    )

    assert "minimax-m2.7" in catalog.providers
    assert catalog.providers["minimax-m2.7"].provider_type == "anthropic_messages"
    assert catalog.providers["minimax-m2.7"].model_name == "MiniMax-M2.7"
    assert catalog.providers["minimax-m2.7"].api_key_env == "MINIMAX_API_KEY"
    assert catalog.providers["minimax-m2.7"].endpoint_env == "MINIMAX_BASE_URL"


def test_load_provider_catalog_keeps_glm_entries():
    catalog = load_provider_catalog(
        Path(__file__).resolve().parents[2] / "configs" / "llm_providers.json"
    )

    assert catalog.providers["glm-5"].provider_type == "zai_chat"
    assert catalog.providers["glm-5"].model_name == "glm-5"
    assert catalog.providers["glm-4.7"].provider_type == "zai_chat"
    assert catalog.providers["glm-4.7"].model_name == "glm-4.7"
