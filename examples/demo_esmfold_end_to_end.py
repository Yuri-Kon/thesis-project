#!/usr/bin/env python
"""
ESMFold 远程调用 + HITL + 恢复演示

演示链路:
  Planner → WAITING_PLAN_CONFIRM → (恢复) → 决策 → Executor(远程 ESMFold) → Summarizer

使用方法:
  python examples/demo_esmfold_end_to_end.py --mode mock
  python examples/demo_esmfold_end_to_end.py --mode real --remote-url http://<host>:<port>

可选:
  --planner-provider <name>   使用 LLM Provider 生成计划（例如 nemotron）
  --provider-config <path>    Provider 配置文件路径
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path
from uuid import uuid4


def _check_dependencies() -> None:
    required = ("pydantic", "httpx")
    missing = [name for name in required if importlib.util.find_spec(name) is None]
    if not missing:
        return
    missing_list = ", ".join(missing)
    print(f"[ERROR] Missing Python dependencies: {missing_list}", file=sys.stderr)
    print("Install with:", file=sys.stderr)
    print("  python -m pip install -r requirements.txt", file=sys.stderr)
    raise SystemExit(1)


# 添加项目根目录到 Python 路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

_check_dependencies()

from src.adapters.registry import ADAPTER_REGISTRY, register_adapter
from src.adapters.remote_esmfold_adapter import RemoteESMFoldAdapter
from src.agents.executor import ExecutorAgent
from src.agents.planner import PlannerAgent, ToolSpec
from src.agents.summarizer import SummarizerAgent
from src.engines.remote_model_service import (
    JobStatus,
    RemoteModelInvocationService,
    RESTModelInvocationService,
)
from src.llm.provider_registry import create_provider, load_provider_catalog
from src.models.contracts import (
    Decision,
    DecisionChoice,
    PendingActionCandidate,
    PendingActionType,
    ProteinDesignTask,
    now_iso,
)
from src.models.db import ExternalStatus, InternalStatus, TaskRecord
from src.workflow.context import WorkflowContext
from src.workflow.decision_apply import apply_plan_confirm_decision
from src.workflow.pending_action import build_pending_action, enter_waiting_state
from src.workflow.recovery import recover_context_with_event_logs
from src.workflow.snapshots import default_snapshot_writer
from src.workflow.status import transition_task_status


class MockRemoteModelService(RemoteModelInvocationService):
    """用于演示的远程服务模拟器（无需 GPU）。"""

    def __init__(self) -> None:
        self.base_url = "mock://esmfold"
        self._jobs: dict[str, dict] = {}

    def submit_job(self, payload, task_id, step_id):
        job_id = f"mock_{uuid4().hex[:8]}"
        self._jobs[job_id] = {
            "task_id": task_id,
            "step_id": step_id,
            "sequence": payload.get("sequence", ""),
        }
        return job_id

    def poll_status(self, job_id):
        return JobStatus.COMPLETED

    def wait_for_completion(self, job_id):
        return JobStatus.COMPLETED

    def download_results(self, job_id, output_dir):
        job = self._jobs.get(job_id, {})
        sequence = job.get("sequence", "")
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        pdb_path = output_dir / f"{job_id}.pdb"
        pdb_content = "\n".join(
            [
                "HEADER    MOCK STRUCTURE",
                f"TITLE     MOCK ESMFOLD PREDICTION FOR {job_id}",
                f"REMARK    Sequence length: {len(sequence)}",
                "ATOM      1  N   MET A   1      10.000  10.000  10.000  1.00 85.00           N",
                "END",
            ]
        )
        pdb_path.write_text(pdb_content, encoding="utf-8")

        mock_plddt = min(0.95, 0.60 + (len(sequence) / 500) * 0.20) if sequence else 0.75
        outputs = {
            "pdb_path": str(pdb_path),
            "metrics": {
                "tool": "esmfold",
                "plddt_mean": round(mock_plddt, 2),
                "confidence": "high" if mock_plddt > 0.80 else "medium",
            },
        }
        return outputs


def _reset_adapter_registry() -> None:
    ADAPTER_REGISTRY._by_tool_id.clear()
    ADAPTER_REGISTRY._by_adapter_id.clear()


def _save_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def _build_planner(tool_registry: list[ToolSpec], provider_name: str | None, provider_config: Path) -> PlannerAgent:
    if not provider_name or provider_name.lower() == "none":
        return PlannerAgent(tool_registry=tool_registry)

    catalog = load_provider_catalog(provider_config)
    settings = catalog.providers.get(provider_name)
    if settings is None:
        raise ValueError(f"Unknown planner provider: {provider_name}")

    provider = create_provider(settings)
    return PlannerAgent(tool_registry=tool_registry, llm_provider=provider)


def _build_service(mode: str, remote_url: str | None) -> RemoteModelInvocationService:
    if mode == "mock":
        return MockRemoteModelService()
    resolved_url = remote_url or os.getenv("ESMFOLD_API_URL")
    if not resolved_url:
        raise ValueError("Real mode requires --remote-url or ESMFOLD_API_URL")
    return RESTModelInvocationService(resolved_url)


def run_demo(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    task_id = args.task_id or f"demo_{uuid4().hex[:8]}"
    task = ProteinDesignTask(
        task_id=task_id,
        goal="Predict structure with remote ESMFold and recover from HITL",
        constraints={
            "sequence": args.sequence,
            "method": "esmfold",
        },
        metadata={"demo": True, "mode": args.mode},
    )

    record = TaskRecord(
        id=task_id,
        status=ExternalStatus.CREATED,
        internal_status=InternalStatus.CREATED,
        created_at=now_iso(),
        updated_at=now_iso(),
        goal=task.goal,
        constraints=task.constraints,
        metadata=task.metadata,
        plan=None,
        design_result=None,
        safety_events=[],
    )

    context = WorkflowContext(
        task=task,
        plan=None,
        step_results={},
        safety_events=[],
        design_result=None,
        status=InternalStatus.CREATED,
    )

    service = _build_service(args.mode, args.remote_url)
    adapter = RemoteESMFoldAdapter(
        service=service,
        output_dir=output_dir / "remote",
        snapshot_writer=default_snapshot_writer,
        enable_snapshot=True,
    )
    _reset_adapter_registry()
    register_adapter(adapter)

    tool_registry = [
        ToolSpec(
            id="esmfold",
            capabilities=("structure_prediction",),
            inputs=("sequence",),
            outputs=("pdb_path", "metrics"),
            cost=5,
            safety_level=1,
        )
    ]
    planner = _build_planner(tool_registry, args.planner_provider, args.provider_config)
    executor = ExecutorAgent()
    summarizer = SummarizerAgent()

    print("[1] 规划阶段")
    transition_task_status(context, record, InternalStatus.PLANNING, reason="demo_planning")
    plan = planner.plan(task)
    if isinstance(plan.metadata, dict):
        plan.metadata.setdefault("plan_version", 0)
    context.plan = plan
    record.plan = plan

    candidate = PendingActionCandidate(
        candidate_id="candidate_plan_1",
        payload=plan,
        summary="remote esmfold plan",
    )
    pending_action = build_pending_action(
        task_id=task.task_id,
        action_type=PendingActionType.PLAN_CONFIRM,
        candidates=[candidate],
        default_suggestion=candidate.candidate_id,
        explanation="demo plan confirmation",
    )
    enter_waiting_state(
        context,
        record,
        pending_action,
        InternalStatus.WAITING_PLAN_CONFIRM,
        reason="demo_waiting_plan_confirm",
    )
    transition_task_status(
        context,
        record,
        InternalStatus.WAITING_PLAN_CONFIRM,
        reason="demo_waiting_plan_confirm",
    )

    _save_json(output_dir / "task.json", task.model_dump())
    _save_json(output_dir / "plan.json", plan.model_dump())
    _save_json(output_dir / "pending_action.json", pending_action.model_dump())

    print("[2] 模拟重启并恢复")
    recovered = recover_context_with_event_logs(task=task, plan=plan)
    if recovered is None:
        raise RuntimeError("Recovery failed: no snapshot/event logs")

    _save_json(
        output_dir / "recovery.json",
        {
            "status": recovered.context.status.value,
            "resume_from_existing": recovered.resume_from_existing,
            "applied_events": [e.model_dump() for e in recovered.applied_event_logs],
        },
    )

    print("[3] 应用人工决策")
    decision = Decision(
        decision_id=f"decision_{uuid4().hex[:8]}",
        task_id=task.task_id,
        pending_action_id=pending_action.pending_action_id,
        choice=DecisionChoice.ACCEPT,
        selected_candidate_id=candidate.candidate_id,
        decided_by="demo_user",
    )
    apply_plan_confirm_decision(recovered.context, record, decision)

    print("[4] 执行远程 ESMFold")
    executor.run_plan(
        recovered.context.plan or plan,
        recovered.context,
        record=record,
        finalize_status=False,
        resume_from_existing=recovered.resume_from_existing,
    )

    print("[5] 汇总并完成")
    executor.summarize_and_finalize(recovered.context, record, summarizer)

    _save_json(output_dir / "step_results.json", {
        step_id: result.model_dump()
        for step_id, result in recovered.context.step_results.items()
    })
    _save_json(output_dir / "design_result.json", record.design_result.model_dump())
    _save_json(output_dir / "task_record.json", record.model_dump())

    print("\n=== 演示完成 ===")
    print(f"Task ID: {task_id}")
    print(f"Status: {record.status.value}")
    print(f"Output dir: {output_dir}")
    print("Artifacts:")
    for name in (
        "task.json",
        "plan.json",
        "pending_action.json",
        "recovery.json",
        "step_results.json",
        "design_result.json",
        "task_record.json",
    ):
        print(f"  - {output_dir / name}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="ESMFold remote + HITL recovery demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--mode",
        choices=["mock", "real"],
        default="mock",
        help="远程执行模式: mock 或 real",
    )
    parser.add_argument(
        "--remote-url",
        default=None,
        help="真实模式下远程服务地址 (或设置 ESMFOLD_API_URL)",
    )
    parser.add_argument(
        "--sequence",
        default="MKFLKFSLLTAVLLSVVFAFSSCGDDDDTGYLPPSQAIQDLLKRMKV",
        help="输入序列 (FASTA string)",
    )
    parser.add_argument(
        "--output-dir",
        default=str(PROJECT_ROOT / "demo_output"),
        help="输出目录",
    )
    parser.add_argument(
        "--task-id",
        default=None,
        help="自定义 task_id（默认自动生成）",
    )
    parser.add_argument(
        "--planner-provider",
        default="none",
        help="Planner provider name (configs/llm_providers.json)，或 'none' 使用内置 Planner",
    )
    parser.add_argument(
        "--provider-config",
        type=Path,
        default=PROJECT_ROOT / "configs" / "llm_providers.json",
        help="Provider 配置文件路径",
    )

    args = parser.parse_args()
    try:
        return run_demo(args)
    except Exception as exc:
        print(f"\n[ERROR] {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
