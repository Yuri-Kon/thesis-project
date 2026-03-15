# SFT 数据集 v1 冻结说明（W11-Docs-1 / Issue #147）

## 1. 目标与范围

本文档对应 Issue #147，记录 SFT 数据集冻结与后续补齐结果，作为 Week12 训练输入基线说明。

覆盖内容：

- 数据集版本冻结（不可变语义）
- 字段字典与分布统计
- Requirement2 工具覆盖矩阵与 P0 覆盖判定
- 增量版本（v1.1/r02）与上一版本差异
- 复现命令与发布流程

## 2. 版本总览

### 2.1 v1（首版冻结）

- `dataset_version`: `w11-sft-dataset-v1-20260315-0ce8eb8`
- 冻结目录：`output/dataset_v1/w11-sft-dataset-v1-20260315-0ce8eb8/`
- 输入/纳入/阻断：`36 / 32 / 4`
- P0 核心覆盖：`false`
  - 已覆盖：`structure_prediction`
  - 缺失：`sequence_core`, `quality_qc`, `objective_scoring`

### 2.2 v1.1（增量补齐 / r02）

- `dataset_version`: `w11-sft-dataset-v1.1-20260315-57fc60d-r02`
- 冻结目录：`output/dataset_v1/w11-sft-dataset-v1.1-20260315-57fc60d-r02/`
- 输入/纳入/阻断：`39 / 35 / 4`
- P0 核心覆盖：`true`
  - 覆盖结果：
    - `sequence_core`（通过 `sequence_design`）
    - `structure_prediction`
    - `quality_qc`
    - `objective_scoring`

## 3. 冻结语义与版本演进

冻结语义：

- 同版本内容不可变更；
- 仅当 fingerprint 相同允许幂等复用；
- 输入变化必须升版本。

v1.1 在 manifest 中新增：

- `delta_from_previous`
  - `dataset_counts_delta`
  - `split_counts_delta`
  - `capability_distribution_delta`
  - `tool_coverage_matrix_delta`
  - `p0_core_coverage_change`

v1.1 相对 v1 的关键差异：

- `accepted_total`: `+3`
- capability 新增：`sequence_design`, `quality_qc`, `objective_scoring`
- tool coverage 新增键：
  - `sequence_design|protein_mpnn|remote`
  - `quality_qc|biopython_qc|local`
  - `objective_scoring|objective_ranker|local`
- `p0_core_minimum_coverage`: `false -> true`

## 4. 输入与产物

### 4.1 输入来源

- 基础样本：`output/training/w11-data-1/samples.jsonl`
- 基础门禁：`output/training/w11-data-2/gated_samples.jsonl`
- Addon 补齐样本：`output/training/w11-data-3/requirement2_addon_samples.jsonl`
- Addon 合并门禁：`output/training/w11-data-3/gated_samples.jsonl`
- 工具目录：
  - `src/kg/protein_tool_kg.json`
  - `src/kg/protein_tool_kg/extension_draft_v0.1.json`

### 4.2 冻结产物

每个冻结版本目录下包含：

- `accepted_samples.jsonl`
- `train.jsonl` / `val.jsonl` / `test.jsonl`
- `dataset_stats.json`
- `field_dictionary.json`
- `tool_coverage_matrix.json`
- `training_reader_config.json`
- `manifest.json`

代码仓同步提供配置模板：

- `configs/training/sft_dataset_v1.example.json`

## 5. Requirement2 并入结果

### 5.1 工具覆盖矩阵

矩阵维度固定为：`capability x tool x adapter_mode`。

v1.1 新增覆盖：

- `sequence_design -> protein_mpnn -> remote`
- `quality_qc -> biopython_qc -> local`
- `objective_scoring -> objective_ranker -> local`

### 5.2 P0 工具版本/模型标识固化

manifest `requirement2.p0_tool_registry` 固化字段：

- `tool_id`
- `capability_id`
- `adapter_mode`
- `tool_version`
- `provider`
- `model_id`

### 5.3 最小覆盖门槛判定

P0 核心能力要求：

- `sequence_core`（`sequence_generation` 或 `sequence_design`）
- `structure_prediction`
- `quality_qc`
- `objective_scoring`

v1.1 判定结果：`satisfied = true`。

## 6. 发布流水线接入

Issue #147 的后续补充已纳入发布流程：

1. `extract_training_samples.py`
2. `quality_gate_training_data.py`（base）
3. `augment_requirement2_coverage.py`
4. `quality_gate_training_data.py`（addons 合并后）
5. `freeze_sft_dataset_v1.py --fail-on-missing-p0-core`

推荐一键命令：

```bash
uv run python scripts/release_sft_dataset_v1_1.py \
  --dataset-version w11-sft-dataset-v1.1-20260315-57fc60d-r02 \
  --previous-manifest-path output/dataset_v1/w11-sft-dataset-v1-20260315-0ce8eb8/manifest.json
```

说明文档：`scripts/w11-data-3-requirement2-addons-release.md`

## 7. 偏差、限制与后续补充

### 7.1 当前可用性

- v1.1 已满足 Requirement2 的 P0 核心覆盖门槛，可作为 Week12 训练输入版本。

### 7.2 当前限制

- 新增覆盖来自 addon 补齐样本（可复现、可追溯），但规模仍小；
- 总体工具分布仍偏向结构预测任务；
- 样本规模对泛化评估仍偏保守。

### 7.3 后续建议

- 增加真实运行任务中的 `sequence/qc/objective` 原生样本比例；
- 若目标是“真实工具执行覆盖”而非“最小门槛覆盖”，需补充对应工具在生产链路中的实际执行数据。

## 8. 验收对照（Issue #147）

- [x] 生成并固化数据集版本号（manifest + 不可变语义）。
- [x] 输出字段字典与分布统计。
- [x] 文档化偏差与不适用边界。
- [x] 产出最小复现实验与发布命令。
- [x] Requirement2：
  - [x] `tool_coverage_matrix`
  - [x] P0 工具版本/模型标识固化
  - [x] 工具偏差与限制说明
  - [x] P0 核心覆盖要求与判定（v1.1 达标）
