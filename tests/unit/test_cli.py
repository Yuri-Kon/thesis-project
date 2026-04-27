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
