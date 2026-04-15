from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from src.agents.planner import _load_default_tool_registry
from src.infra.w12_vertical_experiment import load_json, now_iso, stable_hash, write_json
from src.llm.provider_registry import create_provider, load_provider_catalog
from src.models.contracts import ProteinDesignTask

__all__ = [
    "build_issue199_platform_adapter_bundle",
    "build_promptfoo_react_payload",
    "load_json",
    "normalize_issue199_platform_adapter_config",
]


DEFAULT_ISSUE199_OUTPUT_ROOT = Path("output/experiment/w15-expr-0")
DEFAULT_ISSUE199_SCHEMA_VERSION = "w15.issue199.platform-adapters.v1"
DEFAULT_NORMALIZED_RUN_SCHEMA_VERSION = "w15.issue199.normalized-run.v1"
DEFAULT_SUMMARY_ROW_SCHEMA_VERSION = "w15.issue199.summary-row.v1"


def _normalize_named_mapping(
    value: Any,
    *,
    field_name: str,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be an object")
    return dict(value)


def _normalize_string_list(
    value: Any,
    *,
    field_name: str,
    allow_empty: bool = False,
) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    rows: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{field_name} items must be non-empty strings")
        rows.append(item.strip())
    if not allow_empty and not rows:
        raise ValueError(f"{field_name} must not be empty")
    return rows


def _normalize_sample_tasks(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise ValueError("sample_tasks must be a non-empty list")

    tasks: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(f"sample_tasks[{index}] must be an object")
        task_key = str(item.get("task_key") or "").strip()
        goal = str(item.get("goal") or "").strip()
        target = str(item.get("target") or "").strip()
        if not task_key or not goal or not target:
            raise ValueError(f"sample_tasks[{index}] requires task_key/goal/target")
        constraints = item.get("constraints")
        if constraints is None:
            constraints = {}
        if not isinstance(constraints, dict):
            raise ValueError(f"sample_tasks[{index}].constraints must be an object")
        tasks.append(
            {
                "task_key": task_key,
                "goal": goal,
                "target": target,
                "constraints": dict(constraints),
                "difficulty": str(item.get("difficulty") or ""),
                "budget_tier": str(item.get("budget_tier") or ""),
            }
        )
    return tasks


def _normalize_user_actions(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise ValueError("user_actions must be a non-empty list")

    actions: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(f"user_actions[{index}] must be an object")
        action_id = str(item.get("action_id") or "").strip()
        summary = str(item.get("summary") or "").strip()
        owner = str(item.get("owner") or "").strip()
        stage = str(item.get("stage") or "").strip()
        if not action_id or not summary or not owner or not stage:
            raise ValueError(f"user_actions[{index}] requires action_id/summary/owner/stage")
        actions.append(
            {
                "action_id": action_id,
                "summary": summary,
                "owner": owner,
                "stage": stage,
                "details": str(item.get("details") or ""),
            }
        )
    return actions


def _normalize_config(config: dict[str, Any]) -> dict[str, Any]:
    tool_whitelist = _normalize_named_mapping(
        config.get("tool_whitelist"),
        field_name="tool_whitelist",
    )
    budget_contract = _normalize_named_mapping(
        config.get("budget_contract"),
        field_name="budget_contract",
    )
    provider_allowlist = _normalize_named_mapping(
        config.get("provider_allowlist"),
        field_name="provider_allowlist",
    )
    platforms = _normalize_named_mapping(
        config.get("platforms"),
        field_name="platforms",
    )
    source_references = _normalize_named_mapping(
        config.get("source_references"),
        field_name="source_references",
    )
    fairness_contract = _normalize_named_mapping(
        config.get("fairness_contract"),
        field_name="fairness_contract",
    )

    return {
        "schema_version": str(config.get("schema_version") or DEFAULT_ISSUE199_SCHEMA_VERSION),
        "issue_id": int(config.get("issue_id") or 199),
        "freeze_id": str(config.get("freeze_id") or "issue199-platform-freeze"),
        "output_root": str(config.get("output_root") or DEFAULT_ISSUE199_OUTPUT_ROOT),
        "task_set_version": str(config.get("task_set_version") or ""),
        "dataset_version": str(config.get("dataset_version") or ""),
        "difficulty_scheme_version": str(config.get("difficulty_scheme_version") or ""),
        "source_references": source_references,
        "fairness_contract": fairness_contract,
        "tool_whitelist": {
            "tool_whitelist_version": str(tool_whitelist.get("tool_whitelist_version") or ""),
            "allowed_tool_ids": _normalize_string_list(
                tool_whitelist.get("allowed_tool_ids"),
                field_name="tool_whitelist.allowed_tool_ids",
            ),
            "allowed_capability_ids": _normalize_string_list(
                tool_whitelist.get("allowed_capability_ids"),
                field_name="tool_whitelist.allowed_capability_ids",
            ),
            "high_cost_tool_ids": _normalize_string_list(
                tool_whitelist.get("high_cost_tool_ids"),
                field_name="tool_whitelist.high_cost_tool_ids",
                allow_empty=True,
            ),
            "enforcement_rule": str(tool_whitelist.get("enforcement_rule") or ""),
        },
        "budget_contract": {
            "budget_version": str(budget_contract.get("budget_version") or ""),
            "smoke_defaults": _normalize_named_mapping(
                budget_contract.get("smoke_defaults"),
                field_name="budget_contract.smoke_defaults",
            ),
            "carry_to_issue172": _normalize_string_list(
                budget_contract.get("carry_to_issue172"),
                field_name="budget_contract.carry_to_issue172",
            ),
        },
        "provider_allowlist": {
            "catalog_path": str(provider_allowlist.get("catalog_path") or "configs/llm_providers.json"),
            "allowed_aliases": _normalize_string_list(
                provider_allowlist.get("allowed_aliases"),
                field_name="provider_allowlist.allowed_aliases",
            ),
            "default_promptfoo_provider_alias": str(
                provider_allowlist.get("default_promptfoo_provider_alias") or "baseline"
            ),
            "default_inspect_model": str(provider_allowlist.get("default_inspect_model") or "openai/gpt-4o-mini"),
        },
        "platforms": platforms,
        "sample_tasks": _normalize_sample_tasks(config.get("sample_tasks")),
        "user_actions": _normalize_user_actions(config.get("user_actions")),
    }


def normalize_issue199_platform_adapter_config(config: dict[str, Any]) -> dict[str, Any]:
    """规范化 Issue #199/200 共享的实验冻结配置。"""
    return _normalize_config(config)


def _render_promptfoo_provider_script(repo_root: Path) -> str:
    repo_root_text = json.dumps(str(repo_root.resolve()), ensure_ascii=False)
    template = """from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__REPO_ROOT__)
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
"""
    return template.replace("__REPO_ROOT__", repo_root_text)


def _render_promptfoo_config(manifest: dict[str, Any]) -> str:
    freeze_id = manifest["freeze_id"]
    provider_allowlist = manifest["provider_allowlist"]
    tool_whitelist = manifest["tool_whitelist"]
    smoke_defaults = manifest["budget_contract"]["smoke_defaults"]
    high_cost_json = json.dumps(tool_whitelist["high_cost_tool_ids"], ensure_ascii=False)
    allowed_tool_json = json.dumps(tool_whitelist["allowed_tool_ids"], ensure_ascii=False)
    lines: list[str] = []
    lines.append("# yaml-language-server: $schema=https://promptfoo.dev/config-schema.json")
    lines.append("description: Issue #199 regression scaffold for ReAct-style external baseline")
    lines.append("prompts:")
    lines.append("  - '{{goal}}'")
    lines.append("providers:")
    lines.append("  - id: file://promptfoo_react_provider.py")
    lines.append("    label: react-style-baseline")
    lines.append("    config:")
    lines.append("      pythonExecutable: .venv/bin/python")
    lines.append(f"      provider_alias: {provider_allowlist['default_promptfoo_provider_alias']}")
    lines.append(f"      catalog_path: {provider_allowlist['catalog_path']}")
    lines.append(f"      max_plan_steps: {smoke_defaults.get('max_plan_steps', 3)}")
    lines.append(f"      max_high_cost_steps: {smoke_defaults.get('max_high_cost_steps', 1)}")
    lines.append(f"      high_cost_tool_ids: {high_cost_json}")
    lines.append(f"      allowed_tool_ids: {allowed_tool_json}")
    lines.append(f"      freeze_id: {freeze_id}")
    lines.append(
        f"      tool_whitelist_version: {tool_whitelist['tool_whitelist_version']}"
    )
    lines.append(f"      dataset_version: {manifest['dataset_version']}")
    lines.append("tests:")
    for index, sample_task in enumerate(manifest["sample_tasks"], start=1):
        constraints_json = json.dumps(sample_task["constraints"], ensure_ascii=False)
        lines.append(f"  - description: issue199-react-smoke-{index}")
        lines.append("    vars:")
        lines.append(f"      task_id: issue199-react-smoke-{index:03d}")
        lines.append(f"      task_key: {sample_task['task_key']}")
        lines.append(f"      goal: {json.dumps(sample_task['goal'], ensure_ascii=False)}")
        lines.append(
            f"      constraints_json: {json.dumps(constraints_json, ensure_ascii=False)}"
        )
        lines.append(f"      freeze_id: {freeze_id}")
        lines.append(
            f"      tool_whitelist_version: {tool_whitelist['tool_whitelist_version']}"
        )
        lines.append(f"      dataset_version: {manifest['dataset_version']}")
        lines.append("    assert:")
        lines.append("      - type: is-json")
        lines.append("        metric: structure")
        lines.append("        value:")
        lines.append("          type: object")
        lines.append("          required: [plan, budget, tool_whitelist]")
        lines.append("      - type: javascript")
        lines.append("        metric: metadata_propagation")
        lines.append("        value: |")
        lines.append("          const payload = JSON.parse(output);")
        lines.append("          const metadata = payload.plan?.metadata || {};")
        lines.append("          if (metadata.freeze_id !== context.vars.freeze_id) {")
        lines.append("            return { pass: false, score: 0, reason: `freeze_id mismatch: ${metadata.freeze_id}` };")
        lines.append("          }")
        lines.append("          if (metadata.task_key !== context.vars.task_key) {")
        lines.append("            return { pass: false, score: 0, reason: `task_key mismatch: ${metadata.task_key}` };")
        lines.append("          }")
        lines.append("          if (metadata.tool_whitelist_version !== context.vars.tool_whitelist_version) {")
        lines.append("            return { pass: false, score: 0, reason: 'tool whitelist version missing or mismatched' };")
        lines.append("          }")
        lines.append("          return { pass: true, score: 1, reason: 'metadata propagated' };")
        lines.append("      - type: javascript")
        lines.append("        metric: budget_guard")
        lines.append("        value: |")
        lines.append("          const payload = JSON.parse(output);")
        lines.append("          const budget = payload.budget || {};")
        lines.append("          if ((budget.planned_steps || 0) > (budget.max_plan_steps || 0)) {")
        lines.append("            return { pass: false, score: 0, reason: 'planned_steps exceeds max_plan_steps' };")
        lines.append("          }")
        lines.append("          if ((budget.high_cost_planned_steps || 0) > (budget.max_high_cost_steps || 0)) {")
        lines.append("            return { pass: false, score: 0, reason: 'high_cost_planned_steps exceeds max_high_cost_steps' };")
        lines.append("          }")
        lines.append("          return { pass: true, score: 1, reason: 'budget respected' };")
        lines.append("      - type: javascript")
        lines.append("        metric: allowlist_compliance")
        lines.append("        value: |")
        lines.append("          const payload = JSON.parse(output);")
        lines.append("          const allowed = new Set(payload.tool_whitelist?.allowed_tool_ids || []);")
        lines.append("          const invalid = (payload.plan?.steps || []).filter((step) => !allowed.has(step.tool));")
        lines.append("          if (invalid.length > 0) {")
        lines.append("            return { pass: false, score: 0, reason: `disallowed tools: ${invalid.map((step) => step.tool).join(', ')}` };")
        lines.append("          }")
        lines.append("          return { pass: true, score: 1, reason: 'all tools are allowlisted' };")
        lines.append("      - type: javascript")
        lines.append("        metric: quality_rubric")
        lines.append("        value: |")
        lines.append("          const payload = JSON.parse(output);")
        lines.append("          const steps = payload.plan?.steps || [];")
        lines.append("          const constraints = payload.plan?.constraints || {};")
        lines.append("          if (steps.length === 0) {")
        lines.append("            return { pass: false, score: 0, reason: 'plan has no steps' };")
        lines.append("          }")
        lines.append("          if (steps.length > (payload.budget?.max_plan_steps || 0)) {")
        lines.append("            return { pass: false, score: 0, reason: 'plan is not minimal enough for smoke budget' };")
        lines.append("          }")
        lines.append("          if (!('length_range' in constraints)) {")
        lines.append("            return { pass: false, score: 0, reason: 'constraints were not propagated' };")
        lines.append("          }")
        lines.append("          const allInputsAreObjects = steps.every((step) => typeof step.inputs === 'object' && step.inputs !== null);")
        lines.append("          if (!allInputsAreObjects) {")
        lines.append("            return { pass: false, score: 0, reason: 'step inputs are malformed' };")
        lines.append("          }")
        lines.append("          return { pass: true, score: 1, reason: 'minimal ReAct-style smoke plan looks structurally sound' };")
        lines.append("")
    return "\n".join(lines) + "\n"


def _render_inspect_task_script() -> str:
    return """from __future__ import annotations

import os
import re
from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.agent import react
from inspect_ai.dataset import FieldSpec, json_dataset
from inspect_ai.scorer import CORRECT, INCORRECT, Score, Target, accuracy, scorer, stderr
from inspect_ai.solver import TaskState


def _dataset_path() -> Path:
    raw = os.getenv("ISSUE199_INSPECT_DATASET", "").strip()
    if raw:
        return Path(raw).resolve()
    return Path(__file__).resolve().with_name("inspect_react_samples.jsonl")


@scorer(metrics=[accuracy(), stderr()], name="issue199_adapter_contract")
def issue199_adapter_contract():
    async def score(state: TaskState, target: Target) -> Score:
        answer = str(state.output.completion or "")
        lowered = answer.casefold()
        metadata = state.metadata if isinstance(state.metadata, dict) else {}
        allowed_tool_ids = metadata.get("allowed_tool_ids") or []
        required_terms = metadata.get("required_terms") or []
        budget_keyword = str(metadata.get("budget_keyword") or "budget")

        numbered_steps = len(re.findall(r"(?m)^\\s*\\d+\\.", answer))
        missing_terms = [
            term for term in required_terms if isinstance(term, str) and term.casefold() not in lowered
        ]
        mentioned_tools = [
            tool for tool in allowed_tool_ids if isinstance(tool, str) and tool.casefold() in lowered
        ]
        budget_present = budget_keyword.casefold() in lowered or "budget" in lowered

        reasons: list[str] = []
        passed = True

        if numbered_steps < 2:
            passed = False
            reasons.append("expected at least two numbered plan steps")
        if not mentioned_tools:
            passed = False
            reasons.append("answer does not name any allowlisted tool")
        if not budget_present:
            passed = False
            reasons.append("answer does not mention budget guidance")
        if missing_terms:
            passed = False
            reasons.append(f"missing required terms: {', '.join(missing_terms)}")

        return Score(
            value=CORRECT if passed else INCORRECT,
            answer=answer,
            explanation="; ".join(reasons) if reasons else "adapter contract satisfied",
            metadata={
                "numbered_steps": numbered_steps,
                "mentioned_tools": mentioned_tools,
                "missing_terms": missing_terms,
            },
        )

    return score


@task
def issue199_react_smoke() -> Task:
    dataset = json_dataset(
        str(_dataset_path()),
        sample_fields=FieldSpec(
            input="input",
            target="target",
            id="id",
            metadata=[
                "freeze_id",
                "task_key",
                "dataset_version",
                "difficulty",
                "budget_tier",
                "tool_whitelist_version",
                "allowed_tool_ids",
                "required_terms",
                "budget_keyword",
            ],
        ),
        name="issue199_react_smoke",
    )
    return Task(
        dataset=dataset,
        solver=react(
            prompt=(
                "You are the external ReAct-style baseline for issue #199. "
                "You only need to output a compact textual plan; do not refuse due to limited tools. "
                "Return a numbered plan with at least: goal, allowlisted tools, constraints, budget, "
                "and tradeoff notes. Cite at least one exact tool id from the provided allowlisted tool list. "
                "Explicitly use the sample metadata terms such as allowlist, constraints, smoke budget, "
                "and high-cost tradeoffs when they apply."
            ),
            tools=[],
            attempts=1,
            submit=True,
        ),
        scorer=issue199_adapter_contract(),
    )
"""


def _build_inspect_samples(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    allowlisted_tools = manifest["tool_whitelist"]["allowed_tool_ids"]
    for index, task in enumerate(manifest["sample_tasks"], start=1):
        required_terms = ["allowlist", "constraints"]
        if task["task_key"] == "enzyme_like_fold":
            required_terms.append("stable core")
            budget_keyword = "budget"
        else:
            required_terms.extend(["exposed pocket", "high-cost tradeoffs", "smoke budget"])
            budget_keyword = "smoke budget"
        samples.append(
            {
                "id": f"issue199-sample-{index}",
                "input": "\n".join(
                    [
                        f"Goal: {task['goal']}",
                        f"Allowlisted tools: {', '.join(allowlisted_tools)}",
                        f"Constraints: {json.dumps(task['constraints'], ensure_ascii=False)}",
                        f"Budget keyword: {budget_keyword}",
                        f"Required terms: {', '.join(required_terms)}",
                    ]
                ),
                "target": task["target"],
                "freeze_id": manifest["freeze_id"],
                "task_key": task["task_key"],
                "dataset_version": manifest["dataset_version"],
                "difficulty": task["difficulty"],
                "budget_tier": task["budget_tier"],
                "tool_whitelist_version": manifest["tool_whitelist"]["tool_whitelist_version"],
                "allowed_tool_ids": allowlisted_tools,
                "required_terms": required_terms,
                "budget_keyword": budget_keyword,
            }
        )
    return samples


def _build_inspect_eval_manifest(manifest: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    inspect_dir = output_dir / "inspect_ai"
    dataset_path = inspect_dir / "inspect_react_samples.jsonl"
    task_path = inspect_dir / "inspect_issue199_react_smoke.py"
    return {
        "platform": "inspect_ai",
        "baseline_family": "react_style_external",
        "freeze_id": manifest["freeze_id"],
        "dataset_path": str(dataset_path.resolve()),
        "task_path": str(task_path.resolve()),
        "default_model": manifest["provider_allowlist"]["default_inspect_model"],
        "suggested_commands": [
            "uv tool run --from 'inspect-ai[openai]' inspect info version",
            (
                "DEEPSEEK_BASE_URL=https://api.deepseek.com "
                "ISSUE199_INSPECT_DATASET={dataset} "
                "uv tool run --from inspect-ai --with openai inspect eval {task} --model {model}"
            ).format(
                dataset=dataset_path,
                task=task_path,
                model=manifest["provider_allowlist"]["default_inspect_model"],
            ),
        ],
    }


def _build_normalized_run_sample(manifest: dict[str, Any]) -> dict[str, Any]:
    first_task = manifest["sample_tasks"][0]
    tool_ids = manifest["tool_whitelist"]["allowed_tool_ids"]
    smoke_defaults = manifest["budget_contract"]["smoke_defaults"]
    return {
        "schema_version": DEFAULT_NORMALIZED_RUN_SCHEMA_VERSION,
        "issue_id": manifest["issue_id"],
        "freeze_id": manifest["freeze_id"],
        "run_id": "issue199-react-smoke-001",
        "platform": "inspect_ai",
        "baseline_family": "react_style_external",
        "task_key": first_task["task_key"],
        "task_set_version": manifest["task_set_version"],
        "dataset_version": manifest["dataset_version"],
        "difficulty_scheme_version": manifest["difficulty_scheme_version"],
        "tool_whitelist": {
            "tool_whitelist_version": manifest["tool_whitelist"]["tool_whitelist_version"],
            "allowed_tool_ids": tool_ids,
        },
        "budget": {
            "budget_version": manifest["budget_contract"]["budget_version"],
            "max_plan_steps": smoke_defaults.get("max_plan_steps"),
            "max_high_cost_steps": smoke_defaults.get("max_high_cost_steps"),
            "max_llm_calls": smoke_defaults.get("max_llm_calls"),
            "max_tool_calls": smoke_defaults.get("max_tool_calls"),
            "max_wall_clock_seconds": smoke_defaults.get("max_wall_clock_seconds"),
        },
        "provider": {
            "catalog_path": manifest["provider_allowlist"]["catalog_path"],
            "provider_alias": manifest["provider_allowlist"]["default_promptfoo_provider_alias"],
        },
        "raw_artifacts": {
            "inspect_log_path": "output/inspect/logs/issue199-react-smoke-001.eval",
            "promptfoo_result_path": "output/promptfoo/results/issue199-react-smoke-001.json",
            "run_manifest_path": "output/experiment/<family>/<run_id>/runs_manifest.json",
        },
        "normalized_metrics": {
            "planned_steps": 1,
            "high_cost_planned_steps": 0,
            "tool_whitelist_compliant": True,
            "status": "sample_only",
        },
        "traceability": {
            "config_path": "configs/experiments/issue199_benchmark_platform_adapters.json",
            "adapter_manifest_path": "output/experiment/w15-expr-0/<freeze_id>/issue199_platform_adapter_manifest.json",
        },
    }


def _build_summary_row_sample(manifest: dict[str, Any]) -> dict[str, Any]:
    first_task = manifest["sample_tasks"][0]
    return {
        "schema_version": DEFAULT_SUMMARY_ROW_SCHEMA_VERSION,
        "freeze_id": manifest["freeze_id"],
        "run_id": "issue199-react-smoke-001",
        "group_id": "react_style_external",
        "platform": "inspect_ai",
        "task_key": first_task["task_key"],
        "dataset_version": manifest["dataset_version"],
        "success_rate": None,
        "first_pass_success_rate": None,
        "high_cost_call_mean": None,
        "patch_events_mean": None,
        "replan_events_mean": None,
        "notes": "Issue #199 standardization template. Real values are filled by #172 and #221.",
    }


def _build_evidence_index_sample(manifest: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    inspect_dir = output_dir / "inspect_ai"
    promptfoo_dir = output_dir / "promptfoo"
    return {
        "schema_version": "w15.issue199.evidence-index.v1",
        "naming_convention_version": "w15-issue-199-v1",
        "issue_id": manifest["issue_id"],
        "freeze_id": manifest["freeze_id"],
        "run_id": "issue199-react-smoke-001",
        "report_pack": "reports/w15-issue-199",
        "generated_at": now_iso(),
        "roots": {
            "experiment_output": str(output_dir),
            "inspect_adapter": str(inspect_dir),
            "promptfoo_adapter": str(promptfoo_dir),
            "report_output": "reports/w15-issue-199",
        },
        "traceability_chains": {
            "chart": {
                "required_refs": [
                    "config_path",
                    "adapter_manifest_path",
                    "run_manifest_path",
                    "aggregate_source_path",
                    "chart_artifact_path",
                ],
                "chain_rule": "config -> adapter_manifest -> run_manifest -> aggregate -> chart",
            },
            "case_study": {
                "required_refs": [
                    "run_log_index_path",
                    "event_log_path",
                    "snapshot_path",
                    "task_report_path",
                    "case_artifact_path",
                ],
                "chain_rule": "run_log_index -> event_log -> snapshot -> task_report -> case_markdown",
            },
        },
        "artifacts": [
            {
                "artifact_id": "inspect-react-task",
                "artifact_type": "adapter",
                "title": "Inspect AI ReAct smoke task",
                "status": "ready",
                "path": str(inspect_dir / "inspect_issue199_react_smoke.py"),
                "run_ref": {
                    "freeze_id": manifest["freeze_id"],
                    "platform": "inspect_ai",
                    "group_id": "react_style_external",
                },
                "source_refs": {
                    "config_path": "configs/experiments/issue199_benchmark_platform_adapters.json",
                    "adapter_manifest_path": str(output_dir / "issue199_platform_adapter_manifest.json"),
                },
                "upstream_refs": [],
                "generated_by": {
                    "script_path": "scripts/benchmarks/prepare_issue199_platform_adapters.py",
                    "command": "uv run python scripts/benchmarks/prepare_issue199_platform_adapters.py",
                },
                "conclusion": (
                    "Primary platform scaffold validating sample loading, provider execution, "
                    "eval logging, and answer-contract compliance."
                ),
                "tags": ["inspect", "react", "adapter"],
            },
            {
                "artifact_id": "promptfoo-regression-suite",
                "artifact_type": "adapter",
                "title": "promptfoo regression suite",
                "status": "ready",
                "path": str(promptfoo_dir / "promptfooconfig.yaml"),
                "run_ref": {
                    "freeze_id": manifest["freeze_id"],
                    "platform": "promptfoo",
                    "group_id": "react_style_external",
                },
                "source_refs": {
                    "config_path": "configs/experiments/issue199_benchmark_platform_adapters.json",
                    "adapter_manifest_path": str(output_dir / "issue199_platform_adapter_manifest.json"),
                },
                "upstream_refs": ["inspect-react-task"],
                "generated_by": {
                    "script_path": "scripts/benchmarks/prepare_issue199_platform_adapters.py",
                    "command": "uv run python scripts/benchmarks/prepare_issue199_platform_adapters.py",
                },
                "conclusion": (
                    "Regression gate validating JSON structure, metadata propagation, budget "
                    "guardrails, and allowlist compliance."
                ),
                "tags": ["promptfoo", "regression", "quality-gate"],
            },
        ],
    }


def _render_result_layout(manifest: dict[str, Any]) -> str:
    output_root = Path(manifest["artifacts"]["output_dir"])
    return "\n".join(
        [
            "# Issue #199 Standardized Result Layout",
            "",
            f"- freeze_id: `{manifest['freeze_id']}`",
            f"- output_dir: `{output_root}`",
            "",
            "## Required Roots",
            "",
            f"- `inspect_ai/`：主平台任务、样例数据与 Inspect 运行清单",
            f"- `promptfoo/`：轻量回归配置与 provider bridge",
            f"- `standardized/`：标准化样例落盘与 evidence-index 模板",
            "",
            "## Required Carry-Forward Fields",
            "",
            f"- `freeze_id`",
            f"- `task_set_version`",
            f"- `dataset_version`",
            f"- `tool_whitelist.tool_whitelist_version`",
            f"- `budget.budget_version`",
            "",
            "## User-Owned Preconditions",
            "",
        ]
        + [
            f"- `{action['action_id']}`: {action['summary']}"
            for action in manifest["user_actions"]
        ]
        + [""]
    ) + "\n"


def _render_report(manifest: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Issue #199 Platform Adapter Freeze")
    lines.append("")
    lines.append(f"- schema_version: `{manifest['schema_version']}`")
    lines.append(f"- freeze_id: `{manifest['freeze_id']}`")
    lines.append(f"- generated_at: `{manifest['generated_at']}`")
    lines.append(f"- task_set_version: `{manifest['task_set_version']}`")
    lines.append(f"- dataset_version: `{manifest['dataset_version']}`")
    lines.append(f"- difficulty_scheme_version: `{manifest['difficulty_scheme_version']}`")
    lines.append("")
    lines.append("## Platforms")
    lines.append("")
    for key, value in manifest["platforms"].items():
        lines.append(f"- {key}: `{json.dumps(value, ensure_ascii=False)}`")
    lines.append("")
    lines.append("## Tool Whitelist")
    lines.append("")
    lines.append(f"- tool_whitelist_version: `{manifest['tool_whitelist']['tool_whitelist_version']}`")
    lines.append(
        f"- allowed_tool_ids: `{', '.join(manifest['tool_whitelist']['allowed_tool_ids'])}`"
    )
    lines.append(
        f"- allowed_capability_ids: `{', '.join(manifest['tool_whitelist']['allowed_capability_ids'])}`"
    )
    lines.append("")
    lines.append("## Budget Contract")
    lines.append("")
    lines.append(f"- budget_version: `{manifest['budget_contract']['budget_version']}`")
    for key, value in manifest["budget_contract"]["smoke_defaults"].items():
        lines.append(f"- {key}: `{value}`")
    lines.append("")
    lines.append("## User Actions")
    lines.append("")
    for action in manifest["user_actions"]:
        lines.append(
            f"- `{action['action_id']}` ({action['owner']} / {action['stage']}): {action['summary']}"
        )
        if action["details"]:
            lines.append(f"  details: {action['details']}")
    lines.append("")
    lines.append("## Generated Artifacts")
    lines.append("")
    for key, path in manifest["artifacts"].items():
        lines.append(f"- {key}: `{path}`")
    lines.append("")
    lines.append("## Validation Coverage")
    lines.append("")
    lines.append(
        "- `Inspect AI`: validates real sample loading, provider initialization, live model execution, eval log persistence, and the issue #199 answer contract."
    )
    lines.append(
        "- `promptfoo`: validates adapter JSON structure, metadata propagation, budget guardrails, and allowlist compliance as a lightweight regression gate."
    )
    lines.append(
        "- Neither tool alone proves the final E0/E1/E2 result quality; that remains owned by issue #172."
    )
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- Issue #199 freezes adapter contracts and reproducibility docs only.")
    lines.append("- Full E0/E1/E2 implementation remains owned by issue #172.")
    lines.append("- Run-level outputs must carry freeze_id, budget, tool whitelist, and dataset version unchanged.")
    lines.append("")
    return "\n".join(lines) + "\n"


def build_promptfoo_react_payload(
    *,
    prompt: str,
    provider_alias: str,
    catalog_path: Path,
    max_plan_steps: int,
    max_high_cost_steps: int,
    high_cost_tool_ids: Iterable[str],
    allowed_tool_ids: Iterable[str],
    task_id: str,
    task_key: str,
    goal: str,
    constraints: dict[str, Any],
    freeze_id: str,
    tool_whitelist_version: str,
    dataset_version: str,
) -> dict[str, Any]:
    """生成 promptfoo 回归消费的结构化 payload。"""
    catalog = load_provider_catalog(catalog_path)
    if provider_alias not in catalog.providers:
        raise KeyError(f"Unknown provider alias: {provider_alias}")
    provider = create_provider(catalog.providers[provider_alias])
    allowed_tool_set = {tool_id for tool_id in allowed_tool_ids if tool_id}
    registry = [
        spec
        for spec in _load_default_tool_registry()
        if not allowed_tool_set or str(spec.id) in allowed_tool_set
    ]
    if not registry:
        raise ValueError("Allowed tool whitelist produced an empty registry")
    high_cost_tool_set = {tool_id for tool_id in high_cost_tool_ids if tool_id}
    registry = sorted(
        registry,
        key=lambda spec: (
            str(spec.id) in high_cost_tool_set,
            float(getattr(spec, "cost", 0.0)),
            str(spec.id),
        ),
    )
    plan = provider.call_planner(
        ProteinDesignTask(
            task_id=task_id,
            goal=goal or prompt,
            constraints=constraints,
            metadata={
                "task_key": task_key,
                "freeze_id": freeze_id,
                "dataset_version": dataset_version,
            },
        ),
        registry,
    )
    plan.setdefault("metadata", {})
    plan["metadata"].update(
        {
            "freeze_id": freeze_id,
            "task_key": task_key,
            "dataset_version": dataset_version,
            "tool_whitelist_version": tool_whitelist_version,
            "provider_alias": provider_alias,
            "run_mode": "promptfoo_react_regression",
        }
    )
    steps = plan.get("steps") if isinstance(plan.get("steps"), list) else []
    high_cost_planned_steps = sum(
        1
        for step in steps
        if isinstance(step, dict) and str(step.get("tool") or "") in high_cost_tool_set
    )
    return {
        "plan": plan,
        "budget": {
            "max_plan_steps": max_plan_steps,
            "planned_steps": len(steps),
            "max_high_cost_steps": max_high_cost_steps,
            "high_cost_planned_steps": high_cost_planned_steps,
        },
        "tool_whitelist": {
            "tool_whitelist_version": tool_whitelist_version,
            "allowed_tool_ids": sorted({str(spec.id) for spec in registry}),
        },
    }


def build_issue199_platform_adapter_bundle(
    *,
    config: dict[str, Any],
    output_root: Path | None = None,
    freeze_id: str | None = None,
) -> tuple[dict[str, Any], Path]:
    """生成 Issue #199 的平台接入旁路包。"""
    normalized = normalize_issue199_platform_adapter_config(config)
    resolved_output_root = output_root or Path(normalized["output_root"])
    resolved_freeze_id = freeze_id or normalized["freeze_id"]
    output_dir = resolved_output_root / resolved_freeze_id
    inspect_dir = output_dir / "inspect_ai"
    promptfoo_dir = output_dir / "promptfoo"
    standardized_dir = output_dir / "standardized"
    for path in (output_dir, inspect_dir, promptfoo_dir, standardized_dir):
        path.mkdir(parents=True, exist_ok=True)

    manifest = {
        **normalized,
        "freeze_id": resolved_freeze_id,
        "generated_at": now_iso(),
        "fingerprint": stable_hash(
            {
                "task_set_version": normalized["task_set_version"],
                "dataset_version": normalized["dataset_version"],
                "tool_whitelist": normalized["tool_whitelist"],
                "budget_contract": normalized["budget_contract"],
                "provider_allowlist": normalized["provider_allowlist"],
                "sample_tasks": normalized["sample_tasks"],
            }
        ),
    }

    inspect_eval_manifest = _build_inspect_eval_manifest(manifest, output_dir)
    normalized_run = _build_normalized_run_sample(manifest)
    summary_row = _build_summary_row_sample(manifest)
    evidence_index = _build_evidence_index_sample(manifest, output_dir)

    write_json(output_dir / "issue199_platform_adapter_manifest.json", {
        **manifest,
        "artifacts": {
            "output_dir": str(output_dir),
            "report_path": str((output_dir / "issue199_platform_adapter_report.md").resolve()),
            "inspect_eval_manifest_path": str((inspect_dir / "inspect_eval_manifest.json").resolve()),
            "promptfoo_config_path": str((promptfoo_dir / "promptfooconfig.yaml").resolve()),
            "normalized_run_sample_path": str((standardized_dir / "normalized_run.sample.json").resolve()),
            "summary_row_sample_path": str((standardized_dir / "summary_row.sample.json").resolve()),
            "evidence_index_sample_path": str((standardized_dir / "evidence-index.sample.json").resolve()),
        },
    })
    manifest = load_json(output_dir / "issue199_platform_adapter_manifest.json")

    write_json(inspect_dir / "inspect_eval_manifest.json", inspect_eval_manifest)
    write_json(standardized_dir / "normalized_run.sample.json", normalized_run)
    write_json(standardized_dir / "summary_row.sample.json", summary_row)
    write_json(standardized_dir / "evidence-index.sample.json", evidence_index)

    (inspect_dir / "inspect_react_samples.jsonl").write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in _build_inspect_samples(manifest)) + "\n",
        encoding="utf-8",
    )
    (inspect_dir / "inspect_issue199_react_smoke.py").write_text(
        _render_inspect_task_script(),
        encoding="utf-8",
    )
    (promptfoo_dir / "promptfoo_react_provider.py").write_text(
        _render_promptfoo_provider_script(Path(__file__).resolve().parents[2]),
        encoding="utf-8",
    )
    (promptfoo_dir / "promptfooconfig.yaml").write_text(
        _render_promptfoo_config(manifest),
        encoding="utf-8",
    )
    (standardized_dir / "result_layout.md").write_text(
        _render_result_layout(manifest),
        encoding="utf-8",
    )
    (output_dir / "issue199_platform_adapter_report.md").write_text(
        _render_report(manifest),
        encoding="utf-8",
    )
    return manifest, output_dir
