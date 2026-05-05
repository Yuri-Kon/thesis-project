# 核心算法文献映射：CEBRA-WP 的理论支撑与相关工作

- 生成日期：2026-05-05
- 对应计划项：D3 `core-algorithm-literature-map.md`
- 目标：为“面向高代价蛋白质设计工作流的约束化、证据感知、恢复感知自适应工具链规划算法（CEBRA-WP）”建立文献地图。
- 检索说明：Semantic Scholar 与 arXiv API 在本轮出现 429/timeout，因此优先使用 arXiv/Nature 页面直接核验代表性论文元数据；最终论文 BibTeX 仍建议在定稿前统一核对 DOI、会议/期刊版本和版本号。
- P2-3 补充：稳定的“理论对象 -> 文献 -> 代码落点 -> 正文状态”矩阵见
  `docs/algorithm-and-llm/theory-background-paper-code-map.md`。本文保留分组综述与写作建议，
  映射矩阵作为 issue、论文正文和实现审查的共同索引。

## 1. CEBRA-WP 需要支撑的理论命题

当前算法不是一个单纯的 LLM planner，也不是一个单纯的蛋白设计模型，而是处在以下交叉区域：

```text
high-cost scientific workflow planning
  + tool-using LLM agents
  + belief-state / partially observable decision making
  + budget/risk/recovery-aware control
  + protein design objective evaluation
```

因此文献需要支撑六个核心命题：

1. **部分可观测性**：高代价工作流的失败风险、后缀可行性、恢复价值不能完全由单步观测决定，需要状态估计。
2. **受约束决策**：候选工具链选择不是最大化单一分数，而是在成本、风险、安全、工具可用性、I/O 闭合等约束下优化。
3. **证据感知目标评分**：蛋白设计目标应基于 direct/proxy/degraded evidence，而不是裸模型输出。
4. **恢复感知控制**：失败后不是简单 retry，而是在 patch、suffix replan、stop 之间做控制动作选择。
5. **LLM 工具使用的可靠性问题**：LLM 生成工具调用天然存在 API 幻觉、参数错误、状态漂移，需要结构化工具元数据与可审计候选排序。
6. **蛋白设计链路的高代价性**：RFdiffusion、ProteinMPNN、AlphaFold/ESMFold/AlphaFold3 等模型构成的设计—预测—筛选链路需要多目标、多阶段过滤。

## 2. 文献分组总览

| 分组 | 用于支撑的算法组件 | 关键词 | 代表文献 |
|---|---|---|---|
| A. Belief-state / POMDP | Lite belief-state `x_t`；运行时状态更新 | POMDP, belief state, partially observable planning | Kaelbling et al. 1998; Smallwood & Sondik 1973; Cassandra 1998 |
| B. Constrained / Budgeted / Risk-sensitive MDP | hard feasibility、预算压力、风险惩罚、auto-stop | CMDP, budgeted MDP, risk-sensitive planning | Altman 1999; constrained MDP / budgeted planning literature |
| C. LLM tool-use agents | 候选工具链生成、API 选择、工具调用可靠性 | Toolformer, ReAct, Gorilla, Voyager, Reflexion, Tree of Thoughts | Schick et al. 2023; Yao et al. 2022/2023; Patil et al. 2023; Shinn et al. 2023; Wang et al. 2023 |
| D. Scientific workflow recovery | patch/replan/stop；provenance；失败恢复 | scientific workflow, provenance, failure recovery | Pegasus/Kepler/Taverna/VisTrails 等工作流系统文献 |
| E. Protein design foundation models | 工作流中高代价工具链的领域基础 | RFdiffusion, ProteinMPNN, AlphaFold, ESMFold, AlphaFold3 | Jumper et al. 2021; Lin et al. 2023; Watson et al. 2023; Dauparas et al. 2022; Abramson et al. 2024 |
| F. Multi-objective protein design / guidance | posterior objective scoring；多目标权衡 | multi-objective protein design, inverse folding, reward guidance | RosettaSearch 2026; ProteinGuide 2025; ProteinZero 2025; property-driven inverse folding 2026 |

