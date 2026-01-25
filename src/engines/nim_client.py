"""
NVIDIA NIM client for synchronous model invocation.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

import httpx

from src.engines.provider_config import get_provider_config
from src.workflow.errors import FailureCode, FailureType, StepRunError

__all__ = ["NvidiaNIMClient"]


class NvidiaNIMClient:
    """Minimal NVIDIA NIM REST client (sync)."""

    def __init__(
        self,
        *,
        base_url: Optional[str] = None,
        model_id: str = "nvidia/esmfold",
        api_key: Optional[str] = None,
        timeout: Optional[float] = None,
        client: Optional[httpx.Client] = None,
    ) -> None:
        config = get_provider_config("nvidia_nim")
        self.model_id = model_id
        self.base_url = (base_url or config.base_url).rstrip("/")
        self.api_key = api_key or config.get_api_key()
        self.timeout = timeout or config.timeout
        self._client = client or httpx.Client(timeout=self.timeout)

    def __del__(self) -> None:
        if hasattr(self, "_client"):
            self._client.close()

    def call_sync(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke NIM model endpoint synchronously."""
        if not self.api_key:
            raise StepRunError(
                failure_type=FailureType.NON_RETRYABLE,
                message="NIM API key is missing",
                code=FailureCode.NIM_AUTH_FAILED.value,
            )

        invoke_url = _build_invoke_url(self.base_url, self.model_id)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        try:
            response = self._client.post(
                invoke_url,
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            try:
                data = response.json()
            except ValueError as exc:
                raise StepRunError(
                    failure_type=FailureType.TOOL_ERROR,
                    message="NIM response is not valid JSON",
                    code=FailureCode.NIM_INVALID_RESPONSE.value,
                ) from exc
            if not isinstance(data, dict):
                raise StepRunError(
                    failure_type=FailureType.TOOL_ERROR,
                    message="NIM response payload is not a JSON object",
                    code=FailureCode.NIM_INVALID_RESPONSE.value,
                )
            return data
        except StepRunError:
            raise
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            if status_code in {401, 403}:
                failure_code = FailureCode.NIM_AUTH_FAILED
                failure_type = FailureType.NON_RETRYABLE
            elif status_code == 429:
                failure_code = FailureCode.NIM_QUOTA_EXCEEDED
                failure_type = FailureType.RETRYABLE
            elif status_code == 404:
                failure_code = FailureCode.NIM_MODEL_NOT_FOUND
                failure_type = FailureType.NON_RETRYABLE
            elif status_code in {400, 422}:
                failure_code = FailureCode.NIM_INVALID_INPUT
                failure_type = FailureType.NON_RETRYABLE
            elif status_code >= 500:
                failure_code = FailureCode.NIM_MODEL_ERROR
                failure_type = FailureType.RETRYABLE
            else:
                failure_code = FailureCode.NIM_INVALID_INPUT
                failure_type = FailureType.NON_RETRYABLE
            raise StepRunError(
                failure_type=failure_type,
                message=f"NIM request failed: HTTP {status_code}",
                code=failure_code.value,
            ) from exc
        except httpx.TimeoutException as exc:
            raise StepRunError(
                failure_type=FailureType.RETRYABLE,
                message=f"NIM request timeout: {exc}",
                code=FailureCode.NIM_TIMEOUT.value,
            ) from exc
        except httpx.RequestError as exc:
            raise StepRunError(
                failure_type=FailureType.RETRYABLE,
                message=f"NIM request network error: {exc}",
                code=FailureCode.NIM_NETWORK_ERROR.value,
            ) from exc
        except Exception as exc:
            raise StepRunError(
                failure_type=FailureType.TOOL_ERROR,
                message=f"Unexpected NIM error: {exc}",
                code=FailureCode.NIM_UNEXPECTED_ERROR.value,
            ) from exc


def _build_invoke_url(base_url: str, model_id: str) -> str:
    base_url = base_url.rstrip("/")
    if model_id and base_url.endswith(model_id):
        return base_url
    if "/biology" in base_url:
        if base_url.endswith("/biology"):
            return f"{base_url}/{model_id}"
        return base_url
    return f"{base_url}/biology/{model_id}"
