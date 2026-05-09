from __future__ import annotations

import math
import shlex
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, Tuple, override

from src.adapters.base_tool_adapter import BaseToolAdapter
from src.adapters.tool_schema_utils import (
    build_stability_metrics,
    build_stability_outputs,
    resolve_step_inputs,
)
from src.models.contracts import PlanStep
from src.workflow.context import WorkflowContext
from src.workflow.errors import FailureCode, FailureType, StepRunError

__all__ = ["MDAnalysisAdapter"]


class MDAnalysisAdapter(BaseToolAdapter):
    """基于结构坐标生成稳定性代理指标。"""

    tool_id: str = "mda_analysis"
    adapter_id: str | None = "mda_analysis"

    @override
    def resolve_inputs(self, step: PlanStep, context: WorkflowContext) -> Dict[str, Any]:
        return resolve_step_inputs(step, context, required_keys=("pdb_path",))

    @override
    def run_local(self, inputs: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        pdb_path = Path(str(inputs["pdb_path"]))
        if not pdb_path.exists():
            raise StepRunError(
                failure_type=FailureType.NON_RETRYABLE,
                message=f"PDB file not found: {pdb_path}",
                code=FailureCode.INPUT_RESOLUTION_FAILED.value,
            )

        t0 = perf_counter()
        coordinates, residue_ids = _parse_structure_coordinates(pdb_path)
        if not coordinates:
            raise StepRunError(
                failure_type=FailureType.NON_RETRYABLE,
                message=f"No atom coordinates found in structure file: {pdb_path}",
                code=FailureCode.OUTPUT_MISSING.value,
            )

        center = [
            sum(point[axis] for point in coordinates) / len(coordinates)
            for axis in range(3)
        ]
        squared_distances = [
            sum((point[axis] - center[axis]) ** 2 for axis in range(3))
            for point in coordinates
        ]
        radius_of_gyration = math.sqrt(sum(squared_distances) / len(squared_distances))
        mins = [min(point[axis] for point in coordinates) for axis in range(3)]
        maxs = [max(point[axis] for point in coordinates) for axis in range(3)]
        coordinate_span = math.sqrt(sum((maxs[axis] - mins[axis]) ** 2 for axis in range(3)))

        stability_payload = {
            "atom_count": len(coordinates),
            "residue_count": len(residue_ids),
            "frame_count": 1,
            "radius_of_gyration": round(radius_of_gyration, 6),
            "coordinate_span": round(coordinate_span, 6),
        }
        outputs = build_stability_outputs(self.tool_id, inputs, stability_payload)
        metrics = build_stability_metrics(exec_type="python", frame_count=1)
        metrics["duration_ms"] = int((perf_counter() - t0) * 1000)
        return outputs, metrics


def _parse_structure_coordinates(
    path: Path,
) -> tuple[list[tuple[float, float, float]], set[str]]:
    text = path.read_text(encoding="utf-8")
    coordinates, residue_ids = _parse_pdb_coordinates(text)
    if coordinates:
        return coordinates, residue_ids
    return _parse_mmcif_coordinates(text)


def _parse_pdb_coordinates(
    text: str,
) -> tuple[list[tuple[float, float, float]], set[str]]:
    coordinates: list[tuple[float, float, float]] = []
    residue_ids: set[str] = set()
    for line in text.splitlines():
        if not line.startswith(("ATOM", "HETATM")) or len(line) < 54:
            continue
        try:
            x = float(line[30:38].strip())
            y = float(line[38:46].strip())
            z = float(line[46:54].strip())
        except ValueError:
            continue
        chain_id = line[21:22].strip() or "_"
        residue_no = line[22:26].strip() or "0"
        residue_ids.add(f"{chain_id}:{residue_no}")
        coordinates.append((x, y, z))
    return coordinates, residue_ids


def _parse_mmcif_coordinates(
    text: str,
) -> tuple[list[tuple[float, float, float]], set[str]]:
    coordinates: list[tuple[float, float, float]] = []
    residue_ids: set[str] = set()
    atom_site_headers: list[str] = []
    reading_atom_site = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            if reading_atom_site and atom_site_headers:
                reading_atom_site = False
            continue
        if line == "loop_":
            atom_site_headers = []
            reading_atom_site = False
            continue
        if line.startswith("_atom_site."):
            atom_site_headers.append(line.split()[0])
            reading_atom_site = True
            continue
        if not reading_atom_site or not atom_site_headers:
            continue
        if not line.startswith(("ATOM", "HETATM")):
            reading_atom_site = False
            atom_site_headers = []
            continue

        row = _split_mmcif_row(line)
        if len(row) < len(atom_site_headers):
            continue
        values = dict(zip(atom_site_headers, row, strict=False))
        point = _mmcif_point(values)
        if point is None:
            continue
        chain_id = (
            values.get("_atom_site.auth_asym_id")
            or values.get("_atom_site.label_asym_id")
            or "_"
        )
        residue_no = (
            values.get("_atom_site.auth_seq_id")
            or values.get("_atom_site.label_seq_id")
            or "0"
        )
        residue_ids.add(f"{chain_id}:{residue_no}")
        coordinates.append(point)

    return coordinates, residue_ids


def _split_mmcif_row(line: str) -> list[str]:
    lexer = shlex.shlex(line, posix=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    return list(lexer)


def _mmcif_point(
    values: dict[str, str],
) -> tuple[float, float, float] | None:
    try:
        return (
            float(values["_atom_site.Cartn_x"]),
            float(values["_atom_site.Cartn_y"]),
            float(values["_atom_site.Cartn_z"]),
        )
    except (KeyError, ValueError):
        return None
