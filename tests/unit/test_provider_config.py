import json

import pytest

from src.engines import provider_config
from src.engines.provider_config import ProviderConfig, load_provider_config


def test_load_provider_config_from_file(tmp_path):
    data = {
        "providers": {
            "custom": {
                "provider_type": "custom",
                "description": "Custom provider",
                "base_url": "https://example.com/api",
                "api_key_env": "CUSTOM_API_KEY",
                "timeout": 12,
                "max_retries": 5,
                "extra": {"region": "us-west"},
            }
        }
    }
    path = tmp_path / "providers.json"
    path.write_text(json.dumps(data))

    configs = load_provider_config(path)

    config = configs["custom"]
    assert config.provider_type == "custom"
    assert config.description == "Custom provider"
    assert config.base_url == "https://example.com/api"
    assert config.api_key_env == "CUSTOM_API_KEY"
    assert config.timeout == 12.0
    assert config.max_retries == 5
    assert config.extra["region"] == "us-west"


def test_load_provider_config_fallback_default(tmp_path):
    missing_path = tmp_path / "missing.json"
    configs = load_provider_config(missing_path)

    assert "nvidia_nim" in configs
    config = configs["nvidia_nim"]
    assert config.base_url == "https://health.api.nvidia.com/v1/biology"
    assert config.api_key_env == "NIM_API_KEY"
    assert "supported_models" in config.extra


def test_provider_config_get_api_key(monkeypatch):
    config = ProviderConfig(
        provider_type="nvidia_nim",
        api_key_env="TEST_API_KEY",
    )
    monkeypatch.setenv("TEST_API_KEY", "secret")

    assert config.get_api_key() == "secret"


def test_get_provider_config_uses_default_path(tmp_path, monkeypatch):
    data = {
        "providers": {
            "example": {
                "provider_type": "example",
                "base_url": "https://example.com",
            }
        }
    }
    path = tmp_path / "providers.json"
    path.write_text(json.dumps(data))
    monkeypatch.setattr(provider_config, "DEFAULT_PROVIDER_CONFIG_PATH", path)

    config = provider_config.get_provider_config("example")

    assert config.provider_type == "example"
    assert config.base_url == "https://example.com"


def test_get_provider_config_missing_provider(tmp_path, monkeypatch):
    data = {"providers": {}}
    path = tmp_path / "providers.json"
    path.write_text(json.dumps(data))
    monkeypatch.setattr(provider_config, "DEFAULT_PROVIDER_CONFIG_PATH", path)

    with pytest.raises(KeyError):
        provider_config.get_provider_config("missing")


def test_default_model_providers_contains_plm_rest():
    configs = load_provider_config(provider_config.DEFAULT_PROVIDER_CONFIG_PATH)

    assert "plm_rest" in configs
    plm = configs["plm_rest"]
    assert plm.provider_type == "plm_rest"
    assert plm.base_url == "http://localhost:8100"
