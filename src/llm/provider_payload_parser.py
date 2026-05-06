from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Protocol, Sequence


_CANONICAL_REFERENCE_RE = re.compile(r"^(S\d+)\.([A-Za-z_][A-Za-z0-9_]*)$")
_INDEXED_REFERENCE_RE = re.compile(
    r"^(S\d+)\.([A-Za-z_][A-Za-z0-9_]*)\[\d+\](?:\.([A-Za-z_][A-Za-z0-9_]*))?$"
)
_STEP_REFERENCE_RE = re.compile(
    r"^\$?(?:(?:step|STEP)[_.-]?|S)?(\d+)(?:\.([A-Za-z_][A-Za-z0-9_]*))?$"
)
_TEMPLATE_REFERENCE_RE = re.compile(r"^\$\{([^{}]+)\}$")
_PLACEHOLDER_STEP_RE = re.compile(r"^<from_step_(\d+)(?:_([A-Za-z0-9_]+))?>$")
_TOOL_OUTPUT_RE = re.compile(
    r"^([A-Za-z_][A-Za-z0-9_-]*)\.output\.([A-Za-z_][A-Za-z0-9_]*)$"
)

_FORBIDDEN_LITERAL_FIELDS = {
    "sequence",
    "candidates",
    "pdb_path",
    "structure_results",
    "qc_metrics",
    "score_table",
    "top_k",
}
_PLACEHOLDER_FIELD_ALIASES = {
    "generated_sequence": "sequence",
    "predicted_pdb": "pdb_path",
    "predicted_structure": "structure_results",
    "structure": "structure_results",
    "pdb": "pdb_path",
    "seq": "sequence",
}


class ToolSpecLike(Protocol):
    """Provider 解析器所需的最小工具定义接口。"""

    id: str
    outputs: Sequence[str]


@dataclass(frozen=True)
class PayloadRepair:
    """一次已应用的轻量修复记录。"""

    path: str
    original: Any
    normalized: Any
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "original": self.original,
            "normalized": self.normalized,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class PayloadIssue:
    """一次无法自动修复的 payload 问题。"""

    code: str
    path: str
    message: str
    observed: Any = None
    repair_hint: str | None = None

    def as_dict(self) -> dict[str, Any]:
        payload = {
            "code": self.code,
            "path": self.path,
            "message": self.message,
            "observed": self.observed,
        }
        if self.repair_hint:
            payload["repair_hint"] = self.repair_hint
        return payload


@dataclass(frozen=True)
class ProviderPayloadParseResult:
    """Provider 输出的语法解析结果。"""

    normalized_payload: dict[str, Any] | None
    repairs: tuple[PayloadRepair, ...]
    issues: tuple[PayloadIssue, ...]

    @property
    def is_compliant(self) -> bool:
        return not self.issues


