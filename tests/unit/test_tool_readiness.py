from __future__ import annotations

from typing import Any

import pytest

import src.infra.tool_readiness as tool_readiness
from src.adapters.base_tool_adapter import BaseToolAdapter


class FakeReadinessAdapter(BaseToolAdapter):
    """测试用 adapter。"""

    tool_id = "fake_tool"
    adapter_id = "fake_tool"

    def __init__(self, health: dict[str, Any] | None = None) -> None:
        self._health = health or {"status": "ready", "reason": "fake ready"}

    def resolve_inputs(self, step, context) -> dict[str, Any]:
        return {}

    def run_local(self, inputs: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        return {}, {}

    def healthcheck(self) -> dict[str, Any]:
        return dict(self._health)


def test_readiness_classifies_adapter_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """adapter 未注册应返回 unavailable 和结构化恢复建议。"""

    def raise_missing(tool_id: str):
        raise KeyError(tool_id)

    monkeypatch.setattr(tool_readiness, "get_adapter", raise_missing)

    payload = tool_readiness.evaluate_tool_readiness(
        "missing_tool",
        tool_entry={"id": "missing_tool", "capabilities": ["quality_qc"]},
    )

    assert payload["status"] == "unavailable"
    assert payload["error_category"] == "adapter_missing"
    assert payload["suggested_recovery"]


def test_readiness_classifies_credential_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """NIM 依赖缺少凭证时应归类为 credential_missing。"""

    monkeypatch.delenv("NIM_API_KEY", raising=False)
    monkeypatch.setattr(
        tool_readiness,
        "get_adapter",
        lambda tool_id: FakeReadinessAdapter(),
    )

    payload = tool_readiness.evaluate_tool_readiness(
        "protein_mpnn",
        tool_entry={
            "id": "protein_mpnn",
            "capabilities": ["sequence_design"],
            "execution": {"provider": "nvidia_nim"},
            "constraints": {
                "resource_assumptions": ["network_available", "nim_api_key_configured"]
            },
        },
    )

    assert payload["status"] == "unavailable"
    assert payload["error_category"] == "credential_missing"
    assert "credential" in payload["suggested_recovery"].lower()


def test_readiness_classifies_remote_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    """远程服务未配置时应归类为 remote_unreachable。"""

    monkeypatch.delenv("PLM_REST_BASE_URL", raising=False)
    monkeypatch.setattr(
        tool_readiness,
        "get_adapter",
        lambda tool_id: FakeReadinessAdapter(),
    )

    payload = tool_readiness.evaluate_tool_readiness(
        "protgpt2",
        tool_entry={
            "id": "protgpt2",
            "capabilities": ["sequence_generation"],
            "execution": {"provider": "plm_rest"},
            "constraints": {
                "resource_assumptions": ["network_available", "plm_rest_service_available"]
            },
        },
    )

    assert payload["status"] == "unavailable"
    assert payload["error_category"] == "remote_unreachable"
    assert "remote" in payload["suggested_recovery"].lower()


def test_readiness_classifies_database_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """本地数据库未配置时应以 degraded 暴露 database_missing。"""

    for env_key in (
        "PROTEIN_SEQUENCE_DB_PATH",
        "PROTEIN_STRUCTURE_DB_PATH",
        "PROTEIN_DATABASE_PATH",
    ):
        monkeypatch.delenv(env_key, raising=False)
    monkeypatch.setattr(
        tool_readiness,
        "get_adapter",
        lambda tool_id: FakeReadinessAdapter(),
    )

    payload = tool_readiness.evaluate_tool_readiness(
        "mmseqs2",
        tool_entry={
            "id": "mmseqs2",
            "capabilities": ["sequence_similarity_search"],
            "constraints": {
                "resource_assumptions": [
                    "python_environment_ready",
                    "local_sequence_database_ready",
                ]
            },
        },
    )

    assert payload["status"] == "degraded"
    assert payload["error_category"] == "database_missing"
    assert "database" in payload["reason"]


def test_capability_readiness_matrix_exposes_structured_reasons(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """capability 级矩阵应包含 available/blocked/recovery 字段。"""

    monkeypatch.setattr(tool_readiness, "ensure_builtin_adapters", lambda: None)
    monkeypatch.setattr(
        tool_readiness,
        "load_tool_kg",
        lambda: {
            "capabilities": [
                {"capability_id": "sequence_similarity_search"},
            ],
            "tools": [
                {
                    "id": "mmseqs2",
                    "capabilities": ["sequence_similarity_search"],
                    "constraints": {
                        "resource_assumptions": ["local_sequence_database_ready"]
                    },
                    "priority": "P0",
                }
            ],
        },
    )
    monkeypatch.setattr(
        tool_readiness,
        "get_adapter",
        lambda tool_id: FakeReadinessAdapter(),
    )

    matrix = tool_readiness.build_capability_readiness_matrix()

    assert matrix[0]["capability_id"] == "sequence_similarity_search"
    assert matrix[0]["status"] == "degraded"
    assert matrix[0]["available_tools"][0]["tool_id"] == "mmseqs2"
    assert matrix[0]["degraded_reasons"]
    assert matrix[0]["suggested_recovery"]
