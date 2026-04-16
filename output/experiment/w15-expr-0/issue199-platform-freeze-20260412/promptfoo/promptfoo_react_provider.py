from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path("/home/yurikon/文档/thesis/thesis-project.dev")
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.infra.benchmark_platform_adapters import build_promptfoo_react_payload


def call_api(prompt: str, options: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    provider_config = options.get("config") if isinstance(options, dict) else {}
    if not isinstance(provider_config, dict):
        provider_config = {}
    vars_payload = context.get("vars") if isinstance(context, dict) else {}
    if not isinstance(vars_payload, dict):
        vars_payload = {}

    constraints_json = vars_payload.get("constraints_json") or "{}"
    try:
        constraints = json.loads(constraints_json)
    except json.JSONDecodeError:
        constraints = {}

    payload = build_promptfoo_react_payload(
        prompt=prompt,
        provider_alias=str(provider_config.get("provider_alias") or "baseline"),
        catalog_path=REPO_ROOT / str(provider_config.get("catalog_path") or "configs/llm_providers.json"),
        max_plan_steps=int(provider_config.get("max_plan_steps") or 3),
        max_high_cost_steps=int(provider_config.get("max_high_cost_steps") or 1),
        high_cost_tool_ids=provider_config.get("high_cost_tool_ids") or [],
        allowed_tool_ids=provider_config.get("allowed_tool_ids") or [],
        task_id=str(vars_payload.get("task_id") or "issue199-task"),
        task_key=str(vars_payload.get("task_key") or "unknown"),
        goal=str(vars_payload.get("goal") or prompt),
        constraints=constraints,
        freeze_id=str(vars_payload.get("freeze_id") or provider_config.get("freeze_id") or ""),
        tool_whitelist_version=str(
            vars_payload.get("tool_whitelist_version")
            or provider_config.get("tool_whitelist_version")
            or ""
        ),
        dataset_version=str(vars_payload.get("dataset_version") or provider_config.get("dataset_version") or ""),
    )
    return {"output": json.dumps(payload, ensure_ascii=False)}
