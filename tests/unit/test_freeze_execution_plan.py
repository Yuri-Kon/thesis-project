from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


SCRIPT_PATH = Path("scripts/freeze_execution_plan.py")


def _load_script_module():
    spec = importlib.util.spec_from_file_location("freeze_execution_plan", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")


def _base_config() -> dict:
    return {
        "issue_id": 169,
        "plan_id": "unit-plan",
        "execution_order_policy": ["Data", "Vertical", "Horizontal", "Governance", "Report"],
        "issues": [
            {"number": 169, "title": "plan", "track": "Planning", "start": "2026-03-16", "end": "2026-03-16", "hard_blocked_by": [], "soft_sync": [170]},
            {"number": 170, "title": "data", "track": "Data", "start": "2026-03-16", "end": "2026-03-18", "hard_blocked_by": [169], "soft_sync": [171, 172, 173]},
            {"number": 171, "title": "vertical", "track": "Vertical", "start": "2026-03-18", "end": "2026-03-20", "hard_blocked_by": [170], "soft_sync": [172]},
            {"number": 172, "title": "horizontal", "track": "Horizontal", "start": "2026-03-19", "end": "2026-03-20", "hard_blocked_by": [170], "soft_sync": [171]},
            {"number": 173, "title": "governance", "track": "Governance", "start": "2026-03-20", "end": "2026-03-21", "hard_blocked_by": [170, 144], "soft_sync": [171, 172]},
            {"number": 174, "title": "report", "track": "Report", "start": "2026-03-21", "end": "2026-03-22", "hard_blocked_by": [171, 172, 173], "soft_sync": [152]},
        ],
    }


@pytest.mark.unit
def test_freeze_issue169_plan_outputs_index_and_checks(tmp_path: Path) -> None:
    module = _load_script_module()

    config_path = tmp_path / "plan.json"
    output_root = tmp_path / "out"
    _write_json(config_path, _base_config())

    result = module.freeze_issue169_plan(
        config_path=config_path,
        output_root=output_root,
        plan_id="unit-plan",
    )

    assert result["validations"]["has_time_windows"] is True
    assert result["validations"]["dependency_cycle_free"] is True
    assert result["validations"]["data_issue_on_critical_front"] is True
    assert result["topological_order"][:2] == [169, 170]
    assert result["critical_path"]["issues"][0] == 169
    assert result["critical_path"]["issues"][-1] == 174

    plan_dir = Path(result["artifacts"]["output_dir"])
    assert (plan_dir / "execution_plan_index.json").exists()
    assert (plan_dir / "execution_plan_index.md").exists()
    assert any(pair["issues"] == [171, 172] for pair in result["parallel_items"])


@pytest.mark.unit
def test_freeze_issue169_plan_detects_cycle(tmp_path: Path) -> None:
    module = _load_script_module()
    config = _base_config()
    for item in config["issues"]:
        if item["number"] == 169:
            item["hard_blocked_by"] = [174]
            break

    config_path = tmp_path / "plan_cycle.json"
    _write_json(config_path, config)

    with pytest.raises(ValueError, match="dependency cycle detected"):
        module.freeze_issue169_plan(
            config_path=config_path,
            output_root=tmp_path / "out",
            plan_id="unit-plan-cycle",
        )
