# 实现代码索引与结构化总览
<!-- SID:impl.index.codebase_overview -->

## 1. 文档定位

本文件是代码实现侧的结构化索引，目标是帮助 Agent 快速定位核心模块与关键流程。
系统实现的设计基线以实现设计文档为准（参见 [ref:SID:impl.overview.introduction]、
[ref:SID:impl.techstack.overview]），此处只做代码结构与入口汇总，不重新定义规范。

路径约定：
- `src/` 指向代码仓库根目录（`../thesis-project`）
- 设计侧规范请参见 `docs/design/`（本仓库）

## 2. 分段逻辑（维护约定）

本文件采用固定分段顺序，便于增量扩展与检索：
1) 代码结构快览（粗粒度目录）
2) 核心模块索引（按域分组）
3) 关键流程索引（按流程列入口）
4) 近期新增模块索引（Issue #75-#77）
5) 增量维护清单与变更记录

后续新增模块或流程时，优先在对应索引段落**追加条目**，不替换既有条目。

## 3. 代码结构快览

```text
src/
  agents/          # Planner/Executor/Safety/Summarizer
  workflow/        # FSM 与执行控制流
  models/          # 数据契约与状态模型
  adapters/        # ToolAdapter 适配器与注册
  engines/         # Nextflow/远程调用后端
  llm/             # LLM Provider 抽象与实现
  api/             # FastAPI 入口
  storage/         # 快照、事件日志、文件存储
  infra/           # 事件日志构造器等基础设施
  kg/              # ProteinToolKG 客户端与数据
  tools/           # 工具级实现（如可视化）
  schemas/         # JSON Schema
```

## 4. 核心模块索引

索引字段说明：
- **入口/路径**：推荐从这里开始阅读
- **职责**：该模块的主职责
- **关键对象/扩展点**：涉及的核心对象或可扩展接口

### 4.1 Agent 层

| 模块 | 入口/路径 | 职责 | 关键对象/扩展点 |
| --- | --- | --- | --- |
| PlannerAgent | `src/agents/planner.py` | 生成 Plan，驱动 `PLANNING → PLANNED` | `BaseProvider`、`Plan`、`PlanPatch` |
| ExecutorAgent | `src/agents/executor.py` | 调度 PlanRunner/StepRunner 执行计划 | `PlanRunner`、`StepRunner` |
| SafetyAgent | `src/agents/safety.py` | 安全检查接口（当前为占位实现） | `SafetyResult`、`RiskFlag` |
| SummarizerAgent | `src/agents/summarizer.py` | 汇总结果并生成 `DesignResult` | `DesignResult` |

### 4.2 Workflow/FSM 与执行控制

| 模块 | 入口/路径 | 职责 | 关键对象/扩展点 |
| --- | --- | --- | --- |
| WorkflowContext | `src/workflow/context.py` | 运行期上下文与状态容器 | `status`、`step_results` |
| 状态迁移 | `src/workflow/status.py` | FSM 状态校验与日志 | `InternalStatus`、`transition_task_status` |
| Plan 执行主循环 | `src/workflow/plan_runner.py` | 执行步骤、patch/replan 分支 | `PatchRunner`、`PendingAction` |
| Step 执行 | `src/workflow/step_runner.py` | 调用 ToolAdapter + 重试策略 | `StepRetryPolicy` |
| Patch 应用 | `src/workflow/patch.py` | PlanPatch 操作与 id 分配规则 | `apply_patch` |
| Patch 流程 | `src/workflow/patch_runner.py` | 失败后 patch 闭环 | `PendingPatch` |
| HITL 等待态 | `src/workflow/pending_action.py` | 构造 PendingAction 并写日志/快照 | `PendingAction` |
| Decision 应用 | `src/workflow/decision_apply.py` | 接收人工决策并推进状态 | `DecisionApplyResult` |
| 快照与恢复 | `src/workflow/snapshots.py` / `src/workflow/recovery.py` | 快照写入与恢复逻辑 | `TaskSnapshot`、`RemoteJobContext` |
| 错误分类 | `src/workflow/errors.py` | 失败类型与分类逻辑 | `FailureType` |

