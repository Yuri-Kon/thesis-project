#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_TRAINING_SUMMARY = Path(
    "output/training/w12-issue-148/v0.3.0-rc1/issue148-p0-p1/training_summary.json"
)
DEFAULT_RELEASE_BENCHMARK = Path(
    "output/experiment/w12-expr-2/issue149-offline-benchmark/release_benchmark.json"
)
DEFAULT_RUNTIME_FALLBACK_CONFIG = Path("configs/runtime/w12_issue150_dual_route_fallback.json")
DEFAULT_RUNTIME_RUNBOOK = Path("scripts/w12-issue-150-dual-route-fallback.md")
DEFAULT_DEMO_SUMMARY = Path("output/demo/w12-issue-151/demo-summary.json")
DEFAULT_DEMO_VALIDATION = Path("output/demo/w12-issue-151/release-validation.md")
DEFAULT_VERTICAL_REPORT = Path(
    "output/experiment/w12-expr-2/issue171-remote-batch3-r3/vertical_report.md"
)
DEFAULT_VERTICAL_SUMMARY = Path(
    "output/experiment/w12-expr-2/issue171-remote-batch3-r3/vertical_metrics_summary.csv"
)
DEFAULT_GOVERNANCE_SUMMARY = Path(
    "output/experiment/w12-expr-2/issue173-governance-review/governance_metrics_summary.json"
)
DEFAULT_GOVERNANCE_REPORT = Path(
    "output/experiment/w12-expr-2/issue173-governance-review/governance-report.md"
)
DEFAULT_MIDTERM_CHAPTER = Path("reports/w12-issue-174/midterm_experiment_chapter.md")
DEFAULT_FIGURE_INDEX = Path("reports/w12-issue-174/figure_table_index.csv")
DEFAULT_OUTPUT_DIR = Path("reports/w12-issue-152")


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        raise ValueError("rows must not be empty")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _format_bool(value: bool) -> str:
    return "yes" if value else "no"


def _format_optional_number(value: Any, *, digits: int = 3) -> str:
    if value is None:
        return "-"
    return f"{float(value):.{digits}f}"


