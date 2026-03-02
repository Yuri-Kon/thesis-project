---
doc_key: algo
version: 1.0
status: stable
depends_on: [arch, agent]
---

# core-algorithm-spec

> 版本：v0.3（与 Step1/Step2 对齐）
> 目的：给出**可直接据此编码**的核心算法与输出契约（Plan / Patch / Replan 候选、排序、选择与固化）。
> 说明：本文档属于"算法与决策逻辑规范"，不包含具体 API/FSM/存储实现细节（见 system-implementation-design.md）。

---

## 1. 范围与非目标
<!-- SID:algo.scope.overview -->

### 1.1 本文档覆盖的内容

- PlannerAgent 的核心算法流程与输出对象：
  - 初始 Plan 生成（Planning）
  - Patch 生成（Patching）
  - Replan 生成（Replanning）
- 候选（Candidate）生成、排序、裁剪（Top-K）与解释信息生成
- 与 Human-in-the-loop 的集成点：
  - 何时输出候选并生成 PendingAction
  - 如何应用 Decision 固化最终方案
- 必须遵守的稳定性与一致性约束（可用于测试验收）

### 1.2 本文档不覆盖的内容

- FSM 状态机与挂起/恢复（见 architecture.md / system-implementation-design.md）
- PendingAction / Decision / Snapshot / EventLog 的数据结构字段（见 system-implementation-design.md）
- 工具执行、重试策略、异步调度与后端（ExecutionBackend）（见 system-implementation-design.md）

---

## 2. 术语与对象定义
<!-- SID:algo.definitions.overview -->

### 2.1 主要对象

- Task：一次蛋白设计任务，包含用户 query、结构化 constraints、以及系统选项 options
- Tool：可调用的外部能力（ProteinMPNN / ESMFold / RDKit / …），由 ToolKG 提供能力描述
- Plan：可执行计划，由若干 PlanStep 组成（带依赖关系、输入输出约束、参数）
- PlanStep：单步工具调用（tool_id + inputs + params + expected_outputs + validation）
- Patch：对既有 Plan 的局部修补（PlanPatch），通常针对某一步或某一小段步骤的替换/参数调整
- Replan：对整体策略的重规划，可能表现为“替换 Plan 后缀”或“重新生成新的 Plan”

### 2.2 关键概念：Candidate（候选）
<!-- SID:planner.contracts.candidate_schema BEGIN -->

为了支持 Human-in-the-loop，本规范要求 Planner 在关键节点输出候选集合（Top-K）：

- PlanCandidate：初始 Plan 候选 <!-- SID:planner.contracts.plan_candidate -->
- PatchCandidate：PlanPatch 候选 <!-- SID:planner.contracts.patch_candidate -->
- ReplanCandidate：Replan（Plan 后缀或整体 Plan）候选 <!-- SID:planner.contracts.replan_candidate -->

Candidate 必须包含：
- candidate_id（稳定可引用）
- summary（可读摘要）
- structured_payload（对应 Plan/PlanPatch/Replan 的结构化内容或可解析引用）
- score_breakdown（排序依据）
- risk_level（低/中/高）
- cost_estimate（低/中/高 或数值区间）
- explanation（用于人类审查的理由，允许由 LLM 生成但必须可追溯）
<!-- SID:planner.contracts.candidate_schema END -->

---

## 3. 输入、约束与输出契约
<!-- SID:planner.contracts.io_overview -->

### 3.1 Planner 输入

Planner 接收的输入至少包括：

- query：自然语言任务描述
- constraints：结构化约束（可能为空）
  - 目标长度、motif、结构/功能约束、禁止项、预算、工具白名单/黑名单等
- context（可选）：执行上下文（用于 patch/replan）
  - current_plan（已固化 Plan）
  - current_step_index（已完成步骤）
  - step_results（已执行结果摘要）
  - safety_events（风险事件摘要）
  - failure_context（失败原因/重试信息）

### 3.2 Planner 输出（统一抽象）