class ProviderPayloadParser:
    """Provider 输出语法解析器。

    负责：
    1. 解析 JSON-like 字符串；
    2. 识别并归一化常见占位符 / 模板引用；
    3. 收集无法自动修复的语法违规项。
    """

    def __init__(self, tool_registry: Sequence[ToolSpecLike] | None = None):
        self._registry_outputs = {
            spec.id: tuple(spec.outputs)
            for spec in (tool_registry or ())
            if getattr(spec, "id", None)
        }

    def parse(
        self,
        payload: Any,
        *,
        candidate_kind: str,
    ) -> ProviderPayloadParseResult:
        repairs: list[PayloadRepair] = []
        issues: list[PayloadIssue] = []

        normalized = _normalize_json_like_value(payload, path="$", repairs=repairs)
        if not isinstance(normalized, dict):
            issues.append(
                PayloadIssue(
                    code="PAYLOAD_NOT_OBJECT",
                    path="$",
                    message="provider payload must be a JSON object after syntax normalization",
                    observed=type(normalized).__name__,
                    repair_hint="return a single JSON object instead of text or arrays",
                )
            )
            return ProviderPayloadParseResult(
                normalized_payload=None,
                repairs=tuple(repairs),
                issues=tuple(issues),
            )

        normalized_payload = dict(normalized)
        if candidate_kind in {"plan", "replan", "plan_skeleton"}:
            normalized_payload = self._normalize_plan_payload(
                normalized_payload,
                repairs=repairs,
                issues=issues,
            )
        elif candidate_kind == "patch":
            normalized_payload = self._normalize_patch_payload(
                normalized_payload,
                repairs=repairs,
                issues=issues,
            )

        return ProviderPayloadParseResult(
            normalized_payload=normalized_payload,
            repairs=tuple(repairs),
            issues=tuple(issues),
        )

    def _normalize_plan_payload(
        self,
        payload: dict[str, Any],
        *,
        repairs: list[PayloadRepair],
        issues: list[PayloadIssue],
    ) -> dict[str, Any]:
        normalized = dict(payload)
        steps = normalized.get("steps")
        if isinstance(steps, list):
            normalized["steps"] = self._normalize_plan_steps(
                steps,
                path="$.steps",
                repairs=repairs,
                issues=issues,
            )
        elif "steps" in normalized:
            issues.append(
                PayloadIssue(
                    code="STEPS_NOT_ARRAY",
                    path="$.steps",
                    message="steps must be a JSON array",
                    observed=steps,
                    repair_hint="emit steps as an array of step objects, never as a string",
                )
            )
        return normalized

    def _normalize_patch_payload(
        self,
        payload: dict[str, Any],
        *,
        repairs: list[PayloadRepair],
        issues: list[PayloadIssue],
    ) -> dict[str, Any]:
        normalized = dict(payload)
        operations = normalized.get("operations")
        if isinstance(operations, list):
            normalized["operations"] = self._normalize_patch_operations(
                operations,
                path="$.operations",
                repairs=repairs,
                issues=issues,
            )
        elif "operations" in normalized:
            issues.append(
                PayloadIssue(
                    code="OPERATIONS_NOT_ARRAY",
                    path="$.operations",
                    message="operations must be a JSON array",
                    observed=operations,
                    repair_hint="emit operations as an array of PlanPatchOp objects",
                )
            )
        return normalized

    def _normalize_plan_steps(
        self,
        steps: list[Any],
        *,
        path: str,
        repairs: list[PayloadRepair],
        issues: list[PayloadIssue],
    ) -> list[Any]:
        step_id_map, tool_reference_map = _build_step_reference_maps(steps)
        normalized_steps: list[Any] = []
        field_source_map: dict[str, str] = {}

        for index, raw_step in enumerate(steps, start=1):
            step_path = f"{path}[{index - 1}]"
            if not isinstance(raw_step, dict):
                normalized_steps.append(raw_step)
                continue

            step = dict(raw_step)
            canonical_id = f"S{index}"
            if step.get("id") != canonical_id:
                repairs.append(
                    PayloadRepair(
                        path=f"{step_path}.id",
                        original=step.get("id"),
                        normalized=canonical_id,
                        reason="canonicalize sequential step id",
                    )
                )
            step["id"] = canonical_id

            inputs = step.get("inputs")
            if isinstance(inputs, dict):
                normalized_inputs: dict[str, Any] = {}
                for key, value in inputs.items():
                    normalized_inputs[key] = self._normalize_input_value(
                        value,
                        path=f"{step_path}.inputs.{key}",
                        input_key=key,
                        step_id_map=step_id_map,
                        tool_reference_map=tool_reference_map,
                        field_source_map=field_source_map,
                        repairs=repairs,
                        issues=issues,
                    )
                step["inputs"] = normalized_inputs
            elif "inputs" in step and inputs is not None:
                issues.append(
                    PayloadIssue(
                        code="INPUTS_NOT_OBJECT",
                        path=f"{step_path}.inputs",
                        message="step inputs must be an object",
                        observed=inputs,
                        repair_hint="emit each step.inputs as a JSON object",
                    )
                )

            normalized_steps.append(step)
            for output_name in self._collect_output_fields(step):
                field_source_map.setdefault(output_name, canonical_id)

        return normalized_steps

    def _normalize_patch_operations(
        self,
        operations: list[Any],
        *,
        path: str,
        repairs: list[PayloadRepair],
        issues: list[PayloadIssue],
    ) -> list[Any]:
        pseudo_steps: list[dict[str, Any]] = []
        for operation in operations:
            if not isinstance(operation, dict):
                continue
            step = operation.get("step")
            if not isinstance(step, dict):
                continue
            pseudo_step = dict(step)
            target = operation.get("target")
            if "id" not in pseudo_step and isinstance(target, str):
                pseudo_step["id"] = target
            pseudo_steps.append(pseudo_step)

        step_id_map, tool_reference_map = _build_step_reference_maps(pseudo_steps)
        normalized_operations: list[Any] = []
        field_source_map: dict[str, str] = {}

        for index, raw_operation in enumerate(operations, start=1):
            op_path = f"{path}[{index - 1}]"
            if not isinstance(raw_operation, dict):
                normalized_operations.append(raw_operation)
                continue

            operation = dict(raw_operation)
            target = operation.get("target")
            if isinstance(target, str):
                normalized_target = _normalize_step_identifier(
                    target,
                    step_id_map=step_id_map,
                )
                if normalized_target != target:
                    repairs.append(
                        PayloadRepair(
                            path=f"{op_path}.target",
                            original=target,
                            normalized=normalized_target,
                            reason="canonicalize patch target step id",
                        )
                    )
                operation["target"] = normalized_target

            step = operation.get("step")
            if isinstance(step, dict):
                normalized_step = dict(step)
                step_id = normalized_step.get("id")
                if isinstance(step_id, str):
                    normalized_step_id = _normalize_step_identifier(
                        step_id,
                        step_id_map=step_id_map,
                    )
                    if normalized_step_id != step_id:
                        repairs.append(
                            PayloadRepair(
                                path=f"{op_path}.step.id",
                                original=step_id,
                                normalized=normalized_step_id,
                                reason="canonicalize patch step id",
                            )
                        )
                    normalized_step["id"] = normalized_step_id

                inputs = normalized_step.get("inputs")
                if isinstance(inputs, dict):
                    normalized_inputs: dict[str, Any] = {}
                    for key, value in inputs.items():
                        normalized_inputs[key] = self._normalize_input_value(
                            value,
                            path=f"{op_path}.step.inputs.{key}",
                            input_key=key,
                            step_id_map=step_id_map,
                            tool_reference_map=tool_reference_map,
                            field_source_map=field_source_map,
                            repairs=repairs,
                            issues=issues,
                        )
                    normalized_step["inputs"] = normalized_inputs
                operation["step"] = normalized_step

                normalized_step_id = normalized_step.get("id")
                if isinstance(normalized_step_id, str):
                    for output_name in self._collect_output_fields(normalized_step):
                        field_source_map.setdefault(output_name, normalized_step_id)

            normalized_operations.append(operation)
        return normalized_operations

    def _normalize_input_value(
        self,
        value: Any,
        *,
        path: str,
        input_key: str | None,
        step_id_map: dict[str, str],
        tool_reference_map: dict[str, str],
        field_source_map: dict[str, str],
        repairs: list[PayloadRepair],
        issues: list[PayloadIssue],
    ) -> Any:
        normalized = _normalize_json_like_value(value, path=path, repairs=repairs)

        if isinstance(normalized, list):
            return [
                self._normalize_input_value(
                    item,
                    path=f"{path}[{index}]",
                    input_key=input_key,
                    step_id_map=step_id_map,
                    tool_reference_map=tool_reference_map,
                    field_source_map=field_source_map,
                    repairs=repairs,
                    issues=issues,
                )
                for index, item in enumerate(normalized)
            ]

        if isinstance(normalized, dict):
            return {
                key: self._normalize_input_value(
                    item,
                    path=f"{path}.{key}",
                    input_key=key,
                    step_id_map=step_id_map,
                    tool_reference_map=tool_reference_map,
                    field_source_map=field_source_map,
                    repairs=repairs,
                    issues=issues,
                )
                for key, item in normalized.items()
            }

        if not isinstance(normalized, str):
            return normalized

        parsed = self._parse_reference_token(
            normalized,
            input_key=input_key,
            step_id_map=step_id_map,
            tool_reference_map=tool_reference_map,
            field_source_map=field_source_map,
        )
        if parsed is not None:
            if parsed != normalized:
                repairs.append(
                    PayloadRepair(
                        path=path,
                        original=normalized,
                        normalized=parsed,
                        reason="normalize non-canonical reference token",
                    )
                )
            return parsed

        if _looks_like_forbidden_reference(normalized):
            issues.append(
                PayloadIssue(
                    code="REFERENCE_SYNTAX_INVALID",
                    path=path,
                    message="reference token is not compliant with S<n>.field grammar",
                    observed=normalized,
                    repair_hint=(
                        "rewrite the value using S<n>.field and remove "
                        "${...}, $..., <...>, auto, or bare placeholder tokens"
                    ),
                )
            )
        return normalized

    def _parse_reference_token(
        self,
        value: str,
        *,
        input_key: str | None,
        step_id_map: dict[str, str],
        tool_reference_map: dict[str, str],
        field_source_map: dict[str, str],
    ) -> str | None:
        text = value.strip()
        if not text:
            return None

        canonical = _CANONICAL_REFERENCE_RE.fullmatch(text)
        if canonical is not None:
            return _normalize_reference_field_for_input_key(
                text,
                input_key=input_key,
            )

        indexed = _INDEXED_REFERENCE_RE.fullmatch(text)
        if indexed is not None:
            head = indexed.group(1)
            field = indexed.group(3) or indexed.group(2)
            return _normalize_reference_field_for_input_key(
                f"{head}.{field}",
                input_key=input_key,
            )

        symbolic = _normalize_symbolic_reference(
            text,
            input_key=input_key,
            step_id_map=step_id_map,
            tool_reference_map=tool_reference_map,
        )
        if symbolic is not None:
            return _normalize_reference_field_for_input_key(
                symbolic,
                input_key=input_key,
            )

        template = _TEMPLATE_REFERENCE_RE.fullmatch(text)
        if template is not None:
            inner = template.group(1).strip()
            if inner.lower().startswith("step."):
                inner = "S" + inner.split(".", 1)[1]
            elif inner.lower().startswith("step_"):
                inner = "S" + inner.split("_", 1)[1]
            parsed_inner = self._parse_reference_token(
                inner,
                input_key=input_key,
                step_id_map=step_id_map,
                tool_reference_map=tool_reference_map,
                field_source_map=field_source_map,
            )
            if parsed_inner is not None:
                return parsed_inner

        placeholder = _PLACEHOLDER_STEP_RE.fullmatch(text)
        if placeholder is not None:
            step_token = placeholder.group(1)
            field = placeholder.group(2)
            canonical_step = step_id_map.get(step_token)
            if canonical_step is None:
                return None
            resolved_field = _normalize_placeholder_field(
                field,
                input_key=input_key,
            )
            if resolved_field is None:
                return None
            return f"{canonical_step}.{resolved_field}"

        field_placeholder = None
        if text.startswith("<") and text.endswith(">"):
            field_placeholder = _normalize_placeholder_field(
                text[1:-1],
                input_key=input_key,
            )
        if field_placeholder:
            return _infer_reference_from_field(
                field_placeholder,
                field_source_map=field_source_map,
            )

        step_token = _STEP_REFERENCE_RE.fullmatch(text)
        if step_token is not None:
            canonical_step = step_id_map.get(step_token.group(1))
            if canonical_step is None:
                return None
            field = step_token.group(2) or _infer_reference_field(input_key)
            if field is None:
                return None
            return f"{canonical_step}.{field}"

        tool_output = _TOOL_OUTPUT_RE.fullmatch(text)
        if tool_output is not None:
            tool_name = tool_output.group(1).strip()
            field = tool_output.group(2).strip()
            step_id = tool_reference_map.get(tool_name)
            if step_id is None:
                return None
            return _normalize_reference_field_for_input_key(
                f"{step_id}.{field}",
                input_key=input_key,
            )

        normalized_token = text.strip("$")
        if normalized_token.lower() == "auto":
            expected_field = _infer_reference_field(input_key)
            if expected_field is None:
                return None
            return _infer_reference_from_field(
                expected_field,
                field_source_map=field_source_map,
            )

        field_token = _normalize_placeholder_field(
            normalized_token,
            input_key=input_key,
        )
        if field_token is not None and normalized_token.upper() == normalized_token:
            return _infer_reference_from_field(
                field_token,
                field_source_map=field_source_map,
            )

        return None

    def _collect_output_fields(self, step: dict[str, Any]) -> tuple[str, ...]:
        tool_name = step.get("tool")
        if not isinstance(tool_name, str):
            return ()
        outputs = self._registry_outputs.get(tool_name)
        if outputs:
            return outputs
        return ()


