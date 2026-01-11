from __future__ import annotations

import json
from pathlib import Path
from typing import Any, List, Mapping, Optional

from src.models.contracts import TaskSnapshot

DEFAULT_SNAPSHOT_DIR = Path("data/snapshots")


def append_snapshot(
    snapshot: TaskSnapshot,
    *,
    snapshot_dir: Path = DEFAULT_SNAPSHOT_DIR,
) -> None:
    """追加写入 TaskSnapshot 到 jsonl 文件"""
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    path = snapshot_dir / f"{snapshot.task_id}.jsonl"
    payload: Mapping[str, Any] = snapshot.model_dump()
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


def read_snapshots(
    task_id: str,
    *,
    snapshot_dir: Path = DEFAULT_SNAPSHOT_DIR,
) -> List[TaskSnapshot]:
    """读取指定任务的所有快照

    Args:
        task_id: 任务 ID
        snapshot_dir: 快照文件所在目录

    Returns:
        按时间顺序排列的 TaskSnapshot 对象列表
        如果文件不存在则返回空列表
    """
    path = snapshot_dir / f"{task_id}.jsonl"
    if not path.exists():
        return []

    snapshots: List[TaskSnapshot] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            snapshot = TaskSnapshot.model_validate(payload)
            snapshots.append(snapshot)

    return snapshots


def read_latest_snapshot(
    task_id: str,
    *,
    snapshot_dir: Path = DEFAULT_SNAPSHOT_DIR,
) -> Optional[TaskSnapshot]:
    """读取指定任务的最新快照

    Args:
        task_id: 任务 ID
        snapshot_dir: 快照文件所在目录

    Returns:
        最新的 TaskSnapshot 对象，如果不存在快照则返回 None
    """
    snapshots = read_snapshots(task_id, snapshot_dir=snapshot_dir)
    if not snapshots:
        return None
    return snapshots[-1]
