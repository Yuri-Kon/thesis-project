#!/usr/bin/env python3
"""Real smoke tests for configured LLM planner providers."""

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
from src.models.contracts import ProteinDesignTask

DEFAULT_CONFIG_PATH = project_root / "configs" / "llm_providers.json"
DEFAULT_PROVIDERS = ("qwen-plus", "deepseek-chat", "glm-5", "nemotron")
SMOKE_REGISTRY = [
    ToolSpec(
        id="protgpt2",
        capabilities=("sequence_generation",),
        inputs=("goal",),
        outputs=("sequence",),
    ),
    ToolSpec(
        id="nim_esmfold",
        capabilities=("structure_prediction",),
        inputs=("sequence",),
        outputs=("structure_pdb",),
    ),
    ToolSpec(
        id="biopython_qc",
        capabilities=("quality_qc",),
        inputs=("sequence", "structure_pdb"),
        outputs=("qc_metrics",),
    ),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run real LLM provider smoke tests.")
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
        "--goal",
        default="Design a short stable protein and return a minimal executable plan.",
        help="Planner goal used for the smoke test.",
    )
    parser.add_argument(
        "--target-length",
        type=int,
        default=60,
        help="Target protein length constraint for the smoke task.",
    )
    parser.add_argument(
        "--output",
        help="Optional path to write a JSON report.",
    )
    return parser.parse_args()


def run_provider(alias: str, catalog_path: Path, goal: str, target_length: int) -> dict[str, object]:
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
    task = ProteinDesignTask(
        task_id=f"smoke_{alias.replace('-', '_')}",
        goal=goal,
        constraints={"target_length": target_length},
        metadata={"smoke_test": True},
    )

    started_at = time.time()
    plan = provider.call_planner(task, SMOKE_REGISTRY)
    elapsed = round(time.time() - started_at, 3)

    return {
        "provider": alias,
        "success": True,
        "model": plan.get("metadata", {}).get("model"),
        "provider_name": plan.get("metadata", {}).get("provider"),
        "elapsed_seconds": elapsed,
        "steps": [step["tool"] for step in plan.get("steps", [])],
        "task_id": plan.get("task_id"),
    }


def main() -> int:
    args = parse_args()
    catalog_path = Path(args.config)
    if not catalog_path.is_absolute():
        catalog_path = project_root / catalog_path

    providers = [alias.strip() for alias in args.providers.split(",") if alias.strip()]
    results = [
        run_provider(alias, catalog_path, args.goal, args.target_length)
        for alias in providers
    ]

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
