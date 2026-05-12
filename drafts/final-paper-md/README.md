# 终稿 Markdown 工作区

本目录用于撰写毕业论文终稿的 Markdown 版本。它不是新的草稿池，而是从 `drafts/final-term/` 中已经确认的章节草稿、图表计划、参考文献清单，以及设计仓库和实现仓库中的可核实材料，整理得到的“可复制到 Word 的最终成稿”。

## 目录定位

- `drafts/final-term/`：保留为草稿、规划、图表安排和中间整理材料。
- `drafts/final-paper-md/`：面向终稿正文，章节表达应尽量接近可提交论文。
- `paper/figures/`：终稿图表源文件与导出文件的统一位置。
- `../thesis-project.design/`：系统设计、算法定义、架构依据的优先来源。
- `../thesis-project.dev/`：实现状态、验证材料、运行证据和实验材料的优先来源。

## 文件说明

| 文件 | 用途 |
|---|---|
| `00-writing-rules.md` | 终稿写作规则、术语、引用、图表和证据边界。后续章节应优先遵守该文件。 |
| `01-title-abstract-keywords.md` | 题目、摘要、关键词。 |
| `02-introduction.md` | 绪论。 |
| `03-related-work.md` | 相关技术与理论基础。 |
| `04-requirements-analysis.md` | 需求分析。 |
| `05-system-design.md` | 系统设计。 |
| `06-system-implementation.md` | 系统实现。 |
| `07-testing-validation.md` | 系统测试与验证。 |
| `08-experiments-analysis.md` | 实验与结果分析。 |
| `09-conclusion.md` | 总结与展望。 |
| `figures.md` | 终稿图表清单、图号、图题、路径与插入位置。 |
| `tables.md` | 终稿表格、代码清单和证据索引，供后续正文写作选择使用。 |
| `references.md` | 与当前 Word 终稿同步的文末参考文献列表；BibTeX 引用键回查 `paper/bib/references.bib`。 |
| `appendix/` | 验证截图说明、补充表格和不适合放入正文的附录材料。 |

## 写作流程

1. 先查看 `00-writing-rules.md`，确认术语、章节口吻、图表引用和参考文献引用方式。
2. 写某一章前，先查看 `drafts/final-term/sections/` 中对应草稿，再回查设计与实现依据。
3. 正文中需要引用文献时，优先保持当前 Word 终稿中的编号引用；若继续使用 BibTeX 引用键，可回查 `paper/bib/references.bib`。
4. 正文中需要插图时，使用 `figures.md` 中固定的图号和图题，不临时新增图号。
5. 正文中需要表格或代码清单时，先查看 `tables.md`，确认表号、标题、来源和结论边界。
6. 每章写完后检查三件事：是否有无依据断言，是否所有“如图/如表所示”都有对应图表，是否所有 `[@...]` 都能在 `references.md` 找到。

## 证据边界

终稿写作只整理已有事实，不补造结论。对于系统能力，应区分“设计目标”“已实现功能”“验证通过的行为”和“实验观察结果”。对于蛋白质设计效果，只能表述为计算流程、工具输出、结构化评分或工程验证结论，不扩展为未经湿实验确认的生物学结论。
