#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_SCORE_KEYS = {"feasibility", "objective", "risk", "cost", "overall"}
DEFAULT_REQUIRED_TOP_LEVEL_KEYS = {
    "sample_id",
    "context",
    "candidates",
    "selected",
    "outcome",
    "audit_trace",
}
DEFAULT_REQUIRED_CONTEXT_KEYS = {"task_id", "status_path"}
DEFAULT_REQUIRED_OUTCOME_KEYS = {"final_status", "step_results", "scores"}
DEFAULT_REQUIRED_CANDIDATE_KEYS = {"score_breakdown", "risk_level", "cost_estimate"}
DEFAULT_OUTPUT_DIR = Path("output/training/w11-data-2")
DEFAULT_INPUT_SAMPLES = Path("output/training/w11-data-1/samples.jsonl")


@dataclass(frozen=True)
class GateIssue:
    code: str
    severity: str
    message: str
    field: str | None = None
    tool_id: str | None = None
    capability_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
        }
        if self.field:
            payload["field"] = self.field
        if self.tool_id:
            payload["tool_id"] = self.tool_id
        if self.capability_id:
            payload["capability_id"] = self.capability_id
        return payload


def _str_value(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _json_dump(data: Any) -> str:
    return json.dumps(data, ensure_ascii=True, sort_keys=True)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            payload = json.loads(text)
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(_json_dump(row) + "\n")


def _stable_split(task_id: str, train_ratio: float, val_ratio: float) -> str:
    digest = hashlib.md5(task_id.encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) % 10000
    ratio = bucket / 10000.0
    if ratio < train_ratio:
        return "train"
    if ratio < train_ratio + val_ratio:
        return "val"
    return "test"


def _parse_iso_datetime(value: str | None) -> datetime | None:
    text = _str_value(value)
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalize_sequence(value: str | None) -> str | None:
    if not value:
        return None
    normalized = "".join(value.split()).upper()
    return normalized or None


def _load_report(report_path: str | None) -> dict[str, Any]:
    if not report_path:
        return {}
    path = Path(report_path)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def _extract_sequence(sample: dict[str, Any], report: dict[str, Any]) -> str | None:
    context = sample.get("context")
    if isinstance(context, dict):
        sequence = _normalize_sequence(_str_value(context.get("sequence")))
        if sequence:
            return sequence

    selected = sample.get("selected")
    if isinstance(selected, dict):
        candidate = selected.get("selected_candidate")
        if isinstance(candidate, dict):
            payload = candidate.get("payload")
            if isinstance(payload, dict):
                sequence = _normalize_sequence(_str_value(payload.get("sequence")))
                if sequence:
                    return sequence

    sequence = _normalize_sequence(_str_value(report.get("sequence")))
    if sequence:
        return sequence
    return None


def _extract_time_anchor(sample: dict[str, Any]) -> str | None:
    context = sample.get("context")
    if not isinstance(context, dict):
        return None
    time_window = context.get("time_window")
    if not isinstance(time_window, dict):
        return None

    for key in ("last_ts", "first_ts"):
        value = _str_value(time_window.get(key))
        if value:
            return value
    return None


def _extract_structure_hash(sample: dict[str, Any]) -> str | None:
    outcome = sample.get("outcome")
    if not isinstance(outcome, dict):
        return None

    structure_path = _str_value(outcome.get("structure_pdb_path"))
    if not structure_path:
        return None

    path = Path(structure_path)
    if path.exists():
        try:
            content = path.read_bytes()
            return hashlib.sha256(content).hexdigest()
        except OSError:
            return _hash_text(structure_path)
    return _hash_text(structure_path)


def _extract_tool_lineage(sample: dict[str, Any]) -> list[str]:
    lineage: set[str] = set()

    candidates = sample.get("candidates")
    if isinstance(candidates, list):
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            tool_id = _str_value(candidate.get("tool_id"))
            if tool_id:
                lineage.add(tool_id)

    selected = sample.get("selected")
    if isinstance(selected, dict):
        selected_candidate = selected.get("selected_candidate")
        if isinstance(selected_candidate, dict):
            tool_id = _str_value(selected_candidate.get("tool_id"))
            if tool_id:
                lineage.add(tool_id)

    outcome = sample.get("outcome")
    if isinstance(outcome, dict):
        step_results = outcome.get("step_results")
        if isinstance(step_results, list):
            for item in step_results:
                if not isinstance(item, dict):
                    continue
                tool_id = _str_value(item.get("tool"))
                if tool_id:
                    lineage.add(tool_id)

    return sorted(lineage)


def _extract_capabilities(sample: dict[str, Any]) -> set[str]:
    capability_ids: set[str] = set()

    candidates = sample.get("candidates")
    if isinstance(candidates, list):
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            capability = _str_value(candidate.get("capability_id"))
            if capability:
                capability_ids.add(capability)

    context = sample.get("context")
    if isinstance(context, dict):
        plan_metadata = context.get("plan_metadata")
        if isinstance(plan_metadata, dict):
            kg = plan_metadata.get("kg_explanation")
            if isinstance(kg, dict):
                steps = kg.get("steps")
                if isinstance(steps, list):
                    for step in steps:
                        if not isinstance(step, dict):
                            continue
                        capabilities = step.get("capabilities")
                        if not isinstance(capabilities, list):
                            continue
                        for item in capabilities:
                            if not isinstance(item, dict):
                                continue
                            capability = _str_value(item.get("capability_id"))
                            if capability:
                                capability_ids.add(capability)

    return capability_ids


def _extract_qc_pass(sample: dict[str, Any], report: dict[str, Any]) -> bool | None:
    values: list[Any] = []
    outcome = sample.get("outcome")
    if isinstance(outcome, dict):
        scores = outcome.get("scores")
        if isinstance(scores, dict):
            values.extend(
                [
                    scores.get("qc_pass"),
                    scores.get("qc_ok"),
                    scores.get("quality_pass"),
                ]
            )

    if isinstance(report.get("scores"), dict):
        report_scores = report["scores"]
        values.extend(
            [
                report_scores.get("qc_pass"),
                report_scores.get("qc_ok"),
                report_scores.get("quality_pass"),
            ]
        )

    for item in values:
        if isinstance(item, bool):
            return item
        if isinstance(item, str):
            normalized = item.strip().lower()
            if normalized in {"pass", "passed", "ok", "true"}:
                return True
            if normalized in {"fail", "failed", "false"}:
                return False
    return None


def _extract_plddt(sample: dict[str, Any], report: dict[str, Any]) -> float | None:
    values: list[Any] = []
    outcome = sample.get("outcome")
    if isinstance(outcome, dict):
        scores = outcome.get("scores")
        if isinstance(scores, dict):
            values.extend(
                [
                    scores.get("plddt_mean"),
                    scores.get("pLDDT"),
                    scores.get("plddt"),
                ]
            )

    if isinstance(report.get("scores"), dict):
        report_scores = report["scores"]
        values.extend(
            [
                report_scores.get("plddt_mean"),
                report_scores.get("pLDDT"),
                report_scores.get("plddt"),
            ]
        )

    for value in values:
        if isinstance(value, (int, float)):
            number = float(value)
            if number > 1.0 and number <= 100.0:
                return round(number / 100.0, 6)
            if 0.0 <= number <= 1.0:
                return round(number, 6)
    return None


def _score_completeness(candidates: list[dict[str, Any]]) -> float | None:
    if not candidates:
        return None

    complete = 0
    for candidate in candidates:
        score = candidate.get("score_breakdown")
        if not isinstance(score, dict):
            continue
        score_keys = {
            key for key in score.keys() if isinstance(key, str) and key
        }
        if DEFAULT_SCORE_KEYS.issubset(score_keys):
            complete += 1
    return round(complete / len(candidates), 6)


def _missing_top_level_issues(sample: dict[str, Any]) -> list[GateIssue]:
    issues: list[GateIssue] = []
    for key in sorted(DEFAULT_REQUIRED_TOP_LEVEL_KEYS):
        if key not in sample:
            issues.append(
                GateIssue(
                    code="SCHEMA_MISSING_TOP_LEVEL",
                    severity="block",
                    message=f"Top-level key '{key}' is required.",
                    field=key,
                )
            )

    context = sample.get("context")
    if not isinstance(context, dict):
        issues.append(
            GateIssue(
                code="SCHEMA_INVALID_CONTEXT",
                severity="block",
                message="Field 'context' must be an object.",
                field="context",
            )
        )
    else:
        for key in sorted(DEFAULT_REQUIRED_CONTEXT_KEYS):
            if context.get(key) in (None, "", []):
                issues.append(
                    GateIssue(
                        code="MISSING_CONTEXT_FIELD",
                        severity="block",
                        message=f"Context field '{key}' is required.",
                        field=f"context.{key}",
                    )
                )

    outcome = sample.get("outcome")
    if not isinstance(outcome, dict):
        issues.append(
            GateIssue(
                code="SCHEMA_INVALID_OUTCOME",
                severity="block",
                message="Field 'outcome' must be an object.",
                field="outcome",
            )
        )
    else:
        for key in sorted(DEFAULT_REQUIRED_OUTCOME_KEYS):
            if key not in outcome:
                issues.append(
                    GateIssue(
                        code="MISSING_OUTCOME_FIELD",
                        severity="block",
                        message=f"Outcome field '{key}' is required.",
                        field=f"outcome.{key}",
                    )
                )

    return issues


def _candidate_issues(sample: dict[str, Any]) -> list[GateIssue]:
    issues: list[GateIssue] = []
    candidates = sample.get("candidates")
    if not isinstance(candidates, list):
        return issues

    for idx, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            issues.append(
                GateIssue(
                    code="SCHEMA_INVALID_CANDIDATE",
                    severity="block",
                    message=f"Candidate at index {idx} must be an object.",
                    field=f"candidates[{idx}]",
                )
            )
            continue

        candidate_id = _str_value(candidate.get("candidate_id")) or f"idx-{idx}"
        tool_id = _str_value(candidate.get("tool_id"))
        capability_id = _str_value(candidate.get("capability_id"))

        for field in sorted(DEFAULT_REQUIRED_CANDIDATE_KEYS):
            value = candidate.get(field)
            if value in (None, "", []):
                issues.append(
                    GateIssue(
                        code=f"MISSING_{field.upper()}",
                        severity="block",
                        message=f"Candidate '{candidate_id}' missing required field '{field}'.",
                        field=f"candidates[{idx}].{field}",
                        tool_id=tool_id,
                        capability_id=capability_id,
                    )
                )

        if not tool_id:
            issues.append(
                GateIssue(
                    code="REQ2_MISSING_TOOL_ID",
                    severity="block",
                    message=f"Candidate '{candidate_id}' missing Requirement-2 field 'tool_id'.",
                    field=f"candidates[{idx}].tool_id",
                    capability_id=capability_id,
                )
            )
        if not capability_id:
            issues.append(
                GateIssue(
                    code="REQ2_MISSING_CAPABILITY_ID",
                    severity="block",
                    message=f"Candidate '{candidate_id}' missing Requirement-2 field 'capability_id'.",
                    field=f"candidates[{idx}].capability_id",
                    tool_id=tool_id,
                )
            )

    return issues


def _failure_issues(sample: dict[str, Any]) -> list[GateIssue]:
    issues: list[GateIssue] = []
    outcome = sample.get("outcome")
    if not isinstance(outcome, dict):
        return issues

    final_status = _str_value(outcome.get("final_status")) or "UNKNOWN"
    step_results = outcome.get("step_results")
    failed_steps: list[dict[str, Any]] = []
    if isinstance(step_results, list):
        failed_steps = [
            step
            for step in step_results
            if isinstance(step, dict)
            and (
                (_str_value(step.get("status")) or "").lower() == "failed"
                or step.get("failure_type")
                or step.get("error_message")
            )
        ]

    if final_status != "FAILED" and not failed_steps:
        return issues

    failure_types = outcome.get("step_failure_types")
    has_failure_types = isinstance(failure_types, list) and any(
        _str_value(item) for item in failure_types
    )
    if not has_failure_types:
        issues.append(
            GateIssue(
                code="MISSING_FAILURE_TYPE",
                severity="block",
                message="Failed sample must include outcome.step_failure_types.",
                field="outcome.step_failure_types",
            )
        )

    for idx, step in enumerate(failed_steps):
        failure_type = _str_value(step.get("failure_type"))
        if not failure_type:
            issues.append(
                GateIssue(
                    code="MISSING_FAILURE_TYPE",
                    severity="block",
                    message=f"Failed step at index {idx} is missing failure_type.",
                    field=f"outcome.step_results[{idx}].failure_type",
                    tool_id=_str_value(step.get("tool")),
                )
            )

    return issues


def _req2_issues(
    *,
    sample: dict[str, Any],
    capabilities: set[str],
    sequence_hash: str | None,
    structure_hash: str | None,
    qc_pass: bool | None,
    plddt: float | None,
    score_completeness: float | None,
    plddt_min: float,
    score_completeness_min: float,
) -> list[GateIssue]:
    issues: list[GateIssue] = []

    for capability in sorted(capabilities):
        if capability in {"sequence_generation", "sequence_design"} and not sequence_hash:
            issues.append(
                GateIssue(
                    code="REQ2_SEQUENCE_HASH_MISSING",
                    severity="block",
                    message=f"Capability '{capability}' requires sequence evidence for dedupe.",
                    field="sequence_hash",
                    capability_id=capability,
                )
            )

        if capability == "structure_prediction":
            if not structure_hash:
                issues.append(
                    GateIssue(
                        code="REQ2_STRUCTURE_HASH_MISSING",
                        severity="block",
                        message="Capability 'structure_prediction' requires structure hash.",
                        field="structure_hash",
                        capability_id=capability,
                    )
                )
            if plddt is None:
                issues.append(
                    GateIssue(
                        code="REQ2_PLDDT_MISSING",
                        severity="block",
                        message="Capability 'structure_prediction' requires pLDDT score.",
                        field="plddt_mean",
                        capability_id=capability,
                    )
                )
            elif plddt < plddt_min:
                issues.append(
                    GateIssue(
                        code="REQ2_PLDDT_BELOW_THRESHOLD",
                        severity="warn",
                        message=(
                            "Capability 'structure_prediction' pLDDT below threshold "
                            f"({plddt:.3f} < {plddt_min:.3f})."
                        ),
                        field="plddt_mean",
                        capability_id=capability,
                    )
                )

        if capability == "quality_qc":
            if qc_pass is None:
                issues.append(
                    GateIssue(
                        code="REQ2_QC_PASS_MISSING",
                        severity="block",
                        message="Capability 'quality_qc' requires qc_pass.",
                        field="qc_pass",
                        capability_id=capability,
                    )
                )
            elif qc_pass is False:
                issues.append(
                    GateIssue(
                        code="REQ2_QC_BLOCKED",
                        severity="block",
                        message="Capability 'quality_qc' rejected because qc_pass=false.",
                        field="qc_pass",
                        capability_id=capability,
                    )
                )

        if capability == "objective_scoring":
            if score_completeness is None:
                issues.append(
                    GateIssue(
                        code="REQ2_SCORE_COMPLETENESS_MISSING",
                        severity="block",
                        message="Capability 'objective_scoring' requires score completeness.",
                        field="score_completeness_rate",
                        capability_id=capability,
                    )
                )
            elif score_completeness < score_completeness_min:
                issues.append(
                    GateIssue(
                        code="REQ2_SCORE_COMPLETENESS_BELOW_THRESHOLD",
                        severity="block",
                        message=(
                            "Capability 'objective_scoring' score completeness below threshold "
                            f"({score_completeness:.3f} < {score_completeness_min:.3f})."
                        ),
                        field="score_completeness_rate",
                        capability_id=capability,
                    )
                )

    return issues


def _quality_score(row: dict[str, Any]) -> tuple[int, str, str]:
    sample = row["sample"]
    outcome = sample.get("outcome")
    context = sample.get("context")
    completeness = 0

    if row.get("sequence_hash"):
        completeness += 1
    if row.get("structure_hash"):
        completeness += 1
    if row.get("qc_pass") is not None:
        completeness += 1
    if row.get("plddt") is not None:
        completeness += 1

    candidates = sample.get("candidates")
    if isinstance(candidates, list) and candidates:
        completeness += 1

    last_ts = ""
    if isinstance(context, dict):
        time_window = context.get("time_window")
        if isinstance(time_window, dict):
            last_ts = _str_value(time_window.get("last_ts")) or ""

    sample_id = _str_value(sample.get("sample_id")) or ""
    _ = outcome
    return completeness, last_ts, sample_id


def _collect_issue_context(issues: list[GateIssue]) -> list[dict[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for issue in issues:
        tool_id = issue.tool_id or "unknown"
        capability_id = issue.capability_id or "unknown"
        if tool_id == "unknown" and capability_id == "unknown":
            continue
        pairs.add((tool_id, capability_id))
    return [
        {"tool_id": tool_id, "capability_id": capability_id}
        for tool_id, capability_id in sorted(pairs)
    ]


def _assign_task_splits(
    *,
    rows: list[dict[str, Any]],
    train_ratio: float,
    val_ratio: float,
    split_strategy: str,
) -> tuple[dict[str, str], set[str]]:
    task_to_anchor: dict[str, datetime | None] = {}
    for row in rows:
        task_id = row["task_id"]
        current = task_to_anchor.get(task_id)
        candidate = row.get("time_anchor_dt")
        if current is None:
            task_to_anchor[task_id] = candidate
            continue
        if candidate is None:
            continue
        if candidate < current:
            task_to_anchor[task_id] = candidate

    if split_strategy == "task_hash":
        mapping = {
            task_id: _stable_split(task_id, train_ratio, val_ratio)
            for task_id in task_to_anchor
        }
        return mapping, set()

    with_ts = sorted(
        (
            (task_id, anchor)
            for task_id, anchor in task_to_anchor.items()
            if anchor is not None
        ),
        key=lambda item: (item[1], item[0]),
    )
    without_ts = sorted(task_id for task_id, anchor in task_to_anchor.items() if anchor is None)
    total = len(with_ts)

    mapping: dict[str, str] = {}
    if total > 0:
        for index, (task_id, _) in enumerate(with_ts):
            ratio = index / total
            if ratio < train_ratio:
                mapping[task_id] = "train"
            elif ratio < train_ratio + val_ratio:
                mapping[task_id] = "val"
            else:
                mapping[task_id] = "test"

    for task_id in without_ts:
        mapping[task_id] = _stable_split(task_id, train_ratio, val_ratio)

    return mapping, set(without_ts)


def quality_gate_training_samples(
    *,
    samples_path: Path,
    output_dir: Path,
    train_ratio: float,
    val_ratio: float,
    plddt_min: float,
    score_completeness_min: float,
    split_strategy: str,
) -> dict[str, Any]:
    if not samples_path.exists():
        raise FileNotFoundError(f"samples file not found: {samples_path}")

    if train_ratio <= 0 or val_ratio <= 0 or train_ratio + val_ratio >= 1:
        raise ValueError("Invalid split ratio. Require train > 0, val > 0, train + val < 1.")

    if split_strategy not in {"time", "task_hash"}:
        raise ValueError("split_strategy must be one of: time, task_hash")

    output_dir.mkdir(parents=True, exist_ok=True)
    raw_samples = _read_jsonl(samples_path)
    rows: list[dict[str, Any]] = []
    issues_by_sample: dict[str, list[GateIssue]] = defaultdict(list)

    for sample in raw_samples:
        sample_id = _str_value(sample.get("sample_id")) or "sample::unknown"
        context = sample.get("context")
        context_dict = context if isinstance(context, dict) else {}
        task_id = _str_value(context_dict.get("task_id")) or sample_id

        report_path = None
        outcome = sample.get("outcome")
        if isinstance(outcome, dict):
            report_path = _str_value(outcome.get("report_path"))
        report = _load_report(report_path)

        sequence = _extract_sequence(sample, report)
        sequence_hash = _hash_text(sequence) if sequence else None
        structure_hash = _extract_structure_hash(sample)
        tool_lineage = _extract_tool_lineage(sample)
        capabilities = _extract_capabilities(sample)
        plddt = _extract_plddt(sample, report)
        qc_pass = _extract_qc_pass(sample, report)
        candidates = sample.get("candidates")
        candidate_rows = [item for item in candidates if isinstance(item, dict)] if isinstance(candidates, list) else []
        score_completeness = _score_completeness(candidate_rows)
        time_anchor = _extract_time_anchor(sample)
        time_anchor_dt = _parse_iso_datetime(time_anchor)

        issues: list[GateIssue] = []
        issues.extend(_missing_top_level_issues(sample))
        issues.extend(_candidate_issues(sample))
        issues.extend(_failure_issues(sample))
        issues.extend(
            _req2_issues(
                sample=sample,
                capabilities=capabilities,
                sequence_hash=sequence_hash,
                structure_hash=structure_hash,
                qc_pass=qc_pass,
                plddt=plddt,
                score_completeness=score_completeness,
                plddt_min=plddt_min,
                score_completeness_min=score_completeness_min,
            )
        )

        issues_by_sample[sample_id].extend(issues)
        rows.append(
            {
                "sample": sample,
                "sample_id": sample_id,
                "task_id": task_id,
                "split": None,
                "time_anchor": time_anchor,
                "time_anchor_dt": time_anchor_dt,
                "capabilities": sorted(capabilities),
                "tool_lineage": tool_lineage,
                "tool_lineage_hash": _hash_text("|".join(tool_lineage)) if tool_lineage else None,
                "sequence_hash": sequence_hash,
                "structure_hash": structure_hash,
                "plddt": plddt,
                "qc_pass": qc_pass,
                "score_completeness": score_completeness,
            }
        )

    task_splits, task_ids_without_time = _assign_task_splits(
        rows=rows,
        train_ratio=train_ratio,
        val_ratio=val_ratio,
        split_strategy=split_strategy,
    )
    for row in rows:
        row["split"] = task_splits[row["task_id"]]
        if split_strategy == "time" and row["task_id"] in task_ids_without_time:
            issues_by_sample[row["sample_id"]].append(
                GateIssue(
                    code="SPLIT_TIME_MISSING_FALLBACK_HASH",
                    severity="warn",
                    message=(
                        "Missing time_window timestamp for time split; "
                        "fallback to task-hash split."
                    ),
                    field="context.time_window",
                )
            )

    dedupe_groups: dict[tuple[str | None, str | None, str | None], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        dedupe_key = (
            row.get("sequence_hash"),
            row.get("structure_hash"),
            row.get("tool_lineage_hash"),
        )
        if dedupe_key == (None, None, None):
            continue
        dedupe_groups[dedupe_key].append(row)

    cross_split_leakage_groups = 0
    for group in dedupe_groups.values():
        if len(group) <= 1:
            continue
        split_set = {item["split"] for item in group}
        if len(split_set) > 1:
            cross_split_leakage_groups += 1

        keep = sorted(
            group,
            key=lambda item: _quality_score(item),
            reverse=True,
        )[0]
        keep_id = keep["sample_id"]

        for row in group:
            if row["sample_id"] == keep_id:
                continue
            issues_by_sample[row["sample_id"]].append(
                GateIssue(
                    code="DUPLICATE_CROSS_TOOL",
                    severity="block",
                    message=(
                        "Duplicate sample detected by (sequence_hash, structure_hash, tool_lineage). "
                        f"Kept sample: {keep_id}."
                    ),
                    field="dedupe_key",
                )
            )
            if len(split_set) > 1:
                issues_by_sample[row["sample_id"]].append(
                    GateIssue(
                        code="LEAKAGE_CROSS_SPLIT",
                        severity="block",
                        message="Duplicate appears across multiple splits and may leak information.",
                        field="split",
                    )
                )

    gated_rows: list[dict[str, Any]] = []
    failed_rows: list[dict[str, Any]] = []
    code_counter: Counter[str] = Counter()
    status_counter: Counter[str] = Counter()

    for row in sorted(rows, key=lambda item: item["sample_id"]):
        sample = row["sample"]
        sample_id = row["sample_id"]
        issues = issues_by_sample.get(sample_id, [])
        for issue in issues:
            code_counter[issue.code] += 1

        severities = {issue.severity for issue in issues}
        status = "PASS"
        if "block" in severities:
            status = "BLOCK"
        elif "warn" in severities:
            status = "WARN"
        status_counter[status] += 1

        gate_payload = {
            "status": status,
            "split": row["split"],
            "reject_codes": sorted({issue.code for issue in issues}),
            "issues": [issue.to_dict() for issue in issues],
            "tool_lineage": row["tool_lineage"],
            "capability_ids": row["capabilities"],
            "sequence_hash": row["sequence_hash"],
            "structure_hash": row["structure_hash"],
            "plddt_mean": row["plddt"],
            "qc_pass": row["qc_pass"],
            "score_completeness_rate": row["score_completeness"],
        }

        gated_row = dict(sample)
        gated_row["quality_gate"] = gate_payload
        gated_rows.append(gated_row)

        if status == "BLOCK":
            failed_rows.append(
                {
                    "sample_id": sample_id,
                    "task_id": row["task_id"],
                    "split": row["split"],
                    "status": status,
                    "reject_codes": gate_payload["reject_codes"],
                    "tool_context": _collect_issue_context(issues),
                    "issues": gate_payload["issues"],
                }
            )

    total = len(gated_rows)
    pass_count = status_counter.get("PASS", 0)
    warn_count = status_counter.get("WARN", 0)
    block_count = status_counter.get("BLOCK", 0)
    missing_count = sum(
        1
        for row in gated_rows
        if any(code.startswith("MISSING_") or code.startswith("REQ2_") and code.endswith("_MISSING")
               for code in row["quality_gate"]["reject_codes"])
    )
    duplicate_count = sum(
        1
        for row in gated_rows
        if "DUPLICATE_CROSS_TOOL" in row["quality_gate"]["reject_codes"]
    )

    accepted_rows = [
        row
        for row in gated_rows
        if row["quality_gate"]["status"] in {"PASS", "WARN"}
    ]
    accepted_split_counts = Counter(row["quality_gate"]["split"] for row in accepted_rows)
    all_split_counts = Counter(row["quality_gate"]["split"] for row in gated_rows)

    report = {
        "input": {
            "samples_path": str(samples_path),
            "total_samples": total,
        },
        "output": {
            "gated_samples_path": str(output_dir / "gated_samples.jsonl"),
            "failed_samples_path": str(output_dir / "failed_samples.jsonl"),
            "report_path": str(output_dir / "quality_gate_report.json"),
        },
        "rules": {
            "status_policy": {
                "PASS": "No warn/block issues",
                "WARN": "No block issues and at least one warn issue",
                "BLOCK": "Any block issue present",
            },
            "split_policy": {
                "train_ratio": train_ratio,
                "val_ratio": val_ratio,
                "test_ratio": round(1 - train_ratio - val_ratio, 6),
                "strategy": split_strategy,
            },
            "thresholds": {
                "plddt_min": plddt_min,
                "score_completeness_min": score_completeness_min,
            },
            "req2_capability_gate": {
                "sequence_generation": ["sequence_hash"],
                "sequence_design": ["sequence_hash"],
                "structure_prediction": ["structure_hash", "plddt_mean"],
                "quality_qc": ["qc_pass"],
                "objective_scoring": ["score_completeness_rate"],
            },
            "cross_tool_dedupe_key": [
                "sequence_hash",
                "structure_hash",
                "tool_lineage_hash",
            ],
        },
        "summary": {
            "overall_status": "BLOCK" if block_count > 0 else "WARN" if warn_count > 0 else "PASS",
            "counts": {
                "pass": pass_count,
                "warn": warn_count,
                "block": block_count,
                "accepted": len(accepted_rows),
            },
            "rates": {
                "pass_rate": round(pass_count / total, 6) if total else 0.0,
                "warn_rate": round(warn_count / total, 6) if total else 0.0,
                "block_rate": round(block_count / total, 6) if total else 0.0,
                "missing_rate": round(missing_count / total, 6) if total else 0.0,
                "duplicate_rate": round(duplicate_count / total, 6) if total else 0.0,
            },
            "split_counts": {
                "all": dict(sorted(all_split_counts.items())),
                "accepted": dict(sorted(accepted_split_counts.items())),
            },
            "potential_leakage_groups": cross_split_leakage_groups,
            "major_issue_distribution": dict(sorted(code_counter.items())),
        },
    }

    _write_jsonl(output_dir / "gated_samples.jsonl", gated_rows)
    _write_jsonl(output_dir / "failed_samples.jsonl", failed_rows)
    with (output_dir / "quality_gate_report.json").open("w", encoding="utf-8") as handle:
        handle.write(_json_dump(report) + "\n")

    return report


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run quality gate checks for extracted training samples.",
    )
    parser.add_argument("--samples-path", type=Path, default=DEFAULT_INPUT_SAMPLES)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--train-ratio", type=float, default=0.70)
    parser.add_argument("--val-ratio", type=float, default=0.15)
    parser.add_argument(
        "--split-strategy",
        choices=("time", "task_hash"),
        default="time",
        help="time: chronological task split; task_hash: stable hash split by task_id.",
    )
    parser.add_argument(
        "--plddt-min",
        type=float,
        default=0.70,
        help="Minimum pLDDT threshold for structure_prediction capability.",
    )
    parser.add_argument(
        "--score-completeness-min",
        type=float,
        default=0.80,
        help="Minimum complete score_breakdown ratio for objective_scoring capability.",
    )
    parser.add_argument(
        "--fail-on-block",
        action="store_true",
        help="Exit with code 2 when report summary contains blocked samples (CI gate).",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    report = quality_gate_training_samples(
        samples_path=args.samples_path,
        output_dir=args.output_dir,
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
        plddt_min=args.plddt_min,
        score_completeness_min=args.score_completeness_min,
        split_strategy=args.split_strategy,
    )
    print("Quality gate completed")
    print(_json_dump(report["summary"]))
    if args.fail_on_block and report["summary"]["counts"]["block"] > 0:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
