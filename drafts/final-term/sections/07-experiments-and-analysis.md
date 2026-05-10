# 第七章：策略对比实验与结果分析（草稿）

> 状态：初稿 · 2026-05-11 · 目标章节文件 `chapters/07-experiments.tex`
> 实验数据：`docs/experiment/thesis-final-v1-results.md`（thesis-final-v1-001，84 runs）
> 实验设计依据：`docs/experiment/final-thesis-experiment-design.md`

---

## 7.1 实验设计与研究问题

第 6 章验证了系统功能的正确性——API 合约稳定、FSM 迁移合法、HITL 边界严格、恢复路径可达。本章在此基础上回答递进的问题：**CEBRA-WP 的运行时自适应机制在真实多任务场景中是否产生了可观测的效果，以及这种效果的性质和边界是什么。**

实验围绕四个研究问题（RQ-A1 至 RQ-A4）组织：

- **RQ-A1（可行性）**：CEBRA-WP 的 policy mode、belief-state 更新、runtime rerank、action utility 和后验目标评分能否在代码层面正确执行并产生可追踪的输出？
- **RQ-A2（必要性）**：相比静态规划（static_top1 和 fixed_threshold_gate），引入运行时观测和动态恢复是否改变了系统的行为模式？
- **RQ-A3（增量价值）**：Lite belief-state 相比"有动态观测但无显式信念状态"（dynamic_no_belief_state），是否产生了额外的决策差异？
- **RQ-A4（可解释性）**：算法的决策依据是否能通过事件日志、候选 metadata 和运行时状态摘要被还原和复核？

实验采用四组内部消融设计（static_top1 / fixed_threshold_gate / dynamic_no_belief_state / lite_belief_state），对应算法介入深度的四个递进层次。任务集覆盖 de novo 设计、序列评估、稳定性优化、高代价结构预测、可修复参数失败、远程服务降级、结构性重规划和安全性探测共 8 类设计场景，涉及 12 个 task_key，基于 6 个公开蛋白质结构（Trp-cage 1L2Y、Villin HP35 1VII、GB1 1PGB/2GB1、Ubiquitin 1UBQ、Top7 1QYS、de novo oligomer 5J0H）。每组 21 runs，总计 84 runs，其中 low_cost_first 任务 repeat=2，standard 任务 repeat=2，high_cost_sensitive 任务 repeat=1。

实验设计框架如图 7-1 所示。图中将 84-run 矩阵拆分为任务集合、四组策略、评价指标和证据产物四个层次：任务集合提供不同难度、预算和失败压力；四组策略用于隔离静态选择、固定门控、动态恢复和 Lite belief-state 的贡献；评价指标覆盖成功率、首次成功、高代价调用、恢复事件和运行时状态可观测性；证据产物则由 run_config、event log、snapshot 和矩阵汇总文件构成。后文表 7-1 至表 7-8 均来自这一实验框架下的聚合结果或证据索引。

> **图 7-1**：实验设计框架图，展示任务集、四组策略、指标体系和证据产物之间的关系。来源：`paper/figures/experiment-design-framework.drawio.svg` / `paper/figures/experiment-design-framework.drawio.png`。

为了让实验章节不仅依赖图示说明，表 7-1 先给出实验矩阵配置。该表固定本章所有统计结果的实验范围，后续主结果、分层结果和案例分析均不超出该范围。

**表 7-1：实验矩阵配置表**

| 项目 | 配置 |
|:---|:---|
| run_id | `thesis-final-v1-001` |
| freeze_id | `issue209-baseline-freeze-20260326` |
| planner_provider | `deepseek-v4-pro` |
| 任务覆盖 | 12 个 task_keys，覆盖 T1 至 T8 共 8 类场景 |
| 策略组 | static_top1 / fixed_threshold_gate / dynamic_no_belief_state / lite_belief_state |
| repeats | low_cost_first=2，standard=2，high_cost_sensitive=1 |
| 总 runs | 84 runs，每组 21 runs |
| 完成情况 | 81/84 DONE，3 FAILED |
| 执行时间 | 约 6 小时 |
| 产物路径 | `output/experiment/thesis-final-matrix/thesis-final-v1-001/` |

表 7-1 的作用是限制结论边界：本章结论只针对该任务集、该运行配置和该实验产物成立，不扩大为所有蛋白质设计任务上的一般性性能结论。