Planner 的输出分两层：

- 自动执行路径（默认）：
  - 直接输出“选中的方案”（Plan / PlanPatch / Replan）并进入后续执行
- HITL 路径：
  - 输出候选集合（Top-K candidates）
  - 由系统包装为 PendingAction，等待人类 Decision
  - Decision 生效后固化为最终方案

因此，Planner 必须支持两类输出形态：

A) SelectedOutput（自动路径）
- selected_id
- selected_payload（Plan / PlanPatch / Replan）
- explanation

B) CandidateSetOutput（HITL 路径）
- candidates（Top-K）
- default_suggestion（candidate_id）
- explanation（对候选集的总体解释）

### 3.3 约束检查与可执行性保证

任一 Plan/PlanPatch/Replan 的 structured_payload 必须满足：

- 工具可用性：所引用 tool_id 必须存在于 ToolKG 或系统注册表
- 输入输出闭包：每个 PlanStep 的输入必须来源于：
  - Task 输入（用户提供的初始输入）
  - 上游步骤输出（通过 artifact 引用）
- 参数合法性：params 必须可被对应 ToolAdapter/Backend 接受（类型、范围、必填项）
- 失败容忍：若某工具不稳定，需在 step.validation 中写明可接受的退化策略（例如允许 fallback）

---

## 4. 核心算法总览

Planner 的核心算法由三个模式构成：

1) Initial Planning：从零生成 Plan（无执行上下文或上下文不足）
2) Patch Planning：针对局部失败生成 PlanPatch（上下文明确，目标是最小代价修复）
3) Replanning：针对整体风险/偏移生成 Replan（目标是改变策略或替换后缀）

三者共享以下通用流程：

- Tool Retrieval：从 ToolKG 检索候选工具集合（能力匹配、输入输出适配）
- Candidate Generation：生成若干结构化候选（Plan/PlanPatch/Replan）
- Candidate Scoring：对候选进行多目标打分
- Candidate Selection：自动选最优，或输出 Top-K 供 HITL 决策
- Explainability：输出可解释的摘要与理由（用于审查与审计）

---

## 5. Tool Retrieval（工具检索与约束过滤）
<!-- SID:planner.algorithm.tool_retrieval -->

### 5.1 检索目标

给定 query + constraints，检索工具集合 ToolSet，使其满足：

- 能覆盖任务目标所需的关键能力（设计、评估、过滤、可视化等）
- 工具输入输出能形成闭合链路（可组成可执行计划）
- 满足 constraints 中的工具治理策略：
  - allowed_tools / blocked_tools
  - 风险等级阈值（高风险工具需要人工确认）
  - 成本上限（例如 GPU-heavy 工具）

### 5.2 过滤与排序规则

对工具进行过滤（硬约束）：
- 不在白名单（如指定 allowed_tools）则剔除
- 在黑名单则剔除
- 输入输出不满足最基本适配则剔除

对工具进行排序（软约束），推荐排序信号：
- capability_match_score：能力匹配度
- io_compatibility_score：输入输出适配度
- historical_reliability：历史成功率/稳定性（若有）
- estimated_cost：预估时间/资源消耗
- risk_level：风险等级

输出：
- ToolSet（用于 Candidate Generation 的工具池）

---

## 6. Candidate Generation（候选生成）

### 6.1 初始 Plan 候选生成（PlanCandidate）

目标：生成至少 1 个可执行 Plan；在需要 HITL 时生成 Top-K（建议 K=3）。

生成策略（允许组合）：
- Template-based：使用预定义工具链模板（例如 “MPNN → Fold → Score → Filter”）
- Graph Search：在工具依赖图上进行路径搜索，保证输入输出闭包
- LLM-guided Assembly：由模型提出步骤序列，随后用规则校验并修正

