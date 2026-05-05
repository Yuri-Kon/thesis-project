# CEBRA-WP 理论对象-文献-代码映射

- 版本日期：2026-05-05
- 适用算法版本：`cebra_wp.v2`
- 配套文档：`core-algorithm-theory-v2.md`, `algorithm-version-registry.md`, `core-algorithm-literature-map.md`
- 目标：把论文中的理论对象、核心公式、代表文献和当前代码落点放在同一张可维护清单中。
- 检索口径：经典 POMDP/CMDP/工作流文献按已稳定共识列入；2025-2026 蛋白设计和 agent 论文按 2026-05-05 可检索 arXiv/Nature 页面记录用途，定稿前仍需统一导出 BibTeX 和 DOI。

## 1. 使用规则

本文档是写作和实现之间的中间层，不替代代码里的 schema/version registry。

- 论文正文引用理论对象时，优先从第 2 节选择 `进入正文` 或 `正文+相关工作` 的条目。
- 实现审查或 issue 拆分时，优先从 `代码落点` 和 `字段/metadata` 反查对应理论对象。
- 近期 arXiv 条目只作为 latest related work 或算法细化依据；除非已经完成精读和实验对照，不把它们作为唯一核心理论依据。
- 若代码字段语义变化，先更新 `src/models/algorithm_versions.py` 或相关 schema，再同步本映射。

## 2. 核心公式覆盖矩阵

