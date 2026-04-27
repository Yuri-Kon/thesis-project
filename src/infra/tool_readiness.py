from __future__ import annotations

from collections import defaultdict
import os
from typing import Any, Dict, List, Sequence

from src.adapters.builtins import ensure_builtin_adapters
from src.adapters.registry import get_adapter
from src.infra.active_tool_metadata import metadata_by_tool_id
from src.kg.kg_client import load_tool_kg
from src.models.contracts import CapabilityReadiness, ToolReadiness, now_iso

__all__ = [
    "P0_CAPABILITY_IDS",
    "build_capability_readiness_matrix",
    "build_tool_readiness_snapshot",
    "evaluate_tool_readiness",
]

P0_CAPABILITY_IDS = {
    "structure_prediction",
    "sequence_design",
    "sequence_generation",
    "quality_qc",
    "sequence_similarity_search",
    "objective_scoring",
}

DEFAULT_HEALTHCHECK_TIMEOUT_S = 2.0


def evaluate_tool_readiness(
    tool_id: str,
    *,
    tool_entry: dict[str, Any] | None = None,
    checked_at: str | None = None,
) -> Dict[str, Any]:
    """评估单个工具的可用性。"""
    checked_at = checked_at or now_iso()
    profile = metadata_by_tool_id().get(tool_id)
    capability_ids = _capability_ids(tool_entry, profile)
    cost_prior, risk_prior, latency_prior = _priors_for_tool(tool_entry, profile)

    try:
        adapter = get_adapter(tool_id)
    except KeyError:
        return _tool_payload(
            tool_id=tool_id,
            status="unavailable",
            reason="adapter not registered",
            error_category="adapter_missing",
            capability_ids=capability_ids,
            cost_prior=cost_prior,
            risk_prior=risk_prior,
            latency_prior=latency_prior,
            checked_at=checked_at,
            profile=profile,
            details={"healthcheck_timeout_s": DEFAULT_HEALTHCHECK_TIMEOUT_S},
        )

    try:
        health = adapter.healthcheck()
    except Exception as exc:  # pragma: no cover - 防御性分支
        normalized = adapter.normalize_error(exc)
        reason = str(normalized.get("message") or exc)
        return _tool_payload(
            tool_id=tool_id,
            status="degraded",
            reason=f"healthcheck failed: {reason}",
            error_category=_classify_error(reason, tool_entry),
            capability_ids=capability_ids,
            cost_prior=cost_prior,
            risk_prior=risk_prior,
            latency_prior=latency_prior,
            checked_at=checked_at,
            profile=profile,
            details={
                "normalized_error": normalized,
                "healthcheck_timeout_s": DEFAULT_HEALTHCHECK_TIMEOUT_S,
            },
        )

    status = str(health.get("status") or "ready")
    if status not in {"ready", "degraded", "unavailable"}:
        status = "degraded"
    reason = str(health.get("reason") or "")
    protocol_override = _protocol_readiness_override(tool_entry)
    if protocol_override is not None:
        override_status, override_reason, override_category = protocol_override
        status = _worse_status(status, override_status)
        if override_status != "ready":
            reason = _join_reasons(reason, override_reason)
        error_category = override_category
    else:
        error_category = _classify_error(reason, tool_entry) if status != "ready" else None

    try:
        capability_summary = adapter.describe_capabilities()
    except Exception as exc:  # pragma: no cover - 防御性分支
        capability_summary = {"describe_error": adapter.normalize_error(exc)}
    details = {
        **health,
        "capabilities": capability_summary,
        "cost_estimate": adapter.estimate_cost({}),
        "latency_estimate": adapter.estimate_latency({}),
        "healthcheck_timeout_s": DEFAULT_HEALTHCHECK_TIMEOUT_S,
    }
    return _tool_payload(
        tool_id=tool_id,
        status=status,
        reason=reason,
        error_category=error_category,
        capability_ids=capability_ids,
        cost_prior=cost_prior,
        risk_prior=risk_prior,
        latency_prior=latency_prior,
        checked_at=checked_at,
        profile=profile,
        details=details,
    )


