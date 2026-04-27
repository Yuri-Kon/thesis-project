---
doc_key: interface_web_workspace
version: 1.0
status: stable
depends_on: [interface_surfaces, impl, hitl, tools]
---

# Web 主工作台设计：全信息展示、结构可视化与交互确认
<!-- SID:interface.web_workspace.overview -->

本文档细化 Web 端作为主操纵空间时的落地形态，明确页面框架、信息架构、交互要求与结构可视化约束。

本文档不重新定义 FSM、PendingAction、Decision 或 Agent 边界，只规定这些既有契约在浏览器端应如何被稳定、完整地呈现。

## 框架选择与边界
<!-- SID:interface.web_workspace.framework_choice -->

Web 端应继续采用 FastAPI 托管页面、静态资源与 API 的同仓模式：

- Web 框架使用 FastAPI；
- 页面层可以使用 React + TypeScript 组织组件、状态展示、表单与交互逻辑；
- React 构建产物应作为静态资源由 FastAPI 托管；
- 当前阶段不引入独立前端服务，也不引入前后端语义分裂。

这样做的原因不是降低前端能力，而是保证 Web 界面与 CLI、API、事件日志和报告产物共享同一部署边界，更适合研究型工作台与远程服务器环境。React 在这里是 UI 组织与组件化手段，不是新的执行入口或状态拥有者。

### React UI 组织与实现参考
<!-- SID:interface.web_workspace.react_ui_boundary -->

引入 React 的目标是解决纯手写 HTML、CSS 与 DOM TypeScript 分散、复用困难、构件反复调整成本高的问题。React 只应统一浏览器端 UI 能力：

- 可以抽象 API client、共享类型、页面级 view、复用组件、表单控件与候选对比组件；
- 可以维护组件展开状态、筛选条件、当前选中项、表单草稿和加载/错误提示；
- 不得在 React 本地 store 中复制或重定义任务状态机；
- 不得在浏览器侧合成 EventLog、PendingAction、Decision 或 TaskSnapshot；
- 不得绕过正式 API 直接驱动 Workflow、FSM、Agent 或事件日志写入。

因此，即使采用 React，Web 端仍然必须通过既有 API 读取任务、待办、事件和报告，并通过正式 Decision API 提交人工确认。

建议后续实现按以下具体约束落地。

#### 工程形态

React 前端应作为当前 FastAPI 应用内的静态 UI 子工程存在，而不是新的服务进程。推荐采用 Vite + React + TypeScript，构建产物继续由 `src/api/main.py` 中的 FastAPI `StaticFiles` 托管。

推荐目录形态如下：

```text
src/api/frontend/
  package.json
  tsconfig.json
  vite.config.ts
  index.html
  src/
    main.tsx
    app/App.tsx
    app/routes.ts
    api/client.ts
    api/endpoints.ts
    api/types.ts
    pages/DashboardPage.tsx
    pages/TaskDetailPage.tsx
    pages/EventTimelinePage.tsx
    components/pending/PendingActionList.tsx
    components/pending/PendingReviewWorkspace.tsx
    components/pending/CandidateComparison.tsx
    components/decision/DecisionForm.tsx
    components/timeline/EventTimeline.tsx
    components/report/ReportExplorer.tsx
    components/structure/StructureViewerPanel.tsx
    components/model/ModelInvocationPanel.tsx
    components/readiness/CapabilityReadinessPanel.tsx
    components/common/StatusBadge.tsx
    components/common/ErrorNotice.tsx
    state/uiState.ts
    styles/
```

该目录只表达浏览器端组织方式。后端 API、Pydantic schema、Workflow、事件日志和快照逻辑仍归现有 Python 模块所有。

#### 构建与托管

React 构建产物应输出到 FastAPI 已托管的静态目录下，建议使用独立子目录，避免与现有手写 JS/CSS 混杂：

```text
src/api/static/web/
  assets/
  manifest.json
```

FastAPI 页面路由仍由后端拥有，例如 `/ui`、`/ui/tasks/{task_id}`、`/ui/tasks/{task_id}/events`。这些路由可以返回同一个 React 宿主模板，例如 `src/api/templates/react_app.html`，并通过内嵌 bootstrap JSON 注入最小启动参数：

```json
{
  "view": "dashboard | task_detail | event_timeline",
  "taskId": "task_xxx",
  "pendingActionId": "pa_xxx"
}
```

