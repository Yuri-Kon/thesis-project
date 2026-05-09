from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx
from pydantic import ValidationError

from src.models.task_intake import ConfirmedTaskSpec

DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"


def main(argv: list[str] | None = None) -> int:
    """运行 design CLI 入口。"""
    parser = _build_parser()
    args, unknown_args = parser.parse_known_args(argv)
    base_url = str(args.api_base_url or os.getenv("DESIGN_API_BASE_URL") or DEFAULT_API_BASE_URL).rstrip("/")

    try:
        if args.command == "submit":
            _ensure_no_unknown_args(parser, unknown_args)
            return _submit(
                base_url,
                interactive=args.interactive,
                spec_path=args.spec,
                confirmed=args.confirm,
                text=args.text,
                acknowledged_warnings=args.acknowledge,
                emit_json=args.json,
            )
        if args.command == "task" and args.task_command == "show":
            _ensure_no_unknown_args(parser, unknown_args)
            return _task_show(base_url, args.task_id, emit_json=args.json)
        if args.command == "task" and args.task_command == "watch":
            _ensure_no_unknown_args(parser, unknown_args)
            return _task_watch(
                base_url,
                args.task_id,
                emit_json=args.json,
                interval_s=args.interval,
            )
        if args.command == "pending" and args.pending_command == "show":
            _ensure_no_unknown_args(parser, unknown_args)
            return _pending_show(base_url, args.pending_action_id, emit_json=args.json)
        if args.command == "timeline" and args.timeline_command == "show":
            _ensure_no_unknown_args(parser, unknown_args)
            return _timeline_show(base_url, args.task_id, emit_json=args.json)
        if args.command == "report" and args.report_command == "show":
            _ensure_no_unknown_args(parser, unknown_args)
            return _report_show(base_url, args.task_id, emit_json=args.json)
        if args.command == "intake" and args.intake_command == "schema":
            _ensure_no_unknown_args(parser, unknown_args)
            return _intake_schema(base_url, emit_json=args.json)
        if args.command == "intake" and args.intake_command in {"create", "parse"}:
            return _intake_create(
                base_url,
                text=args.text,
                fields=_collect_intake_fields(base_url, args.field, unknown_args),
                source=args.source,
                emit_json=args.json,
            )
        if args.command == "intake" and args.intake_command == "show":
            _ensure_no_unknown_args(parser, unknown_args)
            return _intake_show(
                base_url,
                intake_id=args.intake_id,
                emit_json=args.json,
            )
        if args.command == "intake" and args.intake_command in {"patch", "set"}:
            return _intake_patch(
                base_url,
                intake_id=args.intake_id,
                fields=_collect_intake_fields(base_url, args.field, unknown_args),
                updated_by=args.updated_by,
                emit_json=args.json,
            )
        if args.command == "intake" and args.intake_command == "confirm":
            _ensure_no_unknown_args(parser, unknown_args)
            return _intake_confirm(
                base_url,
                intake_id=args.intake_id,
                confirmed_by=args.confirmed_by,
                acknowledged_warnings=args.acknowledge,
                emit_json=args.json,
            )
        if args.command == "preflight":
            _ensure_no_unknown_args(parser, unknown_args)
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
    parser = argparse.ArgumentParser(
        prog="design",
        description=(
            "Protein Design System CLI — 蛋白质设计系统的命令行客户端。\n\n"
            "通过 HTTP API 与服务端交互，支持任务录入、查询、报告查看等操作。"
        ),
        epilog=(
            "示例:\n"
            "  design intake schema                          # 查看字段注册表\n"
            "  design intake create --text \"设计一条20aa的螺旋肽\"  # 创建任务录入\n"
            "  design intake show <INTAKE_ID>                 # 查看录入\n"
            "  design intake confirm <INTAKE_ID>              # 确认录入并创建任务\n"
            "  design task show <TASK_ID>                     # 查看任务\n"
            "  design task watch <TASK_ID>                    # 轮询等待任务完成\n"
            "  design timeline show <TASK_ID>                 # 查看事件时间线\n"
            "  design report show <TASK_ID> --json            # 导出报告 JSON\n"
            "  design pending show <PENDING_ID>               # 查看等待决策\n"
            "  design submit --interactive --confirm          # 交互式创建并提交\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--api-base-url",
        default=None,
        metavar="URL",
        help=(
            "API 服务地址。默认使用环境变量 DESIGN_API_BASE_URL，"
            "未设置时回退到 http://127.0.0.1:8000"
        ),
    )
    subparsers = parser.add_subparsers(
        dest="command",
        title="可用命令",
        metavar="command",
    )

    submit_parser = subparsers.add_parser(
        "submit",
        help="提交或创建任务",
        description="提交或创建任务。支持交互式和指定式两种模式：交互式通过 CLI 问答引导填写字段；指定式需提供预先确认的 task spec JSON 文件。",
    )
    submit_mode = submit_parser.add_mutually_exclusive_group(required=True)
    submit_mode.add_argument(
        "--interactive",
        action="store_true",
        help="交互式模式：通过 CLI 问答引导填写任务字段",
    )
    submit_mode.add_argument(
        "--spec",
        default=None,
        metavar="PATH",
        help="指定式模式：提供预先确认的 ConfirmedTaskSpec JSON 文件路径",
    )
    submit_parser.add_argument(
        "--text",
        default=None,
        metavar="TEXT",
        help="自然语言任务描述（交互式模式下作为预填文本）",
    )
    submit_parser.add_argument(
        "--confirm",
        action="store_true",
        help="同时提交确认，跳过人工审核步骤",
    )
    submit_parser.add_argument(
        "--acknowledge",
        action="append",
        default=[],
        help=argparse.SUPPRESS,
    )
    submit_parser.add_argument(
        "--ack-warning",
        dest="acknowledge",
        action="append",
        metavar="CODE",
        help="确认时主动应答安全警告。可多次使用，例如 --ack-warning FORBIDDEN_MOTIF",
    )
    submit_parser.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 格式输出原始 API 响应，不进行人类可读格式化",
    )

    task_parser = subparsers.add_parser(
        "task",
        help="查看或监控任务",
        description="查看任务详情或持续监控任务状态直至完成。",
    )
    task_subparsers = task_parser.add_subparsers(
        dest="task_command",
        title="子命令",
    )
    task_show = task_subparsers.add_parser(
        "show",
        help="查看任务详情",
        description="展示指定任务的完整信息，包括状态、能力就绪度、结构相似性等。",
    )
    task_show.add_argument(
        "task_id",
        metavar="TASK_ID",
        help="任务 ID",
    )
    task_show.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 格式输出",
    )
    task_watch = task_subparsers.add_parser(
        "watch",
        help="轮等待任务完成",
        description="持续轮询任务状态，直至任务进入 DONE / FAILED / CANCELLED 或等待人工决策。",
    )
    task_watch.add_argument(
        "task_id",
        metavar="TASK_ID",
        help="任务 ID",
    )
    task_watch.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 格式输出",
    )
    task_watch.add_argument(
        "--interval",
        type=float,
        default=5.0,
        metavar="SECONDS",
        help="轮询间隔秒数（默认 5 秒）",
    )

    pending_parser = subparsers.add_parser(
        "pending",
        help="查看等待决策",
        description="查看等待人工决策的 PendingAction 详情。",
    )
    pending_subparsers = pending_parser.add_subparsers(
        dest="pending_command",
        title="子命令",
    )
    pending_show = pending_subparsers.add_parser(
        "show",
        help="查看 PendingAction 详情",
        description="展示指定 PendingAction 的候选列表、元数据和关联任务信息。",
    )
    pending_show.add_argument(
        "pending_action_id",
        metavar="PENDING_ACTION_ID",
        help="PendingAction ID",
    )
    pending_show.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 格式输出",
    )

    timeline_parser = subparsers.add_parser(
        "timeline",
        help="查看任务事件时间线",
        description="查询任务的事件日志，按时间顺序展示状态变更和执行记录。",
    )
    timeline_subparsers = timeline_parser.add_subparsers(
        dest="timeline_command",
        title="子命令",
    )
    timeline_show = timeline_subparsers.add_parser(
        "show",
        help="查看事件时间线",
        description="展示指定任务的完整事件日志，包含状态迁移、步骤执行、决策记录等。",
    )
    timeline_show.add_argument(
        "task_id",
        metavar="TASK_ID",
        help="任务 ID",
    )
    timeline_show.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 格式输出",
    )

    report_parser = subparsers.add_parser(
        "report",
        help="查看任务报告",
        description="查询任务的设计结果报告，包含序列、结构、评分、风险标记等。",
    )
    report_subparsers = report_parser.add_subparsers(
        dest="report_command",
        title="子命令",
    )
    report_show = report_subparsers.add_parser(
        "show",
        help="查看设计报告",
        description="展示 DesignResult 的完整内容：序列、结构路径、评分详情、风险标记。",
    )
    report_show.add_argument(
        "task_id",
        metavar="TASK_ID",
        help="任务 ID",
    )
    report_show.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 格式输出",
    )

    intake_parser = subparsers.add_parser(
        "intake",
        help="管理与确认任务录入",
        description="管理任务录入（Task Intake）：创建、查看、修改、确认任务规范。",
    )
    intake_subparsers = intake_parser.add_subparsers(
        dest="intake_command",
        title="子命令",
    )
    intake_schema = intake_subparsers.add_parser(
        "schema",
        help="查看字段注册表",
        description="展示当前任务录入的字段注册表：所有可用字段的类型、默认值、必填条件。",
    )
    intake_schema.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 格式输出完整 schema",
    )
    intake_create = intake_subparsers.add_parser(
        "create",
        help="创建任务录入",
        description="创建新的任务录入。支持自然语言描述和结构化字段混合输入。",
    )
    intake_create.add_argument(
        "--text",
        default=None,
        metavar="TEXT",
        help="自然语言任务描述。例如 '设计一条 20 氨基酸的稳定 α 螺旋'",
    )
    intake_create.add_argument(
        "--field",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="结构化字段，格式 key=JSON值。可多次使用。例如 --field task_kind='\"de_novo_design\"'",
    )
    intake_create.add_argument(
        "--source",
        default="cli",
        choices=["web", "cli", "api", "script", "legacy"],
        help="录入来源标记（默认 cli）",
    )
    intake_create.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 格式输出",
    )
    intake_parse = intake_subparsers.add_parser(
        "parse",
        help="解析并创建录入（需 --text）",
        description="解析自然语言文本为任务录入，并立即创建。必须提供 --text。",
    )
    intake_parse.add_argument(
        "--text",
        required=True,
        metavar="TEXT",
        help="需解析的自然语言任务描述",
    )
    intake_parse.add_argument(
        "--field",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="结构化字段补充，格式 key=JSON值。可多次使用",
    )
    intake_parse.add_argument(
        "--source",
        default="cli",
        choices=["web", "cli", "api", "script", "legacy"],
        help="录入来源标记（默认 cli）",
    )
    intake_parse.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 格式输出",
    )
    intake_show = intake_subparsers.add_parser(
        "show",
        help="查看任务录入",
        description="展示指定录入的当前规范和系统推断的 profile。",
    )
    intake_show.add_argument(
        "intake_id",
        metavar="INTAKE_ID",
        help="录入 ID",
    )
    intake_show.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 格式输出",
    )
    intake_patch = intake_subparsers.add_parser(
        "patch",
        help="修改录入字段",
        description="更新已有录入的字段。仅修改指定的字段，其余保持不变。",
    )
    intake_patch.add_argument(
        "intake_id",
        metavar="INTAKE_ID",
        help="录入 ID",
    )
    intake_patch.add_argument(
        "--field",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="要修改的字段，格式 key=JSON值。可多次使用",
    )
    intake_patch.add_argument(
        "--updated-by",
        default="cli",
        metavar="SOURCE",
        help="更新者标记（默认 cli）",
    )
    intake_patch.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 格式输出",
    )
    intake_set = intake_subparsers.add_parser(
        "set",
        help="覆盖式设置录入字段",
        description="覆盖式设置录入字段。与 patch 不同，未指定的字段也会被重置为系统默认值。",
    )
    intake_set.add_argument(
        "intake_id",
        metavar="INTAKE_ID",
        help="录入 ID",
    )
    intake_set.add_argument(
        "--field",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="要设置的字段，格式 key=JSON值。可多次使用",
    )
    intake_set.add_argument(
        "--updated-by",
        default="cli",
        metavar="SOURCE",
        help="更新者标记（默认 cli）",
    )
    intake_set.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 格式输出",
    )
    intake_confirm = intake_subparsers.add_parser(
        "confirm",
        help="确认录入并创建任务",
        description="确认任务录入，创建正式任务并进入执行流程。如有安全警告需显式应答。",
    )
    intake_confirm.add_argument(
        "intake_id",
        metavar="INTAKE_ID",
        help="录入 ID",
    )
    intake_confirm.add_argument(
        "--confirmed-by",
        default="cli",
        metavar="SOURCE",
        help="确认者标记（默认 cli）",
    )
    intake_confirm.add_argument(
        "--acknowledge",
        action="append",
        default=[],
        help=argparse.SUPPRESS,
    )
    intake_confirm.add_argument(
        "--ack-warning",
        dest="acknowledge",
        action="append",
        metavar="CODE",
        help="确认时主动应答安全警告。可多次使用",
    )
    intake_confirm.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 格式输出",
    )

    subparsers.add_parser(
        "preflight",
        help="（已废弃）使用 design intake 系列命令代替",
        description="preflight 已迁移到 Task Intake 体系，请使用 design intake 系列命令。",
    )
    return parser


