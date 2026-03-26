# 未来一个月(3.24-4.24)规划

> Date Range:
>
> - 开始：2026-03-24
> - 结束：2026-04-24
>
> 当前基础（截至 2026-03-24）：
>
> - 代码侧已经具备 `PlannerAgent.plan_top_k / patch_top_k / replan_top_k`、`score_breakdown / risk_level / cost_estimate`、`evaluate_top_k_gate`、`retry -> patch -> replan` 恢复闭环，以及 `src/infra/w12_vertical_experiment.py` 的实验统计框架。
> - 运行时上下文与持久化侧已经具备 `WorkflowContext`、`TaskSnapshot.artifacts`、`PendingAction`、`EventLog`，但尚未形成专门的 `belief-state / runtime_state` 契约与更新逻辑。
> - 设计文档侧已经具备 SSOT、SID、`index.json`、`topic_views.json` 与 `docslice --lint` 基础；但新算法尚未纳入稳定检索入口，且当前 `docslice --lint` 仍存在 marker fallback warning，说明索引与文档边界还需要收敛。

## 未来一个月总目标（Result-Oriented）

在 2026-04-24 前，形成三个可验收成果：

- R1：新算法被完整纳入 `../thesis-project.design/docs/design/` 的 SSOT 文档、索引和 topic view，且可被 `docslice` 稳定检索。
- R2：在不改变 FSM、Agent 边界和 `retry -> patch -> replan` 契约的前提下，实现 Lite 版自适应工具链规划算法主干：运行时状态估计、动作选择、静态评分结合运行时修正。
- R3：形成可用于论文与 issue 的实验和证据包，至少完成 `静态 Top-1`、`固定阈值 gate`、`动态无 belief-state`、`Lite belief-state` 四组可比较基线。

## 全局边界与验收口径

- 不新增 FSM 状态，不重写 Workflow 引擎，不改变 Planner/Executor/Safety/Summarizer 职责边界。
- 新算法定位为现有 Planner/Recovery 架构之上的轻量决策层，而不是新的 controller 架构。
- 文档纳入必须同步更新：
  - `docs/design/` 对应 SSOT 文档
  - `docs/index/index.json`
  - `docs/index/index.md`
  - `docs/index/topic_views.json`
  - `docs/index/SSOT_MAP.md`
- `docslice --lint` 必须通过，且本月目标是消除当前 marker fallback warning。
- 实验结论必须能追溯到：任务集版本、配置、事件日志、快照、指标汇总、案例证据。

______________________________________________________________________

## Week 13(03.24-03.30)

### 主题：文档 SSOT 收敛 + 基线冻结

### 核心目标

- 把“自适应工具链规划算法”从研究笔记提升为正式设计规范。
- 明确文档纳入路径、SID 方案、索引更新流程和第一版实验对照组。
- 固定当前代码基线与实验资产，避免后续边实现边改口径。

### 本周 Issue 列表

- W13-01 新算法 SSOT 文档纳入设计
- W13-02 docslice 可检索性与索引修复
- W13-03 代码基线审计与接口缺口清单
- W13-04 高代价步骤、任务集与比较基线冻结
- W13-05 证据资产目录与命名约定冻结

### 关键 Issue 设计

