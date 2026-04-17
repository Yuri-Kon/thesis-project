#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.infra.w12_vertical_experiment import load_json
from src.infra.w16_issue221_experiment_matrix import (
    DEFAULT_ISSUE221_CONFIG_PATH,
    build_issue221_run_manifest,
    load_issue221_selection,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run issue #221 four-group unified experiment matrix."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_ISSUE221_CONFIG_PATH,
        help="Issue #221 matrix config JSON path.",
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
        "--selection-manifest-path",
        type=Path,
        default=None,
        help="Optional rerun selection JSON path.",
    )
    parser.add_argument(
        "--dry-run",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Only materialize matrix artifacts without executing tasks.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_json(args.config)
    selection = (
        load_issue221_selection(args.selection_manifest_path)
        if args.selection_manifest_path is not None
        else None
    )
    manifest, run_dir = build_issue221_run_manifest(
        config=config,
        config_path=args.config,
        output_root=args.output_root,
        run_id=args.run_id,
        repeats_override=args.repeats,
        max_runs=args.max_runs,
        dry_run=args.dry_run,
        selection=selection,
    )

    print(f"[issue221] run_id={manifest['run_id']}")
    print(f"[issue221] freeze_id={manifest['freeze_id']}")
    print(f"[issue221] runs={len(manifest['runs'])}")
    print(f"[issue221] manifest={run_dir / 'runs_manifest.json'}")
    print(f"[issue221] log_index={run_dir / 'run_log_index.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
