from __future__ import annotations

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
    "lddt",
    "alnlen",
    "qlen",
    "tlen",
)


class FoldseekAdapter(BaseToolAdapter):
    """结构相似性检索适配器。"""

    tool_id = "foldseek"
    adapter_id = "foldseek"

    def __init__(
        self,
        *,
        binary: str = "foldseek",
        runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    ) -> None:
        self.binary = binary
        self.runner = runner or subprocess.run

    def resolve_inputs(self, step: PlanStep, context: WorkflowContext) -> Dict[str, Any]:
        return resolve_step_inputs(step, context, required_keys=("pdb_path", "database_path"))

    def run_local(self, inputs: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        if shutil.which(self.binary) is None:
            raise StepRunError(
                failure_type=FailureType.NON_RETRYABLE,
                message=f"Foldseek binary '{self.binary}' is not installed",
                code=FailureCode.CANDIDATE_TOOL_UNAVAILABLE.value,
            )

        t0 = perf_counter()
        with tempfile.TemporaryDirectory(prefix="foldseek_") as tmp_dir:
            tmp_path = Path(tmp_dir)
            result_path = tmp_path / "result.m8"
            work_path = tmp_path / "work"
            cmd = [
                self.binary,
                "easy-search",
                str(inputs["pdb_path"]),
                str(inputs["database_path"]),
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
            outputs = build_structure_similarity_outputs(self.tool_id, inputs, hits)
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
                "lddt": parts[5],
                "alignment_length": parts[6],
                "query_length": parts[7],
                "target_length": parts[8],
            }
        )
    return hits
