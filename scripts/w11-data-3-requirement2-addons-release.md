# W11-Data-3: Requirement2 覆盖补齐与 v1.1 发布

本说明对应 Issue #147 后续补充项：

- 补齐 `sequence_core / quality_qc / objective_scoring` 覆盖；
- 发布增量冻结版本（`v1.1/r02`）；
- 将 `freeze + --fail-on-missing-p0-core` 接入发布流水线。

## 1. 一键发布（推荐）

```bash
uv run python scripts/release_sft_dataset_v1_1.py \
  --dataset-version w11-sft-dataset-v1.1-20260315-57fc60d-r02 \
  --previous-manifest-path output/dataset_v1/w11-sft-dataset-v1-20260315-0ce8eb8/manifest.json
```

默认执行流程：

1. `extract_training_samples.py`
2. `quality_gate_training_data.py`（base）
3. `augment_requirement2_coverage.py`
4. `quality_gate_training_data.py`（addons 合并后）
5. `freeze_sft_dataset_v1.py --fail-on-missing-p0-core`

## 2. 仅执行补齐步骤

```bash
uv run python scripts/augment_requirement2_coverage.py \
  --base-samples-path output/training/w11-data-1/samples.jsonl \
  --base-gated-path output/training/w11-data-2/gated_samples.jsonl \
  --output-dir output/training/w11-data-3
```

输出：

- `output/training/w11-data-3/requirement2_addon_samples.jsonl`
- `output/training/w11-data-3/samples_with_addons.jsonl`
- `output/training/w11-data-3/requirement2_addon_report.json`

## 3. 验收点

- `output/training/w11-data-3/gated_samples.jsonl` 中新增能力覆盖：
  - `sequence_design`（代表 `sequence_core`）
  - `quality_qc`
  - `objective_scoring`
- 冻结产物 manifest 含：
  - `requirement2.p0_core_minimum_coverage.satisfied = true`
  - `delta_from_previous`（与上一版差异）
