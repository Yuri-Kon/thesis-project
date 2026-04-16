#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import platform
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_SUMMARY_CSV = Path(
    "output/experiment/w12-expr-2/issue171-remote-batch2-r1/vertical_metrics_summary.csv"
)
DEFAULT_SLICE_CSV = Path(
    "output/experiment/w12-expr-2/issue171-remote-batch2-r1/requirement2_tool_capability_slices.csv"
)
DEFAULT_OUTPUT_DIR = Path("output/experiment/w12-expr-2/issue149-offline-benchmark")
DEFAULT_CANDIDATE_VERSION = "v0.3.0-rc1"
DEFAULT_BASELINE_VERSION = "external-baseline-a0"
DEFAULT_SELF_GROUP = "A2"
DEFAULT_BASELINE_GROUP = "A0"

OFFLINE_THRESHOLDS: dict[str, float] = {
    "schema_valid_rate": 0.995,
    "executable_plan_rate": 0.95,
    "patch_minimality_hit_rate": 0.8,
    "suffix_replan_prefix_preservation_rate": 1.0,
}

METRIC_LABELS: dict[str, str] = {
    "schema_valid_rate": "Schema legal rate",
    "executable_plan_rate": "Executable plan rate",
    "patch_minimality_hit_rate": "Patch minimality hit rate",
    "suffix_replan_prefix_preservation_rate": "Suffix replan prefix retention rate",
}


@dataclass(frozen=True)
class GateCheck:
    metric: str
    threshold: float
    value: float | None
    passed: bool


@dataclass(frozen=True)
class BenchmarkComparison:
    metric: str
    self_value: float | None
    baseline_value: float | None
    delta: float | None


def _json_dump(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2)


def _str_value(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None
    return None


def _to_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False
    return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_json_dump(payload) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in fieldnames})


def _git_short_sha() -> str:
    try:
        return (
            subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True)
            .strip()
            .lower()
        )
    except Exception:
        return "nogit"


def load_group_metric_rows(path: Path) -> dict[str, dict[str, Any]]:
    rows = _read_csv(path)
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        group_id = _str_value(row.get("group_id"))
        if not group_id:
            continue
        grouped[group_id] = {**row}
    return grouped


def build_comparisons(
    *,
    self_row: dict[str, Any],
    baseline_row: dict[str, Any],
) -> list[BenchmarkComparison]:
    rows: list[BenchmarkComparison] = []
    for metric in OFFLINE_THRESHOLDS:
        self_value = _to_float(self_row.get(metric))
        baseline_value = _to_float(baseline_row.get(metric))
        delta = None
        if self_value is not None and baseline_value is not None:
            delta = self_value - baseline_value
        rows.append(
            BenchmarkComparison(
                metric=metric,
                self_value=self_value,
                baseline_value=baseline_value,
                delta=delta,
            )
        )
    return rows


def build_gate_checks(self_row: dict[str, Any]) -> list[GateCheck]:
    checks: list[GateCheck] = []
    for metric, threshold in OFFLINE_THRESHOLDS.items():
        value = _to_float(self_row.get(metric))
        passed = value is not None and value >= threshold
        checks.append(
            GateCheck(
                metric=metric,
                threshold=threshold,
                value=value,
                passed=passed,
            )
        )
    return checks


def build_slice_comparison(
    *,
    slice_rows: list[dict[str, str]],
    self_group: str,
    baseline_group: str,
) -> list[dict[str, Any]]:
    index: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in slice_rows:
        group_id = _str_value(row.get("group_id"))
        slice_type = _str_value(row.get("slice_type"))
        name = _str_value(row.get("name"))
        if not group_id or not slice_type or not name:
            continue
        index[(group_id, slice_type, name)] = row

    keys = sorted(
        {
            (slice_type, name)
            for group_id, slice_type, name in index
            if group_id in {self_group, baseline_group}
        }
    )

    rows: list[dict[str, Any]] = []
    for slice_type, name in keys:
        self_row = index.get((self_group, slice_type, name), {})
        baseline_row = index.get((baseline_group, slice_type, name), {})
        self_usage = _to_float(self_row.get("usage_count")) or 0.0
        baseline_usage = _to_float(baseline_row.get("usage_count")) or 0.0
        rows.append(
            {
                "slice_type": slice_type,
                "name": name,
                "self_covered": _to_bool(self_row.get("covered")),
                "baseline_covered": _to_bool(baseline_row.get("covered")),
                "self_usage_count": int(self_usage),
                "baseline_usage_count": int(baseline_usage),
                "usage_delta": int(self_usage - baseline_usage),
            }
        )
    return rows


