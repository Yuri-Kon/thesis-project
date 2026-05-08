#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import platform
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.storage.log_store import read_timeline_events

DEFAULT_RUN_LOG_INDEX = Path(
    "output/experiment/w12-expr-2/issue171-remote-batch3-r3/run_log_index.csv"
)
DEFAULT_VERTICAL_SUMMARY = Path(
    "output/experiment/w12-expr-2/issue171-remote-batch3-r3/vertical_metrics_summary.csv"
)
DEFAULT_REPLAY_SAMPLE_LOG = Path(
    "output/demo/w12-issue-151/logs/int_s6_patch_decision_replay_done.jsonl"
)
DEFAULT_OUTPUT_DIR = Path("output/experiment/w12-expr-2/issue173-governance-review")


@dataclass(frozen=True)
class TaskGovernance:
    task_id: str
    group_id: str
    waiting_chains_expected: int
    waiting_chains_complete: int
    replay_success_count: int
    failed_events: int
    traceable_failed_events: int
    snapshot_exists: bool
    log_exists: bool


@dataclass(frozen=True)
class GroupGovernance:
    group_id: str
    tasks: int
    waiting_chains_expected: int
    waiting_chains_complete: int
    replay_success_count: int
    failed_events: int
    traceable_failed_events: int
    snapshots_present: int
    logs_present: int


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _json_dump(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in fieldnames})


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_json_dump(payload) + "\n", encoding="utf-8")


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None
    return None


def _git_short_sha() -> str:
    try:
        return (
            subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True)
            .strip()
            .lower()
        )
    except Exception:
        return "nogit"


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 1.0
    return numerator / denominator


def _resolve_log_path(task_id: str, raw: str | None) -> Path:
    if raw:
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = REPO_ROOT / candidate
        return candidate
    return REPO_ROOT / "data" / "logs" / f"{task_id}.jsonl"


def _extract_failure_code(event: dict[str, Any]) -> str | None:
    code = event.get("failure_code")
    if isinstance(code, str) and code:
        return code
    data = event.get("data")
    if isinstance(data, dict):
        for key in ("failure_code",):
            value = data.get(key)
            if isinstance(value, str) and value:
                return value
        s6 = data.get("s6")
        if isinstance(s6, dict):
            value = s6.get("trigger_failure_code")
            if isinstance(value, str) and value:
                return value
    return None


def evaluate_task_governance(
    *,
    task_id: str,
    group_id: str,
    log_path: Path,
    snapshot_path: Path | None,
) -> TaskGovernance:
    log_exists = log_path.exists()
    if not log_exists:
        return TaskGovernance(
            task_id=task_id,
            group_id=group_id,
            waiting_chains_expected=0,
            waiting_chains_complete=0,
            replay_success_count=0,
            failed_events=0,
            traceable_failed_events=0,
            snapshot_exists=snapshot_path.exists() if snapshot_path else False,
            log_exists=False,
        )

    events = read_timeline_events(task_id, log_dir=log_path.parent)
    by_pending_action: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        pending_action_id = event.get("pending_action_id")
        if isinstance(pending_action_id, str) and pending_action_id:
            by_pending_action[pending_action_id].append(event)

    waiting_expected = 0
    waiting_complete = 0
    replay_success = 0
    for pending_action_id, chain in by_pending_action.items():
        chain_sorted = sorted(chain, key=lambda item: int(item.get("seq", 0)))
        enter = [item for item in chain_sorted if item.get("event_type") == "WAITING_ENTER"]
        if not enter:
            continue
        waiting_expected += len(enter)
        decision = [item for item in chain_sorted if item.get("event_type") == "DECISION_APPLIED"]
        exit_events = [item for item in chain_sorted if item.get("event_type") == "WAITING_EXIT"]
        if not decision or not exit_events:
            continue
        first_enter = enter[0]
        first_decision = decision[0]
        first_exit = exit_events[0]
        if int(first_enter.get("seq", 0)) < int(first_decision.get("seq", 0)) < int(first_exit.get("seq", 0)):
            waiting_complete += 1
            replay_success += 1

    failed_events = 0
    traceable_failed = 0
    for event in events:
        if event.get("event_type") != "STEP_FAILED":
            continue
        failed_events += 1
        has_step = isinstance(event.get("step_id"), str) and bool(event.get("step_id"))
        tool_value = event.get("tool_id") or event.get("tool")
        has_tool = isinstance(tool_value, str) and bool(tool_value)
        has_code = _extract_failure_code(event) is not None
        if has_step and has_tool and has_code:
            traceable_failed += 1

    return TaskGovernance(
        task_id=task_id,
        group_id=group_id,
        waiting_chains_expected=waiting_expected,
        waiting_chains_complete=waiting_complete,
        replay_success_count=replay_success,
        failed_events=failed_events,
        traceable_failed_events=traceable_failed,
        snapshot_exists=snapshot_path.exists() if snapshot_path else False,
        log_exists=True,
    )