### 4.3 数据契约与状态模型

| 模块 | 入口/路径 | 职责 | 关键对象/扩展点 |
| --- | --- | --- | --- |
| 核心契约 | `src/models/contracts.py` | Plan/Step/Result/PendingAction 等契约 | `Plan`、`Decision`、`TaskSnapshot` |
| 任务状态 | `src/models/db.py` | 内外部状态与 TaskRecord | `InternalStatus`、`TaskRecord` |
| 决策校验 | `src/models/validation.py` | Decision 与 PendingAction 兼容校验 | `validate_decision_for_pending_action` |
| 事件日志 | `src/models/event_log.py` | 结构化 EventLog 数据 | `EventLog`、`ActorType` |
| JSON Schema | `src/schemas/protein_task.json` | Task JSON 结构定义 | `ProteinDesignTask` |

### 4.4 工具适配与执行后端

| 模块 | 入口/路径 | 职责 | 关键对象/扩展点 |
| --- | --- | --- | --- |
| Adapter 基类 | `src/adapters/base_tool_adapter.py` | 统一输入解析与执行接口 | `resolve_inputs`、`run_local` |
| Adapter 注册表 | `src/adapters/registry.py` | 工具适配器注册与查找 | `register_adapter` |
| 内置注册 | `src/adapters/builtins.py` | 默认适配器注册入口 | `ensure_builtin_adapters` |
| 工具适配器 | `src/adapters/*.py` | ProteinMPNN/ESMFold/RDKit 等 | `run_local`/`run_remote` |
| NIM 适配器 | `src/adapters/nim_adapter.py` | NVIDIA NIM ESMFold 适配器 | `NIMESMFoldAdapter` |
| Nextflow 后端 | `src/engines/nextflow_adapter.py` | 单步执行后端封装 | Nextflow 进程调度 |
| 远程模型调用 | `src/engines/remote_model_service.py` | 远程 submit/poll/download | `RemoteModelInvocationService` |
| NIM 客户端 | `src/engines/nim_client.py` | NVIDIA NIM API 客户端 | `NvidiaNIMClient`、`call_sync` |
| Provider 配置 | `src/engines/provider_config.py` | 远程模型提供商配置管理 | `ProviderConfig`、`load_provider_config` |
| 可视化工具 | `src/tools/visualization/` | 可视化适配与流程 | `adapter.py`、`pipeline.py` |

### 4.5 LLM Provider 层

| 模块 | 入口/路径 | 职责 | 关键对象/扩展点 |
| --- | --- | --- | --- |
| Provider 抽象 | `src/llm/base_llm_provider.py` | 统一调用接口与配置 | `BaseProvider`、`ProviderConfig` |
| OpenAI 兼容 | `src/llm/openai_compatible_provider.py` | OpenAI/Nemotron 等接入 | `OpenAICompatibleProvider` |
| Baseline Provider | `src/llm/baseline_provider.py` | 无 LLM 的基线规划 | `BaselineProvider` |
| Provider 注册表 | `src/llm/provider_registry.py` | Provider 工厂与配置加载 | `create_provider` |

### 4.6 API 与交互

| 模块 | 入口/路径 | 职责 | 关键对象/扩展点 |
| --- | --- | --- | --- |
| FastAPI 入口 | `src/api/main.py` | 任务创建与决策提交 API | `/tasks`、`/pending-actions/{id}/decision` |

### 4.7 存储与可观测

| 模块 | 入口/路径 | 职责 | 关键对象/扩展点 |
| --- | --- | --- | --- |
| 事件日志存储 | `src/storage/log_store.py` | JSONL 事件日志读写 | `append_event` |
| 快照存储 | `src/storage/snapshot_store.py` | TaskSnapshot 持久化 | `read_latest_snapshot` |
| 文件存储 | `src/storage/filestore.py` | 本地输出与工件存储 | `save_file` |
| 事件日志工厂 | `src/infra/event_log_factory.py` | 结构化事件构建 | `make_waiting_enter` |

