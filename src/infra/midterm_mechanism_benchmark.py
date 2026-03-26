from __future__ import annotations

import csv
import json
import math
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ScenarioResult:
    scenario_id: str
    label: str
    family: str
    runner: str
    target: str
    passed: bool
    duration_sec: float
    capabilities: tuple[str, ...]
    artifacts_expected: int
    artifacts_present: int
    signals_expected: int
    signals_passed: int
    evidence_complete: bool
    stdout_path: str
    stderr_path: str
    notes: str = ""


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fieldnames})


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            rows.append(json.loads(text))
    return rows


def has_waiting_chain_complete(events: list[dict[str, Any]]) -> bool:
    seqs: dict[str, list[int]] = {"WAITING_ENTER": [], "DECISION_APPLIED": [], "WAITING_EXIT": []}
    for event in events:
        event_type = str(event.get("event_type") or "")
        if event_type in seqs:
            seqs[event_type].append(int(event.get("seq") or 0))
    if not all(seqs.values()):
        return False
    return min(seqs["WAITING_ENTER"]) < min(seqs["DECISION_APPLIED"]) < min(seqs["WAITING_EXIT"])


def has_done_transition(events: list[dict[str, Any]]) -> bool:
    for event in events:
        if event.get("event_type") == "STATE_TRANSITION" and event.get("to_status") == "DONE":
            return True
    return False


def has_patching_transition(events: list[dict[str, Any]]) -> bool:
    for event in events:
        if event.get("event_type") == "STATE_TRANSITION" and event.get("to_status") == "PATCHING":
            return True
    return False


def has_replace_tool_event(events: list[dict[str, Any]]) -> bool:
    return any(event.get("event_type") == "REPLACE_TOOL" for event in events)


def has_recovery_escalated(events: list[dict[str, Any]], *, reason: str) -> bool:
    for event in events:
        if event.get("event_type") != "RECOVERY_ESCALATED":
            continue
        data = event.get("data")
        if isinstance(data, dict) and data.get("reason") == reason:
            return True
    return False


def has_s6_replan_step_failed(events: list[dict[str, Any]]) -> bool:
    for event in events:
        if event.get("event_type") != "STEP_FAILED":
            continue
        data = event.get("data")
        if not isinstance(data, dict):
            continue
        s6 = data.get("s6")
        if isinstance(s6, dict) and s6.get("action") == "replan":
            return True
    return False


def evaluate_signal(signal: str, events: list[dict[str, Any]]) -> bool:
    if signal == "waiting_chain_complete":
        return has_waiting_chain_complete(events)
    if signal == "done_transition":
        return has_done_transition(events)
    if signal == "patching_transition":
        return has_patching_transition(events)
    if signal == "replace_tool_event":
        return has_replace_tool_event(events)
    if signal == "recovery_escalated_patch_failed":
        return has_recovery_escalated(events, reason="patch_failed")
    if signal == "recovery_escalated_patch_high_risk":
        return has_recovery_escalated(events, reason="patch_high_risk")
    if signal == "s6_replan_step_failed":
        return has_s6_replan_step_failed(events)
    raise ValueError(f"unsupported signal: {signal}")


def summarize_families(results: list[ScenarioResult]) -> list[dict[str, Any]]:
    families = sorted({result.family for result in results})
    rows: list[dict[str, Any]] = []
    for family in families:
        items = [result for result in results if result.family == family]
        passed = sum(1 for item in items if item.passed)
        artifacts_expected = sum(item.artifacts_expected for item in items)
        artifacts_present = sum(item.artifacts_present for item in items)
        signals_expected = sum(item.signals_expected for item in items)
        signals_passed = sum(item.signals_passed for item in items)
        evidence_complete = sum(1 for item in items if item.evidence_complete)
        durations = [item.duration_sec for item in items]
        rows.append(
            {
                "family": family,
                "scenario_count": len(items),
                "passed_count": passed,
                "pass_rate": _ratio(passed, len(items)),
                "avg_duration_sec": statistics.mean(durations) if durations else 0.0,
                "artifact_present_rate": _ratio(artifacts_present, artifacts_expected),
                "signal_pass_rate": _ratio(signals_passed, signals_expected),
                "evidence_complete_rate": _ratio(evidence_complete, len(items)),
            }
        )
    return rows


