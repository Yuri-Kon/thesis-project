#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

LEGACY_EVENT_TYPE_MAP = {
    "TASK_STATUS_CHANGED": "STATE_TRANSITION",
    "PENDING_ACTION_CREATED": "PENDING_ACTION_CREATED",
    "DECISION_APPLIED": "DECISION_APPLIED",
    "STEP_FINISHED": "STEP_FINISHED",
    "STEP_FAILED": "STEP_FAILED",
    "DECISION_SUBMITTED": "DECISION_SUBMITTED",
}


def _read_jsonl(path: Path) -> list[tuple[int, dict[str, Any]]]:
    rows: list[tuple[int, dict[str, Any]]] = []
    if not path.exists():
        return rows

    with path.open("r", encoding="utf-8") as handle:
        for idx, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            payload = json.loads(text)
            if not isinstance(payload, dict):
                continue
            rows.append((idx, payload))
    return rows


def _to_event_type(payload: dict[str, Any]) -> str | None:
    event_type = payload.get("event_type")
    if isinstance(event_type, str) and event_type.strip():
        return event_type.strip()

    event = payload.get("event")
    if isinstance(event, str) and event.strip():
        normalized = event.strip()
        return LEGACY_EVENT_TYPE_MAP.get(normalized, normalized)
    return None


