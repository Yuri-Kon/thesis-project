#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.infra.w12_vertical_experiment import (
    deep_merge,
    load_json,
    now_iso,
    stable_hash,
    validate_freeze_manifest,
    write_csv,
    write_json,
    write_jsonl,
)
from src.models.contracts import ProteinDesignTask
from src.workflow.workflow import run_task_sync


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run vertical ablation experiment groups."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/experiments/vertical_ablation_experiment.json"),
        help="Experiment config JSON path.",
    )
    parser.add_argument(
        "--freeze-manifest-path",
        type=Path,
        default=None,
        help="Optional override of dataset freeze manifest path.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help="Root output directory for experiment artifacts.",
    )
    parser.add_argument(
        "--run-id",
        type=str,
        default=None,
        help="Optional run identifier. Auto-generated when omitted.",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=None,
        help="Optional override of repeat count.",
    )
    parser.add_argument(
        "--max-runs",
        type=int,
        default=None,
        help="Optional cap for total runs (for quick smoke).",
    )
    parser.add_argument(
        "--strict-freeze-check",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Require and validate freeze manifest before execution.",
    )
    parser.add_argument(
        "--dry-run",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Only materialize run manifest without executing tasks.",
    )
    return parser.parse_args()


def _git_short_sha() -> str:
    try:
        output = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True
        ).strip()
        return output or "nogit"
    except Exception:
        return "nogit"


def _sanitize_task_id(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in value)
    return cleaned[:96]


def _resolve_output_root(config: dict[str, Any], override: Path | None) -> Path:
    if override is not None:
        return override
    raw = config.get("output_root")
    if isinstance(raw, str) and raw:
        return Path(raw)
    return Path("output/experiment/w12-expr-2")


def _load_freeze_context(
    config: dict[str, Any],
    args: argparse.Namespace,
) -> tuple[str, dict[str, Any] | None, str | None]:
    expected_freeze_id = config.get("freeze_id") if isinstance(config.get("freeze_id"), str) else None
    freeze_manifest_path = args.freeze_manifest_path
    if freeze_manifest_path is None:
        raw = config.get("freeze_manifest_path")
        if isinstance(raw, str) and raw:
            freeze_manifest_path = Path(raw)

    if not args.strict_freeze_check:
        if expected_freeze_id:
            return expected_freeze_id, None, str(freeze_manifest_path) if freeze_manifest_path else None
        return "UNSET_FREEZE_ID", None, str(freeze_manifest_path) if freeze_manifest_path else None

    if freeze_manifest_path is None:
        raise ValueError("strict freeze check enabled but freeze manifest path is missing")
    if not freeze_manifest_path.exists():
        raise ValueError(f"freeze manifest not found: {freeze_manifest_path}")

    manifest = load_json(freeze_manifest_path)
    validated = validate_freeze_manifest(
        manifest,
        expected_freeze_id=expected_freeze_id,
        require_downstream_ready=True,
    )
    return validated["freeze_id"], manifest, str(freeze_manifest_path)


