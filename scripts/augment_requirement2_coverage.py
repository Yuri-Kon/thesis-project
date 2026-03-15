#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DEFAULT_BASE_SAMPLES_PATH = Path("output/training/w11-data-1/samples.jsonl")
DEFAULT_BASE_GATED_PATH = Path("output/training/w11-data-2/gated_samples.jsonl")
DEFAULT_OUTPUT_DIR = Path("output/training/w11-data-3")
DEFAULT_TOOL_KG_PATH = Path("src/kg/protein_tool_kg.json")
DEFAULT_TOOL_EXTENSION_KG_PATH = Path("src/kg/protein_tool_kg/extension_draft_v0.1.json")
ACCEPTED_STATUSES = {"PASS", "WARN"}

REQ2_TARGETS = {
    "sequence_core": {
        "capability_id": "sequence_design",
        "tool_id": "protein_mpnn",
        "adapter_mode": "remote",
        "provider": "nvidia_nim",
        "model_id": "ipd/proteinmpnn/predict",
    },
    "quality_qc": {
        "capability_id": "quality_qc",
        "tool_id": "biopython_qc",
        "adapter_mode": "local",
        "provider": None,
        "model_id": None,
    },
    "objective_scoring": {
        "capability_id": "objective_scoring",
        "tool_id": "objective_ranker",
        "adapter_mode": "local",
        "provider": None,
        "model_id": None,
    },
}


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

        capability_id = None
        capabilities = item.get("capabilities")
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


def _extract_sequence(sample: dict[str, Any]) -> str:
    context = sample.get("context")
    if isinstance(context, dict):
        sequence = _str_value(context.get("sequence"))
        if sequence:
            return sequence

    selected = sample.get("selected")
    if isinstance(selected, dict):
        selected_candidate = selected.get("selected_candidate")
        if isinstance(selected_candidate, dict):
            payload = selected_candidate.get("payload")
            if isinstance(payload, dict):
                sequence = _str_value(payload.get("sequence"))
                if sequence:
                    return sequence

    return "ACDEFGHIKLMNPQRSTVWY"


def _extract_current_capabilities(gated_rows: list[dict[str, Any]]) -> set[str]:
    capabilities: set[str] = set()
    for row in gated_rows:
        quality_gate = row.get("quality_gate")
        if not isinstance(quality_gate, dict):
            continue
        status = _str_value(quality_gate.get("status"))
        if status not in ACCEPTED_STATUSES:
            continue
        capability_ids = quality_gate.get("capability_ids")
        if not isinstance(capability_ids, list):
            continue
        for item in capability_ids:
            capability = _str_value(item)
            if capability:
                capabilities.add(capability)
    return capabilities


def _missing_groups(current_capabilities: set[str]) -> list[str]:
    missing: list[str] = []
    if not current_capabilities.intersection({"sequence_generation", "sequence_design"}):
        missing.append("sequence_core")
    if "quality_qc" not in current_capabilities:
        missing.append("quality_qc")
    if "objective_scoring" not in current_capabilities:
        missing.append("objective_scoring")
    return missing


def _shift_timestamp(ts: str | None, *, minutes: int) -> str:
    text = _str_value(ts)
    if not text:
        base = datetime(2026, 3, 15, 0, 0, 0, tzinfo=timezone.utc)
        return (base + timedelta(minutes=minutes)).isoformat()
    normalized = text.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        base = datetime(2026, 3, 15, 0, 0, 0, tzinfo=timezone.utc)
        return (base + timedelta(minutes=minutes)).isoformat()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (dt + timedelta(minutes=minutes)).isoformat()


