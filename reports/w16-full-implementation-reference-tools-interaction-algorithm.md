# 全量实现长期参考文档：工具接入、交互设计与核心算法

- 文档类型：长期参考 / 设计对照 / 实施蓝图
- 起草时间：2026-04-13
- 适用范围：
  - 代码仓库：`thesis-project.dev`
  - 设计仓库：`thesis-project.design`
  - 主题范围：工具接入、任务入口与 HITL 交互、核心自适应算法
- 目标：
  - 基于当前设计与现有实现，判断三部分是否已经“完整实现”
  - 给出面向完整实现的目标架构与具体设计方案
  - 形成后续数周到数月都能持续使用的实施与审计依据

## 1. 文档定位

本文件不是一次性的 issue 说明，而是面向后续持续开发的长期参考文档。

本文件回答三个问题：

1. 当前实现到了哪里。
2. 与设计目标相比，还差什么。
3. 如果按“完整实现”推进，应当怎么设计、如何分阶段落地、如何验收。

本文件不改变既有系统不变量：

- 不新增 FSM 状态。
- 不改变 Planner / Executor / Safety / Summarizer 边界。
- 不破坏 `retry -> patch -> replan` 恢复顺序。
- 不把系统入口的意图澄清直接塞进现有运行态 FSM。

这些约束来自：

- `AGENT_CONTRACT.md`
- `docs/design/architecture.md`
- `docs/design/agent-design.md`
- `docs/design/core-algorithm-spec.md`
- `docs/design/runtime-adaptation-formalization.md`

## 2. 主要依据

### 2.1 设计侧依据

- 设计要求系统围绕显式 FSM 运作，`WAITING_*` 表示执行暂停、等待人工决策。
- 设计要求 Planner 输出 `Plan / PlanPatch / Replan` 候选，而不是直接执行工具。
- 设计要求核心算法是工作流级的动态规划问题，而不是简单的 ToolKG 检索。
- 设计要求使用 Lite belief-state 承载运行时状态，支持 `continue / patch_local / suffix_replan / stop`。
- 设计要求 `stop` 复用 `WAITING_REPLAN_CONFIRM` 与 `terminal_stop` 语义，而不是新增 FSM 状态。

对应设计片段可追溯到：

- `SID:algo.adaptive.problem_formulation`
- `SID:algo.adaptive.optimization_objective`
- `SID:planner.algorithm.candidate_scoring`
- `SID:planner.algorithm.runtime_state_estimation`
- `SID:planner.algorithm.runtime_reranking`
- `SID:planner.algorithm.runtime_action_selection`
- `SID:planner.algorithm.stop_semantics`
- `SID:arch.contracts.pending_action`

### 2.2 当前实现依据

本文件以当前仓库真实代码为准，而不是以旧 issue 预期为准。

关键代码入口：

- 任务同步主链：`src/workflow/workflow.py`
- 任务入口 API：`src/api/main.py`
- 规划器：`src/agents/planner.py`
- 目标解析：`src/agents/task_goal_parser.py`
- 运行时上下文：`src/workflow/context.py`
- 运行时状态更新：`src/workflow/belief_state.py`
- 计划执行与动作选择接缝：`src/workflow/plan_runner.py`
- Patch 闭环：`src/workflow/patch_runner.py`
- 动作选择与恢复映射：`src/workflow/recovery.py`
- 内置适配器注册：`src/adapters/builtins.py`
- 工具能力图：`src/kg/protein_tool_kg.json`

### 2.3 现有验证依据

仓库内已有两类高价值证据：

- [full_flow_validation_report.md](/home/yurikon/文档/thesis/thesis-project.dev/reports/full_flow_validation_report.md)
- [usability_validation_report.md](/home/yurikon/文档/thesis/thesis-project.dev/reports/usability_validation_report.md)

此外，本次补充验证执行了：

```bash
uv run pytest \
  tests/integration/test_candidate_score_gate.py \
  tests/integration/test_recovery_layered_patch.py \
  tests/integration/test_s6_control_layer_e2e.py \
  tests/api/test_api_endpoints.py \
  -q
```

结果：`38 passed, 3 warnings in 51.10s`

这说明当前系统不是“只有设计，没有运行链路”，而是已经具备真实主链骨架。

### 2.4 外部参考

本文件关于交互设计与澄清机制，参考了以下公开资料：

