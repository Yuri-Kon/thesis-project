from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeGuard, cast

DEFAULT_PROVIDER_CONFIG_PATH = (
    Path(__file__).resolve().parents[2] / "configs" / "model_providers.json"
)

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | JsonObject | JsonArray
type JsonObject = dict[str, JsonValue]
type JsonArray = list[JsonValue]


@dataclass
class ProviderConfig:
    provider_type: str
    description: str = ""
    base_url: str = ""
    api_key_env: str = ""
    timeout: float = 60.0
    max_retries: int = 3
    extra: JsonObject = field(default_factory=dict)

    def get_api_key(self) -> str:
        """Fetch API key from the configured environment variable."""
        if not self.api_key_env:
            return ""
        return os.getenv(self.api_key_env, "")


def _default_provider_configs() -> dict[str, ProviderConfig]:
    return {
        "nvidia_nim": ProviderConfig(
            provider_type="nvidia_nim",
            description="NVIDIA NIM Biology Models",
            base_url="https://health.api.nvidia.com/v1/biology",
            api_key_env="NIM_API_KEY",
            timeout=60.0,
            max_retries=3,
            extra={
                "supported_models": [
                    "nvidia/esmfold",
                    "nvidia/esm2nv",
                ]
            },
        ),
        "openfold3_rest": ProviderConfig(
            provider_type="openfold3_rest",
            description="OpenFold3 remote REST service provider",
            base_url="http://localhost:8200",
            api_key_env="OPENFOLD3_REST_API_TOKEN",
            timeout=120.0,
            max_retries=3,
            extra={
                "endpoints": {
                    "predict": "/predict",
                    "job": "/job/{id}",
                    "results": "/results/{id}",
                }
            },
        ),
        "plm_rest": ProviderConfig(
            provider_type="plm_rest",
            description="PLM remote REST service provider",
            base_url="http://localhost:8100",
            api_key_env="PLM_REST_API_TOKEN",
            timeout=60.0,
            max_retries=3,
            extra={
                "endpoints": {
                    "predict": "/predict",
                    "job": "/job/{id}",
                    "results": "/results/{id}",
                }
            },
        ),
        "foldseek_web": ProviderConfig(
            provider_type="foldseek_web",
            description="Foldseek public Web API provider",
            base_url="https://search.foldseek.com/api",
            timeout=60.0,
            max_retries=3,
            extra={
                "endpoints": {
                    "databases": "/databases",
                    "ticket": "/ticket",
                    "ticket_status": "/ticket/{id}",
                    "result": "/result/{id}/{entry}",
                    "download": "/result/download/{id}",
                },
                "default_databases": ["afdb-swissprot"],
            },
        ),
    }


def load_provider_config(
    path: Path | None = None,
) -> dict[str, ProviderConfig]:
    """Load provider config from JSON; fallback to defaults if missing."""
    config_path = path or DEFAULT_PROVIDER_CONFIG_PATH
    if not config_path.exists():
        return _default_provider_configs()

    data = _load_json_object(config_path)
    providers = data.get("providers", {})
    if not isinstance(providers, dict):
        raise ValueError("Provider config 'providers' must be a dict")

    configs: dict[str, ProviderConfig] = {}
    for name, raw_payload in providers.items():
        payload = _as_json_object(raw_payload)
        if not isinstance(payload, dict):
            raise ValueError(f"Provider config for '{name}' must be a dict")

        extra = payload.get("extra", {})
        if extra is None:
            extra = {}
        extra_payload = _as_json_object(extra)
        if extra_payload is None:
            raise ValueError(f"Provider config extra for '{name}' must be a dict")

        configs[name] = ProviderConfig(
            provider_type=_string_field(payload, "provider_type", name),
            description=_string_field(payload, "description", ""),
            base_url=_string_field(payload, "base_url", ""),
            api_key_env=_string_field(payload, "api_key_env", ""),
            timeout=_float_field(payload, "timeout", 60.0),
            max_retries=_int_field(payload, "max_retries", 3),
            extra=extra_payload,
        )

    return configs


def get_provider_config(provider: str) -> ProviderConfig:
    """Get config for a single provider by name."""
    configs = load_provider_config()
    try:
        return configs[provider]
    except KeyError as exc:
        raise KeyError(f"Provider config not found: {provider}") from exc


def _load_json_object(path: Path) -> JsonObject:
    payload = cast(object, json.loads(path.read_text(encoding="utf-8")))
    parsed = _as_json_object(payload)
    if parsed is None:
        raise ValueError("Provider config root must be a dict")
    return parsed


def _as_json_object(value: object) -> JsonObject | None:
    if not isinstance(value, dict):
        return None
    result: JsonObject = {}
    for key, item in cast(Mapping[object, object], value).items():
        if isinstance(key, str) and _is_json_value(item):
            result[key] = item
    return result


def _is_json_value(value: object) -> TypeGuard[JsonValue]:
    if value is None or isinstance(value, str | int | float | bool):
        return True
    if isinstance(value, list):
        return all(_is_json_value(item) for item in cast(list[object], value))
    if isinstance(value, dict):
        return all(
            isinstance(key, str) and _is_json_value(item)
            for key, item in cast(Mapping[object, object], value).items()
        )
    return False


def _string_field(payload: JsonObject, key: str, default: str) -> str:
    value = payload.get(key)
    if value is None:
        return default
    if isinstance(value, str):
        return value
    raise ValueError(f"Provider config '{key}' must be a string")


def _float_field(payload: JsonObject, key: str, default: float) -> float:
    value = payload.get(key)
    if value is None:
        return default
    if isinstance(value, int | float):
        return float(value)
    raise ValueError(f"Provider config '{key}' must be a number")


def _int_field(payload: JsonObject, key: str, default: int) -> int:
    value = payload.get(key)
    if value is None:
        return default
    if isinstance(value, int):
        return value
    raise ValueError(f"Provider config '{key}' must be an integer")
