#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.infra.w16_issue222_integration_analysis import (
    DEFAULT_ISSUE222_KG_PATH,
    load_and_analyze_issue222_results,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate issue #222 overall and stratified integration analysis."
    )
    parser.add_argument(
        "--run-manifest-path",
        type=Path,
        required=True,
        help="Path to issue #221 runs_manifest.json.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory for issue #222 artifacts. Defaults to run manifest directory.",
    )
    parser.add_argument(
        "--kg-path",
        type=Path,
        default=DEFAULT_ISSUE222_KG_PATH,
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
        default=20260417,
        help="Random seed for bootstrap resampling.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir or args.run_manifest_path.parent / "issue222-analysis"
    result = load_and_analyze_issue222_results(
        run_manifest_path=args.run_manifest_path,
        output_dir=output_dir,
        kg_path=args.kg_path,
        bootstrap_iterations=args.bootstrap_iterations,
        seed=args.seed,
    )

    print(f"[issue222] analyzed_runs={len(result['run_level_results'])}")
    print(f"[issue222] output_dir={output_dir}")
    print(f"[issue222] overall_csv={output_dir / 'overall_metrics.csv'}")
    print(
        f"[issue222] stratified_csv={output_dir / 'difficulty_stratified_metrics.csv'}"
    )
    print(f"[issue222] chart_rows={output_dir / 'chart_summary_rows.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
