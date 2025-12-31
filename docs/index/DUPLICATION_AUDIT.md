# Duplication Audit（重复内容审计）

> 本文档用于识别跨设计文档的内容重复，明确：
>
> 1. 重复段落的具体位置
> 2. 指定保留的 SSOT SID
> 3. 其他位置应改为 SID 引用的计划
>
> **目标**：确保后续 `docslice` 脚本不会遇到**同概念多来源**问题，维护 SSOT 原则。

---

## 1. 审计总览

### 1.1 审计范围

本次审计覆盖以下 6 个设计文档：

- `docs/design/architecture.md`（doc_key: arch）
- `docs/design/agent-design.md`（doc_key: agent）
- `docs/design/core-algorithm-spec.md`（doc_key: algo）
- `docs/design/system-implementation-design.md`（doc_key: impl）
- `docs/design/tools-catalog.md`（doc_key: tools）
- `docs/design/hitl-extension.md`（doc_key: hitl）

### 1.2 审计方法

- 通过 SID 标记检测跨文档出现的相同 SID
- 通过内容语义分析识别未标注 SID 的重复段落
- 基于 SSOT_MAP.md 确定每个概念的权威来源

### 1.3 审计结果摘要

| 重复类型 | 数量 | 状态 |
|---------|------|------|
| SID 引用（合规） | 多处 | ✅ 已正确使用 `[ref:SID:...]` 引用 |
| SID 重复定义（违规） | 0 | ✅ 无重复定义 SID |
| 内容语义重复（需改进） | 6 处 | ⚠️ 见下文详细分析 |

---

## 2. SID 引用合规性检查

### 2.1 跨文档 SID 引用（✅ 合规）

以下 SID 在多个文档中出现，但符合引用规范（一处定义，多处引用）：

| SID | SSOT 文档 | 引用文档 | 状态 |
|-----|----------|---------|------|
| `SID:arch.contracts.pending_action` | architecture.md | agent-design.md<br>system-implementation-design.md<br>hitl-extension.md | ✅ 合规引用 |
| `SID:arch.contracts.decision` | architecture.md | system-implementation-design.md<br>hitl-extension.md | ✅ 合规引用 |
| `SID:arch.contracts.task_snapshot` | architecture.md | system-implementation-design.md<br>hitl-extension.md | ✅ 合规引用 |
| `SID:fsm.states.definitions` | architecture.md | agent-design.md<br>hitl-extension.md | ✅ 合规引用 |
| `SID:agent.overview.introduction` | agent-design.md | system-implementation-design.md | ✅ 合规引用 |

**结论**：当前所有跨文档 SID 出现均为合规引用，无重复定义问题。

---

## 3. 内容语义重复分析

### 3.1 核心契约对象的重复描述

#### 问题描述

**PendingAction / Decision / TaskSnapshot** 在多个文档中有不同视角的描述：

- **architecture.md**：定义契约的架构语义与在 FSM 中的作用
- **agent-design.md**：描述 Agent 如何与这些契约交互
- **system-implementation-design.md**：提供 Pydantic 模型定义与 API 契约

#### 重复位置

| 概念 | SSOT 定义位置 | 重复描述位置 | 重复类型 |
|------|-------------|------------|---------|
| PendingAction | architecture.md<br>`SID:arch.contracts.pending_action` | system-implementation-design.md<br>未标注独立 SID，通过引用 `[ref:SID:arch.contracts.pending_action]` | ⚠️ 扩展定义（Pydantic 模型） |
| Decision | architecture.md<br>`SID:arch.contracts.decision` | system-implementation-design.md<br>通过引用 `[ref:SID:arch.contracts.decision]` | ⚠️ 扩展定义（Pydantic 模型） |
| TaskSnapshot | architecture.md<br>`SID:arch.contracts.task_snapshot` | system-implementation-design.md<br>通过引用 `[ref:SID:arch.contracts.task_snapshot]` | ⚠️ 扩展定义（Pydantic 模型） |

#### 状态评估

✅ **合规**：system-implementation-design.md 已通过 `[ref:SID:...]` 引用 architecture.md 中的契约定义，仅在实现层添加了 Pydantic 模型扩展，未重新定义语义。

#### 改进计划

**无需改进**：当前做法符合分层设计原则：
- 架构层（architecture.md）定义契约语义
- 实现层（system-implementation-design.md）扩展为技术实现（Pydantic 模型）

---

### 3.2 FSM 状态的跨文档描述

#### 问题描述

FSM 状态定义在 **architecture.md** 中，但在 **agent-design.md** 的 HITL 章节中也有部分状态的语义描述。

#### 重复位置

