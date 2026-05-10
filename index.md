# 毕业论文总索引

最后更新：2026-05-11（第七章草稿完成，84-run 数据已就绪）

## 章节总览

论文采用 8 章结构（详见 `drafts/final-term/toc-and-content-guide.md`）。当前 `final.tex` 仍为 7 章结构，后续需同步更新。

| 章 | LaTeX 文件 | 状态 | 说明 |
|---|---|---|---|
| 1 绪论 | `chapters/01-introduction.tex` | ❌ 占位符 | 仅 skeleton 3 行 |
| 2 相关技术与研究工作 | `chapters/02-related-work.tex` | ❌ 占位符 | 仅 skeleton 3 行 |
| 3 系统需求分析 | `chapters/03-system-requirements.tex` | 🟡 需拆分 | 素材在 Ch3 草稿 §3.1 |
| 4 系统总体设计 | `chapters/04-system-design.tex` | 🟡 需拆分 | 素材在 Ch3 草稿 §3.2–3.4 |
| 5 系统实现 | `chapters/05-system-implementation.tex` | ❌ 文件缺失 | 素材在 `implementation/` |
| 6 系统测试与验证 | `chapters/06-system-testing.tex` | ✅ 草稿完成 | ~20KB Markdown，13 TC 全覆盖 |
| 7 策略对比实验与结果分析 | `chapters/07-experiments.tex` | ✅ 草稿完成 | ~23KB Markdown，84-run 完整分析 |
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
| `sections/06-system-testing-and-validation.md` | **第六章草稿**（系统测试与验证，~20KB） | 第 6 章 | ⭐⭐⭐ 初稿，13 TC + 30 SV 全覆盖，证据引用完整 |
| `sections/07-experiments-and-analysis.md` | **第七章草稿**（策略对比实验与结果分析，~23KB） | 第 7 章 | ⭐⭐⭐ 初稿，84-run 四组消融完整分析 |
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

第 6 章可直接引用已有系统验证证据：

- `docs/system-validation/evidence-index.md` — 集中证据编号（18 张截图、8 个 API JSON、4 组 pytest、4 个 CLI、2 组 EventLog/Snapshot 样本）
- `docs/system-validation/test-case-table.md` — 13 个测试用例表（TC-S01 至 TC-S13）
- `docs/system-validation/system-validation-checklist.md` — SV-* 验证点覆盖矩阵

## 实验数据

第 7 章基于完整 84-run 矩阵：

- `docs/experiment/thesis-final-v1-results.md` — thesis-final-v1-001 结果分析（81/84 DONE，四组消融，机制增量 delta）

## 写作优先级

按数据依赖关系建议如下顺序：

| 优先级 | 章节 | 理由 |
|---|---|---|
| 🥇 1 | **第 6 章：系统测试与验证** | 不依赖 84-run；证据体系已建立（TC + EVD + FIG）；可直接引用 |
| 🥈 2 | **第 3+4 章：需求分析 + 总体设计** | ✅ 草稿已完成（32KB），需拆分为两章并转 LaTeX |
| 🥉 3 | **第 5 章：系统实现** | 素材充足（`implementation/` 6 文件），需压缩改写 |
| 4 | **第 1 章：绪论** | 需在论文主体成形后凝练 |
| 5 | **第 2 章：相关技术与研究工作** | 可在系统章节后写，便于引用具体技术选型 |
| 6 | **第 7 章：策略对比实验与结果分析** | ✅ 草稿已完成（84-run 完整数据） |
| 7 | **第 5 章：系统实现** | 素材充足（`implementation/` 6 文件），需压缩改写 |
| 8 | **第 1 章：绪论** | 需在论文主体成形后凝练 |
| 9 | **第 2 章：相关技术与研究工作** | 可在系统章节后写 |
| 10 | **第 8 章：总结与展望** | 最后写 |

## 下一步行动

1. **优先**：根据 `toc-and-content-guide.md` 第 6 章提纲，写系统测试与验证草稿
2. **并行**：将 Ch3 草稿拆分为第 3 章（需求分析）和第 4 章（总体设计），转 LaTeX
3. **并行**：压缩 `implementation/` 素材 → 第 5 章系统实现草稿
4. **等待**：84-run 完成后 → 第 7 章实验
5. **最后**：绪论、相关技术、总结、同步更新 `final.tex` 为 8 章结构
