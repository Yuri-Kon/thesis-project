#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_OUTPUT_ROOT = Path("output/experiment/w12-expr-1")
DEFAULT_EXTRACT_OUTPUT_DIR = Path("output/experiment/w12-expr-1/_tmp/w11-data-1")
DEFAULT_GATE_OUTPUT_DIR = Path("output/experiment/w12-expr-1/_tmp/w11-data-2")
DEFAULT_TIME_WINDOW_START = "2026-03-16T00:00:00+08:00"
DEFAULT_TIME_WINDOW_END = "2026-03-18T23:59:59+08:00"
DEFAULT_MIN_D_MAIN = 12
DEFAULT_MIN_D_RECOVERY = 8
DEFAULT_MIN_D_HITL = 8
DEFAULT_HITL_PENDING_ACTION_RATE = 0.95
ACCEPTED_STATUSES = {"PASS", "WARN"}


def _json_dump(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2)


def _str_value(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write(_json_dump(payload) + "\n")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n")


def _file_sha256(path: Path | None) -> str | None:
    if path is None or not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_iso_datetime(value: str | None) -> datetime | None:
    text = _str_value(value)
    if not text:
        return None
    normalized = text
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def _git_short_sha() -> str:
    try:
        return (
            subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True)
            .strip()
            .lower()
        )
    except Exception:
        return "nogit"


def _default_freeze_id() -> str:
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"w12-expr1-freeze-{day}-{_git_short_sha()}"


def _quality_status(sample: dict[str, Any]) -> str:
    gate = sample.get("quality_gate")
    if not isinstance(gate, dict):
        return "UNKNOWN"
    status = _str_value(gate.get("status"))
    return status or "UNKNOWN"


def _quality_split(sample: dict[str, Any]) -> str:
    gate = sample.get("quality_gate")
    if isinstance(gate, dict):
        split = _str_value(gate.get("split"))
        if split:
            return split
    return "unknown"


def _sample_id(sample: dict[str, Any]) -> str:
    return _str_value(sample.get("sample_id")) or "sample::unknown"


def _task_id(sample: dict[str, Any]) -> str | None:
    context = sample.get("context")
    if isinstance(context, dict):
        task_id = _str_value(context.get("task_id"))
        if task_id:
            return task_id
    return None


def _sample_anchor_ts(sample: dict[str, Any]) -> str | None:
    context = sample.get("context")
    if not isinstance(context, dict):
        return None
    window = context.get("time_window")
    if not isinstance(window, dict):
        return None
    for key in ("last_ts", "first_ts"):
        value = _str_value(window.get(key))
        if value:
            return value
    return None


def _decision_action_types(sample: dict[str, Any]) -> list[str]:
    actions: list[str] = []
    trace = sample.get("audit_trace")
    if not isinstance(trace, dict):
        return actions
    history = trace.get("decision_history")
    if not isinstance(history, list):
        return actions
    for item in history:
        if not isinstance(item, dict):
            continue
        action = _str_value(item.get("action_type"))
        if action:
            actions.append(action)
    return actions


def _pending_action_ids(sample: dict[str, Any]) -> list[str]:
    trace = sample.get("audit_trace")
    if not isinstance(trace, dict):
        return []
    values = trace.get("pending_action_ids")
    if not isinstance(values, list):
        return []
    rows: list[str] = []
    for value in values:
        text = _str_value(value)
        if text:
            rows.append(text)
    return rows


def _event_ids(sample: dict[str, Any]) -> list[str]:
    trace = sample.get("audit_trace")
    if not isinstance(trace, dict):
        return []
    values = trace.get("event_ids")
    if not isinstance(values, list):
        return []
    rows: list[str] = []
    for value in values:
        text = _str_value(value)
        if text:
            rows.append(text)
    return rows


def _selected_pending_action_id(sample: dict[str, Any]) -> str | None:
    selected = sample.get("selected")
    if not isinstance(selected, dict):
        return None
    return _str_value(selected.get("pending_action_id"))


def _status_path(sample: dict[str, Any]) -> set[str]:
    context = sample.get("context")
    if not isinstance(context, dict):
        return set()
    values = context.get("status_path")
    if not isinstance(values, list):
        return set()
    statuses: set[str] = set()
    for value in values:
        text = _str_value(value)
        if text:
            statuses.add(text)
    return statuses


