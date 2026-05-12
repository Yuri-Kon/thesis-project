# 第七章 实验与结果分析

第六章已经验证系统在任务创建、状态控制、HITL、快照恢复、工具执行和审计追踪等方面具备可运行的工程基础。本章在此基础上，继续分析 CEBRA-WP 相关策略在批量蛋白质设计工作流中的行为差异。实验目标限定在工作流层的规划、运行时观测、恢复控制和成本控制，不涉及候选蛋白的湿实验功能验证。

本章围绕四个研究问题展开：

1.  RQ-A1：CEBRA-WP 的运行时状态、候选重排和动作效用链路是否可执行、可追踪。

2.  RQ-A2：相比静态单链和固定阈值门控，动态观测是否改变系统行为。

3.  RQ-A3：Lite belief-state / 轻量信念状态相比 `dynamic_no_belief_state` 是否提供额外机制信息。

4.  RQ-A4：失败和恢复案例是否能由事件日志、快照和候选 metadata 还原。

## 7.1 实验设计

实验采用四组内部消融设计：`static_top1`、`fixed_threshold_gate`、`dynamic_no_belief_state` 和 `lite_belief_state`。四组策略按照运行时介入深度递进：静态 Top-1 只选择静态最高分候选；固定阈值门控组保留阈值门控和局部修补触发；动态观测组保留恢复链路但不启用显式 Lite belief-state / 轻量信念状态；`lite_belief_state` 组启用运行时状态、runtime adjustment 和 action utility。该设计借鉴了 LLM Agent 中“推理-行动”、候选搜索和失败反馈机制的思想[8,20,21]，但实验对象限定为本系统中的工作流规划与恢复控制。

如图 7-1 所示，实验矩阵由任务集、策略组、评价指标和证据产物四部分组成。任务集提供不同难度、预算和失败压力；策略组用于隔离静态选择、固定阈值门控、动态恢复和 Lite belief-state / 轻量信念状态的影响；评价指标关注成功率、首次成功、高代价调用、恢复事件和机制可观测性；证据产物包括 run config、event log、snapshot、report 和聚合 CSV。

【图 7-1 实验设计框架】

图 7-1 的作用是限定本章统计结果的来源。后续表 7-1 至表 7-8 均来自 thesis-final-v1-001 实验矩阵及其配套日志、快照和聚合产物；对应内部证据入口为 ../thesis-project.dev/docs/experiment/thesis-final-v1-results.md 和 ../thesis-project.dev/output/experiment/thesis-final-matrix/thesis-final-v1-001/。

| 项目 | 配置 |
|:--:|:--:|
| run_id | thesis-final-v1-001 |
| freeze_id | issue209-baseline-freeze-20260326 |
| planner_provider | deepseek-v4-pro |
| 任务覆盖 | 12 个 task_keys，覆盖 T1 至 T8 共 8 类场景 |
| 策略组 | `static_top1` / `fixed_threshold_gate` / `dynamic_no_belief_state` / `lite_belief_state` |
| repeats | low_cost_first=2，standard=2，high_cost_sensitive=1 |
| 总 runs | 84 runs，每组 21 runs |

表 7-1 实验矩阵配置表

表 7-1（续表）

| 项目 | 配置 |
|:--:|:--:|
| 终态结果 | 81 DONE，3 FAILED |
| 执行时间 | 约 6 小时 |
| 产物路径 | ../thesis-project.dev/output/experiment/thesis-final-matrix/thesis-final-v1-001/ |

任务集覆盖 8 类场景：简单 de novo 设计、序列评估、多约束稳定性优化、高代价结构预测、可修复参数失败、远程服务降级、结构性重规划和安全探测。涉及的公开结构包括 Trp-cage、Villin HP35、GB1、Ubiquitin、Top7 和 de novo oligomer。任务定义与分层依据来自 ../thesis-project.dev/docs/experiment/final-thesis-experiment-design.md 和 ../thesis-project.dev/docs/experiment/thesis-final-v1-results.md。该任务集使实验同时包含低成本成功路径、中等压力路径和高代价结构预测路径。

## 7.2 指标定义

本章使用五类指标。任务完成指标包括 success_rate、first_pass_success_rate、schema_valid_rate 和 executable_plan_rate。恢复行为指标包括 patch_events_mean、replan_events_mean 和 suffix_replan_events_mean。成本指标包括 high_cost_call_mean、high_cost_call_total 和 duration_ms_mean，其中高代价调用在本实验中主要对应结构预测与结构精修。机制可观测性指标包括 runtime_state_observable_rate、runtime_state_summary、budget_pressure source 和 action_utility_source。增量指标使用相邻策略组的 paired delta。

局部修补/重规划事件来自 event log，表示实际执行过的恢复动作；action utility 来自候选 metadata，表示算法对 continue、`patch_local`、`suffix_replan` 和 stop 等动作的评分。两者含义不同，后文表格分别列示。

