from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from collections.abc import Mapping
from pathlib import Path
from time import perf_counter, sleep
from typing import Protocol, TypeGuard, cast, override

import httpx

from src.engines.provider_config import get_provider_config
from src.adapters.base_tool_adapter import BaseToolAdapter
from src.adapters.tool_schema_utils import (
    build_structure_similarity_metrics,
    build_structure_similarity_outputs,
    resolve_step_inputs,
)
from src.models.contracts import PlanStep
from src.workflow.context import WorkflowContext
from src.workflow.errors import FailureCode, FailureType, StepRunError

__all__ = ["FoldseekAdapter", "parse_foldseek_tabular"]


class _CompletedProcessRunner(Protocol):
    def __call__(
        self,
        args: list[str],
        *,
        capture_output: bool,
        text: bool,
        check: bool,
    ) -> subprocess.CompletedProcess[str]: ...


class _FoldseekApiClient(Protocol):
    def get(self, url: str, *, timeout: float) -> httpx.Response: ...

    def post(
        self,
        url: str,
        *,
        data: Mapping[str, str | list[str]],
        files: Mapping[str, tuple[str, bytes, str]],
        timeout: float,
    ) -> httpx.Response: ...


type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | JsonObject | JsonArray
type JsonObject = dict[str, JsonValue]
type JsonArray = list[JsonValue]


FOLDSEEK_FIELDS = (
    "query",
    "target",
    "evalue",
    "bits",
    "alntmscore",
    "qtmscore",
    "ttmscore",
    "lddt",
    "alnlen",
    "qlen",
    "tlen",
    "prob",
)
_DATABASE_ENV_KEYS = (
    "FOLDSEEK_DB_PATH",
    "PROTEIN_STRUCTURE_DB_PATH",
    "PROTEIN_DATABASE_PATH",
)
_API_BASE_URL_ENV_KEY = "FOLDSEEK_API_BASE_URL"
_API_DATABASE_ENV_KEYS = ("FOLDSEEK_API_DATABASES", "FOLDSEEK_API_DATABASE")
_DEFAULT_API_BASE_URL = "https://search.foldseek.com/api"
_DEFAULT_API_DATABASES = ("afdb-swissprot",)
_API_COMPLETE_STATES = {"COMPLETE", "COMPLETED"}
_API_PENDING_STATES = {"PENDING", "RUNNING", "UNKNOWN"}


