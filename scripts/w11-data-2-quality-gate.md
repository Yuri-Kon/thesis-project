# W11-Data-2: 训练数据质量门禁说明

## 目标

对 `W11-Data-1` 抽取产物执行自动化质量门禁，输出：

- 通过/警告/阻断（PASS/WARN/BLOCK）判定
- 关键缺失与拒绝码
- 去重与切分结果
- 汇总质量报告

## 输入来源

- 样本：`output/training/w11-data-1/samples.jsonl`

## 使用方式

```bash
uv run python scripts/quality_gate_training_data.py \
  --samples-path output/training/w11-data-1/samples.jsonl \
  --output-dir output/training/w11-data-2 \
  --split-strategy time \
  --train-ratio 0.70 \
  --val-ratio 0.15 \
  --plddt-min 0.70 \
  --score-completeness-min 0.80 \
  --fail-on-block
```

## 输出文件

- `gated_samples.jsonl`：附带 `quality_gate` 的样本全集（含 split）
- `failed_samples.jsonl`：阻断样本清单（含拒绝码、`tool_id/capability_id` 上下文）
- `quality_gate_report.json`：汇总指标与规则快照

## 判定规则（PASS/WARN/BLOCK）

- `BLOCK`：存在任一阻断级问题（schema 缺失、关键字段缺失、失败样本缺少 failure、Requirement-2 缺失、重复/泄漏等）
- `WARN`：无阻断问题，但存在告警（例如 pLDDT 低于阈值）
- `PASS`：无告警/阻断

## 核心检查项

- Schema 检查：`context/candidates/selected/outcome/audit_trace`
- 关键字段缺失：
  - 候选字段：`score_breakdown/risk_level/cost_estimate`
  - 失败样本字段：`step_failure_types` 与失败 step 的 `failure_type`
- 去重与泄漏防护：
  - 跨工具去重键：`sequence_hash + structure_hash + tool_lineage_hash`
  - 若重复跨 split 出现，标记泄漏风险并阻断
- 时间切分：
  - 默认 `--split-strategy time`，按 `context.time_window` 时间顺序进行任务级切分
  - 时间戳缺失时自动回退到 `task_id` 哈希切分并记录警告码
  - 切分比例默认 `train/val/test=70/15/15`

## Requirement-2 门禁并入

按 capability 执行字段门禁：

- `sequence_generation` / `sequence_design`：必须有 `sequence_hash`
- `structure_prediction`：必须有 `structure_hash` 与 `plddt_mean`
- `quality_qc`：必须有 `qc_pass=true`
- `objective_scoring`：必须满足 `score_completeness_rate` 阈值

并在失败样本中保留：

- `tool_id`
- `capability_id`
- `reject_codes`
