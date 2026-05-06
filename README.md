# thesis-project

面向蛋白质设计任务的 **LLM 驱动多智能体工作流系统**。

本仓库的 `master` 分支定位为稳定主线和对外入口。当前 `master`
已经合入 CEBRA-WP v2 阶段成果，阶段标签为 `cebra-wp-v2-stage-20260506`。
当前代码基线包含核心算法实现、Task Intake、React 工作台、runtime schema、
分层 patch/replan 恢复、实验矩阵和审计可视化。算法机制已经在代码中明确落地；
算法有效性仍需要后续实验、消融和指标评估验证。

## 1. 项目定位

`thesis-project` 不把 LLM 只作为文本生成器，而是将其纳入可执行、可恢复、
可审计的科研工作流控制层。系统目标是：

- 根据自然语言或结构化任务输入生成可执行 `Plan`；
- 在运行中维护显式 FSM 状态，并严格记录状态迁移；
- 对高代价、长链路、易失败的蛋白设计流程进行 runtime-aware 控制；
- 在失败时按 `retry -> patch -> replan` 顺序恢复；
- 在关键节点通过 HITL 暂停、展示候选、等待人工决策；
- 将计划、执行、候选、决策、快照和事件日志串成可复现证据链。

不可绕过的系统约束入口：

- `AGENT_CONTRACT.md`：FSM、agent 边界、恢复顺序、状态持久化等系统不变量；
- `AGENTS.md` / `CLAUDE.md`：本仓库内实现助手的操作约束；
- `../thesis-project.design/docs/design/`：算法、架构、HITL、运行时控制的权威设计文档。

## 2. 当前稳定基线

当前 `master` 稳定基线面向 CEBRA-WP v2 阶段成果，重点包括：

- 补齐后续实验所需的关键工具接入：`alphafold`、`openfold/openfold2`、
  `biopython_qc`、`mmseqs2`、`blastp`、`dssp`、`objective_ranker`、
  `foldseek`、`interproscan`、`mda_analysis`、`autodock_vina`；
- 统一 ToolKG、Adapter、Provider、runtime 注册链与 readiness 暴露；
- 落地候选生成、硬可行性过滤、posterior objective、Top-K diversity、
  Lite belief-state、runtime adjustment、action utility、ActionBias 和 stop guard；
- 提供 Task Intake / Task Builder，支持字段注册表驱动的任务创建、LLM 抽取、
  safety precheck 与 `ConfirmedTaskSpec` 投影；
- 提供 React + Vite 工作台、Task Detail、Pending Review、Event Timeline、
  Theory Object Summary 等操作视图；
- 提供 runtime policy ablation group、实验矩阵、evidence-index、gate summary
  与可复用的实验产物；
- 补强运行时恢复、WAITING 审计、snapshot 回填、事件日志和动作选择控制流。

可以把当前稳定代码理解为三层：

- 上层：`PlannerAgent` / `ExecutorAgent` / `SafetyAgent` / `SummarizerAgent`
  组成的多智能体执行框架；
- 中层：显式 FSM、HITL 决策、`retry -> patch -> replan` 恢复链；
- 下层：ToolKG、工具适配器、provider 配置、实验门禁和证据产物。

## 3. 核心算法与运行时控制

设计文档将问题定义为：

> 在高代价、长链路、可失败、可恢复的蛋白质设计工作流中，动态生成、评估、
> 裁剪并修正工具链，使系统以更低成本获得更高任务成功率。

当前代码已经包含候选、运行时状态和动作选择相关契约：

- `PlanCandidate` / `PatchCandidate` / `ReplanCandidate`：用于关键节点的候选集合；
- `RuntimeState`：轻量 belief-state，核心字段包括 `p_success`、
  `p_structural_failure`、`recovery_margin`、`expected_remaining_cost`、
  `evidence_sufficiency`、`budget_pressure` 和 `budget_cap`；
- `PendingAction` / `Decision`：HITL 等待态中的候选展示和人工决策；
- `TaskSnapshot` / `EventLog`：进入等待态前的持久化和后续恢复证据。

CEBRA-WP v2 的算法对象已按版本归档：

- `static_score.v1`：静态候选效用与 `score_breakdown`；
- `posterior_score.v1` / `posterior_objective.v1`：证据加权目标评分；
- `runtime_adjustment.v1`：基于 runtime state 的候选重排序；
- `action_utility.v1` / `action_features.v1`：恢复动作效用；
- `action_bias.v1`：runtime delta 的动作偏置解释层。

动作选择的稳定语义是服务于恢复闭环，而不是替代恢复闭环。第一版动作空间包括：

