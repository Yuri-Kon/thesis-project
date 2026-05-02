from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Dict, Tuple

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


class FoldseekAdapter(BaseToolAdapter):
    """结构相似性检索适配器。"""

    tool_id = "foldseek"
    adapter_id = "foldseek"

    def __init__(
        self,
        *,
        binary: str = "foldseek",
        artifacts_dir: str | Path = "output/artifacts",
        runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    ) -> None:
        self.binary = binary
        self.artifacts_dir = Path(artifacts_dir)
        self.runner = runner or subprocess.run

    def resolve_inputs(self, step: PlanStep, context: WorkflowContext) -> Dict[str, Any]:
        inputs = resolve_step_inputs(step, context, required_keys=("pdb_path",))
        inputs["database_path"] = _resolve_database_path(inputs.get("database_path"))
        return inputs

    def describe_capabilities(self) -> Dict[str, Any]:
        return {
            **super().describe_capabilities(),
            "capability_id": "structure_similarity_search",
            "io_type": "structure_to_similarity_hits",
            "format_output": list(FOLDSEEK_FIELDS),
            "database_env_keys": list(_DATABASE_ENV_KEYS),
        }

    def healthcheck(self) -> Dict[str, Any]:
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

    def normalize_error(self, exc: Exception) -> Dict[str, Any]:
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
                "message": str(exc.stderr or exc.stdout or exc),
                "returncode": exc.returncode,
            }
        return super().normalize_error(exc)

    def run_local(self, inputs: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
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
                self.runner(cmd, capture_output=True, text=True, check=True)
            except subprocess.CalledProcessError as exc:
                raise StepRunError(
                    failure_type=FailureType.TOOL_ERROR,
                    message=f"Foldseek command failed: {exc.stderr or exc.stdout or exc}",
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


def parse_foldseek_tabular(text: str) -> list[Dict[str, Any]]:
    hits: list[Dict[str, Any]] = []
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


def _configured_database_path() -> str | None:
    for env_key in _DATABASE_ENV_KEYS:
        value = os.getenv(env_key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _resolve_database_path(value: Any) -> str:
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


def _require_existing_path(value: Any, *, field_name: str) -> Path:
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


def _resolve_result_path(artifacts_dir: Path, inputs: Dict[str, Any]) -> Path:
    output_dir = inputs.get("output_dir")
    if isinstance(output_dir, str) and output_dir.strip():
        root = Path(output_dir)
    else:
        root = artifacts_dir
    root.mkdir(parents=True, exist_ok=True)
    task_id = _safe_slug(str(inputs.get("task_id") or "task"))
    step_id = _safe_slug(str(inputs.get("step_id") or "foldseek"))
    return root / f"{task_id}_{step_id}_foldseek.m8"


def _safe_slug(value: str) -> str:
    normalized = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in value)
    return normalized.strip("_") or "item"
