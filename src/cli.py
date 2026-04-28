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
        if args.command == "timeline" and args.timeline_command == "show":
            return _timeline_show(base_url, args.task_id, emit_json=args.json)
        if args.command == "report" and args.report_command == "show":
            return _report_show(base_url, args.task_id, emit_json=args.json)
        if args.command == "intake" and args.intake_command == "schema":
            return _intake_schema(base_url, emit_json=args.json)
        if args.command == "intake" and args.intake_command == "create":
            return _intake_create(
                base_url,
                text=args.text,
                fields=_parse_field_args(args.field),
                source=args.source,
                emit_json=args.json,
            )
        if args.command == "intake" and args.intake_command == "patch":
            return _intake_patch(
                base_url,
                intake_id=args.intake_id,
                fields=_parse_field_args(args.field),
                updated_by=args.updated_by,
                emit_json=args.json,
            )
        if args.command == "intake" and args.intake_command == "confirm":
            return _intake_confirm(
                base_url,
                intake_id=args.intake_id,
                confirmed_by=args.confirmed_by,
                acknowledged_warnings=args.acknowledge,
                emit_json=args.json,
            )
        if args.command == "preflight":
            print(
                "preflight has moved to Task Intake; use `design intake ...`.",
                file=sys.stderr,
            )
            return 2
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
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

    timeline_parser = subparsers.add_parser("timeline")
    timeline_subparsers = timeline_parser.add_subparsers(dest="timeline_command")
    timeline_show = timeline_subparsers.add_parser("show")
    timeline_show.add_argument("task_id")
    timeline_show.add_argument("--json", action="store_true")

    report_parser = subparsers.add_parser("report")
    report_subparsers = report_parser.add_subparsers(dest="report_command")
    report_show = report_subparsers.add_parser("show")
    report_show.add_argument("task_id")
    report_show.add_argument("--json", action="store_true")

    intake_parser = subparsers.add_parser("intake")
    intake_subparsers = intake_parser.add_subparsers(dest="intake_command")
    intake_schema = intake_subparsers.add_parser("schema")
    intake_schema.add_argument("--json", action="store_true")
    intake_create = intake_subparsers.add_parser("create")
    intake_create.add_argument("--text", default=None)
    intake_create.add_argument(
        "--field",
        action="append",
        default=[],
        help="Structured field as key=JSON_VALUE, for example length_range='[100,140]'",
    )
    intake_create.add_argument(
        "--source",
        default="cli",
        choices=["web", "cli", "api", "script", "legacy"],
    )
    intake_create.add_argument("--json", action="store_true")
    intake_patch = intake_subparsers.add_parser("patch")
    intake_patch.add_argument("intake_id")
    intake_patch.add_argument("--field", action="append", default=[])
    intake_patch.add_argument("--updated-by", default="cli")
    intake_patch.add_argument("--json", action="store_true")
    intake_confirm = intake_subparsers.add_parser("confirm")
    intake_confirm.add_argument("intake_id")
    intake_confirm.add_argument("--confirmed-by", default="cli")
    intake_confirm.add_argument("--acknowledge", action="append", default=[])
    intake_confirm.add_argument(
        "--ack-warning",
        dest="acknowledge",
        action="append",
        help="Acknowledge a Safety warning code or exact warning message",
    )
    intake_confirm.add_argument("--json", action="store_true")

    subparsers.add_parser("preflight")
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
        if isinstance(task, dict) and str(task.get("status", "")).startswith("WAITING_"):
            pending = task.get("pending_action")
            if isinstance(pending, dict) and not emit_json:
                print("watch: waiting for human decision")
                print(
                    f"pending_action: {pending.get('pending_action_id')} "
                    f"({pending.get('action_type')})"
                )
            return code
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


def _timeline_show(base_url: str, task_id: str, *, emit_json: bool) -> int:
    timeline = _get_json(base_url, f"/tasks/{task_id}/events")
    if emit_json:
        _print_json({"events": timeline})
    else:
        _print_timeline(timeline)
    return 0


def _intake_schema(base_url: str, *, emit_json: bool) -> int:
    schema = _get_json(base_url, "/task-intakes/schema")
    if emit_json:
        _print_json({"schema": schema})
    else:
        fields = schema.get("fields", {}) if isinstance(schema, dict) else {}
        print(f"registry_version: {schema.get('version') if isinstance(schema, dict) else '-'}")
        for name, definition in fields.items():
            if isinstance(definition, dict):
                print(
                    "field: "
                    f"{name} group={definition.get('group')} "
                    f"type={definition.get('type')} control={definition.get('ui_control')}"
                )
    return 0