def render_release_markdown(
    *,
    candidate_version: str,
    baseline_version: str,
    self_group: str,
    baseline_group: str,
    comparisons: list[BenchmarkComparison],
    gate_checks: list[GateCheck],
    slice_rows: list[dict[str, Any]],
    generated_at: str,
    summary_csv: Path,
    slice_csv: Path,
) -> str:
    overall_pass = all(item.passed for item in gate_checks)

    lines = [
        "# release-benchmark",
        "",
        "## Benchmark Target",
        f"- Candidate: `{candidate_version}` (group `{self_group}`)",
        f"- Baseline: `{baseline_version}` (group `{baseline_group}`)",
        f"- Generated at: `{generated_at}`",
        "",
        "## Reproducibility",
        f"- Summary input: `{summary_csv}`",
        f"- Slice input: `{slice_csv}`",
        f"- Command: `python scripts/evaluate_w12_issue149_offline_benchmark.py --summary-csv {summary_csv} --slice-csv {slice_csv} --self-group {self_group} --baseline-group {baseline_group}`",
        "",
        "## Metric Definitions",
        "- Schema legal rate: valid schema runs / total runs in group.",
        "- Executable plan rate: runs without step execution failure / total runs in group.",
        "- Patch minimality hit rate: parameter-level patch events / all patch events (null when patch events are zero).",
        "- Suffix replan prefix retention rate: suffix-replan runs preserving successful prefix / suffix-replan runs (null when no suffix-replan samples).",
        "- Missing value handling: if metric is null, gate check fails and release is blocked.",
        "",
        "## Candidate vs Baseline",
        "| metric | candidate | baseline | delta |",
        "|---|---:|---:|---:|",
    ]

    for item in comparisons:
        lines.append(
            "| {label} | {self_v} | {base_v} | {delta} |".format(
                label=METRIC_LABELS[item.metric],
                self_v="-" if item.self_value is None else f"{item.self_value:.6f}",
                base_v="-" if item.baseline_value is None else f"{item.baseline_value:.6f}",
                delta="-" if item.delta is None else f"{item.delta:+.6f}",
            )
        )

    lines.extend([
        "",
        "## RC Gate-B",
        "| metric | threshold | candidate | pass |",
        "|---|---:|---:|---:|",
    ])

    blocked_reasons: list[str] = []
    for item in gate_checks:
        value_text = "-" if item.value is None else f"{item.value:.6f}"
        pass_text = "yes" if item.passed else "no"
        lines.append(
            f"| {METRIC_LABELS[item.metric]} | {item.threshold:.6f} | {value_text} | {pass_text} |"
        )
        if not item.passed:
            blocked_reasons.append(
                f"{METRIC_LABELS[item.metric]} below threshold ({value_text} < {item.threshold:.6f})"
            )

    lines.extend(["", "## Tool Coverage vs Metrics", "| slice_type | name | candidate covered | baseline covered | candidate usage | baseline usage | usage delta |", "|---|---|---:|---:|---:|---:|---:|"])
    for row in slice_rows:
        lines.append(
            "| {slice_type} | {name} | {self_cov} | {base_cov} | {self_use} | {base_use} | {delta:+d} |".format(
                slice_type=row["slice_type"],
                name=row["name"],
                self_cov="yes" if row.get("self_covered") else "no",
                base_cov="yes" if row.get("baseline_covered") else "no",
                self_use=int(row.get("self_usage_count", 0)),
                base_use=int(row.get("baseline_usage_count", 0)),
                delta=int(row.get("usage_delta", 0)),
            )
        )

    lines.extend(["", "## Release Decision"]) 
    if overall_pass:
        lines.append("- Decision: pass RC Gate-B; release is not blocked by offline thresholds.")
    else:
        lines.append("- Decision: block release due to unmet offline thresholds.")
        for reason in blocked_reasons:
            lines.append(f"- Blocker: {reason}")

    lines.append("")
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate Issue #149 offline benchmark (candidate vs external baseline)."
    )
    parser.add_argument("--summary-csv", type=Path, default=DEFAULT_SUMMARY_CSV)
    parser.add_argument("--slice-csv", type=Path, default=DEFAULT_SLICE_CSV)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--self-group", type=str, default=DEFAULT_SELF_GROUP)
    parser.add_argument("--baseline-group", type=str, default=DEFAULT_BASELINE_GROUP)
    parser.add_argument("--candidate-version", type=str, default=DEFAULT_CANDIDATE_VERSION)
    parser.add_argument("--baseline-version", type=str, default=DEFAULT_BASELINE_VERSION)
    return parser


