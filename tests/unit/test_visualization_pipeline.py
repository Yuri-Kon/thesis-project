from __future__ import annotations

import json
from pathlib import Path

from src.tools.visualization.pipeline import run_visualization


def test_run_visualization_generates_artifacts(tmp_path: Path) -> None:
    fixture_path = Path(__file__).resolve().parents[1] / "fixtures" / "1crn.pdb"
    out_dir = tmp_path / "visualization"

    artifacts = run_visualization(str(fixture_path), out_dir, reuse_cache=True)

    assert artifacts.metrics_json_path.exists()
    assert artifacts.plotly_html_path.exists()
    assert artifacts.report_html_path.exists()

    metrics = json.loads(artifacts.metrics_json_path.read_text(encoding="utf-8"))
    assert "chain_ids" in metrics
    assert "residue_count" in metrics
    assert "per_residue_bfactor_avg" in metrics
