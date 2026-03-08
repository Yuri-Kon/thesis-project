#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import httpx

from src.api.main import TASK_STORE, app
from src.models.contracts import (
    PendingAction,
    PendingActionCandidate,
    PendingActionStatus,
    PendingActionType,
    Plan,
    PlanPatch,
    PlanPatchOp,
    PlanStep,
)
from src.models.db import ExternalStatus, InternalStatus, TaskRecord


def _build_patch(task_id: str, step_tool: str) -> PlanPatch:
    return PlanPatch(
        task_id=task_id,
        operations=[
            PlanPatchOp(
                op="replace_step",
                target="S2",
                step=PlanStep(id="S2", tool=step_tool, inputs={"num_candidates": 3}),
            )
        ],
        metadata={"source": "demo_issue_142"},
    )


def seed_demo_task() -> tuple[str, str]:
    task_id = "task_demo_142"
    pending_action_id = "pa_demo_142"

    TASK_STORE.clear()
    current_plan = Plan(
        task_id=task_id,
        steps=[
            PlanStep(id="S1", tool="proteinmpnn", inputs={"sequence": "MKTAYIAKQ"}),
            PlanStep(id="S2", tool="nim_esmfold", inputs={"sequence_ref": "S1.sequence"}),
        ],
        constraints={"length_range": [20, 80]},
        metadata={"demo": True},
    )

    candidates = [
        PendingActionCandidate(
            candidate_id="patch_remote_best",
            payload=_build_patch(task_id, "nim_esmfold"),
            summary="Remote ESMFold candidate with best overall score.",
            explanation="Highest objective score and acceptable risk/cost profile.",
            risk_level="low",
            cost_estimate="medium",
            score_breakdown={
                "feasibility": 0.86,
                "objective": 0.90,
                "risk": 0.82,
                "cost": 0.68,
                "overall": 0.84,
            },
            tool_id="nim_esmfold",
            capability_id="structure_prediction",
            io_type="sequence_to_structure",
            adapter_mode="remote",
            metadata={"fallback_tool_id": "openfold"},
        ),
        PendingActionCandidate(
            candidate_id="patch_local_safe",
            payload=_build_patch(task_id, "openfold"),
            summary="Local OpenFold candidate for stable local execution.",
            explanation="Lower operational risk and easy fallback to local runtime.",
            risk_level="low",
            cost_estimate="low",
            score_breakdown={
                "feasibility": 0.80,
                "objective": 0.77,
                "risk": 0.88,
                "cost": 0.90,
                "overall": 0.81,
            },
            tool_id="openfold",
            capability_id="structure_prediction",
            io_type="sequence_to_structure",
            adapter_mode="local",
        ),
        PendingActionCandidate(
            candidate_id="patch_metadata_missing",
            payload=_build_patch(task_id, "unknown_tool"),
            summary="Candidate with missing tool metadata for degraded UI path.",
            explanation="Used to verify UI/API fallback display when tool fields are absent.",
            risk_level="medium",
            cost_estimate="high",
            score_breakdown={
                "feasibility": 0.65,
                "objective": 0.60,
                "risk": 0.45,
                "cost": 0.30,
                "overall": 0.50,
            },
        ),
    ]

    pending_action = PendingAction(
        pending_action_id=pending_action_id,
        task_id=task_id,
        action_type=PendingActionType.PATCH_CONFIRM,
        status=PendingActionStatus.PENDING,
        candidates=candidates,
        default_recommendation="patch_remote_best",
        explanation=(
            "Compare patch candidates and choose one based on risk/cost/tool "
            "availability before resuming execution."
        ),
    )

    TASK_STORE[task_id] = TaskRecord(
        id=task_id,
        status=ExternalStatus.WAITING_PATCH_CONFIRM,
        internal_status=InternalStatus.WAITING_PATCH,
        goal="Demo for issue #142 candidate compare + HITL decision",
        constraints={"sequence": "MKTAYIAKQ"},
        metadata={"demo": "issue_142"},
        plan=current_plan,
        design_result=None,
        pending_action=pending_action,
    )
    return task_id, pending_action_id


async def run_in_process_preview(task_id: str, pending_action_id: str) -> int:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://demo.local") as client:
        pending_resp = await client.get("/pending-actions")
        detail_resp = await client.get(f"/pending-actions/{pending_action_id}")

        print("[preview] GET /pending-actions")
        print(
            json.dumps(
                pending_resp.json(),
                ensure_ascii=False,
                indent=2,
            )
        )
        print()
        print(f"[preview] GET /pending-actions/{pending_action_id}")
        print(
            json.dumps(
                detail_resp.json(),
                ensure_ascii=False,
                indent=2,
            )
        )

        if pending_resp.status_code != 200 or detail_resp.status_code != 200:
            return 1
    print()
    print("[preview] success: in-process API example is reproducible.")
    print("[preview] use --serve to run a real HTTP server for UI inspection.")
    print(f"[preview] target UI path: /ui/tasks/{task_id}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run API with seeded HITL candidate-comparison demo data."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8012)
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Start uvicorn server for manual browser inspection.",
    )
    args = parser.parse_args()

    task_id, pending_action_id = seed_demo_task()
    base_url = f"http://{args.host}:{args.port}"
    print(f"[demo] seeded task_id={task_id}")
    print(f"[demo] seeded pending_action_id={pending_action_id}")
    print(f"[demo] dashboard: {base_url}/ui/tasks/{task_id}")
    print(f"[demo] pending detail API: {base_url}/pending-actions/{pending_action_id}")
    print(f"[demo] timeline: {base_url}/ui/tasks/{task_id}/events")

    if not args.serve:
        return asyncio.run(run_in_process_preview(task_id, pending_action_id))

    try:
        import uvicorn
    except ModuleNotFoundError:
        print("[error] uvicorn is required for --serve mode.")
        return 2

    uvicorn.run(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
