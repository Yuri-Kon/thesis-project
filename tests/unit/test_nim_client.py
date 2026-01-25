from __future__ import annotations

from unittest.mock import Mock

import httpx
import pytest

from src.engines.nim_client import NvidiaNIMClient
from src.workflow.errors import FailureType, StepRunError


def test_call_sync_success_builds_request() -> None:
    mock_response = Mock()
    mock_response.raise_for_status = Mock()
    mock_response.json.return_value = {"pdb": "ATOM", "plddt": 42.0}

    mock_client = Mock()
    mock_client.post.return_value = mock_response

    client = NvidiaNIMClient(
        base_url="https://health.api.nvidia.com/v1/biology/nvidia/esmfold",
        api_key="test-token",
        client=mock_client,
    )

    payload = {"sequence": "ACDEFG"}
    data = client.call_sync(payload)

    assert data["pdb"] == "ATOM"
    mock_client.post.assert_called_once()
    _, kwargs = mock_client.post.call_args
    assert kwargs["json"] == payload
    assert kwargs["headers"]["Authorization"] == "Bearer test-token"


def test_call_sync_missing_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NIM_API_KEY", raising=False)
    client = NvidiaNIMClient(
        base_url="https://health.api.nvidia.com/v1/biology/nvidia/esmfold",
        api_key=None,
        client=Mock(),
    )

    with pytest.raises(StepRunError) as exc_info:
        client.call_sync({"sequence": "ACDEFG"})

    assert exc_info.value.failure_type == FailureType.NON_RETRYABLE
    assert exc_info.value.code == "NIM_API_KEY_MISSING"


def test_call_sync_http_5xx() -> None:
    mock_response = Mock()
    mock_response.status_code = 500
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Server error",
        request=Mock(),
        response=mock_response,
    )

    mock_client = Mock()
    mock_client.post.return_value = mock_response

    client = NvidiaNIMClient(
        base_url="https://health.api.nvidia.com/v1/biology/nvidia/esmfold",
        api_key="token",
        client=mock_client,
    )

    with pytest.raises(StepRunError) as exc_info:
        client.call_sync({"sequence": "ACDEFG"})

    assert exc_info.value.failure_type == FailureType.RETRYABLE
    assert exc_info.value.code == "NIM_HTTP_5XX"


def test_call_sync_http_4xx() -> None:
    mock_response = Mock()
    mock_response.status_code = 400
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Client error",
        request=Mock(),
        response=mock_response,
    )

    mock_client = Mock()
    mock_client.post.return_value = mock_response

    client = NvidiaNIMClient(
        base_url="https://health.api.nvidia.com/v1/biology/nvidia/esmfold",
        api_key="token",
        client=mock_client,
    )

    with pytest.raises(StepRunError) as exc_info:
        client.call_sync({"sequence": "ACDEFG"})

    assert exc_info.value.failure_type == FailureType.NON_RETRYABLE
    assert exc_info.value.code == "NIM_HTTP_4XX"


def test_call_sync_timeout() -> None:
    mock_client = Mock()
    mock_client.post.side_effect = httpx.TimeoutException("timeout")

    client = NvidiaNIMClient(
        base_url="https://health.api.nvidia.com/v1/biology/nvidia/esmfold",
        api_key="token",
        client=mock_client,
    )

    with pytest.raises(StepRunError) as exc_info:
        client.call_sync({"sequence": "ACDEFG"})

    assert exc_info.value.failure_type == FailureType.RETRYABLE
    assert exc_info.value.code == "NIM_TIMEOUT"


def test_call_sync_invalid_json() -> None:
    mock_response = Mock()
    mock_response.raise_for_status = Mock()
    mock_response.json.side_effect = ValueError("bad json")

    mock_client = Mock()
    mock_client.post.return_value = mock_response

    client = NvidiaNIMClient(
        base_url="https://health.api.nvidia.com/v1/biology/nvidia/esmfold",
        api_key="token",
        client=mock_client,
    )

    with pytest.raises(StepRunError) as exc_info:
        client.call_sync({"sequence": "ACDEFG"})

    assert exc_info.value.failure_type == FailureType.TOOL_ERROR
    assert exc_info.value.code == "NIM_INVALID_RESPONSE"


def test_call_sync_uses_provider_config_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_response = Mock()
    mock_response.raise_for_status = Mock()
    mock_response.json.return_value = {"pdb": "ATOM", "plddt": 42.0}

    mock_client = Mock()
    mock_client.post.return_value = mock_response

    monkeypatch.setenv("NIM_API_KEY", "test-token")
    client = NvidiaNIMClient(client=mock_client)

    payload = {"sequence": "ACDEFG"}
    client.call_sync(payload)

    mock_client.post.assert_called_once()
    args, kwargs = mock_client.post.call_args
    assert args[0] == "https://integrate.api.nvidia.com/v1/biology/nvidia/esmfold"
    assert kwargs["headers"]["Authorization"] == "Bearer test-token"
