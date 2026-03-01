# thesis-project（master worktree）

> 本目录是 `master` 分支的工作树（worktree）。
>
> 用途：作为项目的稳定基线与对外可读入口，不用于高频实验开发。

## 1. 项目是什么

`thesis-project` 是一个面向蛋白设计任务的 **LLM 驱动多智能体工作流系统**。
系统核心不是“生成自然语言答案”，而是：

- 生成可执行工作流（Plan / Patch / Replan）
- 在失败时按受控策略恢复（`retry -> patch -> replan`）
- 在关键节点进入 HITL（Human-in-the-Loop）决策
- 保留完整审计链（状态迁移、PendingAction、Decision、EventLog）

系统级约束由以下文件定义：

- `AGENT_CONTRACT.md`：系统不变量（FSM、角色边界、恢复顺序）
- `AGENTS.md`：Codex 操作规范
- `CLAUDE.md`：Claude 操作规范

## 2. 代码与模块总览

核心目录（运行时）：

- `src/workflow/`：任务生命周期、状态迁移、执行与恢复主链路
- `src/agents/`：Planner / Safety / Summarizer 等智能体实现
- `src/models/`：契约模型、验证规则、状态定义
- `src/storage/`：日志、快照、持久化抽象
- `src/adapters/`、`src/tools/`、`src/engines/`：工具与后端适配
- `src/api/`：API 层与输入输出契约
- `src/kg/`：ToolKG 与工具事实检索

辅助目录：

- `tests/`：unit / integration / api 测试
- `scripts/`：脚本工具
- `examples/`：演示入口
- `configs/`：模型与运行配置

## 3. Worktree 与长线分支

当前仓库采用多 worktree 协作：

| worktree 路径              | 分支     | 角色定位       | 主要内容                         |
| -------------------------- | -------- | -------------- | -------------------------------- |
| `../thesis-project`        | `master` | 稳定基线       | 对外可读、已合并能力的稳定快照   |
| `../thesis-project.dev`    | `dev`    | 主开发分支     | 功能集成、工具接入、测试推进     |
| `../thesis-project.design` | `design` | 设计与计划分支 | 设计文档、计划书、算法与训练说明 |

### 分支关系（本地快照）

- `master...dev`：`1 | 17`（master 独有 1，dev 独有 17）
- `master...design`：`189 | 60`（两者长期分化，design 主要用于文档体系）

结论：

- “当前最稳定代码”: `master`
- “最新开发能力”: `dev`
- “规范/路线图/算法计划”: `design`

## 4. 各分支具体内容说明

### 4.1 `master`（稳定基线）

定位：

- 发布与展示基线
- 保持可读、可复现、可审查

建议：

- 不在 `master` 直接做功能开发
- 新能力先在 `dev` 完成并验证，再合并到 `master`

### 4.2 `dev`（主开发分支）

相对 `master` 的已知关键变化（来自差异文件）：

- 智能体技能目录迁移：`.claude/skills` -> `.agents/skills`
- 文档契约更新：`AGENTS.md`、`AGENT_CONTRACT.md`
- Provider 配置更新：`configs/model_providers.json`
- 新增远程 PLM 服务实现：`services/plm_rest_server/*`
- 新增 ProtGPT2 适配器：`src/adapters/protgpt2_adapter.py`
- 更新 Planner / ToolKG / Adapter / 测试覆盖

适用场景：

- 新功能开发
- 集成测试与回归验证
- issue 迭代落地

### 4.3 `design`（设计文档分支）

定位：

- 设计文档、计划书、算法与训练方案的权威来源

主要目录（位于 `../thesis-project.design` worktree）：

- `docs/design/`：架构与契约规范
- `docs/algorithm-and-llm/`：算法定义、训练与评估方案
- `plan/`：分周计划（如 `index(3.02-3.23).md`）

适用场景：

- 开发前确认系统约束
- 编写 issue / PR 的规范依据
- 对齐阶段目标与验收口径

## 5. 远端专题分支（topic branches）

以下分支常作为阶段性实现分支：

| 分支                                     | 最近主题                       | 合并状态（相对 `dev` / `master`） | 说明                   |
| ---------------------------------------- | ------------------------------ | --------------------------------- | ---------------------- |
| `origin/w6-tools-0/remote-rest-impl`     | PLM REST server 参考实现       | 已合入 `dev` / 未合入 `master`    | Week6 工具接入基础     |
| `origin/w6-infra-1/remote-protgpt2-impl` | 远程 PLM 实现统一与测试        | 已合入 `dev` / 未合入 `master`    | 基础设施整合           |
| `origin/w6-tools-1/adapte-plm`           | ProtGPT2 接入 de novo 起始节点 | 已合入 `dev` / 未合入 `master`    | 工具链扩展             |
| `origin/w6-tools-2/proteinmpnn-impl`     | ProteinMPNN NIM 接入与回退修复 | 已合入 `dev` / 未合入 `master`    | 工具后端增强           |
| `origin/fix/agent-contract`              | 契约文档路径修正               | 已合入 `dev` / 未合入 `master`    | 文档一致性修复         |
| `origin/fix/test-url`                    | 测试 URL 修复                  | 已合入 `master`                   | 小范围修复             |
| `origin/feature/de-novo-workflow`        | de novo 工作流文档增强         | 未合入 `dev` / 未合入 `master`    | 需按当前路线评估再合并 |
| `origin/feat/auto-index-regen`           | 文档索引 SID 修正              | 未合入 `dev` / 未合入 `master`    | 设计索引维护分支       |
| `origin/thesis-paper`                    | 论文结构草稿                   | 未合入 `dev` / 未合入 `master`    | 论文产物分支           |

> 说明：topic 分支通常为短生命周期；是否合并取决于当周计划与主线契约一致性。

## 6. 推荐协作流程

1. 先在 `design` 确认需求与约束
1. 在 `dev` 实现代码与测试
1. 在 `dev` 完成回归（`uv run pytest ...`）
1. 通过 PR 合并到 `master` 形成稳定快照

不建议：

- 跳过设计约束直接改 FSM/角色边界
- 在 `master` 直接做实验开发
- 未完成测试就推进合并

## 7. 本地快速开始（master）

```bash
# 依赖（推荐使用 uv）
uv sync

# 运行测试
uv run pytest

# 运行示例（按项目实际脚本）
./run_demo.sh
```

如果要查看“最新开发能力”，请切换到 `../thesis-project.dev` worktree。

## 8. 给新成员的最短路径

建议按顺序阅读：

1. `AGENT_CONTRACT.md`（先看系统不变量）
1. `AGENTS.md`（看协作与变更边界）
1. `src/workflow/` + `src/agents/`（看主链路）
1. `tests/integration/`（看端到端行为）
1. `../thesis-project.design/plan/`（看阶段目标）

## 9. 维护建议

为保持 README 持续有效，建议每次阶段切换时更新以下内容：

- worktree/分支关系（特别是 `master...dev` 差异）
- topic 分支合并状态
- 推荐协作流程中的发布门禁
