# 附录 A 系统验证证据与测试用例设计明细

本附录主要用于补充第六章“系统测试与验证”中的测试用例设计细节。正文第六章只保留测试策略、覆盖矩阵和关键验证结论；本附录列出每条测试用例的设计目的、触发方式、预期结果、证据编号和结论边界，便于后续答辩、复核或继续整理终稿时追溯。

本附录中的证据编号与开发目录 ../thesis-project.dev/docs/system-validation/evidence-index.md、test-case-table.md 保持一致。证据编号只说明材料类型和可追溯位置，不将前端截图编号直接写成论文正文图号。

## A.1 证据链路与材料范围

<table style="width:100%;">
<caption><p>图 A-1 系统验证证据链路</p></caption>
<colgroup>
<col style="width: 17%" />
<col style="width: 19%" />
<col style="width: 22%" />
<col style="width: 17%" />
<col style="width: 22%" />
</colgroup>
<thead>
<tr>
<th style="text-align: center;"><strong>设计</strong></th>
<th style="text-align: center;"><strong>执行</strong></th>
<th style="text-align: center;"><strong>归档</strong></th>
<th style="text-align: center;"><strong>追踪</strong></th>
<th style="text-align: center;"><strong>论文使用</strong></th>
</tr>
</thead>
<tbody>
<tr>
<td>测试用例设计<br />
TC-S01 至 TC-S13</td>
<td>执行入口<br />
API / Web / CLI / pytest / 实验运行</td>
<td>证据归档<br />
EVD-API、EVD-TEST、EVD-CLI、FIG-SV、EVD-LOG、EVD-EXP</td>
<td>状态追踪<br />
EventLog / Snapshot / Report</td>
<td>论文结论<br />
正文只使用可被证据支撑的边界化表述</td>
</tr>
</tbody>
</table>

| **证据前缀** | **证据类型** | **数量/范围** | **主要内容** | **论文使用方式** |
|----|----|----|----|----|
| EVD-API | API 响应 JSON | 8 项 | /health、/capabilities/readiness、任务详情、事件、报告和 pending action 接口响应 | 支撑 API 合约、任务状态和事件可追溯性。 |
| EVD-TEST | pytest 执行日志 | 4 组 | API/Web smoke、FSM/HITL/快照、安全恢复、CLI 测试结果 | 支撑自动化测试通过情况和异常边界。 |
| EVD-CLI | CLI 输出日志 | 4 项 | intake schema、task show、timeline show、report show 输出 | 支撑 CLI 主路径可用和部分命令限制。 |
| FIG-SV | 前端验证截图 | 18 张 | Dashboard、Task Builder、Task Detail、Event Timeline 页面截图 | 作为系统验证截图证据，不作为正文正式图号。 |
| EVD-LOG | EventLog / Snapshot / Report 样本 | 8 组 | 等待态、决策、恢复、`terminal_stop`、报告产物和快照样本 | 支撑 FSM、HITL、恢复和审计链路。 |
| EVD-EXP | 实验矩阵与端到端聚合 | 4 项 | smoke run、clean run、action distribution、实验聚合结果 | 支撑端到端流程、工具链执行和第七章实验基础。 |

表 A-1 系统验证证据编号规则

| **材料类别** | **主要位置** | **用途** |
|----|----|----|
| 系统验证索引 | ../thesis-project.dev/docs/system-validation/evidence-index.md | 统一登记 EVD-API、EVD-TEST、EVD-CLI、FIG-SV、EVD-LOG、EVD-EXP 的文件路径和说明。 |
| 测试用例表 | ../thesis-project.dev/docs/system-validation/test-case-table.md | 记录 TC-S01 至 TC-S13 的用例编号、覆盖验证点和执行结果。 |
| 验证检查清单 | ../thesis-project.dev/docs/system-validation/system-validation-checklist.md | 记录系统验证项、检查结果和剩余限制。 |
| 前端截图 | ../thesis-project.dev/docs/system-validation/06-ui-screenshots/ | 保存 Dashboard、Task Builder、Task Detail 和 Timeline 页面截图。 |
| 日志与快照样本 | ../thesis-project.dev/data/logs/、../thesis-project.dev/data/snapshots/ | 保存任务事件、运行时快照和恢复链路证据；固定样本复制于 docs/system-validation/04-data-consistency/。 |
| 实验聚合结果 | ../thesis-project.dev/docs/experiment/ 及实验输出目录 | 保存 smoke/clean run 和最终实验矩阵的聚合结果。 |

表 A-2 系统验证材料目录

## A.2 测试用例设计明细

表 A-3 和表 A-4 按 TC-S01 至 TC-S13 展示系统测试用例。为避免正文过度像测试文档，附录将“设计目的与触发方式”“预期结果”“实际结果与证据”“结论边界”放在同一组表格中呈现。

