#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_VERTICAL_SUMMARY = Path(
    "output/experiment/w12-expr-2/issue171-remote-batch3-r3/vertical_metrics_summary.csv"
)
DEFAULT_MECHANISM_DELTAS = Path(
    "output/experiment/w12-expr-2/issue171-remote-batch3-r3/mechanism_increment_deltas.csv"
)
DEFAULT_GOVERNANCE_SUMMARY = Path(
    "output/experiment/w12-expr-2/issue173-governance-review/governance_metrics_summary.json"
)
DEFAULT_GOVERNANCE_GROUPS = Path(
    "output/experiment/w12-expr-2/issue173-governance-review/governance_metrics_by_group.csv"
)
DEFAULT_OUTPUT_DIR = Path("reports/w12-issue-174")
DEFAULT_HORIZONTAL_NOTE = (
    "E0/E1/E2 横向对比依赖外部平台，"
    "当前中期窗口先显式延期，不把缺失结果伪装成已完成。"
)


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


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


def _format_decimal(value: str | None, *, digits: int = 3, dash_for_empty: bool = True) -> str:
    if value is None:
        return "-" if dash_for_empty else ""
    text = value.strip()
    if not text:
        return "-" if dash_for_empty else ""
    number = float(text)
    return f"{number:.{digits}f}"


def _format_rate_pct(value: str | None) -> str:
    text = _format_decimal(value, digits=3)
    if text == "-":
        return text
    return f"{float(text) * 100:.1f}%"


def _format_int(value: str | None) -> str:
    if value is None:
        return "-"
    text = value.strip()
    if not text:
        return "-"
    return str(int(float(text)))


def _format_duration_ms(value: str | None) -> str:
    if value is None:
        return "-"
    text = value.strip()
    if not text:
        return "-"
    return f"{float(text):.1f}"


def _markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _vertical_table_rows(vertical_rows: list[dict[str, str]]) -> list[list[str]]:
    rows: list[list[str]] = []
    for row in vertical_rows:
        rows.append(
            [
                row["group_id"],
                _format_int(row.get("runs")),
                _format_rate_pct(row.get("success_rate")),
                _format_rate_pct(row.get("executable_plan_rate")),
                _format_rate_pct(row.get("patch_minimality_hit_rate")),
                _format_rate_pct(row.get("suffix_replan_prefix_preservation_rate")),
                _format_duration_ms(row.get("duration_ms_mean")),
            ]
        )
    return rows


def _governance_table_rows(governance_rows: list[dict[str, str]]) -> list[list[str]]:
    rows: list[list[str]] = []
    for row in governance_rows:
        rows.append(
            [
                row["group_id"],
                _format_int(row.get("tasks")),
                _format_rate_pct(row.get("waiting_chain_complete_rate")),
                _format_rate_pct(row.get("replay_success_rate")),
                _format_rate_pct(row.get("failure_traceable_rate")),
                _format_rate_pct(row.get("snapshot_linked_rate")),
            ]
        )
    return rows


def _select_mechanism_rows(delta_rows: list[dict[str, str]]) -> list[list[str]]:
    interesting_metrics = {"success", "executable_plan", "patch_event_count", "duration_ms"}
    picked: list[dict[str, str]] = []
    for row in delta_rows:
        if row.get("metric") not in interesting_metrics:
            continue
        delta = row.get("delta", "").strip()
        if delta and float(delta) != 0:
            picked.append(row)
    if not picked:
        picked = [row for row in delta_rows if row.get("metric") in interesting_metrics][:6]

    rows: list[list[str]] = []
    for row in picked:
        rows.append(
            [
                f"{row['from_group']} -> {row['to_group']}",
                row["metric"],
                _format_decimal(row.get("delta")),
                _format_decimal(row.get("ci_low")),
                _format_decimal(row.get("ci_high")),
            ]
        )
    return rows