- OpenAI Deep Research in ChatGPT
  - `https://help.openai.com/articles/10500283`
  - 关键点：先澄清目标、允许用户审阅和修改计划、再执行研究。
- OpenAI API Deep Research guide
  - `https://platform.openai.com/docs/guides/deep-research`
  - 关键点：Clarification -> Prompt rewriting -> Research 是显式分层；如果开发者不做澄清，模型会直接开始执行。
- LangChain / LangGraph human-in-the-loop
  - `https://reference.langchain.com/javascript/functions/langchain.index.humanInTheLoopMiddleware.html`
  - `https://reference.langchain.com/python/langchain/agents/middleware/human_in_the_loop`
  - 关键点：动作决策不应只有 approve，还应支持 edit 与 reject。
- Microsoft Adaptive Cards / Copilot Studio
  - `https://learn.microsoft.com/en-us/adaptive-cards/`
  - `https://learn.microsoft.com/en-us/microsoft-copilot-studio/guidance/adaptive-card-summarize-responses`
  - `https://learn.microsoft.com/en-us/microsoft-copilot-studio/adaptive-cards-overview`
  - 关键点：对话系统中的多轮收集应尽量落到显式表单、按钮和摘要确认。
- Rahmani et al., 2024
  - `https://aclanthology.org/2024.findings-eacl.84/`
  - 关键点：对模糊或较短请求，具体、简短、针对性的澄清问题更有助于用户满意度。

## 3. 总体结论

当前系统已经完成了“可运行原型”的主要骨架，但三部分均未达到“完整实现”。

### 3.1 工具接入

当前状态：

- 已接入核心 P0 工具族，但覆盖仍然偏窄。
- 已有 ToolKG、AdapterRegistry、fallback、local/remote/hybrid 表达。
- 仍存在“KG 声明有、代码注册没有”的能力缺口。
- 仍存在“为了演示闭环而退化到 dummy_tool”的路径。

结论：

- 工具接入已经具备工程骨架。
- 工具生态尚未完整实现。

### 3.2 交互设计

当前状态：

- HITL 决策页已具备候选展示与决策提交能力。
- 任务入口仍然是 `goal + constraints` 的薄接口。
- 自然语言解析仍是 v1 级别的保守规则抽取。

结论：

- 运行中交互已经具备。
- 规划前交互与任务入口设计尚未完整实现。

### 3.3 核心算法

当前状态：

- 已有候选生成、静态评分、Top-K gate、Lite belief-state、动作选择、terminal stop、runtime rerank 接口。
- 上述机制已经进入主链，不是纯测试 stub。
- 但仍以规则驱动和启发式为主，没有完成完整的“工作流级动态优化器”。

结论：

- 核心算法 v1 已实现。
- 核心算法完整形态尚未实现。

## 4. 当前实现全景

### 4.1 当前已注册工具

根据 `src/adapters/builtins.py` 与 `src/kg/protein_tool_kg.json`，当前已接入的工具主要为：

| 类别 | 当前工具 | 状态 |
|---|---|---|
| 结构预测 | `esmfold` / `nim_esmfold` / `alphafold` / `openfold` | 已实现，部分条件注册 |
| 序列设计 | `protein_mpnn` | 已实现 |
| 序列生成 | `protgpt2` | 已实现 |
| 质量控制 | `biopython_qc` / `dssp` | 已实现 |
| 相似性检索 | `mmseqs2` / `blastp` | 已实现 |
| 可视化 | `visualization` | 已实现 |
| 演示闭环 | `dummy_tool*` | 已实现，但仅用于演示/保底 |

关键事实：

- `nim_esmfold`、`alphafold` 依赖 `NIM_API_KEY`。
- `openfold` 依赖 `OPENFOLD3_REST_BASE_URL` 或 provider config。
- 当环境不满足时，工具不会被注册。
- 任务同步主链仍保留 `nextflow` 缺失时退化为 `dummy_tool` 的路径。

### 4.2 当前任务入口

当前 API 入口是：

- `POST /tasks`
- 请求体字段：`goal`、`constraints`、`metadata`

当前入口特点：

- 简单直接。
- 适合 demo。
- 不适合复杂实验设计任务。
- 不适合用户在多轮中逐步补足约束。

### 4.3 当前交互界面

当前 UI 重点覆盖：

- PendingAction 列表
- Task Detail
- Candidate Comparison
- Decision 提交

当前 UI 不覆盖：

