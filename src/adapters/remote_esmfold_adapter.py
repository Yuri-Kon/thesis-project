"""
RemoteESMFoldAdapter - ESMFold 远程结构预测工具适配器

通过 RemoteModelInvocationService 调用远程 ESMFold 服务。

设计规格：
- 输入：单条氨基酸序列
- 输出：PDB 文件、置信度(pLDDT)
- 执行方式：远程 REST API（blocking with polling）
- 产物目录：output/remote/
"""
from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Dict, Optional, Tuple

from src.adapters.base_tool_adapter import BaseToolAdapter
from src.engines.remote_model_service import (
    JobStatus,
    RESTModelInvocationService,
    RemoteModelInvocationService,
)
from src.models.contracts import PlanStep, TaskSnapshot, now_iso
from src.workflow.context import WorkflowContext
from src.workflow.errors import FailureType, FailureCode, StepRunError
from src.workflow.recovery import RemoteJobContext

__all__ = ["RemoteESMFoldAdapter"]

SnapshotWriter = Callable[[TaskSnapshot], None]


class RemoteESMFoldAdapter(BaseToolAdapter):
    """ESMFold 远程结构预测工具适配器

    使用 RemoteModelInvocationService 调用远程 ESMFold 服务。
    """

    tool_id = "esmfold"
    adapter_id = "esmfold_remote"

    def __init__(
        self,
        service: Optional[RemoteModelInvocationService] = None,
        *,
        base_url: Optional[str] = None,
        output_dir: Optional[Path] = None,
        snapshot_writer: Optional[SnapshotWriter] = None,
        enable_snapshot: bool = True,
    ) -> None:
        """初始化 RemoteESMFoldAdapter

        Args:
            service: 远程服务实例，如果为 None 则使用 base_url 创建 REST 服务
            base_url: 远程服务基础 URL（当 service 为 None 时使用）
            output_dir: 输出目录，默认为 "output/remote"
            snapshot_writer: 可选的快照写入函数，用于在远程作业执行期间保存快照
            enable_snapshot: 是否启用快照写入（默认 True）
        """
        if service is None:
            if base_url is None:
                raise ValueError(
                    "Either 'service' or 'base_url' must be provided"
                )
            service = RESTModelInvocationService(base_url)

        self.service = service
        self.output_dir = Path(output_dir or "output/remote")
        self.snapshot_writer = snapshot_writer
        self.enable_snapshot = enable_snapshot
        self._context: Optional[WorkflowContext] = None

    def resolve_inputs(
        self,
        step: PlanStep,
        context: WorkflowContext,
    ) -> Dict[str, Any]:
        """解析输入参数

        支持字面量和引用语义（如 "S1.sequence"）。

        Args:
            step: 计划步骤
            context: 工作流上下文

        Returns:
            解析后的输入字典

        Raises:
            ValueError: 输入引用无法解析
        """
        # 保存 context 引用用于快照写入
        self._context = context

        resolved: Dict[str, Any] = {}

        for key, val in step.inputs.items():
            # 支持引用语义：StepID.field
            if isinstance(val, str) and "." in val:
                step_id, field = val.split(".", 1)
                if step_id and step_id.startswith("S"):
                    # 引用前一步骤的输出
                    if not context.has_step_result(step_id):
                        raise ValueError(
                            f"Failed to resolve input reference '{val}' "
                            f"for step '{step.id}': step '{step_id}' not found in context"
                        )
                    try:
                        resolved_value = context.get_step_output(step_id, field)
                    except KeyError as exc:
                        raise ValueError(
                            f"Failed to resolve input reference '{val}' "
                            f"for step '{step.id}': field '{field}' not found in step '{step_id}' outputs"
                        ) from exc
                    resolved[key] = resolved_value
                    continue

            # 字面量值
            resolved[key] = val

        # 验证必需的输入
        if "sequence" not in resolved:
            raise ValueError(
                f"Missing required input 'sequence' for ESMFold step '{step.id}'"
            )

        # 添加上下文信息（供 run_remote 使用）
        resolved["task_id"] = context.task.task_id
        resolved["step_id"] = step.id

        return resolved

    def run_local(
        self,
        inputs: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """本地执行（委托到远程执行）

        RemoteESMFoldAdapter 将 run_local 委托给 run_remote。
        这样可以保持与 StepRunner 的兼容性，无需修改现有流程。
        """
        return self.run_remote(inputs, output_dir=self.output_dir)

    def run_remote(
        self,
        inputs: Dict[str, Any],
        output_dir: Optional[Path] = None,
        *,
        resume_job_id: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """远程执行 ESMFold 预测

        通过 RemoteModelInvocationService 调用远程服务。

        Args:
            inputs: 输入参数，必须包含 "sequence"
            output_dir: 可选的输出目录覆盖
            resume_job_id: 可选的恢复作业 ID（用于从快照恢复）

        Returns:
            (outputs, metrics): 输出字典和指标字典
                outputs 包含:
                    - pdb_path: 可选的 PDB 文件路径
                    - metrics: 可选的预测指标（pLDDT 等）
                    - artifacts: 可选的产物文件列表
                metrics 包含:
                    - exec_type: "remote"
                    - duration_ms: 执行时间（毫秒）
                    - job_id: 远程作业 ID
                    - resumed: 是否从快照恢复（布尔值）

        Raises:
            StepRunError: 执行失败
        """
        t0 = perf_counter()

        # 获取上下文信息
        task_id = inputs.get("task_id", "unknown")
        step_id = inputs.get("step_id", "unknown")

        # 如果提供了 resume_job_id，直接跳到轮询阶段
        if resume_job_id:
            job_id = resume_job_id
            resumed = True
        else:
            # 验证输入
            sequence = inputs.get("sequence")
            if not sequence:
                raise StepRunError(
                    failure_type=FailureType.NON_RETRYABLE,
                    message="Missing required input 'sequence'",
                    code=FailureCode.INPUT_RESOLUTION_FAILED.value,
                )

            # 准备远程服务输入
            payload = {
                "sequence": sequence,
            }

            # 提交作业
            job_id = self.service.submit_job(
                payload=payload,
                task_id=task_id,
                step_id=step_id,
            )
            resumed = False

            # 写入快照（保存 job_id 和 endpoint 用于恢复）
            self._write_snapshot_if_enabled(
                task_id=task_id,
                step_id=step_id,
                job_id=job_id,
                status="pending",
            )

        # 等待作业完成（如果服务支持 wait_for_completion）
        if hasattr(self.service, "wait_for_completion"):
            final_status = self.service.wait_for_completion(job_id)
        else:
            # 手动轮询（使用默认策略）
            import time

            max_attempts = 60
            poll_interval = 5.0

            final_status = None
            for _ in range(max_attempts):
                status = self.service.poll_status(job_id)

                if status in (JobStatus.COMPLETED, JobStatus.FAILED):
                    final_status = status
                    break

                if status == JobStatus.UNKNOWN:
                    raise StepRunError(
                        failure_type=FailureType.NON_RETRYABLE,
                        message=f"Job {job_id} status is unknown",
                        code=FailureCode.REMOTE_JOB_UNKNOWN.value,
                    )

                time.sleep(poll_interval)

            if final_status is None:
                raise StepRunError(
                    failure_type=FailureType.RETRYABLE,
                    message=f"Job {job_id} polling timeout",
                    code=FailureCode.REMOTE_POLL_TIMEOUT.value,
                )

        if final_status == JobStatus.FAILED:
            duration_ms = int((perf_counter() - t0) * 1000)
            raise StepRunError(
                failure_type=FailureType.TOOL_ERROR,
                message=f"Remote job {job_id} failed",
                code=FailureCode.REMOTE_JOB_FAILED.value,
            )

        # 下载结果
        actual_output_dir = output_dir or self.output_dir
        actual_output_dir.mkdir(parents=True, exist_ok=True)

        outputs = self.service.download_results(
            job_id=job_id,
            output_dir=actual_output_dir,
        )

        # 构造指标
        duration_ms = int((perf_counter() - t0) * 1000)
        metrics = {
            "exec_type": "remote",
            "duration_ms": duration_ms,
            "job_id": job_id,
            "resumed": resumed,
        }

        return outputs, metrics

    def _write_snapshot_if_enabled(
        self,
        task_id: str,
        step_id: str,
        job_id: str,
        status: str,
    ) -> None:
        """写入快照（如果启用）

        Args:
            task_id: 任务 ID
            step_id: 步骤 ID
            job_id: 远程作业 ID
            status: 作业状态
        """
        if not self.enable_snapshot or self.snapshot_writer is None:
            return

        if self._context is None:
            return

        # 构建远程作业上下文
        endpoint = getattr(self.service, "base_url", "unknown")
        remote_job = RemoteJobContext(
            job_id=job_id,
            endpoint=endpoint,
            step_id=step_id,
            status=status,
            submitted_at=now_iso(),
        )

        # 构建 artifacts
        artifacts: Dict[str, Any] = {
            "remote_jobs": {
                step_id: remote_job.to_dict(),
            }
        }

        # 导入 build_task_snapshot（延迟导入避免循环依赖）
        from src.workflow.snapshots import build_task_snapshot

        # 构建并写入快照
        snapshot = build_task_snapshot(
            self._context,
            artifacts=artifacts,
        )
        self.snapshot_writer(snapshot)
