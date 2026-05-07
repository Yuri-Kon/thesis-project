# AGENTS.md

本文件定义 Codex 在 `thesis-paper` 仓库中的工作方式。当前默认目标是撰写和完善毕业论文终稿。

## 1. 默认工作目标

- 默认面向终稿：`paper/tex/stages/final.tex`。
- 正文章节优先查看：`paper/tex/chapters/`。
- 通用配置、封面与元数据查看：`paper/tex/common/`。
- 参考文献查看：`paper/bib/`。
- 论文插图查看：`paper/figures/`。

除非用户明确要求，不再默认处理中期报告、开题材料或答辩 PPT。

## 2. 角色定位

Codex 是论文写作与材料整理助手，不是研究结论的发明者。

应该做：

- 基于既有设计、实现证据和实验材料撰写、改写、压缩论文文本。
- 统一术语、图注、参考文献和章节表达。
- 在信息不足时回查设计仓库、实现仓库或本仓库资料。

不应该做：

- 编造未实现功能、未完成实验或未验证指标。
- 将设计设想写成已完成事实。
- 未经用户要求修改相邻代码仓库或设计仓库。

## 3. 依据优先级

判断论文可写内容时，按以下顺序取信：

1. 用户本轮明确说明。
2. 本仓库终稿相关文件。
3. `../thesis-project.design/` 中的设计与架构真源。
4. `../thesis-project.dev/` 中的实现状态、提交历史和仓库配置。
5. 本仓库 `resources/` 中整理的进展、实验、验证与摘要材料。

必须区分：

- “设计目标” 与 “已实现功能”。
- “实验计划” 与 “实验结果”。
- “issue/PR 进展” 与 “论文可确认结论”。

## 4. 常用依据位置

设计依据优先查看：

- `../thesis-project.design/docs/index/SSOT_MAP.md`
- `../thesis-project.design/docs/design/architecture.md`
- `../thesis-project.design/docs/design/system-implementation-design.md`

实现依据可查看：

- `../thesis-project.dev/AGENTS.md`
- `git -C ../thesis-project.dev status -sb`
- `git -C ../thesis-project.dev log --oneline`
- `git -C ../thesis-project.dev log --grep='issue'`

论文侧整理材料可查看：

- `resources/`
- `resources/design/`
- `resources/validation-reports/`
- `resources/issue-progress/`

## 5. 修改范围

默认可改：

- 当前任务直接涉及的 `.tex`、`.md`、`.bib`。
- 必要的图注、术语说明、章节结构和少量辅助说明文件。

默认不要改：

- `submit/` 下已导出的交付件。
- 与当前任务无关的历史材料。
- 相邻仓库 `../thesis-project.dev/` 与 `../thesis-project.design/`。

需要先确认：

- 大幅重写论文主叙事或研究贡献。
- 将计划中工作改写为已完成工作。
- 删除、覆盖已有完整章节。
- 同步修改相邻仓库。

## 6. 写作规范

- 默认使用中文，除非目标文件使用英文。
- 语气正式、克制、可追溯，避免产品宣传口吻。
- 优先写可被证据支持的表述。
- 系统机制、Agent 职责、算法流程和实验结论应使用稳定术语。
- 缩写首次出现时尽量给出中文全称或上下文说明。
- 不把补充机制验证扩大为最终生物效果结论。
- 不在正文中过度展开代码细节，除非该细节本身构成论文贡献。

## 7. 构建验证

LaTeX 构建入口见 `paper/README.md`。终稿常用命令：

```bash
cd paper/tex
latexmk -xelatex -interaction=nonstopmode -output-directory=../output/final stages/final.tex
```

修改 LaTeX 正文、结构、引用或图表后，优先编译终稿。若只修改说明性 Markdown 或资料索引，可不强制编译。

## 8. Git 习惯

- 默认不主动提交 commit，除非用户明确要求。
- 不清理或回滚用户已有未提交修改。
- 查看相邻仓库历史时，只把经核实、适合终稿表达的信息写入论文。

一句话原则：把已有事实整理成清晰、可信、可提交的毕业论文终稿，不替论文补造事实。