## 7.3 四组消融主结果

表 7-2 汇总四组策略的核心指标。每组 21 runs，`static_top1` 全部 DONE，其余三组各 1 个 FAILED。

| 指标 | `static_top1` | `fixed_threshold_gate` | `dynamic_no_belief_state` | `lite_belief_state` |
|:--:|:--:|:--:|:--:|:--:|
| runs | 21 | 21 | 21 | 21 |
| DONE | 21 | 20 | 20 | 20 |
| FAILED | 0 | 1 | 1 | 1 |
| success_rate | 1.0000 | 0.9524 | 0.9524 | 0.9524 |
| first_pass_success_rate | 1.0000 | 0.9048 | 0.9524 | 0.9524 |
| schema_valid_rate | 1.0000 | 1.0000 | 0.9524 | 1.0000 |
| executable_plan_rate | 1.0000 | 0.9524 | 1.0000 | 1.0000 |
| waiting_chain_complete_rate | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| failure_traceable_rate | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| runtime_state_observable_rate | 0.0000 | 0.0000 | 0.0000 | 1.0000 |
| patch_events_mean | 0.0000 | 0.2857 | 0.0000 | 0.0000 |
| replan_events_mean | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| suffix_replan_events_mean | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| high_cost_call_mean | 1.0000 | 1.3333 | 0.9524 | 0.9524 |
| high_cost_call_total | 21 | 28 | 20 | 20 |
| duration_ms_mean | 241,905 | 300,238 | 226,571 | 272,095 |
| action_continue_mean | 1.0952 | 1.5238 | 0.9524 | 0.9524 |
| action_patch_local_mean | 0.0000 | 0.2857 | 0.0000 | 0.0000 |

表 7-2 四组消融主实验结果

表 7-2 可以看出三个现象。第一，`static_top1` 在该矩阵中成功率最高，说明任务集中的多数初始候选已经具有较强可执行性。第二，`fixed_threshold_gate` 是唯一触发真实局部修补的组，平均局部修补次数为 0.2857，高代价调用总数也升至 28。第三，`lite_belief_state` 是唯一 runtime_state_observable_rate 达到 1.0000 的组，说明其 Lite belief-state / 轻量信念状态链路在所有 run 中都产生了可追踪输出。

## 7.4 分层结果与机制增量

表 7-3 按任务难度和预算层级汇总成功率。3 个 FAILED run 全部位于 medium/standard 层。

|        分层         | runs | DONE | FAILED | success_rate |
|:-------------------:|:----:|:----:|:------:|:------------:|
|        easy         |  32  |  32  |   0    |    1.0000    |
|       medium        |  40  |  37  |   3    |    0.9250    |
|        hard         |  12  |  12  |   0    |    1.0000    |
|   low_cost_first    |  32  |  32  |   0    |    1.0000    |
|      standard       |  40  |  37  |   3    |    0.9250    |
| high_cost_sensitive |  12  |  12  |   0    |    1.0000    |

表 7-3 按任务难度与预算分层的成功率

分层结果说明，失败主要来自中等难度、标准预算任务。具体任务中，t2_ubiquitin_sequence_eval 贡献 2 个 FAILED，t3_gb1_stability_optimization 贡献 1 个 FAILED。hard 层样本量较小，该行仅作为本矩阵中的观察事实。

表 7-4 给出相邻策略组的 paired delta。delta 为后一个策略组减前一个策略组。

| 对比 | 指标 | delta | 样本数 | 结果含义 |
|:--:|:--:|:--:|:--:|:--:|
| static→fixed | success_rate | -0.0476 | 21 | fixed 组多 1 个失败。 |
| static→fixed | first_pass_success_rate | -0.0952 | 21 | fixed 组首次成功率下降。 |
| static→fixed | patch_event_count | +0.2857 | 21 | `fixed_threshold_gate` 组触发真实局部修补。 |
| static→fixed | high_cost_call_count | +0.3333 | 21 | fixed 组高代价调用增加。 |
| fixed→dynamic | high_cost_call_count | -0.3810 | 21 | dynamic 组高代价调用低于 fixed。 |
| fixed→dynamic | duration_ms | -73,667 | 21 | dynamic 组平均耗时低于 fixed。 |

表 7-4 机制增量配对对比

表 7-4（续表）

| 对比 | 指标 | delta | 样本数 | 结果含义 |
|:--:|:--:|:--:|:--:|:--:|
| dynamic→lite | schema_valid_rate | +0.0476 | 21 | lite 组 schema valid 恢复到 1.0000。 |
| dynamic→lite | high_cost_call_count | 0.0000 | 21 | 两组高代价调用均值相同。 |
| dynamic→lite | duration_ms | +45,524 | 21 | lite 组平均耗时高于 dynamic。 |