### 4.8 ProteinToolKG

| 模块 | 入口/路径 | 职责 | 关键对象/扩展点 |
| --- | --- | --- | --- |
| KG 客户端 | `src/kg/kg_client.py` | KG 查询入口 | `query_tools` |
| KG 数据 | `src/kg/protein_tool_kg.json` | 工具知识图谱数据 | 工具能力/成本/安全级别 |

## 5. 关键流程索引

| 流程 | 入口模块 | 关键路径 |
| --- | --- | --- |
| 任务同步执行 | `src/workflow/workflow.py` | `run_task_sync` → Planner → Executor → Summarizer |
| 计划生成（含 LLM） | `src/agents/planner.py` | `PlannerAgent.plan` → `BaseProvider.call_planner` |
| 步骤执行与重试 | `src/workflow/step_runner.py` | `run_step` → Adapter → StepResult |
| Patch 流程 | `src/workflow/plan_runner.py` | 失败 → `PatchRunner` → `apply_patch` |
| Replan 流程 | `src/workflow/plan_runner.py` | 安全阻断/patch 失败 → `PendingAction` |
| HITL 决策应用 | `src/workflow/decision_apply.py` | API → `apply_*_decision` |
| 远程工具调用 | `src/engines/remote_model_service.py` | submit → poll → download |
| 快照恢复 | `src/workflow/recovery.py` | `restore_context_from_snapshot` |

## 6. 近期新增模块索引（Issue #75 - #77, #101 - #108）

| Issue | 模块/功能 | 入口/路径 | 关联实现文档 |
| --- | --- | --- | --- |
| #75 | LLM Provider 插件化 | `src/llm/`、`src/agents/planner.py` | `docs/impl/issue_75_implementation_summary.md`、`docs/impl/llm_provider_guide.md` |
| #76 | 远程模型调用 | `src/engines/remote_model_service.py`、`src/adapters/remote_esmfold_adapter.py` | `docs/impl/remote_model_invocation.md` |
| #77 | 快照恢复 | `src/workflow/recovery.py`、`src/storage/snapshot_store.py` | `docs/impl/snapshot-recovery.md` |
| #101 | ESMFold 可用性（NIM 路径） | `src/engines/nim_client.py`、`src/adapters/nim_adapter.py` | `docs/impl/remote_model_invocation.md` |
| #102 | KG 工具定义扩展 | `src/kg/protein_tool_kg.json`、`src/kg/kg_client.py` | `docs/design/tools-catalog.md` |
| #105 | NIM 失败码分类 | `src/workflow/errors.py` | `docs/impl/remote_model_invocation.md` |
| #107 | ProteinMPNN 适配器 | `src/adapters/protein_mpnn_adapter.py` | - |
| #108 | Provider 配置系统 | `src/engines/provider_config.py`、`configs/model_providers.json` | `docs/impl/remote_model_invocation.md` |

## 7. 增量维护清单

- 新增模块时：补充到第 4 节对应域的索引表中
- 新增流程时：补充到第 5 节“关键流程索引”
- 新增实现文档时：补充到第 6 节或第 8 节“相关实现文档”
- 每次扩展后：追加更新记录（不覆盖旧记录）

## 8. 相关实现文档

- `docs/impl/issue_75_implementation_summary.md`
- `docs/impl/llm_provider_guide.md`
- `docs/impl/remote_model_invocation.md`
- `docs/impl/snapshot-recovery.md`

## 9. 变更记录（追加）

| 日期 | 变更 |
| --- | --- |
| 2026-01-11 | 初始版本，建立代码结构快览与模块/流程索引 |
| 2026-01-25 | 新增 Issue #101-#108 模块索引（NIM 集成、Provider 配置、失败码分类） |
