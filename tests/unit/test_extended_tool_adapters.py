from __future__ import annotations

import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import cast

import httpx
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
from src.workflow.errors import StepRunError


def _resolved_binary(path: str):
    def fake_which(_: str) -> str:
        return path

    return fake_which


class FakeFoldseekApiClient:
    def __init__(self) -> None:
        self.posted_databases: list[str] = []
        self.get_urls: list[str] = []

    def _response(self, status_code: int, *, json: object, url: str) -> httpx.Response:
        return httpx.Response(
            status_code,
            json=json,
            request=httpx.Request("GET", url),
        )

    def get(self, url: str, *, timeout: float) -> httpx.Response:
        _ = timeout
        self.get_urls.append(url)
        if url.endswith("/databases"):
            return self._response(
                200,
                json={
                    "databases": [
                        {
                            "name": "AlphaFold/Swiss-Prot",
                            "path": "afdb-swissprot",
                            "default": True,
                        }
                    ]
                },
                url=url,
            )
        if url.endswith("/ticket/ticket_123"):
            return self._response(
                200,
                json={"id": "ticket_123", "status": "COMPLETE"},
                url=url,
            )
        if url.endswith("/result/ticket_123/0"):
            return self._response(
                200,
                json={
                    "queries": [{"header": "query_1", "sequence": ""}],
                    "results": [
                        {
                            "db": "afdb-swissprot",
                            "alignments": [
                                [
                                    {
                                        "query": "query_1",
                                        "target": "hitA",
                                        "eval": "1e-8",
                                        "score": 220,
                                        "tmscore": 0.79,
                                        "alnLength": 110,
                                        "qLen": 120,
                                        "dbLen": 135,
                                    }
                                ]
                            ],
                        }
                    ],
                },
                url=url,
            )
        return self._response(404, json={"error": "not found"}, url=url)

    def post(
        self,
        url: str,
        *,
        data: Mapping[str, str | list[str]],
        files: Mapping[str, tuple[str, bytes, str]],
        timeout: float,
    ) -> httpx.Response:
        _ = timeout
        assert url.endswith("/ticket")
        assert files["q"][1] == b"ATOM\n"
        raw_databases = data["database[]"]
        assert isinstance(raw_databases, list)
        self.posted_databases = raw_databases
        return httpx.Response(
            200,
            json={"id": "ticket_123", "status": "PENDING"},
            request=httpx.Request("POST", url),
        )


def test_parse_foldseek_tabular_extracts_structure_hits() -> None:
    hits = parse_foldseek_tabular("q1\tt1\t1e-8\t240\t0.81\t0.80\t0.78\t0.72\t120\t130\t140\t0.91\n")

    assert hits[0]["query_id"] == "q1"
    assert hits[0]["tm_score"] == "0.81"
    assert hits[0]["target_length"] == "140"
    assert hits[0]["probability"] == "0.91"


def test_parse_interproscan_tsv_extracts_terms() -> None:
    terms = parse_interproscan_tsv(
        "q1\tmd5\t100\tPfam\tPF00001\tKinase\t1\t90\t42.0\tT\t2026-04-15\tIPR000001\tKinase domain\tGO:0004672|GO:0005524\tpath:ko04110\n"
    )

    assert terms[0]["analysis"] == "Pfam"
    assert terms[0]["go_terms"] == ["GO:0004672", "GO:0005524"]


