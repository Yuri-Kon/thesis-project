# 毕业论文总索引

最后更新：2026-05-11（第五、六、七章草稿完成，下一阶段转入结构拆分与 LaTeX 同步）

## 章节总览

论文采用 8 章结构（详见 `drafts/final-term/toc-and-content-guide.md`）。当前 `final.tex` 仍为 7 章结构，后续需同步更新。

| 章 | LaTeX 文件 | 状态 | 说明 |
|---|---|---|---|
| 1 绪论 | `chapters/01-introduction.tex` | ❌ 占位符 | 仅 skeleton 3 行 |
| 2 相关技术与研究工作 | `chapters/02-related-work.tex` | ❌ 占位符 | 仅 skeleton 3 行 |
| 3 系统需求分析 | `chapters/03-system-requirements.tex` | 🟡 需拆分 | 素材在 Ch3 草稿 §3.1 |
| 4 系统总体设计 | `chapters/04-system-design.tex` | 🟡 需拆分 | 素材在 Ch3 草稿 §3.2–3.4 |
| 5 系统实现 | `chapters/05-system-implementation.tex` | ✅ 草稿完成 | ~21KB Markdown，覆盖技术栈/API/前端/Workflow/CEBRA-WP/适配器 |
| 6 系统测试与验证 | `chapters/06-system-testing.tex` | ✅ Markdown 草稿完成 | `sections/06-system-testing-and-validation.md`，约 20KB，13 TC + 30 SV 全覆盖 |
| 7 策略对比实验与结果分析 | `chapters/07-experiments.tex` | ✅ Markdown 草稿完成 | `sections/07-experiments-and-analysis.md`，约 23KB，84-run 四组消融完整分析 |
| 8 总结与展望 | `chapters/08-conclusion.tex` | ❌ 占位符 | 最后写 |

## 已有草稿内容

`drafts/final-term/` 下存在 Markdown 草稿，语言为中文，可直接作为 LaTeX 写作素材：

| 草稿文件 | 内容 | 对应章节 | 质量 |
|---|---|---|---|
| `sections/01-requirements-analysis.md` | 需求分析素材（已被整合章节替代） | 第 3 章 | 原始素材 |
| `sections/02-overall-architecture.md` | 总体架构素材（已被整合章节替代） | 第 3 章 | 原始素材 |
| `sections/03-module-design.md` | 模块设计素材（已被整合章节替代） | 第 3 章 | 原始素材 |
| `sections/03-system-requirements-and-design.md` | 第三章完整草稿（需求+架构+模块+CEBRA-WP），32KB，修正稿 | 第 3+4 章 | ⭐⭐⭐ 需按新结构拆分为两章 |
| `toc-and-content-guide.md` | **8 章目录结构与内容指示**（含详细小节标题、篇幅建议、证据引用、图表清单、写作状态） | 全局 | 规划文档 |
| `sections/05-system-implementation.md` | **第五章草稿**（系统实现，~21KB） | 第 5 章 | ⭐⭐⭐ 初稿完成，待转 LaTeX |
| `sections/06-system-testing-and-validation.md` | **第六章草稿**（系统测试与验证，~20KB） | 第 6 章 | ⭐⭐⭐ 初稿完成，待转 LaTeX |
| `sections/07-experiments-and-analysis.md` | **第七章草稿**（策略对比实验与结果分析，~23KB） | 第 7 章 | ⭐⭐⭐ 初稿完成，84-run 结果已落入正文叙事，待转 LaTeX |
| `implementation/03-frontend-workbench-implementation.md` | React 工作台、页面结构 | 第 4 章 | ⭐⭐ 素材，需压缩 |
| `implementation/04-workflow-runtime-implementation.md` | Workflow、PlanRunner、StepRunner、RuntimeState | 第 4 章 | ⭐⭐ 素材，需压缩 |
| `implementation/05-code-snippets.md` | 关键代码片段 | 第 4 章 | ⭐ 辅助 |
| `implementation/06-figure-placeholders.md` | 截图/图表占位清单 | 第 4/5 章 | ⭐ 辅助 |

## 设计文档与实验数据

第 3-7 章按需回查：

- `../thesis-project.design/docs/design/architecture.md` — 整体架构
- `../thesis-project.design/docs/design/system-implementation-design.md` — 系统实现设计
- `../thesis-project.dev/AGENTS.md` — 实现约束与模块范围
- `../thesis-project.dev/docs/experiment/thesis-final-v1-results.md` — **84-run 完整实验结果**
- `../thesis-project.dev/docs/experiment/final-thesis-experiment-design.md` — 实验设计方案

## 系统验证证据

第 6 章已基于以下系统验证证据完成 Markdown 草稿，后续转 LaTeX 时继续引用：

- `docs/system-validation/evidence-index.md` — 集中证据编号（18 张截图、8 个 API JSON、4 组 pytest、4 个 CLI、2 组 EventLog/Snapshot 样本）
- `docs/system-validation/test-case-table.md` — 13 个测试用例表（TC-S01 至 TC-S13）
- `docs/system-validation/system-validation-checklist.md` — SV-* 验证点覆盖矩阵

## 实验数据

第 7 章已基于完整 84-run 矩阵完成 Markdown 草稿：

- `docs/experiment/thesis-final-v1-results.md` — thesis-final-v1-001 结果分析（81/84 DONE，四组消融，机制增量 delta）

## 写作优先级

按数据依赖关系建议如下顺序：

| 优先级 | 章节 | 理由 |
|---|---|---|
| 🥇 1 | **第 3+4 章：需求分析 + 总体设计** | Ch3 合并草稿已完成（约 32KB），当前最需要按 8 章结构拆分并转 LaTeX |
| 🥈 2 | **第 5+6+7 章：实现、测试与实验** | Markdown 草稿均已完成，下一步是校准图表编号、表格题注和证据引用格式并转 LaTeX |
| 🥉 3 | **LaTeX 结构同步** | `final.tex` 仍为 7 章结构，需要同步为 8 章并新增章节入口 |
| 4 | **第 1 章：绪论** | 需在系统、实验主线定型后凝练问题背景、贡献点和论文结构 |
| 5 | **第 2 章：相关技术与研究工作** | 可围绕已定型的系统机制补写相关工作，避免泛泛综述 |
| 6 | **第 8 章：总结与展望** | 最后写，需承接第 6、7 章结论和限制 |

## 下一步行动

1. **优先**：将 `sections/03-system-requirements-and-design.md` 拆分为第 3 章（系统需求分析）和第 4 章（系统总体设计），并转入对应 LaTeX 文件。
2. **整理**：为第 5、6、7 章补齐图表编号、表格题注和证据引用格式，然后转入对应 LaTeX 文件。
3. **结构同步**：将 `paper/tex/stages/final.tex` 从当前 7 章结构同步为 8 章结构，新增第 3、4、5、6、7、8 章文件入口。
4. **构建验证**：完成 LaTeX 结构同步后运行终稿编译，集中处理交叉引用、图表路径和中文排版问题。
5. **最后**：补写绪论、相关技术、总结与展望，并统一摘要、关键词、术语和参考文献。
