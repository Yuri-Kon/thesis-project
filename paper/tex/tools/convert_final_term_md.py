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


FORMULA_BLOCKS = {
    "Pi_raw,t = GenerateCandidates(g, C, K, h_t)": r"""\[
\begin{aligned}
\Pi_{\mathrm{raw},t} &= \operatorname{GenerateCandidates}(g,C,K,h_t),\\
\Pi_t &= \operatorname{FeasibilityFilter}(\Pi_{\mathrm{raw},t},C,K,h_t),\\
S_{\mathrm{static}} &= \operatorname{StaticUtility}(\pi,g,C,K),\\
x_{t+1} &= \operatorname{BeliefUpdate}(x_t,o_t,h_t),\\
G_{\mathrm{post}} &= \operatorname{PosteriorObjective}(\pi,g,o_t),\\
U_{\pi} &= \operatorname{RuntimeCandidateUtility}(S_{\mathrm{static}},G_{\mathrm{post}},x_{t+1}),\\
a_t &= \operatorname{RecoveryAwareActionSelection}(x_{t+1},\Pi_t,h_t,C).
\end{aligned}
\]""",
    "F_h(pi, C, K, h_t)": r"""\[
\begin{aligned}
F_h(\pi,C,K,h_t)
  &= F_{\mathrm{tool}}\land F_{\mathrm{schema}}\land F_{\mathrm{io}}\land F_{\mathrm{safety}}\\
  &\quad{}\land F_{\mathrm{budget\mbox{-}hard}}\land F_{\mathrm{availability}}.
\end{aligned}
\]""",
    "Pi_t = { pi in Pi_raw,t | F_h(pi, C, K, h_t) = 1 }": r"""\[
\Pi_t=\{\pi\in\Pi_{\mathrm{raw},t}\mid F_h(\pi,C,K,h_t)=1\}.
\]""",
    "S_static(pi)": r"""\[
\begin{aligned}
S_{\mathrm{static}}(\pi)
  &= w_f F_s(\pi)
   + w_g G(\pi;g,o_t)
   - w_c C_{\mathrm{norm}}(\pi)\\
  &\quad{}- w_r R_{\mathrm{norm}}(\pi)
   - w_{\mathrm{rec}}\operatorname{Rec}(\pi)
   + w_q Q(\pi).
\end{aligned}
\]""",
    "x_t = [": r"""\[
x_t=\left[
\begin{array}{c}
\statevar{p\_success}\\
\statevar{p\_structural\_failure}\\
\statevar{recovery\_margin}\\
\statevar{expected\_remaining\_cost}\\
\statevar{evidence\_sufficiency}
\end{array}
\right].
\]""",
    "budget_pressure": r"""\[
\statevar{budget\_pressure}
=\operatorname{clip}\left(
\frac{\statevar{expected\_remaining\_cost}}{\max(\statevar{budget\_cap},0.1)},
0,1.5
\right).
\]""",
    "budget_pressure = clip(expected_remaining_cost, 0, 1.5)": r"""\[
\statevar{budget\_pressure}
=\operatorname{clip}(\statevar{expected\_remaining\_cost},0,1.5).
\]""",
    "G_post(pi; g, o_t) = Σ_m λ_m(g) · ρ_m(o_t) · q_m(pi, o_t)": r"""\[
G_{\mathrm{post}}(\pi;g,o_t)
=\sum_m \lambda_m(g)\rho_m(o_t)q_m(\pi,o_t).
\]""",
    "e_t = clip(Σ_m λ_m(g) · ρ_m(o_t), 0, 1)": r"""\[
e_t=\operatorname{clip}\left(\sum_m \lambda_m(g)\rho_m(o_t),0,1\right).
\]""",
    "U_pi(pi, x_t) = clip(S_post(pi) + Delta(pi, x_t), 0, 1)": r"""\[
U_{\pi}(\pi,x_t)
=\operatorname{clip}\left(S_{\mathrm{post}}(\pi)+\Delta(\pi,x_t),0,1\right).
\]""",
    "Delta(pi, x_t)": r"""\[
\begin{aligned}
\Delta(\pi,x_t)
  &= k_s\,(\statevar{p\_success}-0.5)\operatorname{Conf}(\pi)\\
  &\quad{}+k_e\,(2\,\statevar{evidence\_sufficiency}-1)
       \max(\operatorname{Conf}(\pi),F_s(\pi))\\
  &\quad{}-k_f\,\statevar{p\_structural\_failure}\,(1-\operatorname{RiskScore}(\pi))\\
  &\quad{}+k_r\,\statevar{recovery\_margin}\operatorname{RecoveryScore}(\pi)\\
  &\quad{}-k_c\,\statevar{budget\_pressure}\,(1-\operatorname{CostScore}(\pi))\\
  &\quad{}+k_a\,\operatorname{ActionBias}(\pi,x_t).
\end{aligned}
\]""",
    "U_continue": r"""\[
\begin{aligned}
U_{\mathrm{continue}}
  &=0.38s+0.14e+0.12r-0.22f-0.14b,\\
U_{\statevar{patch\_local}}
  &=0.20s+0.24r+0.18\,\statevar{local\_patchability}
    +0.12\,\statevar{evidence\_reusability}\\
  &\quad{}-0.14f-0.12b,\\
U_{\statevar{suffix\_replan}}
  &=0.18(1-s)+0.20f+0.16(1-r)
    +0.18\,\statevar{prefix\_preservability}\\
  &\quad{}+0.14\,\statevar{budget\_relief}
    +0.14\,\statevar{goal\_realignment},\\
U_{\mathrm{stop}}
  &=0.32(1-s)+0.24b+0.18(1-r)
    +0.16\,\statevar{safety\_terminality}\\
  &\quad{}+0.10(1-\statevar{intervention\_value}).
\end{aligned}
\]""",
}


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


