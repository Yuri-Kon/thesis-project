#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shlex
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_GATED_SAMPLES_PATH = Path("output/training/w11-data-2/gated_samples.jsonl")
DEFAULT_QUALITY_REPORT_PATH = Path("output/training/w11-data-2/quality_gate_report.json")
DEFAULT_OUTPUT_ROOT = Path("output/dataset_v1")
DEFAULT_TOOL_KG_PATH = Path("src/kg/protein_tool_kg.json")
DEFAULT_TOOL_EXTENSION_KG_PATH = Path("src/kg/protein_tool_kg/extension_draft_v0.1.json")
DEFAULT_CONFIG_TEMPLATE_PATH = Path("configs/training/sft_dataset_v1.example.json")

ACCEPTED_STATUSES = {"PASS", "WARN"}
P0_CORE_REQUIREMENTS: dict[str, set[str]] = {
    "sequence_core": {"sequence_generation", "sequence_design"},
    "structure_prediction": {"structure_prediction"},
    "quality_qc": {"quality_qc"},
    "objective_scoring": {"objective_scoring"},
}


@dataclass
class FieldStat:
    occurrences: int = 0
    non_null: int = 0
    type_counter: Counter[str] = field(default_factory=Counter)
    row_hits: set[int] = field(default_factory=set)
    example: Any | None = None


