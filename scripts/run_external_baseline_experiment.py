#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from contextlib import contextmanager
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.infra.w12_vertical_experiment import load_json
from src.infra.external_baseline_experiment import (
    DEFAULT_ISSUE172_CONFIG_PATH,
    DEFAULT_ISSUE172_KG_PATH,
    build_issue172_run_manifest,
    evaluate_issue172_run_manifest,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the external baseline comparison experiment."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_ISSUE172_CONFIG_PATH,
        help="External baseline experiment config JSON path.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help="Optional output root override.",
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
        help="Optional cap for total runs.",
    )
    parser.add_argument(
        "--dry-run",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Only materialize matrix artifacts without executing tasks.",
    )
    parser.add_argument(
        "--evaluate",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Evaluate run-level outputs after execution or dry-run materialization.",
    )
    parser.add_argument(
        "--kg-path",
        type=Path,
        default=DEFAULT_ISSUE172_KG_PATH,
        help="ProteinToolKG path used for automatic evaluation.",
    )
    parser.add_argument(
        "--bootstrap-iterations",
        type=int,
        default=10000,
        help="Bootstrap iterations for post-run evaluation.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=20260420,
        help="Random seed for post-run evaluation.",
    )
    parser.add_argument(
        "--planner-provider",
        type=str,
        default=None,
        help="Optional planner provider alias override for this run.",
    )
    parser.add_argument(
        "--internal-summary-path",
        type=Path,
        default=None,
        help="Optional internal reference summary CSV override.",
    )
    return parser.parse_args()


@contextmanager
def _temporary_env(name: str, value: str | None):
    original = os.getenv(name)
    try:
        if value is None:
            yield
            return
        os.environ[name] = value
        yield
    finally:
        if value is None:
            return
        if original is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = original


def main() -> int:
    args = parse_args()
    with _temporary_env("PLANNER_LLM_PROVIDER", args.planner_provider):
        config = load_json(args.config)
        manifest, run_dir = build_issue172_run_manifest(
            config=config,
            config_path=args.config,
            output_root=args.output_root,
            run_id=args.run_id,
            repeats_override=args.repeats,
            max_runs=args.max_runs,
            dry_run=args.dry_run,
            provider_alias=args.planner_provider,
        )
        print(f"[external-baseline] run_id={manifest['run_id']}")
        print(f"[external-baseline] freeze_id={manifest['freeze_id']}")
        print(f"[external-baseline] runs={len(manifest['runs'])}")
        print(f"[external-baseline] manifest={run_dir / 'runs_manifest.json'}")
        print(f"[external-baseline] log_index={run_dir / 'run_log_index.csv'}")
        if args.planner_provider:
            print(f"[external-baseline] planner_provider={args.planner_provider}")
        if args.evaluate:
            result = evaluate_issue172_run_manifest(
                manifest=manifest,
                output_dir=run_dir,
                kg_path=args.kg_path,
                bootstrap_iterations=args.bootstrap_iterations,
                seed=args.seed,
                internal_summary_path=args.internal_summary_path,
            )
            print(f"[external-baseline] evaluated_runs={len(result['run_level_results'])}")
            print(f"[external-baseline] summary_csv={run_dir / 'horizontal_metrics_summary.csv'}")
            print(f"[external-baseline] validation_summary={run_dir / 'validation_summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
