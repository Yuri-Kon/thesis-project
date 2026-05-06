from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest


SCRIPT_PATH = Path("scripts/run_w16_issue172_horizontal_experiment.py")


def _load_script_module():
    spec = importlib.util.spec_from_file_location(
        "run_w16_issue172_horizontal_experiment",
        SCRIPT_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.unit
def test_main_auto_evaluates_horizontal_outputs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_script_module()
    manifest = {"run_id": "issue172-run", "freeze_id": "freeze", "runs": [{}]}
    run_dir = tmp_path / "issue172-run"
    run_dir.mkdir(parents=True, exist_ok=True)
    captured: dict[str, object] = {}

    monkeypatch.setattr(module, "load_json", lambda _: {"issue_id": 172})

    def fake_build_issue172_run_manifest(**kwargs):
        captured["build_kwargs"] = kwargs
        return manifest, run_dir

    def fake_evaluate_issue172_run_manifest(**kwargs):
        captured["evaluate_kwargs"] = kwargs
        return {"run_level_results": [{}, {}]}

    monkeypatch.setattr(module, "build_issue172_run_manifest", fake_build_issue172_run_manifest)
    monkeypatch.setattr(
        module,
        "evaluate_issue172_run_manifest",
        fake_evaluate_issue172_run_manifest,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_w16_issue172_horizontal_experiment.py",
            "--config",
            str(tmp_path / "config.json"),
            "--run-id",
            "issue172-run",
        ],
    )

    assert module.main() == 0
    assert captured["evaluate_kwargs"] == {
        "manifest": manifest,
        "output_dir": run_dir,
        "kg_path": module.DEFAULT_ISSUE172_KG_PATH,
        "bootstrap_iterations": 10000,
        "seed": 20260420,
        "internal_summary_path": None,
    }

    stdout = capsys.readouterr().out
    assert "[issue172] evaluated_runs=2" in stdout
    assert str(run_dir / "validation_summary.json") in stdout


@pytest.mark.unit
def test_main_skips_evaluation_when_no_evaluate(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_script_module()
    run_dir = tmp_path / "issue172-run"
    run_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(module, "load_json", lambda _: {"issue_id": 172})
    monkeypatch.setattr(
        module,
        "build_issue172_run_manifest",
        lambda **_: ({"run_id": "issue172-run", "freeze_id": "freeze", "runs": []}, run_dir),
    )

    def fail_evaluate_issue172_run_manifest(**kwargs):
        raise AssertionError(f"unexpected evaluation call: {kwargs}")

    monkeypatch.setattr(
        module,
        "evaluate_issue172_run_manifest",
        fail_evaluate_issue172_run_manifest,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_w16_issue172_horizontal_experiment.py",
            "--config",
            str(tmp_path / "config.json"),
            "--run-id",
            "issue172-run",
            "--no-evaluate",
        ],
    )

    assert module.main() == 0


@pytest.mark.unit
def test_main_temporarily_sets_horizontal_planner_provider(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_script_module()
    run_dir = tmp_path / "issue172-run"
    run_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("PLANNER_LLM_PROVIDER", "original-provider")
    monkeypatch.setattr(module, "load_json", lambda _: {"issue_id": 172})

    captured: dict[str, str | None] = {}

    def fake_build_issue172_run_manifest(**_kwargs):
        captured["planner_provider"] = os.getenv("PLANNER_LLM_PROVIDER")
        return ({"run_id": "issue172-run", "freeze_id": "freeze", "runs": []}, run_dir)

    monkeypatch.setattr(module, "build_issue172_run_manifest", fake_build_issue172_run_manifest)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_w16_issue172_horizontal_experiment.py",
            "--config",
            str(tmp_path / "config.json"),
            "--run-id",
            "issue172-run",
            "--no-evaluate",
            "--planner-provider",
            "glm-5",
        ],
    )

    assert module.main() == 0
    assert captured["planner_provider"] == "glm-5"
    assert os.getenv("PLANNER_LLM_PROVIDER") == "original-provider"
    assert "[issue172] planner_provider=glm-5" in capsys.readouterr().out
