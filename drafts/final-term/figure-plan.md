# 论文图示规划与缺口清单

> 最后更新：2026-05-11
> 用途：指导后续图示补充，确保每章关键概念有对应视觉呈现

---

## 已有图示（可直接使用）

### 设计图（drawio 源，来自 `dev/asserts/figures/`）

| 编号 | 文件名 | 内容 | 归入章节 |
|------|--------|------|----------|
| D01 | `system-architecture.drawio` | 五层分层架构、控制面 SSOT、可恢复审计链 | 第 4 章 |
| D02 | `fsm-state-transition.drawio` | 11 状态 FSM、三类 WAITING 决策点、恢复路径 | 第 4 章 |
| D03 | `workflow-flowchart.drawio` | 六阶段 de novo 工作流、Safety Gate、Patch/Replan 控制层 | 第 4 章 |
| D04 | `algorithm-loop.drawio` | CEBRA-WP 闭环：候选生成→过滤→静态评分→信念更新→运行时重排序→动作选择 | 第 4 章 |
| D05 | `uml-contracts.drawio` | 核心数据契约：ProteinDesignTask / Plan / StepResult / PendingAction / Decision / TaskSnapshot / RuntimeState / DesignResult | 第 4 章 |
| D06 | `runtime-sequence.drawio` | 运行时执行序列（PlanRunner → StepRunner → Adapter） | 第 5 章（候选） |
| D07 | `workflow-swimlane.drawio` | 泳道式工作流总览 | 第 5 章（候选） |
| D08 | `technical-route.drawio` | 技术路线概览 | 第 2 章或第 3 章（候选） |
| D09 | `experiment-design-framework.drawio` | 实验设计框架 | 第 7 章 |

### Mermaid 图（`paper/figures/`，备选，偏简略）

| 文件名 | 内容 | 备注 |
|--------|------|------|
| `system-architecture-overview.mmd` | 五层架构简图 | 被 D01 替代 |
| `multi-agent-core.mmd` | Agent 类图 | 被 D05 替代 |
| `core-algorithm-overview.mmd` | 算法流程简图 | 被 D04 替代 |
| `recovery-hitl-overview.mmd` | 恢复+HITL 简图 | 可保留作补充 |
| `single-step-sequence.mmd` | 单步时序简图 | 可保留作补充 |
| `total-sequence.mmd` | 全流程时序简图 | 可保留作补充 |
| `component-views.mmd` | 组件视图 | 可保留作补充 |

> **终稿统一原则**：以 drawio（D01-D09）为主图源，Mermaid 图仅作为备选或附录，不在正文混用两套风格。

### 验证截图（`docs/system-validation/06-ui-screenshots/`）

共 18 张 PNG，证编编号 FIG-SV-01 至 FIG-SV-18，用于第 6 章。

---

## 待补充图示

### G01 · 问题-方案对照图 🔴 优先

**归入**：第 3 章末尾或第 4 章开头

**目的**：从需求到设计的叙事过渡——审阅者一眼看清"现有方案的问题"和"本系统的改变"。

**内容建议**（左右对照布局）：

```
┌─────────────────────────────┐    ┌─────────────────────────────────┐
│  固定流水线                     │    │  本系统                          │
│                               │    │                                 │
│  用户输入目标                   │    │  用户输入目标 + 约束               │
│        ↓                      │    │        ↓                        │
│  人工或脚本选定工具链            │    │  Planner + ToolKG 生成候选        │
│        ↓                      │    │        ↓                        │
│  顺序执行                      │    │  人工审查 → 确认/选择候选          │
│        ↓                      │    │        ↓                        │
│  ↓                             │    │  Executor 执行 + RuntimeState 更新│
│  步骤失败? ──→ 任务失败 ❌       │    │        ↓                        │
│                               │    │  ↓                              │
│                               │    │  失败? ──→ retry → patch → replan│
│                               │    │        ↓                        │
│                               │    │  SafetyAgent 全程审查             │
│                               │    │        ↓                        │
│                               │    │  DesignResult + 审计链 ✅         │
└─────────────────────────────┘    └─────────────────────────────────┘
```

**关键对比点标注**：
- 工具链选择：人工固定 vs Planner + KG 候选生成
- 失败处理：直接失败 vs retry → patch → replan 分层恢复
- 安全：无 vs SafetyAgent 全程审查
- 可追溯性：无 vs EventLog + Snapshot 审计链

---

### G02 · ProteinToolKG 局部可视化 🔴 优先

**归入**：第 4 章（4.5.2 候选生成 或 4.7.5 工具适配模块）

**目的**：让"能力驱动的工具链组合"从抽象概念变为可理解的具体结构。

