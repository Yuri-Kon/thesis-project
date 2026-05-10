# 第七章 实验与结果分析

第六章已验证系统在任务创建、状态控制、HITL、快照恢复、工具执行和审计追踪等方面具备可运行的工程基础。本章在该基础上分析 CEBRA-WP 相关策略在批量蛋白质设计工作流中的行为差异。实验目标限定为工作流层的规划、运行时观测、恢复控制和成本控制，不涉及候选蛋白的湿实验功能验证。

本章围绕四个研究问题展开：RQ-A1，CEBRA-WP 的运行时状态、候选重排和动作效用链路是否可执行、可追踪；RQ-A2，相比静态单链和静态门控，动态观测是否改变系统行为；RQ-A3，Lite belief-state 相比 dynamic_no_belief_state 是否提供额外机制信息；RQ-A4，失败和恢复案例是否能由事件日志、快照和候选 metadata 还原。

## 7.1 实验设计

实验采用四组内部消融设计：`static_top1`、`fixed_threshold_gate`、`dynamic_no_belief_state` 和 `lite_belief_state`。四组策略按照运行时介入深度递进：静态 Top-1 只选择静态最高分候选；固定门控组保留静态门控和 patch 触发；动态观测组保留恢复链路但不启用显式信念状态；Lite belief-state 组启用运行时状态、runtime adjustment 和 action utility。该设计借鉴了 LLM Agent 中“推理-行动”、候选搜索和失败反馈机制的思想[@yao2022react; @yao2023tot; @shinn2023reflexion]，但实验对象限定为本文系统中的工作流规划与恢复控制。

如图 7-1 所示，实验矩阵由任务集、策略组、评价指标和证据产物四部分组成。任务集提供不同难度、预算和失败压力；策略组用于隔离静态选择、固定门控、动态恢复和 Lite belief-state 的影响；评价指标覆盖成功率、首次成功、高代价调用、恢复事件和机制可观测性；证据产物由 run config、event log、snapshot、report 和聚合 CSV 组成。

【图 7-1 实验设计框架】
插图文件：`paper/figures/experiment-design-framework.drawio.svg`

图 7-1 的作用是限定本章统计结果的来源。后续表 7-1 至表 7-8 均来自 `thesis-final-v1-001` 实验矩阵及其配套日志、快照和聚合产物。

**表 7-1 实验矩阵配置表**

| 项目 | 配置 |
|---|---|
| run_id | `thesis-final-v1-001` |
| freeze_id | `issue209-baseline-freeze-20260326` |
| planner_provider | `deepseek-v4-pro` |
| 任务覆盖 | 12 个 task_keys，覆盖 T1 至 T8 共 8 类场景 |
| 策略组 | `static_top1` / `fixed_threshold_gate` / `dynamic_no_belief_state` / `lite_belief_state` |
| repeats | `low_cost_first=2`，`standard=2`，`high_cost_sensitive=1` |
| 总 runs | 84 runs，每组 21 runs |
| 终态结果 | 81 DONE，3 FAILED |
| 执行时间 | 约 6 小时 |
| 产物路径 | `../thesis-project.dev/output/experiment/thesis-final-matrix/thesis-final-v1-001/` |

任务集覆盖 8 类场景：简单 de novo 设计、序列评估、多约束稳定性优化、高代价结构预测、可修复参数失败、远程服务降级、结构性重规划和安全探测。涉及的公开结构包括 Trp-cage、Villin HP35、GB1、Ubiquitin、Top7 和 de novo oligomer。该任务集使实验同时包含低成本成功路径、中等压力路径和高代价结构预测路径。

## 7.2 指标定义

本章使用五类指标。任务完成指标包括 `success_rate`、`first_pass_success_rate`、`schema_valid_rate` 和 `executable_plan_rate`。恢复行为指标包括 `patch_events_mean`、`replan_events_mean` 和 `suffix_replan_events_mean`。成本指标包括 `high_cost_call_mean`、`high_cost_call_total` 和 `duration_ms_mean`，其中高代价调用在本实验中主要对应结构预测与结构精修。机制可观测性指标包括 `runtime_state_observable_rate`、`runtime_state_summary`、`budget_pressure source` 和 `action_utility_source`。增量指标使用相邻策略组的 paired delta。