def _str_value(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _json_dump(data: Any) -> str:
    return json.dumps(data, ensure_ascii=True, sort_keys=True)


def _load_tool_catalog(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    tools = payload.get("tools")
    if not isinstance(tools, list):
        return {}

    catalog: dict[str, dict[str, Any]] = {}
    for item in tools:
        if not isinstance(item, dict):
            continue
        tool_id = _str_value(item.get("tool_id")) or _str_value(item.get("id"))
        if not tool_id:
            continue

        execution = item.get("execution")
        provider: str | None = None
        model_id: str | None = None
        adapter_mode_default = "unknown"
        if isinstance(execution, str):
            adapter_mode_default = "local" if execution == "nextflow" else "unknown"
        elif isinstance(execution, dict):
            provider = _str_value(execution.get("provider"))
            model_id = _str_value(execution.get("model_id"))
            backend = _str_value(execution.get("backend"))
            if backend == "remote_model_service":
                adapter_mode_default = "remote"

        capabilities = item.get("capabilities")
        capability_id: str | None = None
        if isinstance(capabilities, list) and capabilities:
            capability_id = _str_value(capabilities[0])

        io = item.get("io")
        io_type: str | None = None
        if isinstance(io, dict):
            io_type = _str_value(io.get("io_type_id"))

        catalog[tool_id] = {
            "tool_id": tool_id,
            "capability_id": capability_id,
            "io_type": io_type,
            "adapter_mode": adapter_mode_default,
            "tool_version": _str_value(item.get("version")),
            "source_link": _str_value(item.get("source_link")),
            "provider": provider,
            "model_id": model_id,
            "priority": _str_value(item.get("priority")) or "unknown",
        }

    return catalog


def _extract_tooling_fields(
    candidate: dict[str, Any],
    tool_catalog: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    metadata = candidate.get("metadata")
    metadata_dict = metadata if isinstance(metadata, dict) else {}

    tool_id = _str_value(candidate.get("tool_id")) or _str_value(metadata_dict.get("tool_id"))
    capability_id = _str_value(candidate.get("capability_id")) or _str_value(metadata_dict.get("capability_id"))
    io_type = _str_value(candidate.get("io_type")) or _str_value(metadata_dict.get("io_type"))
    adapter_mode = _str_value(candidate.get("adapter_mode")) or _str_value(metadata_dict.get("adapter_mode"))
    tool_version = _str_value(metadata_dict.get("tool_version"))
    source_link = _str_value(metadata_dict.get("source_link"))
    provider = _str_value(metadata_dict.get("provider"))
    model_id = _str_value(metadata_dict.get("model_id"))
    priority = _str_value(metadata_dict.get("priority"))

    tool_ref = tool_catalog.get(tool_id) if tool_id else None
    if tool_ref:
        capability_id = capability_id or tool_ref.get("capability_id")
        io_type = io_type or tool_ref.get("io_type")
        adapter_mode = adapter_mode or tool_ref.get("adapter_mode")
        tool_version = tool_version or tool_ref.get("tool_version")
        source_link = source_link or tool_ref.get("source_link")
        provider = provider or tool_ref.get("provider")
        model_id = model_id or tool_ref.get("model_id")
        priority = priority or tool_ref.get("priority")

    return {
        "tool_id": tool_id,
        "capability_id": capability_id,
        "io_type": io_type,
        "adapter_mode": adapter_mode or "unknown",
        "tool_version": tool_version,
        "source_link": source_link,
        "provider": provider,
        "model_id": model_id,
        "priority": priority or "unknown",
    }


def _collect_candidates(
    snapshots: list[tuple[int, dict[str, Any]]],
    tool_catalog: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    candidate_rows: list[dict[str, Any]] = []
    snapshot_ids: list[str] = []
    pending_action_ids: list[str] = []
    seen_candidates: set[tuple[str, str]] = set()

    for _, snap in snapshots:
        snapshot_id = _str_value(snap.get("snapshot_id"))
        if snapshot_id:
            snapshot_ids.append(snapshot_id)

        artifacts = snap.get("artifacts")
        if not isinstance(artifacts, dict):
            continue

        pending_action = artifacts.get("pending_action")
        if not isinstance(pending_action, dict):
            continue

        pending_action_id = _str_value(pending_action.get("pending_action_id"))
        if pending_action_id:
            pending_action_ids.append(pending_action_id)

        action_type = _str_value(pending_action.get("action_type"))
        candidates = pending_action.get("candidates")
        if not isinstance(candidates, list):
            continue

        for rank, raw_candidate in enumerate(candidates, start=1):
            if not isinstance(raw_candidate, dict):
                continue
            candidate_id = _str_value(raw_candidate.get("candidate_id"))
            if not candidate_id:
                continue

            dedupe_key = (pending_action_id or "", candidate_id)
            if dedupe_key in seen_candidates:
                continue
            seen_candidates.add(dedupe_key)

            tooling = _extract_tooling_fields(raw_candidate, tool_catalog)
            candidate_rows.append(
                {
                    "pending_action_id": pending_action_id,
                    "action_type": action_type,
                    "candidate_id": candidate_id,
                    "rank": rank,
                    "score_breakdown": raw_candidate.get("score_breakdown") or {},
                    "risk_level": raw_candidate.get("risk_level"),
                    "cost_estimate": raw_candidate.get("cost_estimate"),
                    "explanation": raw_candidate.get("explanation"),
                    "summary": raw_candidate.get("summary"),
                    "payload": raw_candidate.get("structured_payload") or raw_candidate.get("payload"),
                    **tooling,
                }
            )

    candidate_rows.sort(key=lambda item: (
        item.get("pending_action_id") or "",
        str(item.get("rank") or 0),
        item.get("candidate_id") or "",
    ))
    snapshot_ids = sorted(set(snapshot_ids))
    pending_action_ids = sorted(set(pending_action_ids))
    return candidate_rows, snapshot_ids, pending_action_ids


def _collect_events(task_id: str, log_rows: list[tuple[int, dict[str, Any]]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line_no, payload in log_rows:
        event_type = _to_event_type(payload)
        if not event_type:
            continue

        event_id = _str_value(payload.get("id")) or f"{task_id}:{line_no}"
        data = payload.get("data")
        data_dict = data if isinstance(data, dict) else {}

        events.append(
            {
                "line_no": line_no,
                "event_id": event_id,
                "event_type": event_type,
                "task_id": _str_value(payload.get("task_id")) or task_id,
                "ts": _str_value(payload.get("ts")) or _str_value(payload.get("timestamp")),
                "pending_action_id": _str_value(payload.get("pending_action_id")),
                "decision_id": _str_value(payload.get("decision_id")),
                "choice": _str_value(payload.get("choice")) or _str_value(data_dict.get("choice")),
                "selected_candidate_id": _str_value(payload.get("selected_candidate_id"))
                or _str_value(data_dict.get("selected_candidate_id")),
                "action_type": _str_value(payload.get("action_type"))
                or _str_value(data_dict.get("action_type")),
                "from_status": _str_value(payload.get("from_status")) or _str_value(payload.get("prev_status")),
                "to_status": _str_value(payload.get("to_status")) or _str_value(payload.get("new_status")),
                "state": _str_value(payload.get("state")) or _str_value(payload.get("external_status")),
                "tool": _str_value(payload.get("tool")),
                "step_id": _str_value(payload.get("step_id")),
                "status": _str_value(payload.get("status")),
                "failure_type": _str_value(payload.get("failure_type")) or _str_value(data_dict.get("failure_type")),
                "error_message": _str_value(payload.get("error_message")),
            }
        )

    events.sort(key=lambda item: item["line_no"])
    return events


def _derive_status_path(events: list[dict[str, Any]]) -> list[str]:
    path: list[str] = []
    for event in events:
        if event["event_type"] != "STATE_TRANSITION":
            continue
        to_status = event.get("to_status") or event.get("state")
        if to_status:
            path.append(to_status)
    return path


def _derive_final_status(events: list[dict[str, Any]]) -> str:
    status_path = _derive_status_path(events)
    if status_path:
        return status_path[-1]

    for event in reversed(events):
        state = event.get("state")
        if state:
            return state
        to_status = event.get("to_status")
        if to_status:
            return to_status
    return "UNKNOWN"


def _collect_step_results(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for event in events:
        if event["event_type"] not in {"STEP_FINISHED", "STEP_FAILED"}:
            continue
        rows.append(
            {
                "event_id": event["event_id"],
                "step_id": event.get("step_id"),
                "tool": event.get("tool"),
                "status": event.get("status") or (
                    "failed" if event["event_type"] == "STEP_FAILED" else "success"
                ),
                "failure_type": event.get("failure_type"),
                "error_message": event.get("error_message"),
                "ts": event.get("ts"),
            }
        )
    return rows


def _collect_decisions(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for event in events:
        if event["event_type"] not in {"DECISION_SUBMITTED", "DECISION_APPLIED"}:
            continue
        rows.append(
            {
                "event_id": event["event_id"],
                "event_type": event["event_type"],
                "decision_id": event.get("decision_id"),
                "pending_action_id": event.get("pending_action_id"),
                "choice": event.get("choice"),
                "selected_candidate_id": event.get("selected_candidate_id"),
                "action_type": event.get("action_type"),
                "ts": event.get("ts"),
            }
        )
    return rows


def _select_final_decision(decisions: list[dict[str, Any]]) -> dict[str, Any] | None:
    for decision in reversed(decisions):
        if decision["event_type"] == "DECISION_APPLIED":
            return decision
    return decisions[-1] if decisions else None


def _load_report(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def _find_metric_paths(metrics_dir: Path, task_id: str) -> list[str]:
    paths = sorted(metrics_dir.glob(f"{task_id}_*_metrics.json"))
    return [str(path) for path in paths]


def _build_sample(
    *,
    task_id: str,
    log_path: Path,
    snapshot_path: Path,
    report_path: Path,
    metrics_dir: Path,
    tool_catalog: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    log_rows = _read_jsonl(log_path)
    snapshot_rows = _read_jsonl(snapshot_path)
    events = _collect_events(task_id=task_id, log_rows=log_rows)
    decisions = _collect_decisions(events)
    selected = _select_final_decision(decisions)
    candidates, snapshot_ids, pending_action_ids = _collect_candidates(
        snapshots=snapshot_rows,
        tool_catalog=tool_catalog,
    )

    report = _load_report(report_path)
    step_results = _collect_step_results(events)
    status_path = _derive_status_path(events)
    final_status = _derive_final_status(events)

    first_ts = next((item.get("ts") for item in events if item.get("ts")), None)
    last_ts = next((item.get("ts") for item in reversed(events) if item.get("ts")), None)

    event_ids = [item["event_id"] for item in events]
    decision_event_ids = [item["event_id"] for item in decisions]
    step_failure_types = sorted({
        item["failure_type"]
        for item in step_results
        if isinstance(item.get("failure_type"), str) and item.get("failure_type")
    })

    selected_candidate = None
    selected_candidate_id = selected.get("selected_candidate_id") if selected else None
    if selected_candidate_id:
        selected_candidate = next(
            (item for item in candidates if item.get("candidate_id") == selected_candidate_id),
            None,
        )

    report_metadata = report.get("metadata")
    report_metadata_dict = report_metadata if isinstance(report_metadata, dict) else {}

    sample = {
        "sample_id": f"sample::{task_id}",
        "context": {
            "task_id": task_id,
            "status_path": status_path,
            "start_status": status_path[0] if status_path else None,
            "end_status": status_path[-1] if status_path else final_status,
            "has_hitl": bool(pending_action_ids),
            "time_window": {
                "first_ts": first_ts,
                "last_ts": last_ts,
            },
            "report_created_at": report_metadata_dict.get("created_at"),
            "plan_metadata": report_metadata_dict.get("plan_metadata"),
        },
        "candidates": candidates,
        "selected": {
            "decision_id": selected.get("decision_id") if selected else None,
            "pending_action_id": selected.get("pending_action_id") if selected else None,
            "choice": selected.get("choice") if selected else None,
            "selected_candidate_id": selected_candidate_id,
            "selected_candidate": selected_candidate,
            "action_type": selected.get("action_type") if selected else None,
            "event_id": selected.get("event_id") if selected else None,
            "ts": selected.get("ts") if selected else None,
        },
        "outcome": {
            "final_status": final_status,
            "result": (
                "success"
                if final_status == "DONE"
                else "failed"
                if final_status == "FAILED"
                else "cancelled"
                if final_status == "CANCELLED"
                else "unknown"
            ),
            "step_results": step_results,
            "step_failure_types": step_failure_types,
            "report_path": str(report_path) if report_path.exists() else None,
            "metrics_paths": _find_metric_paths(metrics_dir, task_id),
            "structure_pdb_path": report.get("structure_pdb_path"),
            "scores": report.get("scores") if isinstance(report.get("scores"), dict) else {},
        },
        "audit_trace": {
            "task_id": task_id,
            "event_log_path": str(log_path),
            "snapshot_path": str(snapshot_path) if snapshot_path.exists() else None,
            "event_ids": event_ids,
            "decision_event_ids": decision_event_ids,
            "pending_action_ids": pending_action_ids,
            "snapshot_ids": snapshot_ids,
            "decision_history": decisions,
        },
    }

    mapping_rows = [
        {
            "sample_id": sample["sample_id"],
            "task_id": task_id,
            "event_id": event["event_id"],
            "line_no": event["line_no"],
            "event_type": event["event_type"],
            "ts": event.get("ts"),
            "pending_action_id": event.get("pending_action_id"),
            "decision_id": event.get("decision_id"),
            "step_id": event.get("step_id"),
            "tool": event.get("tool"),
        }
        for event in events
    ]

    return sample, mapping_rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(_json_dump(row) + "\n")


def extract_training_samples(
    *,
    logs_dir: Path,
    snapshots_dir: Path,
    reports_dir: Path,
    metrics_dir: Path,
    tool_kg_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    if not logs_dir.exists():
        raise FileNotFoundError(f"logs dir not found: {logs_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    tool_catalog = _load_tool_catalog(tool_kg_path)

    samples: list[dict[str, Any]] = []
    mapping_rows: list[dict[str, Any]] = []

    log_files = sorted(logs_dir.glob("*.jsonl"))
    for log_path in log_files:
        task_id = log_path.stem
        snapshot_path = snapshots_dir / f"{task_id}.jsonl"
        report_path = reports_dir / f"{task_id}.json"

        sample, sample_mapping = _build_sample(
            task_id=task_id,
            log_path=log_path,
            snapshot_path=snapshot_path,
            report_path=report_path,
            metrics_dir=metrics_dir,
            tool_catalog=tool_catalog,
        )
        samples.append(sample)
        mapping_rows.extend(sample_mapping)

    samples.sort(key=lambda item: item["sample_id"])
    mapping_rows.sort(key=lambda item: (item["task_id"], item["line_no"], item["event_id"]))

    samples_path = output_dir / "samples.jsonl"
    mapping_path = output_dir / "sample_event_mapping.jsonl"
    stats_path = output_dir / "stats.json"

    _write_jsonl(samples_path, samples)
    _write_jsonl(mapping_path, mapping_rows)

    final_status_counter = Counter(sample["outcome"]["final_status"] for sample in samples)
    step_status_counter = Counter(
        step.get("status")
        for sample in samples
        for step in sample["outcome"]["step_results"]
        if step.get("status")
    )
    decision_choice_counter = Counter(
        history.get("choice")
        for sample in samples
        for history in sample["audit_trace"]["decision_history"]
        if history.get("choice")
    )

    tool_by_id = Counter(
        candidate.get("tool_id") or "unknown"
        for sample in samples
        for candidate in sample["candidates"]
    )
    tool_by_capability = Counter(
        candidate.get("capability_id") or "unknown"
        for sample in samples
        for candidate in sample["candidates"]
    )
    tool_by_adapter = Counter(
        candidate.get("adapter_mode") or "unknown"
        for sample in samples
        for candidate in sample["candidates"]
    )
    tool_by_priority = Counter(
        candidate.get("priority") or "unknown"
        for sample in samples
        for candidate in sample["candidates"]
    )

    samples_with_hitl = sum(1 for sample in samples if sample["context"]["has_hitl"])
    samples_with_events = sum(
        1 for sample in samples if len(sample["audit_trace"]["event_ids"]) > 0
    )

    stats = {
        "input": {
            "logs_dir": str(logs_dir),
            "snapshots_dir": str(snapshots_dir),
            "reports_dir": str(reports_dir),
            "metrics_dir": str(metrics_dir),
            "tool_kg_path": str(tool_kg_path),
            "log_file_count": len(log_files),
        },
        "output": {
            "samples_path": str(samples_path),
            "mapping_path": str(mapping_path),
            "stats_path": str(stats_path),
        },
        "counts": {
            "total_samples": len(samples),
            "total_mapping_rows": len(mapping_rows),
            "samples_with_hitl": samples_with_hitl,
            "hitl_ratio": round(samples_with_hitl / len(samples), 6) if samples else 0.0,
        },
        "status_distribution": dict(sorted(final_status_counter.items())),
        "step_status_distribution": dict(sorted(step_status_counter.items())),
        "decision_choice_distribution": dict(sorted(decision_choice_counter.items())),
        "tool_distribution": {
            "by_tool_id": dict(sorted(tool_by_id.items())),
            "by_capability_id": dict(sorted(tool_by_capability.items())),
            "by_adapter_mode": dict(sorted(tool_by_adapter.items())),
            "by_priority": dict(sorted(tool_by_priority.items())),
        },
        "traceability": {
            "samples_with_task_id": sum(1 for sample in samples if sample["context"]["task_id"]),
            "samples_with_event_ids": samples_with_events,
            "mapping_rows_with_event_id": sum(1 for row in mapping_rows if row.get("event_id")),
        },
    }

    with stats_path.open("w", encoding="utf-8") as handle:
        handle.write(_json_dump(stats) + "\n")

    return stats


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract reproducible training samples from task logs/snapshots.",
    )
    parser.add_argument("--logs-dir", type=Path, default=Path("data/logs"))
    parser.add_argument("--snapshots-dir", type=Path, default=Path("data/snapshots"))
    parser.add_argument("--reports-dir", type=Path, default=Path("output/reports"))
    parser.add_argument("--metrics-dir", type=Path, default=Path("output/metrics"))
    parser.add_argument("--tool-kg-path", type=Path, default=Path("src/kg/protein_tool_kg.json"))
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/training/w11-data-1"),
        help="Directory for samples.jsonl, sample_event_mapping.jsonl, stats.json",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    stats = extract_training_samples(
        logs_dir=args.logs_dir,
        snapshots_dir=args.snapshots_dir,
        reports_dir=args.reports_dir,
        metrics_dir=args.metrics_dir,
        tool_kg_path=args.tool_kg_path,
        output_dir=args.output_dir,
    )

    print("Extraction completed")
    print(_json_dump(stats["counts"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