| 模块 | Issue | 具体工作内容 | 验收标准 | 追溯点 |
| :--- | :---- | :----------- | :------- | :----- |
| Docs/Design | W13-01 新算法 SSOT 文档纳入设计 | 重写并扩展 `core-algorithm-spec.md`，将“高代价工作流中的自适应工具链规划”定义为主算法；在 `de-novo-workflow.md` 补入高代价步骤、运行时观测、恢复感知控制；在 `system-implementation-design.md` 补入 runtime state/belief-state、动作选择和审计字段；必要时在 `architecture.md` 仅补充不改语义的架构说明 | 新算法从研究笔记迁移为设计文档 SSOT，且不引入新的 FSM/角色语义 | `../thesis-project.design/docs/design/core-algorithm-spec.md`，`../thesis-project.design/docs/design/de-novo-workflow.md`，`../thesis-project.design/docs/design/system-implementation-design.md`，`../thesis-project.design/docs/design/architecture.md` |
| Docs/Index | W13-02 docslice 可检索性与索引修复 | 为新算法分配稳定 SID；同步更新 `index.json/index.md/topic_views.json/SSOT_MAP.md`；修复当前 marker fallback warning 所指向的边界/索引偏差；优先把新算法纳入现有 `planning` / `execution` / `observability` topic view，避免先引入新的 topic 造成额外维护负担 | `docslice --lint` 通过且 warning 清零；新算法关键段可通过 `--sid` 和 `--topic planning` 稳定提取 | `../thesis-project.design/docs/index/SECTION_CONTRACT.md`，`../thesis-project.design/docs/index/SSOT_MAP.md`，`../thesis-project.design/docs/index/index.json`，`../thesis-project.design/docs/index/index.md`，`../thesis-project.design/docs/index/topic_views.json` |
| Code/Docs | W13-03 代码基线审计与接口缺口清单 | 以当前代码为准，审计 `planner.py`、`plan_runner.py`、`patch_runner.py`、`context.py`、`contracts.py`、`w12_vertical_experiment.py`，明确哪些能力已存在、哪些是新算法真正缺口，输出后续 issue 的最小变更接口清单 | 形成一份“现有能力 / 缺口 / 后续改动落点”清单，避免后续 issue 偏离现状 | `src/agents/planner.py`，`src/workflow/context.py`，`src/workflow/plan_runner.py`，`src/workflow/patch_runner.py`，`src/models/contracts.py`，`src/infra/w12_vertical_experiment.py` |
| Experiment | W13-04 高代价步骤、任务集与比较基线冻结 | 定义哪些步骤算高代价；冻结一版任务集及难度分层；明确四个基线：`静态 Top-1`、`固定阈值 gate`、`动态无 belief-state`、`Lite belief-state`；明确 success/cost/recovery 三类指标口径 | 后续所有实验使用同一任务集、同一高代价定义、同一指标口径 | `../thesis-project.design/docs/experiment/`，`src/infra/w12_vertical_experiment.py`，`reports/`，`output/` |
| Experiment/Report | W13-05 证据资产目录与命名约定冻结 | 约定实验输出目录、配置快照、日志、快照、表格、案例证据和图表命名；建立 `evidence-index.json` 的字段基线，确保后续可以直接服务论文和 issue | 任意一项结论都能回链到 run config、event log、snapshot、summary row 和图表产物 | `output/`，`reports/`，`../thesis-project.design/plan/` |

### 建议新增 SID（供 W13-01/W13-02 使用）

- `SID:algo.adaptive.problem_formulation`
- `SID:algo.adaptive.optimization_objective`
- `SID:planner.algorithm.runtime_state_estimation`
- `SID:planner.algorithm.runtime_action_selection`
- `SID:planner.algorithm.runtime_reranking`
- `SID:workflow.stage.high_cost_control`
- `SID:impl.runtime_state.persistence`
- `SID:obs.runtime_adaptation.audit_fields`

### Week 13 可交付物

- 新算法纳入 SSOT 的首版设计文档。
- 新算法 SID 和索引更新方案。
- 一份基于当前代码的接口缺口清单。
- 一份冻结后的任务集/基线/指标说明。

### 基于 Issue #208 的增补拆分（2026-03-25）

`W13-03` 的代码基线审计已经确认：当前系统不缺 Top-K、gate、patch/replan、snapshot、event log 主骨架；真正需要继续拆分的是 `runtime_state` 契约、动作选择接缝、等待态/快照恢复摘要，以及实验端对 action-level / belief-state-level 证据的聚合能力。

因此，Week 14 到 Week 16 在原有 15 个 issue 之外，建议增补以下 8 个细化 issue，作为既有 issue 的前置落点或中间插入位：

| 周次 | 建议插入位置 | 新增 issue | 对应缺口 | 主要目的 |
| :--- | :----------- | :--------- | :------- | :------- |
| Week 14 | `#211` 之前 | W14-Contracts-1a RuntimeState schema、snapshot 键与版本字段冻结 | D1 | 先把运行时状态模型与持久化键固定下来，避免后续字段漂移 |
| Week 14 | `#211` 与 `#212` 之间 | W14-Contracts-1b PendingActionCandidate / WAITING 运行时摘要契约 | D2 | 固定候选与等待态中的状态摘要、默认建议原因和最小 HITL 回放字段 |
| Week 14 | `#212` 之后 | W14-Workflow-2a belief-state 更新纯函数与字段语义标定 | F1 | 把状态更新逻辑独立出来，先做可重放、可测试的更新器核心 |
| Week 14 | `#213` 之前 | W14-Observability-3a WAITING 前 runtime_state snapshot 持久化 | E2 | 确保运行时状态能跨 `WAITING_*` 和恢复路径保留 |
| Week 14 | `#213` 与 `#214` 之间 | W14-Observability-3b action/runtime 审计事件字段补齐 | E1 | 为动作选择、升级原因、shadow score 等补齐事件证据 |
| Week 15 | `#216` 与 `#217` 之间 | W15-Workflow-1a 统一动作选择器接口与 recovery 映射 | F2 | 在不改变 FSM 的前提下，把四种动作映射回既有恢复闭环 |
| Week 15 | `#217` 之前 | W15-Planner-2a shadow rerank 与 adjusted score 接口 | F3 | 先补静态评分与运行时修正的接口层，再谈默认建议接管 |
| Week 16 | `#221` 与 `#222` 之间 | W16-Evaluation-2a action-level / belief-state 聚合指标扩展 | E3 | 让四组方法在同一聚合脚本下可比较动作与状态证据 |

