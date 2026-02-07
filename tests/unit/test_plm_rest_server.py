from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from scripts.remote.plm_rest_server.app import create_app
from scripts.remote.plm_rest_server.run_plm_job import run_plm_job


def test_plm_rest_happy_path(tmp_path: Path) -> None:
    app = create_app(remote_base_dir=tmp_path)
    client = TestClient(app)

    response = client.post(
        "/predict",
        json={
            "task_id": "task_001",
            "step_id": "S1",
            "inputs": {
                "length_range": [12, 16],
                "num_candidates": 3,
            },
        },
    )
    assert response.status_code == 200
    job_id = response.json()["job_id"]

    status_response = client.get(f"/job/{job_id}")
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "completed"

    results_response = client.get(f"/results/{job_id}")
    assert results_response.status_code == 200
    body = results_response.json()
    assert body["job_id"] == job_id
    assert "sequence" in body["outputs"]
    assert "candidates" in body["outputs"]
    assert len(body["outputs"]["candidates"]) == 3
    assert len(body["artifacts"]) >= 1

    artifact = body["artifacts"][0]
    assert artifact["url"].startswith("http://testserver/files/")
    download = client.get(artifact["url"])
    assert download.status_code == 200


def test_plm_rest_failed_job_contains_failure(tmp_path: Path) -> None:
    app = create_app(remote_base_dir=tmp_path)
    client = TestClient(app)

    response = client.post(
        "/predict",
        json={
            "task_id": "task_002",
            "step_id": "S1",
            "inputs": {
                "force_fail": True,
            },
        },
    )
    job_id = response.json()["job_id"]

    status_response = client.get(f"/job/{job_id}")
    assert status_response.status_code == 200
    payload = status_response.json()
    assert payload["status"] == "failed"
    assert payload["failure"]["code"] == "REMOTE_JOB_FAILED"

    results_response = client.get(f"/results/{job_id}")
    assert results_response.status_code == 409
    error_payload = results_response.json()["error"]
    assert error_payload["code"] == "REMOTE_RESULTS_NOT_READY"


def test_plm_rest_error_envelope_and_auth(tmp_path: Path) -> None:
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


def test_run_plm_job_writes_expected_files(tmp_path: Path) -> None:
    job_id = "plm_job_direct_001"
    job_dir = tmp_path / job_id
    payload = {
        "task_id": "task_003",
        "step_id": "S3",
        "inputs": {
            "num_candidates": 2,
            "length_range": [8, 10],
        },
    }

    outputs = run_plm_job(job_id=job_id, job_dir=job_dir, input_payload=payload)
    assert "sequence" in outputs
    assert len(outputs["candidates"]) == 2

    status = json.loads((job_dir / "status.json").read_text(encoding="utf-8"))
    assert status["status"] == "completed"
    assert (job_dir / "outputs.json").exists()
    assert (job_dir / "artifacts" / "candidates.fasta").exists()