## 3. A 组：Belief-state / POMDP

### 3.1 为什么相关

CEBRA-WP 的 `x_t` 不是普通日志摘要，而是对隐藏工作流状态的低维估计：

```text
x_t = (p_success, p_structural_failure, recovery_margin, expected_remaining_cost, evidence_sufficiency)
```

这对应 POMDP 中 belief state 的工程近似：系统不能直接观测“当前后缀是否结构性不可行”，只能从 `StepResult`、`SafetyResult`、失败上下文、预算消耗、证据充分度中更新判断。

### 3.2 可引用理论点

1. **Belief state 是部分可观测决策中的充分统计**：在 POMDP 中，历史观测可压缩为对隐藏状态的 belief distribution。
2. **CEBRA-WP 是 Lite belief surrogate**：当前实现不是完整 Bayesian posterior，而是低维、确定性、可审计的 belief 代理。
3. **bounded runtime correction**：运行时观测只对静态候选分数做有界修正，避免噪声观测导致剧烈决策振荡。

### 3.3 代表文献

| 文献 | 用法 |
|---|---|
| Smallwood & Sondik, 1973, The Optimal Control of Partially Observable Markov Processes | POMDP 早期理论根基：部分可观测控制问题 |
| Kaelbling, Littman & Cassandra, 1998, Planning and Acting in Partially Observable Stochastic Domains | POMDP/belief-state 经典综述，适合放理论背景 |
| Cassandra, Exact and Approximate Algorithms for Partially Observable Markov Decision Processes | 可作为 belief-state planning 的算法背景 |

### 3.4 映射到本文算法

```text
POMDP hidden state        -> workflow latent viability / failure mode / recovery potential
belief distribution       -> Lite belief-state vector x_t
observation o_t           -> StepResult, SafetyResult, objective evidence, failure context
belief update             -> update_runtime_state(...)
policy pi(b)              -> recovery-aware action selection
```

论文表述建议：

> Inspired by belief-state planning in POMDPs, we maintain a low-dimensional deterministic belief surrogate rather than a full posterior distribution, because scientific workflow execution provides sparse, heterogeneous, and expensive observations.

中文：

> 受 POMDP belief-state planning 启发，本文不维护完整后验分布，而维护一个低维确定性 belief 代理状态，以适配科研工作流中观测稀疏、异质且代价高的现实场景。

## 4. B 组：Constrained / Budgeted / Risk-sensitive decision making

### 4.1 为什么相关

CEBRA-WP 的核心不是“选择得分最高工具”，而是在以下约束下做选择：

- 工具是否可用；
- I/O 是否闭合；
- 安全级别是否允许；
- 预算压力是否过高；
- 风险是否可接受；
- 是否具备恢复余量；
- stop 是否需要 HITL。

这对应 constrained MDP / budgeted MDP / risk-sensitive planning 的问题结构。

### 4.2 可引用理论点

1. **硬约束与软目标分离**：先用 `F_h` 淘汰不可执行候选，再在可行集合上优化效用。
2. **预算是状态变量，不只是惩罚项**：`expected_remaining_cost` 与 `budget_pressure` 影响 continue/patch/replan/stop。
3. **风险敏感决策**：`p_structural_failure` 和 safety block 不是简单负分，而是可触发硬优先级。

### 4.3 代表文献

| 文献 | 用法 |
|---|---|
| Altman, 1999, Constrained Markov Decision Processes | CMDP 理论根基：约束下的序贯决策 |
| Budgeted MDP / Resource-constrained planning literature | 支撑 `expected_remaining_cost`、`budget_pressure` 与 stop gate |
| Risk-sensitive MDP literature | 支撑对结构性失败风险和安全 block 的非线性处理 |

### 4.4 映射到本文算法

```text
Hard constraints F_h      -> candidate filters: tool availability, I/O closure, safety, blocked tools
Budget state              -> expected_remaining_cost, budget_pressure
Risk state                -> p_structural_failure, safety_result
Recovery resource         -> recovery_margin, retry budget, prefix preservability
Terminal action           -> stop / terminal_stop candidate
```

