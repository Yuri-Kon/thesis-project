"""React Web smoke — 验证 React 工作区页面可加载、bootstrap 注入正确。

设计要求（web-operator-workspace.md）：
- /ui 渲染 Dashboard，/ui/tasks/{id} 渲染 Task Detail
- /ui/tasks/{id}/events 渲染 Event Timeline，/ui/task-builder 渲染 Task Builder
- React 页面通过 bootstrap JSON 注入初始 view/taskId，不通过服务端渲染状态
- Decision 提交后刷新 task / pending-actions / pending-action detail / events
"""

from __future__ import annotations

import json
from typing import cast

import httpx
import pytest

from src.api.main import INTAKE_STORE, TASK_STORE, app
from src.models.db import ExternalStatus, InternalStatus, TaskRecord


@pytest.mark.api
@pytest.mark.anyio
class TestWebSmoke:
    @pytest.fixture(autouse=True)
    def disable_providers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PLANNER_LLM_PROVIDER", "off")
        for env_name in (
            "OPENAI_API_KEY", "DASHSCOPE_API_KEY",
            "DEEPSEEK_API_KEY", "ZHIPU_API_KEY", "NIM_API_KEY",
        ):
            monkeypatch.delenv(env_name, raising=False)

    @pytest.fixture
    def anyio_backend(self) -> str:
        return "asyncio"

    @pytest.fixture
    async def client(self) -> httpx.AsyncClient:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as c:
            yield c

    @pytest.fixture(autouse=True)
    def clear_stores(self) -> None:
        TASK_STORE.clear()
        INTAKE_STORE.clear()
        yield
        TASK_STORE.clear()
        INTAKE_STORE.clear()


# -- 页面可加载性 -----------------------------------------------------------


class TestPageLoadability(TestWebSmoke):
    async def test_dashboard_loads_with_bootstrap(self, client: httpx.AsyncClient) -> None:
        resp = await client.get("/ui")
        assert resp.status_code == 200
        html = resp.text
        assert '<div id="root">' in html
        assert 'id="app-bootstrap"' in html
        bootstrap = _extract_bootstrap(html)
        assert bootstrap["view"] == "dashboard"
        assert bootstrap["taskId"] == ""

    async def test_task_detail_loads_with_task_id(self, client: httpx.AsyncClient) -> None:
        _seed_task("task_web_001", goal="test web task")
        resp = await client.get("/ui/tasks/task_web_001")
        assert resp.status_code == 200
        bootstrap = _extract_bootstrap(resp.text)
        assert bootstrap["view"] == "task_detail"
        assert bootstrap["taskId"] == "task_web_001"

    async def test_task_detail_404_renders_no_bootstrap_crash(self, client: httpx.AsyncClient) -> None:
        resp = await client.get("/ui/tasks/nonexistent_xyz")
        # 页面仍应返回（bootstrap 包含空 task）
        assert resp.status_code == 200

    async def test_event_timeline_loads(self, client: httpx.AsyncClient) -> None:
        _seed_task("task_web_002")
        resp = await client.get("/ui/tasks/task_web_002/events")
        assert resp.status_code == 200
        bootstrap = _extract_bootstrap(resp.text)
        assert bootstrap["view"] == "event_timeline"

    async def test_task_builder_loads(self, client: httpx.AsyncClient) -> None:
        resp = await client.get("/ui/task-builder")
        assert resp.status_code == 200
        bootstrap = _extract_bootstrap(resp.text)
        assert bootstrap["view"] == "task_builder"


# -- 完整 intake → task → detail 流程 --------------------------------------


