from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

import pytest

from src.infra.benchmark_acceptance_gate import run_issue200_acceptance_gate
from src.infra.w12_vertical_experiment import load_json, now_iso, write_json

__all__ = [
    "DEFAULT_ISSUE200_ACCEPTANCE_TESTS",
    "run_issue200_acceptance_suite",
]


DEFAULT_ISSUE200_ACCEPTANCE_TESTS = (
    "tests/unit/test_benchmark_acceptance_gate.py",
    "tests/unit/test_benchmark_platform_adapters.py",
)


def run_issue200_acceptance_suite(
    *,
    config_path: Path,
    output_root: Path | None = None,
    freeze_id: str | None = None,
    pytest_args: Sequence[str] | None = None,
) -> tuple[dict[str, Any], Path]:
    """执行本地 benchmark 一键验收。"""
    config = load_json(config_path)
    report, output_dir = run_issue200_acceptance_gate(
        config=config,
        config_path=config_path,
        output_root=output_root,
        freeze_id=freeze_id,
    )

    resolved_pytest_args = list(pytest_args or DEFAULT_ISSUE200_ACCEPTANCE_TESTS)
    pytest_exit_code = int(pytest.main(resolved_pytest_args))
    suite_status = "pass"
    if pytest_exit_code != 0 or report["overall_status"] == "block":
        suite_status = "block"
    elif report["overall_status"] == "warn":
        suite_status = "warn"

    suite_report = {
        "schema_version": "w16.issue200.acceptance-suite.v1",
        "issue_id": 200,
        "generated_at": now_iso(),
        "freeze_id": report["freeze_id"],
        "overall_status": suite_status,
        "pytest": {
            "status": "pass" if pytest_exit_code == 0 else "block",
            "exit_code": pytest_exit_code,
            "args": resolved_pytest_args,
        },
        "gate": {
            "status": report["overall_status"],
            "report_path": report["artifacts"]["json_report_path"],
            "gate_summary_path": report["artifacts"]["gate_summary_path"],
            "blockers_path": report["artifacts"]["blockers_path"],
            "evidence_index_path": report["artifacts"]["evidence_index_path"],
        },
        "artifacts": {
            "output_dir": str(output_dir.resolve()),
            "suite_report_path": str((output_dir / "benchmark_acceptance_suite.json").resolve()),
        },
    }
    write_json(output_dir / "benchmark_acceptance_suite.json", suite_report)
    return suite_report, output_dir