表 7-4 表明，`fixed_threshold_gate` 引入了可观测的局部修补行为，同时带来额外高代价调用。`dynamic_no_belief_state` 相比 `fixed_threshold_gate` 降低了高代价调用和耗时。`lite_belief_state` 相比 `dynamic_no_belief_state` 的主要差异，则体现在 schema valid、`RuntimeState` 和 action utility 等机制信息上。

## 7.5 成本与恢复行为分析

表 7-5 单独列出高代价调用和运行时间。`fixed_threshold_gate` 的高代价调用总数为 28，其中结构映射 27 次，结构精修 1 次；`dynamic_no_belief_state` 和 `lite_belief_state` 均为 20 次。

| 组 | high_cost_total | high_cost_mean | 结构映射 | 结构精修 | 平均耗时 |
|:--:|:--:|:--:|:--:|:--:|:--:|
| `static_top1` | 21 | 1.0000 | 21 | 0 | 241,905 ms |
| `fixed_threshold_gate` | 28 | 1.3333 | 27 | 1 | 300,238 ms |
| `dynamic_no_belief_state` | 20 | 0.9524 | 20 | 0 | 226,571 ms |
| `lite_belief_state` | 20 | 0.9524 | 20 | 0 | 272,095 ms |

表 7-5 高代价调用与运行时间对比

由表 7-5 可计算得出，与 `fixed_threshold_gate` 相比，`dynamic_no_belief_state` 和 `lite_belief_state` 的高代价调用总数从 28 降至 20，降幅为 28.6%。与 `static_top1` 相比，两组高代价调用总数从 21 降至 20，差异来自各自 1 个失败 run 在高代价结构预测前终止。运行时间上，`dynamic_no_belief_state` 最短，`fixed_threshold_gate` 最长，`lite_belief_state` 介于二者之间。

恢复事件方面，四组均未产生真实重规划或后缀重规划；真实局部修补只出现在 `fixed_threshold_gate` 组，总数为 6 次，且均为 tool-level patch。这个结果说明，本次矩阵确实给局部修补机制带来了压力，但对重规划机制的矩阵级触发仍然不足。第六章中的 focused tests 已覆盖后缀重规划和 `terminal_stop` 的可达性，因此本章批量实验结论主要围绕局部修补和高代价调用展开。

## 7.6 Lite belief-state 机制可观测性

表 7-6 对比 Lite belief-state 与其余三组的机制可观测性。该表对应 RQ-A1 和 RQ-A3。

<table>
<caption><p>表 7-6 Lite belief-state 机制可观测性对比</p></caption>
<colgroup>
<col style="width: 34%" />
<col style="width: 37%" />
<col style="width: 28%" />
</colgroup>
<thead>
<tr>
<th style="text-align: center;">特征</th>
<th style="text-align: center;">`static_top1` / `fixed_threshold_gate` / `dynamic_no_belief_state`</th>
<th style="text-align: center;">`lite_belief_state`</th>
</tr>
</thead>
<tbody>
<tr>
<td style="text-align: center;">runtime_state_summary</td>
<td style="text-align: center;">无有效运行时状态摘要</td>
<td style="text-align: center;">21/21 runs 产生 `RuntimeState`</td>
</tr>
<tr>
<td style="text-align: center;">runtime_state_observable_rate</td>
<td style="text-align: center;">0.0000</td>
<td style="text-align: center;">1.0000</td>
</tr>
<tr>
<td style="text-align: center;">belief-state 核心字段</td>
<td style="text-align: center;">未观测</td>
<td style="text-align: center;"><p><span class="math inline"><em>p</em><sub>succ</sub></span>、<span class="math inline"><em>p</em><sub>sf</sub></span></p>
<p>、<span class="math inline"><em>r</em><sub>rec</sub></span>、<span class="math inline"><em>c</em><sub>rem</sub></span>、<span class="math inline"><em>e</em><sub>suf</sub></span></p></td>
</tr>
<tr>
<td style="text-align: center;">budget_pressure source</td>
<td style="text-align: center;">default</td>
<td style="text-align: center;">observed</td>
</tr>
<tr>
<td style="text-align: center;">action_utility_source</td>
<td style="text-align: center;">missing</td>
<td style="text-align: center;">computed</td>
</tr>
<tr>
<td style="text-align: center;">action_utilities</td>
<td style="text-align: center;">空对象或不可用</td>
<td style="text-align: center;">continue、`patch_local`、`suffix_replan`、stop 均有 utility</td>
</tr>
<tr>
<td style="text-align: center;">high_cost_call_mean</td>
<td style="text-align: center;">static=1.0000，fixed=1.3333，dynamic=0.9524</td>
<td style="text-align: center;">0.9524</td>
</tr>
</tbody>
</table>

