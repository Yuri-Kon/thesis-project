#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.infra.w12_vertical_experiment import (
    DEFAULT_HIGH_COST_RULES,
    load_json,
    normalize_high_cost_rules,
    now_iso,
    stable_hash,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze high-cost step definitions, task set, and baseline matrix."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/experiments/baseline_experiment_contract.json"),
        help="Freeze config JSON path.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help="Override output root directory.",
    )
    parser.add_argument(
        "--freeze-id",
        type=str,
        default=None,
        help="Override freeze id.",
    )
    return parser.parse_args()


def _normalize_tasks(raw_tasks: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_tasks, list) or not raw_tasks:
        raise ValueError("config.tasks must be a non-empty list")

    tasks: list[dict[str, Any]] = []
    for raw in raw_tasks:
        if not isinstance(raw, dict):
            continue
        task_key = raw.get("task_key")
        difficulty = raw.get("difficulty")
        if not isinstance(task_key, str) or not task_key:
            raise ValueError("each task requires non-empty task_key")
        if not isinstance(difficulty, str) or not difficulty:
            raise ValueError(f"task {task_key} missing difficulty")
        tasks.append(
            {
                "task_key": task_key,
                "display_name": str(raw.get("display_name") or task_key),
                "difficulty": difficulty,
                "budget_tier": str(raw.get("budget_tier") or "standard"),
                "rationale": str(raw.get("rationale") or ""),
                "prompt": raw.get("prompt"),
                "length_range": raw.get("length_range"),
            }
        )

    if not tasks:
        raise ValueError("config.tasks contains no valid task rows")
    return tasks


def _normalize_baselines(raw_baselines: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_baselines, list) or len(raw_baselines) != 4:
        raise ValueError("config.baselines must contain exactly four rows")

    required_ids = {
        "static_top1",
        "fixed_threshold_gate",
        "dynamic_no_belief_state",
        "lite_belief_state",
    }
    baselines: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(raw_baselines):
        if not isinstance(raw, dict):
            raise ValueError("baseline rows must be objects")
        baseline_id = raw.get("id")
        if not isinstance(baseline_id, str) or not baseline_id:
            raise ValueError(f"baseline at index {index} missing id")
        if baseline_id in seen_ids:
            raise ValueError(f"duplicate baseline id: {baseline_id}")
        seen_ids.add(baseline_id)
        baselines.append(
            {
                "id": baseline_id,
                "label": str(raw.get("label") or baseline_id),
                "comparison_order": int(raw.get("comparison_order") or index),
                "implementation_status": str(raw.get("implementation_status") or "planned"),
                "runtime_policy": str(raw.get("runtime_policy") or "static"),
                "supports_current_repo": bool(raw.get("supports_current_repo", False)),
                "constraint_overrides": raw.get("constraint_overrides")
                if isinstance(raw.get("constraint_overrides"), dict)
                else {},
                "output_fields": raw.get("output_fields")
                if isinstance(raw.get("output_fields"), list)
                else [],
                "notes": str(raw.get("notes") or ""),
            }
        )

    if seen_ids != required_ids:
        missing = sorted(required_ids - seen_ids)
        extra = sorted(seen_ids - required_ids)
        raise ValueError(f"baseline ids mismatch missing={missing} extra={extra}")
    return sorted(baselines, key=lambda item: item["comparison_order"])


def _validate_source_task_alignment(
    *,
    source_task_config_path: Path | None,
    frozen_tasks: list[dict[str, Any]],
) -> dict[str, Any]:
    if source_task_config_path is None:
        return {
            "source_task_config_path": None,
            "aligned": False,
            "source_task_keys": [],
            "missing_in_freeze": [],
            "extra_in_freeze": [row["task_key"] for row in frozen_tasks],
        }

    source_payload = load_json(source_task_config_path)
    raw_tasks = source_payload.get("tasks")
    source_task_keys: list[str] = []
    if isinstance(raw_tasks, list):
        source_task_keys = [
            str(item.get("task_key"))
            for item in raw_tasks
            if isinstance(item, dict) and isinstance(item.get("task_key"), str)
        ]
    frozen_task_keys = [row["task_key"] for row in frozen_tasks]
    missing_in_freeze = sorted(set(source_task_keys) - set(frozen_task_keys))
    extra_in_freeze = sorted(set(frozen_task_keys) - set(source_task_keys))
    return {
        "source_task_config_path": str(source_task_config_path),
        "aligned": not missing_in_freeze and not extra_in_freeze,
        "source_task_keys": source_task_keys,
        "missing_in_freeze": missing_in_freeze,
        "extra_in_freeze": extra_in_freeze,
    }


