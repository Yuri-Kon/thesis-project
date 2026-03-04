#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.infra.runtime_init import RuntimeInitResult, initialize_runtime
from src.kg.kg_client import ToolKGError

TERMINAL_STATUSES = {"DONE", "FAILED", "CANCELLED"}
WAITING_STATUSES = {
    "WAITING_PLAN_CONFIRM",
    "WAITING_PATCH_CONFIRM",
    "WAITING_REPLAN_CONFIRM",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="One-command demo launcher (API + workflow smoke check)."
    )
    parser.add_argument("--host", default="127.0.0.1", help="FastAPI bind host")
    parser.add_argument("--port", type=int, default=8000, help="FastAPI bind port")
    parser.add_argument(
        "--app",
        default="src.api.main:app",
        help="ASGI app import path for uvicorn",
    )
    parser.add_argument(
        "--model-backend",
        default="mock",
        help="Model backend label for demo metadata (mock/real/etc.)",
    )
    parser.add_argument(
        "--mock-tools",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Toggle mock tool mode flag for demo runtime",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="Data directory root (contains logs/snapshots)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Output directory root",
    )
    parser.add_argument(
        "--kg-path",
        type=Path,
        default=Path("src/kg/protein_tool_kg.json"),
        help="ProteinToolKG file path",
    )
    parser.add_argument(
        "--smoke-test",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Run API smoke check after server startup",
    )
    parser.add_argument(
        "--smoke-timeout",
        type=float,
        default=20.0,
        help="Timeout seconds for smoke task polling",
    )
    parser.add_argument(
        "--startup-timeout",
        type=float,
        default=20.0,
        help="Timeout seconds waiting for /health to become ready",
    )
    parser.add_argument(
        "--smoke-task-config",
        type=Path,
        default=Path("configs/demo_task.json"),
        help="JSON file used by smoke test POST /tasks payload",
    )
    parser.add_argument(
        "--check-nextflow",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Warn when Nextflow is unavailable",
    )
    parser.add_argument(
        "--exit-after-smoke",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Exit immediately after smoke test passes",
    )
    return parser.parse_args()


def require_python_312() -> None:
    if sys.version_info < (3, 12):
        version = ".".join(str(x) for x in sys.version_info[:3])
        raise RuntimeError(
            f"Python 3.12+ is required, current version is {version}. "
            "Use `uv python install 3.12` and rerun."
        )


def require_command(name: str) -> None:
    if shutil.which(name) is None:
        raise RuntimeError(f"Required command not found: {name}")


def maybe_warn_nextflow(enabled: bool) -> None:
    if not enabled:
        return
    if shutil.which("nextflow") is None:
        print("[WARN] nextflow not found, demo will run without Nextflow integration.")