- 任务创建与多轮澄清
- 槽位确认
- 预算、目标属性、工具偏好等任务前配置
- 结构化任务模板

### 4.4 当前核心算法骨架

当前算法链已经包括：

| 能力 | 当前实现状态 |
|---|---|
| Plan / Patch / Replan Top-K | 已实现 |
| 静态评分 | 已实现 |
| 运行时状态更新 | 已实现 |
| 运行时重排序 | 已实现 |
| 动作选择 | 已实现 |
| terminal stop | 已实现 |
| Patch / Replan / WAITING_* 闭环 | 已实现 |
| 快照与事件审计 | 已实现 |

这套链路已经足以支撑“Lite v1 自适应控制层”。

## 5. 对比一：工具接入

## 5.1 当前实现与设计的差距

### 当前已经具备

- ToolKG 已定义 capability / io_type / constraints / preferred_next。
- AdapterRegistry 已支持按 `tool_id` 或 `adapter_id` 获取适配器。
- 已支持 local / remote / hybrid / mock 的 source 概念。
- 当前工具已覆盖蛋白设计最小闭环。

### 当前不足

| 问题 | 现状 | 风险 |
|---|---|---|
| 工具覆盖不完整 | 缺少结构相似性、目标评分、功能评分、稳定性评分等关键工具 | 难以支撑更复杂设计目标 |
| KG 与 adapter 不完全一致 | `objective_ranker` 在回退矩阵和 KG 中存在，但没有真实 adapter | 评分链条不闭环 |
| 条件注册过重 | 多个工具仅在环境满足时注册 | 候选排序与真实可执行性脱节 |
| demo 保底路径过强 | `nextflow` 缺失时会退化到 `dummy_tool` | 容易把“闭环完成”误判成“科研任务完成” |
| 缺少统一健康视图 | 没有 capability 级 readiness matrix | 用户和 Planner 都难以明确知道当前可用工具面 |
| 缺少标准化评估工具族 | similarity / QC 已有，但 objective / function / docking / stability 仍缺 | 无法完整比较候选方案 |

## 5.2 完整实现目标

完整实现不是“再接几个工具”，而是形成稳定的工具平台。

目标形态应满足：

1. 每个 capability 至少有一个主工具和一个备工具。
2. KG 中声明的关键工具必须有真实 adapter，不能长期停留在占位状态。
3. 工具可用性必须在规划前显式暴露给用户和 Planner。
4. 工具接入不只是“能调用”，还要有：
   - 输入输出标准契约
   - 健康检查
   - 超时与失败码规范
   - 审计字段
   - fallback 优先级
5. 工具平台必须支持逐步扩张，而不是每接一个工具就写一套新逻辑。

## 5.3 建议的完整工具谱系

建议将工具能力扩展为六层：

| 层级 | 目标 | 建议工具 |
|---|---|---|
| L1 生成/设计 | 产生初始序列或结构条件重设计 | `protgpt2`、`protein_mpnn` |
| L2 结构预测 | 生成结构与结构置信度 | `esmfold`、`nim_esmfold`、`alphafold`、`openfold3_rest` |
| L3 基础 QC | 长度、字符、plddt、二级结构、简单理化检查 | `biopython_qc`、`dssp` |
| L4 相似性与检索 | 判定 novelty、近邻、模板可复用性 | `mmseqs2`、`blastp`、建议新增 `foldseek` |
| L5 目标评分 | 对候选进行综合排序与任务目标对齐评分 | 建议新增 `objective_ranker`、可选 `stability_ranker` |
| L6 功能/实验代理 | 结合位点、相互作用、稳定性、对接、下游实验风险 | 建议新增 docking / interface / stability / annotation 工具 |

## 5.4 工具接入优先级

### P0：必须补齐

- `objective_ranker`
  - 原因：当前 KG 与算法已经依赖 objective scoring，但缺真实执行器。
- `openfold3_rest` 作为显式工具 ID
  - 原因：当前 `openfold` 与远程 REST 混用，表达层不够清晰。
- 工具健康矩阵与 capability readiness
  - 原因：这是 Planner 和 UI 的共同依赖。

### P1：强烈建议补齐

- `foldseek` 或等价结构相似性检索工具
- 结构/功能 annotation 工具
- 稳定性或 docking 代理工具

### P2：在论文主线明确后补齐

- 多目标打分器
- 主动学习/实验反馈接口
- 实验批量调度器

