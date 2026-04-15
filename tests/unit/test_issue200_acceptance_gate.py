from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.infra.issue200_acceptance_gate import run_issue200_acceptance_gate
from src.infra.w12_vertical_experiment import load_json


def test_issue200_acceptance_gate_passes_current_freeze_config(tmp_path: Path) -> None:
    report, output_dir = run_issue200_acceptance_gate(
        config=load_json(Path("configs/experiments/issue199_benchmark_platform_adapters.json")),
        config_path=Path("configs/experiments/issue199_benchmark_platform_adapters.json"),
        output_root=tmp_path,
        freeze_id="issue200-gate-pass",
    )

    assert report["overall_status"] == "pass"
    assert report["summary"]["block_count"] == 0
    assert (output_dir / "issue200_acceptance_gate_report.json").exists()
    assert (output_dir / "issue200_acceptance_gate_summary.md").exists()
    assert (output_dir / "issue200_gate_summary.json").exists()
    assert (output_dir / "issue200_gate_blockers.json").exists()
    assert (output_dir / "issue200_gate_evidence_index.json").exists()

    check_ids = {check["check_id"] for check in report["checks"]}
    assert "freeze_contract_fields" in check_ids
    assert "adapter_registration" in check_ids
    assert "llm_provider_catalog" in check_ids

    gate_summary = json.loads((output_dir / "issue200_gate_summary.json").read_text(encoding="utf-8"))
    blockers = json.loads((output_dir / "issue200_gate_blockers.json").read_text(encoding="utf-8"))
    evidence_index = json.loads(
        (output_dir / "issue200_gate_evidence_index.json").read_text(encoding="utf-8")
    )
    assert gate_summary["ready_for_downstream"] is True
    assert "172" in gate_summary["consumer_issues"]
    assert blockers["block_count"] == 0
    artifact_ids = {artifact["artifact_id"] for artifact in evidence_index["artifacts"]}
    assert "issue200-gate-summary" in artifact_ids
    assert "issue200-gate-blockers" in artifact_ids


def test_issue200_acceptance_gate_blocks_inconsistent_tool_and_provider_alias(
    tmp_path: Path,
) -> None:
    config = load_json(Path("configs/experiments/issue199_benchmark_platform_adapters.json"))
    broken_config = json.loads(json.dumps(config))
    broken_config["tool_whitelist"]["allowed_tool_ids"][0] = "missing_tool"
    broken_config["provider_allowlist"]["default_promptfoo_provider_alias"] = "missing-alias"

    report, _ = run_issue200_acceptance_gate(
        config=broken_config,
        output_root=tmp_path,
        freeze_id="issue200-gate-block",
    )

    assert report["overall_status"] == "block"
    blocked_checks = {
        check["check_id"]: check
        for check in report["checks"]
        if check["status"] == "block"
    }
    assert "tool_whitelist_known_tools" in blocked_checks
    assert "llm_provider_catalog" in blocked_checks
    assert "missing_tool" in blocked_checks["tool_whitelist_known_tools"]["message"]


def test_issue200_acceptance_gate_cli_returns_nonzero_on_block(tmp_path: Path) -> None:
    config = load_json(Path("configs/experiments/issue199_benchmark_platform_adapters.json"))
    broken_config = json.loads(json.dumps(config))
    broken_config["tool_whitelist"]["high_cost_tool_ids"].append("not_in_allowlist")

    config_path = tmp_path / "issue200-broken-config.json"
    config_path.write_text(json.dumps(broken_config, ensure_ascii=False), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/benchmarks/run_issue200_acceptance_gate.py",
            "--config",
            str(config_path),
            "--output-root",
            str(tmp_path / "out"),
            "--freeze-id",
            "issue200-cli-block",
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    assert result.returncode == 1
    assert "[issue200] overall_status=block" in result.stdout
    assert "tool_whitelist_known_tools" in result.stdout
    assert "[issue200] gate_summary=" in result.stdout
