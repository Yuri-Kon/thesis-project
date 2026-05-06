---
doc_key: algo_theory_map
version: 1.0
status: stable
depends_on: [algo, algo_runtime, tools_metadata, impl]
---

# CEBRA-WP 理论对象、文献与代码映射
<!-- SID:algo.theory_map.overview -->

本文档是 CEBRA-WP 论文写作、实现审查和代码注释的共同索引。它不替代以下 SSOT：

- 核心算法语义：[core-algorithm-spec.md](./core-algorithm-spec.md)
- 运行时公式与 schema：[runtime-adaptation-formalization.md](./runtime-adaptation-formalization.md)
- 工具成本与风险先验：[active-tool-metadata-profile.md](./active-tool-metadata-profile.md)

使用规则：

- 论文正文引用理论对象时，优先使用第 1 节中标记为“正文”的条目；
- 实现审查或 issue 拆分时，优先从“代码落点”和“字段 / metadata”反查对应理论对象；
- 近期 arXiv 条目只作为 latest related work 或算法细化依据，定稿前需统一核对 BibTeX、版本号、作者列表和发表状态；
- 若代码字段语义变化，先更新代码侧 schema/version registry，再同步本文档和 `core-algorithm-spec.md`。

## 1. 核心公式覆盖矩阵
<!-- SID:algo.theory_map.formula_matrix -->