论文公式建议：

```text
Pi_t = { pi in Pi_raw | F_h(pi,C,K,h_t)=1 }

pi_t^* = argmax_{pi in Pi_t} U_pi(pi,x_t)
subject to budget(pi,h_t) <= B_t and safety(pi,C) = true
```

## 5. C 组：LLM tool-use agents

### 5.1 已核验代表论文

#### Toolformer

- arXiv: `2302.04761`
- 标题：*Toolformer: Language Models Can Teach Themselves to Use Tools*
- 作者：Timo Schick 等
- arXiv 页面显示提交时间：2023-02-09
- 相关性：语言模型学习何时调用 API、传什么参数、如何整合工具结果。

映射到 CEBRA-WP：

```text
Toolformer API calling -> tool invocation ability
CEBRA-WP               -> workflow-level candidate generation + constraints + recovery
```

差异：Toolformer 关注模型学会调用工具；CEBRA-WP 关注高代价科研工具链的候选选择、证据评估和恢复控制。

#### ReAct

- arXiv: `2210.03629`
- 标题：*ReAct: Synergizing Reasoning and Acting in Language Models*
- 作者：Shunyu Yao 等
- arXiv 页面显示：v1 提交于 2022-10-06，v3 为 ICLR camera ready version
- 摘要要点：交错生成 reasoning traces 和 task-specific actions；通过外部 API/环境获得信息；改善可解释性和错误传播。

映射到 CEBRA-WP：

```text
ReAct reasoning/action interleaving -> Planner/Executor reasoning-action loop
CEBRA-WP                            -> adds Top-K candidates, utility scoring, recovery policy
```

#### Reflexion

- arXiv: `2303.11366`
- 标题：*Reflexion: Language Agents with Verbal Reinforcement Learning*
- 作者：Noah Shinn 等
- arXiv 页面显示：v1 提交于 2023-03-20，v4 修订于 2023-10-10
- 摘要要点：语言 agent 使用语言反馈与 episodic memory 改善后续决策。

映射到 CEBRA-WP：

```text
Reflexion feedback memory -> recovery history / failure context / HITL decision record
CEBRA-WP                  -> converts feedback into structured runtime state and action utility
```

#### Voyager

- arXiv: `2305.16291`
- 标题：*Voyager: An Open-Ended Embodied Agent with Large Language Models*
- 作者：Guanzhi Wang 等
- arXiv 页面显示：v1 提交于 2023-05-25，v2 修订于 2023-10-19
- 摘要要点：自动 curriculum、技能库、环境反馈与执行错误驱动的 iterative prompting。

映射到 CEBRA-WP：

```text
Voyager skill library / environment feedback -> tool capability graph / execution feedback
CEBRA-WP                                 -> constrained scientific workflow planning, not open-ended exploration
```

#### Tree of Thoughts

- arXiv: `2305.10601`
- 标题：*Tree of Thoughts: Deliberate Problem Solving with Large Language Models*
- 作者：Shunyu Yao 等
- arXiv 页面显示：v1 提交于 2023-05-17，NeurIPS 2023 camera ready
- 摘要要点：探索多条 reasoning paths，自评估、lookahead/backtracking。

映射到 CEBRA-WP：

```text
ToT multiple reasoning paths -> Top-K candidate workflows
CEBRA-WP                     -> adds tool metadata constraints and runtime evidence reranking
```

#### Gorilla

- arXiv: `2305.15334`
- 标题：*Gorilla: Large Language Model Connected with Massive APIs*
- 作者：Shishir G. Patil 等
- arXiv 页面显示提交时间：2023-05-24
- 摘要要点：减少 API 调用幻觉，提升工具/API 调用准确性，结合文档检索适应 API 变化。

映射到 CEBRA-WP：

```text
Gorilla API accuracy / documentation retrieval -> tool metadata and schema correctness
CEBRA-WP                                     -> workflow-level feasibility + recovery-aware decisions
```

### 5.2 C 组对本文的贡献

