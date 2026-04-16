from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.openfold3_rest_server import openfold3_runner as runner


def test_build_predict_command_prefers_hyphen_options_and_skips_missing_ckpt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    help_text = """
    Usage: run_openfold predict [OPTIONS]
      --query-json FILE
      --inference-ckpt-path PATH
      --output-dir PATH
    """
    monkeypatch.setattr(runner, "_get_predict_help_text", lambda _bin: help_text)

    model_dir = str(tmp_path / "not-exists")
    command, meta = runner._build_predict_command(
        query_json_path=tmp_path / "query.json",
        output_dir=tmp_path / "artifacts",
        model_dir=model_dir,
        predict_bin="run_openfold",
    )

    assert command[0:2] == ["run_openfold", "predict"]
    assert any(part.startswith("--query-json=") for part in command)
    assert any(part.startswith("--output-dir=") for part in command)
    assert not any(part.startswith("--inference-ckpt-path=") for part in command)
    assert meta["model_arg"] == "none"


def test_build_predict_command_supports_legacy_underscore_flags(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    help_text = """
    Usage: run_openfold predict [OPTIONS]
      --query_json FILE
      --output_dir PATH
      --model_dir PATH
    """
    monkeypatch.setattr(runner, "_get_predict_help_text", lambda _bin: help_text)

    command, meta = runner._build_predict_command(
        query_json_path=tmp_path / "query.json",
        output_dir=tmp_path / "artifacts",
        model_dir="/models/openfold3",
        predict_bin="run_openfold",
    )

    assert any(part.startswith("--query_json=") for part in command)
    assert any(part.startswith("--output_dir=") for part in command)
    assert any(part.startswith("--model_dir=") for part in command)
    assert meta["model_arg"] == "--model_dir"


def test_build_predict_command_appends_runner_yaml_from_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    help_text = """
    Usage: run_openfold predict [OPTIONS]
      --query-json FILE
      --output-dir PATH
      --runner-yaml FILE
    """
    runner_yaml = tmp_path / "runner.yml"
    runner_yaml.write_text("model_update: {}\n", encoding="utf-8")
    monkeypatch.setattr(runner, "_get_predict_help_text", lambda _bin: help_text)
    monkeypatch.setenv("OPENFOLD3_RUNNER_YAML", str(runner_yaml))

    command, meta = runner._build_predict_command(
        query_json_path=tmp_path / "query.json",
        output_dir=tmp_path / "artifacts",
        model_dir="/models/openfold3",
        predict_bin="run_openfold",
    )

    assert any(part == f"--runner-yaml={runner_yaml}" for part in command)
    assert meta["runner_yaml_arg"] == "--runner-yaml"
    assert meta["runner_yaml_path"] == str(runner_yaml)


def test_build_predict_command_rejects_missing_runner_yaml(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    help_text = """
    Usage: run_openfold predict [OPTIONS]
      --query-json FILE
      --output-dir PATH
      --runner-yaml FILE
    """
    monkeypatch.setattr(runner, "_get_predict_help_text", lambda _bin: help_text)
    monkeypatch.setenv("OPENFOLD3_RUNNER_YAML", str(tmp_path / "missing.yml"))

    with pytest.raises(RuntimeError, match="OPENFOLD3_RUNNER_YAML"):
        runner._build_predict_command(
            query_json_path=tmp_path / "query.json",
            output_dir=tmp_path / "artifacts",
            model_dir="/models/openfold3",
            predict_bin="run_openfold",
        )


def test_prepare_query_json_uses_queries_format_when_runtime_requires_queries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENFOLD3_QUERY_FORMAT", raising=False)
    monkeypatch.setattr(runner, "_detect_runtime_query_format", lambda: "queries")

    query_path, query_format = runner._prepare_query_json(
        {"sequence": "ACDEFG", "request_id": "req_a"},
        job_path=tmp_path,
    )

    payload = json.loads(query_path.read_text(encoding="utf-8"))
    assert query_format == "queries"
    assert "queries" in payload
    assert "req_a" in payload["queries"]
    assert payload["queries"]["req_a"]["chains"][0]["sequence"] == "ACDEFG"


def test_prepare_query_json_respects_env_override_inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENFOLD3_QUERY_FORMAT", "inputs")
    monkeypatch.setattr(runner, "_detect_runtime_query_format", lambda: "queries")

    query_path, query_format = runner._prepare_query_json(
        {"sequence": "ACDEFG", "request_id": "req_b"},
        job_path=tmp_path,
    )

    payload = json.loads(query_path.read_text(encoding="utf-8"))
    assert query_format == "inputs"
    assert "inputs" in payload
    assert payload["inputs"][0]["molecules"][0]["sequence"] == "ACDEFG"


def test_find_structure_file_supports_nested_artifact_paths(tmp_path: Path) -> None:
    nested = tmp_path / "openfold3_request" / "seed_42"
    nested.mkdir(parents=True, exist_ok=True)
    model_path = nested / "prediction_model.cif"
    model_path.write_text("data_test\n", encoding="utf-8")

    found = runner._find_structure_file(tmp_path)

    assert found == model_path


def test_extract_plddt_supports_nested_artifact_paths(tmp_path: Path) -> None:
    nested = tmp_path / "openfold3_request" / "seed_42"
    nested.mkdir(parents=True, exist_ok=True)
    (nested / "prediction_confidences.json").write_text(
        json.dumps({"plddt": 81.25}),
        encoding="utf-8",
    )

    plddt = runner._extract_plddt_from_artifacts(tmp_path)

    assert plddt == pytest.approx(81.25)


def test_resolve_predict_bin_prefers_which(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runner.shutil, "which", lambda _name: "/usr/bin/run_openfold")
    resolved = runner._resolve_predict_bin("run_openfold")
    assert resolved == "/usr/bin/run_openfold"


def test_resolve_predict_bin_falls_back_to_python_sibling(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    py = bin_dir / "python"
    py.write_text("", encoding="utf-8")
    openfold = bin_dir / "run_openfold"
    openfold.write_text("", encoding="utf-8")

    monkeypatch.setattr(runner.shutil, "which", lambda _name: None)
    monkeypatch.setattr(runner.sys, "executable", str(py))
    resolved = runner._resolve_predict_bin("run_openfold")
    assert resolved == str(openfold)


def test_resolve_predict_bin_raises_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runner.shutil, "which", lambda _name: None)
    monkeypatch.setattr(runner.sys, "executable", "/tmp/nowhere/python")
    with pytest.raises(RuntimeError):
        runner._resolve_predict_bin("run_openfold")