## 5.5 完整实现的工具平台设计

### 5.5.1 新增 Capability Readiness Matrix

建议新增一层 capability 级 readiness 视图，而不是仅靠 adapter 是否存在。

定义：

```json
{
  "capability_id": "objective_scoring",
  "status": "ready | degraded | unavailable",
  "primary_tool_id": "objective_ranker",
  "fallback_tool_ids": ["mmseqs2", "blastp"],
  "reason": "primary adapter missing",
  "checked_at": "2026-04-13T00:00:00Z"
}
```

用途：

- Planner 在生成候选前读取。
- UI 在任务创建时展示。
- EventLog 在候选退化时引用。

### 5.5.2 新增工具健康检查协议

每个 adapter 增加统一接口：

- `describe_capabilities()`
- `healthcheck()`
- `normalize_error()`
- `estimate_cost()`
- `estimate_latency()`

这样工具不仅能执行，还能作为规划输入参与排序和风险估计。

### 5.5.3 新增 objective_ranker

建议 `objective_ranker` 不依赖大模型，先采用显式规则/加权器完成 v1：

- 输入：
  - `sequence`
  - `structure_pdb`
  - `qc_metrics`
  - `similarity_hits`
  - `secondary_structure_summary`
  - task constraints / objective weights
- 输出：
  - `objective_score`
  - `score_breakdown`
  - `top_k_rank`
  - `objective_explanation`

该工具应成为：

- Planner 静态评分解释的落地点
- Executor 后验评分的真实工具
- Report 中最终排名依据的一部分

### 5.5.4 显式区分工具 ID 与执行模式

建议把 `tool_id` 与 `execution_mode` 彻底分离：

- `tool_id=openfold3`
- `execution_mode=local_cli | remote_rest | nim_proxy | mock`

收益：

- KG 语义更稳定。
- 日志更可比。
- Planner 不再把“同一工具不同模式”误当不同 scientific capability。

### 5.5.5 取消默认 demo 降级误导

当前 `dummy_tool` 可以继续保留，但应改变策略：

- 开发/测试模式允许自动降级。
- 产品/实验模式默认禁止自动降级。
- 若触发降级，必须在 `TaskRecord.metadata`、`EventLog`、`Report` 中显式标记。

推荐增加任务级约束：

- `allow_demo_fallback: bool`
- 默认值在实验模式下为 `false`

## 5.6 工具接入实施顺序

1. 补 `objective_ranker`
2. 补 capability readiness matrix
3. 工具 ID 与 execution mode 解耦
4. 引入结构相似性工具
5. 扩展目标评分与功能工具

## 5.7 工具接入验收标准

- KG 的 P0/P1 工具项都有真实 adapter 或明确标为设计占位。
- 任一 capability 都能从 API 获取 readiness。
- Planner 的默认推荐不会依赖未注册工具。
- 实验模式下禁止静默降级到 demo tool。
- `objective_ranker` 进入真实执行链，而非只存在于 Planner metadata。

## 6. 对比二：交互设计

## 6.1 当前实现与设计的差距

### 当前已经具备

- WAITING_PLAN_CONFIRM / PATCH / REPLAN 三类人在环路能力。
- PendingAction 候选展示与决策提交。
- 候选比较、默认推荐、成本/风险说明的基础 UI。

### 当前不足

| 问题 | 现状 | 风险 |
|---|---|---|
| 任务前交互过薄 | 只有 `goal + constraints` | 用户很难提供完整意图 |
| 自然语言解析过宽 | 主要是 regex + keyword 抽取 | 容易误判或漏掉关键意图 |
| 缺少槽位式确认 | 没有任务创建向导 | 复杂任务输入成本高 |
| 缺少结构化摘要确认 | 用户不能在规划前看到“系统理解了什么” | 规划偏离意图难以及时纠正 |
| 决策类型过少 | 运行中更多是 `accept/replan/cancel` | 缺少 edit 语义 |
| 缺少预算与工具偏好控制 | 入口没有成本/可信度/本地远程偏好显式表达 | Planner 只能靠隐式猜测 |

## 6.2 完整实现目标

完整实现的交互应采用“双层交互”：

1. 规划前的意图收集与约束确认。
2. 运行中的候选决策与恢复确认。

其中，规划前交互不应直接进入现有 FSM；否则会破坏现有生命周期不变量。

