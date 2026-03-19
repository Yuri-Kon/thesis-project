# Reference Format Extracted From `../reference/毛星.docx`

## Page Layout

- Paper size: A4
- Page size in Word XML: `11906 x 16838` twips
- Margins in Word XML:
  - top: `1304` twips
  - bottom: `1304` twips
  - left: `1304` twips
  - right: `1304` twips
- Approximate margin in LaTeX template: `2.3cm`

## Cover Page Structure

The first page is a standalone cover page with this order:

1. `本科毕业论文（设计）中期报告`
2. `题目`
3. `专业`
4. `学生`
5. `学号`
6. `指导教师`
7. `日期`

The extracted title-page text in the reference file is:

- `本科毕业论文（设计）中期报告`
- `题 目：基于自然语言语义的数字水印系统设计与实现`
- `专    业       软件工程`
- `学    生         毛星`
- `学    号      1190200616`
- `指导教师         高峰`
- `日    期     2023年3月8日`

## Typography Signals

- Cover title:
  - centered
  - bold
  - about `48` half-points in Word XML
- Main body headings:
  - use black/heiti-like style
  - section heading around `30` half-points in style definition
- Body text:
  - songti-like body font
  - paragraph first-line indent around `480` twips
  - line spacing around `240` twips in body style

## Midterm Section Structure

The reference document uses this midterm report structure:

1. `毕业设计（论文）内容概述`
2. `已完成的研究工作及成果`
3. `后期拟完成的研究工作及进度安排`
4. `存在的问题与困难`
5. `论文按时完成的可能性`

Subsections include:

- `1.1 项目来源及开发目的和意义`
- `1.2 主要开发任务`
- `1.3 本人所承担任务（模块）说明`
- `2.1 预定计划的执行情况`
- `2.2 系统总体设计`
- `2.3 系统架构设计`
- `2.4 模块交互设计`
- `2.5 系统的详细及实现设计`
- `3.1 后期拟完成的工作`
- `3.2 后期工作的进度安排`

## Notes

- The current LaTeX template in `tex/stages/midterm.tex` follows this extracted structure and recreates the cover page in editable LaTeX form.
- The cover page is preserved structurally rather than embedded as a binary screenshot, so the student metadata can be updated directly.
