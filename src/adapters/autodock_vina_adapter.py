from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Dict, Tuple

from src.adapters.base_tool_adapter import BaseToolAdapter
from src.adapters.tool_schema_utils import (
    build_docking_metrics,
    build_docking_outputs,
    resolve_step_inputs,
)
from src.models.contracts import PlanStep
from src.workflow.context import WorkflowContext
from src.workflow.errors import FailureCode, FailureType, StepRunError

__all__ = ["AutoDockVinaAdapter", "parse_autodock_vina_log"]


class AutoDockVinaAdapter(BaseToolAdapter):
    """AutoDock Vina 对接适配器。"""

    tool_id = "autodock_vina"
    adapter_id = "autodock_vina"

    def __init__(
        self,
        *,
        binary: str = "vina",
        runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    ) -> None:
        self.binary = binary
        self.runner = runner or subprocess.run

    def resolve_inputs(self, step: PlanStep, context: WorkflowContext) -> Dict[str, Any]:
        return resolve_step_inputs(
            step,
            context,
            required_keys=("receptor_path", "ligand_path"),
        )

    def run_local(self, inputs: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        if shutil.which(self.binary) is None:
            raise StepRunError(
                failure_type=FailureType.NON_RETRYABLE,
                message=f"AutoDock Vina binary '{self.binary}' is not installed",
                code=FailureCode.CANDIDATE_TOOL_UNAVAILABLE.value,
            )

        t0 = perf_counter()
        with tempfile.TemporaryDirectory(prefix="vina_") as tmp_dir:
            tmp_path = Path(tmp_dir)
            out_path = tmp_path / "poses.pdbqt"
            log_path = tmp_path / "vina.log"
            cmd = [
                self.binary,
                "--receptor",
                str(inputs["receptor_path"]),
                "--ligand",
                str(inputs["ligand_path"]),
                "--out",
                str(out_path),
                "--log",
                str(log_path),
            ]
            for option in ("center_x", "center_y", "center_z", "size_x", "size_y", "size_z", "cpu"):
                value = inputs.get(option)
                if value is not None:
                    cmd.extend([f"--{option}", str(value)])

            try:
                self.runner(cmd, capture_output=True, text=True, check=True)
            except subprocess.CalledProcessError as exc:
                raise StepRunError(
                    failure_type=FailureType.TOOL_ERROR,
                    message=f"AutoDock Vina command failed: {exc.stderr or exc.stdout or exc}",
                    code=FailureCode.TOOL_EXECUTION_ERROR.value,
                ) from exc

            poses = parse_autodock_vina_log(log_path.read_text(encoding="utf-8"))
            if poses and out_path.exists():
                poses[0]["pose_path"] = str(out_path)
            outputs = build_docking_outputs(self.tool_id, inputs, poses)
            metrics = build_docking_metrics(
                exec_type="local_cli",
                pose_count=len(poses),
                command=cmd,
            )
            metrics["duration_ms"] = int((perf_counter() - t0) * 1000)
            return outputs, metrics


def parse_autodock_vina_log(text: str) -> list[Dict[str, Any]]:
    poses: list[Dict[str, Any]] = []
    in_table = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("mode |"):
            in_table = True
            continue
        if not in_table or not line or line.startswith("-"):
            continue
        parts = line.split()
        if len(parts) < 4 or not parts[0].isdigit():
            continue
        poses.append(
            {
                "mode": int(parts[0]),
                "affinity": float(parts[1]),
                "rmsd_lb": float(parts[2]),
                "rmsd_ub": float(parts[3]),
            }
        )
    return poses