def _str_value(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _json_dump(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows

    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            payload = json.loads(text)
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(_json_dump(row) + "\n")


def _file_sha256(path: Path) -> str | None:
    if not path.exists():
        return None

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def _normalize_adapter_mode(value: str | None) -> str:
    text = _str_value(value)
    if not text:
        return "unknown"
    normalized = text.lower()
    if normalized in {"local", "remote", "mock", "hybrid", "unknown"}:
        return normalized
    if normalized in {"nextflow", "python"}:
        return "local"
    if normalized in {"remote_model_service", "external_api"}:
        return "remote"
    return "unknown"


def _normalize_priority(value: str | None) -> str:
    text = _str_value(value)
    if not text:
        return "unknown"
    normalized = text.upper()
    if normalized in {"P0", "P1", "P2"}:
        return normalized
    return "unknown"


def _first_string(value: Any) -> str | None:
    if isinstance(value, str):
        return _str_value(value)
    if isinstance(value, list):
        for item in value:
            text = _str_value(item)
            if text:
                return text
    return None


def _load_tool_catalog(
    tool_kg_path: Path,
    *,
    extension_path: Path | None,
) -> dict[str, dict[str, Any]]:
    if not tool_kg_path.exists():
        return {}

    with tool_kg_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    tools = payload.get("tools")
    if not isinstance(tools, list):
        return {}

    catalog: dict[str, dict[str, Any]] = {}
    for item in tools:
        if not isinstance(item, dict):
            continue

        tool_id = _str_value(item.get("tool_id")) or _str_value(item.get("id"))
        if not tool_id:
            continue

        execution = item.get("execution")
        provider: str | None = None
        model_id: str | None = None
        adapter_mode = "unknown"
        if isinstance(execution, str):
            adapter_mode = _normalize_adapter_mode(execution)
        elif isinstance(execution, dict):
            provider = _str_value(execution.get("provider"))
            model_id = _str_value(execution.get("model_id"))
            adapter_mode = _normalize_adapter_mode(_str_value(execution.get("backend")))

        capabilities = item.get("capabilities")
        capability_id: str | None = None
        if isinstance(capabilities, list) and capabilities:
            capability_id = _str_value(capabilities[0])

        catalog[tool_id] = {
            "tool_id": tool_id,
            "capability_id": capability_id,
            "adapter_mode": adapter_mode,
            "provider": provider,
            "model_id": model_id,
            "tool_version": _str_value(item.get("version")),
            "priority": _normalize_priority(_str_value(item.get("priority"))),
        }

    if extension_path and extension_path.exists():
        with extension_path.open("r", encoding="utf-8") as handle:
            extension_payload = json.load(handle)
        candidates = extension_payload.get("tool_candidates")
        if isinstance(candidates, list):
            for item in candidates:
                if not isinstance(item, dict):
                    continue
                tool_id = _str_value(item.get("tool_id"))
                if not tool_id:
                    continue
                current = catalog.setdefault(
                    tool_id,
                    {
                        "tool_id": tool_id,
                        "capability_id": None,
                        "adapter_mode": "unknown",
                        "provider": None,
                        "model_id": None,
                        "tool_version": None,
                        "priority": "unknown",
                    },
                )
                if not current.get("capability_id"):
                    current["capability_id"] = _first_string(item.get("capability_id"))
                if current.get("adapter_mode") in {None, "unknown"}:
                    current["adapter_mode"] = _normalize_adapter_mode(
                        _first_string(item.get("adapter_modes"))
                    )
                extension_priority = _normalize_priority(_str_value(item.get("priority")))
                if current.get("priority") in {None, "unknown"} and extension_priority != "unknown":
                    current["priority"] = extension_priority

    return catalog


def _sample_status(sample: dict[str, Any]) -> str:
    quality_gate = sample.get("quality_gate")
    if not isinstance(quality_gate, dict):
        return "UNKNOWN"
    status = _str_value(quality_gate.get("status"))
    return status or "UNKNOWN"


def _sample_split(sample: dict[str, Any]) -> str:
    quality_gate = sample.get("quality_gate")
    if isinstance(quality_gate, dict):
        split = _str_value(quality_gate.get("split"))
        if split:
            return split
    return "unknown"


def _collect_capabilities(sample: dict[str, Any]) -> set[str]:
    capabilities: set[str] = set()

    quality_gate = sample.get("quality_gate")
    if isinstance(quality_gate, dict):
        capability_ids = quality_gate.get("capability_ids")
        if isinstance(capability_ids, list):
            for item in capability_ids:
                text = _str_value(item)
                if text:
                    capabilities.add(text)

    candidates = sample.get("candidates")
    if isinstance(candidates, list):
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            capability_id = _str_value(candidate.get("capability_id"))
            if capability_id:
                capabilities.add(capability_id)

    selected = sample.get("selected")
    if isinstance(selected, dict):
        selected_candidate = selected.get("selected_candidate")
        if isinstance(selected_candidate, dict):
            capability_id = _str_value(selected_candidate.get("capability_id"))
            if capability_id:
                capabilities.add(capability_id)

    return capabilities


def _extract_tool_records(
    sample: dict[str, Any],
    tool_catalog: dict[str, dict[str, Any]],
) -> list[dict[str, str | None]]:
    rows: list[dict[str, str | None]] = []
    seen: set[tuple[str, str, str]] = set()
    capabilities = sorted(_collect_capabilities(sample))

    def append_row(
        *,
        tool_id: str | None,
        capability_id: str | None,
        adapter_mode: str | None,
        provider: str | None,
        model_id: str | None,
        tool_version: str | None,
        priority: str | None,
    ) -> None:
        tool = _str_value(tool_id) or "unknown"
        cap = _str_value(capability_id)
        mode = _normalize_adapter_mode(adapter_mode)

        ref = tool_catalog.get(tool)
        if ref:
            cap = cap or _str_value(ref.get("capability_id"))
            if mode == "unknown":
                mode = _normalize_adapter_mode(_str_value(ref.get("adapter_mode")))
            provider_local = _str_value(provider) or _str_value(ref.get("provider"))
            model_local = _str_value(model_id) or _str_value(ref.get("model_id"))
            version_local = _str_value(tool_version) or _str_value(ref.get("tool_version"))
            priority_local = _normalize_priority(_str_value(priority) or _str_value(ref.get("priority")))
        else:
            provider_local = _str_value(provider)
            model_local = _str_value(model_id)
            version_local = _str_value(tool_version)
            priority_local = _normalize_priority(_str_value(priority))

        key = (tool, cap or "unknown", mode)
        if key in seen:
            return
        seen.add(key)
        rows.append(
            {
                "tool_id": tool,
                "capability_id": cap or "unknown",
                "adapter_mode": mode,
                "provider": provider_local,
                "model_id": model_local,
                "tool_version": version_local,
                "priority": priority_local,
            }
        )

    candidates = sample.get("candidates")
    if isinstance(candidates, list):
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            metadata = candidate.get("metadata")
            metadata_dict = metadata if isinstance(metadata, dict) else {}
            append_row(
                tool_id=_str_value(candidate.get("tool_id")) or _str_value(metadata_dict.get("tool_id")),
                capability_id=_str_value(candidate.get("capability_id")) or _str_value(metadata_dict.get("capability_id")),
                adapter_mode=_str_value(candidate.get("adapter_mode")) or _str_value(metadata_dict.get("adapter_mode")),
                provider=_str_value(candidate.get("provider")) or _str_value(metadata_dict.get("provider")),
                model_id=_str_value(candidate.get("model_id")) or _str_value(metadata_dict.get("model_id")),
                tool_version=_str_value(candidate.get("tool_version")) or _str_value(metadata_dict.get("tool_version")),
                priority=_str_value(candidate.get("priority")) or _str_value(metadata_dict.get("priority")),
            )

    selected = sample.get("selected")
    if isinstance(selected, dict):
        selected_candidate = selected.get("selected_candidate")
        if isinstance(selected_candidate, dict):
            metadata = selected_candidate.get("metadata")
            metadata_dict = metadata if isinstance(metadata, dict) else {}
            append_row(
                tool_id=_str_value(selected_candidate.get("tool_id")) or _str_value(metadata_dict.get("tool_id")),
                capability_id=_str_value(selected_candidate.get("capability_id")) or _str_value(metadata_dict.get("capability_id")),
                adapter_mode=_str_value(selected_candidate.get("adapter_mode")) or _str_value(metadata_dict.get("adapter_mode")),
                provider=_str_value(selected_candidate.get("provider")) or _str_value(metadata_dict.get("provider")),
                model_id=_str_value(selected_candidate.get("model_id")) or _str_value(metadata_dict.get("model_id")),
                tool_version=_str_value(selected_candidate.get("tool_version")) or _str_value(metadata_dict.get("tool_version")),
                priority=_str_value(selected_candidate.get("priority")) or _str_value(metadata_dict.get("priority")),
            )

    quality_gate = sample.get("quality_gate")
    if isinstance(quality_gate, dict):
        tool_lineage = quality_gate.get("tool_lineage")
        if isinstance(tool_lineage, list):
            for tool_id in tool_lineage:
                tool_text = _str_value(tool_id)
                if not tool_text:
                    continue
                if len(capabilities) == 1:
                    capability_id = capabilities[0]
                else:
                    ref = tool_catalog.get(tool_text)
                    capability_id = _str_value(ref.get("capability_id")) if ref else None
                append_row(
                    tool_id=tool_text,
                    capability_id=capability_id,
                    adapter_mode=None,
                    provider=None,
                    model_id=None,
                    tool_version=None,
                    priority=None,
                )

    return rows


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    return type(value).__name__


def _walk_field_stats(
    value: Any,
    *,
    path: str,
    row_index: int,
    stats: dict[str, FieldStat],
) -> None:
    stat = stats[path]
    stat.occurrences += 1
    stat.row_hits.add(row_index)
    value_type = _type_name(value)
    stat.type_counter[value_type] += 1
    if value is not None:
        stat.non_null += 1
    if stat.example is None and value_type in {"str", "int", "float", "bool"}:
        stat.example = value

    if isinstance(value, dict):
        for key in sorted(value.keys()):
            child_path = f"{path}.{key}"
            _walk_field_stats(value[key], path=child_path, row_index=row_index, stats=stats)
        return

    if isinstance(value, list):
        list_path = f"{path}[]"
        for item in value:
            _walk_field_stats(item, path=list_path, row_index=row_index, stats=stats)


def _build_field_dictionary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    stats: dict[str, FieldStat] = defaultdict(FieldStat)
    total_rows = len(rows)
    if total_rows == 0:
        return []

    for row_index, row in enumerate(rows):
        _walk_field_stats(row, path="sample", row_index=row_index, stats=stats)

    dictionary: list[dict[str, Any]] = []
    for path in sorted(stats.keys()):
        stat = stats[path]
        entry: dict[str, Any] = {
            "path": path,
            "types": dict(sorted(stat.type_counter.items())),
            "row_coverage_rate": round(len(stat.row_hits) / total_rows, 6),
            "non_null_rate": round(stat.non_null / stat.occurrences, 6) if stat.occurrences else 0.0,
            "occurrences": stat.occurrences,
        }
        if stat.example is not None:
            entry["example"] = stat.example
        dictionary.append(entry)
    return dictionary


def _collect_capability_distribution(rows: list[dict[str, Any]]) -> Counter[str]:
    counter: Counter[str] = Counter()
    for row in rows:
        for capability in sorted(_collect_capabilities(row)):
            counter[capability] += 1
    return counter


def _build_tool_coverage_matrix(
    rows: list[dict[str, Any]],
    tool_catalog: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], set[str]]:
    matrix: dict[str, dict[str, dict[str, dict[str, int]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(lambda: {"sample_count": 0, "occurrence_count": 0}))
    )
    capability_presence: set[str] = set()

    for row in rows:
        tool_records = _extract_tool_records(row, tool_catalog)
        seen_in_sample: set[tuple[str, str, str]] = set()
        for record in tool_records:
            capability = _str_value(record.get("capability_id")) or "unknown"
            tool_id = _str_value(record.get("tool_id")) or "unknown"
            adapter_mode = _normalize_adapter_mode(_str_value(record.get("adapter_mode")))
            capability_presence.add(capability)

            bucket = matrix[capability][tool_id][adapter_mode]
            bucket["occurrence_count"] += 1
            sample_key = (capability, tool_id, adapter_mode)
            if sample_key not in seen_in_sample:
                bucket["sample_count"] += 1
                seen_in_sample.add(sample_key)

    serialized: dict[str, Any] = {}
    for capability in sorted(matrix.keys()):
        serialized[capability] = {}
        for tool_id in sorted(matrix[capability].keys()):
            serialized[capability][tool_id] = {}
            for adapter_mode in sorted(matrix[capability][tool_id].keys()):
                serialized[capability][tool_id][adapter_mode] = dict(
                    sorted(matrix[capability][tool_id][adapter_mode].items())
                )

    return serialized, capability_presence


def _build_p0_tool_registry(tool_catalog: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for tool_id in sorted(tool_catalog.keys()):
        tool = tool_catalog[tool_id]
        if _normalize_priority(_str_value(tool.get("priority"))) != "P0":
            continue
        rows.append(
            {
                "tool_id": tool_id,
                "capability_id": _str_value(tool.get("capability_id")) or "unknown",
                "adapter_mode": _normalize_adapter_mode(_str_value(tool.get("adapter_mode"))),
                "provider": _str_value(tool.get("provider")),
                "model_id": _str_value(tool.get("model_id")),
                "tool_version": _str_value(tool.get("tool_version")),
            }
        )
    return rows


def _evaluate_p0_core_coverage(capability_presence: set[str]) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    missing_groups: list[str] = []
    for group, required_set in sorted(P0_CORE_REQUIREMENTS.items()):
        present = sorted(capability_presence.intersection(required_set))
        satisfied = bool(present)
        checks[group] = {
            "required_capabilities": sorted(required_set),
            "present_capabilities": present,
            "satisfied": satisfied,
        }
        if not satisfied:
            missing_groups.append(group)
    return {
        "checks": checks,
        "missing_groups": missing_groups,
        "satisfied": len(missing_groups) == 0,
    }


def _infer_tool_biases(
    *,
    tool_coverage_matrix: dict[str, Any],
    p0_core_coverage: dict[str, Any],
    accepted_total: int,
) -> list[str]:
    biases: list[str] = []
    capabilities = sorted(tool_coverage_matrix.keys())
    tools = sorted(
        {
            tool_id
            for capability in tool_coverage_matrix.values()
            if isinstance(capability, dict)
            for tool_id in capability.keys()
        }
    )

    if len(capabilities) <= 1:
        biases.append("Capability distribution is narrow; transfer to other capability families may be limited.")
    if len(tools) <= 1:
        biases.append("Tool coverage is concentrated on one tool lineage; cross-tool generalization risk is high.")
    if accepted_total < 100:
        biases.append("Sample size is small; observed rates may be unstable for Week12 tuning.")
    if not p0_core_coverage.get("satisfied"):
        missing = ", ".join(p0_core_coverage.get("missing_groups", []))
        biases.append(f"P0 core capability coverage is incomplete: {missing}.")
    return biases


def _collect_tool_distributions(
    rows: list[dict[str, Any]],
    tool_catalog: dict[str, dict[str, Any]],
) -> tuple[Counter[str], Counter[str], Counter[str], Counter[str]]:
    tool_counter: Counter[str] = Counter()
    adapter_counter: Counter[str] = Counter()
    provider_counter: Counter[str] = Counter()
    model_counter: Counter[str] = Counter()

    for row in rows:
        for record in _extract_tool_records(row, tool_catalog):
            tool_counter[_str_value(record.get("tool_id")) or "unknown"] += 1
            adapter_counter[_normalize_adapter_mode(_str_value(record.get("adapter_mode")))] += 1
            provider_counter[_str_value(record.get("provider")) or "unknown"] += 1
            model_counter[_str_value(record.get("model_id")) or "unknown"] += 1

    return tool_counter, adapter_counter, provider_counter, model_counter


def _build_dataset_version(value: str | None, *, git_short_sha: str) -> str:
    if value:
        return value
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"w11-sft-dataset-v1-{day}-{git_short_sha}"


def _get_git_ref() -> tuple[str, str]:
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        commit = "unknown"
    try:
        branch = subprocess.check_output(
            ["git", "branch", "--show-current"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        branch = "unknown"
    return branch or "unknown", commit or "unknown"


def _get_uv_version() -> str | None:
    try:
        text = subprocess.check_output(
            ["uv", "--version"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return None
    return text or None


def _fingerprint_rows(rows: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(_json_dump(row).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _flatten_tool_coverage_matrix(matrix: dict[str, Any]) -> dict[str, int]:
    flattened: dict[str, int] = {}
    for capability_id, tools in matrix.items():
        if not isinstance(tools, dict):
            continue
        for tool_id, adapters in tools.items():
            if not isinstance(adapters, dict):
                continue
            for adapter_mode, payload in adapters.items():
                if not isinstance(payload, dict):
                    continue
                sample_count = payload.get("sample_count")
                if not isinstance(sample_count, int):
                    continue
                key = f"{capability_id}|{tool_id}|{adapter_mode}"
                flattened[key] = sample_count
    return flattened


def _build_delta_from_previous(
    *,
    previous_manifest_path: Path,
    current_manifest: dict[str, Any],
    current_capability_distribution: dict[str, int],
    current_tool_coverage_matrix: dict[str, Any],
) -> dict[str, Any]:
    previous_manifest = _read_json_file(previous_manifest_path)
    if not previous_manifest:
        return {}

    previous_counts = previous_manifest.get("dataset_counts")
    previous_counts_dict = previous_counts if isinstance(previous_counts, dict) else {}
    current_counts = current_manifest.get("dataset_counts")
    current_counts_dict = current_counts if isinstance(current_counts, dict) else {}

    previous_split = previous_manifest.get("split_counts")
    previous_split_dict = previous_split if isinstance(previous_split, dict) else {}
    current_split = current_manifest.get("split_counts")
    current_split_dict = current_split if isinstance(current_split, dict) else {}

    previous_stats_path = None
    previous_artifacts = previous_manifest.get("artifacts")
    if isinstance(previous_artifacts, dict):
        previous_stats_path = _str_value(previous_artifacts.get("dataset_stats_path"))
    previous_capability_distribution: dict[str, int] = {}
    if previous_stats_path:
        previous_stats_payload = _read_json_file(Path(previous_stats_path))
        capability_distribution = previous_stats_payload.get("capability_distribution")
        if isinstance(capability_distribution, dict):
            previous_capability_distribution = {
                str(key): int(value)
                for key, value in capability_distribution.items()
                if isinstance(value, int)
            }

    previous_tool_matrix_path = None
    if isinstance(previous_artifacts, dict):
        previous_tool_matrix_path = _str_value(previous_artifacts.get("tool_coverage_matrix_path"))
    previous_tool_matrix: dict[str, Any] = {}
    if previous_tool_matrix_path:
        previous_tool_matrix = _read_json_file(Path(previous_tool_matrix_path))

    current_flat_matrix = _flatten_tool_coverage_matrix(current_tool_coverage_matrix)
    previous_flat_matrix = _flatten_tool_coverage_matrix(previous_tool_matrix)

    all_count_keys = sorted(set(previous_counts_dict.keys()).union(current_counts_dict.keys()))
    counts_delta = {
        key: int(current_counts_dict.get(key, 0)) - int(previous_counts_dict.get(key, 0))
        for key in all_count_keys
        if isinstance(current_counts_dict.get(key, 0), int)
        and isinstance(previous_counts_dict.get(key, 0), int)
    }

    all_split_keys = sorted(set(previous_split_dict.keys()).union(current_split_dict.keys()))
    split_delta = {
        key: int(current_split_dict.get(key, 0)) - int(previous_split_dict.get(key, 0))
        for key in all_split_keys
        if isinstance(current_split_dict.get(key, 0), int)
        and isinstance(previous_split_dict.get(key, 0), int)
    }

    all_capability_keys = sorted(
        set(previous_capability_distribution.keys()).union(current_capability_distribution.keys())
    )
    capability_delta = {
        key: int(current_capability_distribution.get(key, 0))
        - int(previous_capability_distribution.get(key, 0))
        for key in all_capability_keys
    }

    added_matrix_keys = sorted(key for key in current_flat_matrix.keys() if key not in previous_flat_matrix)
    removed_matrix_keys = sorted(key for key in previous_flat_matrix.keys() if key not in current_flat_matrix)
    changed_matrix_keys = sorted(
        key
        for key in current_flat_matrix.keys()
        if key in previous_flat_matrix and current_flat_matrix[key] != previous_flat_matrix[key]
    )

    previous_req2 = previous_manifest.get("requirement2")
    previous_req2_dict = previous_req2 if isinstance(previous_req2, dict) else {}
    previous_p0 = previous_req2_dict.get("p0_core_minimum_coverage")
    previous_p0_dict = previous_p0 if isinstance(previous_p0, dict) else {}
    current_req2 = current_manifest.get("requirement2")
    current_req2_dict = current_req2 if isinstance(current_req2, dict) else {}
    current_p0 = current_req2_dict.get("p0_core_minimum_coverage")
    current_p0_dict = current_p0 if isinstance(current_p0, dict) else {}

    return {
        "previous_manifest_path": str(previous_manifest_path),
        "previous_dataset_version": previous_manifest.get("dataset_version"),
        "dataset_counts_delta": counts_delta,
        "split_counts_delta": split_delta,
        "capability_distribution_delta": capability_delta,
        "tool_coverage_matrix_delta": {
            "added_keys": added_matrix_keys,
            "removed_keys": removed_matrix_keys,
            "changed_keys": changed_matrix_keys,
        },
        "p0_core_coverage_change": {
            "previous_satisfied": bool(previous_p0_dict.get("satisfied")),
            "current_satisfied": bool(current_p0_dict.get("satisfied")),
            "previous_missing_groups": previous_p0_dict.get("missing_groups", []),
            "current_missing_groups": current_p0_dict.get("missing_groups", []),
        },
    }


def _write_training_reader_config(
    *,
    path: Path,
    dataset_version: str,
    freeze_dir: Path,
    p0_core_coverage: dict[str, Any],
) -> dict[str, Any]:
    config = {
        "dataset_version": dataset_version,
        "manifest_path": str(freeze_dir / "manifest.json"),
        "splits": {
            "train_path": str(freeze_dir / "train.jsonl"),
            "val_path": str(freeze_dir / "val.jsonl"),
            "test_path": str(freeze_dir / "test.jsonl"),
        },
        "selection_policy": {
            "accepted_statuses": sorted(ACCEPTED_STATUSES),
            "drop_statuses": ["BLOCK"],
        },
        "requirement2": {
            "tool_coverage_matrix_path": str(freeze_dir / "tool_coverage_matrix.json"),
            "p0_core_coverage_satisfied": bool(p0_core_coverage.get("satisfied")),
            "missing_p0_core_groups": p0_core_coverage.get("missing_groups", []),
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write(_json_dump(config) + "\n")
    return config


def freeze_sft_dataset_v1(
    *,
    gated_samples_path: Path,
    quality_report_path: Path | None,
    output_root: Path,
    dataset_version: str | None,
    previous_manifest_path: Path | None,
    tool_kg_path: Path,
    tool_extension_kg_path: Path | None,
    config_template_path: Path,
) -> dict[str, Any]:
    rows = _read_jsonl(gated_samples_path)
    if not rows:
        raise ValueError(f"no rows found in gated samples: {gated_samples_path}")

    tool_catalog = _load_tool_catalog(tool_kg_path, extension_path=tool_extension_kg_path)
    status_counter = Counter(_sample_status(row) for row in rows)

    accepted_rows = [
        row
        for row in rows
        if _sample_status(row) in ACCEPTED_STATUSES
    ]
    accepted_rows.sort(key=lambda item: _str_value(item.get("sample_id")) or "")

    split_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in accepted_rows:
        split_rows[_sample_split(row)].append(row)
    for split in split_rows.values():
        split.sort(key=lambda item: _str_value(item.get("sample_id")) or "")

    branch, commit = _get_git_ref()
    short_sha = commit[:7] if commit != "unknown" else "unknown"
    resolved_version = _build_dataset_version(dataset_version, git_short_sha=short_sha)
    freeze_dir = output_root / resolved_version

    capability_distribution = _collect_capability_distribution(accepted_rows)
    tool_coverage_matrix, capability_presence = _build_tool_coverage_matrix(accepted_rows, tool_catalog)
    p0_registry = _build_p0_tool_registry(tool_catalog)
    p0_core_coverage = _evaluate_p0_core_coverage(capability_presence)

    tool_counter, adapter_counter, provider_counter, model_counter = _collect_tool_distributions(
        accepted_rows,
        tool_catalog,
    )

    field_dictionary = _build_field_dictionary(accepted_rows)
    quality_report_summary: dict[str, Any] = {}
    if quality_report_path and quality_report_path.exists():
        with quality_report_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
            if isinstance(payload, dict):
                summary = payload.get("summary")
                if isinstance(summary, dict):
                    quality_report_summary = summary

    split_counts = {
        split: len(split_rows.get(split, []))
        for split in sorted(split_rows.keys())
    }
    dataset_fingerprint = _fingerprint_rows(accepted_rows)

    if freeze_dir.exists():
        manifest_path = freeze_dir / "manifest.json"
        if not manifest_path.exists():
            raise FileExistsError(
                f"freeze directory exists without manifest: {freeze_dir}"
            )
        existing_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        existing_fingerprint = _str_value(existing_manifest.get("dataset_fingerprint"))
        if existing_fingerprint != dataset_fingerprint:
            raise FileExistsError(
                "freeze version already exists with different fingerprint; "
                "bump dataset version to keep immutability."
            )
        return existing_manifest

    freeze_dir.mkdir(parents=True, exist_ok=False)
    _write_jsonl(freeze_dir / "accepted_samples.jsonl", accepted_rows)
    for split in sorted(split_rows.keys()):
        _write_jsonl(freeze_dir / f"{split}.jsonl", split_rows[split])

    with (freeze_dir / "field_dictionary.json").open("w", encoding="utf-8") as handle:
        handle.write(_json_dump({"total_fields": len(field_dictionary), "fields": field_dictionary}) + "\n")
    with (freeze_dir / "tool_coverage_matrix.json").open("w", encoding="utf-8") as handle:
        handle.write(_json_dump(tool_coverage_matrix) + "\n")

    stats = {
        "input_total": len(rows),
        "accepted_total": len(accepted_rows),
        "blocked_total": status_counter.get("BLOCK", 0),
        "status_distribution": dict(sorted(status_counter.items())),
        "split_counts": split_counts,
        "capability_distribution": dict(sorted(capability_distribution.items())),
        "tool_distribution": {
            "by_tool_id": dict(sorted(tool_counter.items())),
            "by_adapter_mode": dict(sorted(adapter_counter.items())),
            "by_provider": dict(sorted(provider_counter.items())),
            "by_model_id": dict(sorted(model_counter.items())),
        },
    }
    with (freeze_dir / "dataset_stats.json").open("w", encoding="utf-8") as handle:
        handle.write(_json_dump(stats) + "\n")

    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    command = " ".join(shlex.quote(arg) for arg in sys.argv)
    bias_notes = _infer_tool_biases(
        tool_coverage_matrix=tool_coverage_matrix,
        p0_core_coverage=p0_core_coverage,
        accepted_total=len(accepted_rows),
    )

    manifest = {
        "dataset_version": resolved_version,
        "freeze_semantics": {
            "immutable": True,
            "idempotent_if_fingerprint_equal": True,
        },
        "generated_at": generated_at,
        "git_ref": {
            "branch": branch,
            "commit": commit,
        },
        "input": {
            "gated_samples_path": str(gated_samples_path),
            "quality_report_path": str(quality_report_path) if quality_report_path else None,
            "tool_kg_path": str(tool_kg_path),
            "tool_extension_kg_path": str(tool_extension_kg_path) if tool_extension_kg_path else None,
            "sha256": {
                "gated_samples": _file_sha256(gated_samples_path),
                "quality_report": _file_sha256(quality_report_path) if quality_report_path else None,
                "tool_kg": _file_sha256(tool_kg_path),
                "tool_extension_kg": _file_sha256(tool_extension_kg_path) if tool_extension_kg_path else None,
            },
        },
        "artifacts": {
            "freeze_dir": str(freeze_dir),
            "accepted_samples_path": str(freeze_dir / "accepted_samples.jsonl"),
            "split_paths": {
                split: str(freeze_dir / f"{split}.jsonl")
                for split in sorted(split_rows.keys())
            },
            "manifest_path": str(freeze_dir / "manifest.json"),
            "dataset_stats_path": str(freeze_dir / "dataset_stats.json"),
            "field_dictionary_path": str(freeze_dir / "field_dictionary.json"),
            "tool_coverage_matrix_path": str(freeze_dir / "tool_coverage_matrix.json"),
            "training_reader_config_path": str(freeze_dir / "training_reader_config.json"),
            "training_reader_template_path": str(config_template_path),
        },
        "dataset_counts": {
            "input_total": len(rows),
            "accepted_total": len(accepted_rows),
            "blocked_total": status_counter.get("BLOCK", 0),
        },
        "split_counts": split_counts,
        "quality_gate_summary": quality_report_summary,
        "reproducibility": {
            "command": command,
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "uv_version": _get_uv_version(),
        },
        "requirement2": {
            "tool_coverage_matrix": {
                "dimensions": ["capability_id", "tool_id", "adapter_mode"],
                "path": str(freeze_dir / "tool_coverage_matrix.json"),
            },
            "p0_tool_registry": p0_registry,
            "p0_core_minimum_coverage": p0_core_coverage,
            "tool_bias_and_limits": bias_notes,
        },
        "dataset_fingerprint": dataset_fingerprint,
    }

    if previous_manifest_path:
        delta = _build_delta_from_previous(
            previous_manifest_path=previous_manifest_path,
            current_manifest=manifest,
            current_capability_distribution=dict(sorted(capability_distribution.items())),
            current_tool_coverage_matrix=tool_coverage_matrix,
        )
        if delta:
            manifest["delta_from_previous"] = delta

    _write_training_reader_config(
        path=freeze_dir / "training_reader_config.json",
        dataset_version=resolved_version,
        freeze_dir=freeze_dir,
        p0_core_coverage=p0_core_coverage,
    )

    with (freeze_dir / "manifest.json").open("w", encoding="utf-8") as handle:
        handle.write(_json_dump(manifest) + "\n")

    config_template_payload = {
        "dataset_version": "<dataset_version>",
        "manifest_path": "output/dataset_v1/<dataset_version>/manifest.json",
        "splits": {
            "train_path": "output/dataset_v1/<dataset_version>/train.jsonl",
            "val_path": "output/dataset_v1/<dataset_version>/val.jsonl",
            "test_path": "output/dataset_v1/<dataset_version>/test.jsonl",
        },
        "selection_policy": {
            "accepted_statuses": sorted(ACCEPTED_STATUSES),
            "drop_statuses": ["BLOCK"],
        },
        "requirement2": {
            "tool_coverage_matrix_path": "output/dataset_v1/<dataset_version>/tool_coverage_matrix.json",
            "enforce_p0_core_coverage": True,
        },
    }
    config_template_path.parent.mkdir(parents=True, exist_ok=True)
    with config_template_path.open("w", encoding="utf-8") as handle:
        handle.write(_json_dump(config_template_payload) + "\n")

    return manifest


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Freeze SFT dataset v1 from quality-gated training samples.",
    )
    parser.add_argument("--gated-samples-path", type=Path, default=DEFAULT_GATED_SAMPLES_PATH)
    parser.add_argument("--quality-report-path", type=Path, default=DEFAULT_QUALITY_REPORT_PATH)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--dataset-version", type=str, default=None)
    parser.add_argument(
        "--previous-manifest-path",
        type=Path,
        default=None,
        help="Optional previous manifest to compute version delta (for r02/v1.1 evolution).",
    )
    parser.add_argument("--tool-kg-path", type=Path, default=DEFAULT_TOOL_KG_PATH)
    parser.add_argument(
        "--tool-extension-kg-path",
        type=Path,
        default=DEFAULT_TOOL_EXTENSION_KG_PATH,
    )
    parser.add_argument(
        "--config-template-path",
        type=Path,
        default=DEFAULT_CONFIG_TEMPLATE_PATH,
    )
    parser.add_argument(
        "--fail-on-missing-p0-core",
        action="store_true",
        help="Exit with code 3 when Requirement2 P0 core capability coverage is not satisfied.",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    manifest = freeze_sft_dataset_v1(
        gated_samples_path=args.gated_samples_path,
        quality_report_path=args.quality_report_path,
        output_root=args.output_root,
        dataset_version=args.dataset_version,
        previous_manifest_path=args.previous_manifest_path,
        tool_kg_path=args.tool_kg_path,
        tool_extension_kg_path=args.tool_extension_kg_path,
        config_template_path=args.config_template_path,
    )

    print("Dataset freeze completed")
    print(_json_dump(
        {
            "dataset_version": manifest["dataset_version"],
            "accepted_total": manifest["dataset_counts"]["accepted_total"],
            "p0_core_coverage_satisfied": manifest["requirement2"]["p0_core_minimum_coverage"]["satisfied"],
        }
    ))
    if (
        args.fail_on_missing_p0_core
        and not manifest["requirement2"]["p0_core_minimum_coverage"]["satisfied"]
    ):
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
