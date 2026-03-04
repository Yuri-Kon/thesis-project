from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.infra.runtime_init import initialize_runtime, resolve_runtime_paths
from src.kg.kg_client import ToolKGError


@pytest.mark.unit
def test_resolve_runtime_paths_defaults():
    paths = resolve_runtime_paths()

    assert paths.kg_path == Path("src/kg/protein_tool_kg.json")
    assert paths.output_dir == Path("output")
    assert paths.data_dir == Path("data")
    assert paths.log_dir == Path("data/logs")
    assert paths.snapshot_dir == Path("data/snapshots")


@pytest.mark.unit
def test_initialize_runtime_creates_dirs_and_counts_tools(tmp_path: Path):
    kg_path = tmp_path / "kg.json"
    kg_path.write_text(json.dumps({"tools": [{"id": "dummy_tool"}]}), encoding="utf-8")

    data_dir = tmp_path / "data"
    output_dir = tmp_path / "output"
    result = initialize_runtime(
        kg_path=kg_path,
        data_dir=data_dir,
        output_dir=output_dir,
        log_dir=data_dir / "logs",
        snapshot_dir=data_dir / "snapshots",
    )

    assert result.tool_count == 1
    assert result.paths.output_dir.exists()
    assert result.paths.log_dir.exists()
    assert result.paths.snapshot_dir.exists()


@pytest.mark.unit
def test_initialize_runtime_rejects_invalid_kg_tools(tmp_path: Path):
    kg_path = tmp_path / "kg.json"
    kg_path.write_text(json.dumps({"tools": {"id": "invalid"}}), encoding="utf-8")

    with pytest.raises(ToolKGError):
        initialize_runtime(kg_path=kg_path)
