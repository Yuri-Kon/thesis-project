from __future__ import annotations

import builtins
import json
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
                    "design_result": {
                        "metadata": {
                            "structure_similarity": {
                                "hit_count": 1,
                                "top_hit": {"hit_id": "1abc_A", "tm_score": 0.82},
                            }
                        }
                    },
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
    assert '"structure_similarity"' in output
    assert '"hit_id": "1abc_A"' in output
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
                    "structure_similarity": {
                        "hit_count": 1,
                        "top_hit": {"hit_id": "1abc_A", "tm_score": 0.82},
                        "artifact_refs": [
                            {"kind": "foldseek_tabular", "path": "output/foldseek.m8"}
                        ],
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
    assert '"structure_similarity"' in output
    assert '"hit_id": "1abc_A"' in output


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


def test_intake_parse_json_outputs_profile(monkeypatch, capsys) -> None:
    """design intake parse --json 应输出 intake 与同字段 profile。"""

    seen: dict[str, Any] = {}

    def fake_post(url: str, json: dict[str, Any], timeout: float) -> _FakeResponse:
        assert timeout == 10.0
        seen["url"] = url
        seen["json"] = json
        return _FakeResponse(
            {
                "intake_id": "intake_parse",
                "status": "collecting",
                "draft": {
                    "extraction_mode": "rule_extract",
                    "fields": {
                        "objective_type": {
                            "value": "binding",
                            "source": "llm_extract",
                            "confidence": 0.72,
                            "source_span": "binding",
                            "confirmed": False,
                            "warnings": [],
                        }
                    },
                    "extraction_errors": [],
                },
                "missing_required_fields": ["goal_summary"],
                "ambiguous_fields": ["objective_type"],
                "unmapped_text": ["extra phrase"],
                "warnings": [],
                "safety_check": {"action": "ok", "risk_flags": []},
            }
        )

    monkeypatch.setattr(cli.httpx, "post", fake_post)

    code = cli.main(
        [
            "--api-base-url",
            "http://api.test",
            "intake",
            "parse",
            "--text",
            "design binding protein",
            "--json",
        ]
    )

    assert code == 0
    assert seen["url"] == "http://api.test/task-intakes"
    assert seen["json"]["text"] == "design binding protein"
    output = capsys.readouterr().out
    assert '"intake_id": "intake_parse"' in output
    assert '"pending_fields": [' in output
    assert '"low_confidence_fields": [' in output


def test_intake_show_human_outputs_defaults_and_safety(monkeypatch, capsys) -> None:
    """design intake show 应展示字段、默认值、warning 与 unmapped_text。"""

    def fake_get(url: str, timeout: float) -> _FakeResponse:
        assert timeout == 10.0
        if url.endswith("/task-intakes/intake_show"):
            return _FakeResponse(
                {
                    "intake_id": "intake_show",
                    "status": "needs_confirmation",
                    "draft": {
                        "extraction_mode": "rule_extract",
                        "fields": {
                            "goal_summary": {
                                "value": "design stable protein",
                                "source": "user_explicit",
                                "confidence": 1.0,
                                "source_span": None,
                                "confirmed": True,
                                "warnings": [],
                            }
                        },
                        "extraction_errors": [],
                    },
                    "missing_required_fields": [],
                    "ambiguous_fields": [],
                    "unmapped_text": ["leftover"],
                    "warnings": ["motif present"],
                    "safety_check": {
                        "action": "warn",
                        "risk_flags": [
                            {
                                "level": "warn",
                                "code": "FORBIDDEN_MOTIF_PRESENT",
                                "message": "motif present",
                            }
                        ],
                    },
                }
            )
        if url.endswith("/task-intakes/schema"):
            return _FakeResponse(
                {
                    "fields": {
                        "task_kind": {"default": "de_novo_design"},
                        "goal_summary": {"default": None},
                    }
                }
            )
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(cli.httpx, "get", fake_get)

    code = cli.main(
        [
            "--api-base-url",
            "http://api.test",
            "intake",
            "show",
            "intake_show",
        ]
    )

    assert code == 0
    output = capsys.readouterr().out
    assert "confirmed_fields: goal_summary" in output
    assert 'default_fields: {"task_kind": "de_novo_design"}' in output
    assert "warnings: motif present" in output
    assert "unmapped_text: leftover" in output
    assert "safety_risk: warn FORBIDDEN_MOTIF_PRESENT motif present" in output


def test_intake_set_accepts_schema_derived_field_flags(monkeypatch, capsys) -> None:
    """design intake set 可按 /task-intakes/schema 暴露的 CLI flag 更新字段。"""

    seen: dict[str, Any] = {}

    def fake_get(url: str, timeout: float) -> _FakeResponse:
        assert timeout == 10.0
        if url.endswith("/task-intakes/schema"):
            return _FakeResponse(
                {
                    "cli_arguments": [
                        {"field": "objective_type", "flag": "--objective-type"},
                        {"field": "length_range", "flag": "--length-range"},
                    ]
                }
            )
        raise AssertionError(f"unexpected URL: {url}")

    def fake_patch(url: str, json: dict[str, Any], timeout: float) -> _FakeResponse:
        assert timeout == 10.0
        seen["url"] = url
        seen["json"] = json
        return _FakeResponse(
            {
                "intake_id": "intake_set",
                "status": "needs_confirmation",
                "draft": {"fields": {}, "extraction_errors": []},
                "missing_required_fields": [],
                "ambiguous_fields": [],
                "unmapped_text": [],
                "warnings": [],
                "safety_check": {"action": "ok", "risk_flags": []},
            }
        )

    monkeypatch.setattr(cli.httpx, "get", fake_get)
    monkeypatch.setattr(cli.httpx, "patch", fake_patch)

    code = cli.main(
        [
            "--api-base-url",
            "http://api.test",
            "intake",
            "set",
            "intake_set",
            "--objective-type",
            "stability",
            "--length-range=[100,140]",
            "--json",
        ]
    )

    assert code == 0
    assert seen["url"] == "http://api.test/task-intakes/intake_set"
    assert seen["json"]["fields"] == {
        "objective_type": "stability",
        "length_range": [100, 140],
    }
    assert '"next_action": "confirm"' in capsys.readouterr().out


def test_intake_confirm_success_outputs_task_id_and_created(monkeypatch, capsys) -> None:
    """design intake confirm 成功后输出 task_id 与 CREATED 状态。"""

    def fake_post(url: str, json: dict[str, Any], timeout: float) -> _FakeResponse:
        assert timeout == 10.0
        assert json["acknowledged_warnings"] == ["WARN_1"]
        return _FakeResponse(
            {
                "intake_id": "intake_done",
                "task_id": "task_done",
                "status": "CREATED",
                "confirmed_task_spec": {"goal": "design"},
            }
        )

    monkeypatch.setattr(cli.httpx, "post", fake_post)

    code = cli.main(
        [
            "--api-base-url",
            "http://api.test",
            "intake",
            "confirm",
            "intake_done",
            "--ack-warning",
            "WARN_1",
        ]
    )

    assert code == 0
    output = capsys.readouterr().out
    assert "task_id: task_done" in output
    assert "status: CREATED" in output


def test_intake_confirm_warn_error_shows_ack_warning_path(monkeypatch, capsys) -> None:
    """CLI confirm 在 Safety warn 未确认时提示 --ack-warning。"""

    def fake_post(url: str, json: dict[str, Any], timeout: float) -> cli.httpx.Response:
        assert timeout == 10.0
        assert json["acknowledged_warnings"] == []
        request = cli.httpx.Request("POST", url)
        return cli.httpx.Response(
            422,
            request=request,
            json={
                "status": 422,
                "detail": "safety warnings require acknowledgement before confirm",
                "context": {
                    "safety_check": {
                        "action": "warn",
                        "risk_flags": [
                            {
                                "level": "warn",
                                "code": "FORBIDDEN_MOTIF_PRESENT",
                                "message": "motif present",
                            }
                        ],
                    }
                },
            },
        )

    monkeypatch.setattr(cli.httpx, "post", fake_post)

    code = cli.main(
        [
            "--api-base-url",
            "http://api.test",
            "intake",
            "confirm",
            "intake_warn",
        ]
    )

    assert code == 2
    err = capsys.readouterr().err
    assert "--ack-warning FORBIDDEN_MOTIF_PRESENT" in err


def test_submit_spec_confirm_posts_confirmed_task_spec(monkeypatch, capsys, tmp_path) -> None:
    """design submit --spec task_spec.json --confirm 应创建 CREATED task。"""

    spec_path = tmp_path / "task_spec.json"
    spec_path.write_text(
        json.dumps(
            {
                "goal": "design stable protein",
                "objective": {"objective_type": "stability"},
                "inputs": {},
                "constraints": {},
                "initial_artifacts": [],
                "metadata": {"intake_id": "intake_spec"},
            }
        ),
        encoding="utf-8",
    )
    seen: dict[str, Any] = {}

    def fake_post(url: str, json: dict[str, Any], timeout: float) -> _FakeResponse:
        assert timeout == 10.0
        seen["url"] = url
        seen["json"] = json
        return _FakeResponse(
            {
                "id": "task_spec",
                "status": "CREATED",
            }
        )

    monkeypatch.setattr(cli.httpx, "post", fake_post)

    code = cli.main(
        [
            "--api-base-url",
            "http://api.test",
            "submit",
            "--spec",
            str(spec_path),
            "--confirm",
            "--json",
        ]
    )

    assert code == 0
    assert seen["url"] == "http://api.test/tasks"
    assert seen["json"]["confirmed_task_spec"]["goal"] == "design stable protein"
    output = capsys.readouterr().out
    assert '"task_id": "task_spec"' in output
    assert '"status": "CREATED"' in output


def test_submit_spec_requires_confirm(tmp_path, capsys) -> None:
    """--spec 路径必须显式 --confirm。"""

    spec_path = tmp_path / "task_spec.json"
    spec_path.write_text('{"goal": "design"}', encoding="utf-8")

    code = cli.main(["submit", "--spec", str(spec_path)])

    assert code == 2
    assert "submit --spec requires --confirm" in capsys.readouterr().err


def test_submit_spec_rejects_invalid_confirmed_task_spec(tmp_path, capsys) -> None:
    """--spec 文件必须符合 ConfirmedTaskSpec schema。"""

    spec_path = tmp_path / "task_spec.json"
    spec_path.write_text('{"goal": "design", "initial_artifacts": {}}', encoding="utf-8")

    code = cli.main(["submit", "--spec", str(spec_path), "--confirm"])

    assert code == 2
    assert "ConfirmedTaskSpec schema" in capsys.readouterr().err


def test_submit_interactive_uses_schema_questions(monkeypatch, capsys) -> None:
    """design submit --interactive 从 /task-intakes/schema 派生问题并创建 intake。"""

    answers = iter(["design stable protein", "stability", ""])
    seen: dict[str, Any] = {}

    def fake_get(url: str, timeout: float) -> _FakeResponse:
        assert timeout == 10.0
        if url.endswith("/task-intakes/schema"):
            return _FakeResponse(
                {
                    "cli_questions": [
                        {"field": "goal_summary", "prompt": "Goal"},
                        {"field": "objective_type", "prompt": "Objective"},
                        {"field": "sequence", "prompt": "Sequence"},
                    ]
                }
            )
        raise AssertionError(f"unexpected URL: {url}")

    def fake_post(url: str, json: dict[str, Any], timeout: float) -> _FakeResponse:
        assert timeout == 10.0
        seen["url"] = url
        seen["json"] = json
        return _FakeResponse(
            {
                "intake_id": "intake_interactive",
                "status": "needs_confirmation",
                "draft": {"fields": {}, "extraction_errors": []},
                "missing_required_fields": [],
                "ambiguous_fields": [],
                "unmapped_text": [],
                "warnings": [],
                "safety_check": {"action": "ok", "risk_flags": []},
            }
        )

    monkeypatch.setattr(cli.httpx, "get", fake_get)
    monkeypatch.setattr(cli.httpx, "post", fake_post)
    monkeypatch.setattr(builtins, "input", lambda _prompt: next(answers))

    code = cli.main(
        [
            "--api-base-url",
            "http://api.test",
            "submit",
            "--interactive",
        ]
    )

    assert code == 0
    assert seen["url"] == "http://api.test/task-intakes"
    assert seen["json"]["structured_fields"] == {
        "goal_summary": "design stable protein",
        "objective_type": "stability",
    }
    assert "intake_id: intake_interactive" in capsys.readouterr().out


def test_preflight_command_prompts_migration(capsys) -> None:
    """旧 preflight CLI 入口提示迁移到 design intake。"""

    code = cli.main(["preflight"])

    assert code == 2
    assert "design intake" in capsys.readouterr().err
