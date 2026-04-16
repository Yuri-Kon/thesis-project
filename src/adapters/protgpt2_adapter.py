"""
ProtGPT2Adapter - ProtGPT2 远程序列生成适配器

通过 RemoteModelInvocationService 调用远程 PLM REST 服务，输出：
- sequence
- candidates
- artifacts
"""

from __future__ import annotations

import os
from pathlib import Path
from time import perf_counter, sleep
from typing import Any, Dict, Optional, Tuple

from src.adapters.base_tool_adapter import BaseToolAdapter
from src.engines.provider_config import get_provider_config
from src.engines.remote_model_service import (
    JobStatus,
    RESTModelInvocationService,
    RemoteModelInvocationService,
)
from src.models.contracts import PlanStep
from src.workflow.context import WorkflowContext
from src.workflow.errors import FailureCode, FailureType, StepRunError

__all__ = ["ProtGPT2Adapter"]


class ProtGPT2Adapter(BaseToolAdapter):
    """ProtGPT2 远程序列生成适配器（REST）"""

    tool_id = "protgpt2"
    adapter_id = "protgpt2"

    def __init__(
        self,
        service: Optional[RemoteModelInvocationService] = None,
        *,
        base_url: Optional[str] = None,
        output_dir: str | Path | None = None,
    ) -> None:
        if service is None:
            service_config = _resolve_plm_rest_service_config(base_url=base_url)
            service = RESTModelInvocationService(
                service_config["base_url"],
                timeout=service_config["timeout"],
                headers=service_config["headers"],
            )
        self.service = service
        self.output_dir = Path(output_dir or "output/sequences")

    def resolve_inputs(
        self,
        step: PlanStep,
        context: WorkflowContext,
    ) -> Dict[str, Any]:
        resolved: Dict[str, Any] = {}

        for key, val in step.inputs.items():
            if isinstance(val, str) and "." in val:
                step_id, field = val.split(".", 1)
                if step_id and step_id.startswith("S"):
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
            resolved[key] = val

        if "goal" not in resolved:
            resolved["goal"] = context.task.goal
        if "length_range" not in resolved:
            length_range = context.task.constraints.get("length_range")
            if isinstance(length_range, (list, tuple)) and len(length_range) == 2:
                resolved["length_range"] = [int(length_range[0]), int(length_range[1])]
        if "prompt" not in resolved:
            prompt = context.task.constraints.get("prompt")
            if isinstance(prompt, str) and prompt:
                resolved["prompt"] = prompt
        if "num_candidates" not in resolved:
            num_candidates = context.task.constraints.get("num_candidates")
            if isinstance(num_candidates, int) and num_candidates > 0:
                resolved["num_candidates"] = num_candidates

        goal = resolved.get("goal")
        if not isinstance(goal, str) or not goal.strip():
            raise ValueError(
                f"Missing required input 'goal' for ProtGPT2 step '{step.id}'"
            )

        resolved["task_id"] = context.task.task_id
        resolved["step_id"] = step.id
        return resolved

    def run_local(
        self,
        inputs: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        return self.run_remote(inputs, output_dir=self.output_dir)

    def run_remote(
        self,
        inputs: Dict[str, Any],
        output_dir: Optional[Path] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        t0 = perf_counter()
        task_id = str(inputs.get("task_id", "unknown"))
        step_id = str(inputs.get("step_id", "unknown"))

        payload = _build_submit_payload(inputs)
        job_id = self.service.submit_job(
            payload=payload, task_id=task_id, step_id=step_id
        )

        final_status = self._wait_for_completion(job_id)
        if final_status == JobStatus.FAILED:
            raise StepRunError(
                failure_type=FailureType.TOOL_ERROR,
                message=f"Remote job {job_id} failed",
                code=FailureCode.REMOTE_JOB_FAILED.value,
            )

        actual_output_dir = Path(output_dir or self.output_dir)
        actual_output_dir.mkdir(parents=True, exist_ok=True)
        raw_outputs = self.service.download_results(
            job_id=job_id, output_dir=actual_output_dir
        )
        outputs = _normalize_generation_outputs(raw_outputs)

        duration_ms = int((perf_counter() - t0) * 1000)
        metrics = {
            "exec_type": "remote",
            "duration_ms": duration_ms,
            "job_id": job_id,
            "provider": "plm_rest",
        }
        return outputs, metrics

    def _wait_for_completion(self, job_id: str) -> JobStatus:
        if hasattr(self.service, "wait_for_completion"):
            return self.service.wait_for_completion(job_id)

        max_attempts = 60
        poll_interval = 5.0
        for _ in range(max_attempts):
            status = self.service.poll_status(job_id)
            if status in (JobStatus.COMPLETED, JobStatus.FAILED):
                return status
            if status == JobStatus.UNKNOWN:
                raise StepRunError(
                    failure_type=FailureType.NON_RETRYABLE,
                    message=f"Job {job_id} status is unknown",
                    code=FailureCode.REMOTE_JOB_UNKNOWN.value,
                )
            sleep(poll_interval)
        raise StepRunError(
            failure_type=FailureType.RETRYABLE,
            message=f"Job {job_id} polling timeout",
            code=FailureCode.REMOTE_POLL_TIMEOUT.value,
        )


def _resolve_plm_rest_service_config(
    *,
    base_url: str | None,
) -> dict[str, Any]:
    default_base_url = "http://localhost:8100"
    env_base_url = str(os.getenv("PLM_REST_BASE_URL", "")).strip() or None
    timeout = 30.0
    headers: dict[str, str] | None = None

    try:
        config = get_provider_config("plm_rest")
    except KeyError:
        return {
            "base_url": env_base_url or base_url or default_base_url,
            "timeout": timeout,
            "headers": headers,
        }

    resolved_base_url = env_base_url or base_url or config.base_url or default_base_url
    if isinstance(config.timeout, (int, float)) and config.timeout > 0:
        timeout = float(config.timeout)
    headers = _resolve_plm_rest_headers(config)
    return {
        "base_url": resolved_base_url,
        "timeout": timeout,
        "headers": headers,
    }


def _resolve_plm_rest_headers(config: Any) -> dict[str, str] | None:
    token = ""
    try:
        token = str(config.get_api_key() or "").strip()
    except Exception:
        token = ""
    if not token:
        return None

    extra = config.extra if isinstance(getattr(config, "extra", None), dict) else {}
    header_value = extra.get("auth_header")
    if isinstance(header_value, str):
        key, sep, value = header_value.partition(":")
        if sep and key.strip():
            rendered = value.strip().replace("<token>", token)
            return {key.strip(): rendered}

    return {"Authorization": f"Bearer {token}"}


def _build_submit_payload(inputs: Dict[str, Any]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    passthrough_keys = (
        "goal",
        "length_range",
        "num_candidates",
        "num_return_sequences",
        "prompt",
        "max_new_tokens",
        "top_k",
        "top_p",
        "temperature",
        "repetition_penalty",
        "do_sample",
        "eos_token_id",
    )
    for key in passthrough_keys:
        if key in inputs:
            payload[key] = inputs[key]
    if "num_return_sequences" not in payload and "num_candidates" in payload:
        payload["num_return_sequences"] = payload["num_candidates"]
    return payload


def _normalize_generation_outputs(outputs: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(outputs or {})

    sequence = normalized.get("sequence")
    candidates_raw = normalized.get("candidates")
    candidates: list[dict[str, Any]] = []

    if isinstance(candidates_raw, list):
        for item in candidates_raw:
            if isinstance(item, dict):
                seq = item.get("sequence")
                if isinstance(seq, str) and seq:
                    entry = {"sequence": seq}
                    if "score" in item:
                        entry["score"] = item.get("score")
                    candidates.append(entry)

    if (not isinstance(sequence, str) or not sequence) and candidates:
        sequence = candidates[0]["sequence"]

    if isinstance(sequence, str) and sequence and not candidates:
        candidates = [{"sequence": sequence}]

    if not isinstance(sequence, str) or not sequence:
        raise StepRunError(
            failure_type=FailureType.TOOL_ERROR,
            message="Remote ProtGPT2 result missing 'sequence'",
            code=FailureCode.TOOL_EXECUTION_ERROR.value,
        )

    artifacts = normalized.get("artifacts")
    if isinstance(artifacts, list):
        normalized["artifacts"] = {
            "files": [str(path) for path in artifacts],
        }
    elif not isinstance(artifacts, dict):
        normalized["artifacts"] = {}

    normalized["sequence"] = sequence
    normalized["candidates"] = candidates
    return normalized
