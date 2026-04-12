from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from services.openfold3_rest_server.app import create_app


def test_contract_happy_path_with_stubbed_runner(tmp_path: Path) -> None:
    def fake_run_job(
        base_dir: Path,
        job_id: str,
        *,
        model_dir: str,
        predict_bin: str,
        device: str,
    ) -> None:
        job_path = base_dir / job_id
        (job_path / "artifacts").mkdir(parents=True, exist_ok=True)
        (job_path / "outputs.json").write_text(
            '{"pdb_path":"prediction.pdb","plddt":81.2,"artifacts":{"summary_path":"summary.json"}}',
            encoding="utf-8",
        )
        (job_path / "artifacts" / "prediction.pdb").write_text("ATOM 1\n", encoding="utf-8")
        (job_path / "status.json").write_text(
            '{"job_id":"%s","status":"completed"}' % job_id,
            encoding="utf-8",
        )

    app = create_app(remote_base_dir=tmp_path, run_job_func=fake_run_job)
    client = TestClient(app)
    resp = client.post(
        "/predict",
        json={
            "task_id": "task_001",
            "step_id": "S2",
            "inputs": {"sequence": "ACDEFGHIKLMNPQRSTVWY"},
        },
    )
    assert resp.status_code == 200
    job_id = resp.json()["job_id"]

    status_resp = client.get(f"/job/{job_id}")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "completed"

    results_resp = client.get(f"/results/{job_id}")
    assert results_resp.status_code == 200
    data = results_resp.json()
    assert data["job_id"] == job_id
    assert data["outputs"]["pdb_path"] == "prediction.pdb"
    assert len(data["artifacts"]) == 1
    file_resp = client.get(data["artifacts"][0]["url"])
    assert file_resp.status_code == 200


def test_contract_failure_path(tmp_path: Path) -> None:
    def fake_run_job(
        base_dir: Path,
        job_id: str,
        *,
        model_dir: str,
        predict_bin: str,
        device: str,
    ) -> None:
        job_path = base_dir / job_id
        (job_path / "status.json").write_text(
            '{"job_id":"%s","status":"failed","failure":{"code":"REMOTE_JOB_FAILED","message":"boom","failure_type":"tool_error","retryable":false}}'
            % job_id,
            encoding="utf-8",
        )

    app = create_app(remote_base_dir=tmp_path, run_job_func=fake_run_job)
    client = TestClient(app)
    resp = client.post(
        "/predict",
        json={"task_id": "task_002", "step_id": "S2", "inputs": {"sequence": "ACDE"}},
    )
    assert resp.status_code == 200
    job_id = resp.json()["job_id"]

    status_resp = client.get(f"/job/{job_id}")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "failed"

    results_resp = client.get(f"/results/{job_id}")
    assert results_resp.status_code == 409
    err = results_resp.json()["error"]
    assert err["code"] == "REMOTE_RESULTS_NOT_READY"


def test_contract_lists_and_downloads_nested_artifacts(tmp_path: Path) -> None:
    def fake_run_job(
        base_dir: Path,
        job_id: str,
        *,
        model_dir: str,
        predict_bin: str,
        device: str,
    ) -> None:
        job_path = base_dir / job_id
        nested = job_path / "artifacts" / "openfold3_request" / "seed_42"
        nested.mkdir(parents=True, exist_ok=True)
        (job_path / "outputs.json").write_text(
            '{"pdb_path":"openfold3_request/seed_42/prediction_model.cif","plddt":81.2}',
            encoding="utf-8",
        )
        (nested / "prediction_model.cif").write_text("data_test\n", encoding="utf-8")
        (job_path / "status.json").write_text(
            '{"job_id":"%s","status":"completed"}' % job_id,
            encoding="utf-8",
        )

    app = create_app(remote_base_dir=tmp_path, run_job_func=fake_run_job)
    client = TestClient(app)
    resp = client.post(
        "/predict",
        json={
            "task_id": "task_nested",
            "step_id": "S2",
            "inputs": {"sequence": "ACDEFGHIKLMNPQRSTVWY"},
        },
    )
    assert resp.status_code == 200
    job_id = resp.json()["job_id"]

    results_resp = client.get(f"/results/{job_id}")
    assert results_resp.status_code == 200
    payload = results_resp.json()
    assert payload["outputs"]["pdb_path"] == "openfold3_request/seed_42/prediction_model.cif"
    assert payload["artifacts"][0]["name"] == "openfold3_request/seed_42/prediction_model.cif"

    file_resp = client.get(payload["artifacts"][0]["url"])
    assert file_resp.status_code == 200


def test_contract_error_envelope_and_auth(tmp_path: Path) -> None:
    app = create_app(remote_base_dir=tmp_path, api_token="token-123")
    client = TestClient(app)

    unauthorized = client.get("/job/not_exist")
    assert unauthorized.status_code == 401
    assert unauthorized.json()["error"]["code"] == "UNAUTHORIZED"

    not_found = client.get(
        "/job/not_exist",
        headers={"Authorization": "Bearer token-123"},
    )
    assert not_found.status_code == 404
    assert not_found.json()["error"]["code"] == "REMOTE_JOB_NOT_FOUND"
