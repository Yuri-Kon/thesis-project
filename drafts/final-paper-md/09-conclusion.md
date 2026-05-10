# 第八章 总结与展望

本文面向蛋白质设计工作流中的工具异构、高代价调用、运行时失败和人工审查需求，设计并实现了一个以多 Agent 协作、工具知识约束和恢复自适应规划为核心的科研工作流系统。系统将已有蛋白质设计工具和远程模型服务组织为可执行、可恢复、可审计的工作流，并在此基础上提出 CEBRA-WP（Constraint- and Evidence-aware Belief-guided Recovery-adaptive Workflow Planning）算法，用于在约束、证据、运行时状态和恢复动作之间建立统一的决策机制。

全文围绕需求分析、系统设计、系统实现、系统验证和策略实验逐步展开。需求分析明确了任务录入、候选计划生成、工具执行、HITL、运行时恢复和结果审计等核心需求；系统设计给出了分层架构、ProteinToolKG、FSM、HITL、核心数据契约和 CEBRA-WP 算法定义；系统实现完成了后端 API、前端工作台、工作流运行时、ToolAdapter、RuntimeEvaluator、快照和事件日志等模块；系统测试通过 13 个测试用例覆盖功能正确性和工程可用性；实验分析基于 `thesis-final-v1-001` 的 84-run 四组消融矩阵，考察了静态规划、固定阈值门控、动态观测和 Lite belief-state / 轻量信念状态四类策略的行为差异。

## 8.1 论文工作总结

在系统设计方面，本文将蛋白质设计任务抽象为受约束的工作流规划问题。任务目标、用户约束、工具能力、输入输出契约、预算信息和运行时观测共同决定候选工作流的生成、筛选和重排序。系统采用 FSM 作为任务生命周期的控制核心，将 `CREATED`、`PLANNING`、`RUNNING`、`WAITING_*`、`SUMMARIZING`、`DONE`、`FAILED` 等状态组织为受控迁移路径；采用 PendingAction/Decision 表示 HITL 决策；采用 EventLog 和 TaskSnapshot 保存状态迁移、恢复动作、运行时状态和审计信息。

在算法设计方面，本文提出 CEBRA-WP，将约束感知、证据感知、Lite belief-state / 轻量信念状态和恢复自适应动作统一到工作流层。算法输入包括任务目标、约束集合、ProteinToolKG、历史状态、观测和 Lite belief-state / 轻量信念状态；算法过程包括候选生成、硬可行性筛选、静态评分、后验目标适配、RuntimeState 更新、候选重排序和恢复动作选择。Lite belief-state / 轻量信念状态包含 `p_success`、`p_structural_failure`、`recovery_margin`、`expected_remaining_cost` 和 `evidence_sufficiency` 等状态量，用于刻画任务在运行时的成功概率、结构性失败风险、恢复余量、剩余成本和证据充分性。

在系统实现方面，本文基于 Python、FastAPI、Pydantic、React 和 TypeScript 完成原型系统。后端提供任务录入、任务生命周期、事件查询、报告查询和人工决策接口；前端工作台包含 Dashboard、Task Builder、Task Detail 和 Event Timeline 等页面；工作流运行时通过 WorkflowContext、PlanRunner、StepRunner、RuntimeEvaluator、PendingAction 和 Snapshot 等模块实现任务推进、工具调用、重试、恢复、等待态和审计记录。工具侧通过 ToolAdapter 抽象封装结构预测、序列生成、质量控制等外部能力，使系统能够在统一契约下接入异构蛋白质设计工具。

在系统验证方面，本文构建了覆盖 API、Web、CLI、FSM、HITL、快照、安全边界、失败恢复和端到端执行的验证体系。13 个测试用例中 12 个通过，1 个 CLI 相关用例部分通过。验证结果表明，系统能够稳定处理任务创建、候选生成、人工确认、工具执行、事件追踪和报告输出；等待态下执行停止、终态不可变、快照恢复后不自动推进等关键不变性均有测试或日志证据支撑。

在实验分析方面，本文使用 12 个 task_keys、4 组策略、84 次运行构成消融矩阵。实验结果显示，84 runs 中 81 个进入 DONE，3 个进入 FAILED；`lite_belief_state` 组 21/21 runs 产生有效 RuntimeState，runtime_state_observable_rate 为 1.0000；`fixed_threshold_gate` 组触发 6 次真实局部修补，高代价调用总数为 28；`dynamic_no_belief_state` 与 `lite_belief_state` 的高代价调用总数均为 20，低于 `fixed_threshold_gate` 组。上述结果支持 CEBRA-WP 机制已实现且可观测、固定阈值门控恢复存在额外成本、Lite belief-state / 轻量信念状态能提供运行时决策解释信息等结论。

## 8.2 主要贡献

本文的第一项贡献是构建了一个面向蛋白质设计工作流的可恢复、可审计原型系统。系统围绕任务接入、工具知识约束、候选计划、执行状态、人机决策、恢复路径和审计记录建立完整工程闭环。第六章的系统验证和第七章的 84-run 实验共同说明，该系统能够支撑多任务、多策略的批量运行和结果追踪。

第二项贡献是提出并实现了 CEBRA-WP 工作流规划算法。该算法定位于工作流层的候选筛选、运行时重排序和恢复动作选择。CEBRA-WP 将 ProteinToolKG 中的工具能力、schema、输入输出、成本、风险和证据状态纳入候选评估，并通过 Lite belief-state / 轻量信念状态将运行时观测转化为可解释的决策依据。

