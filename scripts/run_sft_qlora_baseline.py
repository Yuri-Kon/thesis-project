#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import os
import platform
import random
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_DATASET_DIR = Path("output/dataset_v1/w11-sft-dataset-v1.1-20260315-57fc60d-r02")
DEFAULT_OUTPUT_ROOT = Path("output/training/w12-issue-148")
DEFAULT_CONFIG_PATH = Path("configs/training/sft_qlora_baseline_p0_only.json")
DEFAULT_CANDIDATE_VERSION = "v0.3.0-rc1"


@dataclass(frozen=True)
class ToolSliceStats:
    tool_id: str
    capability_id: str | None
    priority: str
    samples: int
    sample_ratio: float
    failure_samples: int
    failure_ratio: float


def _json_dump(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2)


def _str_value(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object expected: {path}")
    return payload


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write(_json_dump(payload) + "\n")


def _write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def _git_short_sha() -> str:
    try:
        return (
            subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True)
            .strip()
            .lower()
        )
    except Exception:
        return "nogit"


def _default_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"issue148-{stamp}-{_git_short_sha()}"


def _sample_tool_slice(sample: dict[str, Any]) -> tuple[str, str | None, str]:
    selected_tool_id: str | None = None
    selected_capability_id: str | None = None
    selected_priority: str | None = None
    selected = sample.get("selected")
    if isinstance(selected, dict):
        candidate = selected.get("selected_candidate")
        if isinstance(candidate, dict):
            selected_tool_id = _str_value(candidate.get("tool_id"))
            selected_capability_id = _str_value(candidate.get("capability_id"))
            metadata = candidate.get("metadata")
            if isinstance(metadata, dict):
                selected_priority = (_str_value(metadata.get("priority")) or "unknown").upper()

    quality = sample.get("quality_gate")
    if isinstance(quality, dict):
        tool_lineage = quality.get("tool_lineage")
        if isinstance(tool_lineage, dict):
            lineage_tool_id = _str_value(tool_lineage.get("tool_id"))
            lineage_capability_id = _str_value(tool_lineage.get("capability_id"))
            lineage_priority = (_str_value(tool_lineage.get("priority")) or "unknown").upper()
            return (
                selected_tool_id or lineage_tool_id or "unknown_tool",
                selected_capability_id or lineage_capability_id,
                selected_priority if selected_priority and selected_priority != "UNKNOWN" else lineage_priority,
            )

    return selected_tool_id or "unknown_tool", selected_capability_id, selected_priority or "UNKNOWN"


def _is_failure_sample(sample: dict[str, Any]) -> bool:
    outcome = sample.get("outcome")
    if not isinstance(outcome, dict):
        return False
    final_status = (_str_value(outcome.get("final_status")) or "").upper()
    if final_status and final_status != "DONE":
        return True
    failure_types = outcome.get("step_failure_types")
    if isinstance(failure_types, list):
        return any(_str_value(item) for item in failure_types)
    return False


