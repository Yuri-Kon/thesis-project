# Objective Scoring Top-K Runbook

## 1. 目标

对应 `#159`，补齐六阶段中的 `S5(Objective Scoring)`：

- 为候选输出统一的多目标评分分解；
- 提供可配置权重并保持确定性排序；
- 输出可直接被 HITL 与数据抽取复用的 `Top-K + default_recommendation`。

## 2. S5 契约（candidate metadata.s5_contract）

每个 Top-K 候选都携带 `metadata.s5_contract`：

- `stage_id`: `S5`
- `stage_name`: `objective_scoring`
- `field_order.inputs`: `candidates`, `metrics`
- `field_order.outputs`: `score_breakdown`, `top_k`, `default_recommendation`, `explanation`
- `weights`: 归一化后的评分权重

`validate_candidate_set_output(..., require_s5_fields=True)` 会校验以上字段完整性。

## 3. 评分维度与默认权重

评分分解字段（`score_breakdown`）与默认权重：

- `feasibility`: `0.20`
- `objective`: `0.20`
- `risk`: `0.15`
- `cost`: `0.15`
- `confidence`: `0.15`
- `tool_readiness`: `0.075`
- `tool_coverage`: `0.075`

整体分数 `overall` 为上述维度的加权和。

## 4. 权重配置

可通过任务约束配置：

- `score_weights`（推荐）
- `objective_weights`（兼容别名）

示例：

```json
{
  "score_weights": {
    "objective": 2.0,
    "risk": 1.0,
    "cost": 1.0,
    "feasibility": 1.0,
    "confidence": 1.0,
    "tool_readiness": 1.0,
    "tool_coverage": 1.0
  }
}
```

实现会自动归一化为和为 1 的权重分布，确保同输入同配置可复现。

## 5. 验收映射

- 可解释 score/risk/cost 分解：由 `score_breakdown` + `s5_contract` 提供。
- Top-K 稳定可复现：候选生成与排序为确定性逻辑，同输入同配置结果一致。
- HITL/数据管线可消费：`PendingAction` 继续输出 `candidates + default_recommendation + explanation`，并新增 S5 契约元数据。
