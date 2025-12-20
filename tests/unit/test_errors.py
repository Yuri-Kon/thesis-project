import pytest

from src.workflow.errors import FailureType, is_retryable_failure


@pytest.mark.parametrize(
    "failure_type,expected",
    [
        (FailureType.RETRYABLE, True),
        (FailureType.NON_RETRYABLE, False),
        (FailureType.TOOL_ERROR, False),
        (FailureType.SAFETY_BLOCK, False),
    ],
)
def test_is_retryable_failure_mapping(failure_type, expected):
    assert is_retryable_failure(failure_type) is expected
