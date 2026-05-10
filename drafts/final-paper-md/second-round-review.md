# 第二轮修改审查报告

审查日期：2026-05-11

审查范围：`drafts/final-paper-md/02-introduction.md` 至 `09-conclusion.md`，以及 `appendix/appendix-a-validation-evidence.md`。本报告只检查、统一和标注问题，不直接改写正文。

## 1. 总体评价

当前论文已经具备完整初版正文，主要论证方向清楚：从蛋白质设计工作流问题出发，提出系统需求、总体设计、CEBRA-WP 算法、工程实现、系统验证和实验分析。第二轮最需要优先处理的问题有五类：

1. 术语中英文混用较多，尤其是 HITL/人在环路/人在环决策、Lite belief-state/轻量信念状态/RuntimeState、ToolKG/ProteinToolKG/工具知识图谱、patch/replan/stop/terminal_stop 等术语。建议先统一术语表，再做正文替换。
2. 图表编号总体连续且文件存在，但第五章代码清单在 `tables.md` 中的登记顺序与正文实际编号不一致，属于高优先级问题。
3. 参考文献引用键均能在 `references.md` 中找到，且参考文献条目基本都被正文使用；但少数背景性或实验性表述仍建议补充来源或内部证据路径。
4. 章节衔接总体顺畅，但第二章“相关系统与本文定位”到第三章需求分析、第五章实现到第六章验证、第七章实验到第八章总结之间可增加轻量过渡句。
5. 个别段落句子偏长，且“不直接”“不能”“不是”等否定式边界说明较多。此类问题多数可留到最终语言精修阶段处理，但涉及结论强度的句子应优先检查。

优先处理顺序建议：先修正代码清单索引和术语表，再补充必要引用/证据路径，然后处理章节过渡句，最后做语言精修。

## 2. 术语统一表

| 当前出现的不同写法 | 建议统一写法 | 出现位置 | 修改理由 | 是否需人工确认 |
|---|---|---|---|---|
| 人在环路、人在环决策、HITL、Human-in-the-loop | 首次写作“人在环决策（Human-in-the-loop, HITL）”，后文统一使用“HITL”或“人在环决策” | `04-requirements-analysis.md:65`、`05-system-design.md:39`、`06-system-implementation.md:74`、`07-testing-validation.md:60` | 同一机制存在多种中文称呼，容易显得概念不稳定 | 否 |
| Lite belief-state、轻量信念状态、信念状态、RuntimeState、运行时状态 | 理论概念统一为“Lite belief-state / 轻量信念状态”；实现对象统一为“RuntimeState”；泛称用“运行时状态” | `03-related-work.md:47`、`04-requirements-analysis.md:73`、`05-system-design.md:156`、`08-experiments-analysis.md:122` | 需要区分算法状态概念与工程模型对象 | 否 |
| ToolKG、ProteinToolKG、工具知识图谱、工具能力图 | 泛称“ToolKG / 工具知识图谱”；本文具体实例统一为“ProteinToolKG” | `03-related-work.md:25`、`04-requirements-analysis.md:29`、`05-system-design.md:32`、`06-system-implementation.md:306` | 泛称与项目实例需稳定区分 | 否 |
| 大语言模型 Agent、LLM Agent、多 Agent、Agent | 首次写作“大语言模型 Agent（LLM Agent）”；多角色系统统一为“多 Agent 协作” | `02-introduction.md:9`、`03-related-work.md:35`、`05-system-design.md:22`、`06-system-implementation.md:21` | 中文、英文和缩写混用，首次定义后应稳定 | 否 |
| de novo、De novo、de novo 蛋白质设计 | 统一为“de novo 蛋白质设计”；标题或图题中也保持小写 `de novo` | `02-introduction.md:5`、`03-related-work.md:9`、`05-system-design.md:57` | 专有拉丁短语应统一大小写 | 否 |
| patch、局部修补、patch_local、修补 | 动作名保留代码形式 `patch_local`，中文解释统一为“局部修补” | `04-requirements-analysis.md:62`、`05-system-design.md:66`、`07-testing-validation.md:96`、`08-experiments-analysis.md:120` | 算法动作与中文叙述需要一一对应 | 否 |
| replan、后缀重规划、整体重规划、重规划 | 动作名 `suffix_replan` 对应“后缀重规划”；泛称“重规划”仅在不区分模式时使用 | `04-requirements-analysis.md:69`、`05-system-design.md:243`、`07-testing-validation.md:110` | 防止把 suffix replan 与 full replan 混为一谈 | 否 |
| stop、terminal_stop、止损、终止型候选 | 算法动作写 `stop`；系统候选写 `terminal_stop`；中文统一解释为“终止型重规划候选” | `04-requirements-analysis.md:69`、`05-system-design.md:276`、`07-testing-validation.md:110` | 需要区分算法动作与 FSM/HITL 载体 | 否 |
| fixed_threshold_gate、固定门控、固定阈值门控 | 统一为“固定阈值门控（fixed_threshold_gate）” | `05-system-design.md:318`、`08-experiments-analysis.md:9`、`08-experiments-analysis.md:68` | “固定门控”略口语且不完整 | 否 |
| dynamic_no_belief、dynamic_no_belief_state、动态观测组 | 策略名统一为 `dynamic_no_belief_state`，中文解释为“动态观测无信念状态组” | `08-experiments-analysis.md:47`、`08-experiments-analysis.md:103` | 表 7-2 列名 `dynamic_no_belief` 与正式策略名不一致 | 否 |
| lite_belief、lite_belief_state、Lite belief-state 组 | 策略名统一为 `lite_belief_state`，中文解释为“Lite belief-state 组” | `08-experiments-analysis.md:47`、`08-experiments-analysis.md:138` | 表格列名与正文策略名需一致 | 否 |
| BioPython、Biopython | 建议统一为“Biopython” | `05-system-design.md:37`、`06-system-implementation.md:3`、`03-related-work.md:23` | 参考文献题名和项目常用写法为 Biopython | 否 |
| OpenFold、OpenFold3 REST、OpenFold/OpenFold | 正文背景使用“OpenFold”；实现路径若确为服务名再写“OpenFold3 REST” | `03-related-work.md:19`、`06-system-implementation.md:3` | 需区分论文工具名与项目部署服务名 | 需人工确认 |
| 结构映射、结构预测 | 阶段名称统一为“结构映射”；具体工具能力可写“结构预测” | `03-related-work.md:7`、`05-system-design.md:57`、`08-experiments-analysis.md:107` | 阶段名和工具功能混用，需要边界一致 | 否 |
| 智能规划层、运行时控制层、工作流控制层 | 第四章架构建议固定一种层名，若采用五层架构则全文按该架构命名 | `05-system-design.md:16`、`figures.md:19` | `figures.md` 中图 4-1 解释使用“运行时控制层”等，与正文“五层”命名不完全一致 | 需人工确认 |

