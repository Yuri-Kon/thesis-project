# 下一阶段 Backlog 草案

- issue: `#152`
- status: W16 closeout update
- generated_at: `2026-04-26`
- detail: `reports/w12-issue-152/historical_backlog_closeout.md`

## P0

- 结果 claim 边界与负结果表述：基于 `docs/evidence/issue-225/write-back-closeout.md`，明确当前 W16 结果支持成本/控制表述，不支持宣称 `lite_belief_state` 提升成功率。
- 最小 case evidence bundle：基于 `#224` 模板和 `#223` rerun/case pack，固定 run config、event log、snapshot、summary row 的可追溯入口；缺失项显式标记为 evidence gap。

## P1

- Belief-state 增量 targeted rerun：在 `#249` canonical naming 与 output mapping 收敛后，对 `dynamic_no_belief_state` 与 `lite_belief_state` 做定向对照。
- 设计 / 实验 / backlog SSOT 同步：以 `#225` consistency matrix 为准，统一 `static_top1`、`fixed_threshold_gate`、`dynamic_no_belief_state`、`lite_belief_state` 四组命名。
- 活跃工具元数据画像：保留 `#248` 作为成本/风险来源与 readiness 解释的后续依赖。

## P2

- 将旧 W12 report pack 作为历史附录保留；后续报告正文只引用 W16 evidence handoff、#225 closeout 和本目录新增的历史 backlog 收束说明。