def _final_status(sample: dict[str, Any]) -> str:
    outcome = sample.get("outcome")
    if not isinstance(outcome, dict):
        return "UNKNOWN"
    return _str_value(outcome.get("final_status")) or "UNKNOWN"


def _step_failure_types(sample: dict[str, Any]) -> list[str]:
    outcome = sample.get("outcome")
    if not isinstance(outcome, dict):
        return []
    values = outcome.get("step_failure_types")
    if not isinstance(values, list):
        return []
    rows: list[str] = []
    for value in values:
        text = _str_value(value)
        if text:
            rows.append(text)
    return rows


def _classify_sample(sample: dict[str, Any]) -> dict[str, Any]:
    actions = [value.lower() for value in _decision_action_types(sample)]
    pending_action_ids = _pending_action_ids(sample)
    selected_pending = _selected_pending_action_id(sample)
    has_hitl = bool(pending_action_ids) or bool(actions) or bool(selected_pending)

    has_recovery_keyword = any(
        "patch" in action or "replan" in action or "recover" in action for action in actions
    )
    final_status = _final_status(sample)
    has_failure = final_status == "FAILED" or bool(_step_failure_types(sample))
    has_recovery = has_failure or has_recovery_keyword

    states = _status_path(sample)
    has_main_state_chain = {"PLANNING", "PLANNED", "RUNNING"}.issubset(states)
    is_d_main = has_main_state_chain and final_status == "DONE" and not has_recovery

    return {
        "sample_id": _sample_id(sample),
        "task_id": _task_id(sample),
        "split": _quality_split(sample),
        "final_status": final_status,
        "anchor_ts": _sample_anchor_ts(sample),
        "has_hitl": has_hitl,
        "has_recovery": has_recovery,
        "is_d_main": is_d_main,
        "is_d_recovery": has_recovery,
        "is_d_hitl": has_hitl,
        "pending_action_ids": pending_action_ids,
        "event_ids": _event_ids(sample),
    }


def _window_filter(
    *,
    samples: list[dict[str, Any]],
    start: datetime,
    end: datetime,
    include_missing_anchor: bool,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    kept: list[dict[str, Any]] = []
    counters: Counter[str] = Counter()
    for sample in samples:
        anchor_raw = _sample_anchor_ts(sample)
        anchor_dt = _parse_iso_datetime(anchor_raw)
        if anchor_raw is None:
            if include_missing_anchor:
                kept.append(sample)
                counters["missing_anchor_included"] += 1
            else:
                counters["missing_anchor_excluded"] += 1
            continue
        if anchor_dt is None:
            counters["invalid_anchor_excluded"] += 1
            continue
        if start <= anchor_dt <= end:
            kept.append(sample)
            counters["in_window"] += 1
        else:
            counters["out_of_window_excluded"] += 1
    return kept, dict(counters)


def _traceability_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "sample_count": 0,
            "task_id_rate": 0.0,
            "event_id_rate": 0.0,
            "pending_action_id_rate": 0.0,
            "missing_examples": [],
        }

    missing_examples: list[dict[str, Any]] = []
    with_task = 0
    with_event = 0
    with_pending = 0
    for sample in rows:
        sample_id = _sample_id(sample)
        task_ok = bool(_task_id(sample))
        event_ok = bool(_event_ids(sample))
        pending_ok = bool(_pending_action_ids(sample) or _selected_pending_action_id(sample))
        if task_ok:
            with_task += 1
        if event_ok:
            with_event += 1
        if pending_ok:
            with_pending += 1
        if len(missing_examples) < 20 and not (task_ok and event_ok and pending_ok):
            missing_examples.append(
                {
                    "sample_id": sample_id,
                    "missing_task_id": not task_ok,
                    "missing_event_ids": not event_ok,
                    "missing_pending_action_id": not pending_ok,
                }
            )

    total = len(rows)
    return {
        "sample_count": total,
        "task_id_rate": round(with_task / total, 6),
        "event_id_rate": round(with_event / total, 6),
        "pending_action_id_rate": round(with_pending / total, 6),
        "missing_examples": missing_examples,
    }


