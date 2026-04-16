from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Dict, Tuple

from src.adapters.base_tool_adapter import BaseToolAdapter
from src.adapters.tool_schema_utils import (
    build_secondary_structure_metrics,
    build_secondary_structure_outputs,
    q3_bucket,
    resolve_step_inputs,
)
from src.models.contracts import PlanStep
from src.workflow.context import WorkflowContext
from src.workflow.errors import FailureCode, FailureType, StepRunError

__all__ = ["DSSPAdapter", "parse_dssp_output"]


class DSSPAdapter(BaseToolAdapter):
    tool_id = "dssp"
    adapter_id = "dssp"

    def __init__(
        self,
        *,
        binary: str = "mkdssp",
        runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    ) -> None:
        self.binary = binary
        self.runner = runner or subprocess.run

    def resolve_inputs(self, step: PlanStep, context: WorkflowContext) -> Dict[str, Any]:
        return resolve_step_inputs(step, context, required_keys=("pdb_path",))

    def run_local(self, inputs: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        if shutil.which(self.binary) is None:
            raise StepRunError(
                failure_type=FailureType.NON_RETRYABLE,
                message=f"DSSP binary '{self.binary}' is not installed",
                code=FailureCode.CANDIDATE_TOOL_UNAVAILABLE.value,
            )

        t0 = perf_counter()
        with tempfile.TemporaryDirectory(prefix="dssp_") as tmp_dir:
            output_path = Path(tmp_dir) / "result.dssp"
            cmd = [
                self.binary,
                "--output-format",
                "dssp",
                str(inputs["pdb_path"]),
                str(output_path),
            ]
            try:
                self.runner(cmd, capture_output=True, text=True, check=True)
            except subprocess.CalledProcessError as exc:
                raise StepRunError(
                    failure_type=FailureType.TOOL_ERROR,
                    message=f"DSSP command failed: {exc.stderr or exc.stdout or exc}",
                    code=FailureCode.TOOL_EXECUTION_ERROR.value,
                ) from exc

            rows = parse_dssp_output(output_path.read_text(encoding="utf-8"))
            outputs = build_secondary_structure_outputs(self.tool_id, inputs, rows)
            metrics = build_secondary_structure_metrics(
                exec_type="local_cli",
                residue_count=len(rows),
                command=cmd,
            )
            metrics["duration_ms"] = int((perf_counter() - t0) * 1000)
            return outputs, metrics


def parse_dssp_output(text: str) -> list[Dict[str, Any]]:
    rows: list[Dict[str, Any]] = []
    in_table = False
    for raw_line in text.splitlines():
        if raw_line.startswith("  #  RESIDUE AA STRUCTURE"):
            in_table = True
            continue
        if not in_table or len(raw_line) < 17:
            continue
        residue_no = raw_line[5:10].strip()
        insertion_code = raw_line[10:11].strip()
        chain_id = raw_line[11:12].strip() or "_"
        aa = raw_line[13:14].strip() or "X"
        q8 = raw_line[16:17].strip() or "C"
        rows.append(
            {
                "index": _safe_int(raw_line[0:5].strip()),
                "residue_number": residue_no,
                "insertion_code": insertion_code or None,
                "chain_id": chain_id,
                "amino_acid": aa,
                "q8": q8,
                "q3": q3_bucket(q8),
            }
        )
    return rows


def _safe_int(value: str) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None
