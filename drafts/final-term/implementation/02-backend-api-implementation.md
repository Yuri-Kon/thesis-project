# 后端 API 与数据契约实现

## 1. 后端实现定位

后端实现承担三个职责：一是任务生命周期的入口，将用户输入转化为 `ProteinDesignTask` 或 Task Intake 会话；二是对外暴露任务、待决策、事件时间线和报告查询接口；三是连接 Workflow 运行时，将任务执行、人工决策和状态迁移统一到 `TaskRecord`。

当前后端入口位于 `../thesis-project.dev/src/api/main.py`，应用使用 FastAPI 创建，并在启动时初始化运行时路径、工具知识图谱、输出目录、日志目录和快照目录。任务记录在原型阶段使用内存 `TASK_STORE` 保存；事件日志和快照由 storage 模块写入文件，以支持审计和恢复材料提取。

## 2. 核心 API 分组

| 分组 | 代表接口 | 作用 |
| --- | --- | --- |
| UI HTML 入口 | `GET /ui`、`GET /ui/tasks/{task_id}`、`GET /ui/tasks/{task_id}/events`、`GET /ui/task-builder` | 返回 React 工作台 HTML，注入当前视图和任务 ID。 |
| 健康与能力 | `GET /health`、`GET /capabilities/readiness`、`GET /capabilities/scenario-gate/preview` | 展示运行时路径、工具数量、能力 readiness 和场景门控预览。 |
| Task Intake | `GET /task-intakes/schema`、`POST /task-intakes`、`PATCH /task-intakes/{id}`、`POST /task-intakes/{id}/confirm` | 支持任务草稿、字段补充、确认和正式任务创建。 |
| 任务执行 | `POST /tasks`、`GET /tasks/{task_id}`、`GET /tasks/{task_id}/report`、`GET /tasks/{task_id}/events` | 创建任务、查看任务状态、读取报告和事件时间线。 |
| 人在环路 | `GET /pending-actions`、`GET /pending-actions/{id}`、`POST /pending-actions/{id}/decision` | 展示待审查候选并提交人工决策。 |

## 3. 数据契约

后端数据契约集中在 `src/models/contracts.py` 和 `src/models/db.py`。其中 `ProteinDesignTask` 描述任务输入，`Plan` 和 `PlanStep` 描述可执行计划，`StepResult` 描述单步执行结果，`SafetyResult` 描述安全检查结果，`PendingAction` 和 `Decision` 描述人在环路，`TaskSnapshot` 描述可恢复上下文。

`TaskRecord` 是 API 对外返回的任务记录模型，包含外部状态、内部状态、任务目标、约束、计划、设计结果、当前待决策对象、决策历史和安全事件。外部状态面向用户展示，如 `WAITING_PATCH_CONFIRM`；内部状态保留执行细节，如 `WAITING_PATCH`、`PATCHING`、`WAITING_REPLAN`、`REPLANNING`。这种双状态设计避免 UI 暴露过多内部细节，同时保留恢复流程所需的精确状态。

## 4. 任务创建流程

`POST /tasks` 支持三种入口：`goal`、`query` 和 `confirmed_task_spec`。其中 `query` 会被转换为 Task Intake，会话进入待确认；`confirmed_task_spec` 会先经过场景门控，若结果允许则创建正式任务；`goal` 则兼容早期直接任务创建路径，构造 `ProteinDesignTask` 后调用 `run_task_sync`。

这一路径体现了系统从简单 Demo 到可审查任务录入的演进：早期可以直接给 goal 创建任务，正式工作台则优先通过 Task Intake 收敛字段，减少自然语言直接执行带来的不确定性。

## 5. PendingAction 与 Decision API

人在环路接口是后端实现的重点。`GET /pending-actions` 遍历任务记录，返回仍处于 pending 状态的待决策对象摘要，包括候选数量、默认建议和解释。`GET /pending-actions/{id}` 返回更详细的候选比较信息，包括 runtime state、score breakdown、workflow action reason、evidence refs 和 theory objects 等展示字段。`POST /pending-actions/{id}/decision` 接收用户选择，并根据 action type 调用 `apply_plan_confirm_decision`、`apply_patch_confirm_decision` 或 `apply_replan_confirm_decision`。

这一设计使 UI 只需要提交结构化 Decision，不需要知道如何修改 Plan 或推进状态机。具体的计划应用、补丁应用、等待状态退出、事件日志和快照写入都在后端完成。

## 6. 后端可写入论文的实现要点

1. 后端使用 FastAPI 暴露任务与人工决策接口，并用 Pydantic 模型统一请求和响应结构。
2. Task Intake 将自然语言输入转换为可确认的结构化任务，避免自由文本直接驱动高代价执行。
3. PendingAction/Decision 将人在环路建模为一等数据结构，而不是 UI 层的临时按钮状态。
4. API 详情页将候选评分、运行时状态和证据引用展开给前端，支撑论文中“可解释人工审查”的实现描述。
5. 原型阶段使用内存任务记录，配合日志和快照保留审计材料；生产化持久化可作为后续扩展。

## 7. 建议插图

- 图：FastAPI 接口分组截图，占位见 `06-figure-placeholders.md` 的 `FIG-API-OPENAPI`。
- 图：`GET /pending-actions/{id}` 返回的候选详情 JSON 截图，占位见 `FIG-API-PENDING-DETAIL`。
- 图：任务状态从 `WAITING_*` 经 Decision 返回执行态的接口调用链，占位见 `FIG-BACKEND-DECISION-FLOW`。

