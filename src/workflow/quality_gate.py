from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import Enum
from itertools import groupby
from typing import Any, Mapping, Sequence

__all__ = [
    "QualityGateRejectCode",
    "QUALITY_GATE_ALL_REJECTED_CODE",
    "evaluate_quality_gate_batch",
]


class QualityGateRejectCode(str, Enum):
    """S3 quality gate reject code enum."""

    SOURCE_STRUCTURE_FAILED = "S3_SOURCE_STRUCTURE_FAILED"
    SEQUENCE_MISSING = "S3_SEQUENCE_MISSING"
    SEQUENCE_LENGTH_OUT_OF_RANGE = "S3_SEQUENCE_LENGTH_OUT_OF_RANGE"
    SEQUENCE_INVALID_CHAR = "S3_SEQUENCE_INVALID_CHAR"
    STRUCTURE_MISSING = "S3_STRUCTURE_MISSING"
    PLDDT_MISSING = "S3_PLDDT_MISSING"
    PLDDT_BELOW_THRESHOLD = "S3_PLDDT_BELOW_THRESHOLD"
    LOW_COMPLEXITY_COMPOSITION = "S3_LOW_COMPLEXITY_COMPOSITION"
    LOW_COMPLEXITY_REPEAT = "S3_LOW_COMPLEXITY_REPEAT"


QUALITY_GATE_ALL_REJECTED_CODE = "S3_ALL_CANDIDATES_REJECTED"

_AMINO_ACIDS = set("ACDEFGHIKLMNPQRSTVWY")
_DEFAULT_MIN_LENGTH = 20
_DEFAULT_MAX_LENGTH = 400
_DEFAULT_MIN_PLDDT = 0.7
_DEFAULT_MAX_RESIDUE_FRACTION = 0.7
_DEFAULT_MAX_REPEAT_RUN = 6


@dataclass(frozen=True)
class _QualityGateConfig:
    min_length: int
    max_length: int
    min_plddt: float
    max_residue_fraction: float
    max_repeat_run: int


