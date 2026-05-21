from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from src.infra.benchmark_platform_adapters import (
    normalize_issue199_platform_adapter_config,
)
from src.infra.experiments._gate_checks import build_issue200_gate_checks
from src.infra.w12_vertical_experiment import now_iso, write_json

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
    """执行本地 benchmark 统一门禁，并生成结构化报告。"""
    normalized = normalize_issue199_platform_adapter_config(config)
    resolved_output_root = output_root or Path(normalized["output_root"])
    resolved_freeze_id = freeze_id or normalized["freeze_id"]
    output_dir = resolved_output_root / resolved_freeze_id
    _ = output_dir.mkdir(parents=True, exist_ok=True)

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
            "json_report_path": str(
                (output_dir / "benchmark_acceptance_gate_report.json").resolve()
            ),
            "markdown_summary_path": str(
                (output_dir / "benchmark_acceptance_gate_summary.md").resolve()
            ),
            "gate_summary_path": str((output_dir / "benchmark_gate_summary.json").resolve()),
            "blockers_path": str((output_dir / "benchmark_gate_blockers.json").resolve()),
            "evidence_index_path": str(
                (output_dir / "benchmark_gate_evidence_index.json").resolve()
            ),
        },
    }

    write_json(output_dir / "benchmark_acceptance_gate_report.json", report)
    gate_summary = _build_gate_summary(report, config=normalized)
    blockers = _build_gate_blockers(report)
    evidence_index = _build_gate_evidence_index(
        report,
        gate_summary=gate_summary,
        blockers=blockers,
        output_dir=output_dir,
    )
    write_json(output_dir / "benchmark_gate_summary.json", gate_summary)
    write_json(output_dir / "benchmark_gate_blockers.json", blockers)
    write_json(output_dir / "benchmark_gate_evidence_index.json", evidence_index)
    _ = (output_dir / "benchmark_acceptance_gate_summary.md").write_text(
        _render_gate_summary(report),
        encoding="utf-8",
    )
    return report, output_dir


def _build_gate_checks(config: dict[str, Any]) -> list[dict[str, Any]]:
    return build_issue200_gate_checks(config=config, repo_root=_REPO_ROOT)


def _resolve_overall_status(counts: Counter[str]) -> str:
    if counts.get("block", 0) > 0:
        return "block"
    if counts.get("warn", 0) > 0:
        return "warn"
    return "pass"


def _render_gate_summary(report: dict[str, Any]) -> str:
    summary = report["summary"]
    checks = report["checks"]
    blocks = [check for check in checks if check["status"] == "block"]
    warnings = [check for check in checks if check["status"] == "warn"]
    lines = [
        "# Benchmark Acceptance Gate",
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
        "naming_convention_version": "benchmark-acceptance-v1",
        "issue_id": 200,
        "freeze_id": report["freeze_id"],
        "run_id": f"benchmark-gate-{report['freeze_id']}",
        "report_pack": "reports/benchmark-acceptance",
        "generated_at": report["generated_at"],
        "roots": {
            "experiment_output": str(output_dir.resolve()),
            "report_output": "reports/benchmark-acceptance",
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
                "artifact_id": "benchmark-gate-summary",
                "artifact_type": "summary",
                "title": "Benchmark gate summary",
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
                    "script_path": "scripts/benchmarks/run_benchmark_acceptance_gate.py",
                    "command": "uv run python scripts/benchmarks/run_benchmark_acceptance_gate.py",
                },
                "conclusion": gate_summary["conclusion"],
                "tags": ["gate", "summary", "benchmark"],
            },
            {
                "artifact_id": "benchmark-gate-blockers",
                "artifact_type": "report",
                "title": "Benchmark blocker list",
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
                "upstream_refs": ["benchmark-gate-summary"],
                "generated_by": {
                    "script_path": "scripts/benchmarks/run_benchmark_acceptance_gate.py",
                    "command": "uv run python scripts/benchmarks/run_benchmark_acceptance_gate.py",
                },
                "conclusion": (
                    "Structured blocker list for fail-fast triage."
                    if blockers["block_count"] > 0
                    else "No blocking items remain."
                ),
                "tags": ["gate", "blockers", "benchmark"],
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
