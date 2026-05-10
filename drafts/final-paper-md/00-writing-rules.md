# 终稿 Markdown 写作规范

本文档是 `drafts/final-paper-md/` 后续章节撰写的直接规则。若章节草稿、历史规划和本文件不一致，优先按本文件执行；若本文件与设计仓库或实现仓库的事实不一致，必须回查真源后修正本文件。

## 1. 总体原则

论文终稿应使用正式、克制、可追溯的中文学术表达。不要使用产品宣传式措辞，不把规划中的能力写成已经完成的功能，不把计算验证结果扩大为生物学实验结论。

写作时按以下优先级取信：

1. 用户本轮明确说明。
2. 本目录终稿 Markdown 和 `drafts/final-term/` 已确认草稿。
3. `../thesis-project.design/` 中的设计文档与架构文档。
4. `../thesis-project.dev/` 中的实现、测试、验证和实验材料。
5. `resources/` 中整理的进展、摘要和验证材料。

所有章节都应区分四类表述：

- “设计目标”：系统希望支持的能力。
- “设计方案”：架构、算法、数据结构和流程。
- “实现状态”：代码中已经落地的模块、接口、页面和运行机制。
- “验证结果”：测试、截图、实验表格或运行记录能够支持的结论。

## 2. 章节定位

文件名前缀只用于排序，不等同于最终论文章号。终稿正文建议按“第一章 绪论、第二章 相关技术与理论基础、第三章 需求分析、第四章 系统设计、第五章 系统实现、第六章 系统测试与验证、第七章 实验与结果分析、第八章 总结与展望”组织。

| 文件 | 章节定位 | 写作重点 |
|---|---|---|
| `01-title-abstract-keywords.md` | 摘要与关键词 | 概括问题、方法、系统、验证和结果，不展开实现细节。 |
| `02-introduction.md` | 第一章 绪论 | 说明研究背景、问题、目标、主要工作和论文结构。 |
| `03-related-work.md` | 第二章 相关技术与理论基础 | 梳理蛋白质设计工具、科学工作流、LLM Agent 和部分可观测规划依据。 |
| `04-requirements-analysis.md` | 第三章 需求分析 | 写清业务需求、功能需求、非功能需求、约束和问题-方案对应关系。 |
| `05-system-design.md` | 第四章 系统设计 | 写清整体架构、数据模型、状态机、工作流和 CEBRA-WP 算法定义。 |
| `06-system-implementation.md` | 第五章 系统实现 | 写实现落点、模块协作、运行链路和关键工程机制。 |
| `07-testing-validation.md` | 第六章 系统测试与验证 | 写测试目标、测试用例、验证证据、通过情况和限制。 |
| `08-experiments-analysis.md` | 第七章 实验与结果分析 | 写实验设计、任务、对照组、指标、表格结果和分析。 |
| `09-conclusion.md` | 第八章 总结与展望 | 总结已完成工作、限制和后续方向。 |

## 3. 术语统一

正文首次出现英文缩写时，统一采用“中文名称（英文全称，英文缩写）”格式；后文直接使用缩写或已统一的中文术语。若术语没有稳定中文译名，可使用“英文全称（英文缩写）”。摘要、正文、图注和表注可视为相对独立部分，若同一缩写在不同部分首次出现，按需要重新说明。不要为只出现一两次且不影响阅读的术语强行设置缩写。

示例：

- 大语言模型 Agent（Large Language Model Agent，LLM Agent）
- 人在环决策（Human-in-the-loop，HITL）
- 有限状态机（Finite State Machine，FSM）
- 约束与证据感知、信念引导、恢复自适应工作流规划（Constraint- and Evidence-aware Belief-guided Recovery-adaptive Workflow Planning，CEBRA-WP）

后文保持同一写法，不在“中文全称、英文全称、缩写”之间来回切换。

