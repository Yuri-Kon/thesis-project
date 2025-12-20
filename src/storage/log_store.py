from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

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
