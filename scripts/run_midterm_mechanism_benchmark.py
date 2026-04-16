#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.infra.midterm_mechanism_benchmark import (
    ScenarioResult,
    build_markdown_report,
    evaluate_signal,
    load_json,
    render_artifact_support_svg,
    render_capability_coverage_svg,
    render_family_summary_svg,
    summarize_artifacts,
    summarize_capabilities,
    summarize_families,
    write_csv,
    write_json,
)
from src.storage.log_store import read_timeline_events


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the redesigned midterm mechanism benchmark and generate PPT-ready charts."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/experiments/midterm_mechanism_benchmark.json"),
        help="Benchmark config path.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help="Optional override of output root.",
    )
    parser.add_argument(
        "--run-id",
        type=str,
        default=None,
        help="Optional run id. Uses UTC timestamp when omitted.",
    )
    parser.add_argument(
        "--max-scenarios",
        type=int,
        default=None,
        help="Optional cap for scenario count during smoke runs.",
    )
    return parser.parse_args()


def _now_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _git_short_sha() -> str:
    try:
        return (
            subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True, cwd=REPO_ROOT)
            .strip()
            .lower()
        )
    except Exception:
        return "nogit"


def _resolve_output_root(config: dict[str, Any], override: Path | None) -> Path:
    if override is not None:
        return override
    raw = config.get("output_root")
    if isinstance(raw, str) and raw:
        return Path(raw)
    return Path("output/experiment/midterm-mechanism-benchmark")


def _abs_repo_path(raw: str) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def _repo_relative(path: Path) -> str:
    absolute = path if path.is_absolute() else (REPO_ROOT / path)
    return str(absolute.relative_to(REPO_ROOT))


def _cleanup_artifacts(artifacts: list[dict[str, Any]]) -> None:
    for artifact in artifacts:
        raw_path = artifact.get("path")
        if not isinstance(raw_path, str) or not raw_path:
            continue
        path = _abs_repo_path(raw_path)
        if not path.exists():
            continue
        if path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)


def _build_command(scenario: dict[str, Any]) -> list[str]:
    runner = str(scenario.get("runner") or "")
    target = str(scenario.get("target") or "")
    if runner == "pytest":
        return ["uv", "run", "pytest", target, "-q"]
    raise ValueError(f"unsupported runner: {runner}")


def _run_scenario(scenario: dict[str, Any], stdout_path: Path, stderr_path: Path) -> tuple[bool, float]:
    command = _build_command(scenario)
    env = dict(os.environ)
    env.setdefault("UV_CACHE_DIR", "/tmp/uv-cache")
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    duration = time.perf_counter() - started
    stdout_path.write_text(completed.stdout, encoding="utf-8")
    stderr_path.write_text(completed.stderr, encoding="utf-8")
    return completed.returncode == 0, duration


