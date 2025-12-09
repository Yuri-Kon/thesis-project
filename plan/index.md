# 进度规划 2025-12-08 

## 进度明细

### 已完成内容(截至12.08)

| 模块                    | 工作内容                                                                                                        | 完成情况 | 备注                                  |
| --------------------- | ----------------------------------------------------------------------------------------------------------- | ---- | ----------------------------------- |
| 数据契约 Models           | ProteinDesignTask, Plan, PlanStep, StepResult, SafetyResult, DesignResult, WorkflowContext, Replan/Patch 契约 | ✔ 完成 | 字段、类型完全对齐设计文档                       |
| 时间戳工具                 | now_iso() 修复弃用 utcnow                                                                                       | ✔ 完成 | 使用 timezone-aware 时间 ISO8601        |
| 任务状态机                 | TaskStatus（CREATED → DONE，全 FSM）                                                                            | ✔ 完成 | 与 system-implementation-design 完全一致 |
| TaskRecord/StepRecord | 全局任务记录结构                                                                                                    | ✔ 完成 | 为 API/DB 提供统一结构                     |
| Agent 框架（接口）          | Planner / Executor / Safety / Summarizer 接口定义                                                               | ✔ 完成 | 后续将补充真实逻辑                           |
| Agent 最小实现            | Planner（dummy 计划）、Executor（dummy 执行）、Summarizer（dummy 汇总）                                                   | ✔ 完成 | 可完整跑通 demo                          |
| workflow              | run_task_sync 串联所有 Agent                                                                                    | ✔ 完成 | 可生成 DesignResult + 文件报表             |
| TaskAPI               | POST /tasks, GET /tasks/{task_id}                                                                           | ✔ 完成 | 可通过 Swagger UI 调试                   |
| 最小Demo                | 成功执行任务、生成报告文件                                                                                               | ✔ 完成 | 项目首次可执行的 pipeline                   |

---

## 后续阶段计划(12.09之后)

以下是未来三周的任务安排(Phase1)

### Week 3（12.09 – 12.15）—— 核心算法框架

> 目标：把简单的Executor重构为真正的 Core Algorithm v1, 先不依赖 Nextflow / LangGraph

| 时间段 | 模块 | 具体任务 | 关键技术点 / 输出 |
|--------|------|----------|-------------------|
| A1     | StepRunner v1 | 将现有单步执行逻辑抽象为 `StepRunner`：解析 PlanStep、组装输入、执行（目前仍是 dummy）、生成 StepResult | `src/workflow/step_runner.py` 或 `Executor.run_step` 内部重构；保证完全契约化使用 `StepResult` |
| A2     | PlanRunner v1 | 实现 `PlanRunner`：顺序遍历 Plan.steps，调用 StepRunner，写入 WorkflowContext；支持多步 Plan（即便暂时只有 1～2 步） | `src/workflow/plan_runner.py`；从“for 循环里写死逻辑”升级为可复用的 Plan 执行器 |
| A3     | 状态机接入（简单版） | 在 PlanRunner 中按执行阶段更新 TaskStatus：CREATED → PLANNING → PLANNED → RUNNING → SUMMARIZING → DONE/FAILED | 把你设计文档中的 FSM 第一次真正写进代码，而不是只在文档里 |
| A4     | Safety Pipeline 框架 | 不做复杂策略，先实现 SafetyAgent 接口的调用链：task_input → pre_step → post_step → final_result，返回 SafetyResult 占位 | `src/agents/safety.py` 中写好接口和伪实现，PlanRunner/StepRunner 正式接上 Safety |
| A5     | v0.3.0 打标签 | 整体重构完成后，标记版本 v0.3.0：**“核心算法骨架 + 安全调用链 + 多步执行框架”** | 一个明确的里程碑版本，用于之后对比 v0.2.0 |


### Week 4（12.16 – 12.22）—— 失败处理 + Patch/Replan 框架 + 适配器基类

> 目标：让核心算法具备 出错时要知道做什么 的能力，同时搭建适配器框架

