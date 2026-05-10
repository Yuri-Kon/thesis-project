# 第八章：总结与展望（草稿）

> 状态：初稿 · 2026-05-11 · 目标章节文件 `chapters/08-conclusion.tex`

---

## 8.1 论文工作总结

本文面向 de novo 蛋白质设计场景，针对固定流水线在工具异构性、高代价调用风险和失败不可恢复三个维度上的不足，设计并实现了一个以多 Agent 协作和自适应工作流规划为核心的智能科研工作流系统。论文的主要工作沿着"需求分析—总体设计—系统实现—系统测试—策略实验"的主线展开。

在需求分析阶段，本文明确了蛋白质设计工作流在工具组合、运行时调整、人工确认和失败恢复四个维度的功能缺口，建立了六类功能需求（任务接入与约束确认、候选计划生成与工具链选择、工作流执行与工具适配、人在环路与决策审查、运行时自适应与恢复决策、结果汇总与审计）和五项非功能需求（可追溯性、可扩展性、可靠性与可恢复性、安全与边界控制、实验可复现性）。

在总体设计阶段，本文提出了五层分层架构（输入层、智能规划层、执行层、安全与汇总层、资源层），以有限状态机（FSM）作为任务生命周期的唯一控制源，将蛋白质设计业务组织为六个可组合、可替换的能力阶段。核心算法 CEBRA-WP（Constraint- and Evidence-aware Belief-guided Recovery-adaptive Workflow Planning）嵌入智能规划层和运行时控制层，以 Lite belief-state 的五个核心状态量（p_success、p_structural_failure、recovery_margin、expected_remaining_cost、evidence_sufficiency）作为运行时决策的信息基础，通过静态多目标评分、后验目标评分、信念更新、运行时重排序和恢复动作选择五个计算阶段，实现 continue / patch_local / suffix_replan / stop 四类动作的恢复自适应。四种递增策略组（Static Top-1、Fixed Threshold Gate、Dynamic Recovery、Lite Belief-State）为实验分离各机制的贡献提供了可控的消融框架。

在系统实现阶段，本文基于 Python 3.12 + FastAPI + Pydantic 构建后端，React 19 + TypeScript + Vite 构建前端，自定义 Workflow/FSM 实现工作流控制。后端通过 15 个 API 端点覆盖任务录入的渐进式确认链路（draft → supplement → confirm → task）、HITL 的结构化交互接口（PendingAction/Decision）和事件时间线的审计查询。前端以四页面工作台（Dashboard、Task Builder、Task Detail、Event Timeline）组织操作员视图。CEBRA-WP 通过 RuntimeEvaluator、belief-state 更新器和 Planner 候选生成逻辑在工程中落地，四种策略模式共享同一代码基。工具适配器通过 BaseToolAdapter 抽象接口和 AdapterRegistry 注册机制实现 ESMFold、OpenFold、ProteinMPNN、ProtGPT2 等工具的统入接入。

在系统测试阶段，本文通过 13 个测试用例（TC-S01 至 TC-S13）和 30 余个验证点对系统进行了多层次验证。结果表明：API 合约稳定（15 个工具能力 ready/degraded/unavailable 状态明确）、HITL 决策边界严格（缺失候选 ID、重复决策和错误绑定均被拒绝）、FSM 迁移合法且终态不可变、快照持久化在进入等待态前完成（恢复后不自动推进）、恢复路径可达（retry → patch → replan 分层验证通过）、安全边界有效（forbidden_motif 确定性阻断和审计链路完整）。Web 前端四个关键页面和 CLI 核心命令可用，12 个测试用例通过，1 个（CLI timeline/report 子命令）部分通过。

在策略实验阶段，本文在 12 个任务 × 4 组策略 × 多次 repeat 的 84-run 消融矩阵中验证了 CEBRA-WP 的可行性、必要性和增量价值。lite_belief_state 在所有 21 个运行中持续产生了有效的 RuntimeState 和 action_utility 输出，证明了算法机制的完整性和持续可观测性。fixed_threshold_gate 在缺少运行时重排序的条件下触发了 6 次真实 patch 和额外的 7 次高代价调用，体现了固定门控"拦截-修复"模式的代价。lite_belief_state 和 dynamic_no_belief_state 相比 fixed_threshold_gate 节省了 28.6% 的高代价调用。三个 FAILED 案例（fixed 的 patch 循环耗尽、lite 的预算感知但未打破循环、dynamic 的候选验证失败）提供了比 81 个成功案例更丰富的机制洞察。

---

## 8.2 主要贡献

本文的主要贡献可归纳为以下四点。

**（1）构建了一个面向高代价科研工作流的可恢复、可审计的自动化系统。** 系统不是对现有蛋白质设计工具的简单封装，而是在多工具之间建立了以 FSM 为控制骨架、以 PendingAction/Decision 为 HITL 契约、以 TaskSnapshot 为恢复基础设施的工作流控制层。84-run 实验矩阵中 81/84 的完成率证明了工程闭环的稳定性，13 个测试用例覆盖了从 API 合约到安全边界的完整验证链。

**（2）提出了 CEBRA-WP 自适应工作流规划算法，并在工程中完整实现。** 该算法以 Lite belief-state 为核心，将静态候选评分与运行时观测（StepResult、SafetyResult、预算消耗）结合，通过信念更新、后验目标评分、运行时重排序和动作效用估计四个阶段，为高代价工作流的 continue / patch / replan / stop 决策提供可解释、可审计的信息基础。四种策略组的消融设计使各机制的贡献可以被实验分离和量化分析。

