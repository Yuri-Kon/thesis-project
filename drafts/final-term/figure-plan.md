# 论文图示规划（已更新）

> 最后更新：2026-05-11（同步用户绘制的 5 张新图，图示已全部就绪）

---

## 图示状态：✅ 全部完成

所有设计图已绘制完毕并迁入 `paper/figures/`。14 张 drawio 源文件 + SVG/PNG 渲染产物。

---

## 图号分配（8 章）

| 图号 | 章节 | 内容 | 源文件 |
|------|------|------|--------|
| 图 3-1 | 第 3 章 | 问题-方案对照：固定流水线 vs 本系统 | `problem-solution-comparison.drawio` |
| 图 4-1 | 第 4 章 | 系统五层分层架构 | `system-architecture.drawio` |
| 图 4-2 | 第 4 章 | ProteinToolKG 局部可视化 | `protein-toolkg-local-view.drawio` |
| 图 4-3 | 第 4 章 | FSM 状态转移图 | `fsm-state-transition.drawio` |
| 图 4-4 | 第 4 章 | HITL 触发条件与决策逻辑 | `hitl-decision-conditions.drawio` |
| 图 4-5 | 第 4 章 | 六阶段 de novo 工作流 | `workflow-flowchart.drawio` |
| 图 4-6 | 第 4 章 | CEBRA-WP 算法闭环 | `algorithm-loop.drawio` |
| 图 4-7 | 第 4 章 | 核心数据契约 UML | `uml-contracts.drawio` |
| 图 4-8 | 第 4 章 | t1 任务实例走查 | `t1-trpcage-instance-walkthrough.drawio` |
| 图 5-1 | 第 5 章 | 运行时执行序列 | `runtime-sequence.drawio` |
| 图 5-2 | 第 5 章 | 工作流泳道式模块协作 | `workflow-swimlane.drawio` |
| 图 7-1 | 第 7 章 | 实验设计框架 | `experiment-design-framework.drawio` |
| 图 7-2 | 第 7 章 | 恢复路径对比 | `recovery-path-comparison-timeline.drawio` |

> 说明：第 6 章测试覆盖矩阵应作为表 6-1，而不是图 6-1。当前 `paper/figures/` 中没有“四组消融主实验结果”的独立图片文件；第 7 章用表 7-1 至表 7-8 承载实验配置、主结果、分层结果、机制对比、成本分析、可观测性、失败归因和证据索引，避免引用不存在的图 7-x。

### 补充图（可选，按需引用）

| 源文件 | 内容 | 可用场景 |
|--------|------|---------|
| `technical-route.drawio` | 技术路线概览 | 第 2 章相关技术 |

---

## 已补缺口（对照 figure-plan.md 原始清单）

| 缺口 | 状态 | 对应文件 |
|------|------|---------|
| G01 问题-方案对照 | ✅ 已绘制 | `problem-solution-comparison.drawio` |
| G02 ProteinToolKG 可视化 | ✅ 已绘制 | `protein-toolkg-local-view.drawio` |
| G03 实例走查 | ✅ 已绘制 | `t1-trpcage-instance-walkthrough.drawio` |
| G04 HITL 触发条件 | ✅ 已绘制 | `hitl-decision-conditions.drawio` |
| G05 恢复路径对比 | ✅ 已绘制 | `recovery-path-comparison-timeline.drawio` |
| G06 实现层视觉 | ✅ 已收口 | 第 5 章使用 `runtime-sequence.drawio` 与 `workflow-swimlane.drawio`；第 6 章 FIG-SV 作为证据截图，不单独编号 |
| 四组消融主实验结果图 | 暂不绘制 | 当前以表 7-1 至表 7-8 呈现，避免引用不存在图片 |
