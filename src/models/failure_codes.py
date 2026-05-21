from __future__ import annotations

from enum import Enum


def normalize_failure_code_value(value: object) -> str | None:
    if isinstance(value, str) and value:
        return value
    if isinstance(value, Enum) and isinstance(value.value, str) and value.value:
        return value.value
    return None