def evaluate_quality_gate_batch(
    candidates: Sequence[Mapping[str, Any]],
    *,
    constraints: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate S3 quality gate for a batch of S2 candidates."""
    cfg = _resolve_config(constraints or {})
    qc_rows: list[dict[str, Any]] = []
    reject_counter: Counter[str] = Counter()

    for index, candidate in enumerate(candidates):
        qc_row = _evaluate_candidate(candidate, index=index, cfg=cfg)
        qc_rows.append(qc_row)
        for code in qc_row["reject_codes"]:
            reject_counter[code] += 1

    passed_rows = [row for row in qc_rows if row["status"] == "pass"]
    failed_rows = [row for row in qc_rows if row["status"] == "fail"]
    pass_count = len(passed_rows)
    fail_count = len(failed_rows)
    total = len(qc_rows)
    pass_rate = round(pass_count / total, 6) if total else 0.0

    qc_metrics = {
        "rule_config": {
            "min_length": cfg.min_length,
            "max_length": cfg.max_length,
            "min_plddt": cfg.min_plddt,
            "max_residue_fraction": cfg.max_residue_fraction,
            "max_repeat_run": cfg.max_repeat_run,
        },
        "total_candidates": total,
        "pass_count": pass_count,
        "fail_count": fail_count,
        "pass_rate": pass_rate,
        "reject_code_counts": dict(sorted(reject_counter.items())),
    }
    return {
        "qc_results": qc_rows,
        "passed_samples": passed_rows,
        "failed_samples": failed_rows,
        "pass_count": pass_count,
        "fail_count": fail_count,
        "pass_fail": pass_count > 0,
        "qc_metrics": qc_metrics,
        "reject_code_counts": qc_metrics["reject_code_counts"],
    }


def _resolve_config(constraints: Mapping[str, Any]) -> _QualityGateConfig:
    local = constraints.get("quality_gate")
    gate_constraints = local if isinstance(local, dict) else {}

    min_length = _to_int(
        _pick_value(
            gate_constraints,
            constraints,
            keys=("min_length",),
        ),
        default=_DEFAULT_MIN_LENGTH,
        minimum=1,
    )
    max_length = _to_int(
        _pick_value(
            gate_constraints,
            constraints,
            keys=("max_length",),
        ),
        default=_DEFAULT_MAX_LENGTH,
        minimum=min_length,
    )

    length_range = _pick_value(gate_constraints, constraints, keys=("length_range",))
    if isinstance(length_range, (list, tuple)) and len(length_range) == 2:
        min_from_range = _to_int(length_range[0], default=min_length, minimum=1)
        max_from_range = _to_int(length_range[1], default=max_length, minimum=min_from_range)
        min_length = min_from_range
        max_length = max_from_range

    min_plddt = _to_float(
        _pick_value(
            gate_constraints,
            constraints,
            keys=("min_plddt", "plddt_threshold"),
        ),
        default=_DEFAULT_MIN_PLDDT,
    )
    max_residue_fraction = _to_float(
        _pick_value(
            gate_constraints,
            constraints,
            keys=(
                "max_residue_fraction",
                "low_complexity_max_residue_fraction",
            ),
        ),
        default=_DEFAULT_MAX_RESIDUE_FRACTION,
    )
    max_repeat_run = _to_int(
        _pick_value(
            gate_constraints,
            constraints,
            keys=("max_repeat_run", "low_complexity_max_repeat_run"),
        ),
        default=_DEFAULT_MAX_REPEAT_RUN,
        minimum=1,
    )

    if min_length > max_length:
        min_length, max_length = max_length, min_length
    if max_residue_fraction <= 0:
        max_residue_fraction = _DEFAULT_MAX_RESIDUE_FRACTION

    return _QualityGateConfig(
        min_length=min_length,
        max_length=max_length,
        min_plddt=min_plddt,
        max_residue_fraction=max_residue_fraction,
        max_repeat_run=max_repeat_run,
    )


def _evaluate_candidate(
    candidate: Mapping[str, Any],
    *,
    index: int,
    cfg: _QualityGateConfig,
) -> dict[str, Any]:
    candidate_id = _as_string(candidate.get("candidate_id")) or f"s2_candidate_{index + 1}"
    source_status = _as_string(candidate.get("status"))
    sequence = _as_string(candidate.get("sequence"))
    pdb_path = _as_string(candidate.get("pdb_path"))
    source_failure_code = _as_string(candidate.get("failure_code"))
    source_failure_reason = _as_string(candidate.get("failure_reason")) or _as_string(
        candidate.get("error_message")
    )
    plddt = _extract_plddt(candidate)
    reject_codes: list[str] = []
    reject_reasons: list[str] = []

    length_value = len(sequence) if sequence else 0
    max_residue_fraction = _max_residue_fraction(sequence)
    longest_repeat_run = _longest_repeat_run(sequence)
    unique_residue_count = len(set(sequence)) if sequence else 0

    if source_status and source_status not in {"success", "pass"}:
        _append_reject(
            reject_codes,
            reject_reasons,
            code=QualityGateRejectCode.SOURCE_STRUCTURE_FAILED.value,
            reason=(
                f"S2 source candidate failed before quality gate"
                f" (source_code={source_failure_code or 'unknown'})"
            ),
        )
    else:
        if not sequence:
            _append_reject(
                reject_codes,
                reject_reasons,
                code=QualityGateRejectCode.SEQUENCE_MISSING.value,
                reason="sequence is required for quality gate",
            )
        else:
            if length_value < cfg.min_length or length_value > cfg.max_length:
                _append_reject(
                    reject_codes,
                    reject_reasons,
                    code=QualityGateRejectCode.SEQUENCE_LENGTH_OUT_OF_RANGE.value,
                    reason=(
                        f"sequence length {length_value} is outside "
                        f"[{cfg.min_length}, {cfg.max_length}]"
                    ),
                )
            if not _is_valid_sequence(sequence):
                _append_reject(
                    reject_codes,
                    reject_reasons,
                    code=QualityGateRejectCode.SEQUENCE_INVALID_CHAR.value,
                    reason="sequence contains invalid residues",
                )
            if max_residue_fraction > cfg.max_residue_fraction:
                _append_reject(
                    reject_codes,
                    reject_reasons,
                    code=QualityGateRejectCode.LOW_COMPLEXITY_COMPOSITION.value,
                    reason=(
                        f"max residue fraction {max_residue_fraction:.3f} exceeds "
                        f"{cfg.max_residue_fraction:.3f}"
                    ),
                )
            if longest_repeat_run > cfg.max_repeat_run:
                _append_reject(
                    reject_codes,
                    reject_reasons,
                    code=QualityGateRejectCode.LOW_COMPLEXITY_REPEAT.value,
                    reason=(
                        f"longest repeat run {longest_repeat_run} exceeds "
                        f"{cfg.max_repeat_run}"
                    ),
                )

        if not pdb_path:
            _append_reject(
                reject_codes,
                reject_reasons,
                code=QualityGateRejectCode.STRUCTURE_MISSING.value,
                reason="pdb_path is required for quality gate",
            )
        if plddt is None:
            _append_reject(
                reject_codes,
                reject_reasons,
                code=QualityGateRejectCode.PLDDT_MISSING.value,
                reason="plddt is required for quality gate",
            )
        else:
            threshold = _resolve_plddt_threshold(plddt, cfg.min_plddt)
            if plddt < threshold:
                _append_reject(
                    reject_codes,
                    reject_reasons,
                    code=QualityGateRejectCode.PLDDT_BELOW_THRESHOLD.value,
                    reason=f"plddt {plddt:.3f} is below threshold {threshold:.3f}",
                )

    status = "pass" if not reject_codes else "fail"
    qc_flags = {
        "length_ok": cfg.min_length <= length_value <= cfg.max_length if sequence else False,
        "valid_sequence_chars": _is_valid_sequence(sequence) if sequence else False,
        "has_structure": bool(pdb_path),
        "has_plddt": plddt is not None,
        "low_complexity_ok": (
            bool(sequence)
            and max_residue_fraction <= cfg.max_residue_fraction
            and longest_repeat_run <= cfg.max_repeat_run
        ),
    }
    qc_metrics = {
        "length": length_value,
        "unique_residue_count": unique_residue_count,
        "max_residue_fraction": max_residue_fraction,
        "longest_repeat_run": longest_repeat_run,
        "plddt": plddt,
    }

    row = {
        "candidate_id": candidate_id,
        "status": status,
        "pass_fail": status == "pass",
        "reason": "; ".join(reject_reasons),
        "reject_codes": sorted(set(reject_codes)),
        "reject_reasons": reject_reasons,
        "qc_flags": qc_flags,
        "qc_metrics": qc_metrics,
        "sequence": sequence,
        "pdb_path": pdb_path,
        "plddt": plddt,
        "tool_id": _as_string(candidate.get("tool_id")),
        "source_failure_code": source_failure_code,
        "source_failure_reason": source_failure_reason,
        "lineage": candidate.get("lineage")
        if isinstance(candidate.get("lineage"), dict)
        else {},
    }
    return row


def _append_reject(
    reject_codes: list[str],
    reject_reasons: list[str],
    *,
    code: str,
    reason: str,
) -> None:
    reject_codes.append(code)
    reject_reasons.append(reason)


def _pick_value(
    local: Mapping[str, Any],
    global_constraints: Mapping[str, Any],
    *,
    keys: Sequence[str],
) -> Any:
    for key in keys:
        if key in local:
            return local.get(key)
    for key in keys:
        if key in global_constraints:
            return global_constraints.get(key)
    return None


def _to_int(
    value: Any,
    *,
    default: int,
    minimum: int,
) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        parsed = int(value)
    else:
        parsed = default
    return max(parsed, minimum)


def _to_float(
    value: Any,
    *,
    default: float,
) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    return default


def _as_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _is_valid_sequence(sequence: str) -> bool:
    return bool(sequence) and all(char in _AMINO_ACIDS for char in sequence)


def _extract_plddt(candidate: Mapping[str, Any]) -> float | None:
    direct = _to_numeric(candidate.get("plddt"))
    if direct is not None:
        return direct
    confidence = candidate.get("confidence")
    if isinstance(confidence, dict):
        conf_value = _to_numeric(confidence.get("plddt_mean"))
        if conf_value is not None:
            return conf_value
    metrics = candidate.get("metrics")
    if isinstance(metrics, dict):
        metric_value = _to_numeric(metrics.get("plddt_mean"))
        if metric_value is not None:
            return metric_value
    return None


def _to_numeric(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _resolve_plddt_threshold(plddt: float, threshold: float) -> float:
    if plddt > 1.0 and threshold <= 1.0:
        return threshold * 100.0
    if plddt <= 1.0 and threshold > 1.0:
        return threshold / 100.0
    return threshold


def _max_residue_fraction(sequence: str | None) -> float:
    if not sequence:
        return 0.0
    counts = Counter(sequence)
    return max(counts.values()) / len(sequence)


def _longest_repeat_run(sequence: str | None) -> int:
    if not sequence:
        return 0
    return max(sum(1 for _ in group) for _, group in groupby(sequence))