| 时间段 | 模块 | 具体任务 | 关键技术点 / 输出 |
|--------|------|----------|-------------------|
| B1     | 失败分类逻辑 | 在 StepRunner / PlanRunner 中区分：可重试错误 / 不可重试错误 / 工具异常 / 安全阻断；统一用枚举或错误码表示 | 为后续 PatchPlanner / ReplanPlanner 提供“决策依据”，不再只是 boolean 成功/失败 |
| B2     | PatchPlanner 框架 | 定义 PatchPlanner 接口：输入 PatchRequest，输出 PlanPatch；实现一个简单策略（例如：同一工具多试一次、换成备选工具） | `src/agents/planner_patch.py` 或合并在 PlannerAgent 内部，**先实现规则版，不用 LLM** |
| B3     | ReplanPlanner 框架 | 定义 ReplanRequest → 新 Plan（suffix）的接口；初版策略可以是：从失败 step 索引到最后，重新生成后缀计划 | `src/agents/planner_replan.py`；同样先规则版 |
| B4     | FSM 扩展 | 将 WAITING_PATCH / PATCHING / WAITING_REPLAN / REPLANNING 状态植入 PlanRunner，根据 Patch/Replan 流程切换 | TaskStatus 真正覆盖完整 FSM，不只是 RUNNING/DONE |
| B5     | BaseToolAdapter + Registry | 定义 `BaseToolAdapter` 抽象类，提供 `resolve_inputs`、`run_local` 方法；实现 `ADAPTER_REGISTRY` + `register_adapter()` / `get_adapter()` | `src/adapters/base.py`；Executor 以后全部通过 Adapter 调用工具 |
| B6     | v0.3.1 打标签 | 版本：**“核心算法支持失败路径 + Patch/Replan 框架 + 适配器骨架”** | 为后续真实适配器实现打基础 |

### Week 5（12.23 – 12.29）—— 适配器简单实现 + ToolKG 最小版 + Demo 验证

> 目标：做出几个简单但结构正确的适配器实现，用来给核心算法跑完整流程

| 时间段 | 模块 | 具体任务 | 关键技术点 / 输出 |
|--------|------|----------|-------------------|
| C1     | ESMFoldAdapter（mock） | 实现 `esmfold_adapter.py`：根据输入序列输出 fake pdb_path 和假 pLDDT 等指标，结构上与未来真实版一致 | 让 StepRunner → Adapter → Summarizer 这一链路**结构定型** |
| C2     | ProteinMPNNAdapter（mock） | 实现 `protein_mpnn_adapter.py`：输入结构 / 约束，输出假序列集合 | 方便后续多步骤 Plan：MPNN → ESMFold |
| C3     | ProteinToolKG 最小版 | 写 `protein_tool_kg.json` 和 `kg_client.py`，至少包含 esmfold/mpnn 两个工具节点，支持按 capability 查找 | Planner 可以不再写死工具名，而是“从 KG 中选工具” |
| C4     | Planner v2（规则 + KG 驱动） | Planner 从 `goal/constraints` 决定 pipeline：例如“有起始结构 → 走 MPNN 再 ESMFold；只有序列 → 直接 ESMFold”等 | 将“选择工具 + 排顺序”第一次写成代码（规则版） |
| C5     | Demo：核心算法 + 多步骤 + 适配器 | 运行一个多步骤任务，例如：`设计序列 → 预测结构 → 汇总结果`，全程走 StepRunner/PlanRunner/Safety/Patch 框架 | 这次 Demo 重点展示“核心算法 + 适配器架构”，即便工具结果仍是 mock |
| C6     | v0.4.0 打标签 | 版本：**“核心算法 v1 完成 + 适配器 mock 实现 + KG 驱动 Planner”** | 这是你 12 月底可以非常踏实交差的一个版本 |

## 未来两个月的整体规划

### 阶段1(1月)： 真实工具接入 + 核心算法v2