patch/replan 事件来自 event log，表示实际执行过的恢复动作；action utility 来自候选 metadata，表示算法对 `continue`、`patch_local`、`suffix_replan` 和 `stop` 等动作的评分。两者含义不同，后文表格分别列示。

## 7.3 四组消融主结果

表 7-2 汇总四组策略的核心指标。每组 21 runs，static_top1 全部 DONE，其余三组各 1 个 FAILED。

**表 7-2 四组消融主实验结果**

| 指标 | static_top1 | fixed_threshold_gate | dynamic_no_belief | lite_belief |
|---|---:|---:|---:|---:|
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

表 7-2 显示出三个结果。第一，static_top1 在该矩阵中成功率最高，说明任务集中的多数初始候选已经具备较强可执行性。第二，fixed_threshold_gate 是唯一触发真实 patch 的组，平均 patch 次数为 0.2857，同时高代价调用总数升至 28。第三，lite_belief_state 是唯一 runtime_state_observable_rate 为 1.0000 的组，说明其信念状态链路在所有 run 中均产生可追踪输出。

## 7.4 分层结果与机制增量

表 7-3 按任务难度和预算层级汇总成功率。3 个 FAILED run 全部位于 medium/standard 层。

**表 7-3 按任务难度与预算分层的成功率**

| 分层 | runs | DONE | FAILED | success_rate |
|---|---:|---:|---:|---:|
| easy | 32 | 32 | 0 | 1.0000 |
| medium | 40 | 37 | 3 | 0.9250 |
| hard | 12 | 12 | 0 | 1.0000 |
| low_cost_first | 32 | 32 | 0 | 1.0000 |
| standard | 40 | 37 | 3 | 0.9250 |
| high_cost_sensitive | 12 | 12 | 0 | 1.0000 |

分层结果说明，失败主要来自中等难度、标准预算任务。具体任务中，`t2_ubiquitin_sequence_eval` 贡献 2 个 FAILED，`t3_gb1_stability_optimization` 贡献 1 个 FAILED。hard 层样本量较小，该行仅作为本矩阵中的观察事实。

表 7-4 给出相邻策略组的 paired delta。delta 为后一个策略组减前一个策略组。

**表 7-4 机制增量配对对比**

| 对比 | 指标 | delta | 样本数 | 结果含义 |
|---|---|---:|---:|---|
| static→fixed | success_rate | -0.0476 | 21 | fixed 组多 1 个失败。 |
| static→fixed | first_pass_success_rate | -0.0952 | 21 | fixed 组首次成功率下降。 |
| static→fixed | patch_event_count | +0.2857 | 21 | fixed 组触发真实 patch。 |
| static→fixed | high_cost_call_count | +0.3333 | 21 | fixed 组高代价调用增加。 |
| fixed→dynamic | high_cost_call_count | -0.3810 | 21 | dynamic 组高代价调用低于 fixed。 |
| fixed→dynamic | duration_ms | -73,667 | 21 | dynamic 组平均耗时低于 fixed。 |
| dynamic→lite | schema_valid_rate | +0.0476 | 21 | lite 组 schema valid 恢复到 1.0000。 |
| dynamic→lite | high_cost_call_count | 0.0000 | 21 | 两组高代价调用均值相同。 |
| dynamic→lite | duration_ms | +45,524 | 21 | lite 组平均耗时高于 dynamic。 |

表 7-4 表明，fixed_threshold_gate 引入了可观测的 patch 行为，也引入了额外高代价调用。dynamic_no_belief_state 相比 fixed_threshold_gate 降低了高代价调用和耗时。lite_belief_state 相比 dynamic_no_belief_state 的主要差异体现在 schema valid、runtime state 和 action utility 的机制信息。

## 7.5 成本与恢复行为分析

表 7-5 单独列出高代价调用和运行时间。fixed_threshold_gate 的高代价调用总数为 28，其中结构映射 27 次，结构精修 1 次；dynamic_no_belief_state 和 lite_belief_state 均为 20 次。