| 推荐写法 | 说明 |
|---|---|
| 蛋白质设计工作流 | 泛指从任务输入到候选方案输出、执行、评估和恢复的流程。 |
| 大语言模型 Agent（Large Language Model Agent，LLM Agent） | 首次出现后可写 LLM Agent；不写成“智能体系统万能求解器”，强调其规划、调用工具和解释能力。 |
| ProteinToolKG | 面向蛋白质设计工具链的工具知识图谱实例，用于组织工具能力、输入输出、约束、成本和适用场景。 |
| 有限状态机（Finite State Machine，FSM） | 首次出现后可写 FSM；用于约束执行、等待、恢复和终止。 |
| 人在环决策（Human-in-the-loop，HITL） | 首次出现后可写 HITL；表示需要人工确认、选择、审批或干预的运行时决策点。 |
| Lite belief-state / 轻量信念状态 | CEBRA-WP 中用于刻画成功概率、结构性失败风险、恢复余量、剩余成本和证据充分性的运行时状态向量。 |
| 约束与证据感知、信念引导、恢复自适应工作流规划（Constraint- and Evidence-aware Belief-guided Recovery-adaptive Workflow Planning，CEBRA-WP） | 首次出现后可写 CEBRA-WP；定位为工作流层规划、重排序和恢复控制算法。 |
| 候选工作流 / candidate workflow | 由任务目标、约束、工具知识和历史状态生成的可执行或待筛选工作流方案。 |
| 硬可行性约束 | 工具、模式、输入输出、安全、硬预算和可用性等必须满足的约束。 |
| 恢复动作 | 包括 `continue`、`patch_local`（局部修补）、`suffix_replan`（后缀重规划）和 `stop`（终止型重规划候选）。 |
| Biopython | 不写作 BioPython；工具能力或适配器可写 Biopython QC。 |

避免使用：

- “证明蛋白质有效”“验证生物学功能”等未经湿实验支持的表述。
- “完全自动化”“通用最优”“显著优于所有方法”等过度结论。
- “系统一定能够”“模型必然选择”等确定性过强的表达。

## 4. 算法写作规则

CEBRA-WP 必须作为第四章系统设计中的独立算法定义出现，不能只散落在工作流描述里。算法定义应至少包括：

- 问题输入：目标 `g`、约束集合 `C`、ProteinToolKG `K`、历史 `h_t`、观测 `o_t` 和 Lite belief-state / 轻量信念状态 `x_t`。
- 候选生成：`GenerateCandidates(g, C, K, h_t)`。
- 硬可行性筛选：工具、schema、输入输出、安全、硬预算和可用性约束均满足后才可进入自动执行。
- 静态候选效用：综合可行性、目标匹配、成本、风险、恢复开销和解释质量。
- 轻量信念状态：至少包含 `p_success`、`p_structural_failure`、`recovery_margin`、`expected_remaining_cost`、`evidence_sufficiency`。
- 后验目标适配：基于 direct/proxy/degraded/missing 等证据状态调整目标匹配。
- 运行时重排序：运行时调整只改变已可行候选的排序，不绕过硬约束。
- 恢复动作：`continue`、`patch_local`、`suffix_replan`、`stop`，其中 `stop` 仍应映射为受 FSM 和 HITL 约束的终止候选。

公式可先保留 Markdown/LaTeX 混写形式，便于后续复制到 Word 公式编辑器。例如：

```tex
U_\pi(\pi, x_t) = clip(S_{static}(\pi) + \Delta(\pi, x_t), 0, 1)
```

算法描述应强调“面向工作流层的规划、重排序和恢复控制”，不要写成序列生成模型、在线强化学习或湿实验优化算法。

## 5. 图表引用规则

插图清单以 `figures.md` 为准，正式表格与代码清单以 `tables.md` 为准。正文引用必须满足三个条件：

1. 前文出现“如图 X-Y 所示”或“如表 X-Y 所示”。
2. 紧随其后或同一小节内给出对应图表的标题、路径或插入标记。
3. 图表之后必须有解释，说明该图表支持了什么论点。

推荐写法：

```md
如图 4-1 所示，系统采用五层分层架构，将输入层、智能规划层、执行层、安全与汇总层和资源层分离。

【图 4-1 系统五层分层架构】
插图文件：`paper/figures/system-architecture.drawio.svg`

图 4-1 强调了控制面与执行面的分离关系。其中，FSM 和 HITL 负责运行时边界控制，ProteinToolKG 负责为候选工作流生成与筛选提供工具约束。
```

不要出现：

- 只写“如下图所示”但没有图号。
- 提到“图 4-6”但 `figures.md` 中不存在，或提到“表 7-5”但 `tables.md` 中不存在。
- 图后没有解释，只把图当作装饰。
- 同一张图在不同章节重复编号。