**（3）通过 84-run 实验矩阵提供了 CEBRA-WP 机制可行性和成本控制优势的证据。** Lite belief-state 在所有运行中持续产生有效的信念状态观测（runtime_state_observable_rate=1.0），证明了算法机制的完整性和持续可用性。lite_belief_state 和 dynamic_no_belief_state 相比 fixed_threshold_gate 节省 28.6% 高代价调用，体现了运行时自适应决策在成本控制上的价值。几个 FAILED 案例不是实验的失败，而是机制边界的有价值展现——fixed 的 patch 循环证明了无运行时重排序的局限，lite 的预算感知展示了信念状态的动态行为，dynamic 的候选验证失败证明了校验机制的必要性。

**（4）建立了从需求到测试的完整工程证据链。** 论文的证据体系覆盖了需求定义（6 类功能需求 + 5 项非功能需求）、设计规范（AGENT_CONTRACT.md 系统不变性）、实现产物（15 个 API 端点、4 个前端页面、7 类模块）、测试用例（13 个 TC、30+ 个 SV）、实验数据（84 runs、4 组策略、12 个指标维度）和审计材料（EventLog、Snapshot、候选 metadata）。所有结论均可通过证据编号（EVD-API-*、EVD-TEST-*、FIG-SV-*、EVD-LOG-*）追溯到原始文件。

---

## 8.3 不足与局限

本文的工作在以下方面存在不足。

**实验统计效力有限。** 84-run 矩阵虽然覆盖了 12 个任务和 4 组策略，但 medium/standard 层的 n=2 使统计检验的效力受限。dynamic_no_belief_state 和 lite_belief_state 在核心指标均值上完全相同，这可能是样本量不足以揭示真实差异的结果，也可能是两种策略在当前任务集上确实等价。论文以"趋势"和"方向"表述实验结论，不做统计显著性推断，这一立场是方法论上的诚实，但也意味着"CEBRA-WP 的性能优势"尚未得到统计上的严格确认。

**恢复机制覆盖不完整。** 四组策略在 84 次运行中均未触发 replan 事件，patch 事件仅出现在 fixed_threshold_gate 组。t5（设计用于诱发 patch 的任务）和 t8（设计用于诱发安全阻断的任务）在矩阵实验中未产生预期行为。这意味着论文对恢复机制的验证主要依赖 focused test（确定性触发场景），而非真实的多任务统计。replan 路径的完整验证是当前证据链中最显著的缺口。

**缺少与外部方法的系统对比。** 论文实验仅覆盖内部四组消融，未与 ReAct-style、ToT-style 或 Reflexion-style 等通用 Agent 范式进行对照。虽然论文选择了不以此作为通过条件（实验设计书明确将外部基线列为"可选"），但这一缺失限制了对"CEBRA-WP 是否在通用方法之外提供了独特价值"这一问题的回答范围。

**原型系统的生产化程度有限。** 任务记录使用内存 TASK_STORE 保存，未实现数据库持久化；工具知识图谱为静态 JSON 文件，不支持动态更新；前端工作台未实现完整的 3D 结构可视化；远程服务的健康检查和自动故障切换依赖外部 tmux 会话管理。这些限制不影响论文的系统验证和实验结论，但将它们表述为"原型实现"而非"生产系统"是必要的诚实。

---

## 8.4 未来工作展望

在上述不足的基础上，未来工作可从以下方向展开。

**扩大实验规模并引入更强的压力条件。** 建议将实验矩阵扩大到 n≥4、任务种类增加到 12-16 类，并在任务设计中显式引入确定性失败条件（如序列长度故意短于结构预测工具的最小要求、预算上限故意低于必需成本、安全约束故意与工具能力冲突）。更强的压力条件有望在矩阵实验中诱发 replan 和 stop 事件，使恢复路径的全谱验证从 focused test 扩展到统计层面。

**补全外部基线对照。** 建议将 lite_belief_state 与 ReAct-style（单轨迹、思考-行动循环）、ToT-style（多分支搜索）和 Reflexion-style（文本反思恢复）等方法在相同任务集上进行横向对比。外部对照不改变论文对 CEBRA-WP 内部机制的论述，但可以为"CEBRA-WP 提供的结构化 HITL 和可审计恢复是否是通用方法不具备的"这一问题提供证据。

**增强恢复层级之间的 escalation 能力。** 当前 fixed_threshold_gate 在 t2_ubiquitin 上的 patch 循环耗尽后直接进入 FAILED，没有尝试升级到 replan 或 terminal_stop。在 patch 循环中增加 escalation 策略——当同一 PendingAction 的 patch 次数超过上限时自动升级为 replan_confirm，再次超限后推荐 terminal_stop——可以在不增加人工干预的情况下减少 FAILED 中的"循环耗尽"类型。

**推进原型系统向可生产化演进。** 将内存 TASK_STORE 替换为关系数据库或文档数据库，实现服务重启后的任务记录持久化；将 ProteinToolKG 迁移到图数据库，支持动态工具注册和实时能力更新；补充 3D 结构可视化组件；建立远程服务的自动化健康检查和故障切换机制。这些演进不改变系统的核心架构和算法，但可以提升系统在真实科研环境中的可用性和可维护性。

**拓展系统到更广泛的科学工作流场景。** CEBRA-WP 的核心假设——高代价步骤、可失败工具、可恢复前缀、需要可审计的人工审查——不仅适用于蛋白质设计。分子动力学模拟、量子化学计算、基因组分析流水线和材料筛选等科学计算场景同样具有这些特征。将 ToolAdapter 接口和 ProteinToolKG 的设计模式推广到其他科学领域，探索 CEBRA-WP 在蛋白质设计之外的适用性，是一个有价值的研究方向。
