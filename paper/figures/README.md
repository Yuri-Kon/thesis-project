# Figures

This directory contains thesis-ready figures rendered from the updated Mermaid sources in:

- `../thesis-project.design/docs/design/diagrams/component-views.mmd`
- `../thesis-project.design/docs/design/diagrams/total-sequence.mmd`
- `../thesis-project.design/docs/design/diagrams/single-step-sequence.mmd`
- `paper/figures/multi-agent-core.mmd`
- `paper/figures/system-architecture-overview.mmd`

Available assets:

- `component-views.pdf` / `component-views.svg`
- `total-sequence.pdf` / `total-sequence.svg`
- `single-step-sequence.pdf` / `single-step-sequence.svg`
- `multi-agent-core.pdf` / `multi-agent-core.svg`
- `system-architecture-overview.pdf` / `system-architecture-overview.svg`

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
- `multi-agent-core`: 多 Agent 核心协作关系
- `system-architecture-overview`: 分层架构总览 / 答辩总图
- `total-sequence`: 系统工作流程 / HITL 执行闭环
- `single-step-sequence`: 单步失败恢复 / Patch 与 Replan 机制
