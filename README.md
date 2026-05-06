# thesis-project

面向蛋白质设计任务的 **LLM 驱动多智能体工作流系统**。

本仓库的 `master` 分支定位为稳定主线和对外入口。当前 `master`
代码基线仍以 `v0.5.4` 的工具接入、运行时控制和 issue `#199` / `#200`
验收门禁为核心；`dev` 分支已经继续推进 `v0.6.0` 相关的 Task Intake、
React 工作台、runtime schema 和分层 patch 恢复修复，合入 `master` 前应以
`dev` 的测试和阶段验收结果为准。

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

当前 `master` 稳定基线面向 `v0.5.4` 后的阶段成果，重点包括：

- 补齐后续实验所需的关键工具接入：`alphafold`、`openfold/openfold2`、
  `biopython_qc`、`mmseqs2`、`blastp`、`dssp`、`objective_ranker`、
  `foldseek`、`interproscan`、`mda_analysis`、`autodock_vina`；
- 统一 ToolKG、Adapter、Provider、runtime 注册链与 readiness 暴露；
- 落地 issue `#199` / `#200` 的实验冻结配置与统一门禁；
- 提供本地/CI 一键验收入口，以及可复用的 gate summary / blockers / evidence-index；
- 补强运行时恢复、WAITING 审计、snapshot 回填和动作选择控制流；
- 提供静态 HITL dashboard 与 event timeline，用于查看 `PendingAction`、提交
  `Decision`、追踪事件日志。

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
  `evidence_sufficiency`；
- `PendingAction` / `Decision`：HITL 等待态中的候选展示和人工决策；
- `TaskSnapshot` / `EventLog`：进入等待态前的持久化和后续恢复证据。

动作选择的稳定语义是服务于恢复闭环，而不是替代恢复闭环。第一版动作空间包括：

- `continue`
- `patch_local`
- `suffix_replan`
- `stop`
- schema / I-O / tool availability 违规先淘汰当前候选；
- `retry_exhausted` 且局部可修时，`patch_local` 先于 `suffix_replan`；
- 可保留前缀足够时，优先后缀 replan 而不是 full replan；
- stop 默认进入 `replan_confirm` 候选，只有满足自动 stop 门槛时才可自动终止。

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
- `src/api/`：FastAPI 服务、API schema、静态 HITL dashboard 和 event timeline；
- `src/infra/`：tool readiness、实验矩阵、评估和运行时基础设施。

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

## 7. issue #200 统一门禁

如果要确认当前稳定版本是否满足工具接入与实验冻结的一致性要求，优先运行：

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

## 8. API 与 HITL UI

当前 `master` 提供 FastAPI 服务和静态前端入口：

- HITL dashboard：查看待决策任务、候选、runtime summary，并提交 `Decision`；
- Event Timeline：查看状态迁移、waiting enter/exit、decision applied、恢复链路和报告信息；
- API schema：通过 `src/api/schemas.py` 暴露任务、pending action、event timeline 等契约。

注意：React + Vite 工作台、Task Builder、字段注册表驱动 intake 表单属于 `dev`
后续开发线，尚不应在当前 `master` README 中作为稳定能力承诺。

## 9. dev 后续同步参考

截至 2026-04-30，`dev` 分支已推进到 `v0.6.0` 之后，近期提交包括：

- `issue-261` / `issue-281`：React 工作台与 Task Builder；
- `issue-282`：CLI Task Intake 循环；
- `issue-263`：runtime schema contracts；
- `fix-patch-recovery-layer-order`：分层 patch 恢复顺序修复；
- README 图示与架构说明更新。


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