def _split_distribution(rows: list[dict[str, Any]]) -> dict[str, int]:
    counter = Counter(_quality_split(sample) for sample in rows)
    return dict(sorted(counter.items()))


def _build_dataset_index(
    *,
    rows: list[dict[str, Any]],
    annotations: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    index_rows: list[dict[str, Any]] = []
    for sample in sorted(rows, key=_sample_id):
        sample_id = _sample_id(sample)
        info = annotations[sample_id]
        index_rows.append(
            {
                "sample_id": sample_id,
                "task_id": info["task_id"],
                "split": info["split"],
                "final_status": info["final_status"],
                "anchor_ts": info["anchor_ts"],
                "in_d_main": info["is_d_main"],
                "in_d_recovery": info["is_d_recovery"],
                "in_d_hitl": info["is_d_hitl"],
                "has_hitl": info["has_hitl"],
                "has_recovery": info["has_recovery"],
                "event_id_count": len(info["event_ids"]),
                "pending_action_id_count": len(info["pending_action_ids"]),
            }
        )
    return index_rows


def _validate_plan_index(
    *,
    plan_index_path: Path | None,
    window_start: datetime,
    window_end: datetime,
) -> dict[str, Any]:
    if plan_index_path is None:
        return {
            "checked": False,
            "reason": "plan_index_path not provided",
        }
    payload = _read_json(plan_index_path)
    if not payload:
        raise ValueError(f"invalid plan index payload: {plan_index_path}")

    validations = payload.get("validations")
    if not isinstance(validations, dict):
        raise ValueError("plan index missing validations")
    data_front = validations.get("data_issue_on_critical_front")
    if data_front is not True:
        raise ValueError("issue #169 plan validation indicates data issue is not on critical front")

    schedule = payload.get("schedule")
    if not isinstance(schedule, list):
        raise ValueError("plan index missing schedule list")
    issue170 = None
    for row in schedule:
        if isinstance(row, dict) and row.get("number") == 170:
            issue170 = row
            break
    if not isinstance(issue170, dict):
        raise ValueError("plan index does not contain issue #170 schedule row")

    issue170_start = issue170.get("start")
    issue170_end = issue170.get("end")
    if not isinstance(issue170_start, str) or not isinstance(issue170_end, str):
        raise ValueError("issue #170 schedule in plan index has invalid dates")
    try:
        start_date = datetime.fromisoformat(issue170_start).date()
        end_date = datetime.fromisoformat(issue170_end).date()
    except ValueError as exc:
        raise ValueError("issue #170 schedule in plan index has invalid dates") from exc

    window_start_date = window_start.date()
    window_end_date = window_end.date()
    if window_start_date < start_date or window_end_date > end_date:
        raise ValueError("issue #170 freeze window is not aligned with issue #169 schedule")

    return {
        "checked": True,
        "plan_freeze_id": payload.get("plan_freeze_id"),
        "plan_index_path": str(plan_index_path),
        "plan_index_sha256": _file_sha256(plan_index_path),
    }


def build_issue170_freeze(
    *,
    gated_samples_path: Path,
    quality_report_path: Path | None,
    output_root: Path,
    freeze_id: str | None,
    time_window_start: str,
    time_window_end: str,
    min_d_main: int,
    min_d_recovery: int,
    min_d_hitl: int,
    min_hitl_pending_action_rate: float,
    include_missing_anchor: bool,
    plan_index_path: Path | None,
) -> dict[str, Any]:
    start = _parse_iso_datetime(time_window_start)
    end = _parse_iso_datetime(time_window_end)
    if start is None or end is None:
        raise ValueError("time window must be valid ISO-8601 datetime")
    if end < start:
        raise ValueError("time window end must be later than start")

    plan_validation = _validate_plan_index(
        plan_index_path=plan_index_path,
        window_start=start,
        window_end=end,
    )

    all_rows = _read_jsonl(gated_samples_path)
    accepted_rows = [row for row in all_rows if _quality_status(row) in ACCEPTED_STATUSES]
    accepted_rows.sort(key=_sample_id)

    window_rows, window_filter_stats = _window_filter(
        samples=accepted_rows,
        start=start,
        end=end,
        include_missing_anchor=include_missing_anchor,
    )
    window_rows.sort(key=_sample_id)

    annotations = {
        _sample_id(sample): _classify_sample(sample)
        for sample in window_rows
    }

    d_main_rows = [
        sample for sample in window_rows if annotations[_sample_id(sample)]["is_d_main"]
    ]
    d_recovery_rows = [
        sample for sample in window_rows if annotations[_sample_id(sample)]["is_d_recovery"]
    ]
    d_hitl_rows = [
        sample for sample in window_rows if annotations[_sample_id(sample)]["is_d_hitl"]
    ]

    d_main_rows.sort(key=_sample_id)
    d_recovery_rows.sort(key=_sample_id)
    d_hitl_rows.sort(key=_sample_id)

    resolved_freeze_id = freeze_id or _default_freeze_id()
    freeze_dir = output_root / resolved_freeze_id
    freeze_dir.mkdir(parents=True, exist_ok=False)

    d_main_path = freeze_dir / "d_main.jsonl"
    d_recovery_path = freeze_dir / "d_recovery.jsonl"
    d_hitl_path = freeze_dir / "d_hitl.jsonl"
    dataset_index_path = freeze_dir / "dataset_index.jsonl"
    split_spec_path = freeze_dir / "input_version_and_split.json"
    manifest_path = freeze_dir / "dataset_manifest.json"

    _write_jsonl(d_main_path, d_main_rows)
    _write_jsonl(d_recovery_path, d_recovery_rows)
    _write_jsonl(d_hitl_path, d_hitl_rows)
    _write_jsonl(
        dataset_index_path,
        _build_dataset_index(rows=window_rows, annotations=annotations),
    )

    d_main_ids = {row["sample_id"] for row in _build_dataset_index(rows=d_main_rows, annotations=annotations)}
    d_recovery_ids = {row["sample_id"] for row in _build_dataset_index(rows=d_recovery_rows, annotations=annotations)}
    d_hitl_ids = {row["sample_id"] for row in _build_dataset_index(rows=d_hitl_rows, annotations=annotations)}

    overlap = {
        "d_main_and_d_recovery": len(d_main_ids & d_recovery_ids),
        "d_main_and_d_hitl": len(d_main_ids & d_hitl_ids),
        "d_recovery_and_d_hitl": len(d_recovery_ids & d_hitl_ids),
        "all_three": len(d_main_ids & d_recovery_ids & d_hitl_ids),
    }

    traces = {
        "D-main": _traceability_summary(d_main_rows),
        "D-recovery": _traceability_summary(d_recovery_rows),
        "D-hitl": _traceability_summary(d_hitl_rows),
    }

    requirement_counts = {
        "D-main": min_d_main,
        "D-recovery": min_d_recovery,
        "D-hitl": min_d_hitl,
    }
    actual_counts = {
        "D-main": len(d_main_rows),
        "D-recovery": len(d_recovery_rows),
        "D-hitl": len(d_hitl_rows),
    }
    count_checks = {
        key: actual_counts[key] >= requirement_counts[key]
        for key in requirement_counts
    }

    trace_checks = {
        "D-main": traces["D-main"]["task_id_rate"] == 1.0 and traces["D-main"]["event_id_rate"] == 1.0,
        "D-recovery": traces["D-recovery"]["task_id_rate"] == 1.0 and traces["D-recovery"]["event_id_rate"] == 1.0,
        "D-hitl": (
            traces["D-hitl"]["task_id_rate"] == 1.0
            and traces["D-hitl"]["event_id_rate"] == 1.0
            and traces["D-hitl"]["pending_action_id_rate"] >= min_hitl_pending_action_rate
        ),
    }

    gaps: list[str] = []
    for key, ok in count_checks.items():
        if not ok:
            gaps.append(
                f"{key} count {actual_counts[key]} < minimum {requirement_counts[key]}"
            )
    for key, ok in trace_checks.items():
        if not ok:
            gaps.append(f"{key} traceability check failed")

    ready = all(count_checks.values()) and all(trace_checks.values())

    quality_summary = {}
    quality_payload = _read_json(quality_report_path) if quality_report_path else {}
    if quality_payload:
        summary = quality_payload.get("summary")
        if isinstance(summary, dict):
            quality_summary = summary

    split_spec = {
        "split_source": "quality_gate.split",
        "accepted_statuses": sorted(ACCEPTED_STATUSES),
        "time_window_filter": {
            "start": _to_iso(start),
            "end": _to_iso(end),
            "include_missing_anchor": include_missing_anchor,
            "stats": window_filter_stats,
        },
        "notes": [
            "D-main: DONE samples with core planning/running states and without recovery markers.",
            "D-recovery: samples with failure evidence or patch/replan recovery markers.",
            "D-hitl: samples with pending action or decision chain evidence.",
        ],
    }
    _write_json(split_spec_path, split_spec)

    manifest = {
        "schema_version": "w12.issue170.freeze.v1",
        "issue_id": 170,
        "freeze_id": resolved_freeze_id,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "time_window": {
            "start": _to_iso(start),
            "end": _to_iso(end),
        },
        "input": {
            "gated_samples_path": str(gated_samples_path),
            "quality_report_path": str(quality_report_path) if quality_report_path else None,
            "sha256": {
                "gated_samples": _file_sha256(gated_samples_path),
                "quality_report": _file_sha256(quality_report_path),
            },
            "accepted_statuses": sorted(ACCEPTED_STATUSES),
            "accepted_total_before_window_filter": len(accepted_rows),
            "accepted_total_after_window_filter": len(window_rows),
            "quality_report_summary": quality_summary,
        },
        "datasets": {
            "D-main": {
                "count": len(d_main_rows),
                "path": str(d_main_path),
                "split_distribution": _split_distribution(d_main_rows),
                "traceability": traces["D-main"],
            },
            "D-recovery": {
                "count": len(d_recovery_rows),
                "path": str(d_recovery_path),
                "split_distribution": _split_distribution(d_recovery_rows),
                "traceability": traces["D-recovery"],
            },
            "D-hitl": {
                "count": len(d_hitl_rows),
                "path": str(d_hitl_path),
                "split_distribution": _split_distribution(d_hitl_rows),
                "traceability": traces["D-hitl"],
            },
        },
        "overlap": overlap,
        "minimum_sample_requirements": {
            "counts": requirement_counts,
            "hitl_pending_action_id_rate": min_hitl_pending_action_rate,
        },
        "downstream_ready": {
            "ready": ready,
            "count_checks": count_checks,
            "traceability_checks": trace_checks,
            "gaps": gaps,
        },
        "plan_validation": plan_validation,
        "artifacts": {
            "freeze_dir": str(freeze_dir),
            "dataset_index_path": str(dataset_index_path),
            "split_spec_path": str(split_spec_path),
            "manifest_path": str(manifest_path),
        },
        "manifest_path": str(manifest_path.resolve()),
    }
    _write_json(manifest_path, manifest)
    return manifest


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Freeze experiment datasets: D-main / D-recovery / D-hitl + manifest.",
    )
    parser.add_argument("--gated-samples-path", type=Path, default=None)
    parser.add_argument("--quality-report-path", type=Path, default=None)
    parser.add_argument("--logs-dir", type=Path, default=Path("data/logs"))
    parser.add_argument("--snapshots-dir", type=Path, default=Path("data/snapshots"))
    parser.add_argument("--reports-dir", type=Path, default=Path("output/reports"))
    parser.add_argument("--metrics-dir", type=Path, default=Path("output/metrics"))
    parser.add_argument("--tool-kg-path", type=Path, default=Path("src/kg/protein_tool_kg.json"))
    parser.add_argument(
        "--tool-extension-kg-path",
        type=Path,
        default=Path("src/kg/protein_tool_kg/extension_draft_v0.1.json"),
    )
    parser.add_argument("--extract-output-dir", type=Path, default=DEFAULT_EXTRACT_OUTPUT_DIR)
    parser.add_argument("--gate-output-dir", type=Path, default=DEFAULT_GATE_OUTPUT_DIR)
    parser.add_argument("--skip-extract", action="store_true")
    parser.add_argument("--skip-quality-gate", action="store_true")
    parser.add_argument("--split-strategy", choices=("time", "task_hash"), default="time")
    parser.add_argument("--train-ratio", type=float, default=0.70)
    parser.add_argument("--val-ratio", type=float, default=0.15)
    parser.add_argument("--plddt-min", type=float, default=0.70)
    parser.add_argument("--score-completeness-min", type=float, default=0.80)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--freeze-id", type=str, default=None)
    parser.add_argument("--time-window-start", type=str, default=DEFAULT_TIME_WINDOW_START)
    parser.add_argument("--time-window-end", type=str, default=DEFAULT_TIME_WINDOW_END)
    parser.add_argument("--min-d-main", type=int, default=DEFAULT_MIN_D_MAIN)
    parser.add_argument("--min-d-recovery", type=int, default=DEFAULT_MIN_D_RECOVERY)
    parser.add_argument("--min-d-hitl", type=int, default=DEFAULT_MIN_D_HITL)
    parser.add_argument(
        "--min-hitl-pending-action-rate",
        type=float,
        default=DEFAULT_HITL_PENDING_ACTION_RATE,
    )
    parser.add_argument(
        "--include-missing-anchor",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Include samples without context.time_window anchor in freeze window filtering.",
    )
    parser.add_argument(
        "--plan-index-path",
        type=Path,
        default=None,
        help="Optional execution plan index for hard-dependency validation.",
    )
    parser.add_argument(
        "--allow-not-ready",
        action="store_true",
        help="Exit with code 0 even when downstream_ready.ready=false.",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    python_exe = sys.executable

    gated_samples_path = args.gated_samples_path
    quality_report_path = args.quality_report_path

    if gated_samples_path is None:
        if not args.skip_extract:
            _run(
                [
                    python_exe,
                    "scripts/extract_training_samples.py",
                    "--logs-dir",
                    str(args.logs_dir),
                    "--snapshots-dir",
                    str(args.snapshots_dir),
                    "--reports-dir",
                    str(args.reports_dir),
                    "--metrics-dir",
                    str(args.metrics_dir),
                    "--tool-kg-path",
                    str(args.tool_kg_path),
                    "--tool-extension-kg-path",
                    str(args.tool_extension_kg_path),
                    "--output-dir",
                    str(args.extract_output_dir),
                ]
            )

        if not args.skip_quality_gate:
            _run(
                [
                    python_exe,
                    "scripts/quality_gate_training_data.py",
                    "--samples-path",
                    str(args.extract_output_dir / "samples.jsonl"),
                    "--output-dir",
                    str(args.gate_output_dir),
                    "--split-strategy",
                    args.split_strategy,
                    "--train-ratio",
                    str(args.train_ratio),
                    "--val-ratio",
                    str(args.val_ratio),
                    "--plddt-min",
                    str(args.plddt_min),
                    "--score-completeness-min",
                    str(args.score_completeness_min),
                ]
            )

        gated_samples_path = args.gate_output_dir / "gated_samples.jsonl"
        quality_report_path = args.gate_output_dir / "quality_gate_report.json"

    if gated_samples_path is None:
        raise ValueError("gated_samples_path must be resolved")

    manifest = build_issue170_freeze(
        gated_samples_path=gated_samples_path,
        quality_report_path=quality_report_path,
        output_root=args.output_root,
        freeze_id=args.freeze_id,
        time_window_start=args.time_window_start,
        time_window_end=args.time_window_end,
        min_d_main=args.min_d_main,
        min_d_recovery=args.min_d_recovery,
        min_d_hitl=args.min_d_hitl,
        min_hitl_pending_action_rate=args.min_hitl_pending_action_rate,
        include_missing_anchor=args.include_missing_anchor,
        plan_index_path=args.plan_index_path,
    )

    print("Experiment dataset freeze completed")
    print(
        _json_dump(
            {
                "freeze_id": manifest["freeze_id"],
                "downstream_ready": manifest["downstream_ready"]["ready"],
                "counts": {
                    "D-main": manifest["datasets"]["D-main"]["count"],
                    "D-recovery": manifest["datasets"]["D-recovery"]["count"],
                    "D-hitl": manifest["datasets"]["D-hitl"]["count"],
                },
                "manifest_path": manifest["manifest_path"],
            }
        )
    )

    if not manifest["downstream_ready"]["ready"] and not args.allow_not_ready:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
