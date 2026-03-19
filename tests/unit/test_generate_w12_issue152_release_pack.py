from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path


def _load_module():
    module_path = Path(__file__).resolve().parents[2] / "scripts" / "generate_w12_issue152_release_pack.py"
    spec = importlib.util.spec_from_file_location("issue152_pack", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_issue152_pack_reports_release_blockers(tmp_path: Path) -> None:
    module = _load_module()

    train_dir = tmp_path / "train_run"
    train_dir.mkdir()
    (train_dir / "training_summary.json").write_text("{}", encoding="utf-8")
    training_summary = tmp_path / "training_summary.json"
    training_summary.write_text(
        json.dumps(
            {
                "candidate_version": "v0.3.0-rc1",
                "dataset_version": "dataset-v1",
                "paths": {"run_dir": str(train_dir), "model_card": str(tmp_path / "model_card.md")},
                "reproducibility": {"command": "run-train"},
                "training": {"base_model": "tiny-gpt2", "qlora_enabled": True},
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "model_card.md").write_text("# card\n", encoding="utf-8")

    release_benchmark = tmp_path / "release_benchmark.json"
    release_benchmark.write_text(
        json.dumps(
            {
                "release_blocked": True,
                "gate_checks": [
                    {"metric": "schema_valid_rate", "candidate_value": 1.0, "passed": True},
                    {"metric": "patch_minimality_hit_rate", "candidate_value": None, "passed": False},
                ],
            }
        ),
        encoding="utf-8",
    )

    runtime_config = tmp_path / "runtime_fallback.json"
    runtime_config.write_text(
        json.dumps(
            {
                "runtime_fallback": {"force_external_only": False},
                "release_defaults": {"circuit_breaker_env": "PLANNER_FORCE_EXTERNAL_FALLBACK"},
            }
        ),
        encoding="utf-8",
    )
    runtime_runbook = tmp_path / "runtime.md"
    runtime_runbook.write_text("# runtime\n", encoding="utf-8")

    demo_summary = tmp_path / "demo_summary.json"
    demo_summary.write_text(
        json.dumps(
            {
                "scenarios": ["six_stage_hitl_replay"],
                "checks": {"e2e_flow_reaches_done": True},
            }
        ),
        encoding="utf-8",
    )
    demo_validation = tmp_path / "release_validation.md"
    demo_validation.write_text("# validation\n", encoding="utf-8")

    vertical_report = tmp_path / "vertical_report.md"
    vertical_report.write_text("# vertical\n", encoding="utf-8")
    vertical_summary = tmp_path / "vertical_summary.csv"
    vertical_summary.write_text("group_id,runs\nA0,12\n", encoding="utf-8")
    governance_summary = tmp_path / "governance_summary.json"
    governance_summary.write_text(
        json.dumps(
            {
                "global": {
                    "failure_traceable_rate": 1.0,
                    "waiting_chain_complete_rate": 0.0,
                    "replay_success_rate": 0.0,
                }
            }
        ),
        encoding="utf-8",
    )
    governance_report = tmp_path / "governance_report.md"
    governance_report.write_text("# gov\n", encoding="utf-8")
    midterm_chapter = tmp_path / "midterm_chapter.md"
    midterm_chapter.write_text("# chapter\n", encoding="utf-8")
    figure_index = tmp_path / "figure_index.csv"
    figure_index.write_text("artifact_id,status\nfigure-1,ready\n", encoding="utf-8")

    result = module.build_issue152_pack(
        training_summary_path=training_summary,
        release_benchmark_path=release_benchmark,
        runtime_fallback_config_path=runtime_config,
        runtime_runbook_path=runtime_runbook,
        demo_summary_path=demo_summary,
        demo_validation_path=demo_validation,
        vertical_report_path=vertical_report,
        vertical_summary_path=vertical_summary,
        governance_summary_path=governance_summary,
        governance_report_path=governance_report,
        midterm_chapter_path=midterm_chapter,
        figure_index_path=figure_index,
        output_dir=tmp_path / "out",
    )

    report_text = result["report"].read_text(encoding="utf-8")
    draft_text = result["release_draft"].read_text(encoding="utf-8")
    artifact_rows = list(csv.DictReader(result["artifact_index"].open("r", encoding="utf-8")))

    assert "patch_minimality_hit_rate" in report_text
    assert "release_blocked: `yes`" in draft_text
    assert any(row["issue"] == "172" and row["exists"] == "no" for row in artifact_rows)
