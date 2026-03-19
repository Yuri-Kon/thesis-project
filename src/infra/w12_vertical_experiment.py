from __future__ import annotations

import csv
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


DEFAULT_REQUIREMENT2_CAPABILITY_MAP: dict[str, list[str]] = {
    "sequence_core": ["sequence_generation", "sequence_design"],
    "quality_qc": ["quality_qc"],
    "objective_scoring": ["objective_scoring"],
    "structure_prediction": ["structure_prediction"],
    "similarity_search": ["sequence_similarity_search"],
    "secondary_structure": ["secondary_structure_annotation"],
}

DEFAULT_OFFLINE_THRESHOLDS: dict[str, float] = {
    "schema_valid_rate": 0.995,
    "executable_plan_rate": 0.95,
    "patch_minimality_hit_rate": 0.8,
    "suffix_replan_prefix_preservation_rate": 1.0,
}

_PATCH_EVENT_NAMES = {"PARAM_TWEAK", "REPLACE_TOOL", "STRUCTURE_PATCH"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False))
            f.write("\n")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in fieldnames})


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                rows.append(value)
    return rows


def parse_iso_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    normalized = value
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:12]


def deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in patch.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_tool_capability_map(kg_path: Path) -> dict[str, list[str]]:
    payload = load_json(kg_path)
    mapping: dict[str, list[str]] = {}
    for tool in payload.get("tools", []):
        if not isinstance(tool, dict):
            continue
        tool_id = tool.get("id")
        if not isinstance(tool_id, str) or not tool_id:
            continue
        caps = tool.get("capabilities")
        if isinstance(caps, list):
            mapping[tool_id] = [str(item) for item in caps if isinstance(item, str)]
        else:
            mapping[tool_id] = []
    return mapping


def validate_freeze_manifest(
    manifest: dict[str, Any],
    *,
    expected_freeze_id: str | None,
    require_downstream_ready: bool = True,
) -> dict[str, Any]:
    freeze_id = manifest.get("freeze_id")
    if not isinstance(freeze_id, str) or not freeze_id:
        raise ValueError("freeze manifest missing freeze_id")
    if expected_freeze_id and freeze_id != expected_freeze_id:
        raise ValueError(
            f"freeze_id mismatch: expected={expected_freeze_id}, actual={freeze_id}"
        )

    if require_downstream_ready:
        downstream_ready = manifest.get("downstream_ready")
        if isinstance(downstream_ready, dict):
            # Newer schema may carry booleans and details.
            ready_flag = downstream_ready.get("ready")
            if ready_flag is False:
                raise ValueError("freeze manifest downstream_ready.ready is false")
        elif downstream_ready is False:
            raise ValueError("freeze manifest downstream_ready is false")

    return {
        "freeze_id": freeze_id,
        "generated_at": manifest.get("generated_at"),
        "time_window": manifest.get("time_window"),
        "manifest_path": str(manifest.get("manifest_path") or ""),
    }


def wilson_interval(success: int, total: int, z: float = 1.96) -> tuple[float | None, float | None]:
    if total <= 0:
        return (None, None)
    phat = success / total
    denom = 1.0 + (z * z / total)
    center = (phat + (z * z) / (2.0 * total)) / denom
    margin = (
        z
        * math.sqrt((phat * (1.0 - phat) / total) + (z * z) / (4.0 * total * total))
        / denom
    )
    return (max(0.0, center - margin), min(1.0, center + margin))


def bootstrap_mean_ci(
    values: list[float],
    *,
    iterations: int,
    seed: int,
    ci: float = 0.95,
) -> tuple[float | None, float | None, float | None]:
    if not values:
        return (None, None, None)
    if len(values) == 1:
        value = float(values[0])
        return (value, value, value)

    rng = random.Random(seed)
    means: list[float] = []
    n = len(values)
    for _ in range(max(iterations, 100)):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)

    means.sort()
    alpha = (1.0 - ci) / 2.0
    low_idx = int(alpha * (len(means) - 1))
    high_idx = int((1.0 - alpha) * (len(means) - 1))
    observed = float(sum(values) / len(values))
    return (observed, means[low_idx], means[high_idx])


