---
doc_key: hitl
version: 1.0
status: stable
depends_on: [arch, agent, impl, algo]
---

# 扩展设计：Human-in-the-loop 与可追溯执行（差分说明）

> 本文档用于描述系统从 v0.2（全自动执行原型）到 v0.3（真实可用版本）的关键重构与扩展点。
> 本文档不替代 architecture.md / system-implementation-design.md / agent-design.md / core-algorithm-spec.md，
> 而是作为"差分索引"和"设计动机说明"。

---

## 1. 重构目标与场景假设

### 1.1 核心目标

在保留系统自动执行能力的前提下，引入以下能力，使系统具备真实可用性：

- 人在环路（Human-in-the-loop）：关键决策节点人工审查
- 快速响应：用户不被长任务阻塞，可实时查看状态与待决策项
- 可追溯与审计：事件日志 + 决策记录 + 可回放边界
- 可恢复执行：任务快照支持系统重启、断线续跑
- 执行后端解耦：为 Nextflow 引入做准备

### 1.2 关键使用场景

- 科研人员希望在高成本计算（如折叠、仿真）前确认工具链与参数
- 执行出现失败，需要人工选择修补（Patch）还是重规划（Replan）
- 安全/风险评估提示高风险，必须暂停并进行人工确认
- 长任务运行中随时可查询进度，系统重启后可继续执行

---

## 2. 架构层变更（architecture.md 对应）

### 2.1 引入"等待人工决策"的语义状态（WAITING_*）

在架构层 FSM 中新增等待审查状态，详见 [ref:SID:fsm.states.definitions]：

- [ref:SID:fsm.states.waiting_plan_confirm]
- [ref:SID:fsm.states.waiting_patch_confirm]
- [ref:SID:fsm.states.waiting_replan_confirm]

这些状态表示：系统已生成候选方案并暂停推进，等待外部 Decision 恢复执行。

### 2.2 PendingAction / Decision 作为一等对象（跨层统一）

所有人工交互通过结构化对象实现，详见：

- `PendingAction`：[ref:SID:arch.contracts.pending_action]
- `Decision`：[ref:SID:arch.contracts.decision]

架构含义：

- 中断/恢复不依赖运行栈
- API / CLI / UI 的交互接口统一
- 审计与回放边界清晰（每个 WAITING_* 都有明确的 pending_action_id）

### 2.3 任务快照与恢复点（TaskSnapshot / Checkpoint）

TaskSnapshot 定义详见 [ref:SID:arch.contracts.task_snapshot]。

在关键节点写入 TaskSnapshot：

- Plan 固化
- 进入 WAITING_* 前
- 应用 Patch / 接受 Replan 后
- DONE 前（汇总产物）

快照最小可恢复上下文：

- 当前状态
- Plan 版本
- 已完成步骤索引
- artifacts 路径映射
- pending_action_id（若有）

---

## 3. 实现层变更（system-implementation-design.md 对应）

### 3.1 双层状态：ExternalStatus 与 InternalStatus

- ExternalStatus（对外语义状态，与 architecture.md 对齐）
- InternalStatus（执行器内部状态，保留 PATCHING / REPLANNING 等细粒度控制）

映射规则（Internal → External）：

- `WAITING_PATCH` / `PATCHING` → `WAITING_PATCH_CONFIRM`
- `WAITING_REPLAN` / `REPLANNING` → `WAITING_REPLAN_CONFIRM`
- 其余同名映射

该设计确保：
- UI/API 不被内部执行态污染
- 执行器仍可精细控制补救过程

### 3.2 新增接口：pending-actions 与 decision 提交

新增并固化 REST API，详见 [ref:SID:api.rest.overview]：

- [ref:SID:api.rest.get_pending_actions]：待人工决策列表
- [ref:SID:api.rest.submit_decision]：提交 Decision 并驱动状态转移

并在 [ref:SID:api.rest.get_task] 返回体中：
- WAITING_* 状态必须返回 `pending_action` 摘要

