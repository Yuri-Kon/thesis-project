#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.infra.w12_vertical_experiment import (
    DEFAULT_OFFLINE_THRESHOLDS,
    DEFAULT_REQUIREMENT2_CAPABILITY_MAP,
    aggregate_group_metrics,
    build_markdown_report,
    compute_increment_deltas,
    extract_run_metrics,
    load_json,
    load_tool_capability_map,
    now_iso,
    write_csv,
    write_json,
    write_jsonl,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate Issue #171 vertical experiment results and generate deliverables."
    )
    parser.add_argument(
        "--run-manifest-path",
        type=Path,
        required=True,
        help="Path to runs_manifest.json produced by run_w12_vertical_issue171.py",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory for evaluation artifacts. Defaults to run manifest directory.",
    )
    parser.add_argument(
        "--kg-path",
        type=Path,
        default=Path("src/kg/protein_tool_kg.json"),
        help="ProteinToolKG path for tool->capability mapping.",
    )
    parser.add_argument(
        "--bootstrap-iterations",
        type=int,
        default=10000,
        help="Bootstrap iterations for confidence intervals.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=20260315,
        help="Random seed for bootstrap resampling.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = load_json(args.run_manifest_path)

    runs = manifest.get("runs")
    if not isinstance(runs, list):
        raise ValueError("run manifest missing `runs` list")

    groups = manifest.get("groups") if isinstance(manifest.get("groups"), list) else []
    group_order = []
    for group in groups:
        if isinstance(group, dict):
            group_id = group.get("id")
            if isinstance(group_id, str) and group_id:
                group_order.append(group_id)

    if not group_order:
        group_order = sorted(
            {
                str(row.get("group_id"))
                for row in runs
                if isinstance(row, dict) and row.get("group_id")
            }
        )

    requirement2_capability_map = dict(DEFAULT_REQUIREMENT2_CAPABILITY_MAP)
    raw_req2 = manifest.get("requirement2_capability_map")
    if isinstance(raw_req2, dict):
        requirement2_capability_map = {
            str(key): [str(cap) for cap in value if isinstance(cap, str)]
            for key, value in raw_req2.items()
            if isinstance(value, list)
        }

    thresholds = dict(DEFAULT_OFFLINE_THRESHOLDS)
    raw_thresholds = manifest.get("offline_thresholds")
    if isinstance(raw_thresholds, dict):
        for key, value in raw_thresholds.items():
            if isinstance(value, (int, float)):
                thresholds[str(key)] = float(value)

    tool_capability_map = load_tool_capability_map(args.kg_path)

    run_metrics = [
        extract_run_metrics(
            row,
            tool_capability_map=tool_capability_map,
            requirement2_capability_map=requirement2_capability_map,
        )
        for row in runs
        if isinstance(row, dict)
    ]

    aggregated = aggregate_group_metrics(
        run_metrics,
        group_order=group_order,
        iterations=max(100, args.bootstrap_iterations),
        seed=args.seed,
        thresholds=thresholds,
        requirement2_capability_map=requirement2_capability_map,
    )

    delta_metrics = [
        "success",
        "first_pass_success",
        "schema_valid",
        "executable_plan",
        "patch_event_count",
        "replan_event_count",
        "duration_ms",
    ]
    delta_rows = []
    for metric in delta_metrics:
        delta_rows.extend(
            compute_increment_deltas(
                run_metrics,
                group_order=group_order,
                metric_key=metric,
                iterations=max(100, args.bootstrap_iterations),
                seed=args.seed + len(delta_rows),
            )
        )

    output_dir = args.output_dir or args.run_manifest_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    summary_rows = aggregated["summary_rows"]
    patch_rows = aggregated["patch_rows"]
    requirement2_rows = aggregated["requirement2_rows"]
    abnormal_rows = aggregated["abnormal_rows"]
    gate_rows = aggregated["gate_rows"]

    write_jsonl(output_dir / "run_metrics.jsonl", run_metrics)

    summary_fields = [
        "group_id",
        "runs",
        "success_rate",
        "success_ci_low",
        "success_ci_high",
        "first_pass_success_rate",
        "first_pass_ci_low",
        "first_pass_ci_high",
        "schema_valid_rate",
        "schema_ci_low",
        "schema_ci_high",
        "executable_plan_rate",
        "executable_ci_low",
        "executable_ci_high",
        "waiting_chain_complete_rate",
        "failure_traceable_rate",
        "patch_events_mean",
        "patch_events_ci_low",
        "patch_events_ci_high",
        "replan_events_mean",
        "replan_events_ci_low",
        "replan_events_ci_high",
        "suffix_replan_events_mean",
        "suffix_replan_events_ci_low",
        "suffix_replan_events_ci_high",
        "duration_ms_mean",
        "duration_ms_ci_low",
        "duration_ms_ci_high",
        "patch_minimality_hit_rate",
        "suffix_replan_prefix_preservation_rate",
        "requirement2_sequence_core",
        "requirement2_quality_qc",
        "requirement2_objective_scoring",
        "requirement2_structure_prediction",
    ]
    write_csv(output_dir / "vertical_metrics_summary.csv", summary_rows, summary_fields)
    write_json(output_dir / "vertical_metrics_summary.json", summary_rows)

    patch_fields = [
        "group_id",
        "patch_events_total",
        "replan_events_total",
        "suffix_replan_events_total",
        "patch_parameter_level",
        "patch_tool_level",
        "patch_structure_level",
        "patch_minimality_hit_rate",
        "suffix_prefix_sample_size",
        "suffix_prefix_preservation_rate",
    ]
    write_csv(output_dir / "patch_replan_breakdown.csv", patch_rows, patch_fields)

    requirement2_fields = ["group_id", "slice_type", "name", "covered", "usage_count"]
    write_csv(
        output_dir / "requirement2_tool_capability_slices.csv",
        requirement2_rows,
        requirement2_fields,
    )

    delta_fields = [
        "from_group",
        "to_group",
        "metric",
        "delta",
        "ci_low",
        "ci_high",
        "sample_size",
        "pairing",
    ]
    write_csv(output_dir / "mechanism_increment_deltas.csv", delta_rows, delta_fields)

    abnormal_fields = [
        "run_id",
        "task_id",
        "group_id",
        "replicate",
        "reason",
        "final_status",
        "event_log_path",
    ]
    write_csv(output_dir / "abnormal_samples.csv", abnormal_rows, abnormal_fields)
    write_jsonl(output_dir / "abnormal_samples.jsonl", abnormal_rows)

    gate_payload = {
        "generated_at": now_iso(),
        "thresholds": thresholds,
        "groups": gate_rows,
    }
    write_json(output_dir / "offline_gate_assessment.json", gate_payload)

    log_index_rows = [
        {
            "run_id": row.get("run_id"),
            "task_id": row.get("task_id"),
            "group_id": row.get("group_id"),
            "replicate": row.get("replicate"),
            "task_key": row.get("task_key"),
            "final_status": row.get("final_status"),
            "event_log_path": row.get("event_log_path"),
            "snapshot_path": row.get("snapshot_path"),
            "report_path": row.get("report_path"),
            "freeze_id": row.get("freeze_id"),
        }
        for row in run_metrics
    ]
    log_index_fields = [
        "run_id",
        "task_id",
        "group_id",
        "replicate",
        "task_key",
        "final_status",
        "event_log_path",
        "snapshot_path",
        "report_path",
        "freeze_id",
    ]
    write_csv(output_dir / "run_log_index.csv", log_index_rows, log_index_fields)

    markdown = build_markdown_report(
        issue_id=int(manifest.get("issue_id") or 171),
        run_manifest_path=args.run_manifest_path,
        freeze_id=str(manifest.get("freeze_id") or "UNKNOWN"),
        summary_rows=summary_rows,
        delta_rows=delta_rows,
        gate_rows=gate_rows,
        generated_at=now_iso(),
    )
    (output_dir / "vertical_report.md").write_text(markdown, encoding="utf-8")

    print(f"[issue171] evaluated_runs={len(run_metrics)}")
    print(f"[issue171] output_dir={output_dir}")
    print(f"[issue171] summary_csv={output_dir / 'vertical_metrics_summary.csv'}")
    print(f"[issue171] log_index={output_dir / 'run_log_index.csv'}")
    print(f"[issue171] abnormal_samples={output_dir / 'abnormal_samples.jsonl'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
