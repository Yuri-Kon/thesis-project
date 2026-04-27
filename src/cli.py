from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any

import httpx

DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"


def main(argv: list[str] | None = None) -> int:
    """运行 design CLI 入口。"""
    parser = _build_parser()
    args = parser.parse_args(argv)
    base_url = str(args.api_base_url or os.getenv("DESIGN_API_BASE_URL") or DEFAULT_API_BASE_URL).rstrip("/")

    try:
        if args.command == "task" and args.task_command == "show":
            return _task_show(base_url, args.task_id, emit_json=args.json)
        if args.command == "task" and args.task_command == "watch":
            return _task_watch(
                base_url,
                args.task_id,
                emit_json=args.json,
                interval_s=args.interval,
            )
        if args.command == "pending" and args.pending_command == "show":
            return _pending_show(base_url, args.pending_action_id, emit_json=args.json)
        if args.command == "report" and args.report_command == "show":
            return _report_show(base_url, args.task_id, emit_json=args.json)
    except httpx.HTTPError as exc:
        print(f"API request failed: {exc}", file=sys.stderr)
        return 2

    parser.print_help()
    return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="design")
    parser.add_argument(
        "--api-base-url",
        default=None,
        help="API base URL; defaults to DESIGN_API_BASE_URL or http://127.0.0.1:8000",
    )
    subparsers = parser.add_subparsers(dest="command")

    task_parser = subparsers.add_parser("task")
    task_subparsers = task_parser.add_subparsers(dest="task_command")
    task_show = task_subparsers.add_parser("show")
    task_show.add_argument("task_id")
    task_show.add_argument("--json", action="store_true")
    task_watch = task_subparsers.add_parser("watch")
    task_watch.add_argument("task_id")
    task_watch.add_argument("--json", action="store_true")
    task_watch.add_argument("--interval", type=float, default=5.0)

    pending_parser = subparsers.add_parser("pending")
    pending_subparsers = pending_parser.add_subparsers(dest="pending_command")
    pending_show = pending_subparsers.add_parser("show")
    pending_show.add_argument("pending_action_id")
    pending_show.add_argument("--json", action="store_true")

    report_parser = subparsers.add_parser("report")
    report_subparsers = report_parser.add_subparsers(dest="report_command")
    report_show = report_subparsers.add_parser("show")
    report_show.add_argument("task_id")
    report_show.add_argument("--json", action="store_true")
    return parser


def _task_show(base_url: str, task_id: str, *, emit_json: bool) -> int:
    task = _get_json(base_url, f"/tasks/{task_id}")
    readiness = _get_json(base_url, "/capabilities/readiness")
    payload = {
        "task": task,
        "readiness_summary": _readiness_summary(readiness),
    }
    if emit_json:
        _print_json(payload)
    else:
        _print_task(payload)
    return 0


def _task_watch(
    base_url: str,
    task_id: str,
    *,
    emit_json: bool,
    interval_s: float,
) -> int:
    while True:
        code = _task_show(base_url, task_id, emit_json=emit_json)
        task = _get_json(base_url, f"/tasks/{task_id}")
        if str(task.get("status")) in {"DONE", "FAILED", "CANCELLED"}:
            return code
        time.sleep(max(1.0, interval_s))


def _pending_show(base_url: str, pending_action_id: str, *, emit_json: bool) -> int:
    pending = _get_json(base_url, f"/pending-actions/{pending_action_id}")
    readiness = _get_json(base_url, "/capabilities/readiness")
    payload = {
        "pending_action": pending,
        "readiness_summary": _readiness_summary(readiness),
    }
    if emit_json:
        _print_json(payload)
    else:
        _print_pending(payload)
    return 0


def _report_show(base_url: str, task_id: str, *, emit_json: bool) -> int:
    report = _get_json(base_url, f"/tasks/{task_id}/report")
    if emit_json:
        _print_json({"report": report})
    else:
        _print_report(report)
    return 0


def _get_json(base_url: str, path: str) -> dict[str, Any] | list[dict[str, Any]]:
    response = httpx.get(f"{base_url}{path}", timeout=10.0)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, (dict, list)):
        raise ValueError(f"API payload for {path} is not an object or list")
    return payload


def _readiness_summary(readiness: dict[str, Any] | list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(readiness, list):
        return []
    return [
        {
            "capability_id": item.get("capability_id"),
            "status": item.get("status"),
            "reason": item.get("reason"),
            "degraded_reasons": item.get("degraded_reasons") or [],
            "suggested_recovery": item.get("suggested_recovery"),
        }
        for item in readiness
        if isinstance(item, dict)
    ]


def _print_task(payload: dict[str, Any]) -> None:
    task = payload["task"]
    print(f"task_id: {task.get('id')}")
    print(f"status: {task.get('status')} / {task.get('internal_status') or '-'}")
    print(f"goal: {task.get('goal')}")
    pending = task.get("pending_action")
    if isinstance(pending, dict):
        print(f"pending_action: {pending.get('pending_action_id')} ({pending.get('action_type')})")
    _print_readiness_summary(payload["readiness_summary"])


def _print_pending(payload: dict[str, Any]) -> None:
    pending = payload["pending_action"]
    print(f"pending_action_id: {pending.get('pending_action_id')}")
    print(f"task_id: {pending.get('task_id')}")
    print(f"action_type: {pending.get('action_type')}")
    print(f"default_suggestion: {pending.get('default_suggestion') or '-'}")
    for candidate in pending.get("candidates") or []:
        if not isinstance(candidate, dict):
            continue
        tool = candidate.get("tool") if isinstance(candidate.get("tool"), dict) else {}
        print(
            "candidate: "
            f"{candidate.get('candidate_id')} "
            f"readiness={tool.get('readiness_status') or '-'} "
            f"recovery={tool.get('suggested_recovery') or '-'}"
        )
    _print_readiness_summary(payload["readiness_summary"])


def _print_report(report: dict[str, Any] | list[dict[str, Any]]) -> None:
    if not isinstance(report, dict):
        print("report: unavailable")
        return
    print(f"task_id: {report.get('task_id')}")
    print(f"report_path: {report.get('report_path') or '-'}")
    scores = report.get("scores") if isinstance(report.get("scores"), dict) else {}
    print(f"objective_score: {scores.get('objective_score', '-')}")
    objective = (
        report.get("objective_scoring")
        if isinstance(report.get("objective_scoring"), dict)
        else {}
    )
    print(f"rank_reason: {objective.get('rank_reason') or '-'}")
    warnings = objective.get("warnings") if isinstance(objective.get("warnings"), list) else []
    print(f"warnings: {len(warnings)}")
    for row in objective.get("top_k") or []:
        if not isinstance(row, dict):
            continue
        print(
            "candidate: "
            f"{row.get('candidate_id') or row.get('id')} "
            f"rank={row.get('top_k_rank') or '-'} "
            f"score={row.get('objective_score', '-')}"
        )


def _print_readiness_summary(items: list[dict[str, Any]]) -> None:
    print("capability_readiness:")
    for item in items:
        print(
            "  "
            f"{item.get('capability_id')}: {item.get('status')} "
            f"reason={item.get('reason') or '-'} "
            f"recovery={item.get('suggested_recovery') or '-'}"
        )


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