| 理论对象 / 公式 | 公式版本或 schema | 设计来源 | 代码落点 | 字段 / metadata | 理论背景 | 代表文献 | 正文状态 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| $\Pi_{\text{raw},t}=G_\theta(g,\mathcal{C},K,h_t)$ 候选生成 | candidate schema | `SID:planner.contracts.candidate_schema` | `src/agents/candidate_generator/generator.py::CandidateGenerator.generate`, `src/agents/planner.py` | `PendingActionCandidate`, `top_k`, `default_recommendation` | LLM tool-use, multi-path search, scientific workflow composition | ReAct; Toolformer; Tree of Thoughts; Gorilla; Pegasus/Kepler/Taverna | 正文+相关工作 |
| $\Pi_t=\{\pi\in\Pi_{\text{raw},t}\mid F_h(\pi,\mathcal{C},K,h_t)=1\}$ 硬可行性过滤 | `candidate_feasibility.v1` | `SID:algo.adaptive.feasibility_filter`, `SID:planner.algorithm.candidate_scoring` | `src/agents/candidate_generator/generator.py::_filter_reason`, `_with_candidate_feasibility` | `metadata.candidate_feasibility.hard_feasible`, `auto_executable`, `requires_hitl`, `blocked_by`, `source_refs` | CMDP hard constraints, API/tool reliability, safety gating | Altman 1999; Gorilla; scientific workflow systems | 正文 |
| $S_{\text{static}}(\pi)$ 静态候选效用 | `static_score.v1`, `score_breakdown.v1` | `SID:planner.algorithm.candidate_scoring` | `src/agents/planner.py::_score_payload`, `src/agents/candidate_generator/recovery_complexity.py` | `score_breakdown.feasibility`, `objective`, `risk`, `cost`, `recovery_complexity`, `recoverability`, `overall` | constrained / budgeted / risk-sensitive planning; workflow utility | Altman 1999; budgeted MDP; workflow scheduling | 正文 |
| $G_{\text{post}}(\pi;g,o_t)=\sum_m\lambda_m\rho_m q_m$ 证据加权后验目标 | `posterior_score.v1`, `posterior_objective.v1` | `SID:algo.posterior.objective_scoring` | `src/adapters/objective_ranker_adapter.py`, `src/agents/candidate_generator/builder.py::_normalize_posterior_objective` | `posterior_objective.components`, `aggregate_score`, `evidence_sufficiency`, `evidence_status`, `source_refs` | evidence-weighted multi-objective objective | ProteinGuide; RosettaSearch; PDB-Struct | 正文+最新相关工作 |
| $\operatorname{binding\_policy}=\text{folded\_into\_generic\_objective}$ binding 代理证据 | `posterior_objective.v1` | `SID:algo.posterior.objective_scoring` | `src/adapters/objective_ranker_adapter.py` | `binding_policy`, `binding_proxy_component`, `binding_proxy_fields`, `binding_evidence` | docking/binding proxy, structure-quality proxy | AlphaFold3; RFdiffusion; ProteinMPNN; AutoBinder Agent | 正文中谨慎表述 |
| $x_t=(s_t,f_t,r_t,c_t,e_t)$ Lite belief-state | runtime state schema | `SID:planner.runtime.belief_state_schema`, `SID:planner.algorithm.runtime_state_estimation` | `src/workflow/belief_state.py::RuntimeState`, `update_runtime_state` | `p_success`, `p_structural_failure`, `recovery_margin`, `expected_remaining_cost`, `evidence_sufficiency` | POMDP belief-state under partial observability | Smallwood & Sondik 1973; Kaelbling et al. 1998; Cassandra 1998 | 正文 |
| $x_{t+1}=B(x_t,o_t,h_t)$ 运行时状态更新 | runtime update rules | `SID:planner.algorithm.runtime_update_rules` | `src/workflow/belief_state.py::BELIEF_STATE_UPDATE_RULES`, `update_runtime_state` | `StepResult`, `SafetyResult`, failure context, objective evidence, progress counters | belief update surrogate, online adaptation, workflow provenance | POMDP belief update; Reflexion; scientific workflow provenance | 正文 |
| $\operatorname{budget\_pressure}=\operatorname{clip}(c_t/\operatorname{budget\_cap})$ 预算压力 | budget pressure derivation | `SID:algo.schema.cost`, `SID:planner.runtime.belief_state_schema` | `src/workflow/action_features.py`, `src/workflow/runtime_evaluator.py` | `budget_pressure`, `expected_remaining_cost`, `BudgetPressureSource` | budgeted MDP, resource-constrained planning | Altman 1999; budgeted MDP literature | 正文 |
| $\Delta(\pi,x_t)$ 有界运行时修正 | `runtime_adjustment.v1` | `SID:planner.algorithm.runtime_reranking`, `SID:planner.algorithm.runtime_adjustment_formula` | `src/workflow/runtime_evaluator.py::compute_runtime_delta`, `_apply_runtime_adjustment` | `metadata.runtime_adjustment.value`, `factors`, `source_refs`, `final_score`, `rerank_reason` | bounded online correction, risk-sensitive adaptation | POMDP online adaptation; risk-sensitive MDP; Reflexion | 正文 |
| $\operatorname{ActionBias}(\pi,x_t)$ runtime delta 的动作偏置 | `action_bias.v1` | `SID:planner.algorithm.runtime_adjustment_formula` | `src/workflow/runtime_evaluator.py::compute_runtime_delta`, `_build_action_bias_payload` | `metadata.runtime_adjustment.action_bias.action`, `value`, `factors.term`, `factors.formula_ref`, `factors.message` | recovery-aware policy explanation | workflow recovery/provenance; CMDP/risk-sensitive planning | 正文 |
| $U_\pi(\pi,x_t)=\operatorname{clip}(S_{\text{static}}+\Delta,0,1)$ 最终候选效用 | runtime rerank payload | `SID:planner.algorithm.runtime_reranking` | `src/workflow/runtime_evaluator.py::_apply_runtime_adjustment` | `static_score`, `runtime_adjustment`, `final_score`, `rerank_reason` | bounded reranking under partial observability | POMDP belief-state planning; budget/risk-sensitive planning | 正文 |
| $\operatorname{SelectDiverseTopK}(\Pi_t,U_\pi,k,\operatorname{coverage})$ 多样性 Top-K | `topk_diversity.v1` | `SID:planner.algorithm.topk_diversity`, `SID:planner.algorithm.runtime_reranking` | `src/agents/candidate_generator/generator.py::_attach_topk_diversity_metadata` | `metadata.topk_diversity.strategy`, `coverage_fields`, `selected_bucket`, `degraded_to_score_sort`, `source_refs` | diversity-aware search, multi-path LLM reasoning, portfolio selection | Tree of Thoughts; diverse beam/search; ProteinZero as related signal | 正文+附录 |
| $U_a(a,x_t,\Pi_t,h_t)$ 动作效用 | `action_utility.v1`, `action_features.v1` | `SID:algo.schema.action_utility` | `src/workflow/runtime_evaluator.py::compute_action_utilities`, `src/workflow/action_features.py::derive_action_features` | `ActionUtility.value`, `factors`, `features`, `source_refs` | recovery-aware workflow control, intervention policy | CMDP/risk-sensitive planning; workflow repair/replanning; Reflexion | 正文 |
| hard priorities and stop guard | action selection / terminal stop refs | `SID:planner.algorithm.action_priority_resolution`, `SID:planner.algorithm.stop_semantics` | `src/workflow/recovery.py::select_workflow_action`, `build_terminal_stop_candidate` | `selected_action`, `action_selection.source_refs`, `terminal_policy`, `requires_hitl` | safety gating, protected terminal action, human decision boundary | CMDP safety constraints; workflow abort/fail-fast; HITL decision systems | 正文 |