def test_parse_autodock_vina_log_extracts_pose_table() -> None:
    poses = parse_autodock_vina_log(
        "mode |   affinity | dist from best mode\n"
        + "-----+------------+---------------------\n"
        + "   1      -7.5      0.000      0.000\n"
        + "   2      -6.8      2.100      3.500\n"
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
    top_k = cast(list[dict[str, object]], outputs["top_k"])
    component_scores = cast(dict[str, dict[str, float]], outputs["component_scores"])
    rank_reason = cast(str, outputs["rank_reason"])
    evidence_refs = cast(list[dict[str, object]], outputs["evidence_refs"])
    first_score = top_k[0]["objective_score"]
    second_score = top_k[1]["objective_score"]

    assert isinstance(first_score, (int, float))
    assert isinstance(second_score, (int, float))
    assert first_score >= second_score
    assert component_scores["cand_a"]["quality"] > 0
    assert isinstance(rank_reason, str)
    assert rank_reason.startswith("cand_a ranks by objective_score")
    assert evidence_refs[0]["candidate_id"] == "cand_a"
    assert isinstance(outputs["warnings"], list)
    assert metrics["objective_progress"] == outputs["objective_score"]
    assert metrics["objective_gap"] > 0
    assert metrics["requirement2"]["capability_id"] == "objective_scoring"


def test_objective_ranker_uses_structure_similarity_for_novelty() -> None:
    adapter = ObjectiveRankerAdapter()

    outputs, _ = adapter.run_local(
        {
            "candidates": [
                {
                    "candidate_id": "novel_fold",
                    "plddt": 88.0,
                    "structure_similarity_hits": [{"tm_score": 0.25, "coverage": 0.8}],
                },
                {
                    "candidate_id": "known_fold",
                    "plddt": 88.0,
                    "structure_similarity_hits": [{"tm_score": 0.9, "coverage": 0.8}],
                },
            ]
        }
    )

    scores = cast(dict[str, dict[str, float]], outputs["component_scores"])
    assert scores["novel_fold"]["novelty"] > scores["known_fold"]["novelty"]


def test_objective_ranker_emits_posterior_score_schema_and_degraded_evidence() -> None:
    adapter = ObjectiveRankerAdapter()

    outputs, metrics = adapter.run_local(
        {
            "task_constraints": {
                "objective": {
                    "objective_type": "stability",
                    "objective_weights": {
                        "stability": 0.7,
                        "structure_quality": 0.3,
                    },
                }
            },
            "candidates": [
                {
                    "candidate_id": "cand_degraded",
                    "plddt": 80.0,
                }
            ],
        }
    )

    top_k = cast(list[dict[str, object]], outputs["top_k"])
    posterior = cast(dict[str, object], top_k[0]["posterior_score"])
    stability = cast(dict[str, object], posterior["stability"])
    weights = cast(dict[str, float], posterior["component_weights"])

    assert posterior["schema_version"] == "posterior_score.v1"
    assert posterior["objective_type"] == "stability"
    assert posterior["aggregate_score"] == outputs["objective_score"]
    assert stability["score"] is None
    assert stability["evidence_status"] == "degraded"
    assert weights["stability"] == 0.7
    assert weights["structure_quality"] == 0.3
    assert metrics["evidence_sufficiency"] == posterior["evidence_sufficiency"]
    assert "posterior_scores" in outputs
    posterior_objective = cast(dict[str, object], top_k[0]["posterior_objective"])
    assert posterior_objective["schema_version"] == "posterior_objective.v1"
    assert posterior_objective["aggregate_score"] == posterior["aggregate_score"]
    assert posterior_objective["source_refs"] == [
        "sid:algo.posterior_objective_scoring",
        "impl:posterior_score.v1",
    ]
    assert outputs["posterior_objective"] == posterior_objective
    assert "posterior_objectives" in outputs


def test_objective_ranker_binding_objective_marks_generic_proxy() -> None:
    adapter = ObjectiveRankerAdapter()

    outputs, _ = adapter.run_local(
        {
            "objective_type": "binding",
            "candidates": [
                {
                    "candidate_id": "binder",
                    "plddt": 82.0,
                    "binding_score": -9.0,
                    "best_pose": {"affinity": -9.0},
                }
            ],
        }
    )

    top_k = cast(list[dict[str, object]], outputs["top_k"])
    posterior_objective = cast(dict[str, object], top_k[0]["posterior_objective"])
    assert posterior_objective["objective_type"] == "binding"
    assert posterior_objective["binding_proxy_component"] == "generic_objective"
    assert posterior_objective["binding_proxy_fields"] == ["binding_score", "best_pose"]


def test_foldseek_adapter_uses_api_by_default_and_emits_structure_similarity_schema(
    tmp_path: Path,
) -> None:
    api_client = FakeFoldseekApiClient()
    query_path = tmp_path / "query.pdb"
    _ = query_path.write_text("ATOM\n", encoding="utf-8")
    adapter = FoldseekAdapter(
        artifacts_dir=tmp_path / "artifacts",
        api_client=api_client,
        poll_interval_s=0.0,
    )

    health = adapter.healthcheck()
    outputs, metrics = adapter.run_local({"pdb_path": str(query_path)})

    assert health["status"] == "ready"
    assert api_client.posted_databases == ["afdb-swissprot"]
    assert outputs["capability_id"] == "structure_similarity_search"
    hits = cast(list[dict[str, object]], outputs["structure_similarity_hits"])
    artifact_refs = cast(list[dict[str, object]], outputs["artifact_refs"])
    assert hits[0]["tm_score"] == 0.79
    assert hits[0]["hit_id"] == "hitA"
    assert artifact_refs[0]["kind"] == "foldseek_api_result"
    assert outputs["api_ticket_id"] == "ticket_123"
    assert metrics["exec_type"] == "remote_api"
    assert metrics["provider"] == "foldseek_web"
    assert metrics["endpoint_type"] == "rest"


def test_foldseek_adapter_runs_local_and_emits_structure_similarity_schema(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def fake_runner(
        args: list[str],
        *,
        capture_output: bool,
        text: bool,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        _ = capture_output, text, check
        _ = Path(args[4]).write_text(
            "query_1\thitA\t1e-8\t220\t0.79\t0.78\t0.76\t0.71\t110\t120\t135\t0.88\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(args, 0, "", "")

    query_path = tmp_path / "query.pdb"
    _ = query_path.write_text("ATOM\n", encoding="utf-8")
    database_path = tmp_path / "foldseek_db"
    database_path.mkdir()
    monkeypatch.setattr(
        "src.adapters.foldseek_adapter.shutil.which",
        _resolved_binary("/usr/bin/foldseek"),
    )
    adapter = FoldseekAdapter(
        artifacts_dir=tmp_path / "artifacts",
        runner=fake_runner,
        execution_mode="local_cli",
    )

    outputs, metrics = adapter.run_local(
        {"pdb_path": str(query_path), "database_path": str(database_path)}
    )

    assert outputs["capability_id"] == "structure_similarity_search"
    hits = cast(list[dict[str, object]], outputs["structure_similarity_hits"])
    artifact_refs = cast(list[dict[str, object]], outputs["artifact_refs"])
    coverage = hits[0]["coverage"]
    assert hits[0]["tm_score"] == 0.79
    assert hits[0]["hit_id"] == "hitA"
    assert isinstance(coverage, float)
    assert abs(coverage - (110 / 120)) < 1e-6
    assert artifact_refs[0]["kind"] == "foldseek_tabular"
    requirement2 = cast(dict[str, object], metrics["requirement2"])
    assert requirement2["capability_id"] == "structure_similarity_search"


def test_foldseek_adapter_reports_missing_input_pdb(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "src.adapters.foldseek_adapter.shutil.which",
        _resolved_binary("/usr/bin/foldseek"),
    )
    database_path = tmp_path / "foldseek_db"
    database_path.mkdir()
    adapter = FoldseekAdapter(artifacts_dir=tmp_path / "artifacts", execution_mode="local_cli")

    with pytest.raises(StepRunError) as exc_info:
        _ = adapter.run_local(
            {"pdb_path": str(tmp_path / "missing.pdb"), "database_path": str(database_path)}
        )

    assert "pdb_path does not exist" in str(exc_info.value)


def test_interproscan_adapter_runs_local_and_emits_function_terms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_runner(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        _unused_kwargs = kwargs
        output_path = Path(cmd[cmd.index("-o") + 1])
        _written = output_path.write_text(
            "query_1\tmd5\t100\tPfam\tPF00001\tKinase\t1\t90\t42.0\tT\t2026-04-15\tIPR000001\tKinase domain\tGO:0004672\t\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(
        "src.adapters.interproscan_adapter.shutil.which",
        _resolved_binary("/usr/bin/interproscan.sh"),
    )
    adapter = InterProScanAdapter(runner=fake_runner)

    outputs, metrics = adapter.run_local({"sequence": "ACDEFGHIK"})

    assert outputs["capability_id"] == "function_annotation"
    assert outputs["annotation_summary"]["term_count"] == 1
    assert metrics["term_count"] == 1


def test_mda_analysis_adapter_generates_stability_proxy_metrics(tmp_path: Path) -> None:
    pdb_path = tmp_path / "input.pdb"
    _ = pdb_path.write_text(
        "ATOM      1  CA  ALA A   1       1.000   0.000   0.000  1.00 77.00           C\n"
        + "ATOM      2  CA  GLY A   2       3.000   0.000   0.000  1.00 77.00           C\n"
        + "ATOM      3  CA  SER A   3       5.000   0.000   0.000  1.00 77.00           C\n"
        + "END\n",
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
    def fake_runner(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        _unused_kwargs = kwargs
        out_path = Path(cmd[cmd.index("--out") + 1])
        log_path = Path(cmd[cmd.index("--log") + 1])
        _out_written = out_path.write_text("MODEL 1\nENDMDL\n", encoding="utf-8")
        _log_written = log_path.write_text(
            "mode |   affinity | dist from best mode\n"
            + "-----+------------+---------------------\n"
            + "   1      -7.5      0.000      0.000\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(
        "src.adapters.autodock_vina_adapter.shutil.which",
        _resolved_binary("/usr/bin/vina"),
    )
    adapter = AutoDockVinaAdapter(runner=fake_runner)

    outputs, metrics = adapter.run_local(
        {"receptor_path": "/tmp/receptor.pdbqt", "ligand_path": "/tmp/ligand.pdbqt"}
    )

    assert outputs["capability_id"] == "docking_scoring"
    assert outputs["binding_score"] == -7.5
    assert metrics["pose_count"] == 1
