"""
WorkflowEngineAdapter - Nextflow 执行后端

职责：
- 接收标准化的工具输入（dict）
- 将输入映射为 Nextflow 参数
- 执行 Nextflow 工作流（blocking）
- 从工作目录解析输出和指标
- 失败映射：Nextflow 非零退出码 / 输出缺失 → StepExecutionError

设计约束（见 SID:impl.nextflow.control_flow_constraints）：
- 单次 Nextflow run == 单个 PlanStep 执行（blocking）
- 不参与多步编排或决策
- 失败传播：Nextflow 失败 → StepExecutionError → StepResult.failed
- 输出目录约定：产物落在 output/，文件名含 task_id
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping
from pathlib import Path
from time import perf_counter
from typing import TypeGuard, cast

from src.workflow.errors import FailureType, StepRunError

__all__ = ["WorkflowEngineAdapter"]

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | JsonObject | JsonArray
type JsonObject = dict[str, JsonValue]
type JsonArray = list[JsonValue]


class WorkflowEngineAdapter:
    """Nextflow 执行后端适配器

    用于统一执行 execution="nextflow" 的工具，不特定于某个工具。
    """

    def __init__(
        self,
        *,
        nextflow_bin: str = "nextflow",
        profile: str = "docker",
        work_dir: Path | None = None,
        output_dir: Path | None = None,
    ) -> None:
        """初始化 WorkflowEngineAdapter

        Args:
            nextflow_bin: Nextflow 可执行文件路径，默认为 "nextflow"
            profile: Nextflow profile，默认为 "docker"
            work_dir: Nextflow 工作目录，默认为 "work/"
            output_dir: 输出目录，默认为 "output/"
        """
        self.nextflow_bin: str = nextflow_bin
        self.profile: str = profile
        self.work_dir: Path = Path(work_dir or "work")
        self.output_dir: Path = Path(output_dir or "output")

    def execute(
        self,
        *,
        module_path: str | Path,
        inputs: Mapping[str, JsonValue],
        task_id: str,
        step_id: str,
        tool_name: str,
    ) -> tuple[JsonObject, JsonObject]:
        """执行 Nextflow 工作流（blocking）

        Args:
            module_path: Nextflow 模块文件路径（.nf 文件）
            inputs: 工具输入参数
            task_id: 任务 ID
            step_id: 步骤 ID
            tool_name: 工具名称

        Returns:
            (outputs, metrics): 输出字典和指标字典

        Raises:
            StepRunError: Nextflow 执行失败或输出解析失败
        """
        t0 = perf_counter()

        # 1. 准备 Nextflow 参数
        nf_params = self._prepare_nextflow_params(
            inputs=inputs,
            task_id=task_id,
            step_id=step_id,
            tool_name=tool_name,
        )

        # 2. 执行 Nextflow
        try:
            result = self._run_nextflow(module_path, nf_params)
        except subprocess.CalledProcessError as exc:
            raise StepRunError(
                failure_type=self._classify_nextflow_error(exc.returncode),
                message=f"Nextflow execution failed with exit code {exc.returncode}",
                code=f"NEXTFLOW_EXIT_{exc.returncode}",
            ) from exc
        except Exception as exc:
            raise StepRunError(
                failure_type=FailureType.TOOL_ERROR,
                message=f"Unexpected error during Nextflow execution: {exc}",
                code="NEXTFLOW_UNEXPECTED_ERROR",
            ) from exc

        # 3. 解析输出
        try:
            outputs = self._parse_outputs(
                task_id=task_id,
                step_id=step_id,
                tool_name=tool_name,
            )
        except Exception as exc:
            raise StepRunError(
                failure_type=FailureType.NON_RETRYABLE,
                message=f"Failed to parse Nextflow outputs: {exc}",
                code="NEXTFLOW_OUTPUT_PARSE_ERROR",
            ) from exc

        # 4. 构造指标
        duration_ms = int((perf_counter() - t0) * 1000)
        metrics: JsonObject = {
            "exec_type": "nextflow",
            "duration_ms": duration_ms,
            "nextflow_exit_code": result.returncode,
        }

        return outputs, metrics

    def _prepare_nextflow_params(
        self,
        *,
        inputs: Mapping[str, JsonValue],
        task_id: str,
        step_id: str,
        tool_name: str,
    ) -> JsonObject:
        """准备 Nextflow 参数

        将标准化的工具输入映射为 Nextflow 参数，添加必要的上下文信息。

        Args:
            inputs: 工具输入参数
            task_id: 任务 ID
            step_id: 步骤 ID
            tool_name: 工具名称

        Returns:
            Nextflow 参数字典
        """
        nf_params: JsonObject = dict(inputs)
        nf_params["task_id"] = task_id
        nf_params["step_id"] = step_id
        nf_params["tool"] = tool_name
        nf_params["output_dir"] = str(self.output_dir.resolve())

        return nf_params

    def _run_nextflow(
        self,
        module_path: str | Path,
        params: Mapping[str, JsonValue],
    ) -> subprocess.CompletedProcess[str]:
        """执行 Nextflow 命令

        Args:
            module_path: Nextflow 模块文件路径
            params: Nextflow 参数

        Returns:
            subprocess.CompletedProcess

        Raises:
            subprocess.CalledProcessError: Nextflow 执行失败（非零退出码）
        """
        module_path = Path(module_path).resolve()

        # 构造 Nextflow 命令
        cmd = [
            self.nextflow_bin,
            "run",
            str(module_path),
            "-profile",
            self.profile,
            "-work-dir",
            str(self.work_dir.resolve()),
        ]

        # 添加参数（通过 --key value 格式）
        for key, value in params.items():
            if isinstance(value, bool):
                if value:
                    cmd.append(f"--{key}")
            else:
                cmd.extend([f"--{key}", str(value)])

        # 执行命令（blocking）
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,  # 非零退出码抛出 CalledProcessError
        )

        return result

    def _parse_outputs(
        self,
        *,
        task_id: str,
        step_id: str,
        tool_name: str,
    ) -> JsonObject:
        """从 Nextflow 工作目录解析输出

        根据输出目录约定（SID:arch.execution.nextflow_boundary）：
        - 产物根目录为 output/
        - 文件名格式：{task_id}_{step_id}.{ext} 或 {task_id}.{ext}（精确匹配）
        - 子目录结构：output/pdb/, output/metrics/, output/artifacts/

        Args:
            task_id: 任务 ID
            step_id: 步骤 ID
            tool_name: 工具名称

        Returns:
            输出字典，包含文件路径和解析的指标

        Raises:
            FileNotFoundError: 必需的输出文件不存在
            ValueError: 输出文件格式错误
        """
        _ = tool_name
        outputs: JsonObject = {}

        # 检查 metrics 输出
        metrics_dir = self.output_dir / "metrics"
        if metrics_dir.exists():
            metrics_file = self._find_output_file(
                metrics_dir, task_id, step_id, "_metrics.json"
            )
            if metrics_file:
                metrics_data = _load_json_object(metrics_file)
                outputs["metrics"] = metrics_data

        # 检查 pdb 输出
        pdb_dir = self.output_dir / "pdb"
        if pdb_dir.exists():
            pdb_file = self._find_output_file(pdb_dir, task_id, step_id, ".pdb")
            if pdb_file:
                outputs["pdb_path"] = str(pdb_file.resolve())

        # 检查 artifacts 输出（使用精确前缀匹配）
        artifacts_dir = self.output_dir / "artifacts"
        if artifacts_dir.exists():
            # 优先匹配 {task_id}_{step_id}_*
            artifact_files = list(artifacts_dir.glob(f"{task_id}_{step_id}_*"))
            if not artifact_files:
                # Fallback: 匹配 {task_id}_*（但不包含其他 task_id 的前缀）
                artifact_files = [
                    f
                    for f in artifacts_dir.glob(f"{task_id}_*")
                    if f.name.startswith(f"{task_id}_")
                ]
            if artifact_files:
                outputs["artifacts"] = [str(f.resolve()) for f in artifact_files]

        return outputs

    def _find_output_file(
        self,
        directory: Path,
        task_id: str,
        step_id: str,
        suffix: str,
    ) -> Path | None:
        """在目录中查找精确匹配的输出文件

        使用精确的文件名格式，避免子串匹配导致的错误。
        优先查找 {task_id}_{step_id}{suffix}，如果不存在则查找 {task_id}{suffix}。

        Args:
            directory: 搜索目录
            task_id: 任务 ID
            step_id: 步骤 ID
            suffix: 文件后缀（如 ".pdb", "_metrics.json"）

        Returns:
            找到的文件路径，如果不存在则返回 None
        """
        # 优先查找包含 step_id 的文件（更精确）
        exact_file = directory / f"{task_id}_{step_id}{suffix}"
        if exact_file.exists():
            return exact_file

        # Fallback: 查找只包含 task_id 的文件（向后兼容）
        fallback_file = directory / f"{task_id}{suffix}"
        if fallback_file.exists():
            return fallback_file

        return None

    def _classify_nextflow_error(self, exit_code: int) -> FailureType:
        """根据 Nextflow 退出码分类失败类型

        Args:
            exit_code: Nextflow 退出码

        Returns:
            失败类型
        """
        # Nextflow 常见退出码：
        # 0: 成功
        # 1: 一般错误（可能可重试）
        # 2: 使用错误（参数问题，不可重试）
        # 137: SIGKILL（可能是 OOM，可重试）
        # 143: SIGTERM（可能是超时，可重试）

        if exit_code in (137, 143):
            # 系统信号导致的失败，可能可重试
            return FailureType.RETRYABLE
        elif exit_code == 2:
            # 使用错误，不可重试
            return FailureType.NON_RETRYABLE
        else:
            # 其他错误，作为工具错误处理
            return FailureType.TOOL_ERROR


def _load_json_object(path: Path) -> JsonObject:
    payload = cast(object, json.loads(path.read_text(encoding="utf-8")))
    parsed = _as_json_object(payload)
    if parsed is None:
        raise ValueError(f"JSON file must contain an object: {path}")
    return parsed


def _as_json_object(value: object) -> JsonObject | None:
    if not isinstance(value, dict):
        return None
    result: JsonObject = {}
    for key, item in cast(Mapping[object, object], value).items():
        if isinstance(key, str) and _is_json_value(item):
            result[key] = item
    return result


def _is_json_value(value: object) -> TypeGuard[JsonValue]:
    if value is None or isinstance(value, str | int | float | bool):
        return True
    if isinstance(value, list):
        return all(_is_json_value(item) for item in cast(list[object], value))
    if isinstance(value, dict):
        return all(
            isinstance(key, str) and _is_json_value(item)
            for key, item in cast(Mapping[object, object], value).items()
        )
    return False