覆盖要求：

- $\Pi_t$、$S_{\text{static}}$、$G_{\text{post}}$、$x_t$、$B$、$\Delta$、$U_\pi$、$\operatorname{SelectDiverseTopK}$、$U_a$、stop guard 均至少有一个理论背景和一个实现入口；
- `posterior_objective`、`runtime_adjustment`、`action_utility`、`action_bias` 均能通过 schema/version 或 metadata 反查文献用途；
- binding / structure proxy 不被描述为实验真值，只作为 expensive or proxy evidence 的一类。

## 2. 分桶映射
<!-- SID:algo.theory_map.literature_buckets -->

| 分桶 | 理论对象 | 文献 / 综述 | 对 CEBRA-WP 的作用 | 是否进入正文 |
| --- | --- | --- | --- | --- |
| POMDP / belief-state / online adaptation | $x_t$、$B(x_t,o_t,h_t)$、bounded $\Delta$ | Smallwood & Sondik 1973; Kaelbling, Littman & Cassandra 1998; Cassandra 1998 | 解释为什么高代价工作流需要把稀疏观测压缩成状态估计，并说明当前只是 deterministic lite belief surrogate | 进入正文 |
| CMDP / hard constraints / safety gating | $F_h$、budget pressure、hard priorities、stop guard | Altman 1999; constrained/budgeted/risk-sensitive MDP literature | 支撑硬可行性先于效用优化、预算是一等决策变量、stop 受保护 | 进入正文 |
| evidence-weighted posterior objective | $G_{\text{post}}$、`posterior_objective`、`evidence_status` | ProteinGuide; RosettaSearch; PDB-Struct | 支撑多目标目标函数、direct/proxy/degraded evidence 权重、objective evidence sufficiency | 正文+相关工作 |
| recovery / replanning / intervention policy | $U_a$、$\operatorname{ActionBias}$、`patch_local`、`suffix_replan`、`terminal_stop` | Pegasus/Kepler/Taverna/VisTrails; workflow repair/provenance; Reflexion | 支撑失败后不是盲目 retry，而是在局部修补、后缀重规划和终止之间做可解释选择 | 进入正文 |
| diversity-aware Top-K selection | $\operatorname{SelectDiverseTopK}$、`topk_diversity` | Tree of Thoughts; portfolio/diverse search literature; ProteinZero as related signal | 支撑 Top-K 不是纯分数排序，而是保留 capability bucket 与恢复路径覆盖 | 正文+附录 |
| docking / binding / structure-quality proxies | `structure_quality`, `binding_evidence`, `binding_policy` | AlphaFold2; ProteinMPNN; RFdiffusion; ESMFold; AlphaFold3; AutoBinder Agent | 支撑蛋白工具链高代价、多阶段验证、binding/interface 任务需要 proxy/direct evidence 分层 | 正文+相关工作 |

## 3. 近期论文复用清单

下列条目适合支撑 related work、实验动机或 future work。定稿前需要核对 BibTeX、版本号、作者列表和发表状态。

