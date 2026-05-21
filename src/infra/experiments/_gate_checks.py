from __future__ import annotations

from typing import Any


def build_freeze_contract_check(config: dict[str, Any]) -> dict[str, Any]:
    """构造冻结字段检查，避免 gate 主流程堆叠基础校验细节。"""

    freeze_fields = {
        "freeze_id": config["freeze_id"],
        "dataset_version": config["dataset_version"],
        "tool_whitelist_version": config["tool_whitelist"]["tool_whitelist_version"],
        "budget_version": config["budget_contract"]["budget_version"],
    }
    missing_freeze_fields = [
        key for key, value in freeze_fields.items() if not isinstance(value, str) or not value.strip()
    ]
    return make_gate_check(
        check_id="freeze_contract_fields",
        title="冻结字段完整",
        status="block" if missing_freeze_fields else "pass",
        message=(
            f"缺少冻结字段: {', '.join(missing_freeze_fields)}"
            if missing_freeze_fields
            else "freeze_id、dataset_version、tool_whitelist_version、budget_version 均已固定。"
        ),
        remediation="补齐实验冻结配置中的缺失字段，并保持这些字段在下游实验与报告中原样透传。",
        details=freeze_fields,
    )


def build_budget_contract_check(config: dict[str, Any]) -> dict[str, Any]:
    """检查 smoke budget 是否覆盖下游 issue 复用字段。"""

    smoke_defaults = config["budget_contract"]["smoke_defaults"]
    carry_fields = config["budget_contract"]["carry_to_issue172"]
    missing_budget_keys = [field for field in carry_fields if field not in smoke_defaults]
    return make_gate_check(
        check_id="budget_contract_keys",
        title="预算字段可下游复用",
        status="block" if missing_budget_keys else "pass",
        message=(
            f"carry_to_issue172 缺少预算字段: {', '.join(missing_budget_keys)}"
            if missing_budget_keys
            else "预算字段已覆盖 carry_to_issue172 要求。"
        ),
        remediation="保证 carry_to_issue172 中的每个字段都在 smoke_defaults 中有固定值。",
        details={
            "carry_to_issue172": carry_fields,
            "smoke_defaults_keys": sorted(smoke_defaults.keys()),
        },
    )


def build_tool_whitelist_check(
    *,
    config: dict[str, Any],
    tool_nodes: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """检查工具白名单与高成本工具子集的基础一致性。"""

    allowed_tool_ids = config["tool_whitelist"]["allowed_tool_ids"]
    high_cost_tool_ids = config["tool_whitelist"]["high_cost_tool_ids"]
    unknown_tool_ids = sorted(tool_id for tool_id in allowed_tool_ids if tool_id not in tool_nodes)
    non_allowlisted_high_cost = sorted(
        tool_id for tool_id in high_cost_tool_ids if tool_id not in set(allowed_tool_ids)
    )
    return make_gate_check(
        check_id="tool_whitelist_known_tools",
        title="工具白名单可解析",
        status="block" if unknown_tool_ids or non_allowlisted_high_cost else "pass",
        message=compose_tool_whitelist_message(
            unknown_tool_ids=unknown_tool_ids,
            non_allowlisted_high_cost=non_allowlisted_high_cost,
        ),
        remediation="将白名单工具 ID 对齐到主 KG 中当前真实存在的 tool.id，并确保高成本子集是白名单子集。",
        details={
            "allowed_tool_ids": allowed_tool_ids,
            "high_cost_tool_ids": high_cost_tool_ids,
        },
    )


def make_gate_check(
    *,
    check_id: str,
    title: str,
    status: str,
    message: str,
    remediation: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "title": title,
        "status": status,
        "message": message,
        "remediation": remediation,
        "details": details or {},
    }


def compose_tool_whitelist_message(
    *,
    unknown_tool_ids: list[str],
    non_allowlisted_high_cost: list[str],
) -> str:
    parts: list[str] = []
    if unknown_tool_ids:
        parts.append(f"未知工具 ID: {', '.join(unknown_tool_ids)}")
    if non_allowlisted_high_cost:
        parts.append(
            f"高成本工具不在 allowlist 中: {', '.join(non_allowlisted_high_cost)}"
        )
    if not parts:
        return "allowed_tool_ids 与 high_cost_tool_ids 均通过基础一致性检查。"
    return "；".join(parts)
