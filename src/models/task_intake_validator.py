from __future__ import annotations

import re
from collections.abc import Mapping, Set as AbstractSet

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | JsonObject | JsonArray
type JsonObject = dict[str, JsonValue]
type JsonArray = list[JsonValue]
type RegistryFieldView = Mapping[str, object]


def validate_registry_value(
    field_name: str,
    value: JsonValue,
    *,
    registry: Mapping[str, RegistryFieldView],
    allowed_tool_ids: AbstractSet[str],
) -> str | None:
    """校验 intake registry 字段值，保持原字段语义和错误信息。"""

    field = registry.get(field_name)
    if field is None:
        return f"unknown intake field: {field_name}"

    field_type = str(field["type"])
    validators = _validators(field)
    options = _options(field)
    return _VALIDATORS.get(field_type, _validate_passthrough)(
        field_name,
        value,
        validators=validators,
        options=options,
        allowed_tool_ids=allowed_tool_ids,
    )


def _validate_passthrough(
    field_name: str,
    value: JsonValue,
    *,
    validators: JsonObject,
    options: list[str],
    allowed_tool_ids: AbstractSet[str],
) -> str | None:
    _ = (field_name, value, validators, options, allowed_tool_ids)
    return None


def _validate_enum(
    field_name: str,
    value: JsonValue,
    *,
    validators: JsonObject,
    options: list[str],
    allowed_tool_ids: AbstractSet[str],
) -> str | None:
    _ = (validators, allowed_tool_ids)
    if value not in set(options):
        return f"{field_name} must be one of {options}"
    return None


def _validate_string(
    field_name: str,
    value: JsonValue,
    *,
    validators: JsonObject,
    options: list[str],
    allowed_tool_ids: AbstractSet[str],
) -> str | None:
    _ = (options, allowed_tool_ids)
    if not isinstance(value, str) or not value.strip():
        return f"{field_name} must be a non-empty string"
    min_length = int(_numeric_validator_value(validators, "min_length", 0))
    max_length = int(_numeric_validator_value(validators, "max_length", len(value)))
    if len(value) < min_length:
        return f"{field_name} is shorter than allowed"
    if len(value) > max_length:
        return f"{field_name} is longer than allowed"
    return None


def _validate_boolean(
    field_name: str,
    value: JsonValue,
    *,
    validators: JsonObject,
    options: list[str],
    allowed_tool_ids: AbstractSet[str],
) -> str | None:
    _ = (validators, options, allowed_tool_ids)
    if not isinstance(value, bool):
        return f"{field_name} must be a boolean"
    return None


def _validate_integer(
    field_name: str,
    value: JsonValue,
    *,
    validators: JsonObject,
    options: list[str],
    allowed_tool_ids: AbstractSet[str],
) -> str | None:
    _ = (options, allowed_tool_ids)
    if not isinstance(value, int) or isinstance(value, bool):
        return f"{field_name} must be an integer"
    minimum = int(_numeric_validator_value(validators, "min", value))
    maximum = int(_numeric_validator_value(validators, "max", value))
    if value < minimum or value > maximum:
        return f"{field_name} is outside allowed range"
    return None


def _validate_number(
    field_name: str,
    value: JsonValue,
    *,
    validators: JsonObject,
    options: list[str],
    allowed_tool_ids: AbstractSet[str],
) -> str | None:
    _ = (options, allowed_tool_ids)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return f"{field_name} must be a number"
    minimum = _numeric_validator_value(validators, "min", value)
    maximum = _numeric_validator_value(validators, "max", value)
    if value < minimum or value > maximum:
        return f"{field_name} is outside allowed range"
    return None