### 3.3 审计与事件日志（EventLog）

EventLog 定义详见 [ref:SID:obs.eventlog.schema]，硬约束详见 [ref:SID:obs.eventlog.mandatory_events]。

新增 HITL 关键事件类型：

- `PENDING_ACTION_CREATED`
- `DECISION_SUBMITTED`
- `DECISION_APPLIED`
- `PENDING_ACTION_CANCELLED`
- `TASK_CANCELLED_BY_USER`

并定义硬约束（详见 [ref:SID:obs.eventlog.mandatory_events]）：

- 进入任意 WAITING_* 前必须：
  - 写 `PENDING_ACTION_CREATED`
  - 写 TaskSnapshot
  - 才允许更新状态
- Decision 应用必须写 `DECISION_APPLIED` 且触发状态转移后再落日志
- FAILED/CANCELLED 终止态必须取消所有 pending PendingAction，并写取消事件

---

## 4. Agent 行为层变更（agent-design.md 对应）

Human-in-the-loop 不改变 Agent 核心职责，但改变"候选如何确认"的路径。

详见各 Agent 的 HITL 职责定义：

- PlannerAgent：[ref:SID:planner.hitl.responsibilities]
  - MUST: [ref:SID:planner.responsibilities.must]
  - MUST NOT: [ref:SID:planner.responsibilities.must_not]
- ExecutorAgent：[ref:SID:executor.hitl.responsibilities]
  - MUST: [ref:SID:executor.responsibilities.must]
  - MUST NOT: [ref:SID:executor.responsibilities.must_not]
- SafetyAgent：[ref:SID:safety.hitl.responsibilities]
  - MUST: [ref:SID:safety.responsibilities.must]
  - MUST NOT: [ref:SID:safety.responsibilities.must_not]
- SummarizerAgent：[ref:SID:summarizer.hitl.responsibilities]
  - MUST: [ref:SID:summarizer.responsibilities.must]
  - MUST NOT: [ref:SID:summarizer.responsibilities.must_not]

统一约束：[ref:SID:agent.hitl.universal_constraints]

---

## 5. 核心算法层变更（core-algorithm-spec.md 对应）

v0.3 引入 Candidate（Top-K）输出与门控（进入 HITL 的规则），详见：

- Candidate 定义：[ref:SID:planner.contracts.candidate_schema]
  - [ref:SID:planner.contracts.plan_candidate]
  - [ref:SID:planner.contracts.patch_candidate]
  - [ref:SID:planner.contracts.replan_candidate]
- 候选评分：[ref:SID:planner.algorithm.candidate_scoring]
- HITL 门控规则：[ref:SID:planner.algorithm.hitl_gate]
- Decision 应用逻辑：[ref:SID:planner.algorithm.decision_application]

这保证：
- 人类看到的不只是"一个方案"，而是一组可比较的候选
- 系统给出默认建议与解释，降低审查成本
- Decision 结果可追溯、可复现

---

## 6. 执行后端解耦（为 Nextflow 接入做准备）

新增抽象：

- `ExecutionBackend`：统一执行接口
  - LocalBackend（当前默认）
  - NextflowBackend（未来扩展）

规划原则：
- 一次 Plan 执行视为独立 workflow run
- 后续可利用 Nextflow 的 trace / resume 提供工业级可追溯与断点续跑

对应实现规范：`system-implementation-design.md` → ExecutionBackend 章节。

---

## 7. 与 v0.2 的关系

v0.3 的改造属于“工程级增强”，而非推翻原架构：

- 原有：LLM 自动规划 → 自动执行 → 自动总结（可演示但不可用）
- 新增：人工审查、快照恢复、审计回放、对外语义状态、后端解耦（可用性增强）

因此，v0.3 更强调：
- 可靠性（恢复/重启）
- 可控性（HITL）
- 可解释性（候选集 + 解释）
- 可追溯性（事件日志 + 决策记录）