- `continue`
- `patch_local`
- `suffix_replan`
- `stop`

硬约束和优先级包括：

- safety block 禁止直接继续；
- schema / I-O / tool availability 违规先淘汰当前候选；
- `retry_exhausted` 且局部可修时，`patch_local` 先于 `suffix_replan`；
- 可保留前缀足够时，优先后缀 replan 而不是 full replan；
- stop 默认进入 `replan_confirm` 候选，只有满足自动 stop 门槛时才可自动终止。

当前实现审阅结论是：算法机制已经有明确实现入口、调用链和契约测试覆盖。
这不等同于证明算法有效性；有效性仍需要后续实验设计、横向对照和消融指标验证。

## 4. 架构总览

系统由显式 FSM 驱动，多智能体只在自己的边界内工作：

- `PlannerAgent`：生成 `Plan` / `PlanPatch` / `Replan` 候选，不执行工具，不直接改状态；
- `ExecutorAgent` / workflow runner：执行工具、处理 retry / patch / replan 流程，
  进入 `WAITING_*` 后必须停止执行；
- `SafetyAgent`：只输出 `allow` / `warn` / `block` 评估，不修改计划；
- `SummarizerAgent`：聚合输出并生成用户可读结果，不重新执行工具。

核心生命周期：

```text
CREATED -> PLANNING -> (WAITING_PLAN_CONFIRM | PLANNED) -> RUNNING
RUNNING -> WAITING_PATCH_CONFIRM | WAITING_REPLAN_CONFIRM | SUMMARIZING
WAITING_*_CONFIRM -> RUNNING | FAILED | CANCELLED
RUNNING -> SUMMARIZING -> DONE
```

内部执行态会映射回外部语义态，例如：

```text
RUNNING -> WAITING_PATCH -> PATCHING -> RUNNING
RUNNING/PATCHING -> WAITING_REPLAN -> REPLANNING -> RUNNING/PLANNING/FAILED
```

进入任意 `WAITING_*` 前必须完成快照和事件日志写入。系统重启或恢复执行时，
若任务仍处于等待态，则继续等待 `Decision`，不会自动推进工具执行。

## 5. 代码结构

核心运行目录：

- `src/workflow/`：FSM 状态迁移、PlanRunner、PatchRunner、decision apply、恢复策略；
- `src/agents/`：Planner / Executor / Safety / Summarizer 实现；
- `src/models/`：Pydantic 契约模型、runtime state、task / plan / result 契约；
- `src/storage/`：事件日志、快照、恢复读取；
- `src/adapters/`、`src/tools/`、`src/engines/`：工具适配器和执行后端；
- `src/kg/`：Protein ToolKG 与能力元数据；
- `src/llm/`：模型 provider、structured output、fallback/repair；
- `src/schemas/`：JSON schema 与兼容性资产；
- `src/api/`：FastAPI 服务、API schema、React 工作台和静态资源入口；
- `src/api/frontend/`：React + Vite 工作台源码；
- `src/infra/`：tool readiness、实验矩阵、评估和运行时基础设施；
- `docs/algorithm-and-llm/`：算法实现追踪、理论背景、issue 拆分和实验映射；
- `docs/experiment/` / `output/experiment/`：实验矩阵、运行产物和指标摘要。

测试目录：

- `tests/unit/`：契约、算法、agent、adapter、runner 单测；
- `tests/integration/`：workflow、HITL、恢复链路、远程 mock/e2e；
- `tests/api/`：API 和前端路由契约；
- `tests/services/`：远程 REST 服务契约与 runner 兼容性。

## 6. 本地快速开始

Python 版本见 `.python-version`，项目执行统一使用 `uv`。

```bash
# 安装/同步 Python 依赖
uv sync

# 运行测试
uv run pytest

# 启动 API 服务
uv run uvicorn src.api.main:app --reload
```

前端资源构建：

```bash
npm run check:ui
npm run build:ui
```

启动后可访问：

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/ui`
- `http://127.0.0.1:8000/ui/tasks/<task_id>/events`

本地演示入口：

```bash
./run_demo.sh
```

更详细的演示说明见 `examples/README_DEMO.md`。

## 7. 阶段验证与实验入口

如果要确认工具接入与实验冻结的一致性要求，优先运行：

```bash
UV_CACHE_DIR=/tmp/uv-cache \
uv run python scripts/benchmarks/run_issue200_acceptance_suite.py \
  --output-root output/experiment/w16-issue200-local
```

如果只需要运行 gate：

