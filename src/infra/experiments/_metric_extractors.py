from __future__ import annotations

from datetime import datetime
from pathlib import Path


def optional_path(value: object) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return Path(value)


def resolve_run_artifact_paths(
    run: dict[str, object],
) -> tuple[Path, Path | None, Path | None]:
    """统一解析单次实验 run 的日志、快照和报告路径。"""

    event_log_path = optional_path(run.get("event_log_path")) or Path("")
    snapshot_path = optional_path(run.get("snapshot_path"))
    report_path = optional_path(run.get("report_path"))
    return event_log_path, snapshot_path, report_path


def resolve_final_status(run: dict[str, object], observed_status: str | None) -> str:
    """优先采用事件日志观察到的终态，再回退到 run 显式状态。"""

    if observed_status is not None:
        return observed_status
    explicit = run.get("status_external")
    if isinstance(explicit, str) and explicit:
        return explicit
    return "UNKNOWN"


def compute_duration_ms(
    *,
    run: dict[str, object],
    started_at: datetime | None,
    finished_at: datetime | None,
    timestamps: list[datetime],
) -> float:
    """按 run 显式耗时、起止时间、事件时间戳的优先级计算耗时。"""

    duration_ms = run.get("duration_ms")
    if isinstance(duration_ms, (int, float)):
        return float(duration_ms)
    if started_at and finished_at:
        return (finished_at - started_at).total_seconds() * 1000.0
    if timestamps:
        return (max(timestamps) - min(timestamps)).total_seconds() * 1000.0
    return 0.0


def build_requirement2_coverage(
    *,
    capability_usage: dict[str, int],
    requirement2_capability_map: dict[str, list[str]],
) -> dict[str, bool]:
    """将 capability 使用计数投影到论文第二项需求覆盖桶。"""

    coverage: dict[str, bool] = {}
    for bucket, capabilities in requirement2_capability_map.items():
        coverage[bucket] = any(capability_usage.get(capability, 0) > 0 for capability in capabilities)
    return coverage
