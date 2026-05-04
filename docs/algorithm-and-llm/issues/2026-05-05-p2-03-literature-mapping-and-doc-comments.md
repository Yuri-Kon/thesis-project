# Issue: P2-3 建立理论背景与最新论文的映射清单

## 类型

- Priority: P2
- Scope: research / documentation / algorithm background
- Phase: CEBRA-WP P2 文档与表达增强
- Body language: Chinese
- 状态：待实现
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