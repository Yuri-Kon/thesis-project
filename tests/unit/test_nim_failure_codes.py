from __future__ import annotations

from src.workflow.errors import FailureCode


def test_nim_failure_codes_enum_values() -> None:
    """验证 NIM 失败码枚举值是否完整。"""
    assert FailureCode.NIM_AUTH_FAILED.value == "NIM_AUTH_FAILED"
    assert FailureCode.NIM_QUOTA_EXCEEDED.value == "NIM_QUOTA_EXCEEDED"
    assert FailureCode.NIM_MODEL_NOT_FOUND.value == "NIM_MODEL_NOT_FOUND"
    assert FailureCode.NIM_INVALID_INPUT.value == "NIM_INVALID_INPUT"
    assert FailureCode.NIM_MODEL_ERROR.value == "NIM_MODEL_ERROR"
