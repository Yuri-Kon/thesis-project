# Issue: P1-7 将 runtime policy mode 直接映射为论文消融组

## 类型

- Priority: P1
- Scope: algorithm / evaluation / ablation design
- Phase: CEBRA-WP P1 规划与实现准备
- Body language: Chinese
- 状态：待实现
- 本文件定位：P1-7 的唯一实现参考来源；进入编码前以本文为准。

## 1. 背景

`RuntimeEvaluator` 已支持多个 policy mode：

- `static_top1`
- `static_gate`
- `dynamic_observation_only`
- `lite_belief_state`

设计仓库还给出了论文主结果组的映射草案。这个非常适合直接用于消融实验，但目前缺少一个“论文组 ↔ 代码 mode ↔ 预期行为”的统一表。

## 2. 当前代码核查结论

### 2.1 已有能力

`tests/unit/test_runtime_evaluator.py` 和 `tests/integration/test_workflow_action_selector.py` 已经在验证：

- `static_top1` 跳过 rerank；
- `static_gate` 跳过 rerank；
- `dynamic_observation_only` 不使用 belief-state；
- `lite_belief_state` 保留完整重排链路。

### 2.2 差距

1. 代码支持了 policy mode，但论文消融没有唯一映射表；
2. 组名与行为有时混用；
3. 如果不统一，实验结果在写作阶段会难以对齐。

## 3. 风险

没有统一映射时，论文很可能出现：

- 组名在图里叫一个名字；
- 代码配置里叫另一个名字；
- 评估表又是第三个名字。

这会增加复现实验和答辩解释成本。

## 4. 建议方案

建议固定一张映射表，作为论文和实验的唯一参考：

```text
static_top1            -> 静态单链基线
static_gate            -> 静态门控基线
dynamic_observation_only -> 动态观测但不使用 belief-state
lite_belief_state      -> 完整 CEBRA-WP
```

并在文档里明确每组回答的问题：

- 静态链路是否足够；
- 简单门控是否足够；
- 仅动态恢复是否足够；
- belief-state 是否带来最后一段增益。

## 5. 最小实现提案

### 5.1 建议文档结构

在实验设计文档中增加：

```text
mode / paper group / semantic meaning / expected effect / key metrics
```

### 5.2 建议代码约束

- `policy_mode` 枚举值不可再隐式扩展；
- 新增 mode 必须同步更新测试和实验文档；
- mode 名称尽量保持与论文一致。

## 6. 测试建议

1. 四个 mode 的行为应有明确差异；
2. `lite_belief_state` 必须是唯一启用完整 runtime adjustment 的组；
3. `static_top1` 与 `static_gate` 不应产生混淆；
4. 消融配置应可被测试直接读取。

## 7. 验收标准

- 论文主结果组与代码 mode 一一对应；
- 消融定义稳定，不再随实现细节漂移；
- 评估脚本和论文表格可以共享同一张映射表。