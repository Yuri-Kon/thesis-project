#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.infra.issue200_acceptance_gate import run_issue200_acceptance_gate
from src.infra.w12_vertical_experiment import load_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Issue #200 acceptance gate for benchmark/tool freeze consistency."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/experiments/issue199_benchmark_platform_adapters.json"),
        help="Issue #199/#200 shared freeze config path.",
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
        help="Override freeze id for generated gate artifacts.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_json(args.config)
    report, output_dir = run_issue200_acceptance_gate(
        config=config,
        config_path=args.config,
        output_root=args.output_root,
        freeze_id=args.freeze_id,
    )
    print(f"[issue200] overall_status={report['overall_status']}")
    print(f"[issue200] freeze_id={report['freeze_id']}")
    print(f"[issue200] output_dir={output_dir}")
    print(f"[issue200] report={report['artifacts']['json_report_path']}")
    print(f"[issue200] summary={report['artifacts']['markdown_summary_path']}")
    for check in report["checks"]:
        if check["status"] == "block":
            print(f"[issue200] block {check['check_id']}: {check['message']}")
    return 1 if report["overall_status"] == "block" else 0


if __name__ == "__main__":
    raise SystemExit(main())
