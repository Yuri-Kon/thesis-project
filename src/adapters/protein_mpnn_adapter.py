"""
ProteinMPNNAdapter - ProteinMPNN 序列设计工具适配器

支持多种执行模式：
- NVIDIA NIM 远程调用（优先）
- Python 本地占位实现（回退）
- Nextflow 模块调用（可选）

设计规格（见 design/system-implementation-design.md）：
- 输入：pdb_path / length_range / goal 等
- 输出：sequence, sequence_score, candidates
"""
from __future__ import annotations

import json
import hashlib
import os
import re
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, List, Optional, Tuple

from src.adapters.base_tool_adapter import BaseToolAdapter
from src.engines.nim_client import NvidiaNIMClient
from src.engines.nextflow_adapter import WorkflowEngineAdapter
from src.models.contracts import PlanStep
from src.workflow.context import WorkflowContext
from src.workflow.errors import FailureCode, FailureType, StepRunError

__all__ = ["ProteinMPNNAdapter"]

_AMINO_ACIDS = "ACDEFGHIKLMNPQRSTVWY"


class ProteinMPNNAdapter(BaseToolAdapter):
    """ProteinMPNN 序列设计工具适配器"""

    tool_id = "protein_mpnn"
    adapter_id = "protein_mpnn"

    def __init__(
        self,
        *,
        execution_mode: str = "auto",
        module_path: str | Path | None = None,
        nextflow_profile: str = "test",
        artifacts_dir: str | Path | None = None,
        default_num_candidates: int = 5,
        nim_client: NvidiaNIMClient | None = None,
        nim_model_id: str = "ipd/proteinmpnn/predict",
        nim_max_atom_lines: int = 200,
        nim_ca_only: bool = False,
        nim_use_soluble_model: bool = False,
        nim_sampling_temp: Optional[List[float]] = None,
    ) -> None:
        if execution_mode not in {"auto", "python", "nextflow", "nvidia_nim"}:
            raise ValueError(
                "execution_mode must be one of: 'auto', 'python', 'nextflow', 'nvidia_nim'"
            )
        self.execution_mode = execution_mode
        self.module_path = Path(module_path or "nf/modules/protein_mpnn.nf")
        self.engine = WorkflowEngineAdapter(profile=nextflow_profile)
        self.artifacts_dir = Path(artifacts_dir or "output/artifacts")
        self.default_num_candidates = max(int(default_num_candidates), 1)
        self.nim_model_id = nim_model_id
        self._nim_client_injected = nim_client is not None
        self.nim_client = nim_client or NvidiaNIMClient(model_id=nim_model_id)
        self.nim_max_atom_lines = max(int(nim_max_atom_lines), 1)
        self.nim_ca_only = bool(nim_ca_only)
        self.nim_use_soluble_model = bool(nim_use_soluble_model)
        self.nim_sampling_temp = nim_sampling_temp or [0.1]

    def _effective_execution_mode(self) -> str:
        if self.execution_mode != "auto":
            return self.execution_mode
        api_key = getattr(self.nim_client, "api_key", "")
        if self._nim_client_injected:
            if isinstance(api_key, str) and api_key:
                return "nvidia_nim"
            return "python"
        if isinstance(api_key, str) and api_key:
            return "nvidia_nim"
        if os.getenv("NIM_API_KEY"):
            return "nvidia_nim"
        return "python"

    def resolve_inputs(
        self,
        step: PlanStep,
        context: WorkflowContext,
    ) -> Dict[str, Any]:
        """解析输入参数，支持引用语义（如 "S1.pdb_path"）。"""
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

        if "pdb_path" not in resolved and "structure_template_pdb" in resolved:
            resolved["pdb_path"] = resolved["structure_template_pdb"]

        if "length_range" not in resolved:
            length_range = context.task.constraints.get("length_range")
            if length_range is not None:
                resolved["length_range"] = length_range

        if "goal" not in resolved:
            resolved["goal"] = context.task.goal

        if "num_candidates" not in resolved:
            resolved["num_candidates"] = self.default_num_candidates

        if "pdb_path" not in resolved:
            raise ValueError(
                f"Missing required input 'pdb_path' for ProteinMPNN step '{step.id}'"
            )

        effective_mode = self._effective_execution_mode()
        if effective_mode in {"python", "nextflow"} and "length_range" not in resolved:
            raise ValueError(
                f"Missing required input 'length_range' for ProteinMPNN step '{step.id}'"
            )

        resolved["task_id"] = context.task.task_id
        resolved["step_id"] = step.id

        return resolved

    def run_local(
        self,
        inputs: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """执行 ProteinMPNN 生成候选序列。"""
        mode = self._effective_execution_mode()
        if mode == "nextflow":
            return self._run_nextflow(inputs)
        if mode == "nvidia_nim":
            return self._run_nvidia_nim(inputs)

        return self._run_python(inputs)

    def _run_nextflow(
        self,
        inputs: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        task_id = inputs.get("task_id", "unknown")
        step_id = inputs.get("step_id", "unknown")
        return self.engine.execute(
            module_path=self.module_path,
            inputs=inputs,
            task_id=task_id,
            step_id=step_id,
            tool_name=self.tool_id,
        )

    def _run_python(
        self,
        inputs: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        t0 = perf_counter()
        pdb_path = inputs.get("pdb_path") or inputs.get("structure_template_pdb")
        if not pdb_path:
            raise StepRunError(
                failure_type=FailureType.NON_RETRYABLE,
                message="Missing required input 'pdb_path'",
                code="PROTEIN_MPNN_MISSING_PDB",
            )

        length_range = inputs.get("length_range")
        try:
            min_len, max_len = _normalize_length_range(length_range)
        except ValueError as exc:
            raise StepRunError(
                failure_type=FailureType.NON_RETRYABLE,
                message=str(exc),
                code="PROTEIN_MPNN_INVALID_LENGTH_RANGE",
            ) from exc

        num_candidates = _normalize_positive_int(
            inputs.get("num_candidates", self.default_num_candidates),
            fallback=self.default_num_candidates,
        )
        goal = str(inputs.get("goal") or "")

        rng = _seeded_rng(pdb_path, goal, min_len, max_len, num_candidates)
        candidates = _generate_candidates(rng, min_len, max_len, num_candidates)
        selected = max(candidates, key=lambda item: item["score"])

        task_id = inputs.get("task_id", "unknown")
        step_id = inputs.get("step_id", "unknown")
        artifacts_path = self._write_artifacts(
            task_id=task_id,
            step_id=step_id,
            pdb_path=pdb_path,
            candidates=candidates,
        )

        duration_ms = int((perf_counter() - t0) * 1000)
        outputs = {
            "sequence": selected["sequence"],
            "sequence_score": selected["score"],
            "candidates": candidates,
            "artifacts": {"candidates_path": str(artifacts_path)},
        }
        metrics = {
            "exec_type": "python",
            "duration_ms": duration_ms,
            "num_candidates": len(candidates),
        }
        return outputs, metrics

    def _run_nvidia_nim(
        self,
        inputs: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        t0 = perf_counter()
        pdb_path = inputs.get("pdb_path") or inputs.get("structure_template_pdb")
        if not pdb_path:
            raise StepRunError(
                failure_type=FailureType.NON_RETRYABLE,
                message="Missing required input 'pdb_path'",
                code=FailureCode.NIM_INVALID_INPUT.value,
            )

        pdb_payload = _read_pdb_for_nim(str(pdb_path), max_atom_lines=self.nim_max_atom_lines)
        sampling_temp = _normalize_sampling_temp(
            inputs.get("sampling_temp", self.nim_sampling_temp)
        )
        payload = {
            "input_pdb": pdb_payload,
            "ca_only": bool(inputs.get("ca_only", self.nim_ca_only)),
            "use_soluble_model": bool(
                inputs.get("use_soluble_model", self.nim_use_soluble_model)
            ),
            "sampling_temp": sampling_temp,
        }

        response = self.nim_client.call_sync(payload)
        response_data = _unwrap_nim_response(response)
        mfasta = _extract_mfasta(response_data)
        if not mfasta:
            raise StepRunError(
                failure_type=FailureType.TOOL_ERROR,
                message="NIM ProteinMPNN response missing 'mfasta'",
                code=FailureCode.NIM_INVALID_RESPONSE.value,
            )

        candidates = _parse_mfasta_candidates(mfasta)
        if not candidates:
            raise StepRunError(
                failure_type=FailureType.TOOL_ERROR,
                message="NIM ProteinMPNN response contains no valid sequence candidates",
                code=FailureCode.NIM_INVALID_RESPONSE.value,
            )

        selected = _select_primary_candidate(candidates)
        task_id = inputs.get("task_id", "unknown")
        step_id = inputs.get("step_id", "unknown")
        artifacts_path = self._write_artifacts(
            task_id=task_id,
            step_id=step_id,
            pdb_path=str(pdb_path),
            candidates=candidates,
        )

        duration_ms = int((perf_counter() - t0) * 1000)
        outputs = {
            "sequence": selected["sequence"],
            "sequence_score": float(selected.get("score", 0.0)),
            "candidates": candidates,
            "artifacts": {"candidates_path": str(artifacts_path)},
        }
        metrics = {
            "exec_type": "nvidia_nim",
            "provider": "nvidia_nim",
            "model_id": self.nim_model_id,
            "duration_ms": duration_ms,
            "num_candidates": len(candidates),
        }
        return outputs, metrics

    def _write_artifacts(
        self,
        *,
        task_id: str,
        step_id: str,
        pdb_path: str,
        candidates: List[Dict[str, Any]],
    ) -> Path:
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        path = self.artifacts_dir / f"protein_mpnn_{task_id}_{step_id}.json"
        payload = {
            "tool": self.tool_id,
            "task_id": task_id,
            "step_id": step_id,
            "pdb_path": pdb_path,
            "candidates": candidates,
        }
        path.write_text(json.dumps(payload, ensure_ascii=True, indent=2))
        return path


def _normalize_length_range(value: Any) -> Tuple[int, int]:
    if isinstance(value, (list, tuple)) and len(value) == 2:
        min_len = int(value[0])
        max_len = int(value[1])
    else:
        raise ValueError("length_range must be a 2-item list or tuple")

    if min_len <= 0 or max_len <= 0:
        raise ValueError("length_range values must be positive")
    if min_len > max_len:
        raise ValueError("length_range min must be <= max")
    return min_len, max_len


def _normalize_positive_int(value: Any, *, fallback: int) -> int:
    try:
        value_int = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(value_int, 1)


def _seeded_rng(
    pdb_path: str,
    goal: str,
    min_len: int,
    max_len: int,
    num_candidates: int,
) -> "random.Random":
    import random

    seed_payload = f"{pdb_path}|{goal}|{min_len}|{max_len}|{num_candidates}"
    seed = int(hashlib.sha256(seed_payload.encode("utf-8")).hexdigest(), 16) % (2**32)
    return random.Random(seed)


def _generate_candidates(
    rng: "random.Random",
    min_len: int,
    max_len: int,
    num_candidates: int,
) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    for _ in range(num_candidates):
        length = rng.randint(min_len, max_len)
        sequence = "".join(rng.choice(_AMINO_ACIDS) for _ in range(length))
        score = round(rng.random(), 6)
        candidates.append({"sequence": sequence, "score": score})
    return candidates


def _read_pdb_for_nim(pdb_path: str, *, max_atom_lines: int) -> str:
    path = Path(pdb_path)
    if not path.exists():
        raise StepRunError(
            failure_type=FailureType.NON_RETRYABLE,
            message=f"PDB file not found: {pdb_path}",
            code=FailureCode.NIM_INVALID_INPUT.value,
        )
    pdb_text = path.read_text(encoding="utf-8")
    atom_lines = [line for line in pdb_text.splitlines() if line.startswith("ATOM")]
    if atom_lines:
        return "\n".join(atom_lines[:max_atom_lines])
    if pdb_text.strip():
        return pdb_text
    raise StepRunError(
        failure_type=FailureType.NON_RETRYABLE,
        message=f"PDB file is empty: {pdb_path}",
        code=FailureCode.NIM_INVALID_INPUT.value,
    )


def _normalize_sampling_temp(value: Any) -> List[float]:
    if isinstance(value, (int, float)):
        return [float(value)]
    if isinstance(value, (list, tuple)):
        out = [float(item) for item in value if isinstance(item, (int, float))]
        if out:
            return out
    return [0.1]


def _unwrap_nim_response(response: Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(response.get("outputs"), dict):
        return response["outputs"]
    if isinstance(response.get("output"), dict):
        return response["output"]
    return response


def _extract_mfasta(data: Dict[str, Any]) -> Optional[str]:
    for key in ("mfasta", "fasta", "output_fasta"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _parse_mfasta_candidates(mfasta: str) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    current_header = ""
    current_seq_parts: List[str] = []

    def flush_current() -> None:
        if not current_seq_parts:
            return
        sequence = "".join(current_seq_parts).strip().upper()
        if not sequence:
            return
        candidates.append(
            {
                "sequence": sequence,
                "score": _extract_score_from_header(current_header),
                "header": current_header,
            }
        )

    for raw_line in mfasta.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(">"):
            flush_current()
            current_header = line[1:].strip()
            current_seq_parts = []
        else:
            current_seq_parts.append(line.replace(" ", ""))
    flush_current()
    return candidates


def _extract_score_from_header(header: str) -> float:
    match = re.search(r"score=([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)", header)
    if not match:
        return 0.0
    return float(match.group(1))


def _select_primary_candidate(candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
    sampled = [
        candidate
        for candidate in candidates
        if "sample=" in str(candidate.get("header", "")).lower()
    ]
    if sampled:
        return sampled[0]
    return candidates[0]
