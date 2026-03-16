# W12 Issue #149：离线评估与外部基线对比

## 目标

针对候选模型 `v0.3.0-rc1` 与外部基线生成可复现的离线评估报告，并给出 RC Gate-B 的通过/阻断结论。

## 输入基线

该脚本复用 Week12 纵向实验输出：

- 汇总指标：`output/experiment/w12-expr-2/issue171-remote-batch2-r1/vertical_metrics_summary.csv`
- 工具/能力切片：`output/experiment/w12-expr-2/issue171-remote-batch2-r1/requirement2_tool_capability_slices.csv`

默认对比映射：

- 候选组：`A2`
- 基线组：`A0`

## 运行命令

```bash
uv run python scripts/evaluate_w12_issue149_offline_benchmark.py \
  --summary-csv output/experiment/w12-expr-2/issue171-remote-batch2-r1/vertical_metrics_summary.csv \
  --slice-csv output/experiment/w12-expr-2/issue171-remote-batch2-r1/requirement2_tool_capability_slices.csv \
  --self-group A2 \
  --baseline-group A0 \
  --candidate-version v0.3.0-rc1 \
  --baseline-version external-baseline-a0 \
  --output-dir output/experiment/w12-expr-2/issue149-offline-benchmark
```

## 输出

- `release_benchmark.json`
- `release_benchmark_comparison.csv`
- `release_benchmark_gate_checks.csv`
- `tool_coverage_vs_metrics.csv`
- `release-benchmark.md`

## 指标公式与分母定义

- Schema 合法率：组内 schema 合法运行数 / 组内总运行数
- 可执行 Plan 率：组内无 step 执行失败运行数 / 组内总运行数
- Patch 最小性命中率：参数级 patch 事件数 / 全部 patch 事件数
  - 若 patch 事件数为 0，则值为 null，门禁判定失败
- `suffix_replan` 前缀保持率：保留成功前缀的 `suffix_replan` 运行数 / `suffix_replan` 运行数
  - 若 `suffix_replan` 样本数为 0，则值为 null，门禁判定失败

## RC Gate-B 门禁阈值

- Schema 合法率 >= 99.5%
- 可执行 Plan 率 >= 95%
- Patch 最小性命中率 >= 80%
- `suffix_replan` 前缀保持率 = 100%

## Requirement-2 并入检查

- `tool_coverage_vs_metrics.csv` 导出按工具/能力切片结果
- 报告中明确给出候选/基线覆盖与使用量差异
- `release-benchmark.md` 在未达标时会输出门禁阻断项