def build_capability_readiness_matrix() -> List[Dict[str, Any]]:
    """构建 capability 级 readiness 视图。"""
    ensure_builtin_adapters()
    kg = load_tool_kg()
    tools = kg.get("tools", [])
    capabilities = kg.get("capabilities", [])
    if not isinstance(tools, list) or not isinstance(capabilities, list):
        return []

    capability_tools: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        for capability_id in tool.get("capabilities", []):
            if isinstance(capability_id, str):
                capability_tools[capability_id].append(tool)

    checked_at = now_iso()
    matrix: list[Dict[str, Any]] = []
    for capability in capabilities:
        if not isinstance(capability, dict):
            continue
        capability_id = capability.get("capability_id")
        if not isinstance(capability_id, str):
            continue
        ranked_tools = sorted(
            capability_tools.get(capability_id, []),
            key=lambda item: (
                0 if _primary_capability(item) == capability_id else 1,
                _priority_rank(item.get("priority")),
                str(item.get("id") or ""),
            ),
        )
        tool_readiness = [
            evaluate_tool_readiness(
                str(tool.get("id")),
                tool_entry=tool,
                checked_at=checked_at,
            )
            for tool in ranked_tools
            if isinstance(tool.get("id"), str)
        ]

        primary_tool_id = next(
            (item["tool_id"] for item in tool_readiness),
            None,
        )
        fallback_tool_ids = [item["tool_id"] for item in tool_readiness[1:]]
        available_tools = [
            item for item in tool_readiness if item["status"] in {"ready", "degraded"}
        ]
        ready_tools = [item for item in tool_readiness if item["status"] == "ready"]
        blocked_tools = [
            item for item in tool_readiness if item["status"] == "unavailable"
        ]
        degraded_reasons = [
            _tool_reason(item)
            for item in tool_readiness
            if item["status"] != "ready" and _tool_reason(item)
        ]

        status = "unavailable"
        reason = "no registered tool is ready"
        if tool_readiness:
            first = tool_readiness[0]
            if first["status"] == "ready":
                status = "ready"
                reason = first["reason"] or "primary tool is ready"
            elif ready_tools:
                status = "degraded"
                reason = "primary tool unavailable; fallback tool is ready"
            elif any(item["status"] == "degraded" for item in tool_readiness):
                status = "degraded"
                reason = "tool registered but health is degraded"
            elif degraded_reasons:
                reason = degraded_reasons[0]

        priors = _aggregate_priors(tool_readiness)
        recovery = _suggest_capability_recovery(status, degraded_reasons, blocked_tools)
        entry = CapabilityReadiness(
            capability_id=capability_id,
            status=status,  # type: ignore[arg-type]
            available_tools=[
                ToolReadiness(**item) for item in available_tools
            ],
            blocked_tools=[
                ToolReadiness(**item) for item in blocked_tools
            ],
            degraded_reasons=degraded_reasons,
            last_checked_at=checked_at,
            cost_prior=priors.get("cost_prior"),
            risk_prior=priors.get("risk_prior"),
            suggested_recovery=recovery,
            primary_tool_id=primary_tool_id,
            fallback_tool_ids=fallback_tool_ids,
            reason=reason,
            tools=[ToolReadiness(**item) for item in tool_readiness],
        )
        payload = entry.model_dump(mode="json", exclude_none=True)
        payload["checked_at"] = checked_at

        matrix.append(payload)
    return matrix


def build_tool_readiness_snapshot(tool_id: str) -> Dict[str, Any]:
    """返回候选可追溯使用的单工具 readiness 快照。"""
    kg = load_tool_kg()
    tools = kg.get("tools", [])
    tool_entry = next(
        (
            item
            for item in tools
            if isinstance(item, dict) and item.get("id") == tool_id
        ),
        None,
    )
    return evaluate_tool_readiness(tool_id, tool_entry=tool_entry)