建议把规划前交互放到“任务创建前的 preflight intent drafting”阶段。

## 6.3 完整交互形态

建议形成五段式交互：

### 阶段 A：任务入口

用户输入：

- 自然语言目标
- 可选模板类型
- 运行预算
- 本地/远程偏好

系统输出：

- `IntentDraft`

### 阶段 B：槽位确认

系统把 `IntentDraft` 渲染成明确槽位：

- 任务类型
- 目标属性
- 长度范围
- 是否有模板结构
- 是否必须 novelty 检查
- 是否必须结构/QC gate
- 预算模式
- 可接受工具范围

用户可以：

- 选择
- 修改
- 跳过

### 阶段 C：任务摘要确认

系统输出：

- 结构化摘要
- 缺失约束列表
- 可能的高风险歧义点

用户确认后，系统才真正创建 TaskRecord 并进入 `CREATED -> PLANNING`。

### 阶段 D：计划候选确认

沿用现有 `WAITING_PLAN_CONFIRM`，但将决策扩展为：

- `approve`
- `edit`
- `reject`

其中 `edit` 不改变 FSM，只表示用户修改结构化约束后重新规划。

### 阶段 E：运行中恢复决策

沿用现有 `patch_confirm / replan_confirm`，同时增强：

- 显示建议动作与原因
- 显示 runtime_state 摘要
- 支持“接受建议但修改部分参数”

## 6.4 为什么不能继续依赖纯自然语言解析

原因不是“自然语言不好”，而是：

- 当前系统是高成本、多工具、多约束工作流。
- 错误理解的代价远高于一次多选题。
- 许多约束天然适合显式槽位表达。

根据外部参考，正确做法不是完全放弃自然语言，而是：

- 用自然语言做初始输入。
- 用澄清问题和结构化槽位来补全意图。
- 用摘要卡片让用户确认系统理解结果。

这比“直接让模型猜完”稳定得多。

## 6.5 建议新增的数据结构

### 6.5.1 IntentDraft

在 Task 创建前增加草案对象：

```json
{
  "draft_id": "draft_xxx",
  "goal_raw": "design a soluble enzyme around 120 aa",
  "slots": {
    "task_type": {"value": "de_novo_design", "confidence": 0.82},
    "target_properties": {"value": ["solubility"], "confidence": 0.71},
    "length_range": {"value": [100, 140], "confidence": 0.93},
    "template_mode": {"value": "none", "confidence": 0.61},
    "tool_preference": {"value": "balanced", "confidence": 0.55}
  },
  "missing_slots": ["budget_mode"],
  "ambiguities": ["target_properties", "template_mode"]
}
```

### 6.5.2 ClarificationCard

```json
{
  "card_id": "clarify_xxx",
  "draft_id": "draft_xxx",
  "slot_name": "budget_mode",
  "question": "本次任务更偏向哪种执行策略？",
  "choices": [
    {"id": "fast", "label": "快速探索"},
    {"id": "balanced", "label": "平衡"},
    {"id": "high_quality", "label": "高质量优先"}
  ],
  "allow_skip": true
}
```

### 6.5.3 TaskSummaryCard

```json
{
  "draft_id": "draft_xxx",
  "summary": {
    "task_type": "de_novo_design",
    "target_properties": ["solubility"],
    "length_range": [100, 140],
    "budget_mode": "balanced",
    "tool_preference": "balanced"
  },
  "ready_to_plan": true
}
```

## 6.6 API 设计建议

建议新增 preflight API，而不是直接修改 `/tasks` 语义：

| 接口 | 作用 |
|---|---|
| `POST /intent-drafts` | 从自然语言创建意图草案 |
| `GET /intent-drafts/{id}` | 查询草案 |
| `POST /intent-drafts/{id}/clarifications` | 提交槽位确认 |
| `POST /intent-drafts/{id}/finalize` | 生成正式 `ProteinDesignTask` 并创建 Task |

现有：

- `POST /tasks`

可保留为高级/批量调用入口，供脚本直接传结构化约束。

## 6.7 UI 设计建议

建议把 UI 分成三个页面或三个大 panel：

1. `Task Builder`
2. `Plan Review`
3. `Execution Review`

### Task Builder

组件建议：

- Goal 输入框
- 结构化槽位表单
- 约束摘要卡片
- “系统理解如下”对照块

### Plan Review

组件建议：

