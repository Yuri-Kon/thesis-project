---
doc_key: interface_surfaces
version: 1.0
status: stable
depends_on: [arch, hitl, impl]
---

# 交互入口设计：Web 主界面与 CLI 辅助入口
<!-- SID:interface.overview.entry_surfaces -->

## 范围与定位
<!-- SID:interface.scope.positioning -->

本文档定义系统的交互入口设计，明确 Web 与 CLI 两类入口的产品定位、适用场景、职责边界与演进约束。

本设计的目标不是引入新的执行语义，而是在不改变现有 FSM、HITL、PendingAction、Decision 与 TaskSnapshot 契约的前提下，为研究人员提供稳定、一致、可恢复的操作入口。

本文档的定位如下：

- Web 端是主操纵空间，用于承载高信息密度、需要上下文比较的交互任务；
- CLI 是控制台入口与无头环境兼容层，用于远程、脚本化、批处理与纯终端环境；
- 两者都必须通过既有 API 与任务契约交互，不得绕过工作流内核直接修改状态。

## 设计目标与非目标
<!-- SID:interface.goals.design_targets -->

本设计追求以下目标：

- 在无图形界面的服务器、SSH 会话或终端环境中，仍可完成任务的最小闭环；
- 在桌面或浏览器环境中，提供更适合人工审查与复杂确认的主界面；
- 保持 Web 与 CLI 的状态一致性，避免出现“双入口语义分叉”；
- 与现有 API、事件日志、快照恢复与 WAITING_* 机制保持兼容；
- 支持未来从“同步提交”平滑演进到“异步提交 + 轮询”的后端模式。

本设计不负责：

- 重新定义任务状态机；
- 引入新的 Agent 角色或修改 Agent 边界；
- 为 CLI 复制浏览器级结构可视化能力；
- 让 Web 绕过 PendingAction / Decision 契约直接驱动执行。

## 双入口架构
<!-- SID:interface.architecture.dual_surface -->

系统采用“双入口、单执行内核”的交互结构：

- Web 与 CLI 都是外层交互壳；
- API 是两类入口共享的集成边界；
- Workflow / FSM / Agents / Storage 仍是唯一执行与持久化内核。

### Web 端：主操纵空间
<!-- SID:interface.web.primary_workspace -->

Web 端应被视为研究人员的主操作界面，负责承载以下高上下文密度任务：

- 查看任务概览、当前状态、当前步骤与风险提示；
- 对 PendingAction 候选进行并排比较；
- 阅读 explanation、recommendation reason、risk/cost 等解释信息；
- 查看事件时间线、WAITING -> DECISION -> RESUME 链路；
- 打开最终 HTML 报告、结构可视化与图表。

Web 端适合需要“看全局后再做决策”的工作，不要求用户记忆命令，也不要求压缩上下文到单屏文本。

### CLI：控制台与无头环境入口
<!-- SID:interface.cli.headless_entry -->

CLI 应被视为系统的控制台入口，主要面向以下场景：

- 远程服务器、SSH、tmux、纯终端环境；
- 批量实验、自动化脚本、CI 或 cron 驱动流程；
- 快速提交任务、轮询状态、处理待确认事项；
- 在浏览器不可用时完成最低限度的人机协作闭环。

CLI 的价值不在于替代 Web 的所有体验，而在于保证系统在没有图形界面的条件下仍然“可用、可恢复、可审计”。

### Web 与 CLI 的协同关系
<!-- SID:interface.cross_surface.relationship -->

Web 与 CLI 不是竞争入口，而是职责互补的两类操作面：

- Web 优先承担“理解与比较”；
- CLI 优先承担“触发、查询、轮询、批处理与远程值守”；
- 两者都围绕同一组 Task / PendingAction / Decision / EventLog 数据工作；
- 任一入口做出的操作，都必须能被另一入口立即观察到。

因此，CLI 应允许用户在 WAITING_* 阶段跳转到 Web 页面继续处理，而 Web 也应允许用户回到 CLI 做轮询、审计和脚本化调用。

## 适用场景
<!-- SID:interface.scenarios.applicability -->

### Web 优先场景
<!-- SID:interface.scenarios.web_first -->

以下情况应默认优先使用 Web：

- 需要比较多个 patch/replan 候选；
- 需要查看较长 explanation 与 recommendation summary；
- 需要沿事件时间线理解为何进入 WAITING_*；
- 需要查看 HTML 报告、结构视图或图表；
- 需要由非命令行熟练用户完成确认操作。

### CLI 优先场景
<!-- SID:interface.scenarios.cli_first -->

以下情况应默认优先使用 CLI：

- 在远程机器上创建与监控任务；
- 在无桌面环境中处理 PendingAction；
- 在脚本中批量提交任务与收集结果；
- 在终端中快速查看任务状态、日志路径与报告路径；
- 在实验执行期间进行值守与巡检。

### 协同切换场景
<!-- SID:interface.scenarios.hybrid -->

以下情况应鼓励 Web 与 CLI 协同使用：

- 先通过 CLI 创建任务与等待稳定状态，再转入 Web 做人工确认；
- 在 Web 完成复杂确认后，回到 CLI 继续轮询直到终态；
- 在 CLI 中检测到 WAITING_* 时，输出可直接打开的任务详情或 pending review 页面；
- 在 Web 中查看报告与时间线，同时使用 CLI 导出 JSON、日志路径或批量结果。

## CLI 功能边界与命令面
<!-- SID:interface.cli.capability_scope -->

