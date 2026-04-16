from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

import pytest


SCRIPT_PATH = Path("scripts/evaluate_w12_issue149_offline_benchmark.py")


def _load_script_module():
    spec = importlib.util.spec_from_file_location("evaluate_w12_issue149_offline_benchmark", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


@pytest.mark.unit
def test_build_comparisons_and_gate_checks() -> None:
    module = _load_script_module()
    self_row = {
        "schema_valid_rate": "0.996",
        "executable_plan_rate": "0.960",
        "patch_minimality_hit_rate": "0.750",
        "suffix_replan_prefix_preservation_rate": "1.0",
    }
    baseline_row = {
        "schema_valid_rate": "0.990",
        "executable_plan_rate": "0.940",
        "patch_minimality_hit_rate": "0.700",
        "suffix_replan_prefix_preservation_rate": "0.950",
    }

    comparisons = module.build_comparisons(self_row=self_row, baseline_row=baseline_row)
    checks = module.build_gate_checks(self_row)

    by_metric = {item.metric: item for item in comparisons}
    assert by_metric["schema_valid_rate"].delta == pytest.approx(0.006)
    assert by_metric["patch_minimality_hit_rate"].delta == pytest.approx(0.05)

    checks_by_metric = {item.metric: item for item in checks}
    assert checks_by_metric["schema_valid_rate"].passed is True
    assert checks_by_metric["patch_minimality_hit_rate"].passed is False


@pytest.mark.unit
def test_build_slice_comparison_aligns_groups() -> None:
    module = _load_script_module()
    rows = [
        {
            "group_id": "A2",
            "slice_type": "capability_bucket",
            "name": "sequence_core",
            "covered": "True",
            "usage_count": "12",
        },
        {
            "group_id": "A0",
            "slice_type": "capability_bucket",
            "name": "sequence_core",
            "covered": "False",
            "usage_count": "3",
        },
    ]

    compared = module.build_slice_comparison(
        slice_rows=rows,
        self_group="A2",
        baseline_group="A0",
    )

    assert len(compared) == 1
    row = compared[0]
    assert row["self_covered"] is True
    assert row["baseline_covered"] is False
    assert row["usage_delta"] == 9


@pytest.mark.unit
def test_load_group_metric_rows_reads_by_group(tmp_path: Path) -> None:
    module = _load_script_module()
    csv_path = tmp_path / "summary.csv"
    _write_csv(
        csv_path,
        ["group_id", "schema_valid_rate"],
        [
            {"group_id": "A0", "schema_valid_rate": 1.0},
            {"group_id": "A2", "schema_valid_rate": 0.99},
        ],
    )

    grouped = module.load_group_metric_rows(csv_path)

    assert set(grouped) == {"A0", "A2"}
    assert grouped["A0"]["schema_valid_rate"] == "1.0"


@pytest.mark.unit
def test_render_release_markdown_reports_blockers() -> None:
    module = _load_script_module()
    comparisons = [
        module.BenchmarkComparison(
            metric="schema_valid_rate",
            self_value=0.99,
            baseline_value=0.98,
            delta=0.01,
        )
    ]
    checks = [
        module.GateCheck(
            metric="schema_valid_rate",
            threshold=0.995,
            value=0.99,
            passed=False,
        )
    ]
    markdown = module.render_release_markdown(
        candidate_version="v0.3.0-rc1",
        baseline_version="baseline-a0",
        self_group="A2",
        baseline_group="A0",
        comparisons=comparisons,
        gate_checks=checks,
        slice_rows=[],
        generated_at="2026-03-16T00:00:00+00:00",
        summary_csv=Path("summary.csv"),
        slice_csv=Path("slice.csv"),
    )

    assert "block release" in markdown
    assert "below threshold" in markdown
