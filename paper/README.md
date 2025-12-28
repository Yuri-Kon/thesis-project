# Thesis Paper (LaTeX)

This directory holds the thesis manuscript in LaTeX, organized by stage.

## Build (per stage)

```bash
cd paper/tex
latexmk -pdf -interaction=nonstopmode -output-directory=../output/proposal stages/proposal.tex
latexmk -pdf -interaction=nonstopmode -output-directory=../output/midterm stages/midterm.tex
latexmk -pdf -interaction=nonstopmode -output-directory=../output/final stages/final.tex
```

## Structure

- `paper/tex/common/` shared preamble
- `paper/tex/chapters/` chapter files
- `paper/tex/stages/` stage entry files (proposal/midterm/final)
- `paper/bib/` bibliography files
- `paper/figures/` figures
- `paper/output/` stage outputs (ignored by git)
- `paper/build/` scratch build artifacts (ignored by git)
