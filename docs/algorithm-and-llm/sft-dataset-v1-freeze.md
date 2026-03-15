# SFT 数据集 v1 冻结说明（W11-Docs-1 / Issue #147）

## 1. 目标与范围

本文档对应 Issue #147，给出 Week11 SFT 数据集 v1 的冻结结果与使用说明，作为 Week12 训练输入基线。

本次冻结覆盖：

- 数据集版本与 manifest（不可变语义）。
- 字段字典与样本统计。
- 已知偏差与不适用场景。
- 最小复现实验命令。
- Requirement2：工具覆盖矩阵、P0 工具版本固化、最小覆盖门槛判定。

## 2. 冻结版本

- `dataset_version`: `w11-sft-dataset-v1-20260315-0ce8eb8`
- 冻结目录：`output/dataset_v1/w11-sft-dataset-v1-20260315-0ce8eb8/`
- manifest：`output/dataset_v1/w11-sft-dataset-v1-20260315-0ce8eb8/manifest.json`
- 冻结语义：
  - 同版本内容不可变更；
  - 若重新执行且输入完全一致，仅允许幂等复用（fingerprint 相同）；
  - 输入变更必须升版本。

## 3. 输入与筛选规则

### 3.1 输入来源

- 质检后样本：`output/training/w11-data-2/gated_samples.jsonl`
- 质检报告：`output/training/w11-data-2/quality_gate_report.json`
- 工具目录：
  - `src/kg/protein_tool_kg.json`
  - `src/kg/protein_tool_kg/extension_draft_v0.1.json`

### 3.2 样本纳入规则

- 仅纳入 `quality_gate.status in {PASS, WARN}` 的样本。
- `BLOCK` 样本不进入训练集。
- split 直接继承门禁结果（`train/val/test`）。

## 4. 数据产物

冻结目录下产物：

- `accepted_samples.jsonl`：纳入训练的全量样本。
- `train.jsonl` / `val.jsonl` / `test.jsonl`：按 split 拆分。
- `dataset_stats.json`：分布统计。
- `field_dictionary.json`：字段字典（路径、类型、覆盖率、非空率）。
- `tool_coverage_matrix.json`：`capability x tool x adapter_mode` 覆盖矩阵。
- `training_reader_config.json`：本版本训练读取配置。
- `manifest.json`：冻结元数据、追溯信息、Requirement2 检查结果。

同时在代码仓维护模板：

- `configs/training/sft_dataset_v1.example.json`

## 5. 统计摘要（本次冻结）

来自 `manifest.json` / `dataset_stats.json`：

- 输入样本：36
- 纳入样本：32
- 阻断样本：4
- split：
  - train: 25
  - val: 5
  - test: 2
- capability 分布：
  - structure_prediction: 32
- 工具分布：
  - tool_id: esmfold (32)
  - adapter_mode: local (32)

## 6. 字段字典说明

字段字典产物：

- `output/dataset_v1/w11-sft-dataset-v1-20260315-0ce8eb8/field_dictionary.json`

说明：

- 每个字段按路径记录（例如 `sample.context.task_id`）。
- 提供字段类型分布、行覆盖率、非空率、示例值（若可提取）。
- 可直接用于 Week12 训练前 schema 对账。

## 7. Requirement2 并入结果

### 7.1 工具覆盖矩阵

产物：

- `output/dataset_v1/w11-sft-dataset-v1-20260315-0ce8eb8/tool_coverage_matrix.json`

当前矩阵结果：

- `structure_prediction -> esmfold -> local`（sample_count=32）

### 7.2 P0 工具版本/模型标识固化

manifest 中 `requirement2.p0_tool_registry` 固化了 P0 工具的：

- `tool_id`
- `capability_id`
- `adapter_mode`
- `tool_version`
- `provider`
- `model_id`

示例（含 provider/model_id）：

- `nim_esmfold` -> `provider=nvidia_nim`, `model_id=nvidia/esmfold`
- `protein_mpnn` -> `provider=nvidia_nim`, `model_id=ipd/proteinmpnn/predict`
- `protgpt2` -> `provider=plm_rest`, `model_id=nferruz/ProtGPT2`

### 7.3 P0 核心能力最小覆盖要求

冻结脚本内置最小覆盖检查：

- `sequence_core`：`sequence_generation` 或 `sequence_design`
- `structure_prediction`
- `quality_qc`
- `objective_scoring`

本版本结果：

- 满足：`structure_prediction`
- 缺失：`sequence_core`, `quality_qc`, `objective_scoring`
- 结论：`p0_core_minimum_coverage.satisfied = false`

该结论已写入 manifest，供 Week12 训练策略决定是否仅用于结构子任务或先补齐数据再进入全能力训练。

## 8. 工具偏差与已知限制（按工具族）

### 8.1 结构预测工具族（esmfold）

- 当前 v1 样本几乎完全由 `esmfold/local` 族构成。
- 偏差风险：模型可能过拟合到单一工具输出风格，跨工具迁移能力有限。

### 8.2 序列生成/设计工具族

- 当前 v1 未覆盖 `protgpt2` / `protein_mpnn` 训练样本。
- 限制：不适合评估或训练 sequence 相关能力。

### 8.3 质量控制与目标评分工具族

- 当前 v1 未覆盖 `biopython_qc` 与 `objective_ranker` 的训练样本。
- 限制：不适合用于 QC gate 学习或 objective score 学习。

## 9. 不适用场景

当前 v1 不建议直接用于：

- 全能力 Planner 训练（尤其包含 sequence/qc/objective 的联合训练）；
- 需要跨工具鲁棒性的评估；
- 用于 Requirement2 中 P0 核心能力“全覆盖”验收。

当前 v1 适合：

- Week12 结构能力相关流程联调；
- 训练链路打通与最小可复现验证。

## 10. 最小复现实验命令

按顺序执行：

```bash
uv run python scripts/extract_training_samples.py \
  --logs-dir data/logs \
  --snapshots-dir data/snapshots \
  --reports-dir output/reports \
  --metrics-dir output/metrics \
  --tool-kg-path src/kg/protein_tool_kg.json \
  --tool-extension-kg-path src/kg/protein_tool_kg/extension_draft_v0.1.json \
  --output-dir output/training/w11-data-1

uv run python scripts/quality_gate_training_data.py \
  --samples-path output/training/w11-data-1/samples.jsonl \
  --output-dir output/training/w11-data-2 \
  --split-strategy time \
  --plddt-min 0.70 \
  --score-completeness-min 0.80

uv run python scripts/freeze_sft_dataset_v1.py \
  --gated-samples-path output/training/w11-data-2/gated_samples.jsonl \
  --quality-report-path output/training/w11-data-2/quality_gate_report.json \
  --tool-kg-path src/kg/protein_tool_kg.json \
  --tool-extension-kg-path src/kg/protein_tool_kg/extension_draft_v0.1.json \
  --dataset-version w11-sft-dataset-v1-20260315-0ce8eb8
```

## 11. 验收对照（Issue #147）

- [x] 生成并固化数据集版本号（tag/manifest）。
- [x] 输出字段字典与分布统计。
- [x] 文档化已知偏差与不适用场景。
- [x] 产出最小复现实验说明。
- [x] Requirement2：
  - [x] manifest 增加 `tool_coverage_matrix`
  - [x] 固化 P0 工具版本/模型标识（provider/model_id）
  - [x] 文档化工具偏差与已知限制
  - [x] 明确 v1 最小覆盖要求并给出判定结果