补充说明：

- 原有 `#211` 到 `#225` 保持为月度主 issue，不删除、不改语义。
- 新增 issue 的定位是“把 `#208` 识别出的真正缺口拆成可执行前置项”，用于避免后续实现继续在大 issue 内混写契约、控制流和证据字段。
- project 排序应按上表插入，使实现顺序与缺口依赖顺序一致。

______________________________________________________________________

## Week 14(03.31-04.06)

### 主题：Lite 版运行时状态契约与观测更新

### 核心目标

- 先把 `belief-state` 做成 Lite 版数据契约和更新逻辑，而不是一开始就做复杂控制器。
- 保证运行时状态既能留在内存上下文，也能跨等待/恢复保存在快照中。
- 为后续动作选择和实验回放准备最小可观测字段。

### 本周 Issue 列表

- W14-01 RuntimeState / BeliefState 契约落地
- W14-02 运行时状态更新器实现
- W14-03 观测与审计字段补齐
- W14-04 候选静态评分与运行时状态的接缝设计
- W14-05 契约级测试与回放样本准备

### 关键 Issue 设计

| 模块 | Issue | 具体工作内容 | 验收标准 | 追溯点 |
| :--- | :---- | :----------- | :------- | :----- |
| Models/Workflow | W14-01 RuntimeState / BeliefState 契约落地 | 在 `WorkflowContext` 增加可选 `belief_state` 或 `runtime_state`；在 `TaskSnapshot.artifacts` 中定义稳定存储格式；为 `PendingActionCandidate.metadata` 保留状态摘要挂点；保持向后兼容 | 状态能在运行中读写，也能跨 `WAITING_*` / snapshot 恢复，不破坏既有契约 | `src/workflow/context.py`，`src/models/contracts.py`，`src/workflow/snapshots.py`，`tests/unit/` |
| Workflow | W14-02 运行时状态更新器实现 | 新增 `src/workflow/belief_state.py` 或 `src/workflow/adaptive_planning.py`，根据 `StepResult`、`SafetyResult`、失败上下文更新最小状态集：`p_success`、`p_structural_failure`、`recovery_margin`、`expected_remaining_cost` | 可从已有运行时观测确定性地产生状态更新；状态字段含义明确、可回放 | `src/workflow/`，`src/models/contracts.py`，`tests/unit/` |
| Observability | W14-03 观测与审计字段补齐 | 在事件与快照中增加运行时状态、动作分数、升级原因、成本/风险来源等审计字段；保证实验端能直接消费，不需要二次人工拼接 | 单次 patch/replan/stop 的原因、候选排序和状态变化可被日志与快照还原 | `src/storage/`，`src/workflow/pending_action.py`，`src/workflow/plan_runner.py`，`src/workflow/patch_runner.py`，`tests/integration/` |
| Planner/Workflow | W14-04 候选静态评分与运行时状态的接缝设计 | 设计“静态先验分 + 运行时状态修正”的组合方式，但先只做接口和 shadow score，不急于直接驱动控制流 | 能在不改变默认执行语义的情况下输出 shadow score / shadow action，供后续对照 | `src/agents/planner.py`，`src/workflow/`，`tests/unit/test_planner_agent.py` |
| Experiment | W14-05 契约级测试与回放样本准备 | 基于冻结任务集准备可离线 replay 的最小样本，验证运行时状态更新和快照恢复；补齐状态/审计相关测试 | 可离线重放至少一批样本并稳定得到相同状态更新结果 | `tests/unit/`，`tests/integration/`，`reports/`，`output/` |

### Week 14 可交付物

- Lite `belief-state` 契约与最小状态集。
- 运行时状态更新器。
- 面向实验和审计的状态字段与回放样本。
- 第一版 shadow score / shadow action 输出。

______________________________________________________________________

## Week 15(04.07-04.13)

### 主题：动作选择接入与动态基线形成

### 核心目标

