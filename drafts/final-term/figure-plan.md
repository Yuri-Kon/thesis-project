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
| 图 4-4 | 第 4 章 | 六阶段 de novo 工作流 | `workflow-flowchart.drawio` |
| 图 4-5 | 第 4 章 | CEBRA-WP 算法闭环 | `algorithm-loop.drawio` |
| 图 4-6 | 第 4 章 | 核心数据契约 UML | `uml-contracts.drawio` |
| 图 4-7 | 第 4 章 | t1 任务实例走查 | `t1-trpcage-instance-walkthrough.drawio` |
| 图 5-1 | 第 5 章 | 模块目录结构 | 文字/代码生成 |
| 图 5-2 | 第 5 章 | 前端关键页面截图 | FIG-SV-02/07/13 |
| 图 5-3 | 第 5 章 | 运行时执行序列 | `runtime-sequence.drawio` |
| 图 6-1 | 第 6 章 | 测试用例覆盖矩阵 | 文字表 |
| 图 6-2 | 第 6 章 | 前端验证截图 | FIG-SV-02/18 |
| 图 7-1 | 第 7 章 | 实验设计框架 | `experiment-design-framework.drawio` |
| 图 7-2 | 第 7 章 | 四组消融主实验结果 | 待 matplotlib 生成 |
| 图 7-3 | 第 7 章 | 恢复路径对比 | `recovery-path-comparison-timeline.drawio` |

### 补充图（可选，按需引用）

| 源文件 | 内容 | 可用场景 |
|--------|------|---------|
| `hitl-decision-conditions.drawio` | HITL 触发条件与决策逻辑 | 第 4 章 FSM 小节或第 6 章 HITL 测试 |
| `workflow-swimlane.drawio` | 泳道式工作流总览 | 第 5 章工作流部分 |
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
| G06 实现层视觉 | 🟡 从已有素材选 | FIG-SV 截图 + 文字表 |
| 图 7-2 实验结果 | ⏳ 待 matplotlib | 依赖数据已就绪，生成脚本待写 |