**内容建议**（知识图谱局部示意）：

选择 6-8 个代表性工具节点，展示 capability、I/O 和 compat 关系：

```
                    ┌──────────────────────┐
                    │     protgpt2          │
                    │  capability:          │
                    │   sequence_generation │
                    │  outputs:             │
                    │   sequence: str       │
                    │  cost: low            │
                    └──────┬───────────────┘
                           │ sequence
                           │ compat: esmfold.sequence
                           ▼
┌──────────────────┐   ┌──────────────────────┐
│   protein_mpnn    │   │      esmfold          │
│  capability:      │   │  capability:          │
│   sequence_design │   │   structure_prediction│
│  outputs:         │   │  inputs:              │
│   sequence: str   │   │   sequence: str       │
│  cost: medium     │   │  outputs:             │
└──────┬───────────┘   │   pdb_path: path       │
       │ sequence       │   plddt: float         │
       │ compat: esmfold│  cost: high ⚠         │
       └───────┬───────┴──────────────────────┘
               │ pdb_path + plddt
               │ compat: biopython_qc.pdb_path
               ▼
       ┌──────────────────────┐
       │    biopython_qc       │
       │  capability:          │
       │   quality_control     │
       │  inputs:              │
       │   pdb_path: path      │
       │  outputs:             │
       │   qc_pass: bool       │
       │  cost: low            │
       └──────────────────────┘
```

**节点属性**（每个节点内标注）：
- `capability`：工具所属的能力分类
- `inputs` / `outputs`：关键 I/O 字段
- `cost`：low / medium / high
- `safety_level`：S0 / S1

**边的语义**：
- 实线箭头 + `compat: {下游工具}.{字段}` 标签（表示 I/O 兼容）
- 不同颜色区分能力分类（序列生成、结构预测、质量控制、目标评分）

---

### G03 · 具体实例走查图 🟡 建议

**归入**：第 4 章（4.8 模块协作流程）或第 5 章（5.1 技术选型之后）

**目的**：用真实任务实例走一遍完整的数据流，让抽象契约"活过来"。

**内容建议**（以 t1_trpcage_denovo 为例的纵向走查）：

```
ProteinDesignTask
┌─────────────────────────────────────────┐
│ task_id: "t1_trpcage_denovo_..."         │
│ goal: "设计一个 30 残基的稳定螺旋肽"       │
│ constraints: {                           │
│   length_range: [25, 35],                │
│   objective_type: "stability"            │
│ }                                        │
└─────────────────────────────────────────┘
                    ↓ Planner + ToolKG
Plan
┌─────────────────────────────────────────┐
│ S1: tool=protein_mpnn                    │
│     inputs: {goal, length_range}         │
│     ↓ sequence                           │
│ S2: tool=esmfold                         │
│     inputs: {sequence: "S1.sequence"} ←──┼── 引用上游
│     ↓ pdb_path, plddt                    │
│ S3: tool=objective_ranker                │
│     inputs: {pdb_path: "S2.pdb_path"} ←──┼── 引用上游
└─────────────────────────────────────────┘
                    ↓ Executor
StepResult(S2)
┌─────────────────────────────────────────┐
│ step_id: "S2"                            │
│ tool: "openfold"                         │
│ status: "success"                        │
│ outputs: {                               │
│   pdb_path: "output/pdb/.../model.cif",  │
│   plddt: 88.2                            │
│ }                                        │
└─────────────────────────────────────────┘
                    ↓ Summarizer
DesignResult
┌─────────────────────────────────────────┐
│ sequence: "NLYIQWLKDGGPSSGRPPPS"         │
│ structure_pdb_path: "output/pdb/..."      │
│ scores: {plddt_mean: 88.2}               │
│ report_path: "output/reports/...json"     │
└─────────────────────────────────────────┘
```

**关键标注**：
- `S1.sequence` → `S2.inputs.sequence` 引用解析（红色箭头）
- 每个对象的真实数据值（非 schema 定义，而是实例值）
- StepResult 标注 `status: success`，强调"这是真实运行的产物"

---

### G04 · HITL 触发条件与决策逻辑图 🟢 可选

**归入**：第 4 章（4.3 FSM 或 4.5.6 策略组）

**目的**：补充 FSM 图（只展示了转移路径）缺失的"转移条件"。

**内容建议**：在 D02（FSM 状态转移图）上叠加条件标注，或单独画决策表：

