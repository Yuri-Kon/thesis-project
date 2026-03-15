# W12 Issue #170: 真实实验数据快采与版本冻结

## 目标

基于质量门禁后的样本，构建三类数据集并冻结版本：

- `D-main`：主路径 DONE 且无恢复标记样本
- `D-recovery`：失败/恢复（patch/replan）样本
- `D-hitl`：含 HITL 决策链样本

同时输出可追溯 manifest（`task_id/event_id/pending_action_id` 覆盖率、切分规则、缺口）。

## 一键运行（默认会复用现有抽取+质检脚本）

```bash
uv run python scripts/freeze_w12_issue170_data.py \
  --output-root output/experiment/w12-expr-1 \
  --time-window-start 2026-03-16T00:00:00+08:00 \
  --time-window-end 2026-03-18T23:59:59+08:00 \
  --plan-index-path output/experiment/w12-expr-0/<plan_freeze_id>/execution_plan_index.json
```

## 仅从已有 gated 样本冻结

```bash
uv run python scripts/freeze_w12_issue170_data.py \
  --gated-samples-path output/training/w11-data-2/gated_samples.jsonl \
  --quality-report-path output/training/w11-data-2/quality_gate_report.json \
  --output-root output/experiment/w12-expr-1 \
  --min-d-main 12 \
  --min-d-recovery 8 \
  --min-d-hitl 8
```

## 输出

输出目录：`output/experiment/w12-expr-1/<freeze_id>/`

- `d_main.jsonl`
- `d_recovery.jsonl`
- `d_hitl.jsonl`
- `dataset_index.jsonl`
- `input_version_and_split.json`
- `dataset_manifest.json`

## 与下游兼容

`dataset_manifest.json` 提供：

- `freeze_id`
- `downstream_ready.ready`
- `time_window`
- `manifest_path`

可被 `scripts/run_w12_vertical_issue171.py --strict-freeze-check` 直接校验使用。
