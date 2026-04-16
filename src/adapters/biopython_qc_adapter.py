"""
BioPythonQCAdapter - basic sequence/structure QC for Executor callable tool.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, Iterable, Optional, Tuple

from src.adapters.base_tool_adapter import BaseToolAdapter
from src.models.contracts import PlanStep
from src.workflow.context import WorkflowContext
from src.workflow.errors import FailureCode, FailureType, StepRunError

__all__ = ["BioPythonQCAdapter"]

_AA_ALPHABET = set("ACDEFGHIKLMNPQRSTVWY")


class BioPythonQCAdapter(BaseToolAdapter):
    """BioPython-based quality control adapter for S3-like QC checks."""

    tool_id = "biopython_qc"
    adapter_id = "biopython_qc"

    def resolve_inputs(
        self,
        step: PlanStep,
        context: WorkflowContext,
    ) -> Dict[str, Any]:
        resolved: Dict[str, Any] = {}
        for key, val in step.inputs.items():
            if isinstance(val, str) and "." in val:
                step_id, field = val.split(".", 1)
                if step_id and step_id.startswith("S"):
                    if not context.has_step_result(step_id):
                        raise ValueError(
                            f"Failed to resolve input reference '{val}' "
                            f"for step '{step.id}': step '{step_id}' not found in context"
                        )
                    try:
                        resolved_value = context.get_step_output(step_id, field)
                    except KeyError as exc:
                        raise ValueError(
                            f"Failed to resolve input reference '{val}' "
                            f"for step '{step.id}': field '{field}' not found in step '{step_id}' outputs"
                        ) from exc
                    resolved[key] = resolved_value
                    continue
            resolved[key] = val

        if "plddt_threshold" not in resolved:
            raw_threshold = context.task.constraints.get("plddt_threshold")
            if isinstance(raw_threshold, (int, float)):
                resolved["plddt_threshold"] = float(raw_threshold)

        resolved["task_id"] = context.task.task_id
        resolved["step_id"] = step.id
        return resolved

    def run_local(
        self,
        inputs: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        t0 = perf_counter()
        candidates = _collect_candidates(inputs)
        if not candidates:
            raise StepRunError(
                failure_type=FailureType.NON_RETRYABLE,
                message="biopython_qc requires at least one candidate input",
                code=FailureCode.INPUT_RESOLUTION_FAILED.value,
            )

        plddt_threshold = _to_float(inputs.get("plddt_threshold")) or 0.0

        qc_results: list[dict[str, Any]] = []
        for idx, candidate in enumerate(candidates, start=1):
            qc_results.append(
                _evaluate_candidate(
                    candidate,
                    index=idx,
                    plddt_threshold=plddt_threshold,
                )
            )

        passed = [row for row in qc_results if row.get("status") == "pass"]
        failed = [row for row in qc_results if row.get("status") == "fail"]
        reject_code_counts = Counter(
            code
            for row in qc_results
            for code in row.get("reject_codes", [])
            if isinstance(code, str)
        )

        best_row = _select_best_passed(passed)
        outputs: Dict[str, Any] = {
            "stage_id": "S3",
            "stage_name": "quality_gate",
            "capability_id": "quality_qc",
            "io_type": "sequence_structure_to_qc_metrics",
            "qc_metrics": qc_results,
            "qc_results": qc_results,
            "passed_samples": passed,
            "failed_samples": failed,
            "pass_count": len(passed),
            "fail_count": len(failed),
            "pass_fail": bool(passed),
            "reject_code_counts": dict(reject_code_counts),
            "quality_gate": {
                "status": "PASS" if passed else "BLOCK",
                "reject_codes": sorted(reject_code_counts.keys()),
                "qc_pass": bool(passed),
                "tool_lineage": sorted(
                    {
                        str(row.get("tool_id"))
                        for row in qc_results
                        if isinstance(row.get("tool_id"), str) and row.get("tool_id")
                    }
                ),
            },
        }
        if isinstance(best_row, dict):
            outputs["best_candidate_id"] = best_row.get("candidate_id")
            outputs["sequence"] = best_row.get("sequence")
            outputs["pdb_path"] = best_row.get("pdb_path")
            outputs["plddt"] = best_row.get("plddt")

        metrics = {
            "exec_type": "python",
            "duration_ms": int((perf_counter() - t0) * 1000),
            "evaluated_candidates": len(qc_results),
            "pass_count": len(passed),
            "fail_count": len(failed),
            "requirement2": {
                "capability_id": "quality_qc",
                "io_type": "sequence_structure_to_qc_metrics",
                "qc_pass": bool(passed),
            },
        }
        return outputs, metrics


def _collect_candidates(inputs: Dict[str, Any]) -> list[dict[str, Any]]:
    structure_results = inputs.get("structure_results")
    candidates: list[dict[str, Any]] = []

    if isinstance(structure_results, list):
        for idx, row in enumerate(structure_results, start=1):
            if not isinstance(row, dict):
                continue
            candidates.append(
                {
                    "candidate_id": row.get("candidate_id") or f"candidate_{idx}",
                    "sequence": row.get("sequence"),
                    "pdb_path": row.get("pdb_path"),
                    "plddt": row.get("plddt"),
                    "status": row.get("status"),
                    "tool_id": row.get("tool_id"),
                }
            )
        if candidates:
            return candidates

    sequence = inputs.get("sequence")
    pdb_path = inputs.get("pdb_path")
    if sequence is None and pdb_path is None:
        return []
    return [
        {
            "candidate_id": str(inputs.get("candidate_id", "candidate_1")),
            "sequence": sequence,
            "pdb_path": pdb_path,
            "plddt": inputs.get("plddt"),
            "status": "success",
            "tool_id": inputs.get("tool_id"),
        }
    ]


def _evaluate_candidate(
    candidate: Dict[str, Any],
    *,
    index: int,
    plddt_threshold: float,
) -> dict[str, Any]:
    candidate_id = str(candidate.get("candidate_id") or f"candidate_{index}")
    sequence = candidate.get("sequence")
    pdb_path = candidate.get("pdb_path")
    plddt = _to_float(candidate.get("plddt"))
    reject_codes: list[str] = []

    sequence_metrics = _evaluate_sequence(sequence, reject_codes)
    structure_metrics = _evaluate_structure(pdb_path, reject_codes)

    if plddt is not None and plddt_threshold > 0 and plddt < plddt_threshold:
        reject_codes.append("S3_LOW_CONFIDENCE")
    if plddt is None:
        inferred = _infer_plddt_from_structure_path(pdb_path)
        if inferred is not None:
            plddt = inferred

    status = "pass" if not reject_codes else "fail"
    return {
        "candidate_id": candidate_id,
        "status": status,
        "sequence": sequence if isinstance(sequence, str) else None,
        "pdb_path": pdb_path if isinstance(pdb_path, str) else None,
        "plddt": plddt,
        "reject_codes": reject_codes,
        "tool_id": candidate.get("tool_id"),
        "sequence_metrics": sequence_metrics,
        "structure_metrics": structure_metrics,
    }


def _evaluate_sequence(
    sequence: Any,
    reject_codes: list[str],
) -> dict[str, Any]:
    if not isinstance(sequence, str) or not sequence:
        reject_codes.append("S3_SEQUENCE_MISSING")
        return {
            "length": 0,
            "invalid_characters": [],
            "molecular_weight": None,
            "max_repeat_run": 0,
        }

    sequence_clean = sequence.strip().upper()
    invalid_chars = sorted({char for char in sequence_clean if char not in _AA_ALPHABET})
    if invalid_chars:
        reject_codes.append("S3_SEQUENCE_INVALID_CHARS")

    molecular_weight = _compute_molecular_weight(sequence_clean) if not invalid_chars else None
    max_repeat_run = _max_repeat_run(sequence_clean)
    return {
        "length": len(sequence_clean),
        "invalid_characters": invalid_chars,
        "molecular_weight": molecular_weight,
        "max_repeat_run": max_repeat_run,
    }


def _evaluate_structure(
    pdb_path: Any,
    reject_codes: list[str],
) -> dict[str, Any]:
    if not isinstance(pdb_path, str) or not pdb_path:
        reject_codes.append("S3_PDB_MISSING")
        return {
            "chain_count": 0,
            "residue_count": 0,
            "atom_count": 0,
            "mean_bfactor": None,
        }

    path = Path(pdb_path)
    if not path.exists() or not path.is_file():
        reject_codes.append("S3_PDB_NOT_FOUND")
        return {
            "chain_count": 0,
            "residue_count": 0,
            "atom_count": 0,
            "mean_bfactor": None,
        }

    try:
        return _parse_structure_metrics(path)
    except Exception:
        reject_codes.append("S3_STRUCTURE_PARSE_ERROR")
        return {
            "chain_count": 0,
            "residue_count": 0,
            "atom_count": 0,
            "mean_bfactor": None,
        }


def _parse_structure_metrics(path: Path) -> dict[str, Any]:
    try:
        from Bio.PDB import PDBParser
        from Bio.PDB.Polypeptide import is_aa
    except Exception:
        return _parse_structure_metrics_fallback(path)

    parser = PDBParser(QUIET=True)
    structure = parser.get_structure("qc", str(path))

    chain_ids: set[str] = set()
    residue_count = 0
    atom_count = 0
    bfactors: list[float] = []
    for model in structure:
        for chain in model:
            chain_ids.add(str(chain.id))
            for residue in chain:
                if not is_aa(residue, standard=True):
                    continue
                residue_count += 1
                for atom in residue.get_atoms():
                    atom_count += 1
                    bfactors.append(float(atom.get_bfactor()))

    return {
        "chain_count": len(chain_ids),
        "residue_count": residue_count,
        "atom_count": atom_count,
        "mean_bfactor": (sum(bfactors) / len(bfactors)) if bfactors else None,
    }


def _parse_structure_metrics_fallback(path: Path) -> dict[str, Any]:
    chain_ids: set[str] = set()
    residues: set[tuple[str, str]] = set()
    atom_count = 0
    bfactors: list[float] = []
    lines = path.read_text(encoding="utf-8").splitlines()
    for line in lines:
        if not (line.startswith("ATOM") or line.startswith("HETATM")):
            continue
        if len(line) < 66:
            continue
        atom_count += 1
        chain_id = line[21].strip() or "_"
        residue_key = line[22:27].strip() or str(atom_count)
        chain_ids.add(chain_id)
        residues.add((chain_id, residue_key))
        bfactor_str = line[60:66].strip()
        if bfactor_str:
            try:
                bfactors.append(float(bfactor_str))
            except ValueError:
                pass
    return {
        "chain_count": len(chain_ids),
        "residue_count": len(residues),
        "atom_count": atom_count,
        "mean_bfactor": (sum(bfactors) / len(bfactors)) if bfactors else None,
    }


def _compute_molecular_weight(sequence: str) -> Optional[float]:
    try:
        from Bio.SeqUtils import molecular_weight
    except Exception:
        return None
    try:
        return float(molecular_weight(sequence, seq_type="protein"))
    except Exception:
        return None


def _max_repeat_run(sequence: str) -> int:
    if not sequence:
        return 0
    max_run = 1
    current = 1
    for idx in range(1, len(sequence)):
        if sequence[idx] == sequence[idx - 1]:
            current += 1
            max_run = max(max_run, current)
        else:
            current = 1
    return max_run


def _select_best_passed(rows: Iterable[dict[str, Any]]) -> Optional[dict[str, Any]]:
    scored = list(rows)
    if not scored:
        return None

    def _score_key(row: dict[str, Any]) -> tuple[float, int]:
        plddt = _to_float(row.get("plddt")) or 0.0
        seq = row.get("sequence")
        seq_len = len(seq) if isinstance(seq, str) else 0
        return plddt, seq_len

    scored.sort(key=_score_key, reverse=True)
    return scored[0]


def _infer_plddt_from_structure_path(value: Any) -> Optional[float]:
    if not isinstance(value, str) or not value.endswith(".pdb"):
        return None
    path = Path(value)
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    values: list[float] = []
    for line in text.splitlines():
        if not (line.startswith("ATOM") or line.startswith("HETATM")):
            continue
        if len(line) < 66:
            continue
        b_factor_str = line[60:66].strip()
        if not b_factor_str:
            continue
        try:
            values.append(float(b_factor_str))
        except ValueError:
            continue
    if not values:
        return None
    return sum(values) / len(values)


def _to_float(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None