---

## 7.2 指标体系

实验采集的指标按分析维度分为五类。

**任务完成指标**：success_rate（进入 DONE 的比例）、first_pass_success_rate（无 patch/replan 即成功的比例）、schema_valid_rate（候选通过 schema 校验的比例）、executable_plan_rate（候选通过可执行性验证的比例）。

**恢复行为指标**：patch_events_mean（平均 patch 次数）、replan_events_mean（平均 replan 次数）、suffix_replan_events_mean（平均后缀重规划次数）。patch 和 replan 事件从 event log 中提取，与候选 metadata 中的 action_utilities 区分——后者是算法评估的效用值，前者是实际执行的恢复动作。

**成本控制指标**：high_cost_call_mean（高代价工具调用均值）、high_cost_call_total（总调用次数）、duration_ms_mean（平均运行耗时）。高代价工具在当前实验环境中定义为 openfold（结构预测）和结构精修工具，它们涉及远程 OpenFold3 REST 服务调用，单次耗时 60-120 秒。

**信念状态指标**（仅 lite_belief_state 组产生）：runtime_state_observable_rate（产生有效 RuntimeState 的 run 比例）、budget_pressure source（预算压力来源：observed vs default fallback）、action_utility_source（动作效用的计算来源：computed vs missing）。

**增量分析指标**：通过配对对比（paired delta）衡量相邻策略组之间的指标变化幅度和方向。

---

## 7.3 实验环境与执行配置

实验在统一环境下执行。Planner 使用 deepseek-v4-pro 模型，通过 Anthropic 兼容 API 调用。工具执行环境：序列生成为 ProtGPT2 PLM REST 远程服务（`execution_mode=plm_rest`），结构预测为 OpenFold3 REST 远程服务（`execution_mode=openfold3_rest`），质量控制为 BioPython QC 本地 Python 脚本。任务通过 `scripts/run_thesis_experiment_matrix.py` 批量执行，每个 run 独立记录 run_config、event_log_path、snapshot_path 和 report_path。矩阵聚合产物包括 `matrix_metrics_summary.csv`、`mechanism_increment_deltas.csv`、`high_cost_breakdown.csv` 和 `action_distribution.csv`。

实验总耗时约 6 小时，81/84 runs 进入 DONE 终态，3 runs 进入 FAILED。三个失败案例均产生完整的 event log 和 snapshot，未出现静默崩溃或产物缺失。

---

## 7.4 CEBRA-WP 机制可行性验证（RQ-A1）

机制可行性验证回答一个基础问题：CEBRA-WP 的代码实现是否能按照第 4 章的设计规范正确运行？

**四组策略切换验证**。四个 policy mode 的语义边界通过矩阵实验确认：（1）static_top1 仅使用静态评分选择单个最优候选，无运行时调整；（2）fixed_threshold_gate 在静态评分基础上增加固定门控，候选 metadata 中无 runtime_adjustment 字段；（3）dynamic_no_belief_state 启用动态观测和分层恢复链路，但 runtime_adjustment 恒为零；（4）lite_belief_state 启用完整的 belief-state 更新和运行时重排序。

**Lite belief-state 的持续可观测性**。在所有 21 个 lite_belief_state runs 中，runtime_state_observable_rate 为 1.0——即每个 run 的至少一个关键决策点产生了有效的 RuntimeState 记录，包含 p_success、p_structural_failure、recovery_margin、expected_remaining_cost、evidence_sufficiency 五个核心状态量。作为对照，其他三个策略组的 runtime_state_observable_rate 均为 0.0。runtime_state_summary 字段在其他组中为 `null`，在 lite 组中为完整的结构化 JSON。

**Budget pressure 的来源差异**。lite 组的 budget_pressure.source 为 `"observed"`（从运行时状态计算），其他三组为 `"default"`（fallback 到固定值 1.0）。这意味着 lite_belief_state 是唯一能根据实际预算消耗动态调整压力估计的策略组。

**Action utility 的计算完整性**。lite 组的 action_utility_source 为 `"computed"`，action_utilities 包含 continue、patch_local、suffix_replan、stop 四项动作的完整效用值。其他三组的 action_utility_source 为 `"missing"`，action_utilities 为空对象。这证明 CEBRA-WP 的动作效用计算链路在代码层面完整可执行。

