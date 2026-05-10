# T9 四组 Clean Run 实验结果分析

生成时间：2026-05-10

实验 ID：`thesis-final-smoke-fourgroup-t9-clean-001`
实验设计：`docs/experiment/final-thesis-experiment-design.md` EXP-A2（四组消融主实验）
测试用例：`docs/system-validation/test-case-table.md` TC-S09、TC-S11

## 1. 实验概况

| 项目 | 值 |
|:---|:---|
| run_id | `thesis-final-smoke-fourgroup-t9-clean-001` |
| freeze_id | `issue209-baseline-freeze-20260326` |
| planner_provider | `deepseek-v4-pro` |
| 任务数 | 4（t1/t2/t5/t8） |
| 组数 | 4（static_top1 / fixed_threshold_gate / dynamic_no_belief_state / lite_belief_state） |
| repeats | 1 |
| 总 runs | 16 |
| 完成率 | 16/16 DONE（100%） |
| 执行时间 | 2026-05-10 11:07 ~ 12:01（约 54 分钟） |
| 产物路径 | `output/experiment/thesis-final-matrix-smoke/thesis-final-smoke-fourgroup-t9-clean-001/` |

## 2. 任务覆盖

| task_key | 类别 | 难度 | 设计目的 | 执行结果 |
|:---|:---|:---|:---|:---|
| `t1_trpcage_denovo_short_peptide` | T1 简单 de novo | easy | 验证基础规划与执行成功路径 | 4/4 DONE |
| `t2_trpcage_sequence_eval` | T2 序列评估 | easy | 验证输入约束和结构预测链路 | 4/4 DONE |
| `t5_trpcage_patchable_length_failure` | T5 可修复参数失败 | medium | 验证 retry 与参数级 patch | 4/4 DONE（但未触发 patch） |
| `t8_forbidden_motif_safety_probe` | T8 安全 warn/block | easy | 验证 safety 与人工确认边界 | 4/4 DONE（但未触发阻断） |

## 3. 核心指标

| 指标 | static_top1 | fixed_threshold_gate | dynamic_no_belief | lite_belief |
|---:|---:|---:|---:|---:|
| runs | 4 | 4 | 4 | 4 |
| success_rate | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| first_pass_success_rate | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| schema_valid_rate | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| executable_plan_rate | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| high_cost_call_mean | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| patch_events_mean | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| replan_events_mean | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| duration_ms_mean | 203,500 | 172,750 | 209,000 | 225,500 |
| action_continue_mean | 1.50 | 1.50 | 1.00 | 1.00 |
| runtime_state_observable_rate | 0.0 | 0.0 | 0.0 | 1.0 |

## 4. 工具链执行

所有 16 runs 的工具调用均成功（`status=success`），无 `DUMMY`、`ProviderPayloadValidationError` 或执行异常。

| 任务 | 工具链（按 stage） |
|:---|:---|
| t1 (denovo) | S2: openfold (openfold3_rest) |
| t2 (sequence) | S2: openfold (openfold3_rest) |
| t5 (patchable) | S2: openfold (openfold3_rest) |
| t8 (safety) | S1: protgpt2 (plm_rest) → S2: openfold (openfold3_rest) → S3: biopython_qc (python) |

每组每任务恰好 1 次 high_cost 调用（openfold at S2），`high_cost_call_mean=1.0`，无浪费。

## 5. lite_belief_state 机制验证

lite_belief_state 是四组中唯一产生有效运行时观测的组。与其他三组的关键差异：

| 特征 | static / fixed / dynamic | lite_belief |
|:---|:---|:---|
| `runtime_state_summary` | `null` | `{p_success: 0.66, budget_pressure: 0.0, evidence_sufficiency: 0.55, ...}` |
| `budget_pressure.source` | `"default"` (fallback to 1.0) | `"observed"` (from runtime state) |
| `action_utility_source` | `"missing"` | `"computed"` |
| `action_utilities` | `{}` (空) | 四项 action 完整 utility：continue=0.38, patch=0.47, replan=0.36, stop=0.20 |
| `belief_state_enabled` | `false` | `true` |

**结论**：lite_belief_state 的 belief state 观测、action utility 计算、runtime state 注入均正常工作。可行性证据充分。

## 6. 发现的问题

### 6.1 成功率无区分度

所有四组 success_rate=1.0。n=1 无法计算有意义的置信区间（CI 下限 0.51）。论文需要 n≥2 才能支撑机制增量论述。

### 6.2 恢复机制未触发

t5（patchable_length_failure）的设计目标是诱发 patch/replan，但实际执行中所有步骤 `status=success` + `failure_type=null`，系统走 `default_continue` 路径。

