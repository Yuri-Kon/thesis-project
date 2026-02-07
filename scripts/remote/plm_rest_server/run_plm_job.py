from __future__ import annotations

import argparse
import hashlib
import json
import random
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List


AMINO_ACIDS = "ACDEFGHIKLMNPQRSTVWY"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def _normalize_length_range(value: Any) -> tuple[int, int]:
    if isinstance(value, (list, tuple)) and len(value) == 2:
        min_len = max(1, int(value[0]))
        max_len = max(min_len, int(value[1]))
        return min_len, max_len
    return (60, 120)


def _normalize_positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(parsed, 1)


def _seed_rng(*parts: str) -> random.Random:
    text = "|".join(parts)
    seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16) % (2**32)
    return random.Random(seed)


def _generate_candidates(
    rng: random.Random,
    *,
    min_len: int,
    max_len: int,
    num_candidates: int,
) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    for _ in range(num_candidates):
        seq_len = rng.randint(min_len, max_len)
        sequence = "".join(rng.choice(AMINO_ACIDS) for _ in range(seq_len))
        score = round(rng.uniform(0.5, 0.99), 4)
        candidates.append(
            {
                "sequence": sequence,
                "score": score,
            }
        )
    return candidates


def _write_artifacts(
    *,
    job_dir: Path,
    job_id: str,
    task_id: str,
    step_id: str,
    candidates: List[Dict[str, Any]],
) -> None:
    artifact_dir = job_dir / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    fasta_path = artifact_dir / "candidates.fasta"
    with fasta_path.open("w", encoding="utf-8") as handle:
        for idx, item in enumerate(candidates, start=1):
            handle.write(f">{job_id}_candidate_{idx}\n")
            handle.write(f"{item['sequence']}\n")

    summary_path = artifact_dir / "summary.json"
    summary = {
        "job_id": job_id,
        "task_id": task_id,
        "step_id": step_id,
        "num_candidates": len(candidates),
        "top_score": max(item["score"] for item in candidates),
    }
    _write_json(summary_path, summary)


def run_plm_job(
    *,
    job_id: str,
    job_dir: Path,
    input_payload: Dict[str, Any],
) -> Dict[str, Any]:
    status_path = job_dir / "status.json"
    outputs_path = job_dir / "outputs.json"
    job_dir.mkdir(parents=True, exist_ok=True)

    task_id = str(input_payload.get("task_id", "unknown"))
    step_id = str(input_payload.get("step_id", "unknown"))
    inputs = input_payload.get("inputs", {})
    if not isinstance(inputs, dict):
        inputs = {}

    _write_json(
        status_path,
        {
            "job_id": job_id,
            "status": "running",
            "updated_at": _now_iso(),
        },
    )

    try:
        if bool(inputs.get("force_fail", False)):
            raise RuntimeError("force_fail requested by input payload")

        length_range = _normalize_length_range(inputs.get("length_range"))
        num_candidates = _normalize_positive_int(inputs.get("num_candidates"), 4)
        goal = str(inputs.get("goal", ""))
        prompt = str(inputs.get("prompt", ""))
        rng = _seed_rng(job_id, task_id, step_id, goal, prompt)

        candidates = _generate_candidates(
            rng,
            min_len=length_range[0],
            max_len=length_range[1],
            num_candidates=num_candidates,
        )
        selected = max(candidates, key=lambda item: item["score"])

        _write_artifacts(
            job_dir=job_dir,
            job_id=job_id,
            task_id=task_id,
            step_id=step_id,
            candidates=candidates,
        )

        outputs = {
            "sequence": selected["sequence"],
            "candidates": candidates,
            "artifacts": {
                "fasta_path": "candidates.fasta",
                "summary_path": "summary.json",
            },
        }
        _write_json(outputs_path, outputs)
        _write_json(
            status_path,
            {
                "job_id": job_id,
                "status": "completed",
                "updated_at": _now_iso(),
            },
        )
        return outputs

    except Exception as exc:
        failure = {
            "code": "REMOTE_JOB_FAILED",
            "message": str(exc),
            "failure_type": "tool_error",
            "retryable": False,
        }
        _write_json(
            status_path,
            {
                "job_id": job_id,
                "status": "failed",
                "updated_at": _now_iso(),
                "failure": failure,
            },
        )
        return {"failure": failure}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a PLM job (stub implementation)")
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--job-dir", required=True)
    parser.add_argument("--input-json", required=True)
    args = parser.parse_args()

    job_dir = Path(args.job_dir)
    input_json = Path(args.input_json)
    payload = json.loads(input_json.read_text(encoding="utf-8"))
    run_plm_job(job_id=args.job_id, job_dir=job_dir, input_payload=payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
