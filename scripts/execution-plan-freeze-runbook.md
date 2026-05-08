# Execution Plan Freeze Runbook

## 目标

冻结 `#169~#174` 的时间窗与依赖关系，输出可执行索引并自动校验：

- 每个实验 issue 均有开始/结束时间
- Hard dependency 图无环
- `#170`（数据快采）位于关键路径前段
- 输出可并行/不可并行清单

## 配置

- `configs/experiments/execution_plan_freeze.json`

## 运行

```bash
uv run python scripts/freeze_execution_plan.py \
  --config configs/experiments/execution_plan_freeze.json \
  --output-root output/experiment/w12-expr-0
```

## 输出

输出目录：`output/experiment/w12-expr-0/<plan_freeze_id>/`

- `execution_plan_index.json`：机器可读执行索引
- `execution_plan_index.md`：人读版计划摘要

## 与验收标准对齐

- 所有 issue 有明确开始/结束：由配置必填 + 脚本校验
- 依赖关系完整且无循环：由拓扑排序和循环检测保障
- 数据 issue 在关键路径最前：由 `data_issue_on_critical_front` 校验保障
