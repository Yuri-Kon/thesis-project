"""
RemoteModelInvocationService 单元测试

测试远程模型调用服务的 REST 实现。
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import httpx
import pytest

from src.engines.remote_model_service import (
    JobStatus,
    RESTModelInvocationService,
)
from src.workflow.errors import FailureType, StepRunError


@pytest.fixture
def service() -> RESTModelInvocationService:
    """创建一个测试用的 REST 服务实例"""
    return RESTModelInvocationService(
        base_url="http://localhost:8000",
        timeout=10.0,
        poll_interval=0.1,  # 短轮询间隔用于测试
        max_poll_attempts=3,
    )


def test_submit_job_success(service: RESTModelInvocationService) -> None:
    """测试成功提交作业"""
    mock_response = Mock()
    mock_response.json.return_value = {"job_id": "job123"}
    mock_response.raise_for_status = Mock()

    with patch.object(service.client, "post", return_value=mock_response) as mock_post:
        job_id = service.submit_job(
            payload={"sequence": "ACDEFG"},
            task_id="task123",
            step_id="S1",
        )

    assert job_id == "job123"
    mock_post.assert_called_once_with(
        "http://localhost:8000/predict",
        json={
            "task_id": "task123",
            "step_id": "S1",
            "inputs": {"sequence": "ACDEFG"},
        },
    )


def test_submit_job_missing_job_id(service: RESTModelInvocationService) -> None:
    """测试服务响应缺少 job_id"""
    mock_response = Mock()
    mock_response.json.return_value = {}  # 缺少 job_id
    mock_response.raise_for_status = Mock()

    with patch.object(service.client, "post", return_value=mock_response):
        with pytest.raises(StepRunError) as exc_info:
            service.submit_job(
                payload={"sequence": "ACDEFG"},
                task_id="task123",
                step_id="S1",
            )

    assert exc_info.value.failure_type == FailureType.TOOL_ERROR
    assert "missing 'job_id'" in str(exc_info.value)


def test_submit_job_http_error(service: RESTModelInvocationService) -> None:
    """测试 HTTP 错误"""
    mock_response = Mock()
    mock_response.status_code = 500

    with patch.object(
        service.client,
        "post",
        side_effect=httpx.HTTPStatusError(
            "Server error",
            request=Mock(),
            response=mock_response,
        ),
    ):
        with pytest.raises(StepRunError) as exc_info:
            service.submit_job(
                payload={"sequence": "ACDEFG"},
                task_id="task123",
                step_id="S1",
            )

    assert exc_info.value.failure_type == FailureType.RETRYABLE
    assert "500" in exc_info.value.code


def test_submit_job_network_error(service: RESTModelInvocationService) -> None:
    """测试网络错误"""
    with patch.object(
        service.client,
        "post",
        side_effect=httpx.RequestError("Connection failed", request=Mock()),
    ):
        with pytest.raises(StepRunError) as exc_info:
            service.submit_job(
                payload={"sequence": "ACDEFG"},
                task_id="task123",
                step_id="S1",
            )

    assert exc_info.value.failure_type == FailureType.RETRYABLE
    assert "NETWORK_ERROR" in exc_info.value.code


def test_poll_status_success(service: RESTModelInvocationService) -> None:
    """测试成功轮询状态"""
    mock_response = Mock()
    mock_response.json.return_value = {"job_id": "job123", "status": "completed"}
    mock_response.raise_for_status = Mock()

    with patch.object(service.client, "get", return_value=mock_response) as mock_get:
        status = service.poll_status("job123")

    assert status == JobStatus.COMPLETED
    mock_get.assert_called_once_with("http://localhost:8000/job/job123")


def test_poll_status_not_found(service: RESTModelInvocationService) -> None:
    """测试作业未找到（404）"""
    mock_response = Mock()
    mock_response.status_code = 404

    with patch.object(
        service.client,
        "get",
        side_effect=httpx.HTTPStatusError(
            "Not found",
            request=Mock(),
            response=mock_response,
        ),
    ):
        status = service.poll_status("job123")

    assert status == JobStatus.UNKNOWN


def test_poll_status_unknown_value(service: RESTModelInvocationService) -> None:
    """测试未知的状态值"""
    mock_response = Mock()
    mock_response.json.return_value = {"job_id": "job123", "status": "invalid_status"}
    mock_response.raise_for_status = Mock()

    with patch.object(service.client, "get", return_value=mock_response):
        status = service.poll_status("job123")

    assert status == JobStatus.UNKNOWN


def test_download_results_success(service: RESTModelInvocationService, tmp_path: Path) -> None:
    """测试成功下载结果"""
    output_dir = tmp_path / "output"

    # Mock 结果响应
    mock_results_response = Mock()
    mock_results_response.json.return_value = {
        "job_id": "job123",
        "outputs": {
            "pdb_path": "structure.pdb",
            "metrics": {"pLDDT": 85.5},
        },
        "artifacts": [
            {"name": "structure.pdb", "url": "http://localhost:8000/files/structure.pdb"},
        ],
    }
    mock_results_response.raise_for_status = Mock()

    # Mock 文件下载
    mock_file_response = Mock()
    mock_file_response.raise_for_status = Mock()
    mock_file_response.iter_bytes = Mock(return_value=[b"ATOM 1"])

    with patch.object(service.client, "get", return_value=mock_results_response):
        with patch.object(service.client, "stream") as mock_stream:
            mock_stream.return_value.__enter__.return_value = mock_file_response

            outputs = service.download_results("job123", output_dir)

    assert outputs["pdb_path"] == "structure.pdb"
    assert outputs["metrics"]["pLDDT"] == 85.5
    assert len(outputs["artifacts"]) == 1
    assert (output_dir / "structure.pdb").exists()


def test_download_results_no_artifacts(service: RESTModelInvocationService, tmp_path: Path) -> None:
    """测试下载结果（无产物）"""
    output_dir = tmp_path / "output"

    mock_response = Mock()
    mock_response.json.return_value = {
        "job_id": "job123",
        "outputs": {"metrics": {"pLDDT": 85.5}},
    }
    mock_response.raise_for_status = Mock()

    with patch.object(service.client, "get", return_value=mock_response):
        outputs = service.download_results("job123", output_dir)

    assert outputs["metrics"]["pLDDT"] == 85.5
    assert "artifacts" not in outputs


def test_wait_for_completion_success(service: RESTModelInvocationService) -> None:
    """测试等待作业完成（成功）"""
    # 模拟状态变化：pending -> running -> completed
    statuses = [
        {"status": "pending"},
        {"status": "running"},
        {"status": "completed"},
    ]
    responses = []
    for status_data in statuses:
        mock_resp = Mock()
        mock_resp.json.return_value = status_data
        mock_resp.raise_for_status = Mock()
        responses.append(mock_resp)

    with patch.object(service.client, "get", side_effect=responses):
        with patch("time.sleep"):  # 跳过实际睡眠
            final_status = service.wait_for_completion("job123")

    assert final_status == JobStatus.COMPLETED


def test_wait_for_completion_failed(service: RESTModelInvocationService) -> None:
    """测试等待作业完成（失败）"""
    mock_response = Mock()
    mock_response.json.return_value = {"status": "failed"}
    mock_response.raise_for_status = Mock()

    with patch.object(service.client, "get", return_value=mock_response):
        final_status = service.wait_for_completion("job123")

    assert final_status == JobStatus.FAILED


def test_wait_for_completion_timeout(service: RESTModelInvocationService) -> None:
    """测试等待作业完成（超时）"""
    mock_response = Mock()
    mock_response.json.return_value = {"status": "running"}
    mock_response.raise_for_status = Mock()

    with patch.object(service.client, "get", return_value=mock_response):
        with patch("time.sleep"):
            with pytest.raises(StepRunError) as exc_info:
                service.wait_for_completion("job123")

    assert exc_info.value.failure_type == FailureType.RETRYABLE
    assert "timeout" in str(exc_info.value)


def test_wait_for_completion_unknown_status(service: RESTModelInvocationService) -> None:
    """测试等待作业完成（未知状态）"""
    mock_response = Mock()
    mock_response.json.return_value = {"status": "unknown"}
    mock_response.raise_for_status = Mock()

    with patch.object(service.client, "get", return_value=mock_response):
        with pytest.raises(StepRunError) as exc_info:
            service.wait_for_completion("job123")

    assert exc_info.value.failure_type == FailureType.NON_RETRYABLE
    assert "unknown" in str(exc_info.value)
