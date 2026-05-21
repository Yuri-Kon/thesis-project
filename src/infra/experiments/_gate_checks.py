from __future__ import annotations

from pathlib import Path
from typing import Any

from src.adapters.builtins import ensure_builtin_adapters
from src.adapters.registry import get_adapter
from src.engines.provider_config import load_provider_config
from src.kg.kg_client import load_tool_kg
from src.llm.provider_registry import load_provider_catalog


def build_issue200_gate_checks(
    *,
    config: dict[str, Any],
    repo_root: Path,
) -> list[dict[str, Any]]:
    """构造 issue200 benchmark gate 检查列表，集中封装 KG / adapter / provider 读取。"""

    kg = load_tool_kg()
    ensure_builtin_adapters()

    tools = kg.get("tools", [])
    capabilities = kg.get("capabilities", [])
    tool_nodes = {
        str(tool.get("id")): tool
        for tool in tools
        if isinstance(tool, dict) and isinstance(tool.get("id"), str)
    }
    capability_ids = {
        str(capability.get("capability_id"))
        for capability in capabilities
        if isinstance(capability, dict) and isinstance(capability.get("capability_id"), str)
    }
    model_provider_configs = load_provider_config()

    checks = [
        build_freeze_contract_check(config),
        build_budget_contract_check(config),
        build_tool_whitelist_check(config=config, tool_nodes=tool_nodes),
        build_capability_whitelist_check(
            config=config,
            capability_ids=capability_ids,
        ),
        build_tool_capability_alignment_check(
            config=config,
            tool_nodes=tool_nodes,
        ),
        build_adapter_registration_check(config),
        build_tool_provider_config_check(
            config=config,
            tool_nodes=tool_nodes,
            provider_configs=model_provider_configs,
        ),
        build_llm_provider_catalog_check(config=config, repo_root=repo_root),
        build_sample_task_input_consistency_check(config),
    ]
    return checks


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

def build_capability_whitelist_check(
    *,
    config: dict[str, Any],
    capability_ids: set[str],
) -> dict[str, Any]:
    """检查 capability allowlist 是否能在主 KG 中解析。"""

    allowed_capability_ids = config["tool_whitelist"]["allowed_capability_ids"]
    unknown_capability_ids = sorted(
        capability_id for capability_id in allowed_capability_ids if capability_id not in capability_ids
    )
    return make_gate_check(
        check_id="tool_whitelist_known_capabilities",
        title="能力白名单可解析",
        status="block" if unknown_capability_ids else "pass",
        message=(
            f"未知 capability_id: {', '.join(unknown_capability_ids)}"
            if unknown_capability_ids
            else "allowed_capability_ids 均能在主 KG 中找到。"
        ),
        remediation="将 allowed_capability_ids 对齐到 src/kg/protein_tool_kg.json 中声明的 capability_id。",
        details={"allowed_capability_ids": allowed_capability_ids},
    )