LLM tool-use agent 文献能支撑：

1. 为什么需要结构化工具元数据，而不是让 LLM 自由调用；
2. 为什么要输出多候选，而不是单一链；
3. 为什么要记录 reasoning/action/evidence；
4. 为什么错误反馈和执行历史可以改善后续决策；
5. 为什么 API hallucination / wrong arguments 是现实风险。

但这些文献不足以直接支撑 CEBRA-WP 的理论深度，因为它们多数不处理高代价科研工作流中的预算、风险和恢复约束。因此需要同时引入 A/B/D/E/F 组。

## 6. D 组：Scientific workflow recovery / provenance

### 6.1 为什么相关

CEBRA-WP 的 `patch_local`、`suffix_replan`、`stop` 本质是工作流恢复策略：

- 保留已验证前缀；
- 局部修补失败步骤；
- 在结构性失败时替换后缀；
- 在预算/恢复余量耗尽时止损；
- 用快照和事件日志保留可审计历史。

这与科学工作流系统中的 provenance、fault tolerance、checkpoint/restart、workflow repair 高度相关。

### 6.2 建议补充检索的经典系统

| 系统/方向 | 可支撑点 |
|---|---|
| Pegasus Workflow Management System | 科学工作流调度、失败处理、provenance |
| Kepler Scientific Workflow System | 科学工作流建模与执行 |
| Taverna / myGrid | 生物信息学工作流与服务组合 |
| VisTrails | provenance-aware scientific workflows |
| Workflow repair / provenance-based debugging | 失败定位、局部重跑、可追溯恢复 |

### 6.3 映射到本文算法

```text
workflow provenance      -> EventLog / Snapshot / StepResult history
checkpoint/restart       -> preserve_prefix_until_step_index
workflow repair          -> patch_local
partial replanning       -> suffix_replan
abort / fail-fast         -> terminal_stop with economic/evidence/recovery reason
```

论文中可以把恢复策略定义为：

```text
A_rec = {patch_local, suffix_replan, stop}
```

并说明：CEBRA-WP 不只做失败后重试，而是根据 belief-state 和预算风险估计选择恢复动作。

## 7. E 组：Protein design foundation models and tools

### 7.1 已核验/高置信代表文献

#### AlphaFold2

- 代表文献：Jumper et al., *Highly accurate protein structure prediction with AlphaFold*, Nature, 2021.
- 作用：结构预测的基础模型，常作为设计候选的后验验证器。

映射：

```text
structure prediction evidence -> structure_quality / pLDDT / RMSD-like metrics
high-cost validation step     -> budget-aware planning
```

#### RFdiffusion

- Nature 页面已核验标题：*De novo design of protein structure and function with RFdiffusion*
- Nature DOI 页面：`s41586-023-06415-8`
- 作用：扩散式蛋白骨架/功能设计，是现代 de novo 设计链路中的高代价生成工具。

映射：

```text
RFdiffusion backbone generation -> high-cost candidate generation step
CEBRA-WP                         -> decide when to invoke, how to validate, when to replan
```

#### ProteinMPNN

- 代表文献：Dauparas et al., *Robust deep learning-based protein sequence design using ProteinMPNN*, Science, 2022.
- 作用：给定结构设计序列，是 RFdiffusion 后常见 sequence design 步骤。

映射：

```text
ProteinMPNN sequence design -> sequence-generation tool
fallback/readiness/cost     -> planner score and recovery complexity
```

#### ESMFold / protein language models

- 代表文献：Lin et al., *Evolutionary-scale prediction of atomic-level protein structure with a language model*, Science, 2023.
- 作用：用蛋白语言模型进行结构预测，可作为较快/不同性质的结构验证或 proxy evidence。

映射：

```text
ESMFold / PLM structure prediction -> proxy/direct structure quality evidence
```

#### AlphaFold3

- Nature 页面已核验标题：*Accurate structure prediction of biomolecular interactions with AlphaFold 3*
- Nature DOI 页面：`s41586-024-07487-w`
- 作用：更广泛的 biomolecular interaction 结构预测，对于 binder/interface 任务尤其相关。