- Top-K candidate compare
- 默认推荐原因
- 工具可用性与 fallback 信息
- `approve / edit / reject`

### Execution Review

组件建议：

- 当前 runtime_state 摘要
- 失败上下文
- patch / replan / stop 建议
- 参数编辑入口

## 6.8 澄清策略设计

应采用“少而准”的澄清策略：

- 只对高影响、低置信度槽位发问。
- 优先单选/多选，少用开放文本。
- 问题必须具体，不问泛泛问题。
- 对明确可跳过的问题允许跳过。

建议建立触发规则：

| 条件 | 动作 |
|---|---|
| 槽位缺失且为高影响 | 必问 |
| 槽位存在但置信度低于阈值 | 追问 |
| 用户已显式给出结构化值 | 不再追问 |
| 仅影响说明文本、不影响规划 | 可不问 |

高影响槽位优先级：

1. `task_type`
2. `length_range`
3. `template_mode`
4. `budget_mode`
5. `tool_preference`
6. `target_properties`

## 6.9 运行中决策模型建议

对于运行中 HITL，建议从：

- `accept / replan / cancel`

升级为：

- `approve`
- `edit`
- `reject`

映射语义：

| UI 决策 | 系统语义 |
|---|---|
| `approve` | 接受当前候选 |
| `edit` | 修改候选参数或约束后再执行 |
| `reject` | 拒绝当前候选，转下一个候选或触发上游重选 |

注意：

- 这不要求新增 FSM 状态。
- `edit` 可以作为现有 `Decision` 的扩展字段，在应用层解释。

## 6.10 交互设计实施顺序

1. 增加 `IntentDraft` 与 preflight API
2. 增加 Task Builder UI
3. 扩展 `Decision` 为 `approve / edit / reject`
4. 在 PendingAction 展示中补 runtime_state 摘要
5. 把计划前和运行中的摘要卡片统一到同一视觉系统

## 6.11 交互设计验收标准

- 用户可以不写 JSON 也能完成复杂任务创建。
- 模糊输入会被转化为显式槽位确认，而不是直接开跑。
- 任务创建前能看到系统理解的结构化摘要。
- 运行中决策支持 edit，而不只是 accept/reject。
- 不引入新的运行态 FSM 状态。

## 7. 对比三：核心算法完整实现

## 7.1 当前实现与设计的差距

### 当前已经具备

- 候选生成与 Top-K 输出。
- 静态评分与 score_breakdown。
- Lite belief-state 的五个核心变量。
- runtime rerank。
- 动作选择器。
- terminal stop。
- 事件审计与 snapshot 恢复。

### 当前不足

| 问题 | 现状 | 风险 |
|---|---|---|
| 候选生成仍偏静态 | 主要从工具替换与预设链生成 | 候选空间不足 |
| belief-state 仍是 v1 规则更新 | 主要靠手工启发式增减 | 难与设计 formalization 完全对齐 |
| utility 分解未独立成统一 schema 层 | score / action / rerank 分散在 Planner 与 recovery 中 | 可解释性与演化性受限 |
| 目标评分工具未闭环 | objective_scoring 缺真实执行器 | 算法难以利用丰富后验信号 |
| 动态控制仍主要依赖局部恢复 | 缺少显式多阶段候选生成与裁剪策略 | 更复杂任务中性能可能不稳 |
| 缺少系统化比较模式 | static / dynamic no-state / lite-state / future learned policy 尚未统一封装 | 实验与迭代难比较 |

## 7.2 完整实现目标

完整实现的核心算法应当被视为“三层控制结构”：

### 层 1：候选工具链生成层

作用：

- 针对任务和当前上下文生成可执行候选集合 `Pi_t`

输入：

- `g`
- `c`
- `K`
- 已完成前缀
- 可用工具矩阵

输出：

- `PlanCandidate`
- `PatchCandidate`
- `ReplanCandidate`

### 层 2：运行时评估层

作用：

- 基于静态评分、运行时状态和后验证据对候选进行重排序与裁剪

输入：

- `score_breakdown`
- `RuntimeState`
- `Action-Utility Schema`

输出：

- `final_score`
- `shadow_action`
- `rerank_reason`

### 层 3：动作选择与恢复层

作用：

- 在当前执行点选择 `continue / patch_local / suffix_replan / stop`

输入：

- `RuntimeState`
- failure context
- stage context
- candidate utility
- safety signal

输出：

- workflow action
- mapped recovery flow
- HITL candidate set