| 理论对象 / 公式 | 公式版本或 schema | 设计来源 | 代码落点 | 字段 / metadata | 理论背景 | 代表文献 | 正文状态 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `Pi_raw,t = G_theta(g,C,K,h_t)` 候选生成 | candidate schema | `sid:planner.contracts.candidate_schema` | `src/agents/candidate_generator/generator.py::CandidateGenerator.generate`, `src/agents/planner.py` | `PendingActionCandidate`, `top_k`, `default_recommendation` | LLM tool-use, Tree-of-Thought style multi-path search, scientific workflow composition | ReAct; Toolformer; Tree of Thoughts; Gorilla; Pegasus/Kepler/Taverna | 正文+相关工作 |
| `Pi_t = {pi in Pi_raw,t | F_h(pi,C,K,h_t)=1}` 硬可行性过滤 | `candidate_feasibility.v1` | `sid:algo.adaptive.feasibility_filter`, `sid:planner.algorithm.candidate_scoring` | `src/agents/candidate_generator/generator.py::_filter_reason`, `_with_candidate_feasibility` | `metadata.candidate_feasibility.hard_feasible`, `auto_executable`, `requires_hitl`, `blocked_by`, `source_refs` | CMDP hard constraints, API/tool reliability, safety gating | Altman 1999; constrained MDP literature; Gorilla; scientific workflow systems | 正文 |
| `S_static(pi)` 静态候选效用 | `static_score.v1`, `score_breakdown.v1` | `sid:planner.algorithm.candidate_scoring` | `src/agents/planner.py::_score_payload`, `src/agents/candidate_generator/recovery_complexity.py` | `score_breakdown.feasibility`, `objective`, `risk`, `cost`, `recovery_complexity`, `recoverability`, `overall` | constrained / budgeted / risk-sensitive planning; workflow utility | Altman 1999; budgeted MDP and risk-sensitive MDP literature; workflow scheduling literature | 正文 |
| `G_post(pi;g,o_t)=sum_m lambda_m rho_m q_m` 证据加权后验目标 | `posterior_score.v1`, `posterior_objective.v1` | `sid:algo.posterior_objective_scoring` | `src/adapters/objective_ranker_adapter.py`, `src/agents/candidate_generator/builder.py::_normalize_posterior_objective` | `posterior_objective.components`, `aggregate_score`, `evidence_sufficiency`, `evidence_status`, `source_refs` | evidence-weighted multi-objective objective; direct/proxy/degraded evidence | ProteinGuide 2025; RosettaSearch 2026; ProtAlign 2026; PDB-Struct 2023 | 正文+最新相关工作 |
| `binding_policy = folded_into_generic_objective` binding 代理证据 | `posterior_objective.v1` | `sid:algo.posterior_objective_scoring` | `src/adapters/objective_ranker_adapter.py` | `binding_policy`, `binding_proxy_component`, `binding_proxy_fields`, `binding_evidence` | docking/binding proxy, biomolecular interaction prediction, structure-quality proxy | AlphaFold3 2024; RFdiffusion 2023; ProteinMPNN 2022; AutoBinder Agent 2026 | 正文中谨慎表述 |
| `x_t=(s_t,f_t,r_t,c_t,e_t)` Lite belief-state | runtime state schema | `sid:planner.runtime.belief_state_schema`, `sid:planner.algorithm.runtime_state_estimation` | `src/workflow/belief_state.py::RuntimeState`, `update_runtime_state` | `p_success`, `p_structural_failure`, `recovery_margin`, `expected_remaining_cost`, `evidence_sufficiency` | POMDP belief-state under partial observability | Smallwood & Sondik 1973; Kaelbling, Littman & Cassandra 1998; Cassandra 1998 | 正文 |
| `x_{t+1}=B(x_t,o_t,h_t)` 运行时状态更新 | runtime update rules | `sid:planner.algorithm.runtime_update_rules` | `src/workflow/belief_state.py::BELIEF_STATE_UPDATE_RULES`, `update_runtime_state` | `StepResult`, `SafetyResult`, failure context, objective evidence, progress counters | belief update surrogate, online adaptation, workflow provenance | POMDP belief update literature; Reflexion; scientific workflow provenance | 正文 |
| `budget_pressure = clip(c_t / budget_cap)` 预算压力 | budget pressure derivation | `sid:algo.schema.cost`, `sid:planner.runtime.belief_state_schema` | `src/workflow/action_features.py`, `src/workflow/runtime_evaluator.py` | `budget_pressure`, `expected_remaining_cost`, `BudgetPressureSource` | budgeted MDP, resource-constrained planning | Altman 1999; budgeted MDP literature | 正文 |
| `Delta(pi,x_t)` 有界运行时修正 | `runtime_adjustment.v1` | `sid:planner.algorithm.runtime_reranking`, `sid:planner.algorithm.runtime_adjustment_formula` | `src/workflow/runtime_evaluator.py::compute_runtime_delta`, `_apply_runtime_adjustment` | `metadata.runtime_adjustment.value`, `factors`, `source_refs`, `final_score`, `rerank_reason` | bounded online correction, risk-sensitive adaptation, evidence sufficiency | POMDP online adaptation; risk-sensitive MDP; Reflexion | 正文 |
| `ActionBias(pi,x_t)` runtime delta 的动作偏置 | `action_bias.v1` | `sid:planner.algorithm.runtime_adjustment_formula` | `src/workflow/runtime_evaluator.py::compute_runtime_delta`, `_build_action_bias_payload` | `metadata.runtime_adjustment.action_bias.action`, `value`, `factors.term`, `factors.formula_ref`, `factors.message` | recovery-aware policy explanation, recoverability and intervention policy | workflow recovery/provenance literature; CMDP/risk-sensitive planning | 正文 |
| `U_pi(pi,x_t)=clip(S_static+Delta,0,1)` 最终候选效用 | runtime rerank payload | `sid:planner.algorithm.runtime_reranking` | `src/workflow/runtime_evaluator.py::_apply_runtime_adjustment` | `static_score`, `runtime_adjustment`, `final_score`, `rerank_reason` | bounded reranking under partial observability | POMDP belief-state planning; budget/risk-sensitive planning | 正文 |
| `SelectDiverseTopK(Pi_t,U_pi,k,coverage)` 多样性 Top-K | `topk_diversity.v1` | `sid:planner.algorithm.candidate_scoring`, `sid:planner.algorithm.runtime_reranking` | `src/agents/candidate_generator/generator.py::_attach_topk_diversity_metadata` | `metadata.topk_diversity.strategy`, `coverage_fields`, `selected_bucket`, `degraded_to_score_sort`, `source_refs` | diversity-aware search, multi-path LLM reasoning, portfolio selection | Tree of Thoughts; diverse beam/search literature; ProteinZero diversity regularization as related signal | 正文+附录 |
| `U_a(a,x_t,Pi_t,h_t)` 动作效用 | `action_utility.v1`, `action_features.v1` | `sid:algo.schema.action_utility` | `src/workflow/runtime_evaluator.py::compute_action_utilities`, `src/workflow/action_features.py::derive_action_features` | `ActionUtility.value`, `factors`, `features`, `source_refs` | recovery-aware workflow control, intervention policy, budget/risk-sensitive action selection | CMDP/risk-sensitive planning; workflow repair/replanning; Reflexion feedback | 正文 |
| hard priorities and stop guard | action selection / terminal stop refs | `sid:planner.algorithm.action_priority_resolution`, `sid:planner.algorithm.stop_semantics` | `src/workflow/recovery.py::select_workflow_action`, `build_terminal_stop_candidate` | `selected_action`, `action_selection.source_refs`, `terminal_policy`, `requires_hitl` | safety gating, protected terminal action, human decision boundary | CMDP safety constraints; workflow abort/fail-fast; HITL decision systems | 正文 |
| runtime policy ablation groups | experiment mapping | `docs/experiment/algorithm-group-paper-mapping.md` | `src/workflow/runtime_evaluator.py::runtime_policy_ablation_group` | `paper_group_id`, `paper_group_name`, `full_runtime_adjustment` | ablation design for static, gated, observation-only, and belief-state policies | offline ablation methodology; related planning baselines | 实验章节 |

