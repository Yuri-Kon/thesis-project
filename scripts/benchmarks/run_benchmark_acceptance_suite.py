#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.infra.benchmark_acceptance_suite import run_issue200_acceptance_suite


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the one-click local benchmark acceptance suite."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/experiments/benchmark_platform_adapters.json"),
        help="Benchmark platform adapter config path.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help="Override output root.",
    )
    parser.add_argument(
        "--freeze-id",
        type=str,
        default=None,
        help="Override freeze id for generated suite artifacts.",
    )
    parser.add_argument(
        "pytest_args",
        nargs="*",
        help="Optional pytest args overriding the default focused benchmark suites.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    suite_report, output_dir = run_issue200_acceptance_suite(
        config_path=args.config,
        output_root=args.output_root,
        freeze_id=args.freeze_id,
        pytest_args=args.pytest_args or None,
    )
    print(f"[benchmark-suite] overall_status={suite_report['overall_status']}")
    print(f"[benchmark-suite] freeze_id={suite_report['freeze_id']}")
    print(f"[benchmark-suite] output_dir={output_dir}")
    print(f"[benchmark-suite] suite_report={suite_report['artifacts']['suite_report_path']}")
    print(f"[benchmark-suite] pytest_exit_code={suite_report['pytest']['exit_code']}")
    print(f"[benchmark-suite] gate_status={suite_report['gate']['status']}")
    print(f"[benchmark-suite] gate_summary={suite_report['gate']['gate_summary_path']}")
    print(f"[benchmark-suite] blockers={suite_report['gate']['blockers_path']}")
    return 1 if suite_report["overall_status"] == "block" else 0


if __name__ == "__main__":
    raise SystemExit(main())