def _intake_create(
    base_url: str,
    *,
    text: str | None,
    fields: dict[str, Any],
    source: str,
    emit_json: bool,
) -> int:
    payload = _post_json(
        base_url,
        "/task-intakes",
        {"text": text, "structured_fields": fields, "source": source},
    )
    if emit_json:
        _print_json({"intake": payload})
    else:
        _print_intake(payload)
    return 0


def _intake_patch(
    base_url: str,
    *,
    intake_id: str,
    fields: dict[str, Any],
    updated_by: str,
    emit_json: bool,
) -> int:
    payload = _patch_json(
        base_url,
        f"/task-intakes/{intake_id}",
        {"fields": fields, "updated_by": updated_by},
    )
    if emit_json:
        _print_json({"intake": payload})
    else:
        _print_intake(payload)
    return 0


def _intake_confirm(
    base_url: str,
    *,
    intake_id: str,
    confirmed_by: str,
    acknowledged_warnings: list[str],
    emit_json: bool,
) -> int:
    payload = _post_json(
        base_url,
        f"/task-intakes/{intake_id}/confirm",
        {
            "confirmed_by": confirmed_by,
            "acknowledged_warnings": acknowledged_warnings,
        },
    )
    if emit_json:
        _print_json({"confirmation": payload})
    else:
        print(f"intake_id: {payload.get('intake_id')}")
        print(f"task_id: {payload.get('task_id')}")
        print(f"status: {payload.get('status')}")
    return 0


def _get_json(base_url: str, path: str) -> dict[str, Any] | list[dict[str, Any]]:
    response = httpx.get(f"{base_url}{path}", timeout=10.0)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, (dict, list)):
        raise ValueError(f"API payload for {path} is not an object or list")
    return payload


