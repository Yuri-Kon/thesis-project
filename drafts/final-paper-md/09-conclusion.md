# 第八章 结论

本文面向蛋白质设计工作流中的工具异构、高代价调用、运行时失败和人工审查需求，设计并实现了一个以多 Agent 协作、工具知识约束和恢复自适应规划为核心的科研工作流系统。系统将既有工具和远程模型服务组织为可执行、可恢复、可审计的工作流，并提出 CEBRA-WP，在约束、证据、运行时状态和恢复动作之间建立决策机制。

全文依次讨论课题背景、相关理论、需求、设计、实现、验证和实验。需求分析明确任务录入、候选计划、工具执行、HITL、恢复和审计需求；系统设计给出分层架构、ProteinToolKG、FSM、HITL、数据契约和 CEBRA-WP；系统实现完成后端 API、前端工作台、运行时、工具适配、快照和事件日志；测试覆盖 13 个用例，实验基于 thesis-final-v1-001 的 84-run 消融矩阵。

在系统设计方面，本文把蛋白质设计任务视为受约束的工作流规划问题。任务目标、用户约束、工具能力、输入输出契约、预算和运行时观测都会影响候选生成、筛选与重排序；FSM 负责控制 CREATED、PLANNING、RUNNING、WAITING_\*、SUMMARIZING、DONE、FAILED 等状态，PendingAction/Decision、EventLog 和 TaskSnapshot 则用于支撑人工确认与审计。

在算法设计方面，本文给出， CEBRA-WP，将约束感知、证据感知、Lite belief-state / 轻量信念状态和恢复自适应动作统一到工作流层。算法输入包括任务目标 $g$、约束集合 $C$、ProteinToolKG $K$、历史状态 $h_{t}$、观测 $o_{t}$ 和 Lite belief-state / 轻量信念状态 $x_{t}$；算法过程包括候选生成、硬可行性筛选、静态评分、后验目标适配、`RuntimeState` 更新、候选重排序和恢复动作选择。Lite belief-state / 轻量信念状态包含 $p_{\text{succ}}$、$p_{\text{sf}}$、$r_{\text{rec}}$、$c_{\text{rem}}$ 和 $e_{\text{suf}}$ 等状态量，用于刻画任务在运行时的成功概率、结构性失败风险、恢复余量、剩余成本和证据充分性。

系统实现方面，本文基于， Python、FastAPI、Pydantic、React 和 TypeScript 完成原型。后端提供任务录入、任务生命周期、事件、报告和人工决策接口；前端提供 Dashboard、Task Builder、Task Detail 和 Event Timeline；运行时模块负责任务推进、工具调用、重试、恢复、等待态和审计记录，ToolAdapter 则封装外部工具能力。

系统验证覆盖 API、Web、CLI、FSM、HITL、快照、安全边界、失败恢复和端到端执行。13 个测试用例中 12 个通过，1 个 CLI 相关用例部分通过；等待态执行停止、终态不可变、快照恢复后不自动推进等关键不变性均有测试或日志证据。

实验使用 12 个 task_keys、4 组策略和 84 次运行。结果显示，81 个 DONE、3 个 FAILED；`lite_belief_state` 组 21/21 runs 产生 `RuntimeState`；`fixed_threshold_gate` 触发 6 次真实局部修补，高代价调用总数为 28；`dynamic_no_belief_state` 与 `lite_belief_state` 高代价调用总数均为 20。结果支持“CEBRA-WP 机制可观测”“固定阈值门控恢复存在额外成本”“Lite belief-state 提供决策解释信息”等判断。

本文有以下几项贡献。第一项贡献是构建可恢复、可审计的蛋白质设计工作流原型。系统围绕任务接入、工具知识约束、候选计划、执行状态、人机决策、恢复路径和审计记录形成工程闭环。

第二项贡献是提出并实现 CEBRA-WP。该算法定位于工作流层候选筛选、运行时重排序和恢复动作选择，将工具能力、schema、成本、风险和证据状态纳入候选评估，并用 Lite belief-state 解释运行时决策。

第三项贡献是把系统验证和策略消融串联为一条证据链。TC-S01 至 TC-S13 覆盖 API、状态机、HITL、快照、恢复和安全边界；第七章表 7-1 至表 7-8 则固定实验配置、主结果、机制增量、成本分析、失败归因和证据产物。

第四项贡献是对， CEBRA-WP 的机制价值作边界化分析。实验展示 `RuntimeState`、budget pressure 和 action utility 的可观测性，也显示 `fixed_threshold_gate` 的局部修补循环会带来额外成本。因此，本文将算法贡献限定在恢复控制、成本意识和审计解释，而非单纯成功率提升。

本文仍有局限。thesis-final-v1-001 包含 84 runs，每组 21 runs，可支撑机制分析和方向性比较，但统计效力有限；`dynamic_no_belief_state` 与 `lite_belief_state` 在 success_rate 和 high_cost_call_mean 上相同，说明任务集对二者差异的放大能力不足。

恢复机制覆盖也不完整。84-run 矩阵中真实局部修补只出现在 `fixed_threshold_gate` 组，四组均未触发真实重规划或后缀重规划。第六章 focused tests 已验证 `suffix_replan` 和 `terminal_stop` 可以达到，但矩阵级证据仍需通过更强失败诱导任务补足。

系统仍处于原型阶段。任务记录主要依赖运行时任务表和日志/快照文件，数据库持久化、ProteinToolKG 动态更新、前端结构展示、远程服务探活与故障切换仍有改进空间。

本文实验以内部消融为主，外部基线仍可扩展。后续可在同一任务集上加入 ReAct-style、Tree-of-Thought-style 或 Reflexion-style 等通用 Agent 方法，以比较 CEBRA-WP 在结构化约束、HITL、恢复审计和高代价控制方面的相对价值。

后续实验还应扩大规模，并增加压力任务，例如工具不可用、预算冲突、schema 错误、I/O 闭包错误和安全约束冲突，使 `patch_local`、`suffix_replan`、`terminal_stop` 和 safety block 都能在批量矩阵中被触发。

作为后续比较对象，外部 Agent 基线与蛋白质设计前沿方法仍有必要纳入讨论。ReAct、Tree of Thoughts、Reflexion 可用于构造工作流决策层基线；ProteinGuide、ProteinZero 等预印本则展示了属性引导、在线反馈和自改进方向[27,28]。

恢复策略还需要更清晰的 escalation 机制。未来可在 RuntimeEvaluator 中引入恢复次数、重复失败类型、预算压力和候选多样性等因素，使同类局部修补多次失败时自动提升到 `suffix_replan` 或 stop，减少循环恢复开销。

原型系统仍有工程化空间，后续可推进任务状态数据库化、ProteinToolKG 热更新、事件日志与实验产物统一追踪、前端结构可视化和远程模型服务配额管理。

从更长周期看，CEBRA-WP 的工作流层思想可扩展到分子动力学、材料筛选、基因组分析等高代价科学计算场景。后续可结合标准化 benchmark 和可复现实验套件，进一步验证恢复自适应工作流规划方法。
