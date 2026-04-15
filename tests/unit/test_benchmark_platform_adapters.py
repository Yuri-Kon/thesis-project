from __future__ import annotations

import json
from pathlib import Path

from src.infra.benchmark_platform_adapters import (
    build_issue199_platform_adapter_bundle,
    build_promptfoo_react_payload,
    load_json,
)


def test_issue199_bundle_writes_expected_artifacts(tmp_path: Path) -> None:
    manifest, output_dir = build_issue199_platform_adapter_bundle(
        config=load_json(Path("configs/experiments/issue199_benchmark_platform_adapters.json")),
        output_root=tmp_path,
        freeze_id="issue199-test-freeze",
    )

    assert manifest["freeze_id"] == "issue199-test-freeze"
    assert (output_dir / "issue199_platform_adapter_manifest.json").exists()
    assert (output_dir / "issue199_platform_adapter_report.md").exists()
    assert (output_dir / "inspect_ai" / "inspect_react_samples.jsonl").exists()
    assert (output_dir / "inspect_ai" / "inspect_issue199_react_smoke.py").exists()
    assert (output_dir / "promptfoo" / "promptfooconfig.yaml").exists()
    assert (output_dir / "promptfoo" / "promptfoo_react_provider.py").exists()
    assert (output_dir / "standardized" / "normalized_run.sample.json").exists()
    assert (output_dir / "standardized" / "summary_row.sample.json").exists()
    assert (output_dir / "standardized" / "evidence-index.sample.json").exists()

    promptfoo_config = (output_dir / "promptfoo" / "promptfooconfig.yaml").read_text(
        encoding="utf-8"
    )
    inspect_task = (output_dir / "inspect_ai" / "inspect_issue199_react_smoke.py").read_text(
        encoding="utf-8"
    )
    report_text = (output_dir / "issue199_platform_adapter_report.md").read_text(
        encoding="utf-8"
    )
    inspect_manifest = json.loads(
        (output_dir / "inspect_ai" / "inspect_eval_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    inspect_samples = (output_dir / "inspect_ai" / "inspect_react_samples.jsonl").read_text(
        encoding="utf-8"
    )
    assert "prompts:" in promptfoo_config
    assert "provider_alias: baseline" in promptfoo_config
    assert "metric: quality_rubric" in promptfoo_config
    assert "issue199_adapter_contract" in inspect_task
    assert "Allowlisted tools:" in inspect_samples
    assert "protgpt2" in inspect_samples
    assert "## Validation Coverage" in report_text
    assert "Inspect AI" in report_text
    assert "promptfoo" in report_text
    assert "inspect info version" in inspect_manifest["suggested_commands"][0]
    assert "uv tool run --from inspect-ai --with openai inspect eval" in inspect_manifest["suggested_commands"][1]


def test_promptfoo_payload_uses_provider_catalog_and_budget_fields() -> None:
    payload = build_promptfoo_react_payload(
        prompt="Design a compact enzyme-like fold.",
        provider_alias="baseline",
        catalog_path=Path("configs/llm_providers.json"),
        max_plan_steps=3,
        max_high_cost_steps=1,
        high_cost_tool_ids=["esmfold", "openfold2", "protein_mpnn"],
        allowed_tool_ids=[
            "protgpt2",
            "biopython_qc",
            "dssp",
            "objective_ranker",
            "esmfold",
            "openfold2",
            "protein_mpnn",
        ],
        task_id="issue199-react-smoke-001",
        task_key="enzyme_like_fold",
        goal="Design a compact enzyme-like fold.",
        constraints={"length_range": [40, 80]},
        freeze_id="issue199-test-freeze",
        tool_whitelist_version="issue199-tool-whitelist-v1",
        dataset_version="issue170-remote-batch3-20260316",
    )

    assert payload["plan"]["metadata"]["freeze_id"] == "issue199-test-freeze"
    assert payload["plan"]["metadata"]["provider_alias"] == "baseline"
    assert payload["budget"]["planned_steps"] >= 1
    assert payload["budget"]["high_cost_planned_steps"] == 0
    assert "tool_whitelist_version" in payload["plan"]["metadata"]
    assert payload["plan"]["steps"][0]["tool"] in payload["tool_whitelist"]["allowed_tool_ids"]


def test_standardized_evidence_sample_has_adapter_artifacts(tmp_path: Path) -> None:
    _, output_dir = build_issue199_platform_adapter_bundle(
        config=load_json(Path("configs/experiments/issue199_benchmark_platform_adapters.json")),
        output_root=tmp_path,
        freeze_id="issue199-evidence-freeze",
    )

    evidence_index = json.loads(
        (output_dir / "standardized" / "evidence-index.sample.json").read_text(
            encoding="utf-8"
        )
    )

    artifact_ids = {row["artifact_id"] for row in evidence_index["artifacts"]}
    assert "inspect-react-task" in artifact_ids
    assert "promptfoo-regression-suite" in artifact_ids