class ProviderPayloadValidationError(ValueError):
    """Provider 输出在 syntax/schema/executability 任一阶段失败。"""

    def __init__(
        self,
        *,
        candidate_kind: str,
        failure_type: str,
        issues: Sequence[dict[str, Any]],
        normalized_payload: dict[str, Any] | None = None,
        parser_repairs: Sequence[dict[str, Any]] | None = None,
        attempts: int = 1,
    ) -> None:
        self.candidate_kind = candidate_kind
        self.failure_type = failure_type
        self.issues = [dict(issue) for issue in issues]
        self.normalized_payload = (
            dict(normalized_payload) if isinstance(normalized_payload, dict) else None
        )
        self.parser_repairs = [dict(repair) for repair in (parser_repairs or ())]
        self.attempts = attempts
        summary = self.issues[0]["message"] if self.issues else failure_type
        super().__init__(f"{candidate_kind}:{failure_type}: {summary}")

    def with_attempts(self, attempts: int) -> "ProviderPayloadValidationError":
        return ProviderPayloadValidationError(
            candidate_kind=self.candidate_kind,
            failure_type=self.failure_type,
            issues=self.issues,
            normalized_payload=self.normalized_payload,
            parser_repairs=self.parser_repairs,
            attempts=attempts,
        )

    def as_event_payload(self) -> dict[str, Any]:
        return {
            "failure_code": self.failure_type,
            "failures": list(self.issues),
            "candidate_kind": self.candidate_kind,
            "attempts": self.attempts,
            "parser_repairs": list(self.parser_repairs),
        }