上述结果直接支撑 RQ-A1 的肯定回答：**CEBRA-WP 的机制在 84-run 矩阵中持续、正确地执行，并产生了可追踪、可对比的运行时输出。**

---

## 7.5 四组策略消融主实验（RQ-A2、RQ-A3）

### 7.5.1 总体结果

表 7-2 汇总了四组策略的核心指标。

**表 7-2：四组消融主实验结果**

| 指标 | static_top1 | fixed_threshold_gate | dynamic_no_belief | lite_belief |
|---:|---:|---:|---:|---:|
| runs | 21 | 21 | 21 | 21 |
| DONE | **21** | 20 | 20 | 20 |
| FAILED | **0** | 1 | 1 | 1 |
| success_rate | **1.0000** | 0.9524 | 0.9524 | 0.9524 |
| first_pass_success_rate | **1.0000** | 0.9048 | 0.9524 | 0.9524 |
| schema_valid_rate | 1.0000 | 1.0000 | 0.9524 | 1.0000 |
| executable_plan_rate | 1.0000 | 0.9524 | 1.0000 | 1.0000 |
| high_cost_call_mean | 1.0000 | **1.3333** | **0.9524** | **0.9524** |
| high_cost_call_total | 21 | **28** | 20 | 20 |
| duration_ms_mean | 241,905 | 300,238 | **226,571** | 272,095 |
| patch_events_mean | 0.0000 | **0.2857** | 0.0000 | 0.0000 |
| replan_events_mean | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

三个关键观察：

**第一，static_top1 是唯一 100% 成功的组。** 这一结果不支持"CEBRA-WP 提升成功率"的简单叙事，但它本身不构成对 CEBRA-WP 的否定——static_top1 的无失败记录恰恰说明，在 12 个任务全部走"静态选择最优候选 + 线性执行"路径时，系统的基础规划能力已经足够稳健。这也意味着，如果论文仅追求成功率最大化，引入任何额外的运行时决策都是不必要的——但成功率不是唯一目标。

**第二，fixed_threshold_gate 产生了与其余三组不同的行为模式。** 它是唯一触发真实 patch 事件的组（patch_events_total=6，平均 0.286 次/run），同时也是高代价调用最高的组（28 次，比 static_top1 多 33%）。6 次 patch 中每一次都导致 openfold（结构预测）被额外调用一次，这些额外的调用直接推高了成本指标。

**第三，dynamic_no_belief 和 lite_belief 在核心指标上高度一致。** 两者的 success_rate、first_pass_success_rate、high_cost_call_mean 和 patch_events_mean 完全相同（均为 0.9524 / 0.9524 / 0.9524 / 0.0）。两者的差异主要体现在运行耗时（lite 比 dynamic 慢 20%，因 belief-state 计算开销）和信念状态指标上。

### 7.5.2 按难度和预算分层

按任务难度和预算类型的分层结果（表 7-3）揭示了失败分布的规律。

**表 7-3：按难度和预算分层的成功率**

| 分层 | runs | DONE | FAILED | success_rate |
|:---|---:|---:|---:|---:|
| easy | 32 | 32 | 0 | 1.0000 |
| medium | 40 | 37 | 3 | 0.9250 |
| hard | 12 | 12 | 0 | 1.0000 |
| low_cost_first | 32 | 32 | 0 | 1.0000 |
| standard | 40 | 37 | 3 | 0.9250 |
| high_cost_sensitive | 12 | 12 | 0 | 1.0000 |

3 个 FAILED run 全部集中在 medium/standard 层。easy 和 hard 任务全部通过——easy 任务因链路简单而稳定，hard 任务因样本量小（各 1 repeat × 4 组 = 4 runs/任务）而恰好未触发失败。t2_ubiquitin（76 aa 大蛋白，medium/standard）是最大的压力点，贡献了 2 个 FAILED；t3_gb1（56 aa，medium/standard）贡献了 1 个 FAILED。

### 7.5.3 机制增量配对对比

表 7-4 通过相邻策略组的配对增量（paired delta）量化了各机制的边际效应。

**表 7-4：机制增量配对对比**

