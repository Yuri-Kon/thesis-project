from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping, Sequence
from typing import cast

from src.llm.provider_payload_parser import ProviderPayloadValidationError


def extract_message_content_with_summary(
    response: object,
) -> tuple[str, dict[str, object]]:
    """提取非流式 chat 响应正文并返回安全摘要。

    Args:
        response: SDK 返回的 chat completion 对象。

    Returns:
        `(content, summary)`；summary 不包含完整 prompt 或凭据。
    """

    choices = _sequence_from_attr(response, "choices")
    summary: dict[str, object] = {
        "response_id": _safe_scalar(getattr(response, "id", None)),
        "response_object": _safe_scalar(getattr(response, "object", None)),
        "created": _safe_scalar(getattr(response, "created", None)),
        "choices_count": len(choices),
        "finish_reasons": _finish_reasons(choices),
        "usage": _usage_summary(getattr(response, "usage", None)),
    }
    if not choices:
        summary["content_length"] = 0
        summary["message_present"] = False
        return "", summary

    first = choices[0]
    message = getattr(first, "message", None)
    summary["message_present"] = message is not None
    content = _content_to_text(getattr(message, "content", None))
    summary["content_length"] = len(content)
    summary["message_has_tool_calls"] = _has_items(getattr(message, "tool_calls", None))
    summary["message_has_function_call"] = getattr(message, "function_call", None) is not None
    summary["message_has_refusal"] = bool(_content_to_text(getattr(message, "refusal", None)))
    summary["message_has_reasoning"] = bool(
        _content_to_text(getattr(message, "reasoning_content", None))
        or _content_to_text(getattr(message, "reasoning", None))
    )
    return content.strip(), summary


def collect_stream_content_with_summary(
    response: Iterable[object],
) -> tuple[str, dict[str, object]]:
    """收集流式 chat 响应正文并返回安全摘要。

    Args:
        response: SDK 返回的 stream iterator。

    Returns:
        `(content, summary)`；summary 仅包含 chunk/finish 统计。
    """

    parts: list[str] = []
    chunk_count = 0
    chunks_without_choices = 0
    content_delta_count = 0
    reasoning_delta_count = 0
    finish_reasons: list[str] = []
    for chunk in response:
        chunk_count += 1
        choices = _sequence_from_attr(chunk, "choices")
        if not choices:
            chunks_without_choices += 1
            continue
        for choice in choices:
            reason = _attr(choice, "finish_reason")
            if isinstance(reason, str) and reason:
                finish_reasons.append(reason)
            delta = _attr(choice, "delta")
            if delta is None:
                continue
            reasoning = _content_to_text(_attr(delta, "reasoning_content"))
            if reasoning:
                reasoning_delta_count += 1
            content = _content_to_text(_attr(delta, "content"))
            if content:
                content_delta_count += 1
                parts.append(content)

    content = "".join(parts).strip()
    summary: dict[str, object] = {
        "stream_chunk_count": chunk_count,
        "stream_chunks_without_choices": chunks_without_choices,
        "stream_content_delta_count": content_delta_count,
        "stream_reasoning_delta_count": reasoning_delta_count,
        "finish_reasons": finish_reasons,
        "content_length": len(content),
    }
    return content, summary


def build_empty_response_error(
    *,
    candidate_kind: str,
    provider_name: str,
    model: str,
    endpoint: str,
    elapsed_seconds: float,
    request_kwargs: Mapping[str, object],
    response_summary: Mapping[str, object],
    prompt_context: Mapping[str, str],
) -> ProviderPayloadValidationError:
    """构造带诊断摘要的空响应错误。

    Args:
        candidate_kind: `plan`、`patch` 或 `replan`。
        provider_name: provider 实现名。
        model: 模型名。
        endpoint: endpoint 标识。
        elapsed_seconds: API 调用耗时。
        request_kwargs: 已发送请求参数；只抽取非敏感字段。
        response_summary: SDK 响应安全摘要。
        prompt_context: system/user prompt 文本；只记录长度与哈希。

    Returns:
        可被 Planner 统一记录的 ProviderPayloadValidationError。
    """

    diagnostic_summary = {
        "provider": provider_name,
        "model": model,
        "endpoint": endpoint,
        "elapsed_seconds": round(elapsed_seconds, 6),
        "candidate_kind": candidate_kind,
        "request": _request_summary(request_kwargs, prompt_context),
        "response": dict(response_summary),
        "possible_causes": _infer_empty_response_causes(
            request_kwargs=request_kwargs,
            response_summary=response_summary,
        ),
    }
    issue = {
        "code": "EMPTY_PROVIDER_RESPONSE",
        "path": "$.choices[0].message.content",
        "message": "LLM provider returned no usable content",
        "observed": diagnostic_summary,
        "repair_hint": (
            "retry the provider call; if repeated, inspect finish_reason, "
            "response_format support, content filtering, max_tokens, and stream deltas"
        ),
    }
    return ProviderPayloadValidationError(
        candidate_kind=candidate_kind,
        failure_type="empty_response",
        issues=[issue],
    )


