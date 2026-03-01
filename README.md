# thesis-project（master worktree）

> 本目录是 `master` 分支的工作树（worktree）。
>
> 角色：稳定主线与对外入口。

## 1. 项目定位

`thesis-project` 是一个面向蛋白设计任务的 **LLM 驱动多智能体工作流系统**。
系统核心目标不是文本回答，而是可控、可执行、可恢复、可审计的工作流生成与执行。

关键能力：

- 生成工作流候选（Plan / Patch / Replan）
- 失败恢复链路：`retry -> patch -> replan`
- 人在环决策（HITL，`WAITING_*`）
- 审计闭环（`PendingAction -> Decision -> EventLog`）

系统级约束入口：

- `AGENT_CONTRACT.md`：系统不变量（FSM、角色边界、恢复顺序）
- `AGENTS.md`：Codex 操作规范
- `CLAUDE.md`：Claude 操作规范

## 2. 代码结构总览

核心运行目录：

- `src/workflow/`：任务状态迁移、执行流程、恢复策略
- `src/agents/`：Planner / Safety / Summarizer 等智能体逻辑
- `src/models/`：契约模型、验证规则、状态定义
- `src/storage/`：日志、快照、持久化结构
- `src/adapters/`、`src/tools/`、`src/engines/`：工具与执行后端适配
- `src/api/`：API schema 与服务入口
- `src/kg/`：ToolKG 能力事实与检索

辅助目录：

- `tests/`：单测、集成测试、API 测试
- `services/`：独立服务（如 PLM REST）
- `configs/`：模型/provider 配置
- `examples/`：演示入口
- `scripts/`：脚本工具

## 3. Worktree 与长线分支

当前使用 3 个核心 worktree：

| worktree 路径 | 分支 | 角色 | 主要内容 |
|---|---|---|---|
| `../thesis-project` | `master` | 稳定主线 | 已合并能力的稳定快照、对外阅读入口 |
| `../thesis-project.dev` | `dev` | 开发主线 | 日常功能开发与集成验证 |
| `../thesis-project.design` | `design` | 设计主线 | 设计文档、计划书、算法/训练说明 |

### 当前分支关系（2026-03-02 本地快照）

- `master...dev`：`4 | 0`
- `master...origin/master`：`0 | 0`
- `dev...origin/dev`：`0 | 0`

解读：

- `master` 已包含此前 `dev` 主线能力，并在此基础上有额外提交。
- 若继续在 `dev` 开发，建议先将 `master` 的最新提交同步回 `dev`，避免后续重复冲突。

## 4. 各分支职责（合并后版本）

### 4.1 `master`

- 作为稳定基线，适合演示、评审、发布前检查。
- 已包含 Week6 工具/基础设施主线能力（通过 `dev -> master` 合并）。

### 4.2 `dev`

- 继续承担新功能开发与实验集成。
- 推荐策略：短周期分支 -> 合并到 `dev` -> 回归 -> 再合并到 `master`。

### 4.3 `design`

- 继续作为架构与计划的权威来源，不承载运行时代码演进。
- 关键路径：`docs/design/`、`docs/algorithm-and-llm/`、`plan/`。

## 5. 远端专题分支状态（相对 master）

| 分支 | 最近主题 | 当前状态（相对 `master`） | 备注 |
|---|---|---|---|
| `origin/dev` | 开发主线 | 已合入 | 当前 `master` 已覆盖该阶段能力 |
| `origin/w6-tools-0/remote-rest-impl` | PLM REST server 参考实现 | 已合入 | 已通过 `dev` 纳入主线 |
| `origin/w6-infra-1/remote-protgpt2-impl` | 远程 PLM 实现统一与测试 | 已合入 | 已通过 `dev` 纳入主线 |
| `origin/w6-tools-1/adapte-plm` | ProtGPT2 接入 de novo 起始节点 | 已合入 | 已通过 `dev` 纳入主线 |
| `origin/w6-tools-2/proteinmpnn-impl` | ProteinMPNN NIM 接入与回退修复 | 已合入 | 已通过 `dev` 纳入主线 |
| `origin/fix/agent-contract` | 契约文档路径修正 | 已合入 | 已通过 `dev` 纳入主线 |
| `origin/fix/test-url` | 测试 URL 修复 | 已合入 | 已在主线 |
| `origin/design` | 设计与计划迭代 | 未合入 | 文档主线，通常不直接合并到代码主线 |
| `origin/feature/de-novo-workflow` | de novo 工作流文档增强 | 未合入 | 需按当前契约评估 |
| `origin/feat/auto-index-regen` | 索引 SID 自动修正 | 未合入 | 设计索引维护分支 |
| `origin/thesis-paper` | 论文结构草稿 | 未合入 | 论文产物分支 |

## 6. 推荐协作流

1. 在 `design` 对齐需求与约束（先看契约，再看计划）
2. 在 `dev` 实现代码与测试
3. 在 `dev` 做回归（`uv run pytest ...`）
4. 发起 `dev -> master` PR，经过验证后合并

不建议：

- 跳过设计约束直接修改 FSM 或 agent 边界
- 在 `master` 直接做高频实验开发
- 无测试验证直接合并

## 7. 本地快速开始（master）

```bash
# 安装依赖
uv sync

# 运行测试
uv run pytest

# 运行演示
./run_demo.sh
```

## 8. 新成员最短路径

1. `AGENT_CONTRACT.md`
2. `AGENTS.md`
3. `src/workflow/` 与 `src/agents/`
4. `tests/integration/`
5. `../thesis-project.design/plan/` 与 `../thesis-project.design/docs/design/`

## 9. README 维护规则

每次阶段合并后，至少更新这三项：

- `master...dev` 分支关系数字
- 远端 topic 分支合并状态
- 当前推荐协作流（是否需要先同步 master 到 dev）