def build_tool_capability_alignment_check(
    *,
    config: dict[str, Any],
    tool_nodes: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """检查工具白名单是否至少覆盖一个白名单 capability。"""

    allowed_tool_ids = config["tool_whitelist"]["allowed_tool_ids"]
    allowed_capability_ids = config["tool_whitelist"]["allowed_capability_ids"]
    allowed_capability_set = set(allowed_capability_ids)
    misaligned_tools: list[str] = []
    for tool_id in allowed_tool_ids:
        tool = tool_nodes.get(tool_id)
        if tool is None:
            continue
        tool_capabilities = {
            capability
            for capability in tool.get("capabilities", [])
            if isinstance(capability, str)
        }
        if tool_capabilities.isdisjoint(allowed_capability_set):
            misaligned_tools.append(tool_id)
    return make_gate_check(
        check_id="tool_capability_alignment",
        title="工具与能力白名单一致",
        status="block" if misaligned_tools else "pass",
        message=(
            f"这些工具不落在 allowlisted capabilities 内: {', '.join(misaligned_tools)}"
            if misaligned_tools
            else "所有 allowlisted tools 都至少覆盖一个 allowlisted capability。"
        ),
        remediation="修正 allowed_tool_ids 或 allowed_capability_ids，避免跨 issue 横向实验时出现能力定义漂移。",
        details={"misaligned_tool_ids": misaligned_tools},
    )


def build_adapter_registration_check(config: dict[str, Any]) -> dict[str, Any]:
    """检查白名单工具是否已注册 adapter。"""

    allowed_tool_ids = config["tool_whitelist"]["allowed_tool_ids"]
    missing_adapters: list[str] = []
    for tool_id in allowed_tool_ids:
        try:
            get_adapter(tool_id)
        except KeyError:
            missing_adapters.append(tool_id)
    return make_gate_check(
        check_id="adapter_registration",
        title="白名单工具已接入 adapter",
        status="block" if missing_adapters else "pass",
        message=(
            f"未注册 adapter 的工具: {', '.join(missing_adapters)}"
            if missing_adapters
            else "所有白名单工具都能通过默认注册链解析到 adapter。"
        ),
        remediation="在 src/adapters 与 src/adapters/builtins.py 中补齐 adapter 接入，避免运行时 tool resolution 失败。",
        details={"missing_adapter_tool_ids": missing_adapters},
    )


def build_tool_provider_config_check(
    *,
    config: dict[str, Any],
    tool_nodes: dict[str, dict[str, Any]],
    provider_configs: dict[str, Any],
) -> dict[str, Any]:
    """检查工具 KG 引用的 provider 是否存在配置。"""

    missing_model_providers = sorted(
        _collect_missing_model_providers(
            allowed_tool_ids=config["tool_whitelist"]["allowed_tool_ids"],
            tool_nodes=tool_nodes,
            provider_configs=provider_configs,
        )
    )
    return make_gate_check(
        check_id="tool_provider_config",
        title="工具 provider 配置完整",
        status="block" if missing_model_providers else "pass",
        message=(
            f"缺少 model provider 配置: {', '.join(missing_model_providers)}"
            if missing_model_providers
            else "allowlisted tools 引用的 execution.provider / alternate_provider 均已配置。"
        ),
        remediation="在 configs/model_providers.json 中补齐缺失 provider，并保持 tool KG execution.provider 指向存在的 provider。",
        details={"missing_model_providers": missing_model_providers},
    )


def build_llm_provider_catalog_check(
    *,
    config: dict[str, Any],
    repo_root: Path,
) -> dict[str, Any]:
    """检查 LLM provider catalog 与 allowlist 的一致性。"""

    llm_catalog_path = _resolve_repo_path(
        config["provider_allowlist"]["catalog_path"],
        repo_root=repo_root,
    )
    if not llm_catalog_path.exists():
        return make_gate_check(
            check_id="llm_provider_catalog",
            title="LLM provider 目录可加载",
            status="block",
            message=f"provider catalog 不存在: {llm_catalog_path}",
            remediation="修正 provider_allowlist.catalog_path，确保 benchmark 门禁和 promptfoo 使用同一份 LLM provider 目录。",
            details={"catalog_path": str(llm_catalog_path)},
        )

    provider_catalog = load_provider_catalog(llm_catalog_path)
    allowed_aliases = config["provider_allowlist"]["allowed_aliases"]
    default_alias = config["provider_allowlist"]["default_promptfoo_provider_alias"]
    missing_aliases = sorted(
        alias for alias in allowed_aliases if alias not in provider_catalog.providers
    )
    default_alias_missing = default_alias not in provider_catalog.providers
    default_not_allowlisted = default_alias not in set(allowed_aliases)
    status = (
        "block"
        if missing_aliases or default_alias_missing or default_not_allowlisted
        else "pass"
    )
    return make_gate_check(
        check_id="llm_provider_catalog",
        title="LLM provider allowlist 完整",
        status=status,
        message=compose_llm_provider_message(
            missing_aliases=missing_aliases,
            default_alias=default_alias,
            default_alias_missing=default_alias_missing,
            default_not_allowlisted=default_not_allowlisted,
        ),
        remediation="确保 provider_allowlist.allowed_aliases 和 default_promptfoo_provider_alias 都能在 configs/llm_providers.json 中解析。",
        details={
            "catalog_path": str(llm_catalog_path),
            "allowed_aliases": allowed_aliases,
            "default_promptfoo_provider_alias": default_alias,
        },
    )


def build_sample_task_input_consistency_check(config: dict[str, Any]) -> dict[str, Any]:
    """检查 sample task 约束中的 task_set_version 是否与顶层一致。"""

    inconsistent_task_versions: list[dict[str, Any]] = []
    expected_task_set_version = config["task_set_version"]
    for task in config["sample_tasks"]:
        constraint_version = task["constraints"].get("task_set_version")
        if constraint_version and constraint_version != expected_task_set_version:
            inconsistent_task_versions.append(
                {
                    "task_key": task["task_key"],
                    "constraint_task_set_version": constraint_version,
                }
            )
    return make_gate_check(
        check_id="sample_task_input_consistency",
        title="样例输入版本一致",
        status="block" if inconsistent_task_versions else "pass",
        message=(
            "sample_tasks.constraints.task_set_version 与顶层 task_set_version 不一致。"
            if inconsistent_task_versions
            else "sample_tasks 的 task_set_version 与冻结配置一致。"
        ),
        remediation="统一 sample_tasks.constraints.task_set_version，避免外部基线实验复用时输入定义漂移。",
        details={
            "task_set_version": expected_task_set_version,
            "mismatched_tasks": inconsistent_task_versions,
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


def compose_llm_provider_message(
    *,
    missing_aliases: list[str],
    default_alias: str,
    default_alias_missing: bool,
    default_not_allowlisted: bool,
) -> str:
    parts: list[str] = []
    if missing_aliases:
        parts.append(f"catalog 中缺少 provider alias: {', '.join(missing_aliases)}")
    if default_alias_missing:
        parts.append(f"default alias 未在 catalog 中找到: {default_alias}")
    if default_not_allowlisted:
        parts.append(f"default alias 未包含在 allowed_aliases 中: {default_alias}")
    if not parts:
        return "LLM provider allowlist 与默认 alias 均可解析。"
    return "；".join(parts)


def _collect_missing_model_providers(
    *,
    allowed_tool_ids: list[str],
    tool_nodes: dict[str, dict[str, Any]],
    provider_configs: dict[str, Any],
) -> set[str]:
    missing: set[str] = set()
    for tool_id in allowed_tool_ids:
        tool = tool_nodes.get(tool_id)
        if tool is None:
            continue
        execution = tool.get("execution")
        if not isinstance(execution, dict):
            continue
        for field_name in ("provider", "alternate_provider"):
            provider_name = execution.get(field_name)
            if not isinstance(provider_name, str) or not provider_name.strip():
                continue
            if provider_name not in provider_configs:
                missing.add(provider_name)
    return missing


def _resolve_repo_path(raw_path: str, *, repo_root: Path) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate
    return (repo_root / candidate).resolve()