映射：

```text
AlphaFold3 complex prediction -> expensive high-value evidence for binder/interface design
CEBRA-WP                     -> should schedule it after cheaper evidence suffices
```

### 7.2 E 组对本文的贡献

这组文献支撑“为什么该系统是高代价、多阶段、需要恢复的”：

1. 蛋白设计通常是生成—序列设计—结构预测—打分—筛选的多步链路；
2. 每一步都有不同成本和失败模式；
3. 高保真结构预测/复合物预测成本较高，不应无证据地频繁调用；
4. 低成本 proxy evidence 与高成本 direct evidence 应分层使用。

## 8. F 组：Multi-objective protein design / guidance / recent work

本组用于直接深化 `posterior objective scoring`，尤其是多目标权衡和 evidence reliability。

### 8.1 已从 arXiv 搜索页核验到的近期方向

#### RosettaSearch: Multi-Objective Inference-Time Search for Protein Sequence Design

- arXiv: `2604.17175`
- 搜索页信息：2026-04 提交；标题为 *RosettaSearch: Multi-Objective Inference-Time Search for Protein Sequence Design*。
- 摘要片段显示：使用 LLM/reasoning 能力进行 multi-objective inference-time search，并改善 ProteinMPNN designs。

对 CEBRA-WP 的启发：

```text
multi-objective inference-time search -> posterior objective scoring / candidate reranking
```

注意：这是 2026 新论文，最终引用前需完整阅读。

#### Property-driven Protein Inverse Folding With Multi-Objective Preference Alignment

- arXiv: `2603.06748`
- 搜索页信息：2026-03 提交。
- 摘要片段显示：使用多目标偏好对齐改善 ProteinMPNN backbone 上的 developability。

对 CEBRA-WP 的启发：

```text
multi-objective preference alignment -> GoalFit / objective weight selection
```

#### AutoBinder Agent: An MCP-Based Agent for End-to-End Protein Binder Design

- arXiv: `2602.00019`
- 搜索页信息：2026-02；MCP-based agent for end-to-end protein binder design。
- 摘要片段显示：组合 PPI site identification、Rosetta、ProteinMPNN、AlphaFold3 等工具。

对 CEBRA-WP 的启发：

```text
end-to-end binder design agent -> closest system-level related work
```

这是非常重要的竞品/相关系统，D2/D4 后续应重点阅读。

#### ProteinGuide: On-the-fly property guidance for protein sequence generative models

- arXiv: `2505.04823`
- 搜索页信息：2025-05。
- 摘要片段显示：on-the-fly property guidance，适配 ESM3、ProteinMPNN、diffusion/flow matching 等模型。

对 CEBRA-WP 的启发：

```text
property guidance -> objective scoring + runtime evidence-guided reranking
```

#### ProteinZero: Self-Improving Protein Generation via Online Reinforcement Learning

- arXiv: `2506.07459`
- 搜索页信息：2025-06 初版，2026-03 修订。
- 摘要片段显示：online RL 改善 designability、stability、recovery、diversity，降低 design failure rates。

对 CEBRA-WP 的启发：

```text
online RL / self-improvement -> future extension, not current deterministic CEBRA-WP core
```

#### Fast non-autoregressive inverse folding with discrete diffusion

- arXiv: `2312.02447`
- 搜索页信息：2023-12。
- 摘要片段显示：将 ProteinMPNN fine-tune 为 discrete diffusion，提供速度—精度权衡。

对 CEBRA-WP 的启发：

```text
speed/accuracy tradeoff -> Cost Schema and tool choice under budget
```

#### PDB-Struct: A Comprehensive Benchmark for Structure-based Protein Design

- arXiv: `2312.00080`
- 搜索页信息：2023-12。
- 摘要片段显示：评估 ByProt、ProteinMPNN、ESM-IF、ESM-Design、AF-Design 等。

对 CEBRA-WP 的启发：

```text
benchmark/evaluation metrics -> objective_score and evidence_sufficiency calibration
```

### 8.2 F 组对本文的贡献

