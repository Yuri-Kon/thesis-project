from __future__ import annotations

from typing import Any

import src.cli as cli


class _FakeResponse:
    def __init__(self, payload: dict[str, Any] | list[dict[str, Any]]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any] | list[dict[str, Any]]:
        return self._payload


def test_task_show_json_includes_readiness_summary(monkeypatch, capsys) -> None:
    """CLI JSON 输出应包含同源 capability readiness 摘要。"""

    def fake_get(url: str, timeout: float) -> _FakeResponse:
        assert timeout == 10.0
        if url.endswith("/tasks/task_cli"):
            return _FakeResponse(
                {
                    "id": "task_cli",
                    "status": "WAITING_PLAN_CONFIRM",
                    "internal_status": "WAITING_PLAN_CONFIRM",
                    "goal": "design",
                }
            )
        if url.endswith("/capabilities/readiness"):
            return _FakeResponse(
                [
                    {
                        "capability_id": "structure_prediction",
                        "status": "degraded",
                        "reason": "remote endpoint unavailable",
                        "degraded_reasons": ["esmfold: remote_unreachable"],
                        "suggested_recovery": "Start remote services.",
                    }
                ]
            )
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(cli.httpx, "get", fake_get)

    code = cli.main(
        [
            "--api-base-url",
            "http://api.test",
            "task",
            "show",
            "task_cli",
            "--json",
        ]
    )

    assert code == 0
    output = capsys.readouterr().out
    assert '"readiness_summary"' in output
    assert '"capability_id": "structure_prediction"' in output
    assert '"suggested_recovery": "Start remote services."' in output


def test_report_show_json_exposes_objective_scoring(monkeypatch, capsys) -> None:
    """design report show --json 应输出 objective scoring 报告结构。"""

    def fake_get(url: str, timeout: float) -> _FakeResponse:
        assert timeout == 10.0
        if url.endswith("/tasks/task_report/report"):
            return _FakeResponse(
                {
                    "task_id": "task_report",
                    "report_path": "output/reports/task_report.json",
                    "scores": {"objective_score": 0.77},
                    "objective_scoring": {
                        "top_k": [
                            {"candidate_id": "cand_a", "objective_score": 0.77}
                        ],
                        "rank_reason": "cand_a ranks by objective_score=0.770",
                    },
                    "metadata": {},
                }
            )
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(cli.httpx, "get", fake_get)

    code = cli.main(
        [
            "--api-base-url",
            "http://api.test",
            "report",
            "show",
            "task_report",
            "--json",
        ]
    )

    assert code == 0
    output = capsys.readouterr().out
    assert '"objective_score": 0.77' in output
    assert '"rank_reason": "cand_a ranks by objective_score=0.770"' in output


def test_pending_show_human_outputs_execution_mode(monkeypatch, capsys) -> None:
    """pending show 应输出执行通道与远程失败恢复提示。"""

    def fake_get(url: str, timeout: float) -> _FakeResponse:
        assert timeout == 10.0
        if url.endswith("/pending-actions/pa_cli"):
            return _FakeResponse(
                {
                    "pending_action_id": "pa_cli",
                    "task_id": "task_cli",
                    "action_type": "patch_confirm",
                    "default_suggestion": "cand_openfold_rest",
                    "workflow_action_reason": "patch lowers failure risk",
                    "runtime_state_summary": {"p_success": 0.58},
                    "evidence_refs": [{"kind": "event", "ref": "WAITING_ENTER#1"}],
                    "candidates": [
                        {
                            "candidate_id": "cand_openfold_rest",
                            "is_default": True,
                            "summary": "Use OpenFold3 REST patch",
                            "risk_level": "low",
                            "cost_estimate": "medium",
                            "expected_effect": "recover failed structure step",
                            "affected_steps": ["S2"],
                            "recovery_semantics": "patch_local",
                            "score_breakdown": {"overall": 0.82},
                            "tool": {
                                "tool_id": "openfold",
                                "adapter_id": "openfold",
                                "execution_mode": "openfold3_rest",
                                "endpoint_type": "rest",
                                "remote_job_id": "of3_job_1",
                                "failure_code": "REMOTE_JOB_FAILED",
                                "recovery_hint": "Inspect OpenFold3 REST logs.",
                                "readiness_status": "degraded",
                            },
                        }
                    ],
                }
            )
        if url.endswith("/capabilities/readiness"):
            return _FakeResponse([])
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(cli.httpx, "get", fake_get)

    code = cli.main(
        [
            "--api-base-url",
            "http://api.test",
            "pending",
            "show",
            "pa_cli",
        ]
    )

    assert code == 0
    output = capsys.readouterr().out
    assert "execution_mode=openfold3_rest" in output
    assert "remote_job_id=of3_job_1" in output
    assert "failure_code=REMOTE_JOB_FAILED" in output
    assert "recovery=Inspect OpenFold3 REST logs." in output
    assert "recommendation: patch lowers failure risk" in output
    assert "runtime_state_summary:" in output
    assert "evidence_refs: 1" in output
    assert "summary=Use OpenFold3 REST patch" in output
    assert "risk=low" in output
    assert "cost=medium" in output
    assert "expected_effect=recover failed structure step" in output
    assert "affected_steps=S2" in output
    assert "recovery_semantics=patch_local" in output
    assert "candidate_score: cand_openfold_rest" in output