每个候选 PlanCandidate 必须包含：
- candidate_id：稳定 ID（建议基于内容哈希 + 序号）
- summary：包含步骤数、工具链、关键参数
- structured_payload：完整 Plan（可序列化）
- score_breakdown：见 7.2
- risk_level / cost_estimate：见 7.3
- explanation：包含“为何选这些工具”“为何这样排序步骤”的理由

### 6.2 Patch 候选生成（PatchCandidate）

输入：current_plan + failure_context（失败步骤、错误类型、重试次数、关键日志摘要）

Patch 的目标是“最小代价恢复执行”，优先级：
1) 参数级修补（调参、重跑、改变采样策略）
2) 工具级替换（同能力低成本工具替代）
3) 结构级调整（增加验证/过滤步骤，避免连锁失败）

PatchCandidate 的 structured_payload 为 PlanPatch，必须明确：
- patch_target：针对哪一步（step_id）或步骤区间
- patch_type：param_update / tool_swap / step_insert / step_remove / step_replace
- patch_ops：具体操作（参数差异、替换工具、插入步骤内容）
- post_patch_validation：应用后应检查的条件

### 6.3 Replan 候选生成（ReplanCandidate）

触发原因一般为：
- SafetyAgent 给出 block 或高置信 warn
- 执行结果偏离目标（指标不达标、结构不稳定）
- Patch 多次失败或被拒绝

Replan 的目标是“改变策略”，常见形式：
- suffix_replan：保留已成功的前缀步骤，替换后缀步骤（推荐默认）
- full_replan：重新生成完整 Plan（在前缀也不可信时）

ReplanCandidate 必须明确：
- replan_mode：suffix_replan / full_replan
- preserve_prefix_until_step_index（若为 suffix_replan）
- structured_payload：新的 Plan 或新的后缀定义
- risk_level / cost_estimate / explanation

---

## 7. Candidate Scoring（候选打分、风险与成本估计）
<!-- SID:planner.algorithm.candidate_scoring -->

### 7.1 多目标打分总体原则

Candidate 的排序为多目标优化（非严格单一目标），推荐使用线性加权或分层排序：

- feasibility_score（可执行性）：硬约束是否满足，若不满足直接淘汰
- objective_score（目标达成）：与设计目标的贴合程度
- risk_penalty（风险惩罚）：高风险扣分
- cost_penalty（成本惩罚）：高成本扣分
- recovery_penalty（恢复代价惩罚）：预计需要更多 patch/replan 的候选扣分
- stability_bonus（稳定性加成）：工具稳定、历史成功率高则加分

### 7.2 score_breakdown 必须包含的字段

每个 Candidate 至少输出：

- feasibility: 0/1（或 0~1），不可执行则=0并淘汰
- objective: 0~1
- risk: 0~1（越高越危险）
- cost: 0~1（越高越昂贵）
- recovery_complexity: 0~1（可选，越高表示后续修复复杂度越大）
- overall: 0~1（最终排序用）

同时输出可读解释：
- 为什么 objective 高/低
- 风险来自哪里（工具/参数/伦理/不确定性）
- 成本估计来自哪里（GPU、时长、外部服务）

### 7.3 风险等级与成本等级映射（必须可复现）

risk_level 映射规则（示例，可按你系统策略调整，但必须固定）：

- risk < 0.33 → low
- 0.33 ≤ risk < 0.66 → medium
- risk ≥ 0.66 → high

cost_estimate 映射规则：
- cost < 0.33 → low
- 0.33 ≤ cost < 0.66 → medium
- cost ≥ 0.66 → high

这些阈值必须在实现中作为常量或配置项存在，确保审计一致性。

---

## 8. Candidate Selection（自动选择 vs HITL 输出）
<!-- SID:planner.algorithm.hitl_gate -->

### 8.1 决策门控（何时进入 HITL）

Planner 在完成候选生成与排序后，需要通过“门控规则”决定：

- 自动路径：输出 SelectedOutput
- HITL 路径：输出 CandidateSetOutput（Top-K + 默认建议）

门控规则必须至少支持以下触发条件（任意满足即进入 HITL）：

