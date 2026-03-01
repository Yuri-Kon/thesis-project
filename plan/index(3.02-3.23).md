# Week 10-12(3.02-3.23)规划

> Date Range:
>
> - 开始：2026-03-02
> - 结束：2026-03-23
>
> 当前基础（截至 2026-03-02）：
>
> - 系统已具备 FSM/HITL 主链路与 `retry -> patch -> replan` 恢复机制
> - ToolKG 已作为 Planner 的工具事实来源，具备可插拔 LLM Provider 基础
> - `docs/algorithm-and-llm/core-algorithm-define.md` 与 `train-llm.md` 已重写为后续计划与训练依赖

## 三周总目标（Result-Oriented）

在 2026-03-23 前，形成三个可验收成果：

- R1：Workflow CandidateSet v1 可用（Top-K + score_breakdown + risk/cost gate + default recommendation）
- R2：Workflow 准确性评估基线可复现（离线/在线指标口径统一，至少 1 轮对比报告）
- R3：Planner 训练 MVP 跑通（数据抽取 -> SFT 基线 -> 评估 -> 回退策略）

## 成果验收口径（全局）

- Plan schema 合法率达到目标阈值（见 Week 12）
- 候选可执行率可度量且有基线对比
- `PendingAction -> Decision -> EventLog` 审计链完整可回放
- 三周成果包含代码/配置/文档/报告四类产物，且可追溯

______________________________________________________________________

## Week 10(03.02-03.08)

### 主题：Workflow 准确生成能力的最小闭环（CandidateSet v1）

### 核心目标

- 将“单候选输出”推进为“候选集决策输出”
- 建立可执行性校验与风险/成本门控的最小实现
- 产出可用于 HITL 展示与决策的结构化候选

### 本周 Issue 列表

- W10-01 CandidateSetOutput 契约与字段对齐
- W10-02 Planner Top-K 候选生成最小实现
- W10-03 候选打分与门控（score/risk/cost）
- W10-04 Candidate 校验器（schema + I/O + tool 可用性）
- W10-05 HITL 展示字段联调与最小演示

### 关键 Issue 设计

| 模块              | Issue                                    | 具体工作内容                                                                                                                          | 验收标准                                               | 追溯点                                                                |
| :---------------- | :--------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------ | :----------------------------------------------------- | :-------------------------------------------------------------------- |
| Models/Contracts  | W10-01 CandidateSetOutput 契约与字段对齐 | 明确 Top-K 候选字段：`structured_payload/score_breakdown/risk_level/cost_estimate/explanation/default_recommendation`；补齐兼容性约束 | 契约可被 Planner 输出与 API/HITL 消费，schema 校验通过 | `src/models/contracts.py`，`src/models/validation.py`，`tests/unit/`  |
| Planner           | W10-02 Planner Top-K 候选生成最小实现    | 在 plan/patch/replan 路径输出可排序候选集（建议 K=3）                                                                                 | 同输入可稳定返回候选集且字段完整                       | `src/agents/planner.py`，`tests/unit/test_planner_agent.py`           |
| Planner/Safety    | W10-03 候选打分与门控（score/risk/cost） | 实现最小打分规则与 HITL gate 阈值；给出默认建议                                                                                       | 风险高或低置信场景可正确进入 WAITING\_\*               | `src/agents/planner.py`，`src/agents/safety.py`，`tests/integration/` |
| Workflow          | W10-04 Candidate 校验器                  | 增加候选可执行性硬约束检查（工具存在、I/O 闭包、参数合法）                                                                            | 不合法候选不进入执行分支                               | `src/workflow/`，`src/models/validation.py`，`tests/unit/`            |
| API/Frontend/Docs | W10-05 HITL 展示字段联调与最小演示       | 在 PendingAction 展示候选摘要、风险和成本；完善演示说明                                                                               | 可通过 UI/接口看到候选差异并提交决策                   | `src/api/`，`docs/demo/README.md`，`examples/`                        |

### Week 10 可交付物

- CandidateSetOutput v1（含验证器）
- 至少 1 条“Top-K 候选 -> HITL 决策 -> 状态推进”可演示链路
- 候选字段口径文档（供 Week11/12 训练数据复用）

______________________________________________________________________

## Week 11(03.09-03.15)

### 主题：恢复策略强化 + 训练数据引擎落地

### 核心目标

- 将 patch/replan 细化为分层恢复策略并可度量
- 建立训练数据抽取、清洗与质量门禁流程
- 形成 SFT 可用数据集 v1

### 本周 Issue 列表

- W11-01 Patch/Replan 分层策略实现
- W11-02 恢复链路可观测性增强
- W11-03 日志到训练样本抽取脚本
- W11-04 训练数据质量门禁（schema/缺失/去重/切分）
- W11-05 SFT 数据集 v1 冻结与说明

### 关键 Issue 设计