## 3. 图表引用问题清单

建议统一格式：图表采用章节编号格式“图 章号-序号”“表 章号-序号”“代码清单 章号-序号”“算法 章号-序号”。正文引用统一写“如图 4-1 所示”“见表 7-5”“代码清单 5-3 展示……”。当前正文主体基本采用该格式。

| 问题位置 | 原文片段 | 问题类型 | 修改建议 |
|---|---|---|---|
| `tables.md:32-36` 与 `06-system-implementation.md:103/132/173/271` | `tables.md` 中代码清单 5-2 为 ToolAdapter，正文中代码清单 5-2 为 WorkflowContext | 代码清单索引与正文编号错位 | 以正文为准修正 `tables.md`：5-2 WorkflowContext，5-3 StepRunner，5-4 PendingAction，5-5 RuntimeEvaluator，5-6 ToolAdapter |
| `tables.md:37` | 代码清单 5-7 构建任务快照 | 有登记但正文未引用 | 保留为“备选代码清单”可以，但建议在 `tables.md` 明确“正文未使用”；若进入正文则放在 5.4.3 |
| `03-related-work.md:57-62` | 图 2-1 技术路线概览 | 图 2-1 当前为可选图，但正文已正式引用 | `figures.md` 中“可作为可选总览图”的说明可改为“已在第二章引用” |
| `05-system-design.md:13` vs `figures.md:19` | 正文图题“系统分层架构”；清单图题“系统五层分层架构” | 图题命名略不一致 | 统一为“系统五层分层架构” |
| `05-system-design.md:43` vs `figures.md:21` | 正文图题“FSM 状态转移”；清单图题“FSM 状态转移图” | 图题命名略不一致 | 统一为“FSM 状态转移图” |
| `05-system-design.md:333` vs `figures.md:25` | 正文图题“UML 核心数据契约”；清单图题“核心数据契约 UML” | 图题词序不一致 | 统一为“核心数据契约 UML” |
| `08-experiments-analysis.md:47` | 表 7-2 列名 `dynamic_no_belief`、`lite_belief` | 表内策略名与正文策略名不一致 | 改为 `dynamic_no_belief_state`、`lite_belief_state`，或在表注说明缩写 |
| `09-conclusion.md:25` | “表 7-1 至表 7-8” | 仅总结性引用，无问题 | 可保留 |

