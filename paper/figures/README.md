# 论文插图

## 主图源（drawio）

所有设计图以 drawio 为可编辑源，同时提供 SVG（矢量，适合 LaTeX）和 PNG（预览）渲染产物。

| 文件（.drawio） | 内容 | 归入章节 | 图号 |
|---|---|---|---|
| `system-architecture.drawio` | 五层分层架构、控制面 SSOT、审计链 | 第 4 章 | 图 4-1 |
| `fsm-state-transition.drawio` | 11 状态 FSM、三类 WAITING 决策点 | 第 4 章 | 图 4-3 |
| `workflow-flowchart.drawio` | 六阶段 de novo 工作流与恢复控制 | 第 4 章 | 图 4-4 |
| `algorithm-loop.drawio` | CEBRA-WP 算法闭环 | 第 4 章 | 图 4-5 |
| `uml-contracts.drawio` | 核心数据契约 UML | 第 4 章 | 图 4-6 |
| `protein-toolkg-local-view.drawio` | ProteinToolKG 局部可视化 | 第 4 章 | 图 4-2 |
| `problem-solution-comparison.drawio` | 固定流水线 vs 本系统对照 | 第 3 章 | 图 3-1 |
| `t1-trpcage-instance-walkthrough.drawio` | t1 任务实例走查 | 第 4 章 | 图 4-7 |
| `hitl-decision-conditions.drawio` | HITL 触发条件与决策逻辑 | 第 4 章 | — |
| `runtime-sequence.drawio` | 运行时执行序列 | 第 5 章 | 图 5-3 |
| `workflow-swimlane.drawio` | 泳道式工作流总览 | 第 5 章 | — |
| `technical-route.drawio` | 技术路线概览 | 第 2 章 | — |
| `experiment-design-framework.drawio` | 实验设计框架 | 第 7 章 | 图 7-1 |
| `recovery-path-comparison-timeline.drawio` | 恢复路径对比 | 第 7 章 | 图 7-3 |

## LaTeX 使用

推荐使用 SVG 格式（矢量，可缩放）：

```tex
\begin{figure}[htbp]
  \centering
  \includegraphics[width=\textwidth]{figures/system-architecture.drawio.svg}
  \caption{系统五层分层架构}
  \label{fig:system-architecture}
\end{figure}
```

## 旧 Mermaid 图

`legacy-mermaid/` 中的 `.mmd` 和渲染产物来自中期答辩，保留作历史参考。终稿不引用 Mermaid 图。

## 验证截图

系统测试截图（18 张 PNG）位于 `../thesis-project.dev/docs/system-validation/06-ui-screenshots/`，论文中证编编号 FIG-SV-01 至 FIG-SV-18。
