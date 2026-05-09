# 前端工作台实现

## 1. 前端实现定位

前端实现位于 `../thesis-project.dev/src/api/frontend/`，使用 React、TypeScript 和 Vite 构建。其目标不是做独立业务系统，而是为后端任务状态提供操作员工作台：用户可以创建任务草稿、查看任务状态、审查 PendingAction 候选、提交人工决策、查看事件时间线、浏览报告和结构产物。

前端的状态来源是后端 API。`main.tsx` 在启动时读取后端注入的 bootstrap payload，判断当前视图是 Dashboard、Task Builder、Task Detail 还是 Event Timeline；随后通过 `apiClient` 拉取 pending actions、capability readiness、task record、event timeline、pending action detail 和 report。该设计使前端成为后端状态的投影，避免前端自行推导工作流状态。

## 2. 页面结构

| 页面 | 主要组件 | 论文表述重点 |
| --- | --- | --- |
| Dashboard | `PendingActionList`、`CapabilityReadinessPanel`、`ModelInvocationPanel`、`TaskSearch` | 展示待审查队列、能力健康状态和任务检索入口。 |
| Task Builder | `TaskDraftForm`、`SafetyPrecheckPanel`、`DraftProtectionDialog` | 支持任务字段收敛、场景门控和确认前检查。 |
| Task Detail | `PendingReviewWorkspace`、`ReportExplorer`、`StructureViewerPanel`、`CapabilityReadinessPanel` | 聚合单个任务的状态、待决策候选、报告和结构产物。 |
| Event Timeline | `MetricCard`、`StatusBadge`、timeline list | 将任务事件按时间线展示，用于审计和调试。 |

整体布局采用三栏工作台：左侧 `WorkbenchSidebar` 提供导航和任务上下文，中间主区域展示当前页面，右侧 `InspectorPanel` 展示与页面相关的摘要和理论对象。这个布局适合长时间任务监控和候选审查，因为用户可以在主操作区之外持续看到当前任务状态、待决策数量和候选依据。

## 3. API Client 与类型边界

`api/client.ts` 封装了所有后端请求，包括任务查询、事件查询、报告查询、PendingAction 查询、Decision 提交、Task Intake 创建与确认、能力 readiness 查询、场景门控预览等。`api/types.ts` 维护与后端响应对齐的 TypeScript 类型，例如 `TaskRecord`、`ExternalStatus`、`InternalStatus`、`PendingActionDetail`、`DecisionRequest`、`CapabilityReadinessEntry`。

这种类型边界的设计原因是：前端展示的对象本身就是论文实现中的核心契约。如果不在前端保留类型定义，字段变化会在运行时才暴露；使用 TypeScript 能够在构建阶段发现字段缺失、状态枚举不匹配和候选详情结构变化。

## 4. Pending Review 工作区

人工审查工作区由 `PendingReviewWorkspace`、`CandidateComparison` 和 `DecisionForm` 组成。该区域展示三类信息：

1. 运行时上下文：默认候选、推荐原因、RuntimeState JSON、Score JSON 和 evidence refs。
2. 候选对比：候选 ID、默认标记、风险等级、成本估计、影响步骤、工具和恢复语义。
3. 决策提交：根据 action type 提供 `accept`、`replan`、`continue`、`cancel` 等选择，并把 `selected_candidate_id`、`decided_by`、`comment` 提交给后端。

这部分是论文前端实现中最值得截图的区域，因为它直接体现了 CEBRA-WP 与人在环路之间的结合：算法输出不是隐藏在后台，而是以候选、分数、证据和推荐理由的形式呈现给用户。

## 5. 能力 readiness 与结构产物展示

`CapabilityReadinessPanel` 和 `ModelInvocationPanel` 用于展示工具能力是否可用、降级或阻断，帮助用户理解当前候选为什么选择某些工具或需要降级执行。`StructureViewerPanel` 目前读取 `task.design_result.structure_pdb_path` 并展示结构产物链接，同时保留可视化区域占位。论文中可以表述为：系统已在任务详情页预留结构产物查看入口，并可与后续 3D Viewer 集成；当前实现至少保证 PDB artifact 能从任务结果中追踪。

## 6. 前端可写入论文的实现要点

1. 前端采用 API-driven 工作台结构，状态来源于后端 `TaskRecord`、`PendingActionDetail` 和 `TaskTimelineEvent`。
2. Dashboard 用于全局监控，Task Detail 用于单任务审查，Event Timeline 用于审计回放，Task Builder 用于任务录入。
3. Pending Review 工作区把 RuntimeState、候选评分、证据引用和决策表单放在同一操作界面，支撑人在环路。
4. 前端使用 TypeScript 类型对齐后端 schema，降低 API 字段漂移风险。
5. 结构展示当前以产物链接和占位视图为主，适合作为系统实现截图中的“结构产物入口”。

## 7. 建议插图

- 图：Dashboard 工作台，展示待审查队列和能力 readiness，占位见 `FIG-UI-DASHBOARD`。
- 图：Task Builder 任务录入界面，占位见 `FIG-UI-TASK-BUILDER`。
- 图：Task Detail + Pending Review，展示候选对比、Runtime JSON 和 Decision Form，占位见 `FIG-UI-PENDING-REVIEW`。
- 图：Event Timeline，展示状态迁移与关键事件，占位见 `FIG-UI-EVENT-TIMELINE`。
- 图：Structure Viewer Panel，展示 PDB artifact 链接与可视化占位，占位见 `FIG-UI-STRUCTURE-PANEL`。