def _tool_payload(
    *,
    tool_id: str,
    status: str,
    reason: str,
    error_category: str | None,
    capability_ids: Sequence[str],
    cost_prior: float | None,
    risk_prior: float | None,
    latency_prior: float | None,
    checked_at: str,
    profile: Any,
    details: dict[str, Any],
) -> Dict[str, Any]:
    suggested_recovery = _suggest_tool_recovery(error_category, reason)
    payload = ToolReadiness(
        tool_id=tool_id,
        status=status,  # type: ignore[arg-type]
        reason=reason,
        error_category=error_category,
        capability_ids=list(capability_ids),
        cost_prior=cost_prior,
        risk_prior=risk_prior,
        latency_prior=latency_prior,
        suggested_recovery=suggested_recovery,
        last_checked_at=checked_at,
        details=details,
        metadata_profile=profile.to_dict() if profile is not None else None,
    ).model_dump(mode="json", exclude_none=True)
    payload["checked_at"] = checked_at
    return payload


def _capability_ids(tool_entry: dict[str, Any] | None, profile: Any) -> list[str]:
    raw = tool_entry.get("capabilities") if isinstance(tool_entry, dict) else None
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, str)]
    if profile is not None:
        return list(profile.capability_ids)
    return []


def _priors_for_tool(
    tool_entry: dict[str, Any] | None,
    profile: Any,
) -> tuple[float | None, float | None, float | None]:
    if profile is not None:
        return profile.step_cost, profile.step_risk, profile.latency_cost_prior
    if isinstance(tool_entry, dict):
        raw_cost = tool_entry.get("cost_score")
        if isinstance(raw_cost, (int, float)):
            cost = round(float(raw_cost), 6)
            return cost, None, cost
    return None, None, None


def _aggregate_priors(tool_readiness: Sequence[Dict[str, Any]]) -> dict[str, float]:
    result: dict[str, float] = {}
    for key in ("cost_prior", "risk_prior"):
        values = [
            float(item[key])
            for item in tool_readiness
            if isinstance(item.get(key), (int, float))
        ]
        if values:
            result[key] = round(sum(values) / len(values), 6)
    return result


def _protocol_readiness_override(
    tool_entry: dict[str, Any] | None,
) -> tuple[str, str, str | None] | None:
    if not isinstance(tool_entry, dict):
        return None
    resource_assumptions = _resource_assumptions(tool_entry)
    execution = tool_entry.get("execution")
    provider = ""
    if isinstance(execution, dict):
        provider = str(execution.get("provider") or "").strip()
    if "nim_api_key_configured" in resource_assumptions and not os.getenv("NIM_API_KEY"):
        alternate = str(
            execution.get("alternate_provider") if isinstance(execution, dict) else ""
        ).strip()
        if alternate == "openfold3_rest" and _configured("OPENFOLD3_REST_BASE_URL"):
            return None
        return (
            "unavailable",
            "NIM API credential is missing",
            "credential_missing",
        )
    if "plm_rest_service_available" in resource_assumptions and not _configured(
        "PLM_REST_BASE_URL"
    ):
        return (
            "unavailable",
            "PLM REST endpoint is not configured or reachable",
            "remote_unreachable",
        )
    if (
        provider == "openfold3_rest"
        or "nim_api_key_configured_or_openfold3_rest_service_available"
        in resource_assumptions
    ) and not (os.getenv("NIM_API_KEY") or _configured("OPENFOLD3_REST_BASE_URL")):
        return (
            "unavailable",
            "OpenFold3 REST endpoint is not configured or reachable",
            "remote_unreachable",
        )
    if any("database_ready" in item for item in resource_assumptions) and not (
        _configured("PROTEIN_SEQUENCE_DB_PATH")
        or _configured("PROTEIN_STRUCTURE_DB_PATH")
        or _configured("PROTEIN_DATABASE_PATH")
    ):
        return (
            "degraded",
            "local similarity database path is not configured",
            "database_missing",
        )
    return None