def _collect_artifact_rows(artifacts: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    present_count = 0
    for artifact in artifacts:
        kind = str(artifact.get("kind") or "unknown")
        raw_path = str(artifact.get("path") or "")
        abs_path = _abs_repo_path(raw_path)
        present = abs_path.exists()
        if present:
            present_count += 1
        rows.append(
            {
                "kind": kind,
                "path": raw_path,
                "present": present,
                "abs_path": str(abs_path),
            }
        )
    return rows, present_count


def _collect_signal_rows(scenario: dict[str, Any], artifacts: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    expected_signals = scenario.get("expected_signals")
    if not isinstance(expected_signals, list) or not expected_signals:
        return [], 0

    event_log_artifact = next(
        (
            artifact
            for artifact in artifacts
            if artifact.get("kind") == "event_log" and artifact.get("present") is True
        ),
        None,
    )
    if event_log_artifact is None:
        return [
            {
                "signal": str(signal),
                "passed": False,
                "reason": "missing_event_log",
            }
            for signal in expected_signals
            if isinstance(signal, str)
        ], 0

    log_path = Path(event_log_artifact["abs_path"])
    events = read_timeline_events(log_path.stem, log_dir=log_path.parent)
    rows: list[dict[str, Any]] = []
    passed_count = 0
    for raw_signal in expected_signals:
        if not isinstance(raw_signal, str):
            continue
        passed = evaluate_signal(raw_signal, events)
        if passed:
            passed_count += 1
        rows.append({"signal": raw_signal, "passed": passed, "reason": "" if passed else "signal_not_found"})
    return rows, passed_count


def main() -> int:
    args = parse_args()
    config = load_json(args.config)

    benchmark_id = str(config.get("benchmark_id") or "midterm_mechanism_benchmark")
    output_root = _resolve_output_root(config, args.output_root)
    run_id = args.run_id or f"{benchmark_id}_{_now_tag()}_{_git_short_sha()}"
    run_dir = output_root / run_id
    logs_dir = run_dir / "scenario-logs"
    charts_dir = run_dir / "charts"
    run_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    charts_dir.mkdir(parents=True, exist_ok=True)

    raw_scenarios = config.get("scenarios")
    if not isinstance(raw_scenarios, list) or not raw_scenarios:
        raise ValueError("config.scenarios must be a non-empty list")

    scenario_results: list[ScenarioResult] = []
    scenario_rows: list[dict[str, Any]] = []
    artifact_rows_export: list[dict[str, Any]] = []
    signal_rows_export: list[dict[str, Any]] = []

    for index, scenario in enumerate(raw_scenarios):
        if args.max_scenarios is not None and index >= args.max_scenarios:
            break
        if not isinstance(scenario, dict):
            continue

        scenario_id = str(scenario.get("id") or f"scenario_{index + 1}")
        label = str(scenario.get("label") or scenario_id)
        family = str(scenario.get("family") or "Unknown")
        runner = str(scenario.get("runner") or "")
        target = str(scenario.get("target") or "")
        capabilities = tuple(
            str(item)
            for item in scenario.get("capabilities", [])
            if isinstance(item, str) and item
        )
        artifacts = scenario.get("artifacts") if isinstance(scenario.get("artifacts"), list) else []

        _cleanup_artifacts([artifact for artifact in artifacts if isinstance(artifact, dict)])

        stdout_path = logs_dir / f"{scenario_id}.stdout.txt"
        stderr_path = logs_dir / f"{scenario_id}.stderr.txt"
        passed, duration = _run_scenario(scenario, stdout_path, stderr_path)

        artifact_rows, artifacts_present = _collect_artifact_rows(
            [artifact for artifact in artifacts if isinstance(artifact, dict)]
        )
        signal_rows, signals_passed = _collect_signal_rows(scenario, artifact_rows)

        evidence_complete = (
            passed
            and artifacts_present == len(artifact_rows)
            and signals_passed == len(signal_rows)
        )
        if not artifact_rows and not signal_rows:
            evidence_complete = passed

        result = ScenarioResult(
            scenario_id=scenario_id,
            label=label,
            family=family,
            runner=runner,
            target=target,
            passed=passed,
            duration_sec=duration,
            capabilities=capabilities,
            artifacts_expected=len(artifact_rows),
            artifacts_present=artifacts_present,
            signals_expected=len(signal_rows),
            signals_passed=signals_passed,
            evidence_complete=evidence_complete,
            stdout_path=_repo_relative(stdout_path),
            stderr_path=_repo_relative(stderr_path),
            notes="" if passed else "scenario_command_failed",
        )
        scenario_results.append(result)

        scenario_rows.append(
            {
                "scenario_id": scenario_id,
                "label": label,
                "family": family,
                "runner": runner,
                "target": target,
                "passed": passed,
                "duration_sec": round(duration, 3),
                "artifacts_expected": len(artifact_rows),
                "artifacts_present": artifacts_present,
                "signals_expected": len(signal_rows),
                "signals_passed": signals_passed,
                "evidence_complete": evidence_complete,
                "capabilities": "|".join(capabilities),
                "stdout_path": result.stdout_path,
                "stderr_path": result.stderr_path,
            }
        )

        for artifact in artifact_rows:
            artifact_rows_export.append(
                {
                    "scenario_id": scenario_id,
                    "family": family,
                    "artifact_kind": artifact["kind"],
                    "path": artifact["path"],
                    "present": artifact["present"],
                }
            )
        for signal in signal_rows:
            signal_rows_export.append(
                {
                    "scenario_id": scenario_id,
                    "family": family,
                    "signal": signal["signal"],
                    "passed": signal["passed"],
                    "reason": signal["reason"],
                }
            )

    family_rows = summarize_families(scenario_results)
    capability_rows = summarize_capabilities(scenario_results)
    artifact_rows = summarize_artifacts(artifact_rows_export)

    manifest = {
        "benchmark_id": benchmark_id,
        "config_path": str(args.config),
        "run_id": run_id,
        "generated_at": _now_iso(),
        "git_sha": _git_short_sha(),
        "run_dir": str(run_dir),
        "scenario_count": len(scenario_results),
    }
    write_json(run_dir / "benchmark_manifest.json", manifest)
    write_json(run_dir / "scenario_results.json", scenario_rows)
    write_csv(
        run_dir / "scenario_results.csv",
        scenario_rows,
        [
            "scenario_id",
            "label",
            "family",
            "runner",
            "target",
            "passed",
            "duration_sec",
            "artifacts_expected",
            "artifacts_present",
            "signals_expected",
            "signals_passed",
            "evidence_complete",
            "capabilities",
            "stdout_path",
            "stderr_path",
        ],
    )
    write_csv(
        run_dir / "artifact_presence.csv",
        artifact_rows_export,
        ["scenario_id", "family", "artifact_kind", "path", "present"],
    )
    write_csv(
        run_dir / "signal_results.csv",
        signal_rows_export,
        ["scenario_id", "family", "signal", "passed", "reason"],
    )
    write_csv(
        run_dir / "family_summary.csv",
        family_rows,
        [
            "family",
            "scenario_count",
            "passed_count",
            "pass_rate",
            "avg_duration_sec",
            "artifact_present_rate",
            "signal_pass_rate",
            "evidence_complete_rate",
        ],
    )
    write_csv(
        run_dir / "capability_summary.csv",
        capability_rows,
        ["capability", "scenario_count", "passed_count", "pass_rate", "family_count"],
    )
    write_csv(
        run_dir / "artifact_summary.csv",
        artifact_rows,
        ["artifact_kind", "scenario_count", "expected_count", "present_count", "present_rate"],
    )

    family_svg = render_family_summary_svg(family_rows)
    capability_svg = render_capability_coverage_svg(capability_rows)
    artifact_svg = render_artifact_support_svg(artifact_rows)
    (charts_dir / "family_summary.svg").write_text(family_svg, encoding="utf-8")
    (charts_dir / "capability_coverage.svg").write_text(capability_svg, encoding="utf-8")
    (charts_dir / "artifact_support.svg").write_text(artifact_svg, encoding="utf-8")

    report = build_markdown_report(
        benchmark_id=benchmark_id,
        config_path=args.config,
        run_dir=run_dir,
        results=scenario_results,
        family_rows=family_rows,
        capability_rows=capability_rows,
        generated_at=_now_iso(),
    )
    (run_dir / "midterm_mechanism_benchmark_report.md").write_text(report, encoding="utf-8")

    print(f"[midterm-benchmark] run_dir={run_dir}")
    print(f"[midterm-benchmark] scenarios={len(scenario_results)}")
    print(f"[midterm-benchmark] family_summary={run_dir / 'family_summary.csv'}")
    print(f"[midterm-benchmark] capability_summary={run_dir / 'capability_summary.csv'}")
    print(f"[midterm-benchmark] charts_dir={charts_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