检查结论：正式插图 `figures.md` 中的图 2-1、图 3-1、图 4-1 至图 4-8、图 5-1 至图 5-2、图 7-1 至图 7-2 均已在正文中引用。正文未发现“如下图”“如图所示”这类无编号表达。

## 4. 参考文献引用问题清单

检查结论：正文中出现的 `[@...]` 引用键均能在 `references.md` 中找到。`references.md` 中 R01 至 R26 基本均在正文中至少出现一次。未发现明显“引用了不存在文献”的问题。

| 问题位置 | 原文片段 | 问题类型 | 修改建议 | 是否需要补充来源或人工核对 |
|---|---|---|---|---|
| `02-introduction.md:5` | “蛋白质是生命活动的核心执行分子，其功能通常由三维结构和局部相互作用模式决定……” | 基础性背景无直接来源 | 可保留为学科常识；若最终严格要求，可在段末沿用 AlphaFold/RFdiffusion 背景引用 | 低，人工确认即可 |
| `03-related-work.md:53` | “近期蛋白质设计相关预印本显示，越来越多研究开始关注……” | 2025/2026 预印本趋势判断较概括 | 已引用三篇预印本，建议保持“近期预印本”措辞，不写成行业共识 | 需人工确认措辞强度 |
| `04-requirements-analysis.md:9` | “科学工作流系统能够支持流程定义、任务调度和可复现执行……” | 引用自然，来源充分 | 无需修改 | 否 |
| `05-system-design.md:72` | “Tree of Thoughts 和 Reflexion 等研究说明，多候选搜索与失败反馈能够改善复杂任务求解过程……” | 引用自然，但句子合并多个理论来源 | 建议拆成两句或分别贴近 ToT/Reflexion 的具体作用，避免像后补引用 | 否 |
| `06-system-implementation.md:3` | “蛋白质设计相关能力主要通过 AlphaFold/OpenFold、ESMFold、ProteinMPNN、ProtGPT2、BioPython 等工具或工具适配器接入……” | 工具引用充分，但实现接入状态需与 dev 仓库一致 | 最终精修时核对实际适配器和工具可用状态，避免把可配置工具写成已完整可用 | 需人工确认 |
| `07-testing-validation.md:116` | “t8 四组 smoke run 和 t9 四组 clean run 共覆盖 20 次运行……” | 实验/验证数据来源为内部材料，非文献引用 | 建议在句末补内部证据编号或路径，如 EVD-EXP-01、EVD-LOG-05 已在上下文出现，可更贴近该句 | 是，内部证据来源 |
| `08-experiments-analysis.md:33` | “涉及的公开结构包括 Trp-cage、Villin HP35、GB1、Ubiquitin、Top7 和 de novo oligomer。” | 具体任务集事实缺少内部来源标注 | 建议补充实验矩阵配置来源或 EVD-EXP 编号；不建议新增外部文献，除非任务集确实来自公开基准 | 是，内部证据来源 |
| `08-experiments-analysis.md:118` | “降幅为 28.6%。” | 计算结论来自表 7-5，可由表内数据支持 | 可保留；建议写成“由表 7-5 可计算得出” | 否 |
| `09-conclusion.md:49` | “面向更广泛任务建立标准化 benchmark 和可复现实验套件……” | 展望性表述已有 `[@pdbstruct2023]` | 可保留，注意不要写成本文已完成 | 否 |

## 5. 章节衔接建议

| 章节位置 | 当前功能 | 与前后章节关系 | 当前问题 | 建议过渡句 | 是否建议调整段落顺序 |
|---|---|---|---|---|---|
| 第一章绪论结尾 | 总览论文结构 | 引出第二章技术基础 | 结构完整，无明显突兀 | 无需新增 | 否 |
| 第二章 2.6 至 2.7 | 从相关系统回到本文定位 | 引出第三章需求分析 | 已有“下一章”句，但第二章中对图 2-1 的技术路线说明可更明确服务需求分析 | 可在 2.7 前加：“上述技术基础说明，本文系统需求并非单一工具能力需求，而是跨工具编排、运行时控制和证据追踪的综合需求。” | 否 |
| 第三章 3.1 至 3.2 | 从问题界定进入用户场景 | 图 3-1 后引出角色和场景 | 衔接较好 | 无需新增 | 否 |
| 第三章 3.5 至 3.6 | 需求优先级与边界到小结 | 引出第四章系统设计 | 已明确“下一章” | 无需新增 | 否 |
| 第四章 4.4 至 4.5 | 从六阶段工作流进入 CEBRA-WP | 工作流背景引出算法 | 衔接自然，但 4.5 开头可更明确“为什么单有六阶段不够” | 可加：“六阶段能力分层说明了可选路径，但仍需要一个机制决定何时选择、修补或替换这些路径。” | 否 |
| 第五章 5.5 至 5.6 | 算法工程落点到工具适配 | 从控制逻辑转到工具接口 | 衔接略硬 | 可加：“上述运行时决策最终需要落到具体工具调用，因此还需说明工具适配层如何为 Executor 提供统一边界。” | 否 |
| 第六章 6.8 结尾 | 系统验证总结 | 引出第七章策略实验 | 衔接较好 | 无需新增 | 否 |
| 第七章 7.8 结尾 | 实验结论 | 引出第八章总结 | 当前结尾强调实验边界，但未显式过渡到全文总结 | 可加：“基于上述实验结论与边界，第八章进一步总结本文贡献并讨论后续改进方向。” | 否 |
| 附录 A.4 | 附录与正文衔接 | 支撑第六章 | 衔接清楚 | 无需新增 | 否 |

