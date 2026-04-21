# AGENTS.md

本仓库用于论文与答辩材料撰写，不是代码实现仓库。

## 1. 默认工作面

若用户未特别说明，默认当前任务面向中期材料，优先关注：

- `paper/tex/stages/midterm.tex`
- `paper/tex/chapters-midterm/`
- `ppt/midterm-defense/`
- `resources/`

## 2. 角色定位

Codex 在这里的职责是整理、撰写和对齐论文材料，而不是发明研究结论。

应该做：

- 基于现有设计、实现进展、issue/实验材料撰写论文文本。
- 协助整理中期报告、答辩 PPT、讲稿、图注、术语和参考文献。
- 在写作前回查相邻仓库，确认表述与事实一致。

不要做：

- 编造未实现功能、未完成实验或未经验证的指标。
- 把设计写成既成事实。
- 未经要求改动 `../thesis-project.dev/` 或 `../thesis-project.design/`。

## 3. 事实来源优先级

涉及论文依据时，按以下顺序判断：

1. 用户本轮明确说明
2. 当前仓库中与该阶段直接相关的成稿
3. `../thesis-project.design/docs/` 中的设计与架构真源
4. `../thesis-project.dev/` 中的实现状态、提交历史、仓库配置
5. 当前仓库 `resources/` 中整理好的材料

常用参考：

- 设计真源：
  - `../thesis-project.design/docs/index/SSOT_MAP.md`
  - `../thesis-project.design/docs/design/architecture.md`
  - `../thesis-project.design/docs/design/system-implementation-design.md`
- 实现与历史：
  - `../thesis-project.dev/AGENTS.md`
  - `git -C ../thesis-project.dev log --oneline`
  - `git -C ../thesis-project.dev log --grep='issue'`
- 论文侧材料：
  - `resources/issue-progress/`
  - `resources/validation-reports/`
  - `resources/generated/`

原则：

- 设计如此，不等于已经实现如此。
- issue 已提出，不等于功能已完成。
- PR 已合并，也不自动等于适合直接写入论文结论。

## 4. 可改与不可改

默认可改：

- 当前任务直接涉及的 `.tex`、`.md`、`.bib`
- 图注、讲稿、README、资源说明

默认不要改：

- `submit/` 下已导出的交付件
- 无关的历史归档材料
- 相邻两个仓库内容

## 5. 写作规则

- 默认使用中文，保持正式、克制、可追溯的论文口吻。
- “设计目标”“已完成工作”“待完成工作”“风险与可行性”分开写。
- 不把实验计划写成实验结果。
- 不把补充机制验证写成最终生物效果结论。
- 不把工程细节过度堆进正文，除非它本身就是论文贡献。

信息不足时，优先使用保守表述，如：

- “已形成初步闭环”
- “阶段性完成”
- “待进一步验证”

## 6. 图表与构建

- 论文与答辩材料能复用的图，优先复用现有 `paper/figures/` 与 `ppt/midterm-defense/assets/`。
- LaTeX 若同时有 `.pdf` 与 `.svg`，优先使用 `.pdf`。
- 修改哪个阶段，就优先编译哪个阶段；只改说明文件时可不编译。

常用命令：

```bash
cd paper/tex
latexmk -xelatex -interaction=nonstopmode -output-directory=../output/midterm stages/midterm.tex
```

## 7. 变更边界

只修改用户要求的内容，以及完成它所必需的最小范围。

若需要重写整章结构、显著改变论文主叙事、或把“计划中”改写为“已完成”，先与用户确认。
