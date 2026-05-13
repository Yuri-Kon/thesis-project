from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module():
    module_path = Path(__file__).resolve().parents[2] / "scripts" / "run_demo_audit.py"
    spec = importlib.util.spec_from_file_location("demo_audit", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_issue151_markdown_templates_are_chinese(tmp_path: Path) -> None:
    module = _load_module()
    scenario = module.DemoScenario(
        name="six_stage_hitl_replay",
        pytest_target="tests/integration/test_s6_control_layer_e2e.py::test_case",
        task_id="task_demo_151",
        replay_filename="replay.md",
    )
    events = [
        {"event_type": "WAITING_ENTER", "ts": "2026-03-19T09:00:00+00:00", "summary": "Enter waiting state"},
        {"event_type": "DECISION_APPLIED", "ts": "2026-03-19T09:00:01+00:00", "summary": "Decision applied"},
        {"event_type": "WAITING_EXIT", "ts": "2026-03-19T09:00:02+00:00", "summary": "Exit waiting state"},
    ]

    replay = module.build_replay_markdown(scenario, events, tmp_path / "task_demo_151.jsonl")
    release = module.build_release_validation_markdown(
        {
            "audit_chain_pendingaction_decision_eventlog": True,
            "tool_fallback_switch_recorded": True,
            "e2e_flow_reaches_done": True,
        }
    )

    assert "# 回放记录：" in replay
    assert "## 事件序列" in replay
    assert "## 检查点" in replay
    assert "# 发布验证（Demo Audit）" in release
    assert "## 范围" in release
    assert "## 命令集合" in release
    assert "## 门禁结果" in release
    assert "## 已知问题" in release
