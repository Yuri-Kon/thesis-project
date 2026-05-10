# 论文参考文献汇总

> 整理自设计文档与论文草稿 · 2026-05-11

## 一、理论方法类

| 编号 | 作者/标题 | 出版信息 | 链接 | 论文中使用场景 |
|------|----------|---------|------|--------------|
| R01 | Kaelbling, L.P., Littman, M.L., Cassandra, A.R. *Planning and Acting in Partially Observable Stochastic Domains*. 1998 | Artificial Intelligence, 101(1-2):99-134 | https://doi.org/10.1016/S0004-3702(98)00023-X | Lite belief-state 设计的理论依据 |
| R02 | Shani, G. *Heuristics for Partially Observable Stochastic Contingent Planning*. 2024 | arXiv | https://arxiv.org/abs/2410.05870 | 部分可观测规划中启发式需显式考虑随机效应 |
| R03 | Carrara, N. et al. *Budgeted Reinforcement Learning in Continuous State Space*. 2019 | NeurIPS | https://arxiv.org/abs/1903.01004 | 预算约束和风险约束应被视为一等决策量 |
| R04 | Schick, T. et al. *Toolformer: Language Models Can Teach Themselves to Use Tools*. 2023 | arXiv | https://arxiv.org/abs/2302.04761 | "何时调用工具"也是决策的一部分 |
| R05 | Yao, S. et al. *ReAct: Synergizing Reasoning and Acting in Language Models*. 2022 | arXiv | https://arxiv.org/abs/2210.03629 | 外部基线对照：ReAct-style 单轨迹代理 |
| R06 | Yao, S. et al. *Tree of Thoughts: Deliberate Problem Solving with Large Language Models*. 2023 | arXiv | https://arxiv.org/abs/2305.10601 | 外部基线对照 + Top-K diversity 保留多候选 |
| R07 | Shinn, N. et al. *Reflexion: Language Agents with Verbal Reinforcement Learning*. 2023 | arXiv | https://arxiv.org/abs/2303.11366 | 外部基线对照 + 利用失败反馈形成结构化恢复 |
| R08 | Xie, T. et al. *OSWorld: Benchmarking Multimodal Agents for Open-Ended Tasks in Real Computer Environments*. 2024 | arXiv | https://arxiv.org/abs/2404.07972 | 执行结果、恢复能力和外部环境稳健性评估 agent |
| R09 | Simmhan, Y. et al. *Reliable Data Pipelines Using Scientific Workflows*. 2009 | Microsoft Research | — | fail-fast、记录 provenance、recovery baked into workflow design |

## 二、蛋白质设计工具类

| 编号 | 作者/标题 | 出版信息 | 链接 | 论文中使用场景 |
|------|----------|---------|------|--------------|
| R10 | Jumper, J. et al. *Highly accurate protein structure prediction with AlphaFold*. 2021 | Nature, 596:583-589 | https://doi.org/10.1038/s41586-021-03819-2 | 结构预测核心工具，第 2 章 |
| R11 | Abramson, J. et al. *Accurate structure prediction of biomolecular interactions with AlphaFold 3*. 2024 | Nature, 630:493-500 | https://www.nature.com/articles/s41586-024-07487-w | 高代价 direct/proxy evidence 工具背景 |
| R12 | Lin, Z. et al. *Evolutionary-scale prediction of atomic-level protein structure with a language model*. 2023 | Science, 379:1123-1130 | https://doi.org/10.1126/science.ade2574 | ESMFold 工具，第 2/5 章 |
| R13 | Dauparas, J. et al. *Robust deep learning-based protein sequence design using ProteinMPNN*. 2022 | Science, 378:49-56 | https://doi.org/10.1126/science.add2187 | 序列设计核心工具，第 2/5 章 |
| R14 | Ferruz, N. et al. *ProtGPT2 is a deep unsupervised language model for protein design*. 2022 | Nature Communications, 13:4348 | https://doi.org/10.1038/s41467-022-32007-7 | 序列生成工具，第 2/5 章 |
| R15 | Watson, J.L. et al. *De novo design of protein structure and function with RFdiffusion*. 2023 | Nature, 620:1089-1100 | https://doi.org/10.1038/s41586-023-06415-8 | 扩散模型背景，第 1/2 章 |
| R16 | Ahdritz, G. et al. *OpenFold: Retraining AlphaFold2 yields new insights into its learning mechanisms and capacity for generalization*. 2024 | Nature Methods | https://doi.org/10.1038/s41592-024-02272-z | 结构预测工具，第 2/5 章 |

