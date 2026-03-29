# 算法实验分组与论文叙事映射
<!-- SID:experiment.group_mapping.overview -->

## 1. 文档目的
<!-- SID:experiment.group_mapping.scope -->

本文档用于统一三套经常被混用的命名：

- 历史实现增量组：`A0-A6`
- 外部对照组：`E0-E2`
- 论文主结果组：`static_top1 / fixed_threshold_gate / dynamic_no_belief_state / lite_belief_state`

统一目标：

- 避免同一组在不同报告里出现不同名字
- 让论文主表与工程 issue 历史都能互相回链
- 明确哪些组是“实现过程组”，哪些组是“论文主结果组”

## 2. 建议的统一叙事
<!-- SID:experiment.group_mapping.narrative_layers -->

### 2.1 三层分组体系

#### 第一层：实现增量组（历史追踪）

保留 `A0-A6`，用于机制开发与 issue 对账。

#### 第二层：论文主结果组（主表）

论文主结果只保留 4 个内部组：

- `static_top1`
- `fixed_threshold_gate`
- `dynamic_no_belief_state`
- `lite_belief_state`

#### 第三层：外部对照组

- `E0 = react_single_trajectory`
- `E1 = tot_multi_branch`
- `E2 = reflexion_recovery`

## 3. A0-A6 与论文主结果组的映射
<!-- SID:experiment.group_mapping.a_to_paper -->

| 历史组 | 机制含义 | 论文组映射 | 在论文中的角色 |
| --- | --- | --- | --- |
| `A0` | 单候选、无运行时自适应 | `static_top1` | 最弱内部基线 |
| `A1` | Top-K + 静态排序 | 不单独进主表 | 机制消融 |
| `A2` | Top-K + 硬校验 | 不单独进主表 | 机制消融 |
| `A3` | 固定阈值门控 | `fixed_threshold_gate` | 无 belief-state 的门控基线 |
| `A4` | 分层 patch/replan | 作为 `dynamic_no_belief_state` 的前置能力 | 机制消融 |
| `A5` | 六阶段增强 + 动态恢复，但无显式 belief-state | `dynamic_no_belief_state` | 关键内部对照 |
| `A6` | Lite belief-state + runtime adjustment + 动作选择 | `lite_belief_state` | 最终方法 |

## 4. 推荐的论文主结果叙事
<!-- SID:experiment.group_mapping.paper_mainline -->

### 4.1 内部主比较

主线建议写成：

1. `static_top1`
   - 回答：静态单路径是否足够
2. `fixed_threshold_gate`
   - 回答：固定阈值门控是否已经够用
3. `dynamic_no_belief_state`
   - 回答：仅做动态恢复，不建模隐状态是否足够
4. `lite_belief_state`
   - 回答：Lite belief-state 是否带来额外价值

### 4.2 外部对照

外部对照只回答“方法风格差异”，不与内部机制消融混在一个表里：

- `E0`: ReAct 风格单轨迹代理
- `E1`: ToT 风格多分支推理
- `E2`: Reflexion 风格文本反思恢复

## 5. 指标解释与分组责任
<!-- SID:experiment.group_mapping.metric_responsibility -->

| 组别 | 必须回答的问题 | 重点指标 |
| --- | --- | --- |
| `static_top1` | 静态单链是否容易浪费高代价调用 | 成功率、成本、早停失败 |
| `fixed_threshold_gate` | 简单门控是否足够 | WAITING 命中正确率、人工介入率 |
| `dynamic_no_belief_state` | 动态 patch/replan 是否已有主要增益 | patch/replan 分配、恢复成功率 |
| `lite_belief_state` | belief-state 是否改善 runtime 决策质量 | 高代价调用次数、止损质量、整体成功率 |
| `E0-E2` | 与主流 agent 风格相比是否更稳健、可审计 | 成功率、时延、治理指标 |

## 6. 建议的主表结构
<!-- SID:experiment.group_mapping.table_layout -->

### 6.1 论文主表

内部主表：

- `static_top1`
- `fixed_threshold_gate`
- `dynamic_no_belief_state`
- `lite_belief_state`

外部主表：

- `lite_belief_state`
- `E0`
- `E1`
- `E2`

### 6.2 机制附表

附表再展示：

- `A1`
- `A2`
- `A4`

它们是机制增量组，不应挤占主结论空间。

## 7. 论文中的命名建议
<!-- SID:experiment.group_mapping.naming -->

建议在正文中统一使用以下名称：

- `Static Top-1`
- `Fixed Threshold Gate`
- `Dynamic Recovery (No Belief-State)`
- `Lite Belief-State`
- `ReAct Baseline`
- `ToT Baseline`
- `Reflexion Baseline`

把 `A0-A6` 只保留在：

- 实验附录
- 实施路线图
- issue/PR 追踪

## 8. 推荐结论主线
<!-- SID:experiment.group_mapping.claim_template -->

最稳妥的论文主命题建议是：

“在相近或更好的成功率下，Lite belief-state 驱动的动态工具链规划，能够更少地进入无效高代价调用，并更合理地分配 patch / suffix_replan / stop。”

这样：

- `static_top1` 负责说明静态链路不够；
- `fixed_threshold_gate` 负责说明简单规则不够；
- `dynamic_no_belief_state` 负责说明仅有动态恢复还不够；
- `lite_belief_state` 负责承接最终方法收益。