bootstrap 只能用于初始化视图选择和 URL 上下文，不得作为任务状态、事件日志或决策结果的数据来源。页面加载后必须通过正式 API 拉取最新数据。

#### 路由映射

React 迁移不得改变对外 URL 语义。建议保持以下映射：

- `/ui`：渲染 Dashboard，默认拉取 `GET /pending-actions` 与能力 readiness 数据；
- `/ui/tasks/{task_id}`：渲染 Task Detail，并联动 Pending Review、Report Explorer 与上下文面板；
- `/ui/tasks/{task_id}/events`：渲染 Event Timeline，读取 `GET /tasks/{task_id}/events`；
- 后续如新增 `/ui/pending/{pending_action_id}`，也应仅作为 Pending Review 的深链入口，最终仍通过 `GET /pending-actions/{pending_action_id}` 与 Decision API 工作。

客户端路由可以使用轻量路由表，也可以由服务端路由直接注入 `view`。无论采用哪种方式，浏览器 URL 不应成为状态真相源；URL 只用于定位当前视图。

#### API Client 与类型

React 代码应集中通过 `api/client.ts` 与 `api/endpoints.ts` 访问后端，禁止组件内散落裸 `fetch`。API client 至少覆盖以下端点：

- `GET /tasks/{task_id}`;
- `GET /tasks/{task_id}/events`;
- `GET /tasks/{task_id}/report`;
- `GET /pending-actions`;
- `GET /pending-actions/{pending_action_id}`;
- `POST /pending-actions/{pending_action_id}/decision`;
- `GET /capabilities/readiness`。

`api/types.ts` 可以手写镜像当前响应字段，或后续由 OpenAPI 生成，但它只是前端类型投影，不是契约源头。字段命名、枚举值与可选性必须跟随后端 Pydantic schema，不得为了 UI 便利重命名契约字段。若 UI 需要派生字段，应在组件或 view model 层显式命名为 derived/display 字段。

错误处理应集中在 API client 层规范化为 UI 可展示错误，例如 `{ status, message, detail }`。错误展示不得吞掉后端状态码，也不得把请求失败解释成任务失败；任务是否失败只能以服务端 `TaskRecord.status` 和事件日志为准。

#### 状态模型

React 本地状态只能分为三类：

- 渲染状态：展开/折叠、选中 tab、排序字段、筛选条件、当前高亮事件；
- 表单草稿：Decision comment、selected_candidate_id、decided_by 等提交前输入；
- 请求状态：loading、error、lastRefreshedAt、inFlight request id。

服务端状态包括 `TaskRecord.status`、`internal_status`、`PendingAction.status`、候选列表、Decision 结果、EventLog 和 Report metadata。服务端状态只能通过 API 获取和刷新，不能复制到一个可被前端自行修改的业务 store 中。

若使用缓存库或查询 hook，只能把它当作请求缓存和刷新协调层：

- cache key 必须以 API 资源为单位，例如 `task:{task_id}`、`events:{task_id}`、`pending-actions`；
- 提交 Decision 成功后必须刷新 task、pending-actions、pending-action detail 与 events；
- 不得通过本地 optimistic update 伪造状态转换；
- 不得在浏览器侧根据 Decision choice 预设下一状态。

#### 组件职责划分

页面级组件负责组合数据请求和布局，领域组件负责展示一个稳定概念，通用组件只处理纯 UI。

推荐组件边界如下：

- `DashboardPage`：待办列表、任务检索、系统消息和 readiness 摘要；
- `TaskDetailPage`：单任务上下文聚合，组合任务概览、当前 PendingAction、Report Explorer 与模型调用面板；
- `EventTimelinePage`：事件查询、过滤和 WAITING -> DECISION -> RESUME 链路展示；
- `PendingActionList`：只展示待办摘要并发出选择事件，不提交 Decision；
- `PendingReviewWorkspace`：组合候选对比、推荐解释、受影响步骤提示与 DecisionForm；
- `CandidateComparison`：展示候选差异、风险、成本、工具元数据与 readiness，不决定业务选择；
- `DecisionForm`：只构造并提交 `DecisionSubmitRequest`，提交成功后通知页面刷新；
- `EventTimeline`：只展示服务端事件，不合成事件；
- `ReportExplorer`：展示报告、结构、图表、日志与下载入口；
- `StructureViewerPanel`：封装 NGL 或后续结构查看器，失败时提供直链和文本降级；
- `ModelInvocationPanel`：展示 tool/provider/model/endpoint/job/failure/recovery 信息，不提供绕过 Workflow 的任意调用按钮。

