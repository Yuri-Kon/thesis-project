#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.storage.log_store import read_timeline_events

OUTPUT_ROOT = REPO_ROOT / "output" / "demo" / "w12-issue-151"
OUTPUT_LOG_DIR = OUTPUT_ROOT / "logs"
DATA_LOG_DIR = REPO_ROOT / "data" / "logs"


@dataclass(frozen=True)
class DemoScenario:
    name: str
    pytest_target: str
    task_id: str
    replay_filename: str


SCENARIOS: tuple[DemoScenario, ...] = (
    DemoScenario(
        name="six_stage_hitl_replay",
        pytest_target="tests/integration/test_s6_control_layer_e2e.py::test_six_stage_waiting_patch_decision_replay_to_done",
        task_id="int_s6_patch_decision_replay_done",
        replay_filename="replay-record-001-six-stage-hitl.md",
    ),
    DemoScenario(
        name="tool_fallback_remote_to_local",
        pytest_target="tests/integration/test_recovery_layered_patch.py::test_layered_patch_promotes_remote_to_local_tool_level",
        task_id="int_layered_patch_remote_to_local",
        replay_filename="replay-record-002-tool-fallback.md",
    ),
)


def _run(cmd: Sequence[str]) -> None:
    completed = subprocess.run(
        list(cmd),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"Command failed ({' '.join(cmd)}):\nSTDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
        )


def _copy_log(task_id: str) -> Path:
    src = DATA_LOG_DIR / f"{task_id}.jsonl"
    if not src.exists():
        raise FileNotFoundError(f"Expected log not found: {src}")
    OUTPUT_LOG_DIR.mkdir(parents=True, exist_ok=True)
    dst = OUTPUT_LOG_DIR / src.name
    shutil.copy2(src, dst)
    return dst


def _write_replay_markdown(scenario: DemoScenario, events: list[dict], log_copy: Path) -> None:
    replay_path = OUTPUT_ROOT / scenario.replay_filename
    event_types = [str(event.get("event_type")) for event in events]
    lines = [
        f"# Replay Record: {scenario.name}",
        "",
        f"- Task ID: `{scenario.task_id}`",
        f"- Source test: `{scenario.pytest_target}`",
        f"- Log copy: `{log_copy}`",
        "",
        "## Event Sequence",
        "",
    ]
    for index, event in enumerate(events, start=1):
        lines.append(
            f"{index}. `{event.get('event_type')}` | ts={event.get('ts')} | summary={event.get('summary')}"
        )

    lines.extend(
        [
            "",
            "## Checkpoints",
            "",
            f"- Total events: `{len(events)}`",
            f"- Contains WAITING_ENTER: `{ 'WAITING_ENTER' in event_types }`",
            f"- Contains DECISION_APPLIED: `{ 'DECISION_APPLIED' in event_types }`",
            f"- Contains WAITING_EXIT: `{ 'WAITING_EXIT' in event_types }`",
            f"- Contains REPLACE_TOOL: `{ 'REPLACE_TOOL' in event_types }`",
            "",
        ]
    )

    replay_path.write_text("\n".join(lines), encoding="utf-8")


def _extract_release_checks(six_stage_events: list[dict], fallback_events: list[dict]) -> dict[str, bool]:
    six_types = [str(event.get("event_type")) for event in six_stage_events]
    fallback_replace = [
        event
        for event in fallback_events
        if event.get("event_type") == "REPLACE_TOOL"
    ]

    chain_ok = all(
        item in six_types for item in ("WAITING_ENTER", "DECISION_APPLIED", "WAITING_EXIT")
    )
    fallback_ok = False
    if fallback_replace:
        recovery = fallback_replace[-1].get("data", {}).get("recovery", {})
        fallback_ok = (
            isinstance(recovery, dict)
            and recovery.get("from_tool") == "failing_tool"
            and recovery.get("to_tool") == "esmfold"
        )

    done_ok = any(
        event.get("event_type") == "STATE_TRANSITION"
        and event.get("to_status") == "DONE"
        for event in six_stage_events
    )

    return {
        "audit_chain_pendingaction_decision_eventlog": chain_ok,
        "tool_fallback_switch_recorded": fallback_ok,
        "e2e_flow_reaches_done": done_ok,
    }


def _write_release_validation(checks: dict[str, bool]) -> None:
    release_path = OUTPUT_ROOT / "release-validation.md"
    known_issues = [
        "Demo scenarios are test-driven with mock runners; real remote services (NIM/Nextflow) are not required in this replay package.",
        "Event ordering relies on timestamp + append sequence; cross-process log writes should keep a single writer per task ID.",
    ]
    lines = [
        "# Release Validation (Issue #151)",
        "",
        "## Scope",
        "",
        "- Candidate generation -> HITL decision -> execution recovery -> terminal output",
        "- Audit replay chain verification: `PendingAction -> Decision -> EventLog`",
        "- Tool fallback replay verification",
        "",
        "## Command Set",
        "",
        "```bash",
        "uv run pytest tests/integration/test_s6_control_layer_e2e.py::test_six_stage_waiting_patch_decision_replay_to_done -q",
        "uv run pytest tests/integration/test_recovery_layered_patch.py::test_layered_patch_promotes_remote_to_local_tool_level -q",
        "```",
        "",
        "## Gate Result",
        "",
    ]
    for key, value in checks.items():
        lines.append(f"- {key}: {'PASS' if value else 'FAIL'}")

    lines.extend(
        [
            "",
            "## Known Issues",
            "",
        ]
    )
    for item in known_issues:
        lines.append(f"- {item}")

    release_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    events_by_scenario: dict[str, list[dict]] = {}
    for scenario in SCENARIOS:
        _run(("uv", "run", "pytest", scenario.pytest_target, "-q"))
        copied_log = _copy_log(scenario.task_id)
        events = read_timeline_events(scenario.task_id, log_dir=DATA_LOG_DIR)
        events_by_scenario[scenario.name] = events
        _write_replay_markdown(scenario, events, copied_log)

    checks = _extract_release_checks(
        six_stage_events=events_by_scenario["six_stage_hitl_replay"],
        fallback_events=events_by_scenario["tool_fallback_remote_to_local"],
    )
    _write_release_validation(checks)

    summary_path = OUTPUT_ROOT / "demo-summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "scenarios": [scenario.name for scenario in SCENARIOS],
                "checks": checks,
                "output_root": str(OUTPUT_ROOT),
            },
            ensure_ascii=True,
            indent=2,
        ),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