def summarize_capabilities(results: list[ScenarioResult]) -> list[dict[str, Any]]:
    capabilities = sorted({cap for result in results for cap in result.capabilities})
    rows: list[dict[str, Any]] = []
    for capability in capabilities:
        items = [result for result in results if capability in result.capabilities]
        passed = sum(1 for item in items if item.passed)
        rows.append(
            {
                "capability": capability,
                "scenario_count": len(items),
                "passed_count": passed,
                "pass_rate": _ratio(passed, len(items)),
                "family_count": len({item.family for item in items}),
            }
        )
    return rows


def summarize_artifacts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, dict[str, int]] = {}
    for row in rows:
        artifact_kind = str(row.get("artifact_kind") or "unknown")
        bucket = counts.setdefault(
            artifact_kind,
            {"expected_count": 0, "present_count": 0, "scenario_ids": set()},
        )
        bucket["expected_count"] += 1
        bucket["present_count"] += 1 if row.get("present") else 0
        scenario_id = row.get("scenario_id")
        if isinstance(scenario_id, str) and scenario_id:
            bucket["scenario_ids"].add(scenario_id)
    rows: list[dict[str, Any]] = []
    for kind, payload in sorted(counts.items()):
        rows.append(
            {
                "artifact_kind": kind,
                "scenario_count": len(payload["scenario_ids"]),
                "expected_count": payload["expected_count"],
                "present_count": payload["present_count"],
                "present_rate": _ratio(payload["present_count"], payload["expected_count"]),
            }
        )
    return rows


