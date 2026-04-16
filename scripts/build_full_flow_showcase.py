#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = Path("reports/showcase")
UV_CACHE_DIR = "/tmp/uv-cache"


def _run(cmd: list[str]) -> None:
    env = os.environ.copy()
    env["UV_CACHE_DIR"] = UV_CACHE_DIR
    completed = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"Command failed ({' '.join(cmd)}):\nSTDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
        )


def _artifact_entry(path: str, *, role: str) -> dict[str, Any]:
    resolved = REPO_ROOT / path
    return {
        "path": path,
        "exists": resolved.exists(),
        "role": role,
    }


def build_showcase_manifest(*, api_port: int, hitl_port: int) -> dict[str, Any]:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "goal": "用于展示 API、HITL、审计回放、恢复机制与实验报告证据的全流程演示包。",
        "servers": {
            "api_demo": {
                "command": f"UV_CACHE_DIR={UV_CACHE_DIR} uv run python scripts/run_demo.py --port {api_port} --no-smoke-test",
                "url_docs": f"http://127.0.0.1:{api_port}/docs",
                "url_health": f"http://127.0.0.1:{api_port}/health",
                "url_dashboard": f"http://127.0.0.1:{api_port}/ui",
            },
            "hitl_compare": {
                "command": f"UV_CACHE_DIR={UV_CACHE_DIR} uv run python examples/run_hitl_candidate_ui_demo.py --serve --port {hitl_port}",
                "url_task": f"http://127.0.0.1:{hitl_port}/ui/tasks/task_demo_142",
                "url_events": f"http://127.0.0.1:{hitl_port}/ui/tasks/task_demo_142/events",
                "url_pending_action": f"http://127.0.0.1:{hitl_port}/pending-actions/pa_demo_142",
            },
        },
        "prepare_commands": [
            f"UV_CACHE_DIR={UV_CACHE_DIR} uv run python scripts/run_demo.py --port {api_port} --exit-after-smoke",
            f"UV_CACHE_DIR={UV_CACHE_DIR} uv run python scripts/run_w12_issue151_demo_audit.py",
            f"UV_CACHE_DIR={UV_CACHE_DIR} uv run python scripts/generate_w12_issue174_midterm_pack.py",
            f"UV_CACHE_DIR={UV_CACHE_DIR} uv run python scripts/generate_w12_issue152_release_pack.py",
        ],
        "design_points": [
            {
                "name": "FSM 与 HITL 暂停/恢复",
                "demo_entry": f"http://127.0.0.1:{hitl_port}/ui/tasks/task_demo_142",
                "evidence": [
                    _artifact_entry(
                        "output/demo/w12-issue-151/replay-record-001-six-stage-hitl.md",
                        role="WAITING_ENTER -> DECISION_APPLIED -> WAITING_EXIT 回放记录",
                    ),
                    _artifact_entry(
                        "output/demo/w12-issue-151/release-validation.md",
                        role="Issue #151 审计门禁摘要",
                    ),
                ],
                "checkpoint": "必须能看到候选对比、默认推荐、人工决策提交，以及决策后状态继续推进。",
            },
            {
                "name": "分层恢复与工具回退",
                "demo_entry": "output/demo/w12-issue-151/replay-record-002-tool-fallback.md",
                "evidence": [
                    _artifact_entry(
                        "output/demo/w12-issue-151/replay-record-002-tool-fallback.md",
                        role="from_tool -> to_tool 回放记录",
                    ),
                    _artifact_entry(
                        "scripts/w12-issue-150-dual-route-fallback.md",
                        role="运行时回退触发条件与审计字段",
                    ),
                ],
                "checkpoint": "要展示 REPLACE_TOOL 或路由决策字段，并解释为什么回退不破坏系统契约。",
            },
            {
                "name": "可审计性与可回放",
                "demo_entry": f"http://127.0.0.1:{api_port}/ui/tasks/<task_id>/events",
                "evidence": [
                    _artifact_entry(
                        "output/demo/w12-issue-151/logs/int_s6_patch_decision_replay_done.jsonl",
                        role="原始可回放事件日志",
                    ),
                    _artifact_entry(
                        "reports/w12-issue-152/artifact_evidence_index.csv",
                        role="报告追溯用产物索引",
                    ),
                ],
                "checkpoint": "时间线页面与 markdown 回放记录必须在事件顺序和任务结果上保持一致。",
            },
            {
                "name": "实验与报告证据",
                "demo_entry": "reports/w12-issue-174/midterm_experiment_chapter.md",
                "evidence": [
                    _artifact_entry(
                        "reports/w12-issue-174/midterm_experiment_chapter.md",
                        role="中期实验章节草稿",
                    ),
                    _artifact_entry(
                        "reports/w12-issue-152/three_week_report.md",
                        role="三周成果总报告",
                    ),
                    _artifact_entry(
                        "reports/w12-issue-152/release_candidate_draft.md",
                        role="RC 草案与阻断项摘要",
                    ),
                ],
                "checkpoint": "要明确说明项目已具备演示与报告能力，但因为 #149 门禁仍阻断，所以还不能宣称正式可发布。",
            },
        ],
    }


