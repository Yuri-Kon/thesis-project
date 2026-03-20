# Figures

This directory contains thesis-ready figures rendered from the updated Mermaid sources in:

- `../thesis-project.design/docs/design/diagrams/component-views.mmd`
- `../thesis-project.design/docs/design/diagrams/total-sequence.mmd`
- `../thesis-project.design/docs/design/diagrams/single-step-sequence.mmd`

Available assets:

- `component-views.pdf` / `component-views.svg`
- `total-sequence.pdf` / `total-sequence.svg`
- `single-step-sequence.pdf` / `single-step-sequence.svg`

Suggested usage in LaTeX:

```tex
\begin{figure}[htbp]
  \centering
  \includegraphics[width=\textwidth]{../../figures/component-views.pdf}
  \caption{系统组件总览}
\end{figure}
```

Recommended chapter mapping:

- `component-views`: 系统总体设计 / 系统架构
- `total-sequence`: 系统工作流程 / HITL 执行闭环
- `single-step-sequence`: 单步失败恢复 / Patch 与 Replan 机制
