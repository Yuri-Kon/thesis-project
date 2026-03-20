# Thesis Paper (LaTeX)

This directory holds the thesis manuscript in LaTeX, organized by stage.

## Build (per stage)

```bash
cd paper/tex
latexmk -xelatex -interaction=nonstopmode -output-directory=../output/proposal stages/proposal.tex
latexmk -xelatex -interaction=nonstopmode -output-directory=../output/midterm stages/midterm.tex
latexmk -xelatex -interaction=nonstopmode -output-directory=../output/final stages/final.tex
```

## Structure

- `paper/tex/common/` shared preamble
- `paper/tex/common/midterm-cover.tex` midterm cover-page template
- `paper/tex/common/midterm-metadata.tex` midterm title-page metadata
- `paper/tex/chapters/` chapter files
- `paper/tex/chapters-midterm/` midterm-specific chapter skeleton
- `paper/tex/stages/` stage entry files (proposal/midterm/final)
- `paper/bib/` bibliography files
- `paper/figures/` figures
- `paper/output/` stage outputs (ignored by git)
- `paper/build/` scratch build artifacts (ignored by git)

## Midterm Template Notes

- `stages/midterm.tex` now follows the formatting extracted from `../reference/毛星.docx`.
- The body layout and heading hierarchy follow the extracted reference formatting.
- The LaTeX-rendered cover page is currently not included in `stages/midterm.tex`; you can insert an external PDF cover later.
- If you want to reuse the LaTeX cover later, edit `paper/tex/common/midterm-metadata.tex` and `paper/tex/common/midterm-cover.tex`.