def _event_name(row: dict[str, Any]) -> str:
    name = row.get("event")
    if isinstance(name, str) and name:
        return name
    fallback = row.get("event_type")
    if isinstance(fallback, str):
        return fallback
    return ""


def _nested(row: dict[str, Any], *path: str) -> Any:
    current: Any = row
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def extract_run_metrics(
    run: dict[str, Any],
    *,
    tool_capability_map: dict[str, list[str]],
    requirement2_capability_map: dict[str, list[str]],
) -> dict[str, Any]:
    event_log_path = Path(str(run.get("event_log_path") or ""))
    rows = read_jsonl(event_log_path)

    timestamps: list[datetime] = []
    step_failed_details: list[dict[str, Any]] = []
    layer_counter: Counter[str] = Counter()
    tool_usage: Counter[str] = Counter()
    capability_usage: Counter[str] = Counter()

    waiting_enter_ids: set[str] = set()
    waiting_exit_ids: set[str] = set()
    decision_pending_ids: set[str] = set()

    candidate_validation_failed = 0
    patch_event_count = 0
    replan_event_count = 0
    suffix_replan_event_count = 0
    step_failed_count = 0
    step_finished_count = 0
    waiting_enter_count = 0

    suffix_prefix_samples: list[bool] = []
    final_status: str | None = None

    for row in rows:
        event_name = _event_name(row)

        ts = parse_iso_datetime(row.get("timestamp") or row.get("ts"))
        if ts is not None:
            timestamps.append(ts)

        if event_name == "TASK_STATUS_CHANGED":
            to_status = row.get("to_status")
            if isinstance(to_status, str) and to_status:
                final_status = to_status
            reason = row.get("reason")
            if isinstance(reason, str) and "suffix_replan" in reason:
                suffix_replan_event_count += 1
            if to_status == "REPLANNING":
                replan_event_count += 1

        if event_name in _PATCH_EVENT_NAMES:
            patch_event_count += 1
            layer = _nested(row, "data", "recovery", "recovery_layer")
            if isinstance(layer, str) and layer:
                layer_counter[layer] += 1

        if event_name in {"RECOVERY_ESCALATED", "DECISION_APPLIED", "STEP_FINISHED", "STEP_FAILED"}:
            encoded = json.dumps(row, ensure_ascii=False)
            if "suffix_replan" in encoded:
                suffix_replan_event_count += 1

        prefix_preserved = _nested(row, "data", "recovery", "prefix_preserved")
        if isinstance(prefix_preserved, bool):
            suffix_prefix_samples.append(prefix_preserved)

        if event_name == "CANDIDATE_VALIDATION_FAILED":
            candidate_validation_failed += 1

        if event_name in {"WAITING_ENTER"}:
            waiting_enter_count += 1
            pending_action_id = row.get("pending_action_id")
            key = str(pending_action_id) if pending_action_id else f"__missing__{waiting_enter_count}"
            waiting_enter_ids.add(key)

        if event_name in {"WAITING_EXIT"}:
            pending_action_id = row.get("pending_action_id")
            key = str(pending_action_id) if pending_action_id else "__missing__"
            waiting_exit_ids.add(key)

        if event_name in {"DECISION_APPLIED"}:
            pending_action_id = row.get("pending_action_id")
            if pending_action_id:
                decision_pending_ids.add(str(pending_action_id))

        if event_name in {"STEP_FINISHED", "STEP_FAILED"}:
            status = row.get("status")
            if status == "failed" or event_name == "STEP_FAILED":
                step_failed_count += 1
                failure_code = (
                    row.get("failure_type")
                    or _nested(row, "data", "failure_code")
                    or _nested(row, "error_details", "failure_code")
                )
                detail = {
                    "step_id": row.get("step_id"),
                    "tool": row.get("tool"),
                    "failure_code": failure_code,
                }
                step_failed_details.append(detail)
            elif status == "success":
                step_finished_count += 1

            tool = row.get("tool")
            if isinstance(tool, str) and tool:
                tool_usage[tool] += 1
                for capability in tool_capability_map.get(tool, []):
                    capability_usage[capability] += 1

    if final_status is None:
        explicit = run.get("status_external")
        if isinstance(explicit, str) and explicit:
            final_status = explicit
        else:
            final_status = "UNKNOWN"

    started_at = parse_iso_datetime(run.get("started_at"))
    finished_at = parse_iso_datetime(run.get("finished_at"))
    duration_ms = run.get("duration_ms")
    if isinstance(duration_ms, (int, float)):
        duration_ms_value = float(duration_ms)
    elif started_at and finished_at:
        duration_ms_value = (finished_at - started_at).total_seconds() * 1000.0
    elif timestamps:
        duration_ms_value = (max(timestamps) - min(timestamps)).total_seconds() * 1000.0
    else:
        duration_ms_value = 0.0

    success = final_status == "DONE"
    first_pass_success = (
        success
        and patch_event_count == 0
        and replan_event_count == 0
        and waiting_enter_count == 0
    )
    schema_valid = candidate_validation_failed == 0
    executable_plan = step_failed_count == 0

    waiting_chain_complete = True
    if waiting_enter_ids:
        waiting_chain_complete = waiting_enter_ids.issubset(waiting_exit_ids | decision_pending_ids)

    failure_traceable = True
    if step_failed_details:
        for detail in step_failed_details:
            if not (detail.get("step_id") and detail.get("tool") and detail.get("failure_code")):
                failure_traceable = False
                break

    abnormal_reasons: list[str] = []
    if final_status in {"FAILED", "CANCELLED", "WAITING_PLAN_CONFIRM", "WAITING_PATCH_CONFIRM", "WAITING_REPLAN_CONFIRM", "WAITING_PATCH", "WAITING_REPLAN"}:
        abnormal_reasons.append(f"terminal_or_waiting_status:{final_status}")
    if not waiting_chain_complete:
        abnormal_reasons.append("waiting_chain_incomplete")
    if not failure_traceable:
        abnormal_reasons.append("failure_not_traceable")
    if step_failed_count > 0:
        abnormal_reasons.append("step_failed")

    requirement2_coverage: dict[str, bool] = {}
    for bucket, capabilities in requirement2_capability_map.items():
        requirement2_coverage[bucket] = any(capability_usage.get(cap, 0) > 0 for cap in capabilities)

    return {
        "run_id": run.get("run_id"),
        "task_id": run.get("task_id"),
        "task_key": run.get("task_key"),
        "group_id": run.get("group_id"),
        "replicate": run.get("replicate"),
        "freeze_id": run.get("freeze_id"),
        "event_log_path": str(event_log_path),
        "snapshot_path": str(run.get("snapshot_path") or ""),
        "report_path": str(run.get("report_path") or ""),
        "started_at": run.get("started_at"),
        "finished_at": run.get("finished_at"),
        "duration_ms": round(duration_ms_value, 3),
        "final_status": final_status,
        "success": success,
        "first_pass_success": first_pass_success,
        "schema_valid": schema_valid,
        "executable_plan": executable_plan,
        "patch_event_count": patch_event_count,
        "replan_event_count": replan_event_count,
        "suffix_replan_event_count": suffix_replan_event_count,
        "waiting_enter_count": waiting_enter_count,
        "step_failed_count": step_failed_count,
        "step_finished_count": step_finished_count,
        "waiting_chain_complete": waiting_chain_complete,
        "failure_traceable": failure_traceable,
        "layer_counter": dict(layer_counter),
        "tool_usage": dict(tool_usage),
        "capability_usage": dict(capability_usage),
        "requirement2_coverage": requirement2_coverage,
        "suffix_prefix_samples": suffix_prefix_samples,
        "abnormal_reasons": abnormal_reasons,
        "step_failed_details": step_failed_details,
    }


