from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from src.adapters.autodock_vina_adapter import (
    AutoDockVinaAdapter,
    parse_autodock_vina_log,
)
from src.adapters.foldseek_adapter import FoldseekAdapter, parse_foldseek_tabular
from src.adapters.interproscan_adapter import (
    InterProScanAdapter,
    parse_interproscan_tsv,
)
from src.adapters.mda_analysis_adapter import MDAnalysisAdapter
from src.adapters.objective_ranker_adapter import ObjectiveRankerAdapter


def test_parse_foldseek_tabular_extracts_structure_hits() -> None:
    hits = parse_foldseek_tabular("q1\tt1\t1e-8\t240\t0.81\t0.72\t120\t130\t140\n")

    assert hits[0]["query_id"] == "q1"
    assert hits[0]["tm_score"] == "0.81"
    assert hits[0]["target_length"] == "140"


def test_parse_interproscan_tsv_extracts_terms() -> None:
    terms = parse_interproscan_tsv(
        "q1\tmd5\t100\tPfam\tPF00001\tKinase\t1\t90\t42.0\tT\t2026-04-15\tIPR000001\tKinase domain\tGO:0004672|GO:0005524\tpath:ko04110\n"
    )

    assert terms[0]["analysis"] == "Pfam"
    assert terms[0]["go_terms"] == ["GO:0004672", "GO:0005524"]


def test_parse_autodock_vina_log_extracts_pose_table() -> None:
    poses = parse_autodock_vina_log(
        "mode |   affinity | dist from best mode\n"
        "-----+------------+---------------------\n"
        "   1      -7.5      0.000      0.000\n"
        "   2      -6.8      2.100      3.500\n"
    )

    assert poses[0]["mode"] == 1
    assert poses[0]["affinity"] == -7.5
    assert poses[1]["rmsd_ub"] == 3.5


def test_objective_ranker_scores_candidates_with_proxy_signals() -> None:
    adapter = ObjectiveRankerAdapter()

    outputs, metrics = adapter.run_local(
        {
            "candidates": [
                {
                    "candidate_id": "cand_a",
                    "plddt": 88.0,
                    "pass_fail": True,
                    "similarity_hits": [{"identity": 0.2}],
                    "annotation_summary": {"term_count": 4},
                    "stability_metrics": {"radius_of_gyration": 12.0, "coordinate_span": 40.0},
                    "binding_score": -8.0,
                },
                {
                    "candidate_id": "cand_b",
                    "plddt": 65.0,
                    "pass_fail": False,
                    "similarity_hits": [{"identity": 0.75}],
                },
            ]
        }
    )

    assert outputs["default_recommendation"] == "cand_a"
    assert outputs["top_k"][0]["objective_score"] >= outputs["top_k"][1]["objective_score"]
    assert metrics["requirement2"]["capability_id"] == "objective_scoring"


def test_foldseek_adapter_runs_local_and_emits_structure_similarity_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_runner(cmd: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        Path(cmd[4]).write_text(
            "query_1\thitA\t1e-8\t220\t0.79\t0.71\t110\t120\t135\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr("src.adapters.foldseek_adapter.shutil.which", lambda _: "/usr/bin/foldseek")
    adapter = FoldseekAdapter(runner=fake_runner)

    outputs, metrics = adapter.run_local(
        {"pdb_path": "/tmp/query.pdb", "database_path": "/db/foldseek"}
    )

    assert outputs["capability_id"] == "structure_similarity_search"
    assert outputs["structure_similarity_hits"][0]["tm_score"] == 0.79
    assert metrics["requirement2"]["capability_id"] == "structure_similarity_search"


def test_interproscan_adapter_runs_local_and_emits_function_terms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_runner(cmd: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        output_path = Path(cmd[cmd.index("-o") + 1])
        output_path.write_text(
            "query_1\tmd5\t100\tPfam\tPF00001\tKinase\t1\t90\t42.0\tT\t2026-04-15\tIPR000001\tKinase domain\tGO:0004672\t\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(
        "src.adapters.interproscan_adapter.shutil.which",
        lambda _: "/usr/bin/interproscan.sh",
    )
    adapter = InterProScanAdapter(runner=fake_runner)

    outputs, metrics = adapter.run_local({"sequence": "ACDEFGHIK"})

    assert outputs["capability_id"] == "function_annotation"
    assert outputs["annotation_summary"]["term_count"] == 1
    assert metrics["term_count"] == 1


def test_mda_analysis_adapter_generates_stability_proxy_metrics(tmp_path: Path) -> None:
    pdb_path = tmp_path / "input.pdb"
    pdb_path.write_text(
        "ATOM      1  CA  ALA A   1       1.000   0.000   0.000  1.00 77.00           C\n"
        "ATOM      2  CA  GLY A   2       3.000   0.000   0.000  1.00 77.00           C\n"
        "ATOM      3  CA  SER A   3       5.000   0.000   0.000  1.00 77.00           C\n"
        "END\n",
        encoding="utf-8",
    )
    adapter = MDAnalysisAdapter()

    outputs, metrics = adapter.run_local({"pdb_path": str(pdb_path)})

    assert outputs["capability_id"] == "stability_simulation"
    assert outputs["stability_metrics"]["atom_count"] == 3
    assert metrics["frame_count"] == 1


def test_autodock_vina_adapter_runs_local_and_extracts_binding_score(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_runner(cmd: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        out_path = Path(cmd[cmd.index("--out") + 1])
        log_path = Path(cmd[cmd.index("--log") + 1])
        out_path.write_text("MODEL 1\nENDMDL\n", encoding="utf-8")
        log_path.write_text(
            "mode |   affinity | dist from best mode\n"
            "-----+------------+---------------------\n"
            "   1      -7.5      0.000      0.000\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(
        "src.adapters.autodock_vina_adapter.shutil.which",
        lambda _: "/usr/bin/vina",
    )
    adapter = AutoDockVinaAdapter(runner=fake_runner)

    outputs, metrics = adapter.run_local(
        {"receptor_path": "/tmp/receptor.pdbqt", "ligand_path": "/tmp/ligand.pdbqt"}
    )

    assert outputs["capability_id"] == "docking_scoring"
    assert outputs["binding_score"] == -7.5
    assert metrics["pose_count"] == 1
