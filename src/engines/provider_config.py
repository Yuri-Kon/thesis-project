from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict

DEFAULT_PROVIDER_CONFIG_PATH = (
    Path(__file__).resolve().parents[2] / "configs" / "model_providers.json"
)


@dataclass
class ProviderConfig:
    provider_type: str
    description: str = ""
    base_url: str = ""
    api_key_env: str = ""
    timeout: float = 60.0
    max_retries: int = 3
    extra: Dict[str, Any] = field(default_factory=dict)

    def get_api_key(self) -> str:
        """Fetch API key from the configured environment variable."""
        if not self.api_key_env:
            return ""
        return os.getenv(self.api_key_env, "")


def _default_provider_configs() -> Dict[str, ProviderConfig]:
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
        )
    }


def load_provider_config(
    path: Path | None = None,
) -> Dict[str, ProviderConfig]:
    """Load provider config from JSON; fallback to defaults if missing."""
    config_path = path or DEFAULT_PROVIDER_CONFIG_PATH
    if not config_path.exists():
        return _default_provider_configs()

    data = json.loads(config_path.read_text(encoding="utf-8"))
    providers = data.get("providers", {})
    if not isinstance(providers, dict):
        raise ValueError("Provider config 'providers' must be a dict")

    configs: Dict[str, ProviderConfig] = {}
    for name, payload in providers.items():
        if not isinstance(payload, dict):
            raise ValueError(f"Provider config for '{name}' must be a dict")

        extra = payload.get("extra", {})
        if extra is None:
            extra = {}
        if not isinstance(extra, dict):
            raise ValueError(f"Provider config extra for '{name}' must be a dict")

        timeout = payload.get("timeout", 60.0)
        if timeout is None:
            timeout = 60.0

        max_retries = payload.get("max_retries", 3)
        if max_retries is None:
            max_retries = 3

        configs[name] = ProviderConfig(
            provider_type=payload.get("provider_type", name),
            description=payload.get("description", ""),
            base_url=payload.get("base_url", ""),
            api_key_env=payload.get("api_key_env", ""),
            timeout=float(timeout),
            max_retries=int(max_retries),
            extra=extra,
        )

    return configs


def get_provider_config(provider: str) -> ProviderConfig:
    """Get config for a single provider by name."""
    configs = load_provider_config()
    try:
        return configs[provider]
    except KeyError as exc:
        raise KeyError(f"Provider config not found: {provider}") from exc