def _plain_normal_tok(block: str) -> list[str]:
    lines: list[str] = []
    for raw_line in block.splitlines():
        match = re.fullmatch(r"\\NormalTok\{(.*)\}", raw_line)
        if not match:
            continue
        line = match.group(1)
        line = line.replace(r"\_", "_")
        line = line.replace(r"\ ", " ")
        line = line.replace(r"\{", "{").replace(r"\}", "}")
        line = line.replace(r"{-}", "-")
        line = line.replace("Σ", "Σ")
        lines.append(line)
    return lines


def _formula_replacement(match: re.Match[str]) -> str:
    block = match.group(0)
    lines = _plain_normal_tok(block)
    first = next((line.strip() for line in lines if line.strip()), "")
    return FORMULA_BLOCKS.get(first, block)


def postprocess_latex(text: str) -> str:
    text = re.sub(r"\\begin\{longtable\}\[\]", r"\\begin{longtable}", text)
    text = text.replace(r"\toprule\noalign{}", r"\toprule")
    text = text.replace(r"\midrule\noalign{}", r"\midrule")
    text = text.replace(r"\bottomrule\noalign{}", r"\bottomrule")
    text = re.sub(
        r"\\begin\{Shaded\}\n\\begin\{Highlighting\}\[\]\n(?:.*?\n)\\end\{Highlighting\}\n\\end\{Shaded\}",
        _formula_replacement,
        text,
        flags=re.DOTALL,
    )
    replacements = {
        r"\texttt{G\_post}": r"$G_{\mathrm{post}}$",
        r"\texttt{S\_post}": r"$S_{\mathrm{post}}$",
        r"\texttt{Delta(pi,\ x\_t)}": r"$\Delta(\pi,x_t)$",
        r"\texttt{Conf(pi)}": r"$\operatorname{Conf}(\pi)$",
        r"\texttt{RiskScore(pi)}": r"$\operatorname{RiskScore}(\pi)$",
        r"\texttt{CostScore(pi)}": r"$\operatorname{CostScore}(\pi)$",
        r"\texttt{RecoveryScore(pi)}": r"$\operatorname{RecoveryScore}(\pi)$",
        r"\texttt{ActionBias(pi,\ x\_t)}": r"$\operatorname{ActionBias}(\pi,x_t)$",
        r"\texttt{λ\_m(g)}": r"$\lambda_m(g)$",
        r"\texttt{q\_m(pi,\ o\_t)}": r"$q_m(\pi,o_t)$",
        r"\texttt{ρ\_m(o\_t)}": r"$\rho_m(o_t)$",
        r"\texttt{pi}": r"$\pi$",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


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
    dst.write_text(postprocess_latex(result.stdout), encoding="utf-8")


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for src_name, dst_name in CHAPTERS:
        convert_one(SRC_DIR / src_name, OUT_DIR / dst_name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