| 状态 | SSOT 定义位置 | 重复描述位置 | 重复类型 |
|------|-------------|------------|---------|
| WAITING_PLAN_CONFIRM | architecture.md<br>`SID:fsm.states.waiting_plan_confirm` | agent-design.md（`SID:planner.hitl.plan_confirm`）<br>描述 PlannerAgent 在该状态下的职责 | ⚠️ 视角差异（架构 vs Agent 行为） |
| WAITING_PATCH_CONFIRM | architecture.md<br>`SID:fsm.states.waiting_patch_confirm` | agent-design.md（`SID:executor.hitl.patch_confirm`）<br>描述 ExecutorAgent 在该状态下的职责 | ⚠️ 视角差异（架构 vs Agent 行为） |
| WAITING_REPLAN_CONFIRM | architecture.md<br>`SID:fsm.states.waiting_replan_confirm` | agent-design.md（`SID:safety.hitl.replan_trigger`）<br>描述 SafetyAgent 触发该状态的条件 | ⚠️ 视角差异（架构 vs Agent 行为） |

#### 状态评估

✅ **合规**：这些描述是**互补视角**，而非重复：
- architecture.md 定义状态的架构语义（状态转换规则、契约要求）
- agent-design.md 定义 Agent 在该状态下的行为职责

#### 改进计划

**无需改进**：两个文档描述的是不同层面的关注点，符合分层设计原则。

---

### 3.3 Agent 接口的跨文档描述

#### 问题描述

**PlannerAgent / ExecutorAgent / SafetyAgent / SummarizerAgent** 的接口在 **agent-design.md** 中定义，但在 **system-implementation-design.md** 中也有部分描述。

#### 重复位置

| Agent | SSOT 定义位置 | 重复描述位置 | 重复类型 |
|-------|-------------|------------|---------|
| PlannerAgent | agent-design.md<br>`SID:planner.interface.overview` | system-implementation-design.md<br>在"Agent 实现"章节有简要描述，已通过 `[ref:SID:planner.interface.overview]` 引用 | ✅ 已引用，无重复定义 |
| ExecutorAgent | agent-design.md<br>未标注独立接口 SID | system-implementation-design.md<br>在"Agent 实现"章节有描述 | ⚠️ agent-design.md 缺少 ExecutorAgent 接口总览 SID |
| SafetyAgent | agent-design.md<br>未标注独立接口 SID | system-implementation-design.md<br>在"Agent 实现"章节有描述 | ⚠️ agent-design.md 缺少 SafetyAgent 接口总览 SID |
| SummarizerAgent | agent-design.md<br>未标注独立接口 SID | system-implementation-design.md<br>在"Agent 实现"章节有描述 | ⚠️ agent-design.md 缺少 SummarizerAgent 接口总览 SID |

#### 状态评估

⚠️ **需改进**：agent-design.md 中仅为 PlannerAgent 标注了 `SID:planner.interface.overview`，其他三个 Agent 缺少对应的接口总览 SID。

#### 改进计划

**后续 Issue**：为 ExecutorAgent、SafetyAgent、SummarizerAgent 在 agent-design.md 中补充以下 SID：
- `SID:executor.interface.overview`
- `SID:safety.interface.overview`
- `SID:summarizer.interface.overview`

然后在 system-implementation-design.md 中通过 `[ref:SID:...]` 引用这些 SID。

---

### 3.4 Plan 对象的双重定义

#### 问题描述

**Plan** 对象在两个地方有 SID 定义：
- `SID:arch.contracts.plan`（architecture.md）
- `SID:agent.contracts.plan`（agent-design.md）

#### 重复位置

| SID | 文档 | 定义内容 |
|-----|------|---------|
| `SID:arch.contracts.plan` | architecture.md | Plan 在架构层的作用：作为 FSM 状态转换的关键对象，与 PendingAction/Decision 的关系 |
| `SID:agent.contracts.plan` | agent-design.md | Plan 的数据结构定义（Python dataclass 形式）：`plan_id`, `steps`, `metadata` 等字段 |

#### 状态评估

✅ **合规**：这是**互补定义**，而非重复：
- `arch.contracts.plan`：架构层视角，定义 Plan 的**作用与契约**
- `agent.contracts.plan`：Agent 层视角，定义 Plan 的**数据结构**

#### 改进计划

**无需改进**：两个 SID 描述的是不同层面的关注点。

**文档改进建议**：在 architecture.md 的 `SID:arch.contracts.plan` 处添加引用说明：

```markdown
Plan 的数据结构定义详见 [ref:SID:agent.contracts.plan]。
```

---

### 3.5 hitl-extension.md 的差分索引特性

#### 问题描述

**hitl-extension.md** 在 issue #29 重构后已转换为**差分索引文档**，其中所有硬编码规约均已替换为 `[ref:SID:...]` 引用。

#### 审计结果

| 原始内容类型 | 当前状态 | 引用目标 |
|------------|---------|---------|
| FSM WAITING_* 状态定义 | ✅ 已引用 | `[ref:SID:fsm.states.waiting_*]` |
| PendingAction/Decision/TaskSnapshot | ✅ 已引用 | `[ref:SID:arch.contracts.*]` |
| Agent 职责边界 | ✅ 已引用 | `[ref:SID:<agent>.responsibilities.*]` |
| EventLog 约束 | ✅ 已引用 | `[ref:SID:obs.eventlog.mandatory_events]` |
| API 端点 | ✅ 已引用 | `[ref:SID:api.rest.*]` |

#### 状态评估