def _proportion_summary(flags: list[bool]) -> dict[str, Any]:
    total = len(flags)
    success = sum(1 for item in flags if item)
    rate = (success / total) if total else None
    ci_low, ci_high = wilson_interval(success, total)
    return {
        "count": success,
        "total": total,
        "rate": rate,
        "ci_low": ci_low,
        "ci_high": ci_high,
    }


def _mean_summary(values: list[float], *, iterations: int, seed: int) -> dict[str, Any]:
    mean, ci_low, ci_high = bootstrap_mean_ci(
        values,
        iterations=iterations,
        seed=seed,
    )
    return {
        "mean": mean,
        "ci_low": ci_low,
        "ci_high": ci_high,
    }


def aggregate_group_metrics(
    runs: list[dict[str, Any]],
    *,
    group_order: list[str],
    iterations: int,
    seed: int,
    thresholds: dict[str, float],
    requirement2_capability_map: dict[str, list[str]],
) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in runs:
        group_id = row.get("group_id")
        if isinstance(group_id, str):
            grouped[group_id].append(row)

    summary_rows: list[dict[str, Any]] = []
    patch_rows: list[dict[str, Any]] = []
    requirement2_rows: list[dict[str, Any]] = []
    abnormal_rows: list[dict[str, Any]] = []
    gate_rows: list[dict[str, Any]] = []

    for idx, group_id in enumerate(group_order):
        rows = grouped.get(group_id, [])
        if not rows:
            continue

        success = _proportion_summary([bool(item.get("success")) for item in rows])
        first_pass = _proportion_summary([bool(item.get("first_pass_success")) for item in rows])
        schema = _proportion_summary([bool(item.get("schema_valid")) for item in rows])
        executable = _proportion_summary([bool(item.get("executable_plan")) for item in rows])
        waiting_chain = _proportion_summary([bool(item.get("waiting_chain_complete")) for item in rows])
        traceability = _proportion_summary([bool(item.get("failure_traceable")) for item in rows])

        patch_counts = [float(item.get("patch_event_count", 0) or 0) for item in rows]
        replan_counts = [float(item.get("replan_event_count", 0) or 0) for item in rows]
        suffix_counts = [float(item.get("suffix_replan_event_count", 0) or 0) for item in rows]
        duration_values = [float(item.get("duration_ms", 0.0) or 0.0) for item in rows]

        patch_summary = _mean_summary(patch_counts, iterations=iterations, seed=seed + idx * 11 + 1)
        replan_summary = _mean_summary(replan_counts, iterations=iterations, seed=seed + idx * 11 + 2)
        suffix_summary = _mean_summary(suffix_counts, iterations=iterations, seed=seed + idx * 11 + 3)
        duration_summary = _mean_summary(duration_values, iterations=iterations, seed=seed + idx * 11 + 4)

        patch_layer_counter: Counter[str] = Counter()
        suffix_prefix_samples: list[bool] = []
        capability_counter: Counter[str] = Counter()
        tool_counter: Counter[str] = Counter()
        total_patch_events_with_layer = 0

        for row in rows:
            for layer, count in (row.get("layer_counter") or {}).items():
                if isinstance(layer, str) and isinstance(count, (int, float)):
                    patch_layer_counter[layer] += int(count)
                    total_patch_events_with_layer += int(count)
            for key, value in (row.get("capability_usage") or {}).items():
                if isinstance(key, str) and isinstance(value, (int, float)):
                    capability_counter[key] += int(value)
            for key, value in (row.get("tool_usage") or {}).items():
                if isinstance(key, str) and isinstance(value, (int, float)):
                    tool_counter[key] += int(value)
            suffix_prefix_samples.extend([bool(v) for v in row.get("suffix_prefix_samples") or []])

        patch_minimality_hit_rate = None
        if total_patch_events_with_layer > 0:
            patch_minimality_hit_rate = patch_layer_counter.get("parameter_level", 0) / total_patch_events_with_layer

        suffix_prefix_preservation_rate = None
        if suffix_prefix_samples:
            suffix_prefix_preservation_rate = (
                sum(1 for flag in suffix_prefix_samples if flag) / len(suffix_prefix_samples)
            )

        requirement2_bucket_status: dict[str, bool] = {}
        for bucket, capabilities in requirement2_capability_map.items():
            requirement2_bucket_status[bucket] = any(
                capability_counter.get(cap, 0) > 0 for cap in capabilities
            )

        summary_row = {
            "group_id": group_id,
            "runs": len(rows),
            "success_rate": success["rate"],
            "success_ci_low": success["ci_low"],
            "success_ci_high": success["ci_high"],
            "first_pass_success_rate": first_pass["rate"],
            "first_pass_ci_low": first_pass["ci_low"],
            "first_pass_ci_high": first_pass["ci_high"],
            "schema_valid_rate": schema["rate"],
            "schema_ci_low": schema["ci_low"],
            "schema_ci_high": schema["ci_high"],
            "executable_plan_rate": executable["rate"],
            "executable_ci_low": executable["ci_low"],
            "executable_ci_high": executable["ci_high"],
            "waiting_chain_complete_rate": waiting_chain["rate"],
            "failure_traceable_rate": traceability["rate"],
            "patch_events_mean": patch_summary["mean"],
            "patch_events_ci_low": patch_summary["ci_low"],
            "patch_events_ci_high": patch_summary["ci_high"],
            "replan_events_mean": replan_summary["mean"],
            "replan_events_ci_low": replan_summary["ci_low"],
            "replan_events_ci_high": replan_summary["ci_high"],
            "suffix_replan_events_mean": suffix_summary["mean"],
            "suffix_replan_events_ci_low": suffix_summary["ci_low"],
            "suffix_replan_events_ci_high": suffix_summary["ci_high"],
            "duration_ms_mean": duration_summary["mean"],
            "duration_ms_ci_low": duration_summary["ci_low"],
            "duration_ms_ci_high": duration_summary["ci_high"],
            "patch_minimality_hit_rate": patch_minimality_hit_rate,
            "suffix_replan_prefix_preservation_rate": suffix_prefix_preservation_rate,
            "requirement2_sequence_core": requirement2_bucket_status.get("sequence_core", False),
            "requirement2_quality_qc": requirement2_bucket_status.get("quality_qc", False),
            "requirement2_objective_scoring": requirement2_bucket_status.get("objective_scoring", False),
            "requirement2_structure_prediction": requirement2_bucket_status.get("structure_prediction", False),
        }
        for bucket, covered in requirement2_bucket_status.items():
            summary_row[f"requirement2_{bucket}"] = covered
        summary_rows.append(summary_row)

        patch_rows.append(
            {
                "group_id": group_id,
                "patch_events_total": sum(patch_counts),
                "replan_events_total": sum(replan_counts),
                "suffix_replan_events_total": sum(suffix_counts),
                "patch_parameter_level": patch_layer_counter.get("parameter_level", 0),
                "patch_tool_level": patch_layer_counter.get("tool_level", 0),
                "patch_structure_level": patch_layer_counter.get("structure_level", 0),
                "patch_minimality_hit_rate": patch_minimality_hit_rate,
                "suffix_prefix_sample_size": len(suffix_prefix_samples),
                "suffix_prefix_preservation_rate": suffix_prefix_preservation_rate,
            }
        )

        for bucket, capabilities in requirement2_capability_map.items():
            requirement2_rows.append(
                {
                    "group_id": group_id,
                    "slice_type": "capability_bucket",
                    "name": bucket,
                    "covered": requirement2_bucket_status.get(bucket, False),
                    "usage_count": sum(capability_counter.get(cap, 0) for cap in capabilities),
                }
            )
        for capability, usage in sorted(capability_counter.items()):
            requirement2_rows.append(
                {
                    "group_id": group_id,
                    "slice_type": "capability",
                    "name": capability,
                    "covered": usage > 0,
                    "usage_count": usage,
                }
            )
        for tool, usage in sorted(tool_counter.items()):
            requirement2_rows.append(
                {
                    "group_id": group_id,
                    "slice_type": "tool",
                    "name": tool,
                    "covered": usage > 0,
                    "usage_count": usage,
                }
            )

        for row in rows:
            for reason in row.get("abnormal_reasons") or []:
                abnormal_rows.append(
                    {
                        "run_id": row.get("run_id"),
                        "task_id": row.get("task_id"),
                        "group_id": group_id,
                        "replicate": row.get("replicate"),
                        "reason": reason,
                        "final_status": row.get("final_status"),
                        "event_log_path": row.get("event_log_path"),
                    }
                )

        gate_checks: list[dict[str, Any]] = []
        for metric_name, threshold in thresholds.items():
            value = summary_row.get(metric_name)
            passed = isinstance(value, (int, float)) and value >= threshold
            if metric_name == "suffix_replan_prefix_preservation_rate":
                passed = isinstance(value, (int, float)) and abs(float(value) - threshold) < 1e-9
            if value is None:
                passed = False
            gate_checks.append(
                {
                    "metric": metric_name,
                    "threshold": threshold,
                    "value": value,
                    "passed": passed,
                    "reason": None if passed else ("missing_value" if value is None else "below_threshold"),
                }
            )

        gate_rows.append(
            {
                "group_id": group_id,
                "all_passed": all(item["passed"] for item in gate_checks),
                "checks": gate_checks,
            }
        )

    return {
        "summary_rows": summary_rows,
        "patch_rows": patch_rows,
        "requirement2_rows": requirement2_rows,
        "abnormal_rows": abnormal_rows,
        "gate_rows": gate_rows,
    }


