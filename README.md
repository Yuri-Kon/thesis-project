# thesis-project

面向蛋白质设计任务的 **LLM 驱动多智能体工作流系统**。

本仓库的 `master` 分支定位为稳定主线和对外入口。当前 `master`
已完成系统验证闭环（13 个 TC 用例，12 通过）和 84-run 完整四组策略
实验矩阵，阶段标签为 `v1.0`。

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

## 2. 当前稳定基线 (v1.0)

v1.0 在 CEBRA-WP v2 代码基线之上，完成了系统验证闭环和正式实验矩阵。

### 系统验证

13 个系统验证用例（TC-S01 至 TC-S13）中 12 个通过、1 个部分通过：

| 类别 | 用例 | 状态 |
|---|---|---|
| 环境与能力就绪 | TC-S01 | ✅ 通过 |
| API 合约与任务录入 | TC-S02/TC-S03 | ✅ 通过 |
| FSM / HITL / 快照 | TC-S04/TC-S05/TC-S06 | ✅ 通过 |
| Web 前端可用性 | TC-S07 | ✅ 通过 |
| CLI 可用性 | TC-S08 | ⚠️ 部分通过 |
| 端到端流程 | TC-S09 | ✅ 通过 |
| 异常输入与安全 | TC-S10 | ✅ 通过 |
| 工具链 I/O | TC-S11 | ✅ 通过 |
| 失败恢复 | TC-S12 | ✅ 通过 |
| 止损审计 | TC-S13 | ✅ 通过 |

验证框架包含三级体系：30 个 `SV-*` 逐点验证清单、13 个 `TC-*` 可执行测试用例、`EVD-*` 证据编号索引。详细证据见 `docs/system-validation/`。

### 实验矩阵

- **t9-clean**（16 runs）：4 任务 × 4 组策略，16/16 DONE
- **thesis-final-v1-001**（84 runs）：7 任务类 × 4 组 × 至多 2 重复，81 DONE / 1 FAILED

四组策略：`static_top1` / `fixed_threshold_gate` / `dynamic_no_belief_state` / `lite_belief_state`

任务覆盖：de novo 设计、序列评估、稳定性优化、高代价结构预测、可修复参数失败、远程服务降级、结构性失败恢复全链路。

### v1.0 新增主要特性

#### 3D 结构查看器
- 基于 Canvas 的交互式分子查看器，支持拖拽旋转、滚轮缩放、点击选原子
- 4 种显示模式：Cartoon ribbon / Trace / Backbone / Sticks / All
- 3 种配色模式：Confidence (pLDDT) / Element (CPK) / Chain
- 全屏模式、滑块控制、残基标签、XYZ 坐标轴

#### LLM 诊断系统
- 独立模块 `src/llm/response_diagnostics.py`（410 行）
- 空响应和 API 调用失败自动诊断，识别 9 种空响应原因和 7 种调用失败原因

#### CLI 帮助系统
- 全部 7 个一级命令 + 二级子命令补充中文 help
- 顶层 10 条示例

#### OpenFold3 Runner 改进
- MSA Server 开关控制
- 运行时临时目录隔离与自动清理
- mmCIF 格式结构文件坐标解析（OpenFold3 输出兼容）

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
- `patch`
- `replan`
- `stop`

当前阶段可说"实现和契约已落地"；不要把单元测试通过表述为算法有效性已验证。

## 4. API、工作台与 HITL UI

当前 `master` 提供 FastAPI 服务和 React 工作台入口：

- Dashboard：查看任务概览、待决策入口和执行状态；
- Task Builder：基于字段注册表创建结构化任务，支持抽取、确认和 safety precheck；
- Task Detail：展示任务状态、pending action、候选比较、结构和报告；
- Pending Review：查看候选、runtime summary、theory objects，并提交 `Decision`；
- Event Timeline：查看状态迁移、waiting enter/exit、decision applied、恢复链路和报告信息；
- **Structure Viewer**：交互式 3D 分子查看器，支持卡通/骨架/棍棒渲染和置信度着色；
- Theory Object Summary：把候选评分、runtime adjustment、action utility 与理论对象关联展示；
- API schema：暴露任务、pending action、event timeline、candidate display 等契约。

UI 语言：中文。

CLI：`python -m src.cli` 或 `design` 命令。支持 submit/task/pending/timeline/report/intake 等子命令。

主要前端源码位于 `src/api/frontend/`，构建产物进入 `src/api/static/web/`。

## 5. 当前阶段标签与后续

当前阶段标签：

- `v1.0`（当前稳定版本）
- `cebra-wp-v2-stage-20260506`（前期代码基线）

v1.0 已完成的重点：

- 系统验证闭环（13 TC, 30 SV, EVD 证据体系）
- 84-run 四组策略实验矩阵
- 3D 结构查看器（三次迭代）
- LLM 诊断模块
- CLI 帮助系统
- OpenFold3 runner 改进与 mmCIF 支持
- 前端全面中文化
- 候选选择与工具回退机制修复
- high-cost 计数修正

## 6. 分支与协作约定

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

## 7. 建议阅读顺序

如果要快速建立上下文，推荐按这个顺序阅读：

1. `AGENT_CONTRACT.md`
2. `AGENTS.md`
3. `src/models/contracts.py`
4. `src/workflow/`
5. `src/agents/`
6. `src/infra/issue200_acceptance_gate.py`
7. `tests/`（特别是 `tests/integration/` 和 `tests/unit/`）
8. `docs/system-validation/`（系统验证证据）
9. `../thesis-project.design/docs/design/`

## 8. README 维护规则

阶段合并或算法/架构调整后，README 至少同步：

- 当前稳定版本标签和代码基线；
- 当前算法能力和 runtime control 语义；
- FSM、agent 边界、恢复链路是否变化；
- API / UI 入口是否变化；
- 当前阶段验证状态与实验结论；
- `master`、`dev`、`design` 的职责说明是否仍准确。