代码片段在正文中称为“代码清单”。每个代码清单都必须说明它解决的实现问题、对应的设计点，以及是否有测试或实验材料支撑。不要把 `drafts/final-term/implementation/05-code-snippets.md` 中的片段原样全部复制进正文。

## 6. 参考文献引用规则

参考文献以 `references.md` 为准。正文使用 Markdown 引用键，格式为 `[@key]`。同一句需要多篇文献时使用 `[@key1; @key2]`。

示例：

```md
部分可观测规划认为，决策主体需要在观测不完整的条件下维护对环境状态的估计，并据此选择后续动作[@kaelbling1998pomdp]。
```

每章写完后必须检查：

- 所有 `[@...]` 都能在 `references.md` 中找到。
- 同一事实优先引用原始论文或设计文档中的真源，不用二手描述替代。
- 2025 年以后 arXiv 论文在正文中应称为“近期预印本”或“相关预印本”，不要写成稳定行业共识。

## 7. 章节推荐引用

| 章节 | 推荐引用 |
|---|---|
| 第一章 绪论 | `[@jumper2021alphafold]`、`[@watson2023rfdiffusion]`、`[@yao2022react]`、`[@schick2023toolformer]` |
| 第二章 相关技术与理论基础 | `[@kaelbling1998pomdp]`、`[@shani2024heuristics]`、`[@carrara2019budgetedrl]`、`[@jumper2021alphafold]`、`[@dauparas2022proteinmpnn]`、`[@lin2023esmfold]`、`[@ditommaso2017nextflow]` |
| 第三章 需求分析 | `[@deelman2005pegasus]`、`[@ditommaso2017nextflow]`、`[@xie2024osworld]` |
| 第四章 系统设计 | `[@kaelbling1998pomdp]`、`[@shani2024heuristics]`、`[@carrara2019budgetedrl]`、`[@yao2023tot]`、`[@shinn2023reflexion]` |
| 第五章 系统实现 | `[@cock2009biopython]`、`[@dauparas2022proteinmpnn]`、`[@lin2023esmfold]`、`[@ferruz2022protgpt2]`、`[@ahdritz2024openfold]` |
| 第六章 系统测试与验证 | `[@simmhan2009reliable]`、`[@xie2024osworld]` |
| 第七章 实验与结果分析 | `[@yao2022react]`、`[@yao2023tot]`、`[@shinn2023reflexion]`、`[@rosettasearch2026]`、`[@autobinder2026]`、`[@preferenceinversefolding2026]` |
| 第八章 总结与展望 | `[@proteinguide2025]`、`[@proteinzero2025]`、`[@pdbstruct2023]` |

## 8. 表述强度

使用“本文设计了”“系统实现了”“实验观察到”“验证结果表明”等有边界的表达。

可以写：

- “实验结果表明，在本文设置的任务和指标下，CEBRA-WP 相比单轨迹基线具有更稳定的恢复表现。”
- “该结果说明运行时重排序机制有助于降低结构性失败后的恢复成本。”
- “系统验证覆盖了登录、任务创建、候选生成、执行推进、HITL 决策和审计记录等核心路径。”

不要写：

- “本系统解决了蛋白质设计的全部自动化问题。”
- “算法证明了候选蛋白具有真实生物功能。”
- “该方法在所有蛋白设计任务上均优于现有系统。”

## 9. Markdown 书写格式

- 每章使用一级标题作为章名，例如 `# 第四章 系统设计`。
- 小节使用二级和三级标题，不要跳级。
- 公式使用 fenced `tex` 代码块或独立 LaTeX 公式，后续再转 Word。
- 表格优先使用 Markdown 表格。
- 文件路径使用反引号，例如 `paper/figures/system-architecture.drawio.svg`。
- 章节内部保留图表插入标记，便于后续复制到 Word 时替换为真实图片。

## 10. 完稿检查清单

每个章节完成后检查：

- 术语是否与本文件一致。
- 是否存在未经依据支持的实现或实验结论。
- 是否所有图号、表号都能在 `figures.md` 或章节表格中找到。
- 是否所有引用键都能在 `references.md` 中找到。
- 是否区分了设计目标、实现状态和验证结果。
- 是否避免把计算流程结论扩大为湿实验结论。