def _build_report(manifest: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Baseline Experiment Contract Freeze")
    lines.append("")
    lines.append(f"- freeze_id: `{manifest['freeze_id']}`")
    lines.append(f"- generated_at: `{manifest['generated_at']}`")
    lines.append(f"- task_set_version: `{manifest['task_set_version']}`")
    lines.append(f"- difficulty_scheme_version: `{manifest['difficulty_scheme_version']}`")
    lines.append("")
    lines.append("## High-Cost Rules")
    lines.append("")
    lines.append("| rule_id | label | stage_ids | capability_ids | tool_ids | cost_tier |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for row in manifest["high_cost_rules"]:
        lines.append(
            "| {rule_id} | {label} | {stage_ids} | {capability_ids} | {tool_ids} | {cost_tier} |".format(
                rule_id=row["rule_id"],
                label=row["label"],
                stage_ids=", ".join(row["stage_ids"]) or "-",
                capability_ids=", ".join(row["capability_ids"]) or "-",
                tool_ids=", ".join(row["tool_ids"]) or "-",
                cost_tier=row["cost_tier"],
            )
        )
    lines.append("")
    lines.append("## Task Catalog")
    lines.append("")
    lines.append("| task_key | difficulty | budget_tier |")
    lines.append("| --- | --- | --- |")
    for row in manifest["tasks"]:
        lines.append(
            f"| {row['task_key']} | {row['difficulty']} | {row['budget_tier']} |"
        )
    lines.append("")
    lines.append("## Baselines")
    lines.append("")
    lines.append("| id | label | status | runtime_policy | current_repo |")
    lines.append("| --- | --- | --- | --- | --- |")
    for row in manifest["baselines"]:
        lines.append(
            "| {id} | {label} | {implementation_status} | {runtime_policy} | {supports_current_repo} |".format(
                **row
            )
        )
    lines.append("")
    lines.append("## Metrics Contract")
    lines.append("")
    for group_name, metric_names in manifest["metrics_contract"].items():
        if group_name.endswith("_key"):
            continue
        lines.append(f"- {group_name}: `{', '.join(metric_names)}`")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- `dynamic_no_belief_state` and `lite_belief_state` are frozen as comparison contracts even when current repo support is partial.")
    lines.append("- High-cost call counting is aligned to the freeze rules and can be consumed by the vertical experiment evaluator.")
    return "\n".join(lines) + "\n"


def build_issue209_baseline_freeze(
    *,
    config: dict[str, Any],
    output_root: Path | None = None,
    freeze_id: str | None = None,
) -> tuple[dict[str, Any], Path]:
    if output_root is None:
        raw_output_root = config.get("output_root")
        output_root = (
            Path(raw_output_root)
            if isinstance(raw_output_root, str) and raw_output_root
            else Path("output/experiment/w13-expr-0")
        )

    freeze_id = freeze_id or str(config.get("freeze_id") or "issue209-baseline-freeze")
    output_dir = output_root / freeze_id
    output_dir.mkdir(parents=True, exist_ok=True)

    tasks = _normalize_tasks(config.get("tasks"))
    baselines = _normalize_baselines(config.get("baselines"))
    high_cost_rules = normalize_high_cost_rules(config.get("high_cost_rules") or DEFAULT_HIGH_COST_RULES)

    source_task_config_path = config.get("source_task_config_path")
    source_path = Path(source_task_config_path) if isinstance(source_task_config_path, str) and source_task_config_path else None
    source_alignment = _validate_source_task_alignment(
        source_task_config_path=source_path,
        frozen_tasks=tasks,
    )

    difficulty_counter = Counter(row["difficulty"] for row in tasks)
    metrics_contract = config.get("metrics_contract")
    if not isinstance(metrics_contract, dict):
        raise ValueError("config.metrics_contract must be an object")

    manifest = {
        "schema_version": "w13.issue209.freeze.v1",
        "issue_id": 209,
        "freeze_id": freeze_id,
        "generated_at": now_iso(),
        "task_set_version": str(config.get("task_set_version") or "issue209-taskset-v1"),
        "difficulty_scheme_version": str(
            config.get("difficulty_scheme_version") or "issue209-difficulty-v1"
        ),
        "source_references": {
            "source_task_config_path": str(source_path) if source_path else None,
            "source_dataset_freeze": config.get("source_dataset_freeze"),
            "source_alignment": source_alignment,
        },
        "tasks": tasks,
        "difficulty_distribution": dict(sorted(difficulty_counter.items())),
        "high_cost_rules": high_cost_rules,
        "baselines": baselines,
        "metrics_contract": metrics_contract,
        "fingerprint": stable_hash(
            {
                "tasks": tasks,
                "high_cost_rules": high_cost_rules,
                "baselines": baselines,
                "metrics_contract": metrics_contract,
            }
        ),
        "artifacts": {
            "output_dir": str(output_dir),
            "manifest_path": str((output_dir / "baseline_freeze_manifest.json").resolve()),
            "report_path": str((output_dir / "baseline_freeze_report.md").resolve()),
        },
    }

    write_json(output_dir / "baseline_freeze_manifest.json", manifest)
    (output_dir / "baseline_freeze_report.md").write_text(
        _build_report(manifest),
        encoding="utf-8",
    )
    return manifest, output_dir


def main() -> int:
    args = parse_args()
    config = load_json(args.config)
    manifest, output_dir = build_issue209_baseline_freeze(
        config=config,
        output_root=args.output_root,
        freeze_id=args.freeze_id,
    )

    print(f"[baseline-contract] freeze_id={manifest['freeze_id']}")
    print(f"[baseline-contract] output_dir={output_dir}")
    print(f"[baseline-contract] manifest={output_dir / 'baseline_freeze_manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
