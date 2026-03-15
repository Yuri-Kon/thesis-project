#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _json_dump(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True)


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def _default_dataset_version() -> str:
    try:
        short_sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        short_sha = "unknown"
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"w11-sft-dataset-v1.1-{day}-{short_sha}-r02"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Release pipeline for SFT dataset v1.1: "
            "extract -> quality gate -> req2 addon -> quality gate -> freeze."
        ),
    )
    parser.add_argument("--logs-dir", type=Path, default=Path("data/logs"))
    parser.add_argument("--snapshots-dir", type=Path, default=Path("data/snapshots"))
    parser.add_argument("--reports-dir", type=Path, default=Path("output/reports"))
    parser.add_argument("--metrics-dir", type=Path, default=Path("output/metrics"))
    parser.add_argument("--tool-kg-path", type=Path, default=Path("src/kg/protein_tool_kg.json"))
    parser.add_argument(
        "--tool-extension-kg-path",
        type=Path,
        default=Path("src/kg/protein_tool_kg/extension_draft_v0.1.json"),
    )
    parser.add_argument("--base-output-dir", type=Path, default=Path("output/training/w11-data-1"))
    parser.add_argument("--base-gate-output-dir", type=Path, default=Path("output/training/w11-data-2"))
    parser.add_argument("--addon-output-dir", type=Path, default=Path("output/training/w11-data-3"))
    parser.add_argument("--freeze-output-root", type=Path, default=Path("output/dataset_v1"))
    parser.add_argument("--dataset-version", type=str, default=None)
    parser.add_argument(
        "--previous-manifest-path",
        type=Path,
        default=Path("output/dataset_v1/w11-sft-dataset-v1-20260315-0ce8eb8/manifest.json"),
    )
    parser.add_argument(
        "--allow-missing-p0-core",
        action="store_true",
        help="Do not fail release when Requirement2 P0 core coverage is missing.",
    )
    parser.add_argument(
        "--skip-extract",
        action="store_true",
        help="Reuse existing output/training/w11-data-1 artifacts.",
    )
    parser.add_argument(
        "--skip-base-gate",
        action="store_true",
        help="Reuse existing output/training/w11-data-2 artifacts.",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    dataset_version = args.dataset_version or _default_dataset_version()
    python_exe = sys.executable

    if not args.skip_extract:
        _run(
            [
                python_exe,
                "scripts/extract_training_samples.py",
                "--logs-dir",
                str(args.logs_dir),
                "--snapshots-dir",
                str(args.snapshots_dir),
                "--reports-dir",
                str(args.reports_dir),
                "--metrics-dir",
                str(args.metrics_dir),
                "--tool-kg-path",
                str(args.tool_kg_path),
                "--tool-extension-kg-path",
                str(args.tool_extension_kg_path),
                "--output-dir",
                str(args.base_output_dir),
            ]
        )

    if not args.skip_base_gate:
        _run(
            [
                python_exe,
                "scripts/quality_gate_training_data.py",
                "--samples-path",
                str(args.base_output_dir / "samples.jsonl"),
                "--output-dir",
                str(args.base_gate_output_dir),
                "--split-strategy",
                "time",
                "--plddt-min",
                "0.70",
                "--score-completeness-min",
                "0.80",
            ]
        )

    _run(
        [
            python_exe,
            "scripts/augment_requirement2_coverage.py",
            "--base-samples-path",
            str(args.base_output_dir / "samples.jsonl"),
            "--base-gated-path",
            str(args.base_gate_output_dir / "gated_samples.jsonl"),
            "--output-dir",
            str(args.addon_output_dir),
            "--tool-kg-path",
            str(args.tool_kg_path),
            "--tool-extension-kg-path",
            str(args.tool_extension_kg_path),
        ]
    )

    _run(
        [
            python_exe,
            "scripts/quality_gate_training_data.py",
            "--samples-path",
            str(args.addon_output_dir / "samples_with_addons.jsonl"),
            "--output-dir",
            str(args.addon_output_dir),
            "--split-strategy",
            "time",
            "--plddt-min",
            "0.70",
            "--score-completeness-min",
            "0.80",
        ]
    )

    freeze_cmd = [
        python_exe,
        "scripts/freeze_sft_dataset_v1.py",
        "--gated-samples-path",
        str(args.addon_output_dir / "gated_samples.jsonl"),
        "--quality-report-path",
        str(args.addon_output_dir / "quality_gate_report.json"),
        "--output-root",
        str(args.freeze_output_root),
        "--dataset-version",
        dataset_version,
        "--tool-kg-path",
        str(args.tool_kg_path),
        "--tool-extension-kg-path",
        str(args.tool_extension_kg_path),
        "--previous-manifest-path",
        str(args.previous_manifest_path),
    ]
    if not args.allow_missing_p0_core:
        freeze_cmd.append("--fail-on-missing-p0-core")
    _run(freeze_cmd)

    manifest_path = args.freeze_output_root / dataset_version / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    print("SFT dataset v1.1 release completed")
    print(
        _json_dump(
            {
                "dataset_version": dataset_version,
                "manifest_path": str(manifest_path),
                "p0_core_coverage_satisfied": manifest["requirement2"]["p0_core_minimum_coverage"]["satisfied"],
                "delta_from_previous": "delta_from_previous" in manifest,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