def _build_artifact_rows(
    *,
    training_summary: dict[str, Any],
    release_benchmark: dict[str, Any],
    demo_summary_path: Path,
    demo_validation_path: Path,
    runtime_fallback_config_path: Path,
    runtime_runbook_path: Path,
    vertical_report_path: Path,
    vertical_summary_path: Path,
    governance_summary_path: Path,
    governance_report_path: Path,
    midterm_chapter_path: Path,
    figure_index_path: Path,
) -> list[dict[str, str]]:
    training_paths = training_summary.get("paths", {})
    rows = [
        {
            "issue": "148",
            "artifact_type": "training_summary",
            "path": str(DEFAULT_TRAINING_SUMMARY if False else training_summary_path_from_payload(training_paths, fallback=DEFAULT_TRAINING_SUMMARY)),
            "exists": _format_bool(Path(training_summary_path_from_payload(training_paths, fallback=DEFAULT_TRAINING_SUMMARY)).exists()),
            "role": "训练摘要与版本冻结",
        },
        {
            "issue": "148",
            "artifact_type": "model_card",
            "path": str(training_paths.get("model_card", "")),
            "exists": _format_bool(Path(str(training_paths.get("model_card", ""))).exists()),
            "role": "模型适用范围与已知限制",
        },
        {
            "issue": "149",
            "artifact_type": "release_benchmark_json",
            "path": str(DEFAULT_RELEASE_BENCHMARK),
            "exists": _format_bool(DEFAULT_RELEASE_BENCHMARK.exists()),
            "role": "离线门禁与基线对比",
        },
        {
            "issue": "150",
            "artifact_type": "runtime_fallback_config",
            "path": str(runtime_fallback_config_path),
            "exists": _format_bool(runtime_fallback_config_path.exists()),
            "role": "回退默认配置与熔断开关",
        },
        {
            "issue": "150",
            "artifact_type": "runtime_runbook",
            "path": str(runtime_runbook_path),
            "exists": _format_bool(runtime_runbook_path.exists()),
            "role": "双路回退使用说明",
        },
        {
            "issue": "151",
            "artifact_type": "demo_summary",
            "path": str(demo_summary_path),
            "exists": _format_bool(demo_summary_path.exists()),
            "role": "端到端演示摘要",
        },
        {
            "issue": "151",
            "artifact_type": "release_validation",
            "path": str(demo_validation_path),
            "exists": _format_bool(demo_validation_path.exists()),
            "role": "RC Gate-D 演示验证",
        },
        {
            "issue": "171",
            "artifact_type": "vertical_report",
            "path": str(vertical_report_path),
            "exists": _format_bool(vertical_report_path.exists()),
            "role": "A0-A6 纵向实验摘要",
        },
        {
            "issue": "171",
            "artifact_type": "vertical_summary_csv",
            "path": str(vertical_summary_path),
            "exists": _format_bool(vertical_summary_path.exists()),
            "role": "统一指标总表",
        },
        {
            "issue": "173",
            "artifact_type": "governance_summary",
            "path": str(governance_summary_path),
            "exists": _format_bool(governance_summary_path.exists()),
            "role": "治理指标 JSON",
        },
        {
            "issue": "173",
            "artifact_type": "governance_report",
            "path": str(governance_report_path),
            "exists": _format_bool(governance_report_path.exists()),
            "role": "治理复核报告",
        },
        {
            "issue": "174",
            "artifact_type": "midterm_chapter",
            "path": str(midterm_chapter_path),
            "exists": _format_bool(midterm_chapter_path.exists()),
            "role": "中期实验章节草稿（当前可交子集）",
        },
        {
            "issue": "174",
            "artifact_type": "figure_index",
            "path": str(figure_index_path),
            "exists": _format_bool(figure_index_path.exists()),
            "role": "图表证据索引",
        },
        {
            "issue": "172",
            "artifact_type": "horizontal_comparison",
            "path": "deferred",
            "exists": "no",
            "role": "外部平台依赖，当前窗口延期",
        },
    ]
    return rows


def training_summary_path_from_payload(paths: dict[str, Any], *, fallback: Path) -> str:
    run_dir = paths.get("run_dir")
    if isinstance(run_dir, str) and run_dir:
        return str(Path(run_dir) / "training_summary.json")
    return str(fallback)