组件之间传递的数据应优先使用后端响应对象或显式 view model。禁止组件直接导入 Python 生成的本地文件、日志文件或快照文件作为主数据源。

#### 页面数据流

Dashboard 数据流：

1. 页面加载后请求 `GET /pending-actions`；
2. 并行请求 `GET /capabilities/readiness`；
3. 用户选择任务后跳转或加载 `/ui/tasks/{task_id}`；
4. 刷新按钮只重新请求 API，不修改本地业务状态。

Task Detail 数据流：

1. 从 bootstrap 或 URL 获得 `task_id`；
2. 请求 `GET /tasks/{task_id}`；
3. 若存在 `pending_action`，请求 `GET /pending-actions/{pending_action_id}`；
4. 若任务有报告，按需请求 `GET /tasks/{task_id}/report`；
5. Decision 提交成功后刷新 task、pending-action、pending-actions 和 events。

Event Timeline 数据流：

1. 从 bootstrap 或 URL 获得 `task_id`；
2. 请求 `GET /tasks/{task_id}/events`；
3. 可按 event_type、tool_id、capability_id 等服务端支持参数筛选；
4. WAITING/DECISION/RESUME 链路只能从返回事件中检测并展示，不能补造缺失事件。

Pending Review 数据流：

1. 使用 `PendingActionDetail.candidates` 渲染候选；
2. 默认推荐只展示 `default_suggestion`，不自动提交；
3. 用户显式选择 candidate 和 choice；
4. 提交 `POST /pending-actions/{pending_action_id}/decision`；
5. 根据 API 返回的 `TaskRecord` 和后续刷新结果更新 UI。

#### 样式与可维护性

React 迁移后应收敛现有 CSS 分散问题。推荐建立全局 design tokens 与组件局部样式：

- 全局 token：颜色、间距、字号、圆角、阴影、状态色；
- 状态色必须覆盖 `WAITING_*`、`RUNNING`、`DONE`、`FAILED`、`CANCELLED`、readiness degraded/unavailable；
- 组件样式应与组件同名或同目录组织，避免单个大型 CSS 文件继续膨胀；
- 报告、结构查看器和时间线可以有专属样式模块，但应复用全局 token。

视觉调整不得改变状态含义。例如红色错误样式不能用于普通 warning，`WAITING_*` 也不能被展示成失败态。

#### 迁移顺序

为降低风险，React 迁移应采用并行替换，而不是一次性重写：

1. 建立 React 子工程、构建脚本和 FastAPI 宿主模板，保持旧 dashboard/timeline 可用；
2. 迁移 API client、类型定义、StatusBadge、ErrorNotice 等基础层；
3. 迁移 Dashboard 与 PendingActionList，验证 `/ui` 待办列表一致；
4. 迁移 Task Detail 与 Pending Review，验证 Decision 提交流程一致；
5. 迁移 Event Timeline，验证 WAITING -> DECISION -> RESUME 链路展示一致；
6. 迁移 Report Explorer、ModelInvocationPanel 与 CapabilityReadinessPanel；
7. 迁移 StructureViewerPanel，并保留 PDB 直链与文本降级；
8. 旧模板与手写 TS 只有在功能、路由、降级和测试都达到等价后才能删除。

每一步迁移都应保持现有 API 不变，并允许 CLI 继续完成无头闭环。

#### 验收清单

React UI 首次替换现有页面前，应至少满足以下检查：

- `GET /ui`、`GET /ui/tasks/{task_id}`、`GET /ui/tasks/{task_id}/events` 均能返回可加载页面；
- Dashboard 能列出与旧 UI 一致的 pending actions；
- Task Detail 能展示 `TaskRecord.status`、`internal_status`、goal、pending_action 和报告入口；
- Pending Review 能展示候选、默认建议、risk/cost/tool/readiness 信息；
- DecisionForm 提交的请求体与现有 `DecisionSubmitRequest` 兼容；
- Decision 成功后不会本地伪造状态，而是刷新 API 并展示服务端返回结果；
- Event Timeline 展示的事件均来自 `GET /tasks/{task_id}/events`；
- 结构查看失败时仍能看到 PDB 链接、指标和文本摘要；
- 浏览器刷新、直接打开深链、无 pending action、任务不存在和 API 报错均有明确降级；
- CLI 不依赖 React 页面也能继续提交、查询、轮询和提交 Decision。