| 对比 | 指标 | delta | 解读 |
|:---|---:|---:|:---|
| static→fixed | success_rate | −0.048 | fixed 因 patch 循环引入了 1 个失败 |
| static→fixed | first_pass | −0.095 | fixed 有更多首次未通过需要恢复 |
| static→fixed | patch_events | **+0.286** | fixed 是唯一触发真实 patch 的组 |
| static→fixed | high_cost | **+0.333** | patch 导致额外的高代价调用（openfold 重跑） |
| fixed→dynamic | high_cost | **−0.381** | dynamic 比 fixed 节省 38% 高代价调用 |
| fixed→dynamic | duration | −73,667ms | dynamic 比 fixed 快 24% |
| dynamic→lite | duration | +45,524ms | lite 因 belief-state 计算慢 20% |

这些 delta 提供了比绝对指标更丰富的解释：static→fixed 的负向 delta 说明固定门控的"拦截-修复"机制虽然可用，但在无运行时重排序的条件下，它的代价（额外的 patch 和高成本调用）超过了收益（成功拦截了部分潜在失败）；fixed→dynamic 的正向 delta 说明取消运行时拦截、依赖规划和候选验证的质量，在本次实验中表现为更低的成本；dynamic→lite 的 delta 说明 belief-state 的计算引入了一定的时间开销，但这种开销是否换来决策质量的提升，需要从机制层面而非指标均值层面来回答。

为进一步支撑成本控制分析，表 7-5 单独列出高代价调用与运行耗时。该表比总体结果表更适合承载“fixed 组恢复代价更高、dynamic/lite 具有较低高代价调用”的论证。

**表 7-5：高代价调用与运行时间对比**

| 组 | high_cost_total | high_cost_mean | 平均耗时 | 主要解释 |
|:---|---:|---:|---:|:---|
| static_top1 | 21 | 1.000 | 241,905 ms | 单候选线性执行，未触发 patch。 |
| fixed_threshold_gate | **28** | **1.333** | 300,238 ms | 6 次 patch 导致 openfold 重跑，另有 1 次结构精修调用。 |
| dynamic_no_belief_state | 20 | 0.952 | **226,571 ms** | 无 patch 开销，1 个失败在高代价执行前被候选验证拦截。 |
| lite_belief_state | 20 | 0.952 | 272,095 ms | 高代价调用数低于 fixed，但 belief-state 与 action utility 计算带来额外时间。 |

表 7-5 支持的结论应表述为：在本实验设置下，dynamic 和 lite 两组的高代价调用比 fixed_threshold_gate 低 28.6%，但 lite 未在运行时间上优于 dynamic。因此，lite 的优势主要是机制可观测性和运行时决策解释，而不是绝对耗时最短。

---

## 7.6 静态规划的必要性分析（RQ-A2 深化）

RQ-A2 问的是"相比静态规划，引入运行时自适应是否有存在必要"。这个问题的答案不能仅看 success_rate 的数值高低，而应考察**静态规划在缺少运行时调整时暴露了哪些局限**。

**fixed_threshold_gate 的拦截成本。** fixed 组是唯一触发真实运行时恢复的组——6 次 tool-level patch 证明了"拦截-修复"机制的可用性。但这 6 次 patch 每次都需要重新调用 openfold 进行结构预测，导致该组的高代价调用均值从 static 的 1.0 跃升至 1.33，总调用次数从 21 升至 28。更关键的是，其中 1 次 patch 循环在 t2_ubiquitin 上耗尽后进入 FAILED（详见 7.8 节案例分析），暴露了固定门控的关键局限：当 patch 后的 plan 仍触发相同的门控条件时，系统缺乏运行时重排序来打破循环。

**static_top1 的"不可见浪费"。** static_top1 的 100% 成功率容易给人"已经足够"的印象。但这个结果建立在任务集中无强制失败条件的前提下——所有 12 个 task 的初始 plan 恰好都是可执行的。在真实科研场景中，如果初始 plan 的某个候选因工具不可用、预算超限或安全冲突而不可执行，static_top1 的单候选策略将直接失效。这一局限在当前实验中被任务集设计掩盖了，但不能作为"静态单链始终足够"的证据。