def aggregate_by_group(items: list[TaskGovernance]) -> list[GroupGovernance]:
    groups: dict[str, GroupGovernance] = {}
    grouped_items: dict[str, list[TaskGovernance]] = defaultdict(list)
    for item in items:
        grouped_items[item.group_id].append(item)

    for group_id, rows in grouped_items.items():
        groups[group_id] = GroupGovernance(
            group_id=group_id,
            tasks=len(rows),
            waiting_chains_expected=sum(item.waiting_chains_expected for item in rows),
            waiting_chains_complete=sum(item.waiting_chains_complete for item in rows),
            replay_success_count=sum(item.replay_success_count for item in rows),
            failed_events=sum(item.failed_events for item in rows),
            traceable_failed_events=sum(item.traceable_failed_events for item in rows),
            snapshots_present=sum(1 for item in rows if item.snapshot_exists),
            logs_present=sum(1 for item in rows if item.log_exists),
        )
    return sorted(groups.values(), key=lambda row: row.group_id)


def render_report_markdown(
    *,
    generated_at: str,
    run_log_index: Path,
    output_dir: Path,
    global_row: GroupGovernance,
    group_rows: list[GroupGovernance],
    vertical_rows: list[dict[str, str]],
    replay_sample_log: Path,
) -> str:
    lines = [
        "# governance-review",
        "",
        "## Inputs",
        f"- run_log_index: `{run_log_index}`",
        f"- replay_sample_log: `{replay_sample_log}`",
        f"- generated_at: `{generated_at}`",
        "",
        "## Repro Command",
        f"- `python scripts/evaluate_governance_review.py --run-log-index {run_log_index} --output-dir {output_dir}`",
        "",
        "## Global Governance Metrics",
        "",
        f"- tasks: `{global_row.tasks}`",
        f"- logs_present_rate: `{_ratio(global_row.logs_present, global_row.tasks):.6f}`",
        f"- snapshot_linked_rate: `{_ratio(global_row.snapshots_present, global_row.tasks):.6f}`",
        f"- waiting_chain_complete_rate: `{_ratio(global_row.waiting_chains_complete, global_row.waiting_chains_expected):.6f}`",
        f"- replay_success_rate: `{_ratio(global_row.replay_success_count, global_row.waiting_chains_expected):.6f}`",
        f"- failure_traceable_rate: `{_ratio(global_row.traceable_failed_events, global_row.failed_events):.6f}`",
        "",
        "## Group Metrics",
        "",
        "| group_id | tasks | waiting_chain_complete_rate | replay_success_rate | failure_traceable_rate | snapshot_linked_rate |",
        "|---|---:|---:|---:|---:|---:|",
    ]

    for row in group_rows:
        lines.append(
            "| {group_id} | {tasks} | {chain:.6f} | {replay:.6f} | {trace:.6f} | {snap:.6f} |".format(
                group_id=row.group_id,
                tasks=row.tasks,
                chain=_ratio(row.waiting_chains_complete, row.waiting_chains_expected),
                replay=_ratio(row.replay_success_count, row.waiting_chains_expected),
                trace=_ratio(row.traceable_failed_events, row.failed_events),
                snap=_ratio(row.snapshots_present, row.tasks),
            )
        )

    lines.extend([
        "",
        "## Vertical Merge (Existing vs Recomputed)",
        "",
        "| group_id | existing_waiting_chain_complete_rate | existing_failure_traceable_rate | recomputed_waiting_chain_complete_rate | recomputed_failure_traceable_rate |",
        "|---|---:|---:|---:|---:|",
    ])

    group_map = {row.group_id: row for row in group_rows}
    for row in vertical_rows:
        group_id = row.get("group_id", "")
        if group_id not in group_map:
            continue
        group_metric = group_map[group_id]
        lines.append(
            "| {group_id} | {old_chain} | {old_trace} | {new_chain:.6f} | {new_trace:.6f} |".format(
                group_id=group_id,
                old_chain=row.get("waiting_chain_complete_rate", ""),
                old_trace=row.get("failure_traceable_rate", ""),
                new_chain=_ratio(group_metric.waiting_chains_complete, group_metric.waiting_chains_expected),
                new_trace=_ratio(group_metric.traceable_failed_events, group_metric.failed_events),
            )
        )

    lines.extend([
        "",
        "## Governance Notes",
        "",
        "- waiting_chain_complete_rate/replay_success_rate are computed from ordered `WAITING_ENTER -> DECISION_APPLIED -> WAITING_EXIT` chains by `pending_action_id`.",
        "- failure_traceable_rate requires `STEP_FAILED` rows to include `step_id`, `tool/tool_id`, and `failure_code`.",
        "- snapshot_linked_rate checks whether `snapshot_path` from run index exists on disk.",
        "",
        "## Anomaly Hints",
        "",
        "- If waiting_chain_complete_rate is low: inspect missing Decision/WAITING_EXIT events.",
        "- If failure_traceable_rate is low: inspect missing `failure_code` and tool metadata in step failure payload.",
    ])

    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate governance metrics.")
    parser.add_argument("--run-log-index", type=Path, default=DEFAULT_RUN_LOG_INDEX)
    parser.add_argument("--vertical-summary", type=Path, default=DEFAULT_VERTICAL_SUMMARY)
    parser.add_argument("--replay-sample-log", type=Path, default=DEFAULT_REPLAY_SAMPLE_LOG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = _read_csv(args.run_log_index)

    task_metrics: list[TaskGovernance] = []
    for row in rows:
        task_id = (row.get("task_id") or "").strip()
        if not task_id:
            continue
        group_id = (row.get("group_id") or "unknown").strip() or "unknown"
        log_path = _resolve_log_path(task_id, row.get("event_log_path"))
        raw_snapshot = (row.get("snapshot_path") or "").strip()
        snapshot_path = None
        if raw_snapshot:
            snapshot_path = Path(raw_snapshot)
            if not snapshot_path.is_absolute():
                snapshot_path = REPO_ROOT / snapshot_path

        task_metrics.append(
            evaluate_task_governance(
                task_id=task_id,
                group_id=group_id,
                log_path=log_path,
                snapshot_path=snapshot_path,
            )
        )

    group_rows = aggregate_by_group(task_metrics)
    global_row = GroupGovernance(
        group_id="ALL",
        tasks=len(task_metrics),
        waiting_chains_expected=sum(item.waiting_chains_expected for item in task_metrics),
        waiting_chains_complete=sum(item.waiting_chains_complete for item in task_metrics),
        replay_success_count=sum(item.replay_success_count for item in task_metrics),
        failed_events=sum(item.failed_events for item in task_metrics),
        traceable_failed_events=sum(item.traceable_failed_events for item in task_metrics),
        snapshots_present=sum(1 for item in task_metrics if item.snapshot_exists),
        logs_present=sum(1 for item in task_metrics if item.log_exists),
    )

    generated_at = _now_iso()
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    summary_payload = {
        "generated_at": generated_at,
        "run_log_index": str(args.run_log_index),
        "vertical_summary": str(args.vertical_summary),
        "replay_sample_log": str(args.replay_sample_log),
        "git_sha": _git_short_sha(),
        "python": platform.python_version(),
        "global": {
            "tasks": global_row.tasks,
            "logs_present_rate": _ratio(global_row.logs_present, global_row.tasks),
            "snapshot_linked_rate": _ratio(global_row.snapshots_present, global_row.tasks),
            "waiting_chain_complete_rate": _ratio(
                global_row.waiting_chains_complete,
                global_row.waiting_chains_expected,
            ),
            "replay_success_rate": _ratio(
                global_row.replay_success_count,
                global_row.waiting_chains_expected,
            ),
            "failure_traceable_rate": _ratio(
                global_row.traceable_failed_events,
                global_row.failed_events,
            ),
        },
    }
    _write_json(output_dir / "governance_metrics_summary.json", summary_payload)

    group_csv_rows: list[dict[str, Any]] = []
    for row in group_rows:
        group_csv_rows.append(
            {
                "group_id": row.group_id,
                "tasks": row.tasks,
                "logs_present_rate": _ratio(row.logs_present, row.tasks),
                "snapshot_linked_rate": _ratio(row.snapshots_present, row.tasks),
                "waiting_chain_complete_rate": _ratio(
                    row.waiting_chains_complete,
                    row.waiting_chains_expected,
                ),
                "replay_success_rate": _ratio(
                    row.replay_success_count,
                    row.waiting_chains_expected,
                ),
                "failure_traceable_rate": _ratio(
                    row.traceable_failed_events,
                    row.failed_events,
                ),
            }
        )

    _write_csv(
        output_dir / "governance_metrics_by_group.csv",
        group_csv_rows,
        fieldnames=[
            "group_id",
            "tasks",
            "logs_present_rate",
            "snapshot_linked_rate",
            "waiting_chain_complete_rate",
            "replay_success_rate",
            "failure_traceable_rate",
        ],
    )

    vertical_rows = _read_csv(args.vertical_summary)
    compare_rows: list[dict[str, Any]] = []
    group_map = {row.group_id: row for row in group_rows}
    for row in vertical_rows:
        group_id = (row.get("group_id") or "").strip()
        if group_id not in group_map:
            continue
        current = group_map[group_id]
        compare_rows.append(
            {
                "group_id": group_id,
                "existing_waiting_chain_complete_rate": _safe_float(row.get("waiting_chain_complete_rate")),
                "existing_failure_traceable_rate": _safe_float(row.get("failure_traceable_rate")),
                "recomputed_waiting_chain_complete_rate": _ratio(
                    current.waiting_chains_complete,
                    current.waiting_chains_expected,
                ),
                "recomputed_failure_traceable_rate": _ratio(
                    current.traceable_failed_events,
                    current.failed_events,
                ),
            }
        )

    _write_csv(
        output_dir / "governance_vs_vertical_comparison.csv",
        compare_rows,
        fieldnames=[
            "group_id",
            "existing_waiting_chain_complete_rate",
            "existing_failure_traceable_rate",
            "recomputed_waiting_chain_complete_rate",
            "recomputed_failure_traceable_rate",
        ],
    )

    replay_sample_path = args.replay_sample_log
    if not replay_sample_path.is_absolute():
        replay_sample_path = REPO_ROOT / replay_sample_path
    sample_task_id = replay_sample_path.stem
    sample_events = read_timeline_events(sample_task_id, log_dir=replay_sample_path.parent)
    sample_lines = [
        "# Governance Replay Sample",
        "",
        f"- task_id: `{sample_task_id}`",
        f"- source_log: `{replay_sample_path}`",
        "",
        "## Event Trace",
        "",
    ]
    for index, event in enumerate(sample_events, start=1):
        sample_lines.append(
            f"{index}. `{event.get('event_type')}` | pending_action_id={event.get('pending_action_id')} | decision_id={event.get('decision_id')}"
        )
    (output_dir / "governance_replay_sample.md").write_text("\n".join(sample_lines) + "\n", encoding="utf-8")

    report = render_report_markdown(
        generated_at=generated_at,
        run_log_index=args.run_log_index,
        output_dir=output_dir,
        global_row=global_row,
        group_rows=group_rows,
        vertical_rows=vertical_rows,
        replay_sample_log=replay_sample_path,
    )
    (output_dir / "governance-report.md").write_text(report, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