def render_showcase_guide(manifest: dict[str, Any]) -> str:
    api_demo = manifest["servers"]["api_demo"]
    hitl_compare = manifest["servers"]["hitl_compare"]
    lines = [
        "# 全流程展示操作手册",
        "",
        "## 1. 一次性准备",
        "",
    ]
    for cmd in manifest["prepare_commands"]:
        lines.append(f"- `{cmd}`")

    lines.extend(
        [
            "",
            "## 2. 启动长期运行界面",
            "",
            f"- API 演示服务：`{api_demo['command']}`",
            f"- HITL 候选对比服务：`{hitl_compare['command']}`",
            "",
            "## 3. 现场展示顺序",
            "",
            f"1. 打开 `{api_demo['url_docs']}` 和 `{api_demo['url_health']}`，先展示服务可用性。",
            f"2. 打开 `{hitl_compare['url_task']}`，展示候选对比、排序、风险/成本和人工决策界面。",
            f"3. 打开 `{hitl_compare['url_events']}`，展示种子 HITL 任务的事件时间线。",
            "4. 打开 `output/demo/w12-issue-151/replay-record-001-six-stage-hitl.md`，讲解端到端回放。",
            "5. 打开 `output/demo/w12-issue-151/replay-record-002-tool-fallback.md`，讲解 patch/recovery 与工具切换。",
            "6. 打开 `reports/w12-issue-174/midterm_experiment_chapter.md` 和 `reports/w12-issue-152/three_week_report.md`，用实验与报告证据收尾。",
            "",
            "## 4. 关键设计点检查清单",
            "",
        ]
    )

    for index, item in enumerate(manifest["design_points"], start=1):
        lines.append(f"### {index}. {item['name']}")
        lines.append("")
        lines.append(f"- 展示入口：`{item['demo_entry']}`")
        lines.append(f"- 检查点：{item['checkpoint']}")
        lines.append("- 证据：")
        for evidence in item["evidence"]:
            status = "已就绪" if evidence["exists"] else "缺失"
            lines.append(f"  - `{evidence['path']}` [{status}] - {evidence['role']}")
        lines.append("")

    lines.extend(
        [
            "## 5. 讲解备注",
            "",
            "- 最优主线是：可用性 -> HITL -> 回放/审计 -> 回退机制 -> 实验/报告证据。",
            "- 不要夸大当前实验结果。准确表述应是：系统已经具备演示能力和证据整理能力，但正式发布仍受离线门禁缺口阻断。",
            "- 如果时间不足，可以只保留第 1、2、4、6 步。",
        ]
    )
    return "\n".join(lines) + "\n"


def build_showcase_bundle(
    *,
    output_dir: Path,
    api_port: int,
    hitl_port: int,
    prepare: bool,
) -> dict[str, Path]:
    if prepare:
        _run(
            [
                "uv",
                "run",
                "python",
                "scripts/run_demo.py",
                "--port",
                str(api_port),
                "--exit-after-smoke",
            ]
        )
        _run(["uv", "run", "python", "scripts/run_w12_issue151_demo_audit.py"])
        _run(["uv", "run", "python", "scripts/generate_w12_issue174_midterm_pack.py"])
        _run(["uv", "run", "python", "scripts/generate_w12_issue152_release_pack.py"])

    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = build_showcase_manifest(api_port=api_port, hitl_port=hitl_port)
    manifest_path = output_dir / "full_flow_showcase_manifest.json"
    guide_path = output_dir / "full_flow_showcase_guide.md"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=True, indent=2), encoding="utf-8")
    guide_path.write_text(render_showcase_guide(manifest), encoding="utf-8")
    return {"manifest": manifest_path, "guide": guide_path}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a full-flow showcase guide and optional preparation bundle."
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--api-port", type=int, default=8000)
    parser.add_argument("--hitl-port", type=int, default=8012)
    parser.add_argument(
        "--prepare",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Run smoke/audit/report generation before writing the showcase bundle.",
    )
    args = parser.parse_args()

    result = build_showcase_bundle(
        output_dir=args.output_dir,
        api_port=args.api_port,
        hitl_port=args.hitl_port,
        prepare=args.prepare,
    )
    print(json.dumps({key: str(value) for key, value in result.items()}, ensure_ascii=True))


if __name__ == "__main__":
    main()