def _build_figure_table_index(
    *,
    vertical_summary_path: Path,
    mechanism_delta_path: Path,
    governance_summary_path: Path,
    governance_groups_path: Path,
    horizontal_note: str,
) -> list[dict[str, str]]:
    return [
        {
            "artifact_id": "table-1",
            "artifact_type": "table",
            "title": "A0-A6 纵向对比总表",
            "source_path": str(vertical_summary_path),
            "status": "ready",
            "note": "成功率、可执行率、patch/replan 与时延统一汇总。",
        },
        {
            "artifact_id": "table-2",
            "artifact_type": "table",
            "title": "E0-E2 横向对比总表",
            "source_path": "external baseline comparison (deferred)",
            "status": "deferred",
            "note": horizontal_note,
        },
        {
            "artifact_id": "figure-1",
            "artifact_type": "figure",
            "title": "成功率-时延平衡图",
            "source_path": str(vertical_summary_path),
            "status": "ready",
            "note": "使用 A0-A6 组的 success_rate 与 duration_ms_mean 绘制。",
        },
        {
            "artifact_id": "figure-2",
            "artifact_type": "figure",
            "title": "恢复路径分布图",
            "source_path": str(mechanism_delta_path),
            "status": "ready",
            "note": "结合 patch/replan/suffix_replan 指标构图。",
        },
        {
            "artifact_id": "figure-3",
            "artifact_type": "figure",
            "title": "治理雷达图",
            "source_path": str(governance_groups_path),
            "status": "ready",
            "note": "使用 waiting/replay/traceable/snapshot 四项治理指标。",
        },
        {
            "artifact_id": "evidence-1",
            "artifact_type": "evidence",
            "title": "治理汇总 JSON",
            "source_path": str(governance_summary_path),
            "status": "ready",
            "note": "记录全局治理统计与输入来源。",
        },
    ]


def render_midterm_chapter(
    *,
    vertical_rows: list[dict[str, str]],
    delta_rows: list[dict[str, str]],
    governance_summary: dict[str, Any],
    governance_rows: list[dict[str, str]],
    vertical_summary_path: Path,
    governance_summary_path: Path,
    governance_groups_path: Path,
    figure_index_path: Path,
    horizontal_note: str,
) -> str:
    global_metrics = governance_summary.get("global", {})
    generated_at = datetime.now(timezone.utc).isoformat()

    vertical_table = _markdown_table(
        [
            "组别",
            "runs",
            "最终成功率",
            "可执行 Plan 率",
            "Patch 最小性命中率",
            "suffix_replan 前缀保持率",
            "平均时延(ms)",
        ],
        _vertical_table_rows(vertical_rows),
    )
    governance_table = _markdown_table(
        [
            "组别",
            "tasks",
            "WAITING 链完整率",
            "回放成功率",
            "失败可追溯率",
            "快照关联率",
        ],
        _governance_table_rows(governance_rows),
    )
    mechanism_table = _markdown_table(
        ["增量", "metric", "delta", "ci_low", "ci_high"],
        _select_mechanism_rows(delta_rows),
    )

    lines = [
        "# W12 中期实验章节草稿（Interim Experiment Pack）",
        "",
        f"- generated_at: `{generated_at}`",
        f"- vertical_summary: `{vertical_summary_path}`",
        f"- governance_summary: `{governance_summary_path}`",
        f"- figure_index: `{figure_index_path}`",
        "",
        "## 1. 章节范围",
        "",
        "- 本草稿优先服务 2026-03-19 中期报告，直接复用已完成的 #171 纵向实验与 #173 治理复核产物。",
        "- `#172` 横向对比因外部平台依赖延期，本稿显式保留占位与风险说明，不把缺口伪装成已完成结果。",
        "- 因此本稿适合作为“当前可展示证据包”，不应宣称已经满足 #174 的全部验收标准。",
        "",
        "## 2. 纵向结果（A0-A6）",
        "",
        vertical_table,
        "",
        "结论摘要：",
        "- 当前数据中 `schema_valid_rate` 维持高位，但 `success_rate` 在 A0-A6 全部为 0，说明实验框架已打通，方法效果尚未形成正向主结果。",
        "- `A2 -> A3` 在 `executable_plan_rate` 上出现正向增量，但未转化为最终成功率提升；这更像执行链通路打通，而不是任务成功闭环已经成立。",
        "- `patch_minimality_hit_rate` 在现有纵向汇总里可见，但 `suffix_replan_prefix_preservation_rate` 缺失样本，后续正式发布仍会被门禁阻断。",
        "",
        "## 3. 机制增量证据",
        "",
        mechanism_table,
        "",
        "## 4. 治理结果",
        "",
        governance_table,
        "",
        f"- 全局 tasks: `{global_metrics.get('tasks', '-')}`",
        f"- 全局失败可追溯率: `{global_metrics.get('failure_traceable_rate', '-')}`",
        f"- 全局 WAITING 链完整率: `{global_metrics.get('waiting_chain_complete_rate', '-')}`",
        f"- 全局回放成功率: `{global_metrics.get('replay_success_rate', '-')}`",
        "",
        "治理解读：",
        "- `failure_traceable_rate=1.0` 说明失败事件的追踪字段齐全，适合作为论文中的工程治理证据。",
        "- `waiting_chain_complete_rate=0.0` 与 `replay_success_rate=0.0` 说明主实验批次缺少可回放的人机决策链，当前治理证据主要依赖 #151 的演示回放样例补齐。",
        "",
        "## 5. 横向对比（E0/E1/E2）状态",
        "",
        horizontal_note,
        "",
        "建议在中期报告中这样处理：",
        "- 将 E0/E1/E2 明确标记为“下阶段实验”，保留表位与公平性约束说明。",
        "- 报告正文只陈述：横向基线设计已冻结，但由于外部平台依赖，本轮未纳入主结果表。",
        "",
        "## 6. 可直接引用的图表来源",
        "",
        f"- 表1：`{vertical_summary_path}`",
        "- 表2：保留空位，等待 #172 产物补齐。",
        f"- 图1/图2：由 `{vertical_summary_path}` 与机制增量 CSV 派生。",
        f"- 图3：由 `{governance_groups_path}` 派生。",
        "",
        "## 7. 风险与限制",
        "",
        "- 当前 A0-A6 结果更能证明实验管线可复现，而不能证明方法效果优于基线。",
        "- 主实验治理样本缺少 WAITING 链，必须结合 #151 的标准回放样例展示 HITL 审计能力。",
        "- 横向对比缺失意味着 #174 目前只能提交中期版草稿，不能按原 issue 口径宣告完成。",
    ]
    return "\n".join(lines) + "\n"


