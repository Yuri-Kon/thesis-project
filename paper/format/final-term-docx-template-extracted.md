# 结题报告 DOCX 样板格式提取

来源文件：`docs/final-term/结题报告.docx`

用途：本文档记录结题报告 `.docx` 样板中的版式信号，供后续 Markdown 转 LaTeX、LaTeX 生成 PDF、或手工撰写 Word 版本时参考。该格式为结题报告专用格式；封面不在本文 LaTeX 入口中重建，后续可由外部 PDF 直接拼接。

## 1. 页面设置

从 `word/document.xml` 的 `sectPr` 提取：

| 项目 | Word XML 值 | 近似 LaTeX 设置 |
|---|---:|---|
| 纸张 | `w=11906`, `h=16838` twips | A4 |
| 上边距 | `2155` twips | 约 `3.80cm` |
| 下边距 | `1701` twips | 约 `3.00cm` |
| 左边距 | `1701` twips | 约 `3.00cm` |
| 右边距 | `1701` twips | 约 `3.00cm` |
| 页眉距边界 | `1701` twips | 约 `3.00cm` |
| 页脚距边界 | `1304` twips | 约 `2.30cm` |
| 文档网格 | `linesAndChars`, `linePitch≈391/395` | 正文按约 `1.25` 倍行距近似 |

## 2. 字体与正文

| 对象 | 样板信号 | LaTeX 近似 |
|---|---|---|
| 中文正文 | 宋体类正文；正文段落使用 `正文首行缩进` 样式 | `Noto Serif CJK SC` / 宋体类字体 |
| 西文正文 | Times New Roman | `Times New Roman` |
| 正文字号 | 样板正文多处为小四号倾向，行距 `300` twips | `12pt` 正文，`1.25` 倍行距 |
| 首行缩进 | `firstLineChars=200`, 部分段落 `firstLine=496` twips | `2em` |
| 段前段后 | 正文段落基本无额外段间距 | `\parskip=0pt` |

## 3. 标题层级

样板正文从“第1章 绪论”开始采用章、节、小节三级结构。

| 层级 | Word 样式 | 样板字号 | 对齐 | 行距/段距 | LaTeX 近似 |
|---|---|---:|---|---|---|
| 章标题 | `heading 1` | `36` half-points，约三号 | 居中 | 段前 `312`、段后 `249`，行距 `288` | `\section` 显示为“第n章 标题”，黑体三号居中 |
| 二级标题 | `heading 2` | `30` half-points，约小三 | 左对齐 | 段前/后 `156`，行距 `300` | `\subsection` 显示为 `n.n 标题`，黑体小三 |
| 三级标题 | `heading 3` | `28` half-points，约四号 | 左对齐 | 段前/后 `156`，行距 `288` | `\subsubsection` 显示为 `n.n.n 标题`，黑体四号 |

样板中标题文本本身已经包含编号，如 `第1章  绪  论`、`1.1  课题背景及研究的目的和意义`。LaTeX 入口中采用自动编号，因此从 Markdown 转换时需要去除标题中手写的章/节编号，避免出现重复编号。

## 4. 目录与正文起点

样板包含封面、摘要、Abstract 和目录，但本次结题报告 PDF 只从“绪论”开始生成，不重建封面。若未来需要拼接完整 PDF，可将外部封面 PDF 放在正文 PDF 前。

当前 LaTeX 入口策略：

- 不生成封面。
- 不生成摘要页。
- 不生成目录页。
- 正文从“第1章 绪论”开始。

## 5. 图、表与公式

样板中表题常见形式为 `表6-2  试样渗透率测试数据`，图表编号按章编号。LaTeX 中采用：

- 图编号：`图 4-1`、`图 7-2` 等；
- 表编号：`表 4-1`、`表 7-8` 等；
- 图题、表题居中；
- 公式编号按章，例如 `(4-1)`。

## 6. 参考文献

样板参考文献为顺序编码形式，正文中使用方括号数字引用。结题报告 LaTeX 入口采用：

- 引用格式：GB/T 7714-2015；
- 引用类型：numeric / 顺序编码；
- LaTeX 近似配置：`natbib` + `gbt7714-numerical`。

注意：本地 TeX 环境需要安装 `gbt7714`/`gbt7714-numerical.bst`。若编译环境缺少该 `.bst`，需要安装对应 TeX 包或在 `paper/tex` 下补充可用的 `gbt7714-numerical.bst`。

## 7. 已映射到 LaTeX 的文件

- 格式入口：`paper/tex/common/final-term-report-preamble.tex`
- 正文入口：`paper/tex/stages/final-term-report.tex`
- 正文章节：`paper/tex/chapters-final-term/`
- Markdown 转换脚本：`paper/tex/tools/convert_final_term_md.py`

