# Planner SFT 基线模型卡（v0.3.0-rc1）

## 摘要
- 运行 ID：`issue148-p0-p1`
- 基座模型：`sshleifer/tiny-gpt2`
- 数据集版本：`w11-sft-dataset-v1.1-20260315-57fc60d-r02`
- 允许优先级：`P0,P1`

## 工具覆盖
| tool_id | capability | priority | samples | sample_ratio | failure_ratio |
|---|---|---:|---:|---:|---:|
| biopython_qc | quality_qc | P0 | 1 | 0.3333 | 0.0000 |
| objective_ranker | objective_scoring | P0 | 1 | 0.3333 | 0.0000 |
| protein_mpnn | sequence_design | P0 | 1 | 0.3333 | 0.0000 |

## 已知限制
- 该结果为 Week12 RC Gate-A 的小样本基线。
- 仅保存 adapter 权重；推理时基座模型从 HuggingFace 加载。
- 按工具 loss 基于抽样验证子集计算，不等同完整基准评测。