def build_provider_invocation_error(
    *,
    candidate_kind: str,
    provider_name: str,
    model: str,
    endpoint: str,
    elapsed_seconds: float,
    request_kwargs: Mapping[str, object],
    prompt_context: Mapping[str, str],
    error: Exception,
) -> ProviderPayloadValidationError:
    """构造 provider 调用阶段失败的安全诊断错误。

    Args:
        candidate_kind: `plan`、`patch` 或 `replan`。
        provider_name: provider 实现名。
        model: 模型名。
        endpoint: endpoint 标识。
        elapsed_seconds: API 调用耗时。
        request_kwargs: 已构造的请求参数；只抽取非敏感字段。
        prompt_context: system/user prompt 文本；只记录长度与哈希。
        error: SDK 或网络层抛出的异常。

    Returns:
        可被 Planner 统一记录的 ProviderPayloadValidationError。
    """

    error_type = type(error).__name__
    error_message = str(error)
    diagnostic_summary = {
        "provider": provider_name,
        "model": model,
        "endpoint": endpoint,
        "elapsed_seconds": round(elapsed_seconds, 6),
        "candidate_kind": candidate_kind,
        "request": _request_summary(request_kwargs, prompt_context),
        "exception": {
            "type": error_type,
            "message": error_message,
        },
        "possible_causes": _infer_invocation_failure_causes(
            error_type=error_type,
            error_message=error_message,
        ),
    }
    issue = {
        "code": "PROVIDER_INVOCATION_FAILED",
        "path": "$.api_call",
        "message": "LLM provider call failed before a usable response was returned",
        "observed": diagnostic_summary,
        "repair_hint": (
            "check provider availability, timeout, endpoint configuration, "
            "rate limits, and API key validity before rerunning"
        ),
    }
    return ProviderPayloadValidationError(
        candidate_kind=candidate_kind,
        failure_type="provider_invocation_failed",
        issues=[issue],
    )


def _request_summary(
    request_kwargs: Mapping[str, object],
    prompt_context: Mapping[str, str],
) -> dict[str, object]:
    response_format = request_kwargs.get("response_format")
    response_format_type = None
    response_format_map = _as_mapping(response_format)
    if response_format_map is not None:
        raw_type = response_format_map.get("type")
        if isinstance(raw_type, str):
            response_format_type = raw_type
    return {
        "stream": bool(request_kwargs.get("stream", False)),
        "max_tokens": _safe_scalar(request_kwargs.get("max_tokens")),
        "temperature": _safe_scalar(request_kwargs.get("temperature")),
        "top_p": _safe_scalar(request_kwargs.get("top_p")),
        "response_format_type": response_format_type,
        "has_extra_body": "extra_body" in request_kwargs,
        "has_thinking": "thinking" in request_kwargs,
        "prompt": _prompt_summary(prompt_context),
    }


def _prompt_summary(prompt_context: Mapping[str, str]) -> dict[str, object]:
    summary: dict[str, object] = {}
    total_chars = 0
    for key, value in prompt_context.items():
        total_chars += len(value)
        summary[key] = {
            "chars": len(value),
            "sha256_12": hashlib.sha256(value.encode("utf-8")).hexdigest()[:12],
        }
    summary["total_chars"] = total_chars
    return summary