def _post_json(base_url: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = httpx.post(f"{base_url}{path}", json=payload, timeout=10.0)
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if path.endswith("/confirm"):
            raise ValueError(_format_intake_confirm_error(response)) from exc
        raise
    body = response.json()
    if not isinstance(body, dict):
        raise ValueError(f"API payload for {path} is not an object")
    return body


def _format_intake_confirm_error(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return f"intake confirm failed with HTTP {response.status_code}"
    if not isinstance(payload, dict):
        return f"intake confirm failed with HTTP {response.status_code}"
    detail = str(payload.get("detail") or f"HTTP {response.status_code}")
    context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
    safety = context.get("safety_check") if isinstance(context, dict) else None
    warning_codes: list[str] = []
    if isinstance(safety, dict):
        for risk in safety.get("risk_flags") or []:
            if isinstance(risk, dict) and risk.get("level") == "warn":
                code = risk.get("code")
                if isinstance(code, str):
                    warning_codes.append(code)
    if warning_codes:
        return (
            f"intake confirm failed: {detail}\n"
            "acknowledge warnings with: "
            + " ".join(f"--ack-warning {code}" for code in warning_codes)
        )
    return f"intake confirm failed: {detail}"


def _patch_json(base_url: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = httpx.patch(f"{base_url}{path}", json=payload, timeout=10.0)
    response.raise_for_status()
    body = response.json()
    if not isinstance(body, dict):
        raise ValueError(f"API payload for {path} is not an object")
    return body


def _parse_field_args(items: list[str]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"field must use key=value syntax: {item}")
        key, raw_value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError("field key must not be empty")
        try:
            fields[key] = json.loads(raw_value)
        except json.JSONDecodeError:
            fields[key] = raw_value
    return fields


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
        for candidate in pending.get("candidates") or []:
            if isinstance(candidate, dict):
                _print_candidate_runtime_line(candidate)
    _print_readiness_summary(payload["readiness_summary"])


def _print_intake(payload: dict[str, Any]) -> None:
    print(f"intake_id: {payload.get('intake_id')}")
    print(f"status: {payload.get('status')}")
    draft = payload.get("draft") if isinstance(payload.get("draft"), dict) else {}
    extraction_mode = draft.get("extraction_mode") if isinstance(draft, dict) else None
    extraction_errors = draft.get("extraction_errors") if isinstance(draft, dict) else []
    print(f"extraction_mode: {extraction_mode or '-'}")
    missing = payload.get("missing_required_fields") or []
    ambiguous = payload.get("ambiguous_fields") or []
    unmapped = payload.get("unmapped_text") or []
    print(f"missing_required_fields: {', '.join(missing) if missing else '-'}")
    print(f"ambiguous_fields: {', '.join(ambiguous) if ambiguous else '-'}")
    print(f"unmapped_text: {', '.join(unmapped) if unmapped else '-'}")
    safety = payload.get("safety_check") if isinstance(payload.get("safety_check"), dict) else {}
    if safety:
        print(f"safety_action: {safety.get('action') or '-'}")
        for risk in safety.get("risk_flags") or []:
            if isinstance(risk, dict):
                print(
                    "safety_risk: "
                    f"{risk.get('level')} "
                    f"{risk.get('code')} "
                    f"{risk.get('message')}"
                )
    if isinstance(extraction_errors, list) and extraction_errors:
        print(f"extraction_errors: {', '.join(str(item) for item in extraction_errors)}")
    fields = draft.get("fields") if isinstance(draft, dict) else {}
    if isinstance(fields, dict) and fields:
        print("fields:")
        for name, field in fields.items():
            if not isinstance(field, dict):
                continue
            source_span = field.get("source_span") or "-"
            print(
                "  "
                f"{name}: value={field.get('value')} "
                f"source={field.get('source') or '-'} "
                f"confidence={field.get('confidence')} "
                f"span={source_span} "
                f"confirmed={field.get('confirmed')}"
            )


def _print_pending(payload: dict[str, Any]) -> None:
    pending = payload["pending_action"]
    print(f"pending_action_id: {pending.get('pending_action_id')}")
    print(f"task_id: {pending.get('task_id')}")
    print(f"action_type: {pending.get('action_type')}")
    print(f"default_suggestion: {pending.get('default_suggestion') or '-'}")
    print(f"recommendation: {pending.get('workflow_action_reason') or pending.get('recommendation_summary') or '-'}")
    runtime_state = pending.get("runtime_state_summary")
    if isinstance(runtime_state, dict) and runtime_state:
        print(f"runtime_state_summary: {json.dumps(runtime_state, ensure_ascii=False, sort_keys=True)}")
    evidence_refs = pending.get("evidence_refs") if isinstance(pending.get("evidence_refs"), list) else []
    print(f"evidence_refs: {len(evidence_refs)}")
    for candidate in pending.get("candidates") or []:
        if not isinstance(candidate, dict):
            continue
        tool = candidate.get("tool") if isinstance(candidate.get("tool"), dict) else {}
        print(
            "candidate: "
            f"{candidate.get('candidate_id')} "
            f"default={candidate.get('is_default') or False} "
            f"summary={candidate.get('summary') or '-'} "
            f"risk={candidate.get('risk_level') or '-'} "
            f"cost={candidate.get('cost_estimate') or '-'} "
            f"expected_effect={candidate.get('expected_effect') or '-'} "
            f"affected_steps={','.join(candidate.get('affected_steps') or []) or '-'} "
            f"recovery_semantics={candidate.get('recovery_semantics') or '-'} "
            f"readiness={tool.get('readiness_status') or '-'} "
            f"tool={tool.get('tool_id') or '-'} "
            f"adapter={tool.get('adapter_id') or '-'} "
            f"execution_mode={tool.get('execution_mode') or '-'} "
            f"endpoint={tool.get('endpoint_type') or '-'} "
            f"remote_job_id={tool.get('remote_job_id') or '-'} "
            f"failure_code={tool.get('failure_code') or '-'} "
            f"recovery={tool.get('recovery_hint') or tool.get('suggested_recovery') or '-'}"
        )
        score_breakdown = candidate.get("score_breakdown")
        if isinstance(score_breakdown, dict) and score_breakdown:
            print(
                "candidate_score: "
                f"{candidate.get('candidate_id')} "
                f"{json.dumps(score_breakdown, ensure_ascii=False, sort_keys=True)}"
            )
    _print_readiness_summary(payload["readiness_summary"])


def _print_candidate_runtime_line(candidate: dict[str, Any]) -> None:
    print(
        "candidate_runtime: "
        f"{candidate.get('candidate_id') or '-'} "
        f"tool={candidate.get('tool_id') or candidate.get('tool') or '-'} "
        f"adapter={candidate.get('adapter_id') or '-'} "
        f"execution_mode={candidate.get('execution_mode') or '-'} "
        f"endpoint={candidate.get('endpoint_type') or '-'} "
        f"remote_job_id={candidate.get('remote_job_id') or '-'}"
    )


def _print_timeline(timeline: dict[str, Any] | list[dict[str, Any]]) -> None:
    if not isinstance(timeline, list):
        print("timeline: unavailable")
        return
    for event in timeline:
        if not isinstance(event, dict):
            continue
        print(
            "event: "
            f"{event.get('event_type') or '-'} "
            f"ts={event.get('ts') or '-'} "
            f"step={event.get('step_id') or '-'} "
            f"tool={event.get('tool_id') or event.get('tool') or '-'} "
            f"adapter={event.get('adapter_id') or '-'} "
            f"execution_mode={event.get('execution_mode') or '-'} "
            f"endpoint={event.get('endpoint_type') or '-'} "
            f"remote_job_id={event.get('remote_job_id') or '-'} "
            f"failure_code={event.get('failure_code') or '-'} "
            f"recovery={event.get('recovery_hint') or event.get('recovery_reason') or '-'} "
            f"summary={event.get('summary') or '-'}"
        )


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