def build_issue174_pack(
    *,
    vertical_summary_path: Path = DEFAULT_VERTICAL_SUMMARY,
    mechanism_delta_path: Path = DEFAULT_MECHANISM_DELTAS,
    governance_summary_path: Path = DEFAULT_GOVERNANCE_SUMMARY,
    governance_groups_path: Path = DEFAULT_GOVERNANCE_GROUPS,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    horizontal_note: str = DEFAULT_HORIZONTAL_NOTE,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    vertical_rows = _read_csv_rows(vertical_summary_path)
    delta_rows = _read_csv_rows(mechanism_delta_path)
    governance_summary = _read_json(governance_summary_path)
    governance_rows = _read_csv_rows(governance_groups_path)

    figure_index_rows = _build_figure_table_index(
        vertical_summary_path=vertical_summary_path,
        mechanism_delta_path=mechanism_delta_path,
        governance_summary_path=governance_summary_path,
        governance_groups_path=governance_groups_path,
        horizontal_note=horizontal_note,
    )

    chapter_path = output_dir / "midterm_experiment_chapter.md"
    figure_index_path = output_dir / "figure_table_index.csv"

    chapter_path.write_text(
        render_midterm_chapter(
            vertical_rows=vertical_rows,
            delta_rows=delta_rows,
            governance_summary=governance_summary,
            governance_rows=governance_rows,
            vertical_summary_path=vertical_summary_path,
            governance_summary_path=governance_summary_path,
            governance_groups_path=governance_groups_path,
            figure_index_path=figure_index_path,
            horizontal_note=horizontal_note,
        ),
        encoding="utf-8",
    )
    _write_csv(figure_index_path, figure_index_rows)
    return {"chapter": chapter_path, "figure_index": figure_index_path}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate the interim midterm chapter pack."
    )
    parser.add_argument("--vertical-summary", type=Path, default=DEFAULT_VERTICAL_SUMMARY)
    parser.add_argument("--mechanism-deltas", type=Path, default=DEFAULT_MECHANISM_DELTAS)
    parser.add_argument("--governance-summary", type=Path, default=DEFAULT_GOVERNANCE_SUMMARY)
    parser.add_argument("--governance-groups", type=Path, default=DEFAULT_GOVERNANCE_GROUPS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--horizontal-note", default=DEFAULT_HORIZONTAL_NOTE)
    args = parser.parse_args()

    result = build_issue174_pack(
        vertical_summary_path=args.vertical_summary,
        mechanism_delta_path=args.mechanism_deltas,
        governance_summary_path=args.governance_summary,
        governance_groups_path=args.governance_groups,
        output_dir=args.output_dir,
        horizontal_note=args.horizontal_note,
    )
    print(json.dumps({key: str(value) for key, value in result.items()}, ensure_ascii=True))


if __name__ == "__main__":
    main()
