from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path


def _load_module():
    module_path = Path(__file__).resolve().parents[2] / "scripts" / "generate_midterm_experiment_pack.py"
    spec = importlib.util.spec_from_file_location("midterm_experiment_pack", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def test_build_issue174_pack_marks_horizontal_as_deferred(tmp_path: Path) -> None:
    module = _load_module()

    vertical_summary = tmp_path / "vertical_summary.csv"
    mechanism_deltas = tmp_path / "mechanism_deltas.csv"
    governance_summary = tmp_path / "governance_summary.json"
    governance_groups = tmp_path / "governance_groups.csv"
    output_dir = tmp_path / "out"

    _write_csv(
        vertical_summary,
        [
            {
                "group_id": "A0",
                "runs": "12",
                "success_rate": "0.0",
                "executable_plan_rate": "1.0",
                "patch_minimality_hit_rate": "1.0",
                "suffix_replan_prefix_preservation_rate": "",
                "duration_ms_mean": "2000.0",
            }
        ],
    )
    _write_csv(
        mechanism_deltas,
        [
            {
                "from_group": "A2",
                "to_group": "A3",
                "metric": "executable_plan",
                "delta": "1.0",
                "ci_low": "1.0",
                "ci_high": "1.0",
                "sample_size": "12",
                "pairing": "paired",
            }
        ],
    )
    governance_summary.write_text(
        json.dumps(
            {
                "global": {
                    "tasks": 84,
                    "failure_traceable_rate": 1.0,
                    "waiting_chain_complete_rate": 0.0,
                    "replay_success_rate": 0.0,
                }
            }
        ),
        encoding="utf-8",
    )
    _write_csv(
        governance_groups,
        [
            {
                "group_id": "A0",
                "tasks": "12",
                "waiting_chain_complete_rate": "0.0",
                "replay_success_rate": "0.0",
                "failure_traceable_rate": "1.0",
                "snapshot_linked_rate": "1.0",
            }
        ],
    )

    result = module.build_issue174_pack(
        vertical_summary_path=vertical_summary,
        mechanism_delta_path=mechanism_deltas,
        governance_summary_path=governance_summary,
        governance_groups_path=governance_groups,
        output_dir=output_dir,
        horizontal_note="external baseline comparison deferred for external dependency",
    )

    chapter_text = result["chapter"].read_text(encoding="utf-8")
    figure_rows = list(csv.DictReader(result["figure_index"].open("r", encoding="utf-8")))

    assert "external baseline comparison deferred for external dependency" in chapter_text
    assert any(row["artifact_id"] == "table-2" and row["status"] == "deferred" for row in figure_rows)