## 7.3 完整实现的核心设计

## 7.3.1 候选生成层

建议从“单一候选再替换”升级为“阶段感知的候选生成器”：

| 场景 | 生成策略 |
|---|---|
| 初始规划 | 按 capability bucket 生成多条可执行链 |
| patch | 在参数级、工具级、结构级分别生成候选 |
| replan | 优先生成 suffix replan，再考虑 terminal stop |

候选生成必须显式考虑：

- 工具可用性
- 输入输出闭包
- 前缀可保留性
- 预算模式
- 工具可信度与 fallback 深度

建议新增独立模块：

- `src/agents/candidate_generator.py`

职责：

- 输入上下文，输出标准化候选 payload 列表。

Planner 本身更专注于：

- 路由
- 评分
- gate
- HITL 组织

## 7.3.2 六类 Schema 固化

完整实现需要把设计里的六类 schema 从“文档概念”变成代码契约：

1. `Cost Schema`
2. `Risk Schema`
3. `Recovery Schema`
4. `State Schema`
5. `Observation Schema`
6. `Action-Utility Schema`

建议新增：

- `src/models/runtime_schemas.py`

其中至少定义：

- `CostProfile`
- `RiskProfile`
- `RecoveryProfile`
- `RuntimeObservation`
- `RuntimeStateSummary`
- `ActionUtility`

收益：

- belief-state、rerank、action selector 使用同一组字段。
- 日志和实验脚本可以直接消费。
- 不再需要多个文件重复解释同一组意义。

## 7.3.3 belief-state v2

当前 v1 已可运行，但完整实现建议升级为 v2：

保留主状态：

- `p_success`
- `p_structural_failure`
- `recovery_margin`
- `expected_remaining_cost`
- `evidence_sufficiency`

新增要求：

- 每个状态量必须有：
  - `value`
  - `source_fields`
  - `last_update_reason`
- 每次更新必须形成可审计 delta，而不是只写最终值。

建议新增：

```json
{
  "p_success": {
    "value": 0.42,
    "delta": -0.11,
    "reason": "S2 failed with retry_exhausted",
    "source_fields": ["step_result.status", "retry_exhausted"]
  }
}
```

这能显著改善论文中的可解释性和案例分析能力。

## 7.3.4 统一 Action Utility

当前 rerank 与 action selection 分别有一套启发式。
完整实现建议将动作评估统一为显式 utility：

```text
U_continue
U_patch_local
U_suffix_replan
U_stop
```

每个 utility 由固定字段组成：

- feasibility contribution
- goal fit contribution
- cost penalty
- risk penalty
- recovery complexity penalty
- human intervention cost penalty

然后再经过：

- 硬约束覆盖
- tie-break
- HITL policy

最终选出动作。

收益：

- 运行时重排序与动作选择共享底层特征。
- 实验可以直接比较 action-level utility。
- 未来接入学习型策略时可保留同一接口。

## 7.3.5 runtime rerank 与 action selector 解耦

完整实现时应明确：

- rerank 负责“候选值不值得继续”
- action selector 负责“系统下一步做什么”

两者共享状态，但不互相覆盖职责。

推荐流程：

1. 生成候选
2. 静态评分
3. 运行时重排序
4. 候选裁剪
5. 计算动作 utility
6. 选动作
7. 进入既有恢复/HITL 流程

## 7.3.6 引入模式化基线

完整实现必须把算法模式显式化，便于实验比较。

建议任务级模式：

- `policy_mode = static_top1`
- `policy_mode = static_gate`
- `policy_mode = dynamic_observation_only`
- `policy_mode = lite_belief_state`
- `policy_mode = learned_policy`（预留）

这样：

- Planner 与 Workflow 可共用同一框架。
- 只切换状态估计与动作选择层。
- 实验更容易横向对比。

## 7.3.7 objective scoring 真正进入后验链

完整实现中，`objective_ranker` 不应只影响 Planner 静态候选，而应成为运行后验评估的一部分：

- S2 后可做结构后验评分
- S3 后可做 QC 后验评分
- similarity / secondary structure / docking 等结果进入目标评分
- 最终 report 使用真实后验综合分，而不是只复用静态 score_breakdown

## 7.4 完整实现的推荐代码重构

建议新增或整理为：