**表 7-5 高代价调用与运行时间对比**

| 组 | high_cost_total | high_cost_mean | 结构映射 | 结构精修 | 平均耗时 |
|---|---:|---:|---:|---:|---:|
| static_top1 | 21 | 1.0000 | 21 | 0 | 241,905 ms |
| fixed_threshold_gate | 28 | 1.3333 | 27 | 1 | 300,238 ms |
| dynamic_no_belief_state | 20 | 0.9524 | 20 | 0 | 226,571 ms |
| lite_belief_state | 20 | 0.9524 | 20 | 0 | 272,095 ms |

与 fixed_threshold_gate 相比，dynamic_no_belief_state 和 lite_belief_state 的高代价调用总数从 28 降至 20，降幅为 28.6%。与 static_top1 相比，两组高代价调用总数从 21 降至 20，差异来自各自 1 个失败 run 在高代价结构预测前终止。运行时间上，dynamic_no_belief_state 最短，fixed_threshold_gate 最长，lite_belief_state 介于二者之间。

恢复事件方面，四组均未产生真实 replan 或 suffix replan；真实 patch 仅出现在 fixed_threshold_gate 组，总数 6 次，均为 tool-level patch。该结果说明，本次矩阵对 patch 机制产生了真实压力，对 replan 机制的矩阵级触发不足；第六章中的 focused tests 已覆盖 replan 和 terminal_stop 的可达性，本章的批量实验结论以 patch 和高代价调用为主。

## 7.6 Lite belief-state 机制可观测性

表 7-6 对比 Lite belief-state 与其余三组的机制可观测性。该表对应 RQ-A1 和 RQ-A3。

**表 7-6 Lite belief-state 机制可观测性对比**

| 特征 | static_top1 / fixed_threshold_gate / dynamic_no_belief_state | lite_belief_state |
|---|---|---|
| runtime_state_summary | 无有效运行时状态摘要 | 21/21 runs 产生 RuntimeState |
| runtime_state_observable_rate | 0.0000 | 1.0000 |
| belief-state 核心字段 | 未观测 | `p_success`、`p_structural_failure`、`recovery_margin`、`expected_remaining_cost`、`evidence_sufficiency` |
| budget_pressure source | `default` | `observed` |
| action_utility_source | `missing` | `computed` |
| action_utilities | 空对象或不可用 | `continue`、`patch_local`、`suffix_replan`、`stop` 均有 utility |
| high_cost_call_mean | static=1.0000，fixed=1.3333，dynamic=0.9524 | 0.9524 |

Lite belief-state 的核心证据是 21/21 runs 均产生有效 RuntimeState，且 budget pressure 来自运行时观测而非默认回退。该结果说明，CEBRA-WP 的信念状态更新、预算压力估计和动作效用计算均已在矩阵实验中执行。与 dynamic_no_belief_state 相比，lite_belief_state 的 success_rate 和 high_cost_call_mean 相同，增量主要体现为完整的运行时状态和动作效用记录。

## 7.7 典型失败案例

如图 7-2 所示，fixed_threshold_gate 和 lite_belief_state 的恢复控制路径不同。fixed_threshold_gate 主要体现为运行时门控后的 patch；lite_belief_state 则在候选评估阶段产生 RuntimeState、runtime adjustment 和 action utility，并据此影响候选排序。

【图 7-2 固定修补与信念状态重排序的恢复路径对比】
插图文件：`paper/figures/recovery-path-comparison-timeline.drawio.svg`

图 7-2 用于解释表 7-7 中的失败案例。fixed_threshold_gate 的失败体现为 patch 循环耗尽；lite_belief_state 的失败体现为运行时状态可观测但仍未打破循环；dynamic_no_belief_state 的失败体现为候选 I/O 闭包校验失败。

**表 7-7 失败案例归因表**

