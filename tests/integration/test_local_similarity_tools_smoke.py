from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.adapters.blastp_adapter import BlastPAdapter
from src.adapters.dssp_adapter import DSSPAdapter
from src.adapters.mmseqs2_adapter import MMseqs2Adapter


def _require_env(name: str) -> str:
    value = str(os.getenv(name, "")).strip()
    if not value:
        pytest.skip(f"{name} not set")
    return value


def _require_file_env(name: str) -> str:
    value = _require_env(name)
    if not Path(value).exists():
        pytest.skip(f"{name} path does not exist: {value}")
    return value


@pytest.mark.integration
def test_local_mmseqs2_smoke() -> None:
    sequence = _require_env("LOCAL_QUERY_SEQUENCE")
    database_path = _require_env("LOCAL_MMSEQS_DB")

    adapter = MMseqs2Adapter()
    outputs, metrics = adapter.run_local(
        {
            "sequence": sequence,
            "database_path": database_path,
            "query_id": "local_smoke_query",
            "max_seqs": 5,
        }
    )

    assert outputs["io_type"] == "sequence_to_similarity_hits"
    assert outputs["capability_id"] == "sequence_similarity_search"
    assert outputs["hit_count"] >= 1
    assert outputs["similarity_hits"]
    top_hit = outputs["similarity_hits"][0]
    assert "identity" in top_hit
    assert "coverage" in top_hit
    assert "evalue" in top_hit
    assert metrics["requirement2"]["capability_id"] == "sequence_similarity_search"


@pytest.mark.integration
def test_local_blastp_smoke() -> None:
    sequence = _require_env("LOCAL_QUERY_SEQUENCE")
    database_path = _require_env("LOCAL_BLAST_DB")

    adapter = BlastPAdapter()
    outputs, metrics = adapter.run_local(
        {
            "sequence": sequence,
            "database_path": database_path,
            "query_id": "local_smoke_query",
            "max_target_seqs": 5,
        }
    )

    assert outputs["io_type"] == "sequence_to_similarity_hits"
    assert outputs["capability_id"] == "sequence_similarity_search"
    assert outputs["hit_count"] >= 1
    assert outputs["similarity_hits"]
    top_hit = outputs["similarity_hits"][0]
    assert "identity" in top_hit
    assert "coverage" in top_hit
    assert "evalue" in top_hit
    assert metrics["requirement2"]["capability_id"] == "sequence_similarity_search"


@pytest.mark.integration
def test_local_dssp_smoke() -> None:
    pdb_path = _require_file_env("LOCAL_DSSP_PDB")
    sequence = str(os.getenv("LOCAL_DSSP_SEQUENCE", "")).strip() or None

    adapter = DSSPAdapter()
    payload = {"pdb_path": pdb_path}
    if sequence:
        payload["sequence"] = sequence
    outputs, metrics = adapter.run_local(payload)

    assert outputs["io_type"] == "sequence_structure_to_qc_metrics"
    assert outputs["secondary_structure"]
    assert outputs["secondary_structure_summary"]["residue_count"] >= 1
    assert "q3_counts" in outputs["secondary_structure_summary"]
    assert metrics["requirement2"]["capability_id"] == "quality_qc"
