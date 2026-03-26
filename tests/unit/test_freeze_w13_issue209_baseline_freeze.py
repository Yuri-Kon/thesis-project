from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from src.infra.w12_vertical_experiment import DEFAULT_HIGH_COST_RULES, normalize_high_cost_rules


def _load_module():
    module_path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "freeze_w13_issue209_baseline_freeze.py"
    )
    spec = importlib.util.spec_from_file_location("issue209_freeze", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_normalize_high_cost_rules_uses_default_shape() -> None:
    rules = normalize_high_cost_rules(None)
    assert rules == DEFAULT_HIGH_COST_RULES
    assert rules[0]["rule_id"] == "structure_mapping"


def test_issue209_freeze_script_writes_manifest(tmp_path: Path) -> None:
    module = _load_module()
    source_task_config_path = tmp_path / "source_tasks.json"

    source_task_config_path.write_text(
        json.dumps(
            {
                "tasks": [
                    {"task_key": "enzyme_like_fold"},
                    {"task_key": "binding_scaffold"},
                    {"task_key": "high_solubility"},
                    {"task_key": "secondary_balance"},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    manifest, output_dir = module.build_issue209_baseline_freeze(
        config={
            "freeze_id": "issue209-test-freeze",
            "output_root": str(tmp_path / "out"),
            "task_set_version": "issue209-taskset-v1",
            "difficulty_scheme_version": "issue209-difficulty-v1",
            "source_task_config_path": str(source_task_config_path),
            "tasks": [
                {"task_key": "enzyme_like_fold", "difficulty": "medium"},
                {"task_key": "binding_scaffold", "difficulty": "hard"},
                {"task_key": "high_solubility", "difficulty": "easy"},
                {"task_key": "secondary_balance", "difficulty": "medium"},
            ],
            "baselines": [
                {"id": "static_top1", "label": "静态 Top-1"},
                {"id": "fixed_threshold_gate", "label": "固定阈值 gate"},
                {"id": "dynamic_no_belief_state", "label": "动态无 belief-state"},
                {"id": "lite_belief_state", "label": "Lite belief-state"},
            ],
            "metrics_contract": {
                "effect": ["success_rate"],
                "cost": ["duration_ms_mean", "high_cost_call_mean"],
                "recovery": ["patch_events_mean"],
                "governance": ["failure_traceable_rate"],
                "task_stratification_key": "difficulty",
            },
        }
    )

    assert manifest["difficulty_distribution"] == {"easy": 1, "hard": 1, "medium": 2}
    assert manifest["source_references"]["source_alignment"]["aligned"] is True
    assert (output_dir / "baseline_freeze_manifest.json").exists()
    assert (output_dir / "baseline_freeze_report.md").exists()