def test_timeline_show_human_outputs_execution_mode(monkeypatch, capsys) -> None:
    """timeline show 应输出 execution mode 与 endpoint 上下文。"""

    def fake_get(url: str, timeout: float) -> _FakeResponse:
        assert timeout == 10.0
        if url.endswith("/tasks/task_cli/events"):
            return _FakeResponse(
                [
                    {
                        "event_type": "STEP_FAILED",
                        "ts": "2026-04-27T00:00:00+00:00",
                        "step_id": "S2",
                        "tool_id": "openfold",
                        "adapter_id": "openfold",
                        "execution_mode": "openfold3_rest",
                        "endpoint_type": "rest",
                        "remote_job_id": "of3_job_1",
                        "failure_code": "REMOTE_JOB_FAILED",
                        "recovery_hint": "Inspect OpenFold3 REST logs.",
                        "summary": "Step failed (S2)",
                    }
                ]
            )
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(cli.httpx, "get", fake_get)

    code = cli.main(
        [
            "--api-base-url",
            "http://api.test",
            "timeline",
            "show",
            "task_cli",
        ]
    )

    assert code == 0
    output = capsys.readouterr().out
    assert "tool=openfold" in output
    assert "adapter=openfold" in output
    assert "execution_mode=openfold3_rest" in output
    assert "endpoint=rest" in output


def test_intake_create_json_posts_task_intake_payload(monkeypatch, capsys) -> None:
    """design intake create 应调用 /task-intakes 并输出 intake_id。"""

    seen: dict[str, Any] = {}

    def fake_post(url: str, json: dict[str, Any], timeout: float) -> _FakeResponse:
        assert timeout == 10.0
        seen["url"] = url
        seen["json"] = json
        return _FakeResponse(
            {
                "intake_id": "intake_cli",
                "status": "needs_confirmation",
                "draft": {},
                "missing_required_fields": [],
                "ambiguous_fields": [],
                "unmapped_text": [],
                "warnings": [],
            }
        )

    monkeypatch.setattr(cli.httpx, "post", fake_post)

    code = cli.main(
        [
            "--api-base-url",
            "http://api.test",
            "intake",
            "create",
            "--text",
            "design stable protein",
            "--field",
            "length_range=[100,140]",
            "--json",
        ]
    )

    assert code == 0
    assert seen["url"] == "http://api.test/task-intakes"
    assert seen["json"]["structured_fields"]["length_range"] == [100, 140]
    output = capsys.readouterr().out
    assert '"intake_id": "intake_cli"' in output


def test_preflight_command_prompts_migration(capsys) -> None:
    """旧 preflight CLI 入口提示迁移到 design intake。"""

    code = cli.main(["preflight"])

    assert code == 2
    assert "design intake" in capsys.readouterr().err