def _resource_assumptions(tool_entry: dict[str, Any]) -> set[str]:
    constraints = tool_entry.get("constraints")
    if not isinstance(constraints, dict):
        return set()
    raw = constraints.get("resource_assumptions")
    if not isinstance(raw, list):
        return set()
    return {item for item in raw if isinstance(item, str)}


def _configured(env_key: str) -> bool:
    return bool(str(os.getenv(env_key, "")).strip())


def _classify_error(reason: str, tool_entry: dict[str, Any] | None) -> str:
    text = reason.lower()
    if "adapter not registered" in text:
        return "adapter_missing"
    if "api key" in text or "credential" in text or "auth" in text:
        return "credential_missing"
    if "database" in text or "db" in text:
        return "database_missing"
    if "timeout" in text:
        return "timeout"
    if "network" in text or "unreachable" in text or "endpoint" in text:
        return "remote_unreachable"
    if "binary" in text or "not installed" in text:
        return "binary_missing"
    if isinstance(tool_entry, dict) and any("database_ready" in item for item in _resource_assumptions(tool_entry)):
        return "database_missing"
    return "healthcheck_error"


def _suggest_tool_recovery(error_category: str | None, reason: str) -> str | None:
    if error_category == "adapter_missing":
        return "Register the adapter or remove the tool from candidate planning."
    if error_category == "credential_missing":
        return "Configure the required provider credential before planning this capability."
    if error_category == "remote_unreachable":
        return "Start the remote service or configure the provider base URL."
    if error_category == "database_missing":
        return "Configure a local database path for the similarity adapter."
    if error_category == "binary_missing":
        return "Install the required local binary or choose a fallback adapter."
    if error_category == "timeout":
        return "Retry after reducing input size or increasing the adapter timeout."
    if reason:
        return "Inspect adapter health details and use a fallback if available."
    return None


def _suggest_capability_recovery(
    status: str,
    degraded_reasons: Sequence[str],
    blocked_tools: Sequence[Dict[str, Any]],
) -> str | None:
    if status == "ready":
        return None
    categories = {
        item.get("error_category")
        for item in blocked_tools
        if isinstance(item.get("error_category"), str)
    }
    if "adapter_missing" in categories:
        return "Register missing adapters or remove unavailable tools from Planner candidates."
    if "credential_missing" in categories:
        return "Configure credentials or prefer a local fallback for this capability."
    if "remote_unreachable" in categories:
        return "Start remote services or configure reachable base URLs."
    if "database_missing" in categories or any("database" in item.lower() for item in degraded_reasons):
        return "Configure required local databases or select a non-database fallback."
    return "Use available fallback tools or inspect adapter health details."


def _tool_reason(item: Dict[str, Any]) -> str:
    reason = str(item.get("reason") or "").strip()
    category = str(item.get("error_category") or "").strip()
    if category and reason:
        return f"{item.get('tool_id')}: {category}: {reason}"
    if reason:
        return f"{item.get('tool_id')}: {reason}"
    return ""


def _join_reasons(*values: str) -> str:
    return "; ".join(value for value in values if value)


def _worse_status(current: str, candidate: str) -> str:
    rank = {"ready": 0, "degraded": 1, "unavailable": 2}
    return candidate if rank.get(candidate, 0) > rank.get(current, 0) else current


def _priority_rank(value: Any) -> int:
    if not isinstance(value, str):
        return 9
    normalized = value.strip().upper()
    if normalized == "P0":
        return 0
    if normalized.startswith("P") and normalized[1:].isdigit():
        return int(normalized[1:])
    return 9


def _primary_capability(tool: dict[str, Any]) -> str | None:
    capabilities = tool.get("capabilities")
    if not isinstance(capabilities, list) or not capabilities:
        return None
    first = capabilities[0]
    return first if isinstance(first, str) else None