def load_smoke_payload(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise RuntimeError(f"Smoke task config not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Smoke task config is invalid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Smoke task config must be a JSON object")
    if "goal" not in payload:
        raise RuntimeError("Smoke task config must include `goal`")
    payload.setdefault("constraints", {})
    payload.setdefault("metadata", {})
    return payload


def wait_for_health(base_url: str, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    last_error: str | None = None
    with httpx.Client(timeout=2.0) as client:
        while time.monotonic() < deadline:
            try:
                response = client.get(f"{base_url}/health")
                if response.status_code == 200:
                    return
                last_error = f"HTTP {response.status_code}"
            except Exception as exc:  # pragma: no cover - best effort diagnostics
                last_error = str(exc)
            time.sleep(0.4)
    raise RuntimeError(
        f"API did not become healthy within {timeout:.1f}s (last error: {last_error})"
    )


def run_smoke(base_url: str, payload: dict[str, Any], timeout: float, data_dir: Path) -> None:
    request_timeout = max(10.0, timeout)
    with httpx.Client(timeout=httpx.Timeout(request_timeout, connect=5.0)) as client:
        health = client.get(f"{base_url}/health")
        if health.status_code != 200:
            raise RuntimeError(f"GET /health failed: {health.status_code}")

        create = client.post(f"{base_url}/tasks", json=payload)
        if create.status_code != 200:
            raise RuntimeError(
                f"POST /tasks failed: {create.status_code} {create.text.strip()}"
            )
        create_data = create.json()
        task_id = create_data.get("id")
        if not task_id:
            raise RuntimeError("POST /tasks response missing task id")

        seen_status: list[str] = []
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            detail = client.get(f"{base_url}/tasks/{task_id}")
            if detail.status_code != 200:
                raise RuntimeError(f"GET /tasks/{task_id} failed: {detail.status_code}")
            task = detail.json()
            status = str(task.get("status"))
            if not seen_status or seen_status[-1] != status:
                seen_status.append(status)
            if status in TERMINAL_STATUSES or status in WAITING_STATUSES:
                break
            time.sleep(0.5)

        if not seen_status:
            raise RuntimeError("No task status observed during smoke test")

        if seen_status[-1] not in TERMINAL_STATUSES and seen_status[-1] not in WAITING_STATUSES:
            raise RuntimeError(
                "Task status did not reach terminal/waiting state within timeout; "
                f"last status={seen_status[-1]}"
            )

        log_file = data_dir / "logs" / f"{task_id}.jsonl"
        if not log_file.exists():
            raise RuntimeError(
                f"Expected EventLog file was not created: {log_file}"
            )

        print(f"[SMOKE] task_id={task_id}")
        print(f"[SMOKE] statuses={seen_status}")
        print(f"[SMOKE] event_log={log_file}")


def start_server(args: argparse.Namespace) -> tuple[subprocess.Popen[Any], str]:
    env = os.environ.copy()
    env["PROTEIN_DATA_DIR"] = str(args.data_dir)
    env["PROTEIN_LOG_DIR"] = str(args.data_dir / "logs")
    env["PROTEIN_SNAPSHOT_DIR"] = str(args.data_dir / "snapshots")
    env["PROTEIN_OUTPUT_DIR"] = str(args.output_dir)
    env["PROTEIN_KG_PATH"] = str(args.kg_path)
    env["PROTEIN_MODEL_BACKEND"] = args.model_backend
    env["PROTEIN_DEMO_MOCK_TOOLS"] = "1" if args.mock_tools else "0"

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        args.app,
        "--host",
        args.host,
        "--port",
        str(args.port),
    ]
    process: subprocess.Popen[Any] = subprocess.Popen(
        cmd,
        cwd=str(REPO_ROOT),
        env=env,
    )
    base_url = f"http://{args.host}:{args.port}"
    return process, base_url


def terminate_process(process: subprocess.Popen[Any]) -> None:
    if process.poll() is not None:
        return
    process.send_signal(signal.SIGINT)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()


def describe_runtime(result: RuntimeInitResult) -> None:
    print(f"[INIT] kg={result.paths.kg_path} (tools={result.tool_count})")
    print(f"[INIT] output_dir={result.paths.output_dir}")
    print(f"[INIT] log_dir={result.paths.log_dir}")
    print(f"[INIT] snapshot_dir={result.paths.snapshot_dir}")


def main() -> int:
    args = parse_args()
    server: subprocess.Popen[Any] | None = None
    try:
        require_python_312()
        require_command("uv")
        maybe_warn_nextflow(args.check_nextflow)

        runtime = initialize_runtime(
            kg_path=args.kg_path,
            output_dir=args.output_dir,
            data_dir=args.data_dir,
            log_dir=args.data_dir / "logs",
            snapshot_dir=args.data_dir / "snapshots",
        )
        describe_runtime(runtime)

        payload = load_smoke_payload(args.smoke_task_config) if args.smoke_test else {}

        server, base_url = start_server(args)
        wait_for_health(base_url, args.startup_timeout)
        print(f"[READY] API docs: {base_url}/docs")
        print(f"[READY] Health:   {base_url}/health")

        if args.smoke_test:
            run_smoke(base_url, payload, args.smoke_timeout, args.data_dir)

        if args.exit_after_smoke:
            return 0

        print("[RUNNING] Press Ctrl+C to stop demo server.")
        while True:
            code = server.poll()
            if code is not None:
                return code
            time.sleep(0.6)
    except ToolKGError as exc:
        print(f"[ERROR] KG initialization failed: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    finally:
        if server is not None:
            terminate_process(server)


if __name__ == "__main__":
    raise SystemExit(main())