- 把 Lite 版运行时状态真正接入现有恢复闭环。
- 保持现有 FSM、HITL 和恢复顺序不变，只在现有接口上改进动作选择。
- 先完成“动态无 belief-state”和“Lite belief-state”两条动态路线的可比较实现。

### 本周 Issue 列表

- W15-01 自适应动作选择器接入 Workflow
- W15-02 候选重排序与默认建议修正
- W15-03 动态无 belief-state 基线实现
- W15-04 Lite belief-state 主路径实现
- W15-05 恢复/FSM/边界回归测试

### 关键 Issue 设计

| 模块 | Issue | 具体工作内容 | 验收标准 | 追溯点 |
| :--- | :---- | :----------- | :------- | :----- |
| Workflow | W15-01 自适应动作选择器接入 Workflow | 在 `plan_runner.py`、`patch_runner.py`、`recovery.py` 接入动作选择器，只支持 `continue`、`patch_local`、`suffix_replan`、`stop` 四种动作；映射到现有状态和恢复路径，不新增 FSM 语义 | 动作选择可以驱动既有执行流，且 `retry -> patch -> replan` 顺序仍然有效 | `src/workflow/plan_runner.py`，`src/workflow/patch_runner.py`，`src/workflow/recovery.py`，`tests/integration/` |
| Planner | W15-02 候选重排序与默认建议修正 | 让 `PlannerAgent` 在保留原静态评分的基础上接受运行时修正分；输出新的默认建议和 explanation，但候选契约保持不变 | Top-K 输出结构不变，默认建议可因运行时状态而调整，解释能说明修正原因 | `src/agents/planner.py`，`src/models/validation.py`，`tests/unit/test_planner_agent.py` |
| Workflow/Baseline | W15-03 动态无 belief-state 基线实现 | 实现不带显式状态估计的动态版本，以规则/直接观测驱动动作选择，作为 belief-state 的核心对照组 | 动态无 belief-state 与 Lite belief-state 共享大部分执行框架，仅差状态估计层 | `src/workflow/`，`tests/unit/`，`tests/integration/` |
| Workflow/Baseline | W15-04 Lite belief-state 主路径实现 | 将 Week14 的状态估计结果正式接入动作选择和候选修正，形成 Lite belief-state 可运行版本 | Lite belief-state 能稳定输出动作选择，并与动态无 belief-state 形成明确实现差异 | `src/workflow/`，`src/agents/planner.py`，`tests/integration/` |
| Tests | W15-05 恢复/FSM/边界回归测试 | 回归测试重点覆盖：WAITING 快照、决策回流、patch/replan 升级、suffix replan 前缀保持、终态不被非法改写 | 所有关键行为都有 focused tests；不出现角色越界或非法状态跳转 | `tests/unit/`，`tests/integration/` |

### Week 15 可交付物

- 动态无 belief-state 基线。
- Lite belief-state 可运行主路径。
- 与现有恢复闭环兼容的动作选择接入。
- 一组覆盖 FSM/恢复/快照的回归测试。

______________________________________________________________________

## Week 16(04.14-04.20)

### 主题：实验矩阵、证据包与论文可用结果

### 核心目标

- 用统一任务集和口径完成四组方法的系统对比。
- 把实验结果整理成论文可直接引用的图表、案例和证据索引。
- 产出下一轮 issue 可以直接继承的结果包。

### 本周 Issue 列表

- W16-01 四组方法统一实验矩阵执行
- W16-02 指标聚合与分层分析
- W16-03 案例研究与失败分析
- W16-04 证据索引、图表和报告模板
- W16-05 设计/实验文档回填与 issue 化准备

### 关键 Issue 设计

| 模块 | Issue | 具体工作内容 | 验收标准 | 追溯点 |
| :--- | :---- | :----------- | :------- | :----- |
| Experiment | W16-01 四组方法统一实验矩阵执行 | 基于冻结任务集执行 `静态 Top-1`、`固定阈值 gate`、`动态无 belief-state`、`Lite belief-state`；必要时加入重复实验和时间预算控制 | 四组方法都产出可复算的 run-level 结果，输入和预算口径一致 | `src/infra/w12_vertical_experiment.py`，`scripts/`，`output/`，`reports/` |
| Experiment | W16-02 指标聚合与分层分析 | 形成总体指标、按难度分层指标、恢复链长度、高代价调用次数、patch/replan 次数、prefix preservation 等分析表 | 至少能支持“动态优于静态”和“belief-state 优于简单规则”两类核心命题判定 | `reports/`，`output/`，`src/infra/` |
| Experiment/Case | W16-03 案例研究与失败分析 | 沉淀一个止损成功案例、一个对照案例、一个失败案例；每个案例必须带日志/快照/候选/动作理由/结果对照 | 案例不是口头描述，而是带证据链的可追溯样例 | `output/`，`reports/`，`data/logs/`，`data/snapshots/` |
| Report | W16-04 证据索引、图表和报告模板 | 生成 `evidence-index.json`、图表清单、表格模板、论文结果段落需要的字段映射；把实验输出变成可以直接消费的成果包 | 每个图表和表格都有输入来源、生成脚本/路径、结论摘要 | `reports/`，`output/`，`../thesis-project.design/docs/experiment/` |
| Docs/Plan | W16-05 设计/实验文档回填与 issue 化准备 | 回填设计文档中已实现部分、实验计划文档和下一阶段的 issue 拆分依据；明确哪些问题已回答，哪些仍属 open question | 后续 issue 可以直接从本月结果包拆分，不需要重新做一次规划 | `../thesis-project.design/docs/experiment/`，`../thesis-project.design/plan/` |

