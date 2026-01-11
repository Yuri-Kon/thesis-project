"""
RemoteModelInvocationService - 远程模型调用服务抽象

职责：
- 提供统一的远程模型调用接口（submit/poll/download）
- 默认实现 REST 客户端（POST predict / GET job / GET results）
- 保留 SSH/SDK 扩展点

设计约束：
- submit_job: 提交作业并返回 job_id
- poll_status: 轮询作业状态
- download_results: 下载作业结果到本地目录
- 产物落为 StepResult + artifacts（可被 Executor/Summarizer 消费）
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import Any, Dict

import httpx

from src.workflow.errors import FailureType, StepRunError

__all__ = [
    "JobStatus",
    "RemoteModelInvocationService",
    "RESTModelInvocationService",
]


class JobStatus(str, Enum):
    """远程作业状态枚举"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    UNKNOWN = "unknown"


class RemoteModelInvocationService(ABC):
    """远程模型调用服务抽象基类

    定义统一的接口，供不同的远程服务实现（REST/SSH/SDK）。
    """

    @abstractmethod
    def submit_job(
        self,
        payload: Dict[str, Any],
        task_id: str,
        step_id: str,
    ) -> str:
        """提交远程作业

        Args:
            payload: 作业输入参数
            task_id: 任务 ID
            step_id: 步骤 ID

        Returns:
            job_id: 远程作业 ID

        Raises:
            StepRunError: 提交失败
        """

    @abstractmethod
    def poll_status(
        self,
        job_id: str,
    ) -> JobStatus:
        """轮询作业状态

        Args:
            job_id: 远程作业 ID

        Returns:
            JobStatus: 作业状态

        Raises:
            StepRunError: 查询失败
        """

    @abstractmethod
    def download_results(
        self,
        job_id: str,
        output_dir: Path,
    ) -> Dict[str, Any]:
        """下载作业结果

        Args:
            job_id: 远程作业 ID
            output_dir: 输出目录

        Returns:
            outputs: 输出字典，包含文件路径和解析的指标

        Raises:
            StepRunError: 下载失败
        """