**dynamic 和 lite 的预防性差异。** dynamic_no_belief 和 lite_belief 在核心指标上高度一致，但两者的"零 patch"有不同的成因。dynamic 无 patch 是因为它的运行时观测链路（无 belief-state）没有产生需要拦截的信号；lite 无 patch 是因为它的运行时重排序在 plan 阶段就已降低高风险候选的优先级——lite 评估了所有 action 的 utility，但始终选择 continue，因为在 rerank 之后，top candidate 已经不再是需要被拦截的那个。这揭示了从 fixed 到 lite 的范式转变：fixed 是"运行时发现问题 → 拦截 → 修复"，lite 是"运行时评估风险 → 重排序 → 预防"。前者的代价是额外的 patch 调用，后者的代价是 belief-state 的计算时间。

---

## 7.7 信念状态的增量价值分析（RQ-A3）

RQ-A3 聚焦 dynamic_no_belief_state 与 lite_belief_state 的定向对比。两个策略组的核心指标均值相同，但机制层面存在本质差异。

**信念状态的可观测性。** 这是两组之间最清晰的差异：lite 的 runtime_state_observable_rate=1.0，dynamic 为 0.0。这意味着在所有 21 个 lite runs 中，系统持续产生了 p_success、p_structural_failure、recovery_margin、expected_remaining_cost 和 evidence_sufficiency 五个核心状态量的有效估计——即使这些估计在本次实验中未转化为不同的动作选择（两组都选择了 continue），它们为决策提供了在 dynamic 组中完全缺失的信息维度。

**Budget pressure 的感知差异。** lite 组从运行时状态中计算 budget_pressure（source="observed"），dynamic 组使用静态默认值（source="default"，固定为 1.0）。这意味着 lite 能够感知到实际预算消耗的动态变化，而 dynamic 始终假定预算压力不变。这种感知差异在 t2_ubiquitin 上表现得最为明显：lite 的 r01（FAILED）在 36 次 patch 循环中，budget_pressure 从 0.0 逐步升高到 1.5，runtime_adjustment 对候选评分产生了 −0.096 的负向调整——系统"意识"到了预算正在消耗。尽管最终 r01 仍未打破循环，但 r02（相同任务、相同策略）成功完成，说明在某些初始条件下 lite 的 rerank 足够打破循环。

**增量价值的当前证据边界。** 在本次实验中，lite 相比 dynamic 的增量价值主要体现在：（1）产生了全面且持续的信念状态观测，为决策审计提供了 dynamic 组完全缺失的信息维度；（2）通过预防性重排序避免了类似 fixed 组的 patch 触发；（3）在 t2_ubiquitin 压力点上展现了预算感知能力。但 lite 未能将这种机制优势转化为 success_rate、high_cost_call_mean 或 duration 的显著改善——两组在这些指标上的均值完全相同。RQ-A3 的当前回答是：**lite belief-state 的机制优势已得到验证，但其在本次任务集上尚未转化为超越 dynamic 的统计显著性能增益。** 这为未来的定向实验（扩大压力任务样本、引入更强的失败诱导条件）留下了明确的研究空间。

表 7-6 将上述机制差异集中呈现。它是本节最重要的证据表，因为它解释了为什么即使 lite 与 dynamic 在成功率上相同，lite 仍然不是“无差异实现”。

**表 7-6：Lite belief-state 机制可观测性对比**

| 特征 | static_top1 / fixed_threshold_gate / dynamic_no_belief_state | lite_belief_state | 论文解释 |
|:---|:---|:---|:---|
| runtime_state_summary | 其他组为 `null` 或无有效观测 | 21/21 runs 产生有效 RuntimeState | 证明 Lite belief-state 链路持续执行。 |
| budget_pressure source | `"default"` fallback | `"observed"` | 证明 lite 能从运行时状态中估计预算压力。 |
| action_utility_source | `"missing"` | `"computed"` | 证明 continue、patch_local、suffix_replan、stop 的动作效用被实际计算。 |
| action_utilities | 空对象或不可用 | 四类动作均有 utility | 支撑恢复动作选择的可解释性。 |
| runtime_state_observable_rate | 0.0 | 1.0 | 这是 lite 与 dynamic 的核心机制差异。 |

表 7-6 不用于声称 lite 在成功率上优于 dynamic，而用于证明 CEBRA-WP 的信念状态、预算感知和动作效用计算在工程上可执行、可追踪。

---

## 7.8 典型案例分析（RQ-A4）