第三项贡献是建立了从系统验证到策略消融的证据链。系统验证部分使用 TC-S01 至 TC-S13 覆盖 API、状态机、HITL、快照、恢复和安全边界；实验分析部分使用表 7-1 至表 7-8 固定实验配置、主结果、分层结果、机制增量、成本分析、机制可观测性、失败归因和证据产物。论文中的主要结论均能回溯到测试日志、API 响应、EventLog、Snapshot、run-level result 或聚合 CSV。

第四项贡献是对 CEBRA-WP 的机制价值给出了有边界的实验分析。实验清楚展示了 Lite belief-state / 轻量信念状态的 RuntimeState、budget pressure 和 action utility 的持续可观测性；同时，fixed_threshold_gate 的局部修补循环和额外高代价调用说明固定阈值门控恢复会带来可测成本。这种结果有助于将算法贡献从“成功率单点比较”转向“高代价工作流中的恢复控制、成本意识和审计解释”。

## 8.3 局限性

本文仍存在若干局限。首先，实验规模有限。`thesis-final-v1-001` 包含 84 runs，每组 21 runs，能够支撑机制分析和方向性比较，但统计效力仍有限。尤其是 `dynamic_no_belief_state` 与 `lite_belief_state` 在 success_rate 和 high_cost_call_mean 上完全相同，说明当前任务集对二者性能差异的放大能力有限。

其次，恢复机制在矩阵实验中的覆盖不完整。84-run 矩阵中真实局部修补仅出现在 `fixed_threshold_gate` 组，且四组均未触发真实重规划或后缀重规划。第六章 focused tests 已验证 `suffix_replan` 和 `terminal_stop` 路径可达，但第七章批量实验主要提供局部修补和高代价调用方面的证据。未来需要通过更强的失败诱导任务补足重规划、`stop` 和 escalation 的矩阵级证据。

第三，系统仍处于原型阶段。当前任务记录以运行时任务表和日志/快照文件为主，数据库持久化需要进一步补充；ProteinToolKG 以静态配置为主，动态工具注册和在线能力更新能力有限；前端结构区域主要提供产物入口和报告展示；远程服务的自动健康管理和故障切换仍可进一步增强。这些限制主要影响系统在长期科研环境中的部署能力。

第四，本文实验以内部消融为主，外部基线对比仍有扩展空间。当前四组策略能够分离静态选择、固定阈值门控、动态观测和 Lite belief-state / 轻量信念状态的机制差异；后续可与 ReAct-style、Tree-of-Thought-style 或 Reflexion-style 等通用 Agent 方法在同一任务集上进行系统对照。外部对照可以进一步说明 CEBRA-WP 在结构化约束、HITL、恢复审计和高代价控制方面的相对价值。

## 8.4 未来工作展望

后续工作首先可以扩大实验规模并增强压力任务设计。未来实验可增加任务种类、repeat 数和失败诱导条件，例如构造更强的工具不可用、预算冲突、schema 错误、I/O 闭包错误和安全约束冲突场景，使 `patch_local`、`suffix_replan`、`terminal_stop` 和 safety block 在批量矩阵中均能被触发。这样可以将当前以 focused tests 为主的恢复路径验证扩展为统计层面的恢复能力分析。

其次，可以补充外部 Agent 基线和蛋白质设计前沿方法对比。ReAct、Tree of Thoughts 和 Reflexion 等通用 Agent 方法适合构成工作流决策层基线；ProteinGuide、ProteinZero 等近期预印本则提示了蛋白质生成中属性引导、在线反馈和自改进方向[@proteinguide2025; @proteinzero2025]。未来可以将 CEBRA-WP 与这些方向结合，比较结构化工作流控制、属性引导生成和在线反馈优化之间的关系。

第三，可以增强恢复策略的 escalation 机制。当前局部修补循环耗尽后进入 FAILED，说明系统能够识别恢复失败，但仍缺少从局部修补到后缀重规划再到终止止损的自动升级策略。未来可在 RuntimeEvaluator 中引入恢复次数、重复失败类型、预算压力和候选多样性等因素，当同类局部修补多次失败时自动提升到 `suffix_replan` 或 `stop` 候选，从而降低循环恢复带来的时间和高代价调用开销。

第四，可以推进原型系统的工程化演进。任务状态可以迁移到关系数据库或文档数据库；ProteinToolKG 可以迁移到图数据库或可热更新的服务；事件日志、快照和实验产物可以统一纳入实验追踪平台；前端可以补充更完整的结构可视化和候选对比视图；远程模型服务可以加入自动探活、降级切换和调用配额管理。这些改进将提升系统在真实科研工作流中的可维护性和长期运行能力。

最后，CEBRA-WP 的工作流层思想可扩展到蛋白质设计之外的科学计算场景。结构化候选生成、硬约束筛选、运行时状态估计、恢复动作选择和审计追踪，同样适用于分子动力学模拟、材料筛选、基因组分析和其他高代价科学工作流。面向更广泛任务建立标准化 benchmark 和可复现实验套件，例如参考结构设计基准中对任务、指标和证据的组织方式[@pdbstruct2023]，是进一步验证该类恢复自适应工作流规划方法的重要方向。