def _submit(
    base_url: str,
    *,
    interactive: bool,
    spec_path: str | None,
    confirmed: bool,
    text: str | None,
    acknowledged_warnings: list[str],
    emit_json: bool,
) -> int:
    if spec_path is not None:
        if not confirmed:
            raise ValueError("submit --spec requires --confirm")
        spec = _read_confirmed_task_spec(spec_path)
        payload = _post_json(base_url, "/tasks", {"confirmed_task_spec": spec})
        _print_submission(payload, emit_json=emit_json)
        return 0
    if interactive:
        fields = _prompt_intake_fields(base_url)
        intake = _post_json(
            base_url,
            "/task-intakes",
            {"text": text, "structured_fields": fields, "source": "cli"},
        )
        if confirmed:
            confirmation = _post_json(
                base_url,
                f"/task-intakes/{intake.get('intake_id')}/confirm",
                {
                    "confirmed_by": "cli",
                    "acknowledged_warnings": acknowledged_warnings,
                },
            )
            _print_submission(confirmation, emit_json=emit_json)
        elif emit_json:
            _print_json({"intake": intake, "profile": _intake_profile(intake)})
        else:
            _print_intake(intake)
        return 0
    raise ValueError("submit requires --interactive or --spec")


def _task_show(base_url: str, task_id: str, *, emit_json: bool) -> int:
    task = _get_json(base_url, f"/tasks/{task_id}")
    readiness = _get_json(base_url, "/capabilities/readiness")
    payload = {
        "task": task,
        "readiness_summary": _readiness_summary(readiness),
        "structure_similarity": _structure_similarity_summary_from_task(task),
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
        cli_args = schema.get("cli_arguments", []) if isinstance(schema, dict) else []
        flags_by_field = {
            str(item.get("field")): item
            for item in cli_args
            if isinstance(item, dict) and item.get("field")
        }
        print(f"registry_version: {schema.get('version') if isinstance(schema, dict) else '-'}")
        for name, definition in fields.items():
            if isinstance(definition, dict):
                cli_arg = flags_by_field.get(str(name), {})
                print(
                    "field: "
                    f"{name} group={definition.get('group')} "
                    f"type={definition.get('type')} control={definition.get('ui_control')}"
                    f" flag={cli_arg.get('flag') or '-'} "
                    f"default={definition.get('default')}"
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
        _print_json({"intake": payload, "profile": _intake_profile(payload)})
    else:
        _print_intake(payload)
    return 0


def _intake_show(base_url: str, *, intake_id: str, emit_json: bool) -> int:
    payload = _get_json(base_url, f"/task-intakes/{intake_id}")
    if not isinstance(payload, dict):
        raise ValueError(f"API payload for /task-intakes/{intake_id} is not an object")
    schema = _get_json(base_url, "/task-intakes/schema")
    schema_payload = schema if isinstance(schema, dict) else {}
    if emit_json:
        _print_json(
            {
                "intake": payload,
                "profile": _intake_profile(payload, schema=schema_payload),
            }
        )
    else:
        _print_intake(payload, schema=schema_payload)
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
        _print_json({"intake": payload, "profile": _intake_profile(payload)})
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
        _print_json({"confirmation": payload, "profile": _confirmation_profile(payload)})
    else:
        _print_submission(payload, emit_json=False)
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
        if path == "/task-intakes" or path == "/tasks":
            raise ValueError(_format_api_error(response, action=path)) from exc
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
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise ValueError(_format_api_error(response, action=path)) from exc
    body = response.json()
    if not isinstance(body, dict):
        raise ValueError(f"API payload for {path} is not an object")
    return body


def _format_api_error(response: httpx.Response, *, action: str) -> str:
    try:
        payload = response.json()
    except ValueError:
        return f"{action} failed with HTTP {response.status_code}"
    if not isinstance(payload, dict):
        return f"{action} failed with HTTP {response.status_code}"
    detail = str(payload.get("detail") or f"HTTP {response.status_code}")
    validation = payload.get("validation_errors")
    if isinstance(validation, list) and validation:
        messages = []
        for item in validation:
            if isinstance(item, dict):
                field = item.get("field") or "-"
                messages.append(f"{field}: {item.get('message')}")
        if messages:
            return f"{action} failed: {detail}; " + "; ".join(messages)
    return f"{action} failed: {detail}"


def _ensure_no_unknown_args(parser: argparse.ArgumentParser, unknown_args: list[str]) -> None:
    if unknown_args:
        parser.error(f"unrecognized arguments: {' '.join(unknown_args)}")


def _collect_intake_fields(
    base_url: str,
    field_args: list[str],
    dynamic_args: list[str],
) -> dict[str, Any]:
    fields = _parse_field_args(field_args)
    if dynamic_args:
        fields.update(_parse_schema_field_args(base_url, dynamic_args))
    return fields


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


def _parse_schema_field_args(base_url: str, items: list[str]) -> dict[str, Any]:
    schema = _get_json(base_url, "/task-intakes/schema")
    if not isinstance(schema, dict):
        raise ValueError("task intake schema is not an object")
    cli_args = schema.get("cli_arguments")
    if not isinstance(cli_args, list):
        raise ValueError("task intake schema does not expose cli_arguments")
    flag_to_field = {
        str(item.get("flag")): str(item.get("field"))
        for item in cli_args
        if isinstance(item, dict) and item.get("flag") and item.get("field")
    }
    fields: dict[str, Any] = {}
    index = 0
    while index < len(items):
        token = items[index]
        value_token: str
        if "=" in token:
            flag, value_token = token.split("=", 1)
        else:
            flag = token
            index += 1
            if index >= len(items):
                raise ValueError(f"schema field flag requires a value: {flag}")
            value_token = items[index]
        field_name = flag_to_field.get(flag)
        if field_name is None:
            raise ValueError(f"unknown intake field flag from schema: {flag}")
        fields[field_name] = _parse_jsonish_value(value_token)
        index += 1
    return fields


def _parse_jsonish_value(raw_value: str) -> Any:
    try:
        return json.loads(raw_value)
    except json.JSONDecodeError:
        return raw_value


def _read_confirmed_task_spec(spec_path: str) -> dict[str, Any]:
    path = Path(spec_path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read task spec: {spec_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"task spec must be valid JSON: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise ValueError("task spec must be a JSON object")
    try:
        return ConfirmedTaskSpec.model_validate(payload).model_dump(mode="json")
    except ValidationError as exc:
        messages = "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors()
        )
        raise ValueError(
            f"task spec must comply with ConfirmedTaskSpec schema: {messages}"
        ) from exc


def _prompt_intake_fields(base_url: str) -> dict[str, Any]:
    schema = _get_json(base_url, "/task-intakes/schema")
    if not isinstance(schema, dict):
        raise ValueError("task intake schema is not an object")
    questions = schema.get("cli_questions")
    if not isinstance(questions, list):
        raise ValueError("task intake schema does not expose cli_questions")
    fields: dict[str, Any] = {}
    for question in questions:
        if not isinstance(question, dict):
            continue
        field_name = question.get("field")
        prompt = question.get("prompt") or field_name
        if not isinstance(field_name, str) or not field_name:
            continue
        raw_value = input(f"{prompt}: ").strip()
        if not raw_value:
            continue
        fields[field_name] = _parse_jsonish_value(raw_value)
    return fields


def _intake_profile(
    payload: dict[str, Any],
    *,
    schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
    draft = payload.get("draft") if isinstance(payload.get("draft"), dict) else {}
    fields = draft.get("fields") if isinstance(draft, dict) else {}
    normalized_fields: dict[str, dict[str, Any]] = {}
    confirmed_fields: list[str] = []
    low_confidence_fields: list[str] = []
    if isinstance(fields, dict):
        for name, field in fields.items():
            if not isinstance(field, dict):
                continue
            confirmed = bool(field.get("confirmed"))
            confidence = field.get("confidence")
            normalized_fields[name] = {
                "value": field.get("value"),
                "source": field.get("source"),
                "confirmed": confirmed,
                "confidence": confidence,
                "source_span": field.get("source_span"),
                "warnings": field.get("warnings") or [],
            }
            if confirmed:
                confirmed_fields.append(name)
            if isinstance(confidence, (int, float)) and confidence < 0.8:
                low_confidence_fields.append(name)
    pending_fields = [
        str(item)
        for item in payload.get("missing_required_fields") or []
    ]
    low_confidence_fields = list(
        dict.fromkeys(
            [
                str(item)
                for item in payload.get("ambiguous_fields") or []
            ]
            + low_confidence_fields
        )
    )
    safety = payload.get("safety_check") if isinstance(payload.get("safety_check"), dict) else {}
    return {
        "intake_id": payload.get("intake_id"),
        "status": payload.get("status"),
        "task_id": payload.get("task_id"),
        "extraction_mode": draft.get("extraction_mode") if isinstance(draft, dict) else None,
        "confirmed_fields": sorted(confirmed_fields),
        "pending_fields": pending_fields,
        "low_confidence_fields": low_confidence_fields,
        "default_fields": _default_field_profile(payload, schema or {}),
        "warnings": payload.get("warnings") or [],
        "safety_action": safety.get("action") if isinstance(safety, dict) else None,
        "safety_warnings": _safety_warning_profile(safety),
        "unmapped_text": payload.get("unmapped_text") or [],
        "fields": normalized_fields,
        "next_action": _intake_next_action(payload),
    }


def _default_field_profile(payload: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    draft = payload.get("draft") if isinstance(payload.get("draft"), dict) else {}
    fields = draft.get("fields") if isinstance(draft, dict) else {}
    present = set(fields) if isinstance(fields, dict) else set()
    registry_fields = schema.get("fields") if isinstance(schema.get("fields"), dict) else {}
    defaults: dict[str, Any] = {}
    for name, definition in registry_fields.items():
        if name in present or not isinstance(definition, dict):
            continue
        if "default" not in definition:
            continue
        default_value = definition.get("default")
        if default_value is not None and default_value != []:
            defaults[str(name)] = default_value
    return defaults


def _safety_warning_profile(safety: Any) -> list[dict[str, Any]]:
    if not isinstance(safety, dict):
        return []
    warnings: list[dict[str, Any]] = []
    for risk in safety.get("risk_flags") or []:
        if isinstance(risk, dict) and risk.get("level") == "warn":
            warnings.append(
                {
                    "code": risk.get("code"),
                    "message": risk.get("message"),
                }
            )
    return warnings


def _intake_next_action(payload: dict[str, Any]) -> str:
    if payload.get("missing_required_fields"):
        return "set_missing_fields"
    if payload.get("ambiguous_fields"):
        return "resolve_low_confidence_fields"
    safety = payload.get("safety_check") if isinstance(payload.get("safety_check"), dict) else {}
    if isinstance(safety, dict) and safety.get("action") == "warn":
        return "confirm_with_warning_acknowledgement"
    if isinstance(safety, dict) and safety.get("action") == "block":
        return "revise_blocked_input"
    if payload.get("status") == "confirmed":
        return "task_created"
    return "confirm"


def _confirmation_profile(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "intake_id": payload.get("intake_id"),
        "task_id": payload.get("task_id") or payload.get("id"),
        "status": payload.get("status"),
        "next_action": "task_show",
    }


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
    metadata = task.get("metadata") if isinstance(task.get("metadata"), dict) else {}
    scenario_gate = metadata.get("scenario_gate") if isinstance(metadata, dict) else None
    print(f"task_id: {task.get('id')}")
    print(f"status: {task.get('status')} / {task.get('internal_status') or '-'}")
    print(f"goal: {task.get('goal')}")
    if isinstance(metadata, dict):
        support_level = metadata.get("support_level")
        if support_level:
            print(f"support_level: {support_level}")
    if isinstance(scenario_gate, dict):
        _print_scenario_gate(scenario_gate)
    pending = task.get("pending_action")
    if isinstance(pending, dict):
        print(f"pending_action: {pending.get('pending_action_id')} ({pending.get('action_type')})")
        for candidate in pending.get("candidates") or []:
            if isinstance(candidate, dict):
                _print_candidate_runtime_line(candidate)
    _print_structure_similarity_summary(payload.get("structure_similarity"))
    _print_readiness_summary(payload["readiness_summary"])


def _print_intake(payload: dict[str, Any], *, schema: dict[str, Any] | None = None) -> None:
    profile = _intake_profile(payload, schema=schema)
    print(f"intake_id: {profile.get('intake_id')}")
    print(f"status: {profile.get('status')}")
    draft = payload.get("draft") if isinstance(payload.get("draft"), dict) else {}
    extraction_errors = draft.get("extraction_errors") if isinstance(draft, dict) else []
    print(f"extraction_mode: {profile.get('extraction_mode') or '-'}")
    print(f"confirmed_fields: {_format_list(profile['confirmed_fields'])}")
    print(f"pending_fields: {_format_list(profile['pending_fields'])}")
    print(f"low_confidence_fields: {_format_list(profile['low_confidence_fields'])}")
    print(f"default_fields: {_format_mapping(profile['default_fields'])}")
    print(f"warnings: {_format_list(profile['warnings'])}")
    print(f"unmapped_text: {_format_list(profile['unmapped_text'])}")
    print(f"next_action: {profile.get('next_action')}")
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


def _print_submission(payload: dict[str, Any], *, emit_json: bool) -> None:
    profile = _confirmation_profile(payload)
    if emit_json:
        _print_json({"confirmation": payload, "profile": profile})
        return
    print(f"intake_id: {profile.get('intake_id') or '-'}")
    print(f"task_id: {profile.get('task_id')}")
    print(f"status: {profile.get('status')}")
    scenario_gate = payload.get("scenario_gate")
    if isinstance(scenario_gate, dict):
        _print_scenario_gate(scenario_gate)


def _print_scenario_gate(scenario_gate: dict[str, Any]) -> None:
    print(
        "scenario_gate: "
        f"{scenario_gate.get('status')} "
        f"support={scenario_gate.get('support_level') or '-'} "
        f"checked_at={scenario_gate.get('checked_at') or '-'}"
    )
    message = scenario_gate.get("user_message_zh") or scenario_gate.get("user_message")
    if message:
        print(f"scenario_gate_message: {message}")
    blocked = scenario_gate.get("blocked_hints")
    if isinstance(blocked, list) and blocked:
        print(f"blocked_capabilities: {_format_list(blocked)}")
    degraded = scenario_gate.get("degraded_hints")
    if isinstance(degraded, list) and degraded:
        print(f"degraded_capabilities: {_format_list(degraded)}")
    readiness = scenario_gate.get("readiness")
    if isinstance(readiness, dict) and readiness:
        print("scenario_capability_readiness:")
        for key, snapshot in readiness.items():
            if not isinstance(snapshot, dict):
                continue
            print(
                "  "
                f"{key}: {snapshot.get('status') or '-'} "
                f"reason={snapshot.get('reason') or '-'}"
            )


def _format_list(items: Any) -> str:
    if not isinstance(items, list) or not items:
        return "-"
    return ", ".join(str(item) for item in items)


def _format_mapping(items: Any) -> str:
    if not isinstance(items, dict) or not items:
        return "-"
    return json.dumps(items, ensure_ascii=False, sort_keys=True)


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
    posterior = (
        objective.get("posterior_score")
        if isinstance(objective.get("posterior_score"), dict)
        else {}
    )
    if posterior:
        print(
            "posterior_score: "
            f"aggregate={posterior.get('aggregate_score', '-')} "
            f"evidence={posterior.get('evidence_status', '-')} "
            f"evidence_sufficiency={posterior.get('evidence_sufficiency', '-')}"
        )
        weights = posterior.get("component_weights")
        if isinstance(weights, dict):
            print(
                "component_weights: "
                f"{json.dumps(weights, ensure_ascii=False, sort_keys=True)}"
            )
    warnings = objective.get("warnings") if isinstance(objective.get("warnings"), list) else []
    print(f"warnings: {len(warnings)}")
    for row in objective.get("top_k") or []:
        if not isinstance(row, dict):
            continue
        row_posterior = (
            row.get("posterior_score")
            if isinstance(row.get("posterior_score"), dict)
            else {}
        )
        print(
            "candidate: "
            f"{row.get('candidate_id') or row.get('id')} "
            f"rank={row.get('top_k_rank') or '-'} "
            f"score={row.get('objective_score', '-')} "
            f"evidence={row_posterior.get('evidence_status', '-')}"
        )
    _print_structure_similarity_summary(report.get("structure_similarity"))


def _structure_similarity_summary_from_task(task: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(task, dict):
        return {}
    design_result = task.get("design_result")
    if not isinstance(design_result, dict):
        return {}
    metadata = design_result.get("metadata")
    if not isinstance(metadata, dict):
        return {}
    structure_similarity = metadata.get("structure_similarity")
    return dict(structure_similarity) if isinstance(structure_similarity, dict) else {}


def _print_structure_similarity_summary(value: Any) -> None:
    if not isinstance(value, dict) or not value:
        return
    top_hit = value.get("top_hit") if isinstance(value.get("top_hit"), dict) else {}
    print(
        "structure_similarity: "
        f"hits={value.get('hit_count', '-')} "
        f"top_hit={top_hit.get('hit_id') or top_hit.get('target_id') or '-'} "
        f"tm_score={top_hit.get('tm_score', '-')}"
    )
    artifacts = value.get("artifact_refs") if isinstance(value.get("artifact_refs"), list) else []
    if artifacts:
        print(f"structure_similarity_artifacts: {len(artifacts)}")


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
