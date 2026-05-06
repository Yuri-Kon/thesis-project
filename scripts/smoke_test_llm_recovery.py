#!/usr/bin/env python3
"""Real smoke tests for LLM planner patch/replan providers."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.agents.planner import ToolSpec
from src.llm.provider_registry import create_provider, load_provider_catalog, resolve_api_key
from src.models.contracts import (
    PatchRequest,
    Plan,
    PlanStep,
    ProteinDesignTask,
    ReplanRequest,
    StepResult,
    now_iso,
)

DEFAULT_CONFIG_PATH = project_root / "configs" / "llm_providers.json"
DEFAULT_PROVIDERS = ("qwen-flash", "deepseek-chat", "glm-5", "nemotron")
RECOVERY_REGISTRY = [
    ToolSpec(
        id="protgpt2",
        capabilities=("sequence_generation",),
        inputs=("goal",),
        outputs=("sequence",),
        cost=0.35,
        safety_level=1,
        io_type="goal_to_sequence_candidates",
        adapter_mode="remote",
        priority="P0",
    ),
    ToolSpec(
        id="nim_esmfold",
        capabilities=("structure_prediction",),
        inputs=("sequence",),
        outputs=("pdb_path", "plddt"),
        cost=0.3,
        safety_level=1,
        io_type="sequence_to_structure",
        adapter_mode="remote",
        priority="P0",
    ),
    ToolSpec(
        id="esmfold",
        capabilities=("structure_prediction",),
        inputs=("sequence",),
        outputs=("pdb_path", "plddt"),
        cost=0.6,
        safety_level=1,
        io_type="sequence_to_structure",
        adapter_mode="local",
        priority="P0",
    ),
    ToolSpec(
        id="biopython_qc",
        capabilities=("quality_qc",),
        inputs=("sequence", "pdb_path"),
        outputs=("qc_metrics",),
        cost=0.2,
        safety_level=1,
        io_type="sequence_structure_to_qc_metrics",
        adapter_mode="local",
        priority="P0",
    ),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run real LLM provider patch/replan smoke tests.")
    parser.add_argument(
        "--providers",
        default=",".join(DEFAULT_PROVIDERS),
        help="Comma-separated provider aliases from configs/llm_providers.json",
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="Path to the provider catalog JSON file.",
    )
    parser.add_argument(
        "--per-provider-timeout",
        type=int,
        default=90,
        help="Hard timeout in seconds for each provider recovery smoke.",
    )
    parser.add_argument(
        "--output",
        help="Optional path to write a JSON report.",
    )
    return parser.parse_args()


def _sample_plan(task_id: str) -> Plan:
    return Plan(
        task_id=task_id,
        steps=[
            PlanStep(
                id="S1",
                tool="protgpt2",
                inputs={"goal": "Design a short stable protein."},
                metadata={"stage_id": "S1"},
            ),
            PlanStep(
                id="S2",
                tool="nim_esmfold",
                inputs={"sequence": "S1.sequence"},
                metadata={"stage_id": "S2"},
            ),
            PlanStep(
                id="S3",
                tool="biopython_qc",
                inputs={"sequence": "S1.sequence", "pdb_path": "S2.pdb_path"},
                metadata={"stage_id": "S3"},
            ),
        ],
        constraints={"goal_type": "de_novo_design", "length_range": [40, 60]},
        metadata={"smoke_test": True},
    )


def _sample_patch_request(task_id: str) -> PatchRequest:
    plan = _sample_plan(task_id)
    failed_result = StepResult(
        task_id=task_id,
        step_id="S2",
        tool="nim_esmfold",
        status="failed",
        failure_type="retryable",
        error_message="timeout during remote structure prediction",
        error_details={},
        outputs={},
        metrics={"retry_exhausted": True},
        risk_flags=[],
        logs_path=None,
        timestamp=now_iso(),
    )
    previous_result = StepResult(
        task_id=task_id,
        step_id="S1",
        tool="protgpt2",
        status="success",
        failure_type=None,
        error_message=None,
        error_details={},
        outputs={"sequence": "ACDEFGHIKLMNPQRSTVWY"},
        metrics={},
        risk_flags=[],
        logs_path=None,
        timestamp=now_iso(),
    )
    return PatchRequest(
        task_id=task_id,
        original_plan=plan,
        context_step_results=[previous_result, failed_result],
        safety_events=[],
        reason="retry exhausted for structure prediction",
    )


def _sample_replan_request(task_id: str) -> ReplanRequest:
    plan = _sample_plan(task_id)
    return ReplanRequest(
        task_id=task_id,
        original_plan=plan,
        failed_steps=["S2"],
        safety_events=[],
        reason="safety_blocked_structure_projection",
    )


def run_provider(alias: str, catalog_path: Path) -> dict[str, object]:
    catalog = load_provider_catalog(catalog_path)
    if alias not in catalog.providers:
        raise KeyError(f"Unknown provider alias: {alias}")

    settings = catalog.providers[alias]
    api_key = resolve_api_key(settings)
    if not api_key:
        return {
            "provider": alias,
            "success": False,
            "error": f"missing_api_key:{settings.api_key_env or 'inline'}",
        }

    provider = create_provider(settings)
    task_id = f"recovery_smoke_{alias.replace('-', '_')}"

    started_at = time.time()
    patch = provider.call_patch(_sample_patch_request(task_id), RECOVERY_REGISTRY)
    replan = provider.call_replan(_sample_replan_request(task_id), RECOVERY_REGISTRY)
    elapsed = round(time.time() - started_at, 3)

    patch_ops = []
    if isinstance(patch, dict):
        for op in patch.get("operations", []):
            patch_ops.append(
                {
                    "op": op.get("op"),
                    "target": op.get("target"),
                    "tool": (op.get("step") or {}).get("tool"),
                }
            )
    replan_steps = []
    if isinstance(replan, dict):
        replan_steps = [step.get("tool") for step in replan.get("steps", [])]

    return {
        "provider": alias,
        "success": bool(isinstance(patch, dict) and isinstance(replan, dict)),
        "provider_name": patch.get("metadata", {}).get("provider") if isinstance(patch, dict) else None,
        "elapsed_seconds": elapsed,
        "patch": {
            "operation_count": len(patch.get("operations", [])) if isinstance(patch, dict) else 0,
            "operations": patch_ops,
            "metadata": patch.get("metadata", {}) if isinstance(patch, dict) else {},
        },
        "replan": {
            "step_count": len(replan.get("steps", [])) if isinstance(replan, dict) else 0,
            "steps": replan_steps,
            "metadata": replan.get("metadata", {}) if isinstance(replan, dict) else {},
        },
    }


def main() -> int:
    args = parse_args()
    catalog_path = Path(args.config)
    if not catalog_path.is_absolute():
        catalog_path = project_root / catalog_path

    providers = [alias.strip() for alias in args.providers.split(",") if alias.strip()]
    results = []
    for alias in providers:
        print(
            f"[recovery-smoke] running provider={alias} timeout={args.per_provider_timeout}s",
            file=sys.stderr,
            flush=True,
        )
        started_at = time.time()
        try:
            result = run_provider(alias=alias, catalog_path=catalog_path)
        except Exception as exc:
            result = {
                "provider": alias,
                "success": False,
                "error": f"{type(exc).__name__}: {exc}",
                "elapsed_seconds": round(time.time() - started_at, 3),
            }
        results.append(result)
        print(
            f"[recovery-smoke] provider={alias} success={result['success']} elapsed={result.get('elapsed_seconds')}",
            file=sys.stderr,
            flush=True,
        )

    report = {"providers": results}
    print(json.dumps(report, ensure_ascii=False, indent=2))

    if args.output:
        output_path = Path(args.output)
        if not output_path.is_absolute():
            output_path = project_root / output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    return 0 if all(result["success"] for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