1) 系统配置：require_plan_confirm / require_patch_confirm / require_replan_confirm
2) 风险阈值：best_candidate.risk_level == high 或 risk ≥ risk_threshold
3) 成本阈值：best_candidate.cost_estimate == high 或 cost ≥ cost_threshold
4) Safety 强约束：SafetyAgent 返回 block（此时必须 HITL 或直接失败/取消，策略由 system-implementation-design.md 定义）

### 8.2 Top-K 输出规范

- 默认 K=3（可配置）
- 候选必须按 overall 从高到低排序
- 必须提供 default_suggestion（默认建议的 candidate_id）
- 必须提供 explanation（对整个候选集的解释摘要）

---

## 9. Decision 应用与方案固化（HITL 路径）
<!-- SID:planner.algorithm.decision_application -->

Planner 不直接等待 Decision，但必须定义“Decision 应用后如何固化”的纯函数逻辑（可测试）。

### 9.1 plan_confirm 的 Decision 应用

输入：
- candidates（PlanCandidate 集合）
- decision.choice
- decision.selected_candidate_id（当 choice=accept 时必须存在）

规则：
- accept：选择 candidate_id 对应的 Plan，固化为 current_plan（写版本号）
- replan：回到 Planning（由系统触发新的 planning 回合）
- cancel：任务终止（由系统处理）

输出：
- selected_plan（当 accept）
- 或 replan_requested 标记（当 replan）

### 9.2 patch_confirm 的 Decision 应用

输入：
- current_plan
- patch_candidates（PatchCandidate 集合）
- decision

规则：
- accept：应用 PlanPatch，生成新 plan_version，并输出 updated_plan
- replan：升级为 Replan 流程（由系统进入 replan_confirm 或直接 planning，取决于实现策略）
- cancel：任务终止

注意：
- Patch 应用必须是可回滚的纯操作（在内存/临时副本上应用，验证通过后再固化）
- Patch 应用后必须更新“后续步骤的输入引用”（artifact mapping）保持闭包

### 9.3 replan_confirm 的 Decision 应用

输入：
- replan_candidates
- decision

规则：
- accept：采用选中的 ReplanCandidate：
  - 若 mode=suffix_replan：保留 prefix，替换后缀，输出新 plan_version
  - 若 mode=full_replan：输出全新 Plan
- continue：继续原计划执行（不修改 Plan）
- cancel：任务终止

---

## 10. Patch/Replan 的可复现性与稳定性约束（验收标准）

以下规则必须可用单元测试验证：

1) Candidate 可执行性：任何被输出为候选（Top-K）都必须通过结构校验（输入输出闭包、参数合法）
2) Candidate ID 稳定性：同一输入上下文下重复生成候选，candidate_id 的生成策略必须可复现（允许顺序不同但需可解释）
3) Decision 幂等性：同一 Decision 重复应用不得产生不同结果（若已应用应被上层拒绝，或结果一致）
4) Patch 最小性：PatchCandidate 的 patch_ops 应优先局部修改，避免无必要的全局替换（作为排序加成项）
5) Replan 保前缀（若 suffix_replan）：必须保证 preserve_prefix 的步骤不被隐式修改
6) 风险与成本阈值：门控阈值必须固定可追溯（来自配置或常量），并写入解释信息

---

## 11. 参考伪代码

### 11.1 初始 Planning（生成 PlanCandidate 集合并选择）

```python
    function plan(task):
        tools = retrieve_tools(task.query, task.constraints)
        candidates = generate_plan_candidates(task, tools)    # list[PlanCandidate]
        candidates = filter_infeasible(candidates)
        candidates = score_and_sort(candidates)

        if should_enter_hitl(task.options, candidates[0]):
            return CandidateSetOutput(
                candidates=top_k(candidates, K),
                default_suggestion=candidates[0].candidate_id,
                explanation=explain_candidates(candidates)
            )
        else:
            return SelectedOutput(
                selected_id=candidates[0].candidate_id,
                selected_payload=candidates[0].structured_payload,
                explanation=candidates[0].explanation
      )
```