class TestIntakeToTaskFlow(TestWebSmoke):
    async def test_full_intake_to_task_detail(self, client: httpx.AsyncClient) -> None:
        # 1. 创建 intake
        create_resp = await client.post("/task-intakes", json={
            "structured_fields": {
                "task_kind": "de_novo_design",
                "objective_type": "stability",
                "length_range": [80, 120],
            },
            "source": "web",
        })
        assert create_resp.status_code == 200
        intake = create_resp.json()
        intake_id = intake["intake_id"]

        # 2. 确认 intake → 创建 task
        confirm_resp = await client.post(
            f"/task-intakes/{intake_id}/confirm",
            json={"confirmed_by": "web_test", "acknowledged_warnings": []},
        )
        assert confirm_resp.status_code == 200
        task_id = confirm_resp.json()["task_id"]

        # 3. Task Detail 页面可加载
        resp = await client.get(f"/ui/tasks/{task_id}")
        assert resp.status_code == 200
        bootstrap = _extract_bootstrap(resp.text)
        assert bootstrap["view"] == "task_detail"
        assert bootstrap["taskId"] == task_id

        # 4. Task 数据可通过 API 获取
        task_resp = await client.get(f"/tasks/{task_id}")
        assert task_resp.status_code == 200
        task_data = task_resp.json()
        assert task_data["status"] == "CREATED"

    async def test_intake_events_flow_to_timeline(self, client: httpx.AsyncClient) -> None:
        # 创建 intake → confirm → 获取事件
        create_resp = await client.post("/task-intakes", json={
            "structured_fields": {
                "task_kind": "de_novo_design",
                "objective_type": "stability",
                "length_range": [60, 100],
            },
            "source": "web",
        })
        intake_id = create_resp.json()["intake_id"]

        confirm_resp = await client.post(
            f"/task-intakes/{intake_id}/confirm",
            json={"confirmed_by": "web_test", "acknowledged_warnings": []},
        )
        task_id = confirm_resp.json()["task_id"]

        # 事件 API 可访问
        events_resp = await client.get(f"/tasks/{task_id}/events")
        assert events_resp.status_code == 200
        events = events_resp.json()
        assert isinstance(events, list)

        # Timeline 页面可加载
        timeline_resp = await client.get(f"/ui/tasks/{task_id}/events")
        assert timeline_resp.status_code == 200
        bootstrap = _extract_bootstrap(timeline_resp.text)
        assert bootstrap["view"] == "event_timeline"
        assert bootstrap["taskId"] == task_id


# -- 安全 warn 场景 ---------------------------------------------------------


class TestSafetyWarnFlow(TestWebSmoke):
    async def test_safety_warn_intake_dashboard_still_loads(self, client: httpx.AsyncClient) -> None:
        # 含 forbidden_motif 的 intake 触发 safety warn
        create_resp = await client.post("/task-intakes", json={
            "structured_fields": {
                "task_kind": "sequence_evaluation",
                "objective_type": "stability",
                "sequence": "ACDE",
                "forbidden_motifs": ["CDE"],
            },
            "source": "web",
        })
        assert create_resp.status_code == 200
        data = create_resp.json()
        assert data["safety_check"]["action"] == "warn"

        # Dashboard 仍应正常加载
        dash_resp = await client.get("/ui")
        assert dash_resp.status_code == 200

    async def test_safety_block_prevents_task_creation(self, client: httpx.AsyncClient) -> None:
        create_resp = await client.post("/task-intakes", json={
            "structured_fields": {
                "task_kind": "de_novo_design",
                "objective_type": "stability",
                "length_range": [80, 120],
            },
            "source": "web",
            "text": "design a toxin-like protein",
        })
        assert create_resp.status_code == 200
        intake_id = create_resp.json()["intake_id"]

        # 确认被阻止
        confirm_resp = await client.post(
            f"/task-intakes/{intake_id}/confirm",
            json={
                "confirmed_by": "web_test",
                "acknowledged_warnings": ["HIGH_RISK_BIOFUNCTION_REQUEST"],
            },
        )
        assert confirm_resp.status_code == 422


# -- pending-actions API ----------------------------------------------------


class TestPendingActionsAPI(TestWebSmoke):
    async def test_pending_actions_list_returns_array(self, client: httpx.AsyncClient) -> None:
        resp = await client.get("/pending-actions")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_pending_actions_empty_for_new_task(self, client: httpx.AsyncClient) -> None:
        _seed_task("task_no_pending", status=ExternalStatus.CREATED)
        resp = await client.get("/pending-actions")
        items = cast(list[object], resp.json())
        task_ids = {
            item["task_id"]
            for item in items
            if isinstance(item, dict) and "task_id" in item
        }
        assert "task_no_pending" not in task_ids


# -- helpers ----------------------------------------------------------------


def _extract_bootstrap(html: str) -> dict[str, object]:
    """从 React HTML 模板中提取 bootstrap JSON。"""
    start = html.find('id="app-bootstrap"')
    if start == -1:
        return {}
    tag_start = html.find(">", start) + 1
    tag_end = html.find("</script>", tag_start)
    raw = html[tag_start:tag_end].strip()
    try:
        result = json.loads(raw)
        return result if isinstance(result, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _seed_task(
    task_id: str,
    *,
    goal: str = "test task",
    status: ExternalStatus = ExternalStatus.CREATED,
) -> None:
    TASK_STORE[task_id] = TaskRecord(
        id=task_id,
        status=status,
        internal_status=cast(InternalStatus, status.value),
        goal=goal,
        constraints={},
        metadata={},
        created_at="2026-05-01T00:00:00Z",
        updated_at="2026-05-01T00:00:00Z",
    )