覆盖检查：

- `Pi_t`, `S_static`, `G_post`, `x_t`, `B`, `Delta`, `U_pi`, `SelectDiverseTopK`, `U_a`, stop guard 均至少有一个理论背景和一个实现入口。
- `posterior_objective`、`runtime_adjustment`、`action_utility`、`action_bias` 均能通过 schema/version 或 metadata 反查文献用途。
- binding / structure proxy 不被描述为实验真值，只作为 expensive or proxy evidence 的一类。

## 3. 分桶映射

| 分桶 | 理论对象 | 文献 / 综述 | 对 CEBRA-WP 的作用 | 是否进入正文 |
| --- | --- | --- | --- | --- |
| POMDP / belief-state / online adaptation | `x_t`, `B(x_t,o_t,h_t)`, bounded `Delta` | Smallwood & Sondik 1973; Kaelbling, Littman & Cassandra 1998; Cassandra 1998 | 解释为什么高代价工作流需要把稀疏观测压缩成状态估计，并说明当前只是 deterministic lite belief surrogate | 进入正文 |
| CMDP / hard constraints / safety gating | `F_h`, budget pressure, hard priorities, stop guard | Altman 1999; constrained/budgeted/risk-sensitive MDP literature | 支撑硬可行性先于效用优化、预算不是普通文案而是约束/状态变量、stop 受保护 | 进入正文 |
| evidence-weighted posterior objective | `G_post`, `posterior_objective`, `evidence_status` | ProteinGuide 2025; RosettaSearch 2026; ProtAlign 2026; PDB-Struct 2023 | 支撑多目标目标函数、direct/proxy/degraded evidence 权重、objective evidence sufficiency | 正文+相关工作 |
| recovery / replanning / intervention policy | `U_a`, `ActionBias`, `patch_local`, `suffix_replan`, `terminal_stop` | Pegasus/Kepler/Taverna/VisTrails; workflow repair/provenance; Reflexion | 支撑失败后不是盲目 retry，而是在局部修补、后缀重规划和终止之间做可解释选择 | 进入正文 |
| diversity-aware Top-K selection | `SelectDiverseTopK`, `topk_diversity` | Tree of Thoughts; portfolio/diverse search literature; ProteinZero 2025 as diversity-related recent work | 支撑 Top-K 不是纯分数排序，而是保留 capability bucket 与恢复路径覆盖 | 正文+附录 |
| docking / binding / structure-quality proxies | `structure_quality`, `binding_evidence`, `binding_policy` | AlphaFold2 2021; ProteinMPNN 2022; RFdiffusion 2023; ESMFold 2023; AlphaFold3 2024; AutoBinder Agent 2026 | 支撑蛋白工具链高代价、多阶段验证、binding/interface 任务需要 proxy/direct evidence 分层 | 正文+相关工作 |

## 4. 近期论文复用清单

下列条目按 2026-05-05 检索结果记录，适合支撑 related work、实验动机或 future work。定稿前需要核对 BibTeX、版本号、作者列表和发表状态。