def main() -> int:
    args = _build_parser().parse_args()

    group_rows = load_group_metric_rows(args.summary_csv)
    self_row = group_rows.get(args.self_group)
    baseline_row = group_rows.get(args.baseline_group)
    if self_row is None:
        raise ValueError(f"self group not found in summary csv: {args.self_group}")
    if baseline_row is None:
        raise ValueError(f"baseline group not found in summary csv: {args.baseline_group}")

    comparisons = build_comparisons(self_row=self_row, baseline_row=baseline_row)
    gate_checks = build_gate_checks(self_row)
    slice_rows = build_slice_comparison(
        slice_rows=_read_csv(args.slice_csv),
        self_group=args.self_group,
        baseline_group=args.baseline_group,
    )

    generated_at = _now_iso()
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    comparison_rows = [
        {
            "metric": item.metric,
            "metric_label": METRIC_LABELS[item.metric],
            "candidate_value": item.self_value,
            "baseline_value": item.baseline_value,
            "delta": item.delta,
        }
        for item in comparisons
    ]
    gate_rows = [
        {
            "metric": item.metric,
            "metric_label": METRIC_LABELS[item.metric],
            "threshold": item.threshold,
            "candidate_value": item.value,
            "passed": item.passed,
        }
        for item in gate_checks
    ]

    _write_csv(
        output_dir / "release_benchmark_comparison.csv",
        comparison_rows,
        ["metric", "metric_label", "candidate_value", "baseline_value", "delta"],
    )
    _write_csv(
        output_dir / "release_benchmark_gate_checks.csv",
        gate_rows,
        ["metric", "metric_label", "threshold", "candidate_value", "passed"],
    )
    _write_csv(
        output_dir / "tool_coverage_vs_metrics.csv",
        slice_rows,
        [
            "slice_type",
            "name",
            "self_covered",
            "baseline_covered",
            "self_usage_count",
            "baseline_usage_count",
            "usage_delta",
        ],
    )

    payload = {
        "issue": 149,
        "generated_at": generated_at,
        "candidate_version": args.candidate_version,
        "baseline_version": args.baseline_version,
        "self_group": args.self_group,
        "baseline_group": args.baseline_group,
        "summary_csv": str(args.summary_csv),
        "slice_csv": str(args.slice_csv),
        "thresholds": OFFLINE_THRESHOLDS,
        "comparisons": comparison_rows,
        "gate_checks": gate_rows,
        "tool_slice_rows": slice_rows,
        "release_blocked": not all(item.passed for item in gate_checks),
        "reproducibility": {
            "command": " ".join(sys.argv),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "git_short_sha": _git_short_sha(),
        },
    }
    _write_json(output_dir / "release_benchmark.json", payload)

    markdown = render_release_markdown(
        candidate_version=args.candidate_version,
        baseline_version=args.baseline_version,
        self_group=args.self_group,
        baseline_group=args.baseline_group,
        comparisons=comparisons,
        gate_checks=gate_checks,
        slice_rows=slice_rows,
        generated_at=generated_at,
        summary_csv=args.summary_csv,
        slice_csv=args.slice_csv,
    )
    (output_dir / "release-benchmark.md").write_text(markdown, encoding="utf-8")

    print(_json_dump({"output_dir": str(output_dir), "release_blocked": payload["release_blocked"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
