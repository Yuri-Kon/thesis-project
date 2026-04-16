from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Dict, Tuple

from src.adapters.base_tool_adapter import BaseToolAdapter
from src.adapters.tool_schema_utils import (
    build_similarity_metrics,
    build_similarity_outputs,
    resolve_step_inputs,
)
from src.models.contracts import PlanStep
from src.workflow.context import WorkflowContext
from src.workflow.errors import FailureCode, FailureType, StepRunError

__all__ = ["MMseqs2Adapter", "parse_mmseqs_tabular"]

MMSEQS_FIELDS = (
    "query",
    "target",
    "pident",
    "alnlen",
    "mismatch",
    "gapopen",
    "qstart",
    "qend",
    "tstart",
    "tend",
    "evalue",
    "bits",
    "qlen",
    "tlen",
)


class MMseqs2Adapter(BaseToolAdapter):
    tool_id = "mmseqs2"
    adapter_id = "mmseqs2"

    def __init__(
        self,
        *,
        binary: str = "mmseqs",
        runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    ) -> None:
        self.binary = binary
        self.runner = runner or subprocess.run

    def resolve_inputs(self, step: PlanStep, context: WorkflowContext) -> Dict[str, Any]:
        return resolve_step_inputs(step, context, required_keys=("sequence", "database_path"))

    def run_local(self, inputs: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        if shutil.which(self.binary) is None:
            raise StepRunError(
                failure_type=FailureType.NON_RETRYABLE,
                message=f"MMseqs2 binary '{self.binary}' is not installed",
                code=FailureCode.CANDIDATE_TOOL_UNAVAILABLE.value,
            )

        t0 = perf_counter()
        with tempfile.TemporaryDirectory(prefix="mmseqs2_") as tmp_dir:
            tmp_path = Path(tmp_dir)
            query_path = tmp_path / "query.fasta"
            result_path = tmp_path / "result.m8"
            work_path = tmp_path / "work"
            query_path.write_text(
                f">{inputs.get('query_id', 'query_1')}\n{str(inputs['sequence']).strip()}\n",
                encoding="utf-8",
            )

            cmd = [
                self.binary,
                "easy-search",
                str(query_path),
                str(inputs["database_path"]),
                str(result_path),
                str(work_path),
                "--format-output",
                ",".join(MMSEQS_FIELDS),
            ]
            max_seqs = inputs.get("max_seqs")
            if max_seqs is not None:
                cmd.extend(["--max-seqs", str(max_seqs)])
            sensitivity = inputs.get("sensitivity")
            if sensitivity is not None:
                cmd.extend(["-s", str(sensitivity)])

            try:
                self.runner(cmd, capture_output=True, text=True, check=True)
            except subprocess.CalledProcessError as exc:
                raise StepRunError(
                    failure_type=FailureType.TOOL_ERROR,
                    message=f"MMseqs2 command failed: {exc.stderr or exc.stdout or exc}",
                    code=FailureCode.TOOL_EXECUTION_ERROR.value,
                ) from exc

            hits = parse_mmseqs_tabular(result_path.read_text(encoding="utf-8"))
            outputs = build_similarity_outputs(self.tool_id, inputs, hits)
            metrics = build_similarity_metrics(
                exec_type="local_cli",
                hit_count=len(hits),
                command=cmd,
            )
            metrics["duration_ms"] = int((perf_counter() - t0) * 1000)
            return outputs, metrics


def parse_mmseqs_tabular(text: str) -> list[Dict[str, Any]]:
    hits: list[Dict[str, Any]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < len(MMSEQS_FIELDS):
            continue
        hits.append(
            {
                "query_id": parts[0],
                "target_id": parts[1],
                "identity": parts[2],
                "alignment_length": parts[3],
                "query_start": parts[6],
                "query_end": parts[7],
                "target_start": parts[8],
                "target_end": parts[9],
                "evalue": parts[10],
                "bitscore": parts[11],
                "query_length": parts[12],
                "target_length": parts[13],
            }
        )
    return hits
