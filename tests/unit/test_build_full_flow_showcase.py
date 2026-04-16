from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_module():
    module_path = Path(__file__).resolve().parents[2] / "scripts" / "build_full_flow_showcase.py"
    spec = importlib.util.spec_from_file_location("full_showcase", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_showcase_bundle_writes_manifest_and_guide(tmp_path: Path) -> None:
    module = _load_module()

    result = module.build_showcase_bundle(
        output_dir=tmp_path,
        api_port=18000,
        hitl_port=18012,
        prepare=False,
    )

    manifest = json.loads(result["manifest"].read_text(encoding="utf-8"))
    guide = result["guide"].read_text(encoding="utf-8")

    assert manifest["servers"]["api_demo"]["url_docs"] == "http://127.0.0.1:18000/docs"
    assert manifest["servers"]["hitl_compare"]["url_task"] == "http://127.0.0.1:18012/ui/tasks/task_demo_142"
    assert "全流程展示操作手册" in guide
    assert "关键设计点检查清单" in guide
    assert "reports/w12-issue-174/midterm_experiment_chapter.md" in guide