def _validate_object(
    field_name: str,
    value: JsonValue,
    *,
    validators: JsonObject,
    options: list[str],
    allowed_tool_ids: AbstractSet[str],
) -> str | None:
    _ = (options, allowed_tool_ids)
    if not isinstance(value, dict):
        return f"{field_name} must be an object"
    allowed_keys = validators.get("allowed_keys")
    if isinstance(allowed_keys, list):
        allowed = {item for item in allowed_keys if isinstance(item, str)}
        unknown = sorted(str(key) for key in value if str(key) not in allowed)
        if unknown:
            return f"{field_name} contains unknown keys: {', '.join(unknown)}"
    for item in value.values():
        if not isinstance(item, (int, float)) or isinstance(item, bool) or item < 0:
            return f"{field_name} values must be non-negative numbers"
    return None


def _validate_integer_range(
    field_name: str,
    value: JsonValue,
    *,
    validators: JsonObject,
    options: list[str],
    allowed_tool_ids: AbstractSet[str],
) -> str | None:
    _ = (options, allowed_tool_ids)
    minimum = int(_numeric_validator_value(validators, "min", 0))
    maximum = int(_numeric_validator_value(validators, "max", 0))
    if (
        not isinstance(value, list)
        or len(value) != 2
        or not all(isinstance(item, int) and not isinstance(item, bool) for item in value)
    ):
        return f"{field_name} must be [min, max] integers"
    lower = value[0]
    upper = value[1]
    if not isinstance(lower, int) or not isinstance(upper, int):
        return f"{field_name} must be [min, max] integers"
    if lower > upper or lower < minimum or upper > maximum:
        return f"{field_name} must be [min, max] integers"
    return None


def _validate_protein_sequence(
    field_name: str,
    value: JsonValue,
    *,
    validators: JsonObject,
    options: list[str],
    allowed_tool_ids: AbstractSet[str],
) -> str | None:
    _ = (options, allowed_tool_ids)
    if not isinstance(value, str) or not value.strip():
        return f"{field_name} must be a non-empty sequence"
    alphabet = set(_string_validator_value(validators, "alphabet", ""))
    invalid = set(value.upper()) - alphabet
    if invalid:
        return f"{field_name} contains invalid residues: {''.join(sorted(invalid))}"
    return None


def _validate_string_list(
    field_name: str,
    value: JsonValue,
    *,
    validators: JsonObject,
    options: list[str],
    allowed_tool_ids: AbstractSet[str],
) -> str | None:
    _ = (validators, options, allowed_tool_ids)
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        return f"{field_name} must be a list of strings"
    return None


def _validate_tool_id_list(
    field_name: str,
    value: JsonValue,
    *,
    validators: JsonObject,
    options: list[str],
    allowed_tool_ids: AbstractSet[str],
) -> str | None:
    _ = (validators, options)
    base_error = _validate_string_list(
        field_name,
        value,
        validators={},
        options=[],
        allowed_tool_ids=allowed_tool_ids,
    )
    if base_error is not None:
        return base_error
    if not isinstance(value, list):
        return f"{field_name} must be a list of strings"
    values = {item for item in value if isinstance(item, str)}
    invalid_tool_ids = sorted(values - set(allowed_tool_ids))
    if invalid_tool_ids:
        return f"{field_name} contains unknown tool_id(s): {', '.join(invalid_tool_ids)}"
    return None


def _validate_residue_list(
    field_name: str,
    value: JsonValue,
    *,
    validators: JsonObject,
    options: list[str],
    allowed_tool_ids: AbstractSet[str],
) -> str | None:
    _ = (validators, options, allowed_tool_ids)
    if not isinstance(value, list) or not all(
        isinstance(item, str) and re.match(r"^[A-Z][0-9]+$", item) for item in value
    ):
        return f"{field_name} must be residue ids like A42"
    return None


def _validate_artifact_ref_list(
    field_name: str,
    value: JsonValue,
    *,
    validators: JsonObject,
    options: list[str],
    allowed_tool_ids: AbstractSet[str],
) -> str | None:
    _ = (validators, options, allowed_tool_ids)
    if not isinstance(value, list):
        return f"{field_name} must be a list of artifact refs"
    for index, raw_artifact in enumerate(value):
        if not isinstance(raw_artifact, dict):
            return f"{field_name}[{index}] must be an object"
        error = _validate_single_artifact_ref(field_name, index, raw_artifact)
        if error is not None:
            return error
    return None