| 时间跨度 | 目标 | 关键技术节点 | 说明 |
|----------|------|--------------|------|
| 1 月上旬 | **接入第一个真实工具**（建议 ESMFold） | - 把 `ESMFoldAdapter` 从 mock 改成真正调用本地/容器/Nextflow 管线<br>- 解决模型路径、显存、运行时间等问题 | 不要求一开始就很快，但要能完整跑完一条真实链路 |
| 1 月中旬 | 核心算法 v2：稳定性 & 错误处理 | - 在 StepRunner/PlanRunner 里加入超时、重试次数上限<br>- 对工具 / IO / 安全错误做统一分类 & 统计<br>- 确保 Patch/Replan 流程在真实工具下能跑通 | 这一步让系统从“能跑”变成“靠谱” |
| 1 月中下旬 | 第二个工具接入（如 ProteinMPNN 或简单 RDKit 性能指标） | - 实现第二个真实 Adapter<br>- 让 Planner 真的组合多个工具，而不是单工具串行 | 这是“多工具协作设计”的关键节点 |
| 1 月底 | v0.5.x 版本：**“核心算法 v2 + 至少 1~2 个真实工具”** | - 可向导师演示真实蛋白预测/简单设计流程<br>- 可以开始收集初步实验数据 | 这一版就是你所谓“比较完整的系统雏形” |

### 阶段 2（2 月）：工作流优化 + LLM（可选）+ 实验与论文

| 方向 | 时间建议 | 关键技术节点 | 说明 |
|------|----------|--------------|------|
| 工作流优化 | 2 月上旬 | - 把现在的同步 `run_task_sync` 抽象成一个简单“任务队列 + 状态轮询”模式<br>- 如有精力，可尝试用 LangGraph/LangChain Workflow 重写部分执行流 | 这块可以只做到“代码结构更清晰、可扩展”，不强求集群级别复杂度 |
| LLM Planner（可选） | 2 月上旬～中旬 | - 设计基于 ToolKG 的 Prompt 模板，让 LLM 生成 Plan JSON<br>- 初版可以与规则 Planner 并存（LLM 先做建议，再由规则层校验） | 这是“基于大模型驱动”的亮点实现，可视时间情况调整深度 |
| LLM Summarizer（可选） | 2 月中旬 | - 使用 LLM 读取 WorkflowContext / StepResult，生成可读性更好的任务总结报告 | 对答辩展示 & 论文附录都很加分 |
| 实验与论文 | 2 月全月穿插 | - 设计 2–3 组实验：不同工具组合、不同规划策略、不同安全约束下的表现<br>- 统计指标：成功率、pLDDT/其他打分、运行时间等<br>- 同步撰写论文系统设计/实现部分 | 这阶段系统功能不必再大改，以验证与写作为主 |

## 关键技术节点一览

### 关键技术节点总览

| 节点 | 预计时间 | 简要说明 |
|------|----------|----------|
| 核心算法 v1（StepRunner + PlanRunner + Safety 框架） | 12 月中旬 | 从“简单 for 循环执行”升级为有上下文、有状态、有安全检查的执行核心 |
| Patch/Replan 框架成型 | 12 月中旬～下旬 | 让系统在工具失败时不直接崩，而是尝试局部修复或后缀重规划 |
| 适配器架构 + ToolKG 驱动 Planner | 12 月底 | 工具接入从“写死”改为“可插拔 + 图谱驱动选择” |
| 第一个真实 Adapter（推荐 ESMFold） | 1 月上旬 | 系统第一次对接真实计算工具，输出真实结构 |
| 核心算法 v2（真实环境下的超时/重试/错误处理） | 1 月中旬 | 让 Patch/Replan/Safety 在真实工具调用中真正发挥作用 |
| 第二个真实工具接入（MPNN 或 RDKit） | 1 月中下旬 | 让系统具备“多工具协作设计”的真实链路 |
| 工作流优化（队列/状态轮询或 LangGraph） | 2 月上旬 | 对用户/调用方来说，系统从“函数”变成“服务” |
| （可选）LLM Planner / Summarizer | 2 月中旬 | 体现“大模型驱动的多 Agent 协作”这一毕设主题 |
