# 终稿参考文献与引用键

本文档整理自 `drafts/final-term/reference-list.md`，用于 `drafts/final-paper-md/` 各章写作。正文中统一使用 `[@key]` 形式引用，例如 `[@kaelbling1998pomdp]`；同一句引用多篇文献时写作 `[@yao2022react; @yao2023tot]`。

进入 Word 定稿阶段时，可以保留这些引用键作为检索标记，再统一替换为学校要求的顺序编码引用格式。

## 一、理论方法类

| 原编号 | 引用键 | 参考文献 | 使用场景 |
|---|---|---|---|
| R01 | `[@kaelbling1998pomdp]` | Kaelbling, L. P., Littman, M. L., & Cassandra, A. R. (1998). *Planning and Acting in Partially Observable Stochastic Domains*. Artificial Intelligence, 101(1-2), 99-134. https://doi.org/10.1016/S0004-3702(98)00023-X | Lite belief-state 与部分可观测规划理论依据。 |
| R02 | `[@shani2024heuristics]` | Shani, G. (2024). *Heuristics for Partially Observable Stochastic Contingent Planning*. arXiv. https://arxiv.org/abs/2410.05870 | 部分可观测规划中启发式和随机效应处理依据。 |
| R03 | `[@carrara2019budgetedrl]` | Carrara, N., et al. (2019). *Budgeted Reinforcement Learning in Continuous State Space*. NeurIPS. https://arxiv.org/abs/1903.01004 | 预算约束、风险约束和资源感知决策依据。 |
| R04 | `[@schick2023toolformer]` | Schick, T., et al. (2023). *Toolformer: Language Models Can Teach Themselves to Use Tools*. arXiv. https://arxiv.org/abs/2302.04761 | LLM 工具调用和“何时调用工具”的背景。 |
| R05 | `[@yao2022react]` | Yao, S., et al. (2022). *ReAct: Synergizing Reasoning and Acting in Language Models*. arXiv. https://arxiv.org/abs/2210.03629 | ReAct-style 单轨迹 Agent 基线。 |
| R06 | `[@yao2023tot]` | Yao, S., et al. (2023). *Tree of Thoughts: Deliberate Problem Solving with Large Language Models*. arXiv. https://arxiv.org/abs/2305.10601 | 多候选思维树、Top-K 多样性与外部基线。 |
| R07 | `[@shinn2023reflexion]` | Shinn, N., et al. (2023). *Reflexion: Language Agents with Verbal Reinforcement Learning*. arXiv. https://arxiv.org/abs/2303.11366 | 失败反馈、结构化恢复和反思式 Agent 对照。 |
| R08 | `[@xie2024osworld]` | Xie, T., et al. (2024). *OSWorld: Benchmarking Multimodal Agents for Open-Ended Tasks in Real Computer Environments*. arXiv. https://arxiv.org/abs/2404.07972 | 开放环境中 Agent 执行、恢复和稳健性评估背景。 |
| R09 | `[@simmhan2009reliable]` | Simmhan, Y., et al. (2009). *Reliable Data Pipelines Using Scientific Workflows*. Microsoft Research. | 科学工作流中的 fail-fast、provenance 和恢复设计依据。 |

## 二、蛋白质设计工具类

| 原编号 | 引用键 | 参考文献 | 使用场景 |
|---|---|---|---|
| R10 | `[@jumper2021alphafold]` | Jumper, J., et al. (2021). *Highly accurate protein structure prediction with AlphaFold*. Nature, 596, 583-589. https://doi.org/10.1038/s41586-021-03819-2 | AlphaFold 与结构预测背景。 |
| R11 | `[@abramson2024alphafold3]` | Abramson, J., et al. (2024). *Accurate structure prediction of biomolecular interactions with AlphaFold 3*. Nature, 630, 493-500. https://www.nature.com/articles/s41586-024-07487-w | 高代价 direct/proxy evidence 工具背景。 |
| R12 | `[@lin2023esmfold]` | Lin, Z., et al. (2023). *Evolutionary-scale prediction of atomic-level protein structure with a language model*. Science, 379, 1123-1130. https://doi.org/10.1126/science.ade2574 | ESMFold 结构预测工具背景。 |
| R13 | `[@dauparas2022proteinmpnn]` | Dauparas, J., et al. (2022). *Robust deep learning-based protein sequence design using ProteinMPNN*. Science, 378, 49-56. https://doi.org/10.1126/science.add2187 | ProteinMPNN 序列设计工具背景。 |
| R14 | `[@ferruz2022protgpt2]` | Ferruz, N., et al. (2022). *ProtGPT2 is a deep unsupervised language model for protein design*. Nature Communications, 13, 4348. https://doi.org/10.1038/s41467-022-32007-7 | ProtGPT2 序列生成工具背景。 |
| R15 | `[@watson2023rfdiffusion]` | Watson, J. L., et al. (2023). *De novo design of protein structure and function with RFdiffusion*. Nature, 620, 1089-1100. https://doi.org/10.1038/s41586-023-06415-8 | 扩散模型和 de novo 蛋白设计背景。 |
| R16 | `[@ahdritz2024openfold]` | Ahdritz, G., et al. (2024). *OpenFold: Retraining AlphaFold2 yields new insights into its learning mechanisms and capacity for generalization*. Nature Methods. https://doi.org/10.1038/s41592-024-02272-z | OpenFold 结构预测工具和实现背景。 |