典型案例分析主要借助恢复路径对比图展开，如图 7-2 所示。该图对比 fixed_threshold_gate 和 lite_belief_state 在恢复控制上的差异：fixed 侧展示“运行时发现问题 → WAITING_PATCH → patch_local → 高代价结构预测重跑 → 可能再次触发门控”的后置拦截路径；lite 侧展示“生成候选 → 运行时状态估计 → runtime rerank → action utility → continue/边界失败”的前置调节路径。图 7-2 的作用不是证明 lite 在本次实验中提升了成功率，而是帮助解释二者机制差异：fixed 的证据是 6 次真实 patch 和更高高代价调用，lite 的证据是 21/21 runs 持续产生 RuntimeState 和 action utility。

> **图 7-2**：恢复路径对比时间线，展示 fixed_threshold_gate 的后置 patch 拦截与 lite_belief_state 的运行时状态驱动重排序。来源：`paper/figures/recovery-path-comparison-timeline.drawio.svg` / `paper/figures/recovery-path-comparison-timeline.drawio.png`。

### 7.8.1 案例一：static_top1 的线性成功（t1_trpcage_denovo_short_peptide）

表 7-7 先汇总三个 FAILED run 的归因，再展开典型案例。这样可以避免案例分析只依靠叙述，读者可以先看到失败分布、失败类型和证据意义。

**表 7-7：FAILED run 归因表**

| 策略组 | 任务 | repeat | 错误类型 | 根因 | 论文解释 |
|:---|:---|:---:|:---|:---|:---|
| fixed_threshold_gate | `t2_ubiquitin_sequence_eval` | r02 | auto decision loop exhausted | 固定门控触发 WAITING_PATCH 循环，patch 后仍触发相同门控条件 | 证明无 runtime rerank 的“拦截-修复”可能引入循环和额外高代价调用。 |
| lite_belief_state | `t2_ubiquitin_sequence_eval` | r01 | auto decision loop exhausted | 36 次 WAITING_PATCH 循环；budget_pressure 从 0.0 升至 1.5，但 rerank 未打破循环 | 展示 belief-state 可观测和预算感知，但也说明其性能增益存在边界。 |
| dynamic_no_belief_state | `t3_gb1_stability_optimization` | r01 | `CANDIDATE_IO_CLOSURE_BROKEN` | 候选 step 输出字段无法被下游引用，规划阶段校验失败 | 证明候选验证机制正常工作，宁可拒绝不可执行候选也不静默执行。 |

static_top1 在 t1 任务上的典型执行路径为：Planner 生成单个候选 → FeasibilityFilter 通过 → 静态评分最优 → 自动选择 → Executor 单步执行 → Summarizer 汇总 → DONE。全流程无等待、无重试、无 patch、无 replan。2 个 repeats 均以约 180 秒完成，high_cost_call_count=1（openfold 在 S2 被调用 1 次）。

这个案例说明的是：当任务简单、约束宽松、候选可行时，CEBRA-WP 的运行时机制不产生额外开销——它不会为了"显得在做自适应"而主动引入延迟或人工确认。系统的工程基础（规划、执行、汇总）已经足够稳定。

### 7.8.2 案例二：fixed_threshold_gate 在 t2_ubiquitin 上的 patch 循环（FAILED）

fixed_threshold_gate / t2_ubiquitin_sequence_eval / r02 是三个失败案例中最能说明机制局限的一个。

事件链如下：Planner 生成候选 → FeasibilityFilter 通过 → 固定门控检测到"高代价低收益"（76 aa 大蛋白 + 标准预算）→ 生成 patch 候选 → 进入 WAITING_PATCH_CONFIRM → 自动决策接受 → 应用 tool-level patch → 恢复执行 → 再次触发相同门控条件 → 再次生成 patch → ...循环耗尽 → FAILED。

这个案例的核心启示是：**固定门控在没有运行时重排序的情况下，对某些边界任务可能引发"拦截-修复-再拦截"的循环，且单靠 patch 无法打破。** 静态门控知道"这里有问题"，但不知道"哪个替代方案更好"——它缺少 CEBRA-WP 的候选重排序能力。这为 RQ-A2（必要性）提供了最直接的案例证据。

### 7.8.3 案例三：lite_belief_state 在 t2_ubiquitin 上的预算感知（r01 FAILED, r02 DONE）

lite_belief_state 在 t2_ubiquitin 上有两个 repeats，结果不同，构成天然的对照。