def render_three_week_report(
    *,
    training_summary: dict[str, Any],
    release_benchmark: dict[str, Any],
    runtime_fallback: dict[str, Any],
    demo_summary: dict[str, Any],
    governance_summary: dict[str, Any],
    midterm_chapter_path: Path,
) -> str:
    training = training_summary.get("training", {})
    reproducibility = training_summary.get("reproducibility", {})
    global_governance = governance_summary.get("global", {})
    release_blocked = bool(release_benchmark.get("release_blocked"))
    gate_checks = release_benchmark.get("gate_checks", [])
    blocked_metrics = [
        str(item.get("metric"))
        for item in gate_checks
        if isinstance(item, dict) and not bool(item.get("passed"))
    ]
    generated_at = datetime.now(timezone.utc).isoformat()

    lines = [
        "# W12 三周成果总报告（Issue #152 Interim Pack）",
        "",
        f"- generated_at: `{generated_at}`",
        f"- candidate_version: `{training_summary.get('candidate_version', '-')}`",
        f"- dataset_version: `{training_summary.get('dataset_version', '-')}`",
        "",
        "## 1. 当前完成度",
        "",
        "- 已有可直接复用产物：#148 训练、#149 离线评估、#150 双路回退、#151 演示审计、#171 纵向实验、#173 治理复核。",
        "- `#172` 横向 E0/E1/E2 因外部平台依赖延期，因此 `#174` 仅能生成中期版章节草稿，不能按原始 issue 口径完全关闭。",
        "- 当前版本更适合定义为“可演示、中期可引用、但未达正式发布门禁”的候选包。",
        "",
        "## 2. 关键实现与证据",
        "",
        f"- 训练基线：`{training_summary.get('candidate_version', '-')}`，基座模型 `{training.get('base_model', '-')}`，QLoRA `{_format_bool(bool(training.get('qlora_enabled')) )}`。",
        f"- 训练复现命令：`{reproducibility.get('command', '-')}`",
        f"- 演示场景：`{', '.join(demo_summary.get('scenarios', [])) or '-'}`",
        f"- 演示审计检查：`{demo_summary.get('checks', {})}`",
        f"- 治理全局指标：failure_traceable_rate=`{global_governance.get('failure_traceable_rate', '-')}`，waiting_chain_complete_rate=`{global_governance.get('waiting_chain_complete_rate', '-')}`，replay_success_rate=`{global_governance.get('replay_success_rate', '-')}`",
        f"- 中期章节草稿：`{midterm_chapter_path}`",
        "",
        "## 3. 统一结论与限制",
        "",
        f"- RC Gate-B 发布阻断：`{_format_bool(release_blocked)}`",
        f"- 阻断指标：`{', '.join(blocked_metrics) if blocked_metrics else '-'}`",
        "- 当前纵向实验说明实验管线可复现，但尚未形成正向任务成功率结果，论文中应按“已完成工程闭环、效果仍待加强”来表述。",
        "- 治理方面，失败可追溯性已经具备，但 WAITING/Decision 主实验样本不足，需继续补充可回放样本。",
        "",
        "## 4. 下一阶段建议",
        "",
        "- 优先恢复 #172 所需外部平台条件，再补齐 E0/E1/E2 横向对照。",
        "- 基于 #172 结果刷新 #174 正式版章节与图表，避免中期稿长期停留为占位。",
        "- 继续采集能触发 patch/suffix_replan 的真实样本，修复 #149 里两个门禁指标的空值问题。",
        "- 若只面向中期答辩，建议以 #151 演示链 + #171/#173 结果表 + #149 阻断项说明构成展示主线。",
        "",
        "## 5. RC 草案结论",
        "",
        "- 版本号建议保持 `v0.3.0-rc1`，但仅作为候选演示版，不进入正式版本发布流程。",
        "- 兼容性说明：当前交付不引入新 FSM 状态，不改变 HITL 决策所有权；回退策略通过配置开关控制。",
        "- 已知问题：离线门禁仍被空值指标阻断；横向对照延期；主实验 WAITING 链样本不足。",
        f"- 回退策略：`runtime_fallback.force_external_only={runtime_fallback.get('runtime_fallback', {}).get('force_external_only', '-')}`，环境变量 `{runtime_fallback.get('release_defaults', {}).get('circuit_breaker_env', '-')}` 可一键熔断。",
    ]
    return "\n".join(lines) + "\n"


