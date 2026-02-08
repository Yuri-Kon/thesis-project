from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, Optional

from services.plm_rest_server.protgpt2_runner import (
    DEFAULT_MODEL_DIR,
    generate_with_protgpt2,
    write_artifacts,
)

ALLOWED_STATUSES = {"pending", "running", "completed", "failed", "unknown"}


class JobError(RuntimeError):
    def __init__(self, *, code: str, message: str, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def job_dir(base_dir: Path, job_id: str) -> Path:
    return base_dir / job_id


def status_path(base_dir: Path, job_id: str) -> Path:
    return job_dir(base_dir, job_id) / "status.json"


def outputs_path(base_dir: Path, job_id: str) -> Path:
    return job_dir(base_dir, job_id) / "outputs.json"


def input_path(base_dir: Path, job_id: str) -> Path:
    return job_dir(base_dir, job_id) / "input.json"


def init_job(base_dir: Path, job_id: str, payload: Dict[str, Any]) -> None:
    _write_json(
        status_path(base_dir, job_id),
        {"job_id": job_id, "status": "pending", "updated_at": _now_iso()},
    )
    _write_json(input_path(base_dir, job_id), payload)


def get_job_status(base_dir: Path, job_id: str) -> Optional[Dict[str, Any]]:
    payload = _read_json(status_path(base_dir, job_id), None)
    if payload is None:
        return None

    status = str(payload.get("status", "unknown")).lower()
    if status not in ALLOWED_STATUSES:
        status = "unknown"

    response: Dict[str, Any] = {"job_id": job_id, "status": status}
    if status == "failed" and isinstance(payload.get("failure"), dict):
        response["failure"] = payload["failure"]
    return response


def get_job_results(base_dir: Path, job_id: str) -> Dict[str, Any]:
    status_payload = _read_json(status_path(base_dir, job_id), None)
    if status_payload is None:
        raise JobError(code="REMOTE_JOB_NOT_FOUND", message=f"Job '{job_id}' does not exist", retryable=False)

    status = str(status_payload.get("status", "unknown")).lower()
    if status != "completed":
        raise JobError(
            code="REMOTE_RESULTS_NOT_READY",
            message=f"Job '{job_id}' is not completed",
            retryable=status in {"pending", "running"},
        )

    outputs = _read_json(outputs_path(base_dir, job_id), {})
    return {"job_id": job_id, "outputs": outputs}


def run_job(base_dir: Path, job_id: str, *, model_dir: str = DEFAULT_MODEL_DIR) -> None:
    job_path = job_dir(base_dir, job_id)
    payload = _read_json(input_path(base_dir, job_id), {})
    inputs = payload.get("inputs", {}) if isinstance(payload, dict) else {}

    _write_json(status_path(base_dir, job_id), {"job_id": job_id, "status": "running", "updated_at": _now_iso()})

    try:
        outputs_payload, metrics = generate_with_protgpt2(inputs, model_dir=model_dir)
        artifacts = write_artifacts(
            job_path,
            outputs_payload=outputs_payload,
            metadata={
                "job_id": job_id,
                "task_id": str(payload.get("task_id", "unknown")),
                "step_id": str(payload.get("step_id", "unknown")),
                **metrics,
            },
        )
        outputs_payload["artifacts"] = artifacts
        _write_json(outputs_path(base_dir, job_id), outputs_payload)
        _write_json(status_path(base_dir, job_id), {"job_id": job_id, "status": "completed", "updated_at": _now_iso()})
    except Exception as exc:
        failure = {
            "code": "REMOTE_JOB_FAILED",
            "message": str(exc),
            "failure_type": "tool_error",
            "retryable": False,
        }
        _write_json(
            status_path(base_dir, job_id),
            {"job_id": job_id, "status": "failed", "updated_at": _now_iso(), "failure": failure},
        )