def _build_step_reference_maps(
    steps: Sequence[Any],
) -> tuple[dict[str, str], dict[str, str]]:
    step_id_map: dict[str, str] = {}
    tool_to_step_ids: dict[str, list[str]] = {}
    for index, raw_step in enumerate(steps, start=1):
        if not isinstance(raw_step, dict):
            continue
        canonical_id = f"S{index}"
        raw_id = raw_step.get("id")
        if isinstance(raw_id, str):
            compact = raw_id.strip()
            if compact:
                step_id_map[compact] = canonical_id
                step_id_map[compact.lower()] = canonical_id
                if compact.isdigit():
                    step_id_map[f"step_{compact}"] = canonical_id
        step_id_map[str(index)] = canonical_id
        step_id_map[f"step_{index}"] = canonical_id
        step_id_map[f"s{index}"] = canonical_id

        tool_name = raw_step.get("tool")
        if isinstance(tool_name, str) and tool_name.strip():
            tool_to_step_ids.setdefault(tool_name.strip(), []).append(canonical_id)

    tool_reference_map = {
        tool_name: step_ids[0]
        for tool_name, step_ids in tool_to_step_ids.items()
        if len(step_ids) == 1
    }
    return step_id_map, tool_reference_map


def _normalize_step_identifier(
    value: str,
    *,
    step_id_map: dict[str, str],
) -> str:
    normalized = step_id_map.get(value.strip())
    if normalized is not None:
        return normalized
    return step_id_map.get(value.strip().lower(), value)