## 三、蛋白质设计前沿相关系统

| 编号 | 作者/标题 | 出版信息 | 链接 | 论文中使用场景 |
|------|----------|---------|------|--------------|
| R17 | *RosettaSearch: Multi-Objective Inference-Time Search for Protein Sequence Design* | 2026, arXiv | https://arxiv.org/abs/2604.17175 | 相关工作对比：workflow-level reranking vs sequence-level search |
| R18 | *AutoBinder Agent: An MCP-Based Agent for End-to-End Protein Binder Design* | 2026, arXiv | https://arxiv.org/abs/2602.00019 | 最接近系统型相关工作，related work 必须提及 |
| R19 | *Property-driven Protein Inverse Folding With Multi-Objective Preference Alignment* | 2026, arXiv | https://arxiv.org/abs/2603.06748 | lambda_m 目标权重和 developability 工程化依据 |
| R20 | *ProteinGuide: Guide your favorite protein sequence generative model* | 2025, arXiv | https://arxiv.org/abs/2505.04823 | property guidance 与 evidence-guided generation |
| R21 | *ProteinZero: Self-Improving Protein Generation via Online Reinforcement Learning* | 2025, arXiv | https://arxiv.org/abs/2506.07459 | 未来扩展方向（不要把 CEBRA-WP 写成 online RL） |
| R22 | *PDB-Struct: A Comprehensive Benchmark for Structure-based Protein Design* | 2023, arXiv | https://arxiv.org/abs/2312.00080 | 校准 objective_score 与 evidence_sufficiency 讨论 |

## 四、蛋白质设计平台

| 编号 | 作者/标题 | 出版信息 | 链接 | 论文中使用场景 |
|------|----------|---------|------|--------------|
| R23 | Leaver-Fay, A. et al. *ROSETTA3: an object-oriented software suite for the simulation and design of macromolecules*. 2011 | Methods in Enzymology, 487:545-574 | — | 固定流水线平台对比，第 1/2 章 |
| R24 | Cock, P.J.A. et al. *Biopython: freely available Python tools for biological computation*. 2009 | Bioinformatics, 25(11):1422-1423 | https://doi.org/10.1093/bioinformatics/btp163 | BioPython 工具背景 |

## 五、科学工作流与系统工程

| 编号 | 作者/标题 | 出版信息 | 链接 | 论文中使用场景 |
|------|----------|---------|------|--------------|
| R25 | Deelman, E. et al. *Pegasus: A framework for mapping complex scientific workflows onto distributed systems*. 2005 | Scientific Programming, 13(3):219-237 | — | 科学工作流引擎对比，第 2 章 |
| R26 | Di Tommaso, P. et al. *Nextflow enables reproducible computational workflows*. 2017 | Nature Biotechnology, 35:316-319 | https://doi.org/10.1038/nbt.3820 | Nextflow 引擎，单步执行后端边界，第 2/5 章 |

---

## 引用建议

| 优先级 | 编号 | 理由 |
|--------|------|------|
| 🔴 必引 | R01-R03, R10-R16 | 理论基石 + 核心工具 |
| 🔴 必引 | R17-R19 | 最相关的前沿系统对比 |
| 🟡 建议引 | R04-R09 | Agent/工作流范式背景 |
| 🟡 建议引 | R20-R22 | 蛋白质设计前沿补充 |
| 🟢 可选 | R23-R26 | 平台/工具背景 |