| **用例** | **设计目的与触发** | **预期结果** | **实际结果与证据** | **结论边界** |
|----|----|----|----|----|
| TC-S01 环境与能力就绪 | 验证 API 服务是否启动正常，并确认系统能够动态暴露工具能力状态。触发方式为调用 /health 与 /capabilities/readiness。 | /health 返回 status=ok；readiness 返回每个工具能力的状态、错误类别和恢复建议。 | 通过。/health 返回任务数、工具数量和路径信息；readiness 返回 15 条能力记录，其中 ready、degraded、unavailable 均有明确说明。证据：EVD-API-01、EVD-API-02。 | 证明当前环境下能力可观测，不代表所有外部工具均已安装或可用。 |
| TC-S02 API 合约与任务录入 | 验证 Task Intake、任务创建、任务详情、事件和报告接口的契约边界。触发 schema、草稿、confirm、互斥创建模式和典型查询接口。 | schema 可返回；缺字段或互斥模式被拒绝；DONE 任务可读取报告；DONE 任务没有 pending actions；事件 API 可读取磁盘日志。 | 通过。API 自动化测试 71 passed；schema 返回完整字段注册表；错误请求返回明确异常；真实实验任务 events 可从日志读取。证据：EVD-TEST-01、EVD-API-03 至 EVD-API-08。 | 证明 API 合约和主要异常边界可用，不等同于所有未来字段组合都已穷尽测试。 |
| TC-S03 计划候选生成 | 验证 PlannerAgent 生成的候选计划是否包含必要契约字段，并保持职责边界。 | 候选包含 candidate_id、评分分解、风险、成本、解释和来源引用；Planner 不执行工具、不直接改变任务状态。 | 通过。focused suite 107 passed；候选字段完整，低置信度场景可生成 PendingAction(plan_confirm)。证据：EVD-TEST-02、EVD-LOG-04。 | 证明候选契约完整，不证明候选在所有科学任务上均为最优。 |
| TC-S04 HITL 决策一致性 | 验证 PendingAction 与 Decision 的绑定、一次性决策和等待态执行停止。 | 合法决策被应用；缺字段返回 400；重复决策返回冲突；错误绑定被拒绝；等待态不继续调用工具。 | 通过。PendingAction 创建、决策应用和等待退出均有事件记录；前端候选/决策区域可展示。证据：EVD-TEST-02、FIG-SV-15、EVD-LOG-08。 | 证明 HITL 运行时契约正确，不评价人工决策本身是否科学最优。 |
| TC-S05 FSM 状态迁移 | 验证有限状态机的合法迁移、非法迁移拒绝和终态不可变性。 | 合法迁移成功；非法迁移被拒绝；终态不可变；`terminal_stop` 接受后进入 FAILED 并保留审计链。 | 通过。状态迁移测试覆盖关键路径；`terminal_stop` 事件链可追溯。证据：EVD-TEST-02、EVD-LOG-03。 | 证明状态控制规则有效，不代表运行中永远不会出现外部进程中断。 |
| TC-S06 快照持久化与恢复 | 验证进入等待态前是否保存 PendingAction、事件和 TaskSnapshot，并确认恢复后不自动推进。 | 进入等待态前写入 pending action、事件和快照；恢复后仍处于等待态；runtime state 保存在 artifacts 中。 | 通过。快照包含 pending_action_id、completed_step_ids、plan_version 和 artifacts.runtime_state。证据：EVD-TEST-02、EVD-LOG-01 至 EVD-LOG-03。 | 证明本地快照恢复语义正确，不等同于分布式容灾或多节点一致性。 |
| TC-S07 Web 前端可用性 | 验证 Dashboard、Task Builder、Task Detail 和 Event Timeline 是否能展示核心状态和交互入口。 | 页面正常加载；任务状态、pending action、事件和报告信息与 API 保持一致。 | 通过。Dashboard、Task Builder、Task Detail、Timeline 共 18 张截图；Web smoke test 通过。证据：FIG-SV-01 至 FIG-SV-18、EVD-TEST-01。 | 截图和 smoke test 证明关键页面可用，不代表全面浏览器兼容性和无障碍测试。 |

表 A-3 系统测试用例设计明细（TC-S01 至 TC-S07）