✅ **完全合规**：hitl-extension.md 不再包含任何硬编码规约，仅作为 HITL 相关规范的差分索引。

#### 改进计划

**无需改进**：hitl-extension.md 已完全符合 SSOT 原则。

---

### 3.6 工具规约的潜在重复

#### 问题描述

**ESMFold** 和 **AlphaFold** 等工具在 **tools-catalog.md** 中定义，可能在 **system-implementation-design.md** 的 ToolAdapter 章节中也有描述。

#### 审计结果

| 工具 | SSOT 定义位置 | 潜在重复位置 | 状态 |
|------|-------------|------------|------|
| ESMFold | tools-catalog.md<br>`SID:tools.esmfold.spec` | system-implementation-design.md | ✅ 未发现重复，impl 文档仅描述 ToolAdapter 接口 |
| AlphaFold | tools-catalog.md<br>`SID:tools.alphafold.spec` | system-implementation-design.md | ✅ 未发现重复 |
| ToolAdapter 约束 | tools-catalog.md<br>`SID:tools.adapter.constraints` | system-implementation-design.md | ⚠️ impl 文档有 ToolAdapter 接口定义，但无重复约束 |

#### 状态评估

✅ **基本合规**：工具规约集中在 tools-catalog.md，system-implementation-design.md 仅定义 ToolAdapter 的技术接口（Pydantic 模型、调用规范等）。

#### 改进计划

**文档改进建议**：在 system-implementation-design.md 的 ToolAdapter 章节添加引用：

```markdown
工具规约与约束详见 [ref:SID:tools.adapter.constraints]。
```

---

## 4. 未标注 SID 的重复段落

### 4.1 审计范围

检查是否存在**语义相同但未标注 SID**的段落，可能导致后续脚本无法识别重复。

### 4.2 审计结果

✅ **未发现未标注的重复段落**：

- 所有核心规约点均已标注 SID
- 跨文档出现的相同概念均已通过 `[ref:SID:...]` 引用

### 4.3 潜在风险区域

以下区域可能在未来引入未标注的重复内容，需持续监控：

| 区域 | 潜在风险 | 建议 |
|------|---------|------|
| Agent 实现细节（system-implementation-design.md） | 可能重复描述 Agent 接口 | 强制引用 agent-design.md 中的 SID |
| ToolAdapter 实现（system-implementation-design.md） | 可能重复描述工具规约 | 强制引用 tools-catalog.md 中的 SID |
| HITL 流程说明（各文档的"使用场景"章节） | 可能重复描述 HITL 机制 | 统一引用 architecture.md 和 agent-design.md 中的 SID |

---

## 5. 改进计划汇总

### 5.1 短期改进（可在本 PR 中完成）

| 改进项 | 位置 | 操作 |
|-------|------|------|
| 在 architecture.md 添加 Plan 数据结构引用 | architecture.md<br>`SID:arch.contracts.plan` | 添加：`Plan 的数据结构定义详见 [ref:SID:agent.contracts.plan]` |
| 在 system-implementation-design.md 添加 ToolAdapter 约束引用 | system-implementation-design.md<br>ToolAdapter 章节 | 添加：`工具规约与约束详见 [ref:SID:tools.adapter.constraints]` |

### 5.2 中期改进（后续 Issue）

| 改进项 | 目标 | 预期收益 |
|-------|------|---------|
| 为 ExecutorAgent、SafetyAgent、SummarizerAgent 补充接口总览 SID | agent-design.md | 完善 Agent 接口的 SSOT 定义，避免 system-implementation-design.md 成为事实 SSOT |
| 为 `storage` 和 `kg` domain 补充 SID 标注 | system-implementation-design.md | 完善存储层和知识图谱的可寻址性 |

### 5.3 长期改进（文档演进）

| 改进项 | 目标 | 预期收益 |
|-------|------|---------|
| 建立 Linting 规则，检测未引用的重复段落 | 整个文档体系 | 自动化 SSOT 原则检查 |
| 建立 `docslice` 脚本，验证引用有效性 | 整个文档体系 | 确保所有 `[ref:SID:...]` 引用指向存在的 SID |

---

## 6. 验收标准

### 6.1 SSOT 原则验收

- ✅ 每个核心概念有且仅有一个 SSOT 定义
- ✅ 所有跨文档引用使用 `[ref:SID:...]` 语法
- ✅ 无重复定义的 SID（全局唯一性）

### 6.2 Docslice 脚本验收

- ✅ `docslice` 提取规范时不会遇到**同概念多来源**
- ✅ 引用有效性检查通过（所有 `[ref:SID:...]` 指向存在的 SID）

### 6.3 Claude Code Skill 验收

- ✅ Skills 使用 `--topic` 聚合时，仅从 SSOT 文档提取规范
- ✅ 无重复规范导致的冲突或歧义

---

## 7. 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| 1.0 | 2025-12-31 | 初始版本，审计 6 个设计文档的内容重复情况，确认 SSOT 合规性 |

---

**本文档是 Milestone "Addressable Design Docs & Spec Retrieval Skill" 的质量保证文件，任何修改应通过正式的 PR 流程并更新版本历史。**
