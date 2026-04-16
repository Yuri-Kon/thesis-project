# thesis-project

面向蛋白设计任务的 LLM 驱动多智能体工作流系统。

当前 `master` 分支定位为稳定主线，已经合入 `dev` 的阶段性成果，并可作为 `v0.5.4` 稳定版本的对外入口。

## 当前稳定版本

`v0.5.4` 对应的核心进展包括：

- 补齐后续实验所需的关键工具接入：`alphafold`、`openfold/openfold2`、`biopython_qc`、`mmseqs2`、`blastp`、`dssp`、`objective_ranker`、`foldseek`、`interproscan`、`mda_analysis`、`autodock_vina`
- 统一 ToolKG、Adapter、Provider、runtime 注册链与 readiness 暴露
- 落地 issue `#199` / `#200` 的实验冻结配置与统一门禁
- 提供本地/CI 一键验收入口，以及可复用的 gate summary / blockers / evidence-index
- 补强运行时恢复、WAITING 审计、snapshot 回填和动作选择控制流

如果你是第一次进入这个仓库，可以把它理解为：

- 上层：Planner / Executor / Safety / Summarizer 组成的多智能体执行框架
- 中层：显式 FSM、HITL 决策、retry -> patch -> replan 恢复链
- 下层：ToolKG、工具适配器、provider 配置、实验与证据产物

## 系统能力

当前主线已经具备以下核心能力：

- 显式任务生命周期管理：`CREATED -> PLANNING -> RUNNING -> SUMMARIZING -> DONE`
- 人在环等待与确认：`WAITING_PLAN_CONFIRM`、`WAITING_PATCH_CONFIRM`、`WAITING_REPLAN_CONFIRM`
- 有界恢复链路：`retry -> patch -> replan`
- EventLog / Snapshot 驱动的审计与恢复
- ToolKG 驱动的工具能力声明、兼容性检索与 readiness 检查
- 面向实验冻结、门禁、一致性校验和证据归档的脚本体系

系统级约束入口：

- `AGENT_CONTRACT.md`：系统不变量与角色边界
- `AGENTS.md`：Codex 在本仓库中的执行约束
- `CLAUDE.md`：Claude 在本仓库中的执行约束

## 目录总览

核心运行目录：

- `src/workflow/`：任务状态迁移、执行流程、恢复策略
- `src/agents/`：Planner / Executor / Safety / Summarizer
- `src/models/`：契约模型、验证规则、状态定义
- `src/storage/`：日志、快照、持久化结构
- `src/adapters/`、`src/engines/`、`src/tools/`：工具适配与执行后端
- `src/api/`：API schema、服务入口与 UI
- `src/kg/`：ToolKG、capability 元数据与兼容性事实
- `src/infra/`：实验冻结、门禁、runtime 初始化等基础设施逻辑

辅助目录：

- `tests/`：单测、集成测试、API 测试、服务契约测试
- `configs/`：provider、实验与运行时配置
- `scripts/`：实验、验收、冻结、评估与发布辅助脚本
- `examples/`：演示入口与示例材料
- `services/`：独立 REST 服务

## 快速开始

### 1. 安装依赖

```bash
uv sync
```

### 2. 运行基础回归

```bash
uv run pytest
```

### 3. 运行本地演示

```bash
./run_demo.sh
```

启动后可访问：

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/ui`
- `http://127.0.0.1:8000/ui/tasks/<task_id>/events`

更详细的演示说明见：

- `examples/README_DEMO.md`

## issue #200 统一门禁

如果你要确认当前稳定版本是否满足工具接入与实验冻结的一致性要求，优先运行：

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

对应 runbook：

- `scripts/benchmarks/issue200-acceptance-gate-runbook.md`

## 设计与协作约定

本仓库当前采用多 worktree 协作：

- `thesis-project.master`：稳定主线与发布入口
- `thesis-project.dev`：开发主线
- `thesis-project.design`：设计与计划主线

推荐流程：

1. 在 `design` 对齐契约、设计与计划
2. 在 `dev` 实现代码与测试
3. 在 `dev` 跑 focused tests / 回归 / gate
4. 通过 `dev -> master` 合并形成稳定版本

不建议：

- 直接在 `master` 上进行高频实验开发
- 跳过契约约束直接修改 FSM 或 agent 边界
- 无验证地合入影响恢复链路或运行时语义的改动

## 建议阅读顺序

如果你要快速建立上下文，推荐按这个顺序阅读：

1. `AGENT_CONTRACT.md`
2. `AGENTS.md`
3. `src/workflow/`
4. `src/agents/`
5. `src/infra/issue200_acceptance_gate.py`
6. `tests/integration/` 与 `tests/unit/`
7. `../thesis-project.design/docs/design/`

## 说明

`README` 应随着阶段性合并而更新，尤其要同步：

- 当前稳定版本标签
- 关键工具接入与门禁能力
- 快速启动命令
- 推荐协作流
