from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from src.adapters.builtins import ensure_builtin_adapters
from src.adapters.registry import get_adapter
from src.engines.provider_config import load_provider_config
from src.infra.benchmark_platform_adapters import (
    normalize_issue199_platform_adapter_config,
)
from src.infra.w12_vertical_experiment import now_iso, write_json
from src.kg.kg_client import load_tool_kg
from src.llm.provider_registry import load_provider_catalog

__all__ = [
    "DEFAULT_ISSUE200_GATE_SCHEMA_VERSION",
    "run_issue200_acceptance_gate",
]


DEFAULT_ISSUE200_GATE_SCHEMA_VERSION = "w16.issue200.acceptance-gate.v1"
DEFAULT_ISSUE200_GATE_SUMMARY_SCHEMA_VERSION = "w16.issue200.gate-summary.v1"
DEFAULT_ISSUE200_GATE_BLOCKERS_SCHEMA_VERSION = "w16.issue200.blockers.v1"
DEFAULT_ISSUE200_GATE_EVIDENCE_INDEX_SCHEMA_VERSION = "w16.issue200.evidence-index.v1"
_REPO_ROOT = Path(__file__).resolve().parents[2]


def run_issue200_acceptance_gate(
    *,
    config: dict[str, Any],
    config_path: Path | None = None,
    output_root: Path | None = None,
    freeze_id: str | None = None,
) -> tuple[dict[str, Any], Path]:
    """执行 Issue #200 本地统一门禁，并生成结构化报告。"""
    normalized = normalize_issue199_platform_adapter_config(config)
    resolved_output_root = output_root or Path(normalized["output_root"])
    resolved_freeze_id = freeze_id or normalized["freeze_id"]
    output_dir = resolved_output_root / resolved_freeze_id
    output_dir.mkdir(parents=True, exist_ok=True)

    checks = _build_gate_checks(normalized)
    counts = Counter(check["status"] for check in checks)
    overall_status = _resolve_overall_status(counts)

    report = {
        "schema_version": DEFAULT_ISSUE200_GATE_SCHEMA_VERSION,
        "issue_id": 200,
        "generated_at": now_iso(),
        "config_path": str((config_path or Path("<in-memory-config>")).resolve())
        if config_path is not None
        else "<in-memory-config>",
        "freeze_id": resolved_freeze_id,
        "dataset_version": normalized["dataset_version"],
        "task_set_version": normalized["task_set_version"],
        "tool_whitelist_version": normalized["tool_whitelist"]["tool_whitelist_version"],
        "budget_version": normalized["budget_contract"]["budget_version"],
        "overall_status": overall_status,
        "summary": {
            "pass_count": counts.get("pass", 0),
            "warn_count": counts.get("warn", 0),
            "block_count": counts.get("block", 0),
        },
        "checks": checks,
        "artifacts": {
            "output_dir": str(output_dir.resolve()),
            "json_report_path": str((output_dir / "issue200_acceptance_gate_report.json").resolve()),
            "markdown_summary_path": str(
                (output_dir / "issue200_acceptance_gate_summary.md").resolve()
            ),
            "gate_summary_path": str((output_dir / "issue200_gate_summary.json").resolve()),
            "blockers_path": str((output_dir / "issue200_gate_blockers.json").resolve()),
            "evidence_index_path": str((output_dir / "issue200_gate_evidence_index.json").resolve()),
        },
    }

    write_json(output_dir / "issue200_acceptance_gate_report.json", report)
    gate_summary = _build_gate_summary(report, config=normalized)
    blockers = _build_gate_blockers(report)
    evidence_index = _build_gate_evidence_index(
        report,
        gate_summary=gate_summary,
        blockers=blockers,
        output_dir=output_dir,
    )
    write_json(output_dir / "issue200_gate_summary.json", gate_summary)
    write_json(output_dir / "issue200_gate_blockers.json", blockers)
    write_json(output_dir / "issue200_gate_evidence_index.json", evidence_index)
    (output_dir / "issue200_acceptance_gate_summary.md").write_text(
        _render_gate_summary(report),
        encoding="utf-8",
    )
    return report, output_dir


