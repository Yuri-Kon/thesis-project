from __future__ import annotations

import argparse
from pathlib import Path

from src.tools.visualization.pipeline import run_visualization

PDB_ID = "1CRN"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download 1CRN PDB into output/demo/pdb/1crn.pdb",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing file if present.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    output_dir = repo_root / "output" / "demo"
    run_visualization(PDB_ID, output_dir, reuse_cache=not args.force)


if __name__ == "__main__":
    main()
