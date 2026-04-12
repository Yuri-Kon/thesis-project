from __future__ import annotations

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

        numbered_steps = len(re.findall(r"(?m)^\s*\d+\.", answer))
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
