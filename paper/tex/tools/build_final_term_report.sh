#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEX_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
OUTPUT_DIR="${TEX_DIR}/../output/final-term"
TARGET="stages/final-term-report.tex"

if ! command -v latexmk >/dev/null 2>&1; then
  echo "latexmk is not available. Install a TeX distribution with latexmk and xelatex." >&2
  exit 127
fi

if ! command -v xelatex >/dev/null 2>&1; then
  echo "xelatex is not available. Install a TeX distribution with XeLaTeX support." >&2
  exit 127
fi

mkdir -p "${OUTPUT_DIR}"
cd "${TEX_DIR}"

latexmk \
  -xelatex \
  -interaction=nonstopmode \
  -file-line-error \
  -halt-on-error \
  -output-directory=../output/final-term \
  "${TARGET}"

echo "Built ${OUTPUT_DIR}/final-term-report.pdf"
