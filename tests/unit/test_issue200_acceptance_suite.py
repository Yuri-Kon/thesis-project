from __future__ import annotations

from pathlib import Path

from src.infra.issue200_acceptance_suite import run_issue200_acceptance_suite


def test_issue200_acceptance_suite_reports_pass(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("src.infra.issue200_acceptance_suite.pytest.main", lambda args: 0)

    suite_report, output_dir = run_issue200_acceptance_suite(
        config_path=Path("configs/experiments/issue199_benchmark_platform_adapters.json"),
        output_root=tmp_path,
        freeze_id="issue200-suite-pass",
    )

    assert suite_report["overall_status"] == "pass"
    assert suite_report["pytest"]["status"] == "pass"
    assert suite_report["gate"]["status"] == "pass"
    assert (output_dir / "issue200_acceptance_suite.json").exists()


def test_issue200_acceptance_suite_blocks_on_pytest_failure(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr("src.infra.issue200_acceptance_suite.pytest.main", lambda args: 1)

    suite_report, _ = run_issue200_acceptance_suite(
        config_path=Path("configs/experiments/issue199_benchmark_platform_adapters.json"),
        output_root=tmp_path,
        freeze_id="issue200-suite-block",
    )

    assert suite_report["overall_status"] == "block"
    assert suite_report["pytest"]["status"] == "block"
