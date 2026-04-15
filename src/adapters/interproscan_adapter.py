from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Dict, Tuple

from src.adapters.base_tool_adapter import BaseToolAdapter
from src.adapters.tool_schema_utils import (
    build_function_annotation_metrics,
    build_function_annotation_outputs,
    resolve_step_inputs,
)
from src.models.contracts import PlanStep
from src.workflow.context import WorkflowContext
from src.workflow.errors import FailureCode, FailureType, StepRunError

__all__ = ["InterProScanAdapter", "parse_interproscan_tsv"]


class InterProScanAdapter(BaseToolAdapter):
    """功能注释适配器。"""

    tool_id = "interproscan"
    adapter_id = "interproscan"

    def __init__(
        self,
        *,
        binary: str = "interproscan.sh",
        runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    ) -> None:
        self.binary = binary
        self.runner = runner or subprocess.run

    def resolve_inputs(self, step: PlanStep, context: WorkflowContext) -> Dict[str, Any]:
        return resolve_step_inputs(step, context, required_keys=("sequence",))

    def run_local(self, inputs: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        if shutil.which(self.binary) is None:
            raise StepRunError(
                failure_type=FailureType.NON_RETRYABLE,
                message=f"InterProScan binary '{self.binary}' is not installed",
                code=FailureCode.CANDIDATE_TOOL_UNAVAILABLE.value,
            )

        t0 = perf_counter()
        with tempfile.TemporaryDirectory(prefix="interproscan_") as tmp_dir:
            tmp_path = Path(tmp_dir)
            fasta_path = tmp_path / "query.fasta"
            output_path = tmp_path / "result.tsv"
            fasta_path.write_text(
                f">{inputs.get('query_id', 'query_1')}\n{str(inputs['sequence']).strip()}\n",
                encoding="utf-8",
            )

            cmd = [
                self.binary,
                "-i",
                str(fasta_path),
                "-f",
                "tsv",
                "-o",
                str(output_path),
            ]
            applications = inputs.get("applications")
            if isinstance(applications, list) and applications:
                cmd.extend(["-appl", ",".join(str(item) for item in applications)])

            try:
                self.runner(cmd, capture_output=True, text=True, check=True)
            except subprocess.CalledProcessError as exc:
                raise StepRunError(
                    failure_type=FailureType.TOOL_ERROR,
                    message=f"InterProScan command failed: {exc.stderr or exc.stdout or exc}",
                    code=FailureCode.TOOL_EXECUTION_ERROR.value,
                ) from exc

            function_terms = parse_interproscan_tsv(output_path.read_text(encoding="utf-8"))
            outputs = build_function_annotation_outputs(self.tool_id, inputs, function_terms)
            metrics = build_function_annotation_metrics(
                exec_type="local_cli",
                term_count=len(function_terms),
                command=cmd,
            )
            metrics["duration_ms"] = int((perf_counter() - t0) * 1000)
            return outputs, metrics


def parse_interproscan_tsv(text: str) -> list[Dict[str, Any]]:
    terms: list[Dict[str, Any]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 13:
            continue
        terms.append(
            {
                "query_id": parts[0],
                "sequence_md5": parts[1],
                "sequence_length": parts[2],
                "analysis": parts[3],
                "signature_accession": parts[4],
                "signature_description": parts[5],
                "start": parts[6],
                "end": parts[7],
                "score": parts[8],
                "status": parts[9],
                "date": parts[10],
                "interpro_accession": parts[11],
                "interpro_description": parts[12],
                "go_terms": parts[13].split("|") if len(parts) > 13 and parts[13] else [],
                "pathways": parts[14].split("|") if len(parts) > 14 and parts[14] else [],
            }
        )
    return terms