class FoldseekAdapter(BaseToolAdapter):
    """结构相似性检索适配器。"""

    tool_id: str = "foldseek"
    adapter_id: str | None = "foldseek"
    execution_mode: str = "foldseek_api"
    provider: str = "foldseek_web"
    endpoint_type: str = "rest"

    def __init__(
        self,
        *,
        binary: str = "foldseek",
        artifacts_dir: str | Path = "output/artifacts",
        runner: _CompletedProcessRunner | None = None,
        execution_mode: str | None = None,
        api_base_url: str | None = None,
        api_client: _FoldseekApiClient | None = None,
        request_timeout_s: float | None = None,
        poll_interval_s: float | None = None,
        max_polls: int | None = None,
    ) -> None:
        self.binary: str = binary
        self.artifacts_dir: Path = Path(artifacts_dir)
        self.runner: _CompletedProcessRunner = runner or subprocess.run
        self.execution_mode = _normalize_execution_mode(
            execution_mode or os.getenv("FOLDSEEK_EXECUTION_MODE") or self.execution_mode
        )
        self.api_base_url: str = _resolve_api_base_url(api_base_url)
        self.api_client: _FoldseekApiClient = api_client or httpx.Client()
        self.request_timeout_s: float = request_timeout_s or _resolve_provider_timeout()
        self.poll_interval_s: float = poll_interval_s if poll_interval_s is not None else 2.0
        self.max_polls: int = max_polls or 60

    @override
    def resolve_inputs(self, step: PlanStep, context: WorkflowContext) -> dict[str, object]:
        inputs = resolve_step_inputs(step, context, required_keys=("pdb_path",))
        if _uses_local_cli(self.execution_mode, inputs):
            inputs["database_path"] = _resolve_database_path(inputs.get("database_path"))
        else:
            api_databases = _resolve_api_databases(
                inputs.get("databases") or inputs.get("database_path")
            )
            inputs["databases"] = api_databases
            inputs["database_path"] = ",".join(api_databases)
        return inputs

    @override
    def describe_capabilities(self) -> dict[str, object]:
        return {
            **super().describe_capabilities(),
            "capability_id": "structure_similarity_search",
            "io_type": "structure_to_similarity_hits",
            "format_output": list(FOLDSEEK_FIELDS),
            "api_base_url": self.api_base_url,
            "api_database_env_keys": list(_API_DATABASE_ENV_KEYS),
            "database_env_keys": list(_DATABASE_ENV_KEYS),
        }

    @override
    def healthcheck(self) -> dict[str, object]:
        if not _uses_local_cli(self.execution_mode):
            return self._api_healthcheck()
        return self._local_healthcheck()

    def _api_healthcheck(self) -> dict[str, object]:
        try:
            response = self.api_client.get(
                _api_url(self.api_base_url, "databases"),
                timeout=min(self.request_timeout_s, 5.0),
            )
            _ = response.raise_for_status()
            payload = _json_object_response(response, context="Foldseek databases")
        except httpx.HTTPError as exc:
            return {
                "status": "unavailable",
                "reason": f"Foldseek API endpoint is unreachable: {exc}",
                "error_category": "remote_unreachable",
                "api_base_url": self.api_base_url,
            }
        except StepRunError as exc:
            return {
                "status": "degraded",
                "reason": str(exc),
                "error_category": "healthcheck_error",
                "api_base_url": self.api_base_url,
            }

        configured_databases = _resolve_api_databases(None)
        available = _available_database_paths(payload)
        missing = [item for item in configured_databases if available and item not in available]
        if missing:
            return {
                "status": "degraded",
                "reason": f"Foldseek API database is unavailable: {', '.join(missing)}",
                "error_category": "database_missing",
                "api_base_url": self.api_base_url,
                "configured_databases": configured_databases,
                "available_database_count": len(available),
            }

        return {
            "status": "ready",
            "reason": "Foldseek Web API is reachable",
            "api_base_url": self.api_base_url,
            "configured_databases": configured_databases,
            "available_database_count": len(available),
        }

    def _local_healthcheck(self) -> dict[str, object]:
        binary_path = shutil.which(self.binary)
        if binary_path is None:
            return {
                "status": "unavailable",
                "reason": f"binary '{self.binary}' not installed",
                "error_category": "binary_missing",
                "database_env_keys": list(_DATABASE_ENV_KEYS),
            }

        raw_database_path = _configured_database_path()
        if raw_database_path is None:
            return {
                "status": "degraded",
                "reason": "Foldseek database path is not configured",
                "binary_path": binary_path,
                "error_category": "database_missing",
                "database_env_keys": list(_DATABASE_ENV_KEYS),
            }

        database_path = Path(raw_database_path)
        if not database_path.exists():
            return {
                "status": "degraded",
                "reason": f"Foldseek database path does not exist: {database_path}",
                "binary_path": binary_path,
                "database_path": str(database_path),
                "error_category": "database_missing",
                "database_env_keys": list(_DATABASE_ENV_KEYS),
            }

        return {
            "status": "ready",
            "reason": "Foldseek binary and database path are configured",
            "binary_path": binary_path,
            "database_path": str(database_path),
        }

    @override
    def normalize_error(self, exc: Exception) -> dict[str, object]:
        if isinstance(exc, StepRunError):
            return {
                "error_type": exc.__class__.__name__,
                "message": str(exc),
                "failure_type": exc.failure_type.value,
                "failure_code": exc.code,
            }
        if isinstance(exc, subprocess.CalledProcessError):
            return {
                "error_type": exc.__class__.__name__,
                "message": str(exc),
                "returncode": exc.returncode,
            }
        if isinstance(exc, httpx.HTTPError):
            return {
                "error_type": exc.__class__.__name__,
                "message": str(exc),
                "failure_type": FailureType.TOOL_ERROR.value,
                "failure_code": FailureCode.REMOTE_JOB_FAILED.value,
            }
        return super().normalize_error(exc)

    @override
    def run_local(self, inputs: dict[str, object]) -> tuple[dict[str, object], dict[str, object]]:
        if not _uses_local_cli(self.execution_mode, inputs):
            return self.run_remote(inputs)
        return self._run_local_cli(inputs)

    @override
    def run_remote(
        self,
        inputs: dict[str, object],
        output_dir: Path | None = None,
    ) -> tuple[dict[str, object], dict[str, object]]:
        if _uses_local_cli(self.execution_mode, inputs):
            return self._run_local_cli(inputs)

        pdb_path = _require_existing_path(inputs.get("pdb_path"), field_name="pdb_path")
        databases = _resolve_api_databases(inputs.get("databases") or inputs.get("database_path"))
        result_path = _resolve_api_result_path(Path(output_dir or self.artifacts_dir), inputs)
        t0 = perf_counter()
        ticket_id = self._submit_api_ticket(pdb_path, databases)
        final_status = self._poll_api_ticket(ticket_id)
        result_payload = self._get_api_result(ticket_id, entry=_resolve_result_entry(inputs))
        _ = result_path.write_text(
            json.dumps(result_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        hits = _parse_foldseek_api_result(result_payload)
        artifact_refs = [
            {
                "kind": "foldseek_api_result",
                "path": str(result_path),
                "format": "json",
                "role": "structure_similarity_hits",
            }
        ]
        normalized_inputs = {
            **inputs,
            "pdb_path": str(pdb_path),
            "database_path": ",".join(databases),
            "databases": databases,
            "artifact_refs": artifact_refs,
        }
        outputs = build_structure_similarity_outputs(
            self.tool_id,
            normalized_inputs,
            hits,
        )
        outputs["artifacts"] = artifact_refs
        outputs["api_ticket_id"] = ticket_id
        metrics = build_structure_similarity_metrics(
            exec_type="remote_api",
            hit_count=len(hits),
        )
        metrics.update(
            {
                "duration_ms": int((perf_counter() - t0) * 1000),
                "tool_id": self.tool_id,
                "adapter_id": self.adapter_id,
                "execution_mode": "foldseek_api",
                "job_id": ticket_id,
                "remote_job_id": ticket_id,
                "provider": self.provider,
                "endpoint_type": self.endpoint_type,
                "api_base_url": self.api_base_url,
                "databases": databases,
                "final_status": final_status,
            }
        )
        return outputs, metrics

    def _submit_api_ticket(self, pdb_path: Path, databases: list[str]) -> str:
        response = self.api_client.post(
            _api_url(self.api_base_url, "ticket"),
            data={
                "mode": "3diaa",
                "database[]": databases,
            },
            files={
                "q": (
                    pdb_path.name or "query.pdb",
                    pdb_path.read_bytes(),
                    "text/plain",
                )
            },
            timeout=self.request_timeout_s,
        )
        try:
            _ = response.raise_for_status()
            ticket = _json_object_response(response, context="Foldseek ticket")
        except httpx.HTTPError as exc:
            raise StepRunError(
                failure_type=FailureType.TOOL_ERROR,
                message=f"Foldseek API ticket submission failed: {exc}",
                code=FailureCode.REMOTE_JOB_FAILED.value,
            ) from exc
        ticket_id = _json_string(ticket.get("id"))
        if ticket_id is None:
            raise StepRunError(
                failure_type=FailureType.TOOL_ERROR,
                message="Foldseek API ticket response did not include an id",
                code=FailureCode.REMOTE_JOB_FAILED.value,
            )
        return ticket_id

    def _poll_api_ticket(self, ticket_id: str) -> str:
        for _ in range(self.max_polls):
            response = self.api_client.get(
                _api_url(self.api_base_url, f"ticket/{ticket_id}"),
                timeout=self.request_timeout_s,
            )
            try:
                _ = response.raise_for_status()
                payload = _json_object_response(response, context="Foldseek ticket status")
            except httpx.HTTPError as exc:
                raise StepRunError(
                    failure_type=FailureType.TOOL_ERROR,
                    message=f"Foldseek API ticket polling failed: {exc}",
                    code=FailureCode.REMOTE_JOB_FAILED.value,
                ) from exc

            status = (_json_string(payload.get("status")) or "UNKNOWN").upper()
            if status in _API_COMPLETE_STATES:
                return status
            if status == "ERROR":
                raise StepRunError(
                    failure_type=FailureType.TOOL_ERROR,
                    message=f"Foldseek API job {ticket_id} failed",
                    code=FailureCode.REMOTE_JOB_FAILED.value,
                )
            if status not in _API_PENDING_STATES:
                raise StepRunError(
                    failure_type=FailureType.NON_RETRYABLE,
                    message=f"Foldseek API job {ticket_id} returned unknown status: {status}",
                    code=FailureCode.REMOTE_JOB_UNKNOWN.value,
                )
            if self.poll_interval_s > 0:
                sleep(self.poll_interval_s)

        raise StepRunError(
            failure_type=FailureType.RETRYABLE,
            message=(
                f"Foldseek API job {ticket_id} did not complete within "
                f"{self.max_polls} polls"
            ),
            code=FailureCode.REMOTE_POLL_TIMEOUT.value,
        )

    def _get_api_result(self, ticket_id: str, *, entry: int) -> JsonObject:
        response = self.api_client.get(
            _api_url(self.api_base_url, f"result/{ticket_id}/{entry}"),
            timeout=self.request_timeout_s,
        )
        try:
            _ = response.raise_for_status()
            return _json_object_response(response, context="Foldseek result")
        except httpx.HTTPError as exc:
            raise StepRunError(
                failure_type=FailureType.TOOL_ERROR,
                message=f"Foldseek API result download failed: {exc}",
                code=FailureCode.REMOTE_JOB_FAILED.value,
            ) from exc

    def _run_local_cli(
        self,
        inputs: dict[str, object],
    ) -> tuple[dict[str, object], dict[str, object]]:
        if shutil.which(self.binary) is None:
            raise StepRunError(
                failure_type=FailureType.NON_RETRYABLE,
                message=f"Foldseek binary '{self.binary}' is not installed",
                code=FailureCode.CANDIDATE_TOOL_UNAVAILABLE.value,
            )

        pdb_path = _require_existing_path(inputs.get("pdb_path"), field_name="pdb_path")
        database_path = _require_existing_path(
            _resolve_database_path(inputs.get("database_path")),
            field_name="database_path",
        )
        result_path = _resolve_result_path(self.artifacts_dir, inputs)
        t0 = perf_counter()
        with tempfile.TemporaryDirectory(prefix="foldseek_") as tmp_dir:
            tmp_path = Path(tmp_dir)
            work_path = tmp_path / "work"
            cmd = [
                self.binary,
                "easy-search",
                str(pdb_path),
                str(database_path),
                str(result_path),
                str(work_path),
                "--format-output",
                ",".join(FOLDSEEK_FIELDS),
            ]
            max_seqs = inputs.get("max_seqs")
            if max_seqs is not None:
                cmd.extend(["--max-seqs", str(max_seqs)])

            try:
                _ = self.runner(cmd, capture_output=True, text=True, check=True)
            except subprocess.CalledProcessError as exc:
                raise StepRunError(
                    failure_type=FailureType.TOOL_ERROR,
                    message=f"Foldseek command failed: {exc}",
                    code=FailureCode.TOOL_EXECUTION_ERROR.value,
                ) from exc

            hits = parse_foldseek_tabular(result_path.read_text(encoding="utf-8"))
            artifact_refs = [
                {
                    "kind": "foldseek_tabular",
                    "path": str(result_path),
                    "format": "m8",
                    "role": "structure_similarity_hits",
                }
            ]
            normalized_inputs = {
                **inputs,
                "pdb_path": str(pdb_path),
                "database_path": str(database_path),
                "artifact_refs": artifact_refs,
            }
            outputs = build_structure_similarity_outputs(
                self.tool_id,
                normalized_inputs,
                hits,
            )
            outputs["artifacts"] = artifact_refs
            metrics = build_structure_similarity_metrics(
                exec_type="local_cli",
                hit_count=len(hits),
                command=cmd,
            )
            metrics["duration_ms"] = int((perf_counter() - t0) * 1000)
            return outputs, metrics


def parse_foldseek_tabular(text: str) -> list[dict[str, object]]:
    hits: list[dict[str, object]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < len(FOLDSEEK_FIELDS):
            continue
        hits.append(
            {
                "query_id": parts[0],
                "target_id": parts[1],
                "evalue": parts[2],
                "bitscore": parts[3],
                "tm_score": parts[4],
                "query_tm_score": parts[5],
                "target_tm_score": parts[6],
                "lddt": parts[7],
                "alignment_length": parts[8],
                "query_length": parts[9],
                "target_length": parts[10],
                "probability": parts[11],
            }
        )
    return hits


def _parse_foldseek_api_result(payload: JsonObject) -> list[dict[str, object]]:
    query_id = _query_header(payload) or "query_1"
    hits: list[dict[str, object]] = []
    results = payload.get("results")
    if not isinstance(results, list):
        return hits
    for db_result in results:
        if not isinstance(db_result, dict):
            continue
        database = _json_string(db_result.get("db"))
        alignments = db_result.get("alignments")
        if not isinstance(alignments, list):
            continue
        for alignment_map in _alignment_maps(alignments):
            hits.append(
                {
                    "query_id": _object_string(alignment_map.get("query")) or query_id,
                    "target_id": _object_string(alignment_map.get("target")),
                    "hit_id": _object_string(alignment_map.get("target")),
                    "database": database,
                    "evalue": alignment_map.get("eval"),
                    "bitscore": alignment_map.get("score"),
                    "tm_score": _first_present(
                        alignment_map,
                        ("tmscore", "tmScore", "alntmscore", "lddt"),
                    ),
                    "query_tm_score": _first_present(alignment_map, ("qtmscore", "qTmScore")),
                    "target_tm_score": _first_present(alignment_map, ("ttmscore", "dbTmScore")),
                    "probability": _first_present(alignment_map, ("prob", "probability")),
                    "alignment_length": alignment_map.get("alnLength"),
                    "query_length": alignment_map.get("qLen"),
                    "target_length": alignment_map.get("dbLen"),
                }
            )
    return hits


def _alignment_maps(value: object) -> list[Mapping[str, object]]:
    if isinstance(value, dict):
        return [cast(Mapping[str, object], value)]
    if not isinstance(value, list):
        return []
    result: list[Mapping[str, object]] = []
    for item in cast(list[object], value):
        result.extend(_alignment_maps(item))
    return result


def _configured_database_path() -> str | None:
    for env_key in _DATABASE_ENV_KEYS:
        value = os.getenv(env_key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _resolve_database_path(value: object) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    configured = _configured_database_path()
    if configured is not None:
        return configured
    raise StepRunError(
        failure_type=FailureType.NON_RETRYABLE,
        message=(
            "Foldseek database path is required; set database_path or one of "
            f"{', '.join(_DATABASE_ENV_KEYS)}"
        ),
        code=FailureCode.CANDIDATE_PARAMS_INVALID.value,
    )


def _require_existing_path(value: object, *, field_name: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise StepRunError(
            failure_type=FailureType.NON_RETRYABLE,
            message=f"Foldseek requires non-empty '{field_name}'",
            code=FailureCode.CANDIDATE_PARAMS_INVALID.value,
        )
    path = Path(value)
    if not path.exists():
        code = (
            FailureCode.CANDIDATE_RESOURCE_CONSTRAINT.value
            if field_name == "database_path"
            else FailureCode.INPUT_RESOLUTION_FAILED.value
        )
        raise StepRunError(
            failure_type=FailureType.NON_RETRYABLE,
            message=f"Foldseek {field_name} does not exist: {path}",
            code=code,
        )
    return path


def _resolve_result_path(artifacts_dir: Path, inputs: dict[str, object]) -> Path:
    output_dir = inputs.get("output_dir")
    if isinstance(output_dir, str) and output_dir.strip():
        root = Path(output_dir)
    else:
        root = artifacts_dir
    root.mkdir(parents=True, exist_ok=True)
    task_id = _safe_slug(str(inputs.get("task_id") or "task"))
    step_id = _safe_slug(str(inputs.get("step_id") or "foldseek"))
    return root / f"{task_id}_{step_id}_foldseek.m8"


def _resolve_api_result_path(artifacts_dir: Path, inputs: dict[str, object]) -> Path:
    output_dir = inputs.get("output_dir")
    root = Path(output_dir) if isinstance(output_dir, str) and output_dir.strip() else artifacts_dir
    root.mkdir(parents=True, exist_ok=True)
    task_id = _safe_slug(str(inputs.get("task_id") or "task"))
    step_id = _safe_slug(str(inputs.get("step_id") or "foldseek"))
    return root / f"{task_id}_{step_id}_foldseek_api.json"


def _resolve_api_base_url(value: str | None) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip().rstrip("/")
    env_value = os.getenv(_API_BASE_URL_ENV_KEY)
    if isinstance(env_value, str) and env_value.strip():
        return env_value.strip().rstrip("/")
    try:
        provider_config = get_provider_config("foldseek_web")
    except KeyError:
        return _DEFAULT_API_BASE_URL
    configured = provider_config.base_url.strip()
    return configured.rstrip("/") if configured else _DEFAULT_API_BASE_URL


def _resolve_provider_timeout() -> float:
    env_value = os.getenv("FOLDSEEK_API_TIMEOUT_S")
    if isinstance(env_value, str) and env_value.strip():
        try:
            return float(env_value)
        except ValueError:
            return 60.0
    try:
        return float(get_provider_config("foldseek_web").timeout)
    except KeyError:
        return 60.0


def _resolve_api_databases(value: object) -> list[str]:
    if isinstance(value, list):
        raw_items = cast(list[object], value)
        databases = [item.strip() for item in raw_items if isinstance(item, str) and item.strip()]
        if databases:
            return databases
    if isinstance(value, tuple):
        raw_items = cast(tuple[object, ...], value)
        databases = [item.strip() for item in raw_items if isinstance(item, str) and item.strip()]
        if databases:
            return databases
    if isinstance(value, str) and value.strip():
        return _split_database_list(value)
    for env_key in _API_DATABASE_ENV_KEYS:
        env_value = os.getenv(env_key)
        if isinstance(env_value, str) and env_value.strip():
            return _split_database_list(env_value)
    return list(_DEFAULT_API_DATABASES)


def _split_database_list(value: str) -> list[str]:
    databases = [item.strip() for item in value.replace(";", ",").split(",")]
    return [item for item in databases if item] or list(_DEFAULT_API_DATABASES)


def _normalize_execution_mode(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_")
    if normalized in {"local", "local_cli", "cli"}:
        return "local_cli"
    if normalized in {"api", "remote", "remote_api", "foldseek_api", "rest"}:
        return "foldseek_api"
    return normalized or "foldseek_api"


def _uses_local_cli(mode: str, inputs: dict[str, object] | None = None) -> bool:
    input_mode = inputs.get("execution_mode") if inputs is not None else None
    if isinstance(input_mode, str) and input_mode.strip():
        return _normalize_execution_mode(input_mode) == "local_cli"
    return _normalize_execution_mode(mode) == "local_cli"


def _api_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _resolve_result_entry(inputs: dict[str, object]) -> int:
    raw = inputs.get("entry")
    if isinstance(raw, int) and raw >= 0:
        return raw
    return 0


def _json_object_response(response: httpx.Response, *, context: str) -> JsonObject:
    raw = cast(object, response.json())
    if not _is_json_value(raw):
        raise StepRunError(
            failure_type=FailureType.TOOL_ERROR,
            message=f"{context} response is not valid JSON",
            code=FailureCode.TOOL_EXECUTION_ERROR.value,
        )
    if not isinstance(raw, dict):
        raise StepRunError(
            failure_type=FailureType.TOOL_ERROR,
            message=f"{context} response must be a JSON object",
            code=FailureCode.TOOL_EXECUTION_ERROR.value,
        )
    return dict(raw)


def _is_json_value(value: object) -> TypeGuard[JsonValue]:
    if value is None or isinstance(value, str | int | float | bool):
        return True
    if isinstance(value, list):
        return all(_is_json_value(item) for item in cast(list[object], value))
    if isinstance(value, dict):
        return all(
            isinstance(key, str) and _is_json_value(item)
            for key, item in cast(Mapping[object, object], value).items()
        )
    return False


def _query_header(payload: JsonObject) -> str | None:
    query = payload.get("query")
    if isinstance(query, dict):
        return _json_string(query.get("header"))
    queries = payload.get("queries")
    if isinstance(queries, list) and queries:
        first = queries[0]
        if isinstance(first, dict):
            return _json_string(first.get("header"))
    return None


def _available_database_paths(payload: JsonObject) -> set[str]:
    databases = payload.get("databases")
    if not isinstance(databases, list):
        return set()
    paths: set[str] = set()
    for item in databases:
        if not isinstance(item, dict):
            continue
        path = _json_string(item.get("path"))
        name = _json_string(item.get("name"))
        if path:
            paths.add(path)
        if name:
            paths.add(name)
    return paths


def _json_string(value: JsonValue | None) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, int | float):
        return str(value)
    return None


def _object_string(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, int | float):
        return str(value)
    return None


def _first_present(payload: Mapping[str, object], keys: tuple[str, ...]) -> object:
    for key in keys:
        value = payload.get(key)
        if value is not None:
            return value
    return None


def _safe_slug(value: str) -> str:
    normalized = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in value)
    return normalized.strip("_") or "item"
