from __future__ import annotations

from pathlib import Path
from collections.abc import Sequence

import httpx
import pytest
from pydantic import TypeAdapter

import src.api.main as api_main
from src.api.main import INTAKE_STORE, TASK_STORE, app
from src.models.db import JsonObject

JSON_OBJECT_ADAPTER: TypeAdapter[JsonObject] = TypeAdapter(JsonObject)
JSON_OBJECT_LIST_ADAPTER: TypeAdapter[list[JsonObject]] = TypeAdapter(list[JsonObject])


@pytest.mark.api
@pytest.mark.anyio
class TestDefenseDemoFixture:
    """答辩全流程本地演示 fixture 的 API 契约测试。"""

    @pytest.fixture
    def anyio_backend(self) -> str:
        return "asyncio"

    @pytest.fixture(autouse=True)
    def isolate_runtime(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        monkeypatch.setenv("PLANNER_LLM_PROVIDER", "off")
        monkeypatch.setenv("PROTEIN_OUTPUT_DIR", str(tmp_path / "output"))
        monkeypatch.setenv("PROTEIN_DATA_DIR", str(tmp_path / "data"))
        monkeypatch.setenv("PROTEIN_LOG_DIR", str(tmp_path / "data" / "logs"))
        monkeypatch.setenv(
            "PROTEIN_SNAPSHOT_DIR",
            str(tmp_path / "data" / "snapshots"),
        )
        for env_name in (
            "OPENAI_API_KEY",
            "DASHSCOPE_API_KEY",
            "DEEPSEEK_API_KEY",
            "ZHIPU_API_KEY",
            "NIM_API_KEY",
            "PROTEIN_ENABLE_DEMO_FIXTURES",
        ):
            monkeypatch.delenv(env_name, raising=False)
        TASK_STORE.clear()
        INTAKE_STORE.clear()
        api_main.RUNTIME_INIT = None
        yield
        TASK_STORE.clear()
        INTAKE_STORE.clear()
        api_main.RUNTIME_INIT = None

    @pytest.fixture
    async def client(self):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            yield client

    async def test_defense_demo_fixture_disabled_returns_404(
        self,
        client: httpx.AsyncClient,
    ):
        response = await client.post("/demo/defense-full-flow")

        assert response.status_code == 404
        assert response.json()["detail"] == "demo fixtures are disabled"

    async def test_defense_demo_fixture_seeds_full_flow(
        self,
        client: httpx.AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ):
        monkeypatch.setenv("PROTEIN_ENABLE_DEMO_FIXTURES", "1")
        api_main.RUNTIME_INIT = None

        create_response = await client.post("/demo/defense-full-flow")

        assert create_response.status_code == 200
        payload = _response_object(create_response)
        tasks = _required_object(payload, "tasks")
        urls = _required_object(payload, "urls")
        assert tasks == {
            "intake": "demo_defense_intake",
            "hitl": "demo_defense_hitl",
            "done": "demo_defense_done",
        }
        assert urls["hitl_task"] == "/ui/tasks/demo_defense_hitl"
        assert urls["done_events"] == "/ui/tasks/demo_defense_done/events"

        artifact_dir = tmp_path / "output" / "demo" / "defense-full-flow"
        assert (artifact_dir / "demo_defense_done.pdb").exists()
        assert (artifact_dir / "demo_defense_done_report.json").exists()
        assert (artifact_dir / "demo_defense_manifest.json").exists()
        assert (artifact_dir / "screenshots").is_dir()

        hitl_response = await client.get("/tasks/demo_defense_hitl")
        hitl = _response_object(hitl_response)
        assert hitl_response.status_code == 200
        assert hitl["status"] == "WAITING_PATCH_CONFIRM"
        assert hitl["internal_status"] == "WAITING_PATCH"
        hitl_pending = _required_object(hitl, "pending_action")
        assert hitl_pending["action_type"] == "patch_confirm"
        assert hitl_pending["default_recommendation"] == "patch_local_openfold"
        assert len(_required_list(hitl_pending, "candidates")) == 3

        pending_detail_response = await client.get("/pending-actions/pa_demo_defense_patch")
        pending_detail = _response_object(pending_detail_response)
        assert pending_detail_response.status_code == 200
        runtime_state = _required_object(pending_detail, "runtime_state_summary")
        candidates = _required_object_list(pending_detail, "candidates")
        assert runtime_state["p_success"] == 0.64
        assert candidates[0]["candidate_id"] == "patch_local_openfold"

        report_response = await client.get("/tasks/demo_defense_done/report")
        report = _response_object(report_response)
        assert report_response.status_code == 200
        objective_scoring = _required_object(report, "objective_scoring")
        structure_similarity = _required_object(report, "structure_similarity")
        top_hit = _required_object(structure_similarity, "top_hit")
        assert objective_scoring["objective_score"] == 0.84
        assert top_hit["hit_id"] == "TRP_CAGE_REFERENCE"

        structure_response = await client.get("/tasks/demo_defense_done/structure")
        assert structure_response.status_code == 200
        assert "HEADER    DEFENSE FULL FLOW DEMO" in structure_response.text
        assert structure_response.text.count("\nATOM") >= 90

        events_response = await client.get("/tasks/demo_defense_done/events")
        events = _response_object_list(events_response)
        assert events_response.status_code == 200
        event_types = {_required_str(event, "event_type") for event in events}
        to_statuses = {_optional_str(event, "to_status") for event in events}
        assert {
            "WAITING_ENTER",
            "DECISION_APPLIED",
            "WAITING_EXIT",
            "STEP_FINISHED",
            "SUMMARY_CREATED",
        }.issubset(event_types)
        assert "DONE" in to_statuses


def _response_object(response: httpx.Response) -> JsonObject:
    return JSON_OBJECT_ADAPTER.validate_json(response.text)


def _response_object_list(response: httpx.Response) -> list[JsonObject]:
    return JSON_OBJECT_LIST_ADAPTER.validate_json(response.text)


def _required_object(payload: JsonObject, key: str) -> JsonObject:
    value = payload[key]
    return JSON_OBJECT_ADAPTER.validate_python(value)


def _required_list(payload: JsonObject, key: str) -> Sequence[object]:
    value = payload[key]
    if not isinstance(value, list):
        raise AssertionError(f"{key} must be a list")
    return value


def _required_object_list(payload: JsonObject, key: str) -> list[JsonObject]:
    value = payload[key]
    return JSON_OBJECT_LIST_ADAPTER.validate_python(value)


def _required_str(payload: JsonObject, key: str) -> str:
    value = payload[key]
    if not isinstance(value, str):
        raise AssertionError(f"{key} must be a string")
    return value


def _optional_str(payload: JsonObject, key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise AssertionError(f"{key} must be a string or null")
    return value
