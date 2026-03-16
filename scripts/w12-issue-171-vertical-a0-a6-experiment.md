# W12 Issue #171：A0-A6 纵向实验执行与归因口径

## 1. 目标与范围

本实现对应 issue #171（A0-A6 纵向对比 + 机制增量归因），并对齐：

- `../thesis-project.design/plan/w12-issues-169-170-experiment-timeline-data-freeze-implementation-plan.md`
- `../thesis-project.design/docs/experiment/w11-w12-midterm-experiment-plan.md`

本实现产物覆盖：

- A0-A6 分组配置固化；
- 实验批量执行脚本；
- 统一口径指标评估脚本；
- 结果表 / 运行日志索引 / 异常样本清单；
- Requirement2 工具/能力切片统计。

## 2. 产物目录约定

运行产物默认落盘到：

- `output/experiment/w12-expr-2/<run_id>/`

核心文件：

- `runs_manifest.json`：完整可复现清单（freeze、分组、任务、重复、run 列表）
- `run_log_index.csv`：日志索引（issue 要求交付物）
- `vertical_metrics_summary.csv`：A0-A6 总表（效果/机制/代价/治理）
- `patch_replan_breakdown.csv`：`patch/replan/suffix_replan` 细分统计
- `mechanism_increment_deltas.csv`：A0->A1 ... A5->A6 机制增量与 CI
- `requirement2_tool_capability_slices.csv`：Requirement2 工具/能力切片
- `offline_gate_assessment.json`：离线门禁阈值达标判定（不达标给原因）
- `abnormal_samples.jsonl`：异常样本清单（issue 要求交付物）
- `vertical_report.md`：便于直接引用到实验文档的摘要报告

## 3. A0-A6 配置

配置文件：

- `configs/experiments/w12_issue171_vertical_a0_a6.json`

关键点：

- 固化 A0-A6 每组机制开关与参数；
- 固化重复次数（默认 3）；
- 固化任务集与统一输入约束；
- 固化离线门禁阈值：
  - `schema_valid_rate >= 0.995`
  - `executable_plan_rate >= 0.95`
  - `patch_minimality_hit_rate >= 0.8`
  - `suffix_replan_prefix_preservation_rate == 1.0`

## 4. 执行命令

### 4.1 运行 A0-A6 实验

```bash
uv run python scripts/run_w12_vertical_issue171.py \
  --config configs/experiments/w12_issue171_vertical_a0_a6.json \
  --freeze-manifest-path <ISSUE170_MANIFEST_PATH> \
  --run-id w12e2-issue171-r01
```

说明：

- 默认开启 `--strict-freeze-check`，会校验 `freeze_id` 与 `downstream_ready`；
- 若仅联调流程，可临时 `--no-strict-freeze-check --dry-run`。

### 4.2 评估与产出汇总

```bash
uv run python scripts/evaluate_w12_vertical_issue171.py \
  --run-manifest-path output/experiment/w12-expr-2/w12e2-issue171-r01/runs_manifest.json
```

## 5. 指标口径（统一）

效果：

- `success_rate`
- `first_pass_success_rate`
- `executable_plan_rate`

机制：

- `schema_valid_rate`
- `patch_events_mean`
- `replan_events_mean`
- `suffix_replan_events_mean`
- `patch_minimality_hit_rate`

代价：

- `duration_ms_mean`

治理：

- `waiting_chain_complete_rate`
- `failure_traceable_rate`

统计方法：

- 比例指标：Wilson 95% CI
- 均值/差值：Bootstrap CI（默认 10,000 次）

## 6. Requirement2 对齐

评估脚本会导出：

- capability bucket 覆盖：`sequence_core / quality_qc / objective_scoring / structure_prediction`
- capability 细粒度 usage
- tool 细粒度 usage

输出文件：

- `requirement2_tool_capability_slices.csv`

## 7. 验收标准映射

对应 issue #171 验收要求：

- A0->A6 链路可复现：由 `runs_manifest.json + resolved_config_snapshot.json + run_log_index.csv` 保证；
- 机制增量证据：由 `mechanism_increment_deltas.csv` 提供；
- 离线门禁阈值达标或原因：由 `offline_gate_assessment.json` 提供；
- 交付物完整：结果表、日志索引、异常样本清单均可直接导出。