| 策略组 | 任务 | repeat | 错误类型 | 根因摘要 | 证据意义 |
|---|---|---:|---|---|---|
| fixed_threshold_gate | `t2_ubiquitin_sequence_eval` | r02 | auto decision loop exhausted | 固定门控触发 WAITING_PATCH 循环，patch 后仍触发相同门控条件。 | 说明静态门控可以触发恢复，也可能引入额外循环和高代价调用。 |
| lite_belief_state | `t2_ubiquitin_sequence_eval` | r01 | auto decision loop exhausted | 多次 WAITING_PATCH 循环中 budget_pressure 升至 1.5，runtime adjustment 已产生但未打破循环。 | 说明 belief-state 链路可观测，且该机制仍受候选质量和循环控制限制。 |
| dynamic_no_belief_state | `t3_gb1_stability_optimization` | r01 | `CANDIDATE_IO_CLOSURE_BROKEN` | 候选 step 输出字段无法被下游引用，候选验证在执行前失败。 | 说明候选可执行性校验能够阻断无效 plan。 |

三个失败案例均有 event log 和 snapshot，是可追溯的边界样本。fixed_threshold_gate 的 t2 案例解释了表 7-5 中高代价调用增加的来源；lite_belief_state 的 t2 案例展示了 RuntimeState 的动态演化；dynamic_no_belief_state 的 t3 案例对应表 7-2 中 schema_valid_rate=0.9524。

## 7.8 证据产物与本章结论

表 7-8 汇总本章使用的实验产物。所有核心结论均可回溯到矩阵报告、CSV 聚合、run 级结果、事件日志或快照。

**表 7-8 实验结果证据产物索引**

| 证据产物 | 路径/来源 | 支撑内容 | 使用位置 |
|---|---|---|---|
| 实验结果报告 | `../thesis-project.dev/docs/experiment/thesis-final-v1-results.md` | 84-run 概况、主结果、分层结果、失败案例 | 全章 |
| 实验设计文档 | `../thesis-project.dev/docs/experiment/final-thesis-experiment-design.md` | 研究问题、任务类、指标体系 | 7.1、7.2 |
| 分组映射文档 | `../thesis-project.dev/docs/experiment/algorithm-group-paper-mapping.md` | 代码 policy mode 与论文组名对应关系 | 7.1 |
| 主指标汇总 | `matrix_metrics_summary.csv` | 四组主指标、成功率、恢复、耗时和高代价调用 | 7.3、7.6 |
| 机制增量表 | `mechanism_increment_deltas.csv` | 相邻策略组 paired delta | 7.4 |
| 高代价调用表 | `high_cost_breakdown.csv` | 高代价调用总数和规则命中 | 7.5 |
| 恢复事件表 | `patch_replan_breakdown.csv`、`action_distribution.csv` | patch/replan/action 分布 | 7.5 |
| run 级结果 | `run_level_results.jsonl` | 失败案例、RuntimeState、tool usage、artifact linkage | 7.6、7.7 |
| 事件日志与快照 | `data/logs/thesis-final-v1-001_*.jsonl`、`data/snapshots/thesis-final-v1-001_*.jsonl` | 决策链、恢复链、运行时状态和失败追踪 | 7.7 |

本章得到以下结论。第一，CEBRA-WP 的机制链路在批量实验中可执行、可追踪，lite_belief_state 组 21/21 runs 产生 RuntimeState，runtime_state_observable_rate 为 1.0000。第二，fixed_threshold_gate 触发 6 次真实 patch，同时高代价调用总数达到 28，说明静态门控能够暴露恢复需求，也带来额外执行成本。第三，dynamic_no_belief_state 与 lite_belief_state 的 high_cost_call_mean 均为 0.9524，低于 fixed_threshold_gate 的 1.3333；lite 的主要增量体现在信念状态、预算压力和动作效用的可观测性。第四，3 个 FAILED run 均有可追溯事件链，失败集中在 medium/standard 层，主要反映候选验证、patch 循环和运行时控制的边界条件。

在当前 `thesis-final-v1-001` 设置下，实验支持“CEBRA-WP 机制已实现且可观测”“固定门控恢复存在额外成本”“Lite belief-state 提供运行时决策解释信息”等结论。成功率方面，static_top1 为 1.0000，其余三组为 0.9524，最终成功率提升并非本章的主要实验结论。