CLI 的设计原则是“最小闭环必须完整，高级体验可以渐进增强”。

### CLI 无头环境最小闭环保证
<!-- SID:interface.cli.headless_guarantee -->
CLI 必须能够在无图形界面的条件下完成以下最小闭环：

- 创建任务；
- 查询任务状态；
- 列出待决策 PendingAction；
- 查看候选摘要与默认建议；
- 提交 Decision；
- 输出报告、日志与快照的可访问路径。

CLI 不得把“打开浏览器”作为继续执行任务的唯一前提。

### CLI 向 Web 的显式跳转约束
<!-- SID:interface.cli.web_handoff -->
CLI 应支持向 Web 主界面进行显式跳转：

- 当检测到 WAITING_* 时，CLI 应输出对应 task_id、pending_action_id 以及建议打开的 Web 路由；
- 若运行环境允许，CLI 可以提供 `open` 子命令或 `--open-web` 选项；
- 该能力属于增强能力，而不是纯 CLI 闭环的必要前提。

### 建议命令树
<!-- SID:interface.cli.command_tree -->

建议的 CLI 命令树如下：

```text
design submit
design task show <task_id>
design task watch <task_id>
design pending list
design pending show <pending_action_id>
design decision apply <pending_action_id>
design timeline <task_id>
design report open <task_id>
design ui open
design ui open --task <task_id>
design ui open --pending <pending_action_id>
```

其中：

- `submit` 负责创建任务；
- `task show/watch` 负责查看与轮询；
- `pending list/show` 负责 WAITING_* 阶段的待办与候选摘要；
- `decision apply` 负责提交 `accept / replan / continue / cancel`；
- `timeline` 负责查看关键事件链；
- `ui open` 负责从 CLI 切换到 Web 主界面。

## Web 功能边界
<!-- SID:interface.web.capability_scope -->

Web 是系统的主操纵空间，因此其设计应优先覆盖“人工判断成本高”的环节，而不是简单重复 CLI 输出。

Web 至少应稳定承载以下能力：

- PendingAction 待办列表；
- Task detail 页面；
- Candidate comparison 区；
- Decision 提交表单；
- Event timeline 页面；
- Report / visualization 打开入口。

Web 的具体 UI 组织方式可以采用组件化前端框架，例如 React + TypeScript，但该框架只能服务于页面结构、组件复用、交互状态与渲染一致性，不改变 Web 作为 API 驱动交互壳的定位。

### Web 页面信息架构
<!-- SID:interface.web.information_architecture -->

建议 Web 的信息架构由以下页面或视图组成：

- Dashboard：待办列表、任务检索、系统消息；
- Task Detail：状态、当前步骤、摘要指标、风险提示、关联报告；
- Pending Review：候选比较、默认建议、Decision 表单；
- Event Timeline：WAITING/DECISION/RESUME 时间线；
- Report View：最终报告与结构/图表产物入口。

其中，Dashboard 与 Pending Review 共同构成主要操纵空间，Event Timeline 与 Report View 构成解释与审计空间。

## 与现有系统契约的对齐要求
<!-- SID:interface.constraints.contract_alignment -->

交互入口只能改变“用户如何操作系统”，不能改变“系统如何执行任务”。

因此，Web 与 CLI 都必须遵守以下对齐要求：

- 仅通过既有 API 暴露与提交交互数据；
- 将 WAITING_* 视为执行暂停的人在环路状态，而不是前端本地状态；
- 将 PendingAction 视为唯一待确认对象，将 Decision 视为唯一确认输入；
- 在任务进入 WAITING_* 前，依赖已持久化的快照与事件日志；
- 不得在前端或 CLI 中自行推断、跳过或合成状态转移；
- 即使 Web 使用 React 等组件化框架，也不得在浏览器侧复制 FSM、合成 EventLog 或直接驱动 Workflow。

### CLI 后端形态兼容性
<!-- SID:interface.cli.backend_compatibility -->
CLI 设计必须兼容两类后端形态：

- 当前实现可能是“提交后同步执行到 WAITING_* 或终态再返回”；
- 未来实现可能演进为“快速返回 task_id，再由客户端轮询状态”。

因此，CLI 的交互应围绕 `task_id + 状态查询 + 轮询` 构建，而不应假定 `POST /tasks` 的返回时机永久不变。

### API 集成边界
<!-- SID:interface.integration.api_boundary -->

CLI 与 Web 的共享集成边界应以以下接口为中心：

- `POST /tasks`
- `GET /tasks/{task_id}`
- `GET /pending-actions`
- `GET /pending-actions/{pending_action_id}`
- `POST /pending-actions/{pending_action_id}/decision`
- `GET /tasks/{task_id}/events`

这意味着 CLI 不应直接读取内部 Python 对象作为主交互方式；即便未来允许本地快捷路径，正式语义也应以 API 契约为准。

## 演进路线
<!-- SID:interface.rollout.milestones -->

建议按以下顺序落地：

1. 先提供基于 API 的 CLI MVP，覆盖提交、查询、轮询、待办、决策与打开 Web；
2. 保持现有 Web dashboard / event timeline 可用，并补齐 Pending review 与 report 跳转体验；
3. 再根据真实使用情况增强 CLI 的交互性，例如 TUI、表格渲染、JSON 导出与批量操作；
4. 当后端切换到异步任务模式时，优先保证 CLI 的 `watch` 与 Web 的自动刷新仍保持语义一致。

演进过程中，必须坚持“单执行内核、双交互入口”的原则，避免产生 Web 专属语义或 CLI 专属状态。