def build_markdown_report(
    *,
    benchmark_id: str,
    config_path: Path,
    run_dir: Path,
    results: list[ScenarioResult],
    family_rows: list[dict[str, Any]],
    capability_rows: list[dict[str, Any]],
    generated_at: str,
) -> str:
    total = len(results)
    passed = sum(1 for item in results if item.passed)
    avg_duration = statistics.mean([item.duration_sec for item in results]) if results else 0.0
    lines = [
        f"# {benchmark_id}",
        "",
        "## Summary",
        f"- generated_at: `{generated_at}`",
        f"- config: `{config_path}`",
        f"- run_dir: `{run_dir}`",
        f"- scenarios: `{total}`",
        f"- passed: `{passed}`",
        f"- pass_rate: `{_ratio(passed, total):.4f}`",
        f"- avg_duration_sec: `{avg_duration:.3f}`",
        "",
        "## Why This Benchmark",
        "- Current vertical midterm results are weak on end biological effect, so this benchmark shifts the midterm evidence toward the project’s core contribution: controllable execution, HITL governance, structured recovery, routing, and summarization.",
        "- All scenarios are reproducible integration checks that already exist in the repository and can be rerun end-to-end through `uv run pytest ...`.",
        "",
        "## Family Summary",
        "",
        "| family | scenarios | passed | pass_rate | avg_duration_sec | evidence_complete_rate |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in family_rows:
        lines.append(
            f"| {row['family']} | {row['scenario_count']} | {row['passed_count']} | {row['pass_rate']:.3f} | {row['avg_duration_sec']:.3f} | {row['evidence_complete_rate']:.3f} |"
        )

    lines.extend(
        [
            "",
            "## Capability Coverage",
            "",
            "| capability | scenarios | passed | pass_rate | family_count |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for row in capability_rows:
        lines.append(
            f"| {row['capability']} | {row['scenario_count']} | {row['passed_count']} | {row['pass_rate']:.3f} | {row['family_count']} |"
        )

    lines.extend(
        [
            "",
            "## PPT Takeaways",
            "- Midterm evidence should focus on mechanism validation rather than claiming final protein-design superiority.",
            "- The strongest story is that gating, HITL, recovery, routing, end-to-end execution, and summarization now all have reproducible benchmark scenarios.",
            "- Use the family and capability charts as the main experiment figures; add screenshots later as auxiliary evidence.",
            "",
            "## Scenario Results",
            "",
            "| scenario_id | family | passed | duration_sec | artifacts | signals |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for row in results:
        lines.append(
            f"| {row.scenario_id} | {row.family} | {int(row.passed)} | {row.duration_sec:.3f} | {row.artifacts_present}/{row.artifacts_expected} | {row.signals_passed}/{row.signals_expected} |"
        )
    return "\n".join(lines) + "\n"


def render_family_summary_svg(rows: list[dict[str, Any]]) -> str:
    prepared = []
    for row in rows:
        prepared.append(
            {
                "label": str(row["family"]),
                "value": float(row["scenario_count"]),
                "annotation": f"pass {row['passed_count']}/{row['scenario_count']} | avg {row['avg_duration_sec']:.1f}s",
            }
        )
    return render_horizontal_bar_chart_svg(
        title="Midterm Mechanism Benchmark: Family Coverage",
        subtitle="Bar length = number of reproducible scenarios in each family",
        rows=prepared,
        max_value=max((item["value"] for item in prepared), default=1.0),
        bar_color="#2E77D0",
    )


def render_capability_coverage_svg(rows: list[dict[str, Any]]) -> str:
    prepared = []
    for row in rows:
        prepared.append(
            {
                "label": str(row["capability"]),
                "value": float(row["passed_count"]),
                "annotation": f"{row['passed_count']}/{row['scenario_count']} scenarios",
            }
        )
    return render_horizontal_bar_chart_svg(
        title="Validated Mechanism Coverage",
        subtitle="Bar length = number of passing scenarios that validate the capability",
        rows=prepared,
        max_value=max((item["value"] for item in prepared), default=1.0),
        bar_color="#1E9D61",
    )


def render_artifact_support_svg(rows: list[dict[str, Any]]) -> str:
    prepared = []
    for row in rows:
        prepared.append(
            {
                "label": str(row["artifact_kind"]),
                "value": float(row["present_rate"]) * 100.0,
                "annotation": f"{row['present_count']}/{row['expected_count']} artifacts",
            }
        )
    return render_horizontal_bar_chart_svg(
        title="Artifact Support Rate",
        subtitle="Bar length = percentage of declared evidence files materialized during the run",
        rows=prepared,
        max_value=100.0,
        bar_color="#C87F1D",
        suffix="%",
    )


def render_horizontal_bar_chart_svg(
    *,
    title: str,
    subtitle: str,
    rows: list[dict[str, Any]],
    max_value: float,
    bar_color: str,
    suffix: str = "",
) -> str:
    width = 1280
    top = 120
    left = 280
    right = 1180
    row_height = 54
    chart_height = max(1, len(rows)) * row_height
    height = top + chart_height + 90
    if max_value <= 0:
        max_value = 1.0

    grid_values = _nice_grid_values(max_value)
    grid_lines: list[str] = []
    for grid in grid_values:
        x = left + ((right - left) * (grid / max_value))
        grid_lines.append(
            f'<line x1="{x:.1f}" y1="{top - 20}" x2="{x:.1f}" y2="{top + chart_height}" stroke="#E5E7EB" stroke-width="1" />'
        )
        grid_lines.append(
            f'<text x="{x:.1f}" y="{top - 28}" fill="#6B7280" font-size="14" text-anchor="middle">{_fmt_number(grid)}{suffix}</text>'
        )

    row_nodes: list[str] = []
    for index, row in enumerate(rows):
        y = top + index * row_height
        value = float(row["value"])
        bar_width = 0.0 if value <= 0 else (right - left) * (value / max_value)
        row_nodes.append(
            f'<text x="{left - 16}" y="{y + 22}" fill="#111827" font-size="17" text-anchor="end">{_xml_escape(str(row["label"]))}</text>'
        )
        row_nodes.append(
            f'<rect x="{left}" y="{y + 4}" width="{right - left}" height="24" rx="8" fill="#F3F4F6" />'
        )
        row_nodes.append(
            f'<rect x="{left}" y="{y + 4}" width="{bar_width:.1f}" height="24" rx="8" fill="{bar_color}" />'
        )
        row_nodes.append(
            f'<text x="{right + 16}" y="{y + 22}" fill="#374151" font-size="15">{_xml_escape(str(row["annotation"]))}</text>'
        )

    return "\n".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
            '<rect width="100%" height="100%" fill="#FFFFFF" />',
            f'<text x="52" y="56" fill="#111827" font-size="30" font-weight="700">{_xml_escape(title)}</text>',
            f'<text x="52" y="88" fill="#6B7280" font-size="18">{_xml_escape(subtitle)}</text>',
            *grid_lines,
            *row_nodes,
            "</svg>",
        ]
    )


def _nice_grid_values(max_value: float) -> list[float]:
    if max_value <= 1.0:
        step = 0.25
    else:
        step = max(1.0, math.ceil(max_value / 4.0))
    values = []
    current = 0.0
    while current <= max_value + 1e-9:
        values.append(round(current, 3))
        current += step
    if values[-1] < max_value:
        values.append(max_value)
    return values


def _fmt_number(value: float) -> str:
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.2f}"


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 1.0
    return numerator / denominator


def _xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