Lite belief-state / 轻量信念状态的核心证据是 21/21 runs 均产生有效 `RuntimeState`，且 budget pressure 来自运行时观测而非默认回退。该结果说明，CEBRA-WP 的运行时状态更新、预算压力估计和动作效用计算均已在矩阵实验中执行。与 `dynamic_no_belief_state` 相比，`lite_belief_state` 的 success_rate 和 high_cost_call_mean 相同，其增量主要体现为完整的 `RuntimeState` 和动作效用记录。

## 7.7 典型失败案例

如图 7-2 所示，`fixed_threshold_gate` 和 `lite_belief_state` 的恢复控制路径不同。`fixed_threshold_gate` 主要体现为运行时门控后的局部修补；`lite_belief_state` 则在候选评估阶段产生 `RuntimeState`、runtime adjustment 和 action utility，并据此影响候选排序。

【图 7-2 固定修补与 Lite belief-state 重排序的恢复路径对比】

图 7-2 用于说明下文三个失败案例：`fixed_threshold_gate` 的问题是局部修补循环耗尽；`lite_belief_state` 的问题是运行时状态可观测但仍未打破循环；`dynamic_no_belief_state` 的问题则是候选 I/O 闭包校验失败。

实验中共有 3 个 FAILED runs，分别来自 `fixed_threshold_gate`、`lite_belief_state` 和 `dynamic_no_belief_state` 三个策略组。三个失败案例均保留了完整 event log 与 snapshot，因此可以作为可追溯的边界样本，用于分析机制行为和失败来源。

`fixed_threshold_gate` 策略组中，任务 t2_ubiquitin_sequence_eval 的 r02 重复实验出现 auto decision loop exhausted 错误。该案例里，固定阈值门控在多轮执行过程中持续触发 `WAITING_PATCH` 循环。系统虽然生成并执行了局部修补（`patch_local`）候选，但修补后的候选仍再次满足相同门控条件，于是流程反复进入恢复链路，最后耗尽自动决策循环预算并失败。该案例说明，固定阈值门控可以真实触发恢复路径，但也可能带来额外循环和高代价调用；表 7-5 中 `fixed_threshold_gate` 组高代价调用次数增加，主要就来自这一类行为。

`lite_belief_state` 策略组中，任务 t2_ubiquitin_sequence_eval 的 r01 同样出现 auto decision loop exhausted 错误。与固定阈值策略不同，该案例能够持续生成 `RuntimeState`，并记录 belief-state 的变化。event log 显示，多次 `WAITING_PATCH` 循环中 budget_pressure 逐渐上升至 1.5，runtime adjustment 已被触发，但仍未打破循环结构，最终耗尽自动决策预算。这个样本说明，belief-state 链路确实具备可观测性和动态状态表达能力；同时也提醒，恢复效果仍受候选质量和循环控制机制限制。`RuntimeState` 的动态演化，在该失败样本中得到了完整记录。

`dynamic_no_belief_state` 策略组中，任务 t3_gb1_stability_optimization 的 r01 出现 CANDIDATE_IO_CLOSURE_BROKEN 错误。系统在候选验证阶段发现部分 step 的输出字段不能被后续 step 正确引用，因此在执行前就把该 plan 判定为不可执行。该案例说明候选可执行性校验可以提前阻断结构无效的 plan，避免后续工具调用进入错误状态；它也对应表 7-2 中 schema_valid_rate=0.9524 的来源。

## 7.8 证据产物与本章结论

本章所有核心结论均可回溯到矩阵报告、CSV 聚合、run 级结果、事件日志或快照。

本章实验得到四点结论。在当前实验矩阵中，CEBRA-WP 的机制链路可执行、可追踪，`lite_belief_state` 组 21/21 runs 产生 `RuntimeState`，runtime_state_observable_rate 为 1.0000。`fixed_threshold_gate` 触发 6 次真实局部修补，高代价调用总数达到 28，说明固定阈值门控能够暴露恢复需求，同时也会带来额外执行成本。`dynamic_no_belief_state` 与 `lite_belief_state` 的 high_cost_call_mean 均为 0.9524，低于 `fixed_threshold_gate` 的 1.3333；lite 的主要增量体现在 Lite belief-state / 轻量信念状态、预算压力和动作效用的可观测性。3 个 FAILED run 均有可追溯事件链，失败集中在 medium/standard 层，主要反映候选验证、局部修补循环和运行时控制的边界条件。

在当前 thesis-final-v1-001 设置下，实验支持“CEBRA-WP 机制已实现且可观测”、“固定阈值门控恢复存在额外成本”、“Lite belief-state / 轻量信念状态提供运行时决策解释信息”等结论。成功率方面，`static_top1` 为 1.0000，其余三组为 0.9524，最终成功率提升并非本章的主要实验结论。

第八章将结合上述实验结论与边界，总结本文贡献并讨论后续改进方向。
