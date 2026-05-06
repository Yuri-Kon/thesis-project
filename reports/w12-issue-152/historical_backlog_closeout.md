# Issue #152 历史 Backlog 收束说明

- issue: `#152`
- title: `W12-Docs-2: 三周成果报告与下一阶段计划`
- generated_at: `2026-04-26`
- closeout_window: `2026-04-20` 至 `2026-04-24`
- primary_plan: `../thesis-project.design/plan/index(3.24-4.24).md`
- gap_source: `../thesis-project.design/plan/w13-issue-208-code-baseline-audit-gap-list.md`
- local_evidence: `reports/w12-issue-174/evidence-pack-handoff.md`, `docs/evidence/issue-225/write-back-closeout.md`

## 收束结论

`#152` 已不再按原 W12 中期收官报告执行。当前应将它视为 W16 收口阶段的历史 backlog 迁移说明：旧 W12 报告材料保留在 `reports/w12-issue-152/`，但 W16 之后的正式口径必须以 W14-W16 adaptive algorithm 主线、`#174` evidence handoff 和 `#225` write-back closeout 为准。

截至 `2026-04-26` 的 GitHub 状态显示，`#212` 之前仍开放的历史 issue 只有 `#152` 本身。换言之，本次收束不是批量迁移多个仍开放旧 issue，而是把 `#152` 的旧报告语义归档，并明确它如何被 W14-W16 主线吸收、哪些事项继续作为后续 backlog 保留。

## 追溯依据

| 结论 | 依据 |
| --- | --- |
| W14-W16 主线不重写既有 FSM / Agent 边界，只做 Lite 自适应规划增量 | `../thesis-project.design/plan/index(3.24-4.24).md` 的全局边界与验收口径 |
| `#208` 后续拆分应围绕 runtime_state、动作选择、证据字段，而不是重写 Planner / Workflow | `../thesis-project.design/plan/w13-issue-208-code-baseline-audit-gap-list.md` |
| `#174` 已转为 W16 evidence pack handoff，不应继续复制旧 `#172 deferred` 口径 | `reports/w12-issue-174/evidence-pack-handoff.md` |
| `#225` 已完成 write-back closeout，并把未回答问题转为下一阶段 issue 草案 | `docs/evidence/issue-225/write-back-closeout.md` |
| 当前 W16 结果支持成本/控制边界，不支持宣称 `lite_belief_state` 提升成功率 | `docs/evidence/issue-225/write-back-closeout.md` 的 Current Result Boundaries |

## Carry-Over / Absorbed / Follow-Up 归档

| category | issue | 去向 | 当前处理 |
| --- | ---: | --- | --- |
| absorbed | `#152` | 被 W14-W16 主线与 `#225` closeout 吸收 | 本文件补齐历史 backlog 收束、迁移说明和后续优先级草案 |
| absorbed | `#211`-`#215` | W14 contract / state / observability / replay 主线 | 已关闭，承接 `#208` 的 D1/D2/F1/E1/E2/F3 缺口 |
| absorbed | `#216`-`#220` | W15 action selection / rerank / dynamic baseline / regression 主线 | 已关闭，承接 `#208` 的 F2/F3 与恢复边界测试 |
| absorbed | `#221`-`#225` | W16 experiment / analysis / evidence / write-back 主线 | 已关闭，构成 `#152` 新口径的主要证据来源 |
| carry-over | `#230` | action-level / belief-state 聚合指标扩展 | 保留为 W16 之后的指标补强项 |
| carry-over | `#248` | 活跃工具元数据画像与派生成本/风险接入 | 保留为后续 runtime / tool readiness 依赖 |
| carry-over | `#249` | canonical naming 与 output mapping 接入 | 保留为后续实验命名、输出映射和论文口径依赖 |
| follow-up | `#225` 草案 A-D | 结果 claim 边界、case bundle、belief-state rerun、SSOT sync | 作为下一阶段 issue 化准备的直接输入 |

完整映射表见 `reports/w12-issue-152/open_issue_mapping.csv`。

## 风险与未完成项

| priority | 风险 / 缺口 | 后续处理建议 |
| --- | --- | --- |
| P0 | 当前 W16 结果不能证明 `lite_belief_state` 提升最终成功率 | 下一阶段先写明 claim boundary，避免论文和 issue 中出现过强表述 |
| P0 | case-level 证据仍依赖本地 `output/`、event log、snapshot 路径 | 打包最小 case bundle，缺失项显式标为 evidence gap |
| P1 | `dynamic_no_belief_state` 与 `lite_belief_state` 的增量价值仍需 targeted rerun | 基于 `#249` canonical naming 后再做对照 rerun |
| P1 | `#248` 工具画像会影响成本/风险来源和 readiness 解释 | 后续工具生态扩展前先固定 active tool metadata |
| P1 | 设计 repo、实验文档和 tracked evidence 的 wording 仍需持续同步 | 以 `#225` closeout 的 consistency matrix 作为同步准则 |

## 下一阶段 Backlog 草案

1. P0: 结果 claim 边界与负结果表述。
   - blocked-by: `#225`
   - 输出：可用于论文结果/讨论章节的 claim-boundary memo。
   - 验收：引用 W16 metrics 和 `#225` closeout，不宣称 `lite_belief_state` 提升成功率。

2. P0: 最小 case evidence bundle。
   - blocked-by: `#224`, `#225`
   - 输出：tracked case manifest 或证据包，覆盖成功止损、静态/动态对照、失败案例。
   - 验收：每个案例回链到 run config、event log、snapshot、summary row；缺失项显式标记。

3. P1: belief-state 增量 targeted rerun。
   - blocked-by: `#222`, `#225`, `#249`
   - 输出：`dynamic_no_belief_state` 与 `lite_belief_state` 的定向对照表。
   - 验收：能区分“更快但不更成功”和“自适应决策质量更高”。

4. P1: 设计 / 实验 / backlog SSOT 同步。
   - blocked-by: `#225`, `#248`, `#249`
   - 输出：设计 repo 实验文档与开放问题口径同步 patch。
   - 验收：统一使用 `static_top1`, `fixed_threshold_gate`, `dynamic_no_belief_state`, `lite_belief_state`，并保留当前结果边界。

## 验收对照

| `#152` 验收项 | 当前状态 |
| --- | --- |
| pre-212 历史开放 issue 已有清晰去向与阶段映射 | 已完成。`#212` 前开放项仅 `#152`，去向为 absorbed by W14-W16 / `#225` closeout |
| 风险与未完成项已形成后续 backlog 建议 | 已完成。见风险表与下一阶段 backlog 草案 |
| 内容可直接供 `#225` 或后续阶段规划复用 | 已完成。本文引用 `#225` closeout，并把其草案 A-D 转为 `#152` 收束口径 |