```bash
UV_CACHE_DIR=/tmp/uv-cache \
uv run python scripts/benchmarks/run_issue200_acceptance_gate.py \
  --output-root output/experiment/w16-issue200-gate-only
```

关键产物包括：

- `issue200_acceptance_suite.json`
- `issue200_acceptance_gate_report.json`
- `issue200_acceptance_gate_summary.md`
- `issue200_gate_summary.json`
- `issue200_gate_blockers.json`
- `issue200_gate_evidence_index.json`

对应 runbook：`scripts/benchmarks/issue200-acceptance-gate-runbook.md`。

CEBRA-WP v2 相关的聚焦契约验证可运行：

```bash
uv run pytest \
  tests/unit/test_algorithm_versions.py \
  tests/unit/test_candidate_generator.py \
  tests/unit/test_planner_posterior_objective_scoring.py \
  tests/unit/test_runtime_evaluator.py \
  tests/unit/test_belief_state.py \
  tests/unit/test_action_features.py \
  tests/unit/test_recovery_selector.py \
  tests/integration/test_workflow_action_selector.py
```

实验与消融相关入口包括：

- `docs/experiment/algorithm-group-paper-mapping.md`
- `scripts/run_w16_issue172_horizontal_experiment.py`
- `scripts/run_w16_issue221_experiment_matrix.py`
- `scripts/evaluate_w16_issue221_experiment_matrix.py`
- `src/workflow/runtime_evaluator.py` 中的 `RUNTIME_POLICY_ABLATION_GROUPS`

当前阶段可说“实现和契约已落地”；不要把单元测试通过表述为算法有效性已验证。

## 8. API、工作台与 HITL UI

当前 `master` 提供 FastAPI 服务和 React 工作台入口：

- Dashboard：查看任务概览、待决策入口和执行状态；
- Task Builder：基于字段注册表创建结构化任务，支持抽取、确认和 safety precheck；
- Task Detail：展示任务状态、pending action、候选比较、结构和报告；
- Pending Review：查看候选、runtime summary、theory objects，并提交 `Decision`；
- Event Timeline：查看状态迁移、waiting enter/exit、decision applied、恢复链路和报告信息；
- Theory Object Summary：把候选评分、runtime adjustment、action utility 与理论对象关联展示；
- API schema：暴露任务、pending action、event timeline、candidate display 等契约。

主要前端源码位于 `src/api/frontend/`，构建产物进入 `src/api/static/web/`。

## 9. 当前阶段标签与后续实验

当前阶段标签：

- `cebra-wp-v2-stage-20260506`

当前阶段已经完成的重点：

- CEBRA-WP v2 公式版本 registry 与 source refs；
- 候选可行性、Top-K diversity、posterior objective、binding proxy policy；
- Lite belief-state 更新表、budget pressure 语义、ActionBias 和 action utility；
- 理论对象、文献、代码映射与前端 Theory Object Summary；
- 面向后续论文实验的 runtime policy ablation group。

后续重点是实验设计和有效性验证，尤其是：

- `success_rate`
- `high_cost_call_count`
- `manual_intervention_rate`
- `patch_success_rate`
- `replan_success_rate`
- `stop_quality`
- `rerank_delta`

## 10. 分支与协作约定

当前常用 worktree：

| worktree 路径 | 分支 | 角色 |
| --- | --- | --- |
| `../thesis-project/` | `master` | 稳定主线、对外入口、阶段发布快照 |
| `../thesis-project.dev/` | `dev` | 开发主线、集成验证、阶段候选产物 |
| `../thesis-project.design/` | `design` | 设计文档、算法说明、论文计划 |


不建议：

- 直接在 `master` 上进行高频实验开发；
- 跳过契约约束直接修改 FSM 或 agent 边界；
- 无验证地合入影响恢复链路或运行时语义的改动。

## 11. 建议阅读顺序

如果要快速建立上下文，推荐按这个顺序阅读：

1. `AGENT_CONTRACT.md`
2. `AGENTS.md`
3. `src/models/contracts.py`
4. `src/workflow/`
5. `src/agents/`
6. `src/infra/issue200_acceptance_gate.py`
7. `tests/integration/` 与 `tests/unit/`
8. `../thesis-project.design/docs/design/`

## 12. README 维护规则

阶段合并或算法/架构调整后，README 至少同步：

- 当前稳定版本标签和代码基线；
- 当前算法能力和 runtime control 语义；
- FSM、agent 边界、恢复链路是否变化；
- API / UI 入口是否变化；
- 当前阶段验证命令与已知排除项；
- `master`、`dev`、`design` 的职责说明是否仍准确。