这组文献用于把当前 `objective_ranker_adapter.py` 从工程打分提升到论文理论：

当前代码已有：

```text
components = generic_objective, stability, novelty, function, structure_quality
binding_policy = folded_into_generic_objective
status = direct | proxy | degraded
aggregate_score = sum component_weight * effective_score
```

理论 v2 可定义：

```text
G(pi;g,o_t) = sum_m lambda_m(g) * rho_m(o_t) * q_m(pi,o_t)
```

其中：

- `m` 是目标维度；
- `lambda_m(g)` 是任务目标权重；
- `q_m` 是归一化目标分数；
- `rho_m` 是证据可靠性权重，对应 direct/proxy/degraded；
- `G` 可作为 static objective 或 posterior objective。

## 9. 文献到算法组件的详细映射

完整代码落点、schema/version 和正文采用状态见
`theory-background-paper-code-map.md`；下表保留概览写法。

| CEBRA-WP 组件 | 最相关文献组 | 支撑点 | 论文写法 |
|---|---|---|---|
| `Pi_t` 候选集合 | LLM tool-use; ToT; scientific workflow | 多路径候选、工具链组合、候选裁剪 | “We generate a bounded Top-K candidate workflow set rather than committing to a single LLM-produced chain.” |
| hard feasibility `F_h` | CMDP; Gorilla/API reliability; workflow systems | API/工具约束、I/O 约束、安全约束 | “Infeasible candidates are removed before utility comparison.” |
| static score `S_static` | CMDP; protein objective scoring | 成本、风险、目标匹配、恢复复杂度 | “Static utility estimates prior workflow quality before consuming runtime observations.” |
| Lite belief-state `x_t` | POMDP; Reflexion; workflow provenance | 历史和反馈压缩为状态估计 | “A deterministic belief surrogate approximates latent workflow viability.” |
| runtime delta `Delta` | POMDP; risk-sensitive planning | 观测驱动的 bounded score correction | “Runtime evidence adjusts but does not fully override static workflow quality.” |
| action utility `U_a` | CMDP; workflow recovery | continue/patch/replan/stop 的恢复控制 | “Control actions are selected by recovery-aware utility under hard priorities.” |
| posterior objective scoring | ProteinGuide; RosettaSearch; multi-objective inverse folding | 多目标、证据可靠性、direct/proxy/degraded | “GoalFit is modeled as evidence-weighted multi-objective posterior score.” |
| terminal stop | budgeted planning; workflow recovery | 高预算压力和低恢复价值下止损 | “Stop is an economic/recovery terminal policy, not user cancellation.” |

## 10. 推荐在论文中采用的 Related Work 结构

### 10.1 Tool-using LLM agents

覆盖：Toolformer、ReAct、Gorilla、Reflexion、Voyager、Tree of Thoughts。

重点对比：

- 这些方法证明 LLM 可以调用工具、与环境交互、生成多路径推理；
- 但多数没有显式建模科研工具成本、失败恢复、证据可靠性；
- CEBRA-WP 的贡献是在 LLM 工具链规划上加入约束化、证据感知和恢复感知控制。

### 10.2 Belief-state and constrained decision making

覆盖：POMDP、CMDP、budgeted/risk-sensitive planning。

重点对比：

- 经典方法理论严谨，但要求明确状态/转移/奖励模型；
- 高代价蛋白设计工作流中这些模型难以精确获得；
- CEBRA-WP 采用低维可解释 belief surrogate 与确定性更新，换取可审计性和工程可部署性。

### 10.3 Scientific workflow recovery

覆盖：Pegasus、Kepler、Taverna、VisTrails、provenance/debugging/recovery。

重点对比：

- 传统科学工作流系统重视调度、provenance 和失败恢复；
- 但较少结合 LLM 动态规划、蛋白设计 objective evidence 和工具链 Top-K rerank；
- CEBRA-WP 可看作 LLM-era scientific workflow recovery policy。

### 10.4 Protein design workflows and objective evaluation