## 设计原则
<!-- SID:interface.web_workspace.design_principles -->

Web 主工作台必须同时满足以下原则：

- 全信息可达：任务、步骤、候选、日志、报告、结构与产物入口必须都能在 Web 中找到；
- 决策上下文同屏：PendingAction、候选差异、风险/成本解释与 Decision 操作应尽量在一个工作区中联动；
- 交互优先而非静态展示：用户必须能筛选、对比、展开、切换、定位和确认，而不是只读报告；
- 结构可视化原生存在：蛋白质结构查看不是报告附件，而是工作台的一等能力；
- 对无头环境友好：Web 是主空间，但不能假定所有任务都只在图形环境完成，因此要与 CLI 保持明确衔接。

## 顶层布局
<!-- SID:interface.web_workspace.primary_layout -->

Web 主工作台建议采用“三栏 + 工作区”的布局思路：

- 左侧为任务导航区，承载任务列表、待办、过滤器与最近活动；
- 中央为主工作区，承载 Task Detail、Pending Review、Timeline 与 Report 等主视图；
- 右侧为上下文检查区，承载当前步骤、模型调用摘要、风险提示、工件路径与 Decision 操作。

当屏幕较窄时，可折叠左右两栏，但中央工作区必须保持为信息主轴。

### 页面拓扑
<!-- SID:interface.web_workspace.page_topology -->

建议 Web 主工作台由以下视图组成：

- Dashboard：任务总览、待确认列表、筛选器、系统消息；
- Task Detail：任务主视图，展示当前阶段、步骤、产物与上下文；
- Pending Review：候选对比、解释信息与确认表单；
- Event Timeline：WAITING、DECISION、RESUME、FAILED、DONE 等事件链；
- Report Explorer：HTML 报告、结构产物、图表与导出入口。

这些视图应共享统一的 task context，避免用户在多个页面之间重新理解状态。

### Dashboard 要求
<!-- SID:interface.web_workspace.dashboard -->

Dashboard 应至少展示：

- 当前处于 `WAITING_*` 的任务；
- 最近变更任务与终态任务；
- 按任务状态、目标类型、工具链、时间范围的过滤能力；
- 任务卡片中的核心摘要，例如当前步骤、最后事件、风险提示、报告可用性。

Dashboard 的目标不是替代 Task Detail，而是帮助用户快速定位“下一步该处理什么”。

### Task Detail 要求
<!-- SID:interface.web_workspace.task_detail -->

Task Detail 必须作为“单任务真相页”存在，至少包含以下区域：

- 任务头部：task_id、目标描述、状态徽标、创建时间、最近更新时间；
- 运行概览：当前阶段、当前步骤、最近事件、失败码、重试/patch/replan 历史摘要；
- 输入与约束：任务目标、约束条件、关键输入参数；
- 工件区：报告、PDB、日志、指标文件、快照与下载入口；
- 上下文区：当前 PendingAction、最新 Decision、关联事件片段。

如果 Web 端只能打开报告而不能看清任务上下文，就不能被视为主工作台。

### Pending Review 工作区
<!-- SID:interface.web_workspace.pending_review -->

Pending Review 应作为高优先级主视图设计，而不是简单表单页。它至少要支持：

- 候选列表与默认推荐候选；
- 候选之间的并排比较；
- explanation、risk、cost、expected_effect 等解释字段的同屏查看；
- 当前执行前缀、受影响步骤与恢复语义的显式提示；
- 提交 `accept / replan / continue / cancel` 的正式入口。

在 WAITING_* 状态下，用户应能不离开该工作区就完成“理解上下文 -> 比较候选 -> 提交决策”的完整闭环。

### 模型调用工作台
<!-- SID:interface.web_workspace.model_invocation_panel -->

Web 端应借鉴 NVIDIA NIM 一类模型调用界面的处理方式，把“模型/工具调用上下文”设计成可展开的操作面板，而不是只显示一条日志。

该面板建议包含：

