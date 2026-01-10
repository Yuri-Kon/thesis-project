import json

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
