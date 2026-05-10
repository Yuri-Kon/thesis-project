"""API端点测试"""
import json
from pathlib import Path

import pytest
import httpx

from src.api.main import app, INTAKE_STORE, TASK_STORE
from src.models.contracts import (
    DesignResult,
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
        INTAKE_STORE.clear()
        if DEFAULT_LOG_DIR.exists():
            for path in DEFAULT_LOG_DIR.glob("test_api_events_*.jsonl"):
                path.unlink()
        yield
        TASK_STORE.clear()
        INTAKE_STORE.clear()
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

    async def test_scenario_gate_preview_applies_hint_and_tool_filters(
        self,
        client: httpx.AsyncClient,
    ):
        """预览接口应按确认阶段的 io_type 与工具过滤器计算 readiness。"""

        response = await client.get(
            "/capabilities/scenario-gate/preview",
            params={
                "structured_fields": json.dumps(
                    {
                        "task_kind": "stability_optimization",
                        "sequence": "ACDEFGHIKLMNPQRSTVWY",
                        "tools_allowed": ["esmfold"],
                    }
                )
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["support_level"] == "P1"
        readiness = data["readiness"]
        objective_key = "objective_scoring:candidates_to_objective_scores_topk"
        assert objective_key in readiness
        objective_entry = readiness[objective_key]
        assert objective_entry["capability_id"] == "objective_scoring"
        assert objective_entry["status"] == "unavailable"
        assert "allowed tool filter" in objective_entry["reason"]
        assert objective_key in data["blocked_hints"]

    async def test_pending_action_detail_exposes_execution_mode(
        self,
        client: httpx.AsyncClient,
    ):
        """PendingAction detail 应展示 tool/adapter/execution mode 边界。"""

        task_id = "test_api_execution_mode"
        pending_action = PendingAction(
            pending_action_id="pa_execution_mode",
            task_id=task_id,
            action_type=PendingActionType.PLAN_CONFIRM,
            status=PendingActionStatus.PENDING,
            candidates=[
                PendingActionCandidate(
                    candidate_id="cand_openfold_rest",
                    payload=Plan(
                        task_id=task_id,
                        steps=[
                            PlanStep(
                                id="S2",
                                tool="openfold",
                                inputs={"sequence": "S1.sequence"},
                            )
                        ],
                    ),
                    tool_id="openfold",
                    adapter_id="openfold",
                    capability_id="structure_prediction",
                    io_type="sequence_to_structure",
                    adapter_mode="remote",
                    execution_mode="openfold3_rest",
                    provider="openfold3_rest",
                    endpoint_type="rest",
                    remote_job_id="of3_job_1",
                    metadata={
                        "failure_code": "REMOTE_JOB_FAILED",
                        "recovery_hint": "Inspect OpenFold3 REST logs.",
                    },
                )
            ],
            explanation="review execution mode",
            default_recommendation="cand_openfold_rest",
        )
        TASK_STORE[task_id] = TaskRecord(
            id=task_id,
            status=ExternalStatus.WAITING_PLAN_CONFIRM,
            internal_status=InternalStatus.WAITING_PLAN_CONFIRM,
            goal="review",
            pending_action=pending_action,
        )

        response = await client.get("/pending-actions/pa_execution_mode")

        assert response.status_code == 200
        data = response.json()
        tool = data["candidates"][0]["tool"]
        assert tool["tool_id"] == "openfold"
        assert tool["adapter_id"] == "openfold"
        assert tool["execution_mode"] == "openfold3_rest"
        assert tool["provider"] == "openfold3_rest"
        assert tool["endpoint_type"] == "rest"
        assert tool["remote_job_id"] == "of3_job_1"
        assert tool["failure_code"] == "REMOTE_JOB_FAILED"
        assert tool["recovery_hint"] == "Inspect OpenFold3 REST logs."

    async def test_task_report_endpoint_exposes_objective_scoring(
        self,
        client: httpx.AsyncClient,
    ):
        """报告接口应暴露 objective score table 与排序理由。"""

        task_id = "test_api_report_objective"
        TASK_STORE[task_id] = TaskRecord(
            id=task_id,
            status=ExternalStatus.DONE,
            internal_status=InternalStatus.DONE,
            goal="设计候选并排序",
            constraints={},
            metadata={},
            design_result=DesignResult(
                task_id=task_id,
                sequence="ACDE",
                structure_pdb_path=None,
                scores={"objective_score": 0.81},
                risk_flags=[],
                report_path="output/reports/test_api_report_objective.json",
                metadata={
                    "objective_scoring": {
                        "top_k": [
                            {"candidate_id": "cand_a", "objective_score": 0.81}
                        ],
                        "component_scores": {"cand_a": {"quality": 0.9}},
                        "warnings": ["proxy warning"],
                        "rank_reason": "cand_a ranks by objective_score=0.810",
                    },
                    "structure_similarity": {
                        "hit_count": 1,
                        "top_hit": {"hit_id": "1abc_A", "tm_score": 0.82},
                        "artifact_refs": [
                            {"kind": "foldseek_tabular", "path": "output/foldseek.m8"}
                        ],
                    }
                },
            ),
        )

        response = await client.get(f"/tasks/{task_id}/report")

        assert response.status_code == 200
        data = response.json()
        assert data["scores"]["objective_score"] == 0.81
        assert data["objective_scoring"]["top_k"][0]["candidate_id"] == "cand_a"
        assert data["objective_scoring"]["rank_reason"].startswith("cand_a ranks")
        assert data["structure_similarity"]["top_hit"]["hit_id"] == "1abc_A"

    async def test_task_report_endpoint_done_contract_and_unfinished_404(
        self,
        client: httpx.AsyncClient,
    ):
        """报告接口应只对已生成 DesignResult 的任务返回稳定报告。"""

        unfinished_task_id = "test_api_report_unfinished"
        TASK_STORE[unfinished_task_id] = TaskRecord(
            id=unfinished_task_id,
            status=ExternalStatus.RUNNING,
            internal_status=InternalStatus.RUNNING,
            goal="运行中任务",
            constraints={},
            metadata={},
            design_result=None,
        )
        done_task_id = "test_api_report_done_contract"
        TASK_STORE[done_task_id] = TaskRecord(
            id=done_task_id,
            status=ExternalStatus.DONE,
            internal_status=InternalStatus.DONE,
            goal="稳定性评估",
            constraints={"sequence": "ACDEFGHIKLMNPQRSTVWY"},
            metadata={"source": "focused_test"},
            design_result=DesignResult(
                task_id=done_task_id,
                sequence="ACDEFGHIKLMNPQRSTVWY",
                structure_pdb_path="output/pdb/test_api_report_done_contract.pdb",
                scores={"plddt": 87.5, "objective_score": 0.76},
                risk_flags=[],
                report_path="output/reports/test_api_report_done_contract.json",
                metadata={
                    "objective_scoring": {
                        "top_k": [
                            {
                                "candidate_id": "seq_eval",
                                "objective_score": 0.76,
                            }
                        ],
                        "rank_reason": "seq_eval ranks by objective_score=0.760",
                    },
                    "structure_similarity": {
                        "hit_count": 0,
                        "artifact_refs": [],
                    },
                    "evidence": {
                        "step_result_count": 1,
                        "structure_artifact": "output/pdb/test_api_report_done_contract.pdb",
                    },
                },
            ),
        )

        unfinished_response = await client.get(f"/tasks/{unfinished_task_id}/report")
        done_response = await client.get(f"/tasks/{done_task_id}/report")

        assert unfinished_response.status_code == 404
        assert unfinished_response.json()["detail"] == "task report not found"
        assert done_response.status_code == 200
        data = done_response.json()
        assert data["task_id"] == done_task_id
        assert data["report_path"] == "output/reports/test_api_report_done_contract.json"
        assert data["structure_pdb_path"] == "output/pdb/test_api_report_done_contract.pdb"
        assert data["scores"] == {"plddt": 87.5, "objective_score": 0.76}
        assert data["objective_scoring"]["top_k"][0]["candidate_id"] == "seq_eval"
        assert data["structure_similarity"]["hit_count"] == 0
        assert data["metadata"]["evidence"]["step_result_count"] == 1

    async def test_task_structure_endpoint_returns_pdb_artifact(
        self,
        client: httpx.AsyncClient,
        tmp_path: Path,
    ):
        """结构文件接口应返回 DesignResult 记录的 PDB 文本。"""

        pdb_path = tmp_path / "test_api_structure.pdb"
        pdb_text = (
            "ATOM      1  N   ALA A   1      11.104  13.207   9.201  1.00 20.00           N\n"
            "ATOM      2  CA  ALA A   1      12.104  13.907   9.701  1.00 20.00           C\n"
            "ATOM      3  CA  GLY A   2      13.204  14.407  10.201  1.00 20.00           C\n"
            "END\n"
        )
        pdb_path.write_text(pdb_text, encoding="utf-8")
        task_id = "test_api_structure"
        TASK_STORE[task_id] = TaskRecord(
            id=task_id,
            status=ExternalStatus.DONE,
            internal_status=InternalStatus.DONE,
            goal="展示结构",
            constraints={},
            metadata={},
            design_result=DesignResult(
                task_id=task_id,
                sequence="AG",
                structure_pdb_path=str(pdb_path),
                scores={},
                risk_flags=[],
                report_path="output/reports/test_api_structure.json",
                metadata={},
            ),
        )

        report_response = await client.get(f"/tasks/{task_id}/report")
        structure_response = await client.get(f"/tasks/{task_id}/structure")

        assert report_response.status_code == 200
        assert report_response.json()["structure_pdb_path"] == str(pdb_path)
        assert structure_response.status_code == 200
        assert "ATOM      2  CA  ALA" in structure_response.text
        assert structure_response.headers["content-type"].startswith("chemical/x-pdb")

    async def test_demo_structure_viewer_fixture_seeds_done_task(
        self,
        client: httpx.AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Demo fixture 应无需真实推理即可创建可展示结构的 DONE 任务。"""

        monkeypatch.setenv("PROTEIN_ENABLE_DEMO_FIXTURES", "1")

        create_response = await client.post("/demo/structure-viewer-task")
        task_response = await client.get("/tasks/demo_structure_viewer")
        structure_response = await client.get("/tasks/demo_structure_viewer/structure")

        assert create_response.status_code == 200
        payload = create_response.json()
        assert payload["task_id"] == "demo_structure_viewer"
        assert payload["ui_url"] == "/ui/tasks/demo_structure_viewer"
        assert task_response.status_code == 200
        assert task_response.json()["status"] == "DONE"
        assert structure_response.status_code == 200
        assert "HEADER    STRUCTURE VIEWER DEMO" in structure_response.text
        assert structure_response.text.count("\nATOM") >= 300

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

    async def test_task_intake_schema_exposes_registry_fields(
        self,
        client: httpx.AsyncClient,
    ):
        """Task Builder 应从 /task-intakes/schema 获取字段注册表。"""

        response = await client.get("/task-intakes/schema")

        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "task-intake.v1"
        assert data["groups"] == [
            "objective",
            "inputs",
            "design_constraints",
            "quality_constraints",
            "structure_constraints",
            "function_constraints",
            "safety_constraints",
            "execution_preferences",
            "planner_policy",
        ]
        assert data["fields"]["task_kind"]["maps_to"] == "constraints.task_kind"
        assert "esmfold" in data["fields"]["tools_allowed"]["options"]
        assert any(
            option["tool_id"] == "esmfold" and option["support_level"] == "P0"
            for option in data["tool_options"]
        )
        assert "de_novo_design" in data["task_profiles"]
        assert data["task_profiles"]["binding_design"]["support_level"] == "P2"
        assert data["task_profiles"]["binding_design"]["conditional_required"][0][
            "required"
        ] == ["binding_partner"]
        assert any(
            rule["profile"] == "binding_design"
            and rule["required"] == ["binding_partner"]
            for rule in data["conditional_required"]
        )
        assert data["cli_arguments"][0]["flag"].startswith("--")
        assert data["cli_questions"][0]["prompt"]
        assert data["confirmed_task_spec_mapping"]["sequence"] == "inputs.sequence"

    async def test_task_intake_create_tracks_ambiguous_and_unmapped_text(
        self,
        client: httpx.AsyncClient,
    ):
        """低置信度字段进入 ambiguous，未识别文本进入 unmapped_text。"""

        response = await client.post(
            "/task-intakes",
            json={
                "text": "unmapped legacy request",
                "structured_fields": {
                    "task_kind": "de_novo_design",
                    "objective_type": {
                        "value": "stability",
                        "confidence": 0.65,
                        "source_span": "maybe stable",
                    },
                    "length_range": [100, 140],
                },
                "source": "web",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "needs_confirmation"
        assert data["ambiguous_fields"] == ["objective_type"]
        assert data["unmapped_text"] == ["unmapped legacy request"]
        assert data["draft"]["fields"]["objective_type"]["source"] == "user_explicit"

    async def test_task_intake_patch_and_confirm_creates_created_task_with_backlink(
        self,
        client: httpx.AsyncClient,
    ):
        """confirm 通过 ConfirmedTaskSpec 创建正式 Task 并回链 intake_id。"""

        create_response = await client.post(
            "/task-intakes",
            json={
                "structured_fields": {
                    "task_kind": "de_novo_design",
                    "objective_type": "stability",
                    "length_range": [100, 140],
                },
                "source": "web",
            },
        )
        assert create_response.status_code == 200
        intake_id = create_response.json()["intake_id"]

        patch_response = await client.patch(
            f"/task-intakes/{intake_id}",
            json={"fields": {"run_profile": "balanced"}, "updated_by": "tester"},
        )
        assert patch_response.status_code == 200
        assert patch_response.json()["draft"]["fields"]["run_profile"]["confirmed"] is True

        confirm_response = await client.post(
            f"/task-intakes/{intake_id}/confirm",
            json={"confirmed_by": "tester", "acknowledged_warnings": []},
        )
        assert confirm_response.status_code == 200
        confirmation = confirm_response.json()
        assert confirmation["status"] == ExternalStatus.CREATED.value

        task_response = await client.get(f"/tasks/{confirmation['task_id']}")
        assert task_response.status_code == 200
        task = task_response.json()
        assert task["status"] == ExternalStatus.CREATED.value
        assert task["internal_status"] == InternalStatus.CREATED.value
        assert task["metadata"]["intake_id"] == intake_id
        assert (
            task["metadata"]["confirmed_task_spec"]["metadata"]["intake_id"]
            == intake_id
        )
        assert task["metadata"]["confirmed_task_spec"]["metadata"][
            "planner_capability_hints"
        ] == ["sequence_generation", "structure_prediction"]
        assert task["metadata"]["scenario_gate"]["status"] == "allow"
        assert confirmation["scenario_gate"]["status"] == "allow"

        events_response = await client.get(f"/tasks/{confirmation['task_id']}/events")
        assert events_response.status_code == 200
        events = events_response.json()
        assert events[0]["event_type"] == "TASK_CREATED_FROM_CONFIRMED_INTAKE"
        assert events[0]["data"]["intake_id"] == intake_id
        assert events[0]["data"]["scenario_gate"]["status"] == "allow"

    async def test_task_intake_confirm_p1_unavailable_returns_draft_only(
        self,
        client: httpx.AsyncClient,
    ):
        """P1 必需能力不可用时不创建正式 TaskRecord。"""

        create_response = await client.post(
            "/task-intakes",
            json={
                "structured_fields": {
                    "task_kind": "motif_scaffold_design",
                    "motif_pattern": "RxxE",
                },
                "source": "web",
            },
        )
        assert create_response.status_code == 200
        intake_id = create_response.json()["intake_id"]

        confirm_response = await client.post(
            f"/task-intakes/{intake_id}/confirm",
            json={"confirmed_by": "tester", "acknowledged_warnings": []},
        )

        assert confirm_response.status_code == 200
        payload = confirm_response.json()
        assert payload["task_id"] is None
        assert payload["status"] == "draft_only"
        assert payload["scenario_gate"]["status"] == "draft_only"
        assert "motif_scaffolding" in payload["scenario_gate"]["blocked_hints"]
        assert TASK_STORE == {}

    async def test_task_intake_confirm_p2_unavailable_is_rejected(
        self,
        client: httpx.AsyncClient,
    ):
        """P2 必需能力不可用时返回 422 和 scenario_gate。"""

        create_response = await client.post(
            "/task-intakes",
            json={
                "structured_fields": {
                    "task_kind": "binding_design",
                    "objective_type": "stability",
                },
                "source": "web",
            },
        )
        assert create_response.status_code == 200
        intake_id = create_response.json()["intake_id"]

        confirm_response = await client.post(
            f"/task-intakes/{intake_id}/confirm",
            json={"confirmed_by": "tester", "acknowledged_warnings": []},
        )

        assert confirm_response.status_code == 422
        payload = confirm_response.json()
        assert payload["scenario_gate"]["status"] == "reject"
        assert "binding_design" in payload["scenario_gate"]["blocked_hints"]
        assert TASK_STORE == {}

    async def test_task_intake_confirm_missing_fields_returns_stable_error(
        self,
        client: httpx.AsyncClient,
    ):
        """缺少必填/条件必填字段时 confirm 返回稳定错误结构。"""

        create_response = await client.post(
            "/task-intakes",
            json={
                "structured_fields": {"task_kind": "binding_design"},
                "source": "web",
            },
        )
        assert create_response.status_code == 200
        intake_id = create_response.json()["intake_id"]

        confirm_response = await client.post(
            f"/task-intakes/{intake_id}/confirm",
            json={"confirmed_by": "tester", "acknowledged_warnings": []},
        )

        assert confirm_response.status_code == 422
        data = confirm_response.json()
        assert data["status"] == 422
        assert "missing required fields" in data["detail"]
        assert "objective_type" in data["missing_fields"]
        assert data["context"]["intake_id"] == intake_id

    async def test_task_intake_warn_requires_ack_before_task_creation(
        self,
        client: httpx.AsyncClient,
    ):
        """Safety warn 未 acknowledgement 时 confirm 返回 4xx，确认后创建正式 Task。"""

        create_response = await client.post(
            "/task-intakes",
            json={
                "structured_fields": {
                    "task_kind": "sequence_evaluation",
                    "objective_type": "stability",
                    "sequence": "ACDEFG",
                    "forbidden_motifs": ["CDE"],
                },
                "source": "web",
            },
        )
        assert create_response.status_code == 200
        intake = create_response.json()
        intake_id = intake["intake_id"]
        assert intake["safety_check"]["action"] == "warn"
        assert intake["safety_check"]["risk_flags"][0]["code"] == "FORBIDDEN_MOTIF_PRESENT"

        rejected = await client.post(
            f"/task-intakes/{intake_id}/confirm",
            json={"confirmed_by": "tester", "acknowledged_warnings": []},
        )

        assert rejected.status_code == 422
        rejected_payload = rejected.json()
        assert "--ack-warning" in rejected_payload["detail"]
        assert (
            rejected_payload["context"]["safety_check"]["risk_flags"][0]["code"]
            == "FORBIDDEN_MOTIF_PRESENT"
        )
        assert TASK_STORE == {}

        accepted = await client.post(
            f"/task-intakes/{intake_id}/confirm",
            json={
                "confirmed_by": "tester",
                "acknowledged_warnings": ["FORBIDDEN_MOTIF_PRESENT"],
            },
        )

        assert accepted.status_code == 200
        task = TASK_STORE[accepted.json()["task_id"]]
        assert task.metadata["confirmed_task_spec"]["metadata"]["safety_check"][
            "action"
        ] == "warn"
        assert task.metadata["confirmed_task_spec"]["metadata"][
            "acknowledged_warnings"
        ] == ["FORBIDDEN_MOTIF_PRESENT"]

    async def test_task_intake_block_cannot_confirm_task_creation(
        self,
        client: httpx.AsyncClient,
    ):
        """Safety block 不能通过 confirm 创建正式 Task。"""

        create_response = await client.post(
            "/task-intakes",
            json={
                "text": "design a toxin-like protein",
                "structured_fields": {
                    "task_kind": "de_novo_design",
                    "objective_type": "stability",
                    "length_range": [80, 120],
                },
                "source": "web",
            },
        )
        assert create_response.status_code == 200
        intake_id = create_response.json()["intake_id"]
        assert create_response.json()["safety_check"]["action"] == "block"

        confirm_response = await client.post(
            f"/task-intakes/{intake_id}/confirm",
            json={
                "confirmed_by": "tester",
                "acknowledged_warnings": ["HIGH_RISK_BIOFUNCTION_REQUEST"],
            },
        )

        assert confirm_response.status_code == 422
        assert "safety input precheck blocked" in confirm_response.json()["detail"]
        assert TASK_STORE == {}

    async def test_task_intake_cancel_records_intake_audit_only(
        self,
        client: httpx.AsyncClient,
    ):
        """取消 intake 只写入 intake 审计事件，不创建正式 Task。"""

        create_response = await client.post(
            "/task-intakes",
            json={
                "structured_fields": {
                    "task_kind": "de_novo_design",
                    "objective_type": "stability",
                    "length_range": [80, 120],
                },
                "source": "web",
            },
        )
        intake_id = create_response.json()["intake_id"]

        cancel_response = await client.post(
            f"/task-intakes/{intake_id}/cancel",
            json={"cancelled_by": "tester", "reason": "duplicate"},
        )

        assert cancel_response.status_code == 200
        data = cancel_response.json()
        assert data["status"] == "cancelled"
        assert data["audit_events"][-1]["event_type"] == "INTAKE_CANCELLED"
        assert TASK_STORE == {}

    @pytest.mark.parametrize(
        ("fields", "expected_message"),
        [
            (
                {
                    "task_kind": "de_novo_design",
                    "objective_type": "invalid",
                    "length_range": [90, 120],
                },
                "objective_type must be one of",
            ),
            (
                {
                    "task_kind": "de_novo_design",
                    "objective_type": "stability",
                    "length_range": [120, 90],
                },
                "length_range must be [min, max] integers",
            ),
            (
                {
                    "task_kind": "de_novo_design",
                    "objective_type": "stability",
                    "length_range": {"min": 90, "max": 120, "unit": "nt"},
                },
                "length_range unit must be amino-acid based",
            ),
            (
                {
                    "task_kind": "de_novo_design",
                    "objective_type": "stability",
                    "length_range": [90, 120],
                    "tools_allowed": ["not_a_tool"],
                },
                "tools_allowed contains unknown tool_id",
            ),
            (
                {
                    "task_kind": "de_novo_design",
                    "objective_type": "stability",
                    "length_range": [90, 120],
                    "initial_artifacts": [{"kind": "template", "path": "../x.pdb"}],
                },
                "initial_artifacts[0].path must be a safe relative path",
            ),
        ],
    )
    async def test_task_intake_rejects_invalid_contract_inputs(
        self,
        client: httpx.AsyncClient,
        fields: dict[str, object],
        expected_message: str,
    ):
        """非法 enum/tool_id/artifact ref/unit/range 均返回 4xx 稳定错误。"""

        response = await client.post(
            "/task-intakes",
            json={"structured_fields": fields, "source": "web"},
        )

        assert response.status_code == 422
        data = response.json()
        assert data["status"] == 422
        assert expected_message in json.dumps(data, ensure_ascii=False)
        assert "validation_errors" in data

    async def test_task_intake_patch_validates_without_mutating_on_error(
        self,
        client: httpx.AsyncClient,
    ):
        """PATCH 校验失败时返回稳定错误且不污染已保存 draft。"""

        create_response = await client.post(
            "/task-intakes",
            json={
                "structured_fields": {
                    "task_kind": "de_novo_design",
                    "objective_type": "stability",
                    "length_range": [90, 120],
                },
                "source": "web",
            },
        )
        intake_id = create_response.json()["intake_id"]

        patch_response = await client.patch(
            f"/task-intakes/{intake_id}",
            json={"fields": {"tools_allowed": ["missing_tool"]}},
        )

        assert patch_response.status_code == 422
        assert "tools_allowed" not in INTAKE_STORE[intake_id].draft.fields

    async def test_task_intake_can_be_read_and_requires_safety_ack(
        self,
        client: httpx.AsyncClient,
    ):
        """Task Builder 可读取 intake，并在 safety warn 时要求 acknowledgement。"""

        create_response = await client.post(
            "/task-intakes",
            json={
                "structured_fields": {
                    "task_kind": "de_novo_design",
                    "objective_type": "stability",
                    "length_range": [100, 140],
                    "safety_level": "S2",
                },
                "source": "web",
            },
        )
        assert create_response.status_code == 200
        intake_id = create_response.json()["intake_id"]

        get_response = await client.get(f"/task-intakes/{intake_id}")
        assert get_response.status_code == 200
        data = get_response.json()
        assert data["safety_check"]["action"] == "warn"
        assert data["safety_check"]["risk_flags"][0]["code"] == "SAFETY_INPUT_WARN"

        blocked_confirm = await client.post(
            f"/task-intakes/{intake_id}/confirm",
            json={"confirmed_by": "tester", "acknowledged_warnings": []},
        )
        assert blocked_confirm.status_code == 422
        assert "SAFETY_INPUT_WARN" in blocked_confirm.json()["detail"]

        confirm_response = await client.post(
            f"/task-intakes/{intake_id}/confirm",
            json={
                "confirmed_by": "tester",
                "acknowledged_warnings": ["SAFETY_INPUT_WARN"],
            },
        )
        assert confirm_response.status_code == 200
        assert confirm_response.json()["status"] == ExternalStatus.CREATED.value

    async def test_legacy_tasks_query_converges_to_intake(
        self,
        client: httpx.AsyncClient,
    ):
        """旧 /tasks query 自由文本入口只返回 intake，不直接进入 Planner。"""

        response = await client.post(
            "/tasks",
            json={"query": "please design around 120 aa stable protein"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["needs_confirmation"] is True
        assert data["status"] in {"collecting", "needs_confirmation"}
        assert data["intake_id"] in INTAKE_STORE
        assert TASK_STORE == {}

    async def test_tasks_create_rejects_mixed_creation_modes(
        self,
        client: httpx.AsyncClient,
    ):
        """正式 Task 创建入口应明确选择一种输入模式。"""

        response = await client.post(
            "/tasks",
            json={
                "goal": "direct legacy goal",
                "confirmed_task_spec": {
                    "goal": "confirmed goal",
                    "metadata": {
                        "intake_id": "intake_mixed",
                        "field_registry_version": "task-intake.v1",
                        "support_level": "P0",
                        "confirmed_by": "tester",
                        "input_mode": "structured_with_confirmation",
                        "acknowledged_warnings": [],
                    },
                },
            },
        )

        assert response.status_code == 422
        assert "choose exactly one" in response.text

    async def test_legacy_intent_draft_maps_to_task_intake_finalize(
        self,
        client: httpx.AsyncClient,
    ):
        """旧 IntentDraft create/clarification/finalize 投影到 Task Intake。"""

        create_response = await client.post(
            "/intent-drafts",
            json={
                "text": "design de novo stable protein around 120 aa",
                "source": "legacy",
            },
        )
        assert create_response.status_code == 200
        intent_draft_id = create_response.json()["intent_draft_id"]

        clarification_response = await client.post(
            f"/intent-drafts/{intent_draft_id}/clarification",
            json={
                "fields": {
                    "task_kind": "de_novo_design",
                    "objective_type": "stability",
                    "length_range": [100, 140],
                },
                "updated_by": "tester",
            },
        )
        assert clarification_response.status_code == 200
        assert clarification_response.json()["intake_id"] == intent_draft_id

        finalize_response = await client.post(
            f"/intent-drafts/{intent_draft_id}/finalize",
            json={"confirmed_by": "tester", "acknowledged_warnings": []},
        )
        assert finalize_response.status_code == 200
        data = finalize_response.json()
        assert data["intake_id"] == intent_draft_id
        assert data["status"] == ExternalStatus.CREATED.value

        task = TASK_STORE[data["task_id"]]
        assert task.status == ExternalStatus.CREATED
        assert task.metadata["intake_id"] == intent_draft_id
        assert task.metadata["intent_draft_id"] == intent_draft_id
        assert task.metadata["scenario_gate"]["status"] == "allow"
        assert data["scenario_gate"]["status"] == "allow"

    async def test_post_tasks_confirmed_spec_p2_rejected(
        self,
        client: httpx.AsyncClient,
    ):
        """兼容 /tasks confirmed_task_spec 分支也必须执行 scenario gate。"""

        response = await client.post(
            "/tasks",
            json={
                "confirmed_task_spec": {
                    "goal": "binding_design for stability",
                    "constraints": {
                        "task_kind": "binding_design",
                    },
                    "metadata": {
                        "support_level": "P2",
                        "planner_capability_hints": [
                            "binding_design",
                            "docking_scoring",
                        ],
                        "planner_capability_hint_details": [
                            {"name": "binding_design", "required": True},
                            {
                                "name": "docking_scoring",
                                "io_type": "structure_ligand_to_binding_score",
                                "required": True,
                            },
                        ],
                    },
                }
            },
        )

        assert response.status_code == 422
        payload = response.json()
        assert payload["scenario_gate"]["status"] == "reject"
        assert TASK_STORE == {}

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

    @pytest.mark.parametrize(
        ("action_type", "external_status", "internal_status"),
        [
            (
                PendingActionType.PLAN_CONFIRM,
                ExternalStatus.WAITING_PLAN_CONFIRM,
                InternalStatus.WAITING_PLAN_CONFIRM,
            ),
            (
                PendingActionType.PATCH_CONFIRM,
                ExternalStatus.WAITING_PATCH_CONFIRM,
                InternalStatus.WAITING_PATCH,
            ),
            (
                PendingActionType.REPLAN_CONFIRM,
                ExternalStatus.WAITING_REPLAN_CONFIRM,
                InternalStatus.WAITING_REPLAN,
            ),
        ],
    )
    async def test_pending_action_detail_exposes_runtime_decision_context(
        self,
        client: httpx.AsyncClient,
        action_type: PendingActionType,
        external_status: ExternalStatus,
        internal_status: InternalStatus,
    ):
        """Pending Review API 应暴露推荐理由、证据、运行时摘要和恢复语义。"""
        task_id = f"task_runtime_context_{action_type.value}"
        pending_action_id = f"pa_runtime_context_{action_type.value}"
        step = PlanStep(id="S1", tool="esmfold", inputs={}, metadata={})
        if action_type == PendingActionType.PATCH_CONFIRM:
            payload = PlanPatch(
                task_id=task_id,
                operations=[
                    PlanPatchOp(op="replace_step", target="S1", step=step),
                ],
                metadata={},
            )
        else:
            payload = Plan(task_id=task_id, steps=[step], constraints={}, metadata={})
        candidate_runtime_state = {
            "p_success": 0.63,
            "p_structural_failure": 0.21,
            "recovery_margin": 0.34,
            "expected_remaining_cost": 1.4,
            "evidence_sufficiency": 0.72,
        }
        pending_runtime_state = {
            "p_success": 0.61,
            "p_structural_failure": 0.24,
            "recovery_margin": 0.3,
            "expected_remaining_cost": 1.5,
            "evidence_sufficiency": 0.68,
        }

        pending_action = PendingAction(
            pending_action_id=pending_action_id,
            task_id=task_id,
            action_type=action_type,
            status=PendingActionStatus.PENDING,
            candidates=[
                PendingActionCandidate(
                    candidate_id="cand_recommended",
                    payload=payload,
                    summary="recommended candidate",
                    explanation="best runtime tradeoff",
                    risk_level="low",
                    cost_estimate="medium",
                    score_breakdown={"overall": 0.91, "risk": 0.82},
                    metadata={
                        "expected_effect": "raise success probability",
                        "affected_steps": ["S1"],
                        "recovery_semantics": "preserve completed prefix",
                        "runtime_state_summary": candidate_runtime_state,
                        "static_score": {
                            "value": 0.82,
                            "source": "score_breakdown.overall.static.v1",
                        },
                        "runtime_adjustment": {
                            "value": 0.07,
                            "source": "planner.runtime_adjustment.patch_local.v1",
                            "formula_version": "v1",
                        },
                        "final_score": {
                            "value": 0.89,
                            "source": "static_score+runtime_adjustment.patch_local.v1",
                        },
                        "default_recommendation_reason": {
                            "code": "runtime_ranked_first",
                            "message": "highest runtime-adjusted score",
                        },
                        "evidence_refs": [
                            {"kind": "event", "ref": "WAITING_ENTER#1"}
                        ],
                    },
                )
            ],
            default_recommendation="cand_recommended",
            explanation="runtime gate requires confirmation",
            metadata={
                "workflow_action": "patch_local",
                "workflow_action_evidence": {
                    "runtime_state_summary": pending_runtime_state,
                    "default_recommendation_reason": {
                        "code": "runtime_gate",
                        "message": "runtime gate selected patch_local",
                    },
                    "selected_action": "patch_local",
                    "budget_pressure": 0.74,
                    "evidence_sufficiency": 0.68,
                    "action_utilities": {
                        "patch_local": {
                            "action": "patch_local",
                            "utility": 0.81,
                            "budget_pressure": 0.74,
                            "intervention_value": 0.25,
                            "source": "runtime_evaluator.action_utility.v1",
                        },
                    },
                    "evidence_refs": [
                        {"kind": "runtime_state", "ref": "snapshot.latest"}
                    ],
                },
            },
        )
        TASK_STORE[task_id] = TaskRecord(
            id=task_id,
            status=external_status,
            internal_status=internal_status,
            goal="runtime context endpoint test",
            constraints={},
            metadata={},
            plan=None,
            design_result=None,
            pending_action=pending_action,
        )

        response = await client.get(f"/pending-actions/{pending_action_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["default_suggestion"] == "cand_recommended"
        assert data["runtime_state_summary"]["p_success"] == pytest.approx(0.61)
        assert data["workflow_action_reason"] == "runtime gate selected patch_local"
        assert data["evidence_refs"][0]["ref"] == "snapshot.latest"
        theory = data["theory_objects"]
        assert theory["static_score"]["value"] == pytest.approx(0.82)
        assert theory["runtime_adjustment"]["value"] == pytest.approx(0.07)
        assert theory["final_score"]["value"] == pytest.approx(0.89)
        assert theory["selected_action"] == "patch_local"
        assert theory["action_utility"]["utility"] == pytest.approx(0.81)
        assert theory["evidence_sufficiency"] == pytest.approx(0.68)
        assert theory["budget_pressure"] == pytest.approx(0.74)
        candidate_theory = data["candidates"][0]["theory_objects"]
        assert candidate_theory["selected_action"] == "patch_local"
        assert "factors" not in theory["runtime_adjustment"]
        assert data["score_breakdown"]["overall"] == pytest.approx(0.91)

        candidate = data["candidates"][0]
        assert candidate["expected_effect"] == "raise success probability"
        assert candidate["affected_steps"] == ["S1"]
        assert candidate["recovery_semantics"] == "preserve completed prefix"
        assert candidate["runtime_state_summary"]["p_success"] == pytest.approx(0.63)
        assert candidate["workflow_action_reason"] == "highest runtime-adjusted score"
        assert candidate["evidence_refs"][0]["ref"] == "WAITING_ENTER#1"

    async def test_ui_routes_and_static_assets_available(
        self, client: httpx.AsyncClient
    ):
        """React 前端宿主页面和静态资源可访问。"""
        dashboard_response = await client.get("/ui")
        assert dashboard_response.status_code == 200
        assert "蛋白质设计操作工作台" in dashboard_response.text
        assert 'id="root"' in dashboard_response.text
        assert '"/static/web/assets/app.js"' in dashboard_response.text
        assert '"view": "dashboard"' in dashboard_response.text

        task_view_response = await client.get("/ui/tasks/task_demo_001")
        assert task_view_response.status_code == 200
        assert '"taskId": "task_demo_001"' in task_view_response.text
        assert '"view": "task_detail"' in task_view_response.text

        app_js = Path("src/api/static/web/assets/app.js")
        assert app_js.exists()
        static_text = app_js.read_text(encoding="utf-8")
        assert "/pending-actions" in static_text
        assert "/capabilities/readiness" in static_text
        assert "提交决策" in static_text
        assert "/task-intakes/schema" in static_text
        assert "任务构建器" in static_text
        assert "实验性" in static_text
        assert "暂不支持" in static_text
        assert "当前没有可用的 Schema 选项" in static_text

        timeline_response = await client.get("/ui/tasks/task_demo_001/events")
        assert timeline_response.status_code == 200
        assert '"view": "event_timeline"' in timeline_response.text

        style_css = Path("src/api/static/web/assets/style.css")
        assert style_css.exists()
        assert "--surface" in style_css.read_text(encoding="utf-8")

        builder_response = await client.get("/ui/task-builder")
        assert builder_response.status_code == 200
        assert '"view": "task_builder"' in builder_response.text
        assert '"/static/web/assets/app.js"' in builder_response.text

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
