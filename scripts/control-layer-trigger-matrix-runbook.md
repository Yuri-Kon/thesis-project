# Control Layer Trigger Matrix Runbook

## 1. 目标

将 S6（Patch/Replan 控制层）规则显式化为“阶段感知触发矩阵”，并给出 WAITING 决策后的恢复操作路径。

## 2. 阶段触发矩阵（v2026-03-16.v1）

- `S1`：默认 `patch`；`SAFETY_*` 前缀失败码直接 `replan`
- `S2`：默认 `patch`；`S2_ALL_*` / `S2_IO_*` 失败码直接 `replan`
- `S3`：默认 `replan`（质量门禁失败属于全局策略调整）
- `S4`：默认 `patch`；`S4_LOOP_EXHAUSTED` 直接 `replan`
- `S5`：默认 `patch`；`S5_OBJECTIVE_NOT_MET` / `S5_SCORE_INVALID` 直接 `replan`

说明：`Safety block` 永远优先 `replan`。

## 3. WAITING 决策回流

- `WAITING_PATCH_CONFIRM` + `accept`：`WAITING_PATCH -> PATCHING -> RUNNING`
- `WAITING_PATCH_CONFIRM` + `replan`：进入 `WAITING_REPLAN`
- `WAITING_REPLAN_CONFIRM` + `accept`：进入 `PLANNING`（使用确认后的 replan 候选）
- `WAITING_REPLAN_CONFIRM` + `continue`：回到 `RUNNING`

## 4. 失败升级顺序

- 必须遵循 `retry -> patch -> replan`
- 当命中矩阵“直接 replan”规则时，跳过 patch，直接等待 replan 决策
- 仅在恢复路径耗尽或安全永久阻断时进入 `FAILED`

## 5. 审计链要求

每次进入控制层都必须保留：

- `WAITING_ENTER`
- `DECISION_APPLIED`
- `WAITING_EXIT`
- 失败上下文（`step_id/tool/failure_code/stage_id`）

