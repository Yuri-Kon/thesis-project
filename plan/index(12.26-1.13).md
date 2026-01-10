# C 阶段三周执行计划

> 用途：
>
> - 直接作为 **GitHub Project / Issue 列表**
> - 或作为 **每周周报 / 里程碑跟踪表**

______________________________________________________________________

## Week 1（12.26 – 12.30）

### 主题：系统级重构落地（v0.3）

| Issue ID | 日期 | 模块 | Issue 标题 | 关键工作内容 | 产出/验收标准 |
|--------|------|------|-----------|-------------|--------------|
| #1 | 12.26 | Core / FSM | Task 状态与 FSM 重构 | 拆分 ExternalStatus / InternalStatus；保留 PATCHING / REPLANNING | FSM 与 architecture.md 完全一致 |
| #2 | 12.26 | Core / FSM | FSM 驱动点统一 | 状态变更仅允许发生在 Planner / Executor / Decision | 无隐式状态跳转 |
| #3 | 12.27 | Model | PendingAction 模型落地 | action_type + candidates + explanation | 可手动构造 WAITING\_\* |
| #4 | 12.27 | Model | Decision 模型落地 | DecisionChoice + 合法性校验 | 决策结构完整 |
| #5 | 12.27 | Model | TaskSnapshot 最小结构 | state / plan_version / step_index / artifacts | 可用于恢复 |
| #6 | 12.28 | Infra | EventLog 结构定义 | HITL 相关事件类型 | 事件可审计 |
| #7 | 12.28 | Infra | 关键节点强制写日志 | WAITING\_\* / DECISION_APPLIED 前后约束 | 可回放 |
| #8 | 12.29 | API | GET /tasks/{id} 重构 | WAITING\_\* 返回 pending_action | curl 可用 |
| #9 | 12.29 | API | Decision 提交接口 | POST /pending-actions/{id}/decision | FSM 正确推进 |
| #10 | 12.30 | Release | v0.3.0 收敛与对齐 | 文档与代码一致 | tag v0.3.0 |

**Week 1 可交付物：**

- ✅ v0.4.0
- ✅ FSM + HITL + Snapshot 结构完整

______________________________________________________________________

## Week 2（12.31 – 01.06）

### 主题：第一个真实工具接入（ESMFold）

| Issue ID | 日期 | 模块 | Issue 标题 | 关键工作内容 | 产出/验收标准 |
|--------|------|------|-----------|-------------|--------------|
| #11 | 12.31 | Tool | ESMFold 接入方法与运行假设确认 | 本地 / 容器 / Nextflow 决策 | 接入路径确定 |
| #12 | 01.01 | Tool | ESMFoldAdapter 最小实现 | run() + 输出标准化 | StepResult 正确 |
| #13 | 01.02 | Executor | StepRunner 真实执行 | 执行时间/失败捕获 | artifacts 生成 |
| #14 | 01.03 | Executor | 真实失败场景测试 | 非法输入 / 超时 | WAITING\_\* 触发 |
| #15 | 01.03 | Planner | Patch / Replan 触发验证 | 规则版 Patch / Replan | 人工确认生效 |
| #16 | 01.04 | Summarizer | Summarizer 最小适配 | 基于真实结果输出 | 失败不影响 DONE |
| #17 | 01.05 | Demo | 端到端真实 Demo | 输入→ESMFold→总结 | 全链路跑通 |
| #18 | 01.06 | Release | v0.4.0 交付 | 打 tag + Demo | 可正式演示 |

**Week 2 可交付物：**

- ✅ v0.5.0
- ✅ 一个真实蛋白预测任务 Demo

______________________________________________________________________

## Week 3（01.07 – 01.13）

### 主题：稳定性、恢复与失败治理（远程模型调用 + Planner LLM Provider 前置）

| Issue ID | 日期 | 模块 | Issue 标题 | 关键工作内容 | 产出/验收标准 |
|--------|------|------|-----------|-------------|--------------|
| #19 | 01.07 | Planner | Planner 接入 Nemotron（LLM Provider 可插拔） | - 抽象 Planner LLM Provider（Nemotron / OpenAI / 其他）统一入口<br>- 固定 3 组 planning 用例用于可复现对比（plan 合法性、候选稳定性、解释一致性）<br>- 产出对比日志快照（plan/candidates/explanation/耗时） | - 仅改“模型调用层”，不改 Planner 算法主干<br>- 可通过配置切换 Nemotron 与基线模型，均能产出可用 Plan（schema 合法） |
| #20 | 01.08 | Tool/Infra | 抽象模型调用服务：RemoteModelInvocationService（替代 RemoteESMFoldService） | - 将“远程 ESMFold 服务”上升为通用“模型调用三段式”接口：submit/poll/download<br>- 参考系统既有传递结构：输入来自 step 的 artifacts/inputs 映射；输出落为 StepResult + artifacts（路径/引用）<br>- 默认实现 REST API（POST predict / GET job / GET results），并保留 SSH/SDK 扩展点（仅定义不实现） | - 形成统一接口：`submit_job(payload, task_id) -> job_id`；`poll_status(job_id)`；`download_results(job_id, output_dir)`<br>- 产物可被 Executor/Summarizer 消费：下载文件 + 元数据写入 artifacts 映射 |
| #21 | 01.09 | Infra | Snapshot 恢复验证（覆盖远程作业引用） | - 中断→恢复执行：包含“远程作业 job_id / endpoint / trace 信息”的快照写入与恢复<br>- 验证恢复后能继续 poll / download，不丢上下文 | - 恢复后任务可继续运行（含远程 job 继续轮询/下载）<br>- 快照字段满足可恢复最小上下文（state/plan_version/step_index/artifacts） |
| #22 | 01.10 | API | Decision 幂等性（409）+ 事件审计闭环 | - 重复提交 / 冲突校验：PendingAction 不存在或非 pending 返回 409<br>- 决策提交后强制写入：Decision 记录 + EventLog + Snapshot（前后） | - `POST /pending-actions/{id}/decision` 冲突场景稳定返回 409<br>- 关键审计事件与快照写入可回放（满足“可审计”验收口径） |
| #23 | 01.11 | Executor | 多次失败治理（含远程模型调用失败） | - 统一归一化失败原因：网络/超时/500/结果缺失 → StepResult.failure_code / error_meta<br>- 连续失败触发 Patch/Replan（FSM 正确进入 WAITING\_*）<br>- 验证远程调用失败同样走治理链路 | - 连续失败→触发 Replan/等待确认流程（FSM 正确）<br>- failure 可追踪、可复现（日志/事件/快照一致） |
| #24 | 01.12 | System/Cleanup/Demo | 异常退出与重启 + 清理 + 最终演示准备 | - 重启后状态恢复：EventLog 回放与 Snapshot 对齐<br>- 清理实验代码、补注释与最关键单测（围绕恢复/幂等/失败治理）<br>- 演示脚本：Planner(可切 Nemotron) → 执行(可走远程模型调用) → 触发一次 HITL → 决策恢复 | - 重启后任务状态与执行进度可恢复（含 WAITING\_* 场景）<br>- Demo 可稳定展示端到端链路（含至少一次 HITL） |
| #25 | 01.13 | Release | v0.5.2 交付 | - 打 tag，冻结接口与关键行为<br>- 发布说明：本周新增能力（模型调用抽象 + Planner Nemotron Provider）与稳定性验收项 | - tag v0.4.2<br>- 工程稳定版：稳定、可恢复、可审计；且 Planner/远程模型调用已接入可演示 |

**Week 3 可交付物：**

- ✅ v0.5.2
- ✅ 稳定、可恢复、可审计的真实工具系统
