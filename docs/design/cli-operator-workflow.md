---
doc_key: interface_cli_workflow
version: 1.0
status: stable
depends_on: [interface_surfaces, impl, hitl]
---

# CLI 交互设计：无头环境闭环、批处理与 Web 协同
<!-- SID:interface.cli_workflow.overview -->

本文档细化 CLI 作为控制台入口时的落地规范，定义其命令面、交互模式、输出契约与与 Web 的协同关系。

CLI 的目标不是复刻 Web 的可视化体验，而是在无图形环境下保证任务可提交、可监控、可确认、可恢复、可审计。

## 定位与职责边界
<!-- SID:interface.cli_workflow.role_boundary -->

CLI 的正式定位如下：

- 是系统的无头环境入口；
- 是自动化、脚本化与批处理的首选入口；
- 是远程服务器、SSH、tmux 场景下的主入口；
- 是 Web 主工作台的辅助入口与控制台伴侣。

CLI 必须完整覆盖最小闭环，但不承担浏览器级结构可视化、富对比布局和长报告阅读体验。

## 体验模式
<!-- SID:interface.cli_workflow.experience_modes -->

CLI 应支持三类体验模式：

- headless mode：纯终端完成全流程最小闭环；
- companion mode：CLI 负责提交、轮询、待办查询，复杂确认跳转到 Web；
- automation mode：面向 shell、CI、脚本与批量实验的非交互模式。

三类模式共享同一组 API 语义，不得出现不同模式下的状态解释分叉。

## 命令分组
<!-- SID:interface.cli_workflow.command_groups -->

CLI 建议按以下命令组组织：

- `design submit`：提交任务；
- `design task show/watch/list`：查询、轮询与检索任务；
- `design pending list/show`：查看待确认事项与候选摘要；
- `design decision apply`：提交正式 Decision；
- `design timeline show`：查看关键事件链；
- `design report show/open`：输出报告与工件入口；
- `design ui open`：打开 Web 主界面或指定任务页面。

命令分组应围绕用户目标组织，而不是围绕内部 Python 模块组织。

## 提交流程
<!-- SID:interface.cli_workflow.submit_flow -->

`submit` 流程必须兼容当前同步后端与未来异步后端：

- 若服务端同步运行到 WAITING_* 或终态再返回，CLI 也要能稳定解析结果；
- 若服务端未来改为快速返回 `task_id`，CLI 应自动切换到轮询路径；
- 提交后必须明确输出 `task_id`，作为后续所有交互的锚点；
- 若有 `--watch` 选项，应在提交后直接进入 watch 流程。

CLI 不得把某一种返回时机写死为永久契约。

## 轮询与值守流程
<!-- SID:interface.cli_workflow.watch_flow -->

`watch` 是 CLI 的核心能力之一，应面向值守场景设计：

- 轮询当前状态、当前步骤、最后事件；
- 在进入 WAITING_* 时立即停止并输出 PendingAction 信息；
- 在终态时输出结果摘要、报告路径与退出码；
- 在网络抖动或瞬时错误下支持有限重试；
- 在用户中断时保留清晰的 task_id 提示，便于稍后恢复。

对长任务来说，`watch` 比一次性返回全文日志更重要。

## 待确认审查流程
<!-- SID:interface.cli_workflow.pending_review -->

CLI 必须支持在纯终端下完成待确认处理：

- `pending list` 列出所有 `PENDING` 状态的待办；
- `pending show` 展示 pending_action_id、类型、推荐候选、候选摘要、风险与成本提示；
- `decision apply` 支持提交 `accept / replan / continue / cancel`；
- 若候选较长，应优先呈现摘要，并允许查看原始 JSON。

纯 CLI 场景下，浏览器打开能力只能是增强项，而不是必需项。

## 非交互模式
<!-- SID:interface.cli_workflow.noninteractive_mode -->

为了服务自动化与脚本调用，CLI 应提供非交互能力：

- 所有关键命令支持 `--json` 输出；
- `decision apply` 支持通过参数直接给出决策；
- 命令失败时返回稳定退出码；
- 避免只依赖人类友好的彩色文本作为唯一输出。

这样才能让 CLI 成为可靠的自动化入口，而不仅是人工终端工具。

## 输出契约
<!-- SID:interface.cli_workflow.output_profiles -->

CLI 建议定义两类输出剖面：

- human profile：简洁、可扫描，适合终端值守；
- machine profile：JSON 结构化输出，适合脚本消费。

两类输出都应围绕相同字段组织，至少包含：

- task_id 或 pending_action_id；
- 当前状态与当前步骤；
- 推荐动作或下一步提示；
- 报告、日志、快照等关键路径或 URL。

## Web 协同与跳转
<!-- SID:interface.cli_workflow.web_handoff -->

CLI 应把 Web 视为复杂交互的主空间，因此需要正式定义跳转行为：

- 当任务进入 WAITING_* 时，输出可直接定位的 task 页面或 pending review 页面；
- 提供 `design ui open --task <task_id>` 与 `design ui open --pending <pending_action_id>`；
- 如果当前环境不支持打开浏览器，也要把目标 URL 明确打印出来；
- 在 Web 完成确认后，CLI 可以继续使用 `watch` 跟进到终态。

CLI 与 Web 的协同目标是“无缝切换”，而不是让用户手工猜测地址与上下文。

## 错误呈现与恢复提示
<!-- SID:interface.cli_workflow.error_mapping -->

CLI 需要把系统内部失败语义转译成用户可操作的信息。至少应做到：

- 对网络类错误提示“可重试”；
- 对 `WAITING_*` 类暂停提示“需要人工确认”；
- 对远程模型失败码给出恢复方向，例如配额问题、鉴权问题、模型不可用或输入无效；
- 对终态失败提示报告路径、日志路径与最近事件。

例如，当远程 NIM 调用返回 `NIM_QUOTA_EXCEEDED`、`NIM_AUTH_FAILED` 或 `NIM_MODEL_NOT_FOUND` 时，CLI 应直接把恢复动作提示给用户，而不是只打印底层异常。

## 无头恢复与审计
<!-- SID:interface.cli_workflow.headless_recovery -->

CLI 还应承担无头环境中的恢复与审计职责：

- 能通过 task_id 重新接回一个已有任务；
- 能查看事件时间线与最近决策；
- 能输出快照路径、日志路径与报告路径；
- 能在断线、tmux 重连或会话中断后继续工作。

这使 CLI 成为服务器场景下最可靠的运维与研究入口。

## 渐进增强边界
<!-- SID:interface.cli_workflow.progressive_enhancement -->

CLI 可以逐步增强，但增强项不能侵蚀其稳定性。可接受的增强包括：

- 表格渲染；
- TUI 风格列表；
- 彩色状态徽标；
- 快捷键辅助与复制友好输出；
- 与本地浏览器、编辑器或文件查看器的快捷联动。

这些增强都应建立在“纯文本 + JSON 仍然完整可用”的前提上。

## 演进顺序
<!-- SID:interface.cli_workflow.milestones -->

CLI 建议按以下顺序落地：

1. 先实现 submit、show、watch、pending、decision、ui open 六类核心能力；
2. 再补充 timeline、report 与 JSON 输出规范；
3. 最后根据真实使用情况增强 TUI、批处理辅助与更丰富的输出格式。

演进过程中，CLI 必须始终保持“无头可用、脚本友好、与 Web 协同明确”的定位。