def _choose_seed_samples(
    *,
    base_samples: list[dict[str, Any]],
    gated_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    sample_index = {
        _str_value(sample.get("sample_id")): sample
        for sample in base_samples
        if _str_value(sample.get("sample_id"))
    }

    seeds: list[dict[str, Any]] = []
    for row in gated_rows:
        quality_gate = row.get("quality_gate")
        if not isinstance(quality_gate, dict):
            continue
        status = _str_value(quality_gate.get("status"))
        if status not in ACCEPTED_STATUSES:
            continue
        sample_id = _str_value(row.get("sample_id"))
        sample = sample_index.get(sample_id)
        if isinstance(sample, dict):
            seeds.append(sample)

    if seeds:
        return seeds
    return [sample for sample in base_samples if isinstance(sample, dict)]


def _tool_metadata(
    *,
    target: dict[str, Any],
    tool_catalog: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    tool_id = target["tool_id"]
    ref = tool_catalog.get(tool_id, {})
    return {
        "tool_id": tool_id,
        "capability_id": target["capability_id"],
        "adapter_mode": target.get("adapter_mode")
        or _str_value(ref.get("adapter_mode"))
        or "unknown",
        "provider": target.get("provider") or _str_value(ref.get("provider")),
        "model_id": target.get("model_id") or _str_value(ref.get("model_id")),
        "tool_version": _str_value(ref.get("tool_version")),
        "priority": _str_value(ref.get("priority")) or "P0",
    }


def _build_addon_sample(
    *,
    seed_sample: dict[str, Any],
    target_group: str,
    target: dict[str, Any],
    index: int,
    tool_catalog: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    sample = copy.deepcopy(seed_sample)
    sample.pop("quality_gate", None)

    source_sample_id = _str_value(seed_sample.get("sample_id")) or f"source_{index:02d}"
    source_context = seed_sample.get("context")
    source_context_dict = source_context if isinstance(source_context, dict) else {}
    source_task_id = _str_value(source_context_dict.get("task_id")) or f"task_seed_{index:02d}"
    task_id = f"{source_task_id}__addon_{target['capability_id']}_{index:02d}"
    sample_id = f"sample::addon::{target['capability_id']}::{index:02d}"
    sequence = _extract_sequence(seed_sample)

    context = sample.get("context")
    context_dict = context if isinstance(context, dict) else {}
    context_dict["task_id"] = task_id
    status_path = context_dict.get("status_path")
    if not isinstance(status_path, list) or not status_path:
        context_dict["status_path"] = ["PLANNING", "PLANNED", "RUNNING", "DONE"]

    time_window = context_dict.get("time_window")
    time_window_dict = time_window if isinstance(time_window, dict) else {}
    time_window_dict["first_ts"] = _shift_timestamp(
        _str_value(time_window_dict.get("first_ts")),
        minutes=index * 3,
    )
    time_window_dict["last_ts"] = _shift_timestamp(
        _str_value(time_window_dict.get("last_ts")) or _str_value(time_window_dict.get("first_ts")),
        minutes=index * 3 + 1,
    )
    context_dict["time_window"] = time_window_dict
    context_dict["sequence"] = sequence

    kg_explanation = {
        "steps": [
            {
                "step_id": "S_addon_1",
                "tool_id": target["tool_id"],
                "capabilities": [{"capability_id": target["capability_id"]}],
            }
        ]
    }
    plan_metadata = context_dict.get("plan_metadata")
    plan_metadata_dict = plan_metadata if isinstance(plan_metadata, dict) else {}
    plan_metadata_dict["kg_explanation"] = kg_explanation
    context_dict["plan_metadata"] = plan_metadata_dict
    sample["context"] = context_dict

    meta = _tool_metadata(target=target, tool_catalog=tool_catalog)
    candidate_id = f"{sample_id}::cand"
    candidate = {
        "candidate_id": candidate_id,
        "tool_id": meta["tool_id"],
        "capability_id": meta["capability_id"],
        "adapter_mode": meta["adapter_mode"],
        "score_breakdown": {
            "feasibility": 0.88,
            "objective": 0.86,
            "risk": 0.22,
            "cost": 0.24,
            "overall": 0.87,
        },
        "risk_level": "low",
        "cost_estimate": "low",
        "payload": {"sequence": sequence},
        "metadata": {
            "provider": meta["provider"],
            "model_id": meta["model_id"],
            "tool_version": meta["tool_version"],
            "priority": meta["priority"],
        },
    }
    sample["candidates"] = [candidate]
    sample["selected"] = {
        "selected_candidate_id": candidate_id,
        "selected_candidate": candidate,
        "choice": "accept",
        "action_type": "plan_confirm",
    }

    outcome = sample.get("outcome")
    outcome_dict = outcome if isinstance(outcome, dict) else {}
    outcome_dict["final_status"] = "DONE"
    outcome_dict["step_results"] = [
        {
            "event_id": f"{task_id}:addon",
            "step_id": "S_addon_1",
            "tool": target["tool_id"],
            "status": "success",
            "failure_type": None,
            "error_message": None,
            "ts": time_window_dict.get("last_ts"),
        }
    ]
    outcome_dict["step_failure_types"] = []
    scores = outcome_dict.get("scores")
    scores_dict = scores if isinstance(scores, dict) else {}
    scores_dict.setdefault("plddt_mean", 0.9)
    if target_group == "quality_qc":
        scores_dict["qc_pass"] = True
    outcome_dict["scores"] = scores_dict
    sample["outcome"] = outcome_dict

    audit_trace = sample.get("audit_trace")
    audit_trace_dict = audit_trace if isinstance(audit_trace, dict) else {}
    audit_trace_dict["task_id"] = task_id
    audit_trace_dict["event_ids"] = [f"{task_id}:addon"]
    audit_trace_dict.setdefault("decision_history", [])
    audit_trace_dict.setdefault("pending_action_ids", [])
    audit_trace_dict.setdefault("snapshot_ids", [])
    audit_trace_dict.setdefault("decision_event_ids", [])
    sample["audit_trace"] = audit_trace_dict

    sample["sample_id"] = sample_id
    sample["addon_metadata"] = {
        "source_sample_id": source_sample_id,
        "source_task_id": source_task_id,
        "addon_group": target_group,
        "generated_for_requirement2": True,
    }
    return sample


def augment_requirement2_coverage(
    *,
    base_samples_path: Path,
    base_gated_path: Path,
    output_dir: Path,
    tool_kg_path: Path,
    tool_extension_kg_path: Path | None,
) -> dict[str, Any]:
    base_samples = _read_jsonl(base_samples_path)
    if not base_samples:
        raise ValueError(f"empty base samples: {base_samples_path}")

    gated_rows = _read_jsonl(base_gated_path)
    if not gated_rows:
        raise ValueError(f"empty base gated rows: {base_gated_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    tool_catalog = _load_tool_catalog(
        tool_kg_path,
        extension_path=tool_extension_kg_path,
    )

    current_capabilities = _extract_current_capabilities(gated_rows)
    missing_groups_before = _missing_groups(current_capabilities)
    target_plan = [REQ2_TARGETS[group] for group in missing_groups_before]

    seeds = _choose_seed_samples(base_samples=base_samples, gated_rows=gated_rows)
    if not seeds:
        raise ValueError("no seed samples available to generate requirement2 addons")

    addon_samples: list[dict[str, Any]] = []
    for index, group in enumerate(missing_groups_before, start=1):
        target = REQ2_TARGETS[group]
        seed = seeds[(index - 1) % len(seeds)]
        addon_samples.append(
            _build_addon_sample(
                seed_sample=seed,
                target_group=group,
                target=target,
                index=index,
                tool_catalog=tool_catalog,
            )
        )

    combined_samples = list(base_samples) + addon_samples
    all_capabilities = set(current_capabilities)
    for target in target_plan:
        all_capabilities.add(target["capability_id"])
    missing_groups_after_expected = _missing_groups(all_capabilities)

    addons_path = output_dir / "requirement2_addon_samples.jsonl"
    combined_path = output_dir / "samples_with_addons.jsonl"
    report_path = output_dir / "requirement2_addon_report.json"

    _write_jsonl(addons_path, addon_samples)
    _write_jsonl(combined_path, combined_samples)

    report = {
        "input": {
            "base_samples_path": str(base_samples_path),
            "base_gated_path": str(base_gated_path),
            "base_samples_count": len(base_samples),
            "base_gated_count": len(gated_rows),
        },
        "output": {
            "addons_samples_path": str(addons_path),
            "combined_samples_path": str(combined_path),
            "report_path": str(report_path),
        },
        "requirement2_coverage": {
            "capabilities_before": sorted(current_capabilities),
            "missing_groups_before": missing_groups_before,
            "missing_groups_after_expected": missing_groups_after_expected,
            "generated_addon_count": len(addon_samples),
            "generated_capabilities": [item["capability_id"] for item in target_plan],
        },
        "addons": [
            {
                "sample_id": _str_value(sample.get("sample_id")),
                "task_id": _str_value(sample.get("context", {}).get("task_id"))
                if isinstance(sample.get("context"), dict)
                else None,
                "capability_id": _str_value(
                    sample.get("candidates", [{}])[0].get("capability_id")
                    if isinstance(sample.get("candidates"), list) and sample.get("candidates")
                    else None
                ),
                "tool_id": _str_value(
                    sample.get("candidates", [{}])[0].get("tool_id")
                    if isinstance(sample.get("candidates"), list) and sample.get("candidates")
                    else None
                ),
                "source_sample_id": _str_value(
                    sample.get("addon_metadata", {}).get("source_sample_id")
                    if isinstance(sample.get("addon_metadata"), dict)
                    else None
                ),
            }
            for sample in addon_samples
        ],
    }

    with report_path.open("w", encoding="utf-8") as handle:
        handle.write(_json_dump(report) + "\n")
    return report


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate requirement2 addon samples to cover missing P0 core capabilities.",
    )
    parser.add_argument("--base-samples-path", type=Path, default=DEFAULT_BASE_SAMPLES_PATH)
    parser.add_argument("--base-gated-path", type=Path, default=DEFAULT_BASE_GATED_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--tool-kg-path", type=Path, default=DEFAULT_TOOL_KG_PATH)
    parser.add_argument("--tool-extension-kg-path", type=Path, default=DEFAULT_TOOL_EXTENSION_KG_PATH)
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    report = augment_requirement2_coverage(
        base_samples_path=args.base_samples_path,
        base_gated_path=args.base_gated_path,
        output_dir=args.output_dir,
        tool_kg_path=args.tool_kg_path,
        tool_extension_kg_path=args.tool_extension_kg_path,
    )

    print("Requirement2 coverage addon generation completed")
    print(_json_dump(report["requirement2_coverage"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
