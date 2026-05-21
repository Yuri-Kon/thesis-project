from __future__ import annotations

import csv
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from src.infra.active_tool_metadata import build_high_cost_rules_from_metadata
from src.infra.experiments._metric_aggregators import (
    build_threshold_gate_checks,
    group_runs_by_order,
)
from src.infra.experiments._metric_extractors import (
    build_requirement2_coverage,
    compute_duration_ms,
    resolve_final_status,
    resolve_run_artifact_paths,
)


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

DEFAULT_HIGH_COST_RULES: list[dict[str, Any]] = build_high_cost_rules_from_metadata()

_PATCH_EVENT_NAMES = {"PARAM_TWEAK", "REPLACE_TOOL", "STRUCTURE_PATCH"}
DEFAULT_REPLAY_SAMPLE_DIR = (
    Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "runtime_shadow_samples"
)
ACTION_SPACE = ("continue", "patch_local", "suffix_replan", "stop")
BELIEF_STATE_CORE_FIELDS = (
    "p_success",
    "p_structural_failure",
    "recovery_margin",
    "expected_remaining_cost",
    "evidence_sufficiency",
)
BELIEF_STATE_DERIVED_FIELDS = (
    "budget_pressure",
    "intervention_value",
    "goal_misalignment",
    "local_patchability",
    "prefix_preservability",
)
CANONICAL_GROUP_ALIASES: dict[str, str] = {
    "A0": "static_top1",
    "A3": "fixed_threshold_gate",
    "A4": "dynamic_no_belief_state",
    "A5": "dynamic_no_belief_state",
    "A6": "lite_belief_state",
    "static_top1": "static_top1",
    "fixed_threshold_gate": "fixed_threshold_gate",
    "dynamic_no_belief_state": "dynamic_no_belief_state",
    "lite_belief_state": "lite_belief_state",
    "E0": "E0",
    "E1": "E1",
    "E2": "E2",
    "react_single_trajectory": "E0",
    "tot_multi_branch": "E1",
    "reflexion_recovery": "E2",
}


@dataclass
class _RunEventMetrics:
    """单次 run 的事件扫描暂存区，避免 extract_run_metrics 直接维护所有细节。"""

    timestamps: list[datetime] = field(default_factory=list)
    step_failed_details: list[dict[str, Any]] = field(default_factory=list)
    layer_counter: Counter[str] = field(default_factory=Counter)
    tool_usage: Counter[str] = field(default_factory=Counter)
    capability_usage: Counter[str] = field(default_factory=Counter)
    high_cost_rule_hits: Counter[str] = field(default_factory=Counter)
    waiting_enter_ids: set[str] = field(default_factory=set)
    waiting_exit_ids: set[str] = field(default_factory=set)
    decision_pending_ids: set[str] = field(default_factory=set)
    action_counter: Counter[str] = field(default_factory=Counter)
    suffix_prefix_samples: list[bool] = field(default_factory=list)
    candidate_validation_failed: int = 0
    patch_event_count: int = 0
    replan_event_count: int = 0
    suffix_replan_event_count: int = 0
    step_failed_count: int = 0
    step_finished_count: int = 0
    waiting_enter_count: int = 0
    high_cost_call_count: int = 0
    high_cost_failure_count: int = 0
    runtime_state_observable: bool = False
    shadow_output_observable: bool = False
    shadow_action_agreement_count: int = 0
    shadow_action_observation_count: int = 0
    final_status: str | None = None


@dataclass
class _GroupAggregateCounters:
    """组级聚合暂存区，只负责跨 run 的计数合并。"""

    patch_layer_counter: Counter[str] = field(default_factory=Counter)
    suffix_prefix_samples: list[bool] = field(default_factory=list)
    capability_counter: Counter[str] = field(default_factory=Counter)
    tool_counter: Counter[str] = field(default_factory=Counter)
    high_cost_rule_counter: Counter[str] = field(default_factory=Counter)
    total_patch_events_with_layer: int = 0
    shadow_action_agreement_total: int = 0
    shadow_action_observation_total: int = 0
    aliases: list[str] = field(default_factory=list)


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
    if not path.exists() or not path.is_file():
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


def load_replay_sample(path: Path) -> dict[str, Any]:
    payload = load_json(path)
    sample_id = payload.get("sample_id")
    if not isinstance(sample_id, str) or not sample_id.strip():
        raise ValueError("replay sample missing sample_id")

    source = payload.get("source")
    if not isinstance(source, dict):
        raise ValueError("replay sample missing source")
    freeze_id = source.get("freeze_id")
    if not isinstance(freeze_id, str) or not freeze_id.strip():
        raise ValueError("replay sample source.freeze_id is required")
    task_key = source.get("task_key")
    if not isinstance(task_key, str) or not task_key.strip():
        raise ValueError("replay sample source.task_key is required")

    purpose = payload.get("purpose")
    if not isinstance(purpose, str) or not purpose.strip():
        raise ValueError("replay sample purpose is required")

    run = payload.get("run")
    if not isinstance(run, dict):
        raise ValueError("replay sample missing run")
    event_log = payload.get("event_log")
    if not isinstance(event_log, list) or not event_log:
        raise ValueError("replay sample event_log must be a non-empty list")

    snapshot = payload.get("snapshot")
    if snapshot is not None and not isinstance(snapshot, dict):
        raise ValueError("replay sample snapshot must be a mapping")

    report = payload.get("report")
    if report is not None and not isinstance(report, dict):
        raise ValueError("replay sample report must be a mapping")

    return payload


def materialize_replay_sample(
    sample: dict[str, Any],
    *,
    output_dir: Path,
) -> dict[str, Any]:
    sample_id = str(sample["sample_id"])
    sample_dir = output_dir / sample_id
    sample_dir.mkdir(parents=True, exist_ok=True)

    event_log_path = sample_dir / "event_log.jsonl"
    write_jsonl(event_log_path, sample["event_log"])

    snapshot_path = sample_dir / "snapshot.json"
    snapshot_payload = sample.get("snapshot")
    if isinstance(snapshot_payload, dict):
        write_json(snapshot_path, snapshot_payload)
        resolved_snapshot_path: Path | None = snapshot_path
    else:
        resolved_snapshot_path = None

    report_path = sample_dir / "report.json"
    report_payload = sample.get("report")
    if isinstance(report_payload, dict):
        write_json(report_path, report_payload)
        resolved_report_path: Path | None = report_path
    else:
        resolved_report_path = None

    run = dict(sample["run"])
    source = dict(sample["source"])
    run.setdefault("freeze_id", source.get("freeze_id"))
    run.setdefault("task_key", source.get("task_key"))
    run["event_log_path"] = str(event_log_path)
    run["snapshot_path"] = str(resolved_snapshot_path) if resolved_snapshot_path else ""
    run["report_path"] = str(resolved_report_path) if resolved_report_path else ""
    run["replay_sample_id"] = sample_id
    run["replay_source_freeze_id"] = str(source.get("freeze_id") or "")
    return run


