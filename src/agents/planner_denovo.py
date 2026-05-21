from __future__ import annotations


def is_de_novo_task_kind(task_kind: str, *, denovo_goal_type: str) -> bool:
    """判断 task kind 是否属于 de novo 计划构造路径。"""

    return task_kind == denovo_goal_type
