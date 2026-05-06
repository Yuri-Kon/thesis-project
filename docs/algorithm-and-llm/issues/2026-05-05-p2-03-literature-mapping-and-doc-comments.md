# Issue: P2-3 建立理论背景与最新论文的映射清单

## 类型

- Priority: P2
- Scope: research / documentation / algorithm background
- Phase: CEBRA-WP P2 文档与表达增强
- Body language: Chinese
- 状态：已实现
- 本文件定位：P2-3 的唯一实现参考来源；进入编码前以本文为准。

## 1. 背景

用户当前关心的不只是代码对不对，而是“算法在理论深度上是否足够”。这意味着问题不是再多加一个工程字段，而是要把系统放进明确的理论背景中。

## 2. 建议映射主题

建议把文献与理论背景按下面几类分桶：

```text
- POMDP / belief-state / online adaptation
- CMDP / hard constraints / safety gating
- evidence-weighted posterior objective
- recovery / replanning / intervention policy
- diversity-aware top-k selection
- docking / binding / structure-quality proxies
```

## 3. 风险

如果没有映射清单，后续论文写作会变成：

- 文献搜到一堆；
- 但不知道每篇论文对应哪个理论对象；
- 结果只剩“相关工作”而没有理论支撑链路。

## 4. 建议方案

在设计文档或 issue 目录中补一份映射清单，格式建议为：

```text
理论对象 -> 论文/综述 -> 对本项目的作用 -> 是否进入正文
```

建议最少覆盖：

- belief-state 更新；
- 约束下动作选择；
- 后验目标重排；
- 多样性 Top-K；
- binding / structure proxy 的证据解释。

## 5. 最小实现提案

- 不把大量文献直接写进业务代码；
- 在设计文档中补“理论对象 - 文献 - 代码落点”的三列表；
- 若引用最新论文，注明日期、版本和用途。

## 6. 验证建议

1. 每个核心公式至少能指向一个理论背景；
2. 每个理论对象至少能落到一个实现入口；
3. 文献条目和代码字段能互相对应。

## 7. 验收标准

- 文献映射不是附录，而是实现/写作共同参考；
- 理论背景不再散落在多份笔记里；
- 最新论文可以作为算法细化依据被稳定复用。

## 8. 实现记录

- 新增 `docs/algorithm-and-llm/theory-background-paper-code-map.md` 作为稳定映射矩阵。
- 矩阵逐项覆盖 `Pi_t`、`S_static`、`G_post`、`x_t`、`B(x_t,o_t,h_t)`、`Delta`、`U_pi`、`SelectDiverseTopK`、`U_a` 和 stop guard。
- 每个条目同时给出设计 SID / schema 或公式版本、代码落点、字段或 metadata、理论背景、代表文献和正文采用状态。
- 近期文献按 2026-05-05 检索口径记录 arXiv/Nature 链接和用途，包括 RosettaSearch、AutoBinder Agent、ProtAlign、ProteinGuide、ProteinZero、PDB-Struct、AlphaFold3 等。
- `core-algorithm-literature-map.md` 和 `core-algorithm-theory-v2.md` 已指向该映射矩阵，避免文献综述、理论公式和实现审查三者分散。