## 三、蛋白质设计前沿相关系统

| 原编号 | 引用键 | 参考文献 | 使用场景 |
|---|---|---|---|
| R17 | `[@rosettasearch2026]` | *RosettaSearch: Multi-Objective Inference-Time Search for Protein Sequence Design*. (2026). arXiv. https://arxiv.org/abs/2604.17175 | 相关工作对比：序列层搜索与本文工作流层重排序的差异。 |
| R18 | `[@autobinder2026]` | *AutoBinder Agent: An MCP-Based Agent for End-to-End Protein Binder Design*. (2026). arXiv. https://arxiv.org/abs/2602.00019 | 最接近的系统型相关工作之一。 |
| R19 | `[@preferenceinversefolding2026]` | *Property-driven Protein Inverse Folding With Multi-Objective Preference Alignment*. (2026). arXiv. https://arxiv.org/abs/2603.06748 | 多目标偏好、目标权重和 developability 工程化讨论。 |
| R20 | `[@proteinguide2025]` | *ProteinGuide: Guide your favorite protein sequence generative model*. (2025). arXiv. https://arxiv.org/abs/2505.04823 | property guidance 与 evidence-guided generation 背景。 |
| R21 | `[@proteinzero2025]` | *ProteinZero: Self-Improving Protein Generation via Online Reinforcement Learning*. (2025). arXiv. https://arxiv.org/abs/2506.07459 | 未来扩展方向；注意不要把 CEBRA-WP 写成 online RL。 |
| R22 | `[@pdbstruct2023]` | *PDB-Struct: A Comprehensive Benchmark for Structure-based Protein Design*. (2023). arXiv. https://arxiv.org/abs/2312.00080 | objective score、evidence sufficiency 和结构设计基准讨论。 |

## 四、蛋白质设计平台

| 原编号 | 引用键 | 参考文献 | 使用场景 |
|---|---|---|---|
| R23 | `[@leaverfay2011rosetta3]` | Leaver-Fay, A., et al. (2011). *ROSETTA3: an object-oriented software suite for the simulation and design of macromolecules*. Methods in Enzymology, 487, 545-574. | 传统蛋白设计平台和固定流程对比。 |
| R24 | `[@cock2009biopython]` | Cock, P. J. A., et al. (2009). *Biopython: freely available Python tools for biological computation*. Bioinformatics, 25(11), 1422-1423. https://doi.org/10.1093/bioinformatics/btp163 | BioPython 工具和工程实现背景。 |

## 五、科学工作流与系统工程

| 原编号 | 引用键 | 参考文献 | 使用场景 |
|---|---|---|---|
| R25 | `[@deelman2005pegasus]` | Deelman, E., et al. (2005). *Pegasus: A framework for mapping complex scientific workflows onto distributed systems*. Scientific Programming, 13(3), 219-237. | 科学工作流引擎与可复现执行背景。 |
| R26 | `[@ditommaso2017nextflow]` | Di Tommaso, P., et al. (2017). *Nextflow enables reproducible computational workflows*. Nature Biotechnology, 35, 316-319. https://doi.org/10.1038/nbt.3820 | Nextflow、可复现计算流程和单步执行后端边界。 |

## 六、按章节引用建议

| 章节 | 建议引用 |
|---|---|
| 第 2 章 绪论 | `[@jumper2021alphafold]`、`[@watson2023rfdiffusion]`、`[@schick2023toolformer]`、`[@yao2022react]` |
| 第 3 章 相关技术与理论基础 | `[@kaelbling1998pomdp]`、`[@shani2024heuristics]`、`[@carrara2019budgetedrl]`、`[@jumper2021alphafold]`、`[@lin2023esmfold]`、`[@dauparas2022proteinmpnn]`、`[@ditommaso2017nextflow]` |
| 第 4 章 需求分析 | `[@deelman2005pegasus]`、`[@ditommaso2017nextflow]`、`[@xie2024osworld]` |
| 第 5 章 系统设计 | `[@kaelbling1998pomdp]`、`[@shani2024heuristics]`、`[@carrara2019budgetedrl]`、`[@yao2023tot]`、`[@shinn2023reflexion]` |
| 第 6 章 系统实现 | `[@cock2009biopython]`、`[@dauparas2022proteinmpnn]`、`[@lin2023esmfold]`、`[@ferruz2022protgpt2]`、`[@ahdritz2024openfold]` |
| 第 7 章 系统测试与验证 | `[@simmhan2009reliable]`、`[@xie2024osworld]` |
| 第 8 章 实验与结果分析 | `[@yao2022react]`、`[@yao2023tot]`、`[@shinn2023reflexion]`、`[@rosettasearch2026]`、`[@autobinder2026]`、`[@preferenceinversefolding2026]` |
| 第 9 章 总结与展望 | `[@proteinguide2025]`、`[@proteinzero2025]`、`[@pdbstruct2023]` |

## 七、引用注意事项

- 优先引用原始论文或工具论文，不用泛泛的博客、新闻或二手材料替代。
- 2025 年以后 arXiv 论文在正文中应谨慎表述为“近期预印本”或“相关预印本”。
- 对 CEBRA-WP 的理论依据可引用部分可观测规划、预算约束决策和 Agent 恢复相关文献，但不要将其表述为这些方法的直接复现。
- 对蛋白质工具的引用应服务于“工具链背景”和“系统集成依据”，不要据此宣称本文完成湿实验验证。