覆盖：AlphaFold2、ESMFold、RFdiffusion、ProteinMPNN、AlphaFold3、近期 multi-objective/protein guidance 论文。

重点对比：

- 基础模型提升了单步生成/预测能力；
- 实际系统仍需要决定何时调用哪个模型、如何组合证据、何时停止或重规划；
- CEBRA-WP 解决的是 model orchestration and evidence-aware workflow planning。

## 11. 后续必须精读的优先级

### P0：直接支撑 CEBRA-WP 核心贡献

1. ReAct — LLM reasoning/action loop。
2. Toolformer — LLM 工具/API 调用。
3. Gorilla — API 调用准确性和文档检索。
4. Kaelbling et al. 1998 POMDP review — belief-state 形式化背景。
5. Altman 1999 CMDP — 约束决策背景。
6. RFdiffusion — 高代价蛋白生成工具。
7. ProteinMPNN — 结构条件序列设计工具。
8. AlphaFold3 / AlphaFold2 / ESMFold — 高代价结构/复合物验证工具。
9. AutoBinder Agent 2026 — 最接近“端到端蛋白 binder agent”的相关系统。

### P1：用于强化 objective scoring 和实验设计

1. ProteinGuide 2025。
2. RosettaSearch 2026。
3. Property-driven Protein Inverse Folding 2026。
4. ProteinZero 2025/2026。
5. PDB-Struct benchmark 2023。
6. Fast non-autoregressive inverse folding with discrete diffusion 2023。

### P2：用于扩展讨论

1. Reflexion。
2. Voyager。
3. Tree of Thoughts。
4. Scientific workflow provenance/recovery 系统文献。
5. Risk-sensitive planning / budgeted planning 细分文献。

## 12. 对 CEBRA-WP 理论深化的直接结论

文献映射后，CEBRA-WP 不应被包装成“一个新的蛋白设计模型”。更准确的贡献表述是：

> CEBRA-WP is a constrained, evidence-aware, recovery-adaptive workflow planning algorithm for orchestrating expensive protein design tools under partial observability.

中文：

> CEBRA-WP 是一种面向高代价蛋白质设计工具编排的约束化、证据感知、恢复自适应工作流规划算法；其核心贡献不在于提出新的生成模型，而在于在部分可观测、高失败代价和多目标证据不完备的条件下，动态选择工具链候选与恢复动作。

理论 v2 应围绕以下四个公式展开：

```text
Pi_t = { pi in G(g,C,K,h_t) | F_h(pi,C,K,h_t)=1 }

S_static(pi) = w_f F_s(pi) + w_g G(pi;g,o_t) - w_c C(pi) - w_r R(pi) - w_rec Rec(pi) + w_q Q(pi)

x_{t+1} = B(x_t, o_t, h_t)

U_pi(pi,x_t) = clip(S_static(pi) + Delta(pi,x_t), 0, 1)

a_t = argmax_{a in A} U_a(a,x_t,Pi_t,h_t)
```

其中：

- `F_h` 来自 constrained planning；
- `x_t` 来自 POMDP belief-state 思想；
- `G(pi;g,o_t)` 来自 protein multi-objective/evidence-weighted scoring；
- `U_a` 来自 recovery-aware workflow control；
- LLM tool-use 文献支撑工具调用与候选生成，但不是全部理论根基。

## 13. 风险与待核验项

1. Semantic Scholar/API 本轮限流，引用计数与 DOI 没有系统拉取；最终参考文献需要再跑一次 BibTeX 核验。
2. POMDP/CMDP 经典文献未在本轮逐页抓取，只基于经典公认条目列出；最终论文引用前建议用 Google Scholar/出版社页面核对。
3. 2026 年 arXiv 新论文需要谨慎使用：可以作为 latest related work，但不要作为核心理论唯一依据。
4. `AutoBinder Agent` 与当前系统主题很接近，必须精读，否则 related work 容易遗漏最直接竞品。
5. RFdiffusion/ProteinMPNN/AlphaFold3 等工具文献应服务于“为什么链路高代价且需编排”，不要把论文重心写偏成蛋白生成模型综述。