def _normalize_symbolic_reference(
    value: str,
    *,
    input_key: str | None,
    step_id_map: dict[str, str],
    tool_reference_map: dict[str, str],
) -> str | None:
    head, sep, tail = value.partition(".")
    if not sep or not tail:
        return None

    normalized_head = step_id_map.get(head.strip()) or step_id_map.get(head.strip().lower())
    normalized_field = tail.strip()
    if normalized_head is None and normalized_field.startswith("output."):
        normalized_head = tool_reference_map.get(head.strip())
        normalized_field = normalized_field.removeprefix("output.").strip()
    if normalized_head is None or not normalized_field:
        return None
    return _normalize_reference_field_for_input_key(
        f"{normalized_head}.{normalized_field}",
        input_key=input_key,
    )


def _infer_reference_field(input_key: str | None) -> str | None:
    if not isinstance(input_key, str):
        return None
    lookup = {
        "sequence": "sequence",
        "pdb_path": "pdb_path",
        "candidates": "candidates",
        "structure_results": "structure_results",
        "qc_metrics": "qc_metrics",
        "score_table": "score_table",
        "top_k": "top_k",
    }
    return lookup.get(input_key.strip())


def _normalize_reference_field_for_input_key(
    value: str,
    *,
    input_key: str | None,
) -> str:
    head, sep, tail = value.partition(".")
    if not sep or not tail:
        return value
    expected_field = _infer_reference_field(input_key)
    if expected_field is None:
        return value
    normalized_field = tail.strip()
    if normalized_field == expected_field:
        return value
    if not _should_rewrite_reference_field(
        input_key=input_key,
        current_field=normalized_field,
        expected_field=expected_field,
    ):
        return value
    return f"{head.strip()}.{expected_field}"