| 当前状态 | 触发条件 | 目标状态 | 决策方式 |
|----------|---------|---------|---------|
| PLANNING | 候选置信度充分 ∧ 无高成本工具 | PLANNED | auto |
| PLANNING | 候选置信度不足 ∨ 高成本工具 ∨ safety warn | WAITING_PLAN_CONFIRM | HITL |
| RUNNING | 步骤成功 | RUNNING（下一步） | auto |
| RUNNING | 步骤失败 ∧ retry 可用 | RUNNING（重试） | auto |
| RUNNING | 步骤失败 ∧ retry 耗尽 ∧ patchable | WAITING_PATCH_CONFIRM | HITL |
| RUNNING | 步骤失败 ∧ retry 耗尽 ∧ 结构性/安全阻断 | WAITING_REPLAN_CONFIRM | HITL |

> 此图可用文字表格替代，不必强求图示。但如果要画，建议做成"FSM 图上标注转移条件"的增强版本。

---

### G05 · 恢复路径对比图 ⏳ 等待

**归入**：第 7 章（7.8 典型案例分析）

**目的**：对比同一失败场景在 static_top1 和 lite_belief_state 下的不同路径。

**内容建议**：等待 84-run 数据后，用真实案例的事件日志绘制两条时间线（上：static_top1 直接 FAILED / 下：lite_belief_state 经信念评估 → patch → 人工确认 → DONE）。标注关键决策点和指标差异（high_cost_call、recovery_margin 等）。

> 依赖第 7 章实验数据，暂不执行。

---

### G06 · 实现层视觉补充 🟢 可选

**归入**：第 5 章

**内容**：
1. **模块目录结构图**（树形图）：`src/api/`、`src/agents/`、`src/workflow/`、`src/models/`、`src/adapters/`、`src/storage/`、`src/kg/`
2. **关键前端页面截图**（2-3 张，从 FIG-SV 中选代表性的）：
   - Dashboard（FIG-SV-02）：展示任务列表和工作区概览
   - Task Builder（FIG-SV-07）：展示中文化后的任务构建入口
   - Task Detail（FIG-SV-13）：展示任务详情首页
3. **15 个 API 端点总览表**（文字表即可，不必画图）

> 这些不属于"需要画的图"，而是"从已有素材中选取和整理"。模块目录树可用命令行 `tree` 生成或手绘。

---

## 图号分配方案（8 章结构）

| 图号 | 章节 | 内容 | 来源 |
|------|------|------|------|
| 图 3-1 | 第 3 章 | 问题-方案对照：固定流水线 vs 本系统 | G01（待画） |
| 图 4-1 | 第 4 章 | 系统五层分层架构 | D01 |
| 图 4-2 | 第 4 章 | ProteinToolKG 局部可视化 | G02（待画） |
| 图 4-3 | 第 4 章 | FSM 状态转移图 | D02 |
| 图 4-4 | 第 4 章 | 六阶段 de novo 工作流 | D03 |
| 图 4-5 | 第 4 章 | CEBRA-WP 算法闭环 | D04 |
| 图 4-6 | 第 4 章 | 核心数据契约 UML | D05 |
| 图 4-7 | 第 4 章 | 实例走查：t1 任务数据流 | G03（待画） |
| 图 5-1 | 第 5 章 | 模块目录结构 | G06 |
| 图 5-2 | 第 5 章 | 前端关键页面（Dashboard / Task Builder / Task Detail） | FIG-SV-02/07/13 |
| 图 5-3 | 第 5 章 | 运行时执行序列 | D06 或 D07 |
| 图 6-1 | 第 6 章 | 测试用例覆盖矩阵（表 6-1 的可视化） | 文字表 |
| 图 6-2 | 第 6 章 | 前端关键页面验证截图（Dashboard / Timeline） | FIG-SV-02/18 |
| 图 7-1 | 第 7 章 | 实验设计框架 | D09 |
| 图 7-2 | 第 7 章 | 四组消融主实验结果 | 待 84-run 数据 |
| 图 7-3 | 第 7 章 | 典型案例时间线对比 | 待 84-run 数据 |

---

## 执行建议

| 优先级 | 图 | 执行时机 |
|--------|-----|---------|
| 🔴 立即 | G02 ProteinToolKG 可视化 | 可现在就画，第 4 章写 LaTeX 时需要 |
| 🔴 立即 | G01 问题-方案对照 | 第 3 章写 LaTeX 时需要 |
| 🟡 第 4 章转 LaTeX 前 | G03 实例走查 | 放在第 4 章末尾或第 5 章开头 |
| 🟢 第 5 章写草稿前 | G06 实现层视觉 | 从已有素材中选 |
| 🟢 第 4 章转 LaTeX 前 | G04 HITL 触发条件 | 可文字表替代 |
| ⏳ 第 7 章写草稿前 | G05 恢复路径对比 | 依赖 84-run 案例数据 |