r01（FAILED）：触发了 36 次 WAITING_PATCH 循环。与 fixed 案例的关键差异在于——lite 的事件日志显示了 runtime_state 的动态演变：budget_pressure 从 0.0 逐步升至 1.5，patch candidate 的 static_score 为 0.789，但 runtime_adjustment 为 −0.096，最终 score 被压低。系统"意识"到预算在消耗、候选在变差，但 rerank 后的候选仍触发了循环。这一过程被完整记录在 event log 和 snapshot 中，可作为展示 CEBRA-WP 决策链的优质案例。

r02（DONE）：相同任务、相同策略，成功完成。两个 repeats 之间的差异说明了初始条件的敏感性——belief-state 的效用依赖于初始候选质量和初始状态估计，而这种依赖在 n=2 的条件下表现为 run-to-run 的变异性。论文将此作为"机制可解释但确定性不足"的诚实展示，而非贬低 belief-state 的价值。

### 7.8.4 案例四：dynamic_no_belief 的候选验证失败（t3_gb1 / r01 FAILED）

dynamic_no_belief_state / t3_gb1_stability_optimization / r01 的失败原因是 `CANDIDATE_IO_CLOSURE_BROKEN`——候选的 step 输出字段无法被下游 step 引用。这不是运行时错误，而是候选验证机制在规划阶段就发现了不可执行的候选并拒绝执行。

该案例说明：dynamic_no_belief_state（无 belief-state）的候选验证不如 lite_belief_state 稳健——lite 的 schema_valid_rate=1.0，dynamic 为 0.9524，差值恰好对应这个 FAILED run。它在论文中的价值是作为"候选验证机制正常工作的证据"——系统宁愿在规划阶段拒绝不可执行候选并进入 FAILED，也不静默执行一个必然出错的 plan。

---

## 7.9 结论边界与限制说明

为保证实验结论可追溯，表 7-8 汇总本章使用的主要证据产物。终稿中可以把该表放在 7.3 实验环境与执行配置之后，或放在 7.9 作为结论边界的支撑。

**表 7-8：实验结果证据产物索引**

| 证据产物 | 路径/来源 | 支撑内容 | 使用位置 |
|:---|:---|:---|:---|
| 实验结果报告 | `../thesis-project.dev/docs/experiment/thesis-final-v1-results.md` | 84-run 概况、主结果、分层结果、失败案例和结论边界 | 全章主依据 |
| 实验设计文档 | `../thesis-project.dev/docs/experiment/final-thesis-experiment-design.md` | 双主线实验定位、研究问题、任务类和指标体系 | 7.1、7.2、7.3 |
| 分组映射文档 | `../thesis-project.dev/docs/experiment/algorithm-group-paper-mapping.md` | 代码 policy mode 与论文组名的一一对应 | 7.1、7.5 |
| 矩阵聚合产物 | `output/experiment/thesis-final-matrix/thesis-final-v1-001/` | matrix summary、action distribution、high cost breakdown、run level results | 7.5 至 7.8 |
| EventLog / Snapshot | `data/logs/thesis-final-v1-001_*.jsonl`、`data/snapshots/thesis-final-v1-001_*.jsonl` | 失败案例、恢复循环、runtime_state 和 decision trace | 7.7、7.8 |
| 系统验证证据 | `../thesis-project.dev/docs/system-validation/evidence-index.md` | 说明实验基础设施已通过工程验证 | 7.1 前置说明 |

基于上述分析，本章的结论在以下边界内成立：

**不做成功率优势声称。** static_top1 的 100% 成功率高于其余三组的 95.2%。论文不将"提升成功率"作为 CEBRA-WP 的主结论。

**成本控制优势有数据支撑，但统计效力受限。** lite 和 dynamic 比 fixed 节省 28.6% 高代价调用（20 vs 28）、比 static 节省 5%（20 vs 21）。但 n=21/组（含 3 个 budget tier 不同 repeat 数的混合设计）限制了统计检验的效力。论文用"趋势"和"方向"表述，不做显著性检验结论。

**信念状态的机制优势已证明，性能增益待验证。** lite 在所有 21 runs 中产生了完整的信念状态输出，这是 RQ-A1 和 RQ-A3 的最强证据。但 lite 未能在核心性能指标上超越 dynamic——两组完全相同。论文将这表述为"机制正确性已建立，性能增量价值需要更大规模和更强压力条件的实验来验证"。

