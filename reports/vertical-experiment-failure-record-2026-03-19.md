# 纵向实验失败记录（A0-A6，2026-03-19）

## 1. 文档用途

- 记录 W12 Issue #171 纵向实验（A0-A6）在当前阶段未形成显著正向结果的事实。
- 为论文撰写提供“实验历程”材料，避免后续只保留成功结果而丢失关键分析过程。
- 本文档描述的是一次失败但可复现的实验批次，不代表系统主链不可运行，而是代表当前实验设计与运行条件不足以支撑方法有效性结论。

## 2. 对应实验批次

- run_id: `issue171-remote-batch3-r3`
- 配置文件: `configs/experiments/w12_issue171_vertical_a0_a6.json`
- 汇总结果: `output/experiment/w12-expr-2/issue171-remote-batch3-r3/vertical_metrics_summary.csv`
- 增量归因: `output/experiment/w12-expr-2/issue171-remote-batch3-r3/mechanism_increment_deltas.csv`
- 异常样本: `output/experiment/w12-expr-2/issue171-remote-batch3-r3/abnormal_samples.jsonl`
- 日志索引: `output/experiment/w12-expr-2/issue171-remote-batch3-r3/run_log_index.csv`

## 3. 失败现象摘要

- A0-A6 全组 `success_rate=0.0`。
- A0-A6 全组 `first_pass_success_rate=0.0`。
- A0-A6 全组 `schema_valid_rate=1.0`，说明问题不在候选 JSON 结构非法。
- 仅 `A2 -> A3` 的 `executable_plan_rate` 出现显著变化，从 `0.0` 变为 `1.0`。
- A3-A6 的 `duration_ms_mean=0.0`，说明这些组并未进入有效执行主链，而是在规划/门控阶段提前停止。

## 4. 直接观察结果

### 4.1 A0-A2：执行阶段失败后停在 WAITING_REPLAN

从 `run_log_index.csv` 可见，A0-A2 任务最终状态统一为 `WAITING_REPLAN`。

代表样本：

- `data/logs/issue171-remote-batch3-r3_A0_enzyme_like_fold_r01.jsonl`

该样本显示：

- 任务先经历 `CREATED -> PLANNING -> PLANNED -> RUNNING`
- 随后进入 `WAITING_PATCH -> PATCHING`
- 执行 `PARAM_TWEAK` 后恢复失败，出现 `RECOVERY_ESCALATED`
- 最终进入 `WAITING_REPLAN`
- `STEP_FAILED` 中记录错误：`Network error during job submission: [Errno 1] Operation not permitted`

这说明 A0-A2 的主要问题不是机制本身没有变化，而是执行链被外部运行失败主导，导致所有组都无法收敛到 `DONE`。

### 4.2 A3-A6：规划阶段被门控提前拦截

从 `run_log_index.csv` 可见，A3-A6 最终状态统一为 `WAITING_PLAN_CONFIRM`。

代表样本：

- `data/logs/issue171-remote-batch3-r3_A3_enzyme_like_fold_r01.jsonl`
- `data/logs/issue171-remote-batch3-r3_A4_enzyme_like_fold_r01.jsonl`
- `data/logs/issue171-remote-batch3-r3_A6_enzyme_like_fold_r01.jsonl`

这些样本显示：

- A3 的等待原因是 `plan_confirm_required`
- A4/A6 的等待原因是 `plan_low_confidence`
- 日志中存在 `PENDING_ACTION_CREATED` 和 `WAITING_ENTER`
- 但实验运行并未继续提交 `Decision`

这意味着 A3-A6 并不是“执行失败”，而是“实验驱动只跑到 HITL 等待点，没有继续完成决策回放”，因此也不可能产出成功率增益。

## 5. 为什么结果不明显

本次结果不明显，主要由以下四点共同造成：

1. 指标被统一压平。
   - A0-A6 全部 `success_rate=0.0`
   - `schema_valid_rate` 全部 `1.0`
   - 结果呈现两端饱和，缺乏中间分辨率

2. 前后组失败机理不同，导致横向不可直接比较。
   - A0-A2 主要反映执行环境/外部调用失败
   - A3-A6 主要反映门控后未继续决策

3. 实验驱动方式不完整。
   - 对自动组，没有稳定执行条件
   - 对 HITL 组，没有自动回放或固定 accept 策略

4. 样本规模偏小。
   - 当前配置仅 4 个任务，3 次重复，每组 12 个 run
   - 当 run 被同一类失败统一截断时，难以观测细粒度机制增益

## 6. 本次实验仍然产出的有效结论

尽管该批次不能支持“方法有效性显著提升”的结论，但仍有以下有效产出：

- 实验管线是可复现的，A0-A6 配置、日志索引、增量归因文件都完整生成。
- 候选结构合法性稳定，`schema_valid_rate=1.0`。
- A2->A3 的 `executable_plan_rate` 变化表明门控机制确实改变了系统行为。
- WAITING/HITL 机制在日志层面可见，但当前批次缺少后续 `Decision`，因此只能证明“能停住”，不能证明“停住后能继续成功完成”。

## 7. 论文中建议采用的表述口径

可以写：

- 本轮 A0-A6 纵向实验完成了配置冻结、批量运行、日志归档与统一评估，证明实验框架具备可复现性。
- 但该批次未能形成支持方法有效性提升的主结果。
- 原因在于两类非目标因素主导了结果分布：一是执行环境相关失败导致 A0-A2 停在恢复链路，二是 A3-A6 在 HITL 门控后未继续注入决策，导致实验终止于 `WAITING_PLAN_CONFIRM`。
- 因此，该批次更适合作为“失败实验记录与后续修正依据”，而非最终效果结论。

不建议写：

- “A0-A6 证明方法无效”
- “A3-A6 优于 A0-A2”
- “当前纵向实验已完成有效性验证”

## 8. 对下一轮实验的修正建议

- 为 A3-A6 增加固定决策回放策略，使 WAITING 组可以继续执行到终态。
- 为 A0-A2 提供更稳定的本地或 mock 执行条件，减少环境失败噪声。
- 将“自动闭环效果实验”和“HITL/治理实验”拆成两套口径，避免互相污染指标。
- 扩大任务规模，并单独补充 recovery 样本和 HITL 样本。

## 9. 结论

本次 `issue171-remote-batch3-r3` 应被明确记录为一次“失败但有效的纵向实验”：

- 失败在于未获得可支持论文主结论的正向效果结果；
- 有效在于其明确暴露了实验设计与执行条件中的关键缺口，并为下一轮实验修正提供了直接证据。