def _validate_single_artifact_ref(
    field_name: str,
    index: int,
    artifact: JsonObject,
) -> str | None:
    for validator in (
        _validate_artifact_kind,
        _validate_artifact_reference_presence,
        _validate_artifact_id,
        _validate_artifact_uri,
        _validate_artifact_path,
        _validate_artifact_task_ref,
    ):
        error = validator(field_name, index, artifact)
        if error is not None:
            return error
    return None


def _validate_artifact_kind(
    field_name: str,
    index: int,
    artifact: JsonObject,
) -> str | None:
    kind = artifact.get("kind")
    if not isinstance(kind, str) or not kind.strip():
        return f"{field_name}[{index}].kind must be a non-empty string"
    return None


def _validate_artifact_reference_presence(
    field_name: str,
    index: int,
    artifact: JsonObject,
) -> str | None:
    ref_values = [
        artifact.get("artifact_id"),
        artifact.get("uri"),
        artifact.get("path"),
        artifact.get("ref"),
    ]
    if not any(isinstance(item, str) and item.strip() for item in ref_values):
        return f"{field_name}[{index}] must include artifact_id, uri, path, or ref"
    return None


def _validate_artifact_id(
    field_name: str,
    index: int,
    artifact: JsonObject,
) -> str | None:
    artifact_id = artifact.get("artifact_id")
    if isinstance(artifact_id, str) and not re.match(r"^[A-Za-z0-9_.:-]+$", artifact_id):
        return f"{field_name}[{index}].artifact_id is invalid"
    return None


def _validate_artifact_uri(
    field_name: str,
    index: int,
    artifact: JsonObject,
) -> str | None:
    uri = artifact.get("uri")
    if isinstance(uri, str) and not (
        uri.startswith("artifact://") or uri.startswith("task://")
    ):
        return f"{field_name}[{index}].uri must use artifact:// or task://"
    return None


def _validate_artifact_path(
    field_name: str,
    index: int,
    artifact: JsonObject,
) -> str | None:
    path = artifact.get("path")
    if isinstance(path, str) and (
        path.startswith("/") or path.startswith("~") or ".." in path.split("/") or not path.strip()
    ):
        return f"{field_name}[{index}].path must be a safe relative path"
    return None


def _validate_artifact_task_ref(
    field_name: str,
    index: int,
    artifact: JsonObject,
) -> str | None:
    ref = artifact.get("ref")
    if isinstance(ref, str) and not re.match(
        r"^task_[A-Za-z0-9_:-]+\.[A-Za-z][A-Za-z0-9_.-]*$",
        ref,
    ):
        return f"{field_name}[{index}].ref must look like task_id.artifact_key"
    return None


def _validators(field: RegistryFieldView) -> JsonObject:
    validators = field.get("validators")
    return validators if isinstance(validators, dict) else {}


def _options(field: RegistryFieldView) -> list[str]:
    options = field.get("options")
    if not isinstance(options, list):
        return []
    return [item for item in options if isinstance(item, str)]


def _numeric_validator_value(
    validators: JsonObject,
    key: str,
    default: int | float,
) -> int | float:
    value = validators.get(key)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    return default


def _string_validator_value(
    validators: JsonObject,
    key: str,
    default: str,
) -> str:
    value = validators.get(key)
    if isinstance(value, str):
        return value
    return default


_VALIDATORS = {
    "enum": _validate_enum,
    "string": _validate_string,
    "boolean": _validate_boolean,
    "integer": _validate_integer,
    "number": _validate_number,
    "object": _validate_object,
    "integer_range": _validate_integer_range,
    "protein_sequence": _validate_protein_sequence,
    "string_list": _validate_string_list,
    "tool_id_list": _validate_tool_id_list,
    "residue_list": _validate_residue_list,
    "artifact_ref_list": _validate_artifact_ref_list,
}
