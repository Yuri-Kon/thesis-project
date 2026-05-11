#!/usr/bin/env python3
"""Convert final-paper Markdown chapters into final-term LaTeX chapters.

This is a mechanical bridge for the report PDF stage. It strips handwritten
chapter/section numbers from Markdown headings so LaTeX can number them using
the extracted final-term report format.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "drafts" / "final-paper-md"
OUT_DIR = ROOT / "paper" / "tex" / "chapters-final-term"

CHAPTERS = [
    ("02-introduction.md", "01-introduction.tex"),
    ("03-related-work.md", "02-related-work.tex"),
    ("04-requirements-analysis.md", "03-requirements-analysis.tex"),
    ("05-system-design.md", "04-system-design.tex"),
    ("06-system-implementation.md", "05-system-implementation.tex"),
    ("07-testing-validation.md", "06-testing-validation.tex"),
    ("08-experiments-analysis.md", "07-experiments-analysis.tex"),
    ("09-conclusion.md", "08-conclusion.tex"),
]


def normalize_markdown(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        line = re.sub(r"^#\s*第[一二三四五六七八九十]+章\s*", "# ", line)
        line = re.sub(r"^##\s*\d+\.\d+\s+", "## ", line)
        line = re.sub(r"^###\s*\d+\.\d+\.\d+\s+", "### ", line)
        line = line.replace("【图 ", "图 ")
        line = line.replace("【表 ", "表 ")
        line = line.replace("】", "")
        lines.append(line)
    return "\n".join(lines) + "\n"


def convert_one(src: Path, dst: Path) -> None:
    normalized = normalize_markdown(src.read_text(encoding="utf-8"))
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".md", delete=False) as tmp:
        tmp.write(normalized)
        tmp_path = Path(tmp.name)
    try:
        result = subprocess.run(
            [
                "pandoc",
                "-f",
                "markdown+citations",
                "-t",
                "latex",
                "--natbib",
                str(tmp_path),
            ],
            check=True,
            text=True,
            capture_output=True,
        )
    finally:
        tmp_path.unlink(missing_ok=True)
    dst.write_text(result.stdout, encoding="utf-8")


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for src_name, dst_name in CHAPTERS:
        convert_one(SRC_DIR / src_name, OUT_DIR / dst_name)
    return 0


if __name__ == "__main__":
    sys.exit(main())

