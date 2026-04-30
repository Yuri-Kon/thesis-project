from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import NotRequired, TypeGuard, TypedDict, cast

DEFAULT_KG_PATH = Path(__file__).resolve().parent / "protein_tool_kg.json"


class ToolKGError(RuntimeError):
    """Raised when ProteinToolKG data cannot be loaded or parsed."""


type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | JsonObject | JsonArray
type JsonObject = dict[str, JsonValue]
type JsonArray = list[JsonValue]


class ExecutionSpec(TypedDict, total=False):
    backend: str
    provider: str


class IoSpec(TypedDict, total=False):
    inputs: dict[str, JsonValue]
    outputs: dict[str, JsonValue]


class ToolNode(TypedDict, total=False):
    id: str
    capabilities: list[str]
    safety_level: int | float
    execution: str | ExecutionSpec
    io: IoSpec
    failure_modes: list[str]


class ToolKG(TypedDict, total=False):
    kg_id: str
    version: str
    capabilities: list[JsonObject]
    io_types: list[JsonObject]
    constraints: list[JsonObject]
    tools: list[ToolNode]
    metadata: NotRequired[JsonObject]


def load_tool_kg(path: Path | None = None) -> dict[str, object]:
    """加载 ProteinToolKG JSON 文件。"""

    payload = _read_tool_kg_payload(path)
    return cast(dict[str, object], dict(_json_object(payload)))


def get_tool_nodes(path: Path | None = None) -> list[ToolNode]:
    """读取 KG 中的工具节点列表。"""

    kg = _load_parsed_tool_kg(path)
    return kg.get("tools", [])


def _read_tool_kg_payload(path: Path | None = None) -> Mapping[object, object]:
    kg_path = path or DEFAULT_KG_PATH
    try:
        with kg_path.open("r", encoding="utf-8") as handle:
            payload = _load_json(handle.read())
    except FileNotFoundError as exc:
        raise ToolKGError(f"ProteinToolKG file not found: {kg_path}") from exc
    except json.JSONDecodeError as exc:
        raise ToolKGError(f"ProteinToolKG JSON is invalid: {kg_path}") from exc
    if not isinstance(payload, dict):
        raise ToolKGError("ProteinToolKG root must be a JSON object")
    return cast(Mapping[object, object], payload)


def _load_parsed_tool_kg(path: Path | None = None) -> ToolKG:
    return _parse_tool_kg(_read_tool_kg_payload(path))


def find_tools_by_capability(
    capability: str,
    constraints: Mapping[str, JsonValue] | None = None,
    *,
    path: Path | None = None,
) -> list[ToolNode]:
    """按能力和可选约束筛选工具。"""

    tools = get_tool_nodes(path)
    filtered = [
        tool
        for tool in tools
        if capability in _string_list_field(tool, "capabilities")
    ]
    if constraints:
        safety_level = constraints.get("safety_level")
        if isinstance(safety_level, int | float):
            filtered = [
                tool
                for tool in filtered
                if _number_field(tool, "safety_level") <= safety_level
            ]
    return filtered


def find_tools_by_backend(
    backend: str,
    provider: str | None = None,
    *,
    path: Path | None = None,
) -> list[ToolNode]:
    """Find tools by execution backend and optional provider."""
    tools = get_tool_nodes(path)
    matched: list[ToolNode] = []

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


def find_compatible_next(
    tool: Mapping[str, JsonValue],
    *,
    path: Path | None = None,
) -> list[ToolNode]:
    """查找可消费当前工具输出的后续工具。"""

    outputs = _io_keys(tool, "outputs")
    if not outputs:
        return []
    compatible: list[ToolNode] = []
    for candidate in get_tool_nodes(path):
        if _string_field(candidate, "id") == _string_field(tool, "id"):
            continue
        inputs = _io_keys(candidate, "inputs")
        if inputs and inputs.issubset(outputs):
            compatible.append(candidate)
    return compatible


def find_alternative_tools(
    failed_tool: Mapping[str, JsonValue],
    context_io: Iterable[str],
    safety_level: int | None = None,
    error_pattern: str | None = None,
    *,
    path: Path | None = None,
) -> list[ToolNode]:
    """按能力、错误模式和当前 I/O 上下文推荐替代工具。"""

    available_inputs = set(context_io)
    capabilities = _string_list_field(failed_tool, "capabilities")
    capability = capabilities[0] if capabilities else ""
    candidates = [
        tool
        for tool in find_tools_by_capability(capability, path=path)
        if _string_field(tool, "id") != _string_field(failed_tool, "id")
    ]
    if safety_level is not None:
        candidates = [
            tool
            for tool in candidates
            if _number_field(tool, "safety_level") <= safety_level
        ]
    if error_pattern:
        candidates = [
            tool
            for tool in candidates
            if error_pattern not in _string_list_field(tool, "failure_modes")
        ]
    viable: list[ToolNode] = []
    for tool in candidates:
        inputs = _io_keys(tool, "inputs")
        if inputs.issubset(available_inputs):
            viable.append(tool)
    return viable


