"""OpenFold 结构预测适配器。"""
from __future__ import annotations

import os
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, Optional, Tuple

from src.adapters.base_tool_adapter import BaseToolAdapter
from src.adapters.structure_projection import normalize_structure_projection_outputs
from src.engines.nim_client import NvidiaNIMClient
from src.engines.provider_config import get_provider_config
from src.engines.remote_model_service import (
    JobStatus,
    RESTModelInvocationService,
    RemoteModelInvocationService,
)
from src.models.contracts import PlanStep
from src.workflow.context import WorkflowContext
from src.workflow.errors import FailureCode, FailureType, StepRunError

__all__ = ["OpenFold3Adapter"]


class OpenFold3Adapter(BaseToolAdapter):
    """OpenFold 适配器，兼容 NIM 与 REST 两种执行模式。"""

    tool_id = "openfold"
    adapter_id = "openfold"
    display_name = "OpenFold3"
    rest_provider_name = "openfold3_rest"
    rest_provider_aliases = ("openfold3_rest",)
    rest_base_url_env = "OPENFOLD3_REST_BASE_URL"
    rest_api_token_env = "OPENFOLD3_REST_API_TOKEN"
    max_sequence_length = 1000

    def __init__(
        self,
        *,
        execution_mode: str = "auto",
        nim_client: Optional[NvidiaNIMClient] = None,
        service: Optional[RemoteModelInvocationService] = None,
        base_url: Optional[str] = None,
        output_dir: str | Path | None = None,
        nim_model_id: str = "openfold/openfold3/predict",
    ) -> None:
        normalized_mode = _normalize_execution_mode(execution_mode)
        if normalized_mode not in {"auto", "nvidia_nim", "openfold3_rest"}:
            raise ValueError(
                "execution_mode must be one of: auto, nvidia_nim, openfold3_rest"
            )
        self.execution_mode = normalized_mode
        self.nim_model_id = nim_model_id
        self.nim_client = nim_client or NvidiaNIMClient(model_id=nim_model_id)
        self.service = service
        self.base_url = base_url
        self.output_dir = Path(output_dir or "output/pdb")

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

        sequence = resolved.get("sequence")
        molecules = resolved.get("molecules")
        if not isinstance(sequence, str) or not sequence:
            # molecules mode is accepted when user provides full request payload
            if not isinstance(molecules, list) or not molecules:
                raise ValueError(
                    f"Missing required input 'sequence' for {self.display_name} step '{step.id}'"
                )

        resolved["task_id"] = context.task.task_id
        resolved["step_id"] = step.id
        return resolved

    def run_local(
        self,
        inputs: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        mode = _normalize_execution_mode(str(inputs.get("execution_mode", self.execution_mode)))
        if mode == "auto":
            mode = self._effective_execution_mode()
        if mode == "nvidia_nim":
            return self._run_nim(inputs)
        if mode in self.rest_provider_aliases:
            return self._run_rest(inputs)
        raise StepRunError(
            failure_type=FailureType.NON_RETRYABLE,
            message=f"Unsupported execution mode: {mode}",
            code=FailureCode.INPUT_RESOLUTION_FAILED.value,
        )

    def _effective_execution_mode(self) -> str:
        api_key = str(getattr(self.nim_client, "api_key", "") or "").strip()
        if api_key or os.getenv("NIM_API_KEY"):
            return "nvidia_nim"
        if self._resolve_rest_service_config(base_url=self.base_url) is not None:
            return self.rest_provider_name
        raise StepRunError(
            failure_type=FailureType.NON_RETRYABLE,
            message=(
                f"{self.display_name} execution mode is unavailable. Set NIM_API_KEY for NIM "
                f"or configure {self.rest_base_url_env} for REST mode."
            ),
            code=FailureCode.NIM_API_KEY_MISSING.value,
        )

    def _run_nim(
        self,
        inputs: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        t0 = perf_counter()
        sequence = inputs.get("sequence")
        if isinstance(sequence, str) and len(sequence) > self.max_sequence_length:
            raise StepRunError(
                failure_type=FailureType.NON_RETRYABLE,
                message=(
                    f"Sequence length exceeds {self.display_name} NIM limit "
                    f"({len(sequence)} > {self.max_sequence_length})"
                ),
                code=FailureCode.NIM_INVALID_INPUT.value,
            )
        payload = _build_nim_payload(inputs, request_prefix=self.tool_id)

        response = self.nim_client.call_sync(payload)
        response_data = _unwrap_response(response)

        structure_text = _extract_structure_text(response_data)
        if not structure_text:
            raise StepRunError(
                failure_type=FailureType.TOOL_ERROR,
                message=f"{self.display_name} NIM response missing structure content",
                code=FailureCode.NIM_INVALID_RESPONSE.value,
            )

        plddt = _extract_plddt(response_data)
        extension = _guess_structure_extension(structure_text)
        task_id = str(inputs.get("task_id", "unknown"))
        step_id = str(inputs.get("step_id", "unknown"))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        structure_path = self.output_dir / f"{self.tool_id}_{task_id}_{step_id}.{extension}"
        structure_path.write_text(structure_text, encoding="utf-8")

        if plddt is None and extension == "pdb":
            plddt = _infer_plddt_from_pdb_text(structure_text)
        if plddt is None:
            plddt = 0.0

        outputs = {
            "pdb_path": str(structure_path.resolve()),
            "plddt": plddt,
            "metrics": {"plddt_mean": plddt},
        }
        sequence_for_output = _extract_sequence_for_downstream(inputs)
        if sequence_for_output:
            outputs["sequence"] = sequence_for_output
        outputs = normalize_structure_projection_outputs(outputs, tool_id=self.tool_id)
        metrics = {
            "exec_type": "nvidia_nim",
            "duration_ms": int((perf_counter() - t0) * 1000),
            "provider": "nvidia_nim",
            "model_id": self.nim_model_id,
        }
        return outputs, metrics

    def _run_rest(
        self,
        inputs: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        t0 = perf_counter()
        service = self._get_rest_service()
        task_id = str(inputs.get("task_id", "unknown"))
        step_id = str(inputs.get("step_id", "unknown"))

        payload = _build_rest_payload(inputs)
        job_id = service.submit_job(payload=payload, task_id=task_id, step_id=step_id)
        final_status = service.wait_for_completion(job_id)
        if final_status == JobStatus.FAILED:
            raise StepRunError(
                failure_type=FailureType.TOOL_ERROR,
                message=f"Remote job {job_id} failed",
                code=FailureCode.REMOTE_JOB_FAILED.value,
            )

        self.output_dir.mkdir(parents=True, exist_ok=True)
        outputs = service.download_results(job_id=job_id, output_dir=self.output_dir)
        outputs = dict(outputs or {})

        pdb_path = outputs.get("pdb_path")
        if not isinstance(pdb_path, str) or not pdb_path:
            cif_path = outputs.get("cif_path")
            if isinstance(cif_path, str) and cif_path:
                outputs["pdb_path"] = cif_path
            else:
                artifacts = outputs.get("artifacts")
                if isinstance(artifacts, list):
                    for path in artifacts:
                        if isinstance(path, str) and path.endswith((".pdb", ".cif", ".mmcif")):
                            outputs["pdb_path"] = path
                            break

        plddt = _extract_plddt(outputs)
        if plddt is None:
            plddt = _infer_plddt_from_pdb_path(outputs.get("pdb_path"))
        if plddt is None:
            plddt = 0.0
        outputs["plddt"] = plddt
        sequence_for_output = _extract_sequence_for_downstream(inputs)
        if sequence_for_output and not isinstance(outputs.get("sequence"), str):
            outputs["sequence"] = sequence_for_output
        outputs.setdefault("metrics", {"plddt_mean": plddt})
        outputs = normalize_structure_projection_outputs(outputs, tool_id=self.tool_id)

        metrics = {
            "exec_type": "remote",
            "duration_ms": int((perf_counter() - t0) * 1000),
            "provider": self.rest_provider_name,
            "job_id": job_id,
        }
        return outputs, metrics

    def _get_rest_service(self) -> RemoteModelInvocationService:
        if self.service is not None:
            return self.service
        service_config = self._resolve_rest_service_config(base_url=self.base_url)
        if service_config is None:
            raise StepRunError(
                failure_type=FailureType.NON_RETRYABLE,
                message=(
                    f"{self.display_name} REST configuration missing. Set {self.rest_base_url_env} "
                    f"or configure provider '{self.rest_provider_name}' in configs/model_providers.json."
                ),
                code=FailureCode.REMOTE_SUBMIT_INVALID_RESPONSE.value,
            )
        self.service = RESTModelInvocationService(
            service_config["base_url"],
            timeout=service_config["timeout"],
            headers=service_config["headers"],
        )
        return self.service

    def _resolve_rest_service_config(
        self,
        *,
        base_url: str | None,
    ) -> dict[str, Any] | None:
        return _resolve_openfold_rest_service_config(
            provider_names=self.rest_provider_aliases,
            base_url_env_keys=(self.rest_base_url_env,),
            api_token_env_keys=(self.rest_api_token_env,),
            base_url=base_url,
        )

    def healthcheck(self) -> Dict[str, Any]:
        api_key = str(getattr(self.nim_client, "api_key", "") or "").strip()
        if api_key or os.getenv("NIM_API_KEY"):
            return {
                "status": "ready",
                "reason": "NIM API key configured",
                "provider": "nvidia_nim",
            }
        rest_config = self._resolve_rest_service_config(base_url=self.base_url)
        if rest_config is not None:
            return {
                "status": "ready",
                "reason": "REST endpoint configured",
                "provider": self.rest_provider_name,
                "base_url": rest_config["base_url"],
            }
        return {
            "status": "unavailable",
            "reason": "neither NIM nor REST endpoint is configured",
        }
def _normalize_execution_mode(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"rest", "openfold3_rest", "remote_rest"}:
        return "openfold3_rest"
    if normalized in {"nim", "nvidia_nim"}:
        return "nvidia_nim"
    if normalized == "auto":
        return "auto"
    return normalized


def _build_nim_payload(inputs: Dict[str, Any], *, request_prefix: str) -> Dict[str, Any]:
    if isinstance(inputs.get("inputs"), list):
        payload: Dict[str, Any] = {"inputs": _inject_query_only_msa(inputs["inputs"])}
        if isinstance(inputs.get("request_id"), str):
            payload["request_id"] = inputs["request_id"]
        return payload

    sequence = inputs.get("sequence")
    if not isinstance(sequence, str) or not sequence:
        raise StepRunError(
            failure_type=FailureType.NON_RETRYABLE,
            message="Missing required input 'sequence' for OpenFold NIM mode",
            code=FailureCode.INPUT_RESOLUTION_FAILED.value,
        )

    request_id = str(inputs.get("request_id", f"{request_prefix}-request"))
    return {
        "request_id": request_id,
        "inputs": [
            {
                "input_id": request_id,
                "molecules": [
                    {
                        "type": "protein",
                        "id": "A",
                        "sequence": sequence,
                        "msa": _build_query_only_msa(sequence),
                    }
                ],
                "output_format": str(inputs.get("output_format", "pdb")),
            }
        ],
    }


def _build_rest_payload(inputs: Dict[str, Any]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    passthrough = (
        "sequence",
        "request_id",
        "output_format",
        "query_json",
        "query_json_path",
        "query_format",
        "openfold_args",
    )
    for key in passthrough:
        if key in inputs:
            payload[key] = inputs[key]
    return payload


def _resolve_openfold_rest_service_config(
    *,
    provider_names: tuple[str, ...],
    base_url_env_keys: tuple[str, ...],
    api_token_env_keys: tuple[str, ...],
    base_url: str | None,
) -> dict[str, Any] | None:
    env_base_url = None
    for env_key in base_url_env_keys:
        candidate = str(os.getenv(env_key, "")).strip()
        if candidate:
            env_base_url = candidate
            break
    timeout = 60.0
    headers: dict[str, str] | None = None

    config = None
    for provider_name in provider_names:
        try:
            config = get_provider_config(provider_name)
            break
        except KeyError:
            continue
    if config is None:
        resolved = env_base_url or base_url
        if not resolved:
            return None
        token = ""
        for env_key in api_token_env_keys:
            candidate = str(os.getenv(env_key, "")).strip()
            if candidate:
                token = candidate
                break
        if token:
            headers = {"Authorization": f"Bearer {token}"}
        return {"base_url": resolved, "timeout": timeout, "headers": headers}

    resolved_base_url = env_base_url or base_url or config.base_url
    if not resolved_base_url:
        return None

    if isinstance(config.timeout, (int, float)) and config.timeout > 0:
        timeout = float(config.timeout)

    token = ""
    try:
        token = str(config.get_api_key() or "").strip()
    except Exception:
        token = ""
    if token:
        extra = config.extra if isinstance(getattr(config, "extra", None), dict) else {}
        auth_header = extra.get("auth_header")
        if isinstance(auth_header, str) and ":" in auth_header:
            key, value = auth_header.split(":", 1)
            headers = {key.strip(): value.strip().replace("<token>", token)}
        else:
            headers = {"Authorization": f"Bearer {token}"}
    return {"base_url": resolved_base_url, "timeout": timeout, "headers": headers}


def _unwrap_response(response: Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(response.get("outputs"), dict):
        return response["outputs"]
    if isinstance(response.get("output"), dict):
        return response["output"]
    return response


def _extract_structure_text(data: Dict[str, Any]) -> Optional[str]:
    keys = (
        "pdb",
        "pdb_string",
        "pdb_text",
        "structure",
        "mmcif",
        "mmcif_string",
        "cif",
        "cif_string",
    )
    return _find_first_text_value(data, keys=keys)


def _extract_plddt(data: Dict[str, Any]) -> Optional[float]:
    target_keys = {"plddt", "plddt_mean", "mean_plddt"}
    # keep canonical aliases with original case too
    alias_keys = {"pLDDT", "mean_pLDDT"}
    for parsed in _iter_values_for_keys(data, target_keys=target_keys, alias_keys=alias_keys):
        if parsed is not None:
            return parsed
    return None


def _to_float(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, list):
        numbers = [float(item) for item in value if isinstance(item, (int, float))]
        if numbers:
            return sum(numbers) / len(numbers)
    if isinstance(value, dict):
        for key in ("mean", "avg", "average"):
            item = value.get(key)
            if isinstance(item, (int, float)):
                return float(item)
    return None


def _inject_query_only_msa(raw_inputs: list[Any]) -> list[Any]:
    normalized: list[Any] = []
    for item in raw_inputs:
        if not isinstance(item, dict):
            normalized.append(item)
            continue
        item_copy = dict(item)
        molecules = item_copy.get("molecules")
        if not isinstance(molecules, list):
            normalized.append(item_copy)
            continue
        fixed_molecules: list[Any] = []
        for molecule in molecules:
            if not isinstance(molecule, dict):
                fixed_molecules.append(molecule)
                continue
            mol_copy = dict(molecule)
            if _is_protein_molecule(mol_copy) and not _has_msa(mol_copy):
                seq = mol_copy.get("sequence")
                if isinstance(seq, str) and seq.strip():
                    mol_copy["msa"] = _build_query_only_msa(seq.strip())
            fixed_molecules.append(mol_copy)
        item_copy["molecules"] = fixed_molecules
        normalized.append(item_copy)
    return normalized


def _is_protein_molecule(molecule: Dict[str, Any]) -> bool:
    value = str(molecule.get("type", "")).strip().lower()
    return value == "protein"


def _has_msa(molecule: Dict[str, Any]) -> bool:
    msa = molecule.get("msa")
    if isinstance(msa, dict) and msa:
        return True
    paired = molecule.get("paired_msa")
    if isinstance(paired, dict) and paired:
        return True
    return False


def _build_query_only_msa(sequence: str) -> Dict[str, Any]:
    return {
        "main": {
            "a3m": {
                "alignment": f">query\n{sequence}\n",
                "format": "a3m",
            }
        }
    }


def _extract_sequence_for_downstream(inputs: Dict[str, Any]) -> Optional[str]:
    sequence = inputs.get("sequence")
    if isinstance(sequence, str) and sequence.strip():
        return sequence.strip()

    raw_inputs = inputs.get("inputs")
    if isinstance(raw_inputs, list):
        for item in raw_inputs:
            if not isinstance(item, dict):
                continue
            molecules = item.get("molecules")
            if not isinstance(molecules, list):
                continue
            for molecule in molecules:
                if not isinstance(molecule, dict):
                    continue
                if not _is_protein_molecule(molecule):
                    continue
                seq = molecule.get("sequence")
                if isinstance(seq, str) and seq.strip():
                    return seq.strip()
    return None


def _iter_values_for_keys(
    payload: Any,
    *,
    target_keys: set[str],
    alias_keys: set[str],
):
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_norm = key.lower()
            if key_norm in target_keys or key in alias_keys:
                yield _to_float(value)
                continue
            yield from _iter_values_for_keys(
                value,
                target_keys=target_keys,
                alias_keys=alias_keys,
            )
    elif isinstance(payload, list):
        for item in payload:
            yield from _iter_values_for_keys(
                item,
                target_keys=target_keys,
                alias_keys=alias_keys,
            )


def _find_first_text_value(payload: Any, *, keys: tuple[str, ...]) -> Optional[str]:
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value
        for value in payload.values():
            found = _find_first_text_value(value, keys=keys)
            if found:
                return found
        return None
    if isinstance(payload, list):
        for item in payload:
            found = _find_first_text_value(item, keys=keys)
            if found:
                return found
        return None
    return None


def _guess_structure_extension(structure_text: str) -> str:
    if structure_text.lstrip().lower().startswith("data_"):
        return "cif"
    return "pdb"


def _infer_plddt_from_pdb_text(pdb_text: str) -> Optional[float]:
    values: list[float] = []
    for line in pdb_text.splitlines():
        if not (line.startswith("ATOM") or line.startswith("HETATM")):
            continue
        if len(line) < 66:
            continue
        b_factor_str = line[60:66].strip()
        if not b_factor_str:
            continue
        try:
            values.append(float(b_factor_str))
        except ValueError:
            continue
    if not values:
        return None
    return sum(values) / len(values)


def _infer_plddt_from_pdb_path(value: Any) -> Optional[float]:
    if not isinstance(value, str) or not value.endswith(".pdb"):
        return None
    path = Path(value)
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    return _infer_plddt_from_pdb_text(text)