def compute_increment_deltas(
    runs: list[dict[str, Any]],
    *,
    group_order: list[str],
    metric_key: str,
    iterations: int,
    seed: int,
) -> list[dict[str, Any]]:
    by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in runs:
        group_id = row.get("group_id")
        if isinstance(group_id, str):
            by_group[group_id].append(row)

    rows: list[dict[str, Any]] = []
    for index in range(len(group_order) - 1):
        left = group_order[index]
        right = group_order[index + 1]
        left_rows = by_group.get(left, [])
        right_rows = by_group.get(right, [])
        if not left_rows or not right_rows:
            continue

        left_map: dict[tuple[str, int], float] = {}
        right_map: dict[tuple[str, int], float] = {}
        for row in left_rows:
            key = (str(row.get("task_key")), int(row.get("replicate") or 0))
            value = row.get(metric_key)
            if isinstance(value, bool):
                left_map[key] = 1.0 if value else 0.0
            elif isinstance(value, (int, float)):
                left_map[key] = float(value)
        for row in right_rows:
            key = (str(row.get("task_key")), int(row.get("replicate") or 0))
            value = row.get(metric_key)
            if isinstance(value, bool):
                right_map[key] = 1.0 if value else 0.0
            elif isinstance(value, (int, float)):
                right_map[key] = float(value)

        paired_keys = sorted(set(left_map.keys()) & set(right_map.keys()))
        paired_diffs = [right_map[key] - left_map[key] for key in paired_keys]

        if paired_diffs:
            mean, ci_low, ci_high = bootstrap_mean_ci(
                paired_diffs,
                iterations=iterations,
                seed=seed + index,
            )
            rows.append(
                {
                    "from_group": left,
                    "to_group": right,
                    "metric": metric_key,
                    "delta": mean,
                    "ci_low": ci_low,
                    "ci_high": ci_high,
                    "sample_size": len(paired_diffs),
                    "pairing": "paired",
                }
            )
            continue

        left_values = list(left_map.values())
        right_values = list(right_map.values())
        if not left_values or not right_values:
            continue

        delta = (sum(right_values) / len(right_values)) - (sum(left_values) / len(left_values))

        rng = random.Random(seed + index)
        samples: list[float] = []
        for _ in range(max(iterations, 100)):
            left_sample = [left_values[rng.randrange(len(left_values))] for _ in range(len(left_values))]
            right_sample = [right_values[rng.randrange(len(right_values))] for _ in range(len(right_values))]
            sample_delta = (sum(right_sample) / len(right_sample)) - (sum(left_sample) / len(left_sample))
            samples.append(sample_delta)
        samples.sort()
        low_idx = int(0.025 * (len(samples) - 1))
        high_idx = int(0.975 * (len(samples) - 1))

        rows.append(
            {
                "from_group": left,
                "to_group": right,
                "metric": metric_key,
                "delta": delta,
                "ci_low": samples[low_idx],
                "ci_high": samples[high_idx],
                "sample_size": min(len(left_values), len(right_values)),
                "pairing": "unpaired",
            }
        )

    return rows


