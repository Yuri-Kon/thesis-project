from __future__ import annotations

import pytest

from src.adapters.structure_projection import normalize_structure_projection_outputs
from src.workflow.errors import StepRunError


def test_normalize_structure_projection_outputs_with_metrics_only() -> None:
    outputs = normalize_structure_projection_outputs(
        {
            "pdb_path": "/tmp/a.pdb",
            "metrics": {"plddt_mean": 0.87},
        },
        tool_id="esmfold",
    )
    assert outputs["stage_id"] == "S2"
    assert outputs["plddt"] == 0.87
    assert outputs["confidence"]["level"] == "high"
    assert outputs["lineage"]["tool_id"] == "esmfold"


def test_normalize_structure_projection_outputs_requires_pdb_and_plddt() -> None:
    with pytest.raises(StepRunError):
        normalize_structure_projection_outputs(
            {"metrics": {"plddt_mean": 0.2}},
            tool_id="esmfold",
        )

    with pytest.raises(StepRunError):
        normalize_structure_projection_outputs(
            {"pdb_path": "/tmp/a.pdb"},
            tool_id="esmfold",
        )