**恢复机制的覆盖不完整。** 四组均无 replan 事件，patch 事件仅出现在 fixed 组。t5（设计用于触发 patch 的任务）和 t8（设计用于触发安全阻断的任务）未产生预期行为。这意味着恢复机制的"全覆盖验证"尚未完成，但已有的 focused tests（TC-S12）和 fixed 组的 6 次真实 patch 提供了恢复路径可达的确定性证据。

**三个 FAILED run 不是失败的实验。** 它们是提供机制洞察的边界案例：（1）fixed 的 patch 循环证明无 rerank 的局限；（2）lite 的 36 次循环展示了信念状态的动态演变和"意识到但无法打破"的诚实行为；（3）dynamic 的候选验证失败证明了候选校验机制的必要性和正常工作。这些案例比 81 个 DONE run 更有分析价值。

---

## 7.10 本章小结

本章在 84-run 四组消融实验中验证了 CEBRA-WP 的可行性、必要性和增量价值。

（1）**可行性已确认**：lite_belief_state 在所有 21 runs 中持续产生了有效的 RuntimeState、action_utility 和 runtime_adjustment，budget_pressure source 为 "observed"（其他组为 "default" fallback）。CEBRA-WP 的完整机制链路在代码层面正确执行。

（2）**必要性有初步证据**：fixed_threshold_gate 在缺少 runtime rerank 的条件下触发了 6 次 patch 和额外 7 次高代价调用，其中 1 次演化为 patch 循环耗尽导致 FAILED。这证明了固定门控"拦截-修复"模式的代价，也暗示了运行时重排序的必要性。

（3）**信念状态的增量价值体现为"预防优于修复"的范式差异**：lite_belief_state 通过运行时重排序在规划阶段降低风险，避免了运行时拦截，与 fixed_threshold_gate 形成对比。但这一优势未转化为 success_rate 或 high_cost_call_mean 的统计显著改善。

（4）**成本控制有数据支撑**：lite 和 dynamic 的高代价调用比 fixed 低 28.6%，比 static 低 5%。

（5）**三个 FAILED run 是机制洞察的来源**：fixed 的循环耗尽证明了 rerank 的必要性，lite 的预算感知展示了信念状态的动态行为，dynamic 的候选验证失败证明了校验机制的价值。

（6）**统计效力和恢复覆盖仍有限制**：n=2 限制了统计推断的强度，无 replan 事件说明压力条件未充分覆盖恢复路径的全谱。这些限制为后续实验（扩大样本、强化压力任务、定向对照 dynamic vs lite）提供了明确的方向。

---

## 图表清单

| 图号 | 标题 | 源文件 |
|------|------|--------|
| 图 7-1 | 实验设计框架：任务集、策略组、指标与证据产物 | `paper/figures/experiment-design-framework.drawio.svg` |
| 图 7-2 | 恢复路径对比：fixed gate 后置 patch 与 lite belief-state 前置重排序 | `paper/figures/recovery-path-comparison-timeline.drawio.svg` |

| 表号 | 标题 | 来源 |
|------|------|------|
| 表 7-1 | 实验矩阵配置表 | `../thesis-project.dev/docs/experiment/thesis-final-v1-results.md` |
| 表 7-2 | 四组消融主实验结果 | `../thesis-project.dev/docs/experiment/thesis-final-v1-results.md` |
| 表 7-3 | 按难度和预算分层的成功率 | `../thesis-project.dev/docs/experiment/thesis-final-v1-results.md` |
| 表 7-4 | 机制增量配对对比 | `../thesis-project.dev/docs/experiment/thesis-final-v1-results.md` |
| 表 7-5 | 高代价调用与运行时间对比 | `../thesis-project.dev/docs/experiment/thesis-final-v1-results.md` |
| 表 7-6 | Lite belief-state 机制可观测性对比 | `../thesis-project.dev/docs/experiment/thesis-final-v1-results.md` |
| 表 7-7 | FAILED run 归因表 | `../thesis-project.dev/docs/experiment/thesis-final-v1-results.md` |
| 表 7-8 | 实验结果证据产物索引 | 实验设计、结果报告、矩阵聚合产物、EventLog/Snapshot |