def _infer_empty_response_causes(
    *,
    request_kwargs: Mapping[str, object],
    response_summary: Mapping[str, object],
) -> list[str]:
    causes: list[str] = []
    choices_count = _safe_int(response_summary.get("choices_count"))
    if choices_count == 0:
        causes.append("response_has_no_choices")
    if bool(response_summary.get("message_has_refusal")):
        causes.append("provider_refusal_without_content")
    if bool(response_summary.get("message_has_tool_calls")):
        causes.append("provider_returned_tool_calls_instead_of_json_content")
    if bool(response_summary.get("message_has_reasoning")):
        causes.append("reasoning_only_response_without_final_content")
    if _safe_int(response_summary.get("stream_content_delta_count")) == 0 and bool(
        request_kwargs.get("stream", False)
    ):
        causes.append("stream_finished_without_content_delta")
    finish_reasons = response_summary.get("finish_reasons")
    if isinstance(finish_reasons, Sequence) and not isinstance(finish_reasons, str):
        finish_set = {item for item in finish_reasons if isinstance(item, str)}
        if "length" in finish_set:
            causes.append("generation_hit_max_tokens")
        if "content_filter" in finish_set:
            causes.append("content_filter_removed_output")
        if "tool_calls" in finish_set:
            causes.append("tool_call_finish_reason_without_content")
    response_format = request_kwargs.get("response_format")
    response_format_map = _as_mapping(response_format)
    if response_format_map is not None:
        raw_type = response_format_map.get("type")
        if raw_type in {"json_object", "json_schema"}:
            causes.append("structured_output_mode_may_be_unsupported_or_unsatisfied")
    if not causes:
        causes.append("provider_returned_blank_message_content")
    return causes


def _infer_invocation_failure_causes(
    *,
    error_type: str,
    error_message: str,
) -> list[str]:
    text = f"{error_type} {error_message}".lower()
    causes: list[str] = []
    if "timeout" in text or "timed out" in text:
        causes.append("provider_request_timeout")
    if "connection" in text or "connect" in text or "refused" in text:
        causes.append("provider_connection_failure")
    if "rate" in text or "429" in text or "quota" in text:
        causes.append("provider_rate_limit_or_quota")
    if "401" in text or "403" in text or "auth" in text or "api key" in text:
        causes.append("provider_auth_or_permission")
    if "400" in text or "invalid" in text or "bad request" in text:
        causes.append("provider_rejected_request_payload")
    if "500" in text or "502" in text or "503" in text or "504" in text:
        causes.append("provider_server_error")
    if not causes:
        causes.append("provider_api_call_failed")
    return causes


def _sequence_from_attr(obj: object, attr: str) -> list[object]:
    value = getattr(obj, attr, None)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    return []


def _finish_reasons(choices: Sequence[object]) -> list[str]:
    reasons: list[str] = []
    for choice in choices:
        reason = getattr(choice, "finish_reason", None)
        if isinstance(reason, str) and reason:
            reasons.append(reason)
    return reasons


def _content_to_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            else:
                item_map = _as_mapping(item)
                if item_map is None:
                    continue
                text = item_map.get("text")
                if isinstance(text, str):
                    parts.append(text)
                nested = item_map.get("content")
                if isinstance(nested, str):
                    parts.append(nested)
        return "".join(parts)
    return ""


def _usage_summary(value: object) -> dict[str, object]:
    if value is None:
        return {}
    value_map = _as_mapping(value)
    if value_map is not None:
        mapping_payload: dict[str, object] = {}
        for key, item in value_map.items():
            safe_item = _safe_scalar(item)
            if safe_item is not None:
                mapping_payload[str(key)] = safe_item
        return mapping_payload
    payload: dict[str, object] = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        item = _safe_scalar(getattr(value, key, None))
        if item is not None:
            payload[key] = item
    return payload


def _has_items(value: object) -> bool:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return len(value) > 0
    return value is not None


def _safe_scalar(value: object) -> object | None:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _safe_int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return 0


def _attr(obj: object, name: str) -> object | None:
    return getattr(obj, name, None)


def _as_mapping(value: object) -> dict[str, object] | None:
    if isinstance(value, Mapping):
        typed = cast(Mapping[object, object], value)
        payload: dict[str, object] = {}
        for key, item in typed.items():
            payload[str(key)] = item
        return payload
    return None