| 模块             | Issue                            | 具体工作内容                                                                        | 验收标准                          | 追溯点                                                                                 |
| :--------------- | :------------------------------- | :---------------------------------------------------------------------------------- | :-------------------------------- | :------------------------------------------------------------------------------------- |
| Planner/Workflow | W11-01 Patch/Replan 分层策略实现 | 按“参数级 -> 工具级 -> 结构级”优先级生成 patch；失败升级 replan，优先 suffix replan | 恢复路径可解释，且与 FSM 规则一致 | `src/agents/planner.py`，`src/workflow/patch_runner.py`，`src/workflow/plan_runner.py` |
| Observability    | W11-02 恢复链路可观测性增强      | 补齐恢复相关事件字段（失败类型、候选ID、决策来源、恢复层级）                        | 事件可支持训练样本反查与审计对账  | `src/storage/`，`src/api/`，`tests/integration/`                                       |
| Data/Script      | W11-03 日志到训练样本抽取        | 从 Task/StepResult/PendingAction/Decision/EventLog 生成统一训练样本                 | 抽取结果可复现且可回溯到原任务    | `scripts/`，`output/`，`docs/algorithm-and-llm/`                                       |
| Data/Validation  | W11-04 数据质量门禁              | 实现样本 schema 检查、关键字段缺失检查、重复样本去重、时间切分                      | 不合格样本可识别并输出统计报告    | `scripts/`，`tests/unit/`，`output/`                                                   |
| Docs             | W11-05 数据集 v1 冻结            | 产出字段字典、抽取流程、样本统计、已知偏差说明                                      | 可直接作为 Week12 SFT 输入        | `docs/algorithm-and-llm/`，`docs/impl/`                                                |

### Week 11 可交付物

- Patch/Replan 分层策略最小可用实现
- 训练数据引擎 v1（抽取+清洗+门禁）
- SFT 数据集 v1 与数据说明文档

______________________________________________________________________

## Week 12(03.16-03.23)

### 主题：Planner 训练 MVP + 对比评估 + 成果固化

### 核心目标

- 跑通 SFT 基线并完成第一轮评估
- 建立线上回退门槛与灰度策略
- 形成可答辩的三周成果包（实现+指标+报告）

### 本周 Issue 列表

- W12-01 SFT/QLoRA 基线训练跑通
- W12-02 离线评估与外部基线对比
- W12-03 双路推理与回退阈值接入
- W12-04 端到端演示与审计链复核
- W12-05 三周成果报告与下一阶段计划

### 关键 Issue 设计

| 模块            | Issue                       | 具体工作内容                                                              | 验收标准                                           | 追溯点                                                      |
| :-------------- | :-------------------------- | :------------------------------------------------------------------------ | :------------------------------------------------- | :---------------------------------------------------------- |
| Training        | W12-01 SFT 基线训练         | 使用 Week11 数据集完成一次 SFT/QLoRA 基线训练并保存模型与配置             | 训练流程可复现，关键参数有记录                     | `scripts/`，`configs/`，`output/`                           |
| Evaluation      | W12-02 离线评估与对比       | 评估 schema 合法率、可执行率、patch 最小性、suffix replan 前缀保持率      | 形成“自研模型 vs 外部基线”对比表                   | `scripts/`，`output/`，`docs/algorithm-and-llm/`            |
| Planner/Runtime | W12-03 双路推理与回退阈值   | 接入“自研默认 + 外部回退”策略（schema连续失败/执行率下降/连续失败超阈值） | 回退触发条件可测且不破坏 FSM/HITL                  | `src/agents/`，`src/workflow/`，`tests/integration/`        |
| System Demo     | W12-04 端到端演示与审计复核 | 演示完整链路：候选生成 -> HITL 决策 -> 执行恢复 -> 报告输出               | `PendingAction -> Decision -> EventLog` 链路可回放 | `docs/demo/README.md`，`output/`，`examples/`               |
| Docs/Report     | W12-05 成果报告与后续路线   | 沉淀成果包：目标完成度、指标结果、问题清单、下阶段任务                    | 2026-03-23 前提交可评审文档                        | `docs/algorithm-and-llm/`，`../thesis-project.design/plan/` |

### Week 12 可交付物

- Planner 训练 MVP（数据->训练->评估->回退）
- 一份可复现对比评估报告
- 一条可演示、可审计、可恢复的端到端工作流成果链路

______________________________________________________________________

## 三周风险与应对

- 风险1：候选质量不足，导致训练数据噪声高
  - 应对：Week10 先固化候选校验器与字段完整性门禁
- 风险2：训练结果不稳定，线上不可直接替换
  - 应对：坚持双路架构，默认保留外部回退
- 风险3：评估口径不统一导致结果不可比较
  - 应对：Week10 冻结指标口径，Week12 只按统一口径出报告

## Go/No-Go 检查点

- G1（03-08）：CandidateSet v1 是否可演示且可校验
- G2（03-15）：训练数据引擎与数据集 v1 是否冻结
- G3（03-23）：SFT 基线 + 对比评估 + 回退策略是否闭环

______________________________________________________________________

## 可追溯性约定

- 每个 Issue 至少绑定一个代码/脚本路径 + 一个文档/报告产物
- 所有关键结论必须可追溯到：配置、日志、模型版本、评估结果
- 产物默认落地在 `output/`（运行）与 `docs/`（说明）