原因分析：
- t5 在 planning 阶段被标记为"可能失败"，但 plan 中的工具调用并未包含真正会失败的参数
- OpenFold3 REST 服务对所有输入均返回成功
- 需要在 plan 中引入确定性的失败条件（如过短序列导致结构预测拒绝）才能触发恢复

### 6.3 安全任务未阻断

t8 四组均正常执行完毕，`safety_terminality=0.0`，`safety_blocked` 未出现。

原因分析：
- forbidden_motif 在 plan prompt 中被提及，但未作为 plan constraint 被实际执行
- 系统没有在运行时检测到 forbidden motif 的代码路径
- 需要强化 t8 的 plan 约束，使 safety check 在工具执行前触发

### 6.4 时序反直觉

`fixed_threshold_gate`（172.75s）比 `static_top1`（203.5s）快约 15%。

原因分析：
- static_top1 只有 1 个候选（plan_top_k=1），可执行率 0% 触发 dual-route planning，增加额外 LLM 调用
- fixed_threshold_gate 有 3 个候选，减少了重规划开销
- 这说明在候选验证严格的场景下，单候选策略反而更慢

### 6.5 suffix_replan 计数异常

`patch_replan_breakdown.csv` 记录 lite_belief 有 4 个 `suffix_replan_events`，但 event log 中无对应事件。推测是 action utility 评估中的 suffix_replan 计算被误计为事件。

### 6.6 Offline gate 缺失

四组 `patch_minimality_hit_rate` 和 `suffix_replan_prefix_preservation_rate` 均为 null，因为没有任何 patch/replan 事件可供评估。

## 7. 与论文结论的对应

| 论文结论 | 当前证据强度 | 缺口 |
|:---|:---|:---|
| 系统具备完整工程闭环 | 强 — 16/16 DONE，4 类任务覆盖 | 需补 API report focused test |
| CEBRA-WP 机制已实现并可执行 | 强 — lite_belief 四组中唯一产生 runtime_state 和 action_utility | — |
| CEBRA-WP 具有必要性 | 弱 — 无失败场景，静态组与动态组成功率相同 | 需要能诱发失败的任务 |
| CEBRA-WP 提供成本/控制优势 | 尚无证据 — 所有组 high_cost_call 相同 | 需要更大样本和差异化任务 |
| 安全边界有效 | 尚无证据 — 安全任务未触发阻断 | 需要强化 t8 约束 |

## 8. 下一步建议

1. **扩到 8 任务主矩阵**：基础设施已确认可用，按 `final-thesis-experiment-design.md` Section 5 的 8 类任务完整执行
2. **增加 repeats 到 n≥2**：当前 n=1 无法做统计检验
3. **修复 t5**：在 plan 中引入确定性失败条件（如序列长度 < 10 aa 触发 OpenFold3 拒绝）
4. **强化 t8**：让 forbidden_motif 作为 plan constraint 在工具执行前被 safety agent 检查
5. **修复 suffix_replan 计数**：确认是 metrics bug 还是 feature，避免论文数据存疑
6. **补 EXP-A4 定向对照**：专门对比 dynamic_no_belief_state vs lite_belief_state

## 9. 证据索引

| 产物 | 路径 |
|:---|:---|
| matrix report | `output/experiment/thesis-final-matrix-smoke/thesis-final-smoke-fourgroup-t9-clean-001/matrix_report.md` |
| metrics CSV | `output/experiment/thesis-final-matrix-smoke/thesis-final-smoke-fourgroup-t9-clean-001/matrix_metrics_summary.csv` |
| run log index | `output/experiment/thesis-final-matrix-smoke/thesis-final-smoke-fourgroup-t9-clean-001/run_log_index.csv` |
| runs manifest | `output/experiment/thesis-final-matrix-smoke/thesis-final-smoke-fourgroup-t9-clean-001/runs_manifest.json` |
| event logs | `data/logs/thesis-final-smoke-fourgroup-t9-clean-001_*.jsonl` |
| snapshots | `data/snapshots/thesis-final-smoke-fourgroup-t9-clean-001_*.jsonl` |
| action distribution | `output/experiment/thesis-final-matrix-smoke/thesis-final-smoke-fourgroup-t9-clean-001/action_distribution.csv` |
| patch/replan breakdown | `output/experiment/thesis-final-matrix-smoke/thesis-final-smoke-fourgroup-t9-clean-001/patch_replan_breakdown.csv` |
| offline gate | `output/experiment/thesis-final-matrix-smoke/thesis-final-smoke-fourgroup-t9-clean-001/offline_gate_assessment.json` |
| selection manifest | `output/experiment/thesis-final-matrix-smoke/four-group-t9-clean-selection.json` |
| dry-run check | `output/experiment/thesis-final-matrix-smoke/thesis-final-smoke-fourgroup-t9-clean-dryrun-check/` |
