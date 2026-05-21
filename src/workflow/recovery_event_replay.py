from __future__ import annotations

from typing import Any


def normalize_runtime_state_summary(
    payload: dict[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    return dict(payload)