| **用例** | **设计目的与触发** | **预期结果** | **实际结果与证据** | **结论边界** |
|----|----|----|----|----|
| TC-S08 CLI 可用性 | 验证命令行入口是否能支持 schema 查看、任务查看和报告/时间线访问。 | schema 和 task show 输出有效内容；timeline/report 应能展示对应信息或暴露当前限制。 | 部分通过。intake schema --json 输出完整字段注册表；task show 输出任务状态和能力 readiness；CLI 自动化测试 16 passed；timeline show 和 report show 当前仅输出 usage。证据：EVD-CLI-01 至 EVD-CLI-04、EVD-TEST-04。 | CLI 主路径可用，但 timeline/report 子命令尚未完整实现；正文中必须保留“部分通过”。 |
| TC-S09 端到端任务流程 | 验证从任务输入到 DONE 终态和 DesignResult 的完整路径。运行 t8 smoke run 和 t9 clean run 并检查报告接口和聚合指标。 | 任务完成并进入 DONE；每个 DONE 任务有 StepResult；report 返回有效结果；未完成任务请求 report 返回 404。 | 通过。t8 四组 smoke 和 t9 四组 clean run 共 20 次运行全部 DONE，success rate、schema valid rate 和 executable plan rate 均为 1.0。证据：EVD-EXP-01、EVD-LOG-05、EVD-API-06。 | 证明系统可承载端到端任务，不代表最终蛋白质具有湿实验验证的生物学功能。 |
| TC-S10 异常输入与安全边界 | 验证异常输入、forbidden motif、安全 warn/block 和工具调用阻断。 | block 阻止工具调用；allow 不误阻断；warn 放行但记录风险标记和安全事件。 | 通过。4 个确定性 focused tests 覆盖安全判定到执行阻断链路。证据：EVD-TEST-03。 | 证明安全机制路径可达，不宣称自动覆盖所有生物安全风险；矩阵实验中安全任务未充分触发 block。 |
| TC-S11 工具链执行与 I/O | 验证工具适配器调用、输入输出边界和候选可执行性检查。 | 工具调用成功；无 dummy 输入；无 provider payload validation error；无效候选在执行前被结构化拒绝。 | 通过。t8/t9 共 20 次运行中相关工具调用均为 success；I/O 边界测试可拒绝错误候选。证据：EVD-TEST-03、EVD-EXP-01。 | 证明当前工具适配路径有效，不代表所有第三方工具版本和部署环境都已覆盖。 |
| TC-S12 失败恢复流程 | 验证 retry、局部修补、后缀重规划的分层恢复路径。 | 可重试失败先进入有界重试；耗尽后转入恢复逻辑；`patch_local` / `suffix_replan` 候选进入 HITL；恢复事件可统计。 | 通过。确定性 retry patch 样本产生 patch_event_count=1、first_pass_success=False、replan_event_count=0；分层局部修补和后缀重规划样本可追溯。证据：EVD-TEST-03、EVD-LOG-01 至 EVD-LOG-03。 | 证明恢复路径存在并可审计，不代表所有失败类型都能恢复为 DONE。 |
| TC-S13 恢复止损与审计链路 | 验证 `terminal_stop` 作为恢复动作时是否通过 FSM/HITL 进入 FAILED，并保留审计链。 | 决策应用后任务进入 FAILED 终态；事件日志记录 WAITING_ENTER、DECISION_APPLIED、WAITING_EXIT 等关键事件。 | 通过。`terminal_stop` 审计链完整记录，可通过事件接口还原。证据：EVD-TEST-02/03、EVD-LOG-03/04。 | 证明止损路径受控，不代表 FAILED 一定是系统错误；也可能是策略性终止。 |

表 A-4 系统测试用例设计明细（TC-S08 至 TC-S13）

## A.3 验证内容与论文结论对应关系

| **验证内容** | **主要用例** | **可支持的论文结论** | **不应扩大的表述** |
|----|----|----|----|
| API 服务、能力 readiness 和任务录入 | TC-S01、TC-S02 | 系统具备可访问的 API 边界，能够动态暴露工具能力，并对任务录入进行结构化约束。 | 不写成所有外部工具在任意部署环境下均可用。 |
| 候选生成与 Planner 职责边界 | TC-S03 | Planner 能生成包含评分、风险、成本和解释字段的候选计划，并保持不执行工具的职责边界。 | 不写成候选计划在科学意义上一定最优。 |
| HITL、FSM 和快照恢复 | TC-S04、TC-S05、TC-S06 | HITL、状态迁移、终态不可变性和等待态恢复均有测试与日志证据支撑。 | 不写成生产级高可用或分布式容灾。 |
| Web 与 CLI 入口 | TC-S07、TC-S08 | Web 工作台核心页面可用，CLI 核心命令可用但部分子命令存在限制。 | 不写成完整 CLI 报告系统或全面前端兼容性测试。 |
| 安全、恢复和止损 | TC-S10、TC-S12、TC-S13 | retry、`patch_local`、`suffix_replan`、`terminal_stop`、safety warn/block 等控制路径可达且可审计。 | 不写成能自动判断所有生物安全风险，或所有失败都可恢复。 |
| 端到端执行与工具链 I/O | TC-S09、TC-S11 | 系统能够承载从任务输入到 DesignResult 的端到端执行，工具调用和 I/O 边界有验证记录。 | 不写成已完成湿实验验证或证明候选蛋白真实有效。 |

表 A-5 验证内容与可支持结论

## A.4 附录与正文衔接

第六章正文以表 6-1 至表 6-4 作为主要论证材料，集中说明系统测试策略、验证覆盖、证据类型和关键结论。本附录补充测试用例级别的设计细节和证据追溯，用来说明每个测试用例不仅有结果记录，也有明确的设计目的、触发方式、预期结果和结论边界。