def render_release_candidate_draft(
    *,
    training_summary: dict[str, Any],
    release_benchmark: dict[str, Any],
    runtime_fallback: dict[str, Any],
    demo_summary: dict[str, Any],
) -> str:
    gate_checks = release_benchmark.get("gate_checks", [])
    blocked_metrics = [
        f"{item.get('metric')}={_format_optional_number(item.get('candidate_value'))}"
        for item in gate_checks
        if isinstance(item, dict) and not bool(item.get("passed"))
    ]
    checks = demo_summary.get("checks", {})
    lines = [
        "# Release Candidate Draft (`v0.3.0-rc1`)",
        "",
        "## 变更摘要",
        "",
        "- 已具备训练基线、离线评估、双路回退、端到端演示、纵向实验与治理复核的基础产物。",
        "",
        "## 兼容性说明",
        "",
        "- 不新增 FSM 状态。",
        "- 不改变 HITL 决策所有权。",
        "- 发布默认开启外部回退兜底，可用紧急熔断环境变量切回外部基线。",
        "",
        "## 评估摘要（来自 #149）",
        "",
        f"- release_blocked: `{_format_bool(bool(release_benchmark.get('release_blocked')) )}`",
        f"- blocked_metrics: `{', '.join(blocked_metrics) if blocked_metrics else '-'}`",
        "",
        "## 回退策略（来自 #150）",
        "",
        f"- force_external_only: `{runtime_fallback.get('runtime_fallback', {}).get('force_external_only', '-')}`",
        f"- circuit_breaker_env: `{runtime_fallback.get('release_defaults', {}).get('circuit_breaker_env', '-')}`",
        "",
        "## 验证证据与已知问题（来自 #151 与当前实验）",
        "",
        f"- demo_scenarios: `{', '.join(demo_summary.get('scenarios', [])) or '-'}`",
        f"- demo_checks: `{checks}`",
        "- known_issue: `#172` 横向对比延期，`#174` 当前仅能形成中期版草稿。",
        "- known_issue: RC Gate-B 仍被 patch/suffix_replan 指标空值阻断。",
        "- known_issue: 主实验 WAITING 链指标为 0，治理展示需依赖标准回放样例。",
        "",
        "## 发布建议",
        "",
        f"- 维持候选版本：`{training_summary.get('candidate_version', '-')}`",
        "- 当前只建议作为答辩演示与论文附录证据包，不建议进入正式 release 流程。",
    ]
    return "\n".join(lines) + "\n"


def render_next_stage_backlog() -> str:
    lines = [
        "# 下一阶段 Backlog 草案",
        "",
        "## P0",
        "",
        "- 恢复并完成 #172：补齐 E0/E1/E2 横向实验运行条件与结果表。",
        "- 刷新 #149：补采真实 patch/suffix_replan 样本，消除门禁空值。",
        "- 刷新 #174：在 #172 完成后生成正式中期实验章节与图表定稿。",
        "",
        "## P1",
        "",
        "- 为 #173 增补主实验 WAITING/Decision 样本，使治理指标不再只依赖 demo 回放。",
        "- 对 #151 的标准演示进一步封装成固定答辩脚本与截图清单。",
        "",
        "## P2",
        "",
        "- 基于新的横向结果更新 #152 正式版收官报告与 Release Draft。",
        "- 评估是否需要新增更贴近论文叙述的可视化图表生成脚本。",
    ]
    return "\n".join(lines) + "\n"


