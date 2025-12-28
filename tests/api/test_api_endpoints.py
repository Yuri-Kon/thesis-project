"""API端点测试"""
import pytest
import httpx

from src.api.main import app, TASK_STORE
from src.models.contracts import (
    PendingAction,
    PendingActionCandidate,
    PendingActionType,
    Plan,
    PlanPatch,
    PlanPatchOp,
    PlanStep,
)
from src.models.db import ExternalStatus, InternalStatus, TaskRecord


@pytest.mark.api
@pytest.mark.anyio
class TestAPIEndpoints:
    """API端点测试类"""

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

    @pytest.mark.parametrize(
        "external_status,internal_status,action_type",
        [
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
                PendingActionCandidate(candidate_id="replan_a", payload=plan)
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