## 6. 常见语言与规范问题清单

| 原文片段 | 问题类型 | 修改建议 | 修改优先级 |
|---|---|---|---|
| `06-system-implementation.md:3` 整段首段 | 句子过长，包含背景、目标、工具、引用和实现重点 | 拆成 2 至 3 句，分别说明“实现目标”“接入工具”“本文实现重点” | 中 |
| `05-system-design.md:72` “CEBRA-WP 的设计动机来自三个方面。第一……第二……第三……” | 段落过长，理论依据密集 | 拆分为三小段或保留但在最终精修时简化句式 | 中 |
| `08-experiments-analysis.md:5` “本章围绕四个研究问题展开……” | 单句列出四个 RQ，信息密度高 | 可改为列表形式，提升可读性 | 中 |
| `08-experiments-analysis.md:68` “static_top1 在该矩阵中成功率最高，说明任务集中的多数初始候选已经具备较强可执行性。” | 结论可能偏强 | 建议改为“提示该任务矩阵中的多数初始候选……” | 高 |
| `07-testing-validation.md:124` “验证结果表明，系统在……方面均具备可追溯证据。” | 列举过长，略模板化 | 保留结论，但可拆分为“接口/状态/恢复/交互”几类 | 低 |
| `07-testing-validation.md:128` “总体而言，本章验证了系统能够稳定承载……” | “稳定承载”可能偏强 | 改为“能够在本文测试范围内承载……” | 高 |
| `03-related-work.md:53` “越来越多研究开始关注……” | 趋势判断较泛 | 改为“近期预印本中已有工作开始关注……” | 中 |
| `05-system-design.md:55` “算法建议不能绕过……” | 否定式边界说明必要，但频次偏高 | 保留事实，最终语言精修时减少连续否定句 | 低 |
| `04-requirements-analysis.md:115` “不声称自动验证候选蛋白真实生物功能……” | 边界说明必要 | 保留；可移到“边界”段落末尾，不做机械替换 | 低 |
| `08-experiments-analysis.md:177` “CEBRA-WP 的机制链路在批量实验中可执行、可追踪……” | 有证据支持，但应限定实验范围 | 建议加“在当前实验矩阵中” | 高 |
| `09-conclusion.md:31` “实验规模有限……统计效力仍有限。” | 规范，边界意识好 | 保留 | 低 |
| 多处“不是……而是……”结构 | AI 写作痕迹/句式重复 | 最终语言精修时保留关键边界，减少重复句式 | 低 |
| 多处“第一，第二，第三”结构 | 段落结构偏整齐 | 最终语言精修时适度改成自然段过渡 | 低 |

## 7. 建议下一轮修改顺序

1. 先处理结构与引用：
   - 修正 `tables.md` 中第五章代码清单编号与正文不一致的问题。
   - 在第七章任务集、t8/t9 运行、84-run 数据来源处补充更贴近的内部证据路径或证据编号。
   - 检查 2025/2026 预印本相关表述，统一使用“近期预印本”或“相关预印本”。

2. 再处理术语与图表：
   - 按本报告术语统一表建立正式术语表，可写入 `00-writing-rules.md` 或单独维护。
   - 统一 HITL、Lite belief-state、RuntimeState、ProteinToolKG、patch/replan/stop、策略组名称。
   - 统一图题、表题与 `figures.md`、`tables.md` 的命名。

3. 最后进行语言精修：
   - 拆分长句和高密度段落。
   - 降低个别结论强度，如“稳定承载”“说明……已经具备”等。
   - 减少连续否定式边界说明和模板化“第一/第二/第三”段落。
   - 保留事实、结构和引用依据，不做降重式机械替换。
