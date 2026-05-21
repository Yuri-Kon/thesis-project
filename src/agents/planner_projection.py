from __future__ import annotations


def normalize_top_k(value: int) -> int:
    """将 Top-K 请求规范化为至少 1 个候选。"""

    if value <= 0:
        return 1
    return value
