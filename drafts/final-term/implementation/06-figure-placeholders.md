# 实现截图与图表占位清单

本文件用于后续补充论文截图。当前先给出占位符、截图内容、建议说明文字和对应代码/接口来源。

## 1. 后端与接口截图

### FIG-API-OPENAPI：FastAPI 接口文档截图

占位符：

```markdown
![FastAPI 接口文档占位图](figures/final-term/fig-api-openapi-placeholder.png)
```

建议内容：打开后端 `/docs` 页面，截取任务、task-intake、pending-actions、capabilities 分组接口。

论文图注建议：系统后端基于 FastAPI 暴露任务创建、任务查询、待决策审查、人工决策提交和能力 readiness 查询接口。

对应代码：`../thesis-project.dev/src/api/main.py`

### FIG-API-PENDING-DETAIL：PendingAction 详情 JSON 截图

占位符：

```markdown
![PendingAction 详情响应占位图](figures/final-term/fig-api-pending-detail-placeholder.png)
```

建议内容：调用 `GET /pending-actions/{pending_action_id}`，截取 candidates、runtime_state_summary、score_breakdown、workflow_action_reason、evidence_refs 字段。

论文图注建议：PendingAction 详情接口将候选方案、运行时状态、评分和证据引用统一提供给前端审查界面。

对应代码：`../thesis-project.dev/src/api/main.py:1761`

### FIG-BACKEND-DECISION-FLOW：人工决策接口调用链

占位符：

```markdown
![人工决策调用链占位图](figures/final-term/fig-backend-decision-flow-placeholder.png)
```

建议内容：可以用 Mermaid 或流程图绘制 `PendingAction -> DecisionSubmitRequest -> decision_apply -> status transition -> snapshot`。

论文图注建议：人工决策提交后，后端校验待决策对象与当前状态，应用候选方案并写入事件日志和任务快照。

对应代码：`../thesis-project.dev/src/workflow/decision_apply.py`

## 2. 前端工作台截图

### FIG-UI-DASHBOARD：Dashboard 工作台

占位符：

```markdown
![Dashboard 工作台占位图](figures/final-term/fig-ui-dashboard-placeholder.png)
```

建议内容：截取待审查数量、能力 readiness、任务检索和右侧 Inspector。

论文图注建议：Dashboard 页面为操作者提供待审查队列、能力健康状态和任务检索入口。

对应代码：`../thesis-project.dev/src/api/frontend/src/pages/DashboardPage.tsx`

### FIG-UI-TASK-BUILDER：任务录入与确认界面

占位符：

```markdown
![Task Builder 占位图](figures/final-term/fig-ui-task-builder-placeholder.png)
```

建议内容：截取任务目标输入、结构化字段、缺失字段提示、安全预检或场景门控提示。

论文图注建议：Task Builder 将自然语言任务目标逐步收敛为可确认的结构化任务规格。

对应代码：`../thesis-project.dev/src/api/frontend/src/pages/TaskBuilderPage.tsx`

### FIG-UI-PENDING-REVIEW：Pending Review 候选审查界面

占位符：

```markdown
![Pending Review 候选审查占位图](figures/final-term/fig-ui-pending-review-placeholder.png)
```

建议内容：截取 Runtime Context、Candidate Comparison 和 Decision Form 三个区域。

论文图注建议：待决策审查界面同时展示默认建议、运行时状态、候选对比和人工决策表单。

对应代码：`../thesis-project.dev/src/api/frontend/src/components/PendingReviewWorkspace.tsx`

### FIG-UI-EVENT-TIMELINE：事件时间线界面

占位符：

```markdown
![事件时间线占位图](figures/final-term/fig-ui-event-timeline-placeholder.png)
```

建议内容：截取任务事件列表，突出 WAITING_ENTER、DECISION_SUBMITTED、DECISION_APPLIED、STEP_EXECUTED 等关键事件。

论文图注建议：事件时间线将任务状态迁移和关键运行事件按顺序呈现，支持审计与调试。

对应代码：`../thesis-project.dev/src/api/frontend/src/pages/EventTimelinePage.tsx`

### FIG-UI-STRUCTURE-PANEL：结构产物入口

占位符：

```markdown
![结构产物入口占位图](figures/final-term/fig-ui-structure-panel-placeholder.png)
```

建议内容：截取 Task Detail 中的 Structure Viewer Panel，展示 PDB artifact 路径或无结构产物提示。

论文图注建议：任务详情页预留结构产物展示入口，并通过 PDB artifact 路径连接执行结果与可视化模块。

对应代码：`../thesis-project.dev/src/api/frontend/src/components/StructureViewerPanel.tsx`

## 3. 工作流与运行时图

### FIG-WORKFLOW-RUNTIME：PlanRunner/StepRunner 执行流程图

占位符：

```markdown
![工作流运行时流程占位图](figures/final-term/fig-workflow-runtime-placeholder.png)
```

建议内容：绘制 `PlanRunner -> StepRunner -> ToolAdapter -> StepResult -> WorkflowContext -> RuntimeState`。

论文图注建议：工作流运行时将计划步骤转换为统一 StepResult，并通过 WorkflowContext 更新安全事件和运行时状态。

### FIG-WORKFLOW-HITL：WAITING 状态与决策恢复流程图

占位符：

```markdown
![WAITING 状态与决策恢复占位图](figures/final-term/fig-workflow-hitl-placeholder.png)
```

建议内容：绘制 `RUNNING -> WAITING_PATCH/WAITING_REPLAN -> Decision -> PATCHING/REPLANNING/RUNNING/FAILED`。

论文图注建议：系统在高风险或失败恢复节点通过 PendingAction 暂停执行，收到人工 Decision 后再恢复工作流。

### FIG-RUNTIME-EVALUATOR：CEBRA-WP runtime adjustment 示意图

占位符：

```markdown
![运行时重排示意占位图](figures/final-term/fig-runtime-evaluator-placeholder.png)
```

建议内容：绘制 `static_score + RuntimeState -> runtime_adjustment -> final_score -> default_recommendation`。

论文图注建议：RuntimeEvaluator 将运行时状态引入候选重排，使默认建议能够反映失败证据、预算压力和恢复余量。

## 4. 截图采集建议

1. 先启动后端和前端构建产物，打开 `/ui`、`/ui/task-builder`、`/ui/tasks/{task_id}`、`/ui/tasks/{task_id}/events`。
2. 准备一个进入 WAITING 状态的样例任务，使 Pending Review 界面有候选可展示。
3. 论文截图优先展示真实字段，但可以遮挡绝对路径、远程 endpoint 或无关机器信息。
4. 若暂时无法复现实任务，可保留占位图，并在正文中先以“界面原型/实现页面”描述，不写具体实验结果。

