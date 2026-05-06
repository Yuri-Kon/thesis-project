from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import cast

from pydantic import BaseModel, Field

from src.llm.base_llm_provider import BaseProvider, JsonObject, ProviderConfig
from src.llm.baseline_provider import BaselineProvider


ProviderFactory = Callable[[ProviderConfig, str | None], BaseProvider]

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | JsonObject | JsonArray
type JsonArray = list[JsonValue]


class ProviderSettings(BaseModel):
    """Provider configuration loaded from a shared catalog."""

    provider_type: str = "openai_compatible"
    description: str | None = None
    model_name: str
    api_key: str | None = None
    api_key_env: str | None = None
    endpoint: str | None = None
    endpoint_env: str | None = None
    timeout: int = 30
    max_tokens: int | None = 2000
    temperature: float = 0.7
    top_p: float = 1.0
    stream: bool = False
    api_style: str | None = None
    structured_output_mode: str | None = None
    tool_strategy: str | None = None
    supports_patch: bool = True
    supports_replan: bool = True
    supports_reasoning: bool = False
    headers: dict[str, str] | None = None
    organization: str | None = None
    anthropic_version: str | None = None
    extra_body: JsonObject | None = None
    use_response_format: bool = True


class ProviderCatalog(BaseModel):
    """Provider catalog loaded from JSON."""

    providers: dict[str, ProviderSettings] = Field(default_factory=dict)


_provider_factories: dict[str, ProviderFactory] = {}
_registered = False


def load_provider_catalog(path: Path) -> ProviderCatalog:
    """Load provider settings from a JSON file."""
    data = cast(object, json.loads(path.read_text(encoding="utf-8")))
    return ProviderCatalog.model_validate(data)


def resolve_api_key(
    settings: ProviderSettings, *, api_key_override: str | None = None
) -> str | None:
    """Resolve API key from override, inline value, or environment variable."""
    if api_key_override:
        return api_key_override
    if settings.api_key:
        return settings.api_key
    if settings.api_key_env:
        return os.getenv(settings.api_key_env)
    return None


def resolve_endpoint(settings: ProviderSettings) -> str | None:
    """Resolve endpoint from inline value or environment variable."""
    if settings.endpoint:
        return settings.endpoint
    if settings.endpoint_env:
        return os.getenv(settings.endpoint_env)
    return None


def register_provider(provider_type: str, factory: ProviderFactory) -> None:
    """Register a provider factory for extension."""
    _provider_factories[provider_type] = factory


def _register_builtins() -> None:
    register_provider("baseline", _create_baseline_provider)
    register_provider("openai_compatible", _create_openai_provider)
    register_provider("anthropic_messages", _create_anthropic_provider)
    register_provider("zai_chat", _create_zai_provider)


def _ensure_registry() -> None:
    global _registered
    if _registered:
        return
    _register_builtins()
    _registered = True


def _create_baseline_provider(
    config: ProviderConfig, endpoint: str | None,
) -> BaseProvider:
    _ = endpoint
    return BaselineProvider(config)


def _create_openai_provider(
    config: ProviderConfig, endpoint: str | None,
) -> BaseProvider:
    from src.llm.openai_compatible_provider import OpenAICompatibleProvider

    return OpenAICompatibleProvider(config, endpoint=endpoint)


def _create_anthropic_provider(
    config: ProviderConfig, endpoint: str | None,
) -> BaseProvider:
    from src.llm.anthropic_messages_provider import AnthropicMessagesProvider

    return AnthropicMessagesProvider(config, endpoint=endpoint)


def _create_zai_provider(
    config: ProviderConfig, endpoint: str | None,
) -> BaseProvider:
    from src.llm.zai_chat_provider import ZaiChatProvider

    return ZaiChatProvider(config, endpoint=endpoint)


def create_provider(
    settings: ProviderSettings, *, api_key_override: str | None = None,
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
        api_style=settings.api_style,
        structured_output_mode=settings.structured_output_mode,
        tool_strategy=settings.tool_strategy,
        supports_patch=settings.supports_patch,
        supports_replan=settings.supports_replan,
        supports_reasoning=settings.supports_reasoning,
        headers=settings.headers,
        organization=settings.organization,
        anthropic_version=settings.anthropic_version,
        extra_body=settings.extra_body,
        use_response_format=settings.use_response_format,
    )
    endpoint = resolve_endpoint(settings)
    factory = _provider_factories.get(settings.provider_type)
    if factory is None:
        raise ValueError(f"Unknown provider type: {settings.provider_type}")
    return factory(config, endpoint)
