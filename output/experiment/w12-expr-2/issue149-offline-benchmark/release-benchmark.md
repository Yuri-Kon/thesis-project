# 发布基准评估（release-benchmark）

## 评估目标
- 候选：`v0.3.0-rc1`（组 `A2`）
- 基线：`external-baseline-a0`（组 `A0`）
- 生成时间：`2026-03-15T20:21:52+00:00`

## 可复现信息
- 汇总输入：`output/experiment/w12-expr-2/issue171-remote-batch2-r1/vertical_metrics_summary.csv`
- 切片输入：`output/experiment/w12-expr-2/issue171-remote-batch2-r1/requirement2_tool_capability_slices.csv`
- 命令：`python scripts/evaluate_w12_issue149_offline_benchmark.py --summary-csv output/experiment/w12-expr-2/issue171-remote-batch2-r1/vertical_metrics_summary.csv --slice-csv output/experiment/w12-expr-2/issue171-remote-batch2-r1/requirement2_tool_capability_slices.csv --self-group A2 --baseline-group A0`

## 指标定义
- Schema 合法率：组内 schema 合法运行数 / 组内总运行数。
- 可执行 Plan 率：组内无 step 执行失败运行数 / 组内总运行数。
- Patch 最小性命中率：参数级 patch 事件数 / 全部 patch 事件数（patch 事件为 0 时为 null）。
- `suffix_replan` 前缀保持率：保留成功前缀的 `suffix_replan` 运行数 / `suffix_replan` 运行数（无样本时为 null）。
- 缺失值处理：若指标为 null，则门禁判定失败并阻断发布。

## 候选 vs 基线
| metric | candidate | baseline | delta |
|---|---:|---:|---:|
| Schema 合法率 | 1.000000 | 1.000000 | +0.000000 |
| 可执行 Plan 率 | 1.000000 | 1.000000 | +0.000000 |
| Patch 最小性命中率 | - | - | - |
| `suffix_replan` 前缀保持率 | - | - | - |

## RC Gate-B
| metric | threshold | candidate | pass |
|---|---:|---:|---:|
| Schema 合法率 | 0.995000 | 1.000000 | yes |
| 可执行 Plan 率 | 0.950000 | 1.000000 | yes |
| Patch 最小性命中率 | 0.800000 | - | no |
| `suffix_replan` 前缀保持率 | 1.000000 | - | no |

## 工具覆盖与指标关联
| slice_type | name | candidate covered | baseline covered | candidate usage | baseline usage | usage delta |
|---|---|---:|---:|---:|---:|---:|
| capability | sequence_design | yes | yes | 4 | 4 | +0 |
| capability | sequence_generation | yes | yes | 4 | 4 | +0 |
| capability | structure_prediction | yes | yes | 8 | 8 | +0 |
| capability_bucket | objective_scoring | no | no | 0 | 0 | +0 |
| capability_bucket | quality_qc | no | no | 0 | 0 | +0 |
| capability_bucket | sequence_core | yes | yes | 8 | 8 | +0 |
| capability_bucket | structure_prediction | yes | yes | 8 | 8 | +0 |
| tool | esmfold | yes | yes | 8 | 8 | +0 |
| tool | protein_mpnn | yes | yes | 4 | 4 | +0 |
| tool | protgpt2 | yes | yes | 4 | 4 | +0 |

## 发布结论
- 决策：离线门禁阈值未满足，阻断发布。
- 阻断项：Patch 最小性命中率未达门禁阈值（- < 0.800000）
- 阻断项：`suffix_replan` 前缀保持率未达门禁阈值（- < 1.000000）