- 调用对象：tool_id、provider、model、adapter、endpoint 类型；
- 输入摘要：标准化后的输入参数、关键约束、推理模式或运行模式；
- 运行状态：pending、running、completed、failed、retrying；
- 输出摘要：核心结果字段、工件链接、指标摘要；
- 调试信息：job_id、remote request id、耗时、失败码与恢复动作建议。

这一面板的重点是帮助用户理解“系统正在调什么、为什么失败、下一步如何确认”，而不是开放一个绕过 Workflow 的任意调用入口。

### 结构可视化工作区
<!-- SID:interface.web_workspace.structure_visualization -->

Web 端必须把蛋白质结构可视化视为一等能力。建议采用 NGL Viewer 作为浏览器内 3D 结构查看器，并满足以下要求：

- 能直接加载任务产物中的 PDB；
- 提供旋转、缩放、自动对焦等基础交互；
- 支持至少一种主表示法，例如 cartoon；
- 支持附加表示法，例如 ball+stick 或按置信度着色；
- 在查看器加载失败时，明确提供 PDB 直链与错误提示。

结构查看区应与任务上下文联动，而不是只在最终 HTML 报告中孤立存在。

### 结构与指标联动
<!-- SID:interface.web_workspace.structure_metric_linking -->

结构可视化不应只停留在“能看 3D 模型”，还应支持与指标区形成联动：

- 当存在 pLDDT、B-factor 或其他 residue-level 指标时，应允许用户在图表与结构之间建立定位关系；
- 当候选方案切换时，应同步刷新结构与指标摘要；
- 当存在多个结构产物时，应允许用户在同一上下文中切换不同构象或不同候选。

第一阶段可以只做到“切换候选时同步刷新结构与图表”，后续再增强到残基级联动。

### 报告与产物浏览
<!-- SID:interface.web_workspace.report_explorer -->

Report Explorer 应把结果浏览做成工作台能力，而不仅是“打开一个 HTML 文件”：

- 可嵌入最终 HTML 报告；
- 可列出所有关联工件并按类型过滤；
- 可区分结构文件、指标文件、日志文件与静态图；
- 对交互式图表提供内嵌浏览入口；
- 对不可内嵌内容提供下载与外部打开入口。

Report Explorer 与 Task Detail 应共享同一个 task context，避免用户在报告页丢失任务状态。

## 交互模式
<!-- SID:interface.web_workspace.interaction_patterns -->

Web 端至少应提供以下交互模式：

- 自动刷新或手动刷新任务状态；
- 筛选与搜索；
- 候选并排对比；
- 关键字段折叠与展开；
- 从 Timeline 跳转到对应 PendingAction 或 Report；
- 从任务卡片快速进入待确认工作区。

这些交互能力的目标是降低理解成本，而不是让用户自行拼接多页信息。

### 状态同步约束
<!-- SID:interface.web_workspace.state_sync -->

Web 端必须把自己视为 API 驱动的观察者与操作者，而不是状态拥有者：

- 任务状态以服务端为准；
- WAITING_* 语义以 PendingAction 与事件日志为准；
- Decision 提交必须经过正式 API；
- Web 本地只能维护渲染状态、筛选状态和临时交互状态；
- 不得在浏览器侧合成新的执行语义或跳过现有确认流程。

### 可视化降级与网络约束
<!-- SID:interface.web_workspace.visualization_fallback -->

由于 NGL 这类浏览器可视化组件可能依赖网络、CDN 或浏览器能力，Web 端必须定义明确的降级路径：

- 结构查看器初始化失败时显示原因；
- 提供直接打开 PDB 的入口；
- 保留静态指标与文本摘要，不因 3D 查看器失败而失去任务可读性；
- 不把结构可视化成功作为完成人工确认的前置条件。

## MVP 与演进
<!-- SID:interface.web_workspace.milestones -->

Web 主工作台建议按以下顺序落地：

1. 先补齐 Dashboard、Task Detail、Pending Review 三个核心视图；
2. 将 Event Timeline 与 Report Explorer 统一到 task context 下；
3. 把现有 NGL + Plotly 能力从“报告内嵌”提升为“工作台内可访问能力”；
4. 再逐步增强候选对比、结构-指标联动与多产物切换。

演进过程中，Web 端始终应保持“全信息展示、强交互确认、结构可视化原生存在”的定位。