### Week 16 可交付物

- 四组方法的统一比较结果。
- 总体、分层、案例三类证据。
- `evidence-index.json` 与图表/表格模板。
- 一份可直接服务 issue 撰写和论文写作的结果包。

______________________________________________________________________

## 收口窗口(04.21-04.24)

### 核心目标

- 处理 Week16 暴露的缺口，避免月底留下“结果有但不可引用”的尾巴。
- 把月度成果转换成下月 issue 队列和论文章节输入。

### 收口任务

- 复核 `docslice --lint`、索引、topic view 与新增 SID 的一致性。
- 复核实验结果的复算性，补齐缺失 manifest、配置快照和图表元信息。
- 根据实际完成度，将未完成项拆成下一月 issue，并明确 blocked-by 关系。
- 对照 `new-algorithm-open-questions.md`，把仍未回答的问题单独列为“研究风险/下一步”。

______________________________________________________________________

## 建议 issue 拆分主线（供后续立 issue 使用）

### 文档主线

- A1：新算法 SSOT 重写与 SID 方案
- A2：索引再生、topic view 更新与 docslice warning 清零
- A3：实验/证据目录与模板文档冻结

### 编码主线

- B1：RuntimeState / BeliefState 契约与快照持久化
- B2：运行时状态更新器
- B3：动作选择器与恢复闭环接入
- B4：候选重排序与默认建议修正
- B5：动态无 belief-state / Lite belief-state 双基线实现

### 实验与证据主线

- C1：任务集与高代价步骤冻结
- C2：四组方法统一实验矩阵
- C3：指标聚合与分层分析
- C4：案例证据与失败分析
- C5：evidence-index 与论文结果包

______________________________________________________________________

## Go/No-Go 检查点

- G1（2026-03-30）：新算法是否已经纳入 SSOT，并可被 `docslice` 稳定检索。
- G2（2026-04-06）：Lite `belief-state` 契约与更新逻辑是否已跑通，且可跨 snapshot 恢复。
- G3（2026-04-13）：动态无 belief-state 与 Lite belief-state 两条实现是否都可运行并通过关键回归测试。
- G4（2026-04-20）：四组方法的统一实验矩阵是否已形成可复算结果与可追溯证据。
- G5（2026-04-24）：月度结果包是否已经足够支撑下一轮 issue 拆分与论文写作。

## 主要风险与应对

- 风险1：文档写了新算法，但没有进入索引与 topic view，后续仍不可检索
  - 应对：把 `index.json/topic_views.json/docslice --lint` 作为 Week13 必达项，不允许只改正文不改索引。
- 风险2：实现过快进入控制流改造，破坏 FSM 或角色边界
  - 应对：先做 Week14 契约与 shadow 输出，再在 Week15 接入动作选择。
- 风险3：belief-state 收益不明显，结果退化成规则系统
  - 应对：强制保留“动态无 belief-state”对照组，避免只和静态基线比较。
- 风险4：实验结果有数字但证据链不完整，后续难以写论文或 issue
  - 应对：Week13 先冻结 evidence-index 结构，Week16 再集中生成结果包。

## 可追溯性约定

- 每个 issue 至少绑定一个代码或文档路径，以及一个实验或报告产物。
- 每个关键结论必须可追溯到：`任务集版本 -> 配置 -> EventLog -> TaskSnapshot -> 聚合指标 -> 图表/案例`。
- 所有月度成果优先落地在：
  - 设计规范：`../thesis-project.design/docs/design/`
  - 索引与检索：`../thesis-project.design/docs/index/`
  - 计划与 issue 依据：`../thesis-project.design/plan/`
  - 运行与实验产物：`output/`、`reports/`