| 条目 | 稳定链接 | 映射对象 | 复用方式 |
| --- | --- | --- | --- |
| RosettaSearch: Multi-Objective Inference-Time Search for Protein Sequence Design | <https://arxiv.org/abs/2604.17175> | $G_{\text{post}}$、multi-objective inference-time search、candidate reranking | latest related work；比较 workflow-level reranking 与 sequence-level inference-time search |
| AutoBinder Agent: An MCP-Based Agent for End-to-End Protein Binder Design | <https://arxiv.org/abs/2602.00019> | binder workflow orchestration, AlphaFold3/ProteinMPNN/Rosetta tool chain | 最接近系统型相关工作；related work 必须提及 |
| Property-driven Protein Inverse Folding With Multi-Objective Preference Alignment | <https://arxiv.org/abs/2603.06748> | multi-objective preference alignment, developability objectives | 说明 `lambda_m` 目标权重和 developability 目标不是任意工程拼接 |
| ProteinGuide: Guide your favorite protein sequence generative model | <https://arxiv.org/abs/2505.04823> | plug-and-play property guidance, posterior objective | 支撑 property guidance 与 evidence-guided generation |
| ProteinZero: Self-Improving Protein Generation via Online Reinforcement Learning | <https://arxiv.org/abs/2506.07459> | online RL, proxy reward, diversity regularization | future extension；不要把 CEBRA-WP 写成 online RL |
| PDB-Struct: A Comprehensive Benchmark for Structure-based Protein Design | <https://arxiv.org/abs/2312.00080> | benchmark metrics, structure-quality evidence | 用于校准 `objective_score` 与 `evidence_sufficiency` 的实验讨论 |
| AlphaFold 3: Accurate structure prediction of biomolecular interactions | <https://www.nature.com/articles/s41586-024-07487-w> | binding/interface evidence, expensive complex prediction | 作为高价值 direct/proxy evidence 工具背景 |

## 4. 代码字段反查索引
<!-- SID:algo.theory_map.code_reverse_index -->

| 字段 / metadata | 理论对象 | 主要代码 | 文献桶 |
| --- | --- | --- | --- |
| `score_breakdown.overall` | $S_{\text{static}}$ | `src/agents/planner.py::_score_payload` | CMDP / utility |
| `score_breakdown.recovery_complexity`, `recoverability` | recovery cost / recoverability | `src/agents/candidate_generator/recovery_complexity.py` | workflow recovery |
| `metadata.candidate_feasibility` | $F_h$ | `src/agents/candidate_generator/generator.py` | CMDP / hard constraints |
| `metadata.posterior_objective` | $G_{\text{post}}$ | `src/adapters/objective_ranker_adapter.py`, `src/agents/candidate_generator/builder.py` | evidence-weighted objective |
| `metadata.runtime_adjustment` | $\Delta$、$U_\pi$ | `src/workflow/runtime_evaluator.py` | POMDP / runtime adaptation |
| `metadata.runtime_adjustment.action_bias` | $\operatorname{ActionBias}$ | `src/workflow/runtime_evaluator.py` | recovery policy |
| `metadata.topk_diversity` | $\operatorname{SelectDiverseTopK}$ | `src/agents/candidate_generator/generator.py` | diversity-aware Top-K |
| `ActionUtility.features` | $U_a$ | `src/workflow/action_features.py`, `src/workflow/runtime_evaluator.py` | intervention / recovery |
| `terminal_policy=stop` | protected stop | `src/workflow/recovery.py`, terminal stop builder | safety gating / workflow stop |
| `runtime_policy_ablation_group` | experiment group | `src/workflow/runtime_evaluator.py`, `docs/experiment/algorithm-group-paper-mapping.md` | evaluation methodology |

## 5. 写作边界

- 可以写：CEBRA-WP 受 POMDP belief-state planning 启发，维护低维 deterministic belief surrogate。
- 不应写：CEBRA-WP 学到了最优 POMDP policy 或严格 Bayesian posterior。
- 可以写：$F_h$ 是 CMDP-like hard feasibility gate，先于效用排序。
- 不应写：runtime adjustment 能覆盖 I/O、schema、安全等硬违规。
- 可以写：posterior objective 是 evidence-weighted computational score。
- 不应写：posterior objective 等价于湿实验验证。
- 可以写：AutoBinder Agent 是近期最接近的 binder agent 相关工作。
- 不应写：CEBRA-WP 与 AutoBinder 完全同类；CEBRA-WP 的重点是约束化、证据感知、恢复感知的工作流规划策略。
