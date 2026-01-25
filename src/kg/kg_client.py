from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List

DEFAULT_KG_PATH = Path(__file__).resolve().parent / "protein_tool_kg.json"


class ToolKGError(RuntimeError):
    """Raised when ProteinToolKG data cannot be loaded or parsed."""


def load_tool_kg(path: Path | None = None) -> dict:
    kg_path = path or DEFAULT_KG_PATH
    try:
        with kg_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise ToolKGError(f"ProteinToolKG file not found: {kg_path}") from exc
    except json.JSONDecodeError as exc:
        raise ToolKGError(f"ProteinToolKG JSON is invalid: {kg_path}") from exc


def get_tool_nodes(path: Path | None = None) -> List[dict]:
    kg = load_tool_kg(path)
    tools = kg.get("tools", [])
    if not isinstance(tools, list):
        raise ToolKGError("ProteinToolKG 'tools' must be a list")
    return tools


def find_tools_by_capability(
    capability: str,
    constraints: dict | None = None,
    *,
    path: Path | None = None,
) -> List[dict]:
    tools = get_tool_nodes(path)
    filtered = [
        tool
        for tool in tools
        if capability in tool.get("capabilities", [])
    ]
    if constraints:
        safety_level = constraints.get("safety_level")
        if safety_level is not None:
            filtered = [
                tool
                for tool in filtered
                if tool.get("safety_level", 0) <= safety_level
            ]
    return filtered


def find_tools_by_backend(
    backend: str,
    provider: str | None = None,
    *,
    path: Path | None = None,
) -> List[dict]:
    """Find tools by execution backend and optional provider."""
    tools = get_tool_nodes(path)
    matched: List[dict] = []

    for tool in tools:
        execution = tool.get("execution")
        if isinstance(execution, str):
            if provider is not None:
                continue
            if execution == backend:
                matched.append(tool)
            continue

        if isinstance(execution, dict):
            if execution.get("backend") != backend:
                continue
            if provider is not None and execution.get("provider") != provider:
                continue
            matched.append(tool)

    return matched


def find_compatible_next(tool: dict, *, path: Path | None = None) -> List[dict]:
    outputs = set(tool.get("io", {}).get("outputs", {}).keys())
    if not outputs:
        return []
    compatible = []
    for candidate in get_tool_nodes(path):
        if candidate.get("id") == tool.get("id"):
            continue
        inputs = set(candidate.get("io", {}).get("inputs", {}).keys())
        if inputs and inputs.issubset(outputs):
            compatible.append(candidate)
    return compatible


def find_alternative_tools(
    failed_tool: dict,
    context_io: Iterable[str],
    safety_level: int | None = None,
    error_pattern: str | None = None,
    *,
    path: Path | None = None,
) -> List[dict]:
    available_inputs = set(context_io)
    capabilities = failed_tool.get("capabilities", [])
    capability = capabilities[0] if capabilities else ""
    candidates = [
        tool
        for tool in find_tools_by_capability(capability, path=path)
        if tool.get("id") != failed_tool.get("id")
    ]
    if safety_level is not None:
        candidates = [
            tool
            for tool in candidates
            if tool.get("safety_level", 0) <= safety_level
        ]
    if error_pattern:
        candidates = [
            tool
            for tool in candidates
            if error_pattern not in tool.get("failure_modes", [])
        ]
    viable = []
    for tool in candidates:
        inputs = set(tool.get("io", {}).get("inputs", {}).keys())
        if inputs.issubset(available_inputs):
            viable.append(tool)
    return viable