def _should_rewrite_reference_field(
    *,
    input_key: str | None,
    current_field: str,
    expected_field: str,
) -> bool:
    if not isinstance(input_key, str):
        return False
    normalized_key = input_key.strip()
    if normalized_key == "sequence" and current_field in {"candidates", "sequence_candidates"}:
        return True
    if normalized_key == "candidates" and current_field == "sequence":
        return True
    if normalized_key == "pdb_path" and current_field in {"structure_pdb", "structure_path", "cif_path"}:
        return True
    if normalized_key == "structure_results" and current_field in {"pdb_path", "sequence", "plddt"}:
        return True
    return current_field == expected_field


def _normalize_json_like_value(
    value: Any,
    *,
    path: str,
    repairs: list[PayloadRepair],
) -> Any:
    parsed = _parse_json_like_string(value)
    if parsed is not value:
        repairs.append(
            PayloadRepair(
                path=path,
                original=value,
                normalized=parsed,
                reason="parse JSON-like string payload",
            )
        )
        return _normalize_json_like_value(parsed, path=path, repairs=repairs)
    if isinstance(value, list):
        return [
            _normalize_json_like_value(
                item,
                path=f"{path}[{index}]",
                repairs=repairs,
            )
            for index, item in enumerate(value)
        ]
    if isinstance(value, dict):
        return {
            key: _normalize_json_like_value(
                item,
                path=f"{path}.{key}",
                repairs=repairs,
            )
            for key, item in value.items()
        }
    return value


def _parse_json_like_string(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    payload = _strip_markdown_json_fence(value).strip()
    if not payload or payload[0] not in "[{":
        return value

    candidates = [payload]
    if '""' in payload:
        candidates.append(payload.replace('""', '"'))

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return value


def _strip_markdown_json_fence(content: str) -> str:
    payload = content.strip()
    if not payload.startswith("```"):
        return payload

    lines = payload.splitlines()
    if not lines:
        return payload
    if lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _normalize_placeholder_field(
    token: str | None,
    *,
    input_key: str | None,
) -> str | None:
    if not isinstance(token, str):
        return _infer_reference_field(input_key)
    compact = token.strip().strip("$").strip()
    if not compact:
        return _infer_reference_field(input_key)

    lowered = compact.lower()
    if lowered.startswith("step_") or lowered.startswith("step."):
        return _infer_reference_field(input_key)
    if lowered in {"output", "value"}:
        return _infer_reference_field(input_key)
    if lowered in _PLACEHOLDER_FIELD_ALIASES:
        return _PLACEHOLDER_FIELD_ALIASES[lowered]
    if lowered in _FORBIDDEN_LITERAL_FIELDS:
        return lowered
    return _infer_reference_field(input_key)


def _infer_reference_from_field(
    field: str,
    *,
    field_source_map: dict[str, str],
) -> str | None:
    source_step = field_source_map.get(field)
    if source_step is None:
        return None
    return f"{source_step}.{field}"


def _looks_like_forbidden_reference(value: str) -> bool:
    compact = value.strip()
    if not compact:
        return False
    if compact == "auto":
        return True
    if compact.startswith("${") or compact.startswith("<") or compact.startswith("$"):
        return True
    if _STEP_REFERENCE_RE.fullmatch(compact) is not None:
        return True
    upper = compact.upper()
    if upper == compact and upper in {
        "CANDIDATES",
        "SEQUENCE",
        "PDB_PATH",
        "STRUCTURE_RESULTS",
        "QC_METRICS",
    }:
        return True
    return False
