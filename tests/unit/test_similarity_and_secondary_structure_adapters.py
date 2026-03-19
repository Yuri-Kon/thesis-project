from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from src.adapters.blastp_adapter import BlastPAdapter, parse_blastp_tabular
from src.adapters.dssp_adapter import DSSPAdapter, parse_dssp_output
from src.adapters.mmseqs2_adapter import MMseqs2Adapter, parse_mmseqs_tabular
from src.workflow.errors import StepRunError


def test_parse_mmseqs_tabular_normalizes_hits() -> None:
    hits = parse_mmseqs_tabular(
        "q1\ttargetA\t95.5\t90\t0\t0\t1\t90\t3\t92\t1e-20\t180\t100\t120\n"
    )

    assert hits[0]["query_id"] == "q1"
    assert hits[0]["target_id"] == "targetA"
    assert hits[0]["identity"] == "95.5"


def test_parse_blastp_tabular_normalizes_hits() -> None:
    hits = parse_blastp_tabular(
        "q1\ttargetB\t88.0\t80\t0\t0\t5\t84\t2\t81\t2e-10\t150\t100\t110\n"
    )

    assert hits[0]["query_start"] == "5"
    assert hits[0]["target_length"] == "110"


def test_parse_dssp_output_extracts_q3_q8_rows() -> None:
    text = (
        "HEADER\n"
        "  #  RESIDUE AA STRUCTURE BP1 BP2  ACC\n"
        "    1    1 A A  H                  0   0\n"
        "    2    2 A V  E                  0   0\n"
        "    3    3 A G                     0   0\n"
    )

    rows = parse_dssp_output(text)

    assert [row["q8"] for row in rows] == ["H", "E", "C"]
    assert [row["q3"] for row in rows] == ["H", "E", "C"]


def test_mmseqs2_adapter_runs_local_and_emits_unified_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_runner(cmd: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        Path(cmd[4]).write_text(
            "query_1\thit1\t97.0\t90\t0\t0\t1\t90\t1\t90\t1e-30\t210\t100\t100\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr("src.adapters.mmseqs2_adapter.shutil.which", lambda _: "/usr/bin/mmseqs")
    adapter = MMseqs2Adapter(runner=fake_runner)

    outputs, metrics = adapter.run_local(
        {"sequence": "ACDEFG", "database_path": "/db/mmseqs", "query_id": "query_1"}
    )

    assert outputs["capability_id"] == "sequence_similarity_search"
    assert outputs["io_type"] == "sequence_to_similarity_hits"
    assert outputs["similarity_hits"][0]["coverage"] == 0.9
    assert metrics["requirement2"]["capability_id"] == "sequence_similarity_search"


def test_blastp_adapter_runs_local_and_emits_unified_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_runner(cmd: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        output_path = Path(cmd[cmd.index("-out") + 1])
        output_path.write_text(
            "query_1\thit2\t89.0\t75\t0\t0\t1\t75\t4\t78\t1e-12\t140\t100\t120\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr("src.adapters.blastp_adapter.shutil.which", lambda _: "/usr/bin/blastp")
    adapter = BlastPAdapter(runner=fake_runner)

    outputs, metrics = adapter.run_local(
        {"sequence": "ACDEFG", "database_path": "/db/blast", "query_id": "query_1"}
    )

    assert outputs["similarity_hits"][0]["target_id"] == "hit2"
    assert outputs["similarity_hits"][0]["coverage"] == 0.75
    assert metrics["hit_count"] == 1


def test_dssp_adapter_runs_local_and_outputs_qc_metrics(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    pdb_path = tmp_path / "input.pdb"
    pdb_path.write_text("ATOM\n", encoding="utf-8")

    def fake_runner(cmd: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        output_path = Path(cmd[-1])
        output_path.write_text(
            "HEADER\n"
            "  #  RESIDUE AA STRUCTURE BP1 BP2  ACC\n"
            "    1    1 A A  H                  0   0\n"
            "    2    2 A V  E                  0   0\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr("src.adapters.dssp_adapter.shutil.which", lambda _: "/usr/bin/mkdssp")
    adapter = DSSPAdapter(runner=fake_runner)

    outputs, metrics = adapter.run_local({"pdb_path": str(pdb_path), "sequence": "AV"})

    assert outputs["io_type"] == "sequence_structure_to_qc_metrics"
    assert outputs["qc_metrics"]["secondary_structure_summary"]["q3_counts"] == {"H": 1, "E": 1}
    assert metrics["requirement2"]["capability_id"] == "quality_qc"
    assert metrics["command"][:3] == ["mkdssp", "--output-format", "dssp"]


def test_adapters_raise_when_binary_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.adapters.mmseqs2_adapter.shutil.which", lambda _: None)
    adapter = MMseqs2Adapter()

    with pytest.raises(StepRunError, match="not installed"):
        adapter.run_local({"sequence": "ACDEFG", "database_path": "/db/mmseqs"})
