# 毕业论文总索引

最后更新：2026-05-10

## 章节总览

`paper/tex/stages/final.tex` 定义终稿结构为 7 章。下图标注每章当前状态：

| 章 | LaTeX 文件 | 状态 | 说明 |
|---|---|---|---|
| 摘要 | （内联于 final.tex） | ✅ 初稿 | 13 行中文摘要已完成 |
| 1 绪论 | `chapters/01-introduction.tex` | ❌ 占位符 | 仅 skeleton 3 行 |
| 2 相关技术 | `chapters/02-related-work.tex` | ❌ 占位符 | 仅 skeleton 3 行 |
| 3 系统需求与总体设计 | `chapters/03-system-requirements-and-design.tex` | ✅ 草稿完成 | 整合章节草稿 ~32KB（修正稿），5 图占位，待转为 LaTeX |
| 4 系统实现 | `chapters/04-system-implementation.tex` | ❌ 文件缺失 | final.tex 引用但文件不存在 |
| 5 系统测试与验证 | `chapters/05-system-testing-and-validation.tex` | ❌ 文件缺失 | final.tex 引用但文件不存在 |
| 6 实验设计与结果分析 | `chapters/06-experiments.tex` (旧名 `04-experiments.tex`) | ❌ 占位符 | 等待 84-run 完整结果 |
| 7 总结与展望 | `chapters/07-conclusion.tex` (旧名 `05-conclusion.tex`) | ❌ 占位符 | 仅 skeleton 3 行 |

> **注意**：现有目录中的 `03-method.tex`、`04-experiments.tex`、`05-conclusion.tex` 是中期报告遗留文件，final.tex 未引用。终稿使用新命名。

## 已有草稿内容

`drafts/final-term/` 下存在 Markdown 草稿，语言为中文，可直接作为 LaTeX 写作素材：

| 草稿文件 | 内容 | 对应章节 | 质量 |
|---|---|---|---|
| `sections/01-requirements-analysis.md` | 需求分析素材（已被整合章节替代） | 第 3 章 | 原始素材 |
| `sections/02-overall-architecture.md` | 总体架构素材（已被整合章节替代） | 第 3 章 | 原始素材 |
| `sections/03-module-design.md` | 模块设计素材（已被整合章节替代） | 第 3 章 | 原始素材 |
| `sections/03-system-requirements-and-design.md` | **第三章完整草稿**（需求+架构+模块+CEBRA-WP） | 第 3 章 | ⭐⭐⭐ 修正稿，32KB，待转 LaTeX |
| `implementation/01-tech-stack-and-structure.md` | 技术栈、目录结构、关键选型 | 第 4 章 | ⭐⭐ 素材，需压缩 |
| `implementation/02-backend-api-implementation.md` | 后端 API、数据契约、HITL 接口 | 第 4 章 | ⭐⭐ 素材，需压缩 |
| `implementation/03-frontend-workbench-implementation.md` | React 工作台、页面结构 | 第 4 章 | ⭐⭐ 素材，需压缩 |
| `implementation/04-workflow-runtime-implementation.md` | Workflow、PlanRunner、StepRunner、RuntimeState | 第 4 章 | ⭐⭐ 素材，需压缩 |
| `implementation/05-code-snippets.md` | 关键代码片段 | 第 4 章 | ⭐ 辅助 |
| `implementation/06-figure-placeholders.md` | 截图/图表占位清单 | 第 4/5 章 | ⭐ 辅助 |

## 设计文档补充

第 3 章和第 4 章可按需回查以下设计源：

- `../thesis-project.design/docs/design/architecture.md` — 整体架构
- `../thesis-project.design/docs/design/system-implementation-design.md` — 系统实现设计
- `../thesis-project.dev/AGENTS.md` — 实现约束与模块范围

## 系统验证证据

第 5 章可直接引用已有系统验证证据：

- `docs/system-validation/evidence-index.md` — 集中证据编号（18 张截图、8 个 API JSON、4 组 pytest、4 个 CLI、2 组 EventLog/Snapshot 样本）
- `docs/system-validation/test-case-table.md` — 13 个测试用例表（TC-S01 至 TC-S13）
- `docs/system-validation/system-validation-checklist.md` — SV-* 验证点覆盖矩阵

## 写作优先级

按数据依赖关系建议如下顺序：

| 优先级 | 章节 | 理由 |
|---|---|---|
| 🥇 1 | **第 3 章：系统需求与总体设计** | ✅ 草稿已完成（32KB Markdown），待转 LaTeX |
| 🥈 2 | **第 5 章：系统测试与验证** | 不依赖 84-run 完整结果；证据体系已建立（TC + EVD）；可直接引用 |
| 🥉 3 | **第 4 章：系统实现** | 素材充足但需压缩改写；不依赖最终实验数据 |
| 4 | **第 1 章：绪论** | 需在整个论文主体成形后凝练 |
| 5 | **第 2 章：相关技术** | 可在系统章节后写，便于引用具体技术选型 |
| 6 | **第 6 章：实验设计与结果分析** | ⚠️ **必须等待 84-run 矩阵完整结果** |
| 7 | **第 7 章：总结与展望** | 最后写 |

## 下一步行动

1. **立即可做**：从草稿改写第 3 章 → 创建 `chapters/03-system-requirements-and-design.tex`
2. **紧随其后**：基于验证证据写第 5 章 → 创建 `chapters/05-system-testing-and-validation.tex`
3. **并行可做**：压缩系统实现素材 → 创建 `chapters/04-system-implementation.tex`
4. **等待**：84-run 完成后 → 第 6 章实验
5. **最后**：绪论、相关技术、总结