def _load_json(text: str) -> object:
    return cast(object, json.loads(text))


def _parse_tool_kg(payload: Mapping[object, object]) -> ToolKG:
    tools = payload.get("tools", [])
    if not isinstance(tools, list):
        raise ToolKGError("ProteinToolKG 'tools' must be a list")

    kg = cast(ToolKG, cast(object, _json_object(payload)))
    for key in ("kg_id", "version"):
        value = payload.get(key)
        if isinstance(value, str):
            kg[key] = value

    for key in ("capabilities", "io_types", "constraints"):
        value = payload.get(key)
        if isinstance(value, list):
            kg[key] = _json_object_list(cast(list[object], value))

    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        kg["metadata"] = _json_object(cast(Mapping[object, object], metadata))

    kg["tools"] = _tool_nodes(cast(list[object], tools))
    return kg


def _tool_nodes(values: list[object]) -> list[ToolNode]:
    nodes: list[ToolNode] = []
    for value in values:
        if not isinstance(value, dict):
            continue
        node = _tool_node(cast(Mapping[object, object], value))
        nodes.append(node)
    return nodes


def _tool_node(value: Mapping[object, object]) -> ToolNode:
    node = cast(ToolNode, cast(object, _json_object(value)))
    tool_id = value.get("id")
    if isinstance(tool_id, str):
        node["id"] = tool_id

    capabilities = value.get("capabilities")
    if isinstance(capabilities, list):
        node["capabilities"] = _string_list(cast(list[object], capabilities))

    safety_level = value.get("safety_level")
    if isinstance(safety_level, int | float):
        node["safety_level"] = safety_level

    execution = value.get("execution")
    if isinstance(execution, str):
        node["execution"] = execution
    elif isinstance(execution, dict):
        node["execution"] = _execution_spec(cast(Mapping[object, object], execution))

    io_value = value.get("io")
    if isinstance(io_value, dict):
        node["io"] = _io_spec(cast(Mapping[object, object], io_value))

    failure_modes = value.get("failure_modes")
    if isinstance(failure_modes, list):
        node["failure_modes"] = _string_list(cast(list[object], failure_modes))

    return node


def _execution_spec(value: Mapping[object, object]) -> ExecutionSpec:
    execution: ExecutionSpec = {}
    backend = value.get("backend")
    if isinstance(backend, str):
        execution["backend"] = backend
    provider = value.get("provider")
    if isinstance(provider, str):
        execution["provider"] = provider
    return execution


def _io_spec(value: Mapping[object, object]) -> IoSpec:
    io: IoSpec = {}
    for key in ("inputs", "outputs"):
        field = value.get(key)
        if isinstance(field, dict):
            io[key] = _json_object(cast(Mapping[object, object], field))
    return io


def _json_object_list(values: list[object]) -> list[JsonObject]:
    objects: list[JsonObject] = []
    for value in values:
        if isinstance(value, dict):
            objects.append(_json_object(cast(Mapping[object, object], value)))
    return objects


def _json_object(value: Mapping[object, object]) -> JsonObject:
    result: JsonObject = {}
    for key, item in value.items():
        if isinstance(key, str) and _is_json_value(item):
            result[key] = item
    return result


def _is_json_value(value: object) -> TypeGuard[JsonValue]:
    if value is None or isinstance(value, str | int | float | bool):
        return True
    if isinstance(value, list):
        return all(_is_json_value(item) for item in cast(Sequence[object], value))
    if isinstance(value, dict):
        return all(
            isinstance(key, str) and _is_json_value(item)
            for key, item in cast(Mapping[object, object], value).items()
        )
    return False


def _string_list(values: list[object]) -> list[str]:
    return [value for value in values if isinstance(value, str)]


def _string_field(value: Mapping[str, object], key: str) -> str | None:
    field = value.get(key)
    if isinstance(field, str):
        return field
    return None


def _string_list_field(value: Mapping[str, object], key: str) -> list[str]:
    field = value.get(key)
    if isinstance(field, list):
        return _string_list(cast(list[object], field))
    return []


def _number_field(value: Mapping[str, object], key: str) -> int | float:
    field = value.get(key)
    if isinstance(field, int | float):
        return field
    return 0


def _io_keys(value: Mapping[str, object], direction: str) -> set[str]:
    io = value.get("io")
    if not isinstance(io, dict):
        return set()
    io_mapping = cast(Mapping[object, object], io)
    ports = io_mapping.get(direction)
    if not isinstance(ports, dict):
        return set()
    port_mapping = cast(Mapping[object, object], ports)
    return {key for key in port_mapping if isinstance(key, str)}