def replay_sample(
    sample_path: Path,
    *,
    output_dir: Path,
    tool_capability_map: dict[str, list[str]],
    requirement2_capability_map: dict[str, list[str]],
    high_cost_rules: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    sample = load_replay_sample(sample_path)
    run = materialize_replay_sample(sample, output_dir=output_dir)
    metrics = extract_run_metrics(
        run,
        tool_capability_map=tool_capability_map,
        requirement2_capability_map=requirement2_capability_map,
        high_cost_rules=high_cost_rules,
    )
    metrics["replay_sample_id"] = run.get("replay_sample_id")
    metrics["replay_source_freeze_id"] = run.get("replay_source_freeze_id")
    metrics["replay_sample_purpose"] = sample.get("purpose")
    return metrics


def replay_samples(
    sample_paths: Iterable[Path],
    *,
    output_dir: Path,
    tool_capability_map: dict[str, list[str]],
    requirement2_capability_map: dict[str, list[str]],
    high_cost_rules: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for sample_path in sample_paths:
        results.append(
            replay_sample(
                sample_path,
                output_dir=output_dir,
                tool_capability_map=tool_capability_map,
                requirement2_capability_map=requirement2_capability_map,
                high_cost_rules=high_cost_rules,
            )
        )
    return results


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


def normalize_high_cost_rules(raw_rules: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_rules, list):
        raw_rules = DEFAULT_HIGH_COST_RULES

    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_rules):
        if not isinstance(raw, dict):
            continue
        rule_id = raw.get("rule_id")
        if not isinstance(rule_id, str) or not rule_id.strip():
            rule_id = f"high_cost_rule_{index + 1}"

        def _normalize_str_list(value: Any) -> list[str]:
            if not isinstance(value, list):
                return []
            return [str(item) for item in value if isinstance(item, str) and item]

        normalized.append(
            {
                "rule_id": rule_id.strip(),
                "label": str(raw.get("label") or rule_id).strip(),
                "stage_ids": _normalize_str_list(raw.get("stage_ids")),
                "tool_ids": _normalize_str_list(raw.get("tool_ids")),
                "capability_ids": _normalize_str_list(raw.get("capability_ids")),
                "cost_tier": str(raw.get("cost_tier") or "unknown"),
                "rationale": str(raw.get("rationale") or ""),
            }
        )

    return normalized or list(DEFAULT_HIGH_COST_RULES)


def _match_high_cost_rule(
    *,
    row: dict[str, Any],
    tool: str,
    capabilities: list[str],
    rule: dict[str, Any],
) -> bool:
    stage_ids = set(rule.get("stage_ids") or [])
    tool_ids = set(rule.get("tool_ids") or [])
    capability_ids = set(rule.get("capability_ids") or [])

    step_id = row.get("step_id")
    stage_id = _nested(row, "data", "stage_id")
    observed_stage_ids = {
        value
        for value in (step_id, stage_id)
        if isinstance(value, str) and value
    }
    if stage_ids and not stage_ids.intersection(observed_stage_ids):
        return False
    if tool_ids and tool not in tool_ids:
        return False
    if capability_ids and not capability_ids.intersection(capabilities):
        return False
    return bool(stage_ids or tool_ids or capability_ids)


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


def canonicalize_group_id(group_id: Any) -> str:
    """把历史实现组和外部别名映射为论文主结果组。"""
    if not isinstance(group_id, str) or not group_id.strip():
        return ""
    text = group_id.strip()
    return CANONICAL_GROUP_ALIASES.get(text, text)


def _numeric(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _runtime_state_candidates(row: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    data = row.get("data")
    if not isinstance(data, dict):
        data = {}

    candidates: list[tuple[str, dict[str, Any]]] = []
    direct = data.get("runtime_state_summary")
    if isinstance(direct, dict):
        candidates.append(("event_log:data.runtime_state_summary", direct))

    waiting_summary = data.get("waiting_runtime_summary")
    if isinstance(waiting_summary, dict):
        waiting_state = waiting_summary.get("runtime_state_summary")
        if isinstance(waiting_state, dict):
            candidates.append(
                ("event_log:data.waiting_runtime_summary.runtime_state_summary", waiting_state)
            )

    recovery = data.get("recovery")
    if isinstance(recovery, dict):
        recovery_state = recovery.get("runtime_state_summary")
        if isinstance(recovery_state, dict):
            candidates.append(("event_log:data.recovery.runtime_state_summary", recovery_state))

    return candidates


def _has_runtime_state_observation(row: dict[str, Any]) -> bool:
    return bool(_runtime_state_candidates(row))


def _has_shadow_output(row: dict[str, Any]) -> bool:
    data = row.get("data")
    if not isinstance(data, dict):
        data = {}
    if isinstance(data.get("shadow_score"), dict):
        return True
    if isinstance(data.get("shadow_action"), str) and data.get("shadow_action"):
        return True
    waiting_summary = data.get("waiting_runtime_summary")
    if isinstance(waiting_summary, dict):
        if isinstance(waiting_summary.get("shadow_score"), dict):
            return True
        if isinstance(waiting_summary.get("shadow_action"), str) and waiting_summary.get("shadow_action"):
            return True
    recovery = data.get("recovery")
    if isinstance(recovery, dict):
        if isinstance(recovery.get("shadow_score"), dict):
            return True
        if isinstance(recovery.get("shadow_action"), str) and recovery.get("shadow_action"):
            return True
    return False


def _extract_shadow_action(row: dict[str, Any]) -> str | None:
    data = row.get("data")
    if not isinstance(data, dict):
        data = {}

    direct = data.get("shadow_action")
    if isinstance(direct, str) and direct:
        return direct

    waiting_summary = data.get("waiting_runtime_summary")
    if isinstance(waiting_summary, dict):
        candidate = waiting_summary.get("shadow_action")
        if isinstance(candidate, str) and candidate:
            return candidate

    recovery = data.get("recovery")
    if isinstance(recovery, dict):
        candidate = recovery.get("shadow_action")
        if isinstance(candidate, str) and candidate:
            return candidate

    return None


def _extract_logged_action_name(row: dict[str, Any]) -> str | None:
    direct = row.get("action_name")
    if isinstance(direct, str) and direct:
        return direct

    data = row.get("data")
    if isinstance(data, dict):
        candidate = data.get("action_name")
        if isinstance(candidate, str) and candidate:
            return candidate
    return None


def _normalize_action_name(
    action_name: str | None,
    *,
    row: dict[str, Any],
    shadow_action: str | None = None,
) -> str | None:
    if not isinstance(action_name, str) or not action_name.strip():
        return None

    normalized = action_name.strip().lower()
    if normalized == "patch":
        return "patch_local"
    if normalized == "replan":
        reason = str(row.get("reason") or _nested(row, "data", "reason") or "").lower()
        replan_mode = _nested(row, "data", "replan_mode") or _nested(
            row,
            "data",
            "recovery",
            "replan_mode",
        )
        if isinstance(replan_mode, str) and replan_mode.strip():
            normalized = replan_mode.strip().lower()
        elif isinstance(shadow_action, str) and shadow_action.strip():
            normalized = shadow_action.strip().lower()
        elif "suffix_replan" in reason:
            normalized = "suffix_replan"
        else:
            normalized = "suffix_replan"

    if normalized in {"continue", "patch_local", "suffix_replan", "stop"}:
        return normalized
    return None


def _load_snapshot_payload(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = load_json(path)
    except Exception:
        payload = None
    if isinstance(payload, dict):
        return payload

    try:
        with path.open("r", encoding="utf-8") as handle:
            last_mapping: dict[str, Any] | None = None
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(value, dict):
                    last_mapping = value
            return last_mapping
    except Exception:
        return None
    return None


def _collect_belief_state_metrics(
    *,
    rows: list[dict[str, Any]],
    snapshot_artifacts: dict[str, Any],
    run: dict[str, Any],
) -> dict[str, Any]:
    latest_values: dict[str, float | None] = {
        field: None for field in (*BELIEF_STATE_CORE_FIELDS, *BELIEF_STATE_DERIVED_FIELDS)
    }
    core_observation_counts: Counter[str] = Counter()
    derived_observation_counts: Counter[str] = Counter()
    source_hits: set[str] = set()
    observation_count = 0

    def consume(source: str, payload: dict[str, Any]) -> None:
        nonlocal observation_count
        observed_any = False
        for field in BELIEF_STATE_CORE_FIELDS:
            value = _numeric(payload.get(field))
            if value is not None:
                latest_values[field] = value
                core_observation_counts[field] += 1
                observed_any = True
        for field in BELIEF_STATE_DERIVED_FIELDS:
            value = _numeric(payload.get(field))
            if value is not None:
                latest_values[field] = value
                derived_observation_counts[field] += 1
                observed_any = True
        if observed_any:
            observation_count += 1
            source_hits.add(source)

    for row in rows:
        for source, payload in _runtime_state_candidates(row):
            consume(source, payload)

    snapshot_state = snapshot_artifacts.get("runtime_state")
    if isinstance(snapshot_state, dict):
        consume("snapshot:artifacts.runtime_state", snapshot_state)

    run_runtime_state = run.get("runtime_state")
    if isinstance(run_runtime_state, dict):
        consume("summary_row:runtime_state", run_runtime_state)
    run_runtime_summary = run.get("runtime_state_summary")
    if isinstance(run_runtime_summary, dict):
        consume("summary_row:runtime_state_summary", run_runtime_summary)

    core_observed = {
        field: core_observation_counts.get(field, 0) > 0 for field in BELIEF_STATE_CORE_FIELDS
    }
    derived_observed = {
        field: derived_observation_counts.get(field, 0) > 0
        for field in BELIEF_STATE_DERIVED_FIELDS
    }
    core_observed_count = sum(1 for observed in core_observed.values() if observed)
    derived_observed_count = sum(1 for observed in derived_observed.values() if observed)

    return {
        "belief_state_observation_count": observation_count,
        "belief_state_core_observed_count": core_observed_count,
        "belief_state_core_completeness": core_observed_count / len(BELIEF_STATE_CORE_FIELDS),
        "belief_state_core_complete": core_observed_count == len(BELIEF_STATE_CORE_FIELDS),
        "belief_state_derived_observed_count": derived_observed_count,
        "belief_state_derived_completeness": (
            derived_observed_count / len(BELIEF_STATE_DERIVED_FIELDS)
        ),
        "belief_state_sources": sorted(source_hits),
        "belief_state_core_observed": core_observed,
        "belief_state_derived_observed": derived_observed,
        "belief_state_latest": latest_values,
    }


def _optional_path(value: Any) -> Path | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    return Path(text)


def _collect_run_event_metrics(
    *,
    rows: list[dict[str, Any]],
    tool_capability_map: dict[str, list[str]],
    high_cost_rules: list[dict[str, Any]],
) -> _RunEventMetrics:
    metrics = _RunEventMetrics()
    for row in rows:
        event_name = _event_name(row)
        shadow_action = _observe_runtime_and_shadow(metrics, row)
        actual_action = _resolve_actual_action(
            row=row,
            event_name=event_name,
            shadow_action=shadow_action,
        )
        _update_action_observation(
            metrics,
            actual_action=actual_action,
            shadow_action=shadow_action,
        )
        _update_status_and_recovery_metrics(
            metrics,
            row=row,
            event_name=event_name,
            actual_action=actual_action,
        )
        _update_waiting_metrics(metrics, row=row, event_name=event_name)
        _update_step_and_tool_metrics(
            metrics,
            row=row,
            event_name=event_name,
            tool_capability_map=tool_capability_map,
            high_cost_rules=high_cost_rules,
        )
    return metrics


def _observe_runtime_and_shadow(
    metrics: _RunEventMetrics,
    row: dict[str, Any],
) -> str | None:
    metrics.runtime_state_observable = (
        metrics.runtime_state_observable or _has_runtime_state_observation(row)
    )
    metrics.shadow_output_observable = (
        metrics.shadow_output_observable or _has_shadow_output(row)
    )
    timestamp = parse_iso_datetime(row.get("timestamp") or row.get("ts"))
    if timestamp is not None:
        metrics.timestamps.append(timestamp)
    return _normalize_action_name(_extract_shadow_action(row), row=row)


def _resolve_actual_action(
    *,
    row: dict[str, Any],
    event_name: str,
    shadow_action: str | None,
) -> str | None:
    if event_name in _PATCH_EVENT_NAMES:
        return "patch_local"
    if event_name == "RECOVERY_ESCALATED":
        return _normalize_action_name(
            _extract_logged_action_name(row) or "replan",
            row=row,
            shadow_action=shadow_action,
        )
    if event_name in {"STEP_FINISHED", "STEP_FAILED"}:
        return _normalize_action_name(
            _extract_logged_action_name(row),
            row=row,
            shadow_action=shadow_action,
        )
    return None


def _update_action_observation(
    metrics: _RunEventMetrics,
    *,
    actual_action: str | None,
    shadow_action: str | None,
) -> None:
    if actual_action is None:
        return
    metrics.action_counter[actual_action] += 1
    if shadow_action is None:
        return
    metrics.shadow_action_observation_count += 1
    if shadow_action == actual_action:
        metrics.shadow_action_agreement_count += 1


def _update_status_and_recovery_metrics(
    metrics: _RunEventMetrics,
    *,
    row: dict[str, Any],
    event_name: str,
    actual_action: str | None,
) -> None:
    if event_name == "TASK_STATUS_CHANGED":
        to_status = row.get("to_status")
        if isinstance(to_status, str) and to_status:
            metrics.final_status = to_status
        reason = row.get("reason")
        if isinstance(reason, str) and "suffix_replan" in reason:
            metrics.suffix_replan_event_count += 1
        if to_status == "REPLANNING":
            metrics.replan_event_count += 1

    if event_name in _PATCH_EVENT_NAMES:
        metrics.patch_event_count += 1
        layer = _nested(row, "data", "recovery", "recovery_layer")
        if isinstance(layer, str) and layer:
            metrics.layer_counter[layer] += 1

    if event_name == "RECOVERY_ESCALATED" and actual_action == "suffix_replan":
        metrics.suffix_replan_event_count += 1

    prefix_preserved = _nested(row, "data", "recovery", "prefix_preserved")
    if isinstance(prefix_preserved, bool):
        metrics.suffix_prefix_samples.append(prefix_preserved)

    if event_name == "CANDIDATE_VALIDATION_FAILED":
        metrics.candidate_validation_failed += 1


def _update_waiting_metrics(
    metrics: _RunEventMetrics,
    *,
    row: dict[str, Any],
    event_name: str,
) -> None:
    if event_name == "WAITING_ENTER":
        metrics.waiting_enter_count += 1
        pending_action_id = row.get("pending_action_id")
        key = (
            str(pending_action_id)
            if pending_action_id
            else f"__missing__{metrics.waiting_enter_count}"
        )
        metrics.waiting_enter_ids.add(key)
    if event_name == "WAITING_EXIT":
        pending_action_id = row.get("pending_action_id")
        key = str(pending_action_id) if pending_action_id else "__missing__"
        metrics.waiting_exit_ids.add(key)
    if event_name == "DECISION_APPLIED":
        pending_action_id = row.get("pending_action_id")
        if pending_action_id:
            metrics.decision_pending_ids.add(str(pending_action_id))


def _update_step_and_tool_metrics(
    metrics: _RunEventMetrics,
    *,
    row: dict[str, Any],
    event_name: str,
    tool_capability_map: dict[str, list[str]],
    high_cost_rules: list[dict[str, Any]],
) -> None:
    if event_name not in {"STEP_FINISHED", "STEP_FAILED"}:
        return
    status = row.get("status")
    if status == "failed" or event_name == "STEP_FAILED":
        metrics.step_failed_count += 1
        metrics.step_failed_details.append(_step_failure_detail(row))
    elif status == "success":
        metrics.step_finished_count += 1

    tool = row.get("tool")
    if not isinstance(tool, str) or not tool:
        return
    capabilities = tool_capability_map.get(tool, [])
    metrics.tool_usage[tool] += 1
    for capability in capabilities:
        metrics.capability_usage[capability] += 1
    _update_high_cost_metrics(
        metrics,
        row=row,
        status=status,
        event_name=event_name,
        tool=tool,
        capabilities=capabilities,
        high_cost_rules=high_cost_rules,
    )


def _step_failure_detail(row: dict[str, Any]) -> dict[str, Any]:
    failure_code = (
        row.get("failure_type")
        or _nested(row, "data", "failure_code")
        or _nested(row, "error_details", "failure_code")
    )
    return {
        "step_id": row.get("step_id"),
        "tool": row.get("tool"),
        "failure_code": failure_code,
    }


def _update_high_cost_metrics(
    metrics: _RunEventMetrics,
    *,
    row: dict[str, Any],
    status: Any,
    event_name: str,
    tool: str,
    capabilities: list[str],
    high_cost_rules: list[dict[str, Any]],
) -> None:
    matched_rules = [
        rule["rule_id"]
        for rule in high_cost_rules
        if _match_high_cost_rule(
            row=row,
            tool=tool,
            capabilities=capabilities,
            rule=rule,
        )
    ]
    if not matched_rules:
        return
    metrics.high_cost_call_count += 1
    if status == "failed" or event_name == "STEP_FAILED":
        metrics.high_cost_failure_count += 1
    for rule_id in matched_rules:
        metrics.high_cost_rule_hits[rule_id] += 1


def _waiting_chain_complete(metrics: _RunEventMetrics) -> bool:
    if not metrics.waiting_enter_ids:
        return True
    return metrics.waiting_enter_ids.issubset(
        metrics.waiting_exit_ids | metrics.decision_pending_ids
    )


def _failure_traceable(step_failed_details: list[dict[str, Any]]) -> bool:
    for detail in step_failed_details:
        if not (detail.get("step_id") and detail.get("tool") and detail.get("failure_code")):
            return False
    return True


def _abnormal_reasons(
    *,
    final_status: str,
    waiting_chain_complete: bool,
    failure_traceable: bool,
    step_failed_count: int,
) -> list[str]:
    reasons: list[str] = []
    waiting_or_terminal = {
        "FAILED",
        "CANCELLED",
        "WAITING_PLAN_CONFIRM",
        "WAITING_PATCH_CONFIRM",
        "WAITING_REPLAN_CONFIRM",
        "WAITING_PATCH",
        "WAITING_REPLAN",
    }
    if final_status in waiting_or_terminal:
        reasons.append(f"terminal_or_waiting_status:{final_status}")
    if not waiting_chain_complete:
        reasons.append("waiting_chain_incomplete")
    if not failure_traceable:
        reasons.append("failure_not_traceable")
    if step_failed_count > 0:
        reasons.append("step_failed")
    return reasons


def _apply_snapshot_observability(
    *,
    metrics: _RunEventMetrics,
    snapshot_artifacts: dict[str, Any],
) -> None:
    if isinstance(snapshot_artifacts.get("runtime_state"), dict):
        metrics.runtime_state_observable = True
    if not isinstance(snapshot_artifacts.get("decision_summary"), dict):
        return
    decision_summary = snapshot_artifacts.get("decision_summary") or {}
    if isinstance(decision_summary.get("shadow_score"), dict):
        metrics.shadow_output_observable = True
    if isinstance(decision_summary.get("shadow_action"), str) and decision_summary.get("shadow_action"):
        metrics.shadow_output_observable = True


def _shadow_action_rates(metrics: _RunEventMetrics) -> tuple[float | None, int, float | None]:
    if metrics.shadow_action_observation_count <= 0:
        return None, 0, None
    agreement_rate = (
        metrics.shadow_action_agreement_count / metrics.shadow_action_observation_count
    )
    bias_count = (
        metrics.shadow_action_observation_count - metrics.shadow_action_agreement_count
    )
    return agreement_rate, bias_count, bias_count / metrics.shadow_action_observation_count


def extract_run_metrics(
    run: dict[str, Any],
    *,
    tool_capability_map: dict[str, list[str]],
    requirement2_capability_map: dict[str, list[str]],
    high_cost_rules: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    event_log_path, snapshot_path, report_path = resolve_run_artifact_paths(run)
    rows = read_jsonl(event_log_path)
    resolved_high_cost_rules = normalize_high_cost_rules(high_cost_rules)
    snapshot_payload = _load_snapshot_payload(snapshot_path) if snapshot_path else None
    snapshot_artifacts = (
        snapshot_payload.get("artifacts")
        if isinstance(snapshot_payload, dict) and isinstance(snapshot_payload.get("artifacts"), dict)
        else {}
    )

    event_metrics = _collect_run_event_metrics(
        rows=rows,
        tool_capability_map=tool_capability_map,
        high_cost_rules=resolved_high_cost_rules,
    )

    final_status = resolve_final_status(run, event_metrics.final_status)

    started_at = parse_iso_datetime(run.get("started_at"))
    finished_at = parse_iso_datetime(run.get("finished_at"))
    duration_ms_value = compute_duration_ms(
        run=run,
        started_at=started_at,
        finished_at=finished_at,
        timestamps=event_metrics.timestamps,
    )

    success = final_status == "DONE"
    first_pass_success = (
        success
        and event_metrics.patch_event_count == 0
        and event_metrics.replan_event_count == 0
        and event_metrics.waiting_enter_count == 0
    )
    schema_valid = event_metrics.candidate_validation_failed == 0
    executable_plan = event_metrics.step_failed_count == 0

    waiting_chain_complete = _waiting_chain_complete(event_metrics)
    failure_traceable = _failure_traceable(event_metrics.step_failed_details)
    abnormal_reasons = _abnormal_reasons(
        final_status=final_status,
        waiting_chain_complete=waiting_chain_complete,
        failure_traceable=failure_traceable,
        step_failed_count=event_metrics.step_failed_count,
    )

    requirement2_coverage = build_requirement2_coverage(
        capability_usage=dict(event_metrics.capability_usage),
        requirement2_capability_map=requirement2_capability_map,
    )

    _apply_snapshot_observability(
        metrics=event_metrics,
        snapshot_artifacts=snapshot_artifacts,
    )

    belief_state_metrics = _collect_belief_state_metrics(
        rows=rows,
        snapshot_artifacts=snapshot_artifacts,
        run=run,
    )

    (
        shadow_action_agreement_rate,
        shadow_actual_bias_count,
        shadow_actual_bias_rate,
    ) = _shadow_action_rates(event_metrics)

    original_group_id = run.get("group_id")
    canonical_group_id = canonicalize_group_id(original_group_id)

    metrics = {
        "run_id": run.get("run_id"),
        "task_id": run.get("task_id"),
        "task_key": run.get("task_key"),
        "group_id": original_group_id,
        "canonical_group_id": canonical_group_id,
        "group_alias": original_group_id if original_group_id != canonical_group_id else "",
        "replicate": run.get("replicate"),
        "freeze_id": run.get("freeze_id"),
        "event_log_path": str(event_log_path) if str(event_log_path) != "." else "",
        "snapshot_path": str(snapshot_path) if snapshot_path else "",
        "report_path": str(report_path) if report_path else "",
        "started_at": run.get("started_at"),
        "finished_at": run.get("finished_at"),
        "duration_ms": round(duration_ms_value, 3),
        "final_status": final_status,
        "success": success,
        "first_pass_success": first_pass_success,
        "schema_valid": schema_valid,
        "executable_plan": executable_plan,
        "patch_event_count": event_metrics.patch_event_count,
        "replan_event_count": event_metrics.replan_event_count,
        "suffix_replan_event_count": event_metrics.suffix_replan_event_count,
        "waiting_enter_count": event_metrics.waiting_enter_count,
        "step_failed_count": event_metrics.step_failed_count,
        "step_finished_count": event_metrics.step_finished_count,
        "waiting_chain_complete": waiting_chain_complete,
        "failure_traceable": failure_traceable,
        "snapshot_linked": bool(snapshot_path and snapshot_path.exists()),
        "report_linked": bool(report_path and report_path.exists()),
        "runtime_state_observable": event_metrics.runtime_state_observable,
        "shadow_output_observable": event_metrics.shadow_output_observable,
        "action_continue_count": event_metrics.action_counter.get("continue", 0),
        "action_patch_local_count": event_metrics.action_counter.get("patch_local", 0),
        "action_suffix_replan_count": event_metrics.action_counter.get("suffix_replan", 0),
        "action_stop_count": event_metrics.action_counter.get("stop", 0),
        "shadow_action_agreement_count": event_metrics.shadow_action_agreement_count,
        "shadow_action_observation_count": event_metrics.shadow_action_observation_count,
        "shadow_action_agreement_rate": shadow_action_agreement_rate,
        "shadow_actual_bias_count": shadow_actual_bias_count,
        "shadow_actual_bias_rate": shadow_actual_bias_rate,
        "layer_counter": dict(event_metrics.layer_counter),
        "tool_usage": dict(event_metrics.tool_usage),
        "capability_usage": dict(event_metrics.capability_usage),
        "high_cost_call_count": event_metrics.high_cost_call_count,
        "high_cost_failure_count": event_metrics.high_cost_failure_count,
        "high_cost_rule_hits": dict(event_metrics.high_cost_rule_hits),
        "requirement2_coverage": requirement2_coverage,
        "suffix_prefix_samples": event_metrics.suffix_prefix_samples,
        "abnormal_reasons": abnormal_reasons,
        "step_failed_details": event_metrics.step_failed_details,
        "replay_sample_id": run.get("replay_sample_id"),
        "replay_source_freeze_id": run.get("replay_source_freeze_id"),
    }
    metrics.update(belief_state_metrics)
    for field in BELIEF_STATE_CORE_FIELDS:
        metrics[f"belief_state_{field}"] = belief_state_metrics["belief_state_latest"].get(
            field
        )
        metrics[f"belief_state_{field}_observed"] = belief_state_metrics[
            "belief_state_core_observed"
        ].get(field, False)
    for field in BELIEF_STATE_DERIVED_FIELDS:
        metrics[f"belief_state_{field}"] = belief_state_metrics["belief_state_latest"].get(
            field
        )
        metrics[f"belief_state_{field}_observed"] = belief_state_metrics[
            "belief_state_derived_observed"
        ].get(field, False)
    return metrics


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


def _collect_group_aggregate_counters(
    *,
    rows: list[dict[str, Any]],
    group_id: str,
) -> _GroupAggregateCounters:
    counters = _GroupAggregateCounters(
        aliases=sorted(
            {
                str(row.get("group_id"))
                for row in rows
                if isinstance(row.get("group_id"), str) and row.get("group_id") != group_id
            }
        )
    )
    for row in rows:
        _merge_counter_mapping(
            target=counters.patch_layer_counter,
            raw_mapping=row.get("layer_counter"),
            on_count=lambda count: setattr(
                counters,
                "total_patch_events_with_layer",
                counters.total_patch_events_with_layer + count,
            ),
        )
        _merge_counter_mapping(
            target=counters.capability_counter,
            raw_mapping=row.get("capability_usage"),
        )
        _merge_counter_mapping(
            target=counters.tool_counter,
            raw_mapping=row.get("tool_usage"),
        )
        _merge_counter_mapping(
            target=counters.high_cost_rule_counter,
            raw_mapping=row.get("high_cost_rule_hits"),
        )
        counters.suffix_prefix_samples.extend(
            [bool(value) for value in row.get("suffix_prefix_samples") or []]
        )
        counters.shadow_action_agreement_total += int(
            row.get("shadow_action_agreement_count", 0) or 0
        )
        counters.shadow_action_observation_total += int(
            row.get("shadow_action_observation_count", 0) or 0
        )
    return counters


def _group_float_series(rows: list[dict[str, Any]], key: str) -> list[float]:
    return [float(item.get(key, 0) or 0) for item in rows]


def _group_action_totals(
    *,
    continue_counts: list[float],
    patch_counts: list[float],
    suffix_replan_counts: list[float],
    stop_counts: list[float],
) -> dict[str, float]:
    return {
        "continue": sum(continue_counts),
        "patch_local": sum(patch_counts),
        "suffix_replan": sum(suffix_replan_counts),
        "stop": sum(stop_counts),
    }


def _group_proportion_summaries(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        "success": _proportion_summary([bool(item.get("success")) for item in rows]),
        "first_pass": _proportion_summary([bool(item.get("first_pass_success")) for item in rows]),
        "schema": _proportion_summary([bool(item.get("schema_valid")) for item in rows]),
        "executable": _proportion_summary([bool(item.get("executable_plan")) for item in rows]),
        "waiting_chain": _proportion_summary([bool(item.get("waiting_chain_complete")) for item in rows]),
        "traceability": _proportion_summary([bool(item.get("failure_traceable")) for item in rows]),
        "snapshot_linked": _proportion_summary([bool(item.get("snapshot_linked")) for item in rows]),
        "runtime_state_observable": _proportion_summary(
            [bool(item.get("runtime_state_observable")) for item in rows]
        ),
        "shadow_output_observable": _proportion_summary(
            [bool(item.get("shadow_output_observable")) for item in rows]
        ),
    }


def _merge_counter_mapping(
    *,
    target: Counter[str],
    raw_mapping: Any,
    on_count: Any = None,
) -> None:
    if not isinstance(raw_mapping, dict):
        return
    for key, value in raw_mapping.items():
        if isinstance(key, str) and isinstance(value, (int, float)):
            count = int(value)
            target[key] += count
            if on_count is not None:
                on_count(count)


def _build_requirement2_slice_rows(
    *,
    group_id: str,
    requirement2_capability_map: dict[str, list[str]],
    requirement2_bucket_status: dict[str, bool],
    counters: _GroupAggregateCounters,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for bucket, capabilities in requirement2_capability_map.items():
        rows.append(
            {
                "group_id": group_id,
                "slice_type": "capability_bucket",
                "name": bucket,
                "covered": requirement2_bucket_status.get(bucket, False),
                "usage_count": sum(
                    counters.capability_counter.get(cap, 0) for cap in capabilities
                ),
            }
        )
    rows.extend(
        {
            "group_id": group_id,
            "slice_type": "capability",
            "name": capability,
            "covered": usage > 0,
            "usage_count": usage,
        }
        for capability, usage in sorted(counters.capability_counter.items())
    )
    rows.extend(
        {
            "group_id": group_id,
            "slice_type": "tool",
            "name": tool,
            "covered": usage > 0,
            "usage_count": usage,
        }
        for tool, usage in sorted(counters.tool_counter.items())
    )
    return rows


def _build_abnormal_rows(
    *,
    rows: list[dict[str, Any]],
    group_id: str,
) -> list[dict[str, Any]]:
    abnormal_rows: list[dict[str, Any]] = []
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
    return abnormal_rows


def _ratio_or_none(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator > 0 else None


def _patch_minimality_rate(counters: _GroupAggregateCounters) -> float | None:
    if counters.total_patch_events_with_layer <= 0:
        return None
    return (
        counters.patch_layer_counter.get("parameter_level", 0)
        / counters.total_patch_events_with_layer
    )


def _suffix_prefix_preservation_rate(counters: _GroupAggregateCounters) -> float | None:
    if not counters.suffix_prefix_samples:
        return None
    return (
        sum(1 for flag in counters.suffix_prefix_samples if flag)
        / len(counters.suffix_prefix_samples)
    )


def _group_shadow_rates(
    counters: _GroupAggregateCounters,
) -> tuple[float | None, int, float | None]:
    if counters.shadow_action_observation_total <= 0:
        return None, 0, None
    agreement_rate = (
        counters.shadow_action_agreement_total
        / counters.shadow_action_observation_total
    )
    bias_total = (
        counters.shadow_action_observation_total
        - counters.shadow_action_agreement_total
    )
    return agreement_rate, bias_total, bias_total / counters.shadow_action_observation_total


def aggregate_group_metrics(
    runs: list[dict[str, Any]],
    *,
    group_order: list[str],
    iterations: int,
    seed: int,
    thresholds: dict[str, float],
    requirement2_capability_map: dict[str, list[str]],
) -> dict[str, Any]:
    grouped = group_runs_by_order(
        runs,
        group_order=group_order,
        canonicalize_group_id=canonicalize_group_id,
    )

    summary_rows: list[dict[str, Any]] = []
    patch_rows: list[dict[str, Any]] = []
    high_cost_rows: list[dict[str, Any]] = []
    action_rows: list[dict[str, Any]] = []
    belief_state_rows: list[dict[str, Any]] = []
    requirement2_rows: list[dict[str, Any]] = []
    abnormal_rows: list[dict[str, Any]] = []
    gate_rows: list[dict[str, Any]] = []

    for idx, group_id in enumerate(group_order):
        rows = grouped.get(group_id, [])
        if not rows:
            continue

        proportions = _group_proportion_summaries(rows)

        patch_counts = _group_float_series(rows, "patch_event_count")
        replan_counts = _group_float_series(rows, "replan_event_count")
        suffix_counts = _group_float_series(rows, "suffix_replan_event_count")
        duration_values = _group_float_series(rows, "duration_ms")
        high_cost_counts = _group_float_series(rows, "high_cost_call_count")
        high_cost_failure_counts = _group_float_series(rows, "high_cost_failure_count")
        action_continue_counts = _group_float_series(rows, "action_continue_count")
        action_patch_counts = _group_float_series(rows, "action_patch_local_count")
        action_suffix_replan_counts = _group_float_series(rows, "action_suffix_replan_count")
        action_stop_counts = _group_float_series(rows, "action_stop_count")
        action_totals_by_name = _group_action_totals(
            continue_counts=action_continue_counts,
            patch_counts=action_patch_counts,
            suffix_replan_counts=action_suffix_replan_counts,
            stop_counts=action_stop_counts,
        )
        action_total = sum(action_totals_by_name.values())

        patch_summary = _mean_summary(patch_counts, iterations=iterations, seed=seed + idx * 11 + 1)
        replan_summary = _mean_summary(replan_counts, iterations=iterations, seed=seed + idx * 11 + 2)
        suffix_summary = _mean_summary(suffix_counts, iterations=iterations, seed=seed + idx * 11 + 3)
        duration_summary = _mean_summary(duration_values, iterations=iterations, seed=seed + idx * 11 + 4)
        high_cost_summary = _mean_summary(
            high_cost_counts,
            iterations=iterations,
            seed=seed + idx * 11 + 5,
        )
        high_cost_failure_summary = _mean_summary(
            high_cost_failure_counts,
            iterations=iterations,
            seed=seed + idx * 11 + 6,
        )
        continue_summary = _mean_summary(
            action_continue_counts,
            iterations=iterations,
            seed=seed + idx * 11 + 7,
        )
        patch_action_summary = _mean_summary(
            action_patch_counts,
            iterations=iterations,
            seed=seed + idx * 11 + 8,
        )
        suffix_action_summary = _mean_summary(
            action_suffix_replan_counts,
            iterations=iterations,
            seed=seed + idx * 11 + 9,
        )
        stop_action_summary = _mean_summary(
            action_stop_counts,
            iterations=iterations,
            seed=seed + idx * 11 + 10,
        )

        counters = _collect_group_aggregate_counters(rows=rows, group_id=group_id)

        patch_minimality_hit_rate = _patch_minimality_rate(counters)
        suffix_prefix_preservation_rate = _suffix_prefix_preservation_rate(counters)
        (
            shadow_action_agreement_rate,
            shadow_actual_bias_total,
            shadow_actual_bias_rate,
        ) = _group_shadow_rates(counters)
        belief_core_observed_rates = {
            field: _proportion_summary(
                [bool(item.get(f"belief_state_{field}_observed")) for item in rows]
            )
            for field in BELIEF_STATE_CORE_FIELDS
        }
        belief_derived_observed_rates = {
            field: _proportion_summary(
                [bool(item.get(f"belief_state_{field}_observed")) for item in rows]
            )
            for field in BELIEF_STATE_DERIVED_FIELDS
        }
        belief_state_observable = _proportion_summary(
            [int(item.get("belief_state_observation_count", 0) or 0) > 0 for item in rows]
        )
        belief_state_core_complete = _proportion_summary(
            [bool(item.get("belief_state_core_complete")) for item in rows]
        )
        belief_core_completeness = _mean_summary(
            [float(item.get("belief_state_core_completeness", 0.0) or 0.0) for item in rows],
            iterations=iterations,
            seed=seed + idx * 11 + 11,
        )
        belief_derived_completeness = _mean_summary(
            [
                float(item.get("belief_state_derived_completeness", 0.0) or 0.0)
                for item in rows
            ],
            iterations=iterations,
            seed=seed + idx * 11 + 12,
        )

        requirement2_bucket_status: dict[str, bool] = {}
        for bucket, capabilities in requirement2_capability_map.items():
            requirement2_bucket_status[bucket] = any(
                counters.capability_counter.get(cap, 0) > 0 for cap in capabilities
            )

        summary_row = {
            "group_id": group_id,
            "canonical_group_id": canonicalize_group_id(group_id),
            "group_aliases": counters.aliases,
            "runs": len(rows),
            "success_rate": proportions["success"]["rate"],
            "success_ci_low": proportions["success"]["ci_low"],
            "success_ci_high": proportions["success"]["ci_high"],
            "first_pass_success_rate": proportions["first_pass"]["rate"],
            "first_pass_ci_low": proportions["first_pass"]["ci_low"],
            "first_pass_ci_high": proportions["first_pass"]["ci_high"],
            "schema_valid_rate": proportions["schema"]["rate"],
            "schema_ci_low": proportions["schema"]["ci_low"],
            "schema_ci_high": proportions["schema"]["ci_high"],
            "executable_plan_rate": proportions["executable"]["rate"],
            "executable_ci_low": proportions["executable"]["ci_low"],
            "executable_ci_high": proportions["executable"]["ci_high"],
            "waiting_chain_complete_rate": proportions["waiting_chain"]["rate"],
            "failure_traceable_rate": proportions["traceability"]["rate"],
            "snapshot_linked_rate": proportions["snapshot_linked"]["rate"],
            "runtime_state_observable_rate": proportions["runtime_state_observable"]["rate"],
            "shadow_output_observable_rate": proportions["shadow_output_observable"]["rate"],
            "belief_state_observable_rate": belief_state_observable["rate"],
            "belief_state_core_complete_rate": belief_state_core_complete["rate"],
            "belief_state_core_completeness_mean": belief_core_completeness["mean"],
            "belief_state_derived_completeness_mean": belief_derived_completeness["mean"],
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
            "high_cost_call_mean": high_cost_summary["mean"],
            "high_cost_call_ci_low": high_cost_summary["ci_low"],
            "high_cost_call_ci_high": high_cost_summary["ci_high"],
            "high_cost_failure_mean": high_cost_failure_summary["mean"],
            "high_cost_failure_ci_low": high_cost_failure_summary["ci_low"],
            "high_cost_failure_ci_high": high_cost_failure_summary["ci_high"],
            "patch_minimality_hit_rate": patch_minimality_hit_rate,
            "suffix_replan_prefix_preservation_rate": suffix_prefix_preservation_rate,
            "action_continue_mean": continue_summary["mean"],
            "action_continue_ci_low": continue_summary["ci_low"],
            "action_continue_ci_high": continue_summary["ci_high"],
            "action_patch_local_mean": patch_action_summary["mean"],
            "action_patch_local_ci_low": patch_action_summary["ci_low"],
            "action_patch_local_ci_high": patch_action_summary["ci_high"],
            "action_suffix_replan_mean": suffix_action_summary["mean"],
            "action_suffix_replan_ci_low": suffix_action_summary["ci_low"],
            "action_suffix_replan_ci_high": suffix_action_summary["ci_high"],
            "action_stop_mean": stop_action_summary["mean"],
            "action_stop_ci_low": stop_action_summary["ci_low"],
            "action_stop_ci_high": stop_action_summary["ci_high"],
            "shadow_action_agreement_rate": shadow_action_agreement_rate,
            "shadow_actual_bias_rate": shadow_actual_bias_rate,
            "requirement2_sequence_core": requirement2_bucket_status.get("sequence_core", False),
            "requirement2_quality_qc": requirement2_bucket_status.get("quality_qc", False),
            "requirement2_objective_scoring": requirement2_bucket_status.get("objective_scoring", False),
            "requirement2_structure_prediction": requirement2_bucket_status.get("structure_prediction", False),
        }
        for action_name, total in action_totals_by_name.items():
            summary_row[f"action_{action_name}_rate"] = (
                _ratio_or_none(total, action_total)
            )
        for field, field_summary in belief_core_observed_rates.items():
            summary_row[f"belief_state_{field}_observable_rate"] = field_summary["rate"]
        for field, field_summary in belief_derived_observed_rates.items():
            summary_row[f"belief_state_{field}_observable_rate"] = field_summary["rate"]
        for bucket, covered in requirement2_bucket_status.items():
            summary_row[f"requirement2_{bucket}"] = covered
        summary_rows.append(summary_row)

        patch_rows.append(
            {
                "group_id": group_id,
                "patch_events_total": sum(patch_counts),
                "replan_events_total": sum(replan_counts),
                "suffix_replan_events_total": sum(suffix_counts),
                "patch_parameter_level": counters.patch_layer_counter.get("parameter_level", 0),
                "patch_tool_level": counters.patch_layer_counter.get("tool_level", 0),
                "patch_structure_level": counters.patch_layer_counter.get("structure_level", 0),
                "patch_minimality_hit_rate": patch_minimality_hit_rate,
                "suffix_prefix_sample_size": len(counters.suffix_prefix_samples),
                "suffix_prefix_preservation_rate": suffix_prefix_preservation_rate,
            }
        )

        high_cost_rows.append(
            {
                "group_id": group_id,
                "high_cost_calls_total": sum(high_cost_counts),
                "high_cost_failures_total": sum(high_cost_failure_counts),
                "high_cost_rule_hits": dict(counters.high_cost_rule_counter),
            }
        )

        action_rows.append(
            {
                "group_id": group_id,
                "canonical_group_id": canonicalize_group_id(group_id),
                "group_aliases": counters.aliases,
                "action_total": action_total,
                "action_continue_total": sum(action_continue_counts),
                "action_continue_rate": _ratio_or_none(action_totals_by_name["continue"], action_total),
                "action_patch_local_total": sum(action_patch_counts),
                "action_patch_local_rate": _ratio_or_none(action_totals_by_name["patch_local"], action_total),
                "action_suffix_replan_total": sum(action_suffix_replan_counts),
                "action_suffix_replan_rate": _ratio_or_none(action_totals_by_name["suffix_replan"], action_total),
                "action_stop_total": sum(action_stop_counts),
                "action_stop_rate": _ratio_or_none(action_totals_by_name["stop"], action_total),
                "shadow_action_observation_total": counters.shadow_action_observation_total,
                "shadow_action_agreement_total": counters.shadow_action_agreement_total,
                "shadow_action_agreement_rate": shadow_action_agreement_rate,
                "shadow_actual_bias_total": shadow_actual_bias_total,
                "shadow_actual_bias_rate": shadow_actual_bias_rate,
            }
        )

        belief_state_rows.append(
            {
                "group_id": group_id,
                "canonical_group_id": canonicalize_group_id(group_id),
                "group_aliases": counters.aliases,
                "runs": len(rows),
                "belief_state_observable_rate": belief_state_observable["rate"],
                "belief_state_core_complete_rate": belief_state_core_complete["rate"],
                "belief_state_core_completeness_mean": belief_core_completeness["mean"],
                "belief_state_derived_completeness_mean": belief_derived_completeness["mean"],
                **{
                    f"{field}_observable_rate": field_summary["rate"]
                    for field, field_summary in belief_core_observed_rates.items()
                },
                **{
                    f"{field}_observable_rate": field_summary["rate"]
                    for field, field_summary in belief_derived_observed_rates.items()
                },
            }
        )

        requirement2_rows.extend(
            _build_requirement2_slice_rows(
                group_id=group_id,
                requirement2_capability_map=requirement2_capability_map,
                requirement2_bucket_status=requirement2_bucket_status,
                counters=counters,
            )
        )
        abnormal_rows.extend(_build_abnormal_rows(rows=rows, group_id=group_id))

        gate_checks = build_threshold_gate_checks(
            summary_row=summary_row,
            thresholds=thresholds,
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
        "high_cost_rows": high_cost_rows,
        "action_rows": action_rows,
        "belief_state_rows": belief_state_rows,
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
    group_order_set = set(group_order)
    for row in runs:
        group_id = row.get("group_id")
        canonical_group_id = row.get("canonical_group_id") or canonicalize_group_id(group_id)
        if isinstance(canonical_group_id, str) and canonical_group_id in group_order_set:
            by_group[canonical_group_id].append(row)
        elif isinstance(group_id, str):
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
        "| group | runs | success_rate | first_pass | schema_valid | executable | high_cost_mean | patch_mean | replan_mean | duration_ms_mean |"
    )
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for row in summary_rows:
        lines.append(
            "| {group_id} | {runs} | {success_rate:.4f} | {first_pass_success_rate:.4f} | {schema_valid_rate:.4f} | {executable_plan_rate:.4f} | {high_cost_call_mean:.4f} | {patch_events_mean:.4f} | {replan_events_mean:.4f} | {duration_ms_mean:.2f} |".format(
                group_id=row.get("group_id"),
                runs=row.get("runs", 0),
                success_rate=float(row.get("success_rate") or 0.0),
                first_pass_success_rate=float(row.get("first_pass_success_rate") or 0.0),
                schema_valid_rate=float(row.get("schema_valid_rate") or 0.0),
                executable_plan_rate=float(row.get("executable_plan_rate") or 0.0),
                high_cost_call_mean=float(row.get("high_cost_call_mean") or 0.0),
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
    lines.append("- Action-level metrics: `action_distribution_breakdown.csv` exports `continue / patch_local / suffix_replan / stop` totals, rates, and shadow/actual bias.")
    lines.append("- Belief-state metrics: `belief_state_observability_breakdown.csv` exports the five frozen core-state observable rates and derived-field completeness.")
    lines.append("- Naming: `canonical_group_id` preserves the paper group name while `group_aliases` links back to historical `A0-A6` or external aliases.")

    return "\n".join(lines) + "\n"
