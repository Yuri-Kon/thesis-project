from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.event_log import EventLog

# 事件日志默认目录，按 task_id 写入 jsonl 文件
DEFAULT_LOG_DIR = Path("data/logs")


def append_event(
    task_id: str,
    event: Mapping[str, Any],
    *,
    log_dir: Path = DEFAULT_LOG_DIR,
) -> None:
    """追加一条事件日志到 jsonl 文件中"""
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"{task_id}.jsonl"
    payload = json.dumps(dict(event), ensure_ascii=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(payload + "\n")


def write_event_log(
    event_log: EventLog,
    *,
    log_dir: Path = DEFAULT_LOG_DIR,
) -> None:
    """将 EventLog 对象持久化到 jsonl 文件中

    Args:
        event_log: EventLog 实例
        log_dir: 日志目录路径
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"{event_log.task_id}.jsonl"
    # 使用 model_dump() 转换为字典，保留所有字段
    payload = json.dumps(event_log.model_dump(), ensure_ascii=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(payload + "\n")


def read_event_logs(
    task_id: str,
    *,
    log_dir: Path = DEFAULT_LOG_DIR,
    strict: bool = False,
) -> list["EventLog"]:
    """读取指定任务的 EventLog 记录（过滤非结构化事件）"""
    path = log_dir / f"{task_id}.jsonl"
    if not path.exists():
        return []

    from src.models.event_log import EventLog

    events: list[EventLog] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                if strict:
                    raise
                continue
            if not isinstance(payload, dict):
                if strict:
                    raise ValueError("EventLog payload must be a JSON object")
                continue
            if "event_type" not in payload:
                continue
            try:
                events.append(EventLog.model_validate(payload))
            except Exception:
                if strict:
                    raise
                continue
    return events