def build_markdown_report(
    *,
    issue_id: int,
    run_manifest_path: Path,
    freeze_id: str,
    summary_rows: list[dict[str, Any]],
    delta_rows: list[dict[str, Any]],
    gate_rows: list[dict[str, Any]],
    generated_at: str,
) -> str:
    lines: list[str] = []
    lines.append(f"# Issue #{issue_id} Vertical Experiment Report (A0-A6)")
    lines.append("")
    lines.append(f"- generated_at: `{generated_at}`")
    lines.append(f"- freeze_id: `{freeze_id}`")
    lines.append(f"- run_manifest: `{run_manifest_path}`")
    lines.append("")

    lines.append("## Unified Metrics (effect / mechanism / cost / governance)")
    lines.append("")
    lines.append(
        "| group | runs | success_rate | first_pass | schema_valid | executable | patch_mean | replan_mean | duration_ms_mean |"
    )
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for row in summary_rows:
        lines.append(
            "| {group_id} | {runs} | {success_rate:.4f} | {first_pass_success_rate:.4f} | {schema_valid_rate:.4f} | {executable_plan_rate:.4f} | {patch_events_mean:.4f} | {replan_events_mean:.4f} | {duration_ms_mean:.2f} |".format(
                group_id=row.get("group_id"),
                runs=row.get("runs", 0),
                success_rate=float(row.get("success_rate") or 0.0),
                first_pass_success_rate=float(row.get("first_pass_success_rate") or 0.0),
                schema_valid_rate=float(row.get("schema_valid_rate") or 0.0),
                executable_plan_rate=float(row.get("executable_plan_rate") or 0.0),
                patch_events_mean=float(row.get("patch_events_mean") or 0.0),
                replan_events_mean=float(row.get("replan_events_mean") or 0.0),
                duration_ms_mean=float(row.get("duration_ms_mean") or 0.0),
            )
        )

    lines.append("")
    lines.append("## Mechanism Increment Deltas")
    lines.append("")
    lines.append("| from | to | metric | delta | ci_low | ci_high | pairing |")
    lines.append("| --- | --- | --- | ---: | ---: | ---: | --- |")
    for row in delta_rows:
        lines.append(
            "| {from_group} | {to_group} | {metric} | {delta:.4f} | {ci_low:.4f} | {ci_high:.4f} | {pairing} |".format(
                from_group=row.get("from_group"),
                to_group=row.get("to_group"),
                metric=row.get("metric"),
                delta=float(row.get("delta") or 0.0),
                ci_low=float(row.get("ci_low") or 0.0),
                ci_high=float(row.get("ci_high") or 0.0),
                pairing=row.get("pairing"),
            )
        )

    lines.append("")
    lines.append("## Offline Gate Check")
    lines.append("")
    lines.append("| group | all_passed | failed_metrics |")
    lines.append("| --- | --- | --- |")
    for row in gate_rows:
        failed_metrics = [item["metric"] for item in row.get("checks", []) if not item.get("passed")]
        lines.append(
            f"| {row.get('group_id')} | {row.get('all_passed')} | {', '.join(failed_metrics) if failed_metrics else '-'} |"
        )

    lines.append("")
    lines.append("## Acceptance Mapping")
    lines.append("")
    lines.append("- A0->A6 chain reproducibility: covered via run manifest + run_log_index + deterministic config snapshot.")
    lines.append("- Mechanism increment evidence: provided in `mechanism_increment_deltas.csv` with CI.")
    lines.append("- Offline thresholds: checked in `offline_gate_assessment.json`; unmet items include reasons.")
    lines.append("- Requirement2: tool/capability slices exported in `requirement2_tool_capability_slices.csv`.")

    return "\n".join(lines) + "\n"
