from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

AMINO_ACIDS = set("ACDEFGHIKLMNPQRSTVWY")
DEFAULT_MODEL_DIR = "/root/autodl-tmp/models/plm/ProtGPT2"


@dataclass(frozen=True)
class GenerationConfig:
    model_dir: str = DEFAULT_MODEL_DIR
    prompt: str = "<|endoftext|>"
    max_new_tokens: int = 128
    num_return_sequences: int = 4
    top_k: int = 950
    top_p: float = 1.0
    temperature: float = 1.0
    repetition_penalty: float = 1.2
    do_sample: bool = True
    eos_token_id: int = 0


def _safe_int(value: Any, default: int, minimum: int = 1) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(parsed, minimum)


def _safe_float(value: Any, default: float, minimum: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return max(parsed, minimum)


def normalize_config(inputs: Dict[str, Any], *, model_dir: str) -> GenerationConfig:
    num_return_sequences = _safe_int(
        inputs.get("num_return_sequences", inputs.get("num_candidates", 4)),
        default=4,
        minimum=1,
    )
    return GenerationConfig(
        model_dir=str(inputs.get("model_dir") or model_dir),
        prompt=str(inputs.get("prompt", "<|endoftext|>")),
        max_new_tokens=_safe_int(inputs.get("max_new_tokens", 128), default=128, minimum=1),
        num_return_sequences=num_return_sequences,
        top_k=_safe_int(inputs.get("top_k", 950), default=950, minimum=1),
        top_p=_safe_float(inputs.get("top_p", 1.0), default=1.0, minimum=0.0),
        temperature=_safe_float(inputs.get("temperature", 1.0), default=1.0, minimum=0.01),
        repetition_penalty=_safe_float(inputs.get("repetition_penalty", 1.2), default=1.2, minimum=0.01),
        do_sample=bool(inputs.get("do_sample", True)),
        eos_token_id=_safe_int(inputs.get("eos_token_id", 0), default=0, minimum=0),
    )


def _sanitize_sequence(text: str) -> str:
    filtered = [ch for ch in text.upper() if ch in AMINO_ACIDS]
    return "".join(filtered)


def _compute_avg_log_probs(step_scores, seq_ids, input_len, candidate_idx: int):
    import torch
    import torch.nn.functional as F

    gen_token_ids = seq_ids[input_len:]
    if len(gen_token_ids) == 0:
        return float("-inf")

    log_probs: List[float] = []
    for t, scores_t in enumerate(step_scores):
        if t >= len(gen_token_ids):
            break
        probs_t = F.log_softmax(scores_t[candidate_idx], dim=-1)
        token_id = gen_token_ids[t]
        log_probs.append(float(probs_t[token_id].item()))

    if not log_probs:
        return float("-inf")
    return sum(log_probs) / len(log_probs)


def _load_model_and_tokenizer(model_dir: str):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    if torch.cuda.is_available():
        try:
            model = AutoModelForCausalLM.from_pretrained(
                model_dir,
                torch_dtype=torch.float16,
                low_cpu_mem_usage=True,
            ).to("cuda")
            return tokenizer, model, "cuda"
        except torch.cuda.OutOfMemoryError:
            torch.cuda.empty_cache()

    model = AutoModelForCausalLM.from_pretrained(model_dir)
    return tokenizer, model, "cpu"


def generate_with_protgpt2(inputs: Dict[str, Any], *, model_dir: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    import torch

    cfg = normalize_config(inputs, model_dir=model_dir)
    tokenizer, model, device = _load_model_and_tokenizer(cfg.model_dir)
    model.eval()

    encoded = tokenizer(cfg.prompt, return_tensors="pt")
    encoded = {k: v.to(device) for k, v in encoded.items()}
    input_len = int(encoded["input_ids"].shape[1])

    with torch.no_grad():
        outputs = model.generate(
            **encoded,
            do_sample=cfg.do_sample,
            top_k=cfg.top_k,
            top_p=cfg.top_p,
            temperature=cfg.temperature,
            repetition_penalty=cfg.repetition_penalty,
            max_new_tokens=cfg.max_new_tokens,
            num_return_sequences=cfg.num_return_sequences,
            eos_token_id=cfg.eos_token_id,
            return_dict_in_generate=True,
            output_scores=True,
        )

    candidates: List[Dict[str, Any]] = []
    for i in range(cfg.num_return_sequences):
        seq_ids = outputs.sequences[i]
        decoded = tokenizer.decode(seq_ids, skip_special_tokens=True)
        aa_sequence = _sanitize_sequence(decoded)
        score = _compute_avg_log_probs(outputs.scores, seq_ids, input_len, i)
        candidates.append(
            {
                "sequence": aa_sequence,
                "score": round(score, 6),
                "raw_text": decoded,
            }
        )

    candidates.sort(key=lambda x: x["score"], reverse=True)
    best = candidates[0] if candidates else {"sequence": "", "score": float("-inf")}

    outputs_payload = {
        "sequence": best["sequence"],
        "candidates": [{"sequence": c["sequence"], "score": c["score"]} for c in candidates],
        "device_used": device,
    }
    metrics = {
        "num_candidates": len(candidates),
        "device_used": device,
        "prompt_length": input_len,
        "max_new_tokens": cfg.max_new_tokens,
        "model_dir": cfg.model_dir,
    }
    return outputs_payload, metrics


def write_artifacts(job_dir: Path, *, outputs_payload: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, str]:
    artifact_dir = job_dir / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    fasta_path = artifact_dir / "candidates.fasta"
    with fasta_path.open("w", encoding="utf-8") as handle:
        for idx, item in enumerate(outputs_payload.get("candidates", []), start=1):
            handle.write(f">candidate_{idx} score={item.get('score')}\n")
            handle.write(f"{item.get('sequence', '')}\n")

    summary_path = artifact_dir / "summary.json"
    summary_path.write_text(json.dumps(metadata, ensure_ascii=True, indent=2), encoding="utf-8")

    return {
        "fasta_path": fasta_path.name,
        "summary_path": summary_path.name,
    }