def build_issue152_pack(
    *,
    training_summary_path: Path = DEFAULT_TRAINING_SUMMARY,
    release_benchmark_path: Path = DEFAULT_RELEASE_BENCHMARK,
    runtime_fallback_config_path: Path = DEFAULT_RUNTIME_FALLBACK_CONFIG,
    runtime_runbook_path: Path = DEFAULT_RUNTIME_RUNBOOK,
    demo_summary_path: Path = DEFAULT_DEMO_SUMMARY,
    demo_validation_path: Path = DEFAULT_DEMO_VALIDATION,
    vertical_report_path: Path = DEFAULT_VERTICAL_REPORT,
    vertical_summary_path: Path = DEFAULT_VERTICAL_SUMMARY,
    governance_summary_path: Path = DEFAULT_GOVERNANCE_SUMMARY,
    governance_report_path: Path = DEFAULT_GOVERNANCE_REPORT,
    midterm_chapter_path: Path = DEFAULT_MIDTERM_CHAPTER,
    figure_index_path: Path = DEFAULT_FIGURE_INDEX,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    training_summary = _read_json(training_summary_path)
    release_benchmark = _read_json(release_benchmark_path)
    runtime_fallback = _read_json(runtime_fallback_config_path)
    demo_summary = _read_json(demo_summary_path)
    governance_summary = _read_json(governance_summary_path)

    artifact_rows = _build_artifact_rows(
        training_summary=training_summary,
        release_benchmark=release_benchmark,
        demo_summary_path=demo_summary_path,
        demo_validation_path=demo_validation_path,
        runtime_fallback_config_path=runtime_fallback_config_path,
        runtime_runbook_path=runtime_runbook_path,
        vertical_report_path=vertical_report_path,
        vertical_summary_path=vertical_summary_path,
        governance_summary_path=governance_summary_path,
        governance_report_path=governance_report_path,
        midterm_chapter_path=midterm_chapter_path,
        figure_index_path=figure_index_path,
    )

    report_path = output_dir / "three_week_report.md"
    release_draft_path = output_dir / "release_candidate_draft.md"
    backlog_path = output_dir / "next_stage_backlog.md"
    artifact_index_path = output_dir / "artifact_evidence_index.csv"

    report_path.write_text(
        render_three_week_report(
            training_summary=training_summary,
            release_benchmark=release_benchmark,
            runtime_fallback=runtime_fallback,
            demo_summary=demo_summary,
            governance_summary=governance_summary,
            midterm_chapter_path=midterm_chapter_path,
        ),
        encoding="utf-8",
    )
    release_draft_path.write_text(
        render_release_candidate_draft(
            training_summary=training_summary,
            release_benchmark=release_benchmark,
            runtime_fallback=runtime_fallback,
            demo_summary=demo_summary,
        ),
        encoding="utf-8",
    )
    backlog_path.write_text(render_next_stage_backlog(), encoding="utf-8")
    _write_csv(artifact_index_path, artifact_rows)
    return {
        "report": report_path,
        "release_draft": release_draft_path,
        "backlog": backlog_path,
        "artifact_index": artifact_index_path,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate the interim release/report pack for issue #152."
    )
    parser.add_argument("--training-summary", type=Path, default=DEFAULT_TRAINING_SUMMARY)
    parser.add_argument("--release-benchmark", type=Path, default=DEFAULT_RELEASE_BENCHMARK)
    parser.add_argument(
        "--runtime-fallback-config", type=Path, default=DEFAULT_RUNTIME_FALLBACK_CONFIG
    )
    parser.add_argument("--runtime-runbook", type=Path, default=DEFAULT_RUNTIME_RUNBOOK)
    parser.add_argument("--demo-summary", type=Path, default=DEFAULT_DEMO_SUMMARY)
    parser.add_argument("--demo-validation", type=Path, default=DEFAULT_DEMO_VALIDATION)
    parser.add_argument("--vertical-report", type=Path, default=DEFAULT_VERTICAL_REPORT)
    parser.add_argument("--vertical-summary", type=Path, default=DEFAULT_VERTICAL_SUMMARY)
    parser.add_argument("--governance-summary", type=Path, default=DEFAULT_GOVERNANCE_SUMMARY)
    parser.add_argument("--governance-report", type=Path, default=DEFAULT_GOVERNANCE_REPORT)
    parser.add_argument("--midterm-chapter", type=Path, default=DEFAULT_MIDTERM_CHAPTER)
    parser.add_argument("--figure-index", type=Path, default=DEFAULT_FIGURE_INDEX)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    result = build_issue152_pack(
        training_summary_path=args.training_summary,
        release_benchmark_path=args.release_benchmark,
        runtime_fallback_config_path=args.runtime_fallback_config,
        runtime_runbook_path=args.runtime_runbook,
        demo_summary_path=args.demo_summary,
        demo_validation_path=args.demo_validation,
        vertical_report_path=args.vertical_report,
        vertical_summary_path=args.vertical_summary,
        governance_summary_path=args.governance_summary,
        governance_report_path=args.governance_report,
        midterm_chapter_path=args.midterm_chapter,
        figure_index_path=args.figure_index,
        output_dir=args.output_dir,
    )
    print(json.dumps({key: str(value) for key, value in result.items()}, ensure_ascii=True))


if __name__ == "__main__":
    main()
