#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.infra.benchmark_platform_adapters import (
    build_issue199_platform_adapter_bundle,
    load_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare Issue #199 Inspect/MLflow/promptfoo benchmark platform adapters."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/experiments/issue199_benchmark_platform_adapters.json"),
        help="Issue #199 adapter freeze config path.",
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
        help="Override freeze id.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_json(args.config)
    manifest, output_dir = build_issue199_platform_adapter_bundle(
        config=config,
        output_root=args.output_root,
        freeze_id=args.freeze_id,
    )
    print(f"[issue199] freeze_id={manifest['freeze_id']}")
    print(f"[issue199] output_dir={output_dir}")
    print(f"[issue199] manifest={output_dir / 'issue199_platform_adapter_manifest.json'}")
    print(f"[issue199] report={output_dir / 'issue199_platform_adapter_report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
