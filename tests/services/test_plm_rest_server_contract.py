from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from services.plm_rest_server.app import create_app


def test_contract_happy_path_with_stubbed_runner(tmp_path: Path) -> None:
    def fake_run_job(base_dir: Path, job_id: str, *, model_dir: str) -> None:
        job_path = base_dir / job_id
        (job_path / "artifacts").mkdir(parents=True, exist_ok=True)
        (job_path / "outputs.json").write_text(
            '{"sequence":"ACDE","candidates":[{"sequence":"ACDE","score":-1.2}],"artifacts":{"fasta_path":"candidates.fasta"}}',
            encoding="utf-8",
        )
        (job_path / "artifacts" / "candidates.fasta").write_text(">x\nACDE\n", encoding="utf-8")
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
            "step_id": "S1",
            "inputs": {
                "prompt": "<|endoftext|>",
                "max_new_tokens": 16,
                "num_return_sequences": 1,
            },
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
    assert data["outputs"]["sequence"] == "ACDE"
    assert len(data["artifacts"]) == 1
    file_resp = client.get(data["artifacts"][0]["url"])
    assert file_resp.status_code == 200


def test_contract_failure_path(tmp_path: Path) -> None:
    def fake_run_job(base_dir: Path, job_id: str, *, model_dir: str) -> None:
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
        json={"task_id": "task_002", "step_id": "S1", "inputs": {"prompt": "x"}},
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
