from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from scripts.remote.plm_rest_server.run_plm_job import run_plm_job


ALLOWED_STATUSES = {"pending", "running", "completed", "failed", "unknown"}


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    retryable: bool,
    details: Optional[Dict[str, Any]] = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "retryable": retryable,
                "details": details or {},
            }
        },
    )


class APIError(Exception):
    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        retryable: bool = False,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.retryable = retryable
        self.details = details or {}


class PredictRequest(BaseModel):
    task_id: str
    step_id: str
    inputs: Dict[str, Any] = Field(default_factory=dict)


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def _job_dir(base_dir: Path, job_id: str) -> Path:
    return base_dir / job_id


def _status_path(base_dir: Path, job_id: str) -> Path:
    return _job_dir(base_dir, job_id) / "status.json"


def _outputs_path(base_dir: Path, job_id: str) -> Path:
    return _job_dir(base_dir, job_id) / "outputs.json"


def _input_path(base_dir: Path, job_id: str) -> Path:
    return _job_dir(base_dir, job_id) / "input.json"


def _execute_job(base_dir: Path, job_id: str) -> None:
    job_dir = _job_dir(base_dir, job_id)
    input_payload = _read_json(_input_path(base_dir, job_id), {})
    run_plm_job(job_id=job_id, job_dir=job_dir, input_payload=input_payload)


def _build_app(base_dir: Path, api_token: str) -> FastAPI:
    app = FastAPI(title="PLM REST Server", version="0.1.0")
    app.state.remote_base_dir = base_dir
    app.state.api_token = api_token

    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        token = app.state.api_token
        if token:
            auth_header = request.headers.get("Authorization", "")
            expected = f"Bearer {token}"
            if auth_header != expected:
                return _error_response(
                    status_code=401,
                    code="UNAUTHORIZED",
                    message="Missing or invalid bearer token",
                    retryable=False,
                )
        return await call_next(request)

    @app.exception_handler(APIError)
    async def handle_api_error(_request: Request, exc: APIError) -> JSONResponse:
        return _error_response(
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
            retryable=exc.retryable,
            details=exc.details,
        )

    @app.exception_handler(HTTPException)
    async def handle_http_exception(_request: Request, exc: HTTPException) -> JSONResponse:
        return _error_response(
            status_code=exc.status_code,
            code="HTTP_EXCEPTION",
            message=str(exc.detail),
            retryable=False,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(_request: Request, exc: Exception) -> JSONResponse:
        return _error_response(
            status_code=500,
            code="INTERNAL_SERVER_ERROR",
            message="Unhandled server error",
            retryable=True,
            details={"exception": str(exc)},
        )

    @app.post("/predict")
    def predict(payload: PredictRequest, background_tasks: BackgroundTasks) -> Dict[str, str]:
        job_id = f"plm_{uuid4().hex}"
        job_dir = _job_dir(base_dir, job_id)
        (job_dir / "artifacts").mkdir(parents=True, exist_ok=True)

        _write_json(
            _status_path(base_dir, job_id),
            {
                "job_id": job_id,
                "status": "pending",
                "updated_at": _now_iso(),
            },
        )
        _write_json(_input_path(base_dir, job_id), payload.model_dump())
        background_tasks.add_task(_execute_job, base_dir, job_id)
        return {"job_id": job_id}

    @app.get("/job/{job_id}")
    def get_job_status(job_id: str) -> Dict[str, Any]:
        status_payload = _read_json(_status_path(base_dir, job_id), None)
        if status_payload is None:
            raise APIError(
                status_code=404,
                code="REMOTE_JOB_NOT_FOUND",
                message=f"Job '{job_id}' does not exist",
                retryable=False,
                details={"job_id": job_id},
            )

        status = str(status_payload.get("status", "unknown")).lower()
        if status not in ALLOWED_STATUSES:
            status = "unknown"

        response = {
            "job_id": job_id,
            "status": status,
        }
        if status == "failed" and isinstance(status_payload.get("failure"), dict):
            response["failure"] = status_payload["failure"]
        return response

    @app.get("/results/{job_id}")
    def get_results(job_id: str, request: Request) -> Dict[str, Any]:
        status_payload = _read_json(_status_path(base_dir, job_id), None)
        if status_payload is None:
            raise APIError(
                status_code=404,
                code="REMOTE_JOB_NOT_FOUND",
                message=f"Job '{job_id}' does not exist",
                retryable=False,
                details={"job_id": job_id},
            )

        status = str(status_payload.get("status", "unknown")).lower()
        if status != "completed":
            raise APIError(
                status_code=409,
                code="REMOTE_RESULTS_NOT_READY",
                message=f"Job '{job_id}' is not completed",
                retryable=status in {"pending", "running"},
                details={"job_id": job_id, "status": status},
            )

        outputs = _read_json(_outputs_path(base_dir, job_id), {})
        artifact_dir = _job_dir(base_dir, job_id) / "artifacts"
        artifacts = []
        if artifact_dir.exists():
            for file_path in sorted(artifact_dir.iterdir()):
                if not file_path.is_file():
                    continue
                artifacts.append(
                    {
                        "name": file_path.name,
                        "url": str(
                            request.url_for(
                                "download_artifact",
                                job_id=job_id,
                                filename=file_path.name,
                            )
                        ),
                        "type": "file",
                    }
                )

        return {
            "job_id": job_id,
            "outputs": outputs,
            "artifacts": artifacts,
        }

    @app.get("/files/{job_id}/{filename}", name="download_artifact")
    def download_artifact(job_id: str, filename: str) -> FileResponse:
        path = _job_dir(base_dir, job_id) / "artifacts" / filename
        if not path.exists() or not path.is_file():
            raise APIError(
                status_code=404,
                code="ARTIFACT_NOT_FOUND",
                message=f"Artifact '{filename}' does not exist for job '{job_id}'",
                retryable=False,
            )
        return FileResponse(path=path)

    return app


def create_app(
    *,
    remote_base_dir: Optional[Path] = None,
    api_token: Optional[str] = None,
) -> FastAPI:
    base_dir = Path(remote_base_dir or os.getenv("PLM_REST_BASE_DIR", "./output/remote/plm_jobs"))
    base_dir.mkdir(parents=True, exist_ok=True)
    token = api_token if api_token is not None else os.getenv("PLM_REST_API_TOKEN", "")
    return _build_app(base_dir=base_dir, api_token=token)


app = create_app()
