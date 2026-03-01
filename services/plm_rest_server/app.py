from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Dict, Optional
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from services.plm_rest_server.jobs import (
    JobError,
    get_job_results,
    get_job_status,
    init_job,
    job_dir,
    run_job,
)
from services.plm_rest_server.protgpt2_runner import DEFAULT_MODEL_DIR
from services.plm_rest_server.schemas import PredictRequest


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


def _status_for_job_error(error: JobError) -> int:
    if error.code == "REMOTE_JOB_NOT_FOUND":
        return 404
    if error.code == "REMOTE_RESULTS_NOT_READY":
        return 409
    return 400


def _build_app(base_dir: Path, api_token: str, model_dir: str) -> FastAPI:
    app = FastAPI(title="PLM REST Server", version="0.2.0")
    app.state.remote_base_dir = base_dir
    app.state.api_token = api_token
    app.state.model_dir = model_dir
    app.state.run_job_func = run_job

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
        (job_dir(base_dir, job_id) / "artifacts").mkdir(parents=True, exist_ok=True)
        init_job(base_dir, job_id, payload.model_dump())
        background_tasks.add_task(app.state.run_job_func, base_dir, job_id, model_dir=app.state.model_dir)
        return {"job_id": job_id}

    @app.get("/job/{job_id}")
    def job_status(job_id: str) -> Dict[str, Any]:
        payload = get_job_status(base_dir, job_id)
        if payload is None:
            return _error_response(
                status_code=404,
                code="REMOTE_JOB_NOT_FOUND",
                message=f"Job '{job_id}' does not exist",
                retryable=False,
                details={"job_id": job_id},
            )
        return payload

    @app.get("/results/{job_id}")
    def results(job_id: str, request: Request) -> Dict[str, Any]:
        try:
            payload = get_job_results(base_dir, job_id)
        except JobError as exc:
            return _error_response(
                status_code=_status_for_job_error(exc),
                code=exc.code,
                message=exc.message,
                retryable=exc.retryable,
                details={"job_id": job_id},
            )

        artifact_dir = job_dir(base_dir, job_id) / "artifacts"
        artifacts = []
        if artifact_dir.exists():
            for file_path in sorted(artifact_dir.iterdir()):
                if file_path.is_file():
                    artifacts.append(
                        {
                            "name": file_path.name,
                            "url": str(request.url_for("download_artifact", job_id=job_id, filename=file_path.name)),
                            "type": "file",
                        }
                    )
        payload["artifacts"] = artifacts
        return payload

    @app.get("/files/{job_id}/{filename}", name="download_artifact")
    def download_artifact(job_id: str, filename: str) -> FileResponse:
        path = job_dir(base_dir, job_id) / "artifacts" / filename
        if not path.exists() or not path.is_file():
            return _error_response(
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
    model_dir: Optional[str] = None,
    run_job_func: Optional[Callable[..., None]] = None,
) -> FastAPI:
    base_dir = Path(remote_base_dir or os.getenv("PLM_REST_BASE_DIR", "./output/remote/plm_jobs"))
    base_dir.mkdir(parents=True, exist_ok=True)
    token = api_token if api_token is not None else os.getenv("PLM_REST_API_TOKEN", "")
    resolved_model_dir = model_dir or os.getenv("PLM_MODEL_DIR", DEFAULT_MODEL_DIR)
    app = _build_app(base_dir=base_dir, api_token=token, model_dir=resolved_model_dir)
    if run_job_func is not None:
        app.state.run_job_func = run_job_func
    return app


app = create_app()