### 11.2 Patch（生成 PatchCandidate 集合并选择/输出）

```python
    function patch(current_plan, failure_context, task_options):
        patch_candidates = generate_patch_candidates(current_plan, failure_context)
        patch_candidates = filter_infeasible(patch_candidates)
        patch_candidates = score_and_sort(patch_candidates)

        if should_enter_hitl(task_options, patch_candidates[0]):
            return CandidateSetOutput(top_k, default_suggestion, explanation)
        else:
            return SelectedOutput(selected_patch)

### 11.3 Replan（suffix_replan 优先）

    function replan(current_plan, context, task_options):
        replan_candidates = generate_replan_candidates(current_plan, context)
        replan_candidates = filter_infeasible(replan_candidates)
        replan_candidates = score_and_sort(replan_candidates)

        if should_enter_hitl(task_options, replan_candidates[0]):
            return CandidateSetOutput(top_k, default_suggestion, explanation)
        else:
            return SelectedOutput(selected_replan)
```
---

## 12. 与 Step1/Step2 的一致性声明（必须）

- 本文档输出的 CandidateSetOutput 将由系统包装为 PendingAction：
  - plan_confirm → WAITING_PLAN_CONFIRM
  - patch_confirm → WAITING_PATCH_CONFIRM（实现层 WAITING_PATCH / PATCHING）
  - replan_confirm → WAITING_REPLAN_CONFIRM（实现层 WAITING_REPLAN / REPLANNING）
- PlannerAgent 行为边界遵循 agent-design.md：
  - Planner 负责生成候选与建议，不负责等待与选择
- Decision 的合法性、冲突处理、事件日志与快照写入约束遵循 system-implementation-design.md：
  - DECISION_SUBMITTED / DECISION_APPLIED
  - PENDING_ACTION_CREATED
  - 必须写 TaskSnapshot 的关键节点

---

## 13. 变更点（相对 v0.2 的核心新增）

- 新增 Candidate（Top-K）输出规范与门控规则
- 新增 Decision 应用与固化规则（可测试的纯逻辑）
- 将 Patch/Replan 的“内部执行态”与“对外等待确认态”做清晰分离
- 强化风险/成本估计与解释输出，支撑人工审查与审计

---

## 14. 与 algorithm-and-llm 研究结论的对齐补充（实施优先级）

本节用于对齐 `docs/algorithm-and-llm/` 的核心结论，并给出落地优先级。

### 14.1 论文结论到系统模块映射

- Toolformer / ReAct：落实到 Candidate 生成与可解释输出（`summary/explanation/score_breakdown`）。
- Reflexion：落实到 `retry -> patch -> replan` 的失败修复闭环与 Patch 最小性约束。
- Multi-Agent Survey：落实到 Planner/Executor/Safety/Summarizer 的角色边界与协作协议。
- OSWorld：落实到执行导向评估，优先关注可执行成功率、恢复成功率与时延，而非仅文本质量。

### 14.2 工作包优先级（建议）

- P0：CandidateSet 能力落地（Top-K、稳定打分、风险/成本门控）。
- P1：Patch/Replan 分层策略（参数级、工具级、结构级）。
- P2：统一评估基准（离线/在线口径、对比基线、统计报表）。
- P3：审计闭环固化（`PendingAction -> Decision -> EventLog -> Snapshot` 对账）。

### 14.3 算法层统一验收指标（建议）

- Workflow schema 合法率
- 候选可执行率
- 首轮执行成功率
- 平均 patch 次数 / replan 次数
- 人工介入率与恢复成功率
- 端到端时延
- 决策可追溯完整率（决策链可回放）

### 14.4 边界重申

- 不允许绕过 FSM 的隐式状态跳转。
- 不允许 Planner 在 `WAITING_*` 阶段替代人工做最终决策。
- 不将“语言流畅”当作“可执行工作流质量”的替代指标。