| 条目 | 日期 / 版本线索 | 稳定链接 | 映射对象 | 复用方式 |
| --- | --- | --- | --- | --- |
| RosettaSearch: Multi-Objective Inference-Time Search for Protein Sequence Design | arXiv `2604.17175`, 2026-04-19 | <https://arxiv.org/abs/2604.17175> | `G_post`, multi-objective inference-time search, candidate reranking | latest related work；可比较 CEBRA-WP 的 workflow-level reranking 与 sequence-level inference-time search |
| AutoBinder Agent: An MCP-Based Agent for End-to-End Protein Binder Design | arXiv `2602.00019`, 2026-01-16 | <https://arxiv.org/abs/2602.00019> | binder workflow orchestration, AlphaFold3/ProteinMPNN/Rosetta tool chain | 最接近系统型相关工作；正文 related work 必须提及 |
| Property-driven Protein Inverse Folding With Multi-Objective Preference Alignment | arXiv `2603.06748`, 2026-03 | <https://arxiv.org/abs/2603.06748> | multi-objective preference alignment, developability objectives | 用于说明 `lambda_m` 目标权重和 developability 目标不是任意工程拼接 |
| ProteinGuide: Guide your favorite protein sequence generative model | arXiv `2505.04823`, 2025-05 | <https://arxiv.org/abs/2505.04823> | plug-and-play property guidance, posterior objective | 支撑 property guidance 与 evidence-guided generation 的相关方向 |
| ProteinZero: Self-Improving Protein Generation via Online Reinforcement Learning | arXiv `2506.07459`, 2025-06, 2026 修订线索 | <https://arxiv.org/abs/2506.07459> | online RL, proxy reward, diversity regularization | future extension；不要把 CEBRA-WP 写成 online RL |
| PDB-Struct: A Comprehensive Benchmark for Structure-based Protein Design | arXiv `2312.00080`, 2023-12 | <https://arxiv.org/abs/2312.00080> | benchmark metrics, structure-quality evidence | 用于校准 `objective_score` 与 `evidence_sufficiency` 的实验讨论 |
| Fast non-autoregressive inverse folding with discrete diffusion | arXiv `2312.02447`, 2023-12 | <https://arxiv.org/abs/2312.02447> | speed/quality tradeoff, inverse folding alternatives | 支撑 `cost`、`risk` 和工具选择下的速度-精度权衡 |
| AlphaFold 3: Accurate structure prediction of biomolecular interactions | Nature 2024, DOI `10.1038/s41586-024-07487-w` | <https://www.nature.com/articles/s41586-024-07487-w> | binding/interface evidence, expensive complex prediction | 正文中作为高价值 direct/proxy evidence 工具背景 |

## 5. 代码字段反查索引

| 字段 / metadata | 理论对象 | 主要代码 | 文献桶 |
| --- | --- | --- | --- |
| `score_breakdown.overall` | `S_static` | `src/agents/planner.py::_score_payload` | CMDP / utility |
| `score_breakdown.recovery_complexity`, `recoverability` | recovery cost / recoverability | `src/agents/candidate_generator/recovery_complexity.py` | workflow recovery |
| `metadata.candidate_feasibility` | `F_h` | `src/agents/candidate_generator/generator.py` | CMDP / hard constraints |
| `metadata.posterior_objective` | `G_post` | `src/adapters/objective_ranker_adapter.py`, `src/agents/candidate_generator/builder.py` | evidence-weighted objective |
| `metadata.runtime_adjustment` | `Delta`, `U_pi` | `src/workflow/runtime_evaluator.py` | POMDP / runtime adaptation |
| `metadata.runtime_adjustment.action_bias` | `ActionBias` | `src/workflow/runtime_evaluator.py` | recovery policy |
| `metadata.topk_diversity` | `SelectDiverseTopK` | `src/agents/candidate_generator/generator.py` | diversity-aware Top-K |
| `ActionUtility.features` | `U_a` | `src/workflow/action_features.py`, `src/workflow/runtime_evaluator.py` | intervention / recovery |
| `terminal_policy=stop` | protected stop | `src/workflow/recovery.py`, terminal stop builder | safety gating / workflow stop |
| `runtime_policy_ablation_group` | experiment group | `src/workflow/runtime_evaluator.py`, `docs/experiment/algorithm-group-paper-mapping.md` | evaluation methodology |

## 6. 写作边界

- 可以写：CEBRA-WP 受 POMDP belief-state planning 启发，维护低维 deterministic belief surrogate。
- 不应写：CEBRA-WP 学到了最优 POMDP policy 或严格 Bayesian posterior。
- 可以写：`F_h` 是 CMDP-like hard feasibility gate，先于效用排序。
- 不应写：runtime adjustment 能覆盖 I/O、schema、安全等硬违规。
- 可以写：posterior objective 是 evidence-weighted computational score。
- 不应写：posterior objective 等价于湿实验验证。
- 可以写：AutoBinder Agent 是近期最接近的 binder agent 相关工作。
- 不应写：CEBRA-WP 与 AutoBinder 完全同类；CEBRA-WP 的重点是约束化、证据感知、恢复感知的工作流规划策略。