def select_samples_for_training(
    rows: list[dict[str, Any]],
    *,
    allowed_priorities: list[str],
    max_samples_per_tool: int,
    seed: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    normalized = {item.upper() for item in allowed_priorities if _str_value(item)}
    randomizer = random.Random(seed)

    candidates: list[dict[str, Any]] = []
    dropped_by_priority = 0
    for row in rows:
        _, _, priority = _sample_tool_slice(row)
        if normalized and priority.upper() not in normalized:
            dropped_by_priority += 1
            continue
        candidates.append(row)

    randomizer.shuffle(candidates)

    selected: list[dict[str, Any]] = []
    per_tool_count: dict[str, int] = {}
    dropped_by_tool_cap = 0
    for row in candidates:
        tool_id, _, _ = _sample_tool_slice(row)
        current = per_tool_count.get(tool_id, 0)
        if max_samples_per_tool > 0 and current >= max_samples_per_tool:
            dropped_by_tool_cap += 1
            continue
        per_tool_count[tool_id] = current + 1
        selected.append(row)

    report = {
        "input_total": len(rows),
        "selected_total": len(selected),
        "dropped_by_priority": dropped_by_priority,
        "dropped_by_tool_cap": dropped_by_tool_cap,
        "allowed_priorities": sorted(normalized),
        "max_samples_per_tool": max_samples_per_tool,
        "seed": seed,
    }
    return selected, report


def _render_prompt(sample: dict[str, Any]) -> str:
    context = sample.get("context") if isinstance(sample.get("context"), dict) else {}
    candidates = sample.get("candidates") if isinstance(sample.get("candidates"), list) else []
    prompt_payload = {
        "task_id": _str_value(context.get("task_id")),
        "sequence": _str_value(context.get("sequence")),
        "constraints": context.get("plan_metadata"),
        "status_path": context.get("status_path"),
        "candidate_count": len(candidates),
        "candidates": candidates[:3],
    }
    return _json_dump(prompt_payload)


def _render_response(sample: dict[str, Any]) -> str:
    selected = sample.get("selected") if isinstance(sample.get("selected"), dict) else {}
    candidate = selected.get("selected_candidate") if isinstance(selected.get("selected_candidate"), dict) else {}
    response_payload = {
        "action_type": _str_value(selected.get("action_type")),
        "choice": _str_value(selected.get("choice")),
        "selected_candidate_id": _str_value(selected.get("selected_candidate_id")),
        "tool_id": _str_value(candidate.get("tool_id")),
        "capability_id": _str_value(candidate.get("capability_id")),
        "risk_level": _str_value(candidate.get("risk_level")),
        "cost_estimate": _str_value(candidate.get("cost_estimate")),
    }
    return _json_dump(response_payload)


def build_training_example(sample: dict[str, Any]) -> dict[str, Any]:
    tool_id, capability_id, priority = _sample_tool_slice(sample)
    prompt = _render_prompt(sample)
    response = _render_response(sample)
    text = (
        "### Instruction\n"
        "Generate planner decision payload in JSON.\n\n"
        "### Input\n"
        f"{prompt}\n\n"
        "### Response\n"
        f"{response}"
    )
    return {
        "text": text,
        "tool_id": tool_id,
        "capability_id": capability_id,
        "priority": priority,
        "is_failure": _is_failure_sample(sample),
    }


def compute_tool_slice_stats(rows: list[dict[str, Any]]) -> dict[str, ToolSliceStats]:
    per_tool: dict[str, dict[str, Any]] = {}
    total = len(rows)
    for row in rows:
        tool_id, capability_id, priority = _sample_tool_slice(row)
        bucket = per_tool.setdefault(
            tool_id,
            {
                "capability_id": capability_id,
                "priority": priority,
                "samples": 0,
                "failure_samples": 0,
            },
        )
        bucket["samples"] += 1
        if _is_failure_sample(row):
            bucket["failure_samples"] += 1

    stats: dict[str, ToolSliceStats] = {}
    for tool_id, payload in per_tool.items():
        samples = int(payload["samples"])
        failure_samples = int(payload["failure_samples"])
        stats[tool_id] = ToolSliceStats(
            tool_id=tool_id,
            capability_id=payload["capability_id"],
            priority=payload["priority"],
            samples=samples,
            sample_ratio=round(samples / total, 6) if total else 0.0,
            failure_samples=failure_samples,
            failure_ratio=round(failure_samples / samples, 6) if samples else 0.0,
        )
    return stats


def _flatten_tool_stats(payload: dict[str, ToolSliceStats]) -> dict[str, Any]:
    rows: dict[str, Any] = {}
    for tool_id, stats in sorted(payload.items()):
        rows[tool_id] = {
            "capability_id": stats.capability_id,
            "priority": stats.priority,
            "samples": stats.samples,
            "sample_ratio": stats.sample_ratio,
            "failure_samples": stats.failure_samples,
            "failure_ratio": stats.failure_ratio,
        }
    return rows


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_model_package_manifest(model_dir: Path) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    for path in sorted(model_dir.rglob("*")):
        if not path.is_file():
            continue
        files.append(
            {
                "path": str(path.relative_to(model_dir)),
                "bytes": path.stat().st_size,
                "sha256": _file_sha256(path),
            }
        )
    digest = hashlib.sha256()
    digest.update(json.dumps(files, ensure_ascii=True, sort_keys=True).encode("utf-8"))
    return {
        "root": str(model_dir),
        "files": files,
        "package_checksum": digest.hexdigest(),
    }


def render_model_card(
    *,
    candidate_version: str,
    dataset_version: str,
    run_id: str,
    base_model: str,
    sampling: dict[str, Any],
    train_stats: dict[str, Any],
    known_limits: list[str],
) -> str:
    lines = [
        f"# Planner SFT Baseline ({candidate_version})",
        "",
        "## Summary",
        f"- Run ID: `{run_id}`",
        f"- Base model: `{base_model}`",
        f"- Dataset version: `{dataset_version}`",
        f"- Allowed priorities: `{','.join(sampling.get('allowed_priorities', []))}`",
        "",
        "## Tool Coverage",
        "| tool_id | capability | priority | samples | sample_ratio | failure_ratio |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for tool_id, stats in sorted(train_stats.items()):
        lines.append(
            "| {tool} | {cap} | {pri} | {samples} | {ratio:.4f} | {failure:.4f} |".format(
                tool=tool_id,
                cap=stats.get("capability_id") or "-",
                pri=stats.get("priority") or "-",
                samples=stats.get("samples", 0),
                ratio=float(stats.get("sample_ratio", 0.0)),
                failure=float(stats.get("failure_ratio", 0.0)),
            )
        )

    lines.extend(["", "## Known Limits"])
    for item in known_limits:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def _import_training_stack() -> dict[str, Any]:
    try:
        import torch  # type: ignore
        from transformers import (  # type: ignore
            AutoModelForCausalLM,
            AutoTokenizer,
            BitsAndBytesConfig,
            DataCollatorForLanguageModeling,
            Trainer,
            TrainingArguments,
        )
        from peft import (  # type: ignore
            LoraConfig,
            PeftModel,
            TaskType,
            get_peft_model,
            prepare_model_for_kbit_training,
        )
    except Exception as exc:
        raise RuntimeError(
            "Missing training dependencies. Use `uv run --with torch --with transformers --with peft --with accelerate --with datasets`"
        ) from exc

    return {
        "torch": torch,
        "AutoModelForCausalLM": AutoModelForCausalLM,
        "AutoTokenizer": AutoTokenizer,
        "BitsAndBytesConfig": BitsAndBytesConfig,
        "DataCollatorForLanguageModeling": DataCollatorForLanguageModeling,
        "Trainer": Trainer,
        "TrainingArguments": TrainingArguments,
        "LoraConfig": LoraConfig,
        "TaskType": TaskType,
        "get_peft_model": get_peft_model,
        "prepare_model_for_kbit_training": prepare_model_for_kbit_training,
        "PeftModel": PeftModel,
    }


def _build_text_dataset(texts: list[str], tokenizer: Any, max_length: int, torch_mod: Any) -> Any:
    class _Dataset(torch_mod.utils.data.Dataset):
        def __init__(self, payloads: list[str]):
            self.items = payloads

        def __len__(self) -> int:
            return len(self.items)

        def __getitem__(self, index: int) -> dict[str, Any]:
            encoded = tokenizer(
                self.items[index],
                truncation=True,
                max_length=max_length,
                padding=False,
                return_tensors=None,
            )
            encoded["labels"] = list(encoded["input_ids"])
            return encoded

    return _Dataset(texts)


def _sanitize_metric_key(value: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in value).strip("_") or "tool"


def _build_eval_metrics_per_tool(
    *,
    trainer: Any,
    tokenizer: Any,
    examples: list[dict[str, Any]],
    max_length: int,
    torch_mod: Any,
    max_eval_samples_per_tool: int,
) -> dict[str, float | None]:
    grouped: dict[str, list[str]] = {}
    for item in examples:
        grouped.setdefault(item["tool_id"], []).append(item["text"])

    metrics: dict[str, float | None] = {}
    for tool_id, texts in sorted(grouped.items()):
        subset = texts[:max_eval_samples_per_tool] if max_eval_samples_per_tool > 0 else texts
        dataset = _build_text_dataset(subset, tokenizer, max_length, torch_mod)
        key = _sanitize_metric_key(tool_id)
        values = trainer.evaluate(eval_dataset=dataset, metric_key_prefix=f"eval_{key}")
        loss = None
        for metric_name, metric_value in values.items():
            if metric_name.endswith("_loss"):
                loss = float(metric_value)
                break
        metrics[tool_id] = loss
    return metrics


def _fallback_validation_rows(
    train_rows: list[dict[str, Any]],
    *,
    seed: int,
    holdout_ratio: float = 0.2,
) -> list[dict[str, Any]]:
    if not train_rows:
        return []
    randomizer = random.Random(seed)
    copied = list(train_rows)
    randomizer.shuffle(copied)
    holdout_size = max(1, int(round(len(copied) * holdout_ratio)))
    return copied[:holdout_size]


def _run_training(config: dict[str, Any]) -> dict[str, Any]:
    stack = _import_training_stack()
    torch_mod = stack["torch"]
    AutoTokenizer = stack["AutoTokenizer"]
    AutoModelForCausalLM = stack["AutoModelForCausalLM"]
    BitsAndBytesConfig = stack["BitsAndBytesConfig"]
    DataCollatorForLanguageModeling = stack["DataCollatorForLanguageModeling"]
    Trainer = stack["Trainer"]
    TrainingArguments = stack["TrainingArguments"]
    LoraConfig = stack["LoraConfig"]
    TaskType = stack["TaskType"]
    get_peft_model = stack["get_peft_model"]
    prepare_model_for_kbit_training = stack["prepare_model_for_kbit_training"]
    PeftModel = stack["PeftModel"]

    run_cfg = config["run"]
    dataset_cfg = config["dataset"]
    sampling_cfg = config["sampling"]
    training_cfg = config["training"]
    inference_cfg = config["inference"]

    dataset_dir = Path(dataset_cfg["dataset_dir"])
    train_rows = _read_jsonl(dataset_dir / dataset_cfg.get("train_file", "train.jsonl"))
    val_rows = _read_jsonl(dataset_dir / dataset_cfg.get("val_file", "val.jsonl"))

    selected_train_rows, train_sampling_report = select_samples_for_training(
        train_rows,
        allowed_priorities=list(sampling_cfg.get("allowed_priorities", [])),
        max_samples_per_tool=int(sampling_cfg.get("max_samples_per_tool", 0)),
        seed=int(sampling_cfg.get("seed", 0)),
    )
    selected_val_rows, val_sampling_report = select_samples_for_training(
        val_rows,
        allowed_priorities=list(sampling_cfg.get("allowed_priorities", [])),
        max_samples_per_tool=int(sampling_cfg.get("max_samples_per_tool", 0)),
        seed=int(sampling_cfg.get("seed", 0)) + 1,
    )
    val_sampling_report["source"] = "dataset_val"
    if not selected_val_rows:
        selected_val_rows = _fallback_validation_rows(
            selected_train_rows,
            seed=int(sampling_cfg.get("seed", 0)) + 99,
            holdout_ratio=0.2,
        )
        val_sampling_report["source"] = "train_holdout_fallback"
        val_sampling_report["selected_total"] = len(selected_val_rows)
        val_sampling_report["fallback_reason"] = "no_val_samples_after_sampling_filters"

    train_examples = [build_training_example(row) for row in selected_train_rows]
    val_examples = [build_training_example(row) for row in selected_val_rows]

    if not train_examples:
        raise RuntimeError("No training samples left after sampling filters")
    if not val_examples:
        raise RuntimeError("No validation samples left after sampling filters")

    train_stats = _flatten_tool_stats(compute_tool_slice_stats(selected_train_rows))
    val_stats = _flatten_tool_stats(compute_tool_slice_stats(selected_val_rows))

    output_root = Path(run_cfg.get("output_root", DEFAULT_OUTPUT_ROOT))
    run_id = _str_value(run_cfg.get("run_id")) or _default_run_id()
    candidate_version = _str_value(run_cfg.get("candidate_version")) or DEFAULT_CANDIDATE_VERSION
    run_dir = output_root / candidate_version / run_id
    model_dir = run_dir / "model"
    logs_dir = run_dir / "logs"
    checkpoints_dir = run_dir / "checkpoints"
    for directory in (model_dir, logs_dir, checkpoints_dir):
        directory.mkdir(parents=True, exist_ok=True)

    model_name = str(training_cfg["model_name"])
    max_length = int(training_cfg.get("max_seq_length", 768))
    seed = int(training_cfg.get("seed", 42))

    random.seed(seed)
    torch_mod.manual_seed(seed)
    if torch_mod.cuda.is_available():
        torch_mod.cuda.manual_seed_all(seed)

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    use_qlora = bool(training_cfg.get("use_qlora", False))
    qlora_enabled = False
    model_load_kwargs: dict[str, Any] = {}
    if use_qlora:
        try:
            import bitsandbytes  # type: ignore # noqa: F401

            q_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_dtype=torch_mod.float16,
            )
            model_load_kwargs["quantization_config"] = q_config
            model_load_kwargs["device_map"] = "auto"
            qlora_enabled = True
        except Exception:
            qlora_enabled = False

    model = AutoModelForCausalLM.from_pretrained(model_name, **model_load_kwargs)
    if qlora_enabled:
        model = prepare_model_for_kbit_training(model)

    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=int(training_cfg.get("lora_r", 16)),
        lora_alpha=int(training_cfg.get("lora_alpha", 32)),
        lora_dropout=float(training_cfg.get("lora_dropout", 0.05)),
        target_modules=list(training_cfg.get("target_modules", ["c_attn"])),
        bias="none",
    )
    model = get_peft_model(model, lora_config)

    train_dataset = _build_text_dataset([item["text"] for item in train_examples], tokenizer, max_length, torch_mod)
    val_dataset = _build_text_dataset([item["text"] for item in val_examples], tokenizer, max_length, torch_mod)
    collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)

    training_args_kwargs = {
        "output_dir": str(checkpoints_dir),
        "per_device_train_batch_size": int(training_cfg.get("per_device_train_batch_size", 1)),
        "per_device_eval_batch_size": int(training_cfg.get("per_device_eval_batch_size", 1)),
        "gradient_accumulation_steps": int(training_cfg.get("gradient_accumulation_steps", 1)),
        "max_steps": int(training_cfg.get("max_steps", 20)),
        "learning_rate": float(training_cfg.get("learning_rate", 2e-4)),
        "lr_scheduler_type": str(training_cfg.get("lr_scheduler_type", "cosine")),
        "warmup_steps": int(training_cfg.get("warmup_steps", 2)),
        "logging_steps": int(training_cfg.get("logging_steps", 1)),
        "eval_steps": int(training_cfg.get("eval_steps", 10)),
        "save_steps": int(training_cfg.get("save_steps", 10)),
        "save_total_limit": int(training_cfg.get("save_total_limit", 2)),
        "report_to": [],
        "bf16": bool(training_cfg.get("bf16", False)),
        "fp16": bool(training_cfg.get("fp16", False)) and torch_mod.cuda.is_available(),
        "seed": seed,
        "remove_unused_columns": False,
        "dataloader_num_workers": 0,
        "gradient_checkpointing": bool(training_cfg.get("gradient_checkpointing", False)),
    }
    signature = inspect.signature(TrainingArguments.__init__)
    if "evaluation_strategy" in signature.parameters:
        training_args_kwargs["evaluation_strategy"] = "steps"
    elif "eval_strategy" in signature.parameters:
        training_args_kwargs["eval_strategy"] = "steps"

    training_args = TrainingArguments(**training_args_kwargs)

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        data_collator=collator,
    )

    train_result = trainer.train()
    eval_result = trainer.evaluate()

    trainer.model.save_pretrained(model_dir)
    tokenizer.save_pretrained(model_dir)

    smoke_prompt = val_examples[0]["text"].split("### Response", 1)[0] + "### Response\n"
    inputs = tokenizer(smoke_prompt, return_tensors="pt")
    if torch_mod.cuda.is_available():
        inputs = {key: value.to("cuda") for key, value in inputs.items()}

    with torch_mod.no_grad():
        generated_ids = trainer.model.generate(
            **inputs,
            max_new_tokens=int(inference_cfg.get("smoke_max_new_tokens", 64)),
            do_sample=False,
            eos_token_id=tokenizer.eos_token_id,
            pad_token_id=tokenizer.pad_token_id,
        )
    generated_text = tokenizer.decode(generated_ids[0], skip_special_tokens=True)

    reload_base = AutoModelForCausalLM.from_pretrained(model_name)
    reload_model = PeftModel.from_pretrained(reload_base, model_dir)
    reload_tokenizer = AutoTokenizer.from_pretrained(model_dir)
    reload_inputs = reload_tokenizer(smoke_prompt, return_tensors="pt")
    with torch_mod.no_grad():
        reload_out = reload_model.generate(
            **reload_inputs,
            max_new_tokens=16,
            do_sample=False,
            eos_token_id=reload_tokenizer.eos_token_id,
            pad_token_id=reload_tokenizer.pad_token_id,
        )
    reload_preview = reload_tokenizer.decode(reload_out[0], skip_special_tokens=True)

    per_tool_eval_loss = _build_eval_metrics_per_tool(
        trainer=trainer,
        tokenizer=tokenizer,
        examples=val_examples,
        max_length=max_length,
        torch_mod=torch_mod,
        max_eval_samples_per_tool=int(training_cfg.get("max_eval_samples_per_tool", 8)),
    )

    combined_tool_stats: dict[str, Any] = {}
    for tool_id in sorted(set(train_stats) | set(val_stats)):
        combined_tool_stats[tool_id] = {
            "priority": train_stats.get(tool_id, val_stats.get(tool_id, {})).get("priority", "UNKNOWN"),
            "capability_id": train_stats.get(tool_id, val_stats.get(tool_id, {})).get("capability_id"),
            "train_samples": train_stats.get(tool_id, {}).get("samples", 0),
            "train_sample_ratio": train_stats.get(tool_id, {}).get("sample_ratio", 0.0),
            "train_failure_ratio": train_stats.get(tool_id, {}).get("failure_ratio", 0.0),
            "val_samples": val_stats.get(tool_id, {}).get("samples", 0),
            "val_sample_ratio": val_stats.get(tool_id, {}).get("sample_ratio", 0.0),
            "val_failure_ratio": val_stats.get(tool_id, {}).get("failure_ratio", 0.0),
            "val_loss": per_tool_eval_loss.get(tool_id),
        }

    model_manifest = build_model_package_manifest(model_dir)
    _write_json(run_dir / "model_package_manifest.json", model_manifest)

    checksum_lines = [
        f"{item['sha256']}  {item['path']}" for item in model_manifest["files"]
    ]
    _write_text(run_dir / "model_package_checksums.sha256", "\n".join(checksum_lines) + "\n")

    model_card = render_model_card(
        candidate_version=candidate_version,
        dataset_version=str(dataset_cfg["dataset_version"]),
        run_id=run_id,
        base_model=model_name,
        sampling={
            "allowed_priorities": [value.upper() for value in sampling_cfg.get("allowed_priorities", [])],
        },
        train_stats={
            key: {
                "capability_id": value.get("capability_id"),
                "priority": value.get("priority"),
                "samples": value.get("samples", 0),
                "sample_ratio": value.get("sample_ratio", 0.0),
                "failure_ratio": value.get("failure_ratio", 0.0),
            }
            for key, value in train_stats.items()
        },
        known_limits=[
            "Small-sample baseline for Week12 RC Gate-A.",
            "Only adapter weights are saved; base model is loaded from HuggingFace at inference time.",
            "Per-tool loss is measured on sampled validation subsets and is not a full benchmark.",
        ],
    )
    _write_text(run_dir / "model_card.md", model_card)

    summary = {
        "issue": "148",
        "run_id": run_id,
        "candidate_version": candidate_version,
        "dataset_version": dataset_cfg["dataset_version"],
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "paths": {
            "run_dir": str(run_dir),
            "model_dir": str(model_dir),
            "model_manifest": str(run_dir / "model_package_manifest.json"),
            "model_card": str(run_dir / "model_card.md"),
            "training_log": str(logs_dir / "trainer_log_history.json"),
            "smoke_inference": str(logs_dir / "smoke_inference.json"),
            "checksums": str(run_dir / "model_package_checksums.sha256"),
        },
        "sampling": {
            "train": train_sampling_report,
            "val": val_sampling_report,
        },
        "training": {
            "base_model": model_name,
            "qlora_enabled": qlora_enabled,
            "max_steps": training_args.max_steps,
            "learning_rate": training_args.learning_rate,
            "per_device_train_batch_size": training_args.per_device_train_batch_size,
            "gradient_accumulation_steps": training_args.gradient_accumulation_steps,
            "seed": training_args.seed,
            "train_runtime_seconds": train_result.metrics.get("train_runtime"),
            "train_samples_per_second": train_result.metrics.get("train_samples_per_second"),
            "final_train_loss": train_result.metrics.get("train_loss"),
            "eval_loss": eval_result.get("eval_loss"),
        },
        "tool_slice_stats": combined_tool_stats,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "cuda_available": torch_mod.cuda.is_available(),
            "torch": torch_mod.__version__,
        },
        "reproducibility": {
            "command": " ".join(sys.argv),
            "git_short_sha": _git_short_sha(),
        },
    }

    _write_json(logs_dir / "trainer_log_history.json", trainer.state.log_history)
    _write_json(
        logs_dir / "smoke_inference.json",
        {
            "prompt": smoke_prompt,
            "generation": generated_text,
            "reload_preview": reload_preview,
            "reload_success": True,
        },
    )
    _write_json(run_dir / "training_summary.json", summary)

    return summary


def load_config(path: Path) -> dict[str, Any]:
    payload = _read_json(path)
    for key in ("run", "dataset", "sampling", "training", "inference"):
        if key not in payload:
            raise ValueError(f"Missing config key: {key}")
    return payload


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run baseline SFT/QLoRA training and export model package artifacts."
        )
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    config = load_config(args.config)
    summary = _run_training(config)
    print(_json_dump(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