| 模块 | 作用 |
|---|---|
| `src/models/runtime_schemas.py` | 六类 schema 与 utility 契约 |
| `src/agents/candidate_generator.py` | 统一候选生成 |
| `src/workflow/runtime_evaluator.py` | runtime rerank 与 utility 计算 |
| `src/tools/objective_ranker/adapter.py` | 真实 objective scoring 工具 |
| `src/api/intent_preflight.py` | preflight intent draft API |

现有模块职责调整：

- `planner.py` 保留 orchestrator 角色
- `recovery.py` 保留动作映射与恢复闭环角色
- `belief_state.py` 升级为纯状态更新器
- `patch_runner.py` 与 `plan_runner.py` 只消费统一动作接口，不再承载过多评分逻辑

## 7.5 完整实现的实施顺序

### 阶段 A：把 v1 机制补齐为可比较版本

- 固化 `policy_mode`
- 补 `objective_ranker`
- 补 readiness matrix
- 补 preflight intent draft

### 阶段 B：把状态、评分、动作三层拆清

- 抽 `candidate_generator`
- 抽 `runtime_evaluator`
- 固化六类 schema

### 阶段 C：把后验信号接全

- 接入结构相似性
- 接入 objective ranking
- 接入功能/稳定性评分

### 阶段 D：把实验体系做成长期资产

- 四组 policy baseline 固化
- action utility 指标固化
- evidence index 与案例模板固化

## 7.6 核心算法验收标准

- `policy_mode` 可切换且行为稳定。
- `RuntimeState`、`ActionUtility`、`RuntimeObservation` 有稳定契约。
- rerank 与 action selector 共用统一底层特征。
- `objective_ranker` 进入真实执行链。
- `stop`、`suffix_replan`、`patch_local` 都有可审计证据。
- 实验可稳定比较：
  - 静态基线
  - 动态无显式状态基线
  - Lite belief-state

## 8. 统一落地路线图

## 8.1 第一阶段：补齐完整实现前的硬缺口

- 补 `objective_ranker`
- 补 capability readiness matrix
- 禁止实验模式静默 demo fallback
- 增加 `IntentDraft` 与 preflight API

## 8.2 第二阶段：完成交互前置层

- Task Builder UI
- 槽位确认
- 结构化摘要确认
- `Decision` 扩展为 `approve / edit / reject`

## 8.3 第三阶段：完成算法完整化

- 六类 schema 代码化
- `candidate_generator` 抽离
- `runtime_evaluator` 抽离
- action utility 统一化

## 8.4 第四阶段：补强工具生态

- `foldseek`
- objective / stability / function 工具
- 多目标后验评分

## 9. 最终判断

### 工具接入

当前不是“未实现”，而是“最小可运行闭环已实现，完整工具平台未实现”。

### 交互设计

当前不是“没有交互”，而是“运行中交互已实现，规划前交互未实现”。

### 核心算法

当前不是“没有算法”，而是“Lite v1 已实现，完整算法平台未实现”。

## 10. 建议作为后续默认原则

后续所有实现都应遵循以下默认原则：

1. 优先补齐缺失能力，不优先堆叠更多局部 patch。
2. 规划前澄清与运行中 HITL 分层处理。
3. 不为新交互破坏既有 FSM。
4. 不为新算法重写整个 Workflow。
5. 先把 schema、评估和证据链做稳定，再追求复杂策略。
6. 所有新增工具都必须同时补：
   - KG
   - adapter
   - health/readiness
   - tests
   - event fields
7. 所有新增算法层都必须同时补：
   - contract
   - snapshot
   - event log
   - baseline comparison

## 11. 推荐后续 issue 方向

建议后续按三条主线持续推进：

### 工具主线

- `objective_ranker` 实现
- capability readiness matrix
- structure similarity tool
- objective/function/stability 工具扩展

### 交互主线

- intent draft API
- task builder UI
- clarification card system
- decision edit path

### 算法主线

- runtime schemas 代码化
- candidate generator 抽离
- runtime evaluator 抽离
- policy mode 基线固化

## 12. 本文档的使用方式

本文件应当被用作：

- 后续 issue 拆分依据
- PR 设计说明依据
- 论文“系统限制与后续工作”章节依据
- 代码评审时判断“这是补缺口还是绕开问题”的依据

如果未来代码继续演化，本文件应优先更新以下内容：

- 当前工具清单与 readiness 状态
- 当前交互形态
- 当前 policy mode 与实验基线
- 已实现/未实现判断

