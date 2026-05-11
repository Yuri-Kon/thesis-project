# Thesis Paper (LaTeX)

This directory holds the thesis manuscript in LaTeX, organized by stage.

## Build (per stage)

```bash
cd paper/tex
latexmk -xelatex -interaction=nonstopmode -output-directory=../output/proposal stages/proposal.tex
latexmk -xelatex -interaction=nonstopmode -output-directory=../output/midterm stages/midterm.tex
latexmk -xelatex -interaction=nonstopmode -output-directory=../output/final stages/final.tex
latexmk -xelatex -interaction=nonstopmode -output-directory=../output/final-term stages/final-term-report.tex
```

## Structure

- `paper/tex/common/` shared preamble
- `paper/tex/common/midterm-cover.tex` midterm cover-page template
- `paper/tex/common/midterm-metadata.tex` midterm title-page metadata
- `paper/tex/common/final-term-report-preamble.tex` final-term report body style extracted from `docs/final-term/结题报告.docx`
- `paper/tex/chapters/` chapter files
- `paper/tex/chapters-final-term/` final-term report body chapters generated from `drafts/final-paper-md/`
- `paper/tex/chapters-midterm/` midterm-specific chapter skeleton
- `paper/tex/stages/` stage entry files (proposal/midterm/final)
- `paper/bib/` bibliography files
- `paper/figures/` figures
- `paper/output/` stage outputs (ignored by git)
- `paper/build/` scratch build artifacts (ignored by git)

## Figures

- `paper/figures/component-views.pdf` / `.svg`: current system component overview
- `paper/figures/multi-agent-core.pdf` / `.svg`: multi-agent collaboration core view
- `paper/figures/system-architecture-overview.pdf` / `.svg`: simplified layered architecture overview
- `paper/figures/total-sequence.pdf` / `.svg`: end-to-end workflow with HITL and recovery
- `paper/figures/single-step-sequence.pdf` / `.svg`: single-step retry / patch / replan loop
- Prefer `\includegraphics{../../figures/<name>.pdf}` in LaTeX for stable builds

## Midterm Template Notes

- `stages/midterm.tex` now follows the formatting extracted from `../reference/毛星.docx`.
- The body layout and heading hierarchy follow the extracted reference formatting.
- The LaTeX-rendered cover page is currently not included in `stages/midterm.tex`; you can insert an external PDF cover later.
- If you want to reuse the LaTeX cover later, edit `paper/tex/common/midterm-metadata.tex` and `paper/tex/common/midterm-cover.tex`.

## Final-Term Report Notes

- `paper/format/final-term-docx-template-extracted.md` records the extracted Word style signals from `docs/final-term/结题报告.docx`.
- `paper/tex/stages/final-term-report.tex` starts directly from Chapter 1 / 绪论. It intentionally does not generate a cover, abstract, or table of contents.
- The final-term report uses `gbt7714-numerical` for GB/T 7714-2015 numeric references. The build environment must provide the corresponding `.bst` file.
- To refresh LaTeX body chapters from Markdown, run:

```bash
python3 paper/tex/tools/convert_final_term_md.py
```
