from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
from importlib import metadata
from pathlib import Path
from typing import Any, Dict, Tuple

DEFAULT_MODEL_DIR = "/root/autodl-tmp/models/openfold3"
DEFAULT_PREDICT_BIN = "run_openfold"
DEFAULT_DEVICE = "cuda"
_HELP_TEXT_CACHE: dict[str, str] = {}
_RUNNER_YAML_ENV = "OPENFOLD3_RUNNER_YAML"
_USE_MSA_SERVER_ENV = "OPENFOLD3_USE_MSA_SERVER"


def run_openfold3_prediction(
    inputs: Dict[str, Any],
    *,
    job_path: Path,
    model_dir: str = DEFAULT_MODEL_DIR,
    predict_bin: str = DEFAULT_PREDICT_BIN,
    device: str = DEFAULT_DEVICE,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Run OpenFold3 inference and return (outputs, metrics)."""
    if _is_mock_mode():
        return _run_mock_prediction(inputs=inputs, job_path=job_path, device=device)

    resolved_predict_bin = _resolve_predict_bin(predict_bin)
    query_json_path, query_format = _prepare_query_json(inputs=inputs, job_path=job_path)
    artifact_dir = job_path / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    runtime_tmp_dir = job_path / "tmp"
    runtime_tmp_dir.mkdir(parents=True, exist_ok=True)

    command, command_meta = _build_predict_command(
        query_json_path=query_json_path,
        output_dir=artifact_dir,
        model_dir=model_dir,
        predict_bin=resolved_predict_bin,
        inputs=inputs,
    )
    env = _build_predict_env(tmp_dir=runtime_tmp_dir)
    proc = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    if proc.returncode != 0:
        stderr_text = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(
            f"OpenFold3 command failed (code={proc.returncode}): {stderr_text}"
        )

    structure_path = _find_structure_file(artifact_dir)
    if structure_path is None:
        raise RuntimeError("OpenFold3 output missing structure file (.pdb/.cif/.mmcif)")

    plddt = _extract_plddt_from_artifacts(artifact_dir)
    if plddt is None and structure_path.suffix.lower() == ".pdb":
        plddt = _infer_plddt_from_pdb_text(structure_path.read_text(encoding="utf-8"))
    if plddt is None:
        plddt = 0.0

    outputs: Dict[str, Any] = {
        "pdb_path": str(structure_path.relative_to(artifact_dir).as_posix()),
        "plddt": plddt,
    }
    if structure_path.suffix.lower() in {".cif", ".mmcif"}:
        outputs["cif_path"] = str(structure_path.relative_to(artifact_dir).as_posix())

    metrics = {
        "device_used": device,
        "predict_bin": resolved_predict_bin,
        "model_dir": model_dir,
        "query_format": query_format,
        "openfold3_version": _detect_openfold3_version(),
        **command_meta,
    }
    return outputs, metrics


def write_artifacts(
    job_path: Path,
    *,
    outputs_payload: Dict[str, Any],
    metadata: Dict[str, Any],
) -> Dict[str, str]:
    artifact_dir = job_path / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    summary_path = artifact_dir / "summary.json"
    summary_payload = {
        "outputs": outputs_payload,
        "metadata": metadata,
    }
    summary_path.write_text(
        json.dumps(summary_payload, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )

    return {"summary_path": summary_path.name}


def _prepare_query_json(inputs: Dict[str, Any], *, job_path: Path) -> tuple[Path, str]:
    custom_path = inputs.get("query_json_path")
    if isinstance(custom_path, str) and custom_path:
        path = Path(custom_path)
        if not path.exists() or not path.is_file():
            raise RuntimeError(f"query_json_path does not exist: {custom_path}")
        return path, "custom"

    query_json = inputs.get("query_json")
    if isinstance(query_json, (dict, list)):
        payload = query_json
        query_format = "custom"
    else:
        sequence = inputs.get("sequence")
        if not isinstance(sequence, str) or not sequence.strip():
            raise RuntimeError(
                "OpenFold3 requires 'sequence' or explicit 'query_json/query_json_path'"
            )
        request_id = str(inputs.get("request_id", "openfold3_request"))
        query_format = _resolve_query_format(inputs)
        payload = _build_default_query_json(
            sequence=sequence.strip(),
            request_id=request_id,
            query_format=query_format,
        )

    query_path = job_path / "query.json"
    query_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    return query_path, query_format


def _build_default_query_json(
    *,
    sequence: str,
    request_id: str,
    query_format: str,
) -> Dict[str, Any]:
    if query_format == "queries":
        return {
            "queries": {
                request_id: {
                    "query_name": request_id,
                    "chains": [
                        {
                            "molecule_type": 0,
                            "chain_ids": ["A"],
                            "sequence": sequence,
                        }
                    ],
                }
            }
        }

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
                    }
                ],
                "output_format": "pdb",
            }
        ],
    }


def _build_predict_command(
    *,
    query_json_path: Path,
    output_dir: Path,
    model_dir: str,
    predict_bin: str,
    inputs: Dict[str, Any] | None = None,
) -> tuple[list[str], dict[str, Any]]:
    use_msa_server = _resolve_use_msa_server(inputs or {})
    custom_cmd = str(os.getenv("OPENFOLD3_PREDICT_CMD", "")).strip()
    if custom_cmd:
        rendered = custom_cmd.format(
            query_json=str(query_json_path),
            output_dir=str(output_dir),
            model_dir=model_dir,
            predict_bin=predict_bin,
            use_msa_server=str(use_msa_server),
        )
        return shlex.split(rendered), {
            "command_mode": "custom",
            "use_msa_server": use_msa_server,
        }

    query_opt = _pick_supported_option(
        predict_bin,
        ("--query-json", "--query_json"),
        default="--query_json",
    )
    output_opt = _pick_supported_option(
        predict_bin,
        ("--output-dir", "--output_dir"),
        default="--output_dir",
    )

    command = [
        predict_bin,
        "predict",
        f"{query_opt}={query_json_path}",
        f"{output_opt}={output_dir}",
    ]
    model_arg_mode = "none"
    if model_dir:
        model_arg = _build_model_arg(predict_bin=predict_bin, model_dir=model_dir)
        if model_arg is not None:
            command.append(model_arg)
            model_arg_mode = model_arg.split("=", 1)[0]

    runner_yaml_arg = _build_runner_yaml_arg(predict_bin=predict_bin)
    if runner_yaml_arg is not None:
        command.append(runner_yaml_arg)

    msa_server_arg = _build_use_msa_server_arg(
        predict_bin=predict_bin,
        use_msa_server=use_msa_server,
    )
    if msa_server_arg is not None:
        command.append(msa_server_arg)

    extra = str(os.getenv("OPENFOLD3_EXTRA_ARGS", "")).strip()
    if extra:
        command.extend(shlex.split(extra))
    return command, {
        "command_mode": "auto",
        "query_arg": query_opt,
        "output_arg": output_opt,
        "model_arg": model_arg_mode,
        "runner_yaml_arg": runner_yaml_arg.split("=", 1)[0] if runner_yaml_arg else "none",
        "runner_yaml_path": runner_yaml_arg.split("=", 1)[1] if runner_yaml_arg else None,
        "use_msa_server": use_msa_server,
        "use_msa_server_arg": msa_server_arg.split("=", 1)[0] if msa_server_arg else "none",
    }


def _resolve_query_format(inputs: Dict[str, Any]) -> str:
    configured = str(
        inputs.get("query_format")
        or os.getenv("OPENFOLD3_QUERY_FORMAT", "auto")
    ).strip().lower()
    if configured in {"queries", "inputs"}:
        return configured
    return _detect_runtime_query_format()


def _detect_runtime_query_format() -> str:
    try:
        from openfold3.projects.of3_all_atom.config.inference_query_format import InferenceQuerySet

        fields = getattr(InferenceQuerySet, "model_fields", {})
        if isinstance(fields, dict):
            if "queries" in fields:
                return "queries"
            if "inputs" in fields:
                return "inputs"
    except Exception:
        pass
    return "inputs"


def _build_model_arg(*, predict_bin: str, model_dir: str) -> str | None:
    model_opt = _pick_supported_option(
        predict_bin,
        ("--model-dir", "--model_dir"),
        default=None,
    )
    if model_opt is not None:
        return f"{model_opt}={model_dir}"

    ckpt_opt = _pick_supported_option(
        predict_bin,
        ("--inference-ckpt-path", "--inference_ckpt_path"),
        default=None,
    )
    if ckpt_opt is None:
        return None

    path = Path(model_dir)
    # For newer OpenFold3, invalid ckpt path fails fast; skip non-existing defaults.
    if not path.exists():
        return None
    return f"{ckpt_opt}={model_dir}"


def _build_runner_yaml_arg(*, predict_bin: str) -> str | None:
    configured = str(os.getenv(_RUNNER_YAML_ENV, "")).strip()
    if not configured:
        return None

    runner_yaml = Path(configured)
    if not runner_yaml.exists() or not runner_yaml.is_file():
        raise RuntimeError(
            f"{_RUNNER_YAML_ENV} does not exist or is not a file: {runner_yaml}"
        )

    runner_opt = _pick_supported_option(
        predict_bin,
        ("--runner-yaml", "--runner_yaml"),
        default="--runner_yaml",
    )
    if runner_opt is None:
        raise RuntimeError(
            f"{predict_bin} predict does not support --runner-yaml/--runner_yaml"
        )

    return f"{runner_opt}={runner_yaml}"


def _build_use_msa_server_arg(
    *,
    predict_bin: str,
    use_msa_server: bool,
) -> str | None:
    msa_opt = _pick_supported_option(
        predict_bin,
        ("--use-msa-server", "--use_msa_server"),
        default=None,
    )
    if msa_opt is None:
        return None
    return f"{msa_opt}={'True' if use_msa_server else 'False'}"


def _resolve_use_msa_server(inputs: Dict[str, Any]) -> bool:
    configured = inputs.get("use_msa_server")
    if configured is None:
        configured = os.getenv(_USE_MSA_SERVER_ENV, "false")
    if isinstance(configured, bool):
        return configured
    if isinstance(configured, (int, float)):
        return configured != 0
    value = str(configured).strip().lower()
    return value in {"1", "true", "yes", "on"}


def _build_predict_env(*, tmp_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    tmp_value = str(tmp_dir.resolve())
    env["TMPDIR"] = tmp_value
    env["TMP"] = tmp_value
    env["TEMP"] = tmp_value
    return env


def _pick_supported_option(
    predict_bin: str,
    options: tuple[str, ...],
    *,
    default: str | None,
) -> str | None:
    help_text = _get_predict_help_text(predict_bin)
    if help_text:
        for option in options:
            if option in help_text:
                return option
    return default


def _get_predict_help_text(predict_bin: str) -> str:
    cached = _HELP_TEXT_CACHE.get(predict_bin)
    if cached is not None:
        return cached

    try:
        proc = subprocess.run(
            [predict_bin, "predict", "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        _HELP_TEXT_CACHE[predict_bin] = ""
        return ""

    output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    _HELP_TEXT_CACHE[predict_bin] = output
    return output


def _detect_openfold3_version() -> str:
    try:
        return metadata.version("openfold3")
    except Exception:
        return "unknown"


def _resolve_predict_bin(predict_bin: str) -> str:
    path_like = Path(predict_bin)
    if path_like.parent != Path("."):
        return predict_bin

    resolved = shutil.which(predict_bin)
    if resolved:
        return resolved

    sibling = Path(sys.executable).resolve().parent / predict_bin
    if sibling.exists() and sibling.is_file():
        return str(sibling)

    raise RuntimeError(
        f"Predict binary '{predict_bin}' not found in PATH. "
        "Set OPENFOLD3_PREDICT_BIN to an absolute path."
    )


def _find_structure_file(artifact_dir: Path) -> Path | None:
    patterns = ("*.pdb", "*.cif", "*.mmcif")
    for pattern in patterns:
        files = sorted(artifact_dir.rglob(pattern))
        if files:
            return files[0]
    return None


def _extract_plddt_from_artifacts(artifact_dir: Path) -> float | None:
    for json_file in sorted(artifact_dir.rglob("*.json")):
        try:
            payload = json.loads(json_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        value = _extract_plddt(payload)
        if value is not None:
            return value
    return None


def _extract_plddt(payload: Any) -> float | None:
    if isinstance(payload, dict):
        for key in ("plddt", "pLDDT", "plddt_mean", "mean_plddt", "mean_pLDDT"):
            value = payload.get(key)
            if isinstance(value, (int, float)):
                return float(value)
        for value in payload.values():
            parsed = _extract_plddt(value)
            if parsed is not None:
                return parsed
    if isinstance(payload, list):
        values = [float(item) for item in payload if isinstance(item, (int, float))]
        if values:
            return sum(values) / len(values)
        for item in payload:
            parsed = _extract_plddt(item)
            if parsed is not None:
                return parsed
    return None


def _infer_plddt_from_pdb_text(pdb_text: str) -> float | None:
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


def _run_mock_prediction(
    *,
    inputs: Dict[str, Any],
    job_path: Path,
    device: str,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    sequence = str(inputs.get("sequence", "ACDEFGHIKLMNPQRSTVWY")).strip()
    if not sequence:
        sequence = "ACDEFGHIKLMNPQRSTVWY"

    artifact_dir = job_path / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    pdb_path = artifact_dir / "prediction.pdb"
    pdb_path.write_text(
        _mock_pdb(sequence),
        encoding="utf-8",
    )
    plddt = 75.0
    outputs = {"pdb_path": pdb_path.name, "plddt": plddt}
    metrics = {"device_used": f"{device} (mock)", "predict_bin": "mock"}
    return outputs, metrics


def _mock_pdb(sequence: str) -> str:
    lines: list[str] = []
    x = 1.0
    for idx, aa in enumerate(sequence, start=1):
        residue = _aa3(aa)
        lines.append(
            f"ATOM  {idx:5d}  CA  {residue} A{idx:4d}    {x:8.3f}{0.0:8.3f}{0.0:8.3f}  1.00 75.00           C"
        )
        x += 1.0
    lines.append("END")
    return "\n".join(lines) + "\n"


def _aa3(aa1: str) -> str:
    mapping = {
        "A": "ALA",
        "C": "CYS",
        "D": "ASP",
        "E": "GLU",
        "F": "PHE",
        "G": "GLY",
        "H": "HIS",
        "I": "ILE",
        "K": "LYS",
        "L": "LEU",
        "M": "MET",
        "N": "ASN",
        "P": "PRO",
        "Q": "GLN",
        "R": "ARG",
        "S": "SER",
        "T": "THR",
        "V": "VAL",
        "W": "TRP",
        "Y": "TYR",
    }
    return mapping.get(aa1.upper(), "GLY")


def _is_mock_mode() -> bool:
    value = str(os.getenv("OPENFOLD3_MOCK_MODE", "")).strip().lower()
    return value in {"1", "true", "yes", "on"}
