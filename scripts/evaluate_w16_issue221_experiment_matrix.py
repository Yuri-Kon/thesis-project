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
    DEFAULT_ISSUE221_KG_PATH,
    evaluate_issue221_run_manifest,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate issue #221 four-group unified experiment outputs."
    )
    parser.add_argument(
        "--run-manifest-path",
        type=Path,
        required=True,
        help="Path to runs_manifest.json produced by the issue221 runner.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Optional output directory. Defaults to run manifest directory.",
    )
    parser.add_argument(
        "--kg-path",
        type=Path,
        default=DEFAULT_ISSUE221_KG_PATH,
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
        default=20260416,
        help="Random seed for bootstrap resampling.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = load_json(args.run_manifest_path)
    output_dir = args.output_dir or args.run_manifest_path.parent
    result = evaluate_issue221_run_manifest(
        manifest=manifest,
        output_dir=output_dir,
        kg_path=args.kg_path,
        bootstrap_iterations=args.bootstrap_iterations,
        seed=args.seed,
    )

    print(f"[issue221] evaluated_runs={len(result['run_level_results'])}")
    print(f"[issue221] output_dir={output_dir}")
    print(f"[issue221] summary_csv={output_dir / 'matrix_metrics_summary.csv'}")
    print(f"[issue221] rerun_candidates={output_dir / 'rerun_candidates.json'}")
    print(f"[issue221] evidence_index={output_dir / 'evidence_index.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