def main() -> int:
    args = parse_args()
    config = load_json(args.config)

    issue_id = int(config.get("issue_id") or 171)
    groups = config.get("groups")
    tasks = config.get("tasks")
    if not isinstance(groups, list) or not groups:
        raise ValueError("config.groups must be a non-empty list")
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("config.tasks must be a non-empty list")

    repeats = args.repeats if args.repeats is not None else int(config.get("repeats") or 3)
    if repeats <= 0:
        raise ValueError("repeats must be positive")

    freeze_id, freeze_manifest, freeze_manifest_path = _load_freeze_context(config, args)

    output_root = _resolve_output_root(config, args.output_root)
    run_id = args.run_id or f"w12e2-{datetime_now_tag()}-{_git_short_sha()}"
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    base_constraints = config.get("base_constraints") if isinstance(config.get("base_constraints"), dict) else {}
    base_metadata = config.get("base_metadata") if isinstance(config.get("base_metadata"), dict) else {}

    run_entries: list[dict[str, Any]] = []
    max_runs = args.max_runs if isinstance(args.max_runs, int) and args.max_runs > 0 else None

    counter = 0
    for group in groups:
        if not isinstance(group, dict):
            continue
        group_id = str(group.get("id") or "")
        if not group_id:
            continue
        group_constraints = group.get("constraint_overrides") if isinstance(group.get("constraint_overrides"), dict) else {}
        group_metadata = group.get("metadata") if isinstance(group.get("metadata"), dict) else {}

        for replicate in range(1, repeats + 1):
            for task in tasks:
                if max_runs is not None and counter >= max_runs:
                    break
                if not isinstance(task, dict):
                    continue

                task_key = str(task.get("task_key") or f"task{counter + 1:03d}")
                goal = str(task.get("goal") or "de_novo_design")
                task_constraints = task.get("constraints") if isinstance(task.get("constraints"), dict) else {}
                task_metadata = task.get("metadata") if isinstance(task.get("metadata"), dict) else {}

                merged_constraints = deep_merge(base_constraints, group_constraints)
                merged_constraints = deep_merge(merged_constraints, task_constraints)
                merged_metadata = deep_merge(base_metadata, group_metadata)
                merged_metadata = deep_merge(merged_metadata, task_metadata)

                merged_metadata = deep_merge(
                    merged_metadata,
                    {
                        "issue_id": issue_id,
                        "experiment": "vertical_ablation_experiment",
                        "group_id": group_id,
                        "task_key": task_key,
                        "replicate": replicate,
                        "freeze_id": freeze_id,
                    },
                )

                logical_run_id = f"{run_id}_{group_id}_{task_key}_r{replicate:02d}"
                task_id = _sanitize_task_id(logical_run_id)

                started_at = now_iso()
                status_external = "DRY_RUN"
                status_internal = "DRY_RUN"
                report_path = ""
                pending_action_type = None
                execution_error = None

                if not args.dry_run:
                    try:
                        record = run_task_sync(
                            ProteinDesignTask(
                                task_id=task_id,
                                goal=goal,
                                constraints=merged_constraints,
                                metadata=merged_metadata,
                            )
                        )
                        status_external = str(getattr(record.status, "value", record.status))
                        status_internal = str(
                            getattr(record.internal_status, "value", record.internal_status)
                        )
                        report_path = (
                            str(record.design_result.report_path)
                            if record.design_result is not None
                            else ""
                        )
                        pending_action_type = (
                            str(record.pending_action.action_type.value)
                            if record.pending_action is not None
                            else None
                        )
                    except Exception as exc:  # pragma: no cover - runtime resilience path
                        status_external = "FAILED"
                        status_internal = "FAILED"
                        execution_error = f"{type(exc).__name__}: {exc}"

                finished_at = now_iso()
                event_log_path = Path("data/logs") / f"{task_id}.jsonl"
                snapshot_path = Path("data/snapshots") / f"{task_id}.jsonl"

                entry = {
                    "run_id": logical_run_id,
                    "task_id": task_id,
                    "task_key": task_key,
                    "group_id": group_id,
                    "replicate": replicate,
                    "issue_id": issue_id,
                    "freeze_id": freeze_id,
                    "goal": goal,
                    "constraints_hash": stable_hash(merged_constraints),
                    "metadata_hash": stable_hash(merged_metadata),
                    "status_external": status_external,
                    "status_internal": status_internal,
                    "pending_action_type": pending_action_type,
                    "started_at": started_at,
                    "finished_at": finished_at,
                    "event_log_path": str(event_log_path),
                    "snapshot_path": str(snapshot_path),
                    "report_path": report_path,
                    "execution_error": execution_error,
                    "group_expected_mechanisms": group.get("expected_mechanisms")
                    if isinstance(group.get("expected_mechanisms"), list)
                    else [],
                }
                run_entries.append(entry)
                counter += 1

            if max_runs is not None and counter >= max_runs:
                break
        if max_runs is not None and counter >= max_runs:
            break

    run_manifest = {
        "issue_id": issue_id,
        "generated_at": now_iso(),
        "run_id": run_id,
        "config_path": str(args.config),
        "config_hash": stable_hash(config),
        "freeze_id": freeze_id,
        "freeze_manifest_path": freeze_manifest_path,
        "freeze_manifest": freeze_manifest,
        "dry_run": args.dry_run,
        "repeats": repeats,
        "groups": groups,
        "tasks": tasks,
        "runs": run_entries,
    }

    write_json(run_dir / "runs_manifest.json", run_manifest)
    write_json(run_dir / "resolved_config_snapshot.json", {
        "config": config,
        "args": {
            "config": str(args.config),
            "freeze_manifest_path": str(args.freeze_manifest_path) if args.freeze_manifest_path else None,
            "output_root": str(args.output_root) if args.output_root else None,
            "run_id": args.run_id,
            "repeats": args.repeats,
            "max_runs": args.max_runs,
            "strict_freeze_check": args.strict_freeze_check,
            "dry_run": args.dry_run,
        },
    })
    write_jsonl(run_dir / "runs.jsonl", run_entries)

    index_fields = [
        "run_id",
        "task_id",
        "group_id",
        "replicate",
        "task_key",
        "status_external",
        "status_internal",
        "started_at",
        "finished_at",
        "event_log_path",
        "snapshot_path",
        "report_path",
        "freeze_id",
        "pending_action_type",
        "execution_error",
    ]
    write_csv(run_dir / "run_log_index.csv", run_entries, index_fields)

    print(f"[vertical-experiment] run_id={run_id}")
    print(f"[vertical-experiment] freeze_id={freeze_id}")
    print(f"[vertical-experiment] runs={len(run_entries)}")
    print(f"[vertical-experiment] manifest={run_dir / 'runs_manifest.json'}")
    print(f"[vertical-experiment] log_index={run_dir / 'run_log_index.csv'}")

    return 0


def datetime_now_tag() -> str:
    return now_iso().replace(":", "").replace("-", "").replace("+", "z")


if __name__ == "__main__":
    raise SystemExit(main())
