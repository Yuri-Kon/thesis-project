from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from pydantic import BaseModel, Field

from src.llm.base_llm_provider import BaseProvider, ProviderConfig
from src.llm.baseline_provider import BaselineProvider


ProviderFactory = Callable[[ProviderConfig, Optional[str]], BaseProvider]


class ProviderSettings(BaseModel):
    """Provider configuration loaded from a shared catalog."""

    provider_type: str = "openai_compatible"
    description: Optional[str] = None
    model_name: str
    api_key: Optional[str] = None
    api_key_env: Optional[str] = None
    endpoint: Optional[str] = None
    timeout: int = 30
    max_tokens: int = 2000
    temperature: float = 0.7
    top_p: float = 1.0
    stream: bool = False
    extra_body: Optional[Dict[str, Any]] = None
    use_response_format: bool = True


class ProviderCatalog(BaseModel):
    """Provider catalog loaded from JSON."""

    providers: Dict[str, ProviderSettings] = Field(default_factory=dict)


_PROVIDER_FACTORIES: Dict[str, ProviderFactory] = {}
_REGISTERED = False


def load_provider_catalog(path: Path) -> ProviderCatalog:
    """Load provider settings from a JSON file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return ProviderCatalog.model_validate(data)


def resolve_api_key(
    settings: ProviderSettings, *, api_key_override: Optional[str] = None
) -> Optional[str]:
    """Resolve API key from override, inline value, or environment variable."""
    if api_key_override:
        return api_key_override
    if settings.api_key:
        return settings.api_key
    if settings.api_key_env:
        return os.getenv(settings.api_key_env)
    return None


def register_provider(provider_type: str, factory: ProviderFactory) -> None:
    """Register a provider factory for extension."""
    _PROVIDER_FACTORIES[provider_type] = factory


def _register_builtins() -> None:
    register_provider("baseline", _create_baseline_provider)
    register_provider("openai_compatible", _create_openai_provider)


def _ensure_registry() -> None:
    global _REGISTERED
    if _REGISTERED:
        return
    _register_builtins()
    _REGISTERED = True


def _create_baseline_provider(
    config: ProviderConfig, endpoint: Optional[str]
) -> BaseProvider:
    return BaselineProvider(config)


def _create_openai_provider(
    config: ProviderConfig, endpoint: Optional[str]
) -> BaseProvider:
    from src.llm.openai_compatible_provider import OpenAICompatibleProvider

    return OpenAICompatibleProvider(config, endpoint=endpoint)


def create_provider(
    settings: ProviderSettings, *, api_key_override: Optional[str] = None
) -> BaseProvider:
    """Create a provider instance from settings."""
    _ensure_registry()
    api_key = resolve_api_key(settings, api_key_override=api_key_override)
    config = ProviderConfig(
        model_name=settings.model_name,
        api_key=api_key,
        timeout=settings.timeout,
        max_tokens=settings.max_tokens,
        temperature=settings.temperature,
        top_p=settings.top_p,
        stream=settings.stream,
        extra_body=settings.extra_body,
        use_response_format=settings.use_response_format,
    )
    factory = _PROVIDER_FACTORIES.get(settings.provider_type)
    if factory is None:
        raise ValueError(f"Unknown provider type: {settings.provider_type}")
    return factory(config, settings.endpoint)
