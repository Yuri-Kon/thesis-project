# 技术栈与工程结构

## 1. 技术栈概览

| 层次 | 当前实现 | 设计原因 |
| --- | --- | --- |
| 后端语言与运行时 | Python 3.12 | 与生物信息学工具、脚本和模型服务生态兼容，便于快速封装本地/远程计算能力。 |
| Web API | FastAPI 0.128.0 + Starlette | 支持 Pydantic 模型校验、自动 OpenAPI 文档和异步接口，适合作为任务、待决策和事件查询边界。 |
| 数据契约 | Pydantic 2.12.5 | 对任务、计划、步骤结果、风险、PendingAction、Decision、RuntimeState 等对象做结构化校验。 |
| 前端 | React 19 + TypeScript 5.9 + Vite 7 | 实现轻量工作台，使用类型定义对齐后端响应，便于快速构建 Dashboard、Task Detail、Pending Review 等页面。 |
| 工作流控制 | 自定义 Workflow/FSM + PlanRunner/StepRunner | 当前控制语义需要严格对齐 `Plan -> StepResult -> PendingAction -> Decision -> Snapshot`，因此使用显式状态机而不是把控制权交给外部流程引擎。 |
| 工具接入 | ToolAdapter + AdapterRegistry | 将具体生物信息学工具、远程模型服务和本地脚本隔离在统一接口后，Executor 只依赖抽象适配器。 |
| 运行时决策 | RuntimeState + RuntimeEvaluator | 承载 CEBRA-WP 的 Lite belief-state、runtime adjustment 和动作 utility。 |
| 存储与审计 | 本地日志、快照、产物目录 | 原型阶段便于复现实验、检查事件链路和恢复上下文；后续可替换为数据库或对象存储。 |
| 质量保证 | pytest + basedpyright | pytest 支持行为验证，basedpyright 约束类型边界，减少契约漂移。 |

## 2. 后端目录结构

当前后端核心目录位于 `../thesis-project.dev/src/`：

```text
src/
  api/
    main.py                 # FastAPI 应用、任务接口、HITL 接口、UI HTML 入口
    schemas.py              # API 相关 schema
    frontend/               # React/Vite 前端源码
  models/
    contracts.py            # ProteinDesignTask、Plan、StepResult、PendingAction 等契约
    db.py                   # ExternalStatus、InternalStatus、TaskRecord 等记录模型
    runtime_schemas.py      # ActionUtility 等运行时 schema
  workflow/
    workflow.py             # 同步任务执行入口 run_task_sync
    context.py              # WorkflowContext 与 RuntimeState 更新入口
    plan_runner.py          # 完整 Plan 执行与状态推进
    step_runner.py          # 单个 PlanStep 执行、重试、安全检查、适配器调用
    pending_action.py       # WAITING_* 状态前的 PendingAction、日志、快照写入
    decision_apply.py       # 人工决策应用到 Plan/Patch/Replan
    snapshots.py            # TaskSnapshot 构建与 runtime_state 注入
    runtime_evaluator.py    # runtime adjustment、候选重排与 action utility
    recovery.py             # 恢复、动作选择、terminal stop 候选等
  agents/
    planner.py              # 初始计划、patch、replan 候选生成
    executor.py             # ExecutorAgent，封装 PlanRunner/StepRunner
    safety.py               # 输入/步骤/输出安全检查
    summarizer.py           # DesignResult 与报告汇总
  adapters/
    base_tool_adapter.py    # 统一工具适配器接口
    registry.py             # 适配器注册表
    *_adapter.py            # ESMFold、ProteinMPNN、RDKitProps 等具体适配器
  kg/
    kg_client.py
    protein_tool_kg.json    # 工具能力、I/O、成本、安全信息
  storage/
    log_store.py
    snapshot_store.py
```

该结构基本对应论文中的五层架构：`api` 对应输入交互层，`agents` 与 `workflow` 对应规划/执行/安全汇总层，`adapters` 与 `kg` 对应工具能力与资源层，`models` 则作为跨层数据契约。

## 3. 前端目录结构

前端源码位于 `../thesis-project.dev/src/api/frontend/src/`：

```text
frontend/src/
  main.tsx                         # 工作台入口、全局状态加载与视图路由
  api/
    client.ts                      # fetch 封装与 API 方法
    types.ts                       # 后端响应的 TypeScript 类型
  pages/
    DashboardPage.tsx              # 总览页：待审查、能力 readiness、任务检索
    TaskBuilderPage.tsx            # 任务录入与确认
    TaskDetailPage.tsx             # 任务状态、PendingReview、报告和结构产物
    EventTimelinePage.tsx          # 事件时间线
  components/
    PendingReviewWorkspace.tsx     # 人工审查主区域
    CandidateComparison.tsx        # 候选方案对比
    DecisionForm.tsx               # 人工决策提交
    CapabilityReadinessPanel.tsx   # 工具能力可用性展示
    ModelInvocationPanel.tsx       # 模型/工具调用摘要
    StructureViewerPanel.tsx       # 结构产物入口与可视化占位
    ReportExplorer.tsx             # 报告浏览
    InspectorPanel.tsx             # 右侧上下文检查面板
```

前端没有直接保存业务状态，而是从后端 API 读取 `TaskRecord`、`PendingActionDetail`、`TaskTimelineEvent`、`CapabilityReadinessEntry` 等对象。这种设计保证了 UI 是工作流状态的投影，而不是独立状态来源。

## 4. 关键设计原因

使用 FastAPI 和 Pydantic 的主要原因是任务契约较多，并且需要把错误尽早限制在 API 边界。蛋白质设计任务从自然语言到结构化字段之间存在不确定性，Pydantic 校验可以明确区分缺失字段、非法字段和可确认字段。

使用 React/Vite/TypeScript 的原因是前端需要围绕同一任务状态构建多个视图：待审查队列、任务详情、候选对比、事件时间线和报告浏览。TypeScript 类型与后端响应字段对齐，可以降低字段变更造成的展示错误。

使用自定义 Workflow/FSM 的原因是系统控制语义强依赖 `WAITING_*`、`PendingAction`、`Decision` 和 `TaskSnapshot`。如果直接把多步控制交给外部流程引擎，人工确认和运行时恢复的审计链路会更难保持一致。当前实现将 Nextflow 等执行后端限制在单个 PlanStep 内，保持全局控制流由系统自身管理。

使用 ToolAdapter 的原因是蛋白质设计工具异构性很强：有的工具是本地二进制，有的是 Python 脚本，有的是远程 REST 服务。统一适配器接口使 Executor 不关心工具内部细节，只消费标准输入、输出、指标和错误信息。