def _build_gate_checks(config: dict[str, Any]) -> list[dict[str, Any]]:
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
    checks: list[dict[str, Any]] = []

    freeze_fields = {
        "freeze_id": config["freeze_id"],
        "dataset_version": config["dataset_version"],
        "tool_whitelist_version": config["tool_whitelist"]["tool_whitelist_version"],
        "budget_version": config["budget_contract"]["budget_version"],
    }
    missing_freeze_fields = [
        key for key, value in freeze_fields.items() if not isinstance(value, str) or not value.strip()
    ]
    checks.append(
        _make_check(
            check_id="freeze_contract_fields",
            title="冻结字段完整",
            status="block" if missing_freeze_fields else "pass",
            message=(
                f"缺少冻结字段: {', '.join(missing_freeze_fields)}"
                if missing_freeze_fields
                else "freeze_id、dataset_version、tool_whitelist_version、budget_version 均已固定。"
            ),
            remediation=(
                "补齐实验冻结配置中的缺失字段，并保持这些字段在 issue #172/#221/#224 中原样透传。"
            ),
            details=freeze_fields,
        )
    )

    smoke_defaults = config["budget_contract"]["smoke_defaults"]
    carry_fields = config["budget_contract"]["carry_to_issue172"]
    missing_budget_keys = [field for field in carry_fields if field not in smoke_defaults]
    checks.append(
        _make_check(
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
    )

    allowed_tool_ids = config["tool_whitelist"]["allowed_tool_ids"]
    high_cost_tool_ids = config["tool_whitelist"]["high_cost_tool_ids"]
    unknown_tool_ids = sorted(tool_id for tool_id in allowed_tool_ids if tool_id not in tool_nodes)
    non_allowlisted_high_cost = sorted(
        tool_id for tool_id in high_cost_tool_ids if tool_id not in set(allowed_tool_ids)
    )
    checks.append(
        _make_check(
            check_id="tool_whitelist_known_tools",
            title="工具白名单可解析",
            status="block" if unknown_tool_ids or non_allowlisted_high_cost else "pass",
            message=_compose_tool_whitelist_message(
                unknown_tool_ids=unknown_tool_ids,
                non_allowlisted_high_cost=non_allowlisted_high_cost,
            ),
            remediation="将白名单工具 ID 对齐到主 KG 中当前真实存在的 tool.id，并确保高成本子集是白名单子集。",
            details={
                "allowed_tool_ids": allowed_tool_ids,
                "high_cost_tool_ids": high_cost_tool_ids,
            },
        )
    )

    allowed_capability_ids = config["tool_whitelist"]["allowed_capability_ids"]
    unknown_capability_ids = sorted(
        capability_id for capability_id in allowed_capability_ids if capability_id not in capability_ids
    )
    checks.append(
        _make_check(
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
    )

    misaligned_tools = []
    allowed_capability_set = set(allowed_capability_ids)
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
    checks.append(
        _make_check(
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
    )

    missing_adapters = []
    for tool_id in allowed_tool_ids:
        try:
            get_adapter(tool_id)
        except KeyError:
            missing_adapters.append(tool_id)
    checks.append(
        _make_check(
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
    )

    missing_model_providers = sorted(
        _collect_missing_model_providers(
            allowed_tool_ids=allowed_tool_ids,
            tool_nodes=tool_nodes,
            provider_configs=model_provider_configs,
        )
    )
    checks.append(
        _make_check(
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
    )

    llm_catalog_path = _resolve_repo_path(config["provider_allowlist"]["catalog_path"])
    if not llm_catalog_path.exists():
        checks.append(
            _make_check(
                check_id="llm_provider_catalog",
                title="LLM provider 目录可加载",
                status="block",
                message=f"provider catalog 不存在: {llm_catalog_path}",
                remediation="修正 provider_allowlist.catalog_path，确保 issue #200 门禁和 promptfoo 使用同一份 LLM provider 目录。",
                details={"catalog_path": str(llm_catalog_path)},
            )
        )
    else:
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
        checks.append(
            _make_check(
                check_id="llm_provider_catalog",
                title="LLM provider allowlist 完整",
                status=status,
                message=_compose_llm_provider_message(
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
        )

    inconsistent_task_versions = []
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
    checks.append(
        _make_check(
            check_id="sample_task_input_consistency",
            title="样例输入版本一致",
            status="block" if inconsistent_task_versions else "pass",
            message=(
                "sample_tasks.constraints.task_set_version 与顶层 task_set_version 不一致。"
                if inconsistent_task_versions
                else "sample_tasks 的 task_set_version 与冻结配置一致。"
            ),
            remediation="统一 sample_tasks.constraints.task_set_version，避免 issue #172 横向实验复用时输入定义漂移。",
            details={
                "task_set_version": expected_task_set_version,
                "mismatched_tasks": inconsistent_task_versions,
            },
        )
    )
    return checks


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


def _make_check(
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


def _resolve_overall_status(counts: Counter[str]) -> str:
    if counts.get("block", 0) > 0:
        return "block"
    if counts.get("warn", 0) > 0:
        return "warn"
    return "pass"


def _resolve_repo_path(raw_path: str) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate
    return (_REPO_ROOT / candidate).resolve()


def _compose_tool_whitelist_message(
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


def _compose_llm_provider_message(
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


def _render_gate_summary(report: dict[str, Any]) -> str:
    summary = report["summary"]
    checks = report["checks"]
    blocks = [check for check in checks if check["status"] == "block"]
    warnings = [check for check in checks if check["status"] == "warn"]
    lines = [
        "# Issue #200 Acceptance Gate",
        "",
        f"- overall_status: `{report['overall_status']}`",
        f"- freeze_id: `{report['freeze_id']}`",
        f"- dataset_version: `{report['dataset_version']}`",
        f"- tool_whitelist_version: `{report['tool_whitelist_version']}`",
        f"- budget_version: `{report['budget_version']}`",
        f"- generated_at: `{report['generated_at']}`",
        "",
        "## Summary",
        "",
        f"- pass: `{summary['pass_count']}`",
        f"- warn: `{summary['warn_count']}`",
        f"- block: `{summary['block_count']}`",
        "",
    ]
    if blocks:
        lines.extend(["## Blocking Items", ""])
        for check in blocks:
            lines.append(f"- `{check['check_id']}`: {check['message']}")
            lines.append(f"  remediation: {check['remediation']}")
        lines.append("")
    if warnings:
        lines.extend(["## Warnings", ""])
        for check in warnings:
            lines.append(f"- `{check['check_id']}`: {check['message']}")
            lines.append(f"  remediation: {check['remediation']}")
        lines.append("")
    lines.extend(["## Checks", ""])
    for check in checks:
        lines.append(
            f"- `{check['check_id']}` [{check['status']}]: {check['message']}"
        )
    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            f"- json_report: `{report['artifacts']['json_report_path']}`",
            f"- markdown_summary: `{report['artifacts']['markdown_summary_path']}`",
            "",
        ]
    )
    return "\n".join(lines)


def _build_gate_summary(report: dict[str, Any], *, config: dict[str, Any]) -> dict[str, Any]:
    checks = report["checks"]
    passed = [check for check in checks if check["status"] == "pass"]
    warned = [check for check in checks if check["status"] == "warn"]
    blocked = [check for check in checks if check["status"] == "block"]
    consumer_issues = config.get("source_references", {}).get("consumer_issues")
    if not isinstance(consumer_issues, list):
        consumer_issues = []

    return {
        "schema_version": DEFAULT_ISSUE200_GATE_SUMMARY_SCHEMA_VERSION,
        "issue_id": 200,
        "freeze_id": report["freeze_id"],
        "generated_at": report["generated_at"],
        "overall_status": report["overall_status"],
        "ready_for_downstream": report["overall_status"] == "pass",
        "consumer_issues": [
            str(issue_id)
            for issue_id in consumer_issues
            if isinstance(issue_id, (str, int))
        ],
        "carry_forward_contract": {
            "freeze_id": report["freeze_id"],
            "dataset_version": report["dataset_version"],
            "task_set_version": report["task_set_version"],
            "tool_whitelist_version": report["tool_whitelist_version"],
            "budget_version": report["budget_version"],
            "allowed_tool_ids": config["tool_whitelist"]["allowed_tool_ids"],
            "allowed_capability_ids": config["tool_whitelist"]["allowed_capability_ids"],
            "budget_fields": config["budget_contract"]["smoke_defaults"],
            "fairness_requirements": config["fairness_contract"].get("requirements", []),
        },
        "counts": report["summary"],
        "pass_items": [
            _to_gate_item(check, include_remediation=False)
            for check in passed
        ],
        "warn_items": [
            _to_gate_item(check, include_remediation=True)
            for check in warned
        ],
        "block_items": [
            _to_gate_item(check, include_remediation=True)
            for check in blocked
        ],
        "source_refs": {
            "checks_report_path": report["artifacts"]["json_report_path"],
            "checks_summary_markdown_path": report["artifacts"]["markdown_summary_path"],
            "config_path": report["config_path"],
        },
        "conclusion": _compose_gate_conclusion(report["overall_status"], blocked_count=len(blocked)),
    }


def _build_gate_blockers(report: dict[str, Any]) -> dict[str, Any]:
    blocked = [check for check in report["checks"] if check["status"] == "block"]
    return {
        "schema_version": DEFAULT_ISSUE200_GATE_BLOCKERS_SCHEMA_VERSION,
        "issue_id": 200,
        "freeze_id": report["freeze_id"],
        "generated_at": report["generated_at"],
        "overall_status": report["overall_status"],
        "block_count": len(blocked),
        "blockers": [
            {
                "check_id": check["check_id"],
                "title": check["title"],
                "reason": check["message"],
                "remediation": check["remediation"],
                "details": check["details"],
            }
            for check in blocked
        ],
    }


def _build_gate_evidence_index(
    report: dict[str, Any],
    *,
    gate_summary: dict[str, Any],
    blockers: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    return {
        "schema_version": DEFAULT_ISSUE200_GATE_EVIDENCE_INDEX_SCHEMA_VERSION,
        "naming_convention_version": "w16-issue-200-v1",
        "issue_id": 200,
        "freeze_id": report["freeze_id"],
        "run_id": f"issue200-gate-{report['freeze_id']}",
        "report_pack": "reports/w16-issue-200",
        "generated_at": report["generated_at"],
        "roots": {
            "experiment_output": str(output_dir.resolve()),
            "report_output": "reports/w16-issue-200",
        },
        "traceability_chains": {
            "gate_summary": {
                "required_refs": [
                    "config_path",
                    "checks_report_path",
                    "gate_summary_path",
                ],
                "chain_rule": "config -> checks_report -> gate_summary",
            },
            "gate_blockers": {
                "required_refs": [
                    "config_path",
                    "checks_report_path",
                    "blockers_path",
                ],
                "chain_rule": "config -> checks_report -> blockers",
            },
        },
        "artifacts": [
            {
                "artifact_id": "issue200-gate-summary",
                "artifact_type": "summary",
                "title": "Issue #200 gate summary",
                "status": "ready" if gate_summary["ready_for_downstream"] else "blocked",
                "path": report["artifacts"]["gate_summary_path"],
                "run_ref": {
                    "freeze_id": report["freeze_id"],
                    "issue_id": 200,
                    "status": report["overall_status"],
                },
                "source_refs": {
                    "config_path": report["config_path"],
                    "checks_report_path": report["artifacts"]["json_report_path"],
                    "gate_summary_path": report["artifacts"]["gate_summary_path"],
                },
                "upstream_refs": [],
                "generated_by": {
                    "script_path": "scripts/benchmarks/run_issue200_acceptance_gate.py",
                    "command": "uv run python scripts/benchmarks/run_issue200_acceptance_gate.py",
                },
                "conclusion": gate_summary["conclusion"],
                "tags": ["gate", "summary", "issue200"],
            },
            {
                "artifact_id": "issue200-gate-blockers",
                "artifact_type": "report",
                "title": "Issue #200 blocker list",
                "status": "ready",
                "path": report["artifacts"]["blockers_path"],
                "run_ref": {
                    "freeze_id": report["freeze_id"],
                    "issue_id": 200,
                    "status": report["overall_status"],
                },
                "source_refs": {
                    "config_path": report["config_path"],
                    "checks_report_path": report["artifacts"]["json_report_path"],
                    "blockers_path": report["artifacts"]["blockers_path"],
                },
                "upstream_refs": ["issue200-gate-summary"],
                "generated_by": {
                    "script_path": "scripts/benchmarks/run_issue200_acceptance_gate.py",
                    "command": "uv run python scripts/benchmarks/run_issue200_acceptance_gate.py",
                },
                "conclusion": (
                    "Structured blocker list for fail-fast triage."
                    if blockers["block_count"] > 0
                    else "No blocking items remain."
                ),
                "tags": ["gate", "blockers", "issue200"],
            },
        ],
    }


def _to_gate_item(check: dict[str, Any], *, include_remediation: bool) -> dict[str, Any]:
    item = {
        "check_id": check["check_id"],
        "title": check["title"],
        "summary": check["message"],
    }
    if include_remediation:
        item["remediation"] = check["remediation"]
    return item


def _compose_gate_conclusion(overall_status: str, *, blocked_count: int) -> str:
    if overall_status == "pass":
        return "Gate passed. The frozen contract can be carried into downstream experiment/report issues."
    if overall_status == "warn":
        return "Gate passed with warnings. Downstream reuse is possible, but warnings should be tracked."
    return f"Gate blocked with {blocked_count} blocking item(s). Downstream experiment execution should not proceed."
