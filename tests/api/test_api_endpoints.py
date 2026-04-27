"""API端点测试"""
import json

import pytest
import httpx

from src.api.main import app, TASK_STORE
from src.models.contracts import (
    DecisionChoice,
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
from src.storage.log_store import DEFAULT_LOG_DIR


@pytest.mark.api
@pytest.mark.anyio
class TestAPIEndpoints:
    """API端点测试类"""

    @pytest.fixture(autouse=True)
    def disable_catalog_provider_autoload(self, monkeypatch):
        monkeypatch.setenv("PLANNER_LLM_PROVIDER", "off")
        for env_name in (
            "OPENAI_API_KEY",
            "DASHSCOPE_API_KEY",
            "DEEPSEEK_API_KEY",
            "ZHIPU_API_KEY",
            "NIM_API_KEY",
        ):
            monkeypatch.delenv(env_name, raising=False)

    @pytest.fixture
    def anyio_backend(self):
        return "asyncio"

    @pytest.fixture
    async def client(self):
        """创建测试客户端"""
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            yield client

    @pytest.fixture(autouse=True)
    def clear_task_store(self):
        TASK_STORE.clear()
        if DEFAULT_LOG_DIR.exists():
            for path in DEFAULT_LOG_DIR.glob("test_api_events_*.jsonl"):
                path.unlink()
        yield
        TASK_STORE.clear()
        if DEFAULT_LOG_DIR.exists():
            for path in DEFAULT_LOG_DIR.glob("test_api_events_*.jsonl"):
                path.unlink()

    async def test_create_task_endpoint(self, client: httpx.AsyncClient):
        """测试创建任务端点"""
        response = await client.post(
            "/tasks",
            json={
                "goal": "设计一个测试蛋白质",
                "constraints": {"sequence": "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQLR"},
                "metadata": {"test": True},
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["goal"] == "设计一个测试蛋白质"
        assert data["status"] == ExternalStatus.DONE.value

    async def test_health_endpoint(self, client: httpx.AsyncClient):
        """测试健康检查端点"""
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "kg_tool_count" in data
        assert "capability_readiness_count" in data
        assert "paths" in data
        assert "logs" in data["paths"]

    async def test_capability_readiness_endpoint(self, client: httpx.AsyncClient):
        response = await client.get("/capabilities/readiness")

        assert response.status_code == 200
        data = response.json()
        assert any(item["capability_id"] == "objective_scoring" for item in data)
        objective_entry = next(
            item for item in data if item["capability_id"] == "objective_scoring"
        )
        assert objective_entry["primary_tool_id"] == "objective_ranker"
        assert "available_tools" in objective_entry
        assert "blocked_tools" in objective_entry
        assert "degraded_reasons" in objective_entry
        assert "suggested_recovery" in objective_entry

    async def test_create_task_with_minimal_data(self, client: httpx.AsyncClient):
        """测试使用最少数据创建任务"""
        response = await client.post(
            "/tasks",
            json={"goal": "最小任务"},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["goal"] == "最小任务"
        assert "id" in data

    async def test_create_task_with_custom_constraints(self, client: httpx.AsyncClient):
        """测试使用自定义约束创建任务"""
        response = await client.post(
            "/tasks",
            json={
                "goal": "自定义约束任务",
                "constraints": {
                    "length_range": [40, 60],
                    "sequence": "ACDEFGHIKLMNPQRSTVWY",
                },
                "metadata": {"priority": "high"},
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["constraints"]["length_range"] == [40, 60]
        assert data["metadata"]["priority"] == "high"

    async def test_get_task_endpoint_success(self, client: httpx.AsyncClient):
        """测试获取任务端点成功"""
        # 先创建一个任务
        create_response = await client.post(
            "/tasks",
            json={"goal": "测试获取任务"},
        )
        assert create_response.status_code == 200
        task_id = create_response.json()["id"]
        
        # 获取任务
        get_response = await client.get(f"/tasks/{task_id}")
        
        assert get_response.status_code == 200
        data = get_response.json()
        assert data["id"] == task_id
        assert data["goal"] == "测试获取任务"

    async def test_get_task_endpoint_not_found(self, client: httpx.AsyncClient):
        """测试获取不存在的任务"""
        response = await client.get("/tasks/nonexistent_task_id")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    async def test_create_task_generates_unique_ids(self, client: httpx.AsyncClient):
        """测试创建任务生成唯一ID"""
        response1 = await client.post("/tasks", json={"goal": "任务1"})
        response2 = await client.post("/tasks", json={"goal": "任务2"})
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        task_id1 = response1.json()["id"]
        task_id2 = response2.json()["id"]
        
        assert task_id1 != task_id2

    async def test_create_task_returns_complete_record(self, client: httpx.AsyncClient):
        """测试创建任务返回完整记录"""
        response = await client.post(
            "/tasks",
            json={
                "goal": "完整记录测试",
                "constraints": {"test": "value"},
                "metadata": {"meta": "data"},
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # 验证所有必需字段存在
        assert "id" in data
        assert "status" in data
        assert "created_at" in data
        assert "updated_at" in data
        assert "goal" in data
        assert "constraints" in data
        assert "metadata" in data
        assert "plan" in data
        assert "design_result" in data

    async def test_get_task_returns_same_data_as_create(self, client: httpx.AsyncClient):
        """测试获取任务返回与创建时相同的数据"""
        create_data = {
            "goal": "一致性测试",
            "constraints": {"key": "value"},
            "metadata": {"test": True},
        }
        
        create_response = await client.post("/tasks", json=create_data)
        assert create_response.status_code == 200
        task_id = create_response.json()["id"]
        
        get_response = await client.get(f"/tasks/{task_id}")
        assert get_response.status_code == 200
        
        created = create_response.json()
        retrieved = get_response.json()
        
        # 验证关键字段一致
        assert created["id"] == retrieved["id"]
        assert created["goal"] == retrieved["goal"]
        assert created["constraints"] == retrieved["constraints"]
        assert created["metadata"] == retrieved["metadata"]

    async def test_get_pending_actions_default_only_pending(
        self, client: httpx.AsyncClient
    ):
        """默认只返回 pending 状态的 PendingAction。"""
        pending_task_id = "task_pending_list_a"
        decided_task_id = "task_pending_list_b"

        pending_action = PendingAction(
            pending_action_id="pa_pending",
            task_id=pending_task_id,
            action_type=PendingActionType.PLAN_CONFIRM,
            status=PendingActionStatus.PENDING,
            candidates=[
                PendingActionCandidate(
                    candidate_id="plan_a",
                    payload=Plan(task_id=pending_task_id, steps=[], constraints={}, metadata={}),
                )
            ],
            default_suggestion="plan_a",
            explanation="please confirm initial plan",
        )
        decided_action = PendingAction(
            pending_action_id="pa_decided",
            task_id=decided_task_id,
            action_type=PendingActionType.PATCH_CONFIRM,
            status=PendingActionStatus.DECIDED,
            candidates=[
                PendingActionCandidate(
                    candidate_id="patch_a",
                    payload=PlanPatch(task_id=decided_task_id, operations=[], metadata={}),
                )
            ],
            explanation="already decided",
        )

        TASK_STORE[pending_task_id] = TaskRecord(
            id=pending_task_id,
            status=ExternalStatus.WAITING_PLAN_CONFIRM,
            internal_status=InternalStatus.WAITING_PLAN_CONFIRM,
            goal="pending task",
            constraints={},
            metadata={},
            plan=None,
            design_result=None,
            pending_action=pending_action,
        )
        TASK_STORE[decided_task_id] = TaskRecord(
            id=decided_task_id,
            status=ExternalStatus.WAITING_PATCH_CONFIRM,
            internal_status=InternalStatus.WAITING_PATCH,
            goal="decided task",
            constraints={},
            metadata={},
            plan=None,
            design_result=None,
            pending_action=decided_action,
        )

        response = await client.get("/pending-actions")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["pending_action_id"] == "pa_pending"
        assert data[0]["candidate_count"] == 1
        assert data[0]["default_suggestion"] == "plan_a"
        assert "plan_a" in data[0]["summary"]

    async def test_get_pending_actions_supports_status_and_task_filters(
        self, client: httpx.AsyncClient
    ):
        """支持按 status/task_id 过滤 pending action 列表。"""
        task_id = "task_pending_filter"
        action = PendingAction(
            pending_action_id="pa_filter",
            task_id=task_id,
            action_type=PendingActionType.REPLAN_CONFIRM,
            status=PendingActionStatus.DECIDED,
            candidates=[
                PendingActionCandidate(
                    candidate_id="replan_a",
                    payload=Plan(task_id=task_id, steps=[], constraints={}, metadata={}),
                )
            ],
            explanation="decided replan",
        )
        TASK_STORE[task_id] = TaskRecord(
            id=task_id,
            status=ExternalStatus.WAITING_REPLAN_CONFIRM,
            internal_status=InternalStatus.WAITING_REPLAN,
            goal="filter task",
            constraints={},
            metadata={},
            plan=None,
            design_result=None,
            pending_action=action,
        )

        response = await client.get(
            "/pending-actions",
            params={"status": PendingActionStatus.DECIDED.value, "task_id": task_id},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["pending_action_id"] == "pa_filter"
        assert data[0]["task_id"] == task_id

    async def test_get_pending_action_detail_returns_candidate_display_fields(
        self, client: httpx.AsyncClient
    ):
        """PendingAction 详情接口返回候选比较与工具展示字段。"""
        task_id = "task_pending_detail"
        pending_action_id = "pa_detail"

        plan = Plan(
            task_id=task_id,
            steps=[PlanStep(id="S1", tool="esmfold", inputs={}, metadata={})],
            constraints={},
            metadata={},
        )
        pending_action = PendingAction(
            pending_action_id=pending_action_id,
            task_id=task_id,
            action_type=PendingActionType.PLAN_CONFIRM,
            status=PendingActionStatus.PENDING,
            candidates=[
                PendingActionCandidate(
                    candidate_id="plan_remote_best",
                    payload=plan,
                    summary="remote candidate",
                    explanation="best overall score with fallback",
                    risk_level="low",
                    cost_estimate="medium",
                    score_breakdown={
                        "feasibility": 0.88,
                        "objective": 0.83,
                        "risk": 0.8,
                        "cost": 0.72,
                        "overall": 0.84,
                    },
                    tool_id="esmfold",
                    capability_id="structure_prediction",
                    io_type="sequence_to_structure",
                    adapter_mode="remote",
                    metadata={"fallback_tool_id": "openfold"},
                ),
                PendingActionCandidate(
                    candidate_id="plan_local_safe",
                    payload=plan,
                    summary="local candidate",
                    explanation="lower cost baseline",
                    risk_level="low",
                    cost_estimate="low",
                    score_breakdown={
                        "feasibility": 0.82,
                        "objective": 0.77,
                        "risk": 0.85,
                        "cost": 0.9,
                        "overall": 0.80,
                    },
                    tool_id="openfold",
                    capability_id="structure_prediction",
                    io_type="sequence_to_structure",
                    adapter_mode="local",
                ),
            ],
            default_recommendation="plan_remote_best",
            explanation="pick candidate with best overall quality",
        )
        TASK_STORE[task_id] = TaskRecord(
            id=task_id,
            status=ExternalStatus.WAITING_PLAN_CONFIRM,
            internal_status=InternalStatus.WAITING_PLAN_CONFIRM,
            goal="detail endpoint test",
            constraints={},
            metadata={},
            plan=None,
            design_result=None,
            pending_action=pending_action,
        )

        response = await client.get(f"/pending-actions/{pending_action_id}")
        assert response.status_code == 200
        data = response.json()

        assert data["pending_action_id"] == pending_action_id
        assert data["default_suggestion"] == "plan_remote_best"
        assert data["recommendation_summary"].startswith("default=plan_remote_best")
        assert len(data["candidates"]) == 2

        first = data["candidates"][0]
        assert first["rank"] == 1
        assert first["candidate_id"] == "plan_remote_best"
        assert first["is_default"] is True
        assert first["overall_score"] == pytest.approx(0.84)
        assert first["tool"]["source"] == "remote"
        assert first["tool"]["adapter_mode"] == "remote"
        assert first["tool"]["available"] is True
        assert first["tool"]["can_fallback"] is True
        assert "risk=low" in first["recommendation_reason"]

    async def test_get_pending_action_detail_degrades_when_tool_fields_missing(
        self, client: httpx.AsyncClient
    ):
        """工具字段缺失时，接口应返回降级提示，避免前端崩溃。"""
        task_id = "task_pending_detail_degraded"
        pending_action_id = "pa_detail_degraded"

        plan = Plan(
            task_id=task_id,
            steps=[PlanStep(id="S1", tool="unknown_tool", inputs={}, metadata={})],
            constraints={},
            metadata={},
        )
        pending_action = PendingAction(
            pending_action_id=pending_action_id,
            task_id=task_id,
            action_type=PendingActionType.PLAN_CONFIRM,
            status=PendingActionStatus.PENDING,
            candidates=[
                PendingActionCandidate(
                    candidate_id="plan_missing_tool_fields",
                    payload=plan,
                    summary="candidate with missing tool metadata",
                    explanation="used to verify degraded rendering",
                    risk_level="medium",
                    cost_estimate="high",
                    score_breakdown={
                        "feasibility": 0.7,
                        "objective": 0.68,
                        "risk": 0.45,
                        "cost": 0.35,
                        "overall": 0.56,
                    },
                )
            ],
            default_suggestion="plan_missing_tool_fields",
            explanation="fallback to degraded display",
        )
        TASK_STORE[task_id] = TaskRecord(
            id=task_id,
            status=ExternalStatus.WAITING_PLAN_CONFIRM,
            internal_status=InternalStatus.WAITING_PLAN_CONFIRM,
            goal="degraded endpoint test",
            constraints={},
            metadata={},
            plan=None,
            design_result=None,
            pending_action=pending_action,
        )

        response = await client.get(f"/pending-actions/{pending_action_id}")
        assert response.status_code == 200
        data = response.json()
        candidate = data["candidates"][0]

        assert candidate["tool"]["source"] == "unknown"
        assert candidate["tool"]["adapter_mode"] is None
        assert candidate["tool"]["available"] is False
        assert candidate["tool"]["can_fallback"] is False
        assert "Tool metadata missing" in candidate["tool"]["availability_hint"]
        assert "tool_source=unknown" in candidate["recommendation_reason"]

    async def test_ui_routes_and_static_assets_available(
        self, client: httpx.AsyncClient
    ):
        """前端 UI 页面和静态资源可访问。"""
        dashboard_response = await client.get("/ui")
        assert dashboard_response.status_code == 200
        assert "HITL PendingAction Dashboard" in dashboard_response.text
        assert "Candidate Comparison" in dashboard_response.text
        assert "Model Invocation" in dashboard_response.text
        assert "model-invocation-body" in dashboard_response.text

        task_view_response = await client.get("/ui/tasks/task_demo_001")
        assert task_view_response.status_code == 200
        assert "HITL PendingAction Dashboard" in task_view_response.text

        static_response = await client.get("/static/js/hitl-dashboard.js")
        assert static_response.status_code == 200
        assert "ALLOWED_CHOICES" in static_response.text
        assert "adapter_mode" in static_response.text
        assert "degraded" in static_response.text
        assert "availability_hint" in static_response.text
        assert "renderModelInvocation" in static_response.text

        timeline_response = await client.get("/ui/tasks/task_demo_001/events")
        assert timeline_response.status_code == 200
        assert "Task Event Timeline" in timeline_response.text

        timeline_js = await client.get("/static/js/event-timeline.js")
        assert timeline_js.status_code == 200
        assert "renderChainSummary" in timeline_js.text

    async def test_get_task_events_timeline_mapping_and_order(
        self, client: httpx.AsyncClient
    ):
        """Event 时间线接口应返回稳定排序及关键类型映射。"""
        task_id = "test_api_events_001"
        TASK_STORE[task_id] = TaskRecord(
            id=task_id,
            status=ExternalStatus.RUNNING,
            internal_status=InternalStatus.RUNNING,
            goal="timeline task",
            constraints={},
            metadata={},
            plan=None,
            design_result=None,
            pending_action=None,
        )

        DEFAULT_LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_file = DEFAULT_LOG_DIR / f"{task_id}.jsonl"
        events = [
            {
                "event": "TASK_STATUS_CHANGED",
                "task_id": task_id,
                "from_status": "RUNNING",
                "to_status": "WAITING_PATCH",
                "timestamp": "2026-03-08T01:00:01+00:00",
            },
            {
                "event": "PENDING_ACTION_CREATED",
                "task_id": task_id,
                "pending_action_id": "pa_001",
                "action_type": "patch_confirm",
                "timestamp": "2026-03-08T01:00:02+00:00",
            },
            {
                "event": "STEP_FAILED",
                "task_id": task_id,
                "step_id": "S5",
                "tool": "dummy_tool",
                "status": "failed",
                "failure_type": "tool_error",
                "timestamp": "2026-03-08T01:00:03+00:00",
                "error_details": {"failure_code": "S3_QUALITY_GATE_FAIL"},
                "data": {
                    "failure_code": "S3_QUALITY_GATE_FAIL",
                    "recovery": {
                        "recovery_layer": "tool_level",
                        "from_tool": "dummy_tool",
                        "to_tool": "esmfold",
                        "capability_id": "structure_prediction",
                        "adapter_mode": "remote",
                        "io_type": "sequence_to_structure",
                        "reason": "quality_gate_blocked",
                    },
                },
            },
            {
                "event_type": "DECISION_APPLIED",
                "task_id": task_id,
                "decision_id": "decision_001",
                "pending_action_id": "pa_001",
                "ts": "2026-03-08T01:00:04+00:00",
                "data": {
                    "choice": "accept",
                    "selected_candidate_id": "cand_001",
                    "decision_source": "human_reviewer",
                    "tool_id": "esmfold",
                    "capability_id": "structure_prediction",
                    "adapter_mode": "remote",
                },
            },
            {
                "event": "STEP_FINISHED",
                "task_id": task_id,
                "step_id": "S6",
                "tool": "dummy_tool",
                "status": "success",
                "timestamp": "2026-03-08T01:00:05+00:00",
            },
        ]
        with log_file.open("w", encoding="utf-8") as handle:
            for event in events:
                handle.write(json.dumps(event, ensure_ascii=True) + "\n")

        response = await client.get(f"/tasks/{task_id}/events")
        assert response.status_code == 200
        data = response.json()
        assert [entry["event_type"] for entry in data] == [
            "STATE_TRANSITION",
            "PENDING_ACTION_CREATED",
            "STEP_FAILED",
            "DECISION_APPLIED",
            "STEP_FINISHED",
        ]
        assert all(entry["highlight"] for entry in data)
        step_failed = data[2]
        assert step_failed["failure_type"] == "tool_error"
        assert step_failed["failure_code"] == "S3_QUALITY_GATE_FAIL"
        assert step_failed["from_tool"] == "dummy_tool"
        assert step_failed["to_tool"] == "esmfold"
        assert step_failed["capability_id"] == "structure_prediction"
        assert step_failed["adapter_mode"] == "remote"

        decision_applied = data[3]
        assert decision_applied["candidate_id"] == "cand_001"
        assert decision_applied["decision_source"] == "human_reviewer"
        assert decision_applied["tool_id"] == "esmfold"

        filtered = await client.get(
            f"/tasks/{task_id}/events",
            params={"tool_id": "esmfold", "adapter_mode": "remote"},
        )
        assert filtered.status_code == 200
        filtered_data = filtered.json()
        assert len(filtered_data) == 2
        assert {item["event_type"] for item in filtered_data} == {
            "STEP_FAILED",
            "DECISION_APPLIED",
        }

        event_filtered = await client.get(
            f"/tasks/{task_id}/events",
            params={"event_type": "STEP_FAILED"},
        )
        assert event_filtered.status_code == 200
        event_data = event_filtered.json()
        assert len(event_data) == 1
        assert event_data[0]["event_type"] == "STEP_FAILED"

    async def test_get_task_events_not_found(self, client: httpx.AsyncClient):
        """task 不存在且无日志时，events 接口返回 404。"""
        response = await client.get("/tasks/not_found_events_case/events")
        assert response.status_code == 404

    @pytest.mark.parametrize(
        "external_status,internal_status,action_type",
        [
            (
                ExternalStatus.WAITING_PLAN_CONFIRM,
                InternalStatus.WAITING_PLAN_CONFIRM,
                PendingActionType.PLAN_CONFIRM,
            ),
            (
                ExternalStatus.WAITING_PATCH_CONFIRM,
                InternalStatus.PATCHING,
                PendingActionType.PATCH_CONFIRM,
            ),
            (
                ExternalStatus.WAITING_REPLAN_CONFIRM,
                InternalStatus.WAITING_REPLAN,
                PendingActionType.REPLAN_CONFIRM,
            ),
        ],
    )
    async def test_get_task_waiting_state_returns_pending_action(
        self,
        client: httpx.AsyncClient,
        external_status: ExternalStatus,
        internal_status: InternalStatus,
        action_type: PendingActionType,
    ):
        """测试 WAITING_* 状态时 API 返回 pending_action"""
        task_id = f"task_waiting_{action_type.value}"
        if action_type == PendingActionType.PATCH_CONFIRM:
            patched_step = PlanStep(id="S1", tool="tool_b", inputs={}, metadata={})
            patch = PlanPatch(
                task_id=task_id,
                operations=[
                    PlanPatchOp(op="replace_step", target="S1", step=patched_step)
                ],
                metadata={},
            )
            candidates = [
                PendingActionCandidate(candidate_id="patch_a", payload=patch)
            ]
        else:
            plan = Plan(
                task_id=task_id,
                steps=[PlanStep(id="S1", tool="tool_a", inputs={}, metadata={})],
                constraints={},
                metadata={},
            )
            candidates = [
                PendingActionCandidate(candidate_id="plan_a" if action_type == PendingActionType.PLAN_CONFIRM else "replan_a", payload=plan)
            ]

        pending_action = PendingAction(
            pending_action_id=f"pa_{action_type.value}",
            task_id=task_id,
            action_type=action_type,
            candidates=candidates,
            explanation="waiting for decision",
        )
        record = TaskRecord(
            id=task_id,
            status=external_status,
            internal_status=internal_status,
            goal="waiting state test",
            constraints={},
            metadata={},
            plan=None,
            design_result=None,
            pending_action=pending_action,
        )
        TASK_STORE[task_id] = record

        response = await client.get(f"/tasks/{task_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == external_status.value
        assert data["pending_action"] is not None
        assert data["pending_action"]["action_type"] == action_type.value
        assert data["pending_action"]["candidates"]
        assert data["pending_action"]["explanation"] == "waiting for decision"

    @pytest.mark.parametrize(
        "external_status,internal_status",
        [
            (ExternalStatus.CREATED, InternalStatus.CREATED),
            (ExternalStatus.PLANNING, InternalStatus.PLANNING),
            (ExternalStatus.PLANNED, InternalStatus.PLANNED),
            (ExternalStatus.RUNNING, InternalStatus.RUNNING),
            (ExternalStatus.DONE, InternalStatus.DONE),
            (ExternalStatus.FAILED, InternalStatus.FAILED),
        ],
    )
    async def test_get_task_non_waiting_state_no_pending_action(
        self,
        client: httpx.AsyncClient,
        external_status: ExternalStatus,
        internal_status: InternalStatus,
    ):
        """测试非 WAITING_* 状态时 API 不返回 pending_action 或返回 null"""
        task_id = f"task_non_waiting_{external_status.value}"
        record = TaskRecord(
            id=task_id,
            status=external_status,
            internal_status=internal_status,
            goal="non-waiting state test",
            constraints={},
            metadata={},
            plan=None,
            design_result=None,
            pending_action=None,  # 非 WAITING 状态，pending_action 应为 None
        )
        TASK_STORE[task_id] = record

        response = await client.get(f"/tasks/{task_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == external_status.value
        # pending_action 应该是 None 或不存在
        assert data.get("pending_action") is None

    async def test_submit_decision_accept_plan(self, client: httpx.AsyncClient):
        """测试提交 ACCEPT 决策以接受计划"""
        task_id = "task_decision_accept_plan"
        pending_action_id = "pa_accept_plan"

        # 创建一个 WAITING_PLAN_CONFIRM 状态的任务
        plan = Plan(
            task_id=task_id,
            steps=[PlanStep(id="S1", tool="tool_a", inputs={}, metadata={})],
            constraints={},
            metadata={},
        )
        pending_action = PendingAction(
            pending_action_id=pending_action_id,
            task_id=task_id,
            action_type=PendingActionType.PLAN_CONFIRM,
            status=PendingActionStatus.PENDING,
            candidates=[
                PendingActionCandidate(candidate_id="plan_1", payload=plan)
            ],
            explanation="please confirm plan",
        )
        record = TaskRecord(
            id=task_id,
            status=ExternalStatus.WAITING_PLAN_CONFIRM,
            internal_status=InternalStatus.WAITING_PLAN_CONFIRM,
            goal="test decision accept",
            constraints={},
            metadata={},
            plan=None,
            design_result=None,
            pending_action=pending_action,
        )
        TASK_STORE[task_id] = record

        # 提交决策
        response = await client.post(
            f"/pending-actions/{pending_action_id}/decision",
            json={
                "choice": "accept",
                "selected_candidate_id": "plan_1",
                "decided_by": "test_user",
                "comment": "looks good",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == task_id
        assert data["status"] == ExternalStatus.PLANNED.value
        assert data["plan"] is not None
        assert data["pending_action"] is None or data["pending_action"]["status"] == PendingActionStatus.DECIDED.value

    async def test_submit_decision_not_found(self, client: httpx.AsyncClient):
        """测试提交决策时 PendingAction 不存在"""
        response = await client.post(
            "/pending-actions/nonexistent_pa/decision",
            json={
                "choice": "accept",
                "selected_candidate_id": "plan_1",
                "decided_by": "test_user",
            },
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    async def test_submit_decision_validation_error(self, client: httpx.AsyncClient):
        """测试提交决策时验证失败（accept 缺少 candidate_id）"""
        task_id = "task_decision_validation_error"
        pending_action_id = "pa_validation_error"

        pending_action = PendingAction(
            pending_action_id=pending_action_id,
            task_id=task_id,
            action_type=PendingActionType.PLAN_CONFIRM,
            status=PendingActionStatus.PENDING,
            candidates=[
                PendingActionCandidate(
                    candidate_id="plan_1",
                    payload=Plan(task_id=task_id, steps=[], constraints={}, metadata={}),
                )
            ],
            explanation="test",
        )
        record = TaskRecord(
            id=task_id,
            status=ExternalStatus.WAITING_PLAN_CONFIRM,
            internal_status=InternalStatus.WAITING_PLAN_CONFIRM,
            goal="test validation error",
            constraints={},
            metadata={},
            plan=None,
            design_result=None,
            pending_action=pending_action,
        )
        TASK_STORE[task_id] = record

        # 提交 accept 决策但不提供 selected_candidate_id
        response = await client.post(
            f"/pending-actions/{pending_action_id}/decision",
            json={
                "choice": "accept",
                "decided_by": "test_user",
            },
        )

        # Pydantic 验证错误会被捕获并返回 400
        assert response.status_code == 400

    async def test_submit_decision_replan_choice(self, client: httpx.AsyncClient):
        """测试提交 REPLAN 决策"""
        task_id = "task_decision_replan"
        pending_action_id = "pa_replan"

        pending_action = PendingAction(
            pending_action_id=pending_action_id,
            task_id=task_id,
            action_type=PendingActionType.PLAN_CONFIRM,
            status=PendingActionStatus.PENDING,
            candidates=[
                PendingActionCandidate(
                    candidate_id="plan_1",
                    payload=Plan(task_id=task_id, steps=[], constraints={}, metadata={}),
                )
            ],
            explanation="test replan",
        )
        record = TaskRecord(
            id=task_id,
            status=ExternalStatus.WAITING_PLAN_CONFIRM,
            internal_status=InternalStatus.WAITING_PLAN_CONFIRM,
            goal="test replan decision",
            constraints={},
            metadata={},
            plan=None,
            design_result=None,
            pending_action=pending_action,
        )
        TASK_STORE[task_id] = record

        # 提交 replan 决策
        response = await client.post(
            f"/pending-actions/{pending_action_id}/decision",
            json={
                "choice": "replan",
                "decided_by": "test_user",
                "comment": "need better plan",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == task_id
        # REPLAN 会触发重新规划，状态应该变为 PLANNING
        assert data["status"] == ExternalStatus.PLANNING.value

    async def test_submit_decision_cancel_choice(self, client: httpx.AsyncClient):
        """测试提交 CANCEL 决策"""
        task_id = "task_decision_cancel"
        pending_action_id = "pa_cancel"

        pending_action = PendingAction(
            pending_action_id=pending_action_id,
            task_id=task_id,
            action_type=PendingActionType.PLAN_CONFIRM,
            status=PendingActionStatus.PENDING,
            candidates=[
                PendingActionCandidate(
                    candidate_id="plan_1",
                    payload=Plan(task_id=task_id, steps=[], constraints={}, metadata={}),
                )
            ],
            explanation="test cancel",
        )
        record = TaskRecord(
            id=task_id,
            status=ExternalStatus.WAITING_PLAN_CONFIRM,
            internal_status=InternalStatus.WAITING_PLAN_CONFIRM,
            goal="test cancel decision",
            constraints={},
            metadata={},
            plan=None,
            design_result=None,
            pending_action=pending_action,
        )
        TASK_STORE[task_id] = record

        # 提交 cancel 决策
        response = await client.post(
            f"/pending-actions/{pending_action_id}/decision",
            json={
                "choice": "cancel",
                "decided_by": "test_user",
                "comment": "task cancelled by user",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == task_id
        # CANCEL 应该将任务状态设置为 CANCELLED
        assert data["status"] == ExternalStatus.CANCELLED.value