class RESTModelInvocationService(RemoteModelInvocationService):
    """基于 REST API 的远程模型调用服务

    默认端点约定：
    - POST {base_url}/predict - 提交作业
    - GET {base_url}/job/{job_id} - 查询作业状态
    - GET {base_url}/results/{job_id} - 获取作业结果
    """

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 30.0,
        poll_interval: float = 5.0,
        max_poll_attempts: int = 60,
    ) -> None:
        """初始化 REST 客户端

        Args:
            base_url: 远程服务基础 URL
            timeout: 请求超时时间（秒）
            poll_interval: 轮询间隔（秒）
            max_poll_attempts: 最大轮询次数
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.max_poll_attempts = max_poll_attempts
        self.client = httpx.Client(timeout=timeout)

    def __del__(self) -> None:
        """清理 HTTP 客户端"""
        if hasattr(self, "client"):
            self.client.close()

    def submit_job(
        self,
        payload: Dict[str, Any],
        task_id: str,
        step_id: str,
    ) -> str:
        """提交远程作业

        POST {base_url}/predict
        Body: {
            "task_id": "...",
            "step_id": "...",
            "inputs": {...}
        }
        Response: {
            "job_id": "..."
        }
        """
        endpoint = f"{self.base_url}/predict"

        request_data = {
            "task_id": task_id,
            "step_id": step_id,
            "inputs": payload,
        }

        try:
            response = self.client.post(endpoint, json=request_data)
            response.raise_for_status()
            data = response.json()

            if "job_id" not in data:
                raise StepRunError(
                    failure_type=FailureType.TOOL_ERROR,
                    message="Remote service response missing 'job_id'",
                    code="REMOTE_INVALID_RESPONSE",
                )

            return data["job_id"]

        except httpx.HTTPStatusError as exc:
            raise StepRunError(
                failure_type=FailureType.RETRYABLE
                if exc.response.status_code >= 500
                else FailureType.NON_RETRYABLE,
                message=f"Failed to submit job: HTTP {exc.response.status_code}",
                code=f"REMOTE_SUBMIT_HTTP_{exc.response.status_code}",
            ) from exc
        except httpx.RequestError as exc:
            raise StepRunError(
                failure_type=FailureType.RETRYABLE,
                message=f"Network error during job submission: {exc}",
                code="REMOTE_SUBMIT_NETWORK_ERROR",
            ) from exc
        except Exception as exc:
            raise StepRunError(
                failure_type=FailureType.TOOL_ERROR,
                message=f"Unexpected error during job submission: {exc}",
                code="REMOTE_SUBMIT_UNEXPECTED_ERROR",
            ) from exc

    def poll_status(
        self,
        job_id: str,
    ) -> JobStatus:
        """轮询作业状态

        GET {base_url}/job/{job_id}
        Response: {
            "job_id": "...",
            "status": "pending|running|completed|failed"
        }
        """
        endpoint = f"{self.base_url}/job/{job_id}"

        try:
            response = self.client.get(endpoint)
            response.raise_for_status()
            data = response.json()

            status_str = data.get("status", "unknown").lower()
            try:
                return JobStatus(status_str)
            except ValueError:
                return JobStatus.UNKNOWN

        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return JobStatus.UNKNOWN
            raise StepRunError(
                failure_type=FailureType.RETRYABLE
                if exc.response.status_code >= 500
                else FailureType.NON_RETRYABLE,
                message=f"Failed to poll job status: HTTP {exc.response.status_code}",
                code=f"REMOTE_POLL_HTTP_{exc.response.status_code}",
            ) from exc
        except httpx.RequestError as exc:
            raise StepRunError(
                failure_type=FailureType.RETRYABLE,
                message=f"Network error during status polling: {exc}",
                code="REMOTE_POLL_NETWORK_ERROR",
            ) from exc
        except Exception as exc:
            raise StepRunError(
                failure_type=FailureType.TOOL_ERROR,
                message=f"Unexpected error during status polling: {exc}",
                code="REMOTE_POLL_UNEXPECTED_ERROR",
            ) from exc

    def download_results(
        self,
        job_id: str,
        output_dir: Path,
    ) -> Dict[str, Any]:
        """下载作业结果

        GET {base_url}/results/{job_id}
        Response: {
            "job_id": "...",
            "outputs": {...},
            "artifacts": [
                {"name": "...", "url": "...", "type": "..."},
                ...
            ]
        }
        """
        endpoint = f"{self.base_url}/results/{job_id}"

        try:
            response = self.client.get(endpoint)
            response.raise_for_status()
            data = response.json()

            outputs: Dict[str, Any] = data.get("outputs", {})
            artifacts = data.get("artifacts", [])

            # 确保输出目录存在
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

            # 下载产物文件
            downloaded_artifacts = []
            for artifact in artifacts:
                artifact_name = artifact.get("name")
                artifact_url = artifact.get("url")

                if not artifact_name or not artifact_url:
                    continue

                # 下载文件
                artifact_path = output_dir / artifact_name
                self._download_file(artifact_url, artifact_path)
                downloaded_artifacts.append(str(artifact_path.resolve()))

            # 添加产物路径到输出
            if downloaded_artifacts:
                outputs["artifacts"] = downloaded_artifacts

            return outputs

        except httpx.HTTPStatusError as exc:
            raise StepRunError(
                failure_type=FailureType.RETRYABLE
                if exc.response.status_code >= 500
                else FailureType.NON_RETRYABLE,
                message=f"Failed to download results: HTTP {exc.response.status_code}",
                code=f"REMOTE_DOWNLOAD_HTTP_{exc.response.status_code}",
            ) from exc
        except httpx.RequestError as exc:
            raise StepRunError(
                failure_type=FailureType.RETRYABLE,
                message=f"Network error during result download: {exc}",
                code="REMOTE_DOWNLOAD_NETWORK_ERROR",
            ) from exc
        except Exception as exc:
            raise StepRunError(
                failure_type=FailureType.TOOL_ERROR,
                message=f"Unexpected error during result download: {exc}",
                code="REMOTE_DOWNLOAD_UNEXPECTED_ERROR",
            ) from exc

    def _download_file(
        self,
        url: str,
        path: Path,
    ) -> None:
        """下载单个文件

        Args:
            url: 文件 URL
            path: 本地保存路径

        Raises:
            httpx.HTTPStatusError: HTTP 错误
            httpx.RequestError: 网络错误
        """
        with self.client.stream("GET", url) as response:
            response.raise_for_status()
            with open(path, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=8192):
                    f.write(chunk)

    def wait_for_completion(
        self,
        job_id: str,
    ) -> JobStatus:
        """等待作业完成（阻塞式轮询）

        Args:
            job_id: 远程作业 ID

        Returns:
            JobStatus: 最终作业状态

        Raises:
            StepRunError: 轮询超时或失败
        """
        for _ in range(self.max_poll_attempts):
            status = self.poll_status(job_id)

            if status in (JobStatus.COMPLETED, JobStatus.FAILED):
                return status

            if status == JobStatus.UNKNOWN:
                raise StepRunError(
                    failure_type=FailureType.NON_RETRYABLE,
                    message=f"Job {job_id} status is unknown",
                    code="REMOTE_JOB_UNKNOWN",
                )

            time.sleep(self.poll_interval)

        # 超时
        raise StepRunError(
            failure_type=FailureType.RETRYABLE,
            message=f"Job {job_id} polling timeout after {self.max_poll_attempts} attempts",
            code="REMOTE_POLL_TIMEOUT",
        )
