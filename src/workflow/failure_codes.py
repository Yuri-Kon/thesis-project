from __future__ import annotations

from src.models.contracts import StepResult
from src.models.failure_codes import normalize_failure_code_value


def extract_step_failure_code(
    step_result: StepResult,
    *,
    include_risk_flags: bool = False,
) -> str | None:
    failure_code = normalize_failure_code_value(
        step_result.error_details.get("failure_code")
    )
    if failure_code:
        return failure_code
    if include_risk_flags:
        for flag in step_result.risk_flags:
            failure_code = normalize_failure_code_value(flag.code)
            if failure_code:
                return failure_code
    return None


def extract_step_failure_code_or_default(
    step_result: StepResult,
    *,
    default: str,
    include_risk_flags: bool = False,
) -> str:
    return (
        extract_step_failure_code(
            step_result,
            include_risk_flags=include_risk_flags,
        )
        or default
    )
