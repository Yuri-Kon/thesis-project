# W13 Issue #209：高代价步骤、任务集与比较基线冻结

## 目标

冻结未来一个月实验所用的：

- 高代价步骤定义；
- 任务集版本与难度分层；
- 四组比较基线；
- 统一指标口径。

## 一键生成冻结产物

```bash
uv run python scripts/freeze_w13_issue209_baseline_freeze.py \
  --config configs/experiments/w13_issue209_baseline_freeze.json
```

默认输出目录：

- `output/experiment/w13-expr-0/<freeze_id>/`

核心产物：

- `baseline_freeze_manifest.json`
- `baseline_freeze_report.md`

## 冻结原则

- 高代价步骤沿用 SSOT 中的 `workflow.stage.high_cost_control` 定义，不新增工作流语义。
- 任务集默认锚定到 `configs/experiments/w12_issue171_vertical_a0_a6.json` 的四个任务键，并在本 issue 内冻结难度标签。
- 四组基线必须同时保留“当前仓库已支持”与“后续计划实现”状态，避免把计划态误写成已实现态。
- 指标字段直接对齐 `src/infra/w12_vertical_experiment.py` 的聚合输出。

## 当前仓库映射

- `静态 Top-1`：已可由 `plan_top_k=1` 等约束表达。
- `固定阈值 gate`：已可由 `min_candidate_confidence` 与 `high_cost_min_overall` 等阈值表达。
- `动态无 belief-state`：本次冻结比较契约，但当前仓库尚未完整实现动作选择器。
- `Lite belief-state`：本次冻结比较契约，但当前仓库尚未落地 `runtime_state / belief_state` 契约。
